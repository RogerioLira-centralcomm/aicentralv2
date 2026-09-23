#!/usr/bin/env python3
"""Scan all templates for DaisyUI class usage."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "aicentralv2" / "templates"

FORBIDDEN = re.compile(
    r"^(?:"
    r"modal(?:-(?:box|action|backdrop|compact|bottom|middle|open))?|"
    r"btn(?:-(?:primary|secondary|accent|ghost|outline|error|success|warning|info|neutral|sm|xs|lg|circle|square|wide|block|link|disabled))?|"
    r"badge(?:-(?:primary|secondary|accent|ghost|outline|error|success|warning|info|neutral|sm|xs|lg))?|"
    r"card(?:-(?:body|title|actions|compact|side))?|form-control|"
    r"label(?:-(?:text|text-alt))?|input(?:-(?:bordered|sm|xs|lg|error|ghost))?|"
    r"select(?:-(?:bordered|sm|xs|lg|error|ghost))?|textarea(?:-(?:bordered|sm|xs|lg|error|ghost))?|"
    r"alert(?:-(?:error|success|warning|info))?|loading(?:-(?:spinner|dots|ring|ball|bars|infinity|xs|sm|md|lg))?|"
    r"toggle(?:-(?:primary|success|warning|error|sm|xs|lg))?|checkbox(?:-(?:primary|success|warning|error|sm|xs|lg))?|"
    r"radio(?:-(?:primary|success|warning|error|sm|xs|lg))?|range(?:-(?:primary|success|warning|error|xs|sm|md|lg))?|"
    r"steps?|step(?:-(?:primary|success|warning|error|info))?|table(?:-(?:xs|sm|md|lg|zebra|pin-rows|pin-cols))?|"
    r"progress(?:-(?:primary|success|warning|error|info))?|join(?:-(?:item|vertical|horizontal))?|"
    r"dropdown(?:-(?:content|end|top|bottom|left|right|hover|open))?|toast(?:-(?:top|bottom|start|center|end|middle))?"
    r"|avatar|placeholder|menu(?:-(?:title|horizontal|vertical|compact))?"
    r")$"
)
EXTRA = re.compile(r"(?:\bdivider\b|text-base-content|border-base-|bg-base-|modal-box|\btab-active\b)")
CLASS_ATTR = re.compile(r"""class\s*=\s*(['"])(.*?)\1""", re.DOTALL)


def classify(name: str, rel: str) -> str:
    n = name.lower()
    r = rel.lower()
    if "modal" in n or "_drawer" in n or "dialog" in n or "/crm/" in r and "modal" in r:
        return "modal"
    if "form" in n or n.endswith("_form.html") or "checkout" in n or n.endswith("novo.html") or "edit" in n:
        return "form"
    if any(k in n for k in ("list", "lista", "pipeline", "logs", "gestao")) or n.endswith("index.html"):
        return "lista"
    return "outro"


def main() -> None:
    results: dict[str, list[tuple[str, list[str]]]] = {
        "form": [],
        "lista": [],
        "modal": [],
        "outro": [],
    }

    for path in sorted(ROOT.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        tokens: set[str] = set()
        for match in CLASS_ATTR.finditer(text):
            for tok in re.split(r"\s+", match.group(2).strip()):
                if not tok or tok.startswith(("cx-", "crm-v3-", "pi-op-", "cot-op-")):
                    continue
                if FORBIDDEN.fullmatch(tok):
                    tokens.add(tok)
        if EXTRA.search(text):
            tokens.add("base-content/divider/modal-box/tab-active")
        if not tokens:
            continue
        rel = str(path.relative_to(ROOT.parent)).replace("\\", "/")
        cat = classify(path.name, rel)
        results[cat].append((rel, sorted(tokens)))

    for cat in ("form", "lista", "modal", "outro"):
        items = results[cat]
        print(f"=== {cat.upper()} ({len(items)}) ===")
        for rel, toks in items:
            preview = ", ".join(toks[:8])
            if len(toks) > 8:
                preview += ", ..."
            print(f"  {rel}")
            print(f"    -> {preview}")
        print()

    print("TOTAL COM DAISYUI:", sum(len(v) for v in results.values()))


if __name__ == "__main__":
    main()
