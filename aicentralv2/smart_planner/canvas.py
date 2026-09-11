"""Quadro do plano — schema, geração completa e página única."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import one_page
from .ai import chat_json
from .helpers import as_dict, as_list, plan_mode_of, session_title, text
from .repository import get_by_token, merge_dados, update_session

SECTIONS = (
    {"id": "context", "title": "Contexto", "order": 1},
    {"id": "strategy", "title": "Estratégia", "order": 2},
    {"id": "media", "title": "Plano de Mídia", "order": 3},
    {"id": "execution", "title": "Execução", "order": 4},
)

ONE_PAGE_TYPES = one_page.ONE_PAGE_TYPES + one_page.LEGACY_ONE_PAGE_TYPES

CANVAS_PROMPT = """Você monta o quadro do Smart Planner no CentralX a partir do briefing e do planejamento.
Devolva APENAS JSON válido no formato:

{
  "meta": {"title": "", "client": "", "campaign": ""},
  "sections": [
    {
      "id": "context|strategy|media|execution",
      "title": "",
      "cards": [
        {
          "type": "summary|kpi-group|allocation|audience|channel-mix|recommendation|creative|next-steps|table",
          "title": "",
          "body": "texto curto em markdown",
          "items": ["opcional"]
        }
      ]
    }
  ]
}

Regras:
- Não invente verba, canal ou KPI que o material não trouxe.
- body objetivo, sem jargão de agência.
- plan_mode=completo: as 4 seções, 2 a 4 cards por seção.
"""


def empty_plan(meta: dict, mode: str, branding: dict | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    if mode == "one_page":
        return one_page.empty_one_page(meta, branding or {})
    else:
        sections = [
            {"id": section["id"], "type": section["id"], "title": section["title"], "order": section["order"], "cards": []}
            for section in SECTIONS
        ]
    return {
        "schemaVersion": 2,
        "planMode": mode,
        "meta": {
            "title": meta.get("title") or "Novo Plano",
            "client": meta.get("client"),
            "campaign": meta.get("campaign"),
            "createdAt": now,
            "updatedAt": now,
        },
        "sections": sections,
    }


def _normalize_card(card: dict, index: int) -> dict:
    items = as_list(card.get("items"))
    return {
        "id": text(card.get("id")) or f"card-{index}",
        "type": text(card.get("type") or "summary"),
        "title": text(card.get("title")) or "Card",
        "body": text(card.get("body")),
        "items": [text(item) for item in items if text(item)],
    }


def normalize_plan(payload: dict, mode: str, meta: dict, branding: dict | None = None) -> dict:
    if mode == "one_page":
        return one_page.normalize_one_page(payload, meta, branding or as_dict(payload.get("branding") if isinstance(payload, dict) else {}))
    plan = empty_plan(meta, mode)
    incoming = as_list(payload.get("sections")) if isinstance(payload, dict) else []
    by_id = {text(section.get("id")): section for section in incoming if isinstance(section, dict)}
    for section in plan["sections"]:
        source = by_id.get(section["id"], {})
        section["cards"] = [
            _normalize_card(card, i) for i, card in enumerate(as_list(source.get("cards")))
        ][:6]
    if isinstance(payload, dict):
        incoming_meta = as_dict(payload.get("meta"))
        plan["meta"].update({k: incoming_meta[k] for k in ("title", "client", "campaign") if incoming_meta.get(k)})
    return plan


def generate_canvas(token: str, presenter_id: str | None = None) -> dict:
    row = get_by_token(token)
    if not row:
        raise ValueError("Plano não encontrado.")
    dados = as_dict(row.get("dados_detectados"))
    mode = plan_mode_of(dados)
    briefing = text(row.get("briefing_melhorado") or row.get("briefing_compilado"))
    planejamento = text(dados.get("planejamento"))
    campanha = as_dict(dados.get("campanha"))
    meta = {
        "title": session_title(row, dados),
        "client": text(row.get("cliente") or dados.get("cliente") or campanha.get("cliente")),
        "agency": text(dados.get("agencia") or campanha.get("agencia")),
        "campaign": text(row.get("nome_campanha") or dados.get("nome_campanha")),
    }
    if mode != "one_page" and not planejamento and not briefing:
        raise ValueError("Gere o planejamento antes de abrir o canvas.")
    if mode == "one_page" and not planejamento and not briefing and not meta.get("client"):
        raise ValueError("Informe o cliente final ou o briefing antes de montar a página única.")
    chosen = text(presenter_id) or text(dados.get("presenter_brand")) or "centralcomm"
    if mode == "one_page":
        plan = one_page.build_one_page(meta, briefing, planejamento, campanha, chosen)
        merge_dados(token, {"presenter_brand": plan["meta"]["presenter"]})
        row = update_session(token, {
            "plan_content": plan,
            "schema_version": 3,
            "canvas_layout": {"mode": mode, "generatedAt": plan["meta"]["updatedAt"], "presenter": plan["meta"]["presenter"]},
        })
        return {"plan": plan, "session": row}
    parsed = chat_json(
        CANVAS_PROMPT,
        json.dumps(
            {
                "plan_mode": mode,
                "meta": meta,
                "briefing": briefing[:12000],
                "planejamento": planejamento[:20000],
                "campanha": campanha,
            },
            ensure_ascii=False,
        ),
        max_tokens=5000,
        temperature=0.2,
    )
    plan = normalize_plan(parsed if isinstance(parsed, dict) else {}, mode, meta)
    row = update_session(token, {
        "plan_content": plan,
        "schema_version": 2,
        "canvas_layout": {"mode": mode, "generatedAt": plan["meta"]["updatedAt"]},
    })
    return {"plan": plan, "session": row}


def save_plan(token: str, plan: dict) -> dict:
    row = get_by_token(token)
    dados = as_dict(row.get("dados_detectados") if row else {})
    mode = plan_mode_of(dados)
    meta = as_dict(plan.get("meta")) if isinstance(plan, dict) else {}
    branding = as_dict(plan.get("branding")) if isinstance(plan, dict) else {}
    normalized = normalize_plan(plan if isinstance(plan, dict) else {}, mode, meta, branding)
    return update_session(token, {"plan_content": normalized})
