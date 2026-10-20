"""Modelos de apresentação do link público: CentralComm, neutro e marcas do Workspace.

Um modelo é logo + paleta já tratada para leitura (tinta, destaque, cor de
marca, papel e cores de gráfico). O modelo da agência ou do cliente vem da
marca analisada no Workspace (``cx_clients``), então ajustar a marca uma vez
vale para todos os planos e executivos daquela agência ou cliente.
"""

from __future__ import annotations

import base64
import io
import re
from typing import Any

from .helpers import as_dict, as_list, text
from .logos import CENTRALCOMM_LOGO, public_logo

HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")

TOKEN_KEYS = ("ink", "brand", "accent", "paper", "soft", "muted")

CENTRALCOMM = {
    "id": "centralcomm",
    "kind": "house",
    "name": "CentralComm",
    "label": "Padrão CentralComm",
    "logo": CENTRALCOMM_LOGO,
    "note": "Verde e âmbar da marca CentralComm.",
    "tokens": {
        "ink": "#10252D",
        "brand": "#0B6B52",
        "accent": "#F0B000",
        "paper": "#FFFEFA",
        "soft": "#EEF5F1",
        "muted": "#5F7076",
    },
    "chart": ["#0B6B52", "#F0B000", "#20C070", "#10252D", "#7FA9A0", "#C98A00"],
}

NEUTRO = {
    "id": "neutro",
    "kind": "neutral",
    "name": "Neutro",
    "label": "Neutro",
    "logo": CENTRALCOMM_LOGO,
    "note": "Tons de cinza, sem cor de marca. Bom para impressão e para repassar o plano.",
    "tokens": {
        "ink": "#1F2328",
        "brand": "#3D444D",
        "accent": "#8C959F",
        "paper": "#FFFFFF",
        "soft": "#F3F4F6",
        "muted": "#5F6670",
    },
    "chart": ["#3D444D", "#8C959F", "#5F6670", "#B6BCC3", "#1F2328", "#D5D9DE"],
}

BUILTIN = {"centralcomm": CENTRALCOMM, "neutro": NEUTRO}
CHOICES = ("agencia", "cliente", "centralcomm", "neutro")


# ---------------------------------------------------------------- cores


def hex_colors(values: Any) -> list[str]:
    """Cores hexadecimais de uma paleta em qualquer formato (texto, dicts do Workspace)."""
    found: list[str] = []
    for item in as_list(values) if not isinstance(values, str) else [values]:
        raw = as_dict(item).get("hex") if isinstance(item, dict) else item
        for match in HEX.findall(text(raw)):
            color = _expand(match)
            if color not in found:
                found.append(color)
    return found


def _expand(color: str) -> str:
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return "#" + value.upper()


def _rgb(color: str) -> tuple[int, int, int]:
    value = _expand(color).lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def luminance(color: str) -> float:
    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(color: str, other: str, amount: float) -> str:
    a, b = _rgb(color), _rgb(other)
    return _hex(tuple(a[i] + (b[i] - a[i]) * amount for i in range(3)))


def _saturation(color: str) -> float:
    r, g, b = (c / 255 for c in _rgb(color))
    high, low = max(r, g, b), min(r, g, b)
    if high == low:
        return 0.0
    light = (high + low) / 2
    return (high - low) / (1 - abs(2 * light - 1))


def _until(color: str, against: str, ratio: float, toward: str) -> str:
    """Escurece (ou clareia) a cor até ter o contraste pedido contra ``against``."""
    current = color
    for step in range(1, 21):
        if contrast(current, against) >= ratio:
            return current
        current = mix(color, toward, step / 20)
    return current


def palette_tokens(colors: list[str]) -> dict:
    """Transforma a paleta da marca em papéis legíveis, com contraste garantido.

    A primeira cor é a primária da marca (como no Workspace). Textos escuros
    usam ``ink``, títulos e barras usam ``brand``, realces usam ``accent``.
    """
    paper = "#FFFEFA"
    colors = hex_colors(colors)
    if not colors:
        return dict(CENTRALCOMM["tokens"])
    chromatic = [c for c in colors if _saturation(c) > 0.18 and 0.03 < luminance(c) < 0.85]
    primary = (chromatic or colors)[0]
    darkest = min(colors, key=luminance)
    ink = darkest if contrast(darkest, paper) >= 10 else _until(mix(primary, "#000000", 0.55), paper, 10, "#000000")
    brand = _until(primary, paper, 4.5, "#000000")
    others = [c for c in chromatic if c != primary]
    accent = max(others, key=_saturation) if others else mix(primary, "#FFFFFF", 0.25)
    # O destaque aparece sobre a capa escura e sobre o papel; precisa ler nos dois.
    if contrast(accent, ink) < 3:
        accent = _until(accent, ink, 3, "#FFFFFF")
    return {
        "ink": ink,
        "brand": brand,
        "accent": accent,
        "paper": paper,
        "soft": mix(brand, "#FFFFFF", 0.92),
        "muted": _until(mix(ink, "#FFFFFF", 0.38), paper, 4.5, "#000000"),
    }


