"""Identidade da marca (Modelagem) e partes do planejamento."""

from __future__ import annotations

import logging
from typing import Any

from ..db import get_db
from .catalog import CHANNEL_CATALOG
from .helpers import as_dict, as_list, text
from .logos import lookup_agency_for_client, lookup_party_by_id, public_logo

logger = logging.getLogger(__name__)

SEED_KEYS = ("plan_mode", "cliente_id", "agencia_id", "cx_client_id", "brand")

PLATE_TO_CHANNEL = {
    "instagram": "meta_ads",
    "meta": "meta_ads",
    "facebook": "meta_ads",
    "tiktok": "tiktok",
    "linkedin": "linkedin",
    "youtube": "youtube",
    "google": "google_ads",
    "google_ads": "google_ads",
    "serasa": "serasa",
    "prime_video": "prime_video",
    "netflix": "netflix",
    "disney": "disney",
    "hbo_max": "hbo_max",
    "globoplay": "globoplay",
    "spotify": "spotify",
    "g1": "g1",
    "uol": "uol",
    "r7": "r7",
    "cnn": "cnn",
    "ooh": "ooh",
    "dv360": "dv360",
    "gpt_ads": "gpt_ads",
    "meta_ads": "meta_ads",
}


def map_plate_channels(plate_channels: Any) -> list[str]:
    mapped: list[str] = []
    raw = plate_channels if isinstance(plate_channels, dict) else {}
    for key, values in raw.items():
        candidates = [key]
        if isinstance(values, (list, tuple)):
            candidates.extend(values)
        elif values:
            candidates.append(values)
        for item in candidates:
            token = text(item).lower()
            if not token:
                continue
            channel = token if token in CHANNEL_CATALOG else PLATE_TO_CHANNEL.get(token)
            if channel in CHANNEL_CATALOG and channel not in mapped:
                mapped.append(channel)
    return mapped


def snapshot_brand(client: dict | None) -> dict:
    if not isinstance(client, dict) or not client:
        return {}
    try:
        from ..creative_format_lab.brand_context import build_brand_context

        context = build_brand_context(client)
    except Exception:
        logger.exception("Falha ao montar contexto da marca %s", client.get("id"))
        context = {
            "id": client.get("id"),
            "name": text(client.get("name")),
            "logo_url": public_logo(client.get("logo_upload_path") or client.get("logo_url")),
            "sector": text(client.get("sector")),
            "tone_of_voice": text(client.get("tone_of_voice")),
            "brand_summary": text(as_dict(client.get("brand_profile")).get("brand_summary")),
            "target_audience": text(as_dict(client.get("brand_profile")).get("target_audience")),
            "products_services": as_list(as_dict(client.get("brand_profile")).get("products_services")),
            "campaign_opportunities": as_list(as_dict(client.get("brand_profile")).get("campaign_opportunities")),
            "creative_guidelines": text(as_dict(client.get("brand_profile")).get("creative_guidelines")),
            "palette": [],
        }
    profile = as_dict(client.get("brand_profile"))
    canais = map_plate_channels(profile.get("plate_channels"))
    products = [text(item) for item in as_list(context.get("products_services")) if text(item)][:6]
    opportunities = [text(item) for item in as_list(context.get("campaign_opportunities")) if text(item)][:6]
    snapshot = {
        "id": context.get("id") or client.get("id"),
        "name": text(context.get("name") or client.get("name")),
        "logo_url": public_logo(context.get("logo_url") or client.get("logo_upload_path") or client.get("logo_url")),
        "sector": text(context.get("sector")),
        "tone_of_voice": text(context.get("tone_of_voice")),
        "brand_summary": text(context.get("brand_summary")),
        "target_audience": text(context.get("target_audience")),
        "products_services": products,
        "campaign_opportunities": opportunities,
        "creative_guidelines": text(context.get("creative_guidelines")),
        "palette": [text(item) for item in as_list(context.get("palette")) if text(item)][:6],
        "canais": canais,
    }
    snapshot["has_identity"] = bool(
        snapshot["brand_summary"]
        or snapshot["target_audience"]
        or snapshot["products_services"]
        or snapshot["tone_of_voice"]
        or snapshot["logo_url"]
    )
    return snapshot


