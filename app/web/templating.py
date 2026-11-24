"""Jinja2 templates for the app shell."""

from fastapi.templating import Jinja2Templates

from app.paths import TEMPLATES_DIR

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
