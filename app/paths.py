"""Filesystem paths used across the app (all relative to the project root)."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DEBUG_DIR = ROOT_DIR / "debug"
LOGS_DIR = ROOT_DIR / "logs"
DB_PATH = DATA_DIR / "zatsepka.db"
BROWSER_PROFILE_DIR = DATA_DIR / "browser_profile"
BROWSER_LOCK_PATH = DATA_DIR / "browser.lock"
STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "web" / "templates"
FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures"


def ensure_dirs() -> None:
    for d in (DATA_DIR, DEBUG_DIR, LOGS_DIR, BROWSER_PROFILE_DIR):
        d.mkdir(parents=True, exist_ok=True)
