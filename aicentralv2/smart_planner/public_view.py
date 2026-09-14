"""Documento público do Smart Planner — só folha e plano, marca Centralcomm."""

from __future__ import annotations

import re

from .catalog import CHANNEL_CATALOG, CHANNEL_LOGOS, OBJETIVO_OPTIONS, PRACA_OPTIONS, objetivo_label
from .helpers import as_bool, as_dict, as_list, normalize_markdown, plan_mode_of, session_title, text
from .mix import METHODS
from .share import HOUSE, public_sheet_url

CHANNEL_COLORS = {
    "google_ads": "#4285F4",
    "gpt_ads": "#10A37F",
    "youtube": "#E11D2E",
    "meta_ads": "#1877F2",
    "tiktok": "#121212",
    "linkedin": "#0A66C2",
    "dv360": "#34A853",
    "spotify": "#1DB954",
    "netflix": "#B81D24",
    "prime_video": "#00A8E1",
    "disney": "#113CCF",
    "hbo_max": "#B525DE",
    "globoplay": "#E31C23",
    "serasa": "#00A3E0",
    "g1": "#C4170C",
    "uol": "#003399",
    "r7": "#E30613",
    "cnn": "#CC0000",
    "interativos": "#1e4d4f",
    "places": "#167a3a",
    "ooh": "#1e4d4f",
}

GROUP_ROLE = {
    "performance": "Captação de demanda",
    "social": "Engajamento",
    "video": "Consideração",
    "ctv": "Presença em tela",
    "portais": "Contexto editorial",
    "places": "Presença no sítio",
    "programmatic": "Alcance e eficiência",
    "audio": "Frequência em áudio",
    "data": "Base e crédito",
    "ooh": "Lembrança de rua",
}

DENSITY_LABELS = {
    "serasa", "redes", "interativo", "ctv", "marketplace", "retarget",
    "portal", "app", "loja", "campo",
}

FACT_LIMIT = 72
METHOD_LABELS = {item["id"]: item["label"] for item in METHODS}

BOARD_IDS = ("context", "strategy", "media", "execution")
SHEET_TYPES = ("strategy", "creative", "market", "defense")


def _cards(plan: dict) -> list[dict]:
    out = []
    for section in as_list((plan or {}).get("sections")):
        for card in as_list(as_dict(section).get("cards")):
            item = as_dict(card)
            if text(item.get("body") or item.get("title") or item.get("image_url") or item.get("stat")):
                out.append(item)
    return out


def _is_board(plan: dict) -> bool:
    ids = {text(as_dict(section).get("id")) for section in as_list((plan or {}).get("sections"))}
    return bool(ids & set(BOARD_IDS))


def _sheet_cards(plan: dict) -> dict:
    found = {}
    for card in _cards(plan):
        kind = text(card.get("type"))
        if kind in SHEET_TYPES and kind not in found:
            found[kind] = card
    return found


def _is_real_stat(stat: str) -> bool:
    value = text(stat).lower()
    return bool(value) and value != "premissa" and "informe" not in value


