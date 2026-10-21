"""Apresentação da proposta pública: o plano em slides 16:9, prontos para mostrar ao cliente.

Cada slide é um canvas de 1600 x 900 que a página escala para caber na tela, sem rolagem no
desktop. Para isso o conteúdo precisa caber: aqui cada bloco tem um orçamento de caracteres e de
itens, e o que não cabe fica para o documento completo (link no topo). Slides sem conteúdo saem.
"""

from __future__ import annotations

import re
from typing import Any

from markupsafe import Markup, escape

from .helpers import as_dict, as_list, short_title, text
from .mockups import channel_logo, mockups_for, showcase_for, site_logo

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
        {"label": label, "value": clip(value, 38)}
        for label, value in as_list(view.get("facts"))
        if text(label) not in {"Anunciante", "Público"} and text(value)
    ][:4]
    title = short_title(identity.get("campaign") or view.get("title"), 70)
    hero = as_dict(view.get("hero"))
    creative = text(hero.get("creative_image")) if hero.get("has_generated_visual") else ""
    mocks = mockups_for(view, creative) if creative else []
    return {
        "type": "cover",
        # Com o criativo do plano, ele vira o fundo da capa e aparece inteiro no mockup do canal.
        "layout": "hero" if creative else "",
        # Arte vertical: o fundo da capa usa a versão horizontal dela, quando existe.
        "background": text(as_dict(hero.get("creative_variants")).get("horizontal")) or creative,
        "mockup": mocks[0] if mocks else {},
        "nav": "Capa",
        "title": title,
        # Títulos longos descem de tamanho em vez de serem cortados com reticências.
        "title_size": "lg" if len(title) <= 32 else "md" if len(title) <= 52 else "sm",
        "client": text(identity.get("client") or view.get("client")),
        "agency": text(identity.get("agency")),
        "logo": text(view.get("brand_logo")),
        "image": text(as_dict(view.get("hero")).get("creative_image") or as_dict(view.get("hero")).get("image")),
        "facts": facts,
        "label": text(view.get("document_label")) or "Plano de mídia",
    }


GENERIC_TITLES = {"tese", "tese central", "a decisão", "decisão", "a tese", "tese do plano"}


