import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(
    r"^(?:modal(?:-(?:box|action|backdrop|compact|bottom|middle|open))?|"
    r"btn(?:-(?:primary|secondary|accent|ghost|outline|error|success|warning|info|neutral|sm|xs|lg|circle|square|wide|block|link|disabled))?|"
    r"badge(?:-(?:primary|secondary|accent|ghost|outline|error|success|warning|info|neutral|sm|xs|lg))?|"
    r"card(?:-(?:body|title|actions|compact|side))?|form-control|"
    r"label(?:-(?:text|text-alt))?|input(?:-(?:bordered|sm|xs|lg|error|ghost))?|"
    r"select(?:-(?:bordered|sm|xs|lg|error|ghost))?|textarea(?:-(?:bordered|sm|xs|lg|error|ghost))?|"
    r"alert(?:-(?:error|success|warning|info))?|loading(?:-(?:spinner|dots|ring|ball|bars|infinity|xs|sm|md|lg))?|"
    r"toggle(?:-(?:primary|success|warning|error|sm|xs|lg))?|checkbox(?:-(?:primary|success|warning|error|sm|xs|lg))?|"
    r"radio(?:-(?:primary|success|warning|error|sm|xs|lg))?|range(?:-(?:primary|success|warning|error|xs|sm|md|lg))?|"
    r"steps?|step(?:-(?:primary|success|warning|error|info))?|table(?:-(?:xs|sm|md|lg|zebra|pin-rows|pin-cols))?|"
    r"progress(?:-(?:primary|success|warning|error|info))?|join(?:-(?:item|vertical|horizontal))?|"
    r"dropdown(?:-(?:content|end|top|bottom|left|right|hover|open))?|toast(?:-(?:top|bottom|start|center|end|middle))?|"
    r"avatar|placeholder|menu(?:-(?:title|horizontal|vertical|compact))?)$"
)

SEMANTIC = re.compile(
    r"\b(?:text-base-content|bg-base-\d+|border-base-\d+|text-primary(?:-content)?|"
    r"text-error|text-warning|text-success|text-info|bg-primary|bg-success|"
    r"collapse(?:-(?:arrow|title|content|open|close))?|tabs(?:-(?:boxed|bordered|lifted|xs|sm|md|lg))?|"
    r"tab(?:-(?:active|disabled))?|link(?:-(?:primary|secondary|accent|hover))?)\b"
)

for name in ["parametros_testes_dv.html", "parametros_testes_dv_legado.html"]:
    p = ROOT / "aicentralv2/templates" / name
    src = p.read_text(encoding="utf-8")
    tokens: set[str] = set()
    semantic: set[str] = set()
    for m in re.finditer(r'class\s*=\s*(["\'])(.*?)\1', src, re.DOTALL):
        for t in re.split(r"\s+", m.group(2).strip()):
            if not t:
                continue
            if FORBIDDEN.fullmatch(t):
                tokens.add(t)
            if SEMANTIC.search(t):
                semantic.add(t)
    for m in re.finditer(r"classList\.(?:add|remove|toggle)\((.*?)\)", src, re.DOTALL):
        for q in re.finditer(r'(["\'])([^"\']+)\1', m.group(1)):
            t = q.group(2)
            if FORBIDDEN.fullmatch(t):
                tokens.add(t)
    print(f"=== {name} ===")
    print(f"FORBIDDEN-style DaisyUI tokens: {len(tokens)}")
    for t in sorted(tokens):
        print(f"  {t}")
    print(f"Semantic/theme tokens: {len(semantic)}")
    for t in sorted(semantic):
        print(f"  {t}")
    print(f"Lines: {src.count(chr(10))+1}")
