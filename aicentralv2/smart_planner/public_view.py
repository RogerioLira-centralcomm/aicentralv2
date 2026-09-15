"""Documento público do Smart Planner — só folha e plano, marca Centralcomm."""

from __future__ import annotations

import re
import os
from datetime import datetime, timezone
from html import escape
import unicodedata

from flask import has_request_context, url_for

from .catalog import CHANNEL_CATALOG, CHANNEL_LOGOS, OBJETIVO_OPTIONS, PRIMARY_FORMATS, PRACA_OPTIONS, objetivo_label
from .helpers import as_bool, as_dict, as_list, normalize_markdown, plan_mode_of, session_title, text
from .mix import METHODS
from .pace import format_money, parse_money
from .share import HOUSE, public_document_url, public_sheet_url

CHANNEL_COLORS = {
    "google_ads": "#4285F4",
    "gpt_ads": "#10A37F",
    "youtube": "#FF0033",
    "meta_ads": "#1684F8",
    "tiktok": "#121212",
    "linkedin": "#0A66C2",
    "dv360": "#7C3AED",
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


def _public_asset_url(value: str) -> str:
    """Make local creative assets usable by social crawlers outside the app."""
    asset = text(value)
    if asset.startswith(("https://", "http://")):
        return asset
    if asset.startswith("/static/") and has_request_context():
        return url_for("static", filename=asset.removeprefix("/static/"), _external=True)
    if asset.startswith("/"):
        base = text(os.getenv("BASE_URL")).rstrip("/")
        return f"{base}{asset}" if base else asset
    return asset


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
            "text": _clip(" · ".join(text(item.get("label")) for item in rows if text(item.get("label"))), 110),
        })
    if len(rows) >= 2:
        out.append({
            "title": "Canais no mesmo plano",
            "text": _clip(" · ".join(
                f"{text(item.get('label'))} {item.get('pct')}%"
                for item in rows
                if text(item.get("label"))
            ), 120),
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
                "amount": _money(item.get("amount") or item.get("amount_label")),
            })
    how = text(pace.get("how"))
    note = text(as_dict((folha or {}).get("theme")).get("density_note") or how)
    if months and note == how:
        note = ""
    method = _method_label(media.get("method_label") or media.get("method") or as_dict((campos or {}).get("mix")).get("method"))
    calendar = as_dict(media.get("calendar"))
    _attach_matrix(channels, months, calendar)
    _attach_week_bars(channels, months)
    peak_amt = max((_money(item.get("amount")) for item in months), default=0) or 1
    for item in months:
        item["bar"] = max(12, round(_money(item.get("amount")) / peak_amt * 56))
        item["flight"] = text(item.get("full_label") or item.get("label"))
    for channel in channels:
        channel["flight_note"] = _flight_note(channel, months)
        channel["role_short"] = _clip(text(channel.get("priority") or channel.get("role") or channel.get("goal")), 42)
    total = sum(_money(item.get("amount")) for item in channels) or sum(_money(item.get("amount")) for item in months)
    average = round(total / len(months)) if months and total else 0
    peak = max(months, key=lambda row: _money(row.get("amount")), default={})
    leader = max(channels, key=lambda row: row.get("pct") or 0, default={})
    weeks = _week_lanes(months)
    return {
        "method_label": method,
        "channels": channels,
        "months": months,
        "how": how,
        "note": note,
        "donut": _donut_style(channels),
        "slices": _donut_slices(channels),
        "weeks": weeks,
        "week_count": sum(len(item.get("weeks") or []) for item in weeks),
        "has_weekly": len(months) >= 1 and bool(channels),
        "total": total,
        "total_label": format_money(total) if total else "",
        "average": average,
        "average_label": format_money(average) if average else "",
        "peak_label": text(peak.get("full_label") or peak.get("label")),
        "peak_amount": text(peak.get("amount_label")),
        "leader_label": text(leader.get("label")),
        "leader_pct": leader.get("pct") or 0,
        "total_pct": sum(item.get("pct") or 0 for item in channels),
        "checks": _finance_checks(channels, months, total),
    }


def _is_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.count("|") >= 2


def _is_sep_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells if cell)


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.+?)\s*$")


def _inline_html(value: str) -> str:
    """Render the small, safe subset of inline Markdown emitted by the planner.

    Content is escaped first.  The public template can therefore safely mark this
    derived value as HTML without turning an LLM response into executable markup.
    """
    out = escape(text(value), quote=False)
    placeholders: list[str] = []

    def code(match):
        placeholders.append(f"<code>{escape(match.group(1), quote=False)}</code>")
        return f"\x00CODE{len(placeholders) - 1}\x00"

    out = re.sub(r"`([^`\n]+)`", code, out)
    out = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)|(?<!_)_([^_\n]+)_(?!_)", lambda m: f"<em>{m.group(1) or m.group(2)}</em>", out)
    for index, item in enumerate(placeholders):
        out = out.replace(f"\x00CODE{index}\x00", item)
    return out