def chart_colors(tokens: dict, colors: list[str]) -> list[str]:
    base = [tokens["brand"], tokens["accent"]]
    for color in hex_colors(colors):
        if color not in base and 0.02 < luminance(color) < 0.9:
            base.append(color)
    for amount in (0.35, 0.6, 0.2):
        base.append(mix(tokens["brand"], "#FFFFFF", amount))
    return list(dict.fromkeys(base))[:6]


def colors_from_image(data_url: str, count: int = 5) -> list[str]:
    """Cores dominantes de uma logo (sem fundo branco/transparente), mais saturadas primeiro."""
    header, _, encoded = text(data_url).partition(",")
    if not header.startswith("data:image/") or not encoded:
        return []
    try:
        from PIL import Image

        raw = base64.b64decode(encoded, validate=True)
        image = Image.open(io.BytesIO(raw)).convert("RGBA")
        image.thumbnail((160, 160))
        pixels = [
            (r, g, b) for r, g, b, a in (image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata())
            if a > 200 and not (r > 240 and g > 240 and b > 240)
        ]
        if not pixels:
            return []
        sample = Image.new("RGB", (len(pixels), 1))
        sample.putdata(pixels)
        quant = sample.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
        palette = quant.getpalette() or []
        counts = sorted(quant.getcolors() or [], reverse=True)
    except Exception:
        return []
    found: list[str] = []
    for _, index in counts:
        color = _hex(tuple(palette[index * 3:index * 3 + 3]))
        if all(sum(abs(a - b) for a, b in zip(_rgb(color), _rgb(seen))) > 60 for seen in found):
            found.append(color)
    found.sort(key=lambda c: (_saturation(c) < 0.18, -_saturation(c)))
    return found[:count]


# ---------------------------------------------------------------- modelos


def from_brand(kind: str, brand: dict, owner_name: str = "") -> dict | None:
    """Modelo a partir da marca do Workspace; sem logo e sem paleta não há modelo."""
    brand = as_dict(brand)
    colors = hex_colors(brand.get("palette"))
    logo = public_logo(brand.get("logo_url"))
    if not colors and not logo:
        return None
    tokens = palette_tokens(colors) if colors else dict(CENTRALCOMM["tokens"])
    name = text(brand.get("name") or owner_name)
    return {
        "id": kind,
        "kind": kind,
        "name": name,
        "label": f"Agência · {name}" if kind == "agencia" else f"Cliente · {name}",
        "logo": logo,
        "note": "Logo e paleta da marca analisada no Workspace." if colors else "Logo da marca; paleta CentralComm até a marca ter cores.",
        "tokens": tokens,
        "chart": chart_colors(tokens, colors),
        "brand_id": brand.get("id"),
        "has_palette": bool(colors),
        "swatches": colors[:6],
    }


def _with_swatches(template: dict) -> dict:
    out = dict(template)
    out.setdefault("swatches", [out["tokens"][k] for k in ("brand", "accent", "ink")])
    return out


def neutral(template: dict) -> dict:
    """Mesmo modelo (e logo), cores em cinza: para exportar ou repassar sem a cor da marca."""
    out = dict(template)
    out["tokens"] = dict(NEUTRO["tokens"])
    out["chart"] = list(NEUTRO["chart"])
    out["neutral"] = True
    return out


def plan_parties(row: dict) -> dict:
    """Cliente e agência do plano, com as marcas do Workspace de cada um."""
    from .brand import brand_for_client
    from .logos import lookup_agency_for_client

    dados = as_dict(row.get("dados_detectados"))
    folha = as_dict(dados.get("folha"))
    branding = as_dict(folha.get("branding"))
    client_party = as_dict(branding.get("client") or branding.get("hero"))
    cliente_id = dados.get("cliente_id") or client_party.get("id")
    client_brand = as_dict(dados.get("brand"))
    if cliente_id and not (client_brand.get("palette") or client_brand.get("logo_url")):
        client_brand = as_dict(brand_for_client(cliente_id)) or client_brand
    agency = as_dict(branding.get("agency"))
    if not agency.get("id") and cliente_id:
        agency = as_dict(lookup_agency_for_client(cliente_id)) or agency
    agency_brand = as_dict(brand_for_client(agency.get("id"))) if agency.get("id") else {}
    return {
        "client": {"id": cliente_id, "name": text(client_party.get("name") or client_brand.get("name") or as_dict(dados.get("campanha")).get("cliente")), "brand": client_brand},
        "agency": {"id": agency.get("id"), "name": text(agency.get("name")), "logo_url": public_logo(agency.get("logo_url")), "brand": agency_brand},
    }


