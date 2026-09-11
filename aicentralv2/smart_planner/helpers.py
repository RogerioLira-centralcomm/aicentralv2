"""Utilitários do Smart Planner."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any


def as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [value]
        except (TypeError, ValueError):
            return [value]
    return []


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def extract_json(payload: str) -> Any:
    raw = (payload or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json|markdown|md)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except (TypeError, ValueError):
            return None


def normalize_markdown(texto: str) -> str:
    texto = (texto or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    fenced = re.match(r"^```(?:markdown|md)?\s*\n([\s\S]*?)\n```$", texto, re.I)
    if fenced:
        texto = fenced.group(1).strip()
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r"([^\n])\n(#{1,6}\s)", r"\1\n\n\2", texto)
    return texto.strip() + "\n"


def format_when(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                value = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return value
    if not isinstance(value, datetime):
        return ""
    now = datetime.now(value.tzinfo) if value.tzinfo else datetime.now()
    days = int((now - value.replace(tzinfo=value.tzinfo)).total_seconds() // 86400)
    if days <= 0:
        return "hoje"
    if days == 1:
        return "ontem"
    if days < 30:
        return f"há {days} dias"
    return value.strftime("%d/%m/%Y")


def campaign_from_campos(campos: dict) -> dict:
    canais = as_list(campos.get("canais"))
    dispositivos = as_list(campos.get("dispositivos"))
    return {
        "canais": [str(item) for item in canais if item],
        "praca": text(campos.get("praca")),
        "praca_detalhe": text(campos.get("praca_detalhe")),
        "verba": text(campos.get("verba")),
        "periodo": text(campos.get("periodo")),
        "dispositivos": [str(item) for item in dispositivos if item],
        "objetivo": text(campos.get("objetivo")),
        "agencia": text(campos.get("agencia")),
    }


def plan_mode_of(dados: dict, fallback: str = "completo") -> str:
    mode = text(dados.get("plan_mode")).lower()
    return mode if mode in {"completo", "one_page"} else fallback


def session_title(row: dict, dados: dict) -> str:
    raw_name = row.get("nome_campanha") or dados.get("nome_campanha")
    if not raw_name and not isinstance(dados.get("campanha"), dict):
        raw_name = dados.get("campanha")
    campanha = text(raw_name)
    cliente = text(row.get("cliente") or dados.get("cliente") or dados.get("anunciante"))
    return campanha or cliente or "Campanha sem nome"


def plan_href(token: str, step: str) -> str:
    token = text(token)
    if not token:
        return "/smart-planner/"
    suffix = {
        "briefing": "briefing",
        "revisao": "revisao",
        "canais": "canais",
        "gerar": "gerar",
        "canvas": "canvas",
    }.get(text(step), "briefing")
    return f"/smart-planner/{token}/{suffix}"
