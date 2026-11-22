"""Оркестрация: скачивание → распознавание → поиск моментов → рендер клипов."""
from __future__ import annotations

import os
import re
import shutil
import threading
import time
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import analyze, db, downloader, reframe, render, subtitles, transcribe, utils
from .errors import Cancelled
from .config import PROJECTS_DIR

DEFAULT_OPTIONS: Dict[str, Any] = {
    "count": 10,
    "min_dur": 15,
    "max_dur": 60,
    "target_dur": 32,
    "language": "auto",
    "aspect": "9:16",
    "mode": "auto",
    "subtitles": True,
    "accent": "yellow",
    "uppercase": True,
    "show_hook": True,
    "cookies_browser": "",
    "sub_size": 118,
    "sub_font": "montserrat",
    "sub_position": "bottom",
    "sub_offset": 0,
    "sub_speed": "calm",
    "max_height": 1080,
    "segments": False,
    "audio_track": 0,
    "sub_free": None,
    "force_hd": False,
    "cut_pauses": False,
}


def normalize_options(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    opts = dict(DEFAULT_OPTIONS)
    if raw:
        for key, value in raw.items():
            if value is not None:
                opts[key] = value
    opts["cut_pauses"] = bool(opts.get("cut_pauses"))
    try:
        opts["count"] = int(opts["count"])
    except Exception:
        opts["count"] = 10
    opts["count"] = max(0, min(200, opts["count"]))
    try:
        opts["min_dur"] = max(8, min(120, int(opts["min_dur"])))
        opts["max_dur"] = max(opts["min_dur"] + 5, min(180, int(opts["max_dur"])))
        opts["target_dur"] = max(opts["min_dur"], min(opts["max_dur"], int(opts["target_dur"])))
    except Exception:
        opts.update({"min_dur": 15, "max_dur": 60, "target_dur": 32})
    if opts.get("composition"):
        from . import composition
        opts["composition"] = composition.validate(opts["composition"])
    if opts["aspect"] not in render.ASPECTS:
        opts["aspect"] = "9:16"
    if opts["mode"] not in ("auto", "blur", "crop"):
        opts["mode"] = "auto"
    if opts["accent"] not in subtitles.ACCENTS:
        opts["accent"] = "yellow"
    try:
        size = int(opts.get("sub_size", 118))
        if size < 70:
            size = 118
        opts["sub_size"] = max(70, min(180, size))
    except Exception:
        opts["sub_size"] = 118
    if not subtitles.font_exists(opts.get("sub_font") or ""):
        opts["sub_font"] = "montserrat"
    if opts.get("sub_position") not in subtitles.POSITIONS:
        opts["sub_position"] = "bottom"
    if opts.get("sub_speed") not in subtitles.SPEEDS:
        opts["sub_speed"] = "calm"
    try:
        opts["sub_offset"] = max(-120, min(180, int(opts.get("sub_offset", 0))))
    except Exception:
        opts["sub_offset"] = 0
    try:
        mh = int(opts.get("max_height", 1080))
    except Exception:
        mh = 1080
    opts["max_height"] = mh if mh in (1080, 720, 480, 360) else 1080
    # эконом-режим отключён: качество выбирается явно (max_height)
    opts["segments"] = False
    try:
        opts["audio_track"] = max(0, int(opts.get("audio_track") or 0))
    except (TypeError, ValueError):
        opts["audio_track"] = 0
    opts["force_hd"] = bool(opts.get("force_hd"))
    opts["language"] = str(opts.get("language") or "auto")
    if opts["language"] == "auto":
        opts["language"] = ""
    return opts


CANCELLED: set = set()


def request_cancel(pid: str) -> None:
    CANCELLED.add(pid)


def clear_cancel(pid: str) -> None:
    CANCELLED.discard(pid)


def _check_cancel(pid: str) -> None:
    if pid in CANCELLED:
        raise Cancelled()


# Последний записанный в лог этап: журнал app.log должен показывать, на чём
# именно приложение упало, но без сотни повторяющихся строк прогресса.
_STAGE_LOG: Dict[str, str] = {}


def _update(pid: str, **fields: Any) -> None:
    stage = fields.get("stage")
    if isinstance(stage, str) and stage and _STAGE_LOG.get(pid) != stage:
        _STAGE_LOG[pid] = stage
        print(f"[stage] {stage}", file=sys.stderr, flush=True)
    db.update_project(pid, **fields)


def _heartbeat(pid: str, label: str):
    """Обновляет этап раз в 5 секунд, чтобы интерфейс не выглядел зависшим."""
    import threading

    stop = threading.Event()
    started = time.time()

    def run() -> None:
        while not stop.wait(5):
            try:
                # Только этап: статус и прогресс остаются за рабочим потоком.
                db.set_stage_if_active(pid, f"{label} · {int(time.time() - started)} с")
            except Exception:
                pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return stop, thread


def _download_phase(pid: str, project: Dict[str, Any], opts: Dict[str, Any],
                    workdir: Path, progress: Callable[[float, str], None]) -> Path:
    """Скачивает исходник, пишет метаданные и возвращает путь к файлу."""
    # Повтор после отмены не должен заново качать часовое видео: исходник уже
    # лежит в папке проекта. Единственное исключение — принудительное HD.
    if not opts.get("force_hd"):
        for name in ("source.mp4", "source.mkv", "source.webm", "source.mov", "source.m4a", "source.mp3"):
            cached = workdir / name
            if cached.exists() and cached.stat().st_size > 1024:
                try:
                    info = utils.probe(cached)
                except Exception:  # noqa: BLE001
                    break
                if info.get("duration", 0) >= 5:
                    progress(0.98, "Исходник уже скачан · пропускаю загрузку")
                    _update(pid, source=str(cached), duration=round(info["duration"], 2))
                    db.merge_meta(pid, {"width": info["width"], "height": info["height"],
                                        "source_height": info["height"]})
                    return cached
    if project["url"].startswith("local:"):
        source = Path(project.get("source") or (workdir / "source.mp4"))
        if not source.exists():
            raise RuntimeError("Загруженный файл не найден, попробуйте загрузить снова.")
        meta = {"path": source, "title": project.get("title"), "duration": None,
                "uploader": None, "extractor": "upload"}
    else:
        try:
            if downloader.is_direct_media(project["url"]):
                meta = downloader.download_file(
                    project["url"], workdir,
                    progress=lambda p, st: progress(p * 0.9, st))
            else:
                meta = downloader.download(
                    project["url"], workdir,
                    progress=lambda p, st: progress(p * 0.9, st),
                    browser=opts.get("cookies_browser") or None,
                    force_hd=opts.get("force_hd", False),
                    max_height=1080 if opts.get("force_hd") else int(opts.get("max_height", 1080)),
                )
        except downloader.DownloadError as exc:
            raise RuntimeError(str(exc)) from exc

    source: Path = meta["path"]
    info = utils.probe(source)
    duration = info["duration"] or meta.get("duration") or 0
    if duration < 5:
        raise RuntimeError("Видео слишком короткое для нарезки.")
    _update(pid, title=meta.get("title") or project["title"], duration=round(duration, 2),
            source=str(source), thumb=None,
            meta={"width": info["width"], "height": info["height"],
                  "source_height": info["height"], "quality": meta.get("quality"),
                  "max_height": meta.get("max_height"),
                  "selected_format": meta.get("selected_format"),
                  "vcodec": meta.get("vcodec"), "fps": meta.get("fps"),
                  "download_seconds": meta.get("download_seconds"),
                  "merge_seconds": meta.get("merge_seconds"),
                  "avg_speed_mbps": meta.get("avg_speed_mbps"),
                  "fallback": meta.get("fallback"),
                  "fallback_reason": meta.get("fallback_reason"),
                  "uploader": meta.get("uploader"), "extractor": meta.get("extractor")})
    _copy_to_download_dir(source, meta.get("title") or project.get("title") or source.stem)
    return source


def _copy_to_download_dir(source: Path, title: str) -> None:
    """Копирует скачанный исходник в папку, которую выбрал пользователь."""
    try:
        from . import settings as app_settings

        target_dir = app_settings.get().get("download_dir") or ""
        if not target_dir:
            return
        dest_dir = Path(target_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w\-. ]+", " ", str(title)).strip()[:80] or source.stem
        dest = dest_dir / f"{safe}{source.suffix}"
        index = 1
        while dest.exists():
            dest = dest_dir / f"{safe} ({index}){source.suffix}"
            index += 1
        if dest.resolve() == source.resolve():
            return
        shutil.copy2(source, dest)
        print(f"[download] исходник сохранён: {dest}", file=sys.stderr, flush=True)
    except Exception as exc:  # noqa: BLE001 — копия не должна ломать обработку
        print(f"[download] не удалось скопировать исходник: {exc}", file=sys.stderr, flush=True)


def pip_options(opts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Окно стримера из опций проекта: включено, где камера и где окно."""
    conf = opts.get("pip") or {}
    if not conf.get("enabled"):
        return None
    cam = conf.get("cam") or {}
    try:
        cw = int(cam.get("w") or 0)
        ch = int(cam.get("h") or 0)
        cx = int(cam.get("x") or 0)
        cy = int(cam.get("y") or 0)
    except (TypeError, ValueError):
        return None
    pos = conf.get("pos") or [0.72, 0.78]
    result = {
        "cam": {"x": cx, "y": cy, "w": cw, "h": ch} if cw >= 32 and ch >= 32 else None,
        "cam_corner": conf.get("cam_corner"),
        "cam_share": float(conf.get("cam_share") or 0.3),
        "radius": int(conf.get("radius") or 20),
        "size": float(conf.get("size") or 0.28),
        "pos": [float(pos[0]), float(pos[1])],
    }
    return result


def _clip_settings(opts: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "aspect": opts["aspect"], "mode": opts["mode"], "subtitles": opts["subtitles"],
        "accent": opts["accent"], "uppercase": opts["uppercase"],
        "show_hook": opts["show_hook"], "focus_x": 0.5, "sub_size": opts["sub_size"],
        "sub_font": opts["sub_font"], "sub_position": opts["sub_position"],
        "sub_offset": opts["sub_offset"], "sub_free": opts.get("sub_free"), "sub_speed": opts["sub_speed"],
        "segments": bool(opts.get("segments")), "cut_pauses": bool(opts.get("cut_pauses")),
    }


def _prepare_segments(pid: str, project: Dict[str, Any], opts: Dict[str, Any],
                      workdir: Path, progress: Callable[[float, str], None]) -> None:
    """Экономный режим: аудио → анализ → предпросмотр одного момента."""
    progress(0.02, "Скачивание аудио")
    audio = downloader.download_audio(
        project["url"], workdir, browser=opts.get("cookies_browser") or None,
        progress=lambda p, st: progress(0.02 + p * 0.28, st),
    )
    duration = float(audio.get("duration") or 0) or utils.media_duration(audio["path"])
    if duration < 5:
        raise RuntimeError("Видео слишком короткое для нарезки.")

    progress(0.32, "Распознавание речи")
    stop_hb, hb_thread = _heartbeat(pid, "Распознавание речи")
    try:
        transcript = transcribe.transcribe(
            audio["path"], workdir, language=opts.get("language") or None,
            on_progress=lambda p, st: progress(0.32 + p * 0.38, f"{st} {int(p*100)}%"),
        )
    finally:
        stop_hb.set(); hb_thread.join(timeout=1)
    _update(pid, title=audio.get("title") or project["title"], duration=round(duration, 2),
            source=str(audio["path"]), language=transcript.get("language"),
            meta={"width": 0, "height": 0, "segments_mode": True,
                  "audio_size": audio.get("size"), "engine": transcript.get("engine"),
                  "segments": len(transcript.get("segments") or [])})

    progress(0.72, "Поиск вирусных моментов")
    found = analyze.find_segments(
        transcript["segments"], audio["path"], duration,
        count=opts["count"] or 0, min_dur=opts["min_dur"],
        max_dur=opts["max_dur"], target_dur=opts["target_dur"],
    )
    if not found:
        raise RuntimeError("Не нашлось связных фрагментов. Попробуйте увеличить длину клипа.")

    settings = _clip_settings(opts)
    db.clear_clips(pid)
    for i, cand in enumerate(found):
        db.add_clip(pid, i, cand["start"], cand["end"], cand["score"], cand["title"],
                    cand["hook"], cand["caption"], cand["words"],
                    {**settings, "score_parts": cand.get("parts") or {}}, status="pending")

    # короткий предпросмотр первого момента, чтобы окно шаблона было с видео
    first = found[0]
    preview_path = workdir / "preview.mp4"
    try:
        progress(0.78, "Скачивание предпросмотра")
        sec_start = max(0.0, first["start"] - 0.5)
        sec_end = min(duration, first["end"] + 0.5)
        part = downloader.download_section(
            project["url"], workdir / "preview_src", sec_start, sec_end,
            progress=lambda p, st: progress(0.78 + p * 0.16, st),
            browser=opts.get("cookies_browser") or None, max_height=360,
        )
        shutil.copy2(part, preview_path)
        shutil.rmtree(workdir / "preview_src", ignore_errors=True)
    except Exception:
        preview_path.unlink(missing_ok=True)
        traceback.print_exc()

    _update(pid, status="review", progress=100, error=None,
            stage=f"Найдено {len(found)} моментов · настройте субтитры")
    db.merge_meta(pid, {"pending": len(found)})


def _process_segments(pid: str, project: Dict[str, Any], opts: Dict[str, Any],
                      workdir: Path, progress: Callable[[float, str], None]) -> None:
    started = time.time()
    clips = [c for c in db.list_clips(pid) if c["status"] == "pending"]
    total = len(clips)
    if not total:
        raise RuntimeError("Список моментов пуст — запустите анализ заново.")
    duration = float(project.get("duration") or 0)
    rendered = 0
    sections = workdir / "sections"
    sections.mkdir(parents=True, exist_ok=True)
    settings = _clip_settings(opts)
    low_res: List[int] = []
    for i, clip in enumerate(clips):
        _check_cancel(pid)
        base = i / total
        label = f"Момент {i + 1} из {total}"
        db.update_clip(clip["id"], status="rendering", settings=settings)


        def sub_progress(p: float, st: str, _i: int = i) -> None:
            progress(0.55 + (_i + p) / total * 0.45, f"{st} · {label}")

        try:
            sec_start = max(0.0, float(clip["start"]) - 0.5)
            sec_end = min(duration or float(clip["end"]) + 1, float(clip["end"]) + 0.5)
            quality: Dict[str, Any] = {}
            part = downloader.download_section(
                project["url"], sections / clip["id"], sec_start, sec_end,
                progress=sub_progress, browser=opts.get("cookies_browser") or None,
                # пересборка в HD забирает фрагменты в 1080p, а не в 360
                max_height=1080 if opts.get("force_hd") else int(opts.get("max_height", 1080)),
                quality=quality,
            )
            low_res.append(int(quality.get("height") or 0))
            if os.environ.get("VIRALCUT_DEBUG_SECTIONS"):
                info = utils.probe(part)
                print(f"[section] клип {clip['idx'] + 1}: {info['width']}x{info['height']} "
                      f"max_height={opts.get('max_height')} force_hd={opts.get('force_hd')}",
                      file=sys.stderr, flush=True)
            actual = utils.media_duration(part)
            offset = max(0.0, float(clip["start"]) - sec_start)
            words = []
            for w in clip["words"]:
                words.append({**w, "start": float(w["start"]) - sec_start,
                              "end": float(w["end"]) - sec_start})
            virtual = {**clip, "start": offset,
                       "end": min(actual, offset + (float(clip["end"]) - float(clip["start"]))),
                       "words": words}
            _render_one(part, workdir, virtual, settings,
                        lambda p, _i=i: progress(0.55 + (_i + p) / total * 0.45, label))
            db.update_clip(clip["id"], status="ready", error=None)
            rendered += 1
            shutil.rmtree(sections / clip["id"], ignore_errors=True)
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            db.update_clip(clip["id"], status="error", error=str(exc)[:400])

    # если какие-то фрагменты пришли в низком разрешении — подскажем в интерфейсе
    weak = [h for h in low_res if 0 < h < 720]
    if weak:
        db.merge_meta(pid, {"low_res_clips": len(weak), "low_res_height": min(weak)})
        print(f"[section] низкое качество у {len(weak)} из {len(low_res)} фрагментов",
              file=sys.stderr, flush=True)

    elapsed = round(time.time() - started, 1)
    if rendered == 0:
        raise RuntimeError("Не удалось скачать и отрендерить ни одного момента.")
    _update(pid, status="done", progress=100, stage=f"Готово: {rendered} клипов",
            error=None)
    db.merge_meta(pid, {"clips": rendered})


def prepare_project(pid: str) -> None:
    """Скачивает видео и переводит проект в режим настройки субтитров."""
    project = db.get_project(pid)
    if not project:
        return
    opts = normalize_options(project.get("options"))
    workdir = PROJECTS_DIR / pid
    workdir.mkdir(parents=True, exist_ok=True)

    def progress(value: float, stage: str) -> None:
        _check_cancel(pid)
        _update(pid, progress=round(max(0.0, min(1.0, value)) * 100, 1), stage=stage,
                status="preparing")

    try:
        progress(0.01, "Подготовка")
        _update(pid, status="preparing", error=None)
        if opts.get("segments"):
            _prepare_segments(pid, project, opts, workdir, progress)
            return
        progress(0.02, "Загрузка видео")
        source = _download_phase(pid, project, opts, workdir, progress)
        info = utils.probe(source)
        took = (db.get_project(pid) or {}).get("meta", {}).get("download_seconds")
        took_txt = f" за {took:.0f} с" if took else ""
        if info["width"] and info["width"] < info["height"]:
            res_txt = f"{info['width']}×{info['height']}"
        else:
            res_txt = f"{info['height']}p"
        _update(pid, status="review", progress=100, error=None,
                stage=f"Видео готово ({res_txt}{took_txt}) · настройте субтитры")
    except Cancelled:
        _update(pid, status="cancelled", stage="Загрузка отменена", error=None)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        _update(pid, status="error", error=str(exc)[:600], stage="Ошибка загрузки")


def process_project(pid: str) -> None:
    """Распознаёт речь и рендерит нарезки из уже скачанного исходника."""
    project = db.get_project(pid)
    if not project:
        return
    source_raw = project.get("source")
    if not source_raw or not Path(source_raw).exists():
        _update(pid, status="error", error="Исходное видео не найдено. Загрузите его заново.",
                stage="Ошибка")
        return
    source = Path(source_raw)
    opts = normalize_options(project.get("options"))
    workdir = PROJECTS_DIR / pid
    started = time.time()

    def progress(value: float, stage: str) -> None:
        _check_cancel(pid)
        _update(pid, progress=round(max(0.0, min(1.0, value)) * 100, 1), stage=stage,
                status="running")

    if opts.get("segments"):
        pending = [c for c in db.list_clips(pid) if c["status"] == "pending"]
        if pending:
            try:
                _process_segments(pid, project, opts, workdir, progress)
            except Cancelled:
                _update(pid, status="cancelled", stage="Обработка отменена", error=None)
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                _update(pid, status="error", error=str(exc)[:600], stage="Ошибка")
            return

    info = utils.probe(source)
    duration = info["duration"]

    try:
        progress(0.05, "Распознавание речи")
        transcript: Optional[Dict[str, Any]] = None
        if not transcribe.model_cached():
            progress(0.05, "Скачиваю модель распознавания речи (~460 МБ, один раз)")
        stop_hb, hb_thread = _heartbeat(pid, "Распознавание речи")
        try:
            transcript = transcribe.transcribe(
                source, workdir, language=opts.get("language") or None,
                on_progress=lambda p, s: progress(0.05 + p * 0.45, f"{s} {int(p*100)}%"),
            )
            stop_hb.set(); hb_thread.join(timeout=1)
        except Exception as exc:  # noqa: BLE001
            stop_hb.set(); hb_thread.join(timeout=1)
            sub_path = downloader.fetch_subtitles(project["url"], workdir,
                                                  browser=opts.get("cookies_browser") or None)
            if sub_path:
                segs = utils.parse_vtt(Path(sub_path))
                if segs:
                    transcript = {"language": "ru", "duration": duration, "segments": segs,
                                  "engine": "source-subtitles"}
            if transcript is None:
                raise RuntimeError("Не удалось распознать речь. " + str(exc)[:300]) from exc

        _update(pid, language=transcript.get("language"))
        db.merge_meta(pid, {
            "engine": transcript.get("engine"),
            "segments": len(transcript.get("segments") or []),
        })

        progress(0.55, "Поиск вирусных моментов")
        found = analyze.find_segments(
            transcript["segments"], source, duration,
            count=opts["count"] or 0,
            min_dur=opts["min_dur"], max_dur=opts["max_dur"],
            target_dur=opts["target_dur"],
        )
        if not found:
            raise RuntimeError("Не нашлось связных фрагментов. Попробуйте увеличить длину клипа.")

        clip_settings = {
            "aspect": opts["aspect"], "mode": opts["mode"], "subtitles": opts["subtitles"],
            "accent": opts["accent"], "uppercase": opts["uppercase"],
            "show_hook": opts["show_hook"], "focus_x": 0.5, "sub_size": opts["sub_size"],
            "sub_font": opts["sub_font"], "sub_position": opts["sub_position"],
            "sub_offset": opts["sub_offset"], "sub_free": opts.get("sub_free"),
            "sub_speed": opts["sub_speed"], "cut_pauses": bool(opts.get("cut_pauses")),
        }
        _check_cancel(pid)
        total = len(found)
        progress(0.60, f"Рендер {total} клипов")
        clips = []
        for i, cand in enumerate(found):
            clip = db.add_clip(
                pid, i, cand["start"], cand["end"], cand["score"], cand["title"],
                cand["hook"], cand["caption"], cand["words"],
                {**clip_settings, "score_parts": cand.get("parts") or {}},
            )
            clips.append(clip)

        from concurrent.futures import ThreadPoolExecutor, as_completed

        lock = threading.Lock()
        state = {"done": 0, "failed": 0, "cancel": False}

        def render_one(clip) -> bool:
            if state["cancel"]:
                return False
            try:
                _check_cancel(pid)
            except Cancelled:
                with lock:
                    state["cancel"] = True
                return False
            try:
                _render_one(source, workdir, clip, clip_settings, lambda p: None, opts)
            except Cancelled:
                with lock:
                    state["cancel"] = True
                return False
            except Exception as exc:  # noqa: BLE001
                db.update_clip(clip["id"], status="error", error=str(exc)[:400])
                with lock:
                    state["failed"] += 1
                    state["done"] += 1
                    done, failed = state["done"], state["failed"]
                progress(0.60 + (done / max(1, total)) * 0.40,
                         f"Рендер: {done} из {total} готово" + (f" · ошибок {failed}" if failed else ""))
                return False
            with lock:
                state["done"] += 1
                done = state["done"]
            progress(0.60 + (done / max(1, total)) * 0.40, f"Рендер: {done} из {total} готово")
            return True

        workers = min(_render_workers(), max(1, total))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(render_one, clip) for clip in clips]
            rendered = sum(1 for fut in as_completed(futures) if fut.result())
        if state["cancel"]:
            raise Cancelled()

        elapsed = round(time.time() - started, 1)
        if rendered == 0:
            failed = [c.get("error") for c in db.list_clips(pid) if c.get("status") == "error"]
            reason = next((e for e in failed if e), "")
            raise RuntimeError("Не удалось отрендерить ни одного клипа."
                               + (f" Причина: {str(reason)[:300]}" if reason else ""))
        word = "клип" if rendered % 10 == 1 and rendered % 100 != 11 else (
            "клипа" if 2 <= rendered % 10 <= 4 and not 12 <= rendered % 100 <= 14 else "клипов")
        _update(pid, status="done", progress=100, error=None,
                stage=f"Готово: {rendered} {word} за {elapsed:.0f} с")
        db.merge_meta(pid, {"elapsed": elapsed, "clips": rendered})

    except Cancelled:
        _update(pid, status="cancelled", stage="Обработка отменена", error=None)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        _update(pid, status="error", error=str(exc)[:600], stage="Ошибка")


def _render_workers() -> int:
    """Сколько клипов рендерить параллельно.

    Один ffmpeg занимает ~3 ядра, поэтому на 8–10 ядрах это 2–3 рендера: суммарно
    в 1.5–2 раза быстрее, а машина остаётся отзывчивой.
    """
    from . import resources

    return resources.render_workers()


def run_project(pid: str) -> None:
    """Полный цикл: скачать → подготовить → обработать (для ретраев/API без превью)."""
    prepare_project(pid)
    project = db.get_project(pid)
    if not project or project.get("status") != "review":
        return
    process_project(pid)


def _pause_spans(source: Path, start: float, end: float) -> List[Dict[str, float]]:
    """План склейки окна без пауз; пустой список — резать нечего.

    Порог паузы 0.45 с и запас 0.12 с по краям: дыхание и микропаузы внутри
    фразы остаются, а «эээ…» и молчание между мыслями исчезают.
    """
    try:
        curve, mean_db = analyze.cached_energy_curve(source)
        if not curve:
            return []
        gaps = analyze.silence_gaps(curve, mean_db, start, end)
        spans = analyze.cut_plan(start, end, gaps)
        return spans if len(spans) > 1 else []
    except Exception as exc:  # noqa: BLE001 — без плана рендерим как обычно
        print(f"[render] паузы не вырезаны: {exc}", file=sys.stderr, flush=True)
        return []


def _render_one(source: Path, workdir: Path, clip: Dict[str, Any],
                settings: Dict[str, Any], on_progress: Optional[Callable[[float], None]] = None,
                opts: Optional[Dict[str, Any]] = None) -> None:
    out_dir = workdir / "clips"
    ass_dir = workdir / "ass"
    out_dir.mkdir(parents=True, exist_ok=True)
    ass_dir.mkdir(parents=True, exist_ok=True)

    composition_conf = (opts or {}).get("composition") or {}
    panel_size = None
    render_aspect = settings.get("aspect", "9:16")
    if composition_conf.get("game"):
        from . import composition
        full_w, full_h = render.ASPECTS.get(render_aspect, (1080, 1920))
        panel_h = int(full_h * .60) // 2 * 2
        panel_size = (full_w, panel_h)
        render_aspect = f"{full_w}:{panel_h}"

    # «Вырезать паузы»: считаем план склейки до рендера, а слова и кривую
    # кадрирования пересчитываем на новое время — иначе субтитры и кроп
    # отставали бы на длину вырезанного.
    spans: List[Dict[str, float]] = []
    words = list(clip["words"] or [])
    if settings.get("cut_pauses") and not settings.get("segments"):
        spans = _pause_spans(source, float(clip["start"]), float(clip["end"]))
        if spans:
            words = analyze.remap_words(words, spans)

    ass_path = None
    if settings.get("subtitles", True) and words:
        text = subtitles.build_ass(
            words, 0.0 if spans else clip["start"],
            round(spans[-1]["output"] + (spans[-1]["end"] - spans[-1]["start"]), 3)
            if spans else clip["end"],
            hook=clip.get("hook") or clip.get("title") or "",
            accent=settings.get("accent", "yellow"),
            uppercase=settings.get("uppercase", True),
            show_hook=settings.get("show_hook", True),
            sub_size=int(settings.get("sub_size", 118)),
            font=settings.get("sub_font", "montserrat"),
            position=settings.get("sub_position", "bottom"),
            offset=int(settings.get("sub_offset", 0)),
            speed=settings.get("sub_speed", "calm"),
        )
        if panel_size:
            import re
            # Render captions into the panel at full width, without squeezing a portrait clip.
            panel_h = panel_size[1]
            text = text.replace("PlayResY: 1920", f"PlayResY: {panel_h}")
            text = re.sub(r"\\pos\(([^,]+),([0-9.]+)\)",
                          lambda m: f"\\pos({m[1]},{float(m[2])*panel_h/1920:.1f})", text)
        ass_path = ass_dir / f"{clip['id']}.ass"
        ass_path.write_text(text, encoding="utf-8")

    out_path = out_dir / f"clip_{clip['idx'] + 1:02d}.mp4"
    crop_path = None
    mode = settings.get("mode", "auto")
    if mode == "auto":
        try:
            crop_path = reframe.build_crop_path(
                source, clip["start"], clip["end"], aspect=render_aspect)
            if crop_path and spans:
                crop_path = reframe.remap_crop_path(crop_path, spans, float(clip["start"]))
        except Exception:
            crop_path = None
        # если лиц почти нет (скринкаст, слайды) — заполняем кадр по центру,
        # а не оставляем размытые поля: так просили пользователи
        if crop_path and crop_path.get("coverage", 1.0) < 0.18:
            mode = "crop"
            crop_path = None
    render.render_clip(
        source, clip["start"], clip["end"], out_path, ass_path=ass_path,
        aspect=settings.get("aspect", "9:16"), mode=mode,
        focus_x=float(settings.get("focus_x", 0.5)), on_progress=on_progress,
        crop_path=crop_path, pip=pip_options(opts or {}),
        audio_track=int((opts or {}).get("audio_track") or 0),
        spans=spans or None, output_size=panel_size,
    )
    if (opts or {}).get("composition"):
        from . import composition
        report = composition.apply(out_path, opts["composition"],
                                   canvas=render.ASPECTS.get(settings.get("aspect", "9:16")),
                                   main_prepared=bool(panel_size), variation=int(clip["idx"]))
        db.update_clip(clip["id"], settings={**settings, "composition_info": report})
    thumb_path = workdir / "thumbs" / f"{clip['id']}.jpg"
    render.make_thumb(out_path, thumb_path, at=min(1.2, max(0.2, (clip["end"] - clip["start"]) * 0.15)))
    render.make_preview(out_path, workdir / "previews" / f"{clip['id']}.mp4")
    db.update_clip(clip["id"], status="ready", path=str(out_path),
                   thumb=str(thumb_path) if thumb_path.exists() else None, error=None)


def rerender_clip(clip_id: str, payload: Dict[str, Any],
                  on_progress: Optional[Callable[[float], None]] = None) -> Dict[str, Any]:
    clip = db.get_clip(clip_id)
    if not clip:
        raise RuntimeError("Клип не найден")
    project = db.get_project(clip["project_id"])
    if not project:
        raise RuntimeError("Клип не найден")
    workdir = PROJECTS_DIR / project["id"]
    live_recording = (workdir / "segments" / "times.jsonl").exists()
    if not project.get("source") and not live_recording:
        raise RuntimeError("Исходное видео не найдено: запись эфира удалена или ещё не началась.")
    settings = dict(clip["settings"])
    if settings.get("segments"):
        raise RuntimeError("Клип собран в экономном режиме из фрагмента. Шаблон меняется до запуска нарезки.")
    for key in ("aspect", "mode", "subtitles", "accent", "uppercase", "show_hook", "focus_x",
                "sub_size", "sub_font", "sub_position", "sub_offset", "sub_speed", "cut_pauses"):
        if key in payload and payload[key] is not None:
            settings[key] = payload[key]
    start = float(payload.get("start", clip["start"]))
    end = float(payload.get("end", clip["end"]))
    if end - start < 3:
        raise RuntimeError("Клип слишком короткий")
    words = list(clip["words"] or [])
    if not project.get("source"):
        from . import live
        # старые live-клипы хранили слова относительно окна эфира
        words = live._absolute_words(words, float(clip["start"]))
    if start != clip["start"] or end != clip["end"]:
        words = [w for w in words if float(w["end"]) > start and float(w["start"]) < end]
    # правка текста субтитров: сохраняем тайминги, меняем только слова
    if payload.get("text") is not None and str(payload.get("text")).strip():
        words = subtitles.retime_words(words, str(payload["text"]))
    db.update_clip(clip_id, status="rendering", start=start, end=end, words=words,
                   hook=payload.get("hook", clip["hook"]), title=payload.get("title", clip["title"]),
                   caption=payload.get("caption", clip["caption"]),
                   settings=settings, error=None)
    updated = db.get_clip(clip_id)
    if project.get("source"):
        _render_one(Path(project["source"]), workdir, updated, settings, on_progress,
                    project.get("options") or {})
    else:
        from . import live
        # клип из прямого эфира: берём фрагмент из записанных сегментов
        live._render_live_clip(workdir, updated, 0.0, settings, project.get("options") or {})
    return db.get_clip(clip_id) or updated


def export_zip(project_id: str, dest: Path) -> Path:
    clips = [c for c in db.list_clips(project_id) if c["status"] == "ready" and c["path"]]
    if not clips:
        raise RuntimeError("Нет готовых клипов для экспорта")
    import zipfile

    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED) as zf:
        for c in clips:
            src = Path(c["path"])
            if src.exists():
                zf.write(src, arcname=f"{c['idx'] + 1:02d}_{_slug(c['title'])}.mp4")
    return dest


def _slug(text: str) -> str:
    import re

    slug = re.sub(r"[^\w\-]+", "_", (text or "clip").lower(), flags=re.U).strip("_")
    slug = slug[:40].rstrip("_")
    return slug or "clip"


def delete_project_files(project_id: str) -> None:
    shutil.rmtree(PROJECTS_DIR / project_id, ignore_errors=True)


# --- ручная нарезка по таймкоду ---------------------------------------------

def parse_timecode(value: str) -> Optional[float]:
    """«12:40», «1:02:03» или «760» → секунды."""
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        if ":" in text:
            parts = [float(p) for p in text.split(":")]
            total = 0.0
            for part in parts:
                total = total * 60 + part
            return max(0.0, total)
        return max(0.0, float(text))
    except ValueError:
        return None


def trim_silence(source: Path, start: float, end: float,
                 max_trim: float = 3.0) -> Tuple[float, float]:
    """Подтягивает края клипа к речи, чтобы не брать пустые секунды."""
    try:
        curve, mean_db = analyze.cached_energy_curve(source)
        if not curve:
            return start, end
        new_start = analyze._nearest_quiet(curve, mean_db, start + 0.05, 0.25, window=0.35)
        new_end = analyze._nearest_quiet(curve, mean_db, end - 0.05, 0.25, window=0.35)
        new_start = max(start, min(new_start, start + max_trim))
        new_end = min(end, max(new_end, end - max_trim))
        if new_end - new_start >= 3:
            return new_start, new_end
    except Exception:  # noqa: BLE001
        pass
    return start, end


def add_manual_clip(pid: str, start: float, end: float,
                    trim: bool = True) -> Dict[str, Any]:
    """Создаёт клип по таймкоду, без анализа: пользователь сам выбрал момент."""
    project = db.get_project(pid)
    if not project or not project.get("source"):
        raise RuntimeError("Ручная нарезка доступна для загруженных видео и ссылок")
    source = Path(project["source"])
    duration = float(project.get("duration") or utils.media_duration(source) or 0)
    start = max(0.0, min(float(start), max(0.0, duration - 1)))
    end = min(float(end), duration if duration else float(end))
    if end - start < 3:
        raise RuntimeError("Клип короче 3 секунд")
    if trim:
        start, end = trim_silence(source, start, end)
    words: List[Dict[str, Any]] = []
    try:
        transcript = (project.get("meta") or {}).get("transcript")
        if not transcript:
            path = PROJECTS_DIR / pid / "transcript.json"
            if path.exists():
                transcript = json.loads(path.read_text(encoding="utf-8"))
        for seg in (transcript or []):
            for word in seg.get("words") or []:
                if float(word["end"]) > start and float(word["start"]) < end:
                    words.append(word)
    except Exception:  # noqa: BLE001
        words = []
    opts = project.get("options") or {}
    settings = _clip_settings(opts)
    existing = db.list_clips(pid)
    idx = max([int(c["idx"]) for c in existing], default=-1) + 1
    clip = db.add_clip(pid, idx, start, end, 1.0, f"Клип {idx + 1}", "",
                       f"Вручную {int(start // 60)}:{int(start % 60):02d}", words, settings)
    from . import jobs as _jobs

    db.update_project(pid, status="running", stage="Рендер клипа")
    _jobs.submit_rerender(clip["id"], {})
    return clip