def _thesis(view: dict) -> dict | None:
    overview = text(view.get("overview"))
    if not overview:
        return None
    title = text(view.get("overview_title"))
    headline = short_title(title, 70) if title and title.lower().strip(" .") not in GENERIC_TITLES else ""
    # Com manchete, a frase da tese vira o texto de apoio e cabe inteira; sem ela,
    # a frase é o título e desce de tamanho conforme o comprimento, sem reticências.
    # Planos gerados antes da manchete trazem só a frase: ela entra inteira, sem reticências.
    statement = _first_sentences(overview, 300 if headline else 340)
    support = text(view.get("overview_support"))
    return {
        "type": "thesis",
        "nav": "A decisão",
        "kicker": "A decisão",
        "headline": headline,
        "statement": statement,
        "statement_size": "md" if headline or len(statement) <= 130 else "sm" if len(statement) <= 190 else "long",
        "support": _first_sentences(support, LIMITS["support"]) if support and support != overview else "",
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
    image = text(hero.get("creative_image") or as_dict(hero.get("support_image")).get("url"))
    return {
        "type": "creative",
        "nav": "Criativo",
        "kicker": "Criativo no canal",
        "title": short_title(concept, 80),
        "body": _first_sentences(view.get("concept_body"), 260),
        "image": image,
        # O criativo dentro da tela do canal (TV, portal, celular), não solto na página.
        "mockups": mockups_for(view, image),
        "outputs": outputs,
    }


def _showcase(view: dict) -> dict | None:
    """O criativo montado na tela de cada canal do plano, no layout certo de cada um."""
    hero = as_dict(view.get("hero"))
    image = text(hero.get("creative_image")) if hero.get("has_generated_visual") else ""
    screens = showcase_for(view, image)
    if not screens:
        return None
    return {
        "type": "showcase",
        "nav": "Criativo nos canais",
        "kicker": "Criativo nos canais",
        "title": "Como a campanha aparece em cada canal",
        "screens": screens,
        "note": "Simulação com a peça principal. A versão final de cada formato é adaptada na produção.",
    }


def _campaign_arts(view: dict) -> dict | None:
    """As peças da campanha lado a lado: a principal e as extras que o executivo marcou."""
    hero = as_dict(view.get("hero"))
    extras = [as_dict(item) for item in as_list(hero.get("campaign_arts")) if text(as_dict(item).get("url"))]
    main = text(hero.get("creative_image"))
    if not extras or not main or not hero.get("has_generated_visual"):
        return None
    arts = [{"url": main, "shape": text(hero.get("creative_shape")) or "horizontal", "label": "Peça principal"}]
    arts += [{"url": text(item["url"]), "shape": text(item.get("shape")) or "horizontal", "label": f"Peça {index}"} for index, item in enumerate(extras, 2)]
    return {
        "type": "arts",
        "nav": "Criativos da campanha",
        "kicker": "Criativos da campanha",
        "title": "As peças que a campanha usa",
        "arts": arts,
        "note": "A peça principal aparece nas telas dos canais. As demais entram na rotação de criativos.",
    }


def _share_bar(view: dict) -> list[dict]:
    """Uma barra só: frentes, quando houver, ou canais. Mais que isso vira gráfico com linhas demais."""
    fronts = [as_dict(front) for front in as_list(view.get("fronts")) if as_dict(front).get("weight")]
    if fronts:
        return [{"label": text(front.get("label")), "pct": round(float(front["weight"]))} for front in fronts]
    channels = [as_dict(c) for c in as_list(as_dict(view.get("media")).get("channels")) if as_dict(c).get("pct")]
    return [{"label": text(c.get("label")), "pct": int(c.get("pct") or 0)} for c in channels][:6]


WEEK_LABEL = re.compile(r"^\s*S\d+", re.IGNORECASE)


def _periods(view: dict) -> list[dict]:
    return [as_dict(m) for m in as_list(as_dict(view.get("media")).get("months")) if text(as_dict(m).get("label"))]


def _period_unit(months: list[dict]) -> str:
    return "semana" if months and all(WEEK_LABEL.match(text(m.get("label"))) for m in months) else "mês"


def _flight(view: dict) -> list[dict]:
    months = _periods(view)
    if len(months) < 2:
        return []
    peak = max((int(m.get("amount") or 0) for m in months), default=0) or 1
    return [
        {"label": text(m.get("full_label") or m.get("label")), "value": text(m.get("amount_label")),
         "height": max(8, round(int(m.get("amount") or 0) * 100 / peak)),
         "peak": int(m.get("amount") or 0) == peak}
        for m in months[:12]
    ]


def _brl(value: float) -> str:
    return "R$ " + f"{round(value):,}".replace(",", ".")


def _flight_reading(view: dict) -> dict:
    """Leitura do voo para quem decide: total, média, pico e como a verba se distribui no tempo."""
    months = _periods(view)
    amounts = [int(m.get("amount") or 0) for m in months]
    total = sum(amounts)
    if len(months) < 2 or not total:
        return {}
    unit = _period_unit(months)
    plural = "semanas" if unit == "semana" else "meses"
    peak_index = max(range(len(amounts)), key=lambda i: amounts[i])
    half = len(amounts) // 2
    late = sum(amounts[len(amounts) - half:]) * 100 / total if half else 0
    early = sum(amounts[:half]) * 100 / total if half else 0
    first, last = amounts[0], amounts[-1]
    rising = first and last >= first * 1.4 and late > early
    falling = last and first >= last * 1.4 and early > late
    if rising:
        ratio = f"{last / first:.1f}".replace(".", ",").replace(",0", "")
        shape = f"A verba cresce {'semana a semana' if unit == 'semana' else 'mês a mês'}: o fim do voo recebe {ratio}x o começo, com mais peso perto da entrega."
    elif falling:
        shape = f"Começo forte: {round(early)}% da verba na primeira metade, para abrir a campanha com volume."
    else:
        shape = "Distribuição equilibrada no período, sem depender de um único pico."
    peak = months[peak_index]
    return {
        "unit": unit,
        "stats": [
            {"label": "Investimento", "value": _brl(total)},
            {"label": f"Em {len(months)} {plural}", "value": f"{_brl(total / len(months))} por {unit}"},
            {"label": f"Pico · {text(peak.get('full_label') or peak.get('label'))}", "value": f"{round(amounts[peak_index] * 100 / total)}% da verba"},
        ],
        "shape": shape,
    }


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
            "types": [text(t) for t in as_list(row.get("format_types")) if text(t)][:4],
            "tags": [clip(tag, 34) for tag in as_list(row.get("formats"))][:4] + ([text(row.get("segment"))] if text(row.get("segment")) else []),
        })
    channels = [
        {"id": text(c.get("id")), "label": text(c.get("label")), "pct": c.get("pct"), "role": clip(c.get("role"), LIMITS["role"]), "color": text(c.get("color")), "logo": channel_logo(c)}
        for c in (as_dict(item) for item in as_list(media.get("channels")))
    ][:6]
    share = _share_bar(view)
    flight = _flight(view)
    reading = _flight_reading(view)
    # Uma parte só (um canal, sem frentes divididas) não vira barra de 100%: o que informa é o voo.
    solo = len(fronts) <= 1 and len(share) <= 1 and len([c for c in channels if c.get("pct")]) <= 1
    formats = as_dict(view.get("formats_by_channel"))
    solo_channel = {}
    if solo and channels:
        lead = channels[0]
        solo_channel = {
            **lead,
            "formats": [clip(as_dict(f).get("nome"), 34) for f in as_list(formats.get(lead.get("id")))][:5],
            "front": fronts[0] if fronts else {},
        }
    return {
        "type": "media",
        "nav": "Estratégia de mídia",
        "kicker": "Estratégia de mídia",
        "title": short_title(narrative.get("decision") or "Como a verba trabalha", 90),
        "layout": "solo" if solo else ("fronts" if fronts else "mix"),
        "share": [] if solo else share,
        "fronts": [] if solo else fronts[:2],
        "channels": [] if solo or fronts else channels,
        "solo": solo_channel,
        "flight": flight,
        "flight_unit": reading.get("unit") or _period_unit(_periods(view)),
        "reading": reading,
    }


