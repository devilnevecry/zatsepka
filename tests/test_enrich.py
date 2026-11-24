"""Stage 8: enrichment unit tests on saved HTML samples."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.enrich.site import parse_site_html
from app.enrich.socials import is_social_only_website, normalize_social_url, normalize_socials
from app.enrich.template_detect import compute_flags, detect_template

FIXTURES = Path("tests/fixtures/sites")


@pytest.fixture(scope="module", autouse=True)
def _samples():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "contacts.html").write_text(
        """<html><head><meta name="generator" content="Tilda"></head><body>
        <a href="mailto:info@example.ru">info@example.ru</a>
        <div>+7 (845) 211-11-11</div>
        <a href="https://t.me/barber_saratov">Telegram</a>
        <a href="https://instagram.com/barber_saratov">Instagram</a>
        <a href="/contacts">Контакты</a></body></html>""",
        encoding="utf-8",
    )
    (FIXTURES / "wix.html").write_text('<html><body><script src="https://static.wixstatic.com/x.js"></script>Тест</body></html>', encoding="utf-8")
    (FIXTURES / "plain.html").write_text("<html><body><h1>Барбершоп</h1><p>Саратов</p></body></html>", encoding="utf-8")


@pytest.mark.unit
def test_parse_site_contacts():
    info = parse_site_html((FIXTURES / "contacts.html").read_text(encoding="utf-8"), "https://example.ru")
    assert "info@example.ru" in info.emails
    assert "+78452111111" in info.phones
    assert info.socials["telegram"].endswith("/barber_saratov")
    assert info.socials["instagram"] == "https://instagram.com/barber_saratov"


@pytest.mark.unit
def test_detect_templates():
    assert detect_template((FIXTURES / "contacts.html").read_text(encoding="utf-8"), "") == "tilda"
    assert detect_template((FIXTURES / "wix.html").read_text(encoding="utf-8"), "") == "wix"
    assert detect_template((FIXTURES / "plain.html").read_text(encoding="utf-8"), "") is None
    assert detect_template("", "https://shop.setup.shop/barber") == "setup.shop"


@pytest.mark.unit
def test_social_normalizers():
    assert normalize_social_url("https://t.me/barber") == ("https://t.me/barber", "barber")
    assert normalize_social_url("https://www.instagram.com/barber/?utm=x")[0] == "https://instagram.com/barber"
    assert normalize_social_url("https://vk.com/barber_sar")[0] == "https://vk.com/barber_sar"
    assert normalize_social_url("not a link") == (None, None)
    out = normalize_socials({"x": "https://t.me/a", "y": "https://vk.com/b"})
    assert set(out) == {"telegram", "vk"}


@pytest.mark.unit
def test_flags():
    assert compute_flags({"website": "", "socials": {}})["no_site"]
    assert compute_flags({"website": "", "socials": {"telegram": "https://t.me/x"}})["only_socials"]
    assert is_social_only_website("https://linktr.ee/barber")
    assert not is_social_only_website("https://example.ru")
    f = compute_flags({"website": "https://example.ru", "socials": {}, "extra": {"template_name": "tilda"}})
    assert f["template_site"] and f["template_name"] == "tilda"


@pytest.mark.unit
def test_dead_site_never_raises():
    import asyncio

    from app.enrich.site import fetch_site

    info = asyncio.run(fetch_site("http://127.0.0.1:9/dead"))
    assert info.emails == []
    assert info.errors
