"""Contexto mínimo e não confiável da tela para o Agente CentralX."""

from flask import request


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
    "cadu_pi_novo": ("comercial", "pi_recebido"),
    "cadu_pi_lista": ("operacao", "pedidos_insercao"),
    "campanhas_pi": ("operacao", "campanhas"),
    "campanhas_pi_lista": ("operacao", "acompanhamento"),
    "diarios_campanha": ("operacao", "diarios"),
    "status_campanha": ("operacao", "status_campanha"),
    "link_destinos": ("operacao", "links_destino"),
    "metricas_semanais": ("operacao", "metricas"),
    "cadu_audiencias": ("cadu", "audiencias"),
    "cadu_audiencia_nova": ("cadu", "audiencia"),
    "cadu_audiencia_editar": ("cadu", "audiencia"),
    "cadu_audiencia_detalhes": ("cadu", "audiencia"),
    "cadu_categorias": ("cadu", "categorias"),
    "cadu_categorias_novo": ("cadu", "categoria"),
    "cadu_categorias_editar": ("cadu", "categoria"),
    "cadu_categorias_detalhes": ("cadu", "categoria"),
    "cadu_subcategorias": ("cadu", "subcategorias"),
    "cadu_subcategorias_novo": ("cadu", "subcategoria"),
    "cadu_subcategorias_editar": ("cadu", "subcategoria"),
    "cadu_subcategorias_detalhes": ("cadu", "subcategoria"),
    "interesse_produto_listar": ("cadu", "interesses"),
    "up_audiencia": ("cadu", "upload_audiencia"),
    "admin_metrics_dashboard": ("cadu", "metricas_plataforma"),
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
    "dv360_pages.diagnostico": ("parametros", "diagnostico_dv360"),
}


def resolve_page_context():
    """Resolve módulo/tela pelo endpoint; entidades são sempre validadas pelas tools."""
    endpoint = request.endpoint or ""
    module, screen = ENDPOINT_CONTEXT.get(endpoint, ("erp", endpoint or "desconhecida"))
    if endpoint == "cadu_pi_lista":
        origem = request.args.get("origem")
        substatus = request.args.get("id_sub_status_pi")
        if origem in {"faturamento", "nf_emitida"}:
            module, screen = "financeiro", origem
        elif substatus == "2":
            module, screen = "comercial", "pi_configuracao"
        else:
            module, screen = "operacao", "pedidos_insercao"
    elif endpoint.startswith("cotacoes."):
        module, screen = "comercial", "cotacao"
    elif endpoint.startswith("financeiro."):
        module, screen = "financeiro", endpoint.split(".", 1)[-1]
    elif endpoint.startswith("crm_v3."):
        module, screen = "crm", endpoint.split(".", 1)[-1]
    elif endpoint.startswith("crm."):
        module, screen = "comercial", endpoint.split(".", 1)[-1]
    elif endpoint.startswith("whatsapp."):
        module, screen = "comercial", endpoint.split(".", 1)[-1]
    elif endpoint.startswith("intelligence."):
        module, screen = "parametros", endpoint.split(".", 1)[-1]
    return {
        "module": module,
        "screen": screen,
        "entity_type": "",
        "entity_id": "",
        "entity_label": "",
        "endpoint": endpoint,
    }
