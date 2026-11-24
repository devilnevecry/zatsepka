"""Social profile URL normalization (SPEC stage 8)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

SOCIAL_PATTERNS = {
    "instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/([\w.]+)/?", re.I),
    "telegram": re.compile(r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([\w]+)/?", re.I),
    "whatsapp": re.compile(r"(?:https?://)?(?:www\.)?wa\.me/(\d+)", re.I),
    "viber": re.compile(r"(?:https?://)?(?:www\.)?viber\.me/(\d+)", re.I),
    "vk": re.compile(r"(?:https?://)?(?:www\.)?vk\.com/([\w.]+)", re.I),
    "facebook": re.compile(r"(?:https?://)?(?:www\.)?facebook\.com/([\w.]+)", re.I),
    "youtube": re.compile(r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:@)?|youtu\.be/)([\w.-]+)", re.I),
}

SOCIAL_DOMAINS = {
    "instagram": "instagram.com",
    "telegram": "t.me",
    "whatsapp": "wa.me",
    "viber": "viber.me",
    "vk": "vk.com",
    "facebook": "facebook.com",
    "youtube": "youtube.com",
}


def normalize_social_url(raw: str) -> tuple[str | None, str | None]:
    """Return (canonical url, username) or (None, None) for unknown links."""
    text = str(raw or "").strip()
    if not text:
        return None, None
    for key, pattern in SOCIAL_PATTERNS.items():
        m = pattern.search(text)
        if m:
            ident = m.group(1)
            if key == "whatsapp":
                return f"https://wa.me/{ident}", ident
            if key == "viber":
                return f"https://viber.me/{ident}", ident
            if key == "telegram":
                return f"https://t.me/{ident}", ident
            return f"https://{SOCIAL_DOMAINS[key]}/{ident}", ident
    return None, None


def normalize_socials(raw: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for value in (raw or {}).values():
        url, _ = normalize_social_url(str(value or ""))
        if not url:
            continue
        for key, domain in SOCIAL_DOMAINS.items():
            if domain in url:
                out[key] = url
                break
    return out


def is_social_only_website(website: str) -> bool:
    host = urlparse(website).netloc.lower().removeprefix("www.")
    social_hosts = {"instagram.com", "t.me", "vk.com", "facebook.com", "youtube.com", "linktr.ee", "taplink.cc"}
    return any(host == h or host.endswith("." + h) for h in social_hosts)
