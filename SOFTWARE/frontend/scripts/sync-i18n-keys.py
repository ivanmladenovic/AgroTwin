#!/usr/bin/env python3
"""Collect tr() keys from scoped frontend files and merge into locale JSON."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_PATH = ROOT / "src/shared/i18n/locales/en/translation.json"
SR_PATH = ROOT / "src/shared/i18n/locales/sr/translation.json"

# Import scope from find_unwrapped_i18n
import sys

sys.path.insert(0, str(ROOT / "scripts"))
from find_unwrapped_i18n import collect_paths  # noqa: E402

TR_RE = re.compile(
    r"tr\s*\(\s*([\"'`])((?:\\.|(?!\1).)*)\1",
    re.DOTALL,
)


def collect_tr_keys() -> set[str]:
    keys: set[str] = set()
    for fp in collect_paths():
        text = fp.read_text(encoding="utf-8")
        for m in TR_RE.finditer(text):
            key = m.group(2)
            key = key.replace("\\'", "'").replace('\\"', '"')
            if key and "{{" not in key and "${" not in key:
                keys.add(key)
            elif key:
                keys.add(key)
    return keys


def main() -> None:
    keys = collect_tr_keys()
    en: dict[str, str] = json.loads(EN_PATH.read_text(encoding="utf-8"))
    sr: dict[str, str] = json.loads(SR_PATH.read_text(encoding="utf-8"))

    added_en = 0
    added_sr = 0
    for key in sorted(keys):
        if key not in sr:
            sr[key] = key
            added_sr += 1
        if key not in en:
            # Fallback: keep Serbian until manually translated; build will still work via defaultValue
            en[key] = en.get(key, key)
            added_en += 1

    EN_PATH.write_text(json.dumps(en, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SR_PATH.write_text(json.dumps(sr, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"tr keys in scope: {len(keys)}; added sr: {added_sr}; added en: {added_en}")


if __name__ == "__main__":
    main()
