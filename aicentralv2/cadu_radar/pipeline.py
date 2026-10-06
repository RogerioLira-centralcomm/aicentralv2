"""Pipeline do Radar de Oportunidades (fluxo F1, escolhido no Lab em 2026-10-06).

Três buscas do Perplexity (via OpenRouter, cobradas pelo custo) começam juntas:

    discover_open    o que está acontecendo no tema (sonar-pro)
    discover_press   só em reportagens dos veículos da base curada, com os regionais das praças
    discover_trends  assuntos e buscas em alta
    extract          lê as páginas citadas (Firecrawl, com leitor Python como reserva)
    judge            o modelo preenche critérios (0–100); notas, penalidades e quadrante são de scoring.py
    verify           checagem de realidade: um modelo com busca confere cada oportunidade FORA do pacote
    save             nível das fontes, selo de confiança, links que abrem; grava sinais e oportunidades

Cada etapa grava status, detalhe e tokens em ``cadu_radar_runs.steps``, para a tela
mostrar o encadeamento ao vivo. Créditos: reserva pelo custo em US$ antes de começar
e cobrança por chamada, com chave idempotente por run e etapa. Os prompts são
versionados em ``prompts.py``; a base de fontes, em ``sources.py``.
"""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from flask import current_app
from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest

from . import prompts, scoring, sources as source_base
from .contracts import QUADRANTS
from .research import build_packet, check_url, citations, facts_from, json_loads, parse_date, python_read

logger = logging.getLogger(__name__)

STEPS = (
    ('discover_open', 'Descobrindo sinais', 'Perplexity procura o que está acontecendo no tema.'),
    ('discover_press', 'Lendo a imprensa', 'Procura só em reportagens de veículos conhecidos, com os da sua praça.'),
    ('discover_trends', 'Buscando o que está em alta', 'Assuntos e buscas que cresceram nos últimos dias.'),
    ('extract', 'Lendo as fontes', 'As páginas citadas são lidas para virar evidência.'),
    ('judge', 'Avaliando oportunidades', 'Cada oportunidade recebe nota editorial, paga e por praça.'),
    ('verify', 'Conferindo na web', 'Um segundo modelo pesquisa fora das fontes e tenta provar que cada oportunidade está errada.'),
    ('save', 'Organizando o resultado', 'Nível das fontes, selo de confiança e links conferidos.'),
)
PARALLEL = ('discover_open', 'discover_press', 'discover_trends')
READ_LIMIT, MAX_OPPORTUNITIES = 4, 5
# Custo típico do F1 no Lab: US$ 0,09 por busca. A reserva dá folga, mas é em US$, não em tokens fixos.
ESTIMATE_USD = 0.15
STAGE_USD = {'discover_open': 0.03, 'discover_press': 0.015, 'discover_trends': 0.015, 'judge': 0.03, 'verify': 0.03}
LENSES = ('Sazonalidade e datas', 'Concorrência', 'Tendências e cultura', 'Regulação', 'Lançamentos do setor', 'Reputação')
RECENCY_DAYS = (7, 30, 60)
LEASE_MINUTES = 5


def models():
    from ..cadu_workspace import insights_research
    return {
        'discover_open': os.getenv('CADU_RADAR_DISCOVER_MODEL', 'perplexity/sonar-pro'),
        'discover_press': os.getenv('CADU_RADAR_PRESS_MODEL', 'perplexity/sonar'),
        'discover_trends': os.getenv('CADU_RADAR_TRENDS_MODEL', 'perplexity/sonar'),
        'judge': os.getenv('CADU_RADAR_JUDGE_MODEL', insights_research.SYNTHESIS_MODEL),
        'verify': os.getenv('CADU_RADAR_CHECK_MODEL', 'perplexity/sonar'),
    }


class RadarDisabled(RuntimeError):
    pass


def enabled() -> bool:
    return bool(current_app.config.get('CADU_RADAR_ENABLED'))


