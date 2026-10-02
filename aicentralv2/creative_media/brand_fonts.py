"""Brand typography shared by Workspace and Studio.

A brand keeps its fonts in ``cx_clients.brand_profile.fonts`` (family, role, classification...). This
module adds the font *file* to that same entry when someone uploads it, from Workspace or from Studio,
so both products read one source of truth; and it resolves the file the Studio draws text with.

Resolution order for a role (display/body):
  1. a file uploaded for the brand (entry["file_url"])
  2. a free family bundled with the Studio (static/fonts/brand/<Family>-<Weight>.ttf)
  3. a neutral fallback of the same classification (static/fonts/OpenSans-Regular.ttf)
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path

from PIL import ImageFont

FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}
MAX_FONT_BYTES = 8 * 1024 * 1024
UPLOAD_PREFIX = "/static/uploads/brand_fonts/"


def _static_root():
    from flask import current_app
    return Path(current_app.static_folder).resolve()


def bundled_dir():
    return Path(__file__).resolve().parents[1] / "static" / "fonts" / "brand"


def fallback_font():
    return Path(__file__).resolve().parents[1] / "static" / "fonts" / "OpenSans-Regular.ttf"


def _key(family):
    return re.sub(r"[^a-z0-9]", "", str(family or "").lower())


def _bundled(family, bold):
    folder = bundled_dir()
    if not folder.is_dir():
        return None
    wanted = _key(family)
    weights = ("Bold", "SemiBold", "Medium", "Regular") if bold else ("Regular", "Medium", "Book")
    files = {path.stem.lower(): path for path in folder.glob("*.[ot]tf")}
    for weight in weights:
        for stem, path in files.items():
            base, _, style = stem.partition("-")
            if _key(base) == wanted and style == weight.lower():
                return path
    return None


# Commercial families the Studio cannot ship, mapped to a free family of the same construction.
SUBSTITUTES = {
    "gotham": "Montserrat", "proximanova": "Montserrat", "avenir": "Montserrat", "futura": "Montserrat",
    "helveticaneue": "Inter", "helvetica": "Inter", "arial": "Inter", "sfprodisplay": "Inter", "sfpro": "Inter",
}


def _substitute(family):
    key = _key(family)
    for name, free in SUBSTITUTES.items():
        if key.startswith(name):
            return free
    return None


def _uploaded(entry):
    url = str(entry.get("file_url") or "")
    if not url.startswith(UPLOAD_PREFIX):
        return None
    try:
        path = (_static_root() / url.removeprefix("/static/")).resolve()
        path.relative_to(_static_root())
    except (RuntimeError, ValueError):
        return None
    return path if path.is_file() else None


def resolve_font(brand_context, role="display", bold=False):
    """Font file and family the Studio should draw with, plus whether it is the brand's own."""
    fonts = brand_context.get("fonts") if isinstance(brand_context, dict) and isinstance(brand_context.get("fonts"), list) else []
    ordered = sorted(fonts, key=lambda item: 0 if str(item.get("role") or "") == role else 1)
    for entry in ordered:
        if not isinstance(entry, dict):
            continue
        path = _uploaded(entry)
        if path:
            return {"path": path, "family": entry.get("family") or path.stem, "source": "brand_upload"}
        if entry.get("family"):
            path = _bundled(entry["family"], bold)
            if path:
                return {"path": path, "family": entry["family"], "source": "bundled"}
    for entry in ordered:
        substitute = _substitute(entry.get("family")) if isinstance(entry, dict) else None
        path = _bundled(substitute, bold) if substitute else None
        if path:
            return {"path": path, "family": substitute, "source": "substitute", "requested": entry.get("family")}
    for family in ("Inter", "Open Sans"):  # neutral, licensed for embedding
        path = _bundled(family, bold)
        if path:
            return {"path": path, "family": family, "source": "fallback"}
    return {"path": fallback_font(), "family": "Open Sans", "source": "fallback"}


def keep_font_files(new_fonts, old_fonts):
    """Carry uploaded files over when a form rewrites the font list by family name."""
    files = {
        _key(item.get("family")): {key: item[key] for key in ("file_url", "file_style") if item.get(key)}
        for item in (old_fonts or []) if isinstance(item, dict) and item.get("file_url")
    }
    return [{**item, **files.get(_key(item.get("family")), {})} if isinstance(item, dict) else item for item in (new_fonts or [])]


def save_brand_font(client_id, upload, role="display"):
    """Store an uploaded font and attach it to the brand profile (Workspace and Studio share it)."""
    filename = str(getattr(upload, "filename", "") or "")
    extension = Path(filename).suffix.lower()
    if extension not in FONT_EXTENSIONS:
        raise ValueError("Envie a fonte em TTF, OTF, WOFF ou WOFF2.")
    content = upload.read(MAX_FONT_BYTES + 1)
    if not content or len(content) > MAX_FONT_BYTES:
        raise ValueError("O arquivo da fonte precisa ter até 8 MB.")
    try:
        font = ImageFont.truetype(io.BytesIO(content), 24)
        family, style = font.getname()
    except OSError as exc:
        raise ValueError("Não foi possível ler este arquivo de fonte.") from exc
    role = role if role in {"display", "body", "accent", "legal"} else "display"
    digest = hashlib.sha256(content).hexdigest()[:24]
    target = _static_root() / "uploads" / "brand_fonts"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{digest}{extension}").write_bytes(content)
    file_url = f"{UPLOAD_PREFIX}{digest}{extension}"

    from ..db import get_db
    connection = get_db()
    with connection.cursor() as cursor:
        cursor.execute("SELECT brand_profile FROM cx_clients WHERE id = %s FOR UPDATE", (int(client_id),))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Marca não encontrada.")
        profile = row["brand_profile"] if isinstance(row["brand_profile"], dict) else {}
        fonts = [item for item in (profile.get("fonts") or []) if isinstance(item, dict)]
        entry = next((item for item in fonts if _key(item.get("family")) == _key(family)), None)
        if entry is None:
            entry = {"family": family, "classification": "", "role": role, "weight": "", "style": "", "source": "manual", "confidence": 1.0}
            fonts.insert(0, entry)
        entry.update({"file_url": file_url, "file_style": style, "role": entry.get("role") or role})
        cursor.execute(
            "UPDATE cx_clients SET brand_profile = COALESCE(brand_profile, '{}'::jsonb) || %s::jsonb, updated_at = NOW() WHERE id = %s",
            (json.dumps({"fonts": fonts}), int(client_id)),
        )
    connection.commit()
    return {"family": family, "style": style, "file_url": file_url, "role": entry["role"]}
