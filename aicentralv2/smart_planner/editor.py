"""Contexto do editor admin da página única — sem folha de venda."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import current_app, has_app_context

from ..product_domains import product_url

from .brand import brand_for_client, snapshot_brand, load_cx_client_for_crm
from .canvas import SECTIONS
from .estimates import ORIGIN_LABELS as ESTIMATE_ORIGIN_LABELS, public_view as estimates_view
from .helpers import as_dict, as_list, plan_mode_of, text
from .images import ART_PUBLIC_PREFIX, MAX_EXTRA_ARTS, creative_images, is_generated_art, is_variant_file
from .logos import lookup_agency_for_client, public_logo
from .skills.catalog import COMPLETO_STEPS, ONE_PAGE_STEPS

logger = logging.getLogger(__name__)

FOLHA_CHECKS = (
    {"id": "strategy", "label": "Tese e briefing", "anchor": "sp-acc-strategy"},
    {"id": "creative", "label": "Criativo no canal", "anchor": "sp-acc-creative"},
    {"id": "media", "label": "Gestão de mídia", "anchor": "sp-acc-media"},
    {"id": "market", "label": "Mercado", "anchor": "sp-acc-market"},
    {"id": "defense", "label": "Defesa", "anchor": "sp-acc-defense"},
    {"id": "images", "label": "Imagens", "anchor": "sp-acc-creative"},
    {"id": "brand", "label": "Marca", "anchor": "sp-acc-brand"},
)

COMPLETO_CHECKS = (
    {"id": "full_strategy", "label": "Estratégia", "section": "strategy"},
    {"id": "full_media", "label": "Mídia", "section": "media"},
    {"id": "full_execution", "label": "Execução", "section": "execution"},
    {"id": "full_defense", "label": "Defesa comercial", "section": "execution"},
    {"id": "compose", "label": "Quadro", "section": None},
)


def _cards_by_type(folha: dict) -> dict:
    found = {}
    for section in as_list(folha.get("sections")):
        for card in as_list(as_dict(section).get("cards")):
            kind = text(as_dict(card).get("type"))
            if kind and kind not in found:
                found[kind] = as_dict(card)
    return found


def _has_text(*parts) -> bool:
    return any(text(part) for part in parts)


def _folha_checklist(folha: dict, cards: dict, gallery: list, brand_panel: dict) -> list[dict]:
    media = as_dict(folha.get("media"))
    theme = as_dict(folha.get("theme"))
    creative = cards.get("creative") or {}
    market = cards.get("market") or {}
    strategy = cards.get("strategy") or {}
    defense = cards.get("defense") or {}
    done = {
        "strategy": _has_text(strategy.get("body")),
        "creative": _has_text(creative.get("body"), creative.get("channel")),
        "media": bool(as_list(media.get("channels")) or as_list(theme.get("density")) or as_dict(media.get("pace")).get("months")),
        "market": _has_text(market.get("stat"), market.get("body")),
        "defense": _has_text(defense.get("body")),
        "images": bool(gallery),
        "brand": bool(brand_panel.get("client") or brand_panel.get("agency")),
    }
    return [
        {
            **item,
            "done": bool(done.get(item["id"])),
            "href": f"#{item['anchor']}",
        }
        for item in FOLHA_CHECKS
    ]


def _step_done(geracao: dict, step_id: str) -> bool:
    for item in as_list(geracao.get("steps")):
        if text(as_dict(item).get("id")) == step_id:
            return text(as_dict(item).get("state")) in {"done", "skipped"}
    return False


def _completo_checklist(row: dict, dados: dict, share_url: str, token: str) -> list[dict]:
    plan = as_dict(row.get("plan_content"))
    sections = {
        text(as_dict(section).get("id")): as_dict(section)
        for section in as_list(plan.get("sections"))
        if text(as_dict(section).get("id")) not in {"one_page", ""}
    }
    chapters = as_list(as_dict(dados.get("planejamento_grupos")).values()) if dados.get("planejamento_grupos") else []
    has_doc = bool(chapters) or any(as_list(as_dict(sec).get("cards")) for sec in sections.values())
    geracao = as_dict(dados.get("geracao"))
    mode = plan_mode_of(dados)
    wizard = f"/smart-planner/{token}/revisao"
    out = []
    for item in COMPLETO_CHECKS:
        section_id = item.get("section")
        section = sections.get(section_id or "", {}) if section_id else {}
        created = bool(as_list(section.get("cards"))) if section_id else has_doc
        if not created:
            created = _step_done(geracao, item["id"]) and mode == "completo"
        if item["id"] == "compose":
            created = has_doc or _step_done(geracao, "compose") or _step_done(geracao, "publish")
        href = f"{share_url}#documento" if created and share_url else wizard
        out.append({
            "id": item["id"],
            "label": item["label"],
            "done": created,
            "state": "created" if created else "planned",
            "href": href,
            "external": bool(created and share_url),
        })
    return out


SHAPE_LABELS = {"horizontal": "Horizontal", "vertical": "Vertical"}
VARIANT_LABELS = {"horizontal": "16:9", "vertical": "9:16", "square": "1:1"}
OTHER_LABELS = {"background": "Fundo gerado", "persona": "Persona do plano", "place": "Lugar da campanha"}


def _gallery(folha: dict) -> list[dict]:
    """Artes do plano primeiro (a que está no plano marcada), depois as imagens de apoio."""
    cards = _cards_by_type(folha)
    creative = cards.get("creative") or {}
    current = text(as_dict(as_dict(folha.get("public_design")).get("hero")).get("asset_url")) or text(creative.get("image_url"))
    items = []
    for index, art in enumerate(creative_images(creative), 1):
        shape = text(art.get("shape")) or "horizontal"
        variants = as_dict(art.get("variants"))
        items.append({
            "id": f"art-{index}",
            "label": f"Arte {index}",
            "url": art["url"],
            "kind": "creative",
            "shape": shape,
            "shape_label": SHAPE_LABELS.get(shape, "Horizontal"),
            "formats": [VARIANT_LABELS[shape]] + [VARIANT_LABELS[key] for key in ("horizontal", "vertical", "square") if text(variants.get(key)) and key != shape],
            "active": art["url"] == current,
            "in_plan": art["url"] != current and art.get("in_plan") is True,
        })
    # Plano de antes da lista de artes: as artes antigas estão só na pasta, pelo nome do cliente.
    legacy = [] if as_list(creative.get("images")) else _generated_files(_slug_from_meta(folha))
    for path in legacy:
        url = f"{ART_PUBLIC_PREFIX}{path.name}"
        if "-creative-" not in path.name or is_variant_file(url) or any(item["url"] == url for item in items):
            continue
        items.append({
            "id": path.stem, "label": "Arte anterior", "url": url, "kind": "creative", "shape": "horizontal",
            "shape_label": "Horizontal", "formats": ["16:9"], "active": url == current,
        })
    for asset in as_list(folha.get("asset_manifest")):
        row = as_dict(asset)
        url = text(row.get("asset_url") or row.get("image_url"))
        kind = text(row.get("kind")) or "other"
        if not url or kind == "creative" or any(item["url"] == url for item in items):
            continue
        items.append({"id": text(row.get("id") or kind), "label": text(row.get("label")) or OTHER_LABELS.get(kind, "Imagem de apoio"),
                      "url": url, "kind": kind, "status": text(row.get("status")) or "draft", "active": url == current})
    bg = text(as_dict(folha.get("theme")).get("bg_url"))
    if bg and is_generated_art(bg) and not any(item["url"] == bg for item in items):
        items.append({"id": "bg", "label": "Fundo gerado", "url": bg, "kind": "background", "status": "draft", "active": False})
    extras = 0
    for item in items:
        if item.get("in_plan"):
            extras += 1
            item["in_plan"] = extras <= MAX_EXTRA_ARTS
    return items[:16]


def _slug_from_meta(folha: dict) -> str:
    meta = as_dict(folha.get("meta"))
    hero = as_dict(as_dict(folha.get("branding")).get("hero"))
    raw = text(meta.get("client") or hero.get("name") or "folha").lower()
    out = []
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")[:40] or "folha"


def _generated_files(slug: str) -> list[Path]:
    root = _art_dir()
    if not root.is_dir():
        return []
    # Só as artes deste cliente; a pasta é compartilhada por todos os planos.
    return sorted(root.glob(f"{slug}-*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:12]


def _art_dir() -> Path:
    if has_app_context() and current_app.static_folder:
        root = current_app.static_folder
    else:
        root = os.path.join(os.path.dirname(__file__), "..", "static")
    return Path(os.path.abspath(os.path.join(root, "uploads", "smart_planner")))


def _brand_panel(dados: dict, folha: dict) -> dict:
    branding = as_dict(folha.get("branding"))
    client_party = as_dict(branding.get("client") or branding.get("hero"))
    agency_party = as_dict(branding.get("agency"))
    presenter = as_dict(branding.get("presenter"))
    cliente_id = dados.get("cliente_id") or client_party.get("id")
    cx_id = dados.get("cx_client_id")
    brand = as_dict(dados.get("brand"))
    if not brand.get("has_identity") and cliente_id:
        brand = as_dict(brand_for_client(cliente_id) or brand)
    if not brand.get("name") and cx_id:
        brand = as_dict(snapshot_brand(load_cx_client_for_crm(cliente_id) if cliente_id else None) or brand)
    agency = as_dict(agency_party)
    if not agency.get("name") and cliente_id:
        agency = as_dict(lookup_agency_for_client(cliente_id) or agency)
    assets = as_list(brand.get("brand_assets"))
    if not assets and brand.get("id"):
        loaded = load_cx_client_for_crm(cliente_id) if cliente_id else None
        assets = as_list(as_dict(loaded).get("brand_assets"))
    asset_count = len(assets)
    logo = public_logo(brand.get("logo_url") or client_party.get("logo_url"))
    has_identity = bool(brand.get("has_identity") or logo or brand.get("brand_summary"))
    marcas_path = f"/workspace/app/marcas/{brand.get('id')}" if brand.get("id") else "/workspace/app/marcas"
    params = []
    if cliente_id:
        params.append(f"crm_client_id={cliente_id}")
    if brand.get("id"):
        params.append(f"creative_client_id={brand.get('id')}")
    if params:
        marcas_path = f"{marcas_path}?{'&'.join(params)}"
    # This context is also assembled by exports and background callers that do
    # not have an active Flask app. Preserve the relative Workspace hand-off
    # there; browser requests still resolve to the configured Workspace host.
    marcas_url = product_url("workspace", marcas_path) if has_app_context() else marcas_path
    return {
        "client": {
            "name": text(brand.get("name") or client_party.get("name")),
            "logo_url": logo,
            "has_identity": has_identity,
            "palette": as_list(brand.get("palette"))[:6],
            "asset_count": asset_count,
            "cx_client_id": brand.get("id") or cx_id,
            "crm_client_id": cliente_id,
        },
        "agency": {
            "name": text(agency.get("name")),
            "logo_url": public_logo(agency.get("logo_url")),
        } if text(agency.get("name")) else {},
        "presenter": {
            "id": text(presenter.get("id") or dados.get("presenter_brand") or "centralcomm"),
            "name": text(presenter.get("name")),
            "role": text(presenter.get("role") or "support"),
        },
        "marcas_url": marcas_url,
        "create_url": marcas_url,
        "can_open": bool(brand.get("id") or has_identity),
        "needs_create": not has_identity,
    }


def _channel_formats(dados: dict, media: dict) -> list[dict]:
    """Formatos escolhidos por canal (revisão e táticas), com o tipo de cada um.

    O catálogo de cada canal define o que ele aceita: interativos só existem na Rede de portais.
    """
    from . import formats as format_catalog
    from .catalog import CHANNEL_CATALOG
    from .taticas import family_label, family_of, formats_for_channel, normalize_taticas

    try:
        campanha = format_catalog.migrate_campanha(as_dict(dados.get("campanha")))
        canais = [text(c) for c in as_list(campanha.get("canais"))]
        taticas = normalize_taticas(campanha.get("taticas") or dados.get("taticas"), canais)
        chosen = as_dict(campanha.get("formatos"))
        labels = {text(as_dict(c).get("id")): text(as_dict(c).get("label")) for c in as_list(media.get("channels"))}
        out = []
        for key in canais:
            slugs = list(dict.fromkeys([text(s) for s in as_list(chosen.get(key))] + formats_for_channel(key, taticas)))
            catalog = format_catalog.formats_for_channel(key)
            items = []
            for slug in slugs:
                row = format_catalog.by_id(slug)
                family = family_of(slug)
                items.append({
                    "name": text(row.get("name")) or slug,
                    "type": family_label(family) if family else "",
                    "aggregated": bool(row.get("aggregated_cost")),
                    "description": text(row.get("description")) if row.get("interactive") else "",
                })
            out.append({
                "id": key,
                "label": labels.get(key) or text(as_dict(CHANNEL_CATALOG.get(key)).get("label")) or key,
                "formats": items,
                "available": len(catalog),
                "interactive": any(row.get("interactive") for row in catalog),
            })
        return out
    except Exception:
        logger.exception("Falha ao montar os formatos por canal do editor")
        return []


def _media_for_editor(media: dict) -> dict:
    """Altura de cada barra do voo (semana ou mês) pela verba do período; o board só guarda o valor."""
    media = dict(media)
    pace = dict(as_dict(media.get("pace")))
    months = [dict(as_dict(m)) for m in as_list(pace.get("months"))]
    peak = max((int(m.get("amount") or 0) for m in months), default=0)
    for month in months:
        amount = int(month.get("amount") or 0)
        month["pct"] = round(amount * 100 / peak) if peak and amount else 0
    if months:
        pace["months"] = months
        media["pace"] = pace
    return media


def _presentation_panel(row: dict, dados: dict, folha: dict) -> dict:
    """Seletor de modelo de apresentação (logo e paleta) e links de exportação."""
    from . import presentation

    try:
        panel = presentation.editor_panel(row)
    except Exception:
        logger.exception("Falha ao montar o painel de modelo de apresentação")
        panel = {"options": [], "selected": "centralcomm", "missing": []}
    public_token = text(as_dict(folha.get("share")).get("public_token") or dados.get("public_token") or row.get("public_token"))
    if public_token:
        base = f"/smart-planner/p/{public_token}"
        panel["slides_url"] = f"{base}/proposta"
        panel["pptx_url"] = f"{base}/apresentacao.pptx"
    return panel


def _impact_for_review(dados: dict) -> dict:
    """Estimativa de impacto só para o executivo: valores parecem cotação e não vão para o cliente."""
    estimates = as_dict(dados.get("estimates"))
    view = estimates_view(estimates)
    if not as_list(view.get("rows")):
        return {}
    view["origin_label"] = ESTIMATE_ORIGIN_LABELS.get(estimates.get("origin"), "Estimativa")
    return view


def editor_context(row: dict, share_url: str = "") -> dict:
    dados = as_dict(row.get("dados_detectados"))
    folha = as_dict(dados.get("folha"))
    if not as_list(folha.get("sections")):
        plan = as_dict(row.get("plan_content"))
        if text(plan.get("planMode")) == "one_page" or any(
            text(as_dict(section).get("id")) == "one_page" for section in as_list(plan.get("sections"))
        ):
            folha = plan
    cards = _cards_by_type(folha)
    brand_panel = _brand_panel(dados, folha)
    gallery = _gallery(folha)
    token = text(row.get("session_token"))
    url = text(share_url) or text(as_dict(folha.get("share")).get("url"))
    presentation = _presentation_panel(row, dados, folha)
    return {
        "folha": folha,
        "cards": cards,
        "gallery": gallery,
        "brand_panel": brand_panel,
        "presentation": presentation,
        "impact_review": _impact_for_review(dados),
        "channel_formats": _channel_formats(dados, as_dict(folha.get("media"))),
        "folha_checks": _folha_checklist(folha, cards, gallery, brand_panel),
        "completo_checks": _completo_checklist(row, dados, url, token),
        "media": _media_for_editor(as_dict(folha.get("media"))),
        "theme": as_dict(folha.get("theme")),
        "meta": as_dict(folha.get("meta")),
        "public_design": as_dict(folha.get("public_design")),
        "asset_manifest": as_list(folha.get("asset_manifest")),
        "executive_contact": as_dict(folha.get("executive_contact")),
        "editor_mode": "one_page",
        "one_page_steps": [{"id": item["id"], "title": item["title"]} for item in ONE_PAGE_STEPS],
        "completo_steps": [{"id": item["id"], "title": item["title"]} for item in COMPLETO_STEPS],
        "board_sections": [{"id": s["id"], "title": s["title"]} for s in SECTIONS],
    }
