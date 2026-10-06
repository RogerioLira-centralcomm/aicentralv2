"""Solicitação de mudança de plano pelo checkout de autoatendimento (B1).

Não há cobrança automática: o checkout NÃO ativa plano nem cria fatura. Ele
registra uma solicitação (auditoria) e avisa o financeiro, que lança a fatura
e ativa o plano manualmente. Preço, limites e ``max_users`` do navegador são
ignorados; o plano é resolvido só pelo catálogo do servidor.
"""
from __future__ import annotations

import json
import logging
from html import escape
from typing import Any, Optional

from . import cadu_billing_catalog as catalog

logger = logging.getLogger(__name__)

AUDIT_MODULE = "ASSINATURAS"
AUDIT_TYPE = "plan_change_request"
DEDUP_WINDOW_HOURS = 24

BILLING_FIELDS = ("cnpj", "razao_social", "nome_fantasia", "cep", "cidade", "estado", "endereco",
                  "responsavel_nome", "email_faturamento", "telefone")


class CheckoutError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def resolve_plan(data: dict, definitions: list[dict], current_plan: Optional[dict] = None) -> dict:
    """Plano do catálogo do servidor a partir de slug, plan_type ou id da definição."""
    keys = []
    for field in ("plan_slug", "plan_type"):
        if data.get(field):
            keys.append(catalog._key(data[field]))
    plan_id = data.get("plan_id")
    if plan_id not in (None, ""):
        row = next((dict(r) for r in definitions or () if str(dict(r).get("id")) == str(plan_id)), None)
        if row:
            keys += [catalog._key(row.get(f)) for f in ("plan_type", "plan_name", "slug") if row.get(f)]
    public_slugs = {item["slug"] for item in catalog.PLAN_CATALOG}
    for plan in catalog.commercial_plans(definitions, current_plan):
        if plan["slug"] in keys and plan["slug"] in public_slugs:
            return plan
    raise CheckoutError("Plano desconhecido. Escolha um plano do catálogo atual.")


def ensure_requestable(plan: dict) -> None:
    if plan.get("current"):
        raise CheckoutError("Este já é o seu plano atual.")
    if plan.get("cta") == "contact":
        raise CheckoutError(f"O plano {plan['name']} é contratado com a equipe comercial. "
                            "Use 'Falar com a equipe'; nenhum plano foi alterado.")
    try:
        price = float(plan.get("price_monthly"))
    except (TypeError, ValueError):
        price = 0.0
    if price <= 0:
        raise CheckoutError(f"O plano {plan['name']} ainda não tem preço definido. "
                            "Fale com a equipe; nenhum plano foi alterado.")


def checkout_plans(definitions: list[dict], current_plan: Optional[dict] = None, client_id: Optional[int] = None) -> list[dict]:
    """Planos do catálogo para a página de checkout, marcando os que podem ser solicitados."""
    if current_plan is None and client_id:
        try:
            from . import db
            with db.get_db().cursor() as cursor:
                current_plan = _current_plan(cursor, int(client_id))
        except Exception:
            logger.warning("Plano atual indisponível no checkout do cliente %s", client_id, exc_info=True)
            try:
                from .db import recuperar_transacao_falha
                recuperar_transacao_falha()
            except Exception:
                pass
    public_slugs = {item["slug"] for item in catalog.PLAN_CATALOG}
    result = []
    for plan in catalog.commercial_plans(definitions, current_plan):
        if plan["slug"] not in public_slugs:
            continue
        try:
            ensure_requestable(plan)
            plan["requestable"] = True
        except CheckoutError:
            plan["requestable"] = False
        result.append(plan)
    return result


