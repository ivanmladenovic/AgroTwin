#!/usr/bin/env python3
"""Find user-facing string literals not wrapped in tr() in scoped frontend files."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = [
    "src/features/journal",
    "src/features/health",
    "src/features/agronomist",
    "src/features/knowledge",
    "src/features/reports",
    "src/features/compliance",
    "src/features/planning",
    "src/features/enterprise/pages",
    "src/features/admin",
    "src/features/workforce",
    "src/features/passport",
    "src/features/map-editor",
    "src/features/invoices",
    "src/features/orchard/monitoring",
]
FILES = [
    "src/features/orchard/health.ts",
    "src/features/orchard/varieties.ts",
    "src/features/orchard/weatherIcons.ts",
    "src/features/orchard/monitoring/satelliteLabels.ts",
    "src/features/orchard/monitoring/anomalyBriefing.ts",
]

SKIP_NAMES = {"api.ts", "schemas.ts", "types.ts", "cases.ts", "scheduleApi.ts", "activityLineItems.ts"}
STR_RE = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\"|`([^`]*)`")
SERB = re.compile(r"[ščćžđŠČĆŽĐ]")


def collect_paths():
    out = set()
    for d in DIRS:
        p = ROOT / d
        if p.exists():
            for f in p.rglob("*"):
                if f.suffix in (".tsx", ".ts") and f.name not in SKIP_NAMES:
                    out.add(f)
    for f in FILES:
        fp = ROOT / f
        if fp.exists():
            out.add(fp)
    return sorted(out)


def in_tr(line: str, pos: int) -> bool:
    before = line[:pos]
    idx = before.rfind("tr(")
    if idx < 0:
        return False
    tail = before[idx:]
    return bool(re.search(r"tr\s*\(\s*$", tail) or re.search(r"tr\s*\(\s*['\"`]", tail))


def looks_ui(s: str) -> bool:
    if not s or len(s) > 600:
        return False
    if s.startswith("/") or s.startswith("http") or s.startswith("@/"):
        return False
    if re.fullmatch(r"[a-z0-9_.-]+", s):
        return False
    if SERB.search(s):
        return True
    low = s.lower()
    hints = (
        "nije",
        "nema",
        "obri",
        "sačuv",
        "čuv",
        "dodaj",
        "učit",
        "prika",
        "molim",
        "parcel",
        "zasad",
        "stablo",
        "sadnic",
        "berb",
        "trošk",
        "prinos",
        "fotograf",
        "poruk",
        "razgov",
        "pasoš",
        "digitalni",
        "generi",
        "satelit",
        "granica",
        "prevuc",
        "označ",
        "klikn",
        "izaber",
        "potvrd",
        "otka",
        "zatvor",
        "pretra",
        "uspe",
        "uspel",
        "grešk",
        "izvešt",
        "planir",
        "dobavlja",
        "proizvo",
        "očekiv",
        "kritič",
        "rešen",
        "završ",
        "stručn",
        "realist",
        "optimist",
        "finaliz",
        "opozv",
        "slanj",
        "agronom",
        "simptom",
        "opažanj",
        "zdravlje",
        "bolest",
        "štetoč",
        "navodn",
        "đubr",
        "zaštit",
        "subvenc",
        "račun",
        "faktur",
        "radna",
        "snaga",
        "član",
        "deaktiv",
        "aktivnost",
        "raspored",
        "kalendar",
        "dnevnik",
        "mesec",
        "nedelj",
        "godin",
    )
    if " " in s and any(h in low for h in hints):
        return True
    if any(h in low for h in hints) and len(s) >= 4:
        return True
    return False


def main():
    unique: dict[str, list[tuple[str, int]]] = {}
    for fp in collect_paths():
        rel = fp.relative_to(ROOT)
        for num, line in enumerate(fp.read_text(encoding="utf-8").splitlines(), 1):
            st = line.strip()
            if st.startswith("//") or st.startswith("*") or st.startswith("import "):
                continue
            for m in STR_RE.finditer(line):
                s = m.group(1) or m.group(2) or m.group(3) or ""
                if not looks_ui(s):
                    continue
                if in_tr(line, m.start()):
                    continue
                unique.setdefault(s, []).append((str(rel), num))

    print(json.dumps({"count": len(unique), "strings": sorted(unique.keys())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
