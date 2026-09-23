from pathlib import Path
import re
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]

DAISY_CATEGORIES = {
    "alert": r"\balert(?:-(?:error|success|warning|info))?\b",
    "btn": r"\bbtn(?:-(?:primary|secondary|accent|ghost|outline|error|success|warning|info|neutral|sm|xs|lg|circle|square|wide|block|link|disabled))?\b",
    "badge": r"\bbadge(?:-(?:primary|secondary|accent|ghost|outline|error|success|warning|info|neutral|sm|xs|lg))?\b",
    "modal": r"\bmodal(?:-(?:box|action|backdrop|compact|bottom|middle|open))?\b",
    "form-control": r"\bform-control\b",
    "table": r"\btable(?:-(?:xs|sm|md|lg|zebra|pin-rows|pin-cols))?\b",
    "drawer": r"\bdrawer(?:-(?:content|side|toggle|open|end))?\b",
    "card": r"\bcard(?:-(?:body|title|actions|compact|side))?\b",
    "select": r"\bselect(?:-(?:bordered|sm|xs|lg|error|ghost))?\b",
    "input": r"\binput(?:-(?:bordered|sm|xs|lg|error|ghost))?\b",
    "checkbox": r"\bcheckbox(?:-(?:primary|success|warning|error|sm|xs|lg))?\b",
    "radio": r"\bradio(?:-(?:primary|success|warning|error|sm|xs|lg))?\b",
    "toggle": r"\btoggle(?:-(?:primary|success|warning|error|sm|xs|lg))?\b",
    "loading": r"\bloading(?:-(?:spinner|dots|ring|ball|bars|infinity|xs|sm|md|lg))?\b",
    "menu": r"\bmenu(?:-(?:title|horizontal|vertical|compact))?\b",
    "dropdown": r"\bdropdown(?:-(?:content|end|top|bottom|left|right|hover|open))?\b",
    "divider": r"\bdivider\b",
    "theme/base": r"\b(?:base-content|base-\d+)\b",
    "text-error": r"\btext-error\b",
    "tab": r"\b(?:tab-active|tab-btn|tabs)\b",
    "join": r"\bjoin(?:-(?:item|vertical|horizontal))?\b",
    "steps": r"\bsteps?\b",
    "progress": r"\bprogress(?:-(?:primary|success|warning|error|info))?\b",
    "avatar": r"\bavatar\b",
    "toast": r"\btoast(?:-(?:top|bottom|start|center|end|middle))?\b",
}

files = [
    ROOT / "aicentralv2/templates/clientes.html",
    ROOT / "aicentralv2/templates/modal_busca_cliente.html",
    ROOT / "aicentralv2/static/js/agencias_vinculadas_form.js",
    ROOT / "aicentralv2/static/css/clientes.css",
]

for p in files:
    text = p.read_text(encoding="utf-8")
    print(f"\n=== {p.relative_to(ROOT)} ===")
    total = 0
    for cat, pat in DAISY_CATEGORIES.items():
        hits = re.findall(pat, text)
        if hits:
            total += len(hits)
            print(f"  {cat}: {len(hits)} {dict(Counter(hits))}")
    print(f"  TOTAL broad daisy-ish: {total}")

html = (ROOT / "aicentralv2/templates/clientes.html").read_text(encoding="utf-8")
raw_input = len(re.findall(r'<input[^>]+class="[^"]*w-full px-1\.5', html))
raw_select = len(re.findall(r'<select[^>]+class="[^"]*w-full px-1\.5', html))
cx_input_html = len(re.findall(r'class="[^"]*cx-input', html))
cx_select_html = len(re.findall(r'class="[^"]*cx-select', html))
cx_field = len(re.findall(r'\bcx-field\b', html))
print("\n=== cx adoption (clientes.html) ===")
print(f"cx-field wrappers: {cx_field}")
print(f"cx-input in HTML: {cx_input_html}")
print(f"cx-select in HTML: {cx_select_html}")
print(f"raw tailwind inputs in modal: {raw_input}")
print(f"raw tailwind selects in modal: {raw_select}")
