from pathlib import Path
import re
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from check_priority_daisyui import FORBIDDEN, violations

# Extract class tokens from HTML/JS, ignoring cx-* prefixes
CLASS_ATTR = re.compile(r"""class\s*=\s*(['"])(.*?)\1""", re.DOTALL)
CLASS_LIST = re.compile(r"""classList\.(?:add|remove|toggle)\((['"])([^'"]+)\1\)""")
CLASS_NAME = re.compile(r"""className\s*=\s*(['"])(.*?)\1""", re.DOTALL)

def tokens_from_source(text: str) -> list[str]:
    out: list[str] = []
    for m in CLASS_ATTR.finditer(text):
        out.extend(re.split(r"\s+", m.group(2).strip()))
    for m in CLASS_LIST.finditer(text):
        out.extend(re.split(r"\s+", m.group(2).strip()))
    for m in CLASS_NAME.finditer(text):
        out.extend(re.split(r"\s+", m.group(2).strip()))
    return [t for t in out if t and not t.startswith(("cx-", "crm-v3-", "pi-op-", "cot-op-"))]

def categorize(tokens: list[str]) -> Counter:
    c = Counter()
    for t in tokens:
        if FORBIDDEN.fullmatch(t):
            # bucket by prefix
            base = t.split("-", 1)[0]
            c[t] += 1
    return c

files = {
    "clientes.html": ROOT / "aicentralv2/templates/clientes.html",
    "modal_busca_cliente.html": ROOT / "aicentralv2/templates/modal_busca_cliente.html",
    "agencias_vinculadas_form.js": ROOT / "aicentralv2/static/js/agencias_vinculadas_form.js",
    "clientes.css": ROOT / "aicentralv2/static/css/clientes.css",
    "clientes.js": ROOT / "aicentralv2/static/js/clientes.js",
}

# extra daisy theme tokens not in FORBIDDEN regex
EXTRA = re.compile(r"^(?:divider|base-content|base-\d+)$")

print("=== Strict DaisyUI (FORBIDDEN regex, excl. cx-*) ===")
for name, p in files.items():
    if not p.exists():
        continue
    v = violations(p)
    vc = Counter(t for _, t in v)
    extra = [t for t in tokens_from_source(p.read_text(encoding="utf-8")) if EXTRA.fullmatch(t)]
    ec = Counter(extra)
    print(f"\n{name}: checker violations={len(v)}")
    if vc:
        for tok, cnt in sorted(vc.items(), key=lambda x: -x[1]):
            print(f"  {tok}: {cnt}")
    if ec:
        print(f"  extra theme tokens: {dict(ec)}")

# cx adoption sections
html = files["clientes.html"].read_text(encoding="utf-8")
sections = {
    "list/filters (lines 1-331)": html.split("<!-- Modal de Cliente -->")[0],
    "modals (rest)": html.split("<!-- Modal de Cliente -->")[1] if "<!-- Modal de Cliente -->" in html else "",
}
print("\n=== cx-* adoption by section ===")
for sec, chunk in sections.items():
    cx = len(re.findall(r"\bcx-[a-z0-9-]+\b", chunk))
    raw_fields = len(re.findall(r'class="w-full px-1\.5 py-0\.5 text-xs border', chunk))
    print(f"{sec}: cx-*={cx}, raw inline inputs/selects={raw_fields}")

all_cx = re.findall(r"\bcx-[a-z0-9-]+\b", html)
print(f"\nTotal cx-* in clientes.html: {len(all_cx)} ({len(set(all_cx))} unique)")
for tok, cnt in Counter(all_cx).most_common(25):
    print(f"  {tok}: {cnt}")
