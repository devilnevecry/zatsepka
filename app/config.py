"""Settings with SPEC 6 defaults, persisted in the settings table.

Values are merged over defaults on every read so edits take effect without restart.
A small in-process cache avoids a DB hit per request; writes invalidate it.
"""

from __future__ import annotations

import copy
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.models import Setting

DEFAULTS: dict[str, Any] = {
    "country": "Россия",
    "cities": ["Саратов"],
    "categories": [
        "барбершоп",
        "салон красоты",
        "кофейня",
        "стоматология",
        "автосервис",
        "фитнес-клуб",
    ],
    "sources": {"google": True, "yandex": True, "twogis": True},
    "base_domains": {"google": "google.com", "yandex": "yandex.ru", "twogis": "2gis.ru"},
    "pause_min": 0.8,
    "pause_max": 2.5,
    "pair_pause_min": 4.0,
    "pair_pause_max": 10.0,
    "max_results_per_pair": 60,
    "max_minutes": 60,
    "max_scrolls": 60,
    "skip_days": 14,
    "no_repeat": True,
    "force": False,
    "phone_region": "RU",
    "ollama_url": "http://127.0.0.1:11434",
    "chrome_path": "",
    "my_offer": "",
    "prompt_tone": "дружелюбный, без давления",
    "prompt_length": "короткий (до 700 символов)",
    "theme": "dark",
    "profile_name": "Оператор",
    "profile_avatar": "",
    "hotkeys": {
        "focus_search": "/",
        "next_card": "j",
        "prev_card": "k",
        "add_to_base": "b",
        "open_drawer": "Enter",
        "close": "Escape",
        "start_search": "s",
        "mark_sent": "m",
    },
    "filter_presets": [],
    "prompt_templates": {},
    "enrich_concurrency": 5,
}

_lock = threading.Lock()
_cache: dict[str, Any] | None = None


def get_settings(session: Session) -> dict[str, Any]:
    global _cache
    with _lock:
        if _cache is not None:
            return copy.deepcopy(_cache)
    merged = copy.deepcopy(DEFAULTS)
    for row in session.query(Setting).all():
        merged[row.key] = row.value
    with _lock:
        _cache = copy.deepcopy(merged)
    return merged


def set_setting(session: Session, key: str, value: Any) -> None:
    global _cache
    row = session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.flush()
    with _lock:
        _cache = None


def update_settings(session: Session, values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        if key in DEFAULTS:
            set_setting(session, key, value)
    return get_settings(session)


def invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None
