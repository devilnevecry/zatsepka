"""Outreach API: prompts, links, messages, templates, presets."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Body
from fastapi.responses import Response

from app.ai.prompts import DEFAULT_STATIC_TEMPLATES, build_prompt, render_static, validate_template
from app.db import session_scope
from app.models import Lead, Message, Template

router = APIRouter(prefix="/api")


def _digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def channel_link(lead: dict[str, Any], channel: str, text: str, subject: str = "") -> str | None:
    """Generate target URL; no navigation is performed by the backend."""
    socials = lead.get("socials") or {}
    phone = lead.get("phones") or []
    digits = _digits(phone[0]) if phone else ""
    encoded = quote(text or "")
    if channel == "whatsapp":
        return f"https://wa.me/{digits}?text={encoded}" if digits else None
    if channel == "telegram":
        if socials.get("telegram"):
            return f"https://t.me/{str(socials['telegram']).rsplit('/', 1)[-1]}"
        return f"https://t.me/{digits}" if digits else None
    if channel == "instagram":
        return socials.get("instagram")
    if channel == "viber":
        return f"viber://chat?number=%2B{digits}" if digits else None
    if channel == "email":
        emails = lead.get("emails") or []
        if emails:
            return f"mailto:{emails[0]}?subject={quote(subject)}&body={encoded}"
        return None
    if channel == "call":
        return f"tel:+{digits}" if digits else None
    return None


@router.post("/prompts/build")
def build_prompt_api(body: dict = Body(...)) -> dict:
    from app import config

    with session_scope() as s:
        settings = config.get_settings(s)
    lead = body.get("lead") or {}
    channel = body.get("channel", "telegram")
    return {"prompt": build_prompt(lead, settings, channel)}


@router.get("/prompts/template")
def get_prompt_template() -> dict:
    from app import config

    with session_scope() as s:
        settings = config.get_settings(s)
    templates = settings.get("prompt_templates") or {}
    return {"template": templates.get("default", ""), "variables": list((templates.get("default") or "").count("{" for _ in [0]) and [] or [])}


@router.post("/prompts/template")
def save_prompt_template(body: dict = Body(...)) -> dict:
    from app import config

    text = str(body.get("template", ""))
    unknown = validate_template(text)
    with session_scope() as s:
        settings = config.get_settings(s)
        templates = dict(settings.get("prompt_templates") or {})
        templates["default"] = text
        config.set_setting(s, "prompt_templates", templates)
    return {"ok": True, "unknown_variables": unknown}


@router.post("/prompts/batch")
def batch_prompts(body: dict = Body(...)) -> Response:
    from app import config

    ids = body.get("ids") or []
    with session_scope() as s:
        settings = config.get_settings(s)
        leads = [s.get(Lead, int(i)).to_dict() for i in ids if s.get(Lead, int(i))]
    content = "\n\n---\n\n".join(f"# {lead['name']}\n\n{build_prompt(lead, settings)}" for lead in leads)
    return Response(content, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="prompts.md"'})


@router.post("/messages/link")
def message_link(body: dict = Body(...)) -> dict:
    lead = body.get("lead") or {}
    channel = body.get("channel", "telegram")
    url = channel_link(lead, channel, str(body.get("text", "")), str(body.get("subject", "")))
    return {"url": url, "needs_clipboard": channel in ("telegram", "instagram")}


@router.post("/messages/sent")
def mark_sent(body: dict = Body(...)) -> dict:
    lead_id = int(body.get("lead_id", 0))
    text = str(body.get("text", ""))
    channel = str(body.get("channel", "telegram"))
    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        if not lead:
            return {"ok": False}
        s.add(Message(lead_id=lead_id, channel=channel, direction="out", text=text, status="sent"))
        lead.status = "waiting_reply"
    return {"ok": True}


@router.post("/messages/replied")
def mark_replied(body: dict = Body(...)) -> dict:
    lead_id = int(body.get("lead_id", 0))
    text = str(body.get("text", ""))
    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        if not lead:
            return {"ok": False}
        s.add(Message(lead_id=lead_id, channel="telegram", direction="in", text=text, status="sent"))
        lead.status = "replied"
    return {"ok": True}


@router.get("/messages/conversations")
def conversations() -> list[dict]:
    with session_scope() as s:
        lead_ids = [m.lead_id for m in s.query(Message).all()]
        out = []
        for lead_id in dict.fromkeys(lead_ids):
            lead = s.get(Lead, lead_id)
            if lead:
                d = lead.to_dict()
                d["messages"] = [
                    {"id": m.id, "channel": m.channel, "direction": m.direction, "text": m.text, "status": m.status}
                    for m in s.query(Message).filter_by(lead_id=lead_id).order_by(Message.id).all()
                ]
                out.append(d)
        return out


@router.get("/templates")
def list_templates() -> list[dict]:
    with session_scope() as s:
        rows = s.query(Template).order_by(Template.id).all()
        if not rows:
            return [{"id": 0, "name": flag or "По умолчанию", "channel": "", "body": body, "for_flag": flag} for flag, body in DEFAULT_STATIC_TEMPLATES.items()]
        return [{"id": r.id, "name": r.name, "channel": r.channel, "body": r.body, "for_flag": r.for_flag} for r in rows]


@router.post("/templates")
def save_template(body: dict = Body(...)) -> dict:
    with session_scope() as s:
        existing = s.get(Template, int(body["id"])) if body.get("id") else None
        t = existing or Template(name=str(body.get("name", "")), channel=str(body.get("channel", "")), body=str(body.get("body", "")), for_flag=str(body.get("for_flag", "")))
        for key in ("name", "channel", "body", "for_flag"):
            if key in body:
                setattr(t, key, str(body[key]))
        if existing is None:
            s.add(t)
        s.flush()
        return {"id": t.id}


@router.post("/templates/render")
def render_template_api(body: dict = Body(...)) -> dict:
    return {"text": render_static(str(body.get("body", "")), body.get("lead") or {})}


@router.post("/presets/save")
def save_preset(body: dict = Body(...)) -> dict:
    from app import config

    with session_scope() as s:
        presets = list(config.get_settings(s).get("filter_presets") or [])
        presets.append(body)
        config.set_setting(s, "filter_presets", presets)
    return {"ok": True, "count": len(presets)}
