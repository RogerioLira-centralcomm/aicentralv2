"""Série de 3 e-mails do cadastro público: boas-vindas, marca e projeto, tokens.

Cada envio é isolado: uma falha é registrada e nunca desfaz o cadastro nem
impede os demais. Convidados de uma conta existente não recebem esta série.
"""
from __future__ import annotations

import logging

from .cadu_token_emails import _first_name

logger = logging.getLogger(__name__)

SIGNUP_EVENTS = ("signup_welcome", "signup_brand_project", "signup_tokens")


def send_signup_welcome_email(*, user_email: str, user_name: str) -> dict:
    """E-mail 1: boas-vindas e visão das quatro soluções."""
    from ..product_domains import product_url
    from .brevo_service import get_brevo_product_service, product_email_brand

    brand = product_email_brand("workspace")
    return get_brevo_product_service("workspace").enviar_email_com_template(
        template_name="boas-vindas-cadastro.html", template_folder="emails/externos",
        to_email=user_email, to_name=user_name or "pessoa do time",
        subject="Boas-vindas ao Cadu",
        params={"PRIMEIRO_NOME": _first_name(user_name), "LINK_LOGIN": product_url("workspace"),
                "BRAND": brand, "ILLUSTRATION_URL": brand["illustrations_url"] + "signup-welcome.png"})


def send_signup_brand_project_email(*, user_email: str, user_name: str) -> dict:
    """E-mail 2: configurar marca e primeiro projeto (onboarding do Workspace)."""
    from ..product_domains import product_url
    from .brevo_service import get_brevo_product_service, product_email_brand

    brand = product_email_brand("workspace")
    return get_brevo_product_service("workspace").enviar_email_com_template(
        template_name="configurar-marca-projeto.html", template_folder="emails/externos",
        to_email=user_email, to_name=user_name or "pessoa do time",
        subject="Configure sua marca e seu primeiro projeto",
        params={"PRIMEIRO_NOME": _first_name(user_name),
                "ONBOARDING_URL": product_url("workspace", "/workspace/onboarding"),
                "BRAND": brand, "ILLUSTRATION_URL": brand["illustrations_url"] + "signup-brand-project.png"})


def send_signup_email_series(*, user_email: str, user_name: str, client_id=None) -> list[dict]:
    """Envia os 3 e-mails em ordem e registra cada um no ledger de envios."""
    from ..email_service import record_workspace_email_event
    from .cadu_token_emails import send_public_welcome_tokens_email

    # Sem chave global: o e-mail de boas-vindas nunca dependeu de CADU_PRODUCT_EMAILS_ENABLED
    # (send_welcome_email), e o de tokens já se desliga sozinho.
    if not user_email:
        return []
    steps = (
        ("signup_welcome", "Boas-vindas ao Cadu",
         lambda: send_signup_welcome_email(user_email=user_email, user_name=user_name)),
        ("signup_brand_project", "Configure sua marca e seu primeiro projeto",
         lambda: send_signup_brand_project_email(user_email=user_email, user_name=user_name)),
        ("signup_tokens", "Tokens inclusos no plano Free",
         lambda: send_public_welcome_tokens_email(user_email=user_email, user_name=user_name,
                                                  client_id=client_id)),
    )
    results = []
    for event_type, subject, send in steps:
        try:
            result = send() or {}
        except Exception as exc:  # um e-mail com falha não pode travar os outros
            logger.exception("E-mail de cadastro %s não enviado (cliente %s)", event_type, client_id)
            result = {"success": False, "error": str(exc)}
        record_workspace_email_event(recipient_email=user_email, event_type=event_type,
                                     subject=subject, result=result, client_id=client_id)
        results.append({"event": event_type, **{k: result.get(k) for k in ("success", "skipped") if k in result}})
    return results
