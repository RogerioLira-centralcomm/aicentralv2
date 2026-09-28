#!/usr/bin/env python3
"""Substitui tokens semânticos DaisyUI nos arquivos do gate prioritário."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chk", ROOT / "scripts/check_priority_daisyui.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)  # type: ignore

REPLACEMENTS = [
    (re.compile(r"\btext-base-content/(\d+)\b"), r"text-slate-600/\1"),
    (re.compile(r"\btext-base-content\b"), "text-slate-800"),
    (re.compile(r"\bbg-base-100\b"), "bg-white"),
    (re.compile(r"\bbg-base-200\b"), "bg-gray-100"),
    (re.compile(r"\bborder-base-200\b"), "border-gray-200"),
    (re.compile(r"\bborder-base-300\b"), "border-gray-300"),
    (re.compile(r"\brounded-box\b"), "rounded-lg"),
    (re.compile(r'\bclass="divider\b'), 'class="hidden'),  # noop fallback
    (re.compile(r'\bclass="([^"]*\b)divider(\b[^"]*)"'), r'class="\1border-t border-gray-200 my-2\2"'),
    (re.compile(r"<div class=\"divider"), "<hr class=\"border-gray-200 my-2"),
]

for path in sorted(set(chk.FILES)):
    if not path.exists() or path.suffix != ".html":
        continue
    text = path.read_text(encoding="utf-8")
    orig = text
    for pattern, repl in REPLACEMENTS:
        text = pattern.sub(repl, text)
    if text != orig:
        path.write_text(text, encoding="utf-8")
        print("updated", path.relative_to(ROOT))
