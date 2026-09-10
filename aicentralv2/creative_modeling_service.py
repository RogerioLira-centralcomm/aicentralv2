"""Regras de negócio e composição de prompts da Modelagem de Criativos."""

from datetime import date, datetime
from decimal import Decimal
import base64
import json
import os
import re
import secrets

from .creative_brand_analysis import (
    CreativeBrandAnalyzer,
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
    scene_count_for_format,
)
from .creative_format_compose import compose_native_piece
from .creative_modeling_fx import annotate_cost, brl_from_usd
from .creative_format_geometry import (
    canvas_mismatch,
    default_render_mode,
    format_beat,
    format_direction,
    hygiene_instruction,
    resolve_format_geometry,
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
from .creative_modeling_prompts import (
    apply_render_mode_to_prompt,
    compose_format_mockup_prompt,
    normalize_locks,
    unfold_ab_instruction,
    unfold_image_lock,
)


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

PLACEMENT_CONTEXTS = {"portal", "tv", "celular", "tablet"}
PLACEMENT_FITS = {"contain", "cover", "fill"}
RESPONSIVE_MODES = {"scale", "reflow", "fixed"}
BEHAVIOR_TYPES = {
    "static", "hotspot", "flip", "reveal", "compare", "quiz", "carousel", "video"
}
BEHAVIOR_TRIGGERS = {
    "none", "hover_tap", "click", "drag_vertical", "drag_horizontal",
    "view", "auto",
}
VIEWER_KINDS = {"portal", "tv"}
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
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


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
    return {
        "context": context,
        "viewport": {"width": width, "height": height},
        "slot": normalized_slot,
        "fit": fit,
        "responsive": responsive,
    }


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


class CreativeModelingService:
    def __init__(
        self, repository=None, generator=None, storage=None, brand_analyzer=None
    ):
        self.repository = repository or CreativeModelingRepository()
        self.generator = generator or CreativeGenerationClient()
        self.storage = storage or CreativeAssetStorage()
        self.brand_analyzer = brand_analyzer or CreativeBrandAnalyzer()

    def _append_brand_references(self, client_id, data_urls, job_id=None):
        if (
            not client_id
            or len(data_urls) >= 2
            or not hasattr(self.repository, "list_client_brand_assets")
        ):
            return []
        used = []
        assets = self.repository.list_client_brand_assets(client_id)
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
        return _serialize(formats)

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
        viewer_profile_id = payload.get(
            "default_viewer_profile_id", current.get("default_viewer_profile_id")
        )
        if viewer_profile_id not in (None, ""):
            viewer_profile_id = _integer(viewer_profile_id, "Ambiente de mídia")
            profile = _viewer_profile_data(
                self.repository.get_viewer_profile(viewer_profile_id)
            )
            expected_kind = "tv" if placement_spec["context"] == "tv" else "portal"
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
        clients = self.repository.list_clients()
        if hasattr(self.repository, "list_client_brand_assets"):
            for client in clients:
                client["brand_assets"] = self.repository.list_client_brand_assets(
                    client["id"]
                )
        return _serialize(clients)

    def list_campaign_clients(self):
        clients = self.repository.list_campaign_clients()
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
        client = self.repository.get_client(client_id)
        if hasattr(self.repository, "list_client_brand_assets"):
            client["brand_assets"] = self.repository.list_client_brand_assets(client_id)
        return _serialize(client)

    def create_client(self, payload):
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
        }
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
            "crm_client_id": (
                HOUSE_CRM_CLIENT_ID
                if payload.get("crm_client_id") in (None, "")
                else _integer(payload.get("crm_client_id"), "Cliente CentralComm")
            ),
        }
        client_id = self.repository.create_client(data)
        saved_assets = []
        for candidate in (payload.get("brand_assets") or [])[:9]:
            if not isinstance(candidate, dict):
                continue
            role = candidate.get("role")
            if role not in {"logo", "reference"}:
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
        return {"id": client_id, "brand_assets": saved_assets}

    def analyze_brand(self, website_url=None, image=None):
        return _serialize(self.brand_analyzer.analyze(website_url, image))

    def upload_client_brand_assets(
        self, client_id, files, primary_logo=False, role="reference"
    ):
        client_id = _integer(client_id, "Cliente")
        self.repository.get_client(client_id)
        if role not in {"reference", "creative"}:
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

    def learn_client_creative_line(self, client_id, files):
        client_id = _integer(client_id, "Cliente")
        client = self.repository.get_client(client_id)
        new_assets = []
        if files:
            new_assets = self.upload_client_brand_assets(
                client_id, files, role="creative"
            )
        assets = [
            asset
            for asset in self.repository.list_client_brand_assets(client_id)
            if asset.get("role") == "creative" and asset.get("asset_path")
        ]
        data_urls = []
        for asset in assets[:6]:
            try:
                data_urls.append(
                    self.storage.reference_as_data_url(
                        asset["asset_path"], asset.get("mime_type")
                    )
                )
            except ValueError:
                continue
        creative_line = self.brand_analyzer.analyze_creative_line(
            data_urls, client
        )
        profile = dict(client.get("brand_profile") or {})
        profile["creative_line"] = creative_line
        self.repository.update_client_brand_profile(client_id, profile)
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
        if scene_count not in (1, 4):
            raise ValueError("A quantidade de cenas deve ser 1 ou 4.")
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
                "message": _text(
                    payload.get("campaign_text"),
                    "Mensagem principal",
                    required=True,
                    max_length=12000,
                ),
                "cta": _text(payload.get("cta_text"), "CTA", max_length=1000),
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
                }),
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
        direction = format_direction(format_row or {})
        beats = direction.get("beats") or []
        if beats and len(beats) == int(scene_count or 0):
            return [
                f"{beat['label']}: {beat['job']} Mensagem: {message}."
                for beat in beats
            ]
        if scene_count == 1:
            return [f"Composição final: {message}. Encerrar com reconhecimento de marca."]
        return [
            f"Gancho: apresentar uma situação visual que gere atenção para {message}.",
            f"Contexto e produto: revelar a marca e conectar o produto a {message}.",
            f"Benefício: tornar visualmente concreto o valor central de {message}.",
            f"Fechamento: resolver a narrativa e reforçar a marca.",
        ]

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
            if not isinstance(descriptions, list) or len(descriptions) > 4:
                raise ValueError(
                    f"Cenas da produção {index} devem ser uma lista de até 4 itens."
                )
            format_data = self.repository.get_format(format_id)
            expected_scene_count = scene_count_for_format(format_data)
            if not descriptions:
                descriptions = self.fallback_scene_descriptions(
                    payload.get("campaign_text"),
                    expected_scene_count,
                    format_data,
                )
            if len(descriptions) != expected_scene_count:
                raise ValueError(
                    f"O formato exige exatamente {expected_scene_count} cena(s)."
                )
            productions.append(
                {
                    "format_template_id": format_id,
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
        created = self.repository.create_campaign_with_productions(data)
        return _serialize(
            {
                "campaign": self.repository.get_campaign(created["id"]),
                "productions": [
                    self.repository.get_production(item["id"])
                    for item in created["productions"]
                ],
            }
        )

    def production_detail(self, production_id):
        return _serialize(
            self.repository.get_production(_integer(production_id, "Produção"))
        )

    @staticmethod
    def scene_role(position, total, format_row=None):
        beat = format_beat(format_row or {}, position)
        if beat:
            return beat["job"]
        if int(total or 1) == 1:
            return "Single final composition: the whole ad in this rectangle."
        roles = {
            1: "Opening beat: establish the campaign world and earn attention.",
            2: "Context beat: the product enters this format. Not a recrop of scene 1.",
            3: "Benefit beat: make the main value tangible without inventing claims.",
            4: "Closing beat: resolve the same ad. Show a CTA only if the format has one.",
        }
        return roles.get(int(position or 1), roles[1])

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
        if creative_brief.get("visual_bible"):
            lines.append(
                "Shared visual bible for every scene: "
                f"{creative_brief['visual_bible']}."
            )
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
        position = context["position"]
        flow_kind = _flow_kind(context)
        locks = _brief_locks(context)
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
            "locks": locks,
            "kv_notes": ((context.get("creative_brief") or {}).get("kv_notes") or {}),
            "inherit_from_master": False,
            "master_prompt": None,
            "sequence_bible": (
                (context.get("creative_brief") or {}).get("visual_bible")
            ),
            "client_identity": {
                "name": context["client_name"],
                "sector": context.get("client_sector"),
                "tone": context.get("tone_of_voice"),
                "logo": context.get("logo_upload_path") or context.get("logo_url"),
                "primary_color": context.get("primary_color"),
                "secondary_color": context.get("secondary_color"),
                "profile": context.get("brand_profile") or {},
            },
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
            )
            if flow_kind == "unfold" and "LOCK BLOCK FOR GPT IMAGE 2" not in prompt:
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
        tier = resolve_image_tier(fidelity)
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
        )
        if flow_kind == "unfold" and "LOCK BLOCK FOR GPT IMAGE 2" not in prompt:
            prompt = f"{prompt}\n\n{unfold_image_lock(locks)}"
        variant_level = "source"
        if tier["name"] == PUBLISH:
            prompt = apply_publish_upgrade(prompt)
            variant_level = "publish"
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
                "render_mode": render_mode,
                "iab_family": geometry["family"],
                "target_size": geometry.get("target_size"),
                "iab_cousin": geometry.get("iab_cousin"),
                "flow_kind": flow_kind,
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
            previous_asset_url = context.get("previous_approved_asset_url")
            if previous_asset_url and len(data_urls) < 2:
                data_urls.append(
                    self.storage.generated_as_data_url(previous_asset_url)
                )
            self._append_brand_references(
                context.get("client_id"), data_urls, job_id
            )
            self.repository.mark_job_generating(job_id)
            generated = self.generator.generate_image(
                prompt,
                data_urls,
                aspect_ratio=context.get("aspect_ratio") or "16:9",
                quality=tier["quality"],
                resolution=tier["resolution"],
            )
            source_url = self.storage.save_generated_base64(
                generated["b64_json"], generated.get("output_format", "png")
            )
            composed = self._compose_native_asset(
                source_url,
                generated["b64_json"],
                context,
                geometry,
                render_mode,
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
            review_cost = 0
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
                review_cost = float(review.get("actual_cost_usd") or 0)
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
                    "variant_level": variant_level,
                    "fidelity": tier["name"],
                    "quality": tier["quality"],
                    "resolution": tier["resolution"],
                    "parent_asset_id": source_asset["id"] if source_asset else None,
                    "locks": locks,
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
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else float(actual) + review_cost,
                {
                    "usage": generated.get("usage") or {},
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
        )
        if intent:
            prompt += f"\nRefinement intent: {intent}."
        if variant_level:
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
                context.get("client_id"), data_urls, job_id
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
        return _serialize(campaign)

    def campaign_detail(self, campaign_id):
        campaign = self.repository.get_campaign(_integer(campaign_id, "Campanha"))
        data = annotate_cost(campaign, campaign.get("spent_usd"))
        data["flow_kind"] = _flow_kind(data)
        return _serialize(data)

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
            pass
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
            "has_logo": True,
        })
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
            "productions": [
                {"format_template_id": _integer(item, "Formato")}
                for item in raw_ids
            ],
        })
        if created_by:
            plan["created_by"] = created_by
        return plan

    def generate_unfolding(self, campaign_id, created_by=None):
        campaign = self.campaign_detail(campaign_id)
        if _flow_kind(campaign) != "unfold":
            raise ValueError("Esta campanha não é um desdobramento.")
        pieces = []
        for production in campaign.get("productions") or []:
            for scene in production.get("scenes") or []:
                if scene.get("prompt_status") != "approved":
                    self.generate_scene_prompt(scene["id"], created_by=created_by)
                generated = self.generate_scene(
                    scene["id"], [], created_by=created_by, fidelity=DRAFT
                )
                pieces.append({
                    "production_id": production.get("id"),
                    "scene_id": scene["id"],
                    "format_template_id": production.get("format_template_id"),
                    **generated,
                })
        detail = self.campaign_detail(campaign_id)
        detail["pieces"] = pieces
        return detail

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
            raise ValueError("Não há rascunhos selecionados para publicar.")
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
    def _estimate(kind, fidelity=None):
        if kind == "image":
            return _money(
                image_tier_estimate_usd(fidelity or DRAFT),
                "Custo estimado",
            )
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
            "client_identity": {
                "name": context["client_name"],
                "sector": context.get("client_sector"),
                "tone": context.get("tone_of_voice"),
                "logo": context.get("logo_upload_path") or context.get("logo_url"),
                "primary_color": context.get("primary_color"),
                "secondary_color": context.get("secondary_color"),
                "website_url": context.get("website_url"),
                "profile": context.get("brand_profile") or {},
            },
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
        return {
            "headline": locks["headline"] or context.get("campaign_name") or "",
            "cta": locks["cta"] or context.get("cta_text") or "",
            "brand_color": context.get("primary_color") or "#1E4D4F",
        }

    @staticmethod
    def _refine_instruction(instruction, intent, family, locks=None):
        text = _text(instruction, "Instrução de ajuste", max_length=400) or ""
        if intent in {"ab_simple", "simple", "ab_max", "max", "maximum"}:
            return unfold_ab_instruction(intent, locks)
        if intent in {"chrome", "geometry"}:
            fixed = hygiene_instruction(intent, family)
            return f"{fixed} {text}".strip() if text else fixed
        if not text:
            raise ValueError("Instrução de ajuste é obrigatório.")
        return text

    def _logo_bytes(self, context):
        path = context.get("logo_upload_path")
        reader = getattr(self.storage, "absolute_reference_path", None)
        if not path or not callable(reader):
            return None
        try:
            absolute = reader(path)
        except Exception:
            return None
        if absolute is None:
            return None
        try:
            return absolute.read_bytes()
        except Exception:
            return None

    def _compose_native_asset(
        self, source_url, encoded, context, geometry, render_mode
    ):
        if not should_compose(
            geometry.get("family"),
            render_mode,
            context.get("position") or 1,
            context.get("scene_count") or 1,
        ):
            return {"asset_url": source_url, "source_raster": None}
        try:
            raw = base64.b64decode(encoded)
            composed = compose_native_piece(
                raw,
                geometry,
                self._compose_copy(context),
                self._logo_bytes(context),
            )
        except Exception:
            return {"asset_url": source_url, "source_raster": None}
        composed_url = self.storage.save_generated_base64(
            base64.b64encode(composed).decode("ascii"),
            "png",
        )
        return {"asset_url": composed_url, "source_raster": source_url}

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
        return _serialize({
            "jobs": jobs,
            "modelings": modelings,
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
                "viewer_kind": profile["viewer_kind"],
                "viewer_logo_asset_ref": profile["logo_asset_ref"],
                "viewer_palette": profile["palette"],
                "viewer_shell_spec": profile["shell_spec"],
                "viewer_disclaimer": profile["disclaimer"],
            })
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
