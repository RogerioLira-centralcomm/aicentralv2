"""Turn the current message into a standalone query for project retrieval."""
from __future__ import annotations

import json
import os
import re
import unicodedata

import requests
from flask import current_app, has_app_context

REWRITE_URL = "https://api.openai.com/v1/chat/completions"
REWRITE_MODEL = os.getenv("CADU_RETRIEVAL_REWRITE_MODEL", "gpt-4.1-mini")
REWRITE_TIMEOUT = float(os.getenv("CADU_RETRIEVAL_REWRITE_TIMEOUT", "3"))

_REFERENTIAL = re.compile(
    r"^\s*(?:e\s+(?:o|a|os|as|quanto|qual|quais|sobre|se)\b|e\s*\?|isso|isto|esse|essa|esses|essas|"
    r"dele|dela|deles|delas|aquilo|aquele|aquela|tamb[eé]m|mesmo|ok|certo|beleza|continue|continua|"
    r"segue|pode|faz|fa[cç]a|mais|agora)\b|\b(?:isso|disso|nisso|esse|essa|dele|dela|acima|anterior|"
    r"o mesmo|a mesma|aquilo)\b",
    re.IGNORECASE,
)
_STOP = frozenset({
    "para", "como", "esse", "essa", "este", "esta", "sobre", "dados", "quais", "qual", "com", "dos",
    "das", "uma", "por", "que", "voce", "isso", "isto", "mais", "pode", "faca", "favor", "agora",
    "quero", "preciso", "gostaria", "tambem", "ainda", "aqui", "ser", "tem", "nos", "nas", "seu",
    "sua", "meu", "minha", "nosso", "nossa", "projeto",
})
_SYSTEM = (
    "Reescreva a última mensagem do usuário como uma consulta de busca autônoma em português para "
    "recuperar documentos, decisões e conversas de um projeto de marketing. Resolva pronomes e elipses "
    "(\"e o orçamento?\", \"isso vale para o Instagram?\") usando o histórico. Mantenha nomes, números, "
    "canais, datas e termos técnicos. Não responda à pergunta, não invente fatos e não acrescente termos "
    "ausentes do histórico. Responda somente JSON: {\"query\": \"...\"} com no máximo 30 palavras."
)


def _terms(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return [word for word in re.findall(r"[a-z0-9]{3,}", folded) if word not in _STOP]


def previous_user_messages(history: str, limit: int = 2) -> list[str]:
    """Extract the latest user turns from the bounded transcript built for the provider."""
    body = re.sub(r"^\[Hist[oó]rico anterior:[^\]]*\]\n?|\n?\[Fim do hist[oó]rico\.\]$", "", str(history or ""))
    turns = re.split(r"\n(?=(?:Usu[aá]rio|Assistente): )", body)
    users = [" ".join(turn.split(":", 1)[1].split()) for turn in turns if turn.startswith(("Usuário: ", "Usuario: "))]
    return [item for item in users if item][-limit:]


def needs_context(message: str) -> bool:
    return bool(_REFERENTIAL.search(str(message or ""))) or len(_terms(message)) < 4


def contextual_query(message: str, history: str = "") -> str:
    """Deterministic standalone query: current message plus recent user intent when it is elliptical."""
    current = " ".join(str(message or "").split())
    if not history or not needs_context(current):
        return current[:400]
    previous = " ".join(previous_user_messages(history))
    return f"{current} {previous}".strip()[:400]


def _llm_rewrite(message: str, history: str) -> str:
    from ...services.openrouter_service import resolve_openai_api_key

    key = resolve_openai_api_key()
    if not key:
        return ""
    transcript = str(history or "")[-3000:]
    response = requests.post(
        REWRITE_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": REWRITE_MODEL, "temperature": 0, "max_tokens": 120,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": _SYSTEM},
                           {"role": "user", "content": f"Histórico:\n{transcript}\n\nÚltima mensagem: {message}"}]},
        timeout=REWRITE_TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return " ".join(str(json.loads(content).get("query") or "").split())[:400]


def retrieval_query(message: str, history: str = "") -> dict:
    """Return the query used for project retrieval and how it was produced."""
    current = " ".join(str(message or "").split())[:400]
    if not history or not needs_context(current):
        return {"query": current, "strategy": "message"}
    try:
        rewritten = _llm_rewrite(current, history)
        if len(_terms(rewritten)) >= 2:
            return {"query": rewritten, "strategy": "llm_rewrite"}
    except Exception as exc:
        if has_app_context():
            current_app.logger.warning("Reescrita da consulta indisponível: %s", type(exc).__name__)
    return {"query": contextual_query(current, history), "strategy": "history_merge"}
