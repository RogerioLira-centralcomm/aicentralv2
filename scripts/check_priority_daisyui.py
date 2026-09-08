#!/usr/bin/env python3
"""Falha quando as telas prioritárias ainda contêm classes DaisyUI."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    *sorted((ROOT / "aicentralv2/templates").glob("cadu_audiencias*.html")),
    ROOT / "aicentralv2/templates/cadu_cotacoes_detalhes.html",
    ROOT / "aicentralv2/templates/cadu_cotacoes_detalhes_legado.html",
    ROOT / "aicentralv2/templates/cadu_pi.html",
    ROOT / "aicentralv2/templates/cadu_pi_form.html",
    ROOT / "aicentralv2/templates/cadu_leads.html",
    ROOT / "aicentralv2/templates/clientes.html",
    ROOT / "aicentralv2/templates/modal_busca_cliente.html",
    ROOT / "aicentralv2/templates/crm_v3/_modals.html",
    ROOT / "aicentralv2/static/js/leads.js",
    ROOT / "aicentralv2/static/js/crm_v3.js",
]

CLASS_ATTRIBUTE = re.compile(r"""class\s*=\s*(['"])(.*?)\1""", re.DOTALL)
FORBIDDEN = re.compile(
    r"^(?:"
    r"modal(?:-.+)?|btn(?:-.+)?|badge(?:-.+)?|card(?:-.+)?|"
    r"form-control|label(?:-.+)?|input(?:-.+)?|select(?:-.+)?|textarea(?:-.+)?|"
    r"alert(?:-.+)?|loading(?:-.+)?|toggle(?:-.+)?|checkbox(?:-.+)?|radio(?:-.+)?|"
    r"range(?:-.+)?|steps?|step(?:-.+)?|table(?:-.+)?|progress(?:-.+)?|"
    r"join(?:-.+)?|dropdown(?:-.+)?|toast(?:-.+)?"
    r")$"
)


def violations(path: Path) -> list[tuple[int, str]]:
    source = path.read_text(encoding="utf-8")
    found: list[tuple[int, str]] = []
    for match in CLASS_ATTRIBUTE.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        for token in re.split(r"\s+", match.group(2).strip()):
            if token and not token.startswith(("cx-", "crm-v3-", "pi-op-", "cot-op-")) and FORBIDDEN.fullmatch(token):
                found.append((line, token))
    return found


def main() -> int:
    failures = []
    for path in FILES:
        if not path.exists():
            continue
        for line, token in violations(path):
            failures.append(f"{path.relative_to(ROOT)}:{line}: {token}")

    if failures:
        print("Classes DaisyUI encontradas nas telas prioritárias:")
        print("\n".join(failures))
        return 1

    print(f"OK: {len([path for path in FILES if path.exists()])} arquivos prioritários sem classes DaisyUI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
