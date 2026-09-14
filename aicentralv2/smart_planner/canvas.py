"""Quadro do plano — schema, geração completa e página única."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from . import one_page
from .ai import chat_json
from .skills import load_skill
from .catalog import PRACA_OPTIONS, objetivo_label
from .cost import bound_session
from .helpers import as_dict, as_list, extract_json, plan_mode_of, session_title, text
from .materials import apoio_notes
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
- body de decisão: o que fazer, com que peso e por quê. Sem jargão de agência.
- plan_mode=completo: as 4 seções, 2 a 3 cards por seção.
- O primeiro card de strategy deve ser a recomendação em uma frase.
- Se o voo mensal existir na campanha, um card de media descreve as colunas (menor no começo, maior no meio e no fim).
- Se houver identidade da marca, use público, produto e tom como verdade.
- Se houver pagina_unica, ela é a tese já escrita. Aprofunde. Não contradiga.
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
            "budget": meta.get("budget"),
            "period": meta.get("period"),
            "market": meta.get("market"),
            "objective": meta.get("objective"),
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
        plan["meta"].update({
            k: incoming_meta[k]
            for k in ("title", "client", "campaign", "budget", "period", "market", "objective")
            if incoming_meta.get(k)
        })
    return plan


def _row_meta(row: dict, dados: dict) -> dict:
    campanha = as_dict(dados.get("campanha"))
    praca_key = text(campanha.get("praca") or dados.get("praca"))
    return {
        "title": session_title(row, dados),
        "client": text(row.get("cliente") or dados.get("cliente") or campanha.get("cliente")),
        "agency": text(dados.get("agencia") or campanha.get("agencia")),
        "campaign": text(row.get("nome_campanha") or dados.get("nome_campanha")),
        "budget": text(row.get("budget") or campanha.get("verba") or dados.get("verba")),
        "period": text(row.get("prazo") or campanha.get("periodo") or dados.get("periodo")),
        "market": PRACA_OPTIONS.get(praca_key, {}).get("label", praca_key),
        "objective": objetivo_label(text(row.get("objetivo") or dados.get("objetivo") or campanha.get("objetivo"))),
    }


def folha_text(folha: dict) -> str:
    lines = []
    for section in as_list((folha or {}).get("sections")):
        for card in as_list(as_dict(section).get("cards")):
            item = as_dict(card)
            title = text(item.get("title") or item.get("type"))
            body = text(item.get("body"))
            if not body:
                continue
            lines.append(f"### {title}\n{body}" if title else body)
    return "\n\n".join(lines)


def materialize_folha(token: str, presenter_id: str | None = None) -> dict:
    row = get_by_token(token)
    if not row:
        raise ValueError("Plano não encontrado.")
    dados = as_dict(row.get("dados_detectados"))
    briefing = text(row.get("briefing_melhorado") or row.get("briefing_compilado"))
    campanha = as_dict(dados.get("campanha"))
    apoio = apoio_notes(dados, cap=6000)
    meta = _row_meta(row, dados)
    if not briefing and not meta.get("client"):
        raise ValueError("Informe o cliente final ou o briefing antes de montar a página única.")
    chosen = text(presenter_id) or text(dados.get("presenter_brand")) or "centralcomm"
    page = as_dict(dados.get("one_page_v2"))
    if text(as_dict(page.get("thesis")).get("statement")):
        branding = one_page.resolve_branding(
            meta.get("client"),
            meta.get("agency"),
            chosen,
            [],
            cliente_id=dados.get("cliente_id"),
            agencia_id=dados.get("agencia_id"),
            brand=as_dict(dados.get("brand")),
        )
        theme = one_page.compose_theme(meta.get("client"), meta.get("agency"), briefing, None)
        share = one_page.share_payload(text(dados.get("public_token")), meta.get("client"))
        plan = one_page.assemble_from_v2(
            {**meta, "presenter": branding["presenter"]["id"]},
            branding,
            theme,
            share,
            page,
            as_dict(dados.get("strategy_core")),
            text(as_dict(dados.get("snapshot")).get("snapshot_id")),
        )
        merge_dados(token, {
            "folha": plan,
            "presenter_brand": plan["meta"]["presenter"],
            "public_token": plan["share"]["public_token"],
        })
        return plan
    plan = one_page.build_one_page(
        meta,
        briefing,
        text(dados.get("planejamento")),
        campanha,
        chosen,
        text(dados.get("public_token")),
        brand=as_dict(dados.get("brand")),
        cliente_id=dados.get("cliente_id"),
        agencia_id=dados.get("agencia_id"),
        apoio=apoio,
    )
    merge_dados(token, {
        "folha": plan,
        "presenter_brand": plan["meta"]["presenter"],
        "public_token": plan["share"]["public_token"],
    })
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
    meta = _row_meta(row, dados)
    if mode != "one_page" and not planejamento and not briefing:
        raise ValueError("Gere o planejamento antes de abrir o canvas.")
    if mode == "one_page" and not briefing and not meta.get("client"):
        raise ValueError("Informe o cliente final ou o briefing antes de montar a página única.")
    with bound_session(token):
        if mode == "one_page":
            plan = materialize_folha(token, presenter_id)
            row = update_session(token, {
                "plan_content": plan,
                "schema_version": 3,
                "canvas_layout": {
                    "mode": mode,
                    "generatedAt": plan["meta"]["updatedAt"],
                    "presenter": plan["meta"]["presenter"],
                },
            })
            return {"plan": plan, "session": row}
        folha = as_dict(dados.get("folha"))
        if not as_list(folha.get("sections")):
            folha = materialize_folha(token, presenter_id)
        parsed = chat_json(
            load_skill("planner_canvas_v2") or CANVAS_PROMPT,
            json.dumps(
                {
                    "plan_mode": mode,
                    "meta": meta,
                    "marca": as_dict(dados.get("brand")),
                    "briefing": briefing[:12000],
                    "planejamento": planejamento[:20000],
                    "pagina_unica": folha_text(folha),
                    "campanha": campanha,
                },
                ensure_ascii=False,
            ),
            role="compose",
        )
        plan = normalize_plan(parsed if isinstance(parsed, dict) else {}, mode, meta)
        if _card_count(plan) < 4:
            plan = _fill_from_groups(plan, dados)
        row = update_session(token, {
            "plan_content": plan,
            "schema_version": 2,
            "canvas_layout": {"mode": mode, "generatedAt": plan["meta"]["updatedAt"]},
        })
        return {"plan": plan, "session": row}


def _card_count(plan: dict) -> int:
    return sum(len(as_list(as_dict(section).get("cards"))) for section in as_list((plan or {}).get("sections")))


def _fill_from_groups(plan: dict, dados: dict) -> dict:
    groups = as_dict((dados or {}).get("planejamento_grupos"))
    core = as_dict((dados or {}).get("strategy_core"))
    page = as_dict((dados or {}).get("one_page_v2"))
    thesis = text(core.get("central_thesis")) or text(as_dict(page.get("thesis")).get("statement"))
    bodies = {
        "context": [
            ("summary", "Resumo", text(groups.get("strategy")) or text((dados or {}).get("planejamento"))),
        ],
        "strategy": [
            ("recommendation", "Tese", thesis),
            ("summary", "Estratégia", text(groups.get("strategy"))),
        ],
        "media": [
            ("channel-mix", "Mídia e mix", text(groups.get("media"))),
        ],
        "execution": [
            ("next-steps", "Execução", text(groups.get("execution"))),
            ("summary", "Defesa comercial", text(groups.get("defense"))),
        ],
    }
    filled = dict(plan or {})
    sections = []
    for section in as_list(filled.get("sections")):
        item = dict(section)
        if as_list(item.get("cards")):
            sections.append(item)
            continue
        cards = []
        for index, (kind, title, body) in enumerate(bodies.get(item.get("id"), ())):
            excerpt = _plain_excerpt(body)
            if not excerpt:
                continue
            cards.append({
                "id": f"{item.get('id')}-{index}",
                "type": kind,
                "title": title,
                "body": excerpt,
                "items": [],
            })
        item["cards"] = cards
        sections.append(item)
    filled["sections"] = sections
    return filled


def _plain_excerpt(body: str, limit: int = 1800) -> str:
    raw = text(body).strip()
    parsed = extract_json(raw)
    if isinstance(parsed, dict):
        bits = []
        for key in ("why_this_plan", "why_this_mix", "expected_benefits"):
            bits.extend(text(item) for item in as_list(parsed.get(key)) if text(item))
        if text(parsed.get("approval_argument")):
            bits.append(text(parsed.get("approval_argument")))
        raw = "\n".join(bits) or raw
    lines = []
    for line in raw.splitlines():
        if line.strip().startswith("```"):
            continue
        lines.append(re.sub(r"^#+\s*", "", line).strip())
    return "\n".join(part for part in lines if part).strip()[:limit]


def save_plan(token: str, plan: dict) -> dict:
    row = get_by_token(token)
    dados = as_dict(row.get("dados_detectados") if row else {})
    mode = plan_mode_of(dados)
    meta = as_dict(plan.get("meta")) if isinstance(plan, dict) else {}
    branding = as_dict(plan.get("branding")) if isinstance(plan, dict) else {}
    normalized = normalize_plan(plan if isinstance(plan, dict) else {}, mode, meta, branding)
    return update_session(token, {"plan_content": normalized})
