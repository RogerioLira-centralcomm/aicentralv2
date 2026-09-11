"""Resolve logos de cliente, agência e marcas no CentralX."""

from __future__ import annotations

import logging
from typing import Any

from ..db import get_db
from .helpers import text

logger = logging.getLogger(__name__)

CENTRALCOMM_LOGO = "/static/images/cc_logo.png"

PRESENTER_BRANDS = {
    "centralcomm": {
        "id": "centralcomm",
        "name": "CentralComm",
        "logo_url": CENTRALCOMM_LOGO,
        "role": "support",
    },
    "serasa": {
        "id": "serasa",
        "name": "Serasa Ads",
        "logo_url": "/static/images/canais/experian-portal.png",
        "role": "principal",
    },
    "amazon": {
        "id": "amazon",
        "name": "Amazon",
        "logo_url": "/static/images/creative-viewers/prime-video.svg",
        "role": "principal",
    },
    "logan": {
        "id": "logan",
        "name": "Logan",
        "logo_url": "",
        "role": "principal",
    },
}

PARTNER_LOGOS = {
    "prime_video": {"id": "prime_video", "label": "Prime Video", "logo_url": "/static/images/creative-viewers/prime-video.svg"},
    "meta": {"id": "meta", "label": "Meta", "logo_url": "/static/images/creative-viewers/facebook.svg"},
    "linkedin": {"id": "linkedin", "label": "LinkedIn", "logo_url": "/static/images/creative-viewers/linkedin.svg"},
    "tiktok": {"id": "tiktok", "label": "TikTok", "logo_url": "/static/images/creative-viewers/tiktok.svg"},
    "serasa": {"id": "serasa", "label": "Serasa", "logo_url": "/static/images/canais/experian-portal.png"},
    "instagram": {"id": "instagram", "label": "Instagram", "logo_url": "/static/images/creative-viewers/instagram.svg"},
}


def public_logo(url: str) -> str:
    value = text(url)
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:image/", "/static/")):
        return value
    if "static/" in value:
        return "/" + value.split("static/", 1)[1].lstrip("/") if not value.startswith("/") else value
    return value if value.startswith("/") else ""


def presenter_brand(brand_id: str | None) -> dict:
    key = text(brand_id).lower() or "centralcomm"
    brand = dict(PRESENTER_BRANDS.get(key) or PRESENTER_BRANDS["centralcomm"])
    return brand


def presenter_options() -> list[dict]:
    return [
        {**brand, "label": (
            f"{brand['name']} como apoio" if brand["id"] == "centralcomm"
            else f"{brand['name']} como principal"
        )}
        for brand in PRESENTER_BRANDS.values()
    ]


def partner_marks(keys: list[str]) -> list[dict]:
    marks = []
    for key in keys:
        meta = PARTNER_LOGOS.get(key)
        if meta:
            marks.append(dict(meta))
    return marks


def _empty_party(name: str = "") -> dict:
    return {"id": None, "name": text(name), "logo_url": "", "source": None}


def lookup_party(name: str) -> dict:
    query = text(name)
    if not query:
        return _empty_party()
    try:
        conn = get_db()
        with conn.cursor() as cur:
            from_cx = _from_cx_clients(cur, query)
            if from_cx.get("logo_url"):
                return from_cx
            from_crm = _from_crm(cur, query)
            if from_crm.get("logo_url") or from_crm.get("id"):
                if from_cx.get("name") and not from_crm.get("logo_url"):
                    from_crm["logo_url"] = from_cx.get("logo_url") or ""
                    from_crm["source"] = from_cx.get("source") or from_crm.get("source")
                return from_crm
            return from_cx if from_cx.get("name") else _empty_party(query)
    except Exception:
        logger.exception("Falha ao buscar logo de %s", query)
        return _empty_party(query)


def lookup_agency_for_client(client_id: Any) -> dict:
    if not client_id:
        return _empty_party()
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(ag.nome_fantasia, ag.razao_social) AS nome,
                       web.logo_url
                  FROM tbl_cliente_agencia ca
                  JOIN tbl_cliente ag ON ag.id_cliente = ca.id_agencia_cliente
                  LEFT JOIN cliente_web_info web
                         ON web.id_cliente = ag.id_cliente AND web.status = 'ok'
                 WHERE ca.id_cliente = %s
                 ORDER BY COALESCE(ca.is_principal, FALSE) DESC, ca.id DESC
                 LIMIT 1
                """,
                (client_id,),
            )
            row = cur.fetchone() or {}
            name = text(row.get("nome"))
            if name:
                return {
                    "id": None,
                    "name": name,
                    "logo_url": public_logo(row.get("logo_url")),
                    "source": "crm",
                }
    except Exception:
        logger.exception("Falha ao buscar agência do cliente %s", client_id)
    return _empty_party()


def _from_crm(cur, query: str) -> dict:
    like = f"%{query}%"
    cur.execute(
        """
        SELECT c.id_cliente,
               COALESCE(c.nome_fantasia, c.razao_social) AS nome,
               web.logo_url
          FROM tbl_cliente c
          LEFT JOIN cliente_web_info web
                 ON web.id_cliente = c.id_cliente AND web.status = 'ok'
         WHERE COALESCE(c.status, TRUE) = TRUE
           AND (
                c.nome_fantasia ILIKE %s
             OR c.razao_social ILIKE %s
           )
         ORDER BY CASE
                    WHEN c.nome_fantasia ILIKE %s THEN 0
                    WHEN c.razao_social ILIKE %s THEN 1
                    ELSE 2
                  END, c.id_cliente
         LIMIT 1
        """,
        (like, like, query, query),
    )
    row = cur.fetchone() or {}
    if not row:
        return _empty_party(query)
    return {
        "id": row.get("id_cliente"),
        "name": text(row.get("nome")) or query,
        "logo_url": public_logo(row.get("logo_url")),
        "source": "crm",
    }


def _from_cx_clients(cur, query: str) -> dict:
    like = f"%{query}%"
    try:
        cur.execute(
            """
            SELECT id, name, logo_url, logo_upload_path
              FROM cx_clients
             WHERE name ILIKE %s
             ORDER BY CASE WHEN name ILIKE %s THEN 0 ELSE 1 END, id DESC
             LIMIT 1
            """,
            (like, query),
        )
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass
        return _empty_party(query)
    row = cur.fetchone() or {}
    if not row:
        return _empty_party(query)
    return {
        "id": row.get("id"),
        "name": text(row.get("name")) or query,
        "logo_url": public_logo(row.get("logo_url") or row.get("logo_upload_path")),
        "source": "cx_clients",
    }


def resolve_branding(client_name: str, agency_name: str, presenter_id: str, partners: list[str] | None = None) -> dict:
    client = lookup_party(client_name)
    agency = lookup_party(agency_name)
    if not agency.get("name") and client.get("id"):
        agency = lookup_agency_for_client(client["id"])
    presenter = presenter_brand(presenter_id)
    if presenter["id"] != "centralcomm":
        presenter["role"] = "principal"
    else:
        presenter["role"] = "support"
    return {
        "client": client,
        "agency": agency,
        "presenter": presenter,
        "partners": partner_marks(partners or []),
    }
