#!/usr/bin/env python3
"""Inventário: endpoint → legacy Daisy CSS → classes Daisy no template principal."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "aicentralv2/templates"
ROUTES_GLOBS = [
    ROOT / "aicentralv2/routes.py",
    *ROOT.glob("aicentralv2/*/routes.py"),
]

# Copiado de erp_page_context (evita import Flask)
ENDPOINT_CONTEXT = {
    "index": ("geral", "inicio"),
    "crm_v3.crm_v3": ("crm", "clientes"),
    "crm_pipeline": ("comercial", "pipeline"),
    "clientes": ("crm", "clientes"),
    "leads_list": ("comercial", "leads"),
    "leads_analise": ("comercial", "analise_leads"),
    "briefing_list": ("comercial", "briefings"),
    "briefing_create": ("comercial", "briefing"),
    "briefing_edit": ("comercial", "briefing"),
    "smart_planner.index": ("comercial", "smart_planner"),
    "smart_planner.novo": ("comercial", "smart_planner"),
    "smart_planner.briefing": ("comercial", "smart_planner"),
    "smart_planner.revisao": ("comercial", "smart_planner"),
    "smart_planner.canais": ("comercial", "smart_planner"),
    "smart_planner.gerar": ("comercial", "smart_planner"),
    "smart_planner.canvas": ("comercial", "smart_planner"),
    "smart_planner.canvas_editar": ("comercial", "smart_planner"),
    "smart_planner.publico": ("comercial", "smart_planner"),
    "places.index": ("comercial", "places"),
    "places.novo": ("comercial", "places"),
    "places.editar": ("comercial", "places"),
    "cadu_pi_novo": ("comercial", "pi_recebido"),
    "cadu_pi_lista": ("operacao", "pedidos_insercao"),
    "cadu_pi_editar": ("operacao", "pedidos_insercao"),
    "campanhas_pi": ("operacao", "campanhas"),
    "campanhas_pi_lista": ("operacao", "acompanhamento"),
    "campanha_pi_detalhe": ("operacao", "acompanhamento"),
    "diarios_campanha": ("operacao", "diarios"),
    "status_campanha": ("operacao", "status_campanha"),
    "link_destinos": ("operacao", "links_destino"),
    "metricas_semanais": ("operacao", "metricas"),
    "assinaturas.mesa": ("operacao", "assinaturas"),
    "assinaturas.novo": ("operacao", "assinaturas"),
    "assinaturas.viewer": ("operacao", "assinaturas"),
    "tbl_cargo_contato": ("parametros", "cargos"),
    "tbl_setor": ("parametros", "setores"),
    "tipos_cliente": ("parametros", "tipos_cliente"),
    "tipo_cliente_novo": ("parametros", "tipo_cliente"),
    "tipo_cliente_editar": ("parametros", "tipo_cliente"),
    "faixas_calculo_pi_lista": ("parametros", "faixas_pi"),
    "incentivos_lista": ("parametros", "incentivos"),
    "plataformas_campanha": ("parametros", "plataformas"),
    "cadu_pi_com_vendas_lista": ("parametros", "comissoes"),
    "cotacoes_list": ("parametros", "cotacoes_legado"),
    "cotacao_nova": ("parametros", "cotacao_legado"),
    "cotacao_editar": ("parametros", "cotacao_legado"),
    "cotacao_detalhes": ("parametros", "cotacao_legado"),
    "logs_auditoria": ("parametros", "auditoria"),
    "admin_migrations.page": ("parametros", "migrations"),
    "brevo_test.formulario_teste_brevo": ("parametros", "teste_brevo"),
    "parametros.lista_old_kpi": ("parametros", "kpis_legado"),
    "parametros.testes_dv": ("parametros", "testes_dv360"),
    "parametros.testes_dv_legado": ("parametros", "testes_dv360_legado"),
    "parametros.modelagem_criativos": ("parametros", "modelagem_criativos"),
    "parametros.treinamentos": ("parametros", "treinamentos"),
    "parametros.treinamentos_projetar": ("parametros", "treinamentos"),
    "parametros.treinamentos_projetar_sessao": ("parametros", "treinamentos"),
    "parametros.integracoes": ("parametros", "integracoes"),
    "parametros.monitoramento_servidor": ("parametros", "monitoramento_servidor"),
    "dv360_pages.diagnostico": ("parametros", "diagnostico_dv360"),
    "cadu_cotacoes": ("comercial", "cotacoes"),
    "cadu_cotacoes_form": ("comercial", "cotacao"),
    "notas_fiscais_lista": ("financeiro", "nf"),
    "financeiro.meus_reembolsos": ("financeiro", "reembolsos"),
    "financeiro.gestao": ("financeiro", "gestao"),
}

LEGACY_DAISY_EXCLUDED = frozenset({
    "logs_auditoria", "tbl_setor", "tbl_cargo_contato", "faixas_calculo_pi_lista",
    "incentivos_lista", "plataformas_campanha", "parametros.treinamentos",
    "parametros.integracoes", "intelligence.index", "intelligence.view",
    "parametros.lista_old_kpi", "parametros.monitoramento_servidor",
    "cadu_pi_com_vendas_lista", "brevo_test.formulario_teste_brevo",
    "brevo_test.teste_cadu_growth_emails", "parametros.testes_dv",
    "parametros.testes_dv_legado",
})

FORBIDDEN = re.compile(
    r"^(?:modal(?:-(?:box|action|backdrop|open))?|"
    r"btn(?:-(?:primary|secondary|ghost|outline|sm|xs|lg))?|"
    r"form-control|input-bordered|select-bordered|textarea-bordered|"
    r"alert(?:-(?:error|success|warning|info))?|drawer|menu|navbar|"
    r"badge(?:-(?:primary|ghost|sm|xs))?|loading(?:-(?:spinner|sm))?)$"
)
SKIP_PREFIX = ("cx-", "crm-v3-", "pi-op-", "cot-op-", "camp-")


def legacy_for_endpoint(endpoint: str) -> bool:
    module = ENDPOINT_CONTEXT.get(endpoint, ("erp",))[0]
    if module != "parametros":
        return False
    return endpoint not in LEGACY_DAISY_EXCLUDED


def daisy_tokens_in(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    found: set[str] = set()
    for match in re.finditer(r"""class\s*=\s*(['"])(.*?)\1""", text, re.DOTALL):
        for token in match.group(2).split():
            if not token or token.startswith(SKIP_PREFIX):
                continue
            if FORBIDDEN.fullmatch(token) or token in ("btn", "modal"):
                found.add(token)
    return sorted(found)


def build_endpoint_templates() -> dict[str, str]:
    """Heurística: primeiro render_template após def do endpoint."""
    mapping: dict[str, str] = {}
    fn_to_ep: dict[str, str] = {}
    for rfile in ROUTES_GLOBS:
        if not rfile.is_file():
            continue
        src = rfile.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(
            r"@\w+\.route\([^)]+\)\s*(?:\n\s*@[^\n]+)*\n\s*def\s+(\w+)\s*\(",
            src,
        ):
            fn = m.group(1)
            chunk = src[m.start() : m.start() + 800]
            ep_m = re.search(r"endpoint\s*=\s*['\"]([^'\"]+)['\"]", chunk)
            if ep_m:
                fn_to_ep[fn] = ep_m.group(1)
            else:
                fn_to_ep[fn] = fn
        for m in re.finditer(
            r"def\s+(\w+)\s*\([^)]*\):.*?render_template\s*\(\s*['\"]([^'\"]+)['\"]",
            src,
            re.DOTALL,
        ):
            fn, tpl = m.group(1), m.group(2)
            ep = fn_to_ep.get(fn, fn)
            if ep not in mapping:
                mapping[ep] = tpl
    # overrides conhecidos
    known = {
        "campanhas_pi_lista": "campanhas_pi_lista.html",
        "campanhas_pi": "campanhas_pi.html",
        "campanha_pi_detalhe": "campanha_pi_detalhe.html",
        "cadu_pi_lista": "cadu_pi.html",
        "cadu_pi_editar": "cadu_pi_form.html",
        "cadu_pi_novo": "cadu_pi_form.html",
        "diarios_campanha": "diarios_campanha.html",
        "status_campanha": "status_campanha.html",
        "link_destinos": "link_destinos.html",
        "metricas_semanais": "metricas_semanais.html",
        "clientes": "clientes.html",
        "crm_v3.crm_v3": "crm_v3.html",
        "leads_list": "cadu_leads.html",
        "briefing_list": "briefing_list.html",
        "cadu_cotacoes": "cadu_cotacoes.html",
        "cadu_cotacoes_form": "cadu_cotacoes_form.html",
        "smart_planner.index": "smart_planner/index.html",
        "places.index": "places/index.html",
        "assinaturas.mesa": "assinaturas/mesa.html",
        "parametros.modelagem_criativos": "parametros/modelagem_criativos.html",
        "parametros.treinamentos": "parametros/treinamentos.html",
        "parametros.integracoes": "parametros/integracoes.html",
        "parametros.monitoramento_servidor": "parametros/monitoramento_servidor.html",
        "parametros.testes_dv": "parametros_testes_dv.html",
        "parametros.testes_dv_legado": "parametros_testes_dv_legado.html",
        "parametros.lista_old_kpi": "parametros_lista_old_kpi.html",
        "cotacoes_list": "cadu_cotacoes_legado.html",
        "cotacao_nova": "cadu_cotacoes_form_legado.html",
        "cotacao_editar": "cadu_cotacoes_form_legado.html",
        "cotacao_detalhes": "cadu_cotacoes_detalhes_legado.html",
        "tipos_cliente": "tipo_cliente.html",
        "tipo_cliente_novo": "tipo_cliente_form.html",
        "tipo_cliente_editar": "tipo_cliente_form.html",
        "faixas_calculo_pi_lista": "faixas_calculo_pi.html",
        "incentivos_lista": "incentivos.html",
        "plataformas_campanha": "plataformas_campanha.html",
        "cadu_pi_com_vendas_lista": "cadu_pi_com_vendas.html",
        "tbl_cargo_contato": "tbl_cargo_contato.html",
        "brevo_test.formulario_teste_brevo": "teste_brevo_email.html",
        "dv360_pages.diagnostico": "dv360_diagnostico.html",
    }
    mapping.update({k: v for k, v in known.items() if k not in mapping or mapping[k] != v})
    return mapping


def url_hint(endpoint: str) -> str:
    hints = {
        "campanhas_pi_lista": "/campanhas-pi/lista",
        "campanhas_pi": "/campanhas-pi",
        "cadu_pi_lista": "/cadu-pi/lista",
        "clientes": "/clientes",
        "crm_v3.crm_v3": "/crm-v3",
        "leads_list": "/leads",
        "briefing_list": "/briefings",
        "smart_planner.index": "/smart-planner",
        "parametros.treinamentos": "/parametros/treinamentos",
        "parametros.modelagem_criativos": "/parametros/modelagem-criativos",
        "tipos_cliente": "/tipo-cliente",
        "diarios_campanha": "/campanhas-pi/<id>/diarios",
        "status_campanha": "/status-campanha",
        "link_destinos": "/link-destinos",
        "metricas_semanais": "/metricas/semanais",
        "plataformas_campanha": "/plataformas-campanha",
        "faixas_calculo_pi_lista": "/faixas-calculo-pi",
        "incentivos_lista": "/incentivos",
        "cadu_pi_editar": "/cadu-pi/<id>/editar",
        "campanha_pi_detalhe": "/campanhas-pi/<id>",
        "tipo_cliente_novo": "/tipos-cliente/novo",
        "admin_migrations.page": "/admin/migrations",
    }
    return hints.get(endpoint, "—")


def main() -> None:
    ep_tpl = build_endpoint_templates()
    modules = ("operacao", "comercial", "parametros")
    rows = []
    for ep, (mod, screen) in sorted(ENDPOINT_CONTEXT.items(), key=lambda x: (x[1][0], x[0])):
        if mod not in modules:
            continue
        tpl = ep_tpl.get(ep, "—")
        tpl_path = TEMPLATES / tpl if tpl != "—" else None
        tokens = daisy_tokens_in(tpl_path) if tpl_path else []
        legacy = legacy_for_endpoint(ep)
        if tokens:
            daisy = f"Sim ({', '.join(tokens[:6])}{'…' if len(tokens) > 6 else ''})"
        else:
            daisy = "Não" if tpl != "—" else "?"
        rows.append((mod, ep, url_hint(ep), screen, "Sim" if legacy else "Não", tpl, daisy))

    out = ROOT / "tmp" / "rota-daisy-inventario.md"
    lines = [
        "# Inventário Daisy — Operação, Comercial, Parâmetros",
        "",
        "Gerado por `tmp/rota_daisy_inventario.py`. **Legacy** = `output-legacy.css` no ERP (`base_erp.html`).",
        "",
        "| Módulo | Endpoint | URL (referência) | Tela | Legacy CSS | Template | Classes Daisy |",
        "|--------|----------|------------------|------|------------|----------|---------------|",
    ]
    for mod, ep, url, screen, legacy, tpl, daisy in rows:
        lines.append(f"| {mod} | `{ep}` | {url} | {screen} | {legacy} | `{tpl}` | {daisy} |")

    lines.extend([
        "",
        "## Legenda",
        "",
        "- **Legacy Sim (Parâmetros)**: carrega DaisyUI compilado; telas só com `cx-*` ainda herdam utilitários/base Daisy.",
        "- **Legacy Não**: Comercial/Operação no ERP — Design System Enterprise (`enterprise-system.css`).",
        "- **Classes Daisy**: tokens `btn`, `modal-box`, `form-control`, etc. no template principal (ignora prefixos `cx-`, `crm-v3-`, `pi-op-`).",
        "- **`?` template**: endpoint no mapa de contexto, template não inferido automaticamente — conferir blueprint.",
        "",
        "## Parâmetros: legacy ON vs OFF",
        "",
        "**Legacy ON** (Daisy carregado): migrations, tipos de cliente, cotações legado, modelagem criativos, KPI legado, Brevo test, etc.",
        "",
        "**Legacy OFF** (só Enterprise): auditoria, setores, cargos, faixas PI, incentivos, plataformas, comissões, treinamentos, integrações, monitoramento, testes DV360, intelligence.",
    ])
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)
    print(f"Linhas: {len(rows)}")


if __name__ == "__main__":
    main()
