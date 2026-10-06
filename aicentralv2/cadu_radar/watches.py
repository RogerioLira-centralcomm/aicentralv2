"""Radares ativos: a mesma busca do wizard, repetida de 1 a 3 vezes por dia pelo agendador.

Cada rodada é um run normal (``trigger='agendado'``), cobrado do dono do radar com a
mesma etiqueta de créditos. Sem saldo, o radar vai para ``sem_credito`` e para de
tentar até alguém retomá-lo.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository
from . import pipeline

logger = logging.getLogger(__name__)

TZ = ZoneInfo('America/Sao_Paulo')
# Horários de Brasília por frequência: manhã, depois tarde, depois fim do dia.
RUN_HOURS = {1: (8,), 2: (8, 17), 3: (8, 13, 18)}
MAX_ACTIVE_PER_CLIENT = 10
COLUMNS = '''id, client_id, owner_id, brand_ref, project_ref, name, focus, params, frequency, min_score, status,
             next_run_at, last_run_at, last_run_id, created_at'''


def next_run_at(frequency, after=None):
    """Próximo horário de rodada depois de ``after``, em UTC."""
    hours = RUN_HOURS.get(int(frequency), RUN_HOURS[1])
    local = (after or datetime.now(timezone.utc)).astimezone(TZ)
    for day in range(3):
        for hour in hours:
            candidate = datetime.combine(local.date() + timedelta(days=day), time(hour), tzinfo=TZ)
            if candidate > local:
                return candidate.astimezone(timezone.utc)
    raise RuntimeError('Sem próximo horário.')  # inalcançável: sempre há uma rodada nas próximas 24 h


def _name(focus, brand_ref, params):
    base = focus or ', '.join(params.get('lenses') or []) or 'Radar da marca'
    return ' '.join(str(base).split())[:160]


def list_watches(client_id):
    rows = repository.rows(f'''SELECT {COLUMNS}, (SELECT COUNT(*) FROM cadu_radar_runs r WHERE r.watch_id = w.id) AS runs
                                 FROM cadu_radar_watches w WHERE client_id = %s
                             ORDER BY (status = 'ativo') DESC, created_at DESC''', (int(client_id),))
    return rows


def create_watch(client_id, owner_id, *, focus='', brand_ref=None, project_ref=None, params=None, frequency=1, min_score=70):
    params = pipeline.clean_params(params)
    focus = ' '.join(str(focus or '').split())[:240]
    if len(focus) < 3 and not (brand_ref or project_ref):
        raise BadRequest('Diga o tema ou escolha uma marca para o radar acompanhar.')
    try:
        frequency = max(1, min(3, int(frequency)))
        min_score = max(0, min(100, int(min_score)))
    except (TypeError, ValueError):
        raise BadRequest('Frequência inválida.') from None
    active = repository.rows('''SELECT COUNT(*) AS total FROM cadu_radar_watches WHERE client_id = %s AND status <> 'pausado' ''',
                             (int(client_id),))[0]['total']
    if active >= MAX_ACTIVE_PER_CLIENT:
        raise BadRequest(f'Seu limite é de {MAX_ACTIVE_PER_CLIENT} radares ativos. Pause um para criar outro.')
    watch_id = str(uuid4())
    with repository.get_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO cadu_radar_watches (id, client_id, owner_id, brand_ref, project_ref, name, focus, params,
                                                       frequency, min_score, status, next_run_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ativo', %s)''',
                    (watch_id, int(client_id), int(owner_id), brand_ref, project_ref, _name(focus, brand_ref, params),
                     focus or None, Json(params), frequency, min_score, next_run_at(frequency)))
    return get_watch(client_id, watch_id)


def get_watch(client_id, watch_id):
    rows = repository.rows(f'SELECT {COLUMNS} FROM cadu_radar_watches WHERE id = %s AND client_id = %s',
                           (str(watch_id), int(client_id)))
    if not rows:
        raise NotFound('Radar indisponível.')
    return rows[0]


def update_watch(client_id, watch_id, *, status=None, frequency=None):
    watch = get_watch(client_id, watch_id)
    sets, params = ['updated_at = NOW()'], []
    new_frequency = watch['frequency']
    if frequency is not None:
        try:
            new_frequency = max(1, min(3, int(frequency)))
        except (TypeError, ValueError):
            raise BadRequest('Frequência inválida.') from None
        sets.append('frequency = %s')
        params.append(new_frequency)
    if status is not None:
        if status not in ('ativo', 'pausado'):
            raise BadRequest('Estado inválido.')
        sets.append('status = %s')
        params.append(status)
    if (status == 'ativo' and watch['status'] != 'ativo') or frequency is not None:
        sets.append('next_run_at = %s')
        params.append(next_run_at(new_frequency))
    params.extend([str(watch_id), int(client_id)])
    with repository.get_db() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE cadu_radar_watches SET {', '.join(sets)} WHERE id = %s AND client_id = %s", params)
    return get_watch(client_id, watch_id)


def delete_watch(client_id, watch_id):
    get_watch(client_id, watch_id)
    with repository.get_db() as conn, conn.cursor() as cur:
        # As consultas já feitas continuam no histórico, só perdem o vínculo.
        cur.execute('UPDATE cadu_radar_runs SET watch_id = NULL WHERE watch_id = %s', (str(watch_id),))
        cur.execute('DELETE FROM cadu_radar_watches WHERE id = %s AND client_id = %s', (str(watch_id), int(client_id)))


def run_due(limit=3):
    """Roda, uma a uma e na própria linha de comando, os radares que chegaram no horário."""
    from ..cadu_tool_billing import InsufficientToolCredits
    results = []
    for _ in range(max(1, int(limit))):
        with repository.get_db() as conn, conn.cursor() as cur:
            # Dois agendadores ao mesmo tempo não pegam o mesmo radar.
            cur.execute(f'''SELECT {COLUMNS} FROM cadu_radar_watches WHERE status = 'ativo' AND next_run_at <= NOW()
                            ORDER BY next_run_at LIMIT 1 FOR UPDATE SKIP LOCKED''')
            watch = cur.fetchone()
            if not watch:
                break
            cur.execute('UPDATE cadu_radar_watches SET next_run_at = %s, last_run_at = NOW() WHERE id = %s',
                        (next_run_at(watch['frequency']), str(watch['id'])))
        outcome = {'watch': str(watch['id']), 'status': 'ok'}
        try:
            run = pipeline.start_run(watch['client_id'], watch['owner_id'], focus=watch['focus'] or '', brand_ref=watch['brand_ref'],
                                     project_ref=watch['project_ref'], params=watch['params'], background=False,
                                     trigger='agendado', watch_id=str(watch['id']))
            outcome['run'] = str(run['id'])
            outcome['status'] = run['status']
            with repository.get_db() as conn, conn.cursor() as cur:
                cur.execute('UPDATE cadu_radar_watches SET last_run_id = %s WHERE id = %s', (str(run['id']), str(watch['id'])))
        except InsufficientToolCredits:
            outcome['status'] = 'sem_credito'
            with repository.get_db() as conn, conn.cursor() as cur:
                cur.execute("UPDATE cadu_radar_watches SET status = 'sem_credito', next_run_at = NULL WHERE id = %s", (str(watch['id']),))
        except BadRequest as exc:
            outcome['status'] = f'pulado: {exc.description}'
        except Exception:  # noqa: BLE001 — um radar com problema não impede os outros
            logger.exception('Radar agendado %s falhou', watch['id'])
            outcome['status'] = 'erro'
        results.append(outcome)
    return results
