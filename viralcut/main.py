"""FastAPI-приложение ViralCut."""
from __future__ import annotations

import os
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Form, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import (custom_fonts, db, jobs, pipeline, render, resources,
               settings as app_settings, system_stats, transcribe, utils)
from ._version import __version__
from .config import ASSETS_DIR, DATA_DIR, PROJECTS_DIR, WEB_DIR, ffmpeg


class ProjectIn(BaseModel):
    url: str
    options: Dict[str, Any] = {}
    prepare_only: bool = False


class DiscoveryIn(BaseModel):
    audience: str = Field(default="ru", pattern="^(ru|en)$")
    topic: str = Field(default="general", pattern="^(general|business|science|psychology|comedy|gameplay)$")
    query: str = Field(default="", max_length=120)
    sort: str = Field(default="recommended", pattern="^(recommended|views)$")


class PipIn(BaseModel):
    enabled: Optional[bool] = None
    cam: Optional[Dict[str, Any]] = None
    cam_corner: Optional[str] = None
    cam_share: Optional[float] = None
    pos: Optional[List[float]] = None
    size: Optional[float] = None
    radius: Optional[int] = None


class SettingsIn(BaseModel):
    encoder: Optional[str] = None
    download_dir: Optional[str] = None
    clips_dir: Optional[str] = None
    ask_folder: Optional[bool] = None


class UpdateSettingsIn(BaseModel):
    enabled: bool = True


class RetryIn(BaseModel):
    force_hd: bool = False
    prepare_only: bool = False


class StartIn(BaseModel):
    options: Dict[str, Any] = {}


class ProbeIn(BaseModel):
    url: str
    cookies_browser: str = ""


class StreamIn(BaseModel):
    url: str
    options: Dict[str, Any] = Field(default_factory=dict)


class ClipEdit(BaseModel):
    sub_free: Optional[List[float]] = None
    text: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    hook: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    aspect: Optional[str] = None
    mode: Optional[str] = None
    subtitles: Optional[bool] = None
    accent: Optional[str] = None
    uppercase: Optional[bool] = None
    show_hook: Optional[bool] = None
    sub_size: Optional[int] = None
    sub_font: Optional[str] = None
    sub_position: Optional[str] = None
    sub_offset: Optional[int] = None
    sub_speed: Optional[str] = None
    cut_pauses: Optional[bool] = None


