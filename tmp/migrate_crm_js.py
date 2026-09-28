#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "aicentralv2" / "static" / "js" / "crm.js"
text = path.read_text(encoding="utf-8")
replacements = [
    ('<span class="loading loading-spinner loading-md"></span>', '<span class="cx-spinner cx-spinner-sm"></span>'),
    ('<span class="loading loading-spinner loading-sm col-span-full"></span>', '<span class="cx-spinner cx-spinner-sm col-span-full"></span>'),
    ('<span class="loading loading-spinner loading-sm"></span>', '<span class="cx-spinner cx-spinner-sm"></span>'),
    ('<span class="loading loading-spinner"></span>', '<span class="cx-spinner cx-spinner-sm"></span>'),
    ('class="crm-cliente-edit btn btn-ghost btn-xs btn-square h-5 w-5 min-h-0 p-0"', 'class="crm-cliente-edit cx-btn cx-btn-xs cx-btn-icon cx-btn-ghost h-5 w-5 min-h-0 p-0"'),
    ("return '<span class=\"badge badge-xs badge-success gap-1'><span class=\"w-1.5 h-1.5 rounded-full bg-white\"></span>Ativo</span>';",
     "return '<span class=\"cx-badge cx-badge-xs cx-badge-success gap-1\"><span class=\"w-1.5 h-1.5 rounded-full bg-white\"></span>Ativo</span>';"),
    ("return '<span class=\"badge badge-xs badge-ghost gap-1'><span class=\"w-1.5 h-1.5 rounded-full bg-current opacity-50\"></span>Conquistado</span>';",
     "return '<span class=\"cx-badge cx-badge-xs cx-badge-muted gap-1\"><span class=\"w-1.5 h-1.5 rounded-full bg-current opacity-50\"></span>Conquistado</span>';"),
    ('<span class="badge badge-xs">', '<span class="cx-badge cx-badge-xs cx-badge-muted">'),
    (".classList.add('loading')", ".classList.add('is-loading')"),
    (".classList.remove('loading')", ".classList.remove('is-loading')"),
]
for a, b in replacements:
    text = text.replace(a, b)
path.write_text(text, encoding="utf-8")
print("crm.js updated")
