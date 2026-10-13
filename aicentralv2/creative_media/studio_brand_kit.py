"""O que a marca entrega ao Vídeo: logo oficial, cores e fonte, num formato curto que a tela mostra.

O Vídeo usa isto para dizer, antes de gerar, o que vai aparecer: com qual logo, em quais cores e com que fonte.
Nada aqui gera imagem nem cobra crédito.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

LOGO_MAX_SIDE = 640
LOGO_VARIANTS = 3


def font_url(path):
    """URL pública de um arquivo de fonte servido pelo próprio Studio, ou "" quando ele fica fora de /static."""
    static_root = Path(__file__).resolve().parents[1] / "static"
    try:
        relative = Path(path).resolve().relative_to(static_root.resolve())
    except (TypeError, ValueError, OSError):
        return ""
    return "/static/" + relative.as_posix()


def brand_kit(brand):
    from .brand_fonts import resolve_font, video_font_path
    from .studio_storyboard import _HEX, color_name

    brand = brand if isinstance(brand, dict) else {}
    assets = brand.get("assets") if isinstance(brand.get("assets"), dict) else {}
    logos = [str(url) for url in [brand.get("logo_url"), *(assets.get("logo") or [])] if url]
    palette = []
    for code in brand.get("palette") or []:
        code = str(code or "").strip()
        if _HEX.fullmatch(code) and code.lower() not in {item["hex"] for item in palette}:
            palette.append({"hex": code.lower(), "name": color_name(code)})
    font = resolve_font(brand, "display", bold=True)
    return {
        "name": str(brand.get("name") or ""),
        "logo_url": logos[0] if logos else "",
        "logo_count": len(dict.fromkeys(logos)),
        "palette": palette[:6],
        "primary_color": palette[0]["hex"] if palette else "",
        "font": {
            "family": font.get("family") or "Open Sans",
            # Só fontes que o editor também desenha no MP4; o navegador mostra a mesma.
            "url": font_url(font.get("path")) if video_font_path(font_url(font.get("path"))) else "",
            # brand_upload: arquivo da marca; bundled: a família pedida, incluída no Studio;
            # substitute: família livre parecida; fallback: Open Sans/Inter, a marca não informou fonte.
            "source": font.get("source") or "fallback",
            "requested": font.get("requested") or "",
        },
        "has_references": bool(assets.get("references")),
    }


def logo_variants_data(brand):
    """As variantes do logo oficial como PNG pequeno em data URL, para o worker aplicar sem contexto de app."""
    from .studio_create import load_brand_logos

    encoded = []
    for image in load_brand_logos(brand)[:LOGO_VARIANTS]:
        image = image.convert("RGBA")
        image.thumbnail((LOGO_MAX_SIDE, LOGO_MAX_SIDE))
        output = io.BytesIO()
        image.save(output, "PNG", optimize=True)
        encoded.append("data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii"))
    return encoded
