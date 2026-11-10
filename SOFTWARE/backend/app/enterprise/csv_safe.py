"""CSV cells that spreadsheets will not execute as formulas."""

from __future__ import annotations


def csv_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    if text[:1] in {"=", "+", "-", "@"}:
        text = "'" + text
    escaped = text.replace('"', '""')
    if any(char in escaped for char in [",", '"', "\n", "\r"]):
        return f'"{escaped}"'
    return escaped
