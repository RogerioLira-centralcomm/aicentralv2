#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "aicentralv2" / "templates"

PATTERNS = [
    (r'\bclass="[^"]*\bbtn(?:\s|-)', 'btn'),
    (r"\bclass='[^']*\bbtn(?:\s|-)", 'btn'),
    (r'\bmodal-box\b', 'modal-box'),
    (r'\bmodal-backdrop\b', 'modal-backdrop'),
    (r'\bclass="modal\b', 'modal'),
    (r'\bform-control\b', 'form-control'),
    (r'\binput-bordered\b', 'input-bordered'),
    (r'\bselect-bordered\b', 'select-bordered'),
    (r'\btextarea-bordered\b', 'textarea-bordered'),
    (r'\balert-error\b', 'alert-error'),
    (r'\balert-success\b', 'alert-success'),
    (r'\balert-warning\b', 'alert-warning'),
    (r'\balert-info\b', 'alert-info'),
    (r'\bclass="alert\b', 'alert'),
    (r'\btext-base-content\b', 'text-base-content'),
    (r'\bborder-base-\d+\b', 'border-base-*'),
    (r'\bbg-base-\d+\b', 'bg-base-*'),
    (r'\bclass="[^"]*\bbadge(?:\s|-)', 'badge'),
    (r'\bclass="[^"]*\bcard(?:\s|-)', 'card'),
    (r'\bclass="divider\b', 'divider'),
    (r'\bdropdown-content\b', 'dropdown-content'),
    (r'\bloading-spinner\b', 'loading-spinner'),
    (r'\bjoin-item\b', 'join-item'),
    (r'\bmenu\b.*\brounded-box\b', 'menu/rounded-box'),
]

SKIP = (
    'design_system.html',
    'design_system_enterprise.html',
    'components/tailwind_components.html',
    'format_prototypes/',
    'emails/',
)


def classify(name: str, rel: str) -> str:
    n = name.lower()
    r = rel.replace('\\', '/').lower()
    if 'modal' in n or '_drawer' in n or 'dialog' in n:
        return 'modal'
    if 'form' in n or n.endswith('_form.html') or 'checkout' in n or n.endswith('novo.html'):
        return 'form'
    if any(k in n for k in ('list', 'lista', 'pipeline', 'logs', 'gestao', 'index.html')):
        return 'lista'
    if '/crm/' in r and not any(x in n for x in ('modal', 'form', 'list')):
        return 'lista/página CRM'
    return 'outro'


def main() -> None:
    buckets: dict[str, list[tuple[str, set[str]]]] = {}

    for path in sorted(ROOT.rglob('*.html')):
        rel = str(path.relative_to(ROOT.parent)).replace('\\', '/')
        if any(s in rel for s in SKIP):
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        # ignore cx-* prefixed compound classes false positives
        hits: set[str] = set()
        for pat, label in PATTERNS:
            if re.search(pat, text):
                # skip if only cx-btn etc - pattern already excludes cx-
                if label == 'btn' and 'cx-btn' in text and not re.search(r'(?<!cx-)\bbtn(?:\s|-)', text):
                    continue
                hits.add(label)
        if not hits:
            continue
        cat = classify(path.name, rel)
        buckets.setdefault(cat, []).append((rel, hits))

    for cat in sorted(buckets):
        items = buckets[cat]
        print(f'## {cat} ({len(items)})')
        for rel, hits in items:
            print(f'- `{rel}` — {", ".join(sorted(hits))}')
        print()

    print('TOTAL:', sum(len(v) for v in buckets.values()))


if __name__ == '__main__':
    main()
