#!/usr/bin/env python3
"""Substitui tokens Daisy em Jinja/JS que o checker por class= não pegava."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = (
    "format_prototypes/",
    "design_system.html",
    "components/tailwind_components.html",
    "base_tailwind.html",
)

REPLACEMENTS = [
    (re.compile(r"(?<!cx-)alert-error\b"), "cx-alert-danger"),
    (re.compile(r"(?<!cx-)alert-success\b"), "cx-alert-success"),
    (re.compile(r"(?<!cx-)alert-warning\b"), "cx-alert-warning"),
    (re.compile(r"(?<!cx-)alert-info\b"), "cx-alert-info"),
    (re.compile(r"(?<!cx-)badge-error\b"), "cx-badge-danger"),
    (re.compile(r"(?<!cx-)badge-success\b"), "cx-badge-success"),
    (re.compile(r"(?<!cx-)badge-warning\b"), "cx-badge-warning"),
    (re.compile(r"(?<!cx-)badge-ghost\b"), "cx-badge-muted"),
    (re.compile(r"\bfile-input-bordered\b"), ""),
    (re.compile(r"\bfile-input-sm\b"), ""),
    (re.compile(r"\bfile-input\b"), "cx-input"),
    (re.compile(r'class="table table-sm"'), 'class="w-full text-sm border-collapse"'),
]

for base, pattern in [
    (ROOT / "aicentralv2/templates", "**/*.html"),
    (ROOT / "aicentralv2/static/js", "**/*.js"),
    (ROOT / "aicentralv2/static/cadu_workspace", "**/*.js"),
]:
    if not base.exists():
        continue
    for path in sorted(base.glob(pattern)):
        rel = path.relative_to(ROOT).as_posix()
        if any(s in rel for s in SKIP):
            continue
        text = path.read_text(encoding="utf-8")
        orig = text
        for pat, repl in REPLACEMENTS:
            text = pat.sub(repl, text)
        if text != orig:
            path.write_text(text, encoding="utf-8")
            print("updated", rel)