def _consume_list(lines: list[str], start: int, base_indent: int) -> tuple[dict, int]:
    first = _LIST_ITEM.match(lines[start])
    ordered = bool(first and first.group(2)[0].isdigit())
    items: list[dict] = []
    i = start
    while i < len(lines):
        match = _LIST_ITEM.match(lines[i])
        if not match or len(match.group(1).expandtabs(2)) != base_indent:
            break
        is_ordered = match.group(2)[0].isdigit()
        if is_ordered != ordered:
            break
        item = {"html": _inline_html(match.group(3)), "children": []}
        i += 1
        while i < len(lines):
            nested = _LIST_ITEM.match(lines[i])
            if nested and len(nested.group(1).expandtabs(2)) > base_indent:
                child, i = _consume_list(lines, i, len(nested.group(1).expandtabs(2)))
                item["children"].append(child)
                continue
            if not lines[i].strip():
                i += 1
                break
            if nested or len(lines[i]) - len(lines[i].lstrip()) <= base_indent:
                break
            item["html"] += " " + _inline_html(lines[i].strip())
            i += 1
        items.append(item)
    return {"type": "list", "ordered": ordered, "items": items}, i


def _blocks(raw: str) -> list[dict]:
    lines = raw.replace("\r\n", "\n").split("\n")
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            fence = line.strip()[:3]
            language = line.strip()[3:].strip()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith(fence):
                code.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            blocks.append({"type": "code", "language": language, "text": "\n".join(code)})
            continue
        if _is_table_row(line):
            rows = []
            while i < len(lines) and _is_table_row(lines[i]):
                cells = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
                if not _is_sep_row(cells):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append({"type": "table", "head": [_inline_html(cell) for cell in rows[0]], "rows": [[_inline_html(cell) for cell in row] for row in rows[1:]]})
            continue
        stripped = line.strip()
        heading = _HEADING.match(stripped)
        if heading:
            blocks.append({"type": "heading", "level": min(heading.group(1).count("#"), 4), "html": _inline_html(heading.group(2))})
            i += 1
            continue
        list_match = _LIST_ITEM.match(line)
        if list_match:
            block, i = _consume_list(lines, i, len(list_match.group(1).expandtabs(2)))
            blocks.append(block)
            continue
        if stripped:
            chunk = [stripped]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip() or _HEADING.match(nxt.strip()) or _is_table_row(nxt) or _LIST_ITEM.match(nxt) or nxt.strip().startswith("```"):
                    break
                chunk.append(nxt.strip())
                i += 1
            blocks.append({"type": "p", "html": _inline_html(" ".join(chunk))})
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


def format_public_updated(value) -> dict:
    """Human-friendly publication time plus an exact value for hover/audit."""
    raw = text(value)
    if not raw:
        return {"label": "", "title": ""}
    try:
        when = value if isinstance(value, datetime) else datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return {"label": f"Atualizado em {raw}", "title": raw}
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = datetime.now(when.tzinfo)
    seconds = max(0, int((now - when).total_seconds()))
    if seconds < 60:
        label = "Atualizado agora"
    elif seconds < 3600:
        label = f"Atualizado há {seconds // 60} min"
    elif seconds < 86400:
        label = f"Atualizado há {seconds // 3600} h"
    elif seconds < 172800:
        label = f"Atualizado ontem às {when.strftime('%H:%M')}"
    else:
        label = f"Atualizado em {when.strftime('%d/%m/%Y às %H:%M')}"
    return {"label": label, "title": when.isoformat()}


WATER_MARKERS = ("água", "agua", "reservatório", "reservatorio", "torneira")
METRIC_UNDEFINED = "A definir após validação de segmentação, inventário e premissas de compra."
INVENTORY_DISCLAIMER = (
    "Os veículos, plataformas, portais e aplicativos desta seção são ambientes "
    "recomendados ou potenciais. A veiculação final depende de inventário, "
    "segmentação, brand safety, negociação e aprovação."
)
INVENTORY_FILTERS = (
    ("todos", "Todos"),
    ("plataformas", "Plataformas"),
    ("portais", "Portais"),
    ("apps", "Apps"),
    ("nacional", "Nacional"),
    ("regional", "Regional"),
    ("video", "Vídeo"),
    ("social", "Social"),
    ("programatica", "Programática"),
)

OPEN_ITEM_LABELS = {
    "municipios": "Municípios prioritários",
    "datas": "Datas exatas do voo",
    "metricas": "Metas de alcance e frequência",
}

