"""Persistência da gestão, métricas e créditos do Cadu Skills."""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from .credits import balance_from_ledger


EVENT_TYPES = {"view", "copy", "install", "run_started", "run_succeeded", "run_failed"}


class CaduCreditUnavailable(ValueError):
    """A client has no available Cadu credits for an owned operation."""


def _db():
    from ..db import get_db
    return get_db()


def actor_key(value: str) -> str:
    return hashlib.sha256(str(value or "anonymous").encode("utf-8")).hexdigest()[:32]


def record_event(slug: str, event_type: str, *, actor: str = "", user_id=None, metadata=None) -> bool:
    if event_type not in EVENT_TYPES:
        return False
    try:
        conn = _db()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cadu_skill_events (skill_id, event_type, actor_key, user_id, metadata)
                SELECT id, %s, %s, %s, %s::jsonb FROM cadu_skill_definitions WHERE slug = %s
                """,
                (event_type, actor_key(actor), user_id, json.dumps(metadata or {}), slug),
            )
        conn.commit()
        return True
    except Exception:
        return False


def metrics_by_slug() -> dict:
    try:
        conn = _db()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.slug,
                       COUNT(*) FILTER (WHERE e.event_type = 'view') AS views,
                       COUNT(*) FILTER (WHERE e.event_type = 'copy') AS copies,
                       COUNT(*) FILTER (WHERE e.event_type = 'install') AS installs,
                       COUNT(*) FILTER (WHERE e.event_type = 'run_succeeded') AS runs
                  FROM cadu_skill_definitions d
             LEFT JOIN cadu_skill_events e ON e.skill_id = d.id
              GROUP BY d.id, d.slug
                """
            )
            return {row["slug"]: dict(row) for row in cursor.fetchall()}
    except Exception:
        return {}


def managed_skills(catalog) -> list[dict]:
    metrics = metrics_by_slug()
    overrides = {}
    try:
        conn = _db()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.slug, d.name, d.summary, d.category, d.image_url, d.display_rank,
                       d.status, d.is_testable, v.model, v.credit_cost, v.instructions
                  FROM cadu_skill_definitions d
             LEFT JOIN LATERAL (
                       SELECT * FROM cadu_skill_versions
                        WHERE skill_id = d.id ORDER BY version DESC LIMIT 1
                       ) v ON TRUE
                 WHERE d.owner_type = 'centralx'
                """
            )
            overrides = {row["slug"]: dict(row) for row in cursor.fetchall()}
    except Exception:
        pass
    rows = []
    for source in catalog:
        item = {**source, **{
            k: v for k, v in overrides.get(source["slug"], {}).items()
            if v is not None and not (k in {"instructions", "image_url", "model"} and v == "")
        }}
        item.update(metrics.get(source["slug"], {}))
        for key in ("views", "copies", "installs", "runs"):
            item[key] = int(item.get(key) or 0)
        item["engagements"] = item["views"] + item["copies"] + item["installs"] + item["runs"]
        rows.append(item)
    return sorted(rows, key=lambda item: (int(item.get("display_rank") or item.get("rank") or 999), item["name"]))


def all_owned_skills(catalog) -> list[dict]:
    """Return every published public Cadu-owned skill, with the curated catalog as fallback."""
    curated = managed_skills(catalog)
    by_slug = {item["slug"]: item for item in curated}
    metrics = metrics_by_slug()
    try:
        conn = _db()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.slug, d.name, d.summary, d.category, d.image_url, d.display_rank,
                       d.status, d.visibility, v.model, v.credit_cost, v.instructions
                  FROM cadu_skill_definitions d
             LEFT JOIN LATERAL (
                       SELECT * FROM cadu_skill_versions
                        WHERE skill_id = d.id ORDER BY version DESC LIMIT 1
                       ) v ON TRUE
                 WHERE d.owner_type = 'centralx' AND d.status = 'published'
                   AND d.visibility = 'public'
                """
            )
            database_rows = [dict(row) for row in cursor.fetchall()]
    except Exception:
        database_rows = []
    for row in database_rows:
        existing = by_slug.get(row["slug"], {})
        instructions = str(row.get("instructions") or existing.get("instructions") or "").strip()
        if not instructions:
            continue
        item = {
            **existing, **row,
            "description": row.get("summary") or existing.get("description") or "",
            "image_url": row.get("image_url") or existing.get("image_url") or "/static/images/cadu/products/skills.png",
            "model": row.get("model") or existing.get("model") or "openai/gpt-4o-mini",
            "credit_cost": int(row.get("credit_cost") or existing.get("credit_cost") or 1),
            "instructions": instructions,
            "prompts": existing.get("prompts") or ("Descreva uma tarefa real para esta skill.",),
            "is_testable": True,
        }
        item.update(metrics.get(row["slug"], {}))
        for key in ("views", "copies", "installs", "runs"):
            item[key] = int(item.get(key) or 0)
        item["engagements"] = item["views"] + item["copies"] + item["installs"] + item["runs"]
        by_slug[row["slug"]] = item
    return sorted(by_slug.values(), key=lambda item: (int(item.get("display_rank") or item.get("rank") or 999), item["name"]))


