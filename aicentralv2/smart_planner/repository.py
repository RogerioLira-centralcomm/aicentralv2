"""Persistência em cadu_smart_planner_sessions (mesma base do PHP)."""

from __future__ import annotations

import logging
import secrets
from typing import Any, Optional

from psycopg.types.json import Json

from ..db import get_db
from .catalog import CHANNEL_CATALOG, PRACA_OPTIONS, objetivo_label, plan_mode_label, resume_action
from .helpers import as_dict, as_list, campaign_from_campos, format_when, plan_href, plan_mode_of, session_title, text

logger = logging.getLogger(__name__)

JSON_COLS = {"analise_ia", "dados_detectados", "plataformas_sugeridas", "audiencias_sugeridas", "plan_content", "canvas_layout"}
UPDATE_COLS = {
    "visitor_id", "user_id", "user_email", "user_name", "auth_method",
    "input_type", "input_url", "input_file_path", "input_text_original",
    "briefing_compilado", "briefing_melhorado", "analise_ia", "quality_score",
    "dados_detectados", "publico_alvo", "objetivo", "budget", "prazo",
    "plataformas_sugeridas", "acao_final", "nome_campanha", "cliente",
    "audiencias_sugeridas", "plan_content", "canvas_layout", "schema_version",
}


class SmartPlannerError(RuntimeError):
    pass


class SessionNotFound(SmartPlannerError):
    pass


def count_sessions() -> int:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM cadu_smart_planner_sessions")
        row = cur.fetchone() or {}
    return int(row.get("n") or 0)


def get_by_token(token: str) -> Optional[dict]:
    token = (token or "").strip()
    if not token:
        return None
    conn = get_db()
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                SELECT *
                FROM cadu_smart_planner_sessions
                WHERE session_token = %s AND deleted_at IS NULL
                LIMIT 1
                """,
                (token,),
            )
            return cur.fetchone()
        except Exception:
            conn.rollback()
            cur.execute(
                "SELECT * FROM cadu_smart_planner_sessions WHERE session_token = %s LIMIT 1",
                (token,),
            )
            return cur.fetchone()


def get_by_public_token(public_token: str) -> Optional[dict]:
    token = (public_token or "").strip()
    if not token:
        return None
    conn = get_db()
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                SELECT *
                FROM cadu_smart_planner_sessions
                WHERE deleted_at IS NULL
                  AND dados_detectados->>'public_token' = %s
                LIMIT 1
                """,
                (token,),
            )
            return cur.fetchone()
        except Exception:
            conn.rollback()
            cur.execute(
                """
                SELECT *
                FROM cadu_smart_planner_sessions
                WHERE dados_detectados->>'public_token' = %s
                LIMIT 1
                """,
                (token,),
            )
            return cur.fetchone()


def get_owned(token: str, user_email: str, user_id: Any) -> dict:
    row = get_by_token(token)
    if not row:
        raise SessionNotFound("Plano não encontrado.")
    email = (user_email or "").strip().lower()
    row_email = text(row.get("user_email")).lower()
    if email and row_email and email != row_email:
        raise SessionNotFound("Você não tem acesso a este plano.")
    if not row_email and user_id and row.get("user_id") not in (None, user_id, str(user_id)):
        raise SessionNotFound("Você não tem acesso a este plano.")
    return row


def list_sessions(user_email: str, user_id: Any = None, limit: int = 80) -> list[dict]:
    email = (user_email or "").strip().lower()
    clauses = ["deleted_at IS NULL"]
    params: list[Any] = []
    if email:
        clauses.append("LOWER(user_email) = %s")
        params.append(email)
    elif user_id:
        clauses.append("user_id = %s")
        params.append(user_id)
    else:
        return []
    params.append(max(1, min(200, int(limit))))
    sql = f"""
            SELECT id, session_token, briefing_melhorado, briefing_compilado,
                   dados_detectados, plan_content, objetivo, budget, prazo,
                   quality_score, created_at, updated_at, nome_campanha, cliente
            FROM cadu_smart_planner_sessions
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT %s
            """
    fallback = sql.replace("plan_content, ", "").replace("deleted_at IS NULL", "TRUE")
    conn = get_db()
    with conn.cursor() as cur:
        try:
            cur.execute(sql, params)
            rows = cur.fetchall() or []
        except Exception:
            conn.rollback()
            cur.execute(fallback, params)
            rows = cur.fetchall() or []
    out = []
    for row in rows:
        try:
            out.append(serialize_list_row(row))
        except Exception:
            logger.exception("Falha ao serializar planejamento %s", (row or {}).get("id"))
            token = text((row or {}).get("session_token"))
            out.append({
                "id": (row or {}).get("id"),
                "session_token": token,
                "titulo": session_title(row or {}, {}),
                "cliente": "",
                "objetivo": "",
                "verba": "",
                "praca": "",
                "periodo": "",
                "canais": [],
                "plan_mode": "completo",
                "plan_mode_label": plan_mode_label("completo"),
                "tem_planejamento": False,
                "tem_quadro": False,
                "tem_briefing": False,
                "quando": "",
                "updated_at": None,
                "resume_step": "briefing",
                "resume_action": resume_action("briefing"),
                "href": plan_href(token, "briefing"),
                "canvas_href": plan_href(token, "canvas") if token else "",
            })
    return out


