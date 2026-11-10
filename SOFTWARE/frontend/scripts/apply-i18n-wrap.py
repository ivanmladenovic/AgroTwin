#!/usr/bin/env python3
"""Wrap unwrapped UI string literals with tr() in scoped files."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from find_unwrapped_i18n import (  # type: ignore
    STR_RE,
    collect_paths,
    in_tr,
    looks_ui,
)

IMPORT_LINE = "import { tr } from '@/shared/i18n/i18n'\n"


def ensure_import(text: str) -> str:
    if "from '@/shared/i18n/i18n'" in text or 'from "@/shared/i18n/i18n"' in text:
        return text
    lines = text.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("import "):
            insert_at = i + 1
        elif insert_at and not line.startswith("import ") and line.strip():
            break
    lines.insert(insert_at, IMPORT_LINE)
    return "".join(lines)


def wrap_jsx_attr(line: str) -> str:
    """label="Text" -> label={tr('Text')} when Text is UI."""
    def repl(m: re.Match[str]) -> str:
        name, quote, val, end_quote = m.group(1), m.group(2), m.group(3), m.group(2)
        if name == "placeholder" and val.lstrip().startswith("{"):
            return m.group(0)
        if not looks_ui(val):
            return m.group(0)
        esc = val.replace("\\", "\\\\").replace("'", "\\'")
        return f"{name}={{tr('{esc}')}}"

    return re.sub(
        r"\b([A-Za-z_][\w-]*)=(['\"])([^'\"\\]*(?:\\.[^'\"\\]*)*)\2",
        repl,
        line,
    )


def wrap_jsx_text(line: str) -> str:
    """>Plain text< or >Plain text</tag> -> {tr('...')} when UI Serbian/latin text."""

    def repl(m: re.Match[str]) -> str:
        prefix, text, suffix, close = m.group(1), m.group(2), m.group(3), m.group(4)
        t = text.strip()
        if not t or "{" in text or "`" in text:
            return m.group(0)
        if not looks_ui(t):
            return m.group(0)
        esc = t.replace("\\", "\\\\").replace("'", "\\'")
        return f">{prefix}{{tr('{esc}')}}{suffix}{close}"

    # Text before closing tag on same line
    line = re.sub(
        r">(\s*)([^<{]+?)(\s*)(</[A-Za-z])",
        repl,
        line,
    )

    def repl2(m: re.Match[str]) -> str:
        prefix, text, suffix = m.group(1), m.group(2), m.group(3)
        t = text.strip()
        if not t or "{" in text:
            return m.group(0)
        if not looks_ui(t):
            return m.group(0)
        esc = t.replace("\\", "\\\\").replace("'", "\\'")
        return f">{prefix}{{tr('{esc}')}}{suffix}<"

    line = re.sub(
        r">(\s*)([^<{/][^<{}]*?)(\s*)<(?!/)",
        repl2,
        line,
    )
    return line


def wrap_jsx_text_only_line(line: str) -> str:
    """Line that is only indented JSX text (multiline JSX children)."""
    nl = "\n" if line.endswith("\n") else ""
    core = line[:-1] if nl else line
    m = re.match(r"^(\s+)([^\s<{][^\n<{]*[ščćžđŠČĆŽŠĐ][^\n<{]*)\s*$", core)
    if not m:
        return line
    indent, text = m.group(1), m.group(2).strip()
    if not looks_ui(text):
        return line
    if "tr(" in core:
        return line
    esc = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"{indent}{{tr('{esc}')}}{nl}"


def wrap_literals(line: str) -> str:
    if line.strip().startswith("import ") or line.strip().startswith("//"):
        return line
    line = wrap_jsx_text_only_line(line)
    line = wrap_jsx_attr(line)
    line = wrap_jsx_text(line)
    parts: list[str] = []
    last = 0
    for m in STR_RE.finditer(line):
        s = m.group(1) or m.group(2) or m.group(3) or ""
        if "`" in m.group(0) and "${" in s:
            continue
        if not looks_ui(s):
            continue
        if in_tr(line, m.start()):
            continue
        parts.append(line[last : m.start()])
        parts.append(f"tr({m.group(0)})")
        last = m.end()
    parts.append(line[last:])
    return "".join(parts)


def process_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    changed = False
    new_lines = []
    for line in lines:
        nl = wrap_literals(line)
        if nl != line:
            changed = True
        new_lines.append(nl)
    if not changed:
        return False
    text = "".join(new_lines)
    text = ensure_import(text)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    n = 0
    for fp in collect_paths():
        if process_file(fp):
            n += 1
            print(fp.relative_to(ROOT))
    print(f"Updated {n} files")


if __name__ == "__main__":
    main()
