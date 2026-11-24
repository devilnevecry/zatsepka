"""CSV/XLSX export helpers with Russian column headers."""

from __future__ import annotations

import csv
import io
from typing import Any

from openpyxl import Workbook

COLUMNS: list[tuple[str, str]] = [
    ("name", "Название"),
    ("category", "Категория"),
    ("city", "Город"),
    ("address", "Адрес"),
    ("phones", "Телефоны"),
    ("emails", "Email"),
    ("website", "Сайт"),
    ("socials", "Соцсети"),
    ("rating", "Рейтинг"),
    ("reviews_count", "Отзывов"),
    ("status", "Статус"),
    ("notes", "Заметки"),
]


def _cell(lead: dict[str, Any], key: str) -> str:
    value = lead.get(key, "")
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items() if v)
    return "" if value is None else str(value)


def leads_csv(leads: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([title for _, title in COLUMNS])
    for lead in leads:
        writer.writerow([_cell(lead, key) for key, _ in COLUMNS])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def leads_xlsx(leads: list[dict[str, Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append([title for _, title in COLUMNS])
    for lead in leads:
        ws.append([_cell(lead, key) for key, _ in COLUMNS])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
