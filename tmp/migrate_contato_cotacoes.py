#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "aicentralv2" / "templates"

def migrate_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text
    if path.name == "contato_form.html":
        text = text.replace("{% extends 'base_tailwind.html' %}", "{% extends 'base_erp.html' %}\n{% from 'macros/cx_ui.html' import flash_messages %}\n{% block page_label %}CRM{% endblock %}\n{% block page_subtitle %}Contatos{% endblock %}")
        text = text.replace("max-w-2xl mx-auto bg-base-100 rounded-xl shadow-lg p-4", "max-w-2xl mx-auto cx-card bg-white border border-slate-200 shadow-sm p-4")
        text = re.sub(r'class="alert alert-error[^"]*"', 'class="cx-alert cx-alert-danger text-sm"', text)
        text = re.sub(r'class="alert alert-success[^"]*"', 'class="cx-alert cx-alert-success text-sm"', text)
        text = re.sub(r'class="alert alert-warning[^"]*"', 'class="cx-alert cx-alert-warning text-sm"', text)
        text = re.sub(r'class="alert alert-info[^"]*"', 'class="cx-alert cx-alert-info text-sm"', text)
        text = re.sub(r'<div class="form-control">', '<div class="cx-field">', text)
        text = re.sub(r'class="label font-semibold text-sm"', 'class="cx-label font-semibold text-sm"', text)
        text = re.sub(r'class="input input-bordered w-full"', 'class="cx-input cx-input-sm w-full"', text)
        text = re.sub(r'class="select select-bordered w-full"', 'class="cx-select cx-select-sm w-full"', text)
        text = re.sub(r'class="textarea textarea-bordered w-full"', 'class="cx-textarea cx-textarea-sm w-full"', text)
        text = re.sub(r'class="btn btn-ghost"', 'class="cx-btn cx-btn-secondary"', text)
        text = re.sub(r'class="btn btn-primary"', 'class="cx-btn cx-btn-primary"', text)
        text = text.replace("text-base-content/70", "text-slate-600")
        # flash block
        text = text.replace(
            """{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      <div class="mb-4 space-y-2">
        {% for category, message in messages %}
          <div class="alert """,
            """{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      <div class="mb-4">{{ flash_messages(messages) }}</div>
    {% endif %}
  {% endwith %}
  <!-- legacy-flash-removed -->
          <div class="alert """
        )
        # remove broken legacy flash - simpler: read and fix manually if needed

    common = [
        ('class="modal"', 'class="cx-modal-shell"'),
        ('class="modal-box ', 'class="cx-modal-panel '),
        ('class="modal-backdrop bg-black/50"', 'class="cx-modal-dismiss"'),
        ('class="card bg-base-100', 'class="cx-card bg-white border border-slate-200'),
        ('class="card-body', 'class="cx-card-body'),
        ('class="card-title', 'class="cx-card-title'),
        ('class="btn btn-primary btn-sm"', 'class="cx-btn cx-btn-sm cx-btn-primary"'),
        ('class="btn btn-ghost btn-sm"', 'class="cx-btn cx-btn-sm cx-btn-ghost"'),
        ('class="btn btn-xs btn-ghost', 'class="cx-btn cx-btn-xs cx-btn-ghost'),
        ('class="btn btn-sm join-item"', 'class="cx-btn cx-btn-sm"'),
        ('class="btn btn-sm btn-square join-item"', 'class="cx-btn cx-btn-sm cx-btn-icon"'),
        ('join join-horizontal', 'flex flex-row gap-0'),
        ('form-control', 'cx-field'),
        ('input-bordered', ''),
        ('select-bordered', ''),
        ('textarea-bordered', ''),
    ]
    for a, b in common:
        text = text.replace(a, b)
    text = re.sub(r'class="btn btn-sm([^"]*)" style="background-color:#72cd80[^"]*"', 'class="cx-btn cx-btn-sm cx-btn-primary"', text)
    text = re.sub(r'class="btn btn-sm join-item" style="background-color:#72cd80[^"]*"', 'class="cx-btn cx-btn-sm cx-btn-primary"', text)
    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False

files = [
    ROOT / "contato_form.html",
    ROOT / "cadu_cotacoes_legado.html",
    ROOT / "cadu_cotacoes_form_legado.html",
]
for f in files:
    if f.exists() and migrate_file(f):
        print("updated", f.name)