def clean_params(raw) -> dict:
    """Parâmetros do wizard, validados: nada além do que a busca sabe usar."""
    raw = raw if isinstance(raw, dict) else {}
    sources = raw.get('sources') if isinstance(raw.get('sources'), dict) else {}
    try:
        days = int(raw.get('recency_days') or 30)
    except (TypeError, ValueError):
        days = 30
    return {
        'lenses': [item for item in raw.get('lenses') or [] if item in LENSES][:3],
        'places': ' '.join(str(raw.get('places') or '').split())[:120],
        'recency_days': days if days in RECENCY_DAYS else 30,
        'objective': raw.get('objective') if raw.get('objective') in ('conteudo', 'midia', 'ambos') else 'ambos',
        'sources': {'press': sources.get('press') is not False, 'trends': sources.get('trends') is not False},
    }


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
    params = params or clean_params({})
    off = {'discover_press': not params['sources']['press'], 'discover_trends': not params['sources']['trends']}
    return [{'key': key, 'label': label, 'hint': hint, 'status': 'skipped' if off.get(key) else 'pending', 'tokens': 0,
             'detail': 'Desligada nesta busca' if off.get(key) else '', 'parallel': key in PARALLEL,
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
    with repository.get_db() as conn, conn.cursor() as cur:
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
    with repository.get_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE cadu_radar_runs SET status = 'failed', finished_at = NOW(),
                              error = 'A busca foi interrompida. Rode de novo.'
                        WHERE client_id = %s AND status IN ('queued', 'running')
                          AND COALESCE(lease_until, created_at + INTERVAL '20 minutes') < NOW()''', (int(client_id),))


def _host(url):
    return source_base.host(url) or url


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


class Runner:
    """Executa um run; cada etapa atualiza a linha do run assim que muda."""

    def __init__(self, run_id, client_id, actor_id, focus, brand_ref, project_ref, params=None):
        self.run_id, self.client_id, self.actor_id = run_id, client_id, actor_id
        self.focus, self.brand_ref, self.project_ref = focus, brand_ref, project_ref
        self.params = clean_params(params)
        self.steps = _initial_steps(self.params)
        self.lock = threading.Lock()
        self.web_context = SimpleNamespace(client_id=client_id, user_id=actor_id, conversation_id=None)
        self.models = models()

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
    def _ai(self, stage, model, messages, max_tokens, usd, json_mode=True, web=False):
        """Sempre pelo OpenRouter: cobrança pelo custo real em US$ (a OpenAI direta cobraria 1 token por token)."""
        from ..services.cadu_ai_connector import CaduAIConnector
        options = {'max_tokens': max_tokens, 'timeout': 150, 'temperature': 0.1, 'provider': 'openrouter'}
        if json_mode:
            options['response_format'] = {'type': 'json_object'}
        result = CaduAIConnector().complete(
            messages, client_id=self.client_id, user_id=self.actor_id,
            idempotency_key=f'radar:{self.run_id}:{stage}', app='Cadu Radar', stage=f'radar:{stage}',
            estimated_tokens=max(1_000, usd_to_tokens(self.client_id, usd)), model=model,
            metadata={'radar_run_id': self.run_id, 'stage': stage, 'prompt_version': prompts.VERSION, 'web': web}, **options)
        tokens = int(((result.get('cadu_charge') or {}).get('tokens_cobrados')) or 0)
        return result, tokens

    def _firecrawl_tokens(self, prefix):
        """Tokens cobrados pelo Firecrawl nesta etapa, lidos do livro de créditos."""
        conn = _db()
        with conn.cursor() as cur:
            cur.execute('''SELECT COALESCE(SUM(tokens_cobrados), 0) AS tokens FROM cadu_tools_token_usage
                            WHERE id_cliente = %s AND idempotency_key LIKE %s''',
                        (self.client_id, f'%radar:{self.run_id}:{prefix}%'))
            row = cur.fetchone() or {}
        return int(row.get('tokens') or 0)

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

    def _values(self, ctx, topic):
        places = self.params['places'] or 'Brasil'
        domains = source_base.press_domains(places)
        return domains, dict(topic=topic, places=places, lenses=', '.join(self.params['lenses']),
                             recency_days=self.params['recency_days'], brand_facts='; '.join(ctx['facts']) or 'não informado',
                             sector=ctx.get('sector') or '', domains=', '.join(domains))

    # ---- etapas --------------------------------------------------------------
    def _discover(self, stage, values):
        self._start(stage)
        result, tokens = self._ai(stage, self.models[stage], prompts.messages(stage, **values), max_tokens=3000,
                                  usd=STAGE_USD[stage], json_mode=False, web=True)
        from ..services.openrouter_service import message_text
        message = result.get('message') if isinstance(result.get('message'), dict) else {}
        text = message_text(message)
        facts, cited = facts_from(text, citations(message))
        self._done(stage, f'{len(facts)} fatos, {len(cited)} fontes citadas', tokens,
                   preview=[{'title': item.get('title') or _host(item['url']), 'url': item['url']} for item in cited])
        return {'text': text[:2500], 'facts': facts, 'cited': cited}

    def _extract(self, found, domains):
        from ..cadu_workspace import web_search
        self._start('extract')
        facts, cited, texts = [], [], []
        allowed = {source_base.root(domain) for domain in domains}
        for stage, item in found.items():
            stage_facts = item['facts']
            if stage == 'discover_press':
                # O que o Perplexity trouxer fora da lista curada sai: a busca "só imprensa" tem de ser só imprensa.
                stage_facts = [fact for fact in stage_facts if source_base.root(fact.get('url', '')) in allowed]
            facts += stage_facts
            cited += item['cited']
            texts.append(item['text'])
        urls = list(dict.fromkeys(entry['url'] for entry in cited if entry.get('url')))[:READ_LIMIT]
        pages = {}
        if urls:
            try:
                for page in web_search.read(self.web_context, {'urls': urls, 'request_id': f'radar:{self.run_id}:extract'}).get('sources') or []:
                    if page.get('content'):
                        pages[page.get('url')] = page
            except Exception:  # noqa: BLE001 — a leitura é reforço, não condição
                logger.info('Radar %s: leitura pelo Firecrawl indisponível', self.run_id)
            for url in urls:
                if url not in pages:
                    try:
                        pages[url] = {'url': url, **python_read(url)}
                    except Exception:  # noqa: BLE001
                        continue
        packet = build_packet(facts, list(pages.values()))
        self._done('extract', f'{len(pages)} páginas lidas, {len(packet)} evidências', self._firecrawl_tokens('extract'))
        return packet, '\n\n'.join(texts)

    def _judge(self, ctx, topic, text, packet):
        self._start('judge')
        payload = prompts.judge_payload(topic, ctx, text, packet, places=self.params['places'] or 'Brasil',
                                        lenses=', '.join(self.params['lenses']))
        result, tokens = self._ai('judge', self.models['judge'], prompts.messages('judge', max_opportunities=MAX_OPPORTUNITIES,
                                                                                  payload=payload),
                                  max_tokens=9000, usd=STAGE_USD['judge'])
        from ..services.openrouter_service import message_text
        raw = json_loads(message_text(result.get('message')))
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
        return opportunities

    def _verify(self, opportunities):
        """Checagem de realidade: pesquisa na web fora do pacote e aplica as penalidades por evidência fraca."""
        self._start('verify')
        if not opportunities:
            self._done('verify', 'Nada para verificar', 0, status='skipped')
            return opportunities
        claims = '\n'.join(f"{index}. {item['title']} — {item['thesis']}" for index, item in enumerate(opportunities))
        result, tokens = self._ai('verify', self.models['verify'], prompts.messages(
            'reality_check', recency_days=self.params['recency_days'], today=datetime.now(timezone.utc).date().isoformat(),
            claims=claims), max_tokens=3000, usd=STAGE_USD['verify'], json_mode=False, web=True)
        from ..services.openrouter_service import message_text
        found = {}
        for row in json_loads(message_text(result.get('message'))).get('results') or []:
            if isinstance(row, dict) and str(row.get('index', '')).isdigit():
                found[int(row['index'])] = row
        contested = 0
        for index, item in enumerate(opportunities):
            row = found.get(index) or {}
            verdict = row.get('verdict') if row.get('verdict') in ('confirmado', 'parcial', 'contestado') else 'nao_verificado'
            item['verification'] = {
                'verdict': verdict, 'is_recent': row.get('is_recent'),
                'other_sources': [str(url) for url in row.get('other_sources') or [] if str(url).startswith('http')][:5],
                'contradiction': str(row.get('contradiction') or '')[:300],
                'notes': str(row.get('notes') or row.get('contradiction') or '')[:600]}
            if verdict != 'confirmado':
                # Evidência fraca baixa as duas notas; contestada derruba a oportunidade para "ignorar".
                points = {'contestado': 20, 'nao_verificado': 12, 'parcial': 6}[verdict]
                for key, weights in (('editorial', scoring.EDITORIAL_WEIGHTS), ('paid', scoring.PAID_WEIGHTS)):
                    breakdown = item[key]
                    item[key] = scoring.weighted(breakdown.criteria, weights, {**breakdown.penalties, 'baixa_confianca': points})
                item['quadrant'] = 'ignorar' if verdict == 'contestado' else scoring.quadrant(item['editorial'].score, item['paid'].score)
                contested += verdict == 'contestado'
        confirmed = sum(1 for item in opportunities if item['verification']['verdict'] == 'confirmado')
        self._done('verify', f'{confirmed} confirmadas, {contested} contestadas', tokens)
        return opportunities

    def _annotate(self, opportunities, ctx):
        """Nível de cada fonte, se o link abre e se está na janela; selo de confiança calculado em Python."""
        urls = sorted({signal.get('url') for item in opportunities for signal in item['signals'] if signal.get('url')})
        with ThreadPoolExecutor(max_workers=8) as pool:
            status = dict(zip(urls, pool.map(check_url, urls)))
        since = datetime.now(timezone.utc) - timedelta(days=self.params['recency_days'])
        for item in opportunities:
            for signal in item['signals']:
                look = source_base.lookup(signal.get('url') or '', ctx.get('site'))
                when = parse_date(signal.get('published_at'))
                signal.update(tier=look['tier'], domain=look['domain'], url_status=status.get(signal.get('url'), 'sem_url'),
                              in_window=None if when is None else when >= since)
            alive = [signal['url'] for signal in item['signals'] if signal.get('url') and signal['url_status'] != 'quebrado']
            verification = item.setdefault('verification', {'verdict': 'nao_verificado', 'other_sources': []})
            verification['confidence'] = source_base.confidence(
                alive + verification.get('other_sources', []), ctx.get('site'),
                contradicted=bool(verification.get('contradiction')) or verification.get('verdict') == 'contestado')
            verification['primary_source'] = any(source_base.lookup(url, ctx.get('site'))['primary'] for url in alive)
            verification['sources_ab'] = sum(signal['tier'] in ('A', 'B') for signal in item['signals'])
            if verification['confidence'] == 'baixa':
                item['quadrant'] = 'ignorar'

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
                                 Json([{'url': signal.get('url'), 'title': signal.get('source'), 'published_at': signal.get('published_at'),
                                        'tier': signal.get('tier'), 'url_status': signal.get('url_status')}]),
                                 Json(item.get('verification') or {})))
                quadrant = item['quadrant'] if item['quadrant'] in QUADRANTS else 'ignorar'
                cur.execute('''INSERT INTO cadu_radar_opportunities (id, client_id, run_id, brand_ref, project_ref, title, thesis,
                                   editorial_score, paid_score, geo_scores, score_breakdown, penalties, quadrant, signal_ids)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                            (str(uuid4()), self.client_id, self.run_id, self.brand_ref, self.project_ref, item['title'], item['thesis'],
                             item['editorial'].score, item['paid'].score, Json([asdict(place) for place in item['places']]),
                             Json({'editorial': asdict(item['editorial']), 'paid': asdict(item['paid']),
                                   'verification': item.get('verification') or {}, 'channels': item['channels'],
                                   'window': item['window'], 'why': item['why'],
                                   'sources': [{k: signal.get(k) for k in ('url', 'source', 'domain', 'tier', 'url_status', 'published_at', 'in_window')}
                                               for signal in item['signals']]}),
                             Json(sorted(set(item['editorial'].penalties) | set(item['paid'].penalties))), quadrant, Json(signal_ids)))
        conn.commit()
        self._done('save', f'{len(opportunities)} oportunidades salvas')

    def execute(self):
        ctx = self._context()
        topic = self._topic(ctx)
        domains, values = self._values(ctx, topic)
        app = current_app._get_current_object()

        def in_app(function, *args):
            with app.app_context():
                return function(*args)

        stages = [stage for stage in PARALLEL if self._step(stage)['status'] == 'pending']
        found = {}
        # As buscas não dependem uma da outra: rodam juntas; uma que falha não derruba as outras.
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix=f'radar-{self.run_id[:8]}') as pool:
            futures = {stage: pool.submit(in_app, self._discover, stage, values) for stage in stages}
            for stage, future in futures.items():
                found[stage] = _safe(future, {'text': '', 'facts': [], 'cited': []}, self, stage)
        if not any(item['facts'] or item['cited'] for item in found.values()):
            raise RuntimeError('Nenhuma busca trouxe resultado.')
        packet, text = self._extract(found, domains)
        opportunities = self._judge(ctx, topic, text, packet)
        opportunities = self._verify(opportunities)
        self._annotate(opportunities, ctx)
        self._save(opportunities)
        _finish(self.run_id, 'done')