CHANNEL_PLAYBOOK = {
    "youtube": {
        "priority": "Canal líder",
        "funnel": "Sensibilizar",
        "goal": "Liderar alcance, atenção e sensibilização com força audiovisual.",
        "formats": [
            "Vídeo pulável",
            "Vídeo não pulável, se disponível",
            "Bumper de 6 segundos",
            "Vídeos verticais quando houver peça adequada",
            "Sequenciamento de vídeos, se a estratégia suportar",
        ],
        "placements": ["Feed inicial", "Página de exibição", "Shorts", "Inventário de vídeo compatível com a compra"],
        "platforms": ["YouTube"],
        "buy": "Leilão e reserva, conforme disponibilidade",
        "status": "Recomendado",
    },
    "meta_ads": {
        "priority": "Canal de reforço",
        "funnel": "Reforçar",
        "goal": "Aumentar frequência, recorrência e presença cotidiana.",
        "formats": ["Feed", "Stories", "Reels", "Vídeo", "Carrossel", "Peças estáticas"],
        "placements": ["Instagram", "Facebook"],
        "platforms": ["Instagram", "Facebook"],
        "buy": "Leilão nas plataformas Meta",
        "status": "Recomendado",
    },
    "dv360": {
        "priority": "Cobertura complementar",
        "funnel": "Sustentar presença",
        "goal": "Expandir cobertura regional e presença em diferentes contextos de navegação.",
        "formats": ["Display responsivo", "Banners", "Vídeo programático, se aprovado", "Native, se disponível", "Inventário web", "Inventário in-app"],
        "placements": ["Rede de portais e sites", "Aplicativos compatíveis"],
        "platforms": ["DV360"],
        "buy": "Programática via DV360",
        "status": "Sujeito a disponibilidade",
    },
}

CREATIVE_GUIDE = {
    "youtube": [
        {"title": "Filme principal", "note": "Peça-mãe da sensibilização."},
        {"title": "Versões reduzidas", "note": "Cortes para manter a mensagem no voo."},
        {"title": "Bumper", "note": "Seis segundos para lembrança."},
        {"title": "Adaptação vertical", "note": "Shorts e inventário vertical."},
        {"title": "Thumbnail e legendas", "note": "Leitura sem som e área segura."},
    ],
    "meta_ads": [
        {"title": "Vídeo vertical", "note": "Reels e Stories."},
        {"title": "Feed", "note": "Estático ou vídeo curto."},
        {"title": "Carrossel", "note": "Passos práticos da mensagem."},
        {"title": "Variações de copy", "note": "Mesma tese, aberturas diferentes."},
        {"title": "Legendas e área segura", "note": "Mobile em uso cotidiano."},
    ],
    "dv360": [
        {"title": "Display responsivo", "note": "Um mestre para vários recortes."},
        {"title": "Formatos horizontais e mobile", "note": "Portais e apps."},
        {"title": "Native, se aprovado", "note": "Quando o inventário permitir."},
        {"title": "HTML5, se aprovado", "note": "Variação leve por contexto."},
    ],
}

CREATIVE_PRINCIPLES = (
    "Mensagem simples",
    "Benefício coletivo",
    "Ação prática",
    "Repetição consistente",
    "Adaptação para mobile",
    "Legibilidade",
    "Contraste",
    "Legendas em vídeo",
    "Evitar excesso de texto",
)

STRATEGY_LABELS = ("Tese estratégica", "Diretriz", "Objetivo de comunicação")


def _paragraphs(value: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", text(value)) if chunk.strip()]


def _strategy_board(
    parts: list[str],
    audience: str = "",
    concept: str = "",
    support: str = "",
    defense_lead: str = "",
) -> list[dict]:
    """Monta cards só com texto que veio do plano — sem inventar copy."""
    out = []
    for index, body in enumerate(parts[:3]):
        if text(body):
            out.append({"id": f"strategy-{index}", "title": STRATEGY_LABELS[index], "body": text(body)})
    if text(audience):
        out.append({"id": "audience", "title": "Público prioritário", "body": text(audience)})
    if text(defense_lead):
        out.append({"id": "mix-role", "title": "Papel do mix", "body": text(defense_lead)})
    if text(concept):
        out.append({"id": "concept", "title": "Conceito", "body": text(concept)})
    if text(support):
        out.append({"id": "message", "title": "Recomendação de mensagem", "body": text(support)})
    return out


def _funnel_from_channels(channels: list[dict]) -> list[dict]:
    """Jornada = papel de cada canal no mix aprovado, na ordem de peso."""
    rows = sorted(
        [item for item in channels if text(item.get("label"))],
        key=lambda item: (-(item.get("pct") or 0), text(item.get("label"))),
    )
    out = []
    for item in rows:
        stage = text(item.get("funnel") or item.get("priority") or "Presença")
        goal = text(item.get("role") or item.get("goal") or item.get("label"))
        amount = text(item.get("amount_label"))
        pct = item.get("pct") or 0
        detail = goal
        if pct and amount:
            detail = f"{goal} · {pct}% · {amount}"
        elif pct:
            detail = f"{goal} · {pct}%"
        out.append({
            "id": text(item.get("id")) or stage.lower().replace(" ", "-"),
            "title": stage,
            "channel": text(item.get("label")),
            "text": detail,
            "color": text(item.get("color") or "#1e4d4f"),
            "pct": pct,
        })
    return out


def _money(value) -> int:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0, int(round(value)))
    parsed = parse_money(value)
    return max(0, int(parsed.get("valor") or 0))


def _looks_like_water(*parts: str) -> bool:
    blob = " ".join(text(part).lower() for part in parts)
    return any(marker in blob for marker in WATER_MARKERS)


