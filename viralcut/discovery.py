"""Metadata-only YouTube discovery. Never starts media downloads."""
from __future__ import annotations

import math
import re
import threading
import time
from typing import Any

_CACHE: dict[tuple, tuple[float, dict]] = {}
_LOCK = threading.Lock()
TOPICS = {
    'gameplay': ('minecraft parkour gameplay no commentary', 'minecraft parkour gameplay no commentary'),
    'general': ('подкаст интервью', 'podcast interview'),
    'business': ('бизнес предпринимательство интервью', 'business entrepreneur interview'),
    'science': ('наука технологии подкаст', 'science technology podcast'),
    'psychology': ('психология отношения подкаст', 'psychology relationships podcast'),
    'comedy': ('юмор стендап интервью', 'comedy interview podcast'),
}


def rank_entries(entries: list[dict], audience: str, sort: str) -> list[dict]:
    results = []
    seen = set()
    for entry in entries:
        video_id = entry.get('id') or ''
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id) or video_id in seen:
            continue
        seen.add(video_id)
        if entry.get('live_status') in ('is_live', 'is_upcoming', 'post_live'):
            continue
        duration = entry.get('duration')
        if not isinstance(duration, (int, float)) or not 240 <= duration <= 14400:
            continue
        title = str(entry.get('title') or '')
        cyrillic = len(re.findall(r'[А-Яа-яЁё]', title))
        latin = len(re.findall(r'[A-Za-z]', title))
        language = 'ru' if cyrillic > latin else 'en' if latin > 0 else 'unknown'
        if language != audience:
            continue
        views = entry.get('view_count')
        views = max(0, int(views)) if isinstance(views, (int, float)) else None
        # Transparent heuristic: log views plus duration preference, not predicted virality.
        fit = 2 if 600 <= duration <= 7200 else 0
        score = math.log10((views or 0) + 1) + fit
        results.append({
            'id': video_id, 'url': f'https://www.youtube.com/watch?v={video_id}',
            'thumbnail': f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg',
            'title': title, 'channel': entry.get('channel') or entry.get('uploader') or '',
            'duration': duration, 'views': views, 'language_hint': language,
            'reason': 'Есть материал для нескольких клипов' if fit else 'Подходит по длительности',
            '_score': score,
        })
    results.sort(key=lambda r: (r['views'] or 0) if sort == 'views' else r['_score'], reverse=True)
    for item in results:
        item.pop('_score')
    return results[:12]


def recommend(audience: str, topic: str, query: str, sort: str) -> dict[str, Any]:
    key = (audience, topic, query, sort)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and time.monotonic() - cached[0] < 900:
            return cached[1]
        # Bound parallel searches; cache also avoids repeated requests on double clicks.
        import yt_dlp
        base = TOPICS[topic][0 if audience == 'ru' else 1]
        terms = query if topic == 'gameplay' and query else (f'{query} {base}' if query else base)
        opts = {
            'quiet': True, 'no_warnings': True, 'skip_download': True,
            'extract_flat': True, 'socket_timeout': 12, 'retries': 1,
            'extractor_retries': 1, 'playlistend': 40,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f'ytsearch40:{terms}', download=False)
        entries = list((info or {}).get('entries') or [])
        data = {'items': rank_entries([e for e in entries if e], audience, sort),
                'query': terms, 'notice': 'Подборка среди результатов поиска YouTube, а не общий рейтинг платформы. Язык предположен по заголовку; язык речи и состав аудитории не проверены. Поиск не скачивает видео.',
                'cached_minutes': 15}
        if len(_CACHE) >= 64:
            _CACHE.clear()
        _CACHE[key] = (time.monotonic(), data)
        return data
