"""Website contact extraction with httpx (SPEC stage 8)."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from app.core.normalize import normalize_phone

CONTACT_PATHS = ("/", "/contacts", "/kontakty", "/contact")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
PHONE_RE = re.compile(r"(?:\+7|8)[\s(\-]*\d{3}[\s)\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
SOCIAL_DOMAINS = {
    "instagram": ("instagram.com", "insta.fm"),
    "telegram": ("t.me", "telegram.me"),
    "whatsapp": ("wa.me", "whatsapp.com"),
    "viber": ("viber.me", "vb.me"),
    "vk": ("vk.com", "vk.ru"),
    "facebook": ("facebook.com", "fb.com"),
    "youtube": ("youtube.com", "youtu.be"),
}


@dataclass
class SiteContactInfo:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    socials: dict[str, str] = field(default_factory=dict)
    pages_fetched: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: SiteContactInfo) -> None:
        for e in other.emails:
            if e not in self.emails:
                self.emails.append(e)
        for p in other.phones:
            if p not in self.phones:
                self.phones.append(p)
        for k, v in other.socials.items():
            self.socials.setdefault(k, v)
        self.pages_fetched += other.pages_fetched


def parse_site_html(html: str, base_url: str = "") -> SiteContactInfo:
    """Pure parse fn: extract emails, phones, socials from one page."""
    info = SiteContactInfo(pages_fetched=1)
    info.emails = list(dict.fromkeys(EMAIL_RE.findall(html)))
    for match in PHONE_RE.finditer(html):
        phone = normalize_phone(match.group(0))
        if phone and phone not in info.phones:
            info.phones.append(phone)
    parser = HTMLParser(html)
    for node in parser.css("a[href]"):
        href = node.attributes.get("href") or ""
        full = urljoin(base_url, href) if base_url else href
        low = full.lower()
        for key, domains in SOCIAL_DOMAINS.items():
            if any(d in low for d in domains) and key not in info.socials:
                info.socials[key] = full
    return info


def _same_domain(a: str, b: str) -> bool:
    try:
        return urlparse(a).netloc.lower().removeprefix("www.") == urlparse(b).netloc.lower().removeprefix("www.")
    except ValueError:
        return False


async def fetch_site(url: str, max_pages: int = 3, concurrency: int = 5) -> SiteContactInfo:
    """Fetch main + /contacts + /kontakty pages, only same-domain links named 'контакты'."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Rozvedka/0.1)"}
    semaphore = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(8.0)

    async def fetch(client: httpx.AsyncClient, target: str) -> SiteContactInfo:
        async with semaphore:
            try:
                resp = await client.get(target, timeout=timeout, follow_redirects=True)
                if len(resp.content) > 2 * 1024 * 1024:
                    return SiteContactInfo(errors=["body too large"])
                return parse_site_html(resp.text, str(resp.url))
            except Exception as exc:  # noqa: BLE001 - dead sites never fail the job
                return SiteContactInfo(errors=[f"{target}: {exc}"])

    async with httpx.AsyncClient(headers=headers) as client:
        targets = [url] + [urljoin(url, p) for p in CONTACT_PATHS[1:]]
        results = await asyncio.gather(*(fetch(client, t) for t in targets[:max_pages]))
    combined = SiteContactInfo()
    for r in results:
        combined.merge(r)
        combined.errors.extend(r.errors)
    return combined


def enrich_lead_sync(lead: dict[str, Any]) -> dict[str, Any]:
    """Blocking wrapper used by the job step and manual action."""
    website = lead.get("website") or ""
    if not website:
        return lead
    info = asyncio.run(fetch_site(website))
    lead.setdefault("emails", [])
    for e in info.emails:
        if e not in lead["emails"]:
            lead["emails"].append(e)
    lead.setdefault("phones", [])
    for p in info.phones:
        if p not in lead["phones"]:
            lead["phones"].append(p)
    lead.setdefault("socials", {})
    for k, v in info.socials.items():
        lead["socials"].setdefault(k, v)
    lead.setdefault("extra", {})["enrich_errors"] = info.errors
    return lead
