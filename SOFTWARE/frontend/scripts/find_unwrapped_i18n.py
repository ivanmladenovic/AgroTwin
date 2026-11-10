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
    "src/features/enterprise",
    "src/features/admin",
    "src/features/workforce",
    "src/features/passport",
    "src/features/map-editor",
    "src/features/invoices",
    "src/features/benchmark",
    "src/features/context",
    "src/features/orchard/monitoring",
    "src/app",
]
SHARED_UI_DIR = ROOT / "src/shared"
SHARED_SKIP_PARTS = ("i18n",)
FILES = [
    "src/features/orchard/health.ts",
    "src/features/orchard/varieties.ts",
    "src/features/orchard/weatherIcons.ts",
    "src/features/orchard/monitoring/satelliteLabels.ts",
    "src/features/orchard/monitoring/anomalyBriefing.ts",
    "src/features/orchard/ParcelSoilAnalysesPage.tsx",
    "src/features/orchard/IntelligencePage.tsx",
    "src/features/orchard/TreeDetailPanel.tsx",
    "src/features/orchard/ParcelBoundarySetupCard.tsx",
    "src/features/orchard/OrchardIndicesMap.tsx",
    "src/features/orchard/OrchardSatelliteMap.tsx",
    "src/features/orchard/ParcelSatelliteCard.tsx",
    "src/features/orchard/SatelliteMonitoringPage.tsx",
    "src/features/orchard/SoilLabReviewPanel.tsx",
    "src/features/orchard/ParcelLaborCard.tsx",
    "src/features/orchard/TreeJournalPage.tsx",
    "src/features/orchard/OrchardCanvas.tsx",
    "src/features/orchard/ParcelIntelligenceCard.tsx",
    "src/features/orchard/ParcelSoilAnalysesPage.tsx",
    "src/features/orchard/schemas.ts",
    "src/features/auth/LoginPage.tsx",
    "src/features/auth/schemas.ts",
    "src/features/health/schemas.ts",
    "src/features/journal/schemas.ts",
    "src/features/production/ProductionPage.tsx",
    "src/features/production/HarvestForm.tsx",
    "src/features/dashboard/ParcelsMap.tsx",
    "src/app/AppLayout.tsx",
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
    if SHARED_UI_DIR.exists():
        for f in SHARED_UI_DIR.rglob("*"):
            if f.suffix not in (".tsx", ".ts") or f.name in SKIP_NAMES:
                continue
            if any(part in SHARED_SKIP_PARTS for part in f.parts):
                continue
            out.add(f)
    for f in FILES:
        fp = ROOT / f
        if fp.exists():
            out.add(fp)
    return sorted(out)


def in_tr(line: str, pos: int, lines: list[str] | None = None, line_num: int | None = None) -> bool:
    before = line[:pos]
    idx = before.rfind("tr(")
    if idx >= 0:
        tail = before[idx:]
        if re.search(r"tr\s*\(\s*$", tail) or re.search(r"tr\s*\(\s*['\"`]", tail):
            return True
    if lines is not None and line_num is not None:
        for back in range(1, 5):
            prev_i = line_num - back - 1
            if prev_i < 0:
                break
            prev = lines[prev_i].strip()
            if not prev:
                continue
            if prev.endswith("tr(") or re.search(r"tr\s*\(\s*$", prev):
                return True
            if "tr(" in prev and not prev.endswith(")"):
                return True
    return False


def looks_ui(s: str) -> bool:
    if not s or len(s) > 600:
        return False
    if "${" in s or "{{" in s and s.count("{{") != s.count("}}"):
        return False
    if s.startswith("/") or s.startswith("http") or s.startswith("@/"):
        return False
    if re.fullmatch(r"[a-z0-9_.-]+", s):
        return False
    if re.match(r"^[\w/-]+:\w", s):
        return False
    if re.search(r"\b(bg-|overflow-|relative\b|flex-|grid-|rounded-)", s):
        return False
    if re.fullmatch(r"[a-z][a-zA-Z0-9]*", s) and " " not in s:
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
    if " " in s and re.match(r"^[A-Za-zČĆŽŠĐčćžšđ0-9\s().,:;!?\"'+\-/—·]+$", s):
        if any(
            w in low
            for w in (
                "opciono",
                "izaber",
                "naslov",
                "kategor",
                "ozbilj",
                "obuhvat",
                "map",
                "ozna",
                "otka",
                "prijav",
                "dokument",
                "učitav",
                "filter",
                "segment",
                "danas",
                "kasni",
                "po ",
                "još ",
                "nema ",
                "više ",
                "ceo ",
                "cela ",
                "jedn",
                "svi ",
                "red ",
                "sort",
                "goriv",
                "invest",
                "oprem",
                "kvalitet",
                "napomen",
                "naziv",
                "kratak",
                "opis",
                "izmen",
                "neaktiv",
                "aktivir",
                "deaktiv",
                "lozink",
                "uloga",
                "firma",
                "lokacij",
                "kreiran",
                "iscrt",
                "nedostaj",
                "kurzor",
                "bez ",
                "seg ",
                "klik ",
                "prevuc",
                "teme ",
                "referent",
                "ponovo",
                "iscrtano",
                "pomerena",
                "uklonjena",
                "dodata ",
                "dodavanje",
                "aktivan red",
                "planir",
                "urađen",
                "evidentir",
                "bunarište",
                "ručno",
                "prebačen",
                "stavki",
                "površin",
                "ukupan",
                "upoređen",
                "troška",
                "zatraženo",
                "digitalni",
                "pasoš",
                "simptom",
                "priložen",
            )
        ):
            return True
    return False


def main():
    unique: dict[str, list[tuple[str, int]]] = {}
    for fp in collect_paths():
        rel = fp.relative_to(ROOT)
        file_lines = fp.read_text(encoding="utf-8").splitlines()
        for num, line in enumerate(file_lines, 1):
            st = line.strip()
            if st.startswith("//") or st.startswith("*") or st.startswith("import "):
                continue
            for m in STR_RE.finditer(line):
                s = m.group(1) or m.group(2) or m.group(3) or ""
                if not looks_ui(s):
                    continue
                if in_tr(line, m.start(), file_lines, num):
                    continue
                unique.setdefault(s, []).append((str(rel), num))

    print(json.dumps({"count": len(unique), "strings": sorted(unique.keys())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
