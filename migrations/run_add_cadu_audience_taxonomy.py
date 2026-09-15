#!/usr/bin/env python3
"""Apply CADU Audience Taxonomy V2 and load its reviewed draft mapping.

This migration is additive. It leaves legacy category/subcategory columns intact.
Manual classifications are never overwritten by the draft importer.
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Json


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name("add_cadu_audience_taxonomy.sql")
MAPPING_PATH = ROOT / "output" / "audience-taxonomy-review" / "taxonomy_draft.csv"
SOURCE = "taxonomy-draft-2026-09-15"

MARKET_SLUGS = {
    "Imobiliário & Construção": "imobiliario-construcao",
    "Finanças & Seguros": "financas-seguros",
    "Varejo & Consumo": "varejo-consumo",
    "Serviços ao Consumidor": "servicos-consumidor",
    "B2B, Enterprise & Indústria": "b2b-enterprise-industria",
    "Automotivo, Mobilidade & Logística": "automotivo-mobilidade-logistica",
    "Agronegócio": "agronegocio",
    "Saúde, Bem-estar & Beleza": "saude-bem-estar-beleza",
    "Educação & Carreira": "educacao-carreira",
    "Entretenimento, Conteúdo & Esportes": "entretenimento-conteudo-esportes",
}


def split_values(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def canonical_key(value: str) -> str:
    normalized = value.casefold().strip()
    normalized = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE)
    return normalized.strip("-")[:300]


def taxonomy_row(row: dict[str, str]) -> tuple:
    primary_name = (row.get("mercado_principal_proposto") or "").strip()
    primary_slug = MARKET_SLUGS.get(primary_name)
    scope = row["escopo_mercado"]
    if scope == "transversal":
        primary_slug = None
    metadata = {
        "legacy_category": row.get("categoria_atual") or None,
        "legacy_subcategory": row.get("subcategoria_atual") or None,
        "draft_action": row.get("acao_migracao") or None,
        "import_source": SOURCE,
    }
    return (
        int(row["id"]),
        row["papel_catalogo_proposto"],
        scope,
        primary_slug,
        (row.get("submercado_proposto") or "").strip() or None,
        row["orientacao_b2b_b2c"],
        split_values(row.get("tipos_sinal_propostos")),
        split_values(row.get("estagios_funil_propostos")),
        row["confianca_regra"],
        row["acao_migracao"],
        "quarantined" if row["papel_catalogo_proposto"] == "inválido/quarentena" else "draft",
        (row.get("nome_canonico_proposto") or "").strip() or None,
        canonical_key(row["nome_normalizado_chave"]),
        "v2-draft-2026-09-15",
        SOURCE,
        Json(metadata),
    )


UPSERT_TAXONOMY = """
INSERT INTO cadu_audience_taxonomy (
    audience_id, catalog_role, market_scope, primary_market_slug, primary_submarket,
    b2b_b2c_orientation, signal_types, funnel_stages, classification_confidence,
    migration_action, curation_status, canonical_name, canonical_key, taxonomy_version,
    classification_source, classification_metadata
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
ON CONFLICT (audience_id) DO UPDATE SET
    catalog_role = EXCLUDED.catalog_role,
    market_scope = EXCLUDED.market_scope,
    primary_market_slug = EXCLUDED.primary_market_slug,
    primary_submarket = EXCLUDED.primary_submarket,
    b2b_b2c_orientation = EXCLUDED.b2b_b2c_orientation,
    signal_types = EXCLUDED.signal_types,
    funnel_stages = EXCLUDED.funnel_stages,
    classification_confidence = EXCLUDED.classification_confidence,
    migration_action = EXCLUDED.migration_action,
    curation_status = EXCLUDED.curation_status,
    canonical_name = EXCLUDED.canonical_name,
    canonical_key = EXCLUDED.canonical_key,
    taxonomy_version = EXCLUDED.taxonomy_version,
    classification_source = EXCLUDED.classification_source,
    classification_metadata = EXCLUDED.classification_metadata,
    updated_at = NOW()
WHERE cadu_audience_taxonomy.classification_source = EXCLUDED.classification_source
   OR cadu_audience_taxonomy.curation_status = 'draft'
"""


def main() -> None:
    load_dotenv(ROOT / ".env")
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"Mapeamento não encontrado: {MAPPING_PATH}")
    rows = list(csv.DictReader(MAPPING_PATH.open(encoding="utf-8")))
    if len(rows) != 935:
        raise RuntimeError(f"Esperados 935 itens no mapeamento; encontrados {len(rows)}.")

    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_PATH.read_text(encoding="utf-8"))
            cur.execute("SELECT COUNT(*) FROM cadu_audiencias")
            catalog_count = cur.fetchone()[0]
            if catalog_count != len(rows):
                raise RuntimeError(
                    f"Catálogo mudou: banco possui {catalog_count} itens; mapeamento possui {len(rows)}. "
                    "Regere a revisão antes de aplicar."
                )

            cur.executemany(UPSERT_TAXONOMY, [taxonomy_row(row) for row in rows])

            # Relações do rascunho podem ser reimportadas; relações manuais são
            # preservadas por usarem outra origem.
            cur.execute(
                "DELETE FROM cadu_audience_market_relations WHERE source = %s",
                (SOURCE,),
            )
            relations: list[tuple[int, str, str, str]] = []
            for row in rows:
                audience_id = int(row["id"])
                primary = MARKET_SLUGS.get((row.get("mercado_principal_proposto") or "").strip())
                if row["escopo_mercado"] == "vertical" and primary:
                    relations.append((audience_id, primary, "primary", SOURCE))
                for market in split_values(row.get("mercados_relacionados_propostos")):
                    slug = MARKET_SLUGS.get(market)
                    if slug:
                        relations.append((audience_id, slug, "related", SOURCE))
            cur.executemany(
                """
                INSERT INTO cadu_audience_market_relations
                    (audience_id, market_slug, relation_type, source)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (audience_id, market_slug, relation_type) DO NOTHING
                """,
                relations,
            )
            cur.execute("SELECT COUNT(*) FROM cadu_audience_taxonomy")
            taxonomy_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM cadu_audience_market_relations WHERE source = %s", (SOURCE,))
            relation_count = cur.fetchone()[0]
        conn.commit()
    print(
        json.dumps(
            {
                "catalog_items": catalog_count,
                "taxonomy_rows": taxonomy_count,
                "draft_relations": relation_count,
                "source": SOURCE,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
