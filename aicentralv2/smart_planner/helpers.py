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


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return text(value).lower() in {"1", "true", "yes", "on", "sim"}


_NAME_STOP = {
    "de", "da", "do", "dos", "das", "e", "em", "o", "a", "os", "as", "para",
    "mg", "sa", "s.a", "s/a",
}
_WEAK_NAME = {
    "banco", "marca", "casa", "grupo", "brasil", "minas", "geral", "gerais",
    "digital", "campanha", "cliente", "anunciante",
}
_META_THESIS = re.compile(
    r"^\s*(o planejamento|este planejamento|este plano|esta p[aá]gina|"
    r"esta folha|esta one page|o presente plano)\b",
    re.I,
)


def advertiser_tokens(name: str) -> list[str]:
    raw = text(name)
    if not raw:
        return []
    tokens = [raw]
    for part in re.findall(r"[A-Za-zÀ-ÿ0-9.]{4,}", raw):
        cleaned = part.strip(".")
        if len(cleaned) >= 4 and cleaned.lower() not in _NAME_STOP:
            tokens.append(cleaned)
    seen: list[str] = []
    keys: set[str] = set()
    for token in tokens:
        key = token.lower()
        if key not in keys:
            keys.add(key)
            seen.append(token)
    return seen


def _token_pattern(token: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-zÀ-ÿ0-9])" + re.escape(token) + r"(?![A-Za-zÀ-ÿ0-9])", re.I)


def name_leaks_in(name: str, blob: str) -> bool:
    hay = text(blob)
    if not hay:
        return False
    tokens = advertiser_tokens(name)
    if not tokens:
        return False
    full = tokens[0]
    if _token_pattern(full).search(hay):
        return True
    return any(
        _token_pattern(token).search(hay)
        for token in tokens[1:]
        if token.lower() not in _WEAK_NAME
    )


def redact_advertiser(blob: str, name: str) -> str:
    out = text(blob)
    if not out or not text(name):
        return out
    for token in sorted(advertiser_tokens(name), key=len, reverse=True):
        if token.lower() in _WEAK_NAME and token.lower() != text(name).lower():
            continue
        out = _token_pattern(token).sub("o anunciante", out)
    return out


def thesis_is_meta(statement: str) -> bool:
    return bool(_META_THESIS.search(text(statement)))


def client_display_name(client: dict | None = None, *, confidential: bool = False, name: str = "") -> str:
    data = client if isinstance(client, dict) else {}
    hidden = confidential or as_bool(data.get("confidential"))
    if hidden:
        return "Anunciante"
    return text(data.get("display_name") or data.get("name") or name)


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


def strip_markdown(texto: str) -> str:
    texto = (texto or "").replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"```(?:\w+)?\n?([\s\S]*?)```", r"\1", texto)
    texto = re.sub(r"`([^`]+)`", r"\1", texto)
    texto = re.sub(r"^#{1,6}\s*", "", texto, flags=re.M)
    texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
    texto = re.sub(r"[*_~]{1,3}", "", texto)
    texto = re.sub(r"^\s*[-*+]\s+", "", texto, flags=re.M)
    texto = re.sub(r"^\s*\d+\.\s+", "", texto, flags=re.M)
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def looks_like_reference_dump(texto: str) -> bool:
    raw = (texto or "").lstrip()
    if not raw:
        return False
    return bool(re.search(r"^##\s+(Referência|Notas de apoio)\b", raw, flags=re.I | re.M))


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
    out = {
        "canais": [str(item) for item in canais if item],
        "praca": text(campos.get("praca")),
        "praca_detalhe": text(campos.get("praca_detalhe")),
        "verba": text(campos.get("verba")),
        "periodo": text(campos.get("periodo")),
        "dispositivos": [str(item) for item in dispositivos if item],
        "objetivo": text(campos.get("objetivo")),
        "agencia": text(campos.get("agencia")),
    }
    if "verba_base" in campos:
        base = text(campos.get("verba_base")).lower()
        out["verba_base"] = base if base in {"total", "mensal"} else "total"
    if "verba_valor" in campos:
        try:
            out["verba_valor"] = int(campos.get("verba_valor") or 0)
        except (TypeError, ValueError):
            out["verba_valor"] = 0
    if "verba_alocacao" in campos and isinstance(campos.get("verba_alocacao"), dict):
        out["verba_alocacao"] = {
            str(key): int(value or 0)
            for key, value in campos["verba_alocacao"].items()
            if str(key)
        }
    if "canais_verba" in campos and isinstance(campos.get("canais_verba"), dict):
        out["canais_verba"] = {
            str(key): int(value or 0)
            for key, value in campos["canais_verba"].items()
            if str(key)
        }
    if "mix" in campos and isinstance(campos.get("mix"), dict):
        out["mix"] = campos["mix"]
    if "places" in campos:
        out["places"] = [
            as_dict(item) for item in as_list(campos.get("places")) if as_dict(item).get("slug")
        ]
    if "interativos" in campos:
        raw = campos.get("interativos")
        out["interativos"] = raw if isinstance(raw, dict) else {"formats": as_list(raw)}
    return out


def plan_mode_of(dados: dict, fallback: str = "completo") -> str:
    mode = text(dados.get("plan_mode")).lower()
    return mode if mode in {"completo", "one_page"} else fallback


def session_title(row: dict, dados: dict) -> str:
    raw_name = row.get("nome_campanha") or dados.get("nome_campanha")
    if not raw_name and not isinstance(dados.get("campanha"), dict):
        raw_name = dados.get("campanha")
    campanha = text(raw_name)
    cliente = text(row.get("cliente") or dados.get("cliente") or dados.get("anunciante"))
    if as_bool((dados or {}).get("anunciante_confidencial")):
        if campanha and not name_leaks_in(cliente, campanha):
            return campanha
        return "Anunciante"
    return campanha or cliente or "Campanha sem nome"


def session_public_token(row: dict | None) -> str:
    dados = as_dict((row or {}).get("dados_detectados"))
    share = as_dict(as_dict((row or {}).get("plan_content")).get("share"))
    folha_share = as_dict(as_dict(dados.get("folha")).get("share"))
    return text(
        share.get("public_token")
        or folha_share.get("public_token")
        or dados.get("public_token")
    )


def editor_href(session_token: str = "", public_token: str = "", folha: bool = False) -> str:
    pub = text(public_token)
    sess = text(session_token)
    suffix = "?folha=1" if folha else ""
    if pub:
        return f"/smart-planner/p/{pub}/editar{suffix}"
    if sess:
        return f"/smart-planner/{sess}/canvas{suffix}"
    return "/smart-planner/"


def plan_href(token: str, step: str, public_token: str = "") -> str:
    token = text(token)
    if text(step) == "canvas":
        return editor_href(token, public_token)
    if not token:
        return "/smart-planner/"
    suffix = {
        "briefing": "briefing",
        "revisao": "revisao",
        "canais": "revisao",
        "gerar": "revisao",
        "conclusao": "conclusao",
    }.get(text(step), "briefing")
    return f"/smart-planner/{token}/{suffix}"
