"""Orquestração do Smart Planner no CentralX."""

from __future__ import annotations

from flask import session

from .brand import seed_parties
from .catalog import (
    CHANNEL_CATALOG,
    CHANNEL_SHOWCASE,
    DEVICE_OPTIONS,
    PLAN_MODES,
    PRACA_OPTIONS,
    WIZARD_STEPS,
    WIZARD_TRAIL,
    objetivo_label,
    plan_mode_label,
    score_label,
)
from .mix import METHODS, allocate, normalize_mix, recommend_methods, shares_to_money, spec_for_js
from .cost import cost_from_dados, format_brl
from .models import preview_cost
from .logos import presenter_options
from .helpers import as_dict, as_list, looks_like_reference_dump, plan_mode_of, session_title, text
from .materials import normalize_references
from .pace import (
    allocate_months,
    budget_shares,
    campaign_pace,
    campaign_verba,
    distribute_budget,
    format_money,
    format_verba,
    pace_payload,
    parse_money,
    parse_money_digits,
)
from .repository import (
    SessionNotFound,
    count_sessions,
    create_session,
    get_by_token,
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


def _fonte_referencias(dados: dict) -> list[dict]:
    fonte = as_dict(as_dict(dados).get("fonte"))
    return [
        item for item in normalize_references(fonte.get("referencias") or as_dict(dados).get("referencias"))
        if item.get("notas")
    ]


def _briefing_original(row: dict, dados: dict) -> str:
    fonte = as_dict(as_dict(dados).get("fonte"))
    user = text(fonte.get("briefing"))
    if user:
        return user
    original = text((row or {}).get("input_text_original"))
    if original and not looks_like_reference_dump(original):
        return original
    return ""


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
        "canais": as_list(campanha.get("canais") or dados.get("canais") or row.get("plataformas_sugeridas")),
        "criativos": text(dados.get("criativos")),
        "dispositivos": as_list(campanha.get("dispositivos") or dados.get("dispositivos")),
        "kpis": [text(item) for item in as_list(dados.get("kpis")) if text(item)],
        "mix": as_dict(campanha.get("mix")),
        "observacoes": text(dados.get("observacoes")),
        "cliente_id": dados.get("cliente_id"),
        "agencia_id": dados.get("agencia_id"),
        "cx_client_id": dados.get("cx_client_id"),
    }
    if isinstance(campos["campanha"], dict):
        campos["campanha"] = text(dados.get("nome_campanha"))
    campos["canais"] = [key for key in campos["canais"] if key in CHANNEL_CATALOG]
    verba = campaign_verba({
        "verba": campos["verba"],
        "verba_valor": campanha.get("verba_valor"),
        "verba_base": campanha.get("verba_base"),
    })
    pace = campaign_pace({
        **campanha,
        "verba": campos["verba"],
        "verba_valor": verba["valor"],
        "verba_base": verba["base"],
        "periodo": campos["periodo"],
    })
    method = text(campos["mix"].get("method"))
    if method not in {item["id"] for item in METHODS}:
        method = recommend_methods(campos["objetivo"])[0]
    desk_weights = allocate(campos["canais"], campos["objetivo"], method, campos["mix"].get("weights"))
    if desk_weights and verba["valor"] > 0:
        distribuicao = shares_to_money(desk_weights, verba["valor"])
        shares = {item["id"]: item["pct"] for item in desk_weights}
    else:
        distribuicao = distribute_budget(campos["canais"], verba["valor"], campanha.get("canais_verba"))
        shares = budget_shares(distribuicao)
    mix = []
    for key in campos["canais"]:
        meta = CHANNEL_CATALOG.get(key) or {}
        mix.append({
            "id": key,
            "label": meta.get("label", key),
            "desc": meta.get("desc", ""),
            "valor": distribuicao.get(key, 0),
            "valor_label": format_money(distribuicao.get(key, 0)),
            "pct": shares.get(key, 0),
        })
    mix_desk = {
        "method": method,
        "recommended": recommend_methods(campos["objetivo"]),
        "weights": desk_weights,
        "methods": [dict(item) for item in METHODS],
        "spec": spec_for_js(),
    }
    available = []
    seen = set(campos["canais"])
    for key in list(CHANNEL_SHOWCASE) + [item for item in CHANNEL_CATALOG if item not in CHANNEL_SHOWCASE]:
        if key in seen or key not in CHANNEL_CATALOG:
            continue
        meta = CHANNEL_CATALOG[key]
        if meta.get("tipo") == "dados":
            continue
        available.append({"id": key, "label": meta.get("label", key), "desc": meta.get("desc", "")})
    praca_label = PRACA_OPTIONS.get(campos["praca"], {}).get("label", campos["praca"])
    brand = as_dict(dados.get("brand"))
    custo = cost_from_dados(dados)
    analysis = as_dict(row.get("analise_ia"))
    gaps = [text(item) for item in as_list(analysis.get("falta_completar")) if text(item)]
    share = as_dict(as_dict(row.get("plan_content")).get("share"))
    score = 0
    try:
        score = int(row.get("quality_score") or 0)
    except (TypeError, ValueError):
        score = 0
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
        "briefing_original": _briefing_original(row, dados),
        "fonte": as_dict(dados.get("fonte")),
        "fonte_referencias": _fonte_referencias(dados),
        "planejamento": text(dados.get("planejamento")),
        "tem_quadro": bool(as_list(as_dict(row.get("plan_content")).get("sections"))),
        "share_url": text(share.get("url")),
        "steps": WIZARD_STEPS,
        "trail": WIZARD_TRAIL,
        "step_id": step_id,
        "step_index": index,
        "step_number": index + 1,
        "step_total": len(WIZARD_TRAIL),
        "step_progress": int(round(((index + 1) / len(WIZARD_TRAIL)) * 100)),
        "quality_score": score,
        "quality": score_label(score),
        "analysis": analysis,
        "gaps": gaps,
        "token": row.get("session_token"),
        "verba": verba,
        "pace": pace_payload(pace),
        "mix": mix,
        "mix_desk": mix_desk,
        "available_channels": available,
        "restricoes": campos["observacoes"],
        "cost_options": {
            "one_page": preview_cost("one_page", dados),
            "completo": preview_cost("completo", dados),
        },
        "tem_folha": bool(as_list(as_dict(dados.get("folha")).get("sections"))),
        "consistency": as_dict(dados.get("consistency")),
    }


