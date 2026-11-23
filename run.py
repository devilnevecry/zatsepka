"""Start uvicorn on 127.0.0.1:8000 and open the browser tab once /health answers."""

from __future__ import annotations

import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from app.logging_setup import setup_logging

HOST = "127.0.0.1"
PORT = 8000


def _open_tab_when_ready(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as resp:
                if resp.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:  # noqa: BLE001 - server not up yet
            time.sleep(0.4)


def _port_busy_with_our_app(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/health", timeout=2) as resp:
            return resp.status == 200 and b'"ok"' in resp.read(200)
    except Exception:  # noqa: BLE001
        return False


def _port_free() -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, PORT))
            return True
        except OSError:
            return False


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    setup_logging()
    url = f"http://{HOST}:{PORT}"
    if _port_busy_with_our_app(url):
        print(f"[run] Приложение уже запущено на {url}, открываю вкладку")
        webbrowser.open(url)
        return
    if not _port_free():
        print(f"[run] Порт {PORT} занят другим приложением. Освободите порт и запустите снова.")
        raise SystemExit(1)
    threading.Thread(target=_open_tab_when_ready, args=(url,), daemon=True).start()
    print(f"[run] РАЗВЕДКА запускается на {url}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False, log_level="info")


if __name__ == "__main__":
    main()
