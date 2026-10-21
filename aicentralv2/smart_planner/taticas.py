"""Táticas da campanha: impacto e remarketing, com formatos, DCO, peso e recorte de portais.

O mix diz quanto cada canal pesa. As táticas dizem o que cada frente da campanha faz: quais canais
usa, que formatos veicula (do catálogo de formatos do canal) e, nos portais, o recorte de audiência
(classes AB, por exemplo). Duas frentes podem usar o mesmo canal, como a Rede de portais e sites com
formatos interativos e com DCO, e cada frente tem o seu peso na verba. Sem táticas, o plano continua
igual ao de antes.
"""

from __future__ import annotations

from typing import Any

from . import formats as format_catalog
from .catalog import CHANNEL_CATALOG
from .helpers import as_dict, as_list, text

TATICA_TIPOS = {
    "impacto": {
        "label": "Impacto",
        "hint": "Apresenta a ideia e provoca exploração: formatos interativos e presença editorial.",
    },
    "remarketing": {
        "label": "Remarketing",
        "hint": "Volta a falar com quem interagiu ou visitou o site, com mensagem por etapa.",
    },
}

# Tipos de formato da frente: o que o cliente vê ("vídeo", "display IAB"…) antes dos formatos
# específicos. Cada formato do catálogo pertence a um tipo pelo campo ``tipo`` do catálogo.
FORMAT_FAMILIES = {
    "video": {"label": "Vídeo", "hint": "Vídeo em portais, CTV, streaming e redes."},
    "display": {"label": "Display IAB", "hint": "Banners nos tamanhos padrão IAB."},
    "native": {"label": "Native", "hint": "Anúncio no formato do conteúdo do site."},
    "audio": {"label": "Áudio", "hint": "Spots em streaming de áudio e podcasts."},
    "interativo": {"label": "Interativo", "hint": "Rich media e formatos clicáveis; custo agregado na proposta."},
}
CATALOG_TYPE_FAMILY = {
    "video": "video", "ctv": "video",
    "display": "display",
    "native": "native",
    "audio": "audio",
    "display_interativo": "interativo", "rich-media": "interativo", "rich media": "interativo", "interactive": "interativo",
}
FAMILY_ALIASES = {
    "video": "video", "vídeo": "video", "videos": "video", "vídeos": "video", "ctv": "video", "olv": "video",
    "display": "display", "iab": "display", "display iab": "display", "banner": "display", "banners": "display",
    "native": "native", "nativo": "native", "conteudo nativo": "native",
    "audio": "audio", "áudio": "audio", "spot": "audio", "podcast": "audio",
    "interativo": "interativo", "interativos": "interativo", "rich media": "interativo", "rich-media": "interativo",
}

FORMATO_DCO = {"id": "dco", "label": "DCO · anúncio dinâmico"}
# DCO: anúncio dinâmico. A mesma peça muda conforme as regras da campanha.
DCO_DESCRIPTION = (
    "a peça muda sozinha por horário, geolocalização, estoque do item, condições definidas pela marca "
    "e segmentação de audiência"
)
DCO_PRIMARY = {"id": "dco_dynamic", "label": "DCO · anúncio dinâmico", "surface": "display"}

# Recortes de classe aceitos para orientar a escolha dos portais.
SEGMENTOS = ("A", "AB", "B", "BC", "C")

# DCO varia a peça por regra de campanha: precisa de tela com anúncio de imagem ou vídeo.
DCO_BLOCKED_GROUPS = {"ooh", "places", "audio", "ctv", "data"}


def formato_label(format_id: str) -> str:
    if format_id == FORMATO_DCO["id"]:
        return FORMATO_DCO["label"]
    return format_catalog.display_name(format_id)


def family_of(slug: str) -> str:
    """Tipo de um formato do catálogo; DCO roda em display."""
    if slug == FORMATO_DCO["id"]:
        return "display"
    row = format_catalog.by_id(slug)
    if row.get("interactive"):
        return "interativo"
    return CATALOG_TYPE_FAMILY.get(text(row.get("type")).lower(), "")


def families_for_channels(channels: list[str]) -> list[str]:
    """Tipos que os canais da frente aceitam, pelo catálogo de formatos de cada um."""
    found = {family_of(fmt["id"]) for key in channels for fmt in format_catalog.formats_for_channel(key)}
    return [key for key in FORMAT_FAMILIES if key in found]


def family_label(key: str) -> str:
    return FORMAT_FAMILIES.get(key, {}).get("label", key)


