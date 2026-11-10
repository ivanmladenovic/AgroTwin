#!/usr/bin/env python3
"""Fill English locale for scoped tr() keys where en[key] == key (rate-limited)."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from find_unwrapped_i18n import collect_paths  # noqa: E402

EN_PATH = ROOT / "src/shared/i18n/locales/en/translation.json"
TR_RE = re.compile(r"tr\s*\(\s*([\"'`])((?:\\.|(?!\1).)*)\1")


def scoped_keys() -> set[str]:
    keys: set[str] = set()
    for fp in collect_paths():
        for m in TR_RE.finditer(fp.read_text(encoding="utf-8")):
            key = m.group(2).replace("\\'", "'").replace('\\"', '"')
            if key and "${" not in key:
                keys.add(key)
    return keys


def main() -> None:
    from deep_translator import GoogleTranslator

    keys = scoped_keys()
    en: dict[str, str] = json.loads(EN_PATH.read_text(encoding="utf-8"))
    missing = sorted(k for k in keys if en.get(k, k) == k and k.strip())
    print(f"Scoped keys: {len(keys)}; to translate: {len(missing)}")
    translator = GoogleTranslator(source="sr", target="en")
    updated = 0
    for i, key in enumerate(missing):
        for attempt in range(4):
            try:
                en[key] = translator.translate(key)
                updated += 1
                break
            except Exception as exc:
                wait = 2 ** attempt
                print(f"retry {attempt + 1} for {key[:50]!r}: {exc}")
                time.sleep(wait)
        time.sleep(1.2)
        if (i + 1) % 25 == 0:
            EN_PATH.write_text(json.dumps(en, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"checkpoint {i + 1}/{len(missing)}")
    EN_PATH.write_text(json.dumps(en, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    remaining = sum(1 for k in keys if en.get(k, k) == k)
    print(f"Updated {updated}; remaining identity in scope: {remaining}")


if __name__ == "__main__":
    main()
