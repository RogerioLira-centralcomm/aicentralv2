"""Contexto mínimo e não confiável da tela para o Agente CentralX."""

from flask import request


ENDPOINT_CONTEXT = {
    "index": ("geral", "inicio"),
    "crm_v3.crm_v3": ("crm", "clientes"),
    "crm_pipeline": ("comercial", "pipeline"),
    "clientes": ("crm", "clientes"),
    "leads_list": ("comercial", "leads"),
    "briefing_list": ("comercial", "briefings"),
    "cadu_pi_novo": ("comercial", "pi_recebido"),
    "cadu_pi_lista": ("operacao", "pedidos_insercao"),
    "campanhas_pi": ("operacao", "campanhas"),
    "campanhas_pi_lista": ("operacao", "acompanhamento"),
    "cadu_audiencias": ("cadu", "audiencias"),
}


def resolve_page_context():
    """Resolve módulo/tela pelo endpoint; entidades são sempre validadas pelas tools."""
    endpoint = request.endpoint or ""
    module, screen = ENDPOINT_CONTEXT.get(endpoint, ("erp", endpoint or "desconhecida"))
    if endpoint.startswith("cotacoes."):
        module, screen = "comercial", "cotacao"
    elif endpoint.startswith("financeiro."):
        module, screen = "financeiro", endpoint.split(".", 1)[-1]
    elif endpoint.startswith("crm_v3."):
        module, screen = "crm", endpoint.split(".", 1)[-1]
    return {
        "module": module,
        "screen": screen,
        "entity_type": "",
        "entity_id": "",
        "entity_label": "",
        "endpoint": endpoint,
    }
