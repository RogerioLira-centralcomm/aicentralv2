"""Pipeline do Radar de Oportunidades.

Dois fluxos independentes começam juntos e se encontram na leitura:

    discover  Perplexity via OpenRouter: "o que está acontecendo?"   ┐
    search    Firecrawl: fontes públicas recentes sobre o tema       ┘─► extract
    extract   lê as páginas citadas que ainda não foram lidas
    judge     o modelo preenche critérios (0–100) com justificativa; as notas,
              penalidades e o quadrante são calculados em scoring.py
    verify    um segundo modelo tenta provar que cada oportunidade está errada
    save      grava sinais e oportunidades

Cada etapa grava status, detalhe e tokens gastos em ``cadu_radar_runs.steps``,
para a tela mostrar o encadeamento ao vivo e o custo real em créditos. Os
créditos são reservados antes de começar e cobrados por chamada, com chave
idempotente por run e etapa. O Radar roda sob demanda; não há monitoramento
contínuo.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from flask import current_app
from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest

from . import scoring
from .contracts import QUADRANTS

logger = logging.getLogger(__name__)

STEPS = (
    ('discover', 'Descobrindo sinais', 'Perplexity procura o que está acontecendo no tema.'),
    ('search', 'Buscando fontes', 'Firecrawl encontra publicações recentes e lê as mais fortes.'),
    ('extract', 'Lendo as fontes', 'As páginas citadas são lidas para virar evidência.'),
    ('judge', 'Avaliando oportunidades', 'Cada oportunidade recebe nota editorial, paga e por praça.'),
    ('verify', 'Verificando as evidências', 'Um segundo modelo tenta provar que cada oportunidade está errada.'),
    ('save', 'Organizando o resultado', 'Sinais e oportunidades ficam salvos para o plano.'),
)
PARALLEL = ('discover', 'search')
# Tokens estimados por etapa paga (reserva antes de começar; a cobrança é o uso real).
ESTIMATES = {'discover': 3_500, 'judge': 7_000, 'verify': 4_500}
SEARCH_LIMIT, READ_LIMIT, MAX_OPPORTUNITIES = 6, 4, 5


class RadarDisabled(RuntimeError):
    pass


def enabled() -> bool:
    return bool(current_app.config.get('CADU_RADAR_ENABLED'))


def _models():
    from ..cadu_workspace import insights_research
    return insights_research.RESEARCH_MODEL, insights_research.SYNTHESIS_MODEL, insights_research.REVIEW_MODEL


def estimate_tokens(client_id) -> int:
    """Teto de tokens reservado antes do run (modelos + Firecrawl)."""
    from ..cadu_credit_connector import CaduCreditConnector
    credits = CaduCreditConnector()
    firecrawl = (credits.estimate_firecrawl_tokens('search', client_id=client_id, results=SEARCH_LIMIT)
                 + credits.estimate_firecrawl_tokens('scrape', client_id=client_id, pages=SEARCH_LIMIT + READ_LIMIT))
    return int(sum(ESTIMATES.values()) + firecrawl)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _initial_steps():
    return [{'key': key, 'label': label, 'hint': hint, 'status': 'pending', 'tokens': 0, 'detail': '',
             'parallel': key in PARALLEL, 'started_at': None, 'finished_at': None} for key, label, hint in STEPS]


def start_run(client_id, actor_id, *, focus='', brand_ref=None, project_ref=None):
    """Reserva créditos, grava o run e dispara o pipeline em segundo plano."""
    from ..cadu_credit_connector import CaduCreditConnector, CreditActor
    from ..cadu_family import repository
    from . import repository as radar_repository
    if not enabled():
        raise RadarDisabled('O Radar de Oportunidades ainda não está habilitado neste ambiente.')
    if not radar_repository.available():
        raise BadRequest('Aplique a migration do Radar antes de rodar.')
    focus = ' '.join(str(focus or '').split())[:240]
    if len(focus) < 3 and not (brand_ref or project_ref):
        raise BadRequest('Diga o tema ou escolha uma marca para o Radar procurar.')
    running = repository.rows('''SELECT id FROM cadu_radar_runs WHERE client_id = %s AND status IN ('queued', 'running')
                                    AND created_at > NOW() - INTERVAL '20 minutes' LIMIT 1''', (int(client_id),))
    if running:
        raise BadRequest('Já existe uma busca do Radar em andamento. Aguarde ela terminar.')
    estimate = estimate_tokens(client_id)
    # Sem saldo para o teto, o run nem começa (409 na rota).
    CaduCreditConnector().authorize(CreditActor.from_values(client_id, actor_id), estimate)
    run_id = str(uuid4())
    with repository.get_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO cadu_radar_runs (id, client_id, created_by, brand_ref, project_ref, status, steps, cost, focus)
                       VALUES (%s, %s, %s, %s, %s, 'running', %s, %s, %s)''',
                    (run_id, int(client_id), int(actor_id), brand_ref, project_ref, Json(_initial_steps()),
                     Json({'estimated_tokens': estimate, 'tokens': 0}), focus or None))
    app = current_app._get_current_object()

    def run():
        with app.app_context():
            try:
                Runner(run_id, int(client_id), int(actor_id), focus, brand_ref, project_ref).execute()
            except Exception as exc:  # noqa: BLE001 — o run registra a falha para a tela
                logger.exception('Radar run %s falhou', run_id)
                _finish(run_id, 'failed', error=_public_error(exc))

    threading.Thread(target=run, daemon=True, name=f'cadu-radar-{run_id[:12]}').start()
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


def _json(text):
    text = str(text or '').strip()
    match = re.search(r'\{.*\}', text, re.S)
    try:
        return json.loads(match.group(0) if match else text)
    except (ValueError, AttributeError):
        return {}


class Runner:
    """Executa um run; cada etapa atualiza a linha do run assim que muda."""

    def __init__(self, run_id, client_id, actor_id, focus, brand_ref, project_ref):
        self.run_id, self.client_id, self.actor_id = run_id, client_id, actor_id
        self.focus, self.brand_ref, self.project_ref = focus, brand_ref, project_ref
        self.steps = _initial_steps()
        self.lock = threading.Lock()
        self.web_context = SimpleNamespace(client_id=client_id, user_id=actor_id, conversation_id=None)

    # ---- estado das etapas -------------------------------------------------
    def _step(self, key):
        return next(step for step in self.steps if step['key'] == key)

    def _save_steps(self):
        with self.lock:
            snapshot = [dict(step) for step in self.steps]
            tokens = sum(step['tokens'] for step in snapshot)
        _update(self.run_id, steps=snapshot)
        conn = _db()
        with conn.cursor() as cur:
            cur.execute("UPDATE cadu_radar_runs SET cost = cost || %s WHERE id = %s", (Json({'tokens': tokens}), self.run_id))
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
    def _ai(self, stage, model, messages, max_tokens, estimated, provider=None, json_mode=True):
        from ..services.cadu_ai_connector import CaduAIConnector
        options = {'max_tokens': max_tokens, 'timeout': 75, 'temperature': 0.1}
        if json_mode:
            options['response_format'] = {'type': 'json_object'}
        if provider:
            options['provider'] = provider
        result = CaduAIConnector().complete(
            messages, client_id=self.client_id, user_id=self.actor_id,
            idempotency_key=f'radar:{self.run_id}:{stage}', app='Cadu Radar', stage=f'radar:{stage}',
            estimated_tokens=estimated, model=model, metadata={'radar_run_id': self.run_id, 'stage': stage}, **options)
        tokens = int(((result.get('cadu_charge') or {}).get('tokens_cobrados')) or 0)
        return result, tokens

    def _firecrawl_tokens(self, prefix):
        """Tokens cobrados pelo Firecrawl nesta etapa, lidos do livro de créditos."""
        conn = _db()
        with conn.cursor() as cur:
            cur.execute('''SELECT COALESCE(SUM(tokens_cobrados), 0) AS tokens FROM cadu_tools_token_usage
                            WHERE id_cliente = %s AND idempotency_key LIKE %s''',
                        (self.client_id, f'web-search:radar:{self.run_id}:{prefix}%'))
            row = cur.fetchone() or {}
        return int(row.get('tokens') or 0)

    # ---- contexto -----------------------------------------------------------
    def _context(self):
        from ..cadu_planner.context import load_plan_context
        context = load_plan_context(self.client_id, self.brand_ref, self.project_ref)
        brand, project = context.get('brand') or {}, context.get('project') or {}
        facts = [f"{item['label']}: {item['value']}" for item in (brand.get('fields') or []) + (project.get('fields') or []) if item.get('value')]
        return {'brand': brand.get('name'), 'sector': brand.get('sector'), 'project': project.get('name'),
                'facts': facts[:14]}

    def _topic(self, ctx):
        parts = [self.focus, ctx.get('brand'), ctx.get('sector')]
        return ' '.join(part for part in parts if part)[:240]

    # ---- etapas --------------------------------------------------------------
    def _discover(self, ctx, topic):
        research_model, _, _ = _models()
        self._start('discover')
        result, tokens = self._ai('discover', research_model, [
            {'role': 'system', 'content': (
                'Você é um analista de oportunidades de mídia no Brasil. Pesquise fatos dos últimos 60 dias '
                '(notícias, buscas em alta, regulação, eventos, conversas sociais) que abram uma janela para uma marca '
                'falar ou anunciar. Para cada fato: o que aconteceu, quando, onde, e a URL da fonte. Não invente.')},
            {'role': 'user', 'content': f'Tema: {topic}\nContexto da marca: {"; ".join(ctx["facts"]) or "não informado"}'},
        ], max_tokens=1800, estimated=ESTIMATES['discover'], provider='openrouter', json_mode=False)
        from ..services.openrouter_service import message_text
        message = result.get('message') if isinstance(result.get('message'), dict) else {}
        citations = message.get('_cadu_citations') or []
        if isinstance(citations, dict):
            citations = citations.get('search_results') or citations.get('citations') or []
        urls = []
        for item in citations if isinstance(citations, list) else []:
            url = item if isinstance(item, str) else (item.get('url') or item.get('link') or '') if isinstance(item, dict) else ''
            if url and url not in urls:
                urls.append(str(url))
        text = message_text(message)
        self._done('discover', f'{len(urls)} fontes citadas', tokens,
                   preview=[{'title': url.split('/')[2] if '//' in url else url, 'url': url} for url in urls])
        return {'text': text[:8000], 'urls': urls[:8]}

    def _search(self, topic):
        from ..cadu_workspace import web_search
        self._start('search')
        result = web_search.search(self.web_context, {
            'query': f'{topic} Brasil', 'depth': 'fast', 'limit': SEARCH_LIMIT, 'recency': 'month',
            'include_content': True, 'request_id': f'radar:{self.run_id}:search'})
        sources = result.get('sources') or []
        read = [item for item in sources if item.get('content')]
        self._done('search', f'{len(sources)} fontes, {len(read)} lidas', self._firecrawl_tokens('search'),
                   preview=[{'title': item.get('title') or item.get('url'), 'url': item.get('url')} for item in sources])
        return sources

    def _extract(self, discovered, sources):
        from ..cadu_workspace import web_search
        self._start('extract')
        known = {str(item.get('url') or '').rstrip('/').casefold() for item in sources}
        pending = [url for url in discovered['urls'] if url.rstrip('/').casefold() not in known][:READ_LIMIT]
        if pending:
            try:
                extra = web_search.read(self.web_context, {'urls': pending, 'request_id': f'radar:{self.run_id}:extract'})
                sources = [*sources, *(extra.get('sources') or [])]
            except Exception:  # noqa: BLE001 — leitura extra é opcional
                logger.info('Radar %s: leitura extra indisponível', self.run_id)
        read = [item for item in sources if item.get('content')]
        self._done('extract', f'{len(read)} páginas lidas como evidência', self._firecrawl_tokens('extract'))
        return read

    def _judge(self, ctx, topic, discovered, evidence):
        _, synthesis_model, _ = _models()
        self._start('judge')
        packet = [{'id': f'S{index + 1}', 'title': item.get('title'), 'url': item.get('url'),
                   'published_at': item.get('published_at'), 'excerpt': str(item.get('content') or item.get('excerpt') or '')[:1400]}
                  for index, item in enumerate(evidence[:10])]
        schema = {
            'opportunities': [{
                'title': 'até 90 caracteres', 'thesis': 'por que a marca deve agir agora, 1-2 frases',
                'signals': [{'source_id': 'S1', 'headline': '...', 'source_type': 'news|search_trend|social|regulation|event|report|other'}],
                'editorial': {key: '0-100' for key in scoring.EDITORIAL_WEIGHTS},
                'paid': {key: '0-100' for key in scoring.PAID_WEIGHTS},
                'penalties': {key: f'0-{cap}' for key, cap in scoring.PENALTY_CAPS.items()},
                'places': [{'place': 'cidade ou estado', 'interest': '0-100', 'audience': '0-100', 'context': '0-100', 'reason': '...'}],
                'channels': ['tipos de canal que fazem sentido'], 'window': 'até quando a janela fica aberta',
                'why': {'editorial': 'justificativa curta', 'paid': 'justificativa curta'},
            }]}
        result, tokens = self._ai('judge', synthesis_model, [
            {'role': 'system', 'content': (
                'Você qualifica oportunidades de comunicação e mídia. Use somente as evidências fornecidas; '
                'sem evidência, o critério vale 0. Notas de 0 a 100, conservadoras. Responda só JSON no esquema pedido. '
                f'No máximo {MAX_OPPORTUNITIES} oportunidades, da mais forte para a mais fraca.')},
            {'role': 'user', 'content': json.dumps({
                'tema': topic, 'marca': ctx, 'achados_da_pesquisa': discovered['text'][:4000],
                'evidencias': packet, 'esquema': schema}, ensure_ascii=False)},
        ], max_tokens=3200, estimated=ESTIMATES['judge'])
        from ..services.openrouter_service import message_text
        raw = _json(message_text(result.get('message')))
        by_id = {item['id']: item for item in packet}
        opportunities = []
        for item in (raw.get('opportunities') or [])[:MAX_OPPORTUNITIES]:
            if not isinstance(item, dict) or not item.get('title'):
                continue
            editorial = scoring.editorial_score(_criteria(item.get('editorial'), scoring.EDITORIAL_WEIGHTS),
                                                _criteria(item.get('penalties'), scoring.PENALTY_CAPS))
            paid = scoring.paid_score(_criteria(item.get('paid'), scoring.PAID_WEIGHTS),
                                      _criteria(item.get('penalties'), scoring.PENALTY_CAPS))
            signals = [{**sig, **({'url': by_id[sig.get('source_id')]['url'], 'source': by_id[sig.get('source_id')]['title'],
                                   'published_at': by_id[sig.get('source_id')]['published_at']} if sig.get('source_id') in by_id else {})}
                       for sig in item.get('signals') or [] if isinstance(sig, dict)]
            places = []
            for place in item.get('places') or []:
                if isinstance(place, dict) and place.get('place'):
                    geo = scoring.GeoScore(place=str(place['place'])[:80], interest=_num(place.get('interest')),
                                           audience=_num(place.get('audience')), context=_num(place.get('context')),
                                           reasons=[str(place.get('reason') or '')[:200]])
                    places.append(scoring.geo_score(geo))
            opportunities.append({
                'title': str(item['title'])[:240], 'thesis': str(item.get('thesis') or '')[:1200],
                'editorial': editorial, 'paid': paid, 'quadrant': scoring.quadrant(editorial.score, paid.score),
                'signals': signals[:6], 'places': places[:5], 'channels': [str(c)[:60] for c in item.get('channels') or []][:6],
                'window': str(item.get('window') or '')[:120], 'why': item.get('why') if isinstance(item.get('why'), dict) else {},
            })
        self._done('judge', f'{len(opportunities)} oportunidades avaliadas', tokens,
                   preview=[{'title': item['title'], 'score': max(item['editorial'].score, item['paid'].score)} for item in opportunities])
        return opportunities, packet

    def _verify(self, opportunities, packet):
        _, _, review_model = _models()
        self._start('verify')
        if not opportunities:
            self._done('verify', 'Nada para verificar', 0, status='skipped')
            return opportunities
        result, tokens = self._ai('verify', review_model, [
            {'role': 'system', 'content': (
                'Você é o verificador. Tente provar que cada oportunidade está errada: a evidência é recente? '
                'Há fonte primária? Está fora de contexto? Responda só JSON: {"results": [{"index": 0, '
                '"verdict": "confirmado|parcial|contestado", "is_recent": true, "has_primary_source": true, '
                '"corroborating_sources": 0, "notes": "..."}]}')},
            {'role': 'user', 'content': json.dumps({
                'oportunidades': [{'index': index, 'title': item['title'], 'thesis': item['thesis'],
                                   'signals': item['signals']} for index, item in enumerate(opportunities)],
                'evidencias': packet}, ensure_ascii=False)},
        ], max_tokens=1600, estimated=ESTIMATES['verify'])
        from ..services.openrouter_service import message_text
        verdicts = {int(item.get('index', -1)): item for item in (_json(message_text(result.get('message'))).get('results') or [])
                    if isinstance(item, dict) and str(item.get('index', '')).lstrip('-').isdigit()}
        contested = 0
        for index, item in enumerate(opportunities):
            verdict = verdicts.get(index) or {}
            status = verdict.get('verdict') if verdict.get('verdict') in ('confirmado', 'parcial', 'contestado') else 'nao_verificado'
            item['verification'] = {'verdict': status, 'is_recent': verdict.get('is_recent'),
                                    'has_primary_source': verdict.get('has_primary_source'),
                                    'corroborating_sources': int(_num(verdict.get('corroborating_sources'), 0, 20)),
                                    'notes': str(verdict.get('notes') or '')[:600]}
            if status in ('contestado', 'nao_verificado', 'parcial'):
                # Evidência fraca baixa as duas notas; contestada derruba a oportunidade para "ignorar".
                points = {'contestado': 20, 'nao_verificado': 12, 'parcial': 6}[status]
                for key in ('editorial', 'paid'):
                    breakdown = item[key]
                    penalties = {**breakdown.penalties, 'baixa_confianca': points}
                    weights = scoring.EDITORIAL_WEIGHTS if key == 'editorial' else scoring.PAID_WEIGHTS
                    item[key] = scoring.weighted(breakdown.criteria, weights, penalties)
                item['quadrant'] = 'ignorar' if status == 'contestado' else scoring.quadrant(item['editorial'].score, item['paid'].score)
                contested += status == 'contestado'
        confirmed = sum(1 for item in opportunities if item['verification']['verdict'] == 'confirmado')
        self._done('verify', f'{confirmed} confirmadas, {contested} contestadas', tokens)
        return opportunities

    def _save(self, opportunities):
        from dataclasses import asdict
        self._start('save')
        conn = _db()
        with conn.cursor() as cur:
            for item in opportunities:
                signal_ids = []
                for signal in item['signals']:
                    signal_id = str(uuid4())
                    signal_ids.append(signal_id)
                    source_type = signal.get('source_type') if signal.get('source_type') in (
                        'news', 'search_trend', 'social', 'regulation', 'event', 'crm', 'report', 'other') else 'other'
                    cur.execute('''INSERT INTO cadu_radar_signals (id, run_id, client_id, headline, source, source_type, url,
                                       evidence, verification)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                                (signal_id, self.run_id, self.client_id, str(signal.get('headline') or item['title'])[:500],
                                 str(signal.get('source') or '')[:240], source_type, str(signal.get('url') or '')[:1000],
                                 Json([{'url': signal.get('url'), 'title': signal.get('source'), 'published_at': signal.get('published_at')}]),
                                 Json(item.get('verification') or {})))
                quadrant = item['quadrant'] if item['quadrant'] in QUADRANTS else 'ignorar'
                cur.execute('''INSERT INTO cadu_radar_opportunities (id, client_id, run_id, brand_ref, project_ref, title, thesis,
                                   editorial_score, paid_score, geo_scores, score_breakdown, penalties, quadrant, signal_ids)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                            (str(uuid4()), self.client_id, self.run_id, self.brand_ref, self.project_ref, item['title'], item['thesis'],
                             item['editorial'].score, item['paid'].score, Json([asdict(place) for place in item['places']]),
                             Json({'editorial': asdict(item['editorial']), 'paid': asdict(item['paid']),
                                   'verification': item.get('verification') or {}, 'channels': item['channels'],
                                   'window': item['window'], 'why': item['why']}),
                             Json(sorted(set(item['editorial'].penalties) | set(item['paid'].penalties))), quadrant, Json(signal_ids)))
        conn.commit()
        self._done('save', f'{len(opportunities)} oportunidades salvas')

    def execute(self):
        ctx = self._context()
        topic = self._topic(ctx)
        app = current_app._get_current_object()

        def in_app(function, *args):
            with app.app_context():
                return function(*args)

        # Os dois fluxos de descoberta não dependem um do outro: rodam juntos.
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix=f'radar-{self.run_id[:8]}') as pool:
            discovered_future = pool.submit(in_app, self._discover, ctx, topic)
            sources_future = pool.submit(in_app, self._search, topic)
            discovered = _safe(discovered_future, {'text': '', 'urls': []}, self, 'discover')
            sources = _safe(sources_future, [], self, 'search')
        if not discovered['text'] and not sources:
            raise RuntimeError('Nenhum fluxo de descoberta trouxe resultado.')
        evidence = self._extract(discovered, sources)
        opportunities, packet = self._judge(ctx, topic, discovered, evidence)
        opportunities = self._verify(opportunities, packet)
        self._save(opportunities)
        _finish(self.run_id, 'done')


def _safe(future, fallback, runner, key):
    """Um fluxo que falha não derruba o outro; a etapa aparece como falha na tela."""
    try:
        return future.result()
    except Exception:  # noqa: BLE001
        logger.exception('Radar %s: etapa %s falhou', runner.run_id, key)
        runner._done(key, 'Fonte indisponível agora', 0, status='failed')
        return fallback


def _num(value, low=0, high=100):
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def _criteria(raw, allowed):
    if not isinstance(raw, dict):
        return {}
    return {key: _num(value, 0, allowed[key] if allowed is scoring.PENALTY_CAPS else 100)
            for key, value in raw.items() if key in allowed}


def get_run(client_id, run_id):
    from ..cadu_family import repository
    rows = repository.rows('''SELECT id, status, steps, cost, focus, brand_ref, project_ref, error, created_at, finished_at
                                FROM cadu_radar_runs WHERE id = %s AND client_id = %s''', (str(run_id), int(client_id)))
    if not rows:
        return None
    run = rows[0]
    run['tokens'] = int((run.get('cost') or {}).get('tokens') or 0)
    run['estimated_tokens'] = int((run.get('cost') or {}).get('estimated_tokens') or 0)
    run['opportunities'] = repository.rows('''SELECT id, title, thesis, editorial_score, paid_score, quadrant, status,
                                                      geo_scores, score_breakdown, created_at
                                                 FROM cadu_radar_opportunities WHERE run_id = %s
                                             ORDER BY GREATEST(editorial_score, paid_score) DESC''', (str(run_id),)) if run['status'] == 'done' else []
    return run


def latest_run(client_id):
    from ..cadu_family import repository
    rows = repository.rows('SELECT id FROM cadu_radar_runs WHERE client_id = %s ORDER BY created_at DESC LIMIT 1', (int(client_id),))
    return get_run(client_id, rows[0]['id']) if rows else None
