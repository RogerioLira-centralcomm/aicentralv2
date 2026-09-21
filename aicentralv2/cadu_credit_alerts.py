"""One-shot low-balance notifications for the shared Cadu credit ledger."""
from __future__ import annotations

import logging

from flask import current_app, has_app_context

from .cadu_skills.repository import credit_position
from .product_domains import product_url
from .services.cadu_product_emails import _enabled
from .services.brevo_service import get_brevo_product_service, product_email_brand

logger = logging.getLogger(__name__)


def _level(available: int, granted: int) -> str | None:
    if available <= 0:
        return "empty"
    if granted and available / granted <= .05:
        return "critical"
    if granted and available / granted <= .20:
        return "low"
    return None


def notify_balance(client_id: int, *, usage_id=None) -> None:
    """Persist the current alert once; delivery failures never reverse a charge."""
    if not has_app_context():
        return
    position = credit_position(client_id)
    available, granted = int(position["available"]), int(position["monthly"])
    level = _level(available, granted)
    if not level:
        return
    # A new active-credit total begins a new alert cycle after a refill.
    key = f"{level}:{granted}"
    from .db import get_db, obter_contatos_por_cliente
    try:
        conn = get_db()
        with conn.cursor() as cur:
            # Alerts are auxiliary UX. The global token connector and ledger
            # must work even when this optional notification migration has not
            # been deployed yet.
            cur.execute("SELECT to_regclass('public.cadu_credit_alerts') AS table_name")
            if not (cur.fetchone() or {}).get('table_name'):
                conn.rollback()
                return
            cur.execute("""INSERT INTO cadu_credit_alerts
                (id_cliente, alert_key, available_tokens, source_usage_id)
                VALUES (%s,%s,%s,%s) ON CONFLICT (id_cliente, alert_key) DO NOTHING
                RETURNING id""", (client_id, key, available, usage_id))
            created = cur.fetchone()
        conn.commit()
        if not created or not _enabled():
            return
        recipients = [row for row in obter_contatos_por_cliente(client_id)
                      if row.get("status") and row.get("user_type") in {"admin", "superadmin"} and row.get("email")]
        title = "Seus créditos acabaram" if level == "empty" else "Seu saldo de créditos está baixo"
        description = ("Não há créditos disponíveis para novas execuções." if level == "empty"
                       else f"Restam {available:,} créditos compartilhados entre as ferramentas Cadu.")
        for person in recipients:
            get_brevo_product_service("workspace").enviar_email_com_template(
                template_name="produto-atividade.html", template_folder="emails/externos",
                to_email=person["email"], to_name=person.get("nome_completo") or "Administrador",
                subject=title, params={"BRAND": product_email_brand("workspace"), "TITLE": title,
                "DESCRIPTION": description, "CTA_LABEL": "Ver créditos", "CTA_URL": product_url("workspace", "/workspace/app/creditos")})
    except Exception:
        logger.exception("Não foi possível registrar alerta de créditos para %s", client_id)
