"""Orquestração do Smart Planner no CentralX."""

from __future__ import annotations

from flask import session

from .brand import seed_parties
from .catalog import PLAN_MODES, PRACA_OPTIONS, WIZARD_STEPS, objetivo_label, plan_mode_label
from .cost import cost_from_dados, format_brl
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
    total_brl = 0.0
    for row in rows:
        try:
            total_brl += float((row or {}).get("custo_brl") or 0)
        except (TypeError, ValueError):
            continue
    return {
        "rows": rows,
        "total_user": len(rows),
        "total_base": count_sessions(),
        "custo_total_brl": round(total_brl, 2),
        "custo_total": format_brl(total_brl),
    }


def start_plan(plan_mode: str, payload: dict | None = None) -> dict:
    mode = (plan_mode or "").strip().lower()
    if mode not in PLAN_MODES:
        raise ValueError("Escolha plano completo ou página única.")
    seed = seed_parties(payload or {})
    return create_session(current_user(), mode, seed)


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
        "cliente_id": dados.get("cliente_id"),
        "agencia_id": dados.get("agencia_id"),
        "cx_client_id": dados.get("cx_client_id"),
    }
    if isinstance(campos["campanha"], dict):
        campos["campanha"] = text(dados.get("nome_campanha"))
    praca_label = PRACA_OPTIONS.get(campos["praca"], {}).get("label", campos["praca"])
    brand = as_dict(dados.get("brand"))
    custo = cost_from_dados(dados)
    return {
        "row": row,
        "dados": dados,
        "campanha": campanha,
        "campos": campos,
        "brand": brand,
        "facts": {
            "cliente": campos["cliente"],
            "agencia": campos["agencia"],
            "marca": text(brand.get("name")),
            "verba": campos["verba"],
            "custo": custo["label"],
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
    campos = dict(payload.get("campos") or {})
    for key in ("cliente_id", "agencia_id", "cx_client_id"):
        raw = campos.get(key)
        try:
            campos[key] = int(raw) if raw not in ("", None) else None
        except (TypeError, ValueError):
            campos[key] = None
    return save_campos(token, campos, payload.get("briefing"))


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
