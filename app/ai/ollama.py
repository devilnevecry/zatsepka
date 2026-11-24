"""Ollama status indicator only (no LLM calls from the app)."""

from __future__ import annotations

from typing import Any

import httpx


def ollama_status(url: str, timeout: float = 2.0) -> dict[str, Any]:
    try:
        resp = httpx.get(url.rstrip("/") + "/api/ps", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models") or []
        first = models[0] if models else {}
        return {
            "available": True,
            "model": first.get("name") or first.get("model") or "",
            "vram": first.get("size_vram") or 0,
        }
    except Exception:  # noqa: BLE001 - never an error page
        return {"available": False, "model": "", "vram": 0}
