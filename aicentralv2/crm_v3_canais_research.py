"""Pesquisa e finalize da ficha comercial de cada canal."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from .crm_v3_canais import (
    CANAIS_EXCLUIDOS,
    DISPOSITIVOS,
    _CATALOG_PATH,
    _normalizar_formato,
    persistir_ficha_db,
)
from .services.openrouter_service import OpenRouterError, chat_completion, resolve_api_key

logger = logging.getLogger(__name__)

RESEARCH_MODEL = os.getenv("CANAIS_RESEARCH_MODEL") or os.getenv(
    "PLACES_RESEARCH_MODEL", "perplexity/sonar-pro"
)
FINALIZE_MODEL = os.getenv("CANAIS_FINALIZE_MODEL") or os.getenv(
    "PLACES_FINALIZE_MODEL", "openai/gpt-5-mini"
)


class CanalResearchError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _json_content(raw: Any) -> dict:
    blob = raw
    if isinstance(raw, list):
        blob = "\n".join(
            _text(part.get("text") if isinstance(part, dict) else part) for part in raw
        )
    text_blob = _text(blob)
    if not text_blob:
        return {}
    match = re.search(r"\{.*\}", text_blob, re.S)
    if match:
        text_blob = match.group(0)
    try:
        data = json.loads(text_blob)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _compact(row: dict) -> dict:
    return {
        "slug": row.get("slug"),
        "nome": row.get("nome"),
        "tipo": row.get("tipo"),
        "categoria": row.get("categoria"),
        "alcance": row.get("alcance"),
        "viewability": row.get("viewability"),
        "investimento_minimo": row.get("investimento_minimo"),
        "beneficios": row.get("beneficios") or [],
        "diferenciais": row.get("diferenciais") or [],
        "descricao": row.get("descricao") or "",
        "formatos": row.get("formatos") or [],
    }


def research_canal(row: dict) -> dict:
    nome = _text(row.get("nome"))
    slug = _text(row.get("slug"))
    tipo = _text(row.get("tipo"))
    messages = [
        {
            "role": "system",
            "content": (
                "Você é pesquisador de mídia Brasil 2025–2026. "
                "Valide e complete SOMENTE o que o ad product deste canal vende no Brasil. "
                "Fontes: site do publisher/plataforma, kit 2025/2026, IAB, notícia de produto. "
                "Sem inventar UU, viewability ou mínimo. Responda só JSON válido."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Canal: {nome} ({slug}, tipo {tipo}).\n"
                f"Ficha atual: {json.dumps(_compact(row), ensure_ascii=False)}\n\n"
                "Devolva JSON:\n"
                "{\n"
                '  "formatos": [{ "nome", "dispositivos": [], "melhor_para", "nota" }],\n'
                '  "segmentacoes": [{ "nome", "quando", "exemplo" }],\n'
                '  "alcance": { "label", "fonte", "confianca": "alta|media|baixa" },\n'
                '  "avisos": [],\n'
                '  "fontes": [{ "title", "url" }]\n'
                "}\n"
                "Regras:\n"
                "- formatos: o que a mesa realmente compra (pause, takeover, splash, in-app, pin…). "
                f"dispositivos só destes: {', '.join(DISPOSITIVOS)}.\n"
                "- segmentacoes: 4 a 8 recortes do produto (interesse, contexto, geo, 1st party, momento). "
                "Não copie o tipo genérico.\n"
                "- Se o dado for global, marque aviso. Se não achar, lista vazia — sem chute."
            ),
        },
    ]
    try:
        response = chat_completion(
            messages,
            model=RESEARCH_MODEL,
            max_tokens=2200,
            temperature=0.15,
            timeout=90,
        )
    except OpenRouterError as exc:
        raise CanalResearchError(str(exc) or "A pesquisa do canal não respondeu.") from exc
    return _json_content((response.get("message") or {}).get("content"))


def finalize_canal(row: dict, research: dict) -> dict:
    messages = [
        {
            "role": "system",
            "content": (
                "Você fecha a ficha comercial de um canal. "
                "Não invente número sem fonte. Não copie stub de tipo. "
                "Responda só JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "Devolva JSON: formatos (lista de {nome, dispositivos, melhor_para}), "
                "segmentacoes (4 a 8 de {nome, quando, exemplo}), "
                "alcance_label (string vazia se confiança não for alta).\n\n"
                f"canal={json.dumps(_compact(row), ensure_ascii=False)}\n"
                f"pesquisa={json.dumps(research, ensure_ascii=False)}"
            ),
        },
    ]
    try:
        response = chat_completion(
            messages,
            model=FINALIZE_MODEL,
            max_tokens=2200,
            temperature=0.15,
            timeout=90,
            response_format={"type": "json_object"},
        )
    except OpenRouterError as exc:
        raise CanalResearchError(str(exc) or "O finalize do canal não respondeu.") from exc
    return _json_content((response.get("message") or {}).get("content"))


def merge_pesquisa(row: dict, research: dict, finalized: dict) -> dict:
    tipo = _text(row.get("tipo"))
    out = dict(row)
    formatos = []
    seen = set()
    for raw in list(finalized.get("formatos") or []) + list(research.get("formatos") or []):
        if not isinstance(raw, dict):
            continue
        nome = _text(raw.get("nome"))
        key = nome.casefold()
        if not nome or key in seen:
            continue
        seen.add(key)
        fmt = _normalizar_formato(
            {
                "nome": nome,
                "dispositivos": raw.get("dispositivos") or [],
                "melhor_para": _text(raw.get("melhor_para") or raw.get("nota")),
            },
            tipo,
        )
        if fmt.get("nome"):
            formatos.append(fmt)
    if formatos:
        out["formatos"] = formatos
    segs = []
    seen_seg = set()
    for raw in list(finalized.get("segmentacoes") or []) + list(research.get("segmentacoes") or []):
        if not isinstance(raw, dict):
            continue
        nome = _text(raw.get("nome"))
        key = nome.casefold()
        if not nome or key in seen_seg:
            continue
        seen_seg.add(key)
        segs.append({
            "nome": nome,
            "quando": _text(raw.get("quando")),
            "exemplo": _text(raw.get("exemplo")),
        })
        if len(segs) >= 8:
            break
    if len(segs) >= 3:
        out["segmentacoes"] = segs
    alcance = finalized.get("alcance_label") or (research.get("alcance") or {}).get("label")
    confianca = _text((research.get("alcance") or {}).get("confianca")).casefold()
    if _text(alcance) and confianca == "alta":
        out["alcance"] = _text(alcance)
    fontes = [item for item in (research.get("fontes") or []) if isinstance(item, dict)]
    if fontes:
        out["fontes_pesquisa"] = fontes[:6]
    avisos = [_text(item) for item in (research.get("avisos") or []) if _text(item)]
    if avisos:
        out["avisos_pesquisa"] = avisos[:6]
    return out


def enriquecer_canal(row: dict) -> dict:
    research = research_canal(row)
    finalized = finalize_canal(row, research)
    return merge_pesquisa(row, research, finalized)


def load_catalog() -> list[dict]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def save_catalog(rows: list[dict]) -> None:
    _CATALOG_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def enrich_catalog(*, slugs: list[str] | None = None) -> list[dict]:
    rows = [row for row in load_catalog() if _text(row.get("slug")) not in CANAIS_EXCLUIDOS]
    if not resolve_api_key():
        logger.warning("OPENROUTER_API_KEY ausente — pesquisa dos canais ignorada.")
        save_catalog(rows)
        return rows
    for index, row in enumerate(rows):
        slug = _text(row.get("slug"))
        if slugs and slug not in slugs:
            continue
        if not slugs and row.get("fontes_pesquisa"):
            logger.info("Canal %s já pesquisado — pulando", slug)
            continue
        logger.info("Pesquisando canal %s", slug)
        try:
            rows[index] = enriquecer_canal(row)
        except CanalResearchError:
            logger.exception("Falha na pesquisa de %s", slug)
        save_catalog(rows)
        try:
            persistir_ficha_db(rows[index])
        except Exception:
            logger.exception("Falha ao gravar ficha de %s no banco", slug)
    return rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    enrich_catalog()
