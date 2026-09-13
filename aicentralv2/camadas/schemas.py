"""IDs públicos e validação leve da Camadas V2."""

from __future__ import annotations

import re
import uuid

PUBLIC_PREFIXES = {
    "creative": "crt_",
    "job": "job_",
    "element": "el_",
    "collection": "col_",
    "asset": "ast_",
    "generation": "gen_",
}

TEXT_ROLES = (
    "headline",
    "support",
    "subtitle",
    "price",
    "cta",
    "legal",
    "date",
    "venue",
    "person_label",
    "logo_text",
)

IMAGE_ROLES = (
    "background",
    "person",
    "product",
    "logo",
    "illustration",
    "graphic",
    "badge",
    "decoration",
    "foreground",
    "shadow",
)

PROVENANCE = (
    "original",
    "cutout",
    "html",
    "generated",
    "upload",
)

PROVENANCE_ALIASES = {
    "original": "original",
    "cutout": "cutout",
    "recorte_original": "cutout",
    "extracted": "cutout",
    "html": "html",
    "generated": "generated",
    "generated_ai": "generated",
    "reconstructed": "original",
    "upload": "upload",
    "upload_manual": "upload",
}

PROVENANCE_LABELS = {
    "original": "Original",
    "cutout": "Recorte original",
    "html": "HTML",
    "generated": "Gerado por IA",
    "upload": "Upload manual",
}

ASSET_KINDS = (
    "person",
    "product",
    "logo",
    "badge",
    "graphic",
    "illustration",
    "background",
    "composition",
)

CLIENT_INJECTIONS = ("predictor", "text_callable", "image_callable")

_PUBLIC_ID = re.compile(r"^(crt|job|el|col|ast|gen)_[a-f0-9]{22}$")


def new_public_id(kind):
    prefix = PUBLIC_PREFIXES.get(kind)
    if not prefix:
        raise ValueError("Tipo de id inválido.")
    return prefix + uuid.uuid4().hex[:22]


def is_public_id(value, kind=None):
    text = str(value or "").strip()
    if kind:
        prefix = PUBLIC_PREFIXES.get(kind)
        return bool(prefix) and text.startswith(prefix) and bool(_PUBLIC_ID.match(text))
    return bool(_PUBLIC_ID.match(text))


def strip_client_injections(payload):
    clean = dict(payload or {})
    for key in CLIENT_INJECTIONS:
        clean.pop(key, None)
    return clean


def normalize_provenance(value, layer_type="image"):
    key = str(value or "").strip().lower()
    if key in PROVENANCE_ALIASES:
        return PROVENANCE_ALIASES[key]
    if layer_type == "text":
        return "html"
    return "cutout"


def asset_kind_from_role(role, layer_type="image"):
    mapping = {
        "person": "person",
        "product": "product",
        "logo": "logo",
        "badge": "badge",
        "person_label": "badge",
        "graphic": "graphic",
        "decoration": "graphic",
        "illustration": "illustration",
        "background": "background",
    }
    if layer_type == "text":
        return "composition"
    return mapping.get(str(role or "").strip(), "graphic")


def optional_int(value):
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Identificador numérico inválido.") from exc
    if number <= 0:
        raise ValueError("Identificador numérico inválido.")
    return number