def _formats(view: dict) -> dict | None:
    by_channel = as_dict(view.get("formats_by_channel"))
    media_channels = {text(as_dict(c).get("id")): as_dict(c) for c in as_list(as_dict(view.get("media")).get("channels"))}
    labels = {key: text(c.get("label")) for key, c in media_channels.items()}
    groups = []
    for channel_id, rows in by_channel.items():
        items = [as_dict(row) for row in as_list(rows)]
        if items:
            groups.append({
                "channel": labels.get(channel_id, channel_id),
                "logo": channel_logo(media_channels.get(channel_id) or {"id": channel_id}),
                "formats": [{"name": clip(item.get("nome"), 40), "aggregated": bool(item.get("custo_agregado"))} for item in items][:10],
                "more": max(0, len(items) - 10),
            })
    sites = as_dict(view.get("network_sites"))
    site_names = [text(as_dict(site).get("name")) for site in as_list(sites.get("sites")) if text(as_dict(site).get("name"))][:10]
    site_rows = [{"name": name, "logo": site_logo(name)} for name in site_names]
    if not groups and not site_names:
        return None
    fronts = [
        {"label": text(as_dict(f).get("label")), "types": [text(t) for t in as_list(as_dict(f).get("format_types")) if text(t)]}
        for f in as_list(view.get("fronts"))
        if text(as_dict(f).get("tipo")) != "outros" and as_list(as_dict(f).get("format_types"))
    ][:2]
    hero = as_dict(view.get("hero"))
    image = text(hero.get("creative_image") or as_dict(hero.get("support_image")).get("url"))
    portal = [m for m in mockups_for(view, image, limit=3) if m["kind"] == "portal"] if site_names else []
    return {
        "type": "formats",
        "fronts": fronts,
        # Na Rede de portais, a tela do maior portal mostra onde leaderboard e retângulo aparecem.
        "mockup": portal[0] if portal else {},
        "nav": "Formatos e portais",
        "kicker": "Formatos e rede de portais",
        "groups": groups[:3],
        "aggregated": [clip(name, 40) for name in as_list(view.get("aggregated_formats"))][:6],
        "sites": site_names,
        "site_rows": site_rows,
        "sites_total": int(sites.get("total") or 0),
        "segment": text(as_dict(sites.get("criterios")).get("segmento")),
    }


