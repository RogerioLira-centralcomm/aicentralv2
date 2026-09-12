"""Regras de negócio e composição de prompts da Modelagem de Criativos."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
import base64
import json
import os
import re
import secrets

from .creative_brand_analysis import (
    CreativeBrandAnalyzer,
    _compact_web_evidence,
    _fonts,
    _normalized_public_url,
    format_copy_system_lines,
)
from .creative_modeling_generation import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_TEXT_MODEL,
    CreativeGenerationClient,
    build_display_motion_payload,
    build_higgsfield_payload,
)
from .creative_modeling_repository import (
    HOUSE_CRM_CLIENT_ID,
    CreativeModelingRepository,
    CreativeNotFoundError,
)
from .creative_format_compose import (
    compose_native_result,
    crop_safe_area_collage,
    wipe_safe_areas,
)
from .creative_html_compose import (
    compose_studio_result,
    parse_format_size,
    pack_html5_zip,
    render_card_fragment,
    render_html5_player,
)
from .creative_modeling_fx import annotate_cost, brl_from_usd
from .creative_format_geometry import (
    ALLOWED_SCENE_COUNTS,
    PLACEMENT_ZONES,
    SOCIAL_FORMAT_SLUGS,
    canvas_mismatch,
    default_render_mode,
    default_social_placement,
    format_beat,
    format_direction,
    hygiene_instruction,
    placement_zone_for,
    resolve_format_geometry,
    resolve_scene_count,
    scene_count_for_format,
    should_compose,
)
from .creative_modeling_storage import CreativeAssetStorage
from .creative_image_fidelity import (
    DRAFT,
    PUBLISH,
    apply_publish_upgrade,
    describe_image_tiers,
    image_tier_estimate_usd,
    quote_image_publish,
    resolve_image_tier,
)
from .creative_brand_dna import (
    apply_brand_dna_to_layers,
    attach_brand_dna_to_scenes,
    check_brand_dna,
    materialize_brand_dna,
)
from .creative_compose_library import (
    LIBRARY_FAMILIES,
    apply_script_params,
    catalog_templates,
    catalog_variations,
    normalize_compose_choice,
    persisted_variation_id,
    propose_variation_adjust,
    resolve_variation,
    sanitize_compose_regions,
    schema_for_family,
    suggest_compose_template,
)
from .creative_construct_params import (
    ENGINE_CONSTRUCT,
    describe_unfold_paths,
    model_unit_usd,
    normalize_context_design,
    quote_unfold_path,
    resolve_construct_path,
    scene_copy_on_frame,
    scene_key_for_slug,
)
from .creative_modeling_prompts import (
    ANTI_AI_LOOK,
    BRIEF_LOCK_RULES,
    apply_render_mode_to_prompt,
    compose_format_mockup_prompt,
    normalize_locks,
    unfold_ab_instruction,
    unfold_image_lock,
)


BRAND_ASSET_ROLES = frozenset({
    "logo",
    "reference",
    "creative",
    "background",
    "support",
    "icon",
    "cta_style",
})

MOCKUPS = {
    "portal": (
        "Photorealistic mockup of a news/content portal on a desktop "
        "browser, article layout visible around the ad unit."
    ),
    "tv": (
        "Photorealistic mockup of a smart TV screen (16:9), living room, "
        "soft ambient lighting."
    ),
    "celular": (
        "Photorealistic mockup of a vertical mobile phone (iPhone 17 Pro), "
        "front-facing, no extra UI chrome."
    ),
    "tablet": (
        "Photorealistic mockup of a tablet in landscape orientation, "
        "generous margins."
    ),
}

PLACEMENT_CONTEXTS = {"portal", "tv", "celular", "tablet", "social"}
PLACEMENT_FITS = {"contain", "cover", "fill"}
RESPONSIVE_MODES = {"scale", "reflow", "fixed"}
BEHAVIOR_TYPES = {
    "static", "hotspot", "flip", "reveal", "compare", "quiz", "carousel", "video"
}
BEHAVIOR_TRIGGERS = {
    "none", "hover_tap", "click", "drag_vertical", "drag_horizontal",
    "view", "auto",
}
VIEWER_KINDS = {"portal", "tv", "social"}
VIEWER_PALETTE_KEYS = {"primary", "secondary", "surface", "canvas", "text"}


def _text(value, field, required=False, max_length=None):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} deve ser texto.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} é obrigatório.")
    if max_length and len(value) > max_length:
        raise ValueError(f"{field} deve ter no máximo {max_length} caracteres.")
    return value or None


def _flow_kind(record):
    record = record if isinstance(record, dict) else {}
    brief = record.get("creative_brief")
    if not isinstance(brief, dict):
        brief = {}
    kind = brief.get("flow_kind") or record.get("flow_kind") or "model"
    return "unfold" if kind == "unfold" else "model"


def _brief_locks(record):
    record = record if isinstance(record, dict) else {}
    brief = record.get("creative_brief")
    if not isinstance(brief, dict):
        brief = {}
    return normalize_locks(brief.get("locks") or record.get("locks"))


def _brief_path(record):
    record = record if isinstance(record, dict) else {}
    brief = record.get("creative_brief")
    if not isinstance(brief, dict):
        brief = {}
    return resolve_construct_path(brief.get("construct_path") or brief)


def _plan_construct_path(payload):
    payload = payload if isinstance(payload, dict) else {}
    nested = payload.get("construct_path")
    merged = dict(nested) if isinstance(nested, dict) else {}
    for key in ("engine", "scene_pack", "image_model", "fidelity"):
        if payload.get(key) not in (None, ""):
            merged[key] = payload[key]
    if payload.get("flow_kind") != "unfold" and not merged.get("engine"):
        merged["engine"] = ENGINE_CONSTRUCT
    return resolve_construct_path(merged or payload)


def _campaign_pack(value):
    value = value if isinstance(value, dict) else {}
    extracted = value.get("extracted") if isinstance(value.get("extracted"), dict) else {}
    sources = []
    for item in (value.get("sources") or [])[:4]:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") if item.get("kind") in {"image", "url"} else None
        if not kind:
            continue
        sources.append({
            "kind": kind,
            "name": _text(item.get("name"), "Fonte", max_length=200),
            "asset_url": _text(item.get("asset_url"), "Arquivo", max_length=2000),
            "page_url": _text(item.get("page_url"), "URL", max_length=2000),
        })
    offer = _text(
        extracted.get("offer") or extracted.get("notes"),
        "Oferta",
        max_length=4000,
    )
    pack = {
        "sources": sources,
        "extracted": {
            "headline": _text(extracted.get("headline"), "Headline", max_length=500),
            "subhead": _text(extracted.get("subhead"), "Subhead", max_length=800),
            "cta": _text(extracted.get("cta"), "CTA", max_length=200),
            "offer": offer,
            "other_lines": _text_list(
                extracted.get("other_lines") or [], "Linhas", max_items=8
            ),
        },
        "locks": normalize_locks(value.get("locks") or extracted),
    }
    return pack


def _pack_has_signal(pack):
    pack = pack if isinstance(pack, dict) else {}
    extracted = pack.get("extracted") if isinstance(pack.get("extracted"), dict) else {}
    if any(extracted.get(key) for key in ("headline", "subhead", "cta", "offer")):
        return True
    if extracted.get("other_lines"):
        return True
    return bool(pack.get("sources"))


def _pack_message(pack):
    extracted = (pack or {}).get("extracted") or {}
    return (
        extracted.get("offer")
        or extracted.get("headline")
        or extracted.get("subhead")
        or (extracted.get("other_lines") or [None])[0]
    )


def _pack_image_urls(record):
    brief = record.get("creative_brief") if isinstance(record, dict) else {}
    if not isinstance(brief, dict):
        brief = {}
    pack = brief.get("campaign_pack") if isinstance(brief.get("campaign_pack"), dict) else {}
    urls = []
    for item in pack.get("sources") or []:
        if not isinstance(item, dict) or item.get("kind") != "image":
            continue
        url = item.get("asset_url")
        if url:
            urls.append(url)
    return urls[:2]


def _integer(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} inválido.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} inválido.") from exc
    if result <= 0:
        raise ValueError(f"{field} inválido.")
    return result


def _serialize(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return ""
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


_WHITE_HEX = {"#FFFFFF", "#FFF", "#FFFFFFFF"}


def hydrate_client_from_creative_line(client):
    """Preenche perfil vazio com a auditoria criativa já aprendida."""
    if not isinstance(client, dict):
        return client
    client = dict(client)
    profile = client.get("brand_profile")
    profile = dict(profile) if isinstance(profile, dict) else {}
    line = profile.get("creative_line")
    if not isinstance(line, dict) or not line:
        client["brand_profile"] = profile
        return client
    palette = [
        item
        for item in (line.get("color_palette") or [])
        if isinstance(item, dict) and item.get("hex")
    ]
    hexes = [item["hex"] for item in palette]
    usable = [value for value in hexes if str(value).upper() not in _WHITE_HEX]
    if not client.get("primary_color") and usable:
        client["primary_color"] = usable[0]
    if not client.get("secondary_color") and len(usable) > 1:
        client["secondary_color"] = usable[1]
    elif not client.get("secondary_color"):
        client["secondary_color"] = next(
            (value for value in hexes if value != client.get("primary_color")),
            None,
        )
    if not profile.get("color_palette") and palette:
        profile["color_palette"] = palette
    if not profile.get("brand_summary") and line.get("signature_summary"):
        profile["brand_summary"] = line["signature_summary"]
    if not profile.get("creative_guidelines"):
        bits = [str(item) for item in (line.get("composition_rules") or [])[:3]]
        bits += [str(item) for item in (line.get("must_preserve") or [])[:3]]
        if bits:
            profile["creative_guidelines"] = " ".join(bits)
    if not profile.get("forbidden_elements") and line.get("avoid"):
        profile["forbidden_elements"] = [str(item) for item in line["avoid"][:8]]
    if not profile.get("visual_motifs") and line.get("graphic_devices"):
        profile["visual_motifs"] = [str(item) for item in line["graphic_devices"][:8]]
    if not profile.get("fonts"):
        typography = (line.get("copy_system") or {}).get("typography") or {}
        family = typography.get("family")
        if family:
            profile["fonts"] = [{
                "family": str(family),
                "role": str(typography.get("role") or "display"),
            }]
    if not client.get("tone_of_voice"):
        patterns = [str(item) for item in (line.get("copy_patterns") or []) if item]
        if patterns:
            client["tone_of_voice"] = " ".join(patterns[:2])[:4000]
    client["brand_profile"] = profile
    return client


def apply_creative_line_to_context(context):
    if not isinstance(context, dict):
        return context
    hydrated = hydrate_client_from_creative_line(
        {
            "sector": context.get("client_sector") or context.get("sector"),
            "tone_of_voice": context.get("tone_of_voice"),
            "primary_color": context.get("primary_color"),
            "secondary_color": context.get("secondary_color"),
            "brand_profile": context.get("brand_profile") or {},
        }
    )
    context["client_sector"] = hydrated.get("sector") or context.get("client_sector")
    context["tone_of_voice"] = hydrated.get("tone_of_voice")
    context["primary_color"] = hydrated.get("primary_color")
    context["secondary_color"] = hydrated.get("secondary_color")
    context["brand_profile"] = hydrated.get("brand_profile") or {}
    return context


def client_identity_payload(context):
    apply_creative_line_to_context(context)
    return {
        "name": context.get("client_name") or context.get("name"),
        "sector": context.get("client_sector") or context.get("sector"),
        "tone": context.get("tone_of_voice"),
        "logo": context.get("logo_upload_path") or context.get("logo_url"),
        "primary_color": context.get("primary_color"),
        "secondary_color": context.get("secondary_color"),
        "website_url": context.get("website_url"),
        "profile": context.get("brand_profile") or {},
    }


def _campaign_client_ref(payload):
    payload = payload if isinstance(payload, dict) else {}
    source = payload.get("client_source", "creative")
    if source not in {"creative", "crm"}:
        raise ValueError("Origem do cliente inválida.")
    raw = payload.get("client_id")
    if raw in (None, ""):
        return HOUSE_CRM_CLIENT_ID, "crm"
    return _integer(raw, "Cliente"), source


def _color(value, field):
    value = _text(value, field, max_length=20)
    if value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"{field} deve usar o formato #RRGGBB.")
    return value


def _text_list(value, field, max_items=8, item_length=500):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} deve ser uma lista.")
    if len(value) > max_items:
        raise ValueError(f"{field} deve ter no máximo {max_items} itens.")
    return [
        _text(item, field, required=True, max_length=item_length)
        for item in value
    ]


def _brand_palette(value):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("Paleta da marca deve ser uma lista.")
    result = []
    seen = set()
    for item in value[:6]:
        if not isinstance(item, dict):
            continue
        color = _color(item.get("hex"), "Cor da paleta")
        if not color or color.upper() in seen:
            continue
        color = color.upper()
        seen.add(color)
        try:
            confidence = max(0.0, min(float(item.get("confidence", 0)), 1.0))
        except (TypeError, ValueError):
            confidence = 0.0
        result.append({
            "hex": color,
            "name": _text(
                item.get("name"), "Nome da cor", max_length=80
            ) or "Cor da marca",
            "usage": _text(
                item.get("usage"), "Uso da cor", max_length=240
            ) or "Uso institucional",
            "confidence": confidence,
        })
    return result


def _quality_review_data(value, force_wrong_canvas=False):
    if not isinstance(value, dict):
        raise ValueError("Revisão visual inválida.")
    try:
        score = int(value.get("score"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Pontuação da revisão visual inválida.") from exc
    if score < 0 or score > 100:
        raise ValueError("Pontuação da revisão visual deve estar entre 0 e 100.")
    warnings = _text_list(
        value.get("warnings") or [],
        "Avisos da revisão visual",
        max_items=8,
        item_length=300,
    )
    raw_checks = value.get("checks") or {}
    if not isinstance(raw_checks, dict):
        raise ValueError("Checks da revisão visual inválidos.")
    allowed_checks = {
        "language_pt_br", "cta_correct", "brand_consistent",
        "price_authorized", "continuity", "safe_area",
        "text_locked", "cta_locked", "logo_locked",
    }
    allowed_defects = {
        "dangling_line", "icon_bar", "cta_overflow",
        "wrong_canvas", "extra_chrome",
        "text_rewritten", "cta_changed", "logo_missing",
    }
    checks = {
        key: raw
        for key, raw in raw_checks.items()
        if key in allowed_checks and isinstance(raw, bool)
    }
    defects = [
        item
        for item in (value.get("defects") or [])
        if item in allowed_defects
    ]
    if (
        force_wrong_canvas or value.get("wrong_canvas") is True
    ) and "wrong_canvas" not in defects:
        defects.append("wrong_canvas")
    if "wrong_canvas" in defects:
        checks["safe_area"] = False
    if checks.get("cta_locked") is False and "cta_changed" not in defects:
        defects.append("cta_changed")
    if checks.get("text_locked") is False and "text_rewritten" not in defects:
        defects.append("text_rewritten")
    if checks.get("logo_locked") is False and "logo_missing" not in defects:
        defects.append("logo_missing")
    return {
        "approved_recommendation": value.get("approved_recommendation") is True,
        "score": score,
        "warnings": warnings,
        "checks": checks,
        "defects": defects,
    }


def _money(value, field="Orçamento"):
    try:
        result = Decimal(str(value if value not in (None, "") else "0"))
    except Exception as exc:
        raise ValueError(f"{field} inválido.") from exc
    if result < 0:
        raise ValueError(f"{field} não pode ser negativo.")
    return result.quantize(Decimal("0.000001"))


def _number(value, field, minimum=0, maximum=100):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} inválido.") from exc
    if result < minimum or result > maximum:
        raise ValueError(
            f"{field} deve estar entre {minimum:g} e {maximum:g}."
        )
    return round(result, 3)


def _placement_spec(value):
    if not isinstance(value, dict):
        raise ValueError("Especificação de posicionamento inválida.")
    context = value.get("context")
    fit = value.get("fit", "contain")
    responsive = value.get("responsive", "scale")
    if context not in PLACEMENT_CONTEXTS:
        raise ValueError("Contexto do mockup inválido.")
    if fit not in PLACEMENT_FITS:
        raise ValueError("Ajuste da peça inválido.")
    if responsive not in RESPONSIVE_MODES:
        raise ValueError("Comportamento responsivo inválido.")
    viewport = value.get("viewport")
    slot = value.get("slot")
    if not isinstance(viewport, dict) or not isinstance(slot, dict):
        raise ValueError("Viewport e slot são obrigatórios.")
    width = int(_number(viewport.get("width"), "Largura do viewport", 240, 7680))
    height = int(_number(viewport.get("height"), "Altura do viewport", 240, 4320))
    normalized_slot = {
        "x": _number(slot.get("x"), "Posição X"),
        "y": _number(slot.get("y"), "Posição Y"),
        "width": _number(slot.get("width"), "Largura do slot", 1, 100),
        "height": _number(slot.get("height"), "Altura do slot", 1, 100),
    }
    if normalized_slot["x"] + normalized_slot["width"] > 100:
        raise ValueError("O slot ultrapassa a largura do viewport.")
    if normalized_slot["y"] + normalized_slot["height"] > 100:
        raise ValueError("O slot ultrapassa a altura do viewport.")
    zone = value.get("placement_zone")
    if zone in (None, ""):
        normalized_zone = None
    elif zone not in PLACEMENT_ZONES:
        raise ValueError("Zona de posicionamento inválida.")
    else:
        normalized_zone = zone
    spec = {
        "context": context,
        "viewport": {"width": width, "height": height},
        "slot": normalized_slot,
        "fit": fit,
        "responsive": responsive,
    }
    if normalized_zone:
        spec["placement_zone"] = normalized_zone
    return spec


def _behavior_spec(value):
    if not isinstance(value, dict):
        raise ValueError("Especificação de comportamento inválida.")
    kind = value.get("type", "static")
    trigger = value.get("trigger", "none")
    if kind not in BEHAVIOR_TYPES or trigger not in BEHAVIOR_TRIGGERS:
        raise ValueError("Comportamento ou acionamento inválido.")
    return {
        "type": kind,
        "trigger": trigger,
        "transition_ms": int(
            _number(value.get("transition_ms", 0), "Duração da transição", 0, 5000)
        ),
    }


def _viewer_profile_data(value):
    if not isinstance(value, dict):
        raise ValueError("Ambiente de mídia inválido.")
    slug = _text(value.get("slug"), "Slug do ambiente", required=True, max_length=50)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Slug do ambiente inválido.")
    viewer_kind = value.get("viewer_kind")
    if viewer_kind not in VIEWER_KINDS:
        raise ValueError("Tipo de ambiente inválido.")
    palette = value.get("palette") or {}
    shell = value.get("shell_spec") or {}
    if not isinstance(palette, dict) or not isinstance(shell, dict):
        raise ValueError("Configuração do ambiente inválida.")
    safe_palette = {
        key: _color(raw, f"Cor {key}")
        for key, raw in palette.items()
        if key in VIEWER_PALETTE_KEYS and raw not in (None, "")
    }
    nav = shell.get("nav") or []
    if not isinstance(nav, list) or len(nav) > 8:
        raise ValueError("Navegação do ambiente inválida.")
    safe_shell = {
        key: _text(raw, f"Configuração {key}", max_length=50)
        for key, raw in shell.items()
        if key in {
            "masthead", "density", "headline_style", "layout",
            "edition_label", "account_label",
        }
        and raw is not None
    }
    safe_shell["nav"] = [
        _text(item, "Item de navegação", required=True, max_length=40)
        for item in nav
    ]
    network_links = shell.get("network_links") or []
    if not isinstance(network_links, list) or len(network_links) > 10:
        raise ValueError("Links da rede do ambiente inválidos.")
    safe_shell["network_links"] = [
        _text(item, "Link da rede", required=True, max_length=30)
        for item in network_links
    ]
    hero = shell.get("hero") or {}
    if hero:
        if not isinstance(hero, dict):
            raise ValueError("Hero do ambiente inválido.")
        safe_shell["hero"] = {
            "eyebrow": _text(hero.get("eyebrow"), "Chamada do hero", max_length=60),
            "title": _text(
                hero.get("title"), "Título do hero", required=True, max_length=100
            ),
            "description": _text(
                hero.get("description"), "Descrição do hero", max_length=180
            ),
            "image": _text(hero.get("image"), "Imagem do hero", max_length=255),
        }
    sections = shell.get("sections") or []
    if not isinstance(sections, list) or len(sections) > 3:
        raise ValueError("Seções do catálogo inválidas.")
    safe_sections = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Seção do catálogo inválida.")
        items = section.get("items") or []
        if not isinstance(items, list) or len(items) > 8:
            raise ValueError("Itens do catálogo inválidos.")
        safe_sections.append({
            "title": _text(
                section.get("title"),
                "Título da seção",
                required=True,
                max_length=80,
            ),
            "ranked": section.get("ranked") is True,
            "card_shape": (
                section.get("card_shape")
                if section.get("card_shape") in {"landscape", "portrait"}
                else "landscape"
            ),
            "items": [
                {
                    "title": _text(
                        item.get("title"),
                        "Título do catálogo",
                        required=True,
                        max_length=80,
                    ),
                    "image": _text(
                        item.get("image"),
                        "Imagem do catálogo",
                        max_length=255,
                    ),
                    "category": _text(
                        item.get("category"),
                        "Categoria editorial",
                        max_length=40,
                    ),
                    "summary": _text(
                        item.get("summary"),
                        "Resumo editorial",
                        max_length=180,
                    ),
                    "time": _text(
                        item.get("time"),
                        "Horário editorial",
                        max_length=40,
                    ),
                }
                for item in items
                if isinstance(item, dict)
            ],
        })
    safe_shell["sections"] = safe_sections
    logo = _text(value.get("logo_asset_ref"), "Logo do ambiente", max_length=255)
    if logo and not re.fullmatch(
        r"/static/images/creative-viewers/[a-z0-9.-]+", logo
    ):
        raise ValueError("Logo do ambiente inválido.")
    return {
        **value,
        "slug": slug,
        "viewer_kind": viewer_kind,
        "palette": safe_palette,
        "shell_spec": safe_shell,
        "logo_asset_ref": logo,
        "disclaimer": _text(
            value.get("disclaimer"),
            "Aviso do ambiente",
            required=True,
            max_length=200,
        ),
    }


def _collection_sessions(assets):
    sessions = []
    index = {}
    for asset in assets or []:
        kind = asset.get("viewer_kind") or "portal"
        key = asset.get("viewer_slug") or kind
        if key not in index:
            session = {
                "key": key,
                "kind": kind,
                "name": asset.get("viewer_name") or (
                    "Streaming" if kind == "tv" else "Portais"
                ),
                "logo": asset.get("viewer_logo_asset_ref"),
                "channel_name": asset.get("channel_name"),
                "assets": [],
            }
            index[key] = session
            sessions.append(session)
        index[key]["assets"].append(asset)
    return sessions


def _public_catalog(collection, nav_rows, token):
    rows = list(nav_rows or [])
    if not any(row.get("token") == token for row in rows):
        for session in collection.get("sessions") or []:
            rows.append({
                "token": token,
                "title": collection.get("title"),
                "campaign_name": collection.get("campaign_name"),
                "client_name": collection.get("client_name"),
                "logo_url": collection.get("logo_url"),
                "logo_upload_path": collection.get("logo_upload_path"),
                "viewer_slug": session.get("key"),
                "viewer_name": session.get("name"),
                "viewer_kind": session.get("kind"),
                "viewer_logo": session.get("logo"),
                "asset_count": len(session.get("assets") or []),
            })
    brands = {}
    brand_order = []
    for row in rows:
        brand_name = row.get("client_name") or "Marca"
        if brand_name not in brands:
            brands[brand_name] = {
                "name": brand_name,
                "logo": row.get("logo_upload_path") or row.get("logo_url"),
                "campaigns": {},
                "campaign_order": [],
            }
            brand_order.append(brand_name)
        brand = brands[brand_name]
        camp_token = row.get("token")
        if camp_token not in brand["campaigns"]:
            brand["campaigns"][camp_token] = {
                "token": camp_token,
                "title": row.get("title") or row.get("campaign_name"),
                "campaign_name": row.get("campaign_name") or row.get("title"),
                "current": camp_token == token,
                "href": f"/criativos/publico/{camp_token}",
                "channels": [],
            }
            brand["campaign_order"].append(camp_token)
        channel_key = row.get("viewer_slug") or "canal"
        brand["campaigns"][camp_token]["channels"].append({
            "key": channel_key,
            "name": row.get("viewer_name") or row.get("channel_name") or "Canal",
            "kind": row.get("viewer_kind") or "portal",
            "logo": row.get("viewer_logo"),
            "count": row.get("asset_count") or 0,
            "current": camp_token == token,
            "href": (
                f"#session-{channel_key}"
                if camp_token == token
                else f"/criativos/publico/{camp_token}#session-{channel_key}"
            ),
        })
    campaigns = []
    brand_list = []
    for brand_name in brand_order:
        brand = brands[brand_name]
        camps = [brand["campaigns"][key] for key in brand["campaign_order"]]
        for camp in camps:
            primary = camp["channels"][0] if camp["channels"] else None
            camp["primary_key"] = primary["key"] if primary else None
            camp["select_href"] = camp["href"] + (
                f"#session-{camp['primary_key']}" if camp["primary_key"] else ""
            )
            campaigns.append(camp)
        brand_list.append({
            "name": brand["name"],
            "logo": brand["logo"],
            "campaigns": camps,
        })
    sessions = collection.get("sessions") or []
    primary = max(sessions, key=lambda item: len(item.get("assets") or []), default=None)
    return {
        "exhibitor": {
            "key": primary.get("key"),
            "name": primary.get("name"),
            "kind": primary.get("kind"),
            "logo": primary.get("logo"),
        } if primary else None,
        "campaigns": campaigns,
        "brands": brand_list,
    }


class CreativeModelingService:
    def __init__(
        self, repository=None, generator=None, storage=None, brand_analyzer=None
    ):
        self.repository = repository or CreativeModelingRepository()
        self.generator = generator or CreativeGenerationClient()
        self.storage = storage or CreativeAssetStorage()
        self.brand_analyzer = brand_analyzer or CreativeBrandAnalyzer()

    def _append_brand_references(self, client_id, data_urls, job_id=None, engine=None):
        if (
            not client_id
            or len(data_urls) >= 2
            or not hasattr(self.repository, "list_client_brand_assets")
        ):
            return []
        used = []
        assets = list(self.repository.list_client_brand_assets(client_id) or [])
        has_campaign_refs = bool(data_urls)
        skip_logo = str(engine or "") == ENGINE_CONSTRUCT
        logos = [
            asset for asset in assets
            if asset.get("role") == "logo" and not skip_logo
        ]
        others = [asset for asset in assets if asset.get("role") != "logo"]
        assets = logos + ([] if has_campaign_refs else others)
        for asset in assets:
            if len(data_urls) >= 2:
                break
            path = asset.get("asset_path")
            mime = asset.get("mime_type")
            if not path or not mime:
                continue
            try:
                data_url = self.storage.reference_as_data_url(path, mime)
            except ValueError:
                continue
            data_urls.append(data_url)
            used.append(asset)
            if job_id is not None:
                self.repository.add_job_reference(
                    job_id,
                    {
                        "asset_path": path,
                        "mime_type": mime,
                        "original_name": (
                            (asset.get("metadata") or {}).get("original_name")
                            or f"brand-asset-{asset.get('id')}"
                        ),
                    },
                )
        return used

    def list_formats(self):
        formats = self.repository.list_formats()
        for format_data in formats:
            format_data["scene_count"] = scene_count_for_format(format_data)
            geometry = resolve_format_geometry(format_data)
            format_data["iab_family"] = geometry["family"]
            format_data["iab_cousin"] = geometry.get("iab_cousin")
            format_data["target_size"] = geometry.get("target_size")
            format_data["default_render_mode"] = default_render_mode(
                geometry["family"]
            )
            format_data["element_budget"] = geometry.get("budget")
            format_data["direction"] = format_direction(format_data)
            placement = format_data.get("placement_spec")
            zone = (
                placement.get("placement_zone")
                if isinstance(placement, dict)
                else None
            )
            if format_data.get("slug") in SOCIAL_FORMAT_SLUGS:
                social = default_social_placement(
                    format_data.get("slug"), format_data.get("default_size")
                )
                if not isinstance(placement, dict) or placement.get("context") != "social":
                    format_data["placement_spec"] = social
                else:
                    format_data["placement_spec"] = {**social, **placement, "context": "social"}
                format_data["placement_zone"] = None
                continue
            if zone not in PLACEMENT_ZONES:
                zone = geometry.get("placement_zone")
                if zone and isinstance(placement, dict):
                    format_data["placement_spec"] = {
                        **placement,
                        "placement_zone": zone,
                    }
            format_data["placement_zone"] = zone
        return _serialize(formats)

    def list_compose_library(self, family=None, client_id=None):
        family = str(family or "").strip() or None
        if family and family not in LIBRARY_FAMILIES:
            family = None
        systems = []
        templates = []
        variations = []
        lister = getattr(self.repository, "list_compose_variations", None)
        if callable(lister):
            try:
                systems = self.repository.list_brand_visual_systems(client_id)
                templates = self.repository.list_compose_templates(family)
                variations = lister(family=family, client_id=client_id)
            except Exception:
                systems, templates, variations = [], [], []
        if not isinstance(systems, list):
            systems = []
        if not isinstance(templates, list):
            templates = []
        if not isinstance(variations, list):
            variations = []
        seen = {
            str(item.get("id"))
            for item in variations
            if isinstance(item, dict) and item.get("id") is not None
        }
        for seed in catalog_variations(family):
            if str(seed["id"]) not in seen:
                variations.append(seed)
        seen_templates = {
            str(item.get("slug"))
            for item in templates
            if isinstance(item, dict) and item.get("slug")
        }
        for seed in catalog_templates(family):
            if seed["slug"] not in seen_templates:
                templates.append(seed)
        return _serialize({
            "visual_systems": systems,
            "templates": templates,
            "variations": variations,
        })

    def persist_extract_draft(self, contract):
        lister = getattr(self.repository, "list_compose_templates", None)
        saver = getattr(self.repository, "create_compose_variation", None)
        if not callable(lister) or not callable(saver):
            return None
        family = str(getattr(contract, "family", "") or "square_1x1")
        templates = lister(family) or lister() or []
        regions = getattr(contract, "regions", None) or []
        region_rows = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in regions
        ]
        template = suggest_compose_template(templates, family, region_rows)
        if not template or template.get("id") in (None, "") or str(template.get("id")).startswith("tpl-"):
            return None
        params = dict(getattr(contract, "params", None) or {})
        if region_rows:
            params["regions"] = region_rows
        variation = saver(
            template["id"],
            "Rascunho extraído",
            params,
            "experimental",
        )
        if not isinstance(variation, dict):
            return None
        variation = dict(variation)
        variation["family"] = family
        variation["template_id"] = template.get("id")
        variation["template_slug"] = template.get("slug")
        variation["html_key"] = template.get("html_key")
        return variation

    def run_creative_agent(self, name, payload):
        from .creative_agents.orchestrator import run_agent

        payload = payload if isinstance(payload, dict) else {}
        callable_llm = payload.pop("text_callable", None)
        if callable_llm is None:
            callable_llm = getattr(self.generator, "text_callable", None)
        campaign_id = payload.get("campaign_id")
        if campaign_id not in (None, "") and hasattr(self.repository, "get_campaign"):
            try:
                campaign = self.repository.get_campaign(int(campaign_id))
            except (TypeError, ValueError, Exception):
                campaign = None
            if isinstance(campaign, dict):
                client = campaign.get("client") if isinstance(campaign.get("client"), dict) else {}
                brief = campaign.get("creative_brief") if isinstance(campaign.get("creative_brief"), dict) else {}
                bancada = brief.get("bancada") if isinstance(brief.get("bancada"), dict) else {}
                dna = materialize_brand_dna(
                    client,
                    client.get("brand_profile"),
                    payload.get("brand_dna") or bancada.get("brand_dna"),
                )
                payload["brand_dna"] = dna
                contract = payload.get("contract")
                if isinstance(contract, dict):
                    contract = dict(contract)
                    contract["brand_dna"] = dna
                    contract["brand_dna_id"] = dna["id"]
                    payload["contract"] = contract
        image_callable = payload.pop("image_callable", None)
        if image_callable is None and payload.get("decompose"):
            image_callable = self._agent_image_callable()
        result = run_agent(
            name,
            payload,
            text_callable=callable_llm,
            image_callable=image_callable,
            repository=self.repository,
        )
        data = _serialize(result.model_dump())
        if str(name) == "extractor":
            try:
                data["saved_variation"] = self.persist_extract_draft(result)
            except Exception:
                data["saved_variation"] = None
        return data

    def _agent_image_callable(self):
        generate = getattr(getattr(self, "generator", None), "generate_image", None)
        if not callable(generate):
            return None

        def _run(prompt, aspect_ratio="1:1", background="opaque", input_references=None, **_extra):
            result = generate(
                prompt,
                input_references=input_references,
                aspect_ratio=aspect_ratio,
                background=background,
                output_format="png",
            )
            if isinstance(result, dict):
                return result.get("b64_json") or result.get("url") or ""
            return result

        return _run

    def _format_lab(self):
        from .creative_format_lab.service import FormatLabService

        return FormatLabService(self)

    def format_lab_formats(self):
        return self._format_lab().list_formats()

    def format_lab_campaigns(self):
        return self._format_lab().list_campaigns()

    def format_lab_quote(self, payload=None):
        return self._format_lab().quote(payload)

    def format_lab_campaign(self, slug):
        return self._format_lab().get_campaign_model(slug)

    def format_lab_plates(self, payload, user_id=None):
        return self._format_lab().build_plates(payload, user_id=user_id)

    def list_format_lab_plates(self, client_id):
        return self._format_lab().list_plates(client_id)

    def get_format_lab_plates(self, kit_id):
        return self._format_lab().get_plates(kit_id)

    def patch_format_lab_plates(self, payload, user_id=None):
        return self._format_lab().patch_plates(payload, user_id=user_id)

    def bind_format_lab_plates(self, payload, user_id=None):
        return self._format_lab().bind_plates(payload, user_id=user_id)

    def storyboard_format_lab_session(self, session_id, payload, user_id=None):
        return self._format_lab().storyboard(session_id, payload, user_id=user_id)

    def create_format_lab_session(self, payload, user_id=None):
        return self._format_lab().create_session(payload, user_id=user_id)

    def list_format_lab_sessions(self, payload=None):
        return self._format_lab().list_sessions(payload)

    def get_format_lab_session(self, session_id):
        return self._format_lab().get_session(session_id)

    def run_format_lab_session(self, session_id, payload, user_id=None):
        return self._format_lab().run(session_id, payload, user_id=user_id)

    def mockup_format_lab_session(self, session_id, payload, user_id=None):
        return self._format_lab().mockup(session_id, payload, user_id=user_id)

    def patch_format_lab_session(self, session_id, payload, user_id=None):
        return self._format_lab().patch(session_id, payload, user_id=user_id)

    def swap_format_lab(self, payload, user_id=None):
        return self._format_lab().swap(payload, user_id=user_id)

    def read_format_lab_swap(self, payload, user_id=None):
        return self._format_lab().read_swap(payload, user_id=user_id)

    def preview_format_lab_swap(self, payload, user_id=None):
        return self._format_lab().preview_swap(payload, user_id=user_id)

    def load_format_lab_swap_history(self, payload, user_id=None):
        return self._format_lab().load_swap_history(payload, user_id=user_id)

    def save_format_lab_swap_history(self, payload, user_id=None):
        return self._format_lab().save_swap_history(payload, user_id=user_id)

    def close_format_lab_session(self, session_id, payload, user_id=None):
        return self._format_lab().close(session_id, payload, user_id=user_id)

    def handoff_format_lab_session(self, session_id):
        return self._format_lab().handoff(session_id)

    def list_viewer_profiles(self):
        return _serialize([
            _viewer_profile_data(profile)
            for profile in self.repository.list_viewer_profiles()
        ])

    def update_format_modeling(self, format_id, payload):
        if not isinstance(payload, dict):
            raise ValueError("Corpo JSON inválido.")
        format_id = _integer(format_id, "Formato")
        current = self.repository.get_format(format_id)
        safe_area = payload.get("safe_area") or {}
        if not isinstance(safe_area, dict):
            raise ValueError("Área segura deve ser um objeto JSON.")
        placement_spec = _placement_spec(
            payload.get("placement_spec") or current.get("placement_spec") or {}
        )
        if not placement_spec.get("placement_zone"):
            geometry = resolve_format_geometry(current)
            zone = placement_zone_for(
                family=geometry.get("family"),
                size=geometry.get("size"),
                slug=current.get("slug"),
                context=placement_spec.get("context"),
            )
            if zone:
                placement_spec["placement_zone"] = zone
        viewer_profile_id = payload.get(
            "default_viewer_profile_id", current.get("default_viewer_profile_id")
        )
        if viewer_profile_id not in (None, ""):
            viewer_profile_id = _integer(viewer_profile_id, "Ambiente de mídia")
            profile = _viewer_profile_data(
                self.repository.get_viewer_profile(viewer_profile_id)
            )
            if placement_spec["context"] == "tv":
                expected_kind = "tv"
            elif placement_spec["context"] == "social":
                expected_kind = "social"
            else:
                expected_kind = "portal"
            if profile["viewer_kind"] != expected_kind:
                raise ValueError(
                    "O ambiente escolhido não corresponde ao contexto do formato."
                )
        else:
            viewer_profile_id = None
        data = {
            "safe_area": safe_area,
            "responsive_rules": _text(
                payload.get("responsive_rules"),
                "Regras responsivas",
                max_length=4000,
            ),
            "background_guidance": _text(
                payload.get("background_guidance"),
                "Orientação de background",
                max_length=8000,
            ),
            "foreground_guidance": _text(
                payload.get("foreground_guidance"),
                "Orientação de conteúdo",
                max_length=8000,
            ),
            "placement_spec": placement_spec,
            "behavior_spec": _behavior_spec(
                payload.get("behavior_spec") or current.get("behavior_spec") or {}
            ),
            "default_viewer_profile_id": viewer_profile_id,
        }
        self.repository.update_format_modeling(format_id, data)
        return {"id": format_id}

    def list_clients(self):
        clients = [
            hydrate_client_from_creative_line(client)
            for client in self.repository.list_clients()
        ]
        if hasattr(self.repository, "list_client_brand_assets"):
            for client in clients:
                client["brand_assets"] = self.repository.list_client_brand_assets(
                    client["id"]
                )
        return _serialize(clients)

    def list_campaign_clients(self):
        clients = [
            hydrate_client_from_creative_line(client)
            for client in self.repository.list_campaign_clients()
            if client.get("profile_id") and client.get("profile_status") != "minimal"
        ]
        if hasattr(self.repository, "list_client_brand_assets"):
            for client in clients:
                profile_id = client.get("profile_id")
                client["brand_assets"] = (
                    self.repository.list_client_brand_assets(profile_id)
                    if profile_id else []
                )
        return _serialize(clients)

    def get_client(self, client_id):
        client_id = _integer(client_id, "Cliente")
        client = hydrate_client_from_creative_line(
            self.repository.get_client(client_id)
        )
        if hasattr(self.repository, "list_client_brand_assets"):
            client["brand_assets"] = self.repository.list_client_brand_assets(client_id)
        return _serialize(client)

    def get_brand_design_system(self, client_id):
        from .design_system_ads.service import is_preset_id, payload_for, read_preset

        if is_preset_id(client_id):
            return _serialize({**read_preset(), "exists": True, "preset": True})
        client = self.get_client(client_id)
        stored = self._stored_brand_design_system(client)
        if stored:
            from .design_system_ads.fidelity import attach_client_evidence

            stored = attach_client_evidence(stored, client)
            return _serialize({**payload_for(stored), "exists": True, "preset": False})
        from .design_system_ads.materialize import ensure_brand_design_system

        suggested = ensure_brand_design_system(client)
        return _serialize(
            {
                **payload_for(suggested),
                "exists": False,
                "preset": False,
                "client_id": client.get("id"),
                "status": "missing",
            }
        )

    def ensure_brand_design_system(self, client_id):
        from .design_system_ads.service import is_preset_id, payload_for, read_preset

        if is_preset_id(client_id):
            return _serialize({**read_preset(), "exists": True, "preset": True})
        client = self.get_client(client_id)
        system = self._stored_brand_design_system(client)
        if system is None:
            from .design_system_ads.materialize import ensure_brand_design_system

            system = ensure_brand_design_system(client)
        persisted = self._persist_brand_design_system(client, system)
        return _serialize({**payload_for(persisted), "exists": True, "preset": False})

    def refine_brand_design_system(self, client_id, attempts=4, intent=None):
        from .design_system_ads.refine import IMPROVE_INTENTS, clamp_passes
        from .design_system_ads.service import (
            is_preset_id,
            payload_for,
            read_preset,
            run_improve,
            run_refine,
        )

        kind = str(intent or "").strip().lower()
        if is_preset_id(client_id):
            current = read_preset()
            if kind in IMPROVE_INTENTS:
                improved, _report = run_improve(current, kind)
                return _serialize({**payload_for(improved), "exists": True, "preset": True})
            refined, _reports = run_refine(current, attempts=clamp_passes(attempts))
            return _serialize({**payload_for(refined), "exists": True, "preset": True})
        client = self.get_client(client_id)
        system = self._stored_brand_design_system(client)
        if system is None:
            from .design_system_ads.materialize import ensure_brand_design_system

            system = ensure_brand_design_system(client)
        if kind in IMPROVE_INTENTS:
            improved, _report = run_improve(system, kind)
            persisted = self._persist_brand_design_system(client, improved)
            return _serialize({**payload_for(persisted), "exists": True, "preset": False})
        references = []
        for asset in client.get("brand_assets") or []:
            url = asset.get("asset_url") or asset.get("stored_url") or asset.get("source_url")
            if url:
                references.append(url)
        if client.get("logo_upload_path"):
            references.insert(0, client["logo_upload_path"])
        refined, _reports = run_refine(
            system,
            attempts=clamp_passes(attempts),
            text_callable=self._design_system_text_callable(),
            reference_urls=references[:4],
        )
        persisted = self._persist_brand_design_system(client, refined)
        return _serialize({**payload_for(persisted), "exists": True, "preset": False})

    def patch_brand_design_system(self, client_id, tokens=None, ad_copy=None, dna=None, archetype=None):
        from .design_system_ads.service import (
            is_preset_id,
            payload_for,
            read_preset,
            run_patch,
        )

        if is_preset_id(client_id):
            patched, _applied = run_patch(
                read_preset(), tokens=tokens, ad_copy=ad_copy, dna=dna, archetype=archetype
            )
            return _serialize({**payload_for(patched), "exists": True, "preset": True})
        client = self.get_client(client_id)
        system = self._stored_brand_design_system(client)
        if system is None:
            raise CreativeNotFoundError("A marca ainda não tem Design System Ads.")
        patched, _applied = run_patch(
            system, tokens=tokens, ad_copy=ad_copy, dna=dna, archetype=archetype
        )
        persisted = self._persist_brand_design_system(client, patched)
        return _serialize({**payload_for(persisted), "exists": True, "preset": False})

    def loop_brand_design_system(self, client_id, generate_track=False):
        from .design_system_ads.service import (
            is_preset_id,
            payload_for,
            read_preset,
            run_loop,
        )

        if is_preset_id(client_id):
            advanced, info, _report = run_loop(read_preset())
            payload = {**payload_for(advanced), "exists": True, "preset": True, "loop": info}
            return _serialize(payload)
        client = self.get_client(client_id)
        system = self._stored_brand_design_system(client)
        if system is None:
            from .design_system_ads.materialize import ensure_brand_design_system

            system = ensure_brand_design_system(client)
        from .design_system_ads.fidelity import attach_client_evidence

        system = attach_client_evidence(system, client)
        references = []
        if client.get("logo_upload_path") or client.get("logo_url"):
            references.append(client.get("logo_upload_path") or client.get("logo_url"))
        for asset in client.get("brand_assets") or []:
            url = asset.get("asset_url") or asset.get("stored_url") or asset.get("source_url")
            if url:
                references.append(url)
        advanced, info, _report = run_loop(
            system,
            text_callable=self._design_system_text_callable(),
            reference_urls=references[:4],
        )
        persisted = self._persist_brand_design_system(client, advanced)
        return _serialize({**payload_for(persisted), "exists": True, "preset": False, "loop": info})

    def compose_brand_design_system(self, client_id):
        from .design_system_ads.refine import compose_design_system
        from .design_system_ads.service import is_preset_id, payload_for, read_preset

        callable = self._design_system_text_callable()
        if callable is None:
            raise ValueError("OpenRouter não está configurado para montar o sistema.")
        if is_preset_id(client_id):
            system = read_preset()
            composed, _report = compose_design_system(
                system, text_callable=callable, reference_urls=[system.get("logo_url")]
            )
            return _serialize({**payload_for(composed), "exists": True, "preset": True})
        client = self.get_client(client_id)
        system = self._stored_brand_design_system(client)
        if system is None:
            from .design_system_ads.materialize import ensure_brand_design_system

            system = ensure_brand_design_system(client)
        from .design_system_ads.fidelity import attach_client_evidence

        system = attach_client_evidence(system, client)
        references = []
        if client.get("logo_upload_path") or client.get("logo_url"):
            references.append(client.get("logo_upload_path") or client.get("logo_url"))
        for asset in client.get("brand_assets") or []:
            url = asset.get("asset_url") or asset.get("stored_url") or asset.get("source_url")
            if url:
                references.append(url)
        composed, _report = compose_design_system(
            system, text_callable=callable, reference_urls=references[:4]
        )
        persisted = self._persist_brand_design_system(client, composed)
        return _serialize({**payload_for(persisted), "exists": True, "preset": False})

    def generate_brand_track(self, client_id, track_id, extra=""):
        from .design_system_ads.components import apply_background
        from .design_system_ads.schema import dump_system, parse_system
        from .design_system_ads.service import is_preset_id, payload_for, read_preset
        from .design_system_ads.tracks import merge_tracks, prompt_for_track, track_spec
        from .services.openrouter_service import generate_image, resolve_api_key

        if not resolve_api_key():
            raise ValueError("OpenRouter não está configurado para gerar a trilha.")
        spec = track_spec(track_id)
        if is_preset_id(client_id):
            system = parse_system(read_preset())
            persist = False
            client = None
        else:
            client = self.get_client(client_id)
            system = self._stored_brand_design_system(client)
            if system is None:
                raise CreativeNotFoundError("A marca ainda não tem Design System Ads.")
            persist = True
        refs = self._track_input_references(system, spec["id"], client)
        extra_text = str(extra or "").strip()
        if refs:
            extra_text = (
                f"{extra_text} Use the attached brand images as the real product and mark. "
                "Do not invent a different SKU, bottle or logo."
            ).strip()
        prompt = prompt_for_track(system, spec["id"], extra_text)
        result = generate_image(
            prompt,
            aspect_ratio=spec["aspect"],
            model="openai/gpt-image-2",
            input_references=refs,
        )
        encoded = (result or {}).get("b64_json")
        if not encoded:
            raise ValueError("O GPT Image 2 não devolveu a trilha.")
        url = self.storage.save_generated_base64(encoded)
        data = dump_system(system)
        data["tracks"] = merge_tracks(data.get("tracks"), [{"id": spec["id"], "url": url, "prompt": prompt}])
        tokens = dict(data.get("tokens") or {})
        if spec["id"] == "wash":
            tokens = apply_background(tokens, "wash")
        elif spec["role"] == "ground":
            tokens = apply_background(tokens, "image", image_url=url)
        data["tokens"] = tokens
        parsed = parse_system(data)
        if persist:
            parsed = self._persist_brand_design_system(client, parsed)
        return _serialize({**payload_for(parsed), "exists": True, "preset": not persist})

    def approve_brand_design_system(self, client_id):
        from .design_system_ads.service import (
            is_preset_id,
            mark_approved,
            payload_for,
            read_preset,
        )

        if is_preset_id(client_id):
            approved = mark_approved(read_preset())
            return _serialize({**payload_for(approved), "exists": True, "preset": True})
        client = self.get_client(client_id)
        system = self._stored_brand_design_system(client)
        if system is None:
            raise CreativeNotFoundError("A marca ainda não tem Design System Ads.")
        persisted = self._persist_brand_design_system(client, mark_approved(system))
        return _serialize({**payload_for(persisted), "exists": True, "preset": False})

    def adapt_brand_design_system(
        self, client_id, format_key=None, layer_count=None, swaps=None, archetype=None
    ):
        from .design_system_ads.service import is_preset_id, payload_for, read_preset

        if is_preset_id(client_id):
            return _serialize(
                {
                    **payload_for(
                        read_preset(),
                        format_key=format_key or "iab-billboard",
                        layer_count=layer_count,
                        swaps=swaps,
                        archetype=archetype,
                    ),
                    "exists": True,
                    "preset": True,
                }
            )
        client = self.get_client(client_id)
        system = self._stored_brand_design_system(client)
        if system is None:
            from .design_system_ads.materialize import ensure_brand_design_system

            system = ensure_brand_design_system(client)
        if archetype:
            from .design_system_ads.service import run_patch

            system, _applied = run_patch(system, archetype=archetype)
            system = self._persist_brand_design_system(client, system)
        return _serialize(
            {
                **payload_for(
                    system,
                    format_key=format_key or "iab-billboard",
                    layer_count=layer_count,
                    swaps=swaps,
                    archetype=archetype,
                ),
                "exists": True,
                "preset": False,
            }
        )

    def render_brand_design_system(
        self, client_id, format_key=None, layer_count=None, swaps=None, highlight=None
    ):
        from .design_system_ads.adapt import adapt_system
        from .design_system_ads.render import render_specimen
        from .design_system_ads.service import is_preset_id, read_preset

        if is_preset_id(client_id):
            system = read_preset()
        else:
            system = self.get_brand_design_system(client_id)
        stack = None
        if format_key:
            system, stack = adapt_system(system, format_key, layer_count, swaps=swaps)
        return render_specimen(system, standalone=True, stack=stack, highlight=highlight)

    def get_campaign_design_system(self, campaign_id):
        from .design_system_ads.campaign import (
            ensure_campaign_design_system,
            is_campaign_preset_id,
        )
        from .design_system_ads.service import payload_for, read_campaign_preset

        if is_campaign_preset_id(campaign_id):
            return _serialize({**read_campaign_preset(), "exists": True, "preset": True})
        campaign = self.repository.get_campaign(
            _integer(campaign_id, "Campanha"), productions=False
        )
        stored = self._stored_campaign_design_system(campaign)
        if stored:
            return _serialize({**payload_for(stored), "exists": True, "preset": False})
        brand = self._brand_system_for_campaign(campaign, create=False)
        suggested, items = ensure_campaign_design_system(
            brand, campaign, self._campaign_elements(campaign)
        )
        return _serialize(
            {
                **payload_for(suggested),
                "exists": False,
                "preset": False,
                "elements": items,
                "status": "missing",
            }
        )

    def ensure_campaign_design_system(self, campaign_id):
        from .design_system_ads.campaign import (
            ensure_campaign_design_system,
            is_campaign_preset_id,
        )
        from .design_system_ads.service import payload_for, read_campaign_preset

        if is_campaign_preset_id(campaign_id):
            return _serialize({**read_campaign_preset(), "exists": True, "preset": True})
        campaign = self.repository.get_campaign(
            _integer(campaign_id, "Campanha"), productions=False
        )
        brand = self._brand_system_for_campaign(campaign, create=True)
        system, _items = ensure_campaign_design_system(
            brand, campaign, self._campaign_elements(campaign)
        )
        from .design_system_ads.refine import compose_campaign_design_system

        try:
            system, _report = compose_campaign_design_system(
                system,
                campaign,
                text_callable=self._design_system_text_callable(),
            )
        except Exception:
            system, _report = compose_campaign_design_system(system, campaign)
        persisted = self._persist_campaign_design_system(campaign, system)
        return _serialize({**payload_for(persisted), "exists": True, "preset": False})

    def adapt_campaign_design_system(
        self, campaign_id, format_key=None, layer_count=None, swaps=None
    ):
        from .design_system_ads.campaign import (
            ensure_campaign_design_system,
            is_campaign_preset_id,
        )
        from .design_system_ads.service import payload_for, read_campaign_preset

        if is_campaign_preset_id(campaign_id):
            current = read_campaign_preset()
            return _serialize(
                {
                    **payload_for(
                        current,
                        format_key=format_key or "iab-billboard",
                        layer_count=layer_count,
                        swaps=swaps,
                    ),
                    "exists": True,
                    "preset": True,
                }
            )
        campaign = self.repository.get_campaign(
            _integer(campaign_id, "Campanha"), productions=False
        )
        system = self._stored_campaign_design_system(campaign)
        if system is None:
            brand = self._brand_system_for_campaign(campaign, create=False)
            system, _items = ensure_campaign_design_system(
                brand, campaign, self._campaign_elements(campaign)
            )
        return _serialize(
            {
                **payload_for(
                    system,
                    format_key=format_key or "iab-billboard",
                    layer_count=layer_count,
                    swaps=swaps,
                ),
                "exists": True,
                "preset": False,
            }
        )

    def render_campaign_design_system(
        self, campaign_id, format_key=None, layer_count=None, swaps=None, highlight=None
    ):
        from .design_system_ads.adapt import adapt_system
        from .design_system_ads.campaign import is_campaign_preset_id
        from .design_system_ads.render import render_specimen
        from .design_system_ads.service import read_campaign_preset

        if is_campaign_preset_id(campaign_id):
            system = read_campaign_preset()
        else:
            system = self.get_campaign_design_system(campaign_id)
        stack = None
        if format_key:
            system, stack = adapt_system(system, format_key, layer_count, swaps=swaps)
        return render_specimen(system, standalone=True, stack=stack, highlight=highlight)

    def _brand_system_for_campaign(self, campaign, create=False):
        from .design_system_ads.materialize import ensure_brand_design_system

        client = campaign.get("client") if isinstance(campaign.get("client"), dict) else {}
        stored = self._stored_brand_design_system(client)
        if stored:
            return stored
        system = ensure_brand_design_system(client)
        if create and client.get("id"):
            return self._persist_brand_design_system(client, system)
        return system

    def _campaign_elements(self, campaign):
        from .design_system_ads.campaign import collect_campaign_elements

        record = dict(campaign or {})
        assets = []
        getter = getattr(self.repository, "list_campaign_assets", None)
        if callable(getter) and record.get("id"):
            try:
                assets = getter(record["id"])
            except Exception:
                assets = []
        record["assets"] = assets
        return collect_campaign_elements(record)

    def _stored_campaign_design_system(self, campaign):
        from .design_system_ads.schema import FRAMEWORK, parse_system

        brief = campaign.get("creative_brief") if isinstance(campaign.get("creative_brief"), dict) else {}
        stored = brief.get("design_system_ads")
        if isinstance(stored, dict) and (stored.get("framework") == FRAMEWORK or stored.get("tokens")):
            return parse_system(stored)
        return None

    def _persist_campaign_design_system(self, campaign, system):
        from .design_system_ads.schema import dump_system, parse_system

        brief = campaign.get("creative_brief") if isinstance(campaign.get("creative_brief"), dict) else {}
        brief = dict(brief)
        brief["design_system_ads"] = dump_system(system)
        self.repository.update_campaign_bancada(campaign["id"], brief)
        return parse_system(brief["design_system_ads"])

    def _maybe_generate_campaign_design_system(self, campaign):
        if not isinstance(campaign, dict) or campaign.get("id") in (None, ""):
            return
        client = campaign.get("client") if isinstance(campaign.get("client"), dict) else {}
        if not self._stored_brand_design_system(client):
            return
        try:
            self.ensure_campaign_design_system(campaign["id"])
        except Exception:
            return

    def _stored_brand_design_system(self, client):
        from .design_system_ads.schema import FRAMEWORK, parse_system

        profile = client.get("brand_profile") if isinstance(client.get("brand_profile"), dict) else {}
        stored = profile.get("design_system_ads")
        if isinstance(stored, dict) and (stored.get("framework") == FRAMEWORK or stored.get("tokens")):
            return parse_system(stored)
        getter = getattr(self.repository, "get_design_system_ads", None)
        if not callable(getter):
            return None
        try:
            row = getter(client.get("id"))
        except Exception:
            return None
        tokens = (row or {}).get("tokens") if isinstance(row, dict) else None
        if isinstance(tokens, dict) and (tokens.get("framework") == FRAMEWORK or tokens.get("tokens")):
            return parse_system(tokens)
        return None

    def _persist_brand_design_system(self, client, system):
        from .design_system_ads.schema import dump_system

        data = dump_system(system)
        data["client_id"] = client.get("id")
        profile = dict(client.get("brand_profile") or {})
        profile["design_system_ads"] = data
        client["brand_profile"] = profile
        writer = getattr(self.repository, "update_client_brand_profile", None)
        if callable(writer):
            writer(client["id"], profile)
        upsert = getattr(self.repository, "upsert_design_system_ads", None)
        if callable(upsert):
            upsert(client["id"], data)
        return data

    def _design_system_text_callable(self):
        from .services.openrouter_service import chat_completion, resolve_api_key

        if not resolve_api_key():
            return None
        return chat_completion

    def _client_write_data(self, payload, include_crm=True):
        payload = payload if isinstance(payload, dict) else {}
        logo_url = _text(payload.get("logo_url"), "URL do logo", max_length=2000)
        if logo_url and not logo_url.lower().startswith(("http://", "https://")):
            raise ValueError("URL do logo deve começar com http:// ou https://.")
        website_url = _text(
            payload.get("website_url"), "Site da marca", max_length=2000
        )
        if website_url and not website_url.lower().startswith(("http://", "https://")):
            raise ValueError("Site da marca deve começar com http:// ou https://.")
        brand_profile = {
            "brand_summary": _text(
                payload.get("brand_summary"), "Resumo da marca", max_length=4000
            ),
            "target_audience": _text(
                payload.get("target_audience"), "Público-alvo", max_length=4000
            ),
            "ad_segments": _text_list(
                payload.get("ad_segments"), "Segmentos de anúncios", max_items=8
            ),
            "creative_guidelines": _text(
                payload.get("creative_guidelines"),
                "Direção criativa",
                max_length=4000,
            ),
            "campaign_opportunities": _text_list(
                payload.get("campaign_opportunities"),
                "Oportunidades de campanha",
                max_items=6,
            ),
            "products_services": _text_list(
                payload.get("products_services"), "Produtos e serviços", max_items=10
            ),
            "differentiators": _text_list(
                payload.get("differentiators"), "Diferenciais", max_items=10
            ),
            "proof_points": _text_list(
                payload.get("proof_points"), "Provas da marca", max_items=10
            ),
            "visual_motifs": _text_list(
                payload.get("visual_motifs"), "Motivos visuais", max_items=10
            ),
            "mandatory_elements": _text_list(
                payload.get("mandatory_elements"), "Elementos obrigatórios", max_items=10
            ),
            "forbidden_elements": _text_list(
                payload.get("forbidden_elements"), "Restrições criativas", max_items=10
            ),
            "color_palette": _brand_palette(payload.get("color_palette")),
            "fonts": _fonts(payload.get("fonts")),
        }
        incoming_line = payload.get("creative_line")
        if isinstance(incoming_line, dict) and incoming_line:
            brand_profile["creative_line"] = incoming_line
        analysis_metadata = payload.get("analysis_metadata") or {}
        if not isinstance(analysis_metadata, dict):
            raise ValueError("Metadados da análise inválidos.")
        analysis_metadata = {
            key: analysis_metadata.get(key)
            for key in (
                "model",
                "analyzed_at",
                "source_types",
                "firecrawl_available",
                "confidence",
                "sources",
                "pages_analyzed",
                "assets_found",
                "visual_model",
                "visual_evidence_count",
            )
            if analysis_metadata.get(key) is not None
        }
        data = {
            "name": _text(
                payload.get("name"), "Nome do cliente", required=True, max_length=150
            ),
            "sector": _text(payload.get("sector"), "Setor", max_length=80),
            "tone_of_voice": _text(
                payload.get("tone_of_voice"), "Tom de voz", max_length=4000
            ),
            "logo_url": logo_url,
            "website_url": website_url,
            "primary_color": _color(
                payload.get("primary_color"), "Cor primária"
            ),
            "secondary_color": _color(
                payload.get("secondary_color"), "Cor secundária"
            ),
            "price_policy": (
                "show_price" if payload.get("show_price") is True else "hide_price"
            ),
            "brand_profile": brand_profile,
            "analysis_metadata": analysis_metadata,
        }
        if include_crm:
            data["crm_client_id"] = (
                HOUSE_CRM_CLIENT_ID
                if payload.get("crm_client_id") in (None, "")
                else _integer(payload.get("crm_client_id"), "Cliente CentralComm")
            )
        return data

    def create_client(self, payload):
        data = self._client_write_data(payload)
        client_id = self.repository.create_client(data)
        saved_assets = self._import_candidate_brand_assets(client_id, payload)
        return {"id": client_id, "brand_assets": saved_assets}

    def update_client(self, client_id, payload):
        client_id = _integer(client_id, "Cliente")
        current = self.repository.get_client(client_id)
        payload = payload if isinstance(payload, dict) else {}
        current_profile = current.get("brand_profile") if isinstance(current.get("brand_profile"), dict) else {}
        merged = dict(payload)
        if not merged.get("creative_line") and current_profile.get("creative_line"):
            merged["creative_line"] = current_profile.get("creative_line")
        if not merged.get("analysis_metadata") and current.get("analysis_metadata"):
            merged["analysis_metadata"] = current.get("analysis_metadata")
        if not merged.get("color_palette") and current_profile.get("color_palette"):
            merged["color_palette"] = current_profile.get("color_palette")
        if not merged.get("fonts") and current_profile.get("fonts"):
            merged["fonts"] = current_profile.get("fonts")
        data = self._client_write_data(merged, include_crm=False)
        self.repository.update_client(client_id, data)
        self._import_candidate_brand_assets(client_id, merged)
        return self.get_client(client_id)

    def _import_candidate_brand_assets(self, client_id, payload):
        saved_assets = []
        for candidate in (payload.get("brand_assets") or [])[:9]:
            if not isinstance(candidate, dict):
                continue
            role = candidate.get("role")
            if role not in BRAND_ASSET_ROLES:
                continue
            source_url = _text(
                candidate.get("source_url"), "Imagem da marca", max_length=2000
            )
            page_url = _text(
                candidate.get("page_url"), "Página de origem", max_length=2000
            )
            stored = {}
            try:
                stored = self.storage.save_remote_reference(source_url, page_url)
            except Exception:
                stored = {"source_url": source_url}
            asset_data = {
                **stored,
                "role": role,
                "source_kind": "website",
                "source_url": stored.get("source_url") or source_url,
                "page_url": page_url,
                "width": candidate.get("width"),
                "height": candidate.get("height"),
                "score": candidate.get("score"),
                "status": "approved",
                "is_primary": bool(candidate.get("is_primary") and role == "logo"),
                "metadata": {
                    "category": candidate.get("category"),
                    "reason": candidate.get("reason"),
                },
            }
            duplicate = (
                self.repository.find_client_brand_asset_by_hash(
                    client_id, asset_data.get("sha256")
                )
                if hasattr(self.repository, "find_client_brand_asset_by_hash")
                else None
            )
            if duplicate:
                self.storage.delete(asset_data.get("asset_path"))
                if (
                    asset_data["is_primary"]
                    and duplicate.get("role") == "logo"
                    and hasattr(self.repository, "set_primary_client_brand_asset")
                ):
                    self.repository.set_primary_client_brand_asset(
                        client_id, duplicate["id"]
                    )
                continue
            if hasattr(self.repository, "add_client_brand_asset"):
                asset_id = self.repository.add_client_brand_asset(
                    client_id, asset_data
                )
                asset_data["id"] = asset_id
            if asset_data["is_primary"] and asset_data.get("asset_path"):
                self.repository.set_client_logo(client_id, asset_data["asset_path"])
            saved_assets.append(asset_data)
        return saved_assets

    def analyze_brand(self, website_url=None, image=None):
        return _serialize(self.brand_analyzer.analyze(website_url, image))

    def upload_client_brand_assets(
        self, client_id, files, primary_logo=False, role="reference"
    ):
        client_id = _integer(client_id, "Cliente")
        self.repository.get_client(client_id)
        if role not in BRAND_ASSET_ROLES - {"logo"}:
            raise ValueError("Tipo de referência visual inválido.")
        saved = []
        for position, file_storage in enumerate(list(files or [])[:8]):
            item = self.storage.save_reference(file_storage)
            asset_role = "logo" if primary_logo and position == 0 else role
            data = {
                **item,
                "role": asset_role,
                "source_kind": "upload",
                "status": "approved",
                "is_primary": asset_role == "logo",
                "metadata": {"original_name": item.get("original_name")},
            }
            duplicate = (
                self.repository.find_client_brand_asset_by_hash(
                    client_id, data.get("sha256")
                )
                if hasattr(self.repository, "find_client_brand_asset_by_hash")
                else None
            )
            if duplicate:
                self.storage.delete(item["asset_path"])
                continue
            try:
                asset_id = self.repository.add_client_brand_asset(client_id, data)
            except Exception:
                self.storage.delete(item["asset_path"])
                raise
            data["id"] = asset_id
            if data["is_primary"]:
                self.repository.set_client_logo(client_id, item["asset_path"])
            saved.append(data)
        return _serialize(saved)

    def _track_input_references(self, system, track_id, client=None):
        from .design_system_ads.fidelity import track_reference_urls

        refs = []
        for url in track_reference_urls(system, track_id, client):
            resolved = self._public_image_reference(url)
            if not resolved:
                continue
            refs.append(resolved)
            if len(refs) >= 2:
                break
        return refs

    def _public_image_reference(self, url):
        text = str(url or "").strip()
        if not text:
            return None
        if text.startswith("data:image/"):
            return text
        data = self._asset_as_data_url({"asset_path": text})
        if data:
            return data
        try:
            if "/creative_generated/" in text:
                return self.storage.generated_as_data_url(text)
        except ValueError:
            pass
        raw = self._read_logo_path(text, getattr(self.storage, "read_public_bytes", None))
        if not raw:
            raw = self._static_file_bytes(text)
        if raw:
            mime = "image/jpeg" if text.lower().endswith((".jpg", ".jpeg")) else (
                "image/webp" if text.lower().endswith(".webp") else "image/png"
            )
            encoded = base64.b64encode(raw).decode("ascii")
            return f"data:{mime};base64,{encoded}"
        if text.startswith(("http://", "https://")):
            return text
        return None

    def _static_file_bytes(self, public_path):
        from pathlib import Path

        value = str(public_path or "")
        if not value.startswith("/static/"):
            return None
        try:
            from flask import current_app

            path = Path(current_app.root_path) / value.lstrip("/")
            return path.read_bytes() if path.is_file() else None
        except Exception:
            return None

    def _asset_as_data_url(self, asset):
        path = asset.get("asset_path") if isinstance(asset, dict) else asset
        mime = asset.get("mime_type") if isinstance(asset, dict) else None
        if not path:
            return None
        if hasattr(self.storage, "public_as_data_url"):
            try:
                return self.storage.public_as_data_url(path, mime)
            except ValueError:
                pass
        try:
            return self.storage.reference_as_data_url(path, mime)
        except ValueError:
            return None

    def _official_logo_data_url(self, client):
        assets = [
            asset
            for asset in (client.get("brand_assets") or [])
            if asset.get("role") == "logo" and asset.get("asset_path")
        ]
        assets.sort(key=lambda item: (not item.get("is_primary"), -(item.get("score") or 0)))
        if client.get("logo_upload_path"):
            assets.append({
                "asset_path": client.get("logo_upload_path"),
                "mime_type": None,
            })
        for asset in assets:
            data_url = self._asset_as_data_url(asset)
            if data_url:
                return data_url
        return None

    def _brand_role_data_urls(self, client, role, limit=6):
        urls = []
        for asset in client.get("brand_assets") or []:
            if asset.get("role") != role or not asset.get("asset_path"):
                continue
            data_url = self._asset_as_data_url(asset)
            if not data_url:
                continue
            urls.append(data_url)
            if len(urls) >= limit:
                break
        return urls

    def learn_client_creative_line(self, client_id, files, logo=None, logo_url=None):
        client_id = _integer(client_id, "Cliente")
        self.repository.get_client(client_id)
        new_assets = []
        if logo:
            new_assets.extend(
                self.upload_client_brand_assets(
                    client_id, [logo], primary_logo=True, role="reference"
                )
            )
        elif logo_url:
            new_assets.extend(
                self._import_candidate_brand_assets(client_id, {
                    "brand_assets": [{
                        "role": "logo",
                        "source_url": logo_url,
                        "is_primary": True,
                        "category": "Logo",
                    }]
                })
            )
        if files:
            new_assets.extend(
                self.upload_client_brand_assets(
                    client_id, files, role="creative"
                )
            )
        client = self.get_client(client_id)
        data_urls = self._brand_role_data_urls(client, "creative", limit=6)
        creative_line = self.brand_analyzer.analyze_creative_line(
            data_urls,
            client,
            logo_data_url=self._official_logo_data_url(client),
        )
        profile = dict(client.get("brand_profile") or {})
        profile["creative_line"] = creative_line
        hydrated = hydrate_client_from_creative_line(
            {**client, "brand_profile": profile}
        )
        self.repository.update_client_brand_profile(
            client_id, hydrated["brand_profile"]
        )
        return _serialize({
            "client_id": client_id,
            "creative_line": creative_line,
            "new_assets": new_assets,
            "brand_assets": self.repository.list_client_brand_assets(client_id),
        })

    def set_primary_brand_asset(self, client_id, asset_id):
        return _serialize(
            self.repository.set_primary_client_brand_asset(
                _integer(client_id, "Cliente"),
                _integer(asset_id, "Ativo"),
            )
        )

    def delete_brand_asset(self, client_id, asset_id):
        client_id = _integer(client_id, "Cliente")
        removed = self.repository.delete_client_brand_asset(
            client_id,
            _integer(asset_id, "Ativo"),
        )
        self.storage.delete(removed.get("asset_path"))
        if (
            removed.get("role") == "creative"
            and hasattr(self.repository, "update_client_brand_profile")
        ):
            client = self.repository.get_client(client_id)
            profile = dict(client.get("brand_profile") or {})
            creative_line = dict(profile.get("creative_line") or {})
            if creative_line:
                creative_line["stale"] = True
                creative_line["stale_reason"] = (
                    "Uma referência foi removida; analise novamente."
                )
                profile["creative_line"] = creative_line
                self.repository.update_client_brand_profile(client_id, profile)

    def enhance_campaign_brief(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        scene_count = _integer(payload.get("scene_count", 4), "Quantidade de cenas")
        if scene_count not in ALLOWED_SCENE_COUNTS:
            raise ValueError("A quantidade de cenas deve ser 1, 4, 6 ou 8.")
        pack = _campaign_pack(payload.get("campaign_pack"))
        message = _text(
            payload.get("campaign_text"),
            "Mensagem principal",
            max_length=12000,
        ) or _pack_message(pack)
        if not message:
            raise ValueError(
                "Informe a mensagem ou envie um criativo/link da campanha."
            )
        context = {
            "client": {
                "name": _text(
                    payload.get("client_name"), "Cliente", required=True, max_length=150
                ),
                "profile": payload.get("client_profile")
                if isinstance(payload.get("client_profile"), dict)
                else {},
            },
            "campaign": {
                "name": _text(
                    payload.get("name"), "Campanha", required=True, max_length=200
                ),
                "objective": _text(payload.get("objective"), "Objetivo", max_length=120),
                "message": message,
                "cta": _text(payload.get("cta_text"), "CTA", max_length=1000)
                or (pack.get("extracted") or {}).get("cta"),
            },
            "campaign_pack": pack,
            "reference_weight": {
                "campaign_pack": "primary",
                "client_identity": "brand_signature",
                "creative_line": "background_signature_only",
            },
            "format": {
                "name": _text(payload.get("format_name"), "Formato", max_length=200),
                "mechanic": _text(payload.get("mechanic"), "Mecânica", max_length=100),
                "slug": _text(payload.get("format_slug"), "Slug", max_length=80),
                "default_size": _text(payload.get("default_size"), "Tamanho", max_length=40),
                "behavior_spec": payload.get("behavior_spec")
                if isinstance(payload.get("behavior_spec"), dict)
                else {},
                "scene_count": scene_count,
                "direction": format_direction({
                    "slug": payload.get("format_slug"),
                    "mechanic": payload.get("mechanic"),
                    "default_size": payload.get("default_size"),
                    "behavior_spec": payload.get("behavior_spec")
                    if isinstance(payload.get("behavior_spec"), dict)
                    else {},
                    "layers": payload.get("layers")
                    if isinstance(payload.get("layers"), list)
                    else [],
                    "scene_count": scene_count,
                }, scene_count=scene_count),
            },
        }
        generated = self.generator.generate_campaign_brief(context)
        result = generated.get("result") or {}
        scenes = result.get("scenes")
        if not isinstance(scenes, list) or len(scenes) != scene_count:
            raise OpenRouterError(
                f"O briefing deve conter exatamente {scene_count} cena(s)."
            )
        normalized_scenes = []
        for position, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                raise OpenRouterError("O provedor retornou uma cena inválida.")
            normalized_scenes.append({
                "position": position,
                "role": _text(
                    scene.get("role"), "Função da cena", required=True, max_length=50
                ),
                "description": _text(
                    scene.get("description"),
                    "Descrição da cena",
                    required=True,
                    max_length=8000,
                ),
            })
        return _serialize({
            "campaign_text": _text(
                result.get("campaign_text"),
                "Mensagem aprimorada",
                required=True,
                max_length=12000,
            ),
            "cta_text": _text(result.get("cta_text"), "CTA", max_length=1000),
            "visual_bible": _text(
                result.get("visual_bible"),
                "Bíblia visual",
                required=True,
                max_length=6000,
            ),
            "scenes": normalized_scenes,
            "model": generated.get("model"),
            "usage": generated.get("usage") or {},
        })

    @staticmethod
    def fallback_scene_descriptions(campaign_text, scene_count, format_row=None):
        message = campaign_text or "Comunicar a mensagem principal da campanha"
        count = resolve_scene_count(scene_count, default=4)
        direction = format_direction(format_row or {}, scene_count=count)
        beats = direction.get("beats") or []
        if beats and len(beats) == count:
            return [
                f"{beat['label']}: {beat['job']} Mensagem: {message}."
                for beat in beats
            ]
        if count == 1:
            return [f"Composição final: {message}. Encerrar com reconhecimento de marca."]
        lines = [
            f"Gancho: apresentar uma situação visual que gere atenção para {message}.",
            f"Contexto e produto: revelar a marca e conectar o produto a {message}.",
            f"Benefício: tornar visualmente concreto o valor central de {message}.",
            f"Oferta: tornar a oferta ou a prova visível em {message}.",
            f"Reforço: outro recorte do mesmo anúncio para {message}.",
            f"Segundo gancho: outro recorte A/B do talent para {message}.",
            f"Segundo fechamento: fechar o mesmo anúncio com outro recorte.",
            f"Fechamento: resolver a narrativa e reforçar a marca.",
        ]
        extras = {
            4: lines[:3] + [lines[-1]],
            6: lines[:3] + lines[3:5] + [lines[-1]],
            8: lines[:3] + lines[3:7] + [lines[-1]],
        }
        return extras.get(count, extras[4])

    def delete_client(self, client_id):
        client_id = _integer(client_id, "Cliente")
        client = self.repository.get_client(client_id)
        if hasattr(self.repository, "list_client_brand_assets"):
            client["brand_assets"] = self.repository.list_client_brand_assets(
                client_id, approved_only=False
            )
        self.repository.delete_client(client_id)
        for asset in client.get("brand_assets") or []:
            self.storage.delete(asset.get("asset_path"))
        return client

    def set_client_logo(self, client_id, public_path):
        client_id = _integer(client_id, "Cliente")
        client = self.repository.get_client(client_id)
        self.repository.set_client_logo(client_id, public_path)
        return client.get("logo_upload_path")

    def list_campaigns(self, flow_kind=None):
        rows = []
        for campaign in self.repository.list_campaigns():
            item = annotate_cost(campaign, campaign.get("spent_usd"))
            item["flow_kind"] = _flow_kind(item)
            if flow_kind and item["flow_kind"] != flow_kind:
                continue
            rows.append(item)
        return _serialize(rows)

    def create_production_plan(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        show_price = payload.get("show_price", False)
        if not isinstance(show_price, bool):
            raise ValueError("Exibir preço deve ser verdadeiro ou falso.")
        client_id, client_source = _campaign_client_ref(payload)
        raw_productions = payload.get("productions")
        if not isinstance(raw_productions, list) or not raw_productions:
            raise ValueError("Informe ao menos uma produção.")
        if len(raw_productions) > 20:
            raise ValueError("O plano aceita no máximo 20 formatos.")

        productions = []
        format_ids = set()
        for index, raw in enumerate(raw_productions, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Produção {index} inválida.")
            format_id = _integer(
                raw.get("format_template_id"), f"Formato da produção {index}"
            )
            if format_id in format_ids:
                raise ValueError("Cada formato pode ter apenas uma produção.")
            format_ids.add(format_id)
            descriptions = raw.get("scene_descriptions") or []
            if not isinstance(descriptions, list) or len(descriptions) > 8:
                raise ValueError(
                    f"Cenas da produção {index} devem ser uma lista de até 8 itens."
                )
            format_data = self.repository.get_format(format_id)
            suggested = scene_count_for_format(format_data)
            explicit = resolve_scene_count(
                raw.get("scene_count", payload.get("scene_count")),
                default=None,
            )
            if descriptions:
                if len(descriptions) not in ALLOWED_SCENE_COUNTS:
                    raise ValueError(
                        "A quantidade de cenas deve ser 1, 4, 6 ou 8."
                    )
                expected_scene_count = len(descriptions)
                if explicit and explicit != expected_scene_count:
                    raise ValueError(
                        f"O lote precisa de {explicit} cena(s)."
                    )
            else:
                expected_scene_count = explicit or suggested
                descriptions = self.fallback_scene_descriptions(
                    payload.get("campaign_text"),
                    expected_scene_count,
                    format_data,
                )
            if len(descriptions) != expected_scene_count:
                raise ValueError(
                    f"O lote precisa de {expected_scene_count} cena(s)."
                )
            storyboard = [
                {"position": position, "description": description}
                for position, description in enumerate(descriptions, start=1)
            ]
            pack = _campaign_pack(payload.get("campaign_pack"))
            is_model = payload.get("flow_kind") != "unfold"
            scene_prompts = [
                self._approved_scene_prompt(
                    payload,
                    format_data,
                    description,
                    position,
                    storyboard,
                    pack,
                )
                for position, description in enumerate(descriptions, start=1)
            ] if is_model else []
            productions.append(
                {
                    "format_template_id": format_id,
                    "scene_count": expected_scene_count,
                    "scene_descriptions": [
                        _text(
                            description,
                            f"Descrição da cena {position}",
                            max_length=8000,
                        )
                        for position, description in enumerate(
                            descriptions, start=1
                        )
                    ],
                    "scene_prompts": scene_prompts,
                    "approve_prompts": is_model,
                }
            )

        data = {
            "client_id": client_id,
            "client_source": client_source,
            "name": _text(
                payload.get("name"),
                "Nome da campanha",
                required=True,
                max_length=200,
            ),
            "objective": _text(
                payload.get("objective"), "Objetivo", max_length=120
            ),
            "campaign_text": _text(
                payload.get("campaign_text"),
                "Texto da campanha",
                max_length=12000,
            ),
            "cta_text": _text(payload.get("cta_text"), "CTA", max_length=1000),
            "show_price": show_price,
            "budget_usd": _money(
                5 if payload.get("budget_usd") in (None, "") else payload["budget_usd"]
            ),
            "creative_brief": {
                "flow_kind": (
                    "unfold" if payload.get("flow_kind") == "unfold" else "model"
                ),
                "kv_notes": payload.get("kv_notes") or {},
                "locks": normalize_locks(payload.get("locks")),
                "source": payload.get("source") or {},
                "visual_bible": _text(
                    payload.get("visual_bible"), "Bíblia visual", max_length=6000
                ),
                "campaign_pack": _campaign_pack(payload.get("campaign_pack")),
                "construct_path": _plan_construct_path(payload),
                "context_design": normalize_context_design(
                    payload.get("context_design"),
                    productions[0]["scene_count"],
                ),
                "compose_library": self._resolve_compose_library(
                    payload,
                    self.repository.get_format(
                        productions[0]["format_template_id"]
                    ),
                ),
                "scenes": [
                    {
                        "position": index,
                        "description": description,
                    }
                    for index, description in enumerate(
                        productions[0]["scene_descriptions"], start=1
                    )
                ],
            },
            "productions": productions,
        }
        compose = data["creative_brief"].get("compose_library")
        if (
            compose
            and compose.get("kind") == "script"
            and not payload.get("context_design")
        ):
            data["creative_brief"]["context_design"] = apply_script_params(
                data["creative_brief"]["context_design"],
                compose.get("params"),
                productions[0]["scene_count"],
            )
        try:
            created = self.repository.create_campaign_with_productions(data)
        except Exception as exc:
            if "chk_cx_creative_scene_position" in str(exc):
                raise ValueError(
                    "Este lote tem mais de 4 cenas e o banco ainda limita a posição. "
                    "O próximo deploy aplica a migration e libera 6 e 8 batidas."
                ) from exc
            raise
        campaign = self.repository.get_campaign(created["id"])
        self._maybe_generate_campaign_design_system(campaign)
        return _serialize(
            {
                "campaign": self.repository.get_campaign(created["id"]),
                "productions": [
                    self.repository.get_production(item["id"])
                    for item in created["productions"]
                ],
            }
        )

    def _approved_scene_prompt(
        self, payload, format_data, description, position, storyboard, pack
    ):
        format_data = format_data if isinstance(format_data, dict) else {}
        payload = payload if isinstance(payload, dict) else {}
        return self.build_scene_prompt({
            "position": position,
            "scene_count": len(storyboard) or 1,
            "description": description,
            "campaign_text": payload.get("campaign_text"),
            "campaign_name": payload.get("name"),
            "objective": payload.get("objective"),
            "cta_text": payload.get("cta_text"),
            "show_price": payload.get("show_price"),
            "creative_brief": {
                "visual_bible": payload.get("visual_bible"),
                "campaign_pack": pack,
                "construct_path": _plan_construct_path(payload),
                "context_design": normalize_context_design(
                    payload.get("context_design"),
                    len(storyboard) or 1,
                ),
                "scenes": storyboard,
            },
            "storyboard": storyboard,
            "format_name": format_data.get("name_pt") or format_data.get("name"),
            "format_slug": format_data.get("slug"),
            "mechanic": format_data.get("mechanic"),
            "aspect_ratio": format_data.get("aspect_ratio"),
            "default_size": format_data.get("default_size"),
            "behavior_spec": format_data.get("behavior_spec") or {},
            "layers": format_data.get("layers") or [],
            "forbidden_elements": format_data.get("forbidden_elements") or [],
            "safe_area": format_data.get("safe_area") or {},
        })

    def production_detail(self, production_id):
        data = _serialize(
            self.repository.get_production(_integer(production_id, "Produção"))
        )
        data["direction"] = format_direction(
            data, scene_count=len(data.get("scenes") or [])
        )
        return data

    @staticmethod
    def scene_role(position, total, format_row=None):
        beat = format_beat(format_row or {}, position, scene_count=total)
        if beat:
            return beat["job"]
        if int(total or 1) == 1:
            return "Single final composition: the whole ad in this rectangle."
        roles = {
            1: "Opening beat: establish the campaign world and earn attention.",
            2: "Context beat: the product enters this format. Not a recrop of scene 1.",
            3: "Benefit beat: make the main value tangible without inventing claims.",
            4: "Closing beat: resolve the same ad. Show a CTA only if the format has one.",
            5: "Offer/proof beat: make the offer or proof visible. Same ad, not a variation.",
            6: "Reinforce beat: another crop of the same talent. Same ad.",
            7: "Second hook: A/B talent crop. Same ad, not another campaign.",
            8: "Alternate close: resolve the same ad. Show a CTA only if the format has one.",
        }
        return roles.get(int(position or 1), roles[1])

    @staticmethod
    def _context_design_prompt_lines(design, position, scene_count):
        design = normalize_context_design(design, scene_count)
        people = "one person" if design["cast_count"] == 1 else "the same two people"
        lines = [
            "CONTEXT ENGINEER LOCKS — photographic continuity of ONE ad, not variations.",
            "Do not paint logos, wordmarks, headlines, CTAs or legal. Those layers are composed later.",
        ]
        if design["cast_lock"]:
            lines.append(
                f"Cast lock: keep {people} recognizable across all {scene_count} beats."
            )
        if design["product_lock"]:
            lines.append(
                "Product lock: the same hero product in every beat. Do not swap SKU or pack."
            )
        if design["scenography"] == "line":
            lines.append(
                "Scenography lock: same visual line and set language. Change pose and crop, not the world."
            )
        else:
            lines.append(
                "Scenography: this beat may change set as the creative direction asks, "
                "but cast and product stay the same."
            )
        beat = next(
            (
                item for item in design["scenes"]
                if int(item.get("position") or 0) == int(position or 0)
            ),
            {},
        )
        if beat.get("job"):
            lines.append(f"This beat job: {beat['job']}.")
        if beat.get("set_note"):
            lines.append(f"Set note for this beat: {beat['set_note']}.")
        if beat.get("action_note"):
            lines.append(f"Action note for this beat: {beat['action_note']}.")
        if beat.get("copy_on_frame"):
            lines.append(
                "Copy will be composed on this frame later. Leave the lower third and logo slot empty."
            )
        else:
            lines.append(
                "No composed copy on this frame. Full-bleed photographic still only."
            )
        return lines

    @staticmethod
    def build_scene_prompt(context):
        description = context.get("description") or context.get("campaign_text") or ""
        total = context.get("scene_count") or 1
        creative_brief = context.get("creative_brief") or {}
        direction = format_direction(context)
        beat = format_beat(context, context.get("position") or 1)
        size_label = direction.get("size_label") or direction.get("target_size") or ""
        lines = [
            "Create one premium advertising still that is a beat of ONE animated or interactive ad.",
            f"Brand: {context.get('client_name') or ''}.",
            f"Campaign: {context.get('campaign_name') or ''}.",
            f"Objective: {context.get('objective') or ''}.",
            f"Scene {context['position']} of {total}: {description}.",
            CreativeModelingService.scene_role(
                context["position"], total, context
            ),
            f"Format: {context.get('format_name') or ''}.",
            f"Mechanic: {context.get('mechanic') or ''}.",
            f"Exact canvas: {size_label or context.get('aspect_ratio') or '16:9'}.",
            f"Aspect ratio: {context.get('aspect_ratio') or '16:9'}.",
        ]
        if direction.get("orientation"):
            lines.append(
                f"Orientation: {direction['orientation']}. "
                f"Read {direction.get('reading') or direction['orientation']}."
            )
        layout = direction.get("layout") or {}
        if layout.get("prompt"):
            lines.append(f"Format modeling: {layout['prompt']}")
        if beat:
            lines.append(
                f"Beat {beat['label']}: {beat['job']} "
                f"On screen now: {', '.join(beat.get('on_screen') or []) or 'visual only'}."
            )
        slots = (beat or {}).get("slots") or layout.get("slots") or []
        if slots:
            lines.append(
                "Place elements in these slots (percent of the exact canvas): "
                + "; ".join(
                    f"{item.get('label')}: x{item.get('x')}% y{item.get('y')}% "
                    f"w{item.get('width')}% h{item.get('height')}%"
                    for item in slots
                    if isinstance(item, dict)
                )
                + "."
            )
        present = [
            item["label"]
            for item in direction.get("elements") or []
            if item.get("present")
        ]
        missing = [
            item["label"]
            for item in direction.get("elements") or []
            if not item.get("present")
        ]
        if present:
            lines.append(f"This format has: {', '.join(present)}.")
        if missing:
            lines.append(f"This format does not have: {', '.join(missing)}.")
        message = context.get("campaign_text") or context.get("description") or ""
        if message:
            lines.append(f"Brief lock — campaign message (literal): {message}.")
        lines.append(BRIEF_LOCK_RULES)
        lines.append(ANTI_AI_LOOK)
        if creative_brief.get("visual_bible"):
            lines.append(
                "Shared visual bible for every scene: "
                f"{creative_brief['visual_bible']}."
            )
        lines.extend(
            CreativeModelingService._context_design_prompt_lines(
                creative_brief.get("context_design"),
                context.get("position") or 1,
                total,
            )
        )
        pack = _campaign_pack(creative_brief.get("campaign_pack"))
        extracted = pack.get("extracted") or {}
        if _pack_has_signal(pack):
            lines.append(
                "Campaign pack is the primary offer source. "
                "Use its extracted copy and images. Brand identity only signs "
                "the piece. Do not recycle creative_line offers or old campaigns."
            )
            if extracted.get("headline"):
                lines.append(f"Pack headline (literal): {extracted['headline']}.")
            if extracted.get("subhead"):
                lines.append(f"Pack subhead (literal): {extracted['subhead']}.")
            if extracted.get("cta"):
                lines.append(f"Pack CTA (literal): {extracted['cta']}.")
            if extracted.get("offer"):
                lines.append(f"Pack offer: {extracted['offer']}.")
        storyboard = context.get("storyboard") or creative_brief.get("scenes") or []
        if storyboard:
            lines.append(
                "Full storyboard, preserve progression and do not collapse scenes: "
                + " | ".join(
                    f"{item.get('position')}: {item.get('description')}"
                    for item in storyboard
                    if isinstance(item, dict)
                )
            )
        behavior = context.get("behavior_spec") or {}
        if total > 1:
            lines.append(
                "This still is one beat of the same ad, from the first frame "
                "to the last. Do not recrop scene 1. Keep canvas, brand system "
                "and product identity. The mechanic of this format must be "
                f"legible in this beat: {direction.get('behavior') or behavior.get('type') or 'sequence'}."
            )
        if context.get("tone_of_voice"):
            lines.append(f"Brand tone: {context['tone_of_voice']}.")
        if context.get("primary_color"):
            lines.append(f"Primary brand color: {context['primary_color']}.")
        if context.get("secondary_color"):
            lines.append(f"Secondary brand color: {context['secondary_color']}.")
        has_cta = any(
            item.get("key") == "cta" and item.get("present")
            for item in direction.get("elements") or []
        )
        if has_cta and context.get("cta_text") and int(context.get("position") or 1) == int(total or 1):
            lines.append(f"Call to action: {context['cta_text']}.")
        elif not has_cta:
            lines.append("This format has no CTA. Do not invent a button or endcard command.")
        if not context.get("show_price"):
            lines.append("Do not show prices.")
        if context.get("background_guidance"):
            lines.append(f"Background guidance: {context['background_guidance']}.")
        if context.get("foreground_guidance"):
            lines.append(f"Content guidance: {context['foreground_guidance']}.")
        lines.extend(
            [
                "Keep visual continuity with the campaign sequence while making "
                "this scene independently reviewable.",
                "All visible advertising copy must be Brazilian Portuguese. "
                "Never invent an English slogan; if text cannot be rendered "
                "correctly, omit it. Registered product names may remain unchanged.",
                "Do not reproduce third-party platform logos or interfaces.",
            ]
        )
        for forbidden in context.get("forbidden_elements") or []:
            lines.append(f"Do not include: {forbidden}.")
        return "\n".join(lines)

    def generate_scene_prompt(self, scene_id, created_by=None, payload=None):
        scene_id = _integer(scene_id, "Cena")
        payload = payload if isinstance(payload, dict) else {}
        delta = _text(payload.get("delta"), "Ajuste da cena", max_length=2000)
        context = self.repository.get_scene_context(scene_id)
        apply_creative_line_to_context(context)
        position = context["position"]
        flow_kind = _flow_kind(context)
        locks = _brief_locks(context)
        path = _brief_path(context)
        direction = format_direction(context)
        beat = format_beat(context, position)
        request_context = {
            "campaign": {
                "name": context["campaign_name"],
                "objective": context.get("objective"),
                "message": context.get("description")
                or context.get("campaign_text"),
                "cta": context.get("cta_text"),
                "show_price": context.get("show_price"),
                "scene": context["position"],
                "scene_count": context.get("scene_count") or 1,
                "scene_role": self.scene_role(
                    context["position"],
                    context.get("scene_count") or 1,
                    context,
                ),
                "storyboard": context.get("storyboard") or [],
                "visual_bible": (
                    (context.get("creative_brief") or {}).get("visual_bible")
                ),
                "visible_language": "pt-BR",
                "scene_delta": delta,
                "beat": beat,
            },
            "flow_kind": flow_kind,
            "engine": path.get("engine"),
            "locks": locks,
            "kv_notes": ((context.get("creative_brief") or {}).get("kv_notes") or {}),
            "campaign_pack": _campaign_pack(
                (context.get("creative_brief") or {}).get("campaign_pack")
            ),
            "inherit_from_master": False,
            "master_prompt": None,
            "sequence_bible": (
                (context.get("creative_brief") or {}).get("visual_bible")
            ),
            "client_identity": client_identity_payload(context),
            "format": {
                key: context.get(key)
                for key in (
                    "format_name",
                    "format_slug",
                    "mechanic",
                    "media_type",
                    "aspect_ratio",
                    "default_size",
                    "safe_area",
                    "background_guidance",
                    "foreground_guidance",
                    "layers",
                    "forbidden_elements",
                    "placement_spec",
                    "behavior_spec",
                )
            },
        }
        geometry = resolve_format_geometry(context)
        render_mode = self._resolve_render_mode(
            payload.get("render_mode"), geometry["family"]
        )
        request_context["format"]["iab_family"] = geometry["family"]
        request_context["format"]["target_size"] = geometry.get("target_size")
        request_context["format"]["render_mode"] = render_mode
        request_context["format"]["element_budget"] = geometry.get("budget")
        request_context["format"]["direction"] = direction
        if render_mode == "native":
            request_context["render_constraints"] = apply_render_mode_to_prompt(
                "",
                render_mode,
                geometry,
                self._compose_copy(context),
                flow_kind=flow_kind,
                locks=locks,
            )
        estimate = self._estimate("prompt")
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            None,
            context["format_template_id"],
            "prompt",
            "openrouter",
            DEFAULT_TEXT_MODEL,
            estimate,
            request_payload=request_context,
            created_by=created_by,
            scene_id=scene_id,
        )
        try:
            self.repository.mark_job_generating(job_id)
            generated = self.generator.generate_prompt(request_context)
            prompt = generated["result"]["prompt_en"].strip()
            language_guard = (
                "\n\nVISIBLE COPY REQUIREMENT: All advertising copy visible in the "
                "image must be Brazilian Portuguese. Preserve supplied brand/product "
                "names, use the CTA literally, never invent English slogans, and omit "
                "text that cannot be rendered accurately."
                f"\n\n{BRIEF_LOCK_RULES}\n\n{ANTI_AI_LOOK}"
            )
            if "VISIBLE COPY REQUIREMENT" not in prompt:
                prompt += language_guard
            prompt = apply_render_mode_to_prompt(
                prompt,
                render_mode,
                geometry,
                self._compose_copy(context),
                flow_kind=flow_kind,
                locks=locks,
                engine=path.get("engine"),
            )
            if (
                flow_kind == "unfold"
                and path.get("engine") != ENGINE_CONSTRUCT
                and "LOCK BLOCK FOR GPT IMAGE 2" not in prompt
            ):
                prompt = f"{prompt}\n\n{unfold_image_lock(locks)}"
            scene = self.repository.update_scene_prompt(
                scene_id,
                prompt,
                "approved" if flow_kind == "unfold" else "generated",
            )
            actual = generated.get("actual_cost_usd")
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else actual,
                {
                    "usage": generated.get("usage") or {},
                    "rationale_pt": generated["result"].get("rationale_pt"),
                    "checks": generated["result"].get("checks") or [],
                },
                "review",
            )
            return _serialize({"job_id": job_id, **scene})
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            raise

    def review_scene_prompt(self, scene_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        prompt = _text(
            payload.get("prompt"), "Direção da cena", required=True, max_length=20000
        )
        return _serialize(
            self.repository.update_scene_prompt(
                _integer(scene_id, "Cena"),
                prompt,
                "approved" if payload.get("approved") is True else "reviewed",
            )
        )

    def generate_scene(
        self,
        scene_id,
        files,
        created_by=None,
        render_mode=None,
        fidelity=None,
        source_asset_id=None,
    ):
        scene_id = _integer(scene_id, "Cena")
        references = list(files or [])
        if len(references) > 2:
            raise ValueError("Use no máximo duas imagens de referência.")
        context = self.repository.get_scene_context(scene_id)
        if context.get("media_type") == "video":
            raise ValueError("Vídeo está indisponível para novas produções.")
        if context.get("prompt_status") != "approved":
            raise ValueError("Revise e aprove a direção antes de gerar a imagem.")
        geometry = resolve_format_geometry(context)
        render_mode = self._resolve_render_mode(render_mode, geometry["family"])
        flow_kind = _flow_kind(context)
        locks = _brief_locks(context)
        path = _brief_path(context)
        image_model = path.get("image_model") or DEFAULT_IMAGE_MODEL
        tier = resolve_image_tier(fidelity or path.get("fidelity"))
        source_asset = None
        if source_asset_id not in (None, ""):
            assets = self.repository.get_assets(
                [_integer(source_asset_id, "Peça de origem")],
                approved_only=False,
            )
            if not assets or assets[0].get("scene_id") != scene_id:
                raise CreativeNotFoundError("Peça de origem não encontrada.")
            source_asset = assets[0]
            if (
                tier["name"] == PUBLISH
                and (source_asset.get("metadata") or {}).get("fidelity") == PUBLISH
            ):
                raise ValueError("Esta peça já é publicável.")
        prompt = apply_render_mode_to_prompt(
            context["prompt"] if not source_asset else (
                source_asset.get("job_prompt") or context["prompt"]
            ),
            render_mode,
            geometry,
            self._compose_copy(context),
            flow_kind=flow_kind,
            locks=locks,
            engine=path.get("engine"),
        )
        if (
            flow_kind == "unfold"
            and path.get("engine") != ENGINE_CONSTRUCT
            and "LOCK BLOCK FOR GPT IMAGE 2" not in prompt
        ):
            prompt = f"{prompt}\n\n{unfold_image_lock(locks)}"
        variant_level = "source"
        if tier["name"] == PUBLISH:
            prompt = apply_publish_upgrade(prompt)
            variant_level = "publish"
        estimate = self._estimate("image", tier["name"], image_model)
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            None,
            context["format_template_id"],
            "image",
            "openrouter",
            image_model,
            estimate,
            prompt=prompt,
            request_payload={
                "production_id": context["production_id"],
                "scene_id": scene_id,
                "scene_position": context["position"],
                "render_mode": render_mode,
                "iab_family": geometry["family"],
                "target_size": geometry.get("target_size"),
                "iab_cousin": geometry.get("iab_cousin"),
                "flow_kind": flow_kind,
                "engine": path.get("engine"),
                "image_model": image_model,
                "variant_level": variant_level,
                "fidelity": tier["name"],
                "quality": tier["quality"],
                "resolution": tier["resolution"],
                "parent_asset_id": source_asset["id"] if source_asset else None,
                "locks": locks,
            },
            created_by=created_by,
            scene_id=scene_id,
            reserve_scene=True,
            allow_existing_scene=bool(source_asset) or tier["name"] == PUBLISH,
        )
        saved_paths = []
        try:
            data_urls = []
            for file_storage in references:
                saved = self.storage.save_reference(file_storage)
                saved_paths.append(saved["asset_path"])
                self.repository.add_job_reference(job_id, saved)
                data_urls.append(
                    self.storage.reference_as_data_url(
                        saved["asset_path"], saved["mime_type"]
                    )
                )
            draft_data = None
            if source_asset:
                source_url = (source_asset.get("metadata") or {}).get(
                    "source_raster"
                ) or source_asset.get("asset_url")
                draft_data = self.storage.generated_as_data_url(source_url)
                data_urls.insert(0, draft_data)
                data_urls = data_urls[:2]
            kv_url = ((context.get("creative_brief") or {}).get("source") or {}).get(
                "kv_asset_url"
            )
            kv_data = self._kv_data_url(kv_url)
            if (
                not draft_data
                and flow_kind == "unfold"
                and kv_data
                and len(data_urls) < 2
            ):
                data_urls.insert(0, kv_data)
            if not draft_data and int(context.get("position") or 1) == 1:
                for pack_url in _pack_image_urls(context):
                    if len(data_urls) >= 2:
                        break
                    pack_data = self._kv_data_url(pack_url)
                    if pack_data and pack_data not in data_urls:
                        data_urls.append(pack_data)
            self._attach_previous_reference(
                context, data_urls, path.get("engine"), geometry["family"]
            )
            self._append_brand_references(
                context.get("client_id"),
                data_urls,
                job_id,
                engine=path.get("engine"),
            )
            self.repository.mark_job_generating(job_id)
            generated, composed, layers = self._render_scene_image(
                prompt,
                data_urls,
                context,
                geometry,
                render_mode,
                path,
                image_model,
                tier,
            )
            asset_url = composed["asset_url"]
            response_meta = generated.get("response_metadata") or {}
            quality_review = {
                "approved_recommendation": True,
                "score": None,
                "warnings": [],
                "checks": {},
                "defects": [],
            }
            review_cost = float(layers.get("gate_cost") or 0)
            try:
                review = self.generator.review_image(
                    {
                        "campaign": context.get("campaign_name"),
                        "scene": context.get("position"),
                        "scene_description": context.get("description"),
                        "cta": context.get("cta_text"),
                        "show_price": context.get("show_price"),
                        "safe_area": context.get("safe_area"),
                        "visual_bible": (
                            (context.get("creative_brief") or {}).get("visual_bible")
                        ),
                        "required_language": "pt-BR",
                        "target_size": geometry.get("target_size"),
                        "iab_family": geometry["family"],
                        "render_mode": render_mode,
                        "flow_kind": flow_kind,
                        "locks": locks,
                    },
                    self.storage.generated_as_data_url(asset_url),
                )
                quality_review = _quality_review_data(
                    review.get("result"),
                    force_wrong_canvas=canvas_mismatch(
                        geometry.get("size"),
                        response_meta.get("provider_aspect_ratio")
                        or context.get("aspect_ratio"),
                    ),
                )
                review_cost += float(review.get("actual_cost_usd") or 0)
            except Exception as review_error:
                quality_review["warnings"] = [
                    "A revisão automática não pôde ser concluída; revise a imagem manualmente."
                ]
                quality_review["review_error"] = str(review_error)[:240]
                if canvas_mismatch(
                    geometry.get("size"),
                    response_meta.get("provider_aspect_ratio")
                    or context.get("aspect_ratio"),
                ):
                    quality_review["defects"] = ["wrong_canvas"]
                    quality_review["checks"]["safe_area"] = False
            fidelity = self._publishable_fidelity(
                tier["name"], composed, layers, path.get("engine")
            )
            asset = self.repository.add_generated_asset(
                job_id,
                None,
                "image",
                asset_url,
                {
                    "model": generated.get("model"),
                    "production_id": context["production_id"],
                    "scene_position": context["position"],
                    "quality_review": quality_review,
                    "render_mode": render_mode,
                    "iab_family": geometry["family"],
                    "target_size": geometry.get("target_size"),
                    "iab_cousin": geometry.get("iab_cousin"),
                    "source_raster": composed.get("source_raster"),
                    "flow_kind": flow_kind,
                    "engine": path.get("engine"),
                    "image_model": generated.get("model") or image_model,
                    "variant_level": variant_level,
                    "fidelity": fidelity,
                    "quality": tier["quality"],
                    "resolution": tier["resolution"],
                    "parent_asset_id": source_asset["id"] if source_asset else None,
                    "locks": locks,
                    "composed": composed.get("composed"),
                    "logo_applied": composed.get("logo_applied"),
                    "require_logo": composed.get("require_logo"),
                    "safe_area_clear": layers.get("safe_area_clear"),
                    "needs_retry": layers.get("needs_retry"),
                    "font": composed.get("font"),
                    "renderer": composed.get("renderer"),
                    "requested_aspect_ratio": response_meta.get(
                        "requested_aspect_ratio"
                    ),
                    "provider_aspect_ratio": response_meta.get(
                        "provider_aspect_ratio"
                    ),
                },
                scene_id=scene_id,
            )
            actual = generated.get("actual_cost_usd")
            extra_cost = float(layers.get("image_cost") or 0)
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else float(actual) + extra_cost + review_cost,
                {
                    "usage": generated.get("usage") or {},
                    "needs_retry": layers.get("needs_retry"),
                    "safe_area_clear": layers.get("safe_area_clear"),
                    **(generated.get("response_metadata") or {}),
                },
            )
            return _serialize({"job_id": job_id, "asset": asset, "prompt": prompt})
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            for public_path in saved_paths:
                self.storage.delete(public_path)
            raise

    def refine_scene_asset(
        self, scene_id, asset_id, payload, files=None, created_by=None
    ):
        scene_id = _integer(scene_id, "Cena")
        asset_id = _integer(asset_id, "Asset")
        payload = payload if isinstance(payload, dict) else {}
        intent = _text(payload.get("intent"), "Intenção", max_length=40)
        extras = list(files or [])
        if len(extras) > 1:
            raise ValueError(
                "O ajuste aceita no máximo uma referência extra além da imagem atual."
            )
        context = self.repository.get_scene_context(scene_id)
        if context.get("media_type") == "video":
            raise ValueError("Vídeo está indisponível para novas produções.")
        assets = self.repository.get_assets([asset_id], approved_only=False)
        if not assets or assets[0].get("scene_id") != scene_id:
            raise CreativeNotFoundError("Asset da cena não encontrado.")
        asset = assets[0]
        geometry = resolve_format_geometry(context)
        parent_meta = asset.get("metadata") or {}
        render_mode = self._resolve_render_mode(
            payload.get("render_mode") or parent_meta.get("render_mode"),
            geometry["family"],
        )
        flow_kind = _flow_kind(context)
        locks = _brief_locks(context)
        variant_level = (
            "ab_max" if intent in {"ab_max", "max", "maximum"} else
            "ab_simple" if intent in {"ab_simple", "simple"} else
            None
        )
        instruction = self._refine_instruction(
            payload.get("instruction"), intent, geometry["family"], locks
        )
        job_prompt = (asset.get("job_prompt") or context.get("prompt") or "").strip()
        if not job_prompt:
            raise ValueError("Não há prompt do job para ajustar esta imagem.")
        path = _brief_path(context)
        prompt = apply_render_mode_to_prompt(
            (
                f"{job_prompt}\n\nRefinement instruction: {instruction}\n"
                "Use the attached generated image as the primary reference. "
                "Change only what the refinement instruction requests. "
                "Preserve the inherited visual system, brand identity and CTA "
                "unless the instruction asks otherwise."
            ),
            render_mode,
            geometry,
            self._compose_copy(context),
            flow_kind=flow_kind,
            locks=locks,
            engine=path.get("engine"),
        )
        if intent:
            prompt += f"\nRefinement intent: {intent}."
        if variant_level and path.get("engine") != ENGINE_CONSTRUCT:
            prompt = f"{prompt}\n\n{unfold_image_lock(locks)}"
        tier = resolve_image_tier(DRAFT)
        estimate = self._estimate("image", tier["name"])
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            None,
            context["format_template_id"],
            "image",
            "openrouter",
            DEFAULT_IMAGE_MODEL,
            estimate,
            prompt=prompt,
            request_payload={
                "production_id": context["production_id"],
                "scene_id": scene_id,
                "scene_position": context["position"],
                "parent_asset_id": asset_id,
                "refinement_instruction": instruction,
                "refine_intent": intent,
                "variant_level": variant_level or intent,
                "fidelity": tier["name"],
                "quality": tier["quality"],
                "resolution": tier["resolution"],
                "flow_kind": flow_kind,
                "locks": locks,
                "render_mode": render_mode,
                "iab_family": geometry["family"],
                "target_size": geometry.get("target_size"),
            },
            created_by=created_by,
            scene_id=scene_id,
            reserve_scene=True,
            allow_existing_scene=True,
        )
        saved_paths = []
        try:
            source_url = parent_meta.get("source_raster") or asset["asset_url"]
            data_urls = [self.storage.generated_as_data_url(source_url)]
            for file_storage in extras:
                saved = self.storage.save_reference(file_storage)
                saved_paths.append(saved["asset_path"])
                self.repository.add_job_reference(job_id, saved)
                data_urls.append(
                    self.storage.reference_as_data_url(
                        saved["asset_path"], saved["mime_type"]
                    )
                )
            self._append_brand_references(
                context.get("client_id"),
                data_urls,
                job_id,
                engine=path.get("engine"),
            )
            self.repository.mark_job_generating(job_id)
            generated = self.generator.generate_image(
                prompt,
                data_urls,
                aspect_ratio=context.get("aspect_ratio") or "16:9",
                quality=tier["quality"],
                resolution=tier["resolution"],
            )
            raw_url = self.storage.save_generated_base64(
                generated["b64_json"], generated.get("output_format", "png")
            )
            composed = self._compose_native_asset(
                raw_url,
                generated["b64_json"],
                context,
                geometry,
                render_mode,
                engine=path.get("engine"),
                html_compose=_flow_kind(context) != "unfold",
            )
            result = self.repository.add_generated_asset(
                job_id,
                None,
                "image",
                composed["asset_url"],
                {
                    "model": generated.get("model"),
                    "production_id": context["production_id"],
                    "scene_position": context["position"],
                    "parent_asset_id": asset_id,
                    "refinement_instruction": instruction,
                    "refine_intent": intent,
                    "source_job_prompt": job_prompt,
                    "render_mode": render_mode,
                    "iab_family": geometry["family"],
                    "target_size": geometry.get("target_size"),
                    "iab_cousin": geometry.get("iab_cousin"),
                    "source_raster": composed.get("source_raster"),
                    "fidelity": tier["name"],
                    "quality": tier["quality"],
                    "resolution": tier["resolution"],
                    **(generated.get("response_metadata") or {}),
                },
                scene_id=scene_id,
            )
            actual = generated.get("actual_cost_usd")
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else actual,
                {
                    "usage": generated.get("usage") or {},
                    **(generated.get("response_metadata") or {}),
                },
            )
            return _serialize({
                "job_id": job_id,
                "asset": result,
                "prompt": prompt,
            })
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            for public_path in saved_paths:
                self.storage.delete(public_path)
            raise

    def review_scene(self, scene_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        status = payload.get("status")
        if status not in ("approved", "rejected"):
            raise ValueError("Status da cena deve ser approved ou rejected.")
        result = self.repository.review_scene_asset(
            _integer(scene_id, "Cena"),
            _integer(payload.get("asset_id"), "Asset"),
            status,
        )
        self._record_compose_feedback(
            _integer(scene_id, "Cena"),
            payload,
            status,
        )
        return _serialize(result)

    def select_simulation_asset(self, production_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        return _serialize(
            self.repository.select_production_asset(
                _integer(production_id, "Produção"),
                _integer(payload.get("asset_id"), "Asset"),
            )
        )

    def select_scene_preview_asset(self, scene_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        return _serialize(
            self.repository.set_scene_preview_asset(
                _integer(scene_id, "Cena"),
                _integer(payload.get("asset_id"), "Asset"),
            )
        )

    def create_campaign(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        if payload.get("format_template_id") not in (None, ""):
            plan_payload = {
                **payload,
                "productions": [
                    {
                        "format_template_id": payload["format_template_id"],
                        "scene_descriptions": (
                            payload.get("scene_descriptions") or []
                        ),
                    }
                ],
            }
            created = self.create_production_plan(plan_payload)
            campaign = created["campaign"]
            production = campaign.get("production")
            if production and production.get("scenes"):
                campaign["created_scene_id"] = production["scenes"][0]["id"]
            self._maybe_generate_campaign_design_system(campaign)
            return campaign
        show_price = payload.get("show_price", False)
        if not isinstance(show_price, bool):
            raise ValueError("Exibir preço deve ser verdadeiro ou falso.")
        client_id, client_source = _campaign_client_ref(payload)
        raw_first_step = payload.get("first_step")
        if not isinstance(raw_first_step, dict):
            raise ValueError("Formato inicial é obrigatório.")
        mockup = _text(
            raw_first_step.get("mockup"),
            "Ambiente inicial",
            required=True,
        )
        if mockup not in MOCKUPS:
            raise ValueError("Ambiente inicial inválido.")
        data = {
            "client_id": client_id,
            "client_source": client_source,
            "name": _text(
                payload.get("name"),
                "Nome da campanha",
                required=True,
                max_length=200,
            ),
            "objective": _text(
                payload.get("objective"), "Objetivo", max_length=120
            ),
            "campaign_text": _text(
                payload.get("campaign_text"),
                "Texto da campanha",
                max_length=12000,
            ),
            "cta_text": _text(payload.get("cta_text"), "CTA", max_length=1000),
            "show_price": show_price,
            "budget_usd": _money(
                5 if payload.get("budget_usd") in (None, "") else payload["budget_usd"]
            ),
            "first_step": {
                "format_template_id": _integer(
                    raw_first_step.get("format_template_id"),
                    "Formato inicial",
                ),
                "mockup": mockup,
                "scene_description": _text(
                    raw_first_step.get("scene_description"),
                    "Descrição do primeiro step",
                    max_length=8000,
                ),
            },
        }
        created = self.repository.create_campaign_with_variation_a(data)
        campaign = self.repository.get_campaign(created["id"])
        campaign["created_step_id"] = created["step_id"]
        self._maybe_generate_campaign_design_system(campaign)
        return _serialize(campaign)

    def campaign_detail(self, campaign_id):
        campaign = self.repository.get_campaign(_integer(campaign_id, "Campanha"))
        data = annotate_cost(campaign, campaign.get("spent_usd"))
        data["flow_kind"] = _flow_kind(data)
        client = data.get("client") if isinstance(data.get("client"), dict) else {}
        brief = data.get("creative_brief") if isinstance(data.get("creative_brief"), dict) else {}
        bancada = brief.get("bancada") if isinstance(brief.get("bancada"), dict) else {}
        data["brand_dna"] = materialize_brand_dna(
            client,
            client.get("brand_profile"),
            bancada.get("brand_dna") or (client.get("brand_profile") or {}).get("brand_dna"),
        )
        return _serialize(data)

    def save_bancada_document(self, campaign_id, payload):
        if not isinstance(payload, dict):
            raise ValueError("Corpo JSON inválido.")
        campaign_id = _integer(campaign_id, "Campanha")
        campaign = self.repository.get_campaign(campaign_id)
        brief = campaign.get("creative_brief")
        brief = dict(brief) if isinstance(brief, dict) else {}
        client = campaign.get("client") if isinstance(campaign.get("client"), dict) else {}
        profile = client.get("brand_profile") if isinstance(client.get("brand_profile"), dict) else {}
        dna = materialize_brand_dna(
            client,
            profile,
            payload.get("brand_dna")
            or (brief.get("bancada") or {}).get("brand_dna")
            or profile.get("brand_dna"),
        )
        layers = apply_brand_dna_to_layers(
            sanitize_compose_regions(payload.get("layers") or payload.get("regions")),
            dna,
        )
        tags = []
        for item in payload.get("tags") or []:
            label = str(item or "").strip()
            if label and label not in tags:
                tags.append(label[:48])
            if len(tags) >= 8:
                break
        title = str(payload.get("title") or campaign.get("name") or "").strip()[:180]
        try:
            zoom = max(25, min(300, int(payload.get("zoom") or 100)))
        except (TypeError, ValueError):
            zoom = 100
        scene_id = payload.get("active_scene_id")
        if scene_id not in (None, ""):
            try:
                scene_id = int(scene_id)
            except (TypeError, ValueError):
                scene_id = str(scene_id)[:64]
        else:
            scene_id = None
        cards = []
        for item in payload.get("cards") or payload.get("scenes") or []:
            if not isinstance(item, dict):
                continue
            try:
                duration = max(0.4, min(12.0, float(item.get("duration") or 2)))
            except (TypeError, ValueError):
                duration = 2.0
            card_scene = item.get("scene_id")
            if card_scene not in (None, ""):
                try:
                    card_scene = int(card_scene)
                except (TypeError, ValueError):
                    card_scene = str(card_scene)[:64]
            else:
                card_scene = None
            role = str(item.get("role") or "")[:32]
            regenerate = [
                str(name)[:32]
                for name in (item.get("regenerate") or [])
                if str(name).strip()
            ][:8]
            cards.append({
                "id": str(item.get("id") or "")[:64],
                "label": str(item.get("label") or "")[:80],
                "duration": duration,
                "layers": sanitize_compose_regions(item.get("layers") or []),
                "scene_id": card_scene,
                "role": role,
                "regenerate": regenerate,
                "brand_dna_id": str(item.get("brand_dna_id") or dna["id"])[:80],
            })
            if len(cards) >= 8:
                break
        cards = attach_brand_dna_to_scenes(cards, dna)
        report = check_brand_dna(layers, dna)
        bancada = {
            "layers": layers,
            "scenes": cards,
            "cards": cards,
            "tags": tags,
            "title": title,
            "exploded": bool(payload.get("exploded")),
            "zoom": zoom,
            "active_layer_id": str(payload.get("active_layer_id") or "")[:64],
            "active_scene_id": scene_id,
            "brand_dna_id": dna["id"],
            "brand_dna": dna,
            "brand_check": report,
        }
        brief["bancada"] = bancada
        if layers:
            compose = brief.get("compose_library")
            compose = dict(compose) if isinstance(compose, dict) else {}
            params = dict(compose.get("params") or {})
            params["regions"] = layers
            compose["params"] = params
            brief["compose_library"] = compose
        self.repository.update_campaign_bancada(
            campaign_id,
            brief,
            title or None,
        )
        return _serialize({
            "campaign_id": campaign_id,
            "bancada": bancada,
        })

    def html5_package(self, campaign_id):
        campaign = self.campaign_detail(campaign_id)
        brief = campaign.get("creative_brief") if isinstance(campaign.get("creative_brief"), dict) else {}
        bancada = brief.get("bancada") if isinstance(brief.get("bancada"), dict) else {}
        production = campaign.get("production") or {}
        geometry = resolve_format_geometry({
            "slug": production.get("format_slug"),
            "default_size": production.get("default_size"),
            "aspect_ratio": production.get("aspect_ratio"),
        }) if production else {}
        size = parse_format_size(
            (geometry or {}).get("size") or production.get("default_size"),
            (300, 250),
        )
        family = (geometry or {}).get("family") or "rectangle"
        client = campaign.get("client") or {}
        copy = {
            "headline": str(campaign.get("campaign_text") or campaign.get("name") or ""),
            "cta": str(campaign.get("cta_text") or ""),
            "brand_color": client.get("primary_color") or "#1E4D4F",
            "legal": "",
        }
        still_url = ""
        for scene in production.get("scenes") or []:
            for asset in scene.get("assets") or []:
                url = asset.get("asset_url") or asset.get("preview_url")
                if url:
                    still_url = url
                    break
            if still_url:
                break
        logo_url = client.get("logo_url") or ""
        cards_spec = bancada.get("cards") or bancada.get("scenes") or []
        if not cards_spec:
            cards_spec = [{
                "layers": bancada.get("layers") or [],
                "duration": 2,
                "label": "Card 1",
            }]
        frames = []
        for card in cards_spec:
            layers = card.get("layers") or bancada.get("layers") or []
            card_copy = dict(copy)
            card_copy["compose_params"] = {"regions": layers}
            card_copy["html_key"] = "card_fragment.html"
            html = render_card_fragment(
                {"family": family, "size": size, "html_key": "card_fragment.html"},
                card_copy,
                still_url=still_url,
                logo_url=logo_url,
            )
            frames.append({"html": html, "duration": card.get("duration") or 2})
        index_html = render_html5_player(
            {"size": size, "family": family},
            frames,
            title=bancada.get("title") or campaign.get("name") or "Criativo",
        )
        backup = None
        try:
            from .creative_html_compose import screenshot_html
            backup = screenshot_html(index_html, size[0], size[1])
        except Exception:
            backup = None
        memory, filename = pack_html5_zip(
            index_html,
            backup,
            f"{(campaign.get('name') or 'criativo-html5').replace(' ', '-')[:40]}.zip",
        )
        return memory, filename

    def image_credits(self, user_id=None):
        used, monthly = 0, 500
        try:
            from .db import get_db

            conn = get_db()
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(p.image_credits_used_current_month, 0) AS used,
                           COALESCE(
                               pd.limit_image_generation,
                               p.image_credits_monthly,
                               500
                           ) AS monthly
                      FROM cadu_client_plans p
                      LEFT JOIN cadu_plan_definitions pd
                        ON p.id_plan_definition = pd.id
                     WHERE p.plan_status IN ('active', 'trial', 'ativo')
                     ORDER BY p.id DESC
                     LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if row:
                    used = int(row["used"] or 0)
                    monthly = int(row["monthly"] or 500) or 500
        except Exception:
            pass
        return {"used": used, "monthly": monthly}

    def _campaign_kv_source(self, campaign):
        brief = campaign.get("creative_brief") if isinstance(campaign, dict) else {}
        if not isinstance(brief, dict):
            brief = {}
        url = ((brief.get("source") or {}).get("kv_asset_url"))
        data = self._read_logo_path(
            url, getattr(self.storage, "read_public_bytes", None)
        )
        return url, data

    def _kv_data_url(self, public_path):
        if not public_path:
            return None
        path = str(public_path)
        try:
            if path.startswith("/static/uploads/creative_references/"):
                return self.storage.reference_as_data_url(path, "image/png")
            return self.storage.generated_as_data_url(path)
        except Exception:
            return None

    def read_campaign_pack(self, payload, files=None):
        payload = payload if isinstance(payload, dict) else {}
        files = list(files or [])[:4]
        page_url = _text(
            payload.get("page_url") or payload.get("url"),
            "URL da campanha",
            max_length=2000,
        )
        if not files and not page_url:
            raise ValueError("Envie um criativo desta campanha ou informe o link.")
        sources = []
        extracted = {
            "headline": "",
            "subhead": "",
            "cta": "",
            "offer": "",
            "other_lines": [],
        }
        locks = normalize_locks({})
        for uploaded in files:
            saved = self.storage.save_reference(uploaded)
            sources.append({
                "kind": "image",
                "name": saved.get("original_name") or "criativo",
                "asset_url": saved.get("asset_path"),
            })
            try:
                data_url = self.storage.reference_as_data_url(
                    saved["asset_path"], saved.get("mime_type") or "image/png"
                )
                result = self.generator.extract_kv_locks({}, data_url)
                incoming = normalize_locks(result.get("result"))
                if not extracted["headline"] and incoming.get("headline"):
                    extracted["headline"] = incoming.get("headline") or ""
                if not extracted["subhead"] and incoming.get("subhead"):
                    extracted["subhead"] = incoming.get("subhead") or ""
                if not extracted["cta"] and incoming.get("cta"):
                    extracted["cta"] = incoming.get("cta") or ""
                for line in incoming.get("other_lines") or []:
                    if line and line not in extracted["other_lines"]:
                        extracted["other_lines"].append(line)
                if incoming:
                    locks = incoming
            except Exception:
                pass
        if page_url:
            normalized = _normalized_public_url(page_url)
            sources.append({
                "kind": "url",
                "name": normalized,
                "page_url": normalized,
            })
            try:
                evidence, _record = _compact_web_evidence(normalized)
                bits = [
                    evidence.get("title"),
                    evidence.get("description"),
                ]
                pages = evidence.get("pages") or []
                if pages and isinstance(pages[0], dict):
                    bits.append(pages[0].get("content"))
                notes = " ".join(
                    str(bit).strip() for bit in bits if bit and str(bit).strip()
                )
                if notes and not extracted["offer"]:
                    extracted["offer"] = notes[:4000]
            except Exception:
                if not extracted["offer"]:
                    extracted["offer"] = normalized
        pack = _campaign_pack({
            "sources": sources,
            "extracted": extracted,
            "locks": locks,
        })
        preview_url = next(
            (
                item.get("asset_url")
                for item in pack.get("sources") or []
                if item.get("kind") == "image" and item.get("asset_url")
            ),
            None,
        )
        return {
            "campaign_pack": pack,
            "extracted": pack.get("extracted") or {},
            "locks": pack.get("locks") or {},
            "preview_url": preview_url,
        }

    EXAMPLE_KV_PROMPT = (
        "Finished photoreal 16:9 advertising key visual for a Brazilian home-broadband "
        "campaign. Distinct empty-separated zones, no overlapping type on faces. "
        "Top-left teal wordmark NEXO. Left column: Portuguese headline "
        "'A casa inteira no mesmo plano', offer '500 Mega + 3 linhas', solid CTA "
        "button 'Assine agora'. Bottom legal line "
        "'Consulte regulamentação. Oferta válida por tempo limitado.' "
        "Right half: lifestyle photo of a Brazilian family on a sofa, product-free "
        "hands. Brand teal #1E4D4F and lime #9CCF31. Print-ready agency master. "
        "No English slogans, no extra logos, no watermarks."
    )
    EXAMPLE_KV_COPY = {
        "name": "A casa inteira no mesmo plano",
        "headline": "A casa inteira no mesmo plano",
        "cta": "Assine agora",
        "subhead": "500 Mega + 3 linhas",
        "other_lines": [
            "Consulte regulamentação. Oferta válida por tempo limitado.",
        ],
        "has_logo": True,
        "items": {
            "logo": {"text": "NEXO", "status": "seen"},
            "product_lockup": {"text": "", "status": "absent"},
            "talent": {"text": "Família no sofá", "status": "seen"},
            "headline": {
                "text": "A casa inteira no mesmo plano",
                "status": "seen",
            },
            "offer": {"text": "500 Mega + 3 linhas", "status": "seen"},
            "benefits": {"text": "", "status": "absent"},
            "cta": {"text": "Assine agora", "status": "seen"},
            "legal": {
                "text": "Consulte regulamentação. Oferta válida por tempo limitado.",
                "status": "seen",
            },
            "background": {"text": "", "status": "absent"},
        },
    }

    def create_example_kv(self):
        generate = getattr(self.generator, "generate_image", None)
        if not callable(generate):
            raise ValueError("Gerador de imagem indisponível.")
        result = generate(
            self.EXAMPLE_KV_PROMPT,
            [],
            "16:9",
            model="openai/gpt-image-2",
        )
        encoded = (result or {}).get("b64_json")
        if not encoded:
            raise ValueError("O GPT Image 2 não devolveu o KV.")
        payload = dict(self.EXAMPLE_KV_COPY)
        payload["data_url"] = f"data:image/png;base64,{encoded}"
        payload["model"] = result.get("model") or "openai/gpt-image-2"
        return _serialize(payload)

    def read_kv(self, payload, files=None):
        payload = payload if isinstance(payload, dict) else {}
        files = list(files or [])
        source_asset_id = payload.get("source_asset_id")
        kv_data = None
        preview_url = None
        if source_asset_id not in (None, ""):
            assets = self.repository.get_assets(
                [_integer(source_asset_id, "Peça de origem")],
                approved_only=False,
            )
            if not assets:
                raise CreativeNotFoundError("Peça de origem não encontrada.")
            preview_url = assets[0].get("asset_url")
            kv_data = self._kv_data_url(preview_url)
        elif files:
            uploaded = files[0]
            raw = uploaded.read()
            if hasattr(uploaded, "stream"):
                try:
                    uploaded.stream.seek(0)
                except Exception:
                    pass
            if not raw:
                raise ValueError("Envie o KV ou escolha uma peça gerada.")
            mime = getattr(uploaded, "mimetype", None) or "image/png"
            kv_data = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        else:
            raise ValueError("Envie o KV ou escolha uma peça gerada.")
        extracted = {"headline": "", "subhead": "", "cta": "", "other_lines": [], "has_logo": False}
        try:
            result = self.generator.extract_kv_locks(
                {"source_asset_id": source_asset_id},
                kv_data,
            )
            extracted = normalize_locks(result.get("result"))
        except Exception:
            extracted = normalize_locks(extracted)
        name = extracted["headline"] or (
            extracted["other_lines"][0] if extracted["other_lines"] else ""
        )
        name = (name or "Desdobramento")[:120]
        return _serialize({
            **extracted,
            "name": name,
            "preview_url": preview_url,
        })

    def create_unfolding(self, payload, files=None, created_by=None):
        payload = payload if isinstance(payload, dict) else {}
        files = list(files or [])
        client_ref = str(payload.get("client_ref") or "")
        if client_ref.startswith("crm:"):
            payload["client_source"] = "crm"
            payload["client_id"] = client_ref.split(":", 1)[1]
        elif client_ref.startswith("profile:"):
            payload["client_source"] = "creative"
            payload["client_id"] = client_ref.split(":", 1)[1]
        raw_ids = payload.get("format_ids") or payload.get("format_template_ids") or []
        if isinstance(raw_ids, str):
            raw_ids = [item for item in raw_ids.split(",") if item.strip()]
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValueError("Escolha ao menos um formato para desdobrar.")
        kv_notes = payload.get("kv_notes") if isinstance(payload.get("kv_notes"), dict) else {}
        notes = {
            "offer": _text(payload.get("offer") or kv_notes.get("offer"), "Oferta", max_length=2000),
            "mandatory": _text(
                payload.get("mandatory") or kv_notes.get("mandatory"),
                "Obrigatório na arte",
                max_length=2000,
            ),
            "crop_note": _text(
                payload.get("crop_note") or kv_notes.get("crop_note"),
                "Recorte",
                max_length=1000,
            ),
        }
        source_asset_id = payload.get("source_asset_id")
        source = {"type": "upload"}
        kv_url = None
        if source_asset_id not in (None, ""):
            assets = self.repository.get_assets(
                [_integer(source_asset_id, "Peça de origem")],
                approved_only=False,
            )
            if not assets:
                raise CreativeNotFoundError("Peça de origem não encontrada.")
            kv_url = assets[0].get("asset_url")
            source = {
                "type": "approved_asset",
                "asset_id": assets[0]["id"],
                "kv_asset_url": kv_url,
            }
        elif files:
            saved = self.storage.save_reference(files[0])
            kv_url = saved["asset_path"]
            source = {"type": "upload", "kv_asset_url": kv_url}
        else:
            raise ValueError("Envie o KV ou escolha uma peça aprovada.")
        locks = normalize_locks(payload.get("locks") or {
            "headline": payload.get("headline") or payload.get("campaign_text"),
            "cta": payload.get("cta_text"),
            "subhead": payload.get("subhead") or payload.get("offer"),
            "has_logo": payload.get("has_logo", True),
            "items": payload.get("items"),
        })
        path = resolve_construct_path(payload)
        if not locks["headline"] or not locks["cta"]:
            kv_data = self._kv_data_url(kv_url)
            try:
                extracted = self.generator.extract_kv_locks(
                    {"kv_notes": notes, "supplied": locks},
                    kv_data,
                )
                merged = normalize_locks(extracted.get("result"))
                if not locks["headline"]:
                    locks["headline"] = merged["headline"]
                if not locks["subhead"]:
                    locks["subhead"] = merged["subhead"]
                if not locks["cta"]:
                    locks["cta"] = merged["cta"]
                if not locks["other_lines"]:
                    locks["other_lines"] = merged["other_lines"]
                locks["has_logo"] = locks["has_logo"] or merged["has_logo"]
            except Exception:
                pass
        if not locks["headline"]:
            locks["headline"] = _text(
                payload.get("campaign_text"), "Mensagem", max_length=500
            ) or ""
        if not locks["cta"]:
            locks["cta"] = _text(payload.get("cta_text"), "CTA", max_length=200) or ""
        plan = self.create_production_plan({
            "client_source": payload.get("client_source", "creative"),
            "client_id": payload.get("client_id"),
            "name": payload.get("name"),
            "objective": payload.get("objective") or "Desdobramento",
            "campaign_text": locks["headline"] or notes.get("offer") or payload.get("name"),
            "cta_text": locks["cta"],
            "show_price": payload.get("show_price", False),
            "budget_usd": payload.get("budget_usd") if payload.get("budget_usd") not in (None, "") else 8,
            "visual_bible": notes.get("offer") or "",
            "flow_kind": "unfold",
            "kv_notes": notes,
            "locks": locks,
            "source": source,
            "engine": path["engine"],
            "scene_pack": path["scene_pack"],
            "image_model": path["image_model"],
            "fidelity": path["fidelity"],
            "construct_path": path,
            "productions": [
                {"format_template_id": _integer(item, "Formato")}
                for item in raw_ids
            ],
        })
        if created_by:
            plan["created_by"] = created_by
        return plan

    def generate_unfolding(self, campaign_id, created_by=None, payload=None):
        campaign = self.campaign_detail(campaign_id)
        if _flow_kind(campaign) != "unfold":
            raise ValueError("Esta campanha não é um desdobramento.")
        path = resolve_construct_path({
            **(_brief_path(campaign)),
            **(payload if isinstance(payload, dict) else {}),
        })
        pieces = []
        kv_url, kv_bytes = self._campaign_kv_source(campaign)
        kv_master = None
        if path.get("engine") == ENGINE_CONSTRUCT:
            if not kv_bytes:
                raise ValueError(
                    "Não consegui ler o KV para montar as peças. Envie o arquivo de novo."
                )
            kv_master = {
                "scene_id": None,
                "asset": {
                    "id": None,
                    "asset_url": kv_url,
                    "metadata": {"source_raster": kv_url},
                },
            }
        for production in campaign.get("productions") or []:
            slug = production.get("format_slug")
            key = (
                scene_key_for_slug(slug, path.get("scene_pack"))
                if path.get("engine") == ENGINE_CONSTRUCT
                else None
            )
            for scene in production.get("scenes") or []:
                if kv_master:
                    generated = self._derive_format_from_master(
                        scene["id"],
                        kv_master,
                        created_by=created_by,
                        path=path,
                    )
                else:
                    if scene.get("prompt_status") != "approved":
                        self.generate_scene_prompt(scene["id"], created_by=created_by)
                    generated = self.generate_scene(
                        scene["id"],
                        [],
                        created_by=created_by,
                        fidelity=path["fidelity"],
                    )
                pieces.append({
                    "production_id": production.get("id"),
                    "scene_id": scene["id"],
                    "format_template_id": production.get("format_template_id"),
                    "scene_key": key,
                    **generated,
                })
        detail = self.campaign_detail(campaign_id)
        detail["pieces"] = pieces
        detail["construct_path"] = path
        return detail

    def quote_unfolding(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        slugs = payload.get("format_slugs") or payload.get("slugs") or []
        if isinstance(slugs, str):
            slugs = [item.strip() for item in slugs.split(",") if item.strip()]
        raw_ids = payload.get("format_ids") or payload.get("format_template_ids") or []
        if isinstance(raw_ids, str):
            raw_ids = [item for item in raw_ids.split(",") if item.strip()]
        if not slugs and raw_ids:
            for item in raw_ids:
                try:
                    row = self.repository.get_format(_integer(item, "Formato"))
                except Exception:
                    row = None
                if row and row.get("slug"):
                    slugs.append(row["slug"])
        quoted = quote_unfold_path(payload, slugs)
        quoted["paths"] = describe_unfold_paths()
        return _serialize(quoted)

    def list_unfold_paths(self):
        return _serialize(describe_unfold_paths())

    def _campaign_publish_candidates(self, campaign, asset_ids=None):
        wanted = None
        if asset_ids not in (None, ""):
            if not isinstance(asset_ids, list):
                raise ValueError("asset_ids deve ser uma lista.")
            wanted = {
                _integer(item, "Peça")
                for item in asset_ids
            }
        pieces = []
        for production in campaign.get("productions") or []:
            for scene in production.get("scenes") or []:
                assets = [
                    item for item in (scene.get("assets") or [])
                    if item.get("asset_type") != "video"
                ]
                if wanted is not None:
                    assets = [item for item in assets if item.get("id") in wanted]
                if _flow_kind(campaign) != "unfold":
                    assets = [
                        item for item in assets if item.get("status") == "approved"
                    ]
                if not assets:
                    continue
                publish = next(
                    (
                        item for item in reversed(assets)
                        if (item.get("metadata") or {}).get("fidelity") == PUBLISH
                    ),
                    None,
                )
                draft = next(
                    (
                        item for item in reversed(assets)
                        if (item.get("metadata") or {}).get("fidelity") != PUBLISH
                    ),
                    assets[-1],
                )
                if publish and wanted is None:
                    continue
                source = draft if (draft and (not publish or wanted)) else publish
                if source and (source.get("metadata") or {}).get("fidelity") != PUBLISH:
                    pieces.append({
                        "scene_id": scene["id"],
                        "asset_id": source["id"],
                        "format_template_id": production.get("format_template_id"),
                        "fidelity": (source.get("metadata") or {}).get("fidelity") or DRAFT,
                    })
        return pieces

    def quote_campaign_publish(self, campaign_id, asset_ids=None):
        campaign = self.campaign_detail(campaign_id)
        pieces = self._campaign_publish_candidates(campaign, asset_ids)
        quote = quote_image_publish(len(pieces), PUBLISH)
        quote["pieces"] = pieces
        quote["campaign_id"] = campaign.get("id")
        quote["flow_kind"] = _flow_kind(campaign)
        return _serialize(quote)

    def publish_scene_asset(self, scene_id, asset_id, created_by=None, render_mode=None):
        return self.generate_scene(
            scene_id,
            [],
            created_by=created_by,
            render_mode=render_mode,
            fidelity=PUBLISH,
            source_asset_id=asset_id,
        )

    def publish_campaign(self, campaign_id, payload=None, created_by=None):
        payload = payload if isinstance(payload, dict) else {}
        quote = self.quote_campaign_publish(campaign_id, payload.get("asset_ids"))
        if not quote["pieces"]:
            raise ValueError(
                "Não há rascunhos para gerar em alta."
                if quote.get("flow_kind") == "unfold"
                else "Não há cenas aprovadas em mockup para gerar em alta."
            )
        pieces = []
        for item in quote["pieces"]:
            pieces.append({
                **item,
                **self.publish_scene_asset(
                    item["scene_id"], item["asset_id"], created_by=created_by
                ),
            })
        detail = self.campaign_detail(campaign_id)
        detail["quote"] = quote
        detail["pieces"] = pieces
        return detail

    def prepare_campaign_video(self, campaign_id):
        campaign = self.campaign_detail(_integer(campaign_id, "Campanha"))
        approved = []
        missing_high = []
        for production in campaign.get("productions") or []:
            for scene in production.get("scenes") or []:
                assets = [
                    item for item in (scene.get("assets") or [])
                    if item.get("asset_type") != "video"
                    and item.get("status") == "approved"
                ]
                if not assets:
                    continue
                high = next(
                    (
                        item for item in reversed(assets)
                        if (item.get("metadata") or {}).get("fidelity") == PUBLISH
                    ),
                    None,
                )
                approved.append({"scene_id": scene["id"], "asset_id": (high or assets[-1])["id"]})
                if not high:
                    missing_high.append(scene["id"])
        if not approved:
            raise ValueError("Aprove as cenas em mockup antes de montar o vídeo.")
        if missing_high:
            raise ValueError(
                "Gere a alta resolução das cenas aprovadas antes de montar o vídeo."
            )
        return _serialize({
            "status": "mocked",
            "ready": False,
            "message": "Pipeline de vídeo ainda não está pronto.",
            "campaign_id": campaign.get("id"),
            "scenes": approved,
        })

    def create_variation(self, campaign_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        notes = _text(payload.get("notes"), "Hipótese", max_length=2000)
        return self.repository.create_variation(
            _integer(campaign_id, "Campanha"), notes
        )

    def save_variation(self, variation_id, payload):
        if not isinstance(payload, dict):
            raise ValueError("Corpo JSON inválido.")
        notes = _text(payload.get("notes"), "Hipótese", max_length=2000)
        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list):
            raise ValueError("steps deve ser uma lista.")
        if len(raw_steps) > 20:
            raise ValueError("Cada variação pode ter no máximo 20 steps.")
        steps = []
        for index, raw in enumerate(raw_steps, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Step {index} inválido.")
            mockup = _text(
                raw.get("mockup"), f"Mockup do step {index}", required=True
            )
            if mockup not in MOCKUPS:
                raise ValueError(f"Mockup do step {index} inválido.")
            step = {
                "format_template_id": _integer(
                    raw.get("format_template_id"),
                    f"Formato do step {index}",
                ),
                "mockup": mockup,
                "scene_description": _text(
                    raw.get("scene_description"),
                    f"Descrição do step {index}",
                    max_length=8000,
                ),
            }
            if raw.get("id") not in (None, ""):
                step["id"] = _integer(raw["id"], f"ID do step {index}")
            steps.append(step)
        saved = self.repository.save_variation(
            _integer(variation_id, "Variação"), notes, steps
        )
        return {"steps": saved}

    def delete_variation(self, variation_id):
        self.repository.delete_variation(_integer(variation_id, "Variação"))

    @staticmethod
    def build_prompt(context, step, total_steps):
        apply_creative_line_to_context(context)
        scene = step.get("scene_description") or context.get("campaign_text") or ""
        client_name = context.get("client_name") or ""
        client_sector = context.get("client_sector") or ""
        logo_ref = context.get("logo_upload_path") or context.get("logo_url")
        brand_profile = context.get("brand_profile") or {}
        mockup_desc = MOCKUPS[step["mockup"]]

        lines = [
            "[CONTEXTO DE TELA]",
            mockup_desc,
            "",
            "[CLIENTE]",
            f"Marca: {client_name}",
            f"Setor: {client_sector}",
        ]
        if context.get("tone_of_voice"):
            lines.append(f"Tom de marca: {context['tone_of_voice']}")
        if logo_ref:
            lines.append(f"Referência de logo (URL): {logo_ref}")
        if context.get("primary_color"):
            lines.append(f"Cor primária da marca: {context['primary_color']}")
        if context.get("secondary_color"):
            lines.append(f"Cor secundária da marca: {context['secondary_color']}")
        if brand_profile.get("brand_summary"):
            lines.append(f"Posicionamento: {brand_profile['brand_summary']}")
        if brand_profile.get("target_audience"):
            lines.append(f"Público-alvo: {brand_profile['target_audience']}")
        if brand_profile.get("ad_segments"):
            lines.append(
                "Segmentos/ângulos recomendados: "
                + " | ".join(brand_profile["ad_segments"])
            )
        if brand_profile.get("creative_guidelines"):
            lines.append(
                f"Direção criativa: {brand_profile['creative_guidelines']}"
            )
        profile_labels = (
            ("products_services", "Produtos/serviços verificados"),
            ("differentiators", "Diferenciais"),
            ("proof_points", "Provas e benefícios"),
            ("visual_motifs", "Motivos visuais"),
            ("mandatory_elements", "Elementos obrigatórios"),
            ("forbidden_elements", "Restrições da marca"),
            ("campaign_opportunities", "Oportunidades de campanha"),
        )
        for key, label in profile_labels:
            values = brand_profile.get(key)
            if isinstance(values, list) and values:
                lines.append(f"{label}: " + " | ".join(map(str, values[:8])))
        creative_line = brand_profile.get("creative_line") or {}
        if creative_line.get("signature_summary"):
            lines.append(
                "Assinatura aprendida de criativos reais: "
                + str(creative_line["signature_summary"])
            )
        for key, label in (
            ("composition_rules", "Regras de composição aprendidas"),
            ("imagery_rules", "Regras de imagem aprendidas"),
            ("typography_rules", "Regras tipográficas aprendidas"),
            ("graphic_devices", "Recursos gráficos recorrentes"),
            ("must_preserve", "Preservar da linha criativa"),
            ("avoid", "Evitar segundo a linha criativa"),
        ):
            values = creative_line.get(key)
            if isinstance(values, list) and values:
                lines.append(f"{label}: " + " | ".join(map(str, values[:8])))
        if creative_line.get("gpt_image_instruction"):
            lines.extend([
                "",
                "[INSTRUÇÃO APRENDIDA PARA GPT IMAGE 2]",
                str(creative_line["gpt_image_instruction"]),
            ])
        copy_lines = format_copy_system_lines(creative_line.get("copy_system"))
        if copy_lines:
            lines.extend(["", "[SISTEMA DE COPY APRENDIDO]", *copy_lines])

        lines.extend(
            [
                "",
                "[CAMPANHA]",
                f"Objetivo: {context.get('objective') or ''}",
                f"Mensagem principal: {scene}",
            ]
        )
        if context.get("cta_text"):
            lines.append(f"Chamada para ação: {context['cta_text']}")
        price_instruction = (
            "sim" if context.get("show_price") else "não — nenhum texto de preço"
        )
        lines.append(f"Exibir preço: {price_instruction}")
        lines.extend(
            [
                "",
                f"[FORMATO — {step['format_name']}]",
                f"Mecânica: {step.get('mechanic') or ''}",
            ]
        )
        if step.get("channel_name"):
            lines.append(f"Canal parceiro: {step['channel_name']}")
        if step.get("partner_primary_color"):
            lines.append(
                f"Cor de contexto do parceiro: {step['partner_primary_color']}"
            )
        if step.get("partner_secondary_color"):
            lines.append(
                f"Cor secundária do parceiro: {step['partner_secondary_color']}"
            )
        if step.get("background_guidance"):
            lines.append(f"Background/base: {step['background_guidance']}")
        if step.get("foreground_guidance"):
            lines.append(f"Foreground/conteúdo: {step['foreground_guidance']}")
        replacements = {
            "{{client_sector}}": client_sector or "the brand",
            "{{brand_primary_tone}}": "the brand primary tone",
            "{{brand_name}}": client_name,
            "{{scene_description}}": scene,
            "{{sponsor_label}}": f"Uma mensagem de {client_name}",
        }
        for layer in step.get("layers") or []:
            role = layer.get("role", "layer")
            description = layer.get("description_template", "")
            for source, target in replacements.items():
                description = description.replace(source, target)
            lines.append(f"- {role}: {description}")

        engine_label = (
            "GPT Image 2" if step["engine"] == "gpt_image_2" else "Higgsfield"
        )
        media_label = (
            "imagem estática" if step["media_type"] == "image" else "vídeo"
        )
        lines.extend(
            [
                "",
                "[ESPECIFICAÇÃO TÉCNICA]",
                f"Tipo de saída: {media_label}",
                f"Engine: {engine_label}",
                "Estilo: fotorrealista, qualidade de campanha premium.",
                "",
                "[RESTRIÇÕES]",
                "Não reproduzir logos ou identidade visual de terceiros/plataformas.",
            ]
        )
        for forbidden in step.get("forbidden_elements") or []:
            lines.append(f"Não incluir: {forbidden}.")
        if not context.get("show_price"):
            lines.append("Nenhum texto de preço.")

        lines.extend(
            [
                "",
                f"[VARIAÇÃO {context['label']} — STEP {step['position']}]",
                (
                    f"Este é o step {step['position']} de {total_steps} na "
                    f"sequência da variação {context['label']}."
                ),
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def generate_variation_prompts(self, variation_id, created_by=None):
        context = self.repository.get_variation_context(
            _integer(variation_id, "Variação")
        )
        steps = context.get("steps") or []
        if not steps:
            raise ValueError("Adicione ao menos um step antes de gerar prompts.")
        results = []
        for step in steps:
            generated = self.generate_step_prompt(step["id"], created_by)
            results.append(
                {
                    "step_id": step["id"],
                    "position": step["position"],
                    "prompt": generated["prompt"],
                    "job_id": generated["job_id"],
                }
            )
        return results

    @staticmethod
    def _estimate(kind, fidelity=None, image_model=None):
        if kind == "image":
            usd = (
                model_unit_usd(image_model, fidelity or DRAFT)
                if image_model else image_tier_estimate_usd(fidelity or DRAFT)
            )
            return _money(usd, "Custo estimado")
        defaults = {"prompt": "0.020000", "script": "0.030000"}
        env = f"CREATIVE_{kind.upper()}_ESTIMATED_COST_USD"
        return _money(os.getenv(env, defaults[kind]), "Custo estimado")

    def list_image_tiers(self):
        return _serialize(describe_image_tiers())

    def generate_step_prompt(self, step_id, created_by=None):
        step_id = _integer(step_id, "Step")
        context = self.repository.get_step_context(step_id)
        step = context["step"]
        request_context = {
            "campaign": {
                "name": context["campaign_name"],
                "objective": context.get("objective"),
                "message": step.get("scene_description")
                or context.get("campaign_text"),
                "cta": context.get("cta_text"),
                "show_price": context.get("show_price"),
                "variation": context["label"],
                "step": step["position"],
            },
            "client_identity": client_identity_payload(context),
            "partner_identity": {
                "name": step.get("channel_name"),
                "primary_color": step.get("partner_primary_color"),
                "secondary_color": step.get("partner_secondary_color"),
                "guidelines": step.get("brand_guidelines") or {},
            },
            "format": {
                key: step.get(key)
                for key in (
                    "format_name",
                    "mechanic",
                    "media_type",
                    "aspect_ratio",
                    "default_size",
                    "safe_area",
                    "responsive_rules",
                    "background_guidance",
                    "foreground_guidance",
                    "layers",
                    "forbidden_elements",
                )
            },
            "mockup": step["mockup"],
        }
        estimate = self._estimate("prompt")
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            step_id,
            step["format_template_id"],
            "prompt",
            "openrouter",
            DEFAULT_TEXT_MODEL,
            estimate,
            request_payload=request_context,
            created_by=created_by,
        )
        try:
            self.repository.mark_job_generating(job_id)
            generated = self.generator.generate_prompt(request_context)
            prompt = generated["result"]["prompt_en"].strip()
            self.repository.update_step_prompt(step_id, prompt, "generated")
            actual = generated.get("actual_cost_usd")
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else actual,
                {
                    "usage": generated.get("usage") or {},
                    "rationale_pt": generated["result"].get("rationale_pt"),
                    "checks": generated["result"].get("checks") or [],
                },
                "review",
            )
            return {
                "job_id": job_id,
                "prompt": prompt,
                "rationale": generated["result"].get("rationale_pt"),
                "checks": generated["result"].get("checks") or [],
            }
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            raise

    def review_step_prompt(self, step_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        prompt = _text(
            payload.get("prompt"), "Prompt", required=True, max_length=20000
        )
        approve = payload.get("approved") is True
        return self.repository.update_step_prompt(
            _integer(step_id, "Step"),
            prompt,
            "approved" if approve else "reviewed",
        )

    def generate_step_image(self, step_id, files, created_by=None):
        step_id = _integer(step_id, "Step")
        references = list(files or [])
        if len(references) > 2:
            raise ValueError("Use no máximo duas imagens de referência.")
        context = self.repository.get_step_context(step_id)
        step = context["step"]
        if step.get("prompt_status") != "approved":
            raise ValueError("Revise e aprove o prompt antes de gerar a imagem.")
        tier = resolve_image_tier(DRAFT)
        estimate = self._estimate("image", tier["name"])
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            step_id,
            step["format_template_id"],
            "image",
            "openrouter",
            DEFAULT_IMAGE_MODEL,
            estimate,
            prompt=step.get("rendered_prompt"),
            request_payload={
                "fidelity": tier["name"],
                "quality": tier["quality"],
                "resolution": tier["resolution"],
            },
            created_by=created_by,
        )
        saved_paths = []
        try:
            data_urls = []
            for file_storage in references:
                saved = self.storage.save_reference(file_storage)
                saved_paths.append(saved["asset_path"])
                self.repository.add_job_reference(job_id, saved)
                data_urls.append(
                    self.storage.reference_as_data_url(
                        saved["asset_path"], saved["mime_type"]
                    )
                )
            self._append_brand_references(
                context.get("client_id"), data_urls, job_id
            )
            self.repository.mark_job_generating(job_id)
            generated = self.generator.generate_image(
                step["rendered_prompt"],
                data_urls,
                aspect_ratio=step.get("aspect_ratio") or "16:9",
                quality=tier["quality"],
                resolution=tier["resolution"],
            )
            asset_url = self.storage.save_generated_base64(
                generated["b64_json"], generated.get("output_format", "png")
            )
            asset = self.repository.add_generated_asset(
                job_id,
                step_id,
                "image",
                asset_url,
                {
                    "model": generated.get("model"),
                    "fidelity": tier["name"],
                    "quality": tier["quality"],
                    "resolution": tier["resolution"],
                },
            )
            actual = generated.get("actual_cost_usd")
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else actual,
                {
                    "usage": generated.get("usage") or {},
                    **(generated.get("response_metadata") or {}),
                },
            )
            return {"job_id": job_id, "asset": asset}
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            for public_path in saved_paths:
                self.storage.delete(public_path)
            raise

    def generate_video_script(self, step_id, asset_ids, created_by=None):
        step_id = _integer(step_id, "Step")
        ids = [_integer(value, "Asset") for value in (asset_ids or [])]
        if len(ids) != 4 or len(set(ids)) != 4:
            raise ValueError("Selecione exatamente quatro imagens aprovadas.")
        assets = self.repository.get_assets(ids, approved_only=True)
        if len(assets) != 4:
            raise ValueError("As quatro imagens precisam estar aprovadas.")
        context = self.repository.get_step_context(step_id)
        if any(
            asset.get("campaign_id") not in (None, context["campaign_id"])
            for asset in assets
        ):
            raise ValueError("As imagens devem pertencer à mesma campanha.")
        step = context["step"]
        script_context = {
            "campaign": context["campaign_name"],
            "objective": context.get("objective"),
            "message": context.get("campaign_text"),
            "cta": context.get("cta_text"),
            "format": step["format_name"],
            "images": [
                {"position": index, "asset_url": asset["asset_url"]}
                for index, asset in enumerate(assets, start=1)
            ],
        }
        estimate = self._estimate("script")
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            step_id,
            step["format_template_id"],
            "script",
            "openrouter",
            DEFAULT_TEXT_MODEL,
            estimate,
            request_payload=script_context,
            created_by=created_by,
        )
        try:
            self.repository.mark_job_generating(job_id)
            generated = self.generator.generate_script(script_context)
            script_text = json.dumps(
                generated["result"], ensure_ascii=False, indent=2
            )
            self.repository.update_step_script(step_id, script_text, "generated")
            actual = generated.get("actual_cost_usd")
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else actual,
                {"usage": generated.get("usage") or {}},
                "review",
            )
            return {"job_id": job_id, "script": generated["result"]}
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            raise

    def review_step_script(self, step_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        script_text = _text(
            payload.get("script"), "Roteiro", required=True, max_length=30000
        )
        return self.repository.update_step_script(
            _integer(step_id, "Step"),
            script_text,
            "approved" if payload.get("approved") is True else "reviewed",
        )

    def prepare_higgsfield(self, step_id, asset_ids, created_by=None):
        from .services import integration_credentials

        step_id = _integer(step_id, "Step")
        ids = [_integer(value, "Asset") for value in (asset_ids or [])]
        if len(ids) != 4 or len(set(ids)) != 4:
            raise ValueError("Selecione exatamente quatro imagens aprovadas.")
        assets = self.repository.get_assets(ids, approved_only=True)
        if len(assets) != 4:
            raise ValueError("As quatro imagens precisam estar aprovadas.")
        context = self.repository.get_step_context(step_id)
        if any(
            asset.get("campaign_id") not in (None, context["campaign_id"])
            for asset in assets
        ):
            raise ValueError("As imagens devem pertencer à mesma campanha.")
        step = context["step"]
        if step.get("script_status") != "approved":
            raise ValueError("Revise e aprove o roteiro antes de preparar o vídeo.")
        provider_config = integration_credentials.get_configuration(
            "higgsfield", include_secrets=False
        )
        provider_model = (
            provider_config.get("default_model")
            or "higgsfield-pending-configuration"
        )
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            step_id,
            step["format_template_id"],
            "video_payload",
            "higgsfield",
            provider_model,
            Decimal("0"),
            script_text=step["script_text"],
            created_by=created_by,
        )
        payload = build_higgsfield_payload(
            job_id,
            step["script_text"],
            assets,
            step.get("aspect_ratio"),
            15,
        )
        payload["provider_configuration"] = {
            "configured": provider_config.get("configured", False),
            "source": provider_config.get("source"),
            "workspace_id": provider_config.get("workspace_id") or None,
            "default_model": provider_config.get("default_model") or None,
        }
        self.repository.link_video_assets(job_id, assets)
        self.repository.complete_generation_job(
            job_id, Decimal("0"), payload, "ready_for_higgsfield"
        )
        return {"job_id": job_id, "payload": payload}

    def prepare_display_motion(self, asset_id, created_by=None):
        from .services import integration_credentials

        asset_id = _integer(asset_id, "Asset")
        assets = self.repository.get_assets([asset_id], approved_only=True)
        if len(assets) != 1:
            raise ValueError("A imagem estática precisa estar aprovada.")
        asset = assets[0]
        if asset.get("asset_type") not in ("image", "mockup"):
            raise ValueError("A animação de display exige uma imagem estática.")
        if not asset.get("campaign_id") or not asset.get("format_template_id"):
            raise ValueError("O asset precisa estar vinculado a campanha e formato.")
        provider_config = integration_credentials.get_configuration(
            "higgsfield", include_secrets=False
        )
        job_id = self.repository.create_generation_job(
            asset["campaign_id"],
            asset.get("step_id"),
            asset["format_template_id"],
            "display_motion_payload",
            "higgsfield",
            provider_config.get("default_model")
            or "higgsfield-pending-configuration",
            Decimal("0"),
            prompt=(
                "Complemento animado de 3 segundos criado após aprovação "
                "do keyframe estático."
            ),
            created_by=created_by,
        )
        payload = build_display_motion_payload(
            job_id, asset, asset.get("aspect_ratio")
        )
        payload["provider_configuration"] = {
            "configured": provider_config.get("configured", False),
            "source": provider_config.get("source"),
            "workspace_id": provider_config.get("workspace_id") or None,
            "default_model": provider_config.get("default_model") or None,
        }
        self.repository.link_video_assets(job_id, assets)
        self.repository.complete_generation_job(
            job_id, Decimal("0"), payload, "ready_for_higgsfield"
        )
        return {"job_id": job_id, "payload": payload}

    @staticmethod
    def _resolve_render_mode(value, family):
        mode = str(value or "").strip().lower()
        if mode in {"native", "mockup"}:
            return mode
        return default_render_mode(family)

    @staticmethod
    def _compose_copy(context):
        locks = _brief_locks(context)
        items = locks.get("items") or {}
        omit_cta = (items.get("cta") or {}).get("status") == "absent"
        logo_status = (items.get("logo") or {}).get("status")
        require_logo = logo_status == "seen"
        return {
            "headline": locks["headline"] or context.get("campaign_name") or "",
            "cta": "" if omit_cta else (locks["cta"] or context.get("cta_text") or ""),
            "legal": (items.get("legal") or {}).get("text") or "",
            "omit_cta": omit_cta,
            "require_logo": require_logo,
            "brand_color": context.get("primary_color") or "#1E4D4F",
            "compose_params": (
                (context.get("creative_brief") or {}).get("compose_library") or {}
            ).get("params") or {},
            "html_key": (
                (context.get("creative_brief") or {}).get("compose_library") or {}
            ).get("html_key"),
        }

    @staticmethod
    def _refine_instruction(instruction, intent, family, locks=None):
        text = _text(instruction, "Instrução de ajuste", max_length=400) or ""
        if intent in {"ab_simple", "simple", "ab_max", "max", "maximum"}:
            return unfold_ab_instruction(intent, locks)
        if intent in {
            "chrome",
            "geometry",
            "ai_look",
            "logo",
            "remove_cta",
            "remove_lines",
            "brand",
        }:
            fixed = hygiene_instruction(intent, family)
            return f"{fixed} {text}".strip() if text else fixed
        if not text:
            raise ValueError("Instrução de ajuste é obrigatório.")
        return text

    def _logo_bytes(self, context):
        return self.resolve_brand_logo_bytes(context)

    def resolve_brand_logo_bytes(self, context):
        context = context if isinstance(context, dict) else {}
        reader = getattr(self.storage, "read_public_bytes", None)
        for key in ("logo_upload_path", "logo_url"):
            path = context.get(key)
            data = self._read_logo_path(path, reader)
            if data:
                return data
        client_id = context.get("client_id")
        if not client_id or not hasattr(self.repository, "list_client_brand_assets"):
            return None
        for asset in self.repository.list_client_brand_assets(client_id) or []:
            if asset.get("role") != "logo":
                continue
            data = self._read_logo_path(asset.get("asset_path"), reader)
            if data:
                return data
        return None

    def _read_logo_path(self, path, reader):
        if not path:
            return None
        if callable(reader):
            try:
                data = reader(path)
            except Exception:
                data = None
            if data:
                return data
        absolute_reader = getattr(self.storage, "absolute_public_path", None)
        if callable(absolute_reader):
            try:
                absolute = absolute_reader(path)
                if absolute is not None:
                    return absolute.read_bytes()
            except Exception:
                pass
        legacy = getattr(self.storage, "absolute_reference_path", None)
        if callable(legacy):
            try:
                absolute = legacy(path)
                if absolute is not None:
                    return absolute.read_bytes()
            except Exception:
                return None
        return None

    def _attach_previous_reference(self, context, data_urls, engine, family):
        previous = context.get("previous_approved_asset_url")
        position = int(context.get("position") or 1)
        required = position > 1 and (
            str(engine or "") == ENGINE_CONSTRUCT or family == "sequence_16x9"
        )
        if required and not previous:
            raise ValueError("A cena anterior aprovada é obrigatória neste caminho.")
        if not previous:
            return data_urls
        prev_data = self.storage.generated_as_data_url(previous)
        if prev_data in data_urls:
            return data_urls
        if required:
            if len(data_urls) < 2:
                data_urls.append(prev_data)
            else:
                data_urls[-1] = prev_data
            return data_urls
        if len(data_urls) < 2:
            data_urls.append(prev_data)
        return data_urls

    def _reinforce_empty_boxes(self, prompt, geometry, copy, locks):
        from .creative_modeling_prompts import construct_empty_boxes

        block = construct_empty_boxes(geometry, copy, locks)
        return f"{prompt}\n\nREINFORCED EMPTY BOXES\n{block}".strip()

    def _gate_safe_areas(self, raw_bytes, geometry):
        collage = crop_safe_area_collage(raw_bytes, geometry)
        data_url = "data:image/png;base64," + base64.b64encode(collage).decode("ascii")
        try:
            review = self.generator.review_image(
                {
                    "task": "safe_area_gate",
                    "question": "Há texto, wordmark ou lockup visível nestas caixas?",
                    "target_size": geometry.get("target_size"),
                    "iab_family": geometry.get("family"),
                },
                data_url,
            )
        except Exception as exc:
            return {
                "safe_area_clear": False,
                "text_or_lockup_visible": False,
                "review_error": str(exc)[:240],
                "cost": 0,
            }
        result = review.get("result") or {}
        visible = result.get("text_or_lockup_visible")
        if visible is None:
            visible = result.get("approved_recommendation") is False
        clear = result.get("safe_area_clear")
        if clear is None:
            clear = not bool(visible)
        return {
            "safe_area_clear": bool(clear) and not bool(visible),
            "text_or_lockup_visible": bool(visible),
            "notes": result.get("notes") or [],
            "cost": float(review.get("actual_cost_usd") or 0),
        }

    def _render_scene_image(
        self, prompt, data_urls, context, geometry, render_mode, path, image_model, tier
    ):
        engine = path.get("engine")
        attempts = 2 if engine == ENGINE_CONSTRUCT else 1
        generated = None
        extra_cost = 0
        gate = {"safe_area_clear": None, "needs_retry": False, "gate_cost": 0}
        current_prompt = prompt
        for attempt in range(attempts):
            generated = self.generator.generate_image(
                current_prompt,
                data_urls,
                aspect_ratio=context.get("aspect_ratio") or "16:9",
                quality=tier["quality"],
                resolution=tier["resolution"],
                model=image_model,
            )
            if attempt:
                extra_cost += float(generated.get("actual_cost_usd") or 0)
            if engine != ENGINE_CONSTRUCT:
                break
            raw = base64.b64decode(generated["b64_json"])
            gate = self._gate_safe_areas(raw, geometry)
            gate["gate_cost"] = float(gate.get("cost") or 0)
            if gate.get("safe_area_clear") or attempt == attempts - 1:
                break
            current_prompt = self._reinforce_empty_boxes(
                prompt, geometry, self._compose_copy(context), _brief_locks(context)
            )
        source_url = self.storage.save_generated_base64(
            generated["b64_json"], generated.get("output_format", "png")
        )
        raw = base64.b64decode(generated["b64_json"])
        allow_compose = engine != ENGINE_CONSTRUCT or gate.get("safe_area_clear") is not False
        if engine == ENGINE_CONSTRUCT:
            if gate.get("text_or_lockup_visible") and not gate.get("safe_area_clear"):
                allow_compose = False
            else:
                generated = dict(generated)
                generated["b64_json"] = base64.b64encode(
                    wipe_safe_areas(
                        raw, geometry, context.get("primary_color") or "#1E4D4F"
                    )
                ).decode("ascii")
                allow_compose = True
        if allow_compose:
            composed = self._compose_native_asset(
                source_url,
                generated["b64_json"],
                context,
                geometry,
                render_mode,
                engine=engine,
                html_compose=_flow_kind(context) != "unfold",
            )
        else:
            composed = {
                "asset_url": source_url,
                "source_raster": source_url,
                "composed": False,
                "logo_applied": False,
                "require_logo": self._compose_copy(context).get("require_logo"),
            }
        layers = {
            "safe_area_clear": gate.get("safe_area_clear"),
            "needs_retry": bool(
                engine == ENGINE_CONSTRUCT and not gate.get("safe_area_clear")
            ),
            "gate_cost": float(gate.get("gate_cost") or gate.get("cost") or 0),
            "image_cost": extra_cost,
        }
        return generated, composed, layers

    @staticmethod
    def _publishable_fidelity(requested, composed, layers, engine):
        if requested != PUBLISH:
            return requested
        if engine != ENGINE_CONSTRUCT:
            return requested
        require_logo = bool(composed.get("require_logo"))
        if require_logo and not composed.get("logo_applied"):
            return DRAFT
        if not composed.get("composed"):
            return DRAFT
        if layers.get("safe_area_clear") is not True:
            return DRAFT
        return PUBLISH

    def _resolve_compose_library(self, payload, format_data):
        payload = payload if isinstance(payload, dict) else {}
        if payload.get("flow_kind") == "unfold":
            return None
        geometry = resolve_format_geometry(
            format_data if isinstance(format_data, dict) else {}
        )
        family = geometry.get("family")
        if family not in LIBRARY_FAMILIES:
            return None
        variation = resolve_variation(
            payload.get("variation_id"),
            family,
            self.repository,
        )
        return normalize_compose_choice(variation, family)

    def _record_compose_feedback(self, scene_id, payload, status):
        payload = payload if isinstance(payload, dict) else {}
        getter = getattr(self.repository, "get_scene_context", None)
        if not callable(getter):
            return None
        try:
            context = getter(scene_id)
        except Exception:
            return None
        if not isinstance(context, dict) or _flow_kind(context) == "unfold":
            return None
        brief = context.get("creative_brief") or {}
        library = brief.get("compose_library") if isinstance(brief, dict) else {}
        variation_id = persisted_variation_id(
            (library or {}).get("variation_id") or payload.get("variation_id")
        )
        recorder = getattr(self.repository, "record_compose_feedback", None)
        if not variation_id or not callable(recorder):
            return None
        try:
            updated = recorder(
                variation_id,
                context.get("campaign_id"),
                payload.get("asset_id"),
                status,
            )
        except Exception:
            return None
        if status != "rejected" or not isinstance(updated, dict):
            return updated
        creator = getattr(self.repository, "create_compose_variation", None)
        template_id = (library or {}).get("template_id") or updated.get("template_id")
        if not callable(creator) or not template_id:
            return updated
        family = (library or {}).get("family")
        try:
            creator(
                template_id,
                "Ajuste automático",
                propose_variation_adjust(
                    schema_for_family(family) or (library or {}).get("params"),
                    (library or {}).get("params") or updated.get("params"),
                ),
                "experimental",
            )
        except Exception:
            return updated
        return updated

    def _compose_native_asset(
        self,
        source_url,
        encoded,
        context,
        geometry,
        render_mode,
        engine=None,
        source_bytes=None,
        html_compose=False,
    ):
        copy = self._compose_copy(context)
        empty = {
            "asset_url": source_url,
            "source_raster": None,
            "composed": False,
            "logo_applied": False,
            "require_logo": copy.get("require_logo"),
            "font": None,
        }
        design = (context.get("creative_brief") or {}).get("context_design")
        copy_on_frame = None
        if design and geometry.get("family") == "sequence_16x9":
            copy_on_frame = scene_copy_on_frame(
                design,
                context.get("position"),
                context.get("scene_count"),
            )
        if not should_compose(
            geometry.get("family"),
            render_mode,
            context.get("position") or 1,
            context.get("scene_count") or 1,
            engine=engine,
            copy_on_frame=copy_on_frame,
        ):
            return empty
        try:
            raw = source_bytes if source_bytes is not None else base64.b64decode(encoded)
            logo = self.resolve_brand_logo_bytes(context)
            if html_compose:
                result = compose_studio_result(
                    raw,
                    geometry,
                    copy,
                    logo,
                    flow_kind=_flow_kind(context),
                )
            else:
                result = compose_native_result(raw, geometry, copy, logo)
        except Exception:
            return empty
        composed_url = self.storage.save_generated_base64(
            base64.b64encode(result["png"]).decode("ascii"),
            "png",
        )
        return {
            "asset_url": composed_url,
            "source_raster": source_url,
            "composed": True,
            "logo_applied": bool(result.get("logo_applied")),
            "require_logo": copy.get("require_logo"),
            "font": result.get("font"),
            "renderer": result.get("renderer") or "pillow",
        }

    def _derive_format_from_master(self, scene_id, master, created_by=None, path=None):
        scene_id = _integer(scene_id, "Cena")
        context = self.repository.get_scene_context(scene_id)
        geometry = resolve_format_geometry(context)
        render_mode = self._resolve_render_mode("native", geometry["family"])
        path = path or _brief_path(context)
        master_asset = master.get("asset") or {}
        meta = master_asset.get("metadata") or {}
        source_url = meta.get("source_raster") or master_asset.get("asset_url")
        raw = self._read_logo_path(
            source_url, getattr(self.storage, "read_public_bytes", None)
        )
        if not raw:
            raise ValueError("A cena mestre não tem still para desdobrar.")
        estimate = Decimal("0")
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            None,
            context["format_template_id"],
            "image",
            "openrouter",
            path.get("image_model") or DEFAULT_IMAGE_MODEL,
            estimate,
            prompt="compose from master scene",
            request_payload={
                "production_id": context["production_id"],
                "scene_id": scene_id,
                "source_scene_id": master.get("scene_id"),
                "source_asset_id": master_asset.get("id"),
                "engine": path.get("engine"),
                "fidelity": path.get("fidelity"),
            },
            created_by=created_by,
            scene_id=scene_id,
            reserve_scene=True,
            allow_existing_scene=True,
        )
        try:
            self.repository.mark_job_generating(job_id)
            wiped = wipe_safe_areas(
                raw, geometry, context.get("primary_color") or "#1E4D4F"
            )
            source_saved = self.storage.save_generated_base64(
                base64.b64encode(wiped).decode("ascii"),
                "png",
            )
            composed = self._compose_native_asset(
                source_saved,
                base64.b64encode(wiped).decode("ascii"),
                context,
                geometry,
                render_mode,
                engine=path.get("engine"),
                source_bytes=wiped,
            )
            layers = {"safe_area_clear": True, "needs_retry": False}
            fidelity = self._publishable_fidelity(
                path.get("fidelity") or PUBLISH,
                composed,
                layers,
                path.get("engine"),
            )
            asset = self.repository.add_generated_asset(
                job_id,
                None,
                "image",
                composed["asset_url"],
                {
                    "production_id": context["production_id"],
                    "scene_position": context.get("position"),
                    "render_mode": render_mode,
                    "iab_family": geometry["family"],
                    "target_size": geometry.get("target_size"),
                    "source_raster": composed.get("source_raster"),
                    "source_scene_id": master.get("scene_id"),
                    "source_asset_id": master_asset.get("id"),
                    "engine": path.get("engine"),
                    "fidelity": fidelity,
                    "composed": composed.get("composed"),
                    "logo_applied": composed.get("logo_applied"),
                    "require_logo": composed.get("require_logo"),
                    "safe_area_clear": True,
                    "font": composed.get("font"),
                    "derived_from_master": True,
                    "derived_from_kv": master.get("scene_id") is None,
                },
                scene_id=scene_id,
            )
            self.repository.complete_generation_job(
                job_id,
                estimate,
                {
                    "source_scene_id": master.get("scene_id"),
                    "source_asset_id": master_asset.get("id"),
                    "safe_area_clear": True,
                },
            )
            return _serialize({
                "job_id": job_id,
                "asset": asset,
                "prompt": "compose from master scene",
            })
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            raise

    @staticmethod
    def build_format_mockup_prompt(
        format_data,
        client=None,
        reference_type="full_mockup",
        presentation_mode="single",
        campaign_content=None,
        has_references=False,
        has_brand_references=False,
    ):
        return compose_format_mockup_prompt(
            format_data,
            client,
            reference_type,
            presentation_mode,
            campaign_content,
            has_references,
            has_brand_references,
        )

    def list_format_modeling_jobs(self, format_id):
        format_id = _integer(format_id, "Formato")
        self.repository.get_format(format_id)
        return _serialize(self.repository.list_format_modeling_jobs(format_id))

    def _run_format_modeling(
        self,
        format_data,
        client,
        slot,
        reference_type,
        prompt,
        data_urls,
        saved_paths,
        created_by,
        parent_job_id=None,
        refinement_instruction=None,
    ):
        tier = resolve_image_tier(DRAFT)
        estimate = self._estimate("image", tier["name"])
        job_id = self.repository.create_format_modeling_job(
            format_data["id"],
            client.get("id") if client else None,
            parent_job_id,
            slot,
            reference_type,
            DEFAULT_IMAGE_MODEL,
            prompt,
            saved_paths,
            estimate,
            refinement_instruction,
            created_by,
        )
        generated_path = None
        try:
            self.repository.mark_format_modeling_job_generating(job_id)
            generated = self.generator.generate_image(
                prompt,
                data_urls,
                aspect_ratio=format_data.get("aspect_ratio") or "16:9",
                quality=tier["quality"],
                resolution=tier["resolution"],
            )
            generated_path = self.storage.save_generated_base64(
                generated["b64_json"], generated.get("output_format", "png")
            )
            actual = generated.get("actual_cost_usd")
            job = self.repository.complete_format_modeling_job(
                job_id,
                generated_path,
                estimate if actual is None else actual,
                {
                    "model": generated.get("model"),
                    "usage": generated.get("usage") or {},
                    **(generated.get("response_metadata") or {}),
                },
            )
            return _serialize(job)
        except Exception as exc:
            self.repository.fail_format_modeling_job(job_id, exc)
            if generated_path:
                self.storage.delete(generated_path)
            raise

    def generate_format_mockup(self, format_id, payload, files, created_by=None):
        payload = payload if isinstance(payload, dict) else {}
        format_data = self.repository.get_format(_integer(format_id, "Formato"))
        slot = _integer(payload.get("slot", 1), "Slot")
        if slot > 4:
            raise ValueError("O slot deve estar entre 1 e 4.")
        reference_type = payload.get("reference_type", "full_mockup")
        if reference_type not in ("background", "full_mockup"):
            raise ValueError("Tipo de referência inválido.")
        client = None
        if payload.get("client_id") not in (None, ""):
            client = self.repository.get_client(
                _integer(payload.get("client_id"), "Cliente")
            )
        references = list(files or [])
        if len(references) > 2:
            raise ValueError("Use no máximo duas imagens de referência.")
        saved_paths = []
        data_urls = []
        try:
            for file_storage in references:
                saved = self.storage.save_reference(file_storage)
                saved_paths.append(saved["asset_path"])
                data_urls.append(
                    self.storage.reference_as_data_url(
                        saved["asset_path"], saved["mime_type"]
                    )
                )
            presentation_mode = payload.get("presentation_mode", "single")
            if presentation_mode not in (
                "single", "four_horizontal", "multi_format_board"
            ):
                raise ValueError("Modo de apresentação inválido.")
            behavior = format_data.get("behavior_spec") or {}
            requires_variations = (
                format_data.get("media_type") == "video"
                or behavior.get("type") not in (None, "", "static")
            )
            if (
                reference_type == "full_mockup"
                and presentation_mode == "single"
                and requires_variations
            ):
                presentation_mode = "four_horizontal"
            structural_references = bool(data_urls)
            brand_references = []
            if client and reference_type == "full_mockup":
                brand_references = self._append_brand_references(
                    client.get("id"), data_urls
                )
            instructions = _text(
                payload.get("instructions"),
                "Direção adicional",
                max_length=4000,
            )
            prompt = self.build_format_mockup_prompt(
                format_data,
                client,
                reference_type,
                presentation_mode,
                instructions,
                structural_references,
                bool(brand_references),
            )
            return self._run_format_modeling(
                format_data,
                client,
                slot,
                reference_type,
                prompt,
                data_urls,
                saved_paths,
                created_by,
            )
        except Exception:
            for public_path in saved_paths:
                self.storage.delete(public_path)
            raise

    def refine_format_mockup(self, job_id, payload, files, created_by=None):
        payload = payload if isinstance(payload, dict) else {}
        parent = self.repository.get_format_modeling_job(
            _integer(job_id, "Job de modelagem")
        )
        if parent.get("status") not in ("review", "approved"):
            raise ValueError("Apenas mockups concluídos podem ser refinados.")
        instruction = _text(
            payload.get("instruction"),
            "Instrução de refinamento",
            required=True,
            max_length=4000,
        )
        extras = list(files or [])
        if len(extras) > 1:
            raise ValueError(
                "O refinamento aceita uma referência adicional além do mockup atual."
            )
        format_data = self.repository.get_format(parent["format_template_id"])
        client = (
            self.repository.get_client(parent["client_id"])
            if parent.get("client_id")
            else None
        )
        data_urls = [self.storage.generated_as_data_url(parent["asset_url"])]
        saved_paths = []
        try:
            for file_storage in extras:
                saved = self.storage.save_reference(file_storage)
                saved_paths.append(saved["asset_path"])
                data_urls.append(
                    self.storage.reference_as_data_url(
                        saved["asset_path"], saved["mime_type"]
                    )
                )
            prompt = (
                f"{parent['prompt']}\n\nRefinement instruction: {instruction}\n"
                "Preserve the placement geometry, format and brand identity. "
                "Change only what the refinement instruction requests."
            )
            return self._run_format_modeling(
                format_data,
                client,
                parent["slot"],
                parent["reference_type"],
                prompt,
                data_urls,
                saved_paths,
                created_by,
                parent_job_id=parent["id"],
                refinement_instruction=instruction,
            )
        except Exception:
            for public_path in saved_paths:
                self.storage.delete(public_path)
            raise

    def approve_format_mockup(self, job_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        slot = _integer(payload.get("slot"), "Slot")
        if slot > 4:
            raise ValueError("O slot deve estar entre 1 e 4.")
        return _serialize(
            self.repository.approve_format_modeling_job(
                _integer(job_id, "Job de modelagem"), slot
            )
        )

    def archive_format_mockup(self, job_id):
        archived = self.repository.archive_format_modeling_job(
            _integer(job_id, "Job de modelagem")
        )
        self.storage.delete(archived.get("asset_url"))
        for public_path in archived.get("input_references") or []:
            self.storage.delete(public_path)

    def history(self, campaign_id=None, flow_kind=None):
        campaign = (
            _integer(campaign_id, "Campanha") if campaign_id not in (None, "") else None
        )
        jobs = [
            annotate_cost(job)
            for job in self.repository.list_generation_jobs(campaign)
        ]
        catalog = self.list_campaigns(flow_kind)
        modelings = [
            annotate_cost(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "client": item.get("client"),
                    "spent_usd": item.get("spent_usd") or item.get("cost_usd"),
                    "flow_kind": item.get("flow_kind"),
                },
                item.get("spent_usd") or item.get("cost_usd"),
            )
            for item in catalog
        ]
        if flow_kind and campaign is None:
            allowed = {int(item.get("id") or 0) for item in modelings}
            jobs = [
                job for job in jobs
                if int(job.get("campaign_id") or 0) in allowed
            ]
        if campaign is not None:
            modelings = [
                item for item in modelings if int(item.get("id") or 0) == campaign
            ]
            if not modelings:
                detail = self.repository.get_campaign(campaign)
                client = detail.get("client")
                client_name = (
                    detail.get("client_name")
                    or (client.get("name") if isinstance(client, dict) else client)
                )
                modelings = [
                    annotate_cost(
                        {
                            "id": detail.get("id"),
                            "name": detail.get("name"),
                            "client": client_name,
                            "spent_usd": detail.get("spent_usd"),
                        },
                        detail.get("spent_usd"),
                    )
                ]
        total_usd = sum(float(item.get("cost_usd") or 0) for item in modelings)
        lab_history = []
        for item in modelings:
            try:
                campaign = self.repository.get_campaign(item.get("id"))
            except Exception:
                continue
            brief = campaign.get("creative_brief") if isinstance(campaign, dict) else {}
            lab = (brief or {}).get("format_lab") if isinstance(brief, dict) else {}
            for row in (lab or {}).get("history") or []:
                if isinstance(row, dict):
                    lab_history.append({**row, "campaign_id": item.get("id")})
        return _serialize({
            "jobs": jobs,
            "modelings": modelings,
            "lab": lab_history,
            "total_usd": round(total_usd, 6),
            "total_brl": brl_from_usd(total_usd),
        })

    def review_asset(self, asset_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        status = payload.get("status")
        if status not in ("approved", "rejected"):
            raise ValueError("Status do asset deve ser approved ou rejected.")
        asset_id = _integer(asset_id, "Asset")
        assets = self.repository.get_assets([asset_id], approved_only=False)
        if not assets:
            raise CreativeNotFoundError("Asset não encontrado.")
        if assets[0].get("scene_id"):
            return self.repository.review_scene_asset(
                assets[0]["scene_id"], asset_id, status
            )
        return self.repository.set_asset_status(
            asset_id, status
        )

    def promote_format_reference(self, asset_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        slot = _integer(payload.get("slot"), "Slot")
        if slot > 4:
            raise ValueError("O slot deve estar entre 1 e 4.")
        reference_type = payload.get("reference_type", "full_mockup")
        if reference_type not in ("background", "full_mockup"):
            raise ValueError("Tipo de referência inválido.")
        assets = self.repository.get_assets(
            [_integer(asset_id, "Asset")], approved_only=True
        )
        if not assets:
            raise ValueError("Apenas assets aprovados podem virar referência.")
        asset = assets[0]
        format_id = _integer(
            payload.get("format_template_id"), "Formato"
        )
        prompt = _text(payload.get("prompt"), "Prompt", max_length=20000)
        return self.repository.upsert_format_reference(
            format_id,
            slot,
            reference_type,
            prompt,
            asset["asset_url"],
            asset["job_id"],
        )

    def campaign_assets(self, campaign_id):
        return _serialize(
            self.repository.list_campaign_assets(
                _integer(campaign_id, "Campanha")
            )
        )

    def reorder_campaign_assets(self, campaign_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        raw_ids = payload.get("asset_ids")
        if not isinstance(raw_ids, list):
            raise ValueError("asset_ids deve ser uma lista.")
        asset_ids = [_integer(value, "Asset") for value in raw_ids]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("A lista de assets contém itens duplicados.")
        self.repository.reorder_campaign_assets(
            _integer(campaign_id, "Campanha"), asset_ids
        )
        return {"asset_ids": asset_ids}

    def update_campaign_asset(self, campaign_id, asset_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        return self.repository.update_campaign_asset(
            _integer(campaign_id, "Campanha"),
            _integer(asset_id, "Asset"),
            _text(payload.get("title"), "Título", max_length=200),
            _text(payload.get("caption"), "Descrição", max_length=4000),
        )

    def delete_campaign_asset(self, campaign_id, asset_id):
        path = self.repository.delete_campaign_asset(
            _integer(campaign_id, "Campanha"),
            _integer(asset_id, "Asset"),
        )
        self.storage.delete(path)

    def create_public_collection(self, campaign_id, payload, created_by=None):
        payload = payload if isinstance(payload, dict) else {}
        campaign_id = _integer(campaign_id, "Campanha")
        assets = self.repository.list_campaign_assets(campaign_id)
        requested = payload.get("asset_ids")
        if requested is None:
            asset_ids = [asset["id"] for asset in assets]
        elif isinstance(requested, list):
            asset_ids = [_integer(value, "Asset") for value in requested]
        else:
            raise ValueError("asset_ids deve ser uma lista.")
        if not asset_ids:
            raise ValueError("Adicione ao menos um criativo antes de compartilhar.")
        available = {asset["id"]: asset for asset in assets}
        unknown = [asset_id for asset_id in asset_ids if asset_id not in available]
        if unknown:
            raise ValueError("Um ou mais assets não pertencem à campanha.")
        requested_asset_ids = set(asset_ids)
        representatives = {}
        representative_by_asset = {}
        for asset_id in asset_ids:
            asset = available[asset_id]
            if asset.get("status") not in (None, "approved"):
                continue
            key = (
                ("production", asset["production_id"])
                if asset.get("production_id")
                else ("asset", asset_id)
            )
            representative_id = representatives.setdefault(key, asset_id)
            representative_by_asset[asset_id] = representative_id
        asset_ids = list(representatives.values())
        if not asset_ids:
            raise ValueError("Aprove ao menos uma imagem antes de compartilhar.")
        requested_profiles = payload.get("viewer_profiles") or {}
        if not isinstance(requested_profiles, dict):
            raise ValueError("viewer_profiles deve ser um objeto.")
        viewer_profiles = {}
        for raw_asset_id, raw_profile_id in requested_profiles.items():
            asset_id = _integer(raw_asset_id, "Asset")
            if asset_id not in requested_asset_ids or asset_id not in available:
                raise ValueError("Ambiente informado para um asset inválido.")
            if asset_id not in representative_by_asset:
                continue
            if raw_profile_id in (None, "", "auto"):
                continue
            profile_id = _integer(raw_profile_id, "Ambiente de mídia")
            profile = _viewer_profile_data(
                self.repository.get_viewer_profile(profile_id)
            )
            placement = available[asset_id].get("placement_spec") or {}
            expected_kind = "tv" if placement.get("context") == "tv" else "portal"
            if profile["viewer_kind"] != expected_kind:
                raise ValueError(
                    "O ambiente escolhido não corresponde ao formato do criativo."
                )
            viewer_profiles[representative_by_asset[asset_id]] = profile_id
        title = _text(
            payload.get("title"),
            "Título da apresentação",
            required=True,
            max_length=200,
        )
        description = _text(
            payload.get("description"), "Descrição", max_length=4000
        )
        token = secrets.token_urlsafe(32)
        collection = self.repository.create_public_collection(
            campaign_id,
            token,
            title,
            description,
            asset_ids,
            viewer_profiles,
            created_by,
        )
        return {
            **collection,
            "public_url": f"/criativos/publico/{token}",
            "asset_count": len(asset_ids),
        }

    def list_public_collections(self, campaign_id):
        rows = self.repository.list_public_collections(
            _integer(campaign_id, "Campanha")
        )
        for row in rows:
            row["public_url"] = f"/criativos/publico/{row['token']}"
        return _serialize(rows)

    def revoke_public_collection(self, campaign_id, collection_id):
        self.repository.revoke_public_collection(
            _integer(campaign_id, "Campanha"),
            _integer(collection_id, "Apresentação"),
        )

    def public_collection(self, token):
        token = _text(token, "Token", required=True, max_length=100)
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,100}", token):
            raise CreativeNotFoundError("Apresentação não encontrada ou revogada.")
        collection = self.repository.get_public_collection(token)
        deduplicated_assets = []
        seen_sequences = set()
        for asset in collection.get("assets") or []:
            frames = asset.get("carousel_assets") or []
            sequence_key = (
                tuple(frame.get("id") for frame in frames)
                if len(frames) > 1
                else ("asset", asset.get("id"))
            )
            if sequence_key in seen_sequences:
                continue
            seen_sequences.add(sequence_key)
            deduplicated_assets.append(asset)
        collection["assets"] = deduplicated_assets
        for asset in deduplicated_assets:
            try:
                behavior = _behavior_spec(asset.get("behavior_spec") or {})
            except ValueError:
                behavior = {
                    "type": "static",
                    "trigger": "none",
                    "transition_ms": 0,
                }
            if len(asset.get("carousel_assets") or []) > 1 and (
                behavior["type"] == "static"
            ):
                behavior = {
                    "type": "carousel",
                    "trigger": "auto",
                    "transition_ms": 420,
                }
            asset["behavior_spec"] = behavior
            geometry = resolve_format_geometry({
                "slug": asset.get("format_slug"),
                "default_size": asset.get("default_size"),
            })
            placement = (
                asset.get("placement_spec")
                if isinstance(asset.get("placement_spec"), dict)
                else {}
            )
            zone = placement.get("placement_zone")
            if zone not in PLACEMENT_ZONES:
                zone = placement_zone_for(
                    family=geometry.get("family"),
                    size=geometry.get("size"),
                    slug=asset.get("format_slug"),
                    context=placement.get("context"),
                )
            asset["placement_zone"] = zone
            asset["iab_family"] = geometry.get("family")
            size = geometry.get("size")
            if size:
                asset["iab_width"], asset["iab_height"] = size
            elif zone:
                asset["iab_width"], asset["iab_height"] = (300, 250)
            if not asset.get("viewer_profile_id"):
                continue
            profile = _viewer_profile_data(
                {
                    "id": asset.get("viewer_profile_id"),
                    "slug": asset.get("viewer_slug"),
                    "name": asset.get("viewer_name"),
                    "viewer_kind": asset.get("viewer_kind"),
                    "logo_asset_ref": asset.get("viewer_logo_asset_ref"),
                    "palette": asset.get("viewer_palette"),
                    "shell_spec": asset.get("viewer_shell_spec"),
                    "disclaimer": asset.get("viewer_disclaimer"),
                }
            )
            asset.update({
                "viewer_slug": profile["slug"],
                "viewer_name": profile.get("name") or asset.get("viewer_name"),
                "viewer_kind": profile["viewer_kind"],
                "viewer_logo_asset_ref": profile["logo_asset_ref"],
                "viewer_palette": profile["palette"],
                "viewer_shell_spec": profile["shell_spec"],
                "viewer_disclaimer": profile["disclaimer"],
            })
        collection["sessions"] = _collection_sessions(deduplicated_assets)
        collection["token"] = token
        nav_rows = []
        if collection.get("client_id") and hasattr(
            self.repository, "list_client_public_nav"
        ):
            nav_rows = self.repository.list_client_public_nav(
                collection["client_id"]
            )
        collection["catalog"] = _public_catalog(collection, nav_rows, token)
        return _serialize(collection)

    def public_collection_asset(self, token, asset_id):
        token = _text(token, "Token", required=True, max_length=100)
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,100}", token):
            raise CreativeNotFoundError(
                "Mídia não encontrada ou apresentação revogada."
            )
        return self.repository.get_public_collection_asset(
            token, _integer(asset_id, "Asset")
        )