def _month_full(label: str) -> str:
    raw = text(label).lower()
    names = {
        "jan": "Janeiro", "fev": "Fevereiro", "mar": "Março", "abr": "Abril",
        "mai": "Maio", "jun": "Junho", "jul": "Julho", "ago": "Agosto",
        "set": "Setembro", "out": "Outubro", "nov": "Novembro", "dez": "Dezembro",
    }
    for short, full in names.items():
        if raw.startswith(short) or raw == full.lower():
            return full
    return text(label) or "Mês"


def _largest_remainder(total: int, weights: list[int]) -> list[int]:
    if total <= 0 or not weights:
        return [0] * len(weights)
    mass = sum(max(0, item) for item in weights) or len(weights)
    raw = [total * max(0, item) / mass for item in weights]
    base = [int(item) for item in raw]
    gap = total - sum(base)
    order = sorted(range(len(raw)), key=lambda index: (raw[index] - base[index]), reverse=True)
    for index in order[: max(0, gap)]:
        base[index] += 1
    return base


def _matrix_from_calendar(channels: list[dict], months: list[dict], calendar: dict | None) -> list[list[int]] | None:
    rows = {text(item.get("id")): as_dict(item) for item in as_list(as_dict(calendar).get("rows"))}
    if not rows or not channels or not months:
        return None
    grid = []
    filled = False
    for channel in channels:
        cells = as_list(as_dict(rows.get(text(channel.get("id")))).get("cells"))
        line = []
        for index, _month in enumerate(months):
            cell = as_dict(cells[index] if index < len(cells) else {})
            amount = _money(cell.get("valor") or cell.get("amount") or cell.get("valor_label"))
            if amount:
                filled = True
            line.append(amount)
        grid.append(line)
    return grid if filled else None


def _matrix_from_totals(channels: list[dict], months: list[dict]) -> list[list[int]]:
    month_totals = [_money(item.get("amount") or item.get("amount_label")) for item in months]
    channel_totals = [_money(item.get("amount") or item.get("amount_label")) for item in channels]
    weights = [max(item.get("pct") or 0, 0) or 1 for item in channels]
    if not any(month_totals) and any(channel_totals):
        month_totals = _largest_remainder(sum(channel_totals), [1] * len(months) if months else [1])
    if not any(channel_totals) and any(month_totals):
        channel_totals = _largest_remainder(sum(month_totals), weights)
    grid = []
    grand = sum(month_totals) or sum(channel_totals)
    for channel_total, weight in zip(channel_totals, weights):
        if grand and channel_total:
            line = _largest_remainder(channel_total, month_totals)
        else:
            line = [_largest_remainder(month_total, weights)[len(grid)] for month_total in month_totals]
        grid.append(line)
    for month_index, month_total in enumerate(month_totals):
        current = sum(line[month_index] for line in grid)
        delta = month_total - current
        if not delta or not grid:
            continue
        target = max(range(len(grid)), key=lambda index: grid[index][month_index])
        grid[target][month_index] = max(0, grid[target][month_index] + delta)
    return grid


def _attach_matrix(channels: list[dict], months: list[dict], calendar: dict | None) -> list[dict]:
    grid = _matrix_from_calendar(channels, months, calendar) or _matrix_from_totals(channels, months)
    peak = max((max(line) if line else 0) for line in grid) if grid else 1
    for channel, line in zip(channels, grid):
        bars = []
        for index, month in enumerate(months):
            amount = line[index] if index < len(line) else 0
            bars.append({
                "pct": _as_pct(channel.get("pct")),
                "amount": amount,
                "amount_label": format_money(amount) if amount else "—",
                "heat": max(18, round((amount / peak) * 100)) if peak and amount else 0,
            })
        channel["bars"] = bars
        if not channel.get("amount"):
            channel["amount"] = sum(line)
        if not channel.get("amount_label") and channel.get("amount"):
            channel["amount_label"] = format_money(channel["amount"])
    for index, month in enumerate(months):
        if not month.get("amount"):
            month["amount"] = sum(line[index] for line in grid if index < len(line))
        if month.get("amount") and not month.get("amount_label"):
            month["amount_label"] = format_money(month["amount"])
        month["full_label"] = _month_full(month.get("label"))
    return channels


WEEK_WEIGHTS = (12, 18, 28, 42)


def _week_lanes(months: list[dict]) -> list[dict]:
    out = []
    for month in months:
        amount = _money(month.get("amount"))
        parts = _largest_remainder(amount, list(WEEK_WEIGHTS))
        out.append({
            "label": month.get("full_label") or month.get("label"),
            "short": text(month.get("label"))[:3].title() or "Mês",
            "weeks": [
                {
                    "id": f"S{index + 1}",
                    "amount": value,
                    "amount_label": format_money(value) if value else "—",
                    "heat": max(18, round((value / max(parts)) * 100)) if parts and max(parts) and value else 0,
                }
                for index, value in enumerate(parts)
            ],
        })
    return out


