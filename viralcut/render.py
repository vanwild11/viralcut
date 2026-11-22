"""Рендер вертикальных клипов: кадрирование, фон, субтитры, звук."""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import ffmpeg
from . import custom_fonts, resources
from . import reframe as _reframe
from .reframe import crop_expressions
from .utils import MediaError, probe, run, subprocess_kwargs

ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080), "4:5": (1080, 1350)}


def _esc(path: Path) -> str:
    # экранирование для аргумента фильтра ffmpeg
    p = str(path).replace("\\", "/")
    p = p.replace(":", "\\:").replace("'", "\\'")
    return p


def _bg_chain(w: int, h: int, focus_x: float = 0.5, sharpen: bool = False,
              src: str = "[0:v]") -> str:
    sharp = ",unsharp=5:5:0.7:5:5:0.0" if sharpen else ""
    return (
        f"{src}split=2[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"gblur=sigma=26:steps=2,eq=saturation=0.95[bgb];"
        f"[fg]scale={w}:-2:flags=lanczos{sharp}[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2:shortest=1[base]"
    )


def _crop_chain(w: int, h: int, focus_x: float = 0.5, focus_y: float = 0.45,
                sharpen: bool = False, src: str = "[0:v]") -> str:
    sharp = ",unsharp=5:5:0.7:5:5:0.0" if sharpen else ""
    return (
        f"{src}scale={w}:{h}:force_original_aspect_ratio=increase{sharp},"
        f"crop={w}:{h}:(iw-{w})*{focus_x:.3f}:(ih-{h})*{focus_y:.3f}[base]"
    )


def _auto_chain(w: int, h: int, crop_path: Dict[str, Any], sharpen: bool = False,
                src: str = "[0:v]") -> str:
    """Заливка кадра с плавающим окном по лицам."""
    x_expr, y_expr = crop_expressions(crop_path)
    cw = int(crop_path["crop_w"])
    ch = int(crop_path["crop_h"])
    sharp = ",unsharp=5:5:0.7:5:5:0.0" if sharpen else ""
    return (
        f"{src}crop={cw}:{ch}:x='{x_expr}':y='{y_expr}',"
        f"scale={w}:{h}:flags=lanczos,setsar=1{sharp},format=yuv420p[base]"
    )


def _cut_spans(spans: Optional[List[Dict[str, float]]], clip_start: float,
               clip_end: float) -> List[Dict[str, float]]:
    """Нормализует план склейки без пауз под конкретное окно клипа.

    Возвращает [] если резать нечего (одна сплошная дорожка): тогда рендер идёт
    обычным путём без trim+concat — так дешевле и без лишних швов.
    """
    if not spans:
        return []
    clean: List[List[float]] = []
    for span in sorted(spans, key=lambda s: float(s.get("start", 0.0))):
        start = max(float(clip_start), float(span.get("start", clip_start)))
        end = min(float(clip_end), float(span.get("end", clip_end)))
        if end - start < 0.05:
            continue
        if clean and start - clean[-1][1] < 0.03:
            clean[-1][1] = max(clean[-1][1], end)  # слипшиеся отрезки — без шва
        else:
            clean.append([start, end])
    if len(clean) < 2:
        return []
    covered = sum(end - start for start, end in clean)
    if covered < (clip_end - clip_start) * 0.3:
        # план «съел» почти весь клип — вероятно, ошибочный: не рискуем
        return []
    return [{"start": round(start, 3), "end": round(end, 3)} for start, end in clean]


def _video_spans_graph(segments: List[Dict[str, float]], base: float) -> str:
    """trim+setpts+concat: вход — исходник, выход — метка [vsrc]."""
    parts: List[str] = []
    labels: List[str] = []
    for i, seg in enumerate(segments):
        start = max(0.0, seg["start"] - base)
        end = max(start + 0.02, seg["end"] - base)
        parts.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
    parts.append("".join(labels) + f"concat=n={len(segments)}:v=1:a=0[vsrc]")
    return ";".join(parts)


