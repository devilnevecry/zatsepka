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


@router.get("/page/diagnostics", response_class=HTMLResponse)
def diagnostics_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "diagnostics.html", {"active": "dashboard"})


@router.get("/page/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "dashboard.html", {"active": "dashboard"})


@router.get("/page/charts", response_class=HTMLResponse)
def charts_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "charts.html", {"active": "charts"})


@router.get("/page/profile", response_class=HTMLResponse)
def profile_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "profile.html", {"active": "profile"})


@router.get("/page/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "settings.html", {"active": "settings"})


@router.get("/page/keys", response_class=HTMLResponse)
def keys_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "keys.html", {"active": "keys"})


@router.get("/page/help", response_class=HTMLResponse)
def help_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "help.html", {"active": "help"})


@router.get("/page/ai", response_class=HTMLResponse)
def ai_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "ai.html", {"active": "ai"})


@router.get("/page/base", response_class=HTMLResponse)
def base_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "search.html", {"active": "base"})


@router.get("/page/{slug}", response_class=HTMLResponse)
def stub_page(request: Request, slug: str) -> HTMLResponse:
    title = STUB_TITLES.get(slug, "Раздел")
    return templates.TemplateResponse(request, "stub.html", {"active": slug, "title": title, "items": []})
