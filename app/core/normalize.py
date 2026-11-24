"""Phone/name normalization (SPEC 5)."""

from __future__ import annotations

import re
from typing import Any

import phonenumbers

LEGAL_FORMS = (
    "ооо", "оао", "ао", "ип", "individual entrepreneur", "llc", "ltd", "inc", "gmbh", "ооо рф", "п ao",
)
PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_phone(raw: Any, region: str = "RU") -> str | None:
    if raw is None or raw == "":
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.startswith("+"):
        candidate = text
    else:
        candidate = text
    try:
        parsed = phonenumbers.parse(candidate, region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 10:
        return None
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    elif digits.startswith("7") and len(digits) == 11:
        pass
    elif len(digits) == 10:
        digits = "7" + digits
    return "+" + digits


def normalize_name(raw: Any) -> str:
    text = str(raw or "").casefold().strip()
    text = text.replace("«", " ").replace("»", " ").replace('"', " ").replace("'", " ")
    for form in LEGAL_FORMS:
        text = re.sub(rf"\b{re.escape(form)}\b", " ", text)
    text = PUNCT.sub(" ", text)
    return " ".join(text.split())


def normalize_website(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = "https://" + text
    return text.rstrip("/")


def normalize_socials(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        if value:
            out[str(key).casefold()] = str(value).strip()
    return out
