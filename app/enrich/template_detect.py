"""Website-builder/template detection (SPEC stage 8)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

SITE_BUILDER_DOMAINS = {
    "tilda": ("tilda.ws", "tilda.cc"),
    "wix": ("wixsite.com", "wix.com"),
    "nethouse": ("nethouse.ru",),
    "ukit": ("ukit.io", "u-kit.ru"),
    "jimdo": ("jimdo.com", "jimdo.ru"),
    "squarespace": ("squarespace.com",),
    "wordpress.com": ("wordpress.com",),
    "setup.shop": ("setup.shop",),
}

GENERATOR_MARKERS = {
    "tilda": ("tilda",),
    "wix": ("wix.com", "wixstatic"),
    "nethouse": ("nethouse",),
    "ukit": ("ukit",),
    "jimdo": ("jimdo",),
    "squarespace": ("squarespace",),
    "wordpress.com": ("wordpress.com",),
    "setup.shop": ("setup.shop",),
}


def detect_template(html: str, url: str = "") -> str | None:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for name, domains in SITE_BUILDER_DOMAINS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return name
    low = html[:200000].lower()
    for name, markers in GENERATOR_MARKERS.items():
        if any(m in low for m in markers):
            return name
    m = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', low)
    if m:
        content = m.group(1)
        for name, markers in GENERATOR_MARKERS.items():
            if any(marker in content for marker in markers):
                return name
    return None


def compute_flags(lead: dict) -> dict:
    """no_site / only_socials / template_site per SPEC stage 8."""
    from app.enrich.socials import is_social_only_website

    website = lead.get("website") or ""
    socials = lead.get("socials") or {}
    has_social = any(socials.values())
    has_site = bool(website) and not is_social_only_website(website)
    template_name = lead.get("extra", {}).get("template_name")
    return {
        "no_site": not has_site and not has_social,
        "only_socials": (not has_site and has_social) or (website and is_social_only_website(website)),
        "template_site": bool(template_name),
        "template_name": template_name or "",
        "chain_count": lead.get("extra", {}).get("chain_count", 0),
    }