def list_customizations(*, client_id=None) -> list[dict]:
    try:
        conn = _db()
        query = """
            SELECT c.id, c.name, c.summary, c.image_url, c.client_id, c.brand_id, c.project_id,
                   c.status, c.context_json, c.instructions, c.created_at, c.updated_at,
                   d.slug AS base_slug, d.name AS base_name, d.category,
                   v.model, v.credit_cost, cli.nome_fantasia AS client_name,
                   p.nome AS project_name,
                   COUNT(DISTINCT r.id) AS run_count,
                   COUNT(DISTINCT s.id) FILTER (WHERE s.revoked_at IS NULL) AS active_links
              FROM cadu_skill_customizations c
              JOIN cadu_skill_versions v ON v.id = c.skill_version_id
              JOIN cadu_skill_definitions d ON d.id = v.skill_id
         LEFT JOIN tbl_cliente cli ON cli.id_cliente = c.client_id
         LEFT JOIN cadu_projetos p ON p.id = c.project_id
         LEFT JOIN cadu_skill_runs r ON r.customization_id = c.id
         LEFT JOIN cadu_skill_shares s ON s.customization_id = c.id
             WHERE (%s IS NULL OR c.client_id = %s)
          GROUP BY c.id, d.slug, d.name, d.category, v.model, v.credit_cost,
                   cli.nome_fantasia, p.nome
          ORDER BY c.updated_at DESC, c.id DESC
        """
        with conn.cursor() as cursor:
            cursor.execute(query, (client_id, client_id))
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


def get_customization(customization_id: int, *, client_id=None):
    return next((row for row in list_customizations(client_id=client_id) if int(row["id"]) == int(customization_id)), None)


def customization_targets() -> dict:
    try:
        conn = _db()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id_cliente AS id, nome_fantasia AS name FROM tbl_cliente ORDER BY nome_fantasia")
            clients = [dict(row) for row in cursor.fetchall()]
            cursor.execute("SELECT id, id_cliente AS client_id, nome AS name FROM cadu_projetos ORDER BY nome")
            projects = [dict(row) for row in cursor.fetchall()]
        return {"clients": clients, "projects": projects}
    except Exception:
        return {"clients": [], "projects": []}


def update_customization_links(customization_id: int, *, client_id: int, project_id=None, brand_id=None) -> bool:
    conn = _db()
    try:
        with conn.cursor() as cursor:
            if project_id:
                cursor.execute("SELECT 1 FROM cadu_projetos WHERE id = %s AND id_cliente = %s", (project_id, client_id))
                if not cursor.fetchone():
                    raise ValueError("O projeto selecionado não pertence ao cliente informado.")
            cursor.execute(
                """UPDATE cadu_skill_customizations
                      SET client_id = %s, project_id = %s, brand_id = %s, updated_at = NOW()
                    WHERE id = %s RETURNING id""",
                (client_id, project_id, brand_id, customization_id),
            )
            updated = cursor.fetchone()
        conn.commit()
        return bool(updated)
    except Exception:
        conn.rollback()
        raise


def customization_as_skill(row: dict, fallback: dict) -> dict:
    context = row.get("context_json") if isinstance(row.get("context_json"), dict) else {}
    context_text = json.dumps(context, ensure_ascii=False, indent=2) if context else "Nenhum contexto adicional."
    instructions = str(row.get("instructions") or "").strip() or str(fallback.get("instructions") or "")
    summary = row.get("custom_summary") or row.get("summary") or fallback["summary"]
    return {
        **fallback,
        "name": row.get("name") or fallback["name"],
        "summary": summary,
        "description": summary or fallback.get("description") or fallback["summary"],
        "image_url": row.get("image_url") or fallback.get("image_url"),
        "model": row.get("model") or fallback["model"],
        "credit_cost": int(row.get("credit_cost") or fallback["credit_cost"]),
        "instructions": f"{instructions}\n\nCONTEXTO PERSONALIZADO\n{context_text}",
        "customization_id": int(row["id"]),
        "client_id": int(row["client_id"]),
    }


