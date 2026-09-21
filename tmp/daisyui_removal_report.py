#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_priority_daisyui import violations  # noqa: E402

TEMPLATES = ROOT / "aicentralv2" / "templates"
JS = ROOT / "aicentralv2" / "static" / "js"
FORM_RE = re.compile(r"<form\b", re.I)
EXTENDS_RE = re.compile(r"extends\s+['\"]([^'\"]+)['\"]")


def analyze(path: Path) -> dict | None:
    v = violations(path)
    if not v:
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    ext = EXTENDS_RE.search(text)
    forms = len(FORM_RE.findall(text))
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "violations": len(v),
        "tokens": Counter(t for _, t in v),
        "extends": ext.group(1) if ext else None,
        "forms": forms,
    }


def bucket(path: str) -> str:
    p = path.replace("aicentralv2/templates/", "")
    if p.startswith("parametros") or "parametros_testes" in p or "treinamento" in p:
        return "Parâmetros (carrega output-legacy.css hoje)"
    if p.startswith("base_tailwind") or p.startswith("base_auth.html"):
        return "Base legada (sempre output-legacy.css)"
    if p.startswith("crm/") and not p.startswith("crm_v3"):
        return "CRM v1/v2 (modais legados)"
    if p in {"contato_form.html", "plano_form.html", "cadu_planos.html", "design_system.html"}:
        return "ERP legado base_tailwind"
    if p.startswith("cadu_cotacoes_form_legado") or p.startswith("cadu_cotacoes_legado"):
        return "Cotações legado"
    if p.startswith("whatsapp"):
        return "WhatsApp"
    if p.startswith("components/") or p.startswith("design_system"):
        return "Design system / componentes"
    return "Outros ERP"


rows = []
for path in sorted(TEMPLATES.rglob("*.html")):
    r = analyze(path)
    if r:
        rows.append(r)

js_rows = []
for path in sorted(JS.rglob("*.js")):
    r = analyze(path)
    if r:
        js_rows.append(r)

print("=== REMOÇÃO DAISYUI — IMPACTO ===")
print(f"Templates HTML com DaisyUI: {len(rows)}")
print(f"JS com DaisyUI: {len(js_rows)}")
print(f"Forms afetados: {sum(1 for r in rows if r['forms'])} arquivos, {sum(r['forms'] for r in rows)} tags <form>")
print()

by_bucket: dict[str, list] = defaultdict(list)
for r in rows:
    by_bucket[bucket(r["path"])].append(r)

print("=== POR ÁREA DE IMPACTO ===")
for b in sorted(by_bucket, key=lambda x: (-len(by_bucket[x]), x)):
    subset = by_bucket[b]
    forms = sum(r["forms"] for r in subset)
    print(f"\n{b}: {len(subset)} templates, {forms} forms")
    for r in sorted(subset, key=lambda x: -x["violations"]):
        form_note = f", {r['forms']} form(s)" if r["forms"] else ""
        ext = f" extends {r['extends']}" if r["extends"] else ""
        print(f"  - {r['path'].replace('aicentralv2/templates/', '')} ({r['violations']} classes{form_note}{ext})")

print("\n=== JS A REESCREVER ===")
for r in js_rows:
    print(f"  - {r['path']} ({r['violations']} refs) top: {', '.join(t for t,_ in r['tokens'].most_common(5))}")

# Extends base_tailwind
legacy_base = [r for r in rows if r["extends"] in ("base_tailwind.html", "base_auth.html") or "base_tailwind" in r["path"]]
print(f"\n=== EXTENDS BASE LEGADA: {len(legacy_base)} templates ===")
for r in legacy_base:
    print(f"  - {r['path'].replace('aicentralv2/templates/', '')}")
