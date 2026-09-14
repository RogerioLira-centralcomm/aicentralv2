"""Progresso da geração — skills visíveis na tela."""

from __future__ import annotations

from datetime import datetime, timezone

from .helpers import as_dict, text
from .repository import get_by_token, merge_dados
from .skills import decorate_step, generation_steps, skill_label


def start_progress(token: str, mode: str) -> dict:
    steps = generation_steps(mode)
    payload = {
        "status": "running",
        "mode": mode,
        "step": steps[0]["id"] if steps else "",
        "skill": steps[0].get("skill") if steps else "",
        "title": steps[0].get("title") if steps else "",
        "index": 0,
        "total": len(steps),
        "percent": 2,
        "steps": [decorate_step(item) for item in steps],
        "engine": _engine(),
        "updatedAt": _now(),
    }
    if payload["steps"]:
        payload["steps"][0]["state"] = "running"
    merge_dados(token, {"geracao": payload, "plan_mode": mode})
    return payload


def mark_step(token: str, step_id: str, state: str = "running", error: str = "") -> dict:
    row = get_by_token(token) or {}
    geracao = as_dict(as_dict(row.get("dados_detectados")).get("geracao"))
    steps = list(geracao.get("steps") or [])
    index = 0
    current = {}
    for i, item in enumerate(steps):
        if item.get("id") == step_id:
            index = i
            current = item
            item["state"] = state
            if error:
                item["error"] = error
            break
        if item.get("state") not in {"done", "skipped", "error"}:
            item["state"] = "done"
    total = max(len(steps), 1)
    advanced = state in {"done", "skipped"}
    percent = int(round(((index + (1 if advanced else 0.45)) / total) * 100))
    payload = {
        **geracao,
        "status": "error" if state == "error" else "running",
        "step": step_id,
        "skill": current.get("skill"),
        "title": current.get("title"),
        "label": skill_label(current.get("skill")),
        "index": index,
        "total": total,
        "percent": min(99, max(2, percent)),
        "steps": steps,
        "error": error,
        "updatedAt": _now(),
    }
    merge_dados(token, {"geracao": payload})
    return payload


def finish_progress(token: str, mode: str) -> dict:
    row = get_by_token(token) or {}
    geracao = as_dict(as_dict(row.get("dados_detectados")).get("geracao"))
    steps = list(geracao.get("steps") or [])
    for item in steps:
        if item.get("state") not in {"error", "skipped"}:
            item["state"] = "done"
    payload = {
        **geracao,
        "status": "done",
        "mode": mode,
        "percent": 100,
        "steps": steps,
        "title": "Documentos prontos",
        "updatedAt": _now(),
    }
    merge_dados(token, {"geracao": payload})
    return payload


def progress_view(row: dict) -> dict:
    dados = as_dict((row or {}).get("dados_detectados"))
    geracao = as_dict(dados.get("geracao"))
    if not geracao:
        return {"status": "idle", "steps": [], "percent": 0}
    return {
        "status": text(geracao.get("status") or "idle"),
        "mode": geracao.get("mode"),
        "step": geracao.get("step"),
        "skill": geracao.get("skill"),
        "label": geracao.get("label") or skill_label(geracao.get("skill")),
        "title": geracao.get("title"),
        "index": geracao.get("index") or 0,
        "total": geracao.get("total") or 0,
        "percent": geracao.get("percent") or 0,
        "steps": geracao.get("steps") or [],
        "engine": geracao.get("engine") or _engine(),
        "error": geracao.get("error") or "",
    }


def _engine() -> str:
    try:
        from ..services.openrouter_service import resolve_openai_api_key
        return "openai" if resolve_openai_api_key() else "openrouter"
    except Exception:
        return "openrouter"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