def create_share(customization_id: int, *, user_id: int, permission="view") -> str:
    permission = permission if permission in {"view", "run"} else "view"
    token = secrets.token_urlsafe(32)
    conn = _db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cadu_skill_shares
                    (customization_id, token_hash, permission, created_by)
                VALUES (%s, %s, %s, %s)
                """,
                (customization_id, hashlib.sha256(token.encode("utf-8")).hexdigest(), permission, user_id),
            )
        conn.commit()
        return token
    except Exception:
        conn.rollback()
        raise


def revoke_shares(customization_id: int) -> int:
    conn = _db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_skill_shares SET revoked_at = NOW()
                    WHERE customization_id = %s AND revoked_at IS NULL""",
                (customization_id,),
            )
            count = cursor.rowcount
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise


def customization_markdown(row: dict, skill: dict) -> str:
    context = row.get("context_json") if isinstance(row.get("context_json"), dict) else {}
    lines = [
        "---", f"name: {row.get('name') or skill['name']}",
        f"description: {row.get('summary') or skill['summary']}",
        f"model: {row.get('model') or skill['model']}",
        f"credit_cost: {int(row.get('credit_cost') or skill['credit_cost'])}", "---", "",
        "# Instruções", "", str(row.get("instructions") or skill.get("instructions") or "").strip(),
        "", "# Contexto vinculado", "", "```json", json.dumps(context, ensure_ascii=False, indent=2), "```", "",
        f"Cliente: {row.get('client_name') or row.get('client_id')}",
        f"Projeto: {row.get('project_name') or row.get('project_id') or 'Não vinculado'}", "",
    ]
    return "\n".join(lines)


def update_managed_skill(slug: str, payload: dict, user_id: int) -> bool:
    conn = _db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE cadu_skill_definitions
                   SET name = %s, summary = %s, category = %s, image_url = %s,
                       display_rank = %s, status = %s, is_testable = %s,
                       updated_at = NOW()
                 WHERE slug = %s AND owner_type = 'centralx'
             RETURNING id
                """,
                (
                    payload["name"], payload["summary"], payload["category"], payload.get("image_url") or None,
                    payload["display_rank"], payload["status"], payload["is_testable"], slug,
                ),
            )
            row = cursor.fetchone()
            if not row:
                return False
            cursor.execute(
                """
                UPDATE cadu_skill_versions
                   SET model = %s, credit_cost = %s, instructions = %s
                 WHERE id = (SELECT id FROM cadu_skill_versions WHERE skill_id = %s ORDER BY version DESC LIMIT 1)
                """,
                (payload["model"], payload["credit_cost"], payload["instructions"], row["id"]),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def credit_position(client_id: int) -> dict:
    """Saldo compartilhado de tokens exibido nos shells CADU.

    O Chat de Famílias e as ferramentas internas consomem os mesmos lotes em
    ``cadu_credits_extras``; a navegação não deve mais exibir a franquia
    legada de imagens do plano.
    """
    try:
        conn = _db()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(tokens_amount), 0) AS granted,
                       COALESCE(SUM(tokens_used), 0) AS used,
                       COALESCE(SUM(tokens_amount - tokens_used), 0) AS available
                  FROM cadu_credits_extras
                 WHERE id_cliente = %s
                   AND status = 'active'
                   AND (expires_at IS NULL OR expires_at > NOW())
                """,
                (client_id,),
            )
            lots = cursor.fetchone() or {}
            cursor.execute(
                "SELECT 1 FROM cadu_client_plans WHERE id_cliente = %s AND plan_status = 'active' LIMIT 1",
                (client_id,),
            )
            configured = bool(cursor.fetchone()) or bool(lots.get('granted'))
            cursor.execute("""SELECT COALESCE(pd.tokens_monthly_limit, p.tokens_monthly_limit, 0) AS monthly_limit,
                                     COALESCE(p.tokens_used_current_month, 0) AS monthly_used
                                FROM cadu_client_plans p LEFT JOIN cadu_plan_definitions pd ON pd.id = p.id_plan_definition
                               WHERE p.id_cliente = %s AND p.plan_status = 'active' ORDER BY p.created_at DESC LIMIT 1""", (client_id,))
            plan_usage = cursor.fetchone() or {}
            monthly_limit = max(0, int(plan_usage.get("monthly_limit") or 0))
            monthly_used = max(0, int(plan_usage.get("monthly_used") or 0))
            lot_granted = max(0, int(lots.get("granted") or 0))
            lot_used = max(0, int(lots.get("used") or 0))
            return {
                "available": max(0, int(lots.get("available") or 0)),
                # Kept for existing shells; this is the total of active credit
                # lots, not a monthly plan allowance.
                "monthly": lot_granted,
                "configured": configured,
                "monthly_limit": monthly_limit,
                "monthly_used": monthly_used,
                # Workspace usage is shared across Cadu products and must use
                # active credit lots, not the legacy plan allowance.
                "monthly_usage_percentage": round(min(100, (lot_used * 100) / lot_granted), 1) if lot_granted else 0,
            }
    except Exception:
        return {"available": 0, "monthly": 0, "configured": False, "monthly_limit": 0, "monthly_used": 0, "monthly_usage_percentage": 0}


