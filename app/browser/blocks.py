"""Per-source block detection: captcha, consent, login walls -> NeedsHuman.

Checks URL, title and visible text markers. Pure functions so they are testable
offline; the browser layer feeds them page state.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlockMarkers:
    url_parts: tuple[str, ...]
    title_parts: tuple[str, ...]
    text_parts: tuple[str, ...]


MARKERS: dict[str, BlockMarkers] = {
    "google": BlockMarkers(
        url_parts=("sorry/index", "sorry/captcha", "consent.google.com"),
        title_parts=("unusual traffic", "необычный трафик", "подозрительный трафик"),
        text_parts=(
            "unusual traffic from your computer",
            "необычный трафик",
            "подозрительный трафик",
            "прежде чем продолжить",
            "before you continue to google",
            "i'm not a robot",
            "я не робот",
            "подтвердите, что вы не робот",
            "captcha",
        ),
    ),
    "yandex": BlockMarkers(
        url_parts=("showcaptcha", "captcha.yandex", "passport.yandex"),
        title_parts=("captcha", "капча", "подтвердите"),
        text_parts=(
            "подтвердите, что запросы отправляли вы",
            "введите символы с картинки",
            "ой, капча",
            "smart-captcha",
            "введите код с картинки",
            "доступ ограничен",
        ),
    ),
    "twogis": BlockMarkers(
        url_parts=("captcha", "antibot"),
        title_parts=("captcha", "капча", "доступ ограничен"),
        text_parts=(
            "подтвердите, что вы не робот",
            "введите символы с картинки",
            "доступ ограничен",
            "проверка браузера",
            "captcha",
        ),
    ),
}


def detect_block(source: str, url: str, title: str, text: str) -> str | None:
    """Return a human-readable reason when the page looks like a block, else None."""
    markers = MARKERS.get(source)
    if markers is None:
        return None
    url_l = (url or "").lower()
    title_l = (title or "").lower()
    text_l = (text or "").lower()[:20000]
    for part in markers.url_parts:
        if part in url_l:
            return f"block url: {part}"
    for part in markers.title_parts:
        if part in title_l:
            return f"block title: {part}"
    for part in markers.text_parts:
        if part in text_l:
            return f"block text: {part}"
    return None