def _as_kpis(value) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    return [text(item) for item in as_list(value) if text(item)]


def persist_review(token: str, payload: dict) -> dict:
    payload = payload or {}
    campos = dict(payload.get("campos") or {})
    for key in ("cliente_id", "agencia_id", "cx_client_id"):
        raw = campos.get(key)
        try:
            campos[key] = int(raw) if raw not in ("", None) else None
        except (TypeError, ValueError):
            campos[key] = None
    if "kpis" in campos:
        campos["kpis"] = _as_kpis(campos.get("kpis"))
    canais = [
        str(key)
        for key in as_list(payload.get("canais") if payload.get("canais") is not None else campos.get("canais"))
        if str(key) in CHANNEL_CATALOG
    ]
    if payload.get("canais") is not None or "canais" in campos:
        campos["canais"] = canais
    mix_raw = payload.get("mix") if payload.get("mix") is not None else campos.get("mix")
    if isinstance(mix_raw, dict):
        mix = normalize_mix(mix_raw, canais, campos.get("objetivo"))
        campos["mix"] = mix
        verba = campaign_verba({
            "verba": campos.get("verba"),
            "verba_valor": campos.get("verba_valor"),
            "verba_base": campos.get("verba_base"),
        })
        if verba["valor"] > 0:
            campos["verba_valor"] = verba["valor"]
            campos["verba_base"] = verba["base"]
            if verba["texto"]:
                campos["verba"] = verba["texto"]
            campos["canais_verba"] = shares_to_money(mix["weights"], verba["valor"])
    return save_campos(token, campos, payload.get("briefing"))