def charge_project_rag(cursor, *, client_id: int, user_id: int, project_id: str,
                       tokens: int, stage: str, idempotency_key: str) -> int:
    """Debit the client's Cadu credit lots inside the caller transaction.

    Workspace source ingestion is local PostgreSQL RAG work, not a Dify tool.
    Locking the lots with the source/chunk inserts makes insufficient balance
    fail before a project gains searchable material, and a later error rolls
    the debit back with the indexing transaction.
    """
    raw_tokens = max(1, int(tokens or 0))
    # The displayed and debited amount has a small operating margin, while
    # still remaining directly proportional to the source actually processed.
    # A deployment may tune this without changing code; invalid values fall
    # back to the 20% default.
    try:
        margin = float(os.getenv('CADU_PROJECT_RAG_TOKEN_MARGIN', '1.20'))
    except (TypeError, ValueError):
        margin = 1.20
    margin = min(2.0, max(1.0, margin))
    tokens = max(1, math.ceil(raw_tokens * margin))
    if not idempotency_key or len(idempotency_key) > 160:
        raise ValueError('Identificador inválido para cobrança de RAG.')
    cursor.execute(
        '''SELECT id, tokens_amount, tokens_used
             FROM cadu_credits_extras
            WHERE id_cliente = %s AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
              AND tokens_used < tokens_amount
         ORDER BY COALESCE(expires_at, 'infinity'::timestamptz), purchased_at, id FOR UPDATE''',
        (client_id,),
    )
    lots = [dict(row) for row in cursor.fetchall()]
    available = sum(max(0, int(row.get('tokens_amount') or 0) - int(row.get('tokens_used') or 0)) for row in lots)
    if available < tokens:
        raise CaduCreditUnavailable('Saldo Cadu insuficiente para indexar esta fonte no projeto.')
    remaining = tokens
    for lot in lots:
        spend = min(remaining, max(0, int(lot.get('tokens_amount') or 0) - int(lot.get('tokens_used') or 0)))
        if not spend:
            continue
        cursor.execute('''UPDATE cadu_credits_extras SET tokens_used = tokens_used + %s
                           WHERE id = %s AND id_cliente = %s''', (spend, lot['id'], client_id))
        remaining -= spend
        if not remaining:
            break
    cursor.execute(
        '''INSERT INTO cadu_tools_token_usage
               (idempotency_key, id_cliente, id_contato_cliente, ferramenta, etapa, modelo,
                tokens_entrada, tokens_saida, total_tokens, tokens_cobrados, metadata, status, charged_at)
           VALUES (%s, %s, %s, 'workspace_rag', %s, 'postgres-text', %s, 0, %s, %s,
                   %s::jsonb, 'charged', NOW())''',
        (idempotency_key, client_id, user_id, stage, tokens, tokens, tokens,
         json.dumps({'projeto_id': str(project_id), 'rag': 'postgresql',
                     'tokens_processados': raw_tokens, 'multiplicador': margin})),
    )
    return tokens


