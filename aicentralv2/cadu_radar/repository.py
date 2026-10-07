"""Leituras do Radar. Escritas entram com o pipeline (Fase 3)."""
from __future__ import annotations

from ..cadu_family import repository


def available() -> bool:
    result = repository.rows("SELECT to_regclass('public.cadu_radar_opportunities') IS NOT NULL AS available")
    return bool(result and result[0]['available'])


def watches_available() -> bool:
    result = repository.rows("SELECT to_regclass('public.cadu_radar_watches') IS NOT NULL AS available")
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


def create_plan(client_id, actor_id, opportunity_id, context):
    """Nasce um planejamento a partir da oportunidade: tese vira briefing, praças viram geografia."""
    from werkzeug.exceptions import NotFound
    from ..cadu_planner import plans
    from .db import transaction
    rows = repository.rows('''SELECT id, title, thesis, geo_scores, score_breakdown, brand_ref, project_ref, quadrant
                                FROM cadu_radar_opportunities WHERE id = %s AND client_id = %s''',
                           (str(opportunity_id), int(client_id)))
    if not rows:
        raise NotFound('Oportunidade indisponível.')
    item = rows[0]
    breakdown = item.get('score_breakdown') or {}
    places = [place.get('place') for place in item.get('geo_scores') or [] if place.get('place')]
    # Radar 1.5 has no quadrant: an angle is an idea to put in front of people, so the plan starts as consideration.
    objective = {'conteudo': 'awareness', 'integrada': 'consideracao', 'midia': 'consideracao'}.get(item.get('quadrant'), 'consideracao')
    buzz = [f"{entry.get('assunto')} ({entry.get('veiculo')}, {entry.get('data')})" for entry in breakdown.get('buzz') or []]
    notes = '\n'.join(part for part in [
        item.get('thesis'), f"Por que agora: {breakdown['why_now']}" if breakdown.get('why_now') else '',
        f"Buzz que sustenta: {'; '.join(buzz)}" if buzz else '',
        f"Janela: {breakdown['window']}" if breakdown.get('window') else '',
        f"Formatos sugeridos pelo Radar: {', '.join(breakdown.get('formats') or [])}" if breakdown.get('formats') else '',
        f"Canais sugeridos pelo Radar: {', '.join(breakdown.get('channels') or [])}" if breakdown.get('channels') else ''] if part)
    plan = plans.create_plan(client_id, actor_id, {
        'title': item['title'][:180], 'objective': objective,
        'briefing': {'notes': notes[:2000], 'geography': ', '.join(places)[:120]},
        'brand_ref': item.get('brand_ref'), 'project_ref': item.get('project_ref')}, context)
    with transaction() as cur:
        if plans._cobuild_available():
            cur.execute("UPDATE cadu_planner_plans SET source = 'radar', opportunity_id = %s WHERE id = %s",
                        (str(item['id']), str(plan['id'])))
        cur.execute("UPDATE cadu_radar_opportunities SET status = 'em_plano', updated_at = NOW() WHERE id = %s", (str(item['id']),))
    return plans.get_plan(client_id, actor_id, plan['id'])
