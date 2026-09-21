#!/usr/bin/env python3
"""Classify templates with <form> by CSS stack (cx-*, DaisyUI, vanilla)."""
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "aicentralv2" / "templates"

FORM_FILES = sorted(
    p for p in TEMPLATES.rglob("*.html")
    if "<form" in p.read_text(encoding="utf-8", errors="ignore")
)

CX_FORM = re.compile(
    r"\bcx-(?:field|input|label|select|textarea|btn|form|checkbox|radio|switch|help|control)\b"
)
DAISY_FORM = re.compile(
    r"\b(?:form-control|label-text|input-bordered|select-bordered|textarea-bordered|"
    r"btn-primary|btn-secondary|btn btn-)\b"
)
TW_UTIL = re.compile(
    r"\b(?:flex|grid|gap-|p-|m-|w-|h-|text-|bg-|border-|rounded-|shadow-|space-|items-|justify-)\d*\b"
)


def get_extends(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"extends\s+['\"]([^'\"]+)['\"]", text)
    return m.group(1) if m else None


def count_forms(path: Path) -> int:
    return len(re.findall(r"<form\b", path.read_text(encoding="utf-8", errors="ignore"), re.I))


def infer_stack(path: Path, ext: str | None) -> str:
    rel = path.as_posix()
    if "base_erp" in rel or ext == "base_erp.html":
        return "base_erp (output.css + enterprise-system.css via Tailwind build)"
    if "base_tailwind" in rel or ext == "base_tailwind.html":
        return "base_tailwind (output-legacy.css DaisyUI + Tailwind build)"
    if "base_auth" in rel or (ext and "base_auth" in ext):
        return "base_auth_public (output.css + auth-public.css)"
    if "cadu_family" in rel or (ext and "cadu_family" in ext):
        return "cadu_family (CSS vanilla dedicado)"
    if ext and "cadu_skills" in ext:
        return "cadu_skills (CSS vanilla dedicado)"
    if ext and "base_erp" in ext:
        return "base_erp (via extends)"
    return f"partial/include (extends: {ext or 'n/a'})"


def classify(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    cx = bool(CX_FORM.search(text))
    daisy = bool(DAISY_FORM.search(text))
    tw = bool(TW_UTIL.search(text))
    ext = get_extends(path)
    stack = infer_stack(path, ext)

    if cx and not daisy:
        cat = "cx-* puro (sem DaisyUI em forms)"
    elif cx and daisy:
        cat = "misto cx-* + DaisyUI"
    elif daisy and not cx:
        cat = "DaisyUI/Tailwind legado"
    elif tw and not cx and not daisy:
        cat = "Tailwind utilities (sem cx-* nem DaisyUI explícito)"
    else:
        cat = "CSS vanilla / sem classes de form identificadas"

    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "forms": count_forms(path),
        "cat": cat,
        "stack": stack,
        "cx": cx,
        "daisy": daisy,
        "tw": tw,
        "extends": ext,
    }


rows = [classify(p) for p in FORM_FILES]
cat_counts = Counter(r["cat"] for r in rows)
form_counts = Counter()
for r in rows:
    form_counts[r["cat"]] += r["forms"]

print("=== RESUMO ===")
print(f"Arquivos com <form>: {len(rows)}")
print(f"Total tags <form>: {sum(r['forms'] for r in rows)}")
print()
for cat in sorted(cat_counts):
    print(f"{cat}: {cat_counts[cat]} arquivos, {form_counts[cat]} forms")

sections = [
    ("cx-* PURO (sem DaisyUI) — base_erp / Tailwind build", lambda r: r["cat"] == "cx-* puro (sem DaisyUI em forms)" and "base_erp" in r["stack"]),
    ("cx-* PURO — outros stacks", lambda r: r["cat"] == "cx-* puro (sem DaisyUI em forms)" and "base_erp" not in r["stack"]),
    ("MISTO cx-* + DaisyUI", lambda r: r["cat"] == "misto cx-* + DaisyUI"),
    ("DAISYUI LEGADO (sem cx-*)", lambda r: r["cat"] == "DaisyUI/Tailwind legado"),
    ("OUTROS", lambda r: r["cat"] not in ("cx-* puro (sem DaisyUI em forms)", "misto cx-* + DaisyUI", "DaisyUI/Tailwind legado")),
]

for title, pred in sections:
    subset = [r for r in rows if pred(r)]
    print()
    print(f"=== {title} ===")
    print(f"Count: {len(subset)} arquivos, {sum(r['forms'] for r in subset)} forms")
    for r in sorted(subset, key=lambda x: x["path"]):
        extra = f" — {r['stack']}" if "OUTROS" in title or "outros stacks" in title.lower() else ""
        print(f"  [{r['forms']}] {r['path']}{extra}")

print()
print("=== TOTAIS COMPOSTOS ===")
any_cx = [r for r in rows if r["cx"]]
erp_cx = [r for r in rows if r["cx"] and "base_erp" in r["stack"]]
erp_all = [r for r in rows if "base_erp" in r["stack"]]
family = [r for r in rows if "cadu_family" in r["stack"] or "cadu_skills" in r["stack"]]
auth = [r for r in rows if "base_auth" in r["stack"]]
legacy_tw = [r for r in rows if "base_tailwind" in r["stack"] or r["cat"] == "DaisyUI/Tailwind legado"]

print(f"Qualquer cx-* (puro + misto): {len(any_cx)} arquivos, {sum(r['forms'] for r in any_cx)} forms")
print(f"base_erp + cx-* (puro + misto): {len(erp_cx)} arquivos, {sum(r['forms'] for r in erp_cx)} forms")
print(f"base_erp total (Tailwind build): {len(erp_all)} arquivos, {sum(r['forms'] for r in erp_all)} forms")
print(f"cadu_family/skills (CSS vanilla): {len(family)} arquivos, {sum(r['forms'] for r in family)} forms")
print(f"auth public (output.css + auth-public.css): {len(auth)} arquivos, {sum(r['forms'] for r in auth)} forms")
print(f"DaisyUI legado: {len(legacy_tw)} arquivos, {sum(r['forms'] for r in legacy_tw)} forms")
