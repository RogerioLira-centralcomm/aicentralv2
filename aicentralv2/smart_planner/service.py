"""Orquestração do Smart Planner no CentralX."""

from __future__ import annotations

from flask import session

from .catalog import PLAN_MODES, PRACA_OPTIONS, WIZARD_STEPS, objetivo_label, plan_mode_label
from .logos import presenter_options
from .helpers import as_dict, as_list, plan_mode_of, session_title, text
from .repository import (
    SessionNotFound,
    count_sessions,
    create_session,
    get_owned,
    list_sessions,
    save_campos,
    soft_delete,
    update_session,
)


def current_user() -> dict:
    return {
        "user_id": session.get("user_id"),
        "user_email": (session.get("user_email") or "").strip().lower(),
        "user_name": session.get("user_name") or "",
    }


def history_payload() -> dict:
    user = current_user()
    rows = list_sessions(user["user_email"], user["user_id"])
    return {
        "rows": rows,
        "total_user": len(rows),
        "total_base": count_sessions(),
    }


def start_plan(plan_mode: str) -> dict:
    mode = (plan_mode or "").strip().lower()
    if mode not in PLAN_MODES:
        raise ValueError("Escolha plano completo ou página única.")
    return create_session(current_user(), mode)


def load_owned(token: str) -> dict:
    user = current_user()
    return get_owned(token, user["user_email"], user["user_id"])


def wizard_context(row: dict, step_id: str) -> dict:
    dados = as_dict(row.get("dados_detectados"))
    campanha = dados.get("campanha") if isinstance(dados.get("campanha"), dict) else {}
    step_ids = [item["id"] for item in WIZARD_STEPS]
    index = step_ids.index(step_id) if step_id in step_ids else 0
    campos = {
        "campanha": text(row.get("nome_campanha") or dados.get("nome_campanha") or dados.get("campanha")),
        "cliente": text(row.get("cliente") or dados.get("cliente")),
        "objetivo": text(row.get("objetivo") or dados.get("objetivo") or campanha.get("objetivo")),
        "objetivo_texto": text(dados.get("objetivo_texto")),
        "agencia": text(dados.get("agencia") or campanha.get("agencia")),
        "contexto": text(dados.get("contexto")),
        "publico": text(row.get("publico_alvo") or dados.get("publico")),
        "praca": text(campanha.get("praca") or dados.get("praca")),
        "praca_detalhe": text(campanha.get("praca_detalhe") or dados.get("praca_detalhe")),
        "verba": text(row.get("budget") or campanha.get("verba") or dados.get("verba")),
        "periodo": text(row.get("prazo") or campanha.get("periodo") or dados.get("periodo")),
        "canais": as_list(campanha.get("canais") or dados.get("canais")),
        "criativos": text(dados.get("criativos")),
        "dispositivos": as_list(campanha.get("dispositivos") or dados.get("dispositivos")),
        "kpis": dados.get("kpis") or [],
        "observacoes": text(dados.get("observacoes")),
    }
    if isinstance(campos["campanha"], dict):
        campos["campanha"] = text(dados.get("nome_campanha"))
    praca_label = PRACA_OPTIONS.get(campos["praca"], {}).get("label", campos["praca"])
    return {
        "row": row,
        "dados": dados,
        "campanha": campanha,
        "campos": campos,
        "facts": {
            "cliente": campos["cliente"],
            "verba": campos["verba"],
            "periodo": campos["periodo"],
            "praca": praca_label,
            "objetivo": objetivo_label(campos["objetivo"]) or campos["objetivo_texto"],
        },
        "plan_mode": plan_mode_of(dados),
        "plan_mode_label": plan_mode_label(plan_mode_of(dados)),
        "presenter_brand": text(dados.get("presenter_brand")) or "centralcomm",
        "presenter_options": presenter_options(),
        "titulo": session_title(row, dados),
        "briefing": text(row.get("briefing_melhorado") or row.get("briefing_compilado")),
        "planejamento": text(dados.get("planejamento")),
        "tem_quadro": bool(as_list(as_dict(row.get("plan_content")).get("sections"))),
        "steps": WIZARD_STEPS,
        "step_id": step_id,
        "step_index": index,
        "token": row.get("session_token"),
    }


def persist_review(token: str, payload: dict) -> dict:
    return save_campos(token, payload.get("campos") or {}, payload.get("briefing"))


def persist_canais(token: str, payload: dict) -> dict:
    campos = {
        "verba": payload.get("verba"),
        "periodo": payload.get("periodo"),
        "praca": payload.get("praca"),
        "praca_detalhe": payload.get("praca_detalhe"),
        "canais": payload.get("canais") or [],
        "dispositivos": payload.get("dispositivos") or [],
        "objetivo": payload.get("objetivo"),
    }
    return save_campos(token, campos)


def delete_plan(session_id: int) -> bool:
    user = current_user()
    if not user["user_email"]:
        raise SessionNotFound("Sessão sem e-mail.")
    return soft_delete(session_id, user["user_email"])


def touch_owner(row: dict) -> dict:
    """Garante que um plano reaberto fique com o dono do ERP."""
    user = current_user()
    if text(row.get("user_email")).lower() == user["user_email"]:
        return row
    return update_session(row["session_token"], {
        "user_id": user["user_id"],
        "user_email": user["user_email"],
        "user_name": user["user_name"],
        "auth_method": "cadu",
    })
