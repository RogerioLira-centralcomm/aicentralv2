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


def send_token_purchase_receipt_email(*, user_email: str, user_name: str, package_name: str, tokens,
                                      request_id=None, client_id=None, balance=None) -> dict:
    """Recibo ao comprador depois do commit da compra de um pacote de tokens.

    ``balance`` é o saldo disponível depois da compra; quando omitido é lido do
    saldo compartilhado do cliente. O faturamento segue manual pelo financeiro.
    """
    try:
        if not user_email or not _enabled():
            return {"success": True, "skipped": True}
        from ..product_domains import product_url
        from .cadu_email_connector import send_cadu_event

        if balance is None and client_id:
            from ..cadu_skills.repository import credit_position
            balance = (credit_position(int(client_id)) or {}).get("available")
        title = f"Recibo: {_fmt(tokens)} tokens adicionados ao seu saldo"
        description = (f"Olá, {_first_name(user_name)}. A compra do pacote {package_name} foi confirmada e os "
                       "tokens já estão disponíveis para toda a equipe. Tokens extras não expiram. "
                       "O financeiro registra a cobrança conforme a condição combinada.")
        details = [{"label": "Pedido", "value": f"nº {request_id}" if request_id else "—"},
                   {"label": "Pacote", "value": package_name},
                   {"label": "Tokens adicionados", "value": _fmt(tokens)}]
        if balance is not None:
            details.append({"label": "Saldo disponível agora", "value": f"{_fmt(balance)} tokens"})
        return send_cadu_event(
            product="workspace", event="workspace.token_purchase_receipt", template="produto-atividade.html",
            recipient=user_email, recipient_name=user_name or "pessoa do time", subject=title, client_id=client_id,
            params={"TITLE": title, "EYEBROW": "Recibo de compra", "DESCRIPTION": description, "DETAILS": details,
                    "CTA_LABEL": "Ver meu saldo", "CTA_URL": product_url("workspace", "/workspace/app/creditos")})
    except Exception:
        logger.exception("Recibo da compra de tokens %s não enviado", request_id)
        return {"success": False, "error": "token_purchase_receipt_failed"}


def client_admin_recipients(client_id) -> list[dict]:
    """Administradores ativos da conta (destinatários de avisos de plano)."""
    from ..db import get_db
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT nome_completo AS name, email FROM tbl_contato_cliente
                           WHERE pk_id_tbl_cliente=%s AND status=TRUE AND user_type IN ('admin','superadmin')
                             AND COALESCE(email,'')<>'' ORDER BY id_contato_cliente""", (int(client_id),))
        return [dict(row) for row in cursor.fetchall() or []]


def send_plan_activated_email(*, client_id, plan_definition_id=None, plan_name: str = "",
                              tokens_monthly=None, changed: bool | None = None, new_plan_id=None,
                              recipients=None) -> dict:
    """Avisa os administradores do cliente que o financeiro ativou/alterou o plano."""
    try:
        if not client_id or not _enabled():
            return {"success": True, "skipped": True}
        from ..product_domains import product_url
        from .cadu_email_connector import send_cadu_event

        if plan_definition_id and not plan_name:
            from ..db import get_db
            with get_db().cursor() as cursor:
                cursor.execute("SELECT plan_name FROM cadu_plan_definitions WHERE id=%s", (int(plan_definition_id),))
                row = cursor.fetchone() or {}
            plan_name = str(row.get("plan_name") or "")
        plan_name = plan_name or "Cadu"
        if changed is None:
            # Outro plano ativo na conta além do recém-criado = troca de plano.
            changed = False
            if new_plan_id:
                from ..db import get_db
                with get_db().cursor() as cursor:
                    cursor.execute("""SELECT 1 FROM cadu_client_plans WHERE id_cliente=%s AND id<>%s
                                       AND plan_status='active' LIMIT 1""", (int(client_id), int(new_plan_id)))
                    changed = cursor.fetchone() is not None
        people = recipients if recipients is not None else client_admin_recipients(client_id)
        people = [p for p in people if p.get("email")]
        if not people:
            return {"success": True, "skipped": True, "reason": "no_recipients"}
        title = f"Seu plano {plan_name} {'foi alterado' if changed else 'está ativo'}"
        franchise = int(tokens_monthly or 0)
        description = (f"O financeiro confirmou {'a alteração para' if changed else 'a ativação do'} plano {plan_name} "
                       "na sua conta." + (f" A franquia mensal é de {_fmt(franchise)} tokens, compartilhada pela equipe."
                                          if franchise > 0 else ""))
        details = [{"label": "Plano", "value": plan_name}]
        if franchise > 0:
            details.append({"label": "Franquia mensal", "value": f"{_fmt(franchise)} tokens"})
        results = []
        for person in people:
            results.append(send_cadu_event(
                product="workspace", event="workspace.plan_activated", template="produto-atividade.html",
                recipient=person["email"], recipient_name=person.get("name") or "Administrador", subject=title,
                client_id=int(client_id),
                params={"TITLE": title, "EYEBROW": "Plano e faturamento", "DESCRIPTION": description,
                        "DETAILS": details, "CTA_LABEL": "Conferir meu plano",
                        "CTA_URL": product_url("workspace", "/workspace/app/planos")}))
        return {"success": all(bool((r or {}).get("success")) for r in results), "sent": len(results)}
    except Exception:
        logger.exception("Aviso de plano ativado não enviado para o cliente %s", client_id)
        return {"success": False, "error": "plan_activated_email_failed"}
