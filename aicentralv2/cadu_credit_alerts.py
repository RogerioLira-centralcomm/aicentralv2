"""Avisos únicos de saldo de tokens (franquia do plano e pacotes extras).

Lê o saldo por ``cadu_plan_allowance.get_balance``. Com a franquia desligada
(CADU_PLAN_ALLOWANCE_ENABLED=0) usa o saldo total legado. Falha de e-mail
nunca reverte débito: tudo aqui é auxiliar e engole exceções.
"""
from __future__ import annotations

import logging
from typing import Optional

from flask import has_app_context

from .product_domains import product_url
from .services.cadu_product_emails import _enabled
from .services.brevo_service import get_brevo_product_service, product_email_brand

logger = logging.getLogger(__name__)

LOW_RATIO = .20
PACKAGES_PATH = "/workspace/app/creditos"
PLANS_PATH = "/workspace/app/planos"


def _fmt(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def _ratio_low(available: int, total: int) -> bool:
    return bool(total) and available / total <= LOW_RATIO


def decide_alert(balance: dict) -> Optional[dict]:
    """Escolhe no máximo um aviso (puro). A chave inclui o ciclo para renovar a cada mês."""
    franchise = balance.get("franchise") or {}
    extras = int((balance.get("extras") or {}).get("available") or 0)
    total = int(balance.get("total_available") or 0)
    cycle = franchise.get("cycle_start") or ""
    renews = franchise.get("renews_on") or ""
    plan_total = int(franchise.get("total") or 0)
    buy = ("Comprar pacote de tokens", PACKAGES_PATH)
    plan = ("Conferir meu plano", PLANS_PATH)

    if total <= 0:
        kind, title = "empty", "Seus tokens acabaram"
        desc = "Não há tokens disponíveis para novas execuções. Compre um pacote extra para continuar agora"
        desc += f" ou aguarde a renovação do plano em {renews}." if franchise.get("active") and renews else "."
        cta = buy
    elif franchise.get("active"):
        f_avail = int(franchise.get("available") or 0)
        if f_avail <= 0:
            if _ratio_low(extras, plan_total):
                kind, title, cta = "packages_low", "Seus pacotes de tokens estão acabando", buy
                desc = (f"A franquia do mês acabou e restam {_fmt(extras)} tokens nos seus pacotes extras. "
                        "Pacotes extras não expiram.")
            else:
                kind, title, cta = "franchise_empty", "A franquia de tokens do mês acabou", plan
                desc = (f"Agora o uso consome seus pacotes extras ({_fmt(extras)} tokens). "
                        f"A franquia renova em {renews}.")
        elif _ratio_low(f_avail, int(franchise.get("total") or 0)):
            kind, title, cta = "franchise_low", "A franquia de tokens do mês está baixa", plan
            desc = f"Restam {_fmt(f_avail)} tokens da franquia deste mês (renova em {renews})."
            if extras:
                desc += f" Depois disso, o uso passa para seus pacotes extras ({_fmt(extras)} tokens)."
        else:
            return None
    elif _ratio_low(total, plan_total):
        kind, title, cta = "low", "Seu saldo de tokens está baixo", buy
        desc = f"Restam {_fmt(total)} tokens compartilhados entre as ferramentas Cadu."
    else:
        return None
    return {"key": f"{kind}:{cycle}", "kind": kind, "title": title, "description": desc,
            "cta_label": cta[0], "cta_path": cta[1], "available": total}


def notify_balance(client_id: int, *, usage_id=None) -> None:
    """Persiste o aviso uma vez por (cliente, alert_key); entrega falha sem efeito no débito."""
    if not has_app_context():
        return
    try:
        from .cadu_plan_allowance import get_balance
        alert = decide_alert(get_balance(client_id))
    except Exception:
        logger.exception("Não foi possível ler o saldo de tokens para alerta de %s", client_id)
        return
    if not alert:
        return
    from .db import get_db, obter_contatos_por_cliente
    try:
        conn = get_db()
        with conn.cursor() as cur:
            # Migração opcional: sem a tabela, o alerta simplesmente não roda.
            cur.execute("SELECT to_regclass('public.cadu_credit_alerts') AS table_name")
            if not (cur.fetchone() or {}).get('table_name'):
                conn.rollback()
                return
            cur.execute("""INSERT INTO cadu_credit_alerts
                (id_cliente, alert_key, available_tokens, source_usage_id)
                VALUES (%s,%s,%s,%s) ON CONFLICT (id_cliente, alert_key) DO NOTHING
                RETURNING id""", (client_id, alert["key"], alert["available"], usage_id))
            created = cur.fetchone()
        conn.commit()
        if not created or not _enabled():
            return
        recipients = [row for row in obter_contatos_por_cliente(client_id)
                      if row.get("status") and row.get("user_type") in {"admin", "superadmin"} and row.get("email")]
        for person in recipients:
            get_brevo_product_service("workspace").enviar_email_com_template(
                template_name="produto-atividade.html", template_folder="emails/externos",
                to_email=person["email"], to_name=person.get("nome_completo") or "Administrador",
                subject=alert["title"], params={"BRAND": product_email_brand("workspace"),
                "TITLE": alert["title"], "DESCRIPTION": alert["description"],
                "CTA_LABEL": alert["cta_label"], "CTA_URL": product_url("workspace", alert["cta_path"])})
    except Exception:
        logger.exception("Não foi possível registrar alerta de tokens para %s", client_id)