def persist_canais(token: str, payload: dict) -> dict:
    payload = payload or {}
    row = get_by_token(token)
    if not row:
        raise SessionNotFound("Plano não encontrado.")
    existing = as_dict(as_dict(row.get("dados_detectados")).get("campanha"))
    canais = [str(key) for key in as_list(payload.get("canais")) if str(key) in CHANNEL_CATALOG]
    if not canais:
        canais = [str(key) for key in as_list(existing.get("canais")) if str(key) in CHANNEL_CATALOG]
    verba = campaign_verba({
        "verba": payload.get("verba") or existing.get("verba"),
        "verba_valor": payload.get("verba_valor") if payload.get("verba_valor") not in ("", None) else existing.get("verba_valor"),
        "verba_base": payload.get("verba_base") or existing.get("verba_base"),
    })
    if verba["valor"] <= 0:
        parsed = parse_money(payload.get("verba") or existing.get("verba"))
        verba = {
            "valor": parsed["valor"],
            "base": text(payload.get("verba_base") or existing.get("verba_base")).lower() or parsed["base"] or "total",
            "texto": text(payload.get("verba") or existing.get("verba")),
        }
        if verba["base"] not in {"total", "mensal"}:
            verba["base"] = "total"
        if verba["valor"] > 0:
            verba["texto"] = format_verba(verba["valor"], verba["base"])
    periodo = text(payload.get("periodo")) or text(existing.get("periodo"))
    alocacao_in = payload.get("verba_alocacao") if isinstance(payload.get("verba_alocacao"), dict) else {}
    if not alocacao_in:
        alocacao_in = existing.get("verba_alocacao") if isinstance(existing.get("verba_alocacao"), dict) else {}
    pace = campaign_pace({
        "verba": verba["texto"],
        "verba_valor": verba["valor"],
        "verba_base": verba["base"],
        "periodo": periodo,
        "verba_alocacao": alocacao_in,
    })
    alocacao = pace["alocacao"]
    if pace["editavel"] and alocacao_in and pace["chaves"]:
        alocacao = allocate_months(pace["chaves"], pace["total"], alocacao_in)
    recipe = payload.get("mix") if isinstance(payload.get("mix"), dict) else existing.get("mix")
    canais_verba_in = payload.get("canais_verba") if isinstance(payload.get("canais_verba"), dict) else {}
    if not canais_verba_in and isinstance(payload.get("mix"), list):
        canais_verba_in = {
            str(item.get("id")): item.get("valor")
            for item in payload.get("mix")
            if as_dict(item).get("id")
        }
    if canais_verba_in:
        canais_verba = distribute_budget(canais, verba["valor"], canais_verba_in)
        shares = budget_shares(canais_verba)
        if isinstance(recipe, dict) and (recipe.get("method") or recipe.get("weights")):
            mix = {
                "method": text(recipe.get("method")) or "manual",
                "weights": allocate(canais, text(payload.get("objetivo") or existing.get("objetivo")), "manual", [
                    {"id": key, "pct": shares.get(key, 0)} for key in canais
                ]),
                "locked": True,
            }
        else:
            mix = None
    elif isinstance(recipe, dict) and (recipe.get("method") or recipe.get("weights")):
        mix = normalize_mix(recipe, canais, text(payload.get("objetivo") or existing.get("objetivo")))
        canais_verba = shares_to_money(mix["weights"], verba["valor"]) if verba["valor"] > 0 else {}
    else:
        if not canais_verba_in:
            canais_verba_in = existing.get("canais_verba") if isinstance(existing.get("canais_verba"), dict) else {}
        canais_verba = distribute_budget(canais, verba["valor"], canais_verba_in)
        mix = None
    campos = {
        "verba": verba["texto"] or text(payload.get("verba") or existing.get("verba")),
        "verba_valor": verba["valor"],
        "verba_base": verba["base"],
        "verba_alocacao": alocacao,
        "periodo": periodo,
        "praca": text(payload.get("praca")) if "praca" in payload else text(existing.get("praca")),
        "praca_detalhe": text(payload.get("praca_detalhe")) if "praca_detalhe" in payload else text(existing.get("praca_detalhe")),
        "canais": canais,
        "canais_verba": canais_verba,
    }
    if mix is not None:
        campos["mix"] = mix
    if "dispositivos" in payload:
        campos["dispositivos"] = [
            str(key) for key in as_list(payload.get("dispositivos")) if str(key) in DEVICE_OPTIONS
        ]
    return save_campos(token, campos)


def ritmo_from_payload(payload: dict) -> dict:
    payload = payload or {}
    verba = campaign_verba({
        "verba": payload.get("verba"),
        "verba_valor": payload.get("verba_valor") or parse_money_digits(payload.get("verba")),
        "verba_base": payload.get("verba_base"),
    })
    return pace_payload(campaign_pace({
        "verba": verba["texto"],
        "verba_valor": verba["valor"],
        "verba_base": verba["base"],
        "periodo": payload.get("periodo"),
        "verba_alocacao": payload.get("verba_alocacao") if isinstance(payload.get("verba_alocacao"), dict) else {},
    }))


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
