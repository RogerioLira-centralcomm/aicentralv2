"""Documento público do Smart Planner — só folha e plano, marca Centralcomm."""

from __future__ import annotations

import re

from .catalog import CHANNEL_CATALOG, CHANNEL_LOGOS, OBJETIVO_OPTIONS, PRACA_OPTIONS, objetivo_label
from .helpers import as_bool, as_dict, as_list, normalize_markdown, plan_mode_of, session_title, text
from .mix import METHODS
from .pace import format_money, parse_money
from .share import HOUSE, public_sheet_url

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
    _attach_matrix(channels, months, calendar)
    total = sum(_money(item.get("amount")) for item in channels) or sum(_money(item.get("amount")) for item in months)
    average = round(total / len(months)) if months and total else 0
    peak = max(months, key=lambda row: _money(row.get("amount")), default={})
    leader = max(channels, key=lambda row: row.get("pct") or 0, default={})
    return {
        "method_label": method,
        "channels": channels,
        "months": months,
        "how": how,
        "note": note,
        "donut": _donut_style(channels),
        "slices": _donut_slices(channels),
        "weeks": _week_lanes(months),
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


WATER_MARKERS = ("água", "agua", "reservatório", "reservatorio", "torneira")
METRIC_UNDEFINED = "A definir após validação de segmentação, inventário e premissas de compra."
INVENTORY_DISCLAIMER = (
    "Os veículos, plataformas, portais e aplicativos desta seção são ambientes "
    "recomendados ou potenciais. A veiculação final depende de inventário, "
    "segmentação, brand safety, negociação e aprovação."
)

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

FUNNEL_STEPS = (
    {"id": "sensibilizar", "title": "Sensibilizar", "text": "Abrir a conversa com escala audiovisual."},
    {"id": "reforcar", "title": "Reforçar", "text": "Repetir a mensagem no uso diário."},
    {"id": "sustentar", "title": "Sustentar presença", "text": "Manter cobertura em mais contextos."},
    {"id": "lembrar", "title": "Estimular lembrança", "text": "Fechar o voo com mais pressão."},
)


def _paragraphs(value: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", text(value)) if chunk.strip()]


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


def _week_lanes(months: list[dict]) -> list[dict]:
    out = []
    for month in months:
        amount = _money(month.get("amount"))
        parts = _largest_remainder(amount, [12, 18, 28, 42][: 4 if amount else 4])
        out.append({
            "label": month.get("full_label") or month.get("label"),
            "weeks": [
                {"id": f"S{index + 1}", "amount": value, "heat": max(20, 40 + index * 18)}
                for index, value in enumerate(parts)
            ],
        })
    return out


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
    book["role"] = text(channel.get("role") or book.get("goal"))
    return book


def _inventory(channels: list[dict], praca: str, detalhe: str) -> list[dict]:
    keys = {text(item.get("id")) for item in channels}
    regional = "interior" in text(praca).lower() or "minas" in text(detalhe).lower()
    rows = []
    if "youtube" in keys:
        rows.append({"name": "YouTube", "kind": "Plataforma", "scope": "Nacional", "role": "Escala audiovisual", "buy": "YouTube", "formats": "Vídeo, Shorts, bumper", "status": "Principal", "tags": ["plataformas", "video", "nacional"], "note": "Canal líder do mix."})
    if "meta_ads" in keys:
        rows.extend([
            {"name": "Instagram", "kind": "Social", "scope": "Nacional", "role": "Recorrência visual", "buy": "Meta Ads", "formats": "Feed, Stories, Reels", "status": "Principal", "tags": ["plataformas", "social", "nacional"], "note": "Ambiente de uso diário."},
            {"name": "Facebook", "kind": "Social", "scope": "Nacional", "role": "Frequência complementar", "buy": "Meta Ads", "formats": "Feed, Stories, vídeo", "status": "Complementar", "tags": ["plataformas", "social", "nacional"], "note": "Reforço da mesma mensagem."},
        ])
    if "dv360" in keys:
        rows.extend([
            {"name": "UOL", "kind": "Portal", "scope": "Nacional", "role": "Contexto de notícia e serviço", "buy": "DV360", "formats": "Display, native", "status": "Sujeito a disponibilidade", "tags": ["portais", "nacional", "programatica"], "note": "Inventário potencial."},
            {"name": "Terra", "kind": "Portal", "scope": "Nacional", "role": "Cobertura adicional", "buy": "DV360", "formats": "Display", "status": "Sujeito a disponibilidade", "tags": ["portais", "nacional", "programatica"], "note": "Recomendado, não contratado."},
            {"name": "G1", "kind": "Portal", "scope": "Nacional", "role": "Alcance editorial", "buy": "DV360", "formats": "Display, native", "status": "Sujeito a disponibilidade", "tags": ["portais", "nacional", "programatica"], "note": "Depende de inventário e brand safety."},
            {"name": "R7", "kind": "Portal", "scope": "Nacional", "role": "Presença em notícias", "buy": "DV360", "formats": "Display, vídeo", "status": "Sujeito a disponibilidade", "tags": ["portais", "nacional", "programatica"], "note": "Sujeito a disponibilidade."},
        ])
        if regional:
            rows.extend([
                {"name": "Estado de Minas", "kind": "Portal", "scope": "Regional", "role": "Proximidade editorial", "buy": "DV360", "formats": "Display", "status": "Sujeito a disponibilidade", "tags": ["portais", "regional", "programatica"], "note": "Veículo mineiro potencial."},
                {"name": "O Tempo", "kind": "Portal", "scope": "Regional", "role": "Cobertura local", "buy": "DV360", "formats": "Display", "status": "Sujeito a disponibilidade", "tags": ["portais", "regional", "programatica"], "note": "Recomendado para o interior de Minas."},
                {"name": "G1 Minas", "kind": "Portal", "scope": "Regional", "role": "Notícia do estado", "buy": "DV360", "formats": "Display, native", "status": "Sujeito a disponibilidade", "tags": ["portais", "regional", "programatica"], "note": "Segmentação geográfica a validar."},
                {"name": "Portais do interior", "kind": "Portal", "scope": "Regional", "role": "Capilaridade municipal", "buy": "DV360", "formats": "Display", "status": "Sujeito a disponibilidade", "tags": ["portais", "regional", "programatica"], "note": "Lista final após municípios prioritários."},
            ])
        rows.extend([
            {"name": "Apps de notícias", "kind": "Aplicativo", "scope": "Nacional", "role": "Presença in-app", "buy": "DV360", "formats": "Display, native", "status": "Sujeito a disponibilidade", "tags": ["apps", "programatica", "nacional"], "note": "Categoria de conteúdo."},
            {"name": "Apps de clima", "kind": "Aplicativo", "scope": "Nacional", "role": "Contexto utilitário", "buy": "DV360", "formats": "Display", "status": "Sujeito a disponibilidade", "tags": ["apps", "programatica", "nacional"], "note": "Ambiente cotidiano, não contratado."},
            {"name": "Apps de mobilidade", "kind": "Aplicativo", "scope": "Nacional", "role": "Deslocamento", "buy": "DV360", "formats": "Display", "status": "Sujeito a disponibilidade", "tags": ["apps", "programatica", "nacional"], "note": "Sujeito a inventário."},
        ])
    return rows


def _reading(channels: list[dict], months: list[dict]) -> list[dict]:
    out = []
    for item in channels[:3]:
        role = text(item.get("role") or item.get("label"))
        out.append({"title": item.get("label"), "text": _first_sentence(role, 110)})
    if months:
        peak = max(months, key=lambda row: _money(row.get("amount")))
        if _money(peak.get("amount")):
            out.append({
                "title": peak.get("full_label") or peak.get("label"),
                "text": f"{peak.get('full_label') or peak.get('label')} concentra a maior intensidade de investimento.",
            })
    return out[:4]


def _assumptions(missing: list[str], has_metrics: bool) -> dict:
    points = [
        "Inventário depende de disponibilidade, brand safety e negociação.",
        "Portais e aplicativos desta folha são recomendações, não contratação.",
        "Valores podem ser ajustados na negociação final.",
        "Formatos dependem das peças entregues.",
        "O plano representa uma distribuição estratégica inicial.",
    ]
    if "municipios" in missing:
        points.insert(0, "Municípios prioritários ainda precisam de validação final.")
    if "datas" in missing:
        points.insert(1, "Datas exatas do voo ainda não foram confirmadas.")
    if not has_metrics:
        points.append("Metas de alcance e impressões dependem de CPM, frequência, segmentação e inventário.")
    steps = [
        "Validar municípios atendidos",
        "Confirmar datas exatas",
        "Aprovar o mix",
        "Validar inventário",
        "Definir metas de alcance e frequência",
        "Receber especificações criativas",
        "Confirmar formatos",
        "Consolidar o plano final de compra",
    ]
    return {"points": points, "steps": steps, "missing": missing}


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
    strategy_parts = _paragraphs(strategy.get("body"))
    defense_parts = _paragraphs(defense.get("body"))
    concept = text(creative.get("title"))
    support = text(creative.get("body"))
    missing = []
    if "município" in text(strategy.get("body")).lower() or "municipios" in text(strategy.get("body")).lower() or "sem definição" in text(strategy.get("body")).lower():
        missing.append("municipios")
    if re.search(r"^\d+\s*meses?$", text(period), re.I) or not re.search(r"\d{4}|/|- ", text(period)):
        missing.append("datas")
    if not _is_real_stat(text(as_dict(sheet.get("market")).get("stat"))):
        missing.append("metricas")
    if not hero_image and _looks_like_water(title, text(strategy.get("body")), concept, support):
        hero_image = "/static/images/smart_planner/hero-water.svg"
    nav = [
        {"id": "visao", "label": "Visão geral"},
        {"id": "estrategia", "label": "Estratégia"},
        {"id": "investimento", "label": "Investimento"},
        {"id": "periodo", "label": "Período e Gantt"},
        {"id": "canais", "label": "Canais"},
        {"id": "portais", "label": "Portais e aplicativos"},
        {"id": "criativos", "label": "Criativos e formatos"},
        {"id": "premissas", "label": "Premissas"},
    ]
    if tem_completo:
        nav.append({"id": "documento", "label": "Documento"})
    updated = text(row.get("updated_at") or dados.get("updated_at"))
    return {
        "house": HOUSE,
        "title": title,
        "client": client,
        "confidential": confidential,
        "mode": plan_mode_of(dados, "one_page"),
        "facts": [(item[0], item[1]) for item in facts],
        "fact_items": facts,
        "audience": audience,
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
        "nav": nav,
        "concept": concept,
        "support": support,
        "strategy_parts": strategy_parts,
        "defense_parts": defense_parts,
        "funnel": list(FUNNEL_STEPS),
        "inventory": _inventory(media.get("channels") or [], praca, praca_detalhe),
        "inventory_note": INVENTORY_DISCLAIMER,
        "creative_principles": list(CREATIVE_PRINCIPLES),
        "reading_items": _reading(media.get("channels") or [], media.get("months") or []),
        "assumptions": _assumptions(missing, "metricas" not in missing),
        "metric_note": METRIC_UNDEFINED,
        "praca_line": praca_line,
        "updated_at": updated,
        "period_count": len(media.get("months") or []),
        "channel_count": len(media.get("channels") or []),
    }
