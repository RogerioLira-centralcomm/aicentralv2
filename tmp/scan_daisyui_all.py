#!/usr/bin/env python3
"""Scan all templates + JS for DaisyUI component classes."""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_priority_daisyui import FORBIDDEN, violations  # noqa: E402

SCAN_DIRS = [
    ROOT / "aicentralv2" / "templates",
    ROOT / "aicentralv2" / "static" / "js",
]

FORM_RE = re.compile(r"<form\b", re.I)


def has_form(path: Path) -> bool:
    return bool(FORM_RE.search(path.read_text(encoding="utf-8", errors="ignore")))


def count_forms(path: Path) -> int:
    return len(FORM_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))


def main() -> int:
    files: list[Path] = []
    for base in SCAN_DIRS:
        files.extend(sorted(base.rglob("*.html")))
        files.extend(sorted(base.rglob("*.js")))
    files = sorted(set(files))

    by_file: dict[str, list[tuple[int, str]]] = {}
    token_counter: Counter[str] = Counter()
    for path in files:
        v = violations(path)
        if v:
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            by_file[rel] = v
            for _, token in v:
                token_counter[token] += 1

    form_files = {rel for rel in by_file if rel.endswith(".html") and has_form(ROOT / rel)}
    form_tags = sum(count_forms(ROOT / rel) for rel in form_files)

    print("=== SCAN COMPLETO DAISYUI ===")
    print(f"Arquivos com classes DaisyUI: {len(by_file)}")
    print(f"  HTML templates: {sum(1 for k in by_file if k.endswith('.html'))}")
    print(f"  JS files: {sum(1 for k in by_file if k.endswith('.js'))}")
    print(f"Templates com <form> afetados: {len(form_files)} arquivos, {form_tags} tags <form>")
    print()
    print("Top 15 classes DaisyUI:")
    for token, n in token_counter.most_common(15):
        print(f"  {token}: {n}")

    # Group HTML by area
    areas: dict[str, list[str]] = defaultdict(list)
    for rel in sorted(by_file):
        if not rel.endswith(".html"):
            continue
        p = rel.replace("aicentralv2/templates/", "")
        if p.startswith("crm"):
            area = "CRM"
        elif p.startswith("cadu_cotacoes") or p.startswith("cotacoes/"):
            area = "Cotações"
        elif p.startswith("cadu_pi") or p.startswith("campanhas_pi") or p.startswith("pi_operacao"):
            area = "PI / Campanhas"
        elif p.startswith("parametros"):
            area = "Parâmetros / Studio / MC"
        elif p.startswith("financeiro") or "notas_fiscais" in p:
            area = "Financeiro"
        elif p.startswith("smart_planner"):
            area = "Smart Planner"
        elif p.startswith("cadu_workspace") or p.startswith("cadu_family"):
            area = "Cadu Family"
        elif "auth" in p or "login" in p or "password" in p or "convite" in p or "subscription" in p:
            area = "Auth / Público"
        elif p.startswith("base_"):
            area = "Base layouts"
        else:
            area = "ERP legado / outros"
        areas[area].append(p)

    print()
    print("=== TELAS POR ÁREA (com DaisyUI) ===")
    for area in sorted(areas, key=lambda a: (-len(areas[a]), a)):
        print(f"{area}: {len(areas[area])} templates")
        for p in areas[area][:8]:
            flags = " [form]" if has_form(ROOT / "aicentralv2/templates" / p.split("aicentralv2/templates/")[-1] if p.startswith("aicentralv2") else ROOT / "aicentralv2/templates" / p) else ""
            # fix path
            full = ROOT / "aicentralv2/templates" / p if not p.startswith("aicentralv2") else ROOT / p
            flags = " [form]" if has_form(full) else ""
            print(f"  - {p}{flags}")
        if len(areas[area]) > 8:
            print(f"  ... +{len(areas[area]) - 8} mais")

    print()
    print("=== JS COM DAISYUI ===")
    for rel in sorted(k for k in by_file if k.endswith(".js")):
        print(f"  {rel} ({len(by_file[rel])} ocorrências)")

    return 1 if by_file else 0


if __name__ == "__main__":
    raise SystemExit(main())
