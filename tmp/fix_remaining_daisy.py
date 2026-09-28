#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "aicentralv2"

# crm.js
js = (ROOT / "static/js/crm.js").read_text(encoding="utf-8")
js = js.replace("class=\"badge badge-xs badge-success", "class=\"cx-badge cx-badge-xs cx-badge-success")
js = js.replace("class=\"badge badge-xs badge-ghost", "class=\"cx-badge cx-badge-xs cx-badge-muted")
js = js.replace("class=\"badge badge-xs mr-1\"", "class=\"cx-badge cx-badge-xs cx-badge-muted mr-1\"")
js = js.replace("class=\"badge badge-xs\"", "class=\"cx-badge cx-badge-xs cx-badge-muted\"")
js = js.replace("class=\"btn btn-xs btn-success w-full mt-1\"", "class=\"cx-btn cx-btn-xs cx-btn-primary w-full mt-1\"")
js = js.replace("loading loading-spinner", "cx-spinner")
js = js.replace("loading-sm", "cx-spinner-sm")
js = js.replace("loading-md", "cx-spinner-sm")
(ROOT / "static/js/crm.js").write_text(js, encoding="utf-8")
print("crm.js")

form = (ROOT / "templates/cadu_cotacoes_form_legado.html").read_text(encoding="utf-8")
form = form.replace('class="btn btn-sm join-item', 'class="cx-btn cx-btn-sm')
form = form.replace('class="input  input-sm join-item', 'class="cx-input cx-input-sm')
form = re.sub(r'class="input  input-sm', 'class="cx-input cx-input-sm', form)
form = re.sub(r'class="select  select-sm', 'class="cx-select cx-select-sm', form)
form = form.replace('style="background-color:#72cd80;border-color:#72cd80;color:#fff;"', '')
form = form.replace('id="briefing_btn_busca" class="cx-btn cx-btn-sm"', 'id="briefing_btn_busca" class="cx-btn cx-btn-sm cx-btn-primary"')
if "{% from 'macros/cx_ui.html' import flash_messages %}" not in form:
    form = form.replace(
        "{% extends 'base_erp.html' %}",
        "{% extends 'base_erp.html' %}\n{% from 'macros/cx_ui.html' import flash_messages %}",
    )
form = re.sub(
    r"\{% with messages = get_flashed_messages\(with_categories=true\) %\}.*?\{% endwith %\}",
    "{% with messages = get_flashed_messages(with_categories=true) %}\n    {% if messages %}<div class=\"mb-3\">{{ flash_messages(messages) }}</div>{% endif %}\n  {% endwith %}",
    form,
    count=1,
    flags=re.S,
)
(ROOT / "templates/cadu_cotacoes_form_legado.html").write_text(form, encoding="utf-8")
print("form legado")

leg = (ROOT / "templates/cadu_cotacoes_legado.html").read_text(encoding="utf-8")
if "flash_messages" not in leg:
    leg = leg.replace("{% extends 'base_erp.html' %}", "{% extends 'base_erp.html' %}\n{% from 'macros/cx_ui.html' import flash_messages %}")
(ROOT / "templates/cadu_cotacoes_legado.html").write_text(leg, encoding="utf-8")
print("lista legado")
