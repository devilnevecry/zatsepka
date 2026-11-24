"""System load metrics via psutil; Ollama status indicator (SPEC 9)."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

import psutil

from app import config
from app.ai.ollama import ollama_status
from app.db import session_scope


def system_metrics() -> dict[str, Any]:
    disk = psutil.disk_usage(".")
    result: dict[str, Any] = {
        "cpu": psutil.cpu_percent(interval=0.2),
        "ram": psutil.virtual_memory().percent,
        "disk": disk.percent,
        "gpu": None,
        "vram": None,
    }
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if out.returncode == 0 and out.stdout.strip():
                parts = out.stdout.strip().split("\n")[0].split(",")
                result["gpu"] = float(parts[0].strip())
                result["vram"] = int(float(parts[1].strip()))
        except Exception:  # noqa: BLE001
            pass
    return result


def ollama_card() -> dict[str, Any]:
    with session_scope() as s:
        url = config.get_settings(s).get("ollama_url", "http://127.0.0.1:11434")
    return ollama_status(url)