def _safe(future, fallback, runner, key):
    """Uma busca que falha não derruba as outras; a etapa aparece como falha na tela."""
    try:
        return future.result()
    except Exception:  # noqa: BLE001
        logger.exception('Radar %s: etapa %s falhou', runner.run_id, key)
        runner._done(key, 'Fonte indisponível agora', 0, status='failed')
        return fallback


def get_run(client_id, run_id):
    from ..cadu_family import repository
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
    run['opportunities'] = repository.rows('''SELECT id, title, thesis, editorial_score, paid_score, quadrant, status,
                                                      geo_scores, score_breakdown, created_at
                                                 FROM cadu_radar_opportunities WHERE run_id = %s
                                             ORDER BY GREATEST(editorial_score, paid_score) DESC''', (str(run_id),)) if run['status'] == 'done' else []
    return run


def latest_run(client_id):
    from ..cadu_family import repository
    _expire_dead_runs(client_id)
    rows = repository.rows('SELECT id FROM cadu_radar_runs WHERE client_id = %s ORDER BY created_at DESC LIMIT 1', (int(client_id),))
    return get_run(client_id, rows[0]['id']) if rows else None


def list_runs(client_id, *, limit=30, watch_id=None):
    """Consultas realizadas: uma linha por busca, com o que ela achou e quanto custou."""
    from ..cadu_family import repository
    _expire_dead_runs(client_id)
    clauses, params = ['r.client_id = %s'], [int(client_id)]
    if watch_id:
        clauses.append('r.watch_id = %s')
        params.append(str(watch_id))
    params.append(max(1, min(int(limit), 100)))
    rows = repository.rows(f'''SELECT r.id, r.status, r.focus, r.brand_ref, r.project_ref, r.params, r.trigger, r.watch_id, r.error,
                                      r.cost, r.created_at, r.finished_at,
                                      COUNT(o.id) AS opportunities,
                                      COUNT(o.id) FILTER (WHERE o.quadrant <> 'ignorar') AS actionable,
                                      MAX(GREATEST(o.editorial_score, o.paid_score)) AS top_score
                                 FROM cadu_radar_runs r LEFT JOIN cadu_radar_opportunities o ON o.run_id = r.id
                                WHERE {' AND '.join(clauses)}
                             GROUP BY r.id ORDER BY r.created_at DESC LIMIT %s''', tuple(params))
    for row in rows:
        row['tokens'] = int((row.get('cost') or {}).get('tokens') or 0)
        row.pop('cost', None)
    return rows