def _attach_week_bars(channels: list[dict], months: list[dict]) -> list[dict]:
    """Rateia cada célula mensal em 4 semanas (learn-release). Intensidade visual, não data contratada."""
    peak = 1
    for channel in channels:
        week_bars = []
        for bar in channel.get("bars") or []:
            month_amount = _money(bar.get("amount"))
            parts = _largest_remainder(month_amount, list(WEEK_WEIGHTS)) if month_amount else [0, 0, 0, 0]
            peak = max(peak, max(parts) if parts else 0)
            for index, value in enumerate(parts):
                week_bars.append({
                    "id": f"S{index + 1}",
                    "amount": value,
                    "amount_label": format_money(value) if value else "—",
                    "heat": 0,
                })
        channel["week_bars"] = week_bars
    for channel in channels:
        for cell in channel.get("week_bars") or []:
            amount = _money(cell.get("amount"))
            cell["heat"] = max(14, round((amount / peak) * 100)) if peak and amount else 0
    return channels


def _flight_note(channel: dict, months: list[dict]) -> str:
    bars = channel.get("bars") or []
    if not bars:
        return ""
    index = max(range(len(bars)), key=lambda i: _money(bars[i].get("amount")))
    amount = _money(bars[index].get("amount"))
    if not amount:
        return f"{text(channel.get('label'))} participa do voo com o peso aprovado."
    month = months[index] if index < len(months) else {}
    label = text(month.get("full_label") or month.get("label") or "o período")
    return f"Maior intensidade em {label} ({bars[index].get('amount_label')})."


def _donut_slices(channels: list[dict]) -> list[dict]:
    circ = 264
    cursor = 0
    slices = []
    for item in channels:
        length = round(circ * max(item.get("pct") or 0, 0) / 100)
        slices.append({
            "id": item.get("id"),
            "label": item.get("label"),
            "color": item.get("color"),
            "pct": item.get("pct"),
            "amount_label": item.get("amount_label"),
            "dash": length,
            "gap": max(0, circ - length),
            "offset": cursor,
        })
        cursor += length
    return slices


def _playbook_for(channel: dict) -> dict:
    key = text(channel.get("id"))
    book = dict(CHANNEL_PLAYBOOK.get(key) or {
        "priority": "Canal do plano",
        "funnel": "Sustentar presença",
        "goal": text(channel.get("role") or GROUP_ROLE.get(channel.get("group")) or "Participa do mix aprovado."),
        "formats": [text(channel.get("format") or "Formatos do canal, sujeitos às peças.")],
        "placements": ["Posicionamentos do inventário aprovado"],
        "platforms": [text(channel.get("label"))],
        "buy": "Conforme o plano de compra",
        "status": "Recomendado",
    })
    book["role"] = text(book.get("goal") or channel.get("role"))
    return book


def _inventory(channels: list[dict], praca: str, detalhe: str) -> list[dict]:
    keys = {text(item.get("id")) for item in channels}
    regional = "interior" in text(praca).lower() or "minas" in text(detalhe).lower() or "minas" in text(praca).lower()
    rows = []
    if "youtube" in keys:
        rows.append({"name": "YouTube", "kind": "Plataforma", "scope": "Nacional", "role": "Escala audiovisual", "buy": "YouTube", "formats": "Vídeo, Shorts, bumper", "status": "Principal", "status_tone": "ok", "tags": ["plataformas", "video", "nacional"], "note": "Canal líder do mix aprovado."})
    if "meta_ads" in keys:
        rows.extend([
            {"name": "Instagram", "kind": "Social", "scope": "Nacional", "role": "Recorrência visual", "buy": "Meta Ads", "formats": "Feed, Stories, Reels", "status": "Principal", "status_tone": "ok", "tags": ["plataformas", "social", "nacional"], "note": "Ambiente de uso diário."},
            {"name": "Facebook", "kind": "Social", "scope": "Nacional", "role": "Frequência complementar", "buy": "Meta Ads", "formats": "Feed, Stories, vídeo", "status": "Complementar", "status_tone": "ok", "tags": ["plataformas", "social", "nacional"], "note": "Reforço da mesma mensagem."},
        ])
    if "dv360" in keys:
        rows.extend([
            {"name": "UOL", "kind": "Portal", "scope": "Nacional", "role": "Contexto de notícia e serviço", "buy": "DV360", "formats": "Display, native", "status": "Potencial", "status_tone": "soft", "tags": ["portais", "nacional", "programatica"], "note": "Inventário potencial, não contratado."},
            {"name": "Terra", "kind": "Portal", "scope": "Nacional", "role": "Cobertura adicional", "buy": "DV360", "formats": "Display", "status": "Potencial", "status_tone": "soft", "tags": ["portais", "nacional", "programatica"], "note": "Recomendado, não contratado."},
            {"name": "G1", "kind": "Portal", "scope": "Nacional", "role": "Alcance editorial", "buy": "DV360", "formats": "Display, native", "status": "Potencial", "status_tone": "soft", "tags": ["portais", "nacional", "programatica"], "note": "Depende de inventário e brand safety."},
            {"name": "R7", "kind": "Portal", "scope": "Nacional", "role": "Presença em notícias", "buy": "DV360", "formats": "Display, vídeo", "status": "Potencial", "status_tone": "soft", "tags": ["portais", "nacional", "programatica"], "note": "Sujeito a disponibilidade."},
        ])
        if regional:
            rows.extend([
                {"name": "Estado de Minas", "kind": "Portal", "scope": "Regional", "role": "Proximidade editorial", "buy": "DV360", "formats": "Display", "status": "Potencial", "status_tone": "soft", "tags": ["portais", "regional", "programatica"], "note": "Veículo mineiro potencial."},
                {"name": "O Tempo", "kind": "Portal", "scope": "Regional", "role": "Cobertura local", "buy": "DV360", "formats": "Display", "status": "Potencial", "status_tone": "soft", "tags": ["portais", "regional", "programatica"], "note": "Recomendado para Minas."},
                {"name": "G1 Minas", "kind": "Portal", "scope": "Regional", "role": "Notícia do estado", "buy": "DV360", "formats": "Display, native", "status": "Potencial", "status_tone": "soft", "tags": ["portais", "regional", "programatica"], "note": "Segmentação geográfica a validar."},
                {"name": "Portais do interior", "kind": "Portal", "scope": "Regional", "role": "Capilaridade municipal", "buy": "DV360", "formats": "Display", "status": "A validar", "status_tone": "warn", "tags": ["portais", "regional", "programatica"], "note": "Lista final após municípios prioritários."},
            ])
        rows.extend([
            {"name": "Apps de notícias", "kind": "Aplicativo", "scope": "Nacional", "role": "Presença in-app", "buy": "DV360", "formats": "Display, native", "status": "Potencial", "status_tone": "soft", "tags": ["apps", "programatica", "nacional"], "note": "Categoria de conteúdo, não app nomeado."},
            {"name": "Apps de clima", "kind": "Aplicativo", "scope": "Nacional", "role": "Contexto utilitário", "buy": "DV360", "formats": "Display", "status": "Potencial", "status_tone": "soft", "tags": ["apps", "programatica", "nacional"], "note": "Ambiente cotidiano, não contratado."},
            {"name": "Apps de mobilidade", "kind": "Aplicativo", "scope": "Nacional", "role": "Deslocamento", "buy": "DV360", "formats": "Display", "status": "Potencial", "status_tone": "soft", "tags": ["apps", "programatica", "nacional"], "note": "Sujeito a inventário."},
        ])
    return rows