def load_cx_client_for_crm(crm_client_id: Any) -> dict | None:
    if not crm_client_id:
        return None
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, crm_client_id, name, sector, tone_of_voice, logo_url,
                       logo_upload_path, primary_color, secondary_color,
                       website_url, brand_profile, analysis_metadata
                  FROM cx_clients
                 WHERE crm_client_id = %s
                 ORDER BY id
                 LIMIT 1
                """,
                (crm_client_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            client = dict(row)
            try:
                cur.execute(
                    """
                    SELECT role, asset_url, stored_url, source_url
                      FROM cx_client_brand_assets
                     WHERE client_id = %s
                    """,
                    (client.get("id"),),
                )
                client["brand_assets"] = [dict(item) for item in (cur.fetchall() or [])]
            except Exception:
                try:
                    cur.connection.rollback()
                except Exception:
                    pass
                client["brand_assets"] = []
            return client
    except Exception:
        logger.exception("Falha ao buscar marca do cliente CRM %s", crm_client_id)
        try:
            get_db().rollback()
        except Exception:
            pass
        return None


def brand_for_client(crm_client_id: Any) -> dict:
    return snapshot_brand(load_cx_client_for_crm(crm_client_id))


def search_parties(query: str, kind: str = "cliente", limit: int = 12) -> list[dict]:
    term = text(query)
    if len(term) < 2:
        return []
    like = f"%{term}%"
    clauses = ["COALESCE(c.status, TRUE) = TRUE"]
    params: list[Any] = [like, like]
    if kind == "agencia":
        clauses.append("a.key = TRUE")
    else:
        clauses.append("(a.key = FALSE OR a.key IS NULL)")
    sql = f"""
        SELECT c.id_cliente,
               COALESCE(c.nome_fantasia, c.razao_social) AS nome
          FROM tbl_cliente c
          LEFT JOIN tbl_agencia a ON c.pk_id_tbl_agencia = a.id_agencia
         WHERE {' AND '.join(clauses)}
           AND (
                COALESCE(c.nome_fantasia, '') ILIKE %s
             OR COALESCE(c.razao_social, '') ILIKE %s
           )
         ORDER BY COALESCE(c.nome_fantasia, c.razao_social)
         LIMIT %s
    """
    params.append(max(1, min(30, int(limit))))
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() or []
        return [
            {"id": row.get("id_cliente"), "name": text(row.get("nome"))}
            for row in rows
            if text(row.get("nome"))
        ]
    except Exception:
        logger.exception("Falha ao buscar %s '%s'", kind, term)
        try:
            get_db().rollback()
        except Exception:
            pass
        return []


def briefing_pistas(dados: dict) -> dict:
    dados = as_dict(dados)
    brand = as_dict(dados.get("brand"))
    campanha = dados.get("campanha") if isinstance(dados.get("campanha"), dict) else {}
    contexto_parts = [
        text(dados.get("contexto")),
        text(brand.get("brand_summary")),
        *as_list(brand.get("campaign_opportunities")),
    ]
    canais = as_list(campanha.get("canais") or dados.get("canais") or brand.get("canais"))
    return {
        "cliente": text(dados.get("cliente")),
        "agencia": text(dados.get("agencia") or campanha.get("agencia")),
        "publico": text(dados.get("publico") or brand.get("target_audience")),
        "contexto": " ".join(part for part in contexto_parts if part),
        "canais": [key for key in canais if key in CHANNEL_CATALOG],
    }


def apply_pistas(campos: dict, pistas: dict | None) -> dict:
    merged = dict(campos or {})
    hints = pistas or {}
    for key in ("cliente", "agencia"):
        if text(hints.get(key)):
            merged[key] = text(hints.get(key))
    for key in ("publico", "contexto"):
        if not text(merged.get(key)) and text(hints.get(key)):
            merged[key] = text(hints.get(key))
    extracted = [key for key in as_list(merged.get("canais")) if key in CHANNEL_CATALOG]
    hinted = [key for key in as_list(hints.get("canais")) if key in CHANNEL_CATALOG]
    merged["canais"] = list(dict.fromkeys(hinted + extracted))
    return merged


def brand_prompt_block(brand: dict | None) -> dict:
    snapshot = as_dict(brand)
    if not snapshot:
        return {}
    return {
        "nome": snapshot.get("name"),
        "setor": snapshot.get("sector"),
        "tom": snapshot.get("tone_of_voice"),
        "resumo": snapshot.get("brand_summary"),
        "publico": snapshot.get("target_audience"),
        "produtos": snapshot.get("products_services"),
        "oportunidades": snapshot.get("campaign_opportunities"),
        "direcao_criativa": snapshot.get("creative_guidelines"),
        "canais": snapshot.get("canais"),
    }


def seed_parties(payload: dict) -> dict:
    cliente_id = payload.get("cliente_id") or None
    agencia_id = payload.get("agencia_id") or None
    cliente = text(payload.get("cliente"))
    agencia = text(payload.get("agencia"))
    if cliente_id:
        party = lookup_party_by_id(cliente_id)
        cliente = cliente or text(party.get("name"))
        if not agencia and not agencia_id:
            linked = lookup_agency_for_client(cliente_id)
            agencia = text(linked.get("name"))
            agencia_id = linked.get("id")
    if agencia_id and not agencia:
        agencia = text(lookup_party_by_id(agencia_id).get("name"))
    if not cliente:
        raise ValueError("Informe o anunciante.")
    brand = brand_for_client(cliente_id) if cliente_id else {}
    contexto_parts = [text(brand.get("brand_summary")), *as_list(brand.get("campaign_opportunities"))]
    return {
        "cliente": cliente,
        "agencia": agencia,
        "cliente_id": cliente_id,
        "agencia_id": agencia_id,
        "cx_client_id": brand.get("id"),
        "brand": brand,
        "publico": text(brand.get("target_audience")),
        "contexto": " ".join(part for part in contexto_parts if part),
        "canais": as_list(brand.get("canais")),
    }


def preserve_seed(current: dict, incoming: dict) -> dict:
    merged = dict(current or {})
    merged.update(incoming or {})
    for key in SEED_KEYS:
        if key in (current or {}) and (current or {}).get(key) not in (None, ""):
            if key == "brand" and not as_dict(incoming.get("brand")):
                merged[key] = current[key]
            elif key != "brand":
                merged[key] = current[key]
    return merged