def _families(raw: Any, available: list[str], formats: list[str]) -> list[str]:
    chosen = []
    for value in as_list(raw):
        key = FAMILY_ALIASES.get(text(value).strip().lower())
        if key and key not in chosen and (not available or key in available):
            chosen.append(key)
    # Formato escolhido já diz o tipo; o tipo aparece mesmo que o executivo não o marque.
    for slug in formats:
        key = family_of(slug)
        if key and key not in chosen:
            chosen.append(key)
    return [key for key in FORMAT_FAMILIES if key in chosen]


def dco_allowed(channel_id: str) -> bool:
    return (CHANNEL_CATALOG.get(channel_id) or {}).get("group") not in DCO_BLOCKED_GROUPS


def spec_for_js() -> dict:
    """O que a tela precisa: tipos, recortes e os formatos que cada canal aceita."""
    channels = {}
    for key in format_catalog.CHANNEL_FORMAT_PLATFORMS:
        rows = format_catalog.formats_for_channel(key)
        if rows:
            channels[key] = [
                {"id": row["id"], "name": row["name"], "type": row["type"], "family": family_of(row["id"]), "dimensions": row["dimensions"],
                 "interactive": bool(row["interactive"]), "aggregated": bool(row["aggregated_cost"]),
                 # A vitrine de interativos mostra descrição, categoria, imagem e a peça de teste.
                 **({"description": text(row.get("description"))[:320], "category": text(row.get("category")),
                     "image": text(row.get("image_url")), "demo": text(row.get("creative_url"))} if row["interactive"] else {})}
                for row in rows
            ]
    return {
        "tipos": [{"id": key, **meta} for key, meta in TATICA_TIPOS.items()],
        "segmentos": list(SEGMENTOS),
        "families": [{"id": key, **meta} for key, meta in FORMAT_FAMILIES.items()],
        "dco": dict(FORMATO_DCO),
        "dcoBlockedGroups": sorted(DCO_BLOCKED_GROUPS),
        "network": format_catalog.NETWORK_CHANNEL,
        "channelFormats": channels,
    }


def _segmento(value: Any) -> str:
    key = text(value).upper().replace(" ", "").replace("+", "").replace("/", "")
    return key if key in SEGMENTOS else ""