def _inventory_filters(rows: list[dict]) -> list[dict]:
    present = {"todos"}
    for row in rows:
        present.update(text(tag) for tag in as_list(row.get("tags")) if text(tag))
    return [{"id": key, "label": label} for key, label in INVENTORY_FILTERS if key in present]


def _reading(channels: list[dict], months: list[dict]) -> list[dict]:
    out = []
    ranked = sorted(channels, key=lambda item: (-(item.get("pct") or 0), text(item.get("label"))))
    for item in ranked[:3]:
        role = text(item.get("role") or item.get("goal") or item.get("label"))
        amount = text(item.get("amount_label"))
        pct = item.get("pct") or 0
        detail = _first_sentence(role, 140)
        if pct and amount:
            detail = f"{detail} ({pct}% · {amount})"
        elif pct:
            detail = f"{detail} ({pct}%)"
        out.append({"title": item.get("label"), "text": detail})
    if months:
        peak = max(months, key=lambda row: _money(row.get("amount")))
        if _money(peak.get("amount")):
            label = peak.get("full_label") or peak.get("label")
            out.append({
                "title": label,
                "text": f"{label} concentra a maior intensidade de investimento ({peak.get('amount_label')}).",
            })
    return out[:4]


def _assumptions(missing: list[str], has_metrics: bool, has_inventory: bool = False) -> dict:
    points = [
        "Inventário depende de disponibilidade, brand safety e negociação.",
        "Valores podem ser ajustados na negociação final.",
        "Formatos dependem das peças entregues.",
        "O plano representa uma distribuição estratégica inicial.",
    ]
    if has_inventory:
        points.insert(1, "Portais e aplicativos desta folha são recomendações, não contratação.")
    if "municipios" in missing:
        points.insert(0, "Municípios prioritários ainda precisam de validação final.")
    if "datas" in missing:
        insert_at = 1 if "municipios" in missing else 0
        points.insert(insert_at, "Datas exatas do voo ainda não foram confirmadas.")
    if not has_metrics:
        points.append("Metas de alcance e impressões dependem de CPM, frequência, segmentação e inventário.")

    open_items = []
    for key in ("municipios", "datas"):
        if key in missing:
            open_items.append({"id": key, "label": OPEN_ITEM_LABELS[key]})
    if not has_metrics:
        open_items.append({"id": "metricas", "label": OPEN_ITEM_LABELS["metricas"]})

    steps = []
    if "municipios" in missing:
        steps.append("Validar municípios atendidos")
    if "datas" in missing:
        steps.append("Confirmar datas exatas")
    steps.extend(["Aprovar o mix", "Validar inventário disponível"])
    if not has_metrics:
        steps.append("Definir metas de alcance e frequência")
    steps.extend([
        "Receber especificações criativas",
        "Confirmar formatos por canal",
        "Consolidar o plano final de compra",
    ])
    return {
        "points": points,
        "steps": steps,
        "missing": list(missing),
        "open_items": open_items,
    }


