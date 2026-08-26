"""
Templates e envio de teste Brevo (sem Make.com, sem alterar listas de contatos).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

from flask import current_app, render_template

from aicentralv2.services.brevo_service import BrevoService

BREVO_TEST_TEMPLATE_LABELS: Dict[str, str] = {
    "reset-senha": "Recuperação de senha (recomendado)",
    "convite": "Convite de usuário",
    "bem-vindo": "Boas-vindas",
    "cotacao-enviada": "Cotação enviada (cliente)",
    "cotacao-aprovada-cliente": "Cotação aprovada (cliente)",
    "cotacao-rejeitada-cliente": "Cotação rejeitada (cliente)",
    "relatorio-campanha": "Relatório de campanha",
    "cotacao-recebida": "Cotação recebida (interno)",
    "novo-usuario": "Novo usuário (interno)",
}

DEFAULT_BREVO_TEST_TEMPLATE = "reset-senha"


def _agora() -> str:
    return datetime.now().strftime("%d/%m/%Y às %H:%M")


def _primeiro_nome(nome: str) -> str:
    return (nome or "Teste").strip().split(None, 1)[0]


def _params_aninhados(dados: Dict[str, Any]) -> Dict[str, Any]:
    return {"params": dados}


def build_brevo_test_templates(to_email: str, to_name: str) -> Dict[str, Dict[str, Any]]:
    primeiro = _primeiro_nome(to_name)
    link_base = "https://cadu.centralcomm.media"
    token_teste = "token-teste-brevo-001"
    numero = "COT-TEST-001"

    return {
        "convite": {
            "template_name": "convite-usuario.html",
            "template_folder": "emails/externos",
            "subject": "Você foi convidado para o Cadu por Executivo Teste",
            "params": {
                "CONVIDADO_POR": "Executivo Teste",
                "EMPRESA": "Empresa Teste Ltda",
                "ROLE_LABEL": "Usuário",
                "DIAS_VALIDADE": 7,
                "LINK_CONVITE": f"{link_base}/aceitar-convite?token={token_teste}",
                "TOKEN": token_teste,
                "EXPIRA_EM": "03/09/2026",
            },
        },
        "bem-vindo": {
            "template_name": "bem-vindo.html",
            "template_folder": "emails/externos",
            "subject": "Bem-vindo ao Cadu!",
            "params": {
                "NOME": to_name,
                "PRIMEIRO_NOME": primeiro,
                "EMAIL": to_email,
                "EMPRESA": "Empresa Teste Ltda",
                "ROLE_LABEL": "Usuário",
                "LINK_DASHBOARD": f"{link_base}/login",
                "LINK_LOGIN": f"{link_base}/login",
                "TOKEN": token_teste,
            },
        },
        "reset-senha": {
            "template_name": "reset-senha.html",
            "template_folder": "emails/externos",
            "subject": "Recuperação de Senha - Cadu",
            "params": {
                "NOME": to_name,
                "PRIMEIRO_NOME": primeiro,
                "LINK_RESET": f"{link_base}/reset-senha?token={token_teste}",
                "MINUTOS_VALIDADE": 60,
                "HORAS_VALIDADE": 1,
            },
        },
        "cotacao-enviada": {
            "template_name": "cotacao-enviada.html",
            "template_folder": "emails/externos",
            "subject": f"Sua Proposta - {numero}",
            "params": {
                "NOME": to_name,
                "PRIMEIRO_NOME": primeiro,
                "NUMERO_COTACAO": numero,
                "NOME_CAMPANHA": "Campanha Teste Verão 2026",
                "VALOR_INVESTIMENTO": "R$ 50.000,00",
                "LINK_COTACAO": f"{link_base}/cotacoes/{numero}",
                "VALIDADE": "30/09/2026",
                "EXECUTIVO_NOME": "João Executivo",
                "EXECUTIVO_EMAIL": "joao@centralcomm.media",
                "PERIODO": "01/09/2026 a 30/09/2026",
                "OBJETIVO": "Alcance e conversão",
                "AUDIENCIA_NOME": "Público 25-45 anos",
                "AUDIENCIA_CATEGORIA": "Premium",
                "PRAZO_RESPOSTA": "até 24 horas úteis",
                "DATA_ENVIO": _agora(),
                "TEM_AGENCIA": False,
                "AGENCIA_NOME": "",
                "CLIENTE_NOME": "Cliente Teste",
            },
        },
        "cotacao-aprovada-cliente": {
            "template_name": "cotacao-aprovada-cliente.html",
            "template_folder": "emails/externos",
            "subject": f"Proposta Aprovada - {numero}",
            "params": _params_aninhados(
                {
                    "NOME": to_name,
                    "PRIMEIRO_NOME": primeiro,
                    "NUMERO_COTACAO": numero,
                    "NOME_CAMPANHA": "Campanha Teste Verão 2026",
                    "VALOR_TOTAL": "R$ 50.000,00",
                    "PROXIMOS_PASSOS": "Nossa equipe entrará em contato em até 48h para iniciar a produção.",
                    "CONTATO_COMERCIAL": "João Executivo",
                    "EMAIL_COMERCIAL": "joao@centralcomm.media",
                    "DATA_APROVACAO": _agora(),
                    "LINK_PROPOSTA": f"{link_base}/cotacoes/{numero}",
                    "TEM_AGENCIA": False,
                    "AGENCIA_NOME": "",
                    "CLIENTE_NOME": "Cliente Teste",
                }
            ),
        },
        "cotacao-rejeitada-cliente": {
            "template_name": "cotacao-rejeitada-cliente.html",
            "template_folder": "emails/externos",
            "subject": f"Atualização da Proposta - {numero}",
            "params": _params_aninhados(
                {
                    "NOME": to_name,
                    "PRIMEIRO_NOME": primeiro,
                    "NUMERO_COTACAO": numero,
                    "NOME_CAMPANHA": "Campanha Teste Verão 2026",
                    "MOTIVO_REJEICAO": "Orçamento não aprovado neste ciclo.",
                    "CONTATO_COMERCIAL": "João Executivo",
                    "EMAIL_COMERCIAL": "joao@centralcomm.media",
                    "DATA_REJEICAO": _agora(),
                    "LINK_NOVA_COTACAO": f"{link_base}/cotacoes/nova",
                    "TEM_AGENCIA": False,
                    "AGENCIA_NOME": "",
                    "CLIENTE_NOME": "Cliente Teste",
                }
            ),
        },
        "relatorio-campanha": {
            "template_name": "relatorio-campanha.html",
            "template_folder": "emails/externos",
            "subject": "Relatório de Campanha - Teste Brevo",
            "params": {
                "nome_campanha": "Campanha Teste DV360",
                "cliente_nome": "Cliente Teste Ltda",
                "executivo_nome": "João Executivo",
                "plataforma_nome": "Display & Video 360",
                "objetivo_nome": "Alcance",
                "status_nome": "Em andamento",
                "periodo_inicio": "01/08/2026",
                "periodo_fim": "26/08/2026",
                "dias_campanha": 26,
                "obj_contratados": "1.000.000",
                "totalizador_atingido": "750.000",
                "pct_objetivo": 75.0,
                "valor_plataforma": "R$ 30.000,00",
                "totalizador_gasto": "R$ 22.500,00",
                "pct_investimento": 75.0,
                "mensagem_personalizada": "Este é um envio de teste via formulário (sem Make).",
                "to_name": to_name,
            },
        },
        "cotacao-recebida": {
            "template_name": "cotacao-recebida.html",
            "template_folder": "emails/internos",
            "subject": f"Nova Proposta - {numero}",
            "params": _params_aninhados(
                {
                    "DATA_HORA": _agora(),
                    "CLIENTE_NOME": to_name,
                    "CLIENTE_EMAIL": to_email,
                    "CLIENTE_EMPRESA": "Empresa Teste Ltda",
                    "NOME_CAMPANHA": "Campanha Teste Verão 2026",
                    "AUDIENCIA_NOME": "Público 25-45 anos",
                    "AUDIENCIA_CATEGORIA": "Premium",
                    "VALOR_INVESTIMENTO": "R$ 50.000,00",
                    "IMPRESSOES_ESTIMADAS": "2.500.000",
                    "PERIODO": "Set/2026",
                    "CPM_ESTIMADO": "R$ 20,00",
                    "PRACA": "Nacional",
                    "OBJETIVO": "Alcance e conversão",
                    "OBSERVACOES": "Cotação de teste enviada pelo formulário de teste Brevo.",
                    "LINK_ADMIN": f"{link_base}/admin/cotacoes/{numero}",
                }
            ),
        },
        "novo-usuario": {
            "template_name": "novo-usuario.html",
            "template_folder": "emails/internos",
            "subject": f"Novo Usuário Cadastrado - {to_name}",
            "params": _params_aninhados(
                {
                    "NOME": to_name,
                    "EMAIL": to_email,
                    "EMPRESA": "Empresa Teste Ltda",
                    "ROLE_LABEL": "Usuário",
                    "CARGO": "Analista de Mídia",
                    "TELEFONE": "(11) 99999-0000",
                    "ORIGEM_CADASTRO": "Convite",
                    "IP_CADASTRO": "127.0.0.1",
                    "DATA_CADASTRO": _agora(),
                    "LINK_ADMIN": f"{link_base}/admin/usuarios",
                }
            ),
        },
    }


def list_brevo_test_template_choices() -> List[Tuple[str, str]]:
    templates = build_brevo_test_templates("teste@example.com", "Teste")
    items = [(k, BREVO_TEST_TEMPLATE_LABELS.get(k, k)) for k in sorted(templates)]
    items.sort(key=lambda x: (0 if x[0] == DEFAULT_BREVO_TEST_TEMPLATE else 1, x[1]))
    return items


def render_brevo_test_template(cfg: Dict[str, Any]) -> str:
    template_path = f"{cfg['template_folder']}/{cfg['template_name']}"
    template_vars: Dict[str, Any] = {}
    params = cfg.get("params") or {}
    if params:
        template_vars = {k.lower(): v for k, v in params.items()}
    return render_template(template_path, **template_vars)


def run_brevo_email_test(
    template_key: str,
    to_email: str,
    to_name: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    to_email = (to_email or "").strip()
    to_name = (to_name or "Teste Brevo").strip()
    templates = build_brevo_test_templates(to_email, to_name)

    if template_key not in templates:
        return {
            "success": False,
            "error": f"Template desconhecido: {template_key}",
            "user_message": "Tipo de e-mail inválido.",
        }

    cfg = templates[template_key]
    api_key = (current_app.config.get("BREVO_API_KEY") or "").strip()
    sender_name = (current_app.config.get("BREVO_SENDER_NAME") or "Cadu").strip()
    sender_email = (
        current_app.config.get("BREVO_SENDER_EMAIL") or "contato@centralcomm.media"
    ).strip()

    meta = {
        "template_key": template_key,
        "template_name": cfg["template_name"],
        "template_folder": cfg["template_folder"],
        "subject": cfg["subject"],
        "to_email": to_email,
        "to_name": to_name,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "api_key_set": bool(api_key),
    }

    try:
        html = render_brevo_test_template(cfg)
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "user_message": f"Erro ao renderizar template: {exc}",
            **meta,
        }

    meta["preview_html"] = html[:800]

    if dry_run:
        return {"success": True, "dry_run": True, "user_message": "Pré-visualização OK (nenhum e-mail enviado).", **meta}

    if not api_key:
        return {
            "success": False,
            "error": "BREVO_API_KEY não configurada",
            "user_message": "Configure BREVO_API_KEY no .env.",
            **meta,
        }

    service = BrevoService(
        api_key=api_key,
        sender_name=sender_name,
        sender_email=sender_email,
    )
    result = service.enviar_email_com_template(
        template_name=cfg["template_name"],
        to_email=to_email,
        to_name=to_name,
        subject=cfg["subject"],
        params=cfg["params"],
        template_folder=cfg["template_folder"],
    )
    result.update(meta)
    return result
