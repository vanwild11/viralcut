"""Фоновые задачи: очередь проектов и перерендер клипов."""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from . import db, live, pipeline
from .config import MAX_WORKERS

_project_pool = ThreadPoolExecutor(max_workers=max(1, MAX_WORKERS), thread_name_prefix="project")
_clip_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="clip")
_lock = threading.Lock()

# Каждый эфир — отдельный поток. Раньше стримы шли через пул на 3 места, и
# несколько «ждущих эфир» записей навсегда занимали очередь: следующая запись
# висела на «Запись · подключение», хотя ничего не начиналось.
MAX_STREAMS = max(1, int(os.environ.get("VIRALCUT_MAX_STREAMS", "6")))
_streams: Dict[str, threading.Thread] = {}
_streams_lock = threading.Lock()


_running: Dict[str, int] = {}
_pending: Dict[str, Any] = {}
_running_lock = threading.Lock()


def is_running(pid: str) -> bool:
    """Идёт ли уже обработка этого проекта (защита от двойного запуска)."""
    with _running_lock:
        return bool(_running.get(pid))


def _mark(pid: str, delta: int) -> None:
    with _running_lock:
        count = _running.get(pid, 0) + delta
        if count <= 0:
            _running.pop(pid, None)
        else:
            _running[pid] = count


def _guarded(pid: str, target) -> None:
    """Запускает задачу, если для проекта ещё нет активной обработки.

    Если обработка уже идёт (например, пользователь нажал «повторить» во время
    отмены), задача ставится в очередь на этот же проект и стартует сразу после
    завершения текущей — вместо второй параллельной обработки.
    """
    with _running_lock:
        if _running.get(pid):
            _pending[pid] = target
            return
        _running[pid] = 1

    def work() -> None:
        try:
            target()
        except Exception as exc:  # noqa: BLE001
            db.update_project(pid, status="error", error=str(exc)[:600], stage="Ошибка")
        finally:
            with _running_lock:
                _running.pop(pid, None)
                nxt = _pending.pop(pid, None)
            if nxt is not None:
                _guarded(pid, nxt)

    _project_pool.submit(work)


def submit_project(pid: str) -> None:
    _guarded(pid, lambda: pipeline.run_project(pid))


def submit_stream(pid: str, options: dict) -> None:
    with _streams_lock:
        existing = _streams.get(pid)
        if existing is not None and existing.is_alive():
            return
        if sum(1 for t in _streams.values() if t.is_alive()) >= MAX_STREAMS:
            db.update_project(
                pid, status="error", stage="Слишком много одновременных записей",
                error=f"Одновременно можно записывать не больше {MAX_STREAMS} эфиров.")
            return

        def work() -> None:
            try:
                live.run_stream(pid, options)
            except Exception as exc:  # noqa: BLE001
                db.update_project(pid, status="error", error=str(exc)[:600], stage="Ошибка стрима")
            finally:
                with _streams_lock:
                    _streams.pop(pid, None)

        thread = threading.Thread(target=work, name=f"live-{pid}", daemon=True)
        _streams[pid] = thread
        thread.start()


def submit_prepare(pid: str) -> None:
    _guarded(pid, lambda: pipeline.prepare_project(pid))


def submit_process(pid: str) -> None:
    _guarded(pid, lambda: pipeline.process_project(pid))


def submit_rerender(clip_id: str, payload: Dict[str, Any]) -> None:
    clip = db.get_clip(clip_id)
    if not clip:
        return
    pid = clip["project_id"]
    _mark(pid, 1)
    db.update_clip(clip_id, status="rendering", error=None)

    def work() -> None:
        try:
            pipeline.rerender_clip(clip_id, payload)
        except Exception as exc:  # noqa: BLE001
            db.update_clip(clip_id, status="error", error=str(exc)[:500])
        finally:
            _mark(pid, -1)
            clips = db.list_clips(pid)
            if clips and is_running(pid):
                done = sum(c["status"] in ("ready", "error") for c in clips)
                db.update_project(pid, stage=f"Пересборка: {done} из {len(clips)} готово", progress=done / len(clips))
            if not is_running(pid) and clips and all(c["status"] in ("ready", "error") for c in clips):
                failures = sum(c["status"] == "error" for c in clips)
                db.update_project(pid, status="ready", stage="Готово" if not failures else "Готово с ошибками", progress=1)

    _clip_pool.submit(work)