def _finance_checks(channels: list[dict], months: list[dict], total: int) -> list[str]:
    warnings = []
    channel_sum = sum(_money(item.get("amount")) for item in channels)
    month_sum = sum(_money(item.get("amount")) for item in months)
    pct_sum = sum(item.get("pct") or 0 for item in channels)
    if channels and channel_sum and total and abs(channel_sum - total) > 2:
        warnings.append("channel_total")
    if months and month_sum and total and abs(month_sum - total) > 2:
        warnings.append("month_total")
    if channels and abs(pct_sum - 100) > 1:
        warnings.append("pct_total")
    return warnings


def _creative_plan_for_public(page: dict, channels: list[dict]) -> list[dict]:
    generated = {
        text(as_dict(item).get("channel_id")): as_dict(item)
        for item in as_list(page.get("creative_plan"))
        if text(as_dict(item).get("channel_id"))
    }
    out = []
    for channel in channels:
        channel_id = text(channel.get("id"))
        item = generated.get(channel_id, {})
        primary = as_dict(PRIMARY_FORMATS.get(channel_id))
        deliverables = as_dict(item.get("deliverables"))
        out.append({
            "channel_id": channel_id,
            "channel": text(item.get("channel") or channel.get("label")),
            "role": text(item.get("role") or channel.get("role")),
            "primary_format": text(item.get("primary_format") or primary.get("label") or channel.get("format")),
            "surface": text(item.get("surface") or primary.get("surface")),
            "duration_seconds": item.get("duration_seconds") or primary.get("duration_seconds"),
            "format_rationale": text(item.get("format_rationale")),
            "concepts": int(deliverables.get("concepts") or 1),
            "variations": int(deliverables.get("variations") or 1),
            "final_files": int(deliverables.get("final_files") or 1),
            "image_only": True,
        })
    return out


def _chapter_group(title: str) -> str:
    raw = unicodedata.normalize("NFKD", text(title)).encode("ascii", "ignore").decode().lower()
    if any(word in raw for word in ("indicador", "mensur", "metrica", "otimiz")):
        return "indicators"
    if any(word in raw for word in ("criativ", "formato", "entregavel", "output")):
        return "creative"
    if any(word in raw for word in ("execu", "risco", "depend", "proximo", "apendice", "objec")):
        return "execution"
    if any(word in raw for word in ("midia", "canal", "invest", "voo", "projec", "cenario", "mix")):
        return "media"
    return "strategy"


def _full_groups(chapters: list[dict], board: list[dict]) -> list[dict]:
    labels = {
        "strategy": "Estratégia",
        "media": "Mídia",
        "indicators": "Indicadores",
        "creative": "Criação",
        "execution": "Execução",
    }
    groups = {key: {"id": key, "label": label, "chapters": [], "sections": []} for key, label in labels.items()}
    for chapter in chapters:
        groups[_chapter_group(chapter.get("title"))]["chapters"].append(chapter)
    board_map = {"context": "strategy", "strategy": "strategy", "media": "media", "execution": "execution"}
    for section in board:
        groups[board_map.get(text(section.get("id")), _chapter_group(section.get("title")))]["sections"].append(section)
    return list(groups.values())