def _peso(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", ".").replace("%", ""))
    except (TypeError, ValueError):
        return None
    return round(number, 1) if 0 < number <= 100 else None


def normalize_taticas(raw: Any, canais: Any) -> list[dict]:
    """Táticas válidas para os canais escolhidos; descarta o que não fecha com o mix e com o catálogo."""
    selected = [text(key) for key in as_list(canais) if text(key) in CHANNEL_CATALOG]
    out: list[dict] = []
    seen: set[str] = set()
    for item in as_list(raw):
        row = as_dict(item)
        tipo = text(row.get("tipo") or row.get("id")).lower()
        if tipo not in TATICA_TIPOS or tipo in seen:
            continue
        channels = []
        for key in as_list(row.get("canais")):
            key = text(key)
            if key in selected and key not in channels:
                channels.append(key)
        if not channels:
            continue
        allowed = {
            fmt["id"] for key in channels for fmt in format_catalog.formats_for_channel(key)
        }
        formats: list[str] = []
        for value in as_list(row.get("formatos")):
            if text(value).lower() in {"dco", "criativo dinamico", "criativo dinâmico", "dynamic creative"}:
                if any(dco_allowed(key) for key in channels) and FORMATO_DCO["id"] not in formats:
                    formats.append(FORMATO_DCO["id"])
                continue
            slug = format_catalog.resolve_id(value, allowed)
            if slug and slug not in formats:
                formats.append(slug)
        out.append({
            "tipo": tipo,
            "canais": channels,
            "formatos": formats,
            "tipos_formato": _families(row.get("tipos_formato"), families_for_channels(channels), formats),
            "segmento": _segmento(row.get("segmento")),
            "peso": _peso(row.get("peso")),
        })
        seen.add(tipo)
    weights = [row["peso"] for row in out]
    if len(out) >= 2 and all(weights):
        total = sum(weights)
        for row in out:
            row["peso"] = round(row["peso"] * 100 / total, 1)
    else:
        # Peso só vale quando todas as frentes têm o seu; do contrário vem do mix.
        for row in out:
            row["peso"] = None
    return out


def catalog_formats(taticas: list[dict]) -> list[str]:
    """Formatos do catálogo escolhidos nas táticas, sem DCO, sem repetir."""
    slugs: list[str] = []
    for row in taticas:
        for fid in row.get("formatos") or []:
            if fid != FORMATO_DCO["id"] and fid not in slugs:
                slugs.append(fid)
    return slugs


def interactive_formats(taticas: list[dict]) -> list[str]:
    return [slug for slug in catalog_formats(taticas) if format_catalog.by_id(slug).get("interactive")]


def dco_channels(taticas: list[dict]) -> list[str]:
    """Canais que rodam DCO, na ordem em que aparecem nas táticas."""
    keys: list[str] = []
    for row in taticas:
        if FORMATO_DCO["id"] in (row.get("formatos") or []):
            for key in row.get("canais") or []:
                if dco_allowed(key) and key not in keys:
                    keys.append(key)
    return keys


def tatica_by_channel(taticas: list[dict]) -> dict[str, list[str]]:
    """Táticas de cada canal, na ordem declarada. Um canal pode estar em mais de uma."""
    out: dict[str, list[str]] = {}
    for row in taticas:
        for key in row.get("canais") or []:
            if row["tipo"] not in out.setdefault(key, []):
                out[key].append(row["tipo"])
    return out


def hero_scope(taticas: list[dict]) -> set[str]:
    """Canais entre os quais sai o canal de maior peso: os da tática de impacto, se houver."""
    for row in taticas:
        if row.get("tipo") == "impacto" and row.get("canais"):
            return set(row["canais"])
    return set()


def _surface(slug: str) -> str:
    row = format_catalog.by_id(slug)
    if row.get("type") in {"video", "ctv"}:
        return "ctv"
    return "portal" if row.get("interactive") else "display"


def formats_for_channel(channel_id: str, taticas: list[dict]) -> list[str]:
    """Formatos do catálogo que as táticas escolheram para o canal, na ordem das táticas."""
    out: list[str] = []
    for row in taticas:
        if channel_id in (row.get("canais") or []):
            allowed = {fmt["id"] for fmt in format_catalog.formats_for_channel(channel_id)}
            for fid in row.get("formatos") or []:
                if fid in allowed and fid not in out:
                    out.append(fid)
    return out


def primary_format(channel_id: str, taticas: list[dict]) -> dict | None:
    """Formato principal que a tática impõe ao canal; None deixa valer o catálogo.

    A tática de impacto manda: o primeiro formato dela no canal. Sem formato de catálogo, vale o DCO.
    """
    ordered = sorted(taticas, key=lambda row: 0 if row.get("tipo") == "impacto" else 1)
    for row in ordered:
        if channel_id in (row.get("canais") or []):
            for fid in formats_for_channel(channel_id, [row]):
                return {"id": fid, "label": formato_label(fid), "surface": _surface(fid)}
    if channel_id in dco_channels(taticas):
        return dict(DCO_PRIMARY)
    return None


def taticas_for_prompt(taticas: list[dict], mix: list[dict]) -> list[dict]:
    """Táticas em linguagem do plano, com o peso de cada frente."""
    labels = {text(row.get("id")): text(row.get("label") or row.get("id")) for row in mix}
    pcts = {text(row.get("id")): row.get("pct") for row in mix}
    sharing = tatica_by_channel(taticas)
    out = []
    for row in taticas:
        if row.get("peso"):
            weight = row["peso"]
        else:
            # Canal dividido entre frentes entra na conta por igual.
            weight = sum(float(pcts.get(key) or 0) / max(1, len(sharing.get(key, [1]))) for key in row["canais"])
        entry = {
            "tatica": TATICA_TIPOS[row["tipo"]]["label"],
            "tipo": row["tipo"],
            "para_que": TATICA_TIPOS[row["tipo"]]["hint"],
            "canais": [labels.get(key) or key for key in row["canais"]],
            "formatos": [formato_label(fid) for fid in row["formatos"]],
            "tipos_de_formato": [family_label(key) for key in row.get("tipos_formato") or []],
        }
        if weight:
            entry["peso_pct"] = round(weight, 1)
        if row.get("segmento"):
            entry["recorte_de_portais"] = f"classes {row['segmento']}"
        out.append(entry)
    return out


def problems(taticas: list[dict], canais: Any) -> list[str]:
    """Avisos para a revisão: o que a tática prometeu e o mix não entrega."""
    selected = {text(key) for key in as_list(canais)}
    found = []
    for row in taticas:
        label = TATICA_TIPOS[row["tipo"]]["label"]
        if row.get("segmento") and format_catalog.NETWORK_CHANNEL not in selected:
            found.append(f"{label}: o recorte {row['segmento']} precisa da Rede de portais e sites no mix.")
        if row["tipo"] == "impacto" and not row["formatos"]:
            found.append(f"{label}: escolha os formatos que a frente vai veicular.")
    return found