def _interactives(view: dict) -> dict | None:
    """Os interativos escolhidos, um cartão cada: mecânica, categoria, tamanho e a peça de teste."""
    items = []
    for item in as_list(view.get("interactive_formats"))[:6]:
        item = as_dict(item)
        size = text(item.get("dimensoes")).split("|")[0].replace(" pixels", "").strip()
        meta = [text(item.get("categoria"))] + ([size] if size and "conforme" not in size.lower() else [])
        items.append({
            "name": clip(item.get("nome"), 40),
            "meta": clip(" · ".join(part for part in meta if part), 60),
            "description": clip(item.get("descricao"), 190),
            "demo": text(item.get("demo")),
        })
    if not items:
        return None
    return {"type": "interactives", "nav": "Formatos interativos", "kicker": "Formatos interativos", "cards": items,
            "more": max(0, len(as_list(view.get("interactive_formats"))) - 6)}


def _first_party(view: dict) -> dict | None:
    """Dados do cliente: o que ele fornece e como cada uso entra no plano."""
    data = as_dict(view.get("first_party"))
    if not as_list(data.get("sources")):
        return None
    fronts = {text(as_dict(f).get("tipo")): text(as_dict(f).get("label")) for f in as_list(view.get("fronts"))}
    uses = []
    for use in as_list(data.get("uses")):
        use = as_dict(use)
        where = fronts.get("remarketing") if use.get("id") == "remarketing" else ""
        uses.append({**use, "where": f"Frente de {where.lower()}" if where else ""})
    return {
        "type": "first_party",
        "nav": "Dados do cliente",
        "kicker": "Dados do cliente",
        "title": "Os dados da marca trabalham junto com a mídia",
        "sources": as_list(data.get("sources"))[:6],
        "uses": uses[:3],
        "note": clip(data.get("note"), 160),
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
        "first_name": text(executive.get("first_name")),
        "role": text(executive.get("role")) or "Responsável por este plano",
        "whatsapp": text(executive.get("whatsapp_url")),
        "full_plan_url": text(view.get("full_plan_url")) if view.get("tem_completo") else "",
    }


# Ícone de linha (24 x 24, traço) no título de cada slide, no lugar do traço genérico.
ICONS = {
    "thesis": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "context": '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/>',
    "audience": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M18 14.3a6.5 6.5 0 0 1 3.5 5.7"/>',
    "creative": '<path d="M12 3l1.8 4.9L19 9.7l-5.2 1.8L12 16.5l-1.8-5L5 9.7l5.2-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
    "showcase": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "arts": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M21 16l-5-5-8 8"/>',
    "media": '<path d="M21 12A9 9 0 1 1 12 3v9z"/><path d="M15 3.5A9 9 0 0 1 20.5 9H15z"/>',
    "interactives": '<path d="M9 9l10 4-4 2-2 4z"/><path d="M5 3v4M3 5h4M5 13v4M3 15h4"/>',
    "formats": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "first_party": '<ellipse cx="12" cy="5.5" rx="8" ry="2.5"/><path d="M4 5.5v6c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-6"/><path d="M4 11.5v6c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-6"/>',
    "defense": '<path d="M12 3l8 3v6c0 4.5-3.4 8.2-8 9-4.6-.8-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "market": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "contact": '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-5A8 8 0 1 1 21 12z"/>',
}

# Números que o cliente procura no texto: valores, percentuais e volumes (1,4 mi, 7 mil, 3x).
NUMBER = r"R\$\s?\d+(?:[.,]\d+)*(?:\s?(?:milhões|milhão|bilhões|mil|mi|bi)(?!\w))?|\d+(?:[.,]\d+)*\s?(?:%|(?:milhões|milhão|bilhões|mil|mi|bi)(?!\w))|\d+x(?!\w)"
MAX_EMPHASIS = 3