def public_view(row: dict, document: str | None = None) -> dict:
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
            board_sections.append({
                "id": text(item.get("id")),
                "title": text(item.get("title") or item.get("id")),
                "cards": [
                    {**card, "title_html": _inline_html(card.get("title")), "body_html": _inline_html(card.get("body"))}
                    for card in cards
                ],
            })
    chapters = plan_chapters(text(dados.get("planejamento")))
    page_v2 = as_dict(dados.get("one_page_v2"))
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
    praca_line = praca_detalhe or praca
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
            ("Praça", praca_line, "praca"),
            ("Período", period, "periodo"),
            ("Verba", verba, "verba"),
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
    for channel in media.get("channels") or []:
        channel.update(_playbook_for(channel))
        channel["creatives"] = list(CREATIVE_GUIDE.get(text(channel.get("id"))) or [])
        channel["role_short"] = _clip(
            text(channel.get("priority") or channel.get("role") or channel.get("goal")),
            42,
        )
    strategy_parts = _paragraphs(strategy.get("body"))
    defense_parts = _paragraphs(defense.get("body"))
    concept = text(creative.get("title"))
    support = text(creative.get("body"))
    strategy_board = _strategy_board(
        strategy_parts,
        audience,
        concept,
        support,
        defense_parts[0] if defense_parts else "",
    )
    funnel = _funnel_from_channels(media.get("channels") or [])
    overview = text(strategy_parts[0] if strategy_parts else tagline)
    missing = []
    if "município" in text(strategy.get("body")).lower() or "municipios" in text(strategy.get("body")).lower() or "sem definição" in text(strategy.get("body")).lower():
        missing.append("municipios")
    if re.search(r"^\d+\s*meses?$", text(period), re.I) or not re.search(r"\d{4}|/|- ", text(period)):
        missing.append("datas")
    if not _is_real_stat(text(as_dict(sheet.get("market")).get("stat"))):
        missing.append("metricas")
    if not hero_image and _looks_like_water(title, text(strategy.get("body")), concept, support):
        hero_image = "/static/images/smart_planner/hero-water.svg"
    share_image = _public_asset_url(hero_image or "/static/images/smart_planner/share-placeholder.svg")

    plan_mode = plan_mode_of(dados, "one_page")
    nav_folha = []
    if tem_folha:
        nav_folha = [
            {"id": "visao", "label": "Visão geral", "view": "folha"},
            {"id": "estrategia", "label": "Estratégia", "view": "folha"},
            {"id": "investimento", "label": "Investimento", "view": "folha"},
            {"id": "periodo", "label": "Período e Gantt", "view": "folha"},
            {"id": "canais", "label": "Canais", "view": "folha"},
            {"id": "portais", "label": "Portais e aplicativos", "view": "folha"},
            {"id": "criativos", "label": "Criativos e formatos", "view": "folha"},
            {"id": "premissas", "label": "Premissas", "view": "folha"},
        ]
    nav_plano = []
    if tem_completo:
        nav_plano.append({"id": "plano-doc", "label": "Documento", "view": "plano"})
        for index, chapter in enumerate(chapters):
            label = text(chapter.get("title")) or f"Capítulo {index + 1}"
            nav_plano.append({
                "id": f"cap-{index}",
                "label": _clip(label, 28),
                "view": "plano",
            })
        for index, section in enumerate(board_sections):
            label = text(section.get("title")) or f"Seção {index + 1}"
            nav_plano.append({
                "id": f"board-{index}",
                "label": _clip(label, 28),
                "view": "plano",
            })
    views = []
    if tem_folha:
        views.append({"id": "folha", "label": "Página única"})
    if tem_completo:
        views.append({"id": "plano", "label": "Plano completo"})
    if tem_folha and tem_completo:
        default_view = "plano" if plan_mode == "completo" else "folha"
    elif tem_completo:
        default_view = "plano"
    else:
        default_view = "folha"
    nav = nav_folha if default_view == "folha" else nav_plano
    updated = text(row.get("updated_at") or dados.get("updated_at"))
    updated_display = format_public_updated(row.get("updated_at") or dados.get("updated_at"))
    inventory = _inventory(media.get("channels") or [], praca, praca_detalhe)
    assumptions = _assumptions(missing, "metricas" not in missing, bool(inventory))
    creative_plan = _creative_plan_for_public(page_v2, media.get("channels") or [])
    proposal_url = public_document_url(token, "proposal")
    full_plan_url = public_document_url(token, "full_plan")
    document_url = full_plan_url if document == "full_plan" else proposal_url
    commercial_defense = as_dict(page_v2.get("commercial_defense"))
    defense_points = [text(item) for item in as_list(commercial_defense.get("why_this_mix") or commercial_defense.get("why_this_plan")) if text(item)]
    defense_points.extend(item for item in defense_parts if item not in defense_points)
    return {
        "house": HOUSE,
        "title": title,
        "client": client,
        "confidential": confidential,
        "mode": plan_mode,
        "facts": [(item[0], item[1]) for item in facts],
        "fact_items": facts,
        "audience": audience,
        "branding": branding,
        "sheet": sheet,
        "media": media,
        "hero": {
            "image": hero_image,
            "has_image": bool(hero_image),
            "kicker": "Planejamento de mídia",
            "tagline": tagline,
            "caption": praca_detalhe or praca,
            "verba": verba,
        },
        "share_image": share_image,
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
        "proposal_url": proposal_url,
        "full_plan_url": full_plan_url,
        "document": document,
        "document_url": document_url,
        "document_label": "Planejamento completo" if document == "full_plan" else "Proposta comercial",
        "public_token": token,
        "default_tab": default_view,
        "default_view": default_view,
        "views": views,
        "nav": nav,
        "nav_folha": nav_folha,
        "nav_plano": nav_plano,
        "concept": concept,
        "support": support,
        "overview": overview,
        "strategy_parts": strategy_parts,
        "strategy_board": strategy_board,
        "defense_parts": defense_parts,
        "defense_points": defense_points[:3],
        "creative_plan": creative_plan,
        "full_groups": _full_groups(chapters, board_sections),
        "funnel": funnel,
        "inventory": inventory,
        "inventory_filters": _inventory_filters(inventory),
        "inventory_note": INVENTORY_DISCLAIMER,
        "creative_principles": list(CREATIVE_PRINCIPLES),
        "reading_items": _reading(media.get("channels") or [], media.get("months") or []),
        "assumptions": assumptions,
        "metric_note": METRIC_UNDEFINED,
        "praca_line": praca_line,
        "updated_at": updated_display["label"] or updated,
        "updated_at_title": updated_display["title"] or updated,
        "executive_facts": [
            ("Verba", verba or "A definir"),
            ("Período", period or "A definir"),
            ("Objetivo", objective_label or "A definir"),
            ("Mix", f"{media.get('total_pct') or 0}% alocado" if media.get("channels") else "A definir"),
            ("Metas", "Pendentes de validação" if "metricas" in missing else "Definidas no plano"),
        ],
        "period_count": len(media.get("months") or []),
        "channel_count": len(media.get("channels") or []),
    }
