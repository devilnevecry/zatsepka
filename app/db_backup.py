"""Database backup on startup: keep last 5 copies in data/backups/."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.paths import DATA_DIR, DB_PATH, ensure_dirs

BACKUP_DIR = DATA_DIR / "backups"
KEEP = 5


def backup_db(source: Path | None = None) -> Path | None:
    ensure_dirs()
    src = source or DB_PATH
    if not src.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"zatsepka_{stamp}.db"
    if src.resolve() == target.resolve():
        return None
    shutil.copy2(src, target)
    for old in sorted(BACKUP_DIR.glob("zatsepka_*.db"), reverse=True)[KEEP:]:
        try:
            old.unlink()
        except OSError:
            pass
    return target