def options_for(row: dict, parties: dict | None = None) -> list[dict]:
    parties = parties or plan_parties(row)
    out = []
    agency = as_dict(parties.get("agency"))
    client = as_dict(parties.get("client"))
    agency_brand = dict(as_dict(agency.get("brand")))
    if agency.get("id") and not agency_brand.get("logo_url") and agency.get("logo_url"):
        agency_brand["logo_url"] = agency.get("logo_url")
    for kind, party, brand in (("agencia", agency, agency_brand), ("cliente", client, as_dict(client.get("brand")))):
        template = from_brand(kind, brand, text(party.get("name"))) if party.get("id") else None
        if template:
            out.append(template)
    out.append(_with_swatches(CENTRALCOMM))
    out.append(_with_swatches(NEUTRO))
    return out


def default_choice(options: list[dict]) -> str:
    """Sem escolha no plano, vale o modelo da agência (com paleta); depois, CentralComm."""
    for option in options:
        if option["id"] == "agencia" and option.get("has_palette"):
            return "agencia"
    return "centralcomm"


def resolve(row: dict, *, neutral_palette: bool = False, parties: dict | None = None) -> dict:
    options = options_for(row, parties)
    by_id = {option["id"]: option for option in options}
    choice = text(as_dict(row.get("dados_detectados")).get("presentation_template")).lower()
    template = by_id.get(choice) or by_id.get(default_choice(options)) or _with_swatches(CENTRALCOMM)
    template = dict(template)
    template["selected"] = template["id"]
    template["chosen"] = choice in by_id
    return neutral(template) if neutral_palette else template


def editor_panel(row: dict) -> dict:
    """Dados do seletor de modelo no editor: opções, a escolhida e o que falta montar."""
    parties = plan_parties(row)
    options = options_for(row, parties)
    current = resolve(row, parties=parties)
    agency = as_dict(parties.get("agency"))
    client = as_dict(parties.get("client"))
    have = {option["id"] for option in options}
    missing = []
    if agency.get("id") and "agencia" not in have:
        missing.append({"alvo": "agencia", "name": text(agency.get("name"))})
    if client.get("id") and "cliente" not in have:
        missing.append({"alvo": "cliente", "name": text(client.get("name"))})
    return {
        "options": [
            {
                "id": option["id"],
                "label": option["label"],
                "logo": option.get("logo") or "",
                "note": option.get("note") or "",
                "swatches": option.get("swatches") or [],
            }
            for option in options
        ],
        "selected": current["id"],
        "chosen": current["chosen"],
        "missing": missing,
        "agency_name": text(agency.get("name")),
        "client_name": text(client.get("name")),
    }


def css_vars(template: dict) -> str:
    """Variáveis CSS do modelo; só hexadecimal validado entra no bloco <style>."""
    tokens = as_dict(template.get("tokens"))
    parts = []
    for key in TOKEN_KEYS:
        value = text(tokens.get(key))
        if HEX.fullmatch(value):
            parts.append(f"--sx-{key}:{value}")
    for index, value in enumerate(as_list(template.get("chart"))[:6], start=1):
        if HEX.fullmatch(text(value)):
            parts.append(f"--sx-c{index}:{value}")
    return ";".join(parts)


DOCUMENT_VARS = {"ink": "--ink", "brand": "--brand", "accent": "--gold", "paper": "--paper", "soft": "--soft", "muted": "--muted"}


def document_css_vars(template: dict) -> str:
    """As mesmas cores para o documento em rolagem, que usa nomes de variável próprios."""
    tokens = as_dict(template.get("tokens"))
    return ";".join(
        f"{name}:{tokens[key]}" for key, name in DOCUMENT_VARS.items()
        if HEX.fullmatch(text(tokens.get(key)))
    )


