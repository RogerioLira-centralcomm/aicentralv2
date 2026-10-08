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


def _br_date(value):
    year, month, day = str(value).split('-')
    return f'{day}/{month}/{year}'


def plan_payload(item):
    """Plano que nasce do ângulo. Mídia (1.6) traz objetivo, período, praças e público; os demais, só o briefing em texto."""
    breakdown = item.get('score_breakdown') or {}
    is_media = breakdown.get('type') == 'midia'
    places = [place.get('place') for place in item.get('geo_scores') or [] if place.get('place')]
    # Sem tipo (1.5): o ângulo é uma ideia a levar às pessoas, então o plano começa em consideração.
    objective = breakdown.get('objective') if is_media and breakdown.get('objective') else \
        {'conteudo': 'awareness', 'integrada': 'consideracao', 'midia': 'consideracao'}.get(item.get('quadrant'), 'consideracao')
    period = breakdown.get('period') or {}
    buzz = [f"{entry.get('assunto')} ({entry.get('veiculo')}, {entry.get('data')}): {entry.get('url')}" for entry in breakdown.get('buzz') or []]
    media = [f"{entry.get('name')} ({entry.get('formato')}): {entry.get('por_que')}" for entry in breakdown.get('media') or []] if is_media else []
    notes = '\n'.join(part for part in [
        item.get('thesis'), f"Por que agora: {breakdown['why_now']}" if breakdown.get('why_now') else '',
        f"Público: {breakdown['audience']}" if is_media and breakdown.get('audience') else '',
        f"Mensagem: {breakdown['message']}" if is_media and breakdown.get('message') else '',
        f"Janela: {breakdown['window']}" if breakdown.get('window') else '',
        'Canais sugeridos pelo Radar (já no plano, para revisar):\n' + '\n'.join(f'- {line}' for line in media) if media else '',
        f"Formatos sugeridos pelo Radar: {', '.join(breakdown.get('formats') or [])}" if not is_media and breakdown.get('formats') else '',
        f"Canais sugeridos pelo Radar: {', '.join(breakdown.get('channels') or [])}" if not is_media and breakdown.get('channels') else '',
        'Notícias que sustentam:\n' + '\n'.join(f'- {line}' for line in buzz) if buzz else ''] if part)
    briefing = {'notes': notes[:2000], 'geography': ((breakdown.get('places') if is_media else '') or ', '.join(places))[:120]}
    if is_media and period.get('inicio') and period.get('fim'):
        briefing['period'] = f"{_br_date(period['inicio'])} a {_br_date(period['fim'])}"
    return {'title': item['title'][:180], 'objective': objective, 'briefing': briefing,
            'brand_ref': item.get('brand_ref'), 'project_ref': item.get('project_ref')}


def create_plan(client_id, actor_id, opportunity_id, context):
    """Nasce um planejamento a partir do ângulo; os canais de um ângulo de mídia entram como itens do plano."""
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
    media = breakdown.get('media') if breakdown.get('type') == 'midia' else []
    plan = plans.create_plan(client_id, actor_id, plan_payload(item), context)
    from ..cadu_planner import catalog
    added = []
    for entry in media or []:
        # Canal sugerido entra como item do plano, marcado como sugestão do Radar para o planejador revisar.
        try:
            snapshot = catalog.client_detail('canais', str(entry['id']))
        except NotFound:  # canal saiu do catálogo depois da busca: fica só no briefing
            continue
        added.append((str(entry['id']), {**snapshot, 'radar': {'formato': entry.get('formato'), 'por_que': entry.get('por_que')}}))
    with transaction() as cur:
        for resource_id, snapshot in added:
            cur.execute('''INSERT INTO cadu_planner_plan_items (plan_id, kind, resource_id, snapshot) VALUES (%s, 'canais', %s, %s)
                           ON CONFLICT (plan_id, kind, resource_id) DO NOTHING''', (str(plan['id']), resource_id, Json(snapshot)))
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


def plans_for(client_id, *, signal_ids=(), opportunity_ids=(), plan_ids=()):
    """Planos que nasceram dessas notícias ou ângulos (ou que receberam contexto deles): id, título, estado e o vínculo."""
    columns = _plan_columns()
    clauses, params = [], []
    if plan_ids:
        clauses.append('id = ANY(%s::uuid[])')
        params.append([str(value) for value in plan_ids])
    if 'signal_id' in columns and signal_ids:
        clauses.append('signal_id = ANY(%s::uuid[])')
        params.append([str(value) for value in signal_ids])
    if 'opportunity_id' in columns and opportunity_ids:
        clauses.append('opportunity_id = ANY(%s::uuid[])')
        params.append([str(value) for value in opportunity_ids])
    if not clauses:
        return []
    signal_col = 'signal_id' if 'signal_id' in columns else 'NULL::uuid AS signal_id'
    opp_col = 'opportunity_id' if 'opportunity_id' in columns else 'NULL::uuid AS opportunity_id'
    return repository.rows(f'''SELECT id, title, status, {signal_col}, {opp_col}, created_at FROM cadu_planner_plans
                                 WHERE client_id = %s AND ({' OR '.join(clauses)}) ORDER BY created_at DESC''', (int(client_id), *params))


