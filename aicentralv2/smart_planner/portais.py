"""Seleção de portais da Rede de portais e sites: categorias, regiões, UFs e recorte de classe.

O catálogo tem mais de mil sites. O plano não lista todos: o executivo escolhe o recorte e o plano
mostra quantos sites ele alcança e os maiores, por destaque, faixa de tráfego e ranking de popularidade.
"""

from __future__ import annotations

import logging
from typing import Any

from .helpers import as_dict, as_list, text

logger = logging.getLogger(__name__)

REGIONS = {
    "Norte": ("AC", "AP", "AM", "PA", "RO", "RR", "TO"),
    "Nordeste": ("AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"),
    "Centro-Oeste": ("DF", "GO", "MT", "MS"),
    "Sudeste": ("ES", "MG", "RJ", "SP"),
    "Sul": ("PR", "RS", "SC"),
}
SEGMENTS = ("A", "AB", "B", "BC", "C")
REGIONAL_PREFIX = "Jornalismo online"
TIER_ORDER = "CASE traffic_tier WHEN 'grande' THEN 1 WHEN 'medio' THEN 2 WHEN 'pequeno' THEN 3 ELSE 4 END"
SITE_LIMIT = 8


def normalize_portais(raw: Any) -> dict:
    """Recorte válido: categorias, regiões, UFs e classe; sites preferidos seguem como foram citados."""
    data = as_dict(raw)
    regions = [name for name in (text(item) for item in as_list(data.get("regioes"))) if name in REGIONS]
    ufs = []
    for item in as_list(data.get("ufs")):
        uf = text(item).upper()
        if len(uf) == 2 and any(uf in group for group in REGIONS.values()) and uf not in ufs:
            ufs.append(uf)
    segment = text(data.get("segmento")).upper().replace(" ", "")
    out = {
        "categorias": list(dict.fromkeys(text(item)[:80] for item in as_list(data.get("categorias")) if text(item)))[:12],
        "regioes": list(dict.fromkeys(regions)),
        "ufs": ufs,
        "segmento": segment if segment in SEGMENTS else "",
        "sites_preferidos": list(dict.fromkeys(text(item)[:80] for item in as_list(data.get("sites_preferidos")) if text(item)))[:12],
    }
    return {key: value for key, value in out.items() if value}


def _where(portais: dict) -> tuple[str, list]:
    where, params = ["active IS TRUE"], []
    categories = portais.get("categorias") or []
    if categories:
        clauses = []
        for name in categories:
            if name == REGIONAL_PREFIX:
                clauses.append("category LIKE %s")
                params.append(REGIONAL_PREFIX + "%")
            else:
                clauses.append("category = %s")
                params.append(name)
        where.append("(" + " OR ".join(clauses) + ")")
    ufs = list(portais.get("ufs") or [])
    regions = portais.get("regioes") or []
    for region in regions:
        ufs.extend(REGIONS[region])
    if ufs or regions:
        clauses = []
        if ufs:
            clauses.append("uf = ANY(%s)")
            params.append(sorted(set(ufs)))
        for region in regions:
            clauses.append("category LIKE %s")
            params.append("%· " + region)
        where.append("(" + " OR ".join(clauses) + ")")
    if portais.get("segmento"):
        # A classe do portal vem do perfil demográfico estimado: "AB" atende quem começa em A.
        where.append("COALESCE(demographics->>'classe', '') LIKE %s")
        params.append(portais["segmento"][0] + "%")
    return " AND ".join(where), params


def sites_for(portais: Any, limit: int = SITE_LIMIT) -> dict:
    """Quantos sites o recorte alcança e os maiores deles. Sem banco, devolve só os preferidos citados."""
    selection = normalize_portais(portais)
    preferred = selection.get("sites_preferidos", [])
    result = {"total": 0, "sites": [], "relaxed": "", "criterios": {k: v for k, v in selection.items() if k != "sites_preferidos"}}
    try:
        from ..cadu_family import repository

        # Se o recorte não fecha, abre mão primeiro da região (portais nacionais atendem qualquer praça),
        # depois da classe, e o plano diz qual critério foi aberto.
        attempts = [("", selection)]
        if selection.get("regioes") or selection.get("ufs"):
            attempts.append(("regiao", {**selection, "regioes": [], "ufs": []}))
        if selection.get("segmento"):
            attempts.append(("segmento", {**selection, "regioes": [], "ufs": [], "segmento": ""}))
        for relaxed, current in attempts:
            where, params = _where(current)
            count = repository.rows(f"SELECT count(*) AS n FROM cadu_planner_portals WHERE {where}", params)
            total = int((count[0] if count else {}).get("n") or 0)
            if total:
                rows = repository.rows(
                    f"""SELECT name, domain, category, uf, scope, traffic_tier
                          FROM cadu_planner_portals WHERE {where}
                         ORDER BY featured_rank NULLS LAST, {TIER_ORDER}, popularity_rank NULLS LAST, name
                         LIMIT %s""",
                    [*params, max(1, min(int(limit), 20))],
                )
                result.update({
                    "total": total,
                    "relaxed": relaxed,
                    "sites": [
                        {"name": text(row.get("name")), "domain": text(row.get("domain")), "category": text(row.get("category")),
                         "uf": text(row.get("uf")), "tier": text(row.get("traffic_tier"))}
                        for row in rows or []
                    ],
                })
                break
    except Exception:
        logger.warning("Catálogo de portais indisponível; o plano usa só os sites citados.", exc_info=True)
    if preferred:
        names = {text(site.get("name")).lower() for site in result["sites"]}
        extra = [{"name": name, "domain": "", "category": "", "uf": "", "tier": "", "preferred": True}
                 for name in preferred if name.lower() not in names]
        result["sites"] = (extra + result["sites"])[: max(limit, len(preferred))]
    return result


def facets() -> dict:
    """Opções para a tela: categorias temáticas, regiões, UFs e classes."""
    try:
        from ..cadu_family import repository

        rows = repository.rows(
            "SELECT category, count(*) AS n FROM cadu_planner_portals WHERE active IS TRUE AND category IS NOT NULL GROUP BY 1 ORDER BY n DESC"
        )
    except Exception:
        rows = []
    regional = sum(int(row["n"]) for row in rows if text(row["category"]).startswith(REGIONAL_PREFIX))
    thematic = [{"id": text(row["category"]), "count": int(row["n"])} for row in rows if not text(row["category"]).startswith(REGIONAL_PREFIX)]
    categories = ([{"id": REGIONAL_PREFIX, "count": regional}] if regional else []) + thematic
    return {
        "categorias": categories,
        "regioes": [{"id": name, "ufs": list(ufs)} for name, ufs in REGIONS.items()],
        "segmentos": list(SEGMENTS),
        "total": sum(int(row["n"]) for row in rows),
    }
