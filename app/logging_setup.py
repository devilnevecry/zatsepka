"""Rotating UTF-8 logs: logs/app.log plus per-module logs/<module>.log."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.paths import LOGS_DIR, ensure_dirs

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_configured = False


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    _utf8_console()
    if _configured:
        return
    ensure_dirs()
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter(_FORMAT)
    file_handler = RotatingFileHandler(LOGS_DIR / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(file_handler)
    root.addHandler(console)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    _configured = True


def get_module_logger(module_id: str) -> logging.Logger:
    """Per-module rotating log used by the hub (logs/<module>.log)."""
    setup_logging()
    logger = logging.getLogger(f"module.{module_id}")
    if not any(isinstance(h, RotatingFileHandler) and getattr(h, "zatsepka_module", None) == module_id for h in logger.handlers):
        ensure_dirs()
        handler = RotatingFileHandler(LOGS_DIR / f"{module_id}.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter(_FORMAT))
        handler.zatsepka_module = module_id  # type: ignore[attr-defined]
        logger.addHandler(handler)
        logger.propagate = True
    return logger