def set_pauta(client_id, opportunity_id, saved):
    from werkzeug.exceptions import NotFound
    from .db import transaction
    with transaction() as cur:
        cur.execute("""UPDATE cadu_radar_opportunities SET status = %s, updated_at = NOW()
                        WHERE id = %s AND client_id = %s AND status <> 'em_plano' RETURNING status""",
                    ('salva' if saved else 'nova', str(opportunity_id), int(client_id)))
        row = cur.fetchone()
    if row:
        return row['status']
    rows = repository.rows('SELECT status FROM cadu_radar_opportunities WHERE id = %s AND client_id = %s', (str(opportunity_id), int(client_id)))
    if not rows:
        raise NotFound('Ângulo indisponível.')
    return rows[0]['status']


def intel_block(item, focus=''):
    """Bloco "Contexto do Radar" que um ângulo de inteligência acrescenta ao briefing de um plano."""
    detail = item.get('score_breakdown') or {}
    sources = '; '.join(f"{entry.get('assunto')} ({entry.get('veiculo') or entry.get('domain')}, {entry.get('data')}): {entry.get('url')}"
                        for entry in detail.get('buzz') or [])
    return '\n'.join(part for part in [
        f"Contexto do Radar{f' ({focus})' if focus else ''}: {item.get('title')}",
        item.get('thesis'),
        f"O que muda para a marca: {detail['impact']}" if detail.get('impact') else '',
        f"O que acompanhar: {detail['watch']}" if detail.get('watch') else '',
        f"Fontes: {sources}" if sources else ''] if part)


def brief_plan(client_id, actor_id, opportunity_id, plan_id, context):
    """Leva um ângulo de inteligência ao briefing de um plano (ou de um plano novo) sem apagar o que já está lá."""
    from werkzeug.exceptions import BadRequest, NotFound
    from ..cadu_planner import plans
    from .db import transaction
    rows = repository.rows('''SELECT o.id, o.title, o.thesis, o.score_breakdown, o.geo_scores, o.quadrant, o.brand_ref, o.project_ref, r.focus
                                FROM cadu_radar_opportunities o LEFT JOIN cadu_radar_runs r ON r.id = o.run_id
                               WHERE o.id = %s AND o.client_id = %s''', (str(opportunity_id), int(client_id)))
    if not rows:
        raise NotFound('Ângulo indisponível.')
    item = rows[0]
    block = intel_block(item, item.get('focus') or '')
    if plan_id:
        plan = plans.get_plan(client_id, actor_id, plan_id)
        briefing = dict(plan.get('briefing') or {})
        notes = str(briefing.get('notes') or '').strip()
        if block in notes:
            return plan
        joined = f'{notes}\n\n{block}' if notes else block
        if len(joined) > plans.BRIEFING_LIMITS['notes']:
            raise BadRequest('O briefing deste plano está cheio. Abra o plano e resuma as notas antes de trazer mais contexto.')
        briefing['notes'] = joined
        with transaction() as cur:
            cur.execute('UPDATE cadu_planner_plans SET briefing = %s, updated_at = NOW() WHERE id = %s AND client_id = %s',
                        (Json(briefing), str(plan['id']), int(client_id)))
    else:
        payload = plan_payload(item)
        payload['briefing']['notes'] = block[:plans.BRIEFING_LIMITS['notes']]
        plan = plans.create_plan(client_id, actor_id, payload, context)
    with transaction() as cur:
        # O ângulo guarda para quais planos foi levado: aparece em "Planos relacionados" e o botão mostra que já foi.
        cur.execute('''UPDATE cadu_radar_opportunities
                          SET score_breakdown = jsonb_set(score_breakdown, '{briefed_plans}',
                                  COALESCE(score_breakdown->'briefed_plans', '[]'::jsonb) || to_jsonb(%s::text), TRUE),
                              updated_at = NOW()
                        WHERE id = %s AND NOT COALESCE(score_breakdown->'briefed_plans', '[]'::jsonb) ? %s''',
                    (str(plan['id']), str(item['id']), str(plan['id'])))
    return plans.get_plan(client_id, actor_id, plan['id'])


def list_pautas(client_id):
    """Pautas salvas de todos os radares do cliente, da mais recente para a mais antiga."""
    if not available():
        return []
    return repository.rows('''SELECT o.id, o.title, o.thesis, o.score_breakdown, o.brand_ref, o.project_ref, o.updated_at, o.run_id,
                                      r.focus, r.watch_id
                                 FROM cadu_radar_opportunities o LEFT JOIN cadu_radar_runs r ON r.id = o.run_id
                                WHERE o.client_id = %s AND o.status = 'salva'
                             ORDER BY o.updated_at DESC LIMIT 100''', (int(client_id),))