def serialize_list_row(row: dict) -> dict:
    dados = as_dict(row.get("dados_detectados"))
    campanha = dados.get("campanha") if isinstance(dados.get("campanha"), dict) else {}
    canais_keys = [key for key in as_list(campanha.get("canais") or dados.get("canais")) if text(key)]
    canais = [CHANNEL_CATALOG.get(key, {}).get("label", key) for key in canais_keys]
    praca_key = text(campanha.get("praca") or dados.get("praca"))
    plan = as_dict(row.get("plan_content"))
    has_canvas = bool(as_list(plan.get("sections")))
    has_plan_text = bool(text(dados.get("planejamento")))
    has_briefing = bool(text(row.get("briefing_melhorado") or row.get("briefing_compilado")))
    has_mix = bool(canais_keys or text(row.get("budget") or campanha.get("verba") or dados.get("verba")))
    mode = plan_mode_of(dados)
    token = text(row.get("session_token"))
    if has_canvas:
        resume = "canvas"
    elif has_plan_text or (has_briefing and has_mix):
        resume = "gerar"
    elif has_briefing:
        resume = "revisao"
    else:
        resume = "briefing"
    return {
        "id": row.get("id"),
        "session_token": token,
        "titulo": session_title(row, dados),
        "cliente": text(row.get("cliente") or dados.get("cliente")),
        "objetivo": objetivo_label(text(row.get("objetivo") or dados.get("objetivo") or campanha.get("objetivo"))),
        "verba": text(row.get("budget") or campanha.get("verba") or dados.get("verba")),
        "praca": PRACA_OPTIONS.get(praca_key, {}).get("label", praca_key),
        "periodo": text(row.get("prazo") or campanha.get("periodo") or dados.get("periodo")),
        "canais": canais,
        "plan_mode": mode,
        "plan_mode_label": plan_mode_label(mode),
        "tem_planejamento": has_plan_text or has_canvas,
        "tem_quadro": has_canvas,
        "tem_briefing": has_briefing,
        "quando": format_when(row.get("updated_at") or row.get("created_at")),
        "updated_at": row.get("updated_at"),
        "resume_step": resume,
        "resume_action": resume_action(resume),
        "href": plan_href(token, resume),
        "canvas_href": plan_href(token, "canvas") if token else "",
    }


def create_session(user: dict, plan_mode: str) -> dict:
    token = secrets.token_hex(32)
    dados = {"plan_mode": plan_mode, "campanha": {}}
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cadu_smart_planner_sessions
                (session_token, user_id, user_email, user_name, auth_method,
                 input_type, dados_detectados)
            VALUES
                (%s, %s, %s, %s, 'cadu', 'text', %s)
            RETURNING *
            """,
            (
                token,
                user.get("user_id"),
                user.get("user_email"),
                user.get("user_name"),
                Json(dados),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    if not row:
        raise SmartPlannerError("Não foi possível criar a sessão.")
    return row


def update_session(token: str, fields: dict) -> dict:
    row = get_by_token(token)
    if not row:
        raise SessionNotFound("Plano não encontrado.")
    sets = []
    params: list[Any] = []
    for col, value in fields.items():
        if col not in UPDATE_COLS:
            continue
        if col in JSON_COLS:
            sets.append(f"{col} = %s")
            params.append(Json(value) if value is not None else None)
        else:
            sets.append(f"{col} = %s")
            params.append(value)
    if not sets:
        return row
    params.append(row["id"])
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE cadu_smart_planner_sessions SET {', '.join(sets)} WHERE id = %s RETURNING *",
            params,
        )
        updated = cur.fetchone()
    conn.commit()
    return updated or row


def merge_dados(token: str, patch: dict) -> dict:
    row = get_by_token(token)
    if not row:
        raise SessionNotFound("Plano não encontrado.")
    dados = as_dict(row.get("dados_detectados"))
    dados.update(patch or {})
    return update_session(token, {"dados_detectados": dados})


def save_campos(token: str, campos: dict, briefing_text: str | None = None) -> dict:
    row = get_by_token(token)
    if not row:
        raise SessionNotFound("Plano não encontrado.")
    dados = as_dict(row.get("dados_detectados"))
    campanha = campaign_from_campos(campos)
    if isinstance(dados.get("campanha"), dict):
        campanha = {**dados["campanha"], **{k: v for k, v in campanha.items() if v}}
    dados.update(campos)
    dados["nome_campanha"] = text(campos.get("campanha") or dados.get("nome_campanha"))
    dados["campanha"] = campanha
    dados["campos_editados"] = sorted(set(as_list(dados.get("campos_editados")) + list(campos.keys())))
    payload = {
        "dados_detectados": dados,
        "nome_campanha": dados.get("nome_campanha") or None,
        "cliente": text(campos.get("cliente") or dados.get("cliente")) or None,
        "publico_alvo": text(campos.get("publico") or dados.get("publico")) or None,
        "objetivo": text(campos.get("objetivo") or dados.get("objetivo")) or None,
        "budget": text(campos.get("verba") or campanha.get("verba")) or None,
        "prazo": text(campos.get("periodo") or campanha.get("periodo")) or None,
        "plataformas_sugeridas": campanha.get("canais") or None,
    }
    if briefing_text is not None:
        payload["briefing_melhorado"] = briefing_text
        payload["briefing_compilado"] = briefing_text
    return update_session(token, payload)


def soft_delete(session_id: int, user_email: str) -> bool:
    email = (user_email or "").strip().lower()
    conn = get_db()
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                UPDATE cadu_smart_planner_sessions
                   SET deleted_at = CURRENT_TIMESTAMP, public_token_active = FALSE
                 WHERE id = %s AND LOWER(user_email) = %s AND deleted_at IS NULL
                """,
                (session_id, email),
            )
            deleted = cur.rowcount > 0
        except Exception:
            conn.rollback()
            cur.execute(
                """
                UPDATE cadu_smart_planner_sessions
                   SET deleted_at = CURRENT_TIMESTAMP
                 WHERE id = %s AND LOWER(user_email) = %s AND deleted_at IS NULL
                """,
                (session_id, email),
            )
            deleted = cur.rowcount > 0
    conn.commit()
    return deleted
