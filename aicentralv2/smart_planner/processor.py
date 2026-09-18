"""Processador de briefing — contrato de process.php / ai.php."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone

from ..services.openrouter_service import OpenRouterError
from .ai import chat_json, chat_text
from .brand import apply_pistas, briefing_pistas, preserve_seed
from .cost import bound_session
from .catalog import CHANNEL_CATALOG, DEVICE_OPTIONS, FIELD_SCHEMA
from .places_bridge import (
    apply_places_to_campos,
    catalog_prompt_lines,
    places_prompt_block,
    snapshot_places,
)
from .helpers import (
    as_bool,
    as_dict,
    as_list,
    campaign_from_campos,
    looks_like_reference_dump,
    redact_advertiser,
    strip_markdown,
    text,
)
from .materials import compose_material, normalize_references
from .repository import get_by_token, merge_dados, update_session

SEARCH_LOCKED = {"verba", "kpis", "cliente", "periodo", "campanha", "agencia"}
logger = logging.getLogger(__name__)


NARRATIVE_PROMPT = """Você é o redator de briefing do Smart Planner no CentralX.
Redija uma narrativa de mídia em prosa corrida, fiel ao material.
Não use markdown: sem #, listas com hífen, asteriscos ou negrito.
Parágrafos curtos. Chame a marca de anunciante, nunca de cliente.
"Clientes da marca" é público, não o anunciante.
Não invente verba, prazo, canal, público, praça ou place que o material não trouxe.
Se houver places confirmados, nomeie o title e o ponto. Raios não se somam. Não descreva app que o catálogo não listou.
Formatos interativos só existem em portais (G1, UOL, R7, CNN), nunca em app, CTV, OOH ou Places.
Preserve restrições e observações do anunciante.
Não mencione agência, ferramenta ou que o texto foi gerado por IA."""


def extract_fields(material: str, pistas: dict | None = None) -> dict:
    schema_lines = "\n".join(f"- {key}: {hint}" for key, hint in FIELD_SCHEMA.items())
    canais = "\n".join(
        f"{key} = {meta['label']}" + (" [fonte de dados]" if meta.get("tipo") == "dados" else "")
        for key, meta in CHANNEL_CATALOG.items()
    )
    places_lines = catalog_prompt_lines()
    confirmed = {k: v for k, v in (pistas or {}).items() if v not in ("", [], None)}
    if as_bool(confirmed.get("anunciante_confidencial")):
        confirmed.pop("cliente", None)
    pistas_json = json.dumps(confirmed, ensure_ascii=False)
    prompt = f"""Você é o extrator de campos do Smart Planner no CentralX.
Leia o material e devolva os campos estruturados e uma avaliação de prontidão.

Campos a extrair:
{schema_lines}

Canais válidos (use apenas estes ids em "canais"):
{canais}