def reserve_run(skill: dict, *, client_id: int, user_id: int, prompt: str, customization_id=None) -> dict:
    """Reserva créditos e cria o run na mesma transação."""
    conn = _db()
    cost = max(1, int(skill.get("credit_cost") or 1))
    key = uuid4().hex
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id,
                       COALESCE(pd.limit_image_generation, p.image_credits_monthly, 0) AS monthly_limit
                  FROM cadu_client_plans p
             LEFT JOIN cadu_plan_definitions pd ON pd.id = p.id_plan_definition
                 WHERE p.id_cliente = %s AND p.plan_status = 'active'
              ORDER BY p.created_at DESC LIMIT 1 FOR UPDATE OF p
                """,
                (client_id,),
            )
            plan = cursor.fetchone()
            if not plan:
                raise ValueError("Nenhum plano Cadu ativo foi encontrado.")
            month = datetime.now(timezone.utc).strftime("%Y-%m")
            cursor.execute(
                """
                INSERT INTO cadu_credit_ledger (client_plan_id, kind, amount, idempotency_key, metadata)
                VALUES (%s, 'monthly_grant', %s, %s, %s::jsonb)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (plan["id"], int(plan["monthly_limit"] or 0), f"skills-grant:{plan['id']}:{month}", json.dumps({"month": month})),
            )
            cursor.execute(
                """SELECT kind, amount FROM cadu_credit_ledger
                    WHERE client_plan_id = %s
                      AND created_at >= DATE_TRUNC('month', CURRENT_TIMESTAMP)
                      AND created_at < DATE_TRUNC('month', CURRENT_TIMESTAMP) + INTERVAL '1 month'""",
                (plan["id"],),
            )
            balance = balance_from_ledger(cursor.fetchall())
            if not balance.can_reserve(cost):
                raise ValueError(f"Saldo insuficiente. Esta skill usa {cost} créditos e há {balance.available} disponíveis.")
            cursor.execute(
                """
                INSERT INTO cadu_skill_runs
                    (customization_id, skill_version_id, client_plan_id, user_id, model, status, input_json)
                SELECT %s, v.id, %s, %s, %s, 'reserved', %s::jsonb
                  FROM cadu_skill_versions v JOIN cadu_skill_definitions d ON d.id = v.skill_id
                 WHERE d.slug = %s ORDER BY v.version DESC LIMIT 1 RETURNING id
                """,
                (customization_id, plan["id"], user_id, skill["model"], json.dumps({"prompt": prompt}), skill["slug"]),
            )
            run = cursor.fetchone()
            if not run:
                raise ValueError("A versão executável desta skill ainda não foi publicada.")
            cursor.execute(
                """INSERT INTO cadu_credit_ledger
                    (client_plan_id, run_id, kind, amount, idempotency_key, metadata)
                    VALUES (%s, %s, 'reserve', %s, %s, '{}'::jsonb)""",
                (plan["id"], run["id"], -cost, f"skills-reserve:{key}"),
            )
        conn.commit()
        return {"run_id": run["id"], "plan_id": plan["id"], "cost": cost, "key": key, "balance_before": balance.available}
    except Exception:
        conn.rollback()
        raise


def finish_run(reservation: dict, *, success: bool, result=None, error_code="") -> None:
    conn = _db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_credit_ledger
                    (client_plan_id, run_id, kind, amount, idempotency_key, metadata)
                    VALUES (%s, %s, 'release', %s, %s, '{}'::jsonb)""",
                (reservation["plan_id"], reservation["run_id"], reservation["cost"], f"skills-release:{reservation['key']}"),
            )
            if success:
                cursor.execute(
                    """INSERT INTO cadu_credit_ledger
                        (client_plan_id, run_id, kind, amount, idempotency_key, metadata)
                        VALUES (%s, %s, 'capture', %s, %s, '{}'::jsonb)""",
                    (reservation["plan_id"], reservation["run_id"], -reservation["cost"], f"skills-capture:{reservation['key']}"),
                )
            cursor.execute(
                """
                UPDATE cadu_skill_runs SET status = %s, output_json = %s::jsonb,
                       provider_usage = %s::jsonb, error_code = %s, completed_at = NOW()
                 WHERE id = %s
                """,
                (
                    "succeeded" if success else "failed",
                    json.dumps({"answer": (result or {}).get("answer")}) if success else None,
                    json.dumps((result or {}).get("usage") or {}), error_code or None, reservation["run_id"],
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
