"""Read-only profile export for the CADU programmatic audience catalog."""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "audience_catalog_analysis"


def main() -> None:
    load_dotenv(ROOT / ".env")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = psycopg.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        row_factory=dict_row,
    )
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.id_audiencia_plataforma, a.nome, a.slug,
                   a.titulo_chamativo, a.descricao, a.descricao_curta,
                   a.descricao_comercial, a.caso_uso_principal,
                   a.insights_planejamento, a.diferenciais_competitivos,
                   a.tags, a.perfil_socioeconomico, a.momentos_chave,
                   a.interesses_correlatos, a.categorias_alto_desempenho,
                   a.propensao_compra, a.sazonalidade, a.relevancia_score,
                   a.is_premium, a.is_active, a.dados_validos,
                   a.campos_estimados_total, a.campos_com_dados_reais,
                   a.requer_cotacao, a.fonte, a.plataforma_id,
                   c.id AS categoria_id, c.nome AS categoria,
                   s.id AS subcategoria_id, s.nome AS subcategoria,
                   p.nome AS plataforma
            FROM cadu_audiencias a
            LEFT JOIN cadu_categorias c ON c.id = a.categoria_id
            LEFT JOIN cadu_subcategorias s ON s.id = a.subcategoria_id
            LEFT JOIN cadu_audiencias_plataformas p ON p.id = a.plataforma_id
            ORDER BY a.id
            """
        )
        rows = cur.fetchall()

        cur.execute("SELECT * FROM cadu_categorias ORDER BY ordem_exibicao, nome")
        categories = cur.fetchall()
        cur.execute(
            """
            SELECT s.*, c.nome AS categoria
            FROM cadu_subcategorias s
            LEFT JOIN cadu_categorias c ON c.id = s.categoria_id
            ORDER BY c.nome, s.ordem_exibicao, s.nome
            """
        )
        subcategories = cur.fetchall()

    fields = list(rows[0].keys()) if rows else []
    with (OUT_DIR / "audiences.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    category_counts = Counter((r["categoria"] or "SEM CATEGORIA") for r in rows)
    subcategory_counts = Counter(
        ((r["categoria"] or "SEM CATEGORIA"), (r["subcategoria"] or "SEM SUBCATEGORIA"))
        for r in rows
    )
    platform_counts = Counter((r["plataforma"] or r["fonte"] or "SEM PLATAFORMA") for r in rows)
    normalized_names = Counter(" ".join((r["nome"] or "").casefold().split()) for r in rows)
    summary = {
        "total": len(rows),
        "active": sum(r["is_active"] is True for r in rows),
        "inactive": sum(r["is_active"] is False for r in rows),
        "without_category": sum(r["categoria_id"] is None for r in rows),
        "without_subcategory": sum(r["subcategoria_id"] is None for r in rows),
        "invalid_category_subcategory_pairs": sum(
            r["subcategoria_id"] is not None
            and not any(
                s["id"] == r["subcategoria_id"] and s["categoria_id"] == r["categoria_id"]
                for s in subcategories
            )
            for r in rows
        ),
        "duplicate_normalized_names": {
            name: count for name, count in normalized_names.items() if name and count > 1
        },
        "field_coverage": {
            field: sum(r[field] not in (None, "", [], {}) for r in rows)
            for field in fields
        },
        "categories": dict(category_counts.most_common()),
        "subcategories": [
            {"category": cat, "subcategory": sub, "count": count}
            for (cat, sub), count in subcategory_counts.most_common()
        ],
        "platforms": dict(platform_counts.most_common()),
        "category_records": categories,
        "subcategory_records": subcategories,
    }
    (OUT_DIR / "profile.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in (
        "total", "active", "inactive", "without_category", "without_subcategory",
        "invalid_category_subcategory_pairs", "duplicate_normalized_names", "categories",
        "platforms",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
