"""Prompt construction for cloud chatbots - no model calls from the app."""

from __future__ import annotations

import string
from typing import Any

DEFAULT_PROMPT_TEMPLATE = (
    "Ты — помощник по холодным продажам. Сообщение должно быть на русском языке, без объяснений.\n"
    "Лид: {name} | {category} | {city} | {address}\n"
    "Рейтинг: {rating}, отзывов: {reviews_count}. Флаги: {flag}. Сайт: {website}.\n"
    "Соцсети: {socials}. Отзывы: {top_reviews}. Часы: {hours}.\n"
    "Наше предложение: {my_offer}\n"
    "Канал: {channel}. Тон: {tone}. Длина: {length}.\n"
    "Верни ТОЛЬКО итоговый текст сообщения, не выдумывай факты."
)

VARIABLES = (
    "name", "category", "city", "address", "rating", "reviews_count", "flag",
    "website", "socials", "top_reviews", "my_offer", "channel", "tone", "length", "hours",
)


def _safe(value: Any) -> str:
    if value is None or value == "" or value == [] or value == {}:
        return "не указано"
    if isinstance(value, list):
        return ", ".join(_safe(v) for v in value[:5])
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items() if v) or "не указано"
    return str(value)


def build_prompt(lead: dict[str, Any], settings: dict[str, Any], channel: str = "telegram") -> str:
    template = (settings.get("prompt_templates") or {}).get("default") or DEFAULT_PROMPT_TEMPLATE
    flags = lead.get("flags") or {}
    flag_names = [k for k, v in flags.items() if v and isinstance(v, bool)]
    hours = lead.get("hours") or {}
    values = {
        "name": _safe(lead.get("name")),
        "category": _safe(lead.get("category")),
        "city": _safe(lead.get("city")),
        "address": _safe(lead.get("address")),
        "rating": _safe(lead.get("rating")),
        "reviews_count": _safe(lead.get("reviews_count")),
        "flag": _safe(", ".join(flag_names)),
        "website": _safe(lead.get("website")),
        "socials": _safe(lead.get("socials")),
        "top_reviews": _safe(lead.get("top_reviews")),
        "hours": _safe(hours),
        "my_offer": _safe(settings.get("my_offer")),
        "channel": _safe(channel),
        "tone": _safe(settings.get("prompt_tone")),
        "length": _safe(settings.get("prompt_length")),
    }
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        # tolerate unknown variables in user-edited templates
        return template


def validate_template(text: str) -> list[str]:
    fields = []
    for _, field, _, _ in string.Formatter().parse(text):
        if field and field not in VARIABLES:
            fields.append(field)
    return fields


DEFAULT_STATIC_TEMPLATES = {
    "": "Здравствуйте, {name}! Меня зовут Оператор, я из Саратова. Предлагаю {category} — подробности в сообщении.",
    "no_site": "Здравствуйте! Увидел ваш {category} в {city} — давайте обсудим сотрудничество.",
    "only_socials": "Здравствуйте, {name}! Пишу по поводу вашего {category} в {city}. Есть предложение.",
}

STATIC_VARIABLES = ("name", "category", "city", "rating", "flag")


def render_static(body: str, lead: dict[str, Any]) -> str:
    flags = lead.get("flags") or {}
    flag = next((k for k, v in flags.items() if v and isinstance(v, bool)), "")
    values = {
        "name": _safe(lead.get("name")),
        "category": _safe(lead.get("category")),
        "city": _safe(lead.get("city")),
        "rating": _safe(lead.get("rating")),
        "flag": flag,
    }
    try:
        return body.format(**values)
    except (KeyError, ValueError):
        return body
