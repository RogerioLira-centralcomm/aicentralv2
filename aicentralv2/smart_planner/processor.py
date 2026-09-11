"""Processador de briefing — contrato de process.php / ai.php."""

from __future__ import annotations

import json

from ..services.openrouter_service import OpenRouterError
from .ai import chat_json, chat_text
from .catalog import CHANNEL_CATALOG, DEVICE_OPTIONS, FIELD_SCHEMA
from .helpers import as_dict, campaign_from_campos, normalize_markdown, text
from .materials import compose_material
from .repository import merge_dados, update_session


NARRATIVE_PROMPT = """Você é o redator de briefing do Smart Planner no CentralX.
Redija um briefing de mídia claro, em markdown, fiel ao material.
Não invente verba, prazo, canal, público ou praça que o material não trouxe.
Use títulos ## curtos. Preserve restrições e observações do cliente.
Não mencione agência, ferramenta ou que o texto foi gerado por IA."""


def extract_fields(material: str, pistas: dict | None = None) -> dict:
    schema_lines = "\n".join(f"- {key}: {hint}" for key, hint in FIELD_SCHEMA.items())
    canais = "\n".join(
        f"{key} = {meta['label']}" + (" [fonte de dados]" if meta.get("tipo") == "dados" else "")
        for key, meta in CHANNEL_CATALOG.items()
    )
    pistas_json = json.dumps(
        {k: v for k, v in (pistas or {}).items() if v not in ("", [], None)},
        ensure_ascii=False,
    )
    prompt = f"""Você é o extrator de campos do Smart Planner no CentralX.
Leia o material e devolva os campos estruturados e uma avaliação de prontidão.

Campos a extrair:
{schema_lines}

Canais válidos (use apenas estes ids em "canais"):
{canais}

Dispositivos válidos: {", ".join(DEVICE_OPTIONS)}

Campos já confirmados — copie como estão:
{pistas_json}

Retorne APENAS JSON válido:
{{
  "campos": {{ ... um par por campo acima ... }},
  "score": 0,
  "bem_definido": ["o que já está claro"],
  "falta_completar": ["o que falta"]
}}

Regras:
- Nunca invente. Campo sem base no material vai vazio ("" ou []).
- Canal só entra quando o material o cita.
- score de 0 a 100. Pesa mais: objetivo, público, verba, período e praça.
"""
    parsed = chat_json(
        "Você extrai dados estruturados e responde apenas com JSON válido.",
        prompt + "\n\n--- MATERIAL ---\n" + material[:40000],
        max_tokens=4000,
    )
    campos = as_dict(parsed.get("campos") if isinstance(parsed, dict) else {})
    analysis = {
        "campos": campos,
        "bem_definido": parsed.get("bem_definido") if isinstance(parsed, dict) else [],
        "falta_completar": parsed.get("falta_completar") if isinstance(parsed, dict) else [],
    }
    return {
        "campos": campos,
        "analysis": analysis,
        "score": int(parsed.get("score") or 0) if isinstance(parsed, dict) else 0,
    }


def compose_narrative(material: str, campos: dict, origem: str = "") -> str:
    compact = {}
    for key, value in (campos or {}).items():
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)
        value = text(value)
        if value:
            compact[key] = value
    parts = [NARRATIVE_PROMPT]
    if compact:
        parts.append(
            "CAMPOS JÁ ESTRUTURADOS\nUse-os como verdade.\n"
            + json.dumps(compact, ensure_ascii=False)
        )
    if origem:
        parts.append("ORIGEM DO MATERIAL: " + origem)
    raw = chat_text(
        "\n\n".join(parts),
        "Redija o briefing a partir deste material:\n\n" + material[:40000],
        max_tokens=6000,
        temperature=0.25,
    )
    if not raw:
        raise OpenRouterError("O compositor não devolveu texto.")
    return normalize_markdown(raw)


def process_briefing(token: str, text_in: str, references: list[dict] | None = None) -> dict:
    material = compose_material(text_in, references)
    if len(material) < 40:
        raise ValueError("Escreva o briefing ou adicione uma referência com mais detalhe.")
    extracted = extract_fields(material)
    campos = extracted["campos"]
    origem = "texto escrito ou colado pelo usuário"
    if references and text_in.strip():
        origem = "briefing escrito pelo usuário acompanhado de material de apoio"
    elif references:
        origem = "conteúdo extraído das referências anexadas"
    narrativa = compose_narrative(material, campos, origem)
    dados = dict(campos)
    dados["nome_campanha"] = text(campos.get("campanha"))
    dados["campanha"] = campaign_from_campos(campos)
    if references:
        dados["referencias"] = [
            {"kind": item.get("kind"), "name": item.get("name"), "url": item.get("url")}
            for item in references
        ]
    input_type = "mixed" if references and text_in.strip() else ("pdf" if references else "text")
    if references and all(item.get("kind") == "url" for item in references) and not text_in.strip():
        input_type = "url"
    row = update_session(token, {
        "input_type": input_type,
        "input_text_original": material,
        "input_url": next((item.get("url") for item in (references or []) if item.get("url")), None),
        "briefing_compilado": narrativa,
        "briefing_melhorado": narrativa,
        "quality_score": extracted["score"],
        "analise_ia": extracted["analysis"],
        "publico_alvo": text(campos.get("publico")) or None,
        "objetivo": text(campos.get("objetivo")) or None,
        "budget": text(campos.get("verba")) or None,
        "prazo": text(campos.get("periodo")) or None,
        "nome_campanha": text(campos.get("campanha")) or None,
        "cliente": text(campos.get("cliente")) or None,
        "plataformas_sugeridas": campos.get("canais") or None,
    })
    current = as_dict(row.get("dados_detectados"))
    current.update(dados)
    current["plan_mode"] = current.get("plan_mode") or "completo"
    row = merge_dados(token, current)
    return {
        "session": row,
        "briefing": narrativa,
        "campos": campos,
        "score": extracted["score"],
        "analysis": extracted["analysis"],
    }