def _current_plan(cursor, client_id: int) -> Optional[dict]:
    cursor.execute("""SELECT cp.id_plan_definition, cp.plan_status, pd.plan_type, pd.plan_name AS plan_definition_name
                        FROM cadu_client_plans cp
                   LEFT JOIN cadu_plan_definitions pd ON pd.id = cp.id_plan_definition
                       WHERE cp.id_cliente = %s AND cp.plan_status = 'active'
                    ORDER BY cp.id DESC LIMIT 1""", (client_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def request_plan_change(*, user_id: int, client_id: int, data: dict, ip: str = "", user_agent: str = "") -> dict:
    """Valida e registra a solicitação numa única transação; e-mail só após o commit."""
    from . import db
    from .cadu_family import repository

    actor = repository.actor(user_id) or {}
    if int(actor.get("organization_id") or 0) != int(client_id) or repository.account_role(actor) != "admin":
        raise CheckoutError("Somente administradores da organização podem solicitar mudança de plano.", 403)
    missing = [f for f in BILLING_FIELDS if not str(data.get(f) or "").strip()]
    if missing:
        raise CheckoutError("Preencha todos os campos obrigatórios.")
    billing = {f: str(data.get(f) or "").strip()[:255] for f in BILLING_FIELDS + ("bairro",)}
    from .auth import is_reserved_org_name
    # nome_fantasia decide is_centralcomm no login: conta cliente não pode adotá-lo.
    if is_reserved_org_name(billing.get("nome_fantasia")) or is_reserved_org_name(billing.get("razao_social")):
        raise CheckoutError("Este nome de empresa é reservado. Escolha outro nome.")

    conn = db.get_db()
    try:
        with conn.cursor() as cursor:
            current = _current_plan(cursor, client_id)
            plan = resolve_plan(data, db.obter_plan_definitions(apenas_ativos=True) or [], current)
            ensure_requestable(plan)
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"cadu-plan-request:{client_id}",))
            cursor.execute(f"""SELECT id_log FROM tbl_admin_audit_log
                                WHERE modulo = %s AND registro_tipo = %s AND registro_id = %s
                                  AND dados_novos->>'plan_slug' = %s
                                  AND data_acao > NOW() - INTERVAL '{DEDUP_WINDOW_HOURS} hours'
                             ORDER BY id_log DESC LIMIT 1""",
                           (AUDIT_MODULE, AUDIT_TYPE, client_id, plan["slug"]))
            existing = cursor.fetchone()
            if existing:
                conn.rollback()
                return {"request_id": existing["id_log"], "plan": plan, "duplicate": True,
                        "notification_sent": False}
            cursor.execute("""UPDATE tbl_cliente SET cnpj=%s, razao_social=%s, nome_fantasia=%s, cep=%s,
                                     cidade=%s, logradouro=%s, bairro=%s WHERE id_cliente=%s""",
                           (billing["cnpj"], billing["razao_social"], billing["nome_fantasia"], billing["cep"],
                            billing["cidade"], billing["endereco"], billing["bairro"], client_id))
            before = {"plan_type": (current or {}).get("plan_type"),
                      "plan_name": (current or {}).get("plan_definition_name")}
            after = {"plan_slug": plan["slug"], "plan_name": plan["name"],
                     "price_monthly": plan["price_monthly"], "tokens_monthly": plan["tokens_monthly"],
                     "status": "pending_finance", "cliente_id": client_id, "billing": billing}
            cursor.execute("""INSERT INTO tbl_admin_audit_log
                                (fk_id_usuario, acao, modulo, descricao, registro_id, registro_tipo,
                                 ip_address, user_agent, dados_anteriores, dados_novos)
                              VALUES (%s,'REQUEST',%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb) RETURNING id_log""",
                           (user_id, AUDIT_MODULE,
                            f"Solicitação de plano {plan['name']} (de {before['plan_name'] or 'sem plano'})",
                            client_id, AUDIT_TYPE, (ip or "")[:45], (user_agent or "")[:255],
                            json.dumps(before), json.dumps(after)))
            request_id = cursor.fetchone()["id_log"]
        conn.commit()
    except CheckoutError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.exception("Falha ao registrar solicitação de plano do cliente %s", client_id)
        raise
    logger.info("Solicitação de plano %s: usuário %s, cliente %s, de %s para %s",
                request_id, user_id, client_id, before["plan_name"], plan["slug"])
    sent = _notify_finance(request_id, actor, client_id, plan, before, billing)
    from .services.cadu_token_emails import send_plan_request_received_email
    send_plan_request_received_email(user_email=actor.get("email") or "", user_name=actor.get("name") or "",
                                     plan_name=plan["name"], request_id=request_id)
    return {"request_id": request_id, "plan": plan, "duplicate": False, "notification_sent": sent}


def _notify_finance(request_id: int, actor: dict, client_id: int, plan: dict, before: dict, billing: dict) -> bool:
    try:
        from .email_service import send_email
        subject = f"Solicitação de plano Cadu #{request_id} · {plan['name']}"
        detail = (f"Solicitante: {actor.get('name') or '-'} ({actor.get('email') or '-'}) | Cliente: {client_id} | "
                  f"De: {before.get('plan_name') or 'sem plano'} | Para: {plan['name']} | "
                  f"R$ {float(plan['price_monthly']):.2f}/mês | CNPJ {billing['cnpj']} | "
                  f"Faturamento: {billing['email_faturamento']} | Lançar fatura e ativar manualmente.")
        return bool(send_email(subject, catalog.finance_recipients(), text_body=detail,
                               html_body=f"<p><strong>{escape(subject)}</strong></p><p>{escape(detail)}</p>"))
    except Exception:
        logger.exception("Solicitação de plano %s registrada, mas o e-mail ao financeiro falhou", request_id)
        return False
