"""Radares como investigações: um radar ativo e todas as suas execuções, ou uma busca avulsa (uma só execução).

Cada execução guarda sinais e ângulos. O que muda de uma para outra (sinais com link novo, ângulos com título novo) é
calculado aqui, assim como o que a pessoa ainda não viu. Estado de investigação (andando, agendado, falhou...) e estado de
leitura (novo, com novidades, sem novidades) são propriedades independentes.
"""
from __future__ import annotations

from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository
from . import pipeline, watches

RUN_LIMIT = 300
ACTIVE = ('running', 'queued')


def state_available():
    rows = repository.rows("SELECT to_regclass('public.cadu_radar_user_state') IS NOT NULL AS ok")
    return bool(rows and rows[0]['ok'])


def schedule_label(frequency):
    hours = watches.RUN_HOURS.get(int(frequency or 1), watches.RUN_HOURS[1])
    return f"{'Diário' if len(hours) == 1 else f'{len(hours)}x ao dia'} · {' e '.join(f'{hour:02d}h' for hour in hours)}"


def _key(url):
    return str(url or '').strip().lower().rstrip('/')


def _seen_before(group, seen_at):
    """Execuções que a pessoa já tinha à vista na última visita (sem a mais recente, que é a que se compara)."""
    return [run for run in group[1:] if seen_at and run['created_at'] <= seen_at]


def _novelty(latest, baseline):
    """Sinais com link e ângulos com título que nenhuma execução da referência tinha."""
    urls = {_key(row['url']) for run in baseline for row in run['signal_rows']}
    titles = {row['title'].strip().lower() for run in baseline for row in run['angle_rows']}
    return ([row for row in latest['signal_rows'] if _key(row['url']) not in urls],
            [row for row in latest['angle_rows'] if row['title'].strip().lower() not in titles])


def reading_state(*, state_row, latest, new_signals, new_angles):
    """Estado de leitura: novo (nunca aberto), atualizado, sem novidades, em execução, atenção ou nada a destacar."""
    if latest['status'] in ACTIVE:
        return 'running'
    if latest['status'] == 'failed' or latest.get('broken_sources'):
        return 'attention'
    seen_at = (state_row or {}).get('last_seen_at')
    if not seen_at:
        return 'new'
    if latest['created_at'] > seen_at:
        return 'updated' if (new_signals or new_angles) else 'nochange'
    return 'seen'


def _load(client_id):
    runs = pipeline.list_runs(client_id, limit=RUN_LIMIT)
    ids = [str(run['id']) for run in runs]
    signals, angles = {}, {}
    if ids:
        for row in repository.rows('SELECT run_id, url, source, verification FROM cadu_radar_signals WHERE run_id = ANY(%s::uuid[])', (ids,)):
            signals.setdefault(str(row['run_id']), []).append(row)
        for row in repository.rows('SELECT run_id, title FROM cadu_radar_opportunities WHERE run_id = ANY(%s::uuid[])', (ids,)):
            angles.setdefault(str(row['run_id']), []).append(row)
    for run in runs:
        run['signal_rows'] = [{'url': row['url'], 'source': row['source'], 'ok': (row.get('verification') or {}).get('url_status') in ('ok', 'bloqueado')}
                              for row in signals.get(str(run['id']), [])]
        run['angle_rows'] = [{'title': row['title']} for row in angles.get(str(run['id']), [])]
    return runs


def _user_state(client_id, user_id):
    if not state_available():
        return {}
    rows = repository.rows('SELECT subject_id, last_seen_at, favorite FROM cadu_radar_user_state WHERE client_id = %s AND user_id = %s',
                           (int(client_id), int(user_id)))
    return {str(row['subject_id']): row for row in rows}


def _summary(run):
    return {'id': str(run['id']), 'status': run['status'], 'created_at': run['created_at'], 'finished_at': run.get('finished_at'),
            'error': run.get('error'), 'trigger': run.get('trigger'), 'tokens': run.get('tokens', 0),
            'signals': len(run['signal_rows']), 'sources': len({row['source'] for row in run['signal_rows'] if row['ok']}),
            'angles': len(run['angle_rows']), 'in_plan': int(run.get('in_plan') or 0),
            'broken_sources': int(run.get('broken_sources') or 0)}


def _build(subject_id, kind, group, watch, state_row):
    """``group``: execuções do radar, da mais recente para a mais antiga."""
    latest = group[0]
    seen_at = (state_row or {}).get('last_seen_at')
    baseline = _seen_before(group, seen_at)
    unseen_run = bool(seen_at) and latest['created_at'] > seen_at
    new_signals, new_angles = _novelty(latest, baseline) if unseen_run and baseline and latest['status'] == 'done' else ([], [])
    summary = _summary(latest)
    state = reading_state(state_row=state_row, latest={**latest, **summary}, new_signals=new_signals, new_angles=new_angles)
    title = (watch or {}).get('name') or latest.get('focus') or ''
    schedule = None
    if watch:
        schedule = {'status': watch['status'], 'frequency': watch['frequency'], 'label': schedule_label(watch['frequency']),
                    'last_run_at': watch.get('last_run_at'), 'next_run_at': watch.get('next_run_at')}
    if latest['status'] in ACTIVE:
        phase = 'em_execucao'
    elif latest['status'] == 'failed' or (watch and watch['status'] == 'sem_credito'):
        phase = 'falha'
    elif watch and watch['status'] == 'ativo':
        phase = 'programado'
    elif watch:
        phase = 'pausado'
    else:
        phase = 'concluido'
    return {'id': str(subject_id), 'kind': kind, 'title': title, 'focus': latest.get('focus') or '', 'brand_ref': latest.get('brand_ref'), 'project_ref': latest.get('project_ref'),
            'params': latest.get('params') or {}, 'schedule': schedule, 'phase': phase, 'reading': state,
            'executions': len(group), 'latest': summary, 'favorite': bool((state_row or {}).get('favorite')),
            'changes': {'signals': len(new_signals), 'angles': len(new_angles)}, 'last_seen_at': seen_at,
            'created_at': group[-1]['created_at'], 'activity_at': latest['created_at']}


