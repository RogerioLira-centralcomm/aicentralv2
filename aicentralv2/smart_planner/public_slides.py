"""Apresentação da proposta pública: o plano em slides 16:9, prontos para mostrar ao cliente.

Cada slide é um canvas de 1600 x 900 que a página escala para caber na tela, sem rolagem no
desktop. Para isso o conteúdo precisa caber: aqui cada bloco tem um orçamento de caracteres e de
itens, e o que não cabe fica para o documento completo (link no topo). Slides sem conteúdo saem.
"""

from __future__ import annotations

import re
from typing import Any

from .helpers import as_dict, as_list, short_title, text

# Orçamento de texto por bloco, medido no canvas de 1600 x 900 com as fontes do template.
LIMITS = {
    "title": 64,
    "statement": 210,
    "support": 300,
    "block": 380,
    "step": 150,
    "item": 170,
    "role": 120,
    "note": 220,
}


def clip(value: Any, limit: int) -> str:
    """Corta em palavra inteira e marca o corte; o texto completo segue no documento."""
    raw = re.sub(r"\s+", " ", text(value)).strip()
    if len(raw) <= limit:
        return raw
    cut = raw[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:—- ") + "…"


def _first_sentences(value: Any, limit: int) -> str:
    """Frases inteiras até o limite; só corta no meio quando a primeira já não cabe."""
    raw = re.sub(r"\s+", " ", text(value)).strip()
    if len(raw) <= limit:
        return raw
    out = ""
    for sentence in re.split(r"(?<=[.!?])\s+", raw):
        if len(out) + len(sentence) + 1 > limit:
            break
        out = f"{out} {sentence}".strip()
    return out or clip(raw, limit)


def _cover(view: dict) -> dict:
    identity = as_dict(view.get("cover_identity"))
    facts = [
        {"label": label, "value": clip(value, 60)}
        for label, value in as_list(view.get("facts"))
        if text(label) not in {"Anunciante", "Público"} and text(value)
    ][:4]
    return {
        "type": "cover",
        "nav": "Capa",
        "title": short_title(identity.get("campaign") or view.get("title"), 70),
        "client": text(identity.get("client") or view.get("client")),
        "agency": text(identity.get("agency")),
        "logo": text(view.get("brand_logo")),
        "image": text(as_dict(view.get("hero")).get("creative_image") or as_dict(view.get("hero")).get("image")),
        "facts": facts,
        "label": text(view.get("document_label")) or "Plano de mídia",
    }


def _thesis(view: dict) -> dict | None:
    statement = _first_sentences(view.get("overview"), LIMITS["statement"])
    if not statement:
        return None
    support = text(view.get("overview_support"))
    return {
        "type": "thesis",
        "nav": "A decisão",
        "kicker": "A decisão",
        "statement": statement,
        "support": _first_sentences(support, LIMITS["support"]) if support and support != text(view.get("overview")) else "",
    }


def _context(view: dict) -> dict | None:
    editorial = as_dict(view.get("editorial_context"))
    blocks = []
    for key, fallback in (("challenge", "O desafio"), ("opportunity", "A oportunidade")):
        block = as_dict(editorial.get(key))
        if text(block.get("body")):
            blocks.append({
                "kicker": fallback,
                "title": short_title(block.get("title") or fallback, LIMITS["title"]),
                "body": _first_sentences(block.get("body"), LIMITS["block"]),
            })
    if not blocks:
        return None
    return {"type": "context", "nav": "Contexto", "kicker": "Contexto e oportunidade", "blocks": blocks}


def _audience(view: dict) -> dict | None:
    audience = text(view.get("audience"))
    steps = [
        {"title": short_title(as_dict(item).get("title"), 48), "body": clip(as_dict(item).get("body"), LIMITS["step"])}
        for item in as_list(as_dict(view.get("editorial_context")).get("journey"))
        if text(as_dict(item).get("title"))
    ][:4]
    if not audience and not steps:
        return None
    return {
        "type": "audience",
        "nav": "Público e jornada",
        "kicker": "Público e jornada",
        "audience": _first_sentences(audience, 260),
        "steps": steps,
    }


def _creative(view: dict) -> dict | None:
    concept = text(view.get("concept"))
    if not concept:
        return None
    outputs = [
        {"name": clip(as_dict(item).get("name"), 48), "body": clip(as_dict(item).get("description"), 110)}
        for item in as_list(as_dict(view.get("editorial_context")).get("outputs"))
        if text(as_dict(item).get("name"))
    ][:3]
    hero = as_dict(view.get("hero"))
    return {
        "type": "creative",
        "nav": "Criativo",
        "kicker": "Criativo no canal",
        "title": short_title(concept, 80),
        "body": _first_sentences(view.get("concept_body"), 260),
        "image": text(hero.get("creative_image") or as_dict(hero.get("support_image")).get("url")),
        "outputs": outputs,
    }


def _share_bar(view: dict) -> list[dict]:
    """Uma barra só: frentes, quando houver, ou canais. Mais que isso vira gráfico com linhas demais."""
    fronts = [as_dict(front) for front in as_list(view.get("fronts")) if as_dict(front).get("weight")]
    if fronts:
        return [{"label": text(front.get("label")), "pct": round(float(front["weight"]))} for front in fronts]
    channels = [as_dict(c) for c in as_list(as_dict(view.get("media")).get("channels")) if as_dict(c).get("pct")]
    return [{"label": text(c.get("label")), "pct": int(c.get("pct") or 0)} for c in channels][:6]


def _flight(view: dict) -> list[dict]:
    months = [as_dict(m) for m in as_list(as_dict(view.get("media")).get("months")) if text(as_dict(m).get("label"))]
    if len(months) < 2:
        return []
    peak = max((int(m.get("amount") or 0) for m in months), default=0) or 1
    return [
        {"label": text(m.get("full_label") or m.get("label")), "value": text(m.get("amount_label")),
         "height": max(8, round(int(m.get("amount") or 0) * 100 / peak))}
        for m in months[:12]
    ]


def _media(view: dict) -> dict | None:
    if not view.get("has_approved_mix"):
        return None
    media = as_dict(view.get("media"))
    narrative = as_dict(as_dict(view.get("editorial_context")).get("media"))
    fronts = []
    for front in as_list(view.get("fronts")):
        row = as_dict(front)
        if text(row.get("tipo")) == "outros":
            continue
        fronts.append({
            "label": text(row.get("label")),
            "weight": round(float(row["weight"])) if row.get("weight") else None,
            "text": _first_sentences(row.get("text"), 170),
            "tags": [clip(tag, 34) for tag in as_list(row.get("formats"))][:4] + ([text(row.get("segment"))] if text(row.get("segment")) else []),
        })
    channels = [
        {"label": text(c.get("label")), "pct": c.get("pct"), "role": clip(c.get("role"), LIMITS["role"]), "color": text(c.get("color"))}
        for c in (as_dict(item) for item in as_list(media.get("channels")))
    ][:6]
    return {
        "type": "media",
        "nav": "Estratégia de mídia",
        "kicker": "Estratégia de mídia",
        "title": short_title(narrative.get("decision") or "Como a verba trabalha", 90),
        "share": _share_bar(view),
        "fronts": fronts[:2],
        "channels": [] if fronts else channels,
        "flight": _flight(view),
    }


def _formats(view: dict) -> dict | None:
    by_channel = as_dict(view.get("formats_by_channel"))
    labels = {text(as_dict(c).get("id")): text(as_dict(c).get("label")) for c in as_list(as_dict(view.get("media")).get("channels"))}
    groups = []
    for channel_id, rows in by_channel.items():
        items = [as_dict(row) for row in as_list(rows)]
        if items:
            groups.append({
                "channel": labels.get(channel_id, channel_id),
                "formats": [{"name": clip(item.get("nome"), 40), "aggregated": bool(item.get("custo_agregado"))} for item in items][:10],
                "more": max(0, len(items) - 10),
            })
    sites = as_dict(view.get("network_sites"))
    site_names = [text(as_dict(site).get("name")) for site in as_list(sites.get("sites")) if text(as_dict(site).get("name"))][:10]
    if not groups and not site_names:
        return None
    return {
        "type": "formats",
        "nav": "Formatos e portais",
        "kicker": "Formatos e rede de portais",
        "groups": groups[:3],
        "aggregated": [clip(name, 40) for name in as_list(view.get("aggregated_formats"))][:6],
        "sites": site_names,
        "sites_total": int(sites.get("total") or 0),
        "segment": text(as_dict(sites.get("criterios")).get("segmento")),
    }


def _impact(view: dict) -> dict | None:
    impact = as_dict(view.get("impact"))
    if not as_list(impact.get("rows")):
        return None
    indicator = as_dict(impact.get("indicator"))
    return {
        "type": "impact",
        "nav": "Estimativa de impacto",
        "kicker": "Estimativa de impacto",
        "origin": text(impact.get("origin_label")),
        "reviewed": bool(impact.get("reviewed")),
        "cards": as_list(impact.get("cards"))[:4],
        "indicator": indicator if indicator.get("label") else {},
        "rows": as_list(impact.get("rows"))[:5],
        "note": "Estimativa de referência, não promessa de resultado. " + text(impact.get("reach_note")),
    }


def _defense(view: dict) -> dict | None:
    groups = []
    for group in as_list(view.get("defense_groups")):
        row = as_dict(group)
        items = [clip(item, LIMITS["item"]) for item in as_list(row.get("items")) if text(item)][:3]
        if items:
            groups.append({"title": short_title(row.get("title"), 40), "items": items})
    if not groups:
        return None
    return {"type": "defense", "nav": "Por que este plano", "kicker": "Defesa do plano", "groups": groups[:3]}


def _market(view: dict) -> dict | None:
    if not view.get("show_market"):
        return None
    market = as_dict(as_dict(view.get("editorial_context")).get("market"))
    insight = text(market.get("insight"))
    if not insight:
        return None
    return {
        "type": "market",
        "nav": "Mercado",
        "kicker": "Dado de mercado",
        "title": short_title(market.get("title") or "Dado de mercado", LIMITS["title"]),
        "stat": clip(market.get("stat"), 24),
        "insight": _first_sentences(insight, 280),
        "source": clip(market.get("source"), 80),
        "source_url": text(market.get("source_url")),
    }


def _contact(view: dict) -> dict:
    executive = as_dict(view.get("executive"))
    return {
        "type": "contact",
        "nav": "Próximos passos",
        "kicker": "Próximos passos",
        "name": text(executive.get("name")),
        "photo": text(executive.get("photo_url")),
        "initials": text(executive.get("initials")),
        "whatsapp": text(executive.get("whatsapp_url")),
        "full_plan_url": text(view.get("full_plan_url")) if view.get("tem_completo") else "",
    }


BUILDERS = (_cover, _thesis, _context, _audience, _creative, _media, _formats, _impact, _defense, _market, _contact)


def build_slides(view: dict) -> list[dict]:
    """Slides da proposta, na ordem da conversa com o cliente; os sem conteúdo saem."""
    slides = []
    for builder in BUILDERS:
        slide = builder(as_dict(view))
        if slide:
            slides.append(slide)
    for index, slide in enumerate(slides, start=1):
        slide["index"] = index
    return slides