Places publicados (use apenas estes slugs em "places"):
{places_lines}

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
- Canal "places" só entra se o material citar um venue desta lista (aeroporto, shopping ou evento).
- Nunca invente slug, ponto, raio, reach ou app. App só se existir no ponto escolhido.
- Interativos só se um portal (g1, uol, r7, cnn) for citado. Formatos interativos não são Places.
- praca_detalhe é cidade/UF. O venue vai em "places", não misturado como texto solto.
- cliente é o anunciante (marca que anuncia). Em briefing de agência, a palavra "cliente" do texto = anunciante.
- "Clientes da Copasa / do banco / da marca" é público, nunca o campo cliente.
- Se campos já confirmados tiverem cliente, não liste falta de anunciante ou de cliente em falta_completar.
- score de 0 a 100. Pesa mais: objetivo, público, verba, período e praça.
"""
    parsed = chat_json(
        "Você extrai dados estruturados e responde apenas com JSON válido.",
        prompt + "\n\n--- MATERIAL ---\n" + material[:40000],
        role="extract",
    )
    campos = apply_places_to_campos(
        as_dict(parsed.get("campos") if isinstance(parsed, dict) else {}),
        material=material,
    )
    analysis = {
        "campos": campos,
        "bem_definido": parsed.get("bem_definido") if isinstance(parsed, dict) else [],
        "falta_completar": _drop_advertiser_gaps(
            parsed.get("falta_completar") if isinstance(parsed, dict) else [],
            pistas,
        ),
    }
    return {
        "campos": campos,
        "analysis": analysis,
        "score": int(parsed.get("score") or 0) if isinstance(parsed, dict) else 0,
    }


def compose_narrative(material: str, campos: dict, origem: str = "") -> str:
    compact = {}
    confidential = as_bool((campos or {}).get("anunciante_confidencial"))
    for key, value in (campos or {}).items():
        if key == "anunciante_confidencial":
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)
        value = text(value)
        if value:
            compact[key] = value
    if confidential:
        compact.pop("cliente", None)
        material = redact_advertiser(material, text((campos or {}).get("cliente")))
    parts = [NARRATIVE_PROMPT]
    if confidential:
        parts.append("O nome do anunciante é confidencial. Não o escreva. Use apenas 'o anunciante'.")
    places_note = places_prompt_block(snapshot_places(campos.get("places")))
    if places_note:
        parts.append(places_note)
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
        role="narrative",
    )
    if not raw:
        raise OpenRouterError("O compositor não devolveu texto.")
    narrativa = strip_markdown(raw)
    if confidential:
        narrativa = redact_advertiser(narrativa, text((campos or {}).get("cliente")))
    return narrativa


def process_briefing(
    token: str,
    text_in: str,
    references: list[dict] | None = None,
    *,
    processing: bool = False,
) -> dict:
    material = compose_material(text_in, references)
    if len(material) < 40:
        raise ValueError("Escreva o briefing ou adicione uma referência com mais detalhe.")
    with bound_session(token):
        return _process_briefing(token, text_in, references, material, processing=processing)


def _process_briefing(
    token: str,
    text_in: str,
    references: list[dict] | None,
    material: str,
    *,
    processing: bool = False,
) -> dict:
    row = get_by_token(token)
    dados_atuais = as_dict((row or {}).get("dados_detectados"))
    pistas = briefing_pistas(dados_atuais)
    if processing:
        _mark_processing(token, "extract", "Identificando as informações do briefing", 1)
    extracted = extract_fields(material, pistas)
    refs = normalize_references(references)
    campos = apply_pistas(extracted["campos"], pistas)
    campos = apply_support_facts(campos, refs)
    origem = "texto escrito ou colado pelo usuário"
    if refs and text_in.strip():
        origem = "briefing escrito pelo usuário acompanhado de material de apoio"
    elif refs:
        origem = "conteúdo extraído das referências anexadas"
    campos["anunciante_confidencial"] = as_bool(
        dados_atuais.get("anunciante_confidencial") or pistas.get("anunciante_confidencial")
    )
    if processing:
        _mark_processing(token, "narrative", "Redigindo a revisão para você conferir", 2)
    narrativa = compose_narrative(material, campos, origem)
    dados = dict(campos)
    dados["nome_campanha"] = text(campos.get("campanha"))
    dados["campanha"] = campaign_from_campos(campos)
    dados["fonte"] = {
        "briefing": text_in.strip(),
        "referencias": [_fonte_item(item) for item in refs],
    }
    dados["referencias"] = dados["fonte"]["referencias"]
    input_type = "mixed" if refs and text_in.strip() else ("pdf" if refs else "text")
    if refs and all(item.get("kind") == "url" for item in refs) and not text_in.strip():
        input_type = "url"
    if processing:
        _mark_processing(token, "save", "Salvando a revisão", 3)
    row = update_session(token, {
        "input_type": input_type,
        "input_text_original": text_in.strip(),
        "input_url": next((item.get("url") for item in refs if item.get("url")), None),
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
    current = preserve_seed(dados_atuais, dados)
    current["plan_mode"] = current.get("plan_mode") or dados_atuais.get("plan_mode") or "one_page"
    current["cliente"] = text(campos.get("cliente")) or current.get("cliente")
    current["agencia"] = text(campos.get("agencia")) or current.get("agencia")
    current["anunciante_confidencial"] = as_bool(dados_atuais.get("anunciante_confidencial"))
    current.pop("cost", None)
    row = merge_dados(token, current)
    return {
        "session": row,
        "briefing": narrativa,
        "campos": campos,
        "score": extracted["score"],
        "analysis": extracted["analysis"],
    }


def start_processing(token: str, text_in: str, references: list[dict] | None = None) -> dict:
    """Executa a leitura do briefing fora da requisição HTTP.

    Duas chamadas ao modelo podem ultrapassar o timeout do Gunicorn. O estado
    persistido também permite que a tela se recupere após refresh.
    """
    row = get_by_token(token)
    if not row:
        raise ValueError("Plano não encontrado.")
    material = compose_material(text_in, references)
    if len(material) < 40:
        raise ValueError("Escreva o briefing ou adicione uma referência com mais detalhe.")
    current = as_dict(as_dict(row.get("dados_detectados")).get("processamento"))
    if current.get("status") == "running" and not _stale_processing(current):
        return {"started": True, "already": True, "redirect": f"/smart-planner/{token}/revisao"}
    _mark_processing(token, "read", "Lendo e organizando o material", 0, status="running")

    from flask import current_app, has_app_context
    if not has_app_context():
        _run_processing(token, text_in, references)
    else:
        app = current_app._get_current_object()

        def runner():
            with app.app_context():
                _run_processing(token, text_in, references)

        threading.Thread(target=runner, daemon=True, name=f"sp-brief-{token[:12]}").start()
    return {"started": True, "redirect": f"/smart-planner/{token}/revisao"}


def processing_view(row: dict) -> dict:
    return as_dict(as_dict((row or {}).get("dados_detectados")).get("processamento")) or {
        "status": "idle", "step": "", "title": "", "index": 0, "total": 4,
    }


def _run_processing(token: str, text_in: str, references: list[dict] | None) -> None:
    try:
        result = process_briefing(token, text_in, references, processing=True)
        _mark_processing(token, "done", "Revisão pronta", 4, status="done", score=result["score"])
    except Exception as exc:
        logger.exception("Processamento de briefing falhou: %s", token)
        _mark_processing(token, "error", "Não foi possível processar o briefing", 0, status="error", error=str(exc))
    finally:
        try:
            from ..db import close_db
            close_db()
        except Exception:
            pass


def _mark_processing(token: str, step: str, title: str, index: int, *, status: str = "running", **extra) -> None:
    merge_dados(token, {"processamento": {
        "status": status,
        "step": step,
        "title": title,
        "index": index,
        "total": 4,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        **extra,
    }})


def _stale_processing(data: dict, *, minutes: int = 15) -> bool:
    try:
        updated = datetime.fromisoformat(text(data.get("updatedAt")).replace("Z", "+00:00"))
        return updated < datetime.now(timezone.utc) - timedelta(minutes=minutes)
    except ValueError:
        return True


def _drop_advertiser_gaps(items, pistas: dict | None) -> list:
    if not text((pistas or {}).get("cliente")):
        return [text(item) for item in as_list(items) if text(item)]
    out = []
    for item in as_list(items):
        low = text(item).lower()
        if not low:
            continue
        mentions_adv = "anunciante" in low or "nome do cliente" in low
        if mentions_adv or (low.startswith("cliente") and "público" not in low and "publico" not in low):
            continue
        out.append(item)
    return out


def apply_support_facts(campos: dict, references: list[dict] | None = None) -> dict:
    merged = dict(campos or {})
    for item in references or []:
        fatos = item.get("fatos") if isinstance(item.get("fatos"), dict) else {}
        locked = item.get("kind") == "search" or item.get("papel") == "mercado"
        for key, value in fatos.items():
            if key not in FIELD_SCHEMA or value in ("", [], None):
                continue
            if locked and key in SEARCH_LOCKED:
                continue
            current = merged.get(key)
            if current in ("", [], None):
                merged[key] = value
    return merged


def source_material(row: dict) -> str:
    dados = as_dict((row or {}).get("dados_detectados"))
    fonte = as_dict(dados.get("fonte"))
    user = text(fonte.get("briefing"))
    refs = as_list(fonte.get("referencias") or dados.get("referencias"))
    if user:
        return compose_material(user, refs)
    original = text((row or {}).get("input_text_original"))
    if original and not looks_like_reference_dump(original):
        return compose_material(original, refs)
    if refs:
        composed = compose_material("", refs)
        if len(composed) >= 40:
            return composed
    return original or text((row or {}).get("briefing_compilado"))


def _fonte_item(item: dict) -> dict:
    out = {
        "kind": item.get("kind"),
        "label": item.get("label"),
        "notas": item.get("notas"),
        "fatos": item.get("fatos") if isinstance(item.get("fatos"), dict) else {},
        "papel": item.get("papel"),
    }
    if item.get("url"):
        out["url"] = item.get("url")
    if item.get("name"):
        out["name"] = item.get("name")
    if item.get("kind") == "search" and item.get("scope"):
        out["scope"] = item.get("scope")
    if item.get("kind") == "search" and item.get("source_mode"):
        out["source_mode"] = item.get("source_mode")
    return out


def rewrite_from_plan(token: str) -> dict:
    row = get_by_token(token)
    if not row:
        raise ValueError("Plano não encontrado.")
    original = source_material(row)
    if len(original) < 40:
        raise ValueError("Não há briefing original suficiente para reescrever.")
    dados = as_dict(row.get("dados_detectados"))
    campanha = as_dict(dados.get("campanha"))
    campos = {
        "campanha": text(row.get("nome_campanha") or dados.get("nome_campanha")),
        "cliente": text(row.get("cliente") or dados.get("cliente")),
        "agencia": text(dados.get("agencia") or campanha.get("agencia")),
        "objetivo": text(row.get("objetivo") or dados.get("objetivo") or campanha.get("objetivo")),
        "objetivo_texto": text(dados.get("objetivo_texto")),
        "publico": text(row.get("publico_alvo") or dados.get("publico")),
        "verba": text(row.get("budget") or campanha.get("verba") or dados.get("verba")),
        "periodo": text(row.get("prazo") or campanha.get("periodo") or dados.get("periodo")),
        "praca": text(campanha.get("praca") or dados.get("praca")),
        "praca_detalhe": text(campanha.get("praca_detalhe")),
        "contexto": text(dados.get("contexto")),
        "observacoes": text(dados.get("observacoes")),
        "kpis": dados.get("kpis") or [],
        "canais": campanha.get("canais") or dados.get("canais") or [],
        "places": campanha.get("places") or dados.get("places") or [],
        "interativos": campanha.get("interativos") or dados.get("interativos") or {},
        "mix": campanha.get("mix") or {},
        "anunciante_confidencial": as_bool(dados.get("anunciante_confidencial")),
    }
    with bound_session(token):
        narrativa = compose_narrative(
            original,
            campos,
            "reescrita com a parametrização atual do executivo — mix, verba e objetivo valem mais que o rascunho antigo",
        )
        update_session(token, {
            "briefing_melhorado": narrativa,
            "briefing_compilado": narrativa,
        })
    return {"briefing": narrativa}