def _watches_available():
    from . import repository as radar
    return radar.watches_available()


def _groups(client_id):
    """Execuções agrupadas por radar (da mais recente para a mais antiga) e os radares ativos por id."""
    runs = _load(client_id)
    watch_rows = {str(row['id']): row for row in watches.list_watches(client_id)} if _watches_available() else {}
    groups = {}
    for run in runs:
        key = str(run['watch_id']) if run.get('watch_id') and str(run['watch_id']) in watch_rows else str(run['id'])
        groups.setdefault(key, []).append(run)
    return groups, watch_rows


def list_radars(client_id, user_id):
    groups, watch_rows = _groups(client_id)
    state = _user_state(client_id, user_id)
    radars = [_build(key, 'watch' if key in watch_rows else 'single', group, watch_rows.get(key), state.get(key)) for key, group in groups.items()]
    radars.sort(key=lambda item: item['activity_at'], reverse=True)
    return radars


def get_radar(client_id, user_id, radar_id):
    """O radar com o histórico de execuções, a última execução completa e o que mudou desde a última visita."""
    groups, watch_rows = _groups(client_id)
    key = str(radar_id)
    if key not in groups:
        raise NotFound('Radar indisponível.')
    group = groups[key]
    radar = _build(key, 'watch' if key in watch_rows else 'single', group, watch_rows.get(key), _user_state(client_id, user_id).get(key))
    history = []
    for index, run in enumerate(group):
        earlier = group[index + 1] if index + 1 < len(group) else None
        item = _summary(run)
        item['new_signals'], item['new_angles'] = (len(part) for part in _novelty(run, [earlier])) if earlier else (None, None)
        history.append(item)
    latest = pipeline.get_run(client_id, group[0]['id'])
    changed = {'signals': [], 'angles': []}
    seen_at = radar['last_seen_at']
    baseline = _seen_before(group, seen_at)
    if latest and latest['status'] == 'done' and baseline and group[0]['created_at'] > seen_at:
        urls = {_key(row['url']) for run in baseline for row in run['signal_rows']}
        titles = {row['title'].strip().lower() for run in baseline for row in run['angle_rows']}
        changed = {'signals': [item['id'] for item in latest['signals'] if _key(item['url']) not in urls],
                   'angles': [item['id'] for item in latest['opportunities'] if item['title'].strip().lower() not in titles]}
    return {'radar': radar, 'history': history, 'run': latest, 'changed': changed}


def _subject(client_id, radar_id):
    """Radar ativo ou execução avulsa do cliente; o id vira a chave do estado de leitura."""
    if _watches_available() and repository.rows('SELECT 1 FROM cadu_radar_watches WHERE id = %s AND client_id = %s', (str(radar_id), int(client_id))):
        return str(radar_id)
    if repository.rows('SELECT 1 FROM cadu_radar_runs WHERE id = %s AND client_id = %s', (str(radar_id), int(client_id))):
        return str(radar_id)
    raise NotFound('Radar indisponível.')


def mark_seen(client_id, user_id, radar_id):
    if not state_available():
        raise BadRequest('Aplique a migration do Radar (add_cadu_radar_v4.sql) para guardar o que você já viu.')
    subject = _subject(client_id, radar_id)
    from .db import transaction
    with transaction() as cur:
        cur.execute('''INSERT INTO cadu_radar_user_state (client_id, user_id, subject_id, last_seen_at) VALUES (%s, %s, %s, NOW())
                       ON CONFLICT (user_id, subject_id) DO UPDATE SET last_seen_at = NOW(), updated_at = NOW()''',
                    (int(client_id), int(user_id), subject))


def set_favorite(client_id, user_id, radar_id, favorite):
    if not state_available():
        raise BadRequest('Aplique a migration do Radar (add_cadu_radar_v4.sql) para favoritar radares.')
    subject = _subject(client_id, radar_id)
    from .db import transaction
    with transaction() as cur:
        cur.execute('''INSERT INTO cadu_radar_user_state (client_id, user_id, subject_id, favorite) VALUES (%s, %s, %s, %s)
                       ON CONFLICT (user_id, subject_id) DO UPDATE SET favorite = EXCLUDED.favorite, updated_at = NOW()''',
                    (int(client_id), int(user_id), subject, bool(favorite)))
    return bool(favorite)
