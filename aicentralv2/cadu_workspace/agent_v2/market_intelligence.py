"""Profiles and model policy for the reference Market Intelligence workflow."""

from __future__ import annotations

import json
import os
import re

from psycopg.types.json import Json
from ...services.openrouter_service import chat_completion, message_text, resolve_chat_model
from ...cadu_family import repository


MAX_SOURCES = 150
MAX_QUERIES = 30

PROFILES = {
    "quick": {
        "label": "Quick Scan", "source_target": 15, "max_sources": 20,
        "max_queries": 5, "search_rounds": 1, "token_budget": 24_000,
        "max_agent_calls": 8, "max_extractor_calls": 5,
        "stages": ("discover", "extract", "analyze", "render"),
    },
    "deep": {
        "label": "Deep Analysis", "source_target": 60, "max_sources": 150,
        "max_queries": 30, "search_rounds": 4, "token_budget": 120_000,
        "max_agent_calls": 40, "max_extractor_calls": 80,
        "stages": (),
    },
    "custom": {
        "label": "Custom Client Analysis", "source_target": 60, "max_sources": 150,
        "max_queries": 30, "search_rounds": 4, "token_budget": 120_000,
        "max_agent_calls": 40, "max_extractor_calls": 80,
        "stages": (),
    },
}

ROLE_ENV = {
    "fast_classifier": "CADU_MARKET_MI_FAST_MODEL",
    "query_generator": "CADU_MARKET_MI_QUERY_MODEL",
    "structured_extractor": "CADU_MARKET_MI_EXTRACTOR_MODEL",
    "research_reasoner": "CADU_MARKET_MI_REASONER_MODEL",
    "critic": "CADU_MARKET_MI_CRITIC_MODEL",
    "editorial_writer": "CADU_MARKET_MI_WRITER_MODEL",
}
ROLE_NAMES = frozenset(ROLE_ENV)


def allowed_models() -> set[str]:
    values = {resolve_chat_model()}
    values.update(str(os.getenv(variable) or "").strip() for variable in ROLE_ENV.values())
    values.update(item.strip() for item in os.getenv("CADU_MARKET_MI_ALLOWED_MODELS", "").split(","))
    return {value for value in values if value and re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._:-]+", value)}


def profile_for(mode: str, overrides: dict | None = None) -> dict:
    mode = str(mode or "deep").strip().lower()
    if mode not in PROFILES:
        raise ValueError("Modalidade de Market Intelligence inválida.")
    result = dict(PROFILES[mode])
    overrides = overrides if isinstance(overrides, dict) else {}
    # Client customization is data-only and bounded; it cannot choose tools,
    # models, providers, or exceed the platform's cost and source ceilings.
    if mode == "custom":
        for key, low, high in (("source_target", 10, MAX_SOURCES), ("max_queries", 3, MAX_QUERIES),
                               ("search_rounds", 1, 4), ("token_budget", 10_000, 120_000),
                               ("max_agent_calls", 1, 40),
                               ("max_extractor_calls", 1, 80)):
            if key in overrides:
                result[key] = min(high, max(low, int(overrides[key])))
        result["max_sources"] = result["source_target"]
        for key, limit in (("methodology", 6000), ("taxonomy", 3000), ("scoring", 3000),
                           ("source_preferences", 2000), ("review_policy", 2000),
                           ("artifact_template", 3000)):
            value = overrides.get(key)
            if isinstance(value, str) and value.strip():
                result[key] = " ".join(value.split())[:limit]
        for key in ("include_domains", "exclude_domains"):
            domains = overrides.get(key)
            if domains is not None:
                if not isinstance(domains, list) or len(domains) > 10:
                    raise ValueError("Cada lista de domínios aceita até 10 itens.")
                normalized = []
                for domain in domains:
                    value = str(domain or "").strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
                    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}", value):
                        raise ValueError("Informe domínios válidos sem caminhos ou protocolo.")
                    if value not in normalized:
                        normalized.append(value)
                result[key] = normalized
        if result.get("include_domains") and result.get("exclude_domains"):
            raise ValueError("Escolha domínios para incluir ou excluir, não os dois.")
        model_roles = overrides.get("model_roles")
        if model_roles is not None:
            if not isinstance(model_roles, dict) or set(model_roles) - ROLE_NAMES:
                raise ValueError("A personalização de modelos contém uma função não permitida.")
            approved_models = allowed_models()
            normalized_models = {}
            for role, model in model_roles.items():
                model = str(model or "").strip()
                if model not in approved_models:
                    raise ValueError("O modelo escolhido não está na lista aprovada para Market Intelligence.")
                normalized_models[role] = model
            result["model_roles"] = normalized_models
    result["mode"] = mode
    return result


