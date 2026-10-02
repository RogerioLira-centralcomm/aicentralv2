"""Leituras do Radar. Escritas entram com o pipeline (Fase 3)."""
from __future__ import annotations

from ..cadu_family import repository


def available() -> bool:
    result = repository.rows("SELECT to_regclass('public.cadu_radar_opportunities') IS NOT NULL AS available")
    return bool(result and result[0]['available'])


def list_opportunities(client_id, *, brand_ref=None, status=None, limit=50):
    if not available():
        return []
    clauses, params = ['client_id = %s'], [int(client_id)]
    if brand_ref:
        clauses.append('brand_ref = %s')
        params.append(brand_ref)
    if status:
        clauses.append('status = %s')
        params.append(status)
    params.append(max(1, min(int(limit), 100)))
    return repository.rows(f'''SELECT id, title, thesis, editorial_score, paid_score, quadrant, status,
                                      geo_scores, brand_ref, project_ref, created_at
                                 FROM cadu_radar_opportunities
                                WHERE {' AND '.join(clauses)}
                             ORDER BY created_at DESC LIMIT %s''', tuple(params))
