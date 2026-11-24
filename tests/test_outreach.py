"""Stage 9: prompt rendering, links, message transitions, batch export."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.ai.prompts import DEFAULT_PROMPT_TEMPLATE, build_prompt, render_static, validate_template
from app.db import session_scope
from app.main import create_app
from app.models import Lead
from app.web.routes.outreach import channel_link

LEAD = {
    "name": "Барбершоп Борода", "category": "барбершоп", "city": "Саратов",
    "address": "ул. Лермонтова, 1", "rating": 4.7, "reviews_count": 88,
    "website": "https://example.ru", "socials": {"telegram": "https://t.me/barber"},
    "emails": ["info@example.ru"], "phones": ["+78452111111"],
    "top_reviews": ["Отличный сервис"], "flags": {"no_site": False},
}


@pytest.mark.unit
def test_prompt_all_variables_render():
    settings = {"my_offer": "Скидка 20%", "prompt_tone": "дружелюбный", "prompt_length": "короткий"}
    text = build_prompt(LEAD, settings)
    assert "Барбершоп Борода" in text
    assert "Скидка 20%" in text
    assert "Саратов" in text
    assert "не указано" not in text or "соцсети" in text.lower()


@pytest.mark.unit
def test_prompt_missing_fields_no_none():
    text = build_prompt({"name": "Только имя"}, {})
    assert "None" not in text
    assert "не указано" in text


@pytest.mark.unit
def test_validate_template():
    assert validate_template(DEFAULT_PROMPT_TEMPLATE) == []
    assert "bogus" in validate_template("{name} {bogus}")


@pytest.mark.unit
def test_channel_links():
    assert channel_link(LEAD, "whatsapp", "Привет") == "https://wa.me/78452111111?text=%D0%9F%D1%80%D0%B8%D0%B2%D0%B5%D1%82"
    assert channel_link(LEAD, "telegram", "x") == "https://t.me/barber"
    assert channel_link({"phones": ["+78452111111"]}, "telegram", "x") == "https://t.me/78452111111"
    assert channel_link(LEAD, "email", "Текст", "Тема").startswith("mailto:info@example.ru?subject=")
    assert channel_link(LEAD, "viber", "x") == "viber://chat?number=%2B78452111111"
    assert channel_link(LEAD, "call", "") == "tel:+78452111111"
    assert channel_link({}, "whatsapp", "x") is None


@pytest.mark.unit
def test_static_template_render():
    text = render_static("Здравствуйте, {name} из {city}!", LEAD)
    assert "Барбершоп Борода" in text and "Саратов" in text


@pytest.mark.integration
def test_message_status_transitions(tmp_db):
    with session_scope() as s:
        s.add(Lead(dedupe_key="k1", name="Тест", status="new"))
    with TestClient(create_app()) as c:
        r = c.post("/api/messages/sent", json={"lead_id": 1, "text": "Привет", "channel": "telegram"})
        assert r.json()["ok"]
        leads = c.get("/api/leads?tab=base").json()
        assert leads[0]["status"] == "waiting_reply"
        r2 = c.post("/api/messages/replied", json={"lead_id": 1, "text": "Да"})
        assert r2.json()["ok"]
        leads = c.get("/api/leads?tab=base").json()
        assert leads[0]["status"] == "replied"
        conv = c.get("/api/messages/conversations").json()
        assert len(conv) == 1 and len(conv[0]["messages"]) == 2


@pytest.mark.integration
def test_batch_prompt_export(tmp_db):
    with session_scope() as s:
        s.add(Lead(dedupe_key="k1", name="Тест", city="Саратов"))
    with TestClient(create_app()) as c:
        r = c.post("/api/prompts/batch", json={"ids": [1]})
        assert r.status_code == 200
        assert "Тест" in r.text
