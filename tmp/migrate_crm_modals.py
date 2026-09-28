#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "aicentralv2" / "templates" / "crm"

REPLS = [
    ('class="modal modal-cliente-dialog"', 'class="cx-modal-shell modal-cliente-dialog"'),
    ('class="modal"', 'class="cx-modal-shell"'),
    ('class="modal-box modal-cliente-box', 'class="cx-modal-panel crm-modal-panel-dense modal-cliente-box'),
    ('class="modal-box ', 'class="cx-modal-panel '),
    ('class="modal-box"', 'class="cx-modal-panel"'),
    ('class="modal-backdrop bg-black/50"', 'class="cx-modal-dismiss"'),
    ('class="modal-action', 'class="cx-modal-actions'),
    ('class="form-control', 'class="cx-field'),
]

BTN_RES = [
    (r'class="btn btn-sm btn-circle btn-ghost"', 'class="cx-btn cx-btn-sm cx-btn-icon cx-btn-ghost"'),
    (r'class="btn btn-sm btn-ghost"', 'class="cx-btn cx-btn-sm cx-btn-ghost"'),
    (r'class="btn btn-sm btn-primary"', 'class="cx-btn cx-btn-sm cx-btn-primary"'),
    (r'class="btn btn-sm btn-secondary"', 'class="cx-btn cx-btn-sm cx-btn-secondary"'),
    (r'class="btn btn-sm btn-error"', 'class="cx-btn cx-btn-sm cx-btn-danger"'),
    (r'class="btn btn-sm btn-success"', 'class="cx-btn cx-btn-sm cx-btn-primary"'),
    (r'class="btn btn-sm btn-info"', 'class="cx-btn cx-btn-sm cx-btn-secondary"'),
    (r'class="btn btn-sm btn-outline"', 'class="cx-btn cx-btn-sm cx-btn-outline"'),
    (r'class="btn btn-sm"', 'class="cx-btn cx-btn-sm cx-btn-secondary"'),
    (r'class="btn btn-xs btn-ghost"', 'class="cx-btn cx-btn-xs cx-btn-ghost"'),
    (r'class="btn btn-primary btn-sm"', 'class="cx-btn cx-btn-sm cx-btn-primary"'),
]

for path in sorted(ROOT.glob("_modal*.html")):
    text = path.read_text(encoding="utf-8")
    orig = text
    for a, b in REPLS:
        text = text.replace(a, b)
    for pat, rep in BTN_RES:
        text = re.sub(pat, rep, text)
    text = text.replace("input-bordered", "cx-input cx-input-sm")
    text = text.replace("select-bordered", "cx-select cx-select-sm")
    text = text.replace("textarea-bordered", "cx-textarea cx-textarea-sm")
    text = re.sub(r'class="input ', 'class="cx-input cx-input-sm ', text)
    text = re.sub(r'class="select ', 'class="cx-select cx-select-sm ', text)
    text = re.sub(r'class="textarea ', 'class="cx-textarea cx-textarea-sm ', text)
    text = re.sub(r'class="alert alert-error', 'class="cx-alert cx-alert-danger', text)
    text = re.sub(r'class="alert alert-success', 'class="cx-alert cx-alert-success', text)
    text = re.sub(r'class="badge badge-xs badge-success', 'class="cx-badge cx-badge-xs cx-badge-success', text)
    text = re.sub(r'class="badge badge-xs', 'class="cx-badge cx-badge-xs cx-badge-muted', text)
    text = text.replace("bg-base-100", "bg-white")
    # tabs in modal contato
    text = text.replace('class="tabs tabs-bordered', 'class="crm-tabs crm-tabs-bordered')
    text = text.replace('class="tab tab-active"', 'class="crm-tab crm-tab-active"')
    text = text.replace('class="tab"', 'class="crm-tab"')
    text = re.sub(r'class="radio radio-xs radio-success"', 'class="crm-radio"', text)
    text = re.sub(r'class="radio radio-xs radio-info"', 'class="crm-radio"', text)
    text = re.sub(r'class="label label-text', 'class="cx-label', text)
    text = re.sub(r'class="label cursor-pointer', 'class="crm-radio-label cursor-pointer', text)
    text = re.sub(r'class="checkbox checkbox-xs"', 'class="crm-checkbox-xs"', text)
    if text != orig:
        path.write_text(text, encoding="utf-8")
        print("updated", path.name)