def mode_from_text(message: str) -> str:
    text = str(message or "").lower()
    if re.search(r"\b(?:custom|personalizad\w*|metodologia\s+pr[oó]pria|framework\s+pr[oó]prio)\b", text):
        return "custom"
    if re.search(r"\b(?:deep|profund\w*|aprofundad\w*|robust\w*|completa)\b", text):
        return "deep"
    return "quick"


def _model_for(role: str, model: str = "") -> str:
    if model:
        if model not in allowed_models():
            raise ValueError("O modelo escolhido não está aprovado para Market Intelligence.")
        return model
    return str(os.getenv(ROLE_ENV[role]) or resolve_chat_model()).strip()


def call(role: str, system: str, prompt: str, *, json_output=False, max_tokens=1200, model="") -> dict:
    if role not in ROLE_ENV:
        raise ValueError("Função de modelo inválida.")
    result = chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        model=_model_for(role, model), timeout=120, max_tokens=max(128, min(int(max_tokens), 6000)),
        temperature=0.15 if role in {"research_reasoner", "critic"} else 0.1,
        response_format={"type": "json_object"} if json_output else None,
        provider="openrouter",
    )
    text = message_text(result.get("message") or {})
    parsed = None
    parse_error = None
    if json_output:
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            parse_error = "invalid_json"
        if parsed is not None and not isinstance(parsed, dict):
            parsed = None
            parse_error = "json_not_object"
    return {"text": text, "json": parsed, "model": result.get("model") or _model_for(role, model),
            "provider": result.get("provider") or "openrouter", "usage": result.get("usage") or {},
            "parse_error": parse_error}


def total_tokens(usage: dict) -> int:
    try:
        total = int(usage.get("total_tokens") or 0)
        if total:
            return max(0, total)
        return max(0, int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
                   + int(usage.get("completion_tokens") or usage.get("output_tokens") or 0))
    except (TypeError, ValueError):
        return 0


def validate_client_profile(value: dict | None) -> dict:
    value = value if isinstance(value, dict) else {}
    allowed = {"source_target", "max_queries", "search_rounds", "token_budget", "max_agent_calls", "max_extractor_calls",
               "methodology", "taxonomy", "scoring", "source_preferences", "review_policy", "artifact_template",
               "include_domains", "exclude_domains", "model_roles"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Campo de personalização não permitido: {sorted(unknown)[0]}.")
    return profile_for("custom", value)


def client_profile(client_id: int) -> dict:
    rows = repository.rows("SELECT config,version,updated_at FROM cadu_market_intelligence_profiles WHERE client_id=%s",
                           (int(client_id),))
    if not rows:
        return {}
    config = rows[0].get("config") or {}
    return {**(config if isinstance(config, dict) else {}), "version": int(rows[0].get("version") or 1),
            "updated_at": rows[0].get("updated_at")}


def save_client_profile(client_id: int, user_id: int, value: dict) -> dict:
    config = validate_client_profile(value)
    config = {key: config[key] for key in (
        "source_target", "max_queries", "search_rounds", "token_budget", "max_agent_calls", "max_extractor_calls",
        "methodology", "taxonomy", "scoring", "source_preferences", "review_policy", "artifact_template",
        "include_domains", "exclude_domains",
        "model_roles",
    ) if key in config}
    connection = repository.get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO cadu_market_intelligence_profiles
                (client_id,config,version,updated_by) VALUES (%s,%s,1,%s)
                ON CONFLICT (client_id) DO UPDATE SET config=EXCLUDED.config,
                    version=cadu_market_intelligence_profiles.version+1,updated_by=EXCLUDED.updated_by,updated_at=NOW()
                RETURNING config,version,updated_at""", (int(client_id), Json(config), int(user_id)))
            row = dict(cursor.fetchone())
        connection.commit()
        return {**(row.get("config") or {}), "version": int(row["version"]), "updated_at": row["updated_at"]}
    except Exception:
        connection.rollback()
        raise
