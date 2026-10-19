"""Táticas da campanha: impacto e remarketing, com formatos, DCO e recorte de portais.

O mix diz quanto cada canal pesa. As táticas dizem o que cada frente da campanha
faz: quais canais a compõem, que formatos usa e, nos portais, qual recorte de
audiência (classes AB, por exemplo) orienta a seleção editorial. Sem táticas, o
plano continua igual ao de antes.
"""

from __future__ import annotations

from typing import Any

from .catalog import CHANNEL_CATALOG, INTERATIVOS_FORMATS, PORTAL_CHANNELS
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

FORMATO_DCO = {"id": "dco", "label": "DCO · anúncio dinâmico"}
DCO_PRIMARY = {"id": "dco_dynamic", "label": "DCO · anúncio dinâmico", "surface": "display"}

# Recortes de classe aceitos para orientar a escolha dos portais.
SEGMENTOS = ("A", "AB", "B", "BC", "C")

# DCO monta a peça com dados do usuário: precisa de tela com anúncio de imagem ou vídeo.
DCO_BLOCKED_GROUPS = {"ooh", "places", "audio", "ctv", "data"}

INTERATIVOS_IDS = tuple(item["id"] for item in INTERATIVOS_FORMATS)
INTERATIVOS_HOSTS = PORTAL_CHANNELS + ("dv360",)


def formato_label(format_id: str) -> str:
    if format_id == FORMATO_DCO["id"]:
        return FORMATO_DCO["label"]
    for item in INTERATIVOS_FORMATS:
        if item["id"] == format_id:
            return item["label"]
    return format_id


def spec_for_js() -> dict:
    return {
        "tipos": [{"id": key, **meta} for key, meta in TATICA_TIPOS.items()],
        "segmentos": list(SEGMENTOS),
        "dco": dict(FORMATO_DCO),
        "dcoBlockedGroups": sorted(DCO_BLOCKED_GROUPS),
        "interativosHosts": list(INTERATIVOS_HOSTS),
    }


def _format_id(value: Any) -> str:
    key = text(value).lower().replace("í", "i").replace("é", "e")
    if key in {"dco", "criativo dinamico", "criativo dinâmico", "dynamic creative"}:
        return FORMATO_DCO["id"]
    return key


def _segmento(value: Any) -> str:
    key = text(value).upper().replace(" ", "").replace("+", "").replace("/", "")
    return key if key in SEGMENTOS else ""


def normalize_taticas(raw: Any, canais: Any) -> list[dict]:
    """Táticas válidas para os canais escolhidos; descarta o que não fecha com o mix."""
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
        formats = []
        for value in as_list(row.get("formatos")):
            fid = _format_id(value)
            if fid in formats:
                continue
            if fid == FORMATO_DCO["id"]:
                usable = [
                    key for key in channels
                    if (CHANNEL_CATALOG.get(key) or {}).get("group") not in DCO_BLOCKED_GROUPS
                    and key != "interativos"
                ]
                if usable:
                    formats.append(fid)
            elif fid in INTERATIVOS_IDS and "interativos" in channels:
                formats.append(fid)
        out.append({
            "tipo": tipo,
            "canais": channels,
            "formatos": formats,
            "segmento": _segmento(row.get("segmento")),
        })
        seen.add(tipo)
    return out


def interativos_from_taticas(taticas: list[dict]) -> list[str]:
    """Formatos interativos declarados pelas táticas, sem repetir e na ordem de leitura."""
    formats: list[str] = []
    for row in taticas:
        for fid in row.get("formatos") or []:
            if fid in INTERATIVOS_IDS and fid not in formats:
                formats.append(fid)
    return formats


def dco_channels(taticas: list[dict]) -> list[str]:
    """Canais que rodam DCO, na ordem em que aparecem nas táticas."""
    keys: list[str] = []
    for row in taticas:
        if FORMATO_DCO["id"] in (row.get("formatos") or []):
            for key in row.get("canais") or []:
                if (
                    (CHANNEL_CATALOG.get(key) or {}).get("group") not in DCO_BLOCKED_GROUPS
                    and key != "interativos"
                    and key not in keys
                ):
                    keys.append(key)
    return keys


def tatica_by_channel(taticas: list[dict]) -> dict[str, str]:
    """Tática de cada canal; o primeiro tipo declarado vence quando o canal está em duas."""
    out: dict[str, str] = {}
    for row in taticas:
        for key in row.get("canais") or []:
            out.setdefault(key, row["tipo"])
    return out


def hero_scope(taticas: list[dict]) -> set[str]:
    """Canais entre os quais sai o canal de maior peso: os da tática de impacto, se houver."""
    for row in taticas:
        if row.get("tipo") == "impacto" and row.get("canais"):
            return set(row["canais"])
    return set()


def primary_format(channel_id: str, taticas: list[dict]) -> dict | None:
    """Formato principal que a tática impõe ao canal; None deixa valer o catálogo."""
    if channel_id in dco_channels(taticas):
        return dict(DCO_PRIMARY)
    if channel_id == "interativos":
        formats = interativos_from_taticas(taticas)
        if formats:
            return {"id": formats[0], "label": f"{formato_label(formats[0])} interativo", "surface": "portal"}
    return None


def taticas_for_prompt(taticas: list[dict], mix: list[dict]) -> list[dict]:
    """Táticas em linguagem do plano, com o peso somado dos canais de cada uma."""
    labels = {text(row.get("id")): text(row.get("label") or row.get("id")) for row in mix}
    pcts = {text(row.get("id")): row.get("pct") for row in mix}
    out = []
    for row in taticas:
        total = sum(float(pcts.get(key) or 0) for key in row["canais"])
        entry = {
            "tatica": TATICA_TIPOS[row["tipo"]]["label"],
            "tipo": row["tipo"],
            "para_que": TATICA_TIPOS[row["tipo"]]["hint"],
            "canais": [labels.get(key) or key for key in row["canais"]],
            "formatos": [formato_label(fid) for fid in row["formatos"]],
        }
        if total:
            entry["peso_no_mix_pct"] = round(total, 1)
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
        if row.get("segmento") and not selected.intersection(INTERATIVOS_HOSTS):
            found.append(f"{label}: o recorte {row['segmento']} precisa de portais no mix.")
        if "interativos" in row["canais"] and not interativos_from_taticas([row]):
            found.append(f"{label}: escolha os formatos interativos.")
    return found