def _audio_spans_graph(segments: List[Dict[str, float]], base: float,
                       track: int = 0) -> str:
    """atrim+asetpts+concat для звука: выход — метка [aconc]."""
    src = f"[0:a:{max(0, int(track))}]"
    parts: List[str] = []
    labels: List[str] = []
    for i, seg in enumerate(segments):
        start = max(0.0, seg["start"] - base)
        end = max(start + 0.02, seg["end"] - base)
        parts.append(f"{src}atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[a{i}]")
    parts.append("".join(labels) + f"concat=n={len(segments)}:v=0:a=1[aconc]")
    return ";".join(parts)


_HW_CACHE: Dict[str, Any] = {}


def _hw_args(encoder: str, crf: int) -> List[str]:
    """Аргументы аппаратного энкодера (у каждого свои понятия качества)."""
    if encoder == "h264_videotoolbox":
        # q=75 по замеру даёт SSIM 0.9905 против 0.9894 у libx264 CRF19
        return ["-c:v", encoder, "-q:v", "75", "-profile:v", "high",
                "-pix_fmt", "yuv420p"]
    if encoder == "h264_nvenc":
        return ["-c:v", encoder, "-preset", "p5", "-rc", "vbr", "-cq", str(max(19, crf)),
                "-b:v", "0", "-pix_fmt", "yuv420p"]
    if encoder == "h264_amf":
        # AMD: постоянное качество вместо битрейта, иначе сцены «плывут»
        return ["-c:v", encoder, "-quality", "quality", "-rc", "cqp",
                "-qp_i", str(crf), "-qp_p", str(crf + 2), "-pix_fmt", "yuv420p"]

    if encoder == "h264_qsv":
        return ["-c:v", encoder, "-global_quality", str(crf), "-pix_fmt", "nv12"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-profile:v", "high", "-pix_fmt", "yuv420p"]


def _hw_works(encoder: str) -> bool:
    """Реально ли работает железо, а не только «энкодер есть в сборке ffmpeg».

    `-encoders` показывает скомпилированные кодеки: nvenc есть в списке даже на
    ноутбуке без NVIDIA, videotoolbox — не на каждом чипе. Поэтому пробуем
    закодировать несколько кадров и только потом доверяем энкодеру.
    """
    key = f"works:{encoder}"
    if key in _HW_CACHE:
        return bool(_HW_CACHE[key])
    cmd = [ffmpeg(), "-hide_banner", "-v", "error", "-f", "lavfi",
           "-i", "color=c=black:s=1080x1920:r=30:d=0.4", "-frames:v", "8",
           *_hw_args(encoder, 21), "-f", "null", "-"]
    ok = False
    try:
        proc = run(cmd, timeout=15)
        ok = proc.returncode == 0
    except Exception:  # noqa: BLE001 — таймаут/падение трактуем как «не работает»
        ok = False
    _HW_CACHE[key] = ok
    return ok


def _encoder_mode() -> str:
    try:
        from . import settings

        return settings.encoder_mode()
    except Exception:  # noqa: BLE001
        return "auto"


def hw_cached() -> Optional[str]:
    """Только из кэша: не запускает пробный кадр (для /api/health)."""
    return _HW_CACHE.get("value")


def hw_encoder() -> Optional[str]:
    """Аппаратный энкодер для быстрого рендера: videotoolbox / nvenc / qsv.

    Возвращает имя только если ffmpeg его знает И железо отвечает на пробном
    кадре. При любой ошибке рендер один раз повторится на libx264.
    """
    if "value" in _HW_CACHE:
        return _HW_CACHE["value"]
    mode = _encoder_mode()
    if mode == "cpu":
        # пользователь выбрал процессор — GPU не трогаем вовсе
        _HW_CACHE["value"] = None
        return None
    preferred = {"darwin": ["h264_videotoolbox"],
                 "win32": ["h264_nvenc", "h264_amf", "h264_qsv"],
                 "linux": ["h264_nvenc", "h264_vaapi", "h264_qsv"]}.get(sys.platform, [])
    try:
        proc = run([ffmpeg(), "-hide_banner", "-encoders"])
        text = (proc.stdout or "") + (proc.stderr or "")
    except Exception:
        text = ""
    found = next((name for name in preferred if name in text and _hw_works(name)), None)
    if mode == "gpu" and not found:
        print("[render] выбран GPU, но аппаратный энкодер недоступен — остаюсь на CPU",
              file=sys.stderr, flush=True)
    _HW_CACHE["value"] = found
    return found


def _video_args(encoder: Optional[str], crf: int, preset: str) -> List[str]:
    if encoder:
        return _hw_args(encoder, crf)
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-profile:v", "high", "-pix_fmt", "yuv420p"]


def _run_encode(cmd: List[str], duration: float,
                on_progress: Optional[Callable[[float], None]]
                ) -> Tuple[int, List[str], Optional[str]]:
    """Запускает ffmpeg, качает прогресс и сторожит зависание."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            errors="replace", bufsize=1, **subprocess_kwargs())
    assert proc.stdout is not None and proc.stderr is not None
    tail: List[str] = []
    stopped: List[str] = []

    def _drain() -> None:
        for line in proc.stderr:  # type: ignore[union-attr]
            tail.append(line)
            if len(tail) > 40:
                tail.pop(0)

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()
    limit = max(180.0, duration * 8.0)

    def _watchdog() -> None:
        if proc.poll() is not None:
            return
        stopped.append(f"нет прогресса больше {limit:.0f} с")
        try:
            proc.kill()
        except Exception:
            pass

    timer = threading.Timer(limit, _watchdog)
    timer.daemon = True
    timer.start()
    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_us=") and on_progress:
                try:
                    done = int(line.split("=", 1)[1]) / 1_000_000
                except ValueError:
                    continue
                on_progress(round(min(0.99, done / duration), 3))
        proc.wait()
    finally:
        timer.cancel()
        reader.join(timeout=2)
        proc.stdout.close()
        proc.stderr.close()
    return proc.returncode, tail, (stopped[0] if stopped else None)


def _measure_loudness(source: Path, start: float, duration: float,
                      audio_track: int = 0,
                      segments: Optional[List[Dict[str, float]]] = None
                      ) -> Optional[Dict[str, Any]]:
    """Первый проход loudnorm: измеряем громкость фрагмента.

    С вырезанием пауз измеряем уже склеенную дорожку (trim+concat): иначе
    loudnorm получил бы громкость вместе с выброшенной тишиной и занизил бы
    итоговый уровень.
    """
    try:
        if segments:
            graph = _audio_spans_graph(segments, start, audio_track) + (
                ";[aconc]loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[out]")
            cmd = [ffmpeg(), "-hide_banner", "-nostats",
                   "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source),
                   "-filter_complex", graph, "-map", "[out]", "-f", "null", "-"]
        else:
            cmd = [ffmpeg(), "-hide_banner", "-nostats", "-ss", f"{start:.3f}",
                   "-t", f"{duration:.3f}", "-i", str(source),
                   "-map", f"0:a:{max(0, int(audio_track))}?", "-af",
                   "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                              timeout=max(30.0, duration * 2.5), **subprocess_kwargs())
        text = proc.stderr or ""
        start_idx = text.rfind("{")
        end_idx = text.rfind("}")
        if start_idx == -1 or end_idx <= start_idx:
            return None
        data = json.loads(text[start_idx:end_idx + 1])
        keys = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
        if not all(k in data for k in keys):
            return None
        values = []
        for key in keys:
            try:
                value = float(data[key])
            except (TypeError, ValueError):
                return None
            if value in (float("inf"), float("-inf")) or not math.isfinite(value):
                return None
            values.append(value)
        if not (-99.0 <= values[0] <= 0.0):
            return None
        return data
    except Exception:
        return None


def render_clip(source: Path, clip_start: float, clip_end: float, out_path: Path,
                ass_path: Optional[Path] = None, aspect: str = "9:16",
                mode: str = "blur", focus_x: float = 0.5,
                on_progress: Optional[Callable[[float], None]] = None,
                crf: int = 21, preset: str = "veryfast",
                crop_path: Optional[Dict[str, Any]] = None,
                pip: Optional[Dict[str, Any]] = None,
                audio_track: int = 0,
                spans: Optional[List[Dict[str, float]]] = None,
                output_size: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
    """Рендерит вертикальный клип из окна исходника.

    spans — план склейки без пауз (analyze.cut_plan): отрезки исходника в
    абсолютных секундах. Если он задан, видео и звук режутся trim/atrim, затем
    склеиваются concat — паузы просто исчезают из клипа, а не ускоряются.
    """
    w, h = output_size or ASPECTS.get(aspect, ASPECTS["9:16"])
    segments = _cut_spans(spans, clip_start, clip_end)
    if segments:
        duration = max(0.4, round(sum(seg["end"] - seg["start"] for seg in segments), 3))
        base = segments[0]["start"]            # самый ранний отрезок — точка входа
        input_len = max(duration, segments[-1]["end"] - base)
    else:
        duration = max(0.4, clip_end - clip_start)
        base = clip_start
        input_len = duration
    info = probe(source)
    if info["height"] >= 1000:
        crf = min(crf, 19)
        preset = "veryfast"

    sharpen_base = info["width"] < w * 0.75

    pip_cam = (pip or {}).get("cam") if pip and pip.get("enabled", True) else None
    corner = (pip or {}).get("cam_corner")
    if pip_cam is None and corner and pip and pip.get("enabled", True):
        share = float((pip or {}).get("cam_share", 0.3))
        side = max(64, int(round(min(info["width"], info["height"]) * share)))
        margin = int(round(min(info["width"], info["height"]) * 0.02))
        cx = margin if "left" in corner else info["width"] - side - margin
        cy = margin if "top" in corner else info["height"] - side - margin
        pip_cam = {"x": cx, "y": cy, "w": side, "h": side}
    pip_size = int(round(w * float((pip or {}).get("size", 0.28))))
    pip_size -= pip_size % 2
    pip_mask = None
    if pip_cam and pip_size >= 64:
        from . import pip as _pip

        pip_mask = _pip.ensure_mask(pip_size, int((pip or {}).get("radius", 20)))

    def _build_filters(path_used: Optional[Dict[str, Any]]) -> str:
        sharp = sharpen_base
        src = "[vsrc]" if segments else "[0:v]"
        prefix = _video_spans_graph(segments, base) + ";" if segments else ""
        if mode == "auto" and path_used:
            sharp = float(path_used.get("crop_w", info["width"])) < w * 1.15
            parts = [_auto_chain(w, h, path_used, sharp, src)]
        elif mode == "blur" or (mode == "auto" and not path_used):
            parts = [_bg_chain(w, h, focus_x, sharp, src)]
        else:
            parts = [_crop_chain(w, h, focus_x, sharpen=sharp, src=src)]
        if pip_mask is not None and parts[0].rstrip().endswith("[base]"):
            from . import pip as _pip

            pos = (pip or {}).get("pos") or [0.72, 0.78]
            px = int(round(min(1.0, max(0.0, float(pos[0]))) * (w - pip_size)))
            py = int(round(min(1.0, max(0.0, float(pos[1]))) * (h - pip_size)))
            main_step = parts[0].rstrip()[:-len("[base]")] + "[_basem]"
            parts = [_pip.build_filters(pip_cam, pip_size, px, py, pip_mask, main_step, src)]
        if ass_path is not None:
            parts.append(
                f"[base]ass=filename='{_esc(ass_path)}':fontsdir='{_esc(custom_fonts.libass_dir())}':alpha=1,"
                f"format=yuv420p[v]"
            )
        else:
            parts.append("[base]scale=in_range=auto:out_range=tv,format=yuv420p[v]")
        return prefix + ";".join(parts)

    vlabel = "[v]"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    measured = (_measure_loudness(source, base, input_len, audio_track, segments or None)
                if info["has_audio"] else None)

    def _audio_filter() -> str:
        if measured:
            text = (
                "loudnorm=I=-14:TP=-1.5:LRA=11"
                f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
                f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
                f":offset={measured['target_offset']}:linear=true"
            )
        else:
            text = "loudnorm=I=-14:TP=-1.5:LRA=11"
        fade_out = max(0.0, duration - 0.06)
        return text + f",afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out:.3f}:d=0.05"

    def _compose(video_args: List[str], filters: str) -> List[str]:
        """Собирает команду целиком: так откат на другой энкодер — это пересборка."""
        threads = str(resources.ffmpeg_threads())
        built = resources.wrap_nice([ffmpeg(), "-y", "-hide_banner", "-v", "error", "-nostats",
                 "-progress", "pipe:1",
                 # декодер и фильтры тоже ограничиваем, иначе ffmpeg забирает все ядра
                 "-threads", threads, "-filter_threads", threads,
                 "-ss", f"{base:.3f}", "-t", f"{input_len:.3f}", "-i", str(source)])
        if pip_mask is not None:
            built += ["-loop", "1", "-framerate", "30", "-i", str(pip_mask)]
        graph = filters
        audio_map = f"0:a:{max(0, int(audio_track))}?"
        if info["has_audio"] and segments:
            # звук склеиваем в том же filter_complex, что и видео: паузы выпадают
            graph = (graph + ";" + _audio_spans_graph(segments, base, audio_track) + ";"
                     + f"[aconc]{_audio_filter()}[aout]")
            audio_map = "[aout]"
        built += ["-filter_complex", graph, "-map", vlabel]
        if info["has_audio"]:
            built += ["-map", audio_map]
            if not segments:
                built += ["-af", _audio_filter()]
            built += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
        else:
            built += ["-an"]
        built += ["-threads", str(resources.ffmpeg_threads())] + video_args + [
            "-r", "30", "-movflags", "+faststart", "-shortest", str(out_path)]
        return built

    hw = hw_encoder()
    attempts: List[Tuple[Optional[str], Optional[Dict[str, Any]]]] = []
    if hw:
        attempts.append((hw, crop_path))
    attempts.append((None, crop_path))
    if crop_path:
        # если ffmpeg не переварил длинное выражение кадрирования — грубый путь
        attempts.append((None, _reframe._coarse_path(crop_path)))
        attempts.append((None, None))
    tail_text = ""
    stop_reason: Optional[str] = None
    code = 1
    for attempt, (encoder, path_used) in enumerate(attempts):
        out_path.unlink(missing_ok=True)
        filters = _build_filters(path_used if mode == "auto" else None)
        cmd = _compose(_video_args(encoder, crf, preset), filters)
        if os.environ.get("VIRALCUT_DEBUG_RENDER"):
            print("[render] cmd:", " ".join(cmd), file=sys.stderr, flush=True)
        code, tail, stop_reason = _run_encode(cmd, duration, on_progress if attempt == 0 else None)
        tail_text = "".join(tail)
        if stop_reason:
            break
        if code == 0 and out_path.exists() and out_path.stat().st_size >= 10000:
            break
        if encoder is not None:
            # железо не справилось — повторяем на CPU, не ломая команду
            print(f"[render] {encoder} не сработал, повтор на libx264", file=sys.stderr, flush=True)
        elif path_used is not None:
            print("[render] выражение кадрирования отвергнуто, повторю с упрощённым путём",
                  file=sys.stderr, flush=True)

    if stop_reason:
        out_path.unlink(missing_ok=True)
        raise MediaError(f"Рендер остановлен: {stop_reason}. Попробуйте ещё раз.")
    if code != 0 or not out_path.exists() or out_path.stat().st_size < 10000:
        hint = ""
        if hw and "libx264" not in tail_text:
            hint = " Попробуйте отключить аппаратный энкодер: VIRALCUT_HW_ENCODE=0."
        raise MediaError("Не удалось отрендерить клип: " + tail_text[-600:] + hint)

    if on_progress:
        on_progress(1.0)
    return {"path": out_path, "duration": round(duration, 2), "width": w, "height": h}


def snapshot(source: Path, out: Path, t: float = 0.0, width: int = 900) -> Path:
    """Один кадр исходника в JPEG — для выбора окна камеры в интерфейсе."""
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg(), "-y", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(source),
           "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", str(out)]
    proc = run(cmd, timeout=90)
    if proc.returncode != 0 or not out.exists():
        raise MediaError("Не удалось получить кадр: " + (proc.stderr or "")[-200:])
    return out


def make_preview(clip_path: Path, out_path: Path, width: int = 540) -> Optional[Path]:
    """Лёгкая копия для быстрого предпросмотра в интерфейсе."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg(), "-y", "-v", "error", "-i", str(clip_path),
           "-vf", f"scale={width}:-2", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "30", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
           str(out_path)]
    proc = run(cmd)
    return out_path if proc.returncode == 0 and out_path.exists() else None


def make_thumb(clip_path: Path, out_path: Path, at: float = 0.6) -> Optional[Path]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg(), "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(clip_path),
           "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "3", str(out_path)]
    proc = run(cmd)
    return out_path if proc.returncode == 0 and out_path.exists() else None


