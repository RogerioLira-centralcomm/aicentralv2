"""Leituras do Radar. Escritas entram com o pipeline (Fase 3)."""
from __future__ import annotations

from psycopg.types.json import Json

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


def _plan_columns():
    rows = repository.rows("""SELECT column_name FROM information_schema.columns WHERE table_schema = 'public'
                               AND table_name = 'cadu_planner_plans' AND column_name IN ('opportunity_id', 'signal_id')""")
    return {row['column_name'] for row in rows}


def create_plan_from_signal(client_id, actor_id, signal_id, context):
    """Nasce um planejamento da notícia: ela entra como briefing, com fonte, data, link e o radar que a achou."""
    from werkzeug.exceptions import BadRequest, NotFound
    from ..cadu_planner import plans
    from .db import transaction
    if 'signal_id' not in _plan_columns():
        raise BadRequest('Aplique a migration do Radar (add_cadu_radar_v3.sql) antes de criar planos a partir de notícias.')
    rows = repository.rows('''SELECT s.id, s.headline, s.description, s.source, s.url, s.published_at, r.focus, r.brand_ref, r.project_ref, r.params
                                FROM cadu_radar_signals s LEFT JOIN cadu_radar_runs r ON r.id = s.run_id
                               WHERE s.id = %s AND s.client_id = %s''', (str(signal_id), int(client_id)))
    if not rows:
        raise NotFound('Notícia indisponível.')
    item = rows[0]
    when = item['published_at'].strftime('%d/%m/%Y') if item.get('published_at') else ''
    angles = repository.rows("""SELECT title FROM cadu_radar_opportunities WHERE client_id = %s AND signal_ids @> %s::jsonb ORDER BY created_at""",
                             (int(client_id), Json([str(item['id'])])))
    notes = '\n'.join(part for part in [
        item['headline'], item.get('description'),
        f"Fonte: {item.get('source') or 'não informada'}{f' ({when})' if when else ''}{f' · {item['url']}' if item.get('url') else ''}",
        f"Radar: {item['focus']}" if item.get('focus') else '',
        f"Ângulos que esta notícia sustenta: {'; '.join(angle['title'] for angle in angles)}" if angles else ''] if part)
    places = ((item.get('params') or {}).get('places') or '')[:120]
    plan = plans.create_plan(client_id, actor_id, {
        'title': item['headline'][:180], 'objective': 'awareness',
        'briefing': {'notes': notes[:2000], 'geography': places},
        'brand_ref': item.get('brand_ref'), 'project_ref': item.get('project_ref')}, context)
    with transaction() as cur:
        cur.execute("UPDATE cadu_planner_plans SET source = 'radar', signal_id = %s WHERE id = %s", (str(item['id']), str(plan['id'])))
    return plans.get_plan(client_id, actor_id, plan['id'])


def plans_for(client_id, *, signal_ids=(), opportunity_ids=()):
    """Planos que nasceram dessas notícias ou ângulos: id, título, estado e a que eles se ligam."""
    columns = _plan_columns()
    clauses, params = [], []
    if 'signal_id' in columns and signal_ids:
        clauses.append('signal_id = ANY(%s::uuid[])')
        params.append([str(value) for value in signal_ids])
    if 'opportunity_id' in columns and opportunity_ids:
        clauses.append('opportunity_id = ANY(%s::uuid[])')
        params.append([str(value) for value in opportunity_ids])
    if not clauses:
        return []
    return repository.rows(f'''SELECT id, title, status, signal_id, opportunity_id, created_at FROM cadu_planner_plans
                                 WHERE client_id = %s AND ({' OR '.join(clauses)}) ORDER BY created_at DESC''', (int(client_id), *params))
