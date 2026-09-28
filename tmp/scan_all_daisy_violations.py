#!/usr/bin/env python3
import importlib.util
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("chk", ROOT / "scripts/check_priority_daisyui.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

roots = [
    ROOT / "aicentralv2/templates",
    ROOT / "aicentralv2/static/js",
]
skip_parts = (
    "format_prototypes/",
    "emails/",
    "design_system.html",
    "components/tailwind_components.html",
)

by_file: dict[str, list[str]] = {}
for base in roots:
    glob = "**/*.html" if base.name == "templates" else "**/*.js"
    for path in sorted(base.glob(glob)):
        rel = path.relative_to(ROOT).as_posix()
        if any(s in rel for s in skip_parts):
            continue
        v = chk.violations(path)
        if v:
            by_file[rel] = [f"L{line}:{tok}" for line, tok in v]

print(f"Arquivos com violações reais: {len(by_file)}")
tokens = Counter()
for rel, items in sorted(by_file.items(), key=lambda x: -len(x[1])):
    for it in items:
        tokens[it.split(":", 1)[1]] += 1
    if len(by_file) <= 40 or len(items) >= 3:
        print(f"\n{rel} ({len(items)})")
        for it in items[:12]:
            print(f"  {it}")
        if len(items) > 12:
            print(f"  ... +{len(items)-12}")

print("\nTop tokens:")
for tok, n in tokens.most_common(25):
    print(f"  {tok}: {n}")
