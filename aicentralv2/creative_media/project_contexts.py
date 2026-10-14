"""Read-only Studio project context from the shared database.

The Studio has its own product surface and must not import Workspace route
handlers just to populate its context selector.  The project, brand and link
records are shared database facts; this projection deliberately contains no
Workspace UI or request-layer dependency.
"""
from __future__ import annotations

from ..db import get_db


def linked_project_contexts(account_id: int, include_brandless: bool = False) -> list[dict]:
    """Return active projects that have at least one explicitly linked brand.

    ``include_brandless`` adds active projects without any brand (client_id NULL, brand_count 0);
    the Studio uses them with prompt and uploads only, never with a brand's prior identity.
    """
    if account_id <= 0:
        return []

    try:
        with get_db().cursor() as cursor:
            cursor.execute(
                """
                WITH linked_brands AS (
                    SELECT
                        p.id,
                        p.nome,
                        p.descricao,
                        p.instrucoes,
                        p.updated_at,
                        b.id AS client_id,
                        b.name AS brand_name,
                        COUNT(*) OVER (PARTITION BY p.id) AS brand_count,
                        ROW_NUMBER() OVER (
                            PARTITION BY p.id
                            ORDER BY b.created_at DESC NULLS LAST, b.id DESC
                        ) AS brand_rank
                    FROM cadu_ci_projetos AS p
                    INNER JOIN cadu_family_project_brands AS link
                        ON link.client_id = p.id_cliente
                        AND link.project_ref = ('ci:' || p.id::text)
                    INNER JOIN cx_clients AS b
                        ON b.crm_client_id = p.id_cliente
                        AND link.brand_ref = ('studio:' || b.id::text)
                    WHERE p.id_cliente = %s
                      AND p.status = 'ativo'
                )
                SELECT id, nome, descricao, instrucoes, client_id, brand_name, brand_count, updated_at
                  FROM linked_brands
                 WHERE brand_rank = 1
                """ + ("""
                UNION ALL
                SELECT p.id, p.nome, p.descricao, p.instrucoes, NULL AS client_id, '' AS brand_name, 0 AS brand_count, p.updated_at
                  FROM cadu_ci_projetos AS p
                 WHERE p.id_cliente = %s
                   AND p.status = 'ativo'
                   AND NOT EXISTS (
                       SELECT 1 FROM cadu_family_project_brands AS link
                        WHERE link.client_id = p.id_cliente
                          AND link.project_ref = ('ci:' || p.id::text)
                          AND link.brand_ref LIKE 'studio:%%'
                   )
                """ if include_brandless else "") + """
                 ORDER BY updated_at DESC NULLS LAST, nome
                """,
                (account_id, account_id) if include_brandless else (account_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        # A Studio account with no migrated project-link tables has no usable
        # context yet.  Do not fall back to an unlinked brand selector.
        return []
