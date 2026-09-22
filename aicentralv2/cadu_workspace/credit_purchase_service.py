"""Confirmed, catalog-bound extra-credit purchases for MCP agents."""

from html import escape

from flask import current_app
from werkzeug.exceptions import BadRequest, Forbidden

from ..cadu_family import repository
from ..cadu_skills.repository import credit_position
from ..db import get_db
from .agent_v2.contracts import RequestContext


EXTRA_PACKAGES = {
    "extra essencial": {"name": "Extra Essencial", "tokens": 100_000, "price_brl": 49.0},
    "extra equipe": {"name": "Extra Equipe", "tokens": 500_000, "price_brl": 179.0},
    "extra agência": {"name": "Extra Agência", "tokens": 1_000_000, "price_brl": 299.0},
}


def list_packages() -> list[dict]:
    return [dict(value) for value in EXTRA_PACKAGES.values()]


def purchase_extra(context: RequestContext, package_name: str, billing_mode: str, note: str = "") -> dict:
    actor = repository.actor(context.user_id) or {}
    if int(actor.get("organization_id") or 0) != context.client_id or repository.account_role(actor) != "admin":
        raise Forbidden("Somente administradores podem confirmar compras de créditos.")
    key = " ".join(str(package_name or "").split()).casefold().replace("agencia", "agência")
    package = EXTRA_PACKAGES.get(key)
    if not package:
        raise BadRequest("Escolha um pacote de créditos do catálogo atual.")
    if billing_mode not in {"prepaid", "postpaid"}:
        raise BadRequest("Condição de pagamento inválida.")
    note = str(note or "").strip()[:2000]
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO cadu_credit_requests
                (id_cliente, requested_by, package_name, tokens_amount, price_brl, billing_mode, note, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'approved') RETURNING id""",
                (context.client_id, context.user_id, package["name"], package["tokens"],
                 package["price_brl"], billing_mode, note))
            request_id = int(cursor.fetchone()["id"])
            cursor.execute("""INSERT INTO cadu_credits_extras
                (id_cliente, tokens_amount, tokens_used, purchase_date, expiration_date,
                 purchased_at, expires_at, status)
                VALUES (%s,%s,0,NOW(),NOW() + INTERVAL '12 months',NOW(),NOW() + INTERVAL '12 months','active')
                RETURNING id""", (context.client_id, package["tokens"]))
            lot_id = int(cursor.fetchone()["id"])
            cursor.execute("UPDATE cadu_credit_requests SET credit_lot_id=%s WHERE id=%s", (lot_id, request_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    requester = str(actor.get("name") or "Pessoa não identificada")[:160]
    email = str(actor.get("email") or "").strip()
    notification_sent = False
    try:
        from .. import db
        from ..email_service import send_email
        client = db.obter_cliente_por_id(context.client_id) or {}
        recipients = ["apolo@centralcomm.media"]
        sales = str(client.get("executivo_email") or "").strip()
        if sales and sales.lower() not in {item.lower() for item in recipients}:
            recipients.append(sales)
        subject = f"Novo pedido Cadu #{request_id} · {package['name']}"
        detail = (f"Solicitante: {requester} ({email}) | Cliente: {context.client_id} | "
                  f"{package['tokens']:,} créditos liberados | R$ {package['price_brl']:.2f} | "
                  f"Cobrança: {billing_mode} | {note}")
        finance_sent = bool(send_email(subject, recipients, text_body=detail,
                   html_body=f"<p><strong>{escape(subject)}</strong></p><p>{escape(detail)}</p>"))
        buyer_sent = True
        if email and email.lower() != "apolo@centralcomm.media":
            buyer_sent = bool(send_email(f"Compra confirmada no Cadu #{request_id}", [email], text_body=detail,
                       html_body=f"<p>Compra confirmada.</p><p>{escape(detail)}</p>"))
        notification_sent = finance_sent and buyer_sent
        if not notification_sent:
            current_app.logger.warning("Compra %s confirmada; falha no envio de uma ou mais notificações", request_id)
    except Exception:
        current_app.logger.exception("Compra %s confirmada, mas o e-mail não foi enviado", request_id)
    return {"request_id":request_id, "credit_lot_id":lot_id, "requester_name":requester,
            "package":package, "billing_mode":billing_mode, "credits_released":package["tokens"],
            "notification_sent":notification_sent, "balance":credit_position(context.client_id)}
