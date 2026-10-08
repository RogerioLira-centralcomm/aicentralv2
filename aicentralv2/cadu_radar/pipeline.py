"""Pipeline do Radar (versão 1.5): o que está em buzz agora e os ângulos para falar de um conceito.

    buzz     uma busca do Perplexity (OpenRouter): assuntos em alta sobre o conceito, com data, veículo e link
    check    só fica o que tem data dentro da janela e link que abre; cada fonte ganha o nível A/B/C da base curada
    angles   um modelo transforma o buzz em 3 a 5 ângulos para a marca falar do conceito
    save     grava o buzz (sinais) e os ângulos (oportunidades) para virarem plano

A base de fontes (``sources.py``) só classifica a fonte depois que ela foi achada: não restringe nem guia a busca.
Cada etapa grava status, detalhe e tokens em ``cadu_radar_runs.steps`` para a tela mostrar o andamento. Créditos:
reserva pelo custo em US$ antes de começar e cobrança por chamada, com chave idempotente por run e etapa.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import current_app
from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest

from . import prompts, sources as source_base, time_saved
from .db import transaction
from .research import check_url, json_loads, parse_date

logger = logging.getLogger(__name__)

STEPS = (
    ('buzz', 'Procurando o que está em alta', 'O Perplexity busca o que está gerando buzz agora sobre o conceito.'),
    ('check', 'Conferindo as fontes', 'Só entra o que tem data recente e link que abre.'),
    ('angles', 'Montando os ângulos', 'Ideias para a marca falar do conceito aproveitando o buzz.'),
    ('save', 'Organizando o resultado', 'O buzz e os ângulos ficam salvos para virar plano.'),
)
PARALLEL = ()
PROMPTS = '1.5'
MAX_BUZZ, MAX_ANGLES = 8, 5
# Custo típico no teste real: ~US$ 0,03 por busca. A reserva dá folga, mas é em US$, não em tokens fixos.
ESTIMATE_USD = 0.10
STAGE_USD = {'buzz': 0.05, 'angles': 0.05}
RECENCY_DAYS = (7, 30, 60)
LEASE_MINUTES = 5
TZ = ZoneInfo('America/Sao_Paulo')


def models():
    from ..cadu_workspace import insights_research
    return {
        'buzz': os.getenv('CADU_RADAR_DISCOVER_MODEL', 'perplexity/sonar-pro'),
        'angles': os.getenv('CADU_RADAR_ANGLES_MODEL', insights_research.SYNTHESIS_MODEL),
    }


class RadarDisabled(RuntimeError):
    pass


def enabled() -> bool:
    return bool(current_app.config.get('CADU_RADAR_ENABLED'))


def clean_params(raw) -> dict:
    """Parâmetros do wizard, validados: nada além do que a busca sabe usar."""
    raw = raw if isinstance(raw, dict) else {}
    try:
        days = int(raw.get('recency_days') or 30)
    except (TypeError, ValueError):
        days = 30
    return {'places': ' '.join(str(raw.get('places') or '').split())[:120], 'recency_days': days if days in RECENCY_DAYS else 30}


def usd_to_tokens(client_id, usd) -> int:
    """Tokens Cadu equivalentes a um custo em US$, pelo preço comercial do cliente."""
    from ..cadu_credit_connector import CaduCreditConnector
    from ..cadu_tool_billing import cost_token_equivalent
    price = CaduCreditConnector()._commercial_token_price_usd(client_id)
    return cost_token_equivalent(usd, usd_per_credit_token=price)


def estimate_tokens(client_id) -> int:
    """Teto reservado antes do run (o gasto real costuma ser bem menor)."""
    return int(usd_to_tokens(client_id, ESTIMATE_USD))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _initial_steps(params=None):
    return [{'key': key, 'label': label, 'hint': hint, 'status': 'pending', 'tokens': 0, 'detail': '', 'parallel': False,
             'started_at': None, 'finished_at': None} for key, label, hint in STEPS]


def start_run(client_id, actor_id, *, focus='', brand_ref=None, project_ref=None, params=None,
              background=True, trigger='manual', watch_id=None):
    """Reserva créditos, grava o run e roda o pipeline (em segundo plano, ou inline para o agendador)."""
    from ..cadu_credit_connector import CaduCreditConnector, CreditActor
    from ..cadu_family import repository
    from . import repository as radar_repository
    if not enabled():
        raise RadarDisabled('O Radar de Oportunidades ainda não está habilitado neste ambiente.')
    if not radar_repository.available():
        raise BadRequest('Aplique a migration do Radar antes de rodar.')
    params = clean_params(params)
    focus = ' '.join(str(focus or '').split())[:240]
    if len(focus) < 3 and not (brand_ref or project_ref):
        raise BadRequest('Diga o tema ou escolha uma marca para o Radar procurar.')
    _expire_dead_runs(client_id)
    running = repository.rows('''SELECT id FROM cadu_radar_runs WHERE client_id = %s AND status IN ('queued', 'running')
                                    AND brand_ref IS NOT DISTINCT FROM %s LIMIT 1''', (int(client_id), brand_ref))
    if running:
        raise BadRequest('Já existe uma busca do Radar em andamento para esta marca. Aguarde ela terminar.')
    estimate = estimate_tokens(client_id)
    # Sem saldo para o teto, o run nem começa (409 na rota).
    CaduCreditConnector().authorize(CreditActor.from_values(client_id, actor_id), estimate)
    run_id = str(uuid4())
    with transaction() as cur:
        cur.execute('''INSERT INTO cadu_radar_runs (id, client_id, created_by, brand_ref, project_ref, status, steps, cost, focus,
                                                    params, trigger, watch_id, lease_until)
                       VALUES (%s, %s, %s, %s, %s, 'running', %s, %s, %s, %s, %s, %s, NOW() + make_interval(mins => %s))''',
                    (run_id, int(client_id), int(actor_id), brand_ref, project_ref, Json(_initial_steps(params)),
                     Json({'estimated_tokens': estimate, 'tokens': 0}), focus or None, Json(params), trigger, watch_id,
                     LEASE_MINUTES))
    app = current_app._get_current_object()

    def run():
        with app.app_context():
            try:
                Runner(run_id, int(client_id), int(actor_id), focus, brand_ref, project_ref, params).execute()
            except Exception as exc:  # noqa: BLE001 — o run registra a falha para a tela
                logger.exception('Radar run %s falhou', run_id)
                _finish(run_id, 'failed', error=_public_error(exc))

    if background:
        threading.Thread(target=run, daemon=True, name=f'cadu-radar-{run_id[:12]}').start()
    else:
        run()
    return get_run(client_id, run_id)


def _public_error(exc):
    from ..cadu_tool_billing import InsufficientToolCredits
    if isinstance(exc, InsufficientToolCredits):
        return 'Os créditos acabaram durante a busca. O que foi gasto até aqui está registrado.'
    return 'A busca não pôde ser concluída. Tente de novo em alguns minutos.'


def _db():
    from ..db import get_db
    return get_db()


def _update(run_id, **changes):
    sets, params = [], []
    for column, value in changes.items():
        sets.append(f'{column} = %s')
        params.append(Json(value) if isinstance(value, (dict, list)) else value)
    params.append(run_id)
    conn = _db()
    with conn.cursor() as cur:
        cur.execute(f"UPDATE cadu_radar_runs SET {', '.join(sets)} WHERE id = %s", params)
    conn.commit()


def _finish(run_id, status, error=None):
    conn = _db()
    with conn.cursor() as cur:
        cur.execute('''UPDATE cadu_radar_runs SET status = %s, error = %s, finished_at = NOW() WHERE id = %s''',
                    (status, error, run_id))
        if status == 'failed':
            cur.execute('SELECT steps FROM cadu_radar_runs WHERE id = %s', (run_id,))
            row = cur.fetchone()
            steps = [{**step, 'status': 'failed' if step['status'] == 'running' else
                      ('skipped' if step['status'] == 'pending' else step['status'])} for step in (row or {}).get('steps') or []]
            cur.execute('UPDATE cadu_radar_runs SET steps = %s WHERE id = %s', (Json(steps), run_id))
    conn.commit()


def _expire_dead_runs(client_id):
    """Um run cuja thread morreu (deploy, reinício) fica sem renovar o lease: vira falha em vez de travar a marca."""
    from ..cadu_family import repository
    with transaction() as cur:
        cur.execute('''UPDATE cadu_radar_runs SET status = 'failed', finished_at = NOW(),
                              error = 'A busca foi interrompida. Rode de novo.'
                        WHERE client_id = %s AND status IN ('queued', 'running')
                          AND COALESCE(lease_until, created_at + INTERVAL '20 minutes') < NOW()''', (int(client_id),))


def _host(url):
    return source_base.host(url) or url


def _short(value, limit):
    return ' '.join(str(value or '').split())[:limit]


class Runner:
    """Executa um run; cada etapa atualiza a linha do run assim que muda."""

    def __init__(self, run_id, client_id, actor_id, focus, brand_ref, project_ref, params=None):
        self.run_id, self.client_id, self.actor_id = run_id, client_id, actor_id
        self.focus, self.brand_ref, self.project_ref = focus, brand_ref, project_ref
        self.params = clean_params(params)
        self.steps = _initial_steps(self.params)
        self.lock = threading.Lock()
        self.models = models()
        now = datetime.now(timezone.utc)
        self.today = now.astimezone(TZ).date()
        self.since = now - timedelta(days=self.params['recency_days'])

    # ---- estado das etapas -------------------------------------------------
    def _step(self, key):
        return next(step for step in self.steps if step['key'] == key)

    def _save_steps(self):
        with self.lock:
            snapshot = [dict(step) for step in self.steps]
            tokens = sum(step['tokens'] for step in snapshot)
        conn = _db()
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_radar_runs SET steps = %s, cost = cost || %s::jsonb,
                                  lease_until = NOW() + make_interval(mins => %s) WHERE id = %s''',
                        (Json(snapshot), Json({'tokens': tokens}), LEASE_MINUTES, self.run_id))
        conn.commit()

    def _start(self, key):
        with self.lock:
            self._step(key).update(status='running', started_at=_now())
        self._save_steps()

    def _done(self, key, detail='', tokens=0, preview=None, status='done'):
        with self.lock:
            step = self._step(key)
            step.update(status=status, finished_at=_now(), detail=detail, tokens=int(step['tokens']) + int(tokens or 0))
            if preview is not None:
                step['preview'] = preview[:5]
        self._save_steps()

    # ---- chamadas pagas -----------------------------------------------------
    def _ai(self, stage, model, messages, max_tokens, json_mode=True, web=False):
        """Sempre pelo OpenRouter: cobrança pelo custo real em US$ (a OpenAI direta cobraria 1 token por token)."""
        from ..services.cadu_ai_connector import CaduAIConnector
        options = {'max_tokens': max_tokens, 'timeout': 150, 'temperature': 0.2, 'provider': 'openrouter'}
        if json_mode:
            options['response_format'] = {'type': 'json_object'}
        result = CaduAIConnector().complete(
            messages, client_id=self.client_id, user_id=self.actor_id,
            idempotency_key=f'radar:{self.run_id}:{stage}', app='Cadu Radar', stage=f'radar:{stage}',
            estimated_tokens=max(1, usd_to_tokens(self.client_id, STAGE_USD[stage])), model=model,
            metadata={'radar_run_id': self.run_id, 'stage': stage, 'prompt_version': PROMPTS, 'web': web}, **options)
        tokens = int(((result.get('cadu_charge') or {}).get('tokens_cobrados')) or 0)
        from ..services.openrouter_service import message_text
        return message_text(result.get('message')), tokens

    # ---- contexto -----------------------------------------------------------
    def _context(self):
        from ..cadu_planner.context import load_plan_context
        context = load_plan_context(self.client_id, self.brand_ref, self.project_ref)
        brand, project = context.get('brand') or {}, context.get('project') or {}
        facts = [f"{item['label']}: {item['value']}" for item in (brand.get('fields') or []) + (project.get('fields') or []) if item.get('value')]
        return {'brand': brand.get('name'), 'sector': brand.get('sector'), 'project': project.get('name'),
                'site': brand.get('website_url') or '', 'facts': facts[:14]}

    def _topic(self, ctx):
        parts = [self.focus, ctx.get('brand'), ctx.get('sector')]
        return ' '.join(part for part in parts if part)[:240]

    # ---- etapas --------------------------------------------------------------
    def _buzz(self, ctx, topic):
        """Uma busca com o Perplexity; só entra o que tem data dentro da janela (hoje é a data real, não a do treino)."""
        self._start('buzz')
        text, tokens = self._ai('buzz', self.models['buzz'], prompts.messages(
            'buzz', PROMPTS, today=self.today.isoformat(), since=self.since.date().isoformat(), topic=topic,
            places=self.params['places'] or 'Brasil', brand_facts='; '.join(ctx['facts']) or 'não informado'),
            max_tokens=3000, json_mode=False, web=True)
        found = json_loads(text).get('buzz') or []
        kept, seen = [], set()
        horizon = datetime.now(timezone.utc) + timedelta(days=2)
        for item in found if isinstance(found, list) else []:
            if not isinstance(item, dict):
                continue
            url = str(item.get('url') or '').strip()
            when = parse_date(item.get('data'))
            key = url.split('#')[0].rstrip('/')
            # Sem link, sem data, fora da janela ou do futuro: não vira buzz. Data ausente é descartada de propósito:
            # página sem data costuma ser antiga.
            if not url.startswith('http') or key in seen or when is None or not (self.since <= when <= horizon):
                continue
            seen.add(key)
            kept.append({'id': f'B{len(kept) + 1}', 'assunto': _short(item.get('assunto'), 200),
                         'por_que': _short(item.get('por_que_em_alta'), 400), 'data': when.date().isoformat(),
                         'local': _short(item.get('local'), 80), 'veiculo': _short(item.get('veiculo'), 120), 'url': url})
        kept = [item for item in kept if item['assunto']][:MAX_BUZZ]
        self._done('buzz', f'{len(found)} achados, {len(kept)} dentro da janela de {self.params["recency_days"]} dias', tokens,
                   preview=[{'title': item['assunto'], 'url': item['url']} for item in kept])
        return kept

    def _check(self, buzz, ctx):
        """Abre cada link: o que não abre sai. Cada fonte ganha o nível da base (só informação, não filtro)."""
        self._start('check')
        with ThreadPoolExecutor(max_workers=8) as pool:
            status = list(pool.map(check_url, [item['url'] for item in buzz]))
        alive = []
        for item, state in zip(buzz, status):
            if state == 'quebrado':
                continue
            look = source_base.lookup(item['url'], ctx.get('site'))
            alive.append({**item, 'tier': look['tier'], 'domain': look['domain'], 'url_status': state})
        for index, item in enumerate(alive):
            item['id'] = f'B{index + 1}'
        self._done('check', f'{len(alive)} com link aberto' + (f', {len(buzz) - len(alive)} descartados' if len(alive) < len(buzz) else ''))
        return alive

    def _angles(self, ctx, topic, buzz):
        self._start('angles')
        payload = json.dumps({
            'conceito': topic, 'marca': ctx, 'praca': self.params['places'] or 'Brasil',
            'buzz': [{key: item[key] for key in ('id', 'assunto', 'por_que', 'data', 'veiculo', 'local')} for item in buzz]},
            ensure_ascii=False)
        text, tokens = self._ai('angles', self.models['angles'], prompts.messages('angles', PROMPTS, today=self.today.isoformat(),
                                                                                  payload=payload), max_tokens=6000)
        by_id = {item['id']: item for item in buzz}
        angles = []
        for item in json_loads(text).get('angulos') or []:
            if not isinstance(item, dict) or not item.get('titulo'):
                continue
            ids = [str(value) for value in item.get('buzz') or [] if str(value) in by_id]
            if not ids:
                continue  # ângulo que não se apoia em nenhum buzz da lista é invenção
            angles.append({'titulo': _short(item['titulo'], 160), 'gancho': _short(item.get('gancho'), 600),
                           'por_que_agora': _short(item.get('por_que_agora'), 500),
                           'formatos': [_short(value, 60) for value in item.get('formatos') or []][:5],
                           'canais': [_short(value, 60) for value in item.get('canais') or []][:5],
                           'janela': _short(item.get('janela'), 120), 'buzz': ids})
        angles = angles[:MAX_ANGLES]
        self._done('angles', f'{len(angles)} ângulos', tokens, preview=[{'title': item['titulo']} for item in angles])
        return angles

    def _save(self, buzz, angles):
        self._start('save')
        signal_ids = {}
        with transaction() as cur:
            for item in buzz:
                signal_id = signal_ids[item['id']] = str(uuid4())
                cur.execute('''INSERT INTO cadu_radar_signals (id, run_id, client_id, headline, description, source, source_type, url,
                                   published_at, evidence, verification)
                               VALUES (%s, %s, %s, %s, %s, %s, 'news', %s, %s, %s, %s)''',
                            (signal_id, self.run_id, self.client_id, item['assunto'], item['por_que'], item['veiculo'], item['url'],
                             parse_date(item['data']), Json([{'url': item['url'], 'title': item['veiculo'], 'published_at': item['data']}]),
                             Json({'tier': item['tier'], 'url_status': item['url_status']})))
            for rank, angle in enumerate(angles):
                cur.execute('''INSERT INTO cadu_radar_opportunities (id, client_id, run_id, brand_ref, project_ref, title, thesis,
                                   score_breakdown, penalties, signal_ids)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '[]'::jsonb, %s)''',
                            (str(uuid4()), self.client_id, self.run_id, self.brand_ref, self.project_ref, angle['titulo'], angle['gancho'],
                             Json({'rank': rank, 'why_now': angle['por_que_agora'], 'formats': angle['formatos'],
                                   'channels': angle['canais'], 'window': angle['janela'],
                                   'buzz': [{key: by[key] for key in ('id', 'assunto', 'veiculo', 'data', 'url', 'tier', 'domain')}
                                            for by in buzz if by['id'] in angle['buzz']]}),
                             Json([signal_ids[value] for value in angle['buzz']])))
        self._done('save', f'{len(buzz)} buzz e {len(angles)} ângulos salvos')

    def execute(self):
        ctx = self._context()
        topic = self._topic(ctx)
        buzz = self._check(self._buzz(ctx, topic), ctx)
        if not buzz:
            # Sem buzz recente e verificável não há ângulo honesto: a tela explica e sugere recortar melhor.
            self._done('angles', 'Sem buzz suficiente para montar ângulos', status='skipped')
            self._save([], [])
        else:
            self._save(buzz, self._angles(ctx, topic, buzz))
        _finish(self.run_id, 'done')
        self._notify_finished(ctx.get('brand'))

    def _notify_finished(self, brand):
        """E-mail de conclusão ao dono da busca, com os ângulos e o tempo poupado. Nunca derruba a busca."""
        try:
            from ..cadu_family import repository
            from ..product_domains import product_url
            from . import notify
            run = get_run(self.client_id, self.run_id)
            if run and run['status'] == 'done':
                notify.run_finished(repository.actor(self.actor_id), run=run, brand=brand,
                                    run_url=product_url('planner', f'/radar?run={self.run_id}'),
                                    radars_url=product_url('planner', '/radares'))
        except Exception:  # noqa: BLE001 — o resultado já está salvo e visível na tela
            logger.warning('Radar %s: não foi possível enviar o e-mail de conclusão.', self.run_id, exc_info=True)


def get_run(client_id, run_id):
    from ..cadu_family import repository
    from . import repository as radar_repository
    # A tela consulta este run a cada 2 s: se o executor morreu, ela precisa ver a falha em vez de esperar para sempre.
    _expire_dead_runs(client_id)
    rows = repository.rows('''SELECT id, status, steps, cost, focus, brand_ref, project_ref, params, trigger, watch_id, error,
                                     created_at, finished_at
                                FROM cadu_radar_runs WHERE id = %s AND client_id = %s''', (str(run_id), int(client_id)))
    if not rows:
        return None
    run = rows[0]
    run['tokens'] = int((run.get('cost') or {}).get('tokens') or 0)
    run['estimated_tokens'] = int((run.get('cost') or {}).get('estimated_tokens') or 0)
    done = run['status'] == 'done'
    run['opportunities'] = repository.rows('''SELECT id, title, thesis, status, score_breakdown, created_at
                                                FROM cadu_radar_opportunities WHERE run_id = %s
                                            ORDER BY (score_breakdown->>'rank')::int NULLS LAST, created_at''', (str(run_id),)) if done else []
    run['signals'] = repository.rows('''SELECT id, headline, description, source, url, published_at, verification
                                          FROM cadu_radar_signals WHERE run_id = %s ORDER BY published_at DESC NULLS LAST''',
                                     (str(run_id),)) if done else []
    run['related_plans'] = radar_repository.plans_for(client_id, signal_ids=[row['id'] for row in run['signals']],
                                                       opportunity_ids=[row['id'] for row in run['opportunities']]) if done else []
    if run['opportunities']:
        run['time_saved'] = time_saved.estimate(len(run['signals']), len(run['opportunities']))
    return run


def latest_run(client_id):
    from ..cadu_family import repository
    _expire_dead_runs(client_id)
    rows = repository.rows('SELECT id FROM cadu_radar_runs WHERE client_id = %s ORDER BY created_at DESC LIMIT 1', (int(client_id),))
    return get_run(client_id, rows[0]['id']) if rows else None


def list_runs(client_id, *, limit=30, watch_id=None):
    """Consultas realizadas: uma linha por busca, com os ângulos que ela achou e quanto custou."""
    from ..cadu_family import repository
    _expire_dead_runs(client_id)
    clauses, params = ['r.client_id = %s'], [int(client_id)]
    if watch_id:
        clauses.append('r.watch_id = %s')
        params.append(str(watch_id))
    params.append(max(1, min(int(limit), 100)))
    rows = repository.rows(f'''SELECT r.id, r.status, r.focus, r.brand_ref, r.project_ref, r.params, r.trigger, r.watch_id, r.error,
                                      r.cost, r.created_at, r.finished_at, COUNT(o.id) AS opportunities,
                                      COUNT(o.id) FILTER (WHERE o.status = 'em_plano') AS in_plan,
                                      (SELECT COUNT(*) FROM cadu_radar_signals s WHERE s.run_id = r.id) AS signals
                                 FROM cadu_radar_runs r LEFT JOIN cadu_radar_opportunities o ON o.run_id = r.id
                                WHERE {' AND '.join(clauses)}
                             GROUP BY r.id ORDER BY r.created_at DESC LIMIT %s''', tuple(params))
    for row in rows:
        row['tokens'] = int((row.get('cost') or {}).get('tokens') or 0)
        row.pop('cost', None)
    return rows