def apply_to_view(view: dict, template: dict) -> dict:
    """Leva o modelo para a visão pública: cores dos gráficos, logo da casa e tokens."""
    chart = [c for c in as_list(template.get("chart")) if HEX.fullmatch(text(c))] or CENTRALCOMM["chart"]
    media = as_dict(view.get("media"))
    for index, channel in enumerate(as_list(media.get("channels"))):
        if isinstance(channel, dict):
            channel["color"] = chart[index % len(chart)]
    view["template"] = template
    view["template_css"] = css_vars(template)
    view["document_template_css"] = document_css_vars(template)
    hero = as_dict(view.get("hero"))
    tokens = as_dict(template.get("tokens"))
    hero["theme_ink"] = tokens.get("ink") or hero.get("theme_ink")
    hero["theme_accent"] = tokens.get("accent") or hero.get("theme_accent")
    hero["theme_paper"] = tokens.get("paper") or hero.get("theme_paper")
    view["hero"] = hero
    house = dict(as_dict(view.get("house")))
    if template.get("kind") == "agencia":
        house["name"] = text(template.get("name")) or house.get("name")
        house["logo"] = text(template.get("logo")) or house.get("logo")
    view["house"] = house
    return view


# ---------------------------------------------------------------- montar modelo


def _palette_records(colors: list[str]) -> list[dict]:
    names = ("Cor principal", "Cor de destaque", "Cor escura", "Cor de apoio", "Cor de apoio", "Cor de apoio")
    return [
        {"hex": color, "name": names[index], "usage": "Modelo de apresentação do Smart Planner", "confidence": 1.0}
        for index, color in enumerate(hex_colors(colors)[:6])
    ]


def _save_logo(data_url: str) -> str:
    """Grava a logo na mesma pasta de logos do Workspace (fora do git, preservada no deploy)."""
    from werkzeug.datastructures import FileStorage

    from ..creative_modeling_storage import ClientLogoStorage

    header, _, encoded = text(data_url).partition(",")
    mime = header.split(";", 1)[0].split(":", 1)[-1].lower()
    extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp"}.get(mime)
    if not extension or not encoded:
        raise ValueError("Envie a logo em PNG, JPG ou WEBP.")
    raw = base64.b64decode(encoded, validate=True)
    return ClientLogoStorage().save(FileStorage(stream=io.BytesIO(raw), filename=f"logo{extension}", content_type=mime))


def save_party_template(row: dict, alvo: str, logo_data: str = "", colors: list[str] | None = None) -> dict:
    """Salva logo e paleta na marca do Workspace da agência ou do cliente do plano.

    É a mesma marca que a análise do Workspace preenche; o planner só completa
    logo e cores. Uma vez salva, todos os planos daquela agência ou cliente a usam.
    """
    from psycopg.types.json import Json

    from ..db import get_db
    from .brand import load_cx_client_for_crm

    if alvo not in {"agencia", "cliente"}:
        raise ValueError("Escolha agência ou cliente.")
    party = as_dict(plan_parties(row).get("agency" if alvo == "agencia" else "client"))
    crm_id = party.get("id")
    if not crm_id:
        raise ValueError("O plano não tem " + ("agência" if alvo == "agencia" else "cliente") + " do CRM.")
    palette = hex_colors(colors or [])
    if not palette and logo_data:
        palette = colors_from_image(logo_data)
    if not palette and not logo_data:
        raise ValueError("Envie a logo ou escolha as cores.")
    logo_path = _save_logo(logo_data) if logo_data else ""
    current = load_cx_client_for_crm(crm_id) or {}
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if current.get("id"):
                profile = as_dict(current.get("brand_profile"))
                if palette:
                    profile["color_palette"] = _palette_records(palette)
                cur.execute(
                    """UPDATE cx_clients
                          SET logo_upload_path = COALESCE(NULLIF(%s, ''), logo_upload_path),
                              primary_color = COALESCE(%s, primary_color),
                              secondary_color = COALESCE(%s, secondary_color),
                              brand_profile = %s
                        WHERE id = %s""",
                    (logo_path, palette[0] if palette else None, palette[1] if len(palette) > 1 else None,
                     Json(profile), current["id"]),
                )
                brand_id = current["id"]
            else:
                cur.execute(
                    """INSERT INTO cx_clients (crm_client_id, name, logo_upload_path, primary_color,
                                               secondary_color, brand_profile, analysis_metadata, price_policy)
                       VALUES (%s, %s, NULLIF(%s, ''), %s, %s, %s, %s, 'hide_price')
                       RETURNING id""",
                    (crm_id, text(party.get("name")) or "Marca", logo_path,
                     palette[0] if palette else None, palette[1] if len(palette) > 1 else None,
                     Json({"color_palette": _palette_records(palette)}),
                     Json({"source_types": ["smart_planner_template"]})),
                )
                brand_id = cur.fetchone()["id"]
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"brand_id": brand_id, "palette": palette, "logo": logo_path}
