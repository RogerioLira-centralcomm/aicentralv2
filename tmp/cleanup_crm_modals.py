#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "aicentralv2"

def clean(text: str) -> str:
    text = re.sub(r'\bcx-input cx-input-sm cx-input cx-input-sm input-sm\b', 'cx-input cx-input-sm', text)
    text = re.sub(r'\bcx-textarea cx-textarea-sm cx-textarea cx-textarea-sm textarea-sm\b', 'cx-textarea cx-textarea-sm', text)
    text = re.sub(r'\bcx-select cx-select-sm cx-select cx-select-sm select-sm\b', 'cx-select cx-select-sm', text)
    text = text.replace('class="radio radio-xs"', 'class="crm-radio"')
    text = re.sub(r'<label class="label py-0"><span class="label-text text-xs">([^<]+)</span></label>',
                  r'<label class="cx-label-row py-0"><span class="cx-label text-xs">\1</span></label>', text)
    text = re.sub(r'<span class="label-text text-xs">', '<span class="cx-label text-xs">', text)
    text = text.replace('class="table table-xs table-zebra w-full"', 'class="cx-table cx-table-dense w-full"')
    text = re.sub(r'class="alert(?![-\w])', 'class="cx-alert', text)
    text = text.replace('class="join join-horizontal', 'class="flex flex-row')
    text = text.replace('class="join join-vertical', 'class="flex flex-col')
    text = text.replace('label-text-alt', 'cx-help')
    text = re.sub(r'<label class="label ', '<label class="cx-label-row ', text)
    return text

for rel in [
    "templates/crm/_modal_contato.html",
    "templates/crm/_modal_contatos_crm.html",
    "templates/crm/_modal_status_completo.html",
    "templates/contato_form.html",
    "templates/cadu_cotacoes_form_legado.html",
]:
    p = ROOT / rel
    t = clean(p.read_text(encoding="utf-8"))
    p.write_text(t, encoding="utf-8")
    print(rel)

js = (ROOT / "static/js/crm.js").read_text(encoding="utf-8")
js = js.replace('class="checkbox checkbox-xs crm-sug-check"', 'class="crm-checkbox-xs crm-sug-check"')
(ROOT / "static/js/crm.js").write_text(js, encoding="utf-8")
print("crm.js")
