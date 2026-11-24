"""Page routes: shell, Search page, and stub pages for rail items."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.templating import templates

router = APIRouter()

STUB_TITLES = {
    "dashboard": "Дашборд",
    "profile": "Профиль",
    "chats": "Чаты",
    "otbor": "Отбор",
    "messages": "Сообщения",
    "ai": "ИИ",
    "base": "База",
    "keys": "Клавиши",
    "charts": "Графики",
    "settings": "Настройки",
    "help": "Помощь",
}


@router.get("/", response_class=HTMLResponse)
def search_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "search.html", {"active": "search"})


@router.get("/search", response_class=HTMLResponse)
def search_page_alias(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "search.html", {"active": "search"})


@router.get("/page/{slug}", response_class=HTMLResponse)
def stub_page(request: Request, slug: str) -> HTMLResponse:
    title = STUB_TITLES.get(slug, "Раздел")
    return templates.TemplateResponse(request, "stub.html", {"active": slug, "title": title, "items": []})