def _as_pct(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _clip(value: str, limit: int = FACT_LIMIT) -> str:
    raw = re.sub(r"\s+", " ", text(value)).strip()
    if len(raw) <= limit:
        return raw
    cut = raw[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def _first_sentence(value: str, limit: int = 140) -> str:
    raw = re.sub(r"\s+", " ", text(value)).strip()
    if not raw:
        return ""
    match = re.split(r"(?<=[.!?])\s+", raw, maxsplit=1)
    return _clip(match[0], limit)


def _looks_like_density(channels: list[dict]) -> bool:
    if not channels:
        return True
    known = 0
    density = 0
    for item in channels:
        key = text(item.get("id"))
        label = text(item.get("label")).lower()
        if key in CHANNEL_CATALOG:
            known += 1
        elif label in DENSITY_LABELS:
            density += 1
    return known == 0 and density > 0


def _decorate_channel(item: dict) -> dict:
    key = text(item.get("id"))
    meta = CHANNEL_CATALOG.get(key) or {}
    label = text(item.get("label") or meta.get("label") or key)
    group = text(meta.get("group") or item.get("group"))
    pct = _as_pct(item.get("pct") or item.get("value"))
    return {
        "id": key or label.lower().replace(" ", "_"),
        "label": label,
        "pct": pct,
        "amount_label": text(item.get("amount_label")),
        "role": text(item.get("role") or GROUP_ROLE.get(group)),
        "format": text(meta.get("desc")),
        "logo": CHANNEL_LOGOS.get(key, ""),
        "color": CHANNEL_COLORS.get(key, "#1e4d4f"),
        "group": group,
    }


def _channels_from_mix(campos: dict) -> list[dict]:
    mix = as_dict((campos or {}).get("mix"))
    rows = []
    for item in as_list(mix.get("weights")):
        row = as_dict(item)
        key = text(row.get("id"))
        if key not in CHANNEL_CATALOG:
            continue
        rows.append(_decorate_channel(row))
    return rows


def _method_label(raw: str) -> str:
    key = text(raw).lower()
    if key in METHOD_LABELS:
        return METHOD_LABELS[key]
    return text(raw)


def _highlights(
    strategy: str,
    defense: str,
    objective: str,
    method: str,
    channels: list[dict] | None = None,
    months: list[dict] | None = None,
    how: str = "",
) -> list[dict]:
    out = []
    rows = channels or []
    timeline = months or []
    objective_name = objetivo_label(objective) or text(objective)
    if objective_name and _first_sentence(strategy, 110):
        out.append({
            "title": f"Foco em {objective_name.lower()}",
            "text": _first_sentence(strategy, 110),
        })
    groups = {text(item.get("group")) for item in rows}
    street = groups & {"ooh", "places"}
    digital = {item for item in groups if item and item not in {"ooh", "places"}}
    if street and digital:
        out.append({
            "title": "Digital e rua",
            "text": "O mix junta captura de demanda e lembrança fora da tela.",
        })
    if len(rows) >= 3:
        out.append({
            "title": "Canais no mesmo plano",
            "text": _clip(" · ".join(text(item.get("label")) for item in rows if text(item.get("label"))), 110),
        })
    if len(timeline) > 1 and _first_sentence(how, 110):
        out.append({"title": "Ritmo no período", "text": _first_sentence(how, 110)})
    elif _first_sentence(defense, 110):
        out.append({"title": method or "Defesa do mix", "text": _first_sentence(defense, 110)})
    return out[:4]


def _attach_bars(channels: list[dict], months: list[dict], calendar: dict | None) -> list[dict]:
    rows = {text(item.get("id")): as_dict(item) for item in as_list(as_dict(calendar).get("rows"))}
    for channel in channels:
        match = rows.get(text(channel.get("id")))
        cells = as_list(as_dict(match).get("cells"))
        bars = []
        for index, month in enumerate(months):
            cell = as_dict(cells[index] if index < len(cells) else {})
            pct = _as_pct(cell.get("pct")) if cells and index < len(cells) else _as_pct(channel.get("pct"))
            bars.append({
                "pct": pct,
                "amount_label": text(cell.get("valor_label") or month.get("amount_label")),
            })
        channel["bars"] = bars
    return channels


def _donut_style(channels: list[dict]) -> str:
    if not channels:
        return ""
    cursor = 0
    stops = []
    for item in channels:
        nxt = cursor + max(item.get("pct") or 0, 0)
        stops.append(f"{item['color']} {cursor}% {nxt}%")
        cursor = nxt
    if cursor < 100:
        stops.append(f"#e6ecee {cursor}% 100%")
    return "conic-gradient(" + ", ".join(stops) + ")"


def _media_board(folha: dict, campos: dict | None = None) -> dict:
    media = as_dict((folha or {}).get("media"))
    channels = []
    for row in as_list(media.get("channels")):
        item = as_dict(row)
        label = text(item.get("label") or item.get("id"))
        if not label:
            continue
        channels.append(_decorate_channel(item))
    if _looks_like_density(channels):
        mix_rows = _channels_from_mix(campos or {})
        if mix_rows:
            channels = mix_rows
    if not channels:
        theme = as_dict((folha or {}).get("theme"))
        for row in as_list(theme.get("density")):
            item = as_dict(row)
            label = text(item.get("label"))
            if not label:
                continue
            channels.append(_decorate_channel({
                "label": label,
                "pct": item.get("value") or item.get("pct"),
                "amount_label": item.get("amount_label"),
                "role": item.get("role"),
            }))
    pace = as_dict(media.get("pace"))
    months = []
    for row in as_list(pace.get("months")):
        item = as_dict(row)
        if text(item.get("label")):
            months.append({
                "label": text(item.get("label")),
                "amount_label": text(item.get("amount_label")),
                "amount": _as_pct(item.get("amount")),
            })
    peak = max((item["amount"] for item in months), default=0) or 1
    for item in months:
        item["bar"] = max(12, round((item["amount"] or 0) / peak * 56))
    how = text(pace.get("how"))
    note = text(as_dict((folha or {}).get("theme")).get("density_note") or how)
    if months and note == how:
        note = ""
    method = _method_label(media.get("method_label") or media.get("method") or as_dict((campos or {}).get("mix")).get("method"))
    calendar = as_dict(media.get("calendar"))
    _attach_bars(channels, months, calendar)
    return {
        "method_label": method,
        "channels": channels,
        "months": months,
        "how": how,
        "note": note,
        "donut": _donut_style(channels),
        "total_pct": sum(item.get("pct") or 0 for item in channels),
    }


def _is_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.count("|") >= 2


def _is_sep_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells if cell)


def _blocks(raw: str) -> list[dict]:
    lines = raw.replace("\r\n", "\n").split("\n")
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_table_row(line):
            rows = []
            while i < len(lines) and _is_table_row(lines[i]):
                cells = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
                if not _is_sep_row(cells):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append({"type": "table", "head": rows[0], "rows": rows[1:]})
            continue
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            items = []
            while i < len(lines) and lines[i].strip().startswith(("- ", "* ")):
                items.append(lines[i].strip()[2:].strip())
                i += 1
            if items:
                blocks.append({"type": "ul", "items": items})
            continue
        if stripped:
            chunk = [stripped]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip() or nxt.startswith("##") or _is_table_row(nxt) or nxt.strip().startswith(("- ", "* ")):
                    break
                chunk.append(nxt.strip())
                i += 1
            blocks.append({"type": "p", "text": " ".join(chunk)})
            continue
        i += 1
    return blocks


def plan_chapters(markdown: str) -> list[dict]:
    body = normalize_markdown(markdown).strip()
    if not body:
        return []
    chapters: list[dict] = []
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            if current:
                chapters.append(current)
            current = {"title": line[3:].strip(), "blocks": []}
            continue
        if current is None:
            current = {"title": "", "blocks": []}
        current.setdefault("_lines", []).append(line)
    if current:
        chapters.append(current)
    out = []
    for chapter in chapters:
        blocks = _blocks("\n".join(chapter.pop("_lines", [])))
        if chapter["title"] or blocks:
            out.append({"title": chapter["title"], "blocks": blocks})
    return out


def public_view(row: dict) -> dict:
    dados = as_dict(row.get("dados_detectados"))
    plan = as_dict(row.get("plan_content"))
    share = as_dict(plan.get("share") or as_dict(as_dict(dados.get("folha")).get("share")))
    token = text(share.get("public_token") or dados.get("public_token"))
    url = text(share.get("url")) or public_sheet_url(token)
    folha = as_dict(dados.get("folha"))
    folha_media = as_dict(folha.get("media"))
    has_folha_media = bool(
        as_list(folha_media.get("channels"))
        or as_list(as_dict(folha_media.get("pace")).get("months"))
        or as_list(as_dict(folha.get("theme")).get("density"))
    )
    if not _cards(folha) and not has_folha_media and plan and not _is_board(plan):
        folha = plan
    sheet = _sheet_cards(folha)
    board = plan if _is_board(plan) else {}
    board_sections = []
    for section in as_list(board.get("sections")):
        item = as_dict(section)
        cards = [as_dict(card) for card in as_list(item.get("cards")) if text(as_dict(card).get("body") or as_dict(card).get("title"))]
        if cards:
            board_sections.append({"id": text(item.get("id")), "title": text(item.get("title") or item.get("id")), "cards": cards})
    chapters = plan_chapters(text(dados.get("planejamento")))
    branding = as_dict(folha.get("branding") or board.get("branding"))
    meta = as_dict(folha.get("meta") or board.get("meta"))
    campanha = as_dict(dados.get("campanha"))
    title = session_title(row, dados)
    confidential = as_bool(dados.get("anunciante_confidencial"))
    raw_client = text(meta.get("client") or row.get("cliente") or dados.get("cliente") or campanha.get("cliente"))
    client = "Confidencial" if confidential else raw_client
    if title == "Anunciante":
        title = text(meta.get("campaign") or campanha.get("campanha")) or "Campanha confidencial"
    period = text(meta.get("period") or row.get("prazo") or campanha.get("periodo") or dados.get("periodo"))
    media = _media_board(folha, campanha)
    canais = text(meta.get("canais"))
    method = text(media.get("method_label"))
    if canais and method and f" · {method}" in canais:
        canais = canais.replace(f" · {method}", "").strip()
    objective = text(meta.get("objective") or row.get("objetivo") or campanha.get("objetivo"))
    objective_label = OBJETIVO_OPTIONS.get(objective.lower(), objective) if objective else ""
    if not objective_label:
        objective_label = objetivo_label(objective)
    audience = text(meta.get("publico") or row.get("publico_alvo") or dados.get("publico") or campanha.get("publico"))
    praca_key = text(meta.get("market") or campanha.get("praca"))
    praca = text((PRACA_OPTIONS.get(praca_key.lower()) or {}).get("label") or praca_key)
    praca_detalhe = text(campanha.get("praca_detalhe") or meta.get("market_detail"))
    verba = text(meta.get("budget") or row.get("budget") or campanha.get("verba") or dados.get("verba"))
    if verba.lower() in {"a fechar", "a definir", "-"}:
        verba = ""
    public_fact = audience if audience and len(audience) <= FACT_LIMIT else (_clip(audience, 36) if audience else "")
    facts = [
        item
        for item in (
            ("Anunciante", client if client and client != title else "", "anunciante"),
            ("Objetivo", objective_label, "objetivo"),
            ("Público", public_fact, "publico"),
            ("Praça", praca, "praca"),
            ("Período", period, "periodo"),
            ("Canais", canais, "canais"),
        )
        if item[1]
    ]
    strategy = as_dict(sheet.get("strategy"))
    defense = as_dict(sheet.get("defense"))
    creative = as_dict(sheet.get("creative"))
    theme = as_dict(folha.get("theme") or branding.get("theme"))
    hero_image = text(theme.get("bg_url") or creative.get("image_url") or as_dict(branding.get("hero")).get("image"))
    tagline = _first_sentence(strategy.get("body"), 160)
    highlights = _highlights(
        text(strategy.get("body")),
        text(defense.get("body")),
        objective,
        method,
        media.get("channels"),
        media.get("months"),
        text(media.get("how")),
    )
    tem_folha = bool(sheet) or bool(media.get("channels") or media.get("months"))
    tem_completo = bool(chapters or board_sections)
    return {
        "house": HOUSE,
        "title": title,
        "client": client,
        "confidential": confidential,
        "mode": plan_mode_of(dados, "one_page"),
        "facts": [(item[0], item[1]) for item in facts],
        "fact_items": facts,
        "audience": audience if audience and len(audience) > FACT_LIMIT else "",
        "branding": branding,
        "sheet": sheet,
        "media": media,
        "hero": {
            "image": hero_image,
            "kicker": "Planejamento de mídia",
            "tagline": tagline,
            "caption": praca_detalhe or praca,
            "verba": verba,
        },
        "highlights": highlights,
        "reading": {
            "method": method,
            "defense": _first_sentence(defense.get("body"), 160),
        },
        "show_market": _is_real_stat(text(as_dict(sheet.get("market")).get("stat"))),
        "tem_folha": tem_folha,
        "tem_completo": tem_completo,
        "chapters": chapters,
        "board": board_sections,
        "share_url": url,
        "public_token": token,
        "default_tab": "folha" if tem_folha or not tem_completo else "plano",
    }
