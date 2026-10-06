"""E-mails ao cliente sobre tokens: boas-vindas da conta pública e pedido de plano.

Auxiliares: nunca levantam exceção nem desfazem cadastro/pedido.
"""
from __future__ import annotations

import logging

from .cadu_product_emails import _enabled

logger = logging.getLogger(__name__)


def _fmt(value) -> str:
    return f"{int(value or 0):,}".replace(",", ".")


def _first_name(name) -> str:
    return (str(name or "").split() or ["pessoa do time"])[0]


def send_public_welcome_tokens_email(*, user_email: str, user_name: str, client_id=None) -> dict:
    """Saldo inicial da conta pública: tokens de boas-vindas + franquia do plano Free."""
    try:
        if not user_email or not _enabled():
            return {"success": True, "skipped": True}
        from ..cadu_billing_catalog import FREE_PLAN, welcome_tokens
        from ..cadu_plan_allowance import allowance_enabled
        from ..product_domains import product_url
        from .brevo_service import get_brevo_product_service, product_email_brand

        welcome = welcome_tokens()
        if welcome <= 0:
            return {"success": True, "skipped": True}
        brand = product_email_brand("workspace")
        # Franquia só é anunciada quando realmente liberada (flag do plano ligada).
        plan_tokens = _fmt(FREE_PLAN["tokens_monthly"]) if allowance_enabled() else ""
        return get_brevo_product_service("workspace").enviar_email_com_template(
            template_name="bonus-creditos.html", template_folder="emails/externos",
            to_email=user_email, to_name=user_name or "pessoa do time",
            subject=f"{_fmt(welcome)} tokens para começar no Cadu",
            params={"PRIMEIRO_NOME": _first_name(user_name), "EMPRESA": user_name or "sua equipe",
                    "WELCOME_TOKENS": _fmt(welcome), "PLAN_NAME": FREE_PLAN["name"], "PLAN_TOKENS": plan_tokens,
                    "CREDITS_URL": product_url("workspace", "/workspace/app/creditos"), "BRAND": brand,
                    "ILLUSTRATION_URL": brand["illustrations_url"] + "credits.png"})
    except Exception:
        logger.exception("Boas-vindas com tokens não enviadas para o cliente %s", client_id)
        return {"success": False, "error": "welcome_tokens_email_failed"}


def send_plan_request_received_email(*, user_email: str, user_name: str, plan_name: str, request_id=None) -> dict:
    """Confirma ao cliente que o pedido de plano chegou; faturamento é manual."""
    try:
        if not user_email or not _enabled():
            return {"success": True, "skipped": True}
        from ..product_domains import product_url
        from .brevo_service import get_brevo_product_service, product_email_brand

        title = f"Recebemos seu pedido do plano {plan_name}"
        description = (f"Olá, {_first_name(user_name)}. Registramos seu pedido do plano {plan_name}"
                       f"{f' (nº {request_id})' if request_id else ''}. Nosso financeiro entra em contato para "
                       "confirmar os dados e combinar o faturamento. Nada é cobrado automaticamente; "
                       "o plano é ativado depois dessa confirmação.")
        return get_brevo_product_service("workspace").enviar_email_com_template(
            template_name="produto-atividade.html", template_folder="emails/externos",
            to_email=user_email, to_name=user_name or "Administrador", subject=title,
            params={"BRAND": product_email_brand("workspace"), "TITLE": title, "DESCRIPTION": description,
                    "CTA_LABEL": "Conferir meu plano", "CTA_URL": product_url("workspace", "/workspace/app/planos")})
    except Exception:
        logger.exception("Confirmação do pedido de plano %s não enviada", request_id)
        return {"success": False, "error": "plan_request_email_failed"}