# Лимиты загрузки: интерфейс проверяет 4 ГБ, но сервер обязан проверять сам.
ALLOWED_UPLOAD_SUFFIXES = {
    ".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".ts", ".mts", ".m2ts",
    ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac",
}
MAX_UPLOAD_BYTES = int(float(os.environ.get("VIRALCUT_MAX_UPLOAD_GB", "4")) * 1024 ** 3)
MAX_FONT_BYTES = 24 * 1024 * 1024


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Побочные эффекты старта — здесь, а не на импорте модуля."""
    db.init_db()
    from . import youtube
    youtube.recover()
    db.reset_stale_jobs()
    custom_fonts.sync()
    # пробный кадр GPU — в фоне: /api/health не должен ждать энкодер
    import threading as _threading

    _threading.Thread(target=render.hw_encoder, name="hw-probe", daemon=True).start()
    yield


# CORS не нужен: страница отдаётся с того же origin, что и API. Без него чужая
# вкладка в браузере не может дёргать локальный сервер (SSRF/забивка диска).
app = FastAPI(title="ViralCut", version=__version__, lifespan=_lifespan)
from .youtube import router as youtube_router
app.include_router(youtube_router)


@app.middleware("http")
async def _static_cache_headers(request, call_next):
    """Шрифты и статика неизменяемы в пределах сессии — не перекачиваем их каждым опросом."""
    response = await call_next(request)
    path = request.url.path
    if path.startswith(("/fonts/", "/userfonts/", "/static/")):
        # index/JS должны перепроверяться: иначе после обновления WebView2
        # поднимает старый закешированный app.js и экран остаётся пустым
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


def _clean_clip_edit(body: ClipEdit) -> Dict[str, Any]:
    """Проверяет правку клипа до постановки в очередь: 400 вместо «клип упал».

    Раньше значения уезжали в фоновую задачу, и клип молча переходил в error.
    """
    from . import render, subtitles

    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if "aspect" in data and data["aspect"] not in render.ASPECTS:
        raise HTTPException(400, "Неизвестный формат кадра")
    if "mode" in data and data["mode"] not in ("auto", "blur", "crop"):
        raise HTTPException(400, "Неизвестный режим кадрирования")
    if "accent" in data and data["accent"] not in subtitles.ACCENTS:
        raise HTTPException(400, "Неизвестный цвет акцента")
    if data.get("sub_free"):
        try:
            x, y = (float(v) for v in data["sub_free"][:2])
        except (TypeError, ValueError):
            raise HTTPException(400, "Неверная позиция субтитров") from None
        data["sub_free"] = [min(1.0, max(0.0, x)), min(1.0, max(0.0, y))]
    if "sub_position" in data and data["sub_position"] not in subtitles.POSITIONS:
        raise HTTPException(400, "Неизвестное положение субтитров")
    if "sub_speed" in data and data["sub_speed"] not in subtitles.SPEEDS:
        raise HTTPException(400, "Неизвестная скорость субтитров")
    if "sub_font" in data and not subtitles.font_exists(data["sub_font"]):
        raise HTTPException(400, "Шрифт не найден")
    if "sub_size" in data:
        try:
            data["sub_size"] = max(70, min(180, int(data["sub_size"])))
        except (TypeError, ValueError):
            raise HTTPException(400, "Некорректный размер субтитров") from None
    if "sub_offset" in data:
        try:
            data["sub_offset"] = max(-120, min(180, int(data["sub_offset"])))
        except (TypeError, ValueError):
            raise HTTPException(400, "Некорректное смещение субтитров") from None
    if "text" in data:
        data["text"] = str(data["text"] or "").strip()[:4000]
    for key in ("start", "end"):
        if key in data:
            try:
                data[key] = max(0.0, float(data[key]))
            except (TypeError, ValueError):
                raise HTTPException(400, "Некорректные границы клипа") from None
    return data


@app.get("/api/health")
def health() -> Dict[str, Any]:
    """Готовность приложения: эндпоинт дёргает и интерфейс, и smoke-тесты.

    Пути к ffmpeg/ffprobe и версия нужны, чтобы по одному ответу понять, что
    за сборка запущена и чем она собрана (важно для тестовых Windows-сборок).
    """
    from . import config as app_config

    ok_ffmpeg = True
    binary = ""
    try:
        binary = ffmpeg()
    except Exception:
        ok_ffmpeg = False
    try:
        probe = app_config.ffprobe() or ""
    except Exception:  # noqa: BLE001
        probe = ""
    return {
        "ok": ok_ffmpeg,
        "version": __version__,
        "platform": sys.platform,
        "frozen": bool(getattr(sys, "frozen", False)),
        "ffmpeg": ok_ffmpeg,
        "ffmpeg_path": binary,
        "ffprobe": probe,
        "whisper": transcribe.model_available(),
        "model": transcribe.model_cached(),
        # диагностика рендера: только из кэша, чтобы не тормозить интерфейс
        # пробным кадром GPU (на Windows без NVENC это секунды ожидания)
        "hw": render.hw_cached(),
        "limits": resources.summary(),
        "projects": db.count_projects(),
    }


class ManualClipIn(BaseModel):
    start: str
    end: str
    trim_silence: bool = True


@app.post("/api/projects/{pid}/clips")
def project_add_clip(pid: str, body: ManualClipIn) -> Dict[str, Any]:
    """Клип по таймкоду: пользователь сам указывает начало и конец."""
    start = pipeline.parse_timecode(body.start)
    end = pipeline.parse_timecode(body.end)
    if start is None or end is None:
        raise HTTPException(400, "Время в формате мм:сс или секунды")
    if end <= start:
        raise HTTPException(400, "Конец должен быть позже начала")
    try:
        return pipeline.add_manual_clip(pid, start, end, body.trim_silence)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/projects/{pid}/audio")
def project_audio(pid: str) -> Dict[str, Any]:
    """Звуковые дорожки исходника: язык, название, каналы."""
    project = db.get_project(pid)
    if not project or not project.get("source"):
        return {"tracks": [], "selected": 0}
    tracks = utils.audio_tracks(Path(project["source"]))
    return {"tracks": tracks, "selected": int((project.get("options") or {}).get("audio_track") or 0)}


@app.post("/api/projects/{pid}/audio")
def project_audio_set(pid: str, body: Dict[str, Any]) -> Dict[str, Any]:
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    try:
        track = max(0, int(body.get("index") or 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "Неверная дорожка") from None
    options = dict(project.get("options") or {})
    options["audio_track"] = track
    db.update_project(pid, options=options)
    return {"selected": track}


@app.get("/api/projects/{pid}/pip")
def project_pip(pid: str) -> Dict[str, Any]:
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    return {"pip": (project.get("options") or {}).get("pip") or {}}


@app.post("/api/projects/{pid}/pip")
def project_pip_set(pid: str, body: PipIn) -> Dict[str, Any]:
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    options = dict(project.get("options") or {})
    current = dict(options.get("pip") or {})
    if body.enabled is not None:
        current["enabled"] = body.enabled
    if body.cam:
        try:
            current["cam"] = {k: int(body.cam[k]) for k in ("x", "y", "w", "h")}
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "Неверные координаты камеры")
    if body.cam_corner in ("top-left", "top-right", "bottom-left", "bottom-right"):
        current["cam_corner"] = body.cam_corner
        current.pop("cam", None)
    if body.cam_share is not None:
        current["cam_share"] = max(0.15, min(0.45, float(body.cam_share)))
    if body.pos:
        current["pos"] = [max(0.0, min(1.0, float(body.pos[0]))), max(0.0, min(1.0, float(body.pos[1])))]
    if body.size is not None:
        current["size"] = max(0.12, min(0.45, float(body.size)))
    if body.radius is not None:
        current["radius"] = max(0, min(60, int(body.radius)))
    options["pip"] = current
    db.update_project(pid, options=options)
    return {"pip": current}


@app.get("/api/projects/{pid}/frame.jpg")
def project_frame(pid: str, t: float = 0.0, width: int = 900) -> FileResponse:
    project = db.get_project(pid)
    if not project or not project.get("source"):
        raise HTTPException(404, "Кадр недоступен")
    workdir = PROJECTS_DIR / pid
    out = workdir / f"frame_{int(t)}_{width}.jpg"
    if not out.exists():
        try:
            render.snapshot(Path(project["source"]), out, t=t, width=width)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, f"Не удалось получить кадр: {exc}")
    return FileResponse(out, media_type="image/jpeg")


@app.get("/api/settings")
def settings_get() -> Dict[str, Any]:
    from . import settings as app_settings

    data = app_settings.get()
    data["hw_available"] = render.hw_encoder()
    return data


@app.post("/api/settings")
def settings_set(body: SettingsIn) -> Dict[str, Any]:
    from . import settings as app_settings

    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    data = app_settings.update(patch)
    # выбор энкодера применяем сразу: кэш пробного кадра сбрасываем
    render._HW_CACHE.clear()
    data["hw_available"] = render.hw_encoder()
    return data


@app.get("/api/system")
def system_state() -> Dict[str, Any]:
    """Нагрузка машины для виджета: CPU, память, видеокарта."""
    from . import system_stats

    data = system_stats.snapshot({"hw": render.hw_encoder(), "limits": resources.summary()})
    data["job"] = system_stats.active_job(db.list_projects(5))
    return data


@app.get("/api/diagnostics")
def diagnostics_log(tail: int = 40) -> Dict[str, Any]:
    """Разбор app.log: падение, последний этап, ошибки — для окна «Диагностика»."""
    from . import diagnostics

    system: Dict[str, Any] = {}
    try:
        system = health()
    except Exception:  # noqa: BLE001 — разбор лога важнее телеметрии
        system = {}
    return diagnostics.report(data_dir=DATA_DIR, tail_lines=max(1, min(400, int(tail))),
                              system=system)


@app.get("/api/update")
def update_state(force: bool = False) -> Dict[str, Any]:
    """Состояние проверки обновлений; сеть — только в фоне или по force."""
    from . import updater

    if force:
        return updater.check(force=True)
    updater.maybe_check_async()
    return updater.payload()


@app.post("/api/update/settings")
def update_settings(body: UpdateSettingsIn) -> Dict[str, Any]:
    from . import updater

    return updater.set_enabled(body.enabled)


@app.get("/api/fonts")
def fonts() -> List[Dict[str, Any]]:
    from .subtitles import fonts_payload

    return list(fonts_payload()) + custom_fonts.payload()


@app.post("/api/fonts")
async def font_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    data = await file.read()
    if len(data) > MAX_FONT_BYTES:
        raise HTTPException(413, "Файл шрифта больше 24 МБ")
    try:
        return custom_fonts.save(file.filename or "font.ttf", data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Не удалось прочитать шрифт: {str(exc)[:200]}") from exc


@app.delete("/api/fonts/{key}")
def font_delete(key: str) -> Dict[str, Any]:
    if not custom_fonts.delete(key):
        raise HTTPException(404, "Шрифт не найден")
    return {"ok": True}


@app.get("/api/fonts.css")
def fonts_css() -> Response:
    lines = []
    for font in custom_fonts.list_custom():
        family = custom_fonts._clean_family(font.get("css") or f"VCCustom_{font['key']}").replace(" ", "_")
        lines.append(
            f'@font-face {{ font-family: "{family}"; '
            f'src: url("/userfonts/{font["file"]}"); font-display: swap; }}'
        )
    return Response("\n".join(lines), media_type="text/css")


@app.get("/api/projects")
def projects() -> List[Dict[str, Any]]:
    return db.list_projects(100)


@app.post("/api/projects")
def create_project(body: ProjectIn) -> Dict[str, Any]:
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "Добавьте ссылку на видео")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Ссылка должна начинаться с http:// или https://")
    project = db.create_project(url, pipeline.normalize_options(body.options))
    if body.prepare_only:
        jobs.submit_prepare(project["id"])
    else:
        jobs.submit_project(project["id"])
    return project


@app.post("/api/projects/{pid}/composition")
def project_composition(pid: str, body: Dict[str, Any]):
    from . import composition
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    if jobs.is_running(pid):
        raise HTTPException(409, "Дождитесь завершения обработки проекта")
    try:
        conf = composition.validate(body)
    except (ValueError, TypeError):
        raise HTTPException(400, "Проверьте файлы и параметры композиции") from None
    options = {**(project.get("options") or {}), "composition": conf}
    db.update_project(pid, options=options)
    clips = db.list_clips(pid)
    if clips:
        db.update_project(pid, status="running", stage="Пересборка композиции", progress=0, error=None)
    for clip in clips:
        jobs.submit_rerender(clip["id"], {})
    return {"ok": True, "clips": len(clips)}


@app.post("/api/composition/upload")
async def upload_composition(kind: str = Form(...), file: UploadFile = File(...)):
    from . import composition
    if kind not in ("logo", "game", "ad"):
        raise HTTPException(400, "Неизвестный тип файла")
    composition.ASSETS.mkdir(parents=True, exist_ok=True)
    temp = composition.ASSETS / (uuid.uuid4().hex + ".upload")
    try:
        total = 0
        with temp.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > 200 * 1024 * 1024:
                    raise ValueError("Лимит файла — 200 МБ")
                out.write(chunk)
        target = composition.ASSETS / (uuid.uuid4().hex + (".png" if kind == "logo" else ".mp4"))
        if kind == "logo":
            from PIL import Image
            with Image.open(temp) as image:
                image.thumbnail((2048, 2048))
                image.convert("RGBA").save(target)
        else:
            info = utils.probe(temp)
            if not 1 <= info["duration"] <= (120 if kind == "ad" else 600):
                raise ValueError("Реклама: 1–120 секунд; игра: 1–600 секунд")
            temp.replace(target)
        return {"id": target.name, "name": file.filename}
    except (ValueError, utils.MediaError, OSError) as exc:
        raise HTTPException(400, str(exc)) from None
    finally:
        temp.unlink(missing_ok=True)


@app.get("/api/composition/assets/{asset_id}")
def composition_asset(asset_id: str):
    from . import composition
    try:
        path=composition.asset(asset_id)
    except ValueError as exc:
        raise HTTPException(404,str(exc)) from None
    return FileResponse(path, media_type="image/png" if path.suffix==".png" else "video/mp4")


@app.get("/api/composition/game-info/{asset_id}")
def composition_game_info(asset_id: str):
    from . import composition
    try:
        path=composition.asset(asset_id)
        if path.suffix!='.mp4': raise ValueError("Нужен видеофайл")
        start,length=composition.gameplay_window(path)
        return {"start":start,"length":length,"duration":utils.probe(path)["duration"]}
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from None


class GameImportIn(BaseModel):
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")


@app.post("/api/composition/game")
def import_game(body: GameImportIn):
    from . import composition, downloader
    from tempfile import TemporaryDirectory
    composition.ASSETS.mkdir(parents=True, exist_ok=True)
    try:
        with TemporaryDirectory(dir=composition.ASSETS) as tmp:
            url = "https://www.youtube.com/watch?v=" + body.video_id
            duration = float(downloader.probe(url).get("duration") or 0)
            if duration <= 0:
                raise ValueError("Не удалось определить длительность игры")
            begin = max(0., (duration - 180.) / 2.)
            path = downloader.download_section(url, Path(tmp), begin,
                                               min(duration, begin + 180.), max_height=720)
            target = composition.ASSETS / (uuid.uuid4().hex + ".mp4")
            path.replace(target)
        return {"id": target.name, "name": "Игра с YouTube (участок из середины записи)"}
    except Exception:
        raise HTTPException(502, "Не удалось скачать игру. Попробуйте другой ролик или загрузите свой файл.") from None


@app.post("/api/discovery")
def discover_videos(body: DiscoveryIn) -> Dict[str, Any]:
    from . import discovery
    try:
        return discovery.recommend(body.audience, body.topic, body.query.strip(), body.sort)
    except Exception:
        raise HTTPException(502, "Не удалось получить рекомендации YouTube. Проверьте подключение и повторите поиск.") from None


@app.post("/api/probe")
def probe_video(body: ProbeIn) -> Dict[str, Any]:
    from . import downloader

    url = (body.url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Некорректная ссылка")
    try:
        return downloader.probe(url, browser=body.cookies_browser or None)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Не удалось получить информацию о видео: {str(exc)[:300]}") from exc


@app.post("/api/streams")
def stream_create(body: StreamIn) -> Dict[str, Any]:
    from . import live

    url = (body.url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Ссылка должна начинаться с http:// или https://")
    options = pipeline.normalize_options(body.options)
    project = db.create_project(url, options, title="Прямой эфир")
    db.update_project(project["id"], status="running", stage="Подключаюсь к эфиру…",
                      meta={"live": True, "live_status": "connecting", "live_processed": 0,
                            "live_clips": 0, "ad_intervals": []})
    jobs.submit_stream(project["id"], options)
    return db.get_project(project["id"])


@app.get("/api/streams")
def streams_list() -> List[Dict[str, Any]]:
    return [p for p in db.list_projects(100) if (p.get("meta") or {}).get("live")]


@app.get("/api/streams/{pid}")
def stream_detail(pid: str) -> Dict[str, Any]:
    project = db.get_project(pid)
    if not project or not (project.get("meta") or {}).get("live"):
        raise HTTPException(404, "Стрим не найден")
    clips = db.list_clips(pid)
    for clip in clips:
        preview = PROJECTS_DIR / pid / "previews" / f"{clip['id']}.mp4"
        clip["has_preview"] = preview.exists()
    return {"project": project, "clips": clips}


@app.post("/api/streams/{pid}/stop")
def stream_stop(pid: str) -> Dict[str, Any]:
    from . import live

    project = db.get_project(pid)
    if not project or not (project.get("meta") or {}).get("live"):
        raise HTTPException(404, "Стрим не найден")
    live.stop_stream(pid)
    db.update_project(pid, stage="Останавливаю запись…")
    return {"ok": True}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), options: Optional[str] = Form(None)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(400, "Файл не выбран")
    suffix = Path(file.filename).suffix.lower() or ".mp4"
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(400, f"Формат {suffix} не поддерживается — загрузите видео или аудио")
    # формат и прочие настройки приходят с формой: раньше они молча терялись
    # и проект всегда создавался с настройками по умолчанию
    chosen: Dict[str, Any] = {}
    if options:
        try:
            import json as _json

            chosen = _json.loads(options)
        except ValueError:
            chosen = {}
    project = db.create_project("local:source", pipeline.normalize_options(chosen),
                                title=file.filename)
    workdir = PROJECTS_DIR / project["id"]
    workdir.mkdir(parents=True, exist_ok=True)
    target = workdir / f"source{suffix}"
    written = 0
    try:
        with open(target, "wb") as fh:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    size_hint = (f"{MAX_UPLOAD_BYTES / 1024 ** 3:.1f} ГБ"
                                 if MAX_UPLOAD_BYTES >= 1024 ** 3
                                 else f"{MAX_UPLOAD_BYTES / 1024 ** 2:.0f} МБ")
                    raise HTTPException(
                        413,
                        f"Файл больше {size_hint} — загрузите фрагмент короче "
                        "или поднимите VIRALCUT_MAX_UPLOAD_GB",
                    )
                fh.write(chunk)
    except HTTPException:
        shutil.rmtree(workdir, ignore_errors=True)
        db.delete_project(project["id"])
        raise
    if target.stat().st_size < 1024:
        shutil.rmtree(workdir, ignore_errors=True)
        db.delete_project(project["id"])
        raise HTTPException(400, "Файл пустой или повреждён")
    # Проверяем, что это действительно медиа: иначе в списке появлялся бы
    # проект, который сразу уходит в error.
    try:
        from . import utils

        probed = utils.probe(target)
        if not probed.get("duration"):
            raise ValueError("нет длительности")
    except Exception:  # noqa: BLE001
        shutil.rmtree(workdir, ignore_errors=True)
        db.delete_project(project["id"])
        raise HTTPException(400, "Файл не похож на видео или аудио — проверьте содержимое") from None
    db.update_project(project["id"], source=str(target), title=file.filename)
    jobs.submit_prepare(project["id"])
    return db.get_project(project["id"]) or project


@app.get("/api/projects/{pid}")
def project_detail(pid: str) -> Dict[str, Any]:
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    clips = db.list_clips(pid)
    for clip in clips:
        preview = PROJECTS_DIR / pid / "previews" / f"{clip['id']}.mp4"
        clip["has_preview"] = preview.exists()
    source = project.get("source")
    preview = PROJECTS_DIR / pid / "preview.mp4"
    if preview.exists():
        project["source_url"] = f"/media/{pid}/preview.mp4"
    elif source:
        try:
            from urllib.parse import quote
            rel = Path(source).relative_to(PROJECTS_DIR).as_posix()
            project["source_url"] = "/media/" + quote(rel)
        except ValueError:
            pass
    return {"project": project, "clips": clips}


@app.post("/api/projects/{pid}/start")
def project_start(pid: str, body: StartIn = StartIn()) -> Dict[str, Any]:
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    if project.get("status") != "review":
        raise HTTPException(400, "Видео ещё не готово к настройке")
    if jobs.is_running(pid):
        raise HTTPException(409, "Обработка уже идёт — дождитесь окончания или отмените")
    options = pipeline.normalize_options(body.options or project.get("options"))
    pipeline.clear_cancel(pid)
    pending = [c for c in db.list_clips(pid) if c["status"] == "pending"]
    if not (options.get("segments") and pending):
        db.clear_clips(pid)
    db.update_project(pid, status="queued", stage="В очереди", progress=0, error=None,
                      options=options)
    jobs.submit_process(pid)
    return db.get_project(pid) or project


@app.post("/api/projects/{pid}/cancel")
def project_cancel(pid: str) -> Dict[str, Any]:
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    pipeline.request_cancel(pid)
    db.update_project(pid, status="cancelled", stage="Отменено", error=None)
    return {"ok": True}


@app.post("/api/projects/{pid}/retry")
def project_retry(pid: str, body: RetryIn = RetryIn()) -> Dict[str, Any]:
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    if jobs.is_running(pid):
        # текущая обработка ещё останавливается — поставим повтор в очередь
        pipeline.request_cancel(pid)
    print(f"[api] Пересборка проекта {pid} (force_hd={body.force_hd}, "
          f"prepare_only={body.prepare_only})", file=sys.stderr, flush=True)
    options = dict(project.get("options") or {})
    options["force_hd"] = bool(body.force_hd)
    if body.force_hd:
        # HD-повтор всегда целится в 1080p, даже если проект создавали в 360p
        options["max_height"] = max(1080, int(options.get("max_height") or 0))
    pipeline.clear_cancel(pid)
    meta = project.get("meta") or {}
    if body.force_hd and meta.get("segments_mode"):
        # моменты уже найдены: не тратим время на повторное распознавание,
        # просто заново скачиваем фрагменты в 1080p и рендерим
        db.reset_clips_pending(pid)
        db.update_project(pid, status="queued", stage="Готовлю HD-версии клипов",
                          progress=0, error=None, options=options)
        jobs.submit_process(pid)
        return db.get_project(pid) or project
    db.clear_clips(pid)
    db.update_project(pid, status="queued", stage="В очереди", progress=0, error=None,
                      options=options)
    if body.prepare_only:
        jobs.submit_prepare(pid)
    else:
        jobs.submit_project(pid)
    return db.get_project(pid) or project


@app.delete("/api/projects/{pid}")
def project_delete(pid: str) -> Dict[str, Any]:
    if not db.get_project(pid):
        raise HTTPException(404, "Проект не найден")
    from . import live

    # Сначала гасим запись/рендер и даём потокам увидеть отмену: иначе ffmpeg
    # продолжает писать в папку, которую мы сейчас удаляем.
    live.stop_stream(pid)
    pipeline.request_cancel(pid)
    db.delete_project(pid)
    pipeline.delete_project_files(pid)
    return {"ok": True}


@app.get("/api/clips/{cid}/subtitles.srt")
def clip_srt(cid: str) -> Response:
    """SRT для монтажа в своём редакторе: правленый текст уже внутри."""
    clip = db.get_clip(cid)
    if not clip:
        raise HTTPException(404, "Клип не найден")
    from . import subtitles

    body = subtitles.to_srt(clip.get("words") or [], float(clip["start"]), float(clip["end"]))
    if not body.strip():
        raise HTTPException(400, "В клипе нет субтитров")
    title = (clip.get("title") or "clip").replace("/", " ").replace('"', "").strip()[:60] or "clip"
    # кириллица в заголовке не влезает в latin-1 — отдаём имя по RFC 5987
    from urllib.parse import quote

    disposition = (f"attachment; filename=\"clip.srt\"; "
                   f"filename*=UTF-8''{quote(title + '.srt')}")
    return Response(content=body, media_type="application/x-subrip",
                    headers={"Content-Disposition": disposition})


@app.post("/api/projects/{pid}/pip/apply")
def project_pip_apply(pid: str) -> Dict[str, Any]:
    """Пересобирает готовые клипы проекта с текущими настройками окна камеры."""
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    clips = [c for c in db.list_clips(pid) if c.get("path")]
    if not clips:
        raise HTTPException(400, "Нет готовых клипов — сначала запустите нарезку")
    for clip in clips:
        jobs.submit_rerender(clip["id"], {})
    return {"ok": True, "clips": len(clips)}


@app.post("/api/clips/{cid}/rerender")
def clip_rerender(cid: str, body: ClipEdit) -> Dict[str, Any]:
    clip = db.get_clip(cid)
    if not clip:
        raise HTTPException(404, "Клип не найден")
    project = db.get_project(clip["project_id"])
    if project and not project.get("source"):
        # клип из прямого эфира: режем из записанных сегментов
        if not (PROJECTS_DIR / project["id"] / "segments" / "times.jsonl").exists():
            raise HTTPException(400, "Запись эфира не найдена — перерендер невозможен")
        recorded = float((project.get("meta") or {}).get("live_duration") or 0)
        if body.end and recorded and body.end > recorded + 0.5:
            raise HTTPException(400, "Конец клипа выходит за пределы записанной части эфира")
    payload = _clean_clip_edit(body)
    jobs.submit_rerender(cid, payload)
    return {"ok": True, "clip": db.get_clip(cid)}


@app.get("/api/projects/{pid}/zip")
def project_zip(pid: str) -> FileResponse:
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "Проект не найден")
    dest = PROJECTS_DIR / pid / f"viralcut_{pid}.zip"
    try:
        pipeline.export_zip(pid, dest)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    return FileResponse(dest, filename="viralcut_clips.zip", media_type="application/zip")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


custom_fonts.CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/fonts", StaticFiles(directory=str(ASSETS_DIR / "fonts")), name="fonts")
app.mount("/userfonts", StaticFiles(directory=str(custom_fonts.CUSTOM_DIR)), name="userfonts")
app.mount("/media", StaticFiles(directory=str(PROJECTS_DIR)), name="media")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
