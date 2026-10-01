"""Optional model reranking of retrieved project evidence (off unless enabled)."""
from __future__ import annotations

import json
import os

import requests
from flask import current_app, has_app_context

URL = "https://api.openai.com/v1/chat/completions"
MODEL = os.getenv("CADU_RERANK_MODEL", "gpt-4.1-mini")
TIMEOUT = float(os.getenv("CADU_RERANK_TIMEOUT", "4"))
CANDIDATES = 20
SNIPPET_CHARS = 450

SYSTEM = (
    "Você ordena trechos recuperados de um projeto de marketing pela utilidade para responder a pergunta. "
    "Dê prioridade ao que responde diretamente, com dado concreto (número, decisão, nome, data). "
    "Rebaixe trechos genéricos, apenas tangenciais ou que só repetem o título. Não responda à pergunta. "
    'Responda somente JSON: {"order":["id mais útil","próximo",...]} com ids da lista, sem repetir.'
)


def enabled() -> bool:
    return os.getenv("CADU_RERANK", "0") == "1"


def _text(row: dict) -> str:
    parts = [row.get("title") or row.get("label") or row.get("fonte") or ""]
    parts.append(row.get("trecho") or row.get("display_value") or row.get("description") or "")
    return " | ".join(" ".join(str(part).split()) for part in parts if part)[:SNIPPET_CHARS]


def apply_order(rows: list[dict], order: list) -> list[dict]:
    """Move the model's picks to the front; anything it omitted keeps its original order."""
    by_id = {str(index): row for index, row in enumerate(rows)}
    chosen, seen = [], set()
    for item in order if isinstance(order, list) else []:
        key = str(item)
        if key in by_id and key not in seen:
            seen.add(key)
            chosen.append(by_id[key])
    return chosen + [row for index, row in enumerate(rows) if str(index) not in seen]


def _ask(query: str, rows: list[dict]) -> list:
    from ...services.openrouter_service import resolve_openai_api_key

    key = resolve_openai_api_key()
    if not key:
        raise RuntimeError("OpenAI não configurada para reranking.")
    listing = "\n".join(f"[{index}] {_text(row)}" for index, row in enumerate(rows))
    response = requests.post(
        URL, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": 0, "max_tokens": 200,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": f"Pergunta: {query}\n\nTrechos:\n{listing}"}]},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return json.loads(response.json()["choices"][0]["message"]["content"]).get("order") or []


def rerank(query: str, rows: list[dict], *, setting: bool | None = None) -> tuple[list[dict], bool]:
    """Return (rows, reranked). Failures keep the original order; ranking is never a hard dependency."""
    head, tail = rows[:CANDIDATES], rows[CANDIDATES:]
    # setting: True forces, False disables, None follows CADU_RERANK.
    if setting is False or (setting is None and not enabled()) or len(head) < 3:
        return rows, False
    try:
        return apply_order(head, _ask(query, head)) + tail, True
    except Exception as exc:
        if has_app_context():
            current_app.logger.warning("Reranking indisponível: %s", type(exc).__name__)
        return rows, False
