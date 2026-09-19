from __future__ import annotations

from typing import Literal, TypedDict

VarietyRole = Literal["main", "pollinator", "other"]


class VarietyDict(TypedDict):
    name: str
    role: VarietyRole
    color: str


DEFAULT_VARIETIES: list[VarietyDict] = [
    {"name": "Tonda di Giffoni", "role": "main", "color": "#DC2626"},
    {"name": "Tonda Gentile Romana", "role": "pollinator", "color": "#16A34A"},
    {"name": "Nocchione", "role": "pollinator", "color": "#2563EB"},
]


def main_variety_name(varieties: list[VarietyDict] | list[dict]) -> str:
    for item in varieties:
        if item.get("role") == "main":
            return str(item["name"])
    return str(varieties[0]["name"]) if varieties else DEFAULT_VARIETIES[0]["name"]