def emphasis_terms(view: dict) -> list[str]:
    """Nomes que valem negrito em texto corrido: o cliente e os canais do plano."""
    terms = [text(view.get("client")), text(as_dict(view.get("cover_identity")).get("client"))]
    terms += [text(as_dict(c).get("label")) for c in as_list(as_dict(view.get("media")).get("channels"))]
    seen: list[str] = []
    for term in terms:
        if len(term) >= 3 and term.lower() not in {t.lower() for t in seen}:
            seen.append(term)
    return sorted(seen, key=len, reverse=True)


def _emphasis_pattern(terms) -> re.Pattern:
    parts = [NUMBER] + [rf"(?<!\w){re.escape(term)}(?!\w)" for term in terms]
    return re.compile("|".join(f"(?:{part})" for part in parts))


def emphasize(value: Any, terms: list[str] | tuple = (), pattern: re.Pattern | None = None) -> Markup:
    """Texto escapado com até três destaques em negrito (números e nomes), para leitura rápida."""
    raw = text(value)
    if not raw:
        return Markup("")
    pattern = pattern or _emphasis_pattern(terms)
    out, last, used, seen = [], 0, 0, set()
    for match in pattern.finditer(raw):
        key = match.group(0).lower()
        if used >= MAX_EMPHASIS or key in seen:
            continue
        seen.add(key)
        used += 1
        out.append(escape(raw[last:match.start()]))
        out.append(Markup("<strong>%s</strong>") % match.group(0))
        last = match.end()
    out.append(escape(raw[last:]))
    return Markup("").join(out)


def highlighter(view: dict):
    """Função do template: ``{{ hl(texto) }}`` devolve o texto com os destaques do plano."""
    pattern = _emphasis_pattern(emphasis_terms(view))
    return lambda value: emphasize(value, pattern=pattern)


BUILDERS = (_cover, _thesis, _context, _audience, _creative, _showcase, _campaign_arts, _media, _formats, _interactives, _first_party, _defense, _market, _contact)


def _notes(slide: dict, view: dict) -> list[str]:
    """Notas do apresentador: o texto completo que o slide resumiu, para quem conduz a reunião."""
    editorial = as_dict(view.get("editorial_context"))
    kind = slide.get("type")
    notes: list[str] = []
    if kind == "thesis":
        notes = [text(view.get("overview")), text(view.get("overview_support"))]
    elif kind == "context":
        notes = [text(as_dict(editorial.get(key)).get("body")) for key in ("challenge", "opportunity")]
    elif kind == "audience":
        notes = [text(view.get("audience"))] + [
            f"{text(as_dict(step).get('title'))}: {text(as_dict(step).get('body'))}" for step in as_list(editorial.get("journey"))
        ]
    elif kind == "creative":
        notes = [text(view.get("concept_body"))]
    elif kind == "media":
        narrative = as_dict(editorial.get("media"))
        notes = [text(narrative.get(key)) for key in ("decision", "distribution", "flight")]
        notes += [f"{text(as_dict(f).get('label'))}: {text(as_dict(f).get('text'))}" for f in as_list(view.get("fronts"))]
    elif kind == "defense":
        for group in as_list(view.get("defense_groups")):
            notes += [text(item) for item in as_list(as_dict(group).get("items"))]
    elif kind == "market":
        notes = [text(as_dict(editorial.get("market")).get("insight"))]
    elif kind == "interactives":
        notes = [f"{text(as_dict(f).get('nome'))}: {text(as_dict(f).get('descricao'))}" for f in as_list(view.get("interactive_formats"))
                 if text(as_dict(f).get("descricao"))]
    seen: list[str] = []
    for note in notes:
        note = re.sub(r"\s+", " ", note).strip()
        if note and note not in seen:
            seen.append(note)
    return seen[:12]


def build_slides(view: dict) -> list[dict]:
    """Slides da proposta, na ordem da conversa com o cliente; os sem conteúdo saem."""
    slides = []
    for builder in BUILDERS:
        slide = builder(as_dict(view))
        if slide:
            slides.append(slide)
    for index, slide in enumerate(slides, start=1):
        slide["index"] = index
        slide["icon"] = Markup(ICONS.get(slide.get("type"), ""))
        slide["notes"] = _notes(slide, as_dict(view))
    return slides
