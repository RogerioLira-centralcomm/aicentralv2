#!/usr/bin/env python3
"""Falha quando as telas prioritárias ainda contêm classes DaisyUI."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    *sorted((ROOT / "aicentralv2/templates").glob("cadu_audiencias*.html")),
    *sorted((ROOT / "aicentralv2/templates").glob("cadu_categorias*.html")),
    *sorted((ROOT / "aicentralv2/templates").glob("cadu_subcategorias*.html")),
    *sorted((ROOT / "aicentralv2/templates/crm_v3").glob("*.html")),
    ROOT / "aicentralv2/templates/briefing_list.html",
    ROOT / "aicentralv2/templates/briefing_form.html",
    ROOT / "aicentralv2/templates/crm_pipeline.html",
    ROOT / "aicentralv2/templates/cadu_cotacoes.html",
    ROOT / "aicentralv2/templates/cadu_cotacoes_form.html",
    ROOT / "aicentralv2/templates/campanhas_pi_lista.html",
    ROOT / "aicentralv2/templates/campanhas_pi.html",
    ROOT / "aicentralv2/templates/interesse_produto.html",
    ROOT / "aicentralv2/templates/up_audiencia.html",
    ROOT / "aicentralv2/templates/admin_metrics_dashboard.html",
    ROOT / "aicentralv2/templates/cadu_cotacoes_detalhes.html",
    ROOT / "aicentralv2/templates/cadu_cotacoes_detalhes_legado.html",
    ROOT / "aicentralv2/templates/cadu_pi.html",
    ROOT / "aicentralv2/templates/cadu_pi_form.html",
    ROOT / "aicentralv2/templates/partials/nf_import.html",
    ROOT / "aicentralv2/templates/cadu_leads.html",
    ROOT / "aicentralv2/templates/clientes.html",
    ROOT / "aicentralv2/templates/modal_busca_cliente.html",
    ROOT / "aicentralv2/templates/crm_v3.html",
    ROOT / "aicentralv2/templates/macros/ui.html",
    ROOT / "aicentralv2/templates/financeiro/meus_reembolsos.html",
    ROOT / "aicentralv2/templates/financeiro/gestao.html",
    ROOT / "aicentralv2/templates/financeiro/relatorio_incentivos.html",
    ROOT / "aicentralv2/static/js/leads.js",
    ROOT / "aicentralv2/static/js/crm_v3.js",
    ROOT / "aicentralv2/static/js/crm_v3_drawers.js",
    ROOT / "aicentralv2/static/js/cadu_pi_list.js",
    ROOT / "aicentralv2/static/js/cadu_pi_operacao.js",
    ROOT / "aicentralv2/static/js/campanhas-ui.js",
    ROOT / "aicentralv2/static/js/campanha_pi_detalhe.js",
    ROOT / "aicentralv2/static/js/cotacao_detalhes.js",
    ROOT / "aicentralv2/static/js/financeiro.js",
    ROOT / "aicentralv2/static/js/financeiro_gestao.js",
]

CLASS_ATTRIBUTE = re.compile(r"""class\s*=\s*(['"])(.*?)\1""", re.DOTALL)
CLASS_LIST_CALL = re.compile(r"""classList\.(?:add|remove|toggle|contains)\((.*?)\)""", re.DOTALL)
CLASS_NAME_ASSIGNMENT = re.compile(r"""className\s*=\s*(['"])(.*?)\1""", re.DOTALL)
QUOTED_TOKEN = re.compile(r"""(['"])([^'"]+)\1""")
FORBIDDEN = re.compile(
    r"^(?:"
    r"modal(?:-(?:box|action|backdrop|compact|bottom|middle|open))?|"
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
    r"dropdown(?:-(?:content|end|top|bottom|left|right|hover|open))?|toast(?:-(?:top|bottom|start|center|end|middle))?"
    r"|avatar|placeholder|menu(?:-(?:title|horizontal|vertical|compact))?"
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
    for match in CLASS_LIST_CALL.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        for quoted in QUOTED_TOKEN.finditer(match.group(1)):
            token = quoted.group(2)
            if not token.startswith(("cx-", "crm-v3-", "pi-op-", "cot-op-")) and FORBIDDEN.fullmatch(token):
                found.append((line, token))
    for match in CLASS_NAME_ASSIGNMENT.finditer(source):
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
