"""Lab do Radar: fluxos de pesquisa comparados lado a lado, com revisão em loop e custo simulado e real.

Cada fluxo usa outra combinação de buscador e modelo, mas o mesmo cenário e os
mesmos prompts versionados (``prompts.py``). Todas as chamadas passam pelo
roteador global de créditos:

* modelos: ``CaduAIConnector`` (OpenAI direta ou OpenRouter, com débito idempotente);
* Firecrawl: ``web_search.search`` / ``web_search.read`` (débito por busca e por página).

Antes de cada chamada o Lab simula o custo (tabela de preços pública do
OpenRouter + tamanho do prompt) e, depois, lê o que foi de fato debitado. Um
revisor final (Haiku via OpenRouter) dá notas cegas às oportunidades de todos os
fluxos. Nada é gravado nas tabelas do Radar; só o livro de créditos recebe os
débitos, com ``app='Cadu Radar'`` e ``stage='radar-lab:<fluxo>:<etapa>'``.

Dois loops de revisão:

* **das oportunidades**: o fluxo abaixo da meta reescreve a própria lista a partir
  das notas do revisor (só com o mesmo pacote de evidências), até N voltas; fica a
  melhor versão;
* **dos prompts**: o médico de prompts lê o diagnóstico e propõe a versão seguinte
  dos prompts editáveis (juiz, revisão, checagens). Ela roda sobre as MESMAS
  evidências e só vira a melhor versão se a média dos fluxos subir.
"""
from __future__ import annotations

import json
import random
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from types import SimpleNamespace
from urllib.parse import quote_plus
from uuid import uuid4

import requests

from . import prompts, scoring, sources as source_base
from .research import python_read, check_url, citations, json_loads as _json, parse_date as _date
from .contracts import QUADRANTS

APP = 'Cadu Radar'
REVIEW_MODEL = 'anthropic/claude-haiku-4.5'
CHARS_PER_TOKEN = 3.6       # português, medido grosso
OUTPUT_FILL = 0.6           # fração do max_tokens que costuma sair
UA = {'User-Agent': 'Mozilla/5.0 (compatible; CaduRadarLab/1.0; +https://centralcomm.media)'}

# Fluxos do Lab. ``kind`` diz como descobre e confere:
#   perplexity  Perplexity aberto + imprensa curada + buscas em alta → lê páginas → juiz → checagem Perplexity
#   web         o próprio modelo busca na web (plugin ``web`` nativo do OpenRouter) → juiz → checagem com busca
#   evidence    sem IA na busca: Google Notícias (RSS) + Firecrawl na imprensa curada → juiz → verificador interno
# Modelos trocáveis pela linha de comando (``--model F4.judge=...``).
FLOWS = {
    'F1': {'name': 'Perplexity + imprensa', 'kind': 'perplexity', 'models': {
        'discover_open': 'perplexity/sonar-pro', 'discover_press': 'perplexity/sonar',
        'discover_trends': 'perplexity/sonar', 'judge': 'openai/gpt-5.4-mini', 'check': 'perplexity/sonar'}},
    'F2': {'name': 'OpenAI nativo', 'kind': 'web', 'judge_provider': 'openai', 'models': {
        'discover': 'openai/gpt-5-mini', 'judge': 'gpt-5-mini', 'check': 'openai/gpt-5-mini'}},
    'F3': {'name': 'Evidência primeiro (Firecrawl + Python)', 'kind': 'evidence', 'models': {
        'judge': 'google/gemini-2.5-flash', 'check': 'deepseek/deepseek-v3.2'}},
    'F4': {'name': 'Gemini + busca Google', 'kind': 'web', 'models': {
        'discover': 'google/gemini-3-flash-preview', 'judge': 'google/gemini-3-flash-preview',
        'check': 'google/gemini-3-flash-preview'}},
    'F5': {'name': 'Grok + web e X', 'kind': 'web', 'models': {
        'discover': 'x-ai/grok-4.3', 'judge': 'x-ai/grok-4.3', 'check': 'x-ai/grok-4.3'}},
    'F6': {'name': 'Claude Sonnet + busca Anthropic', 'kind': 'web', 'models': {
        'discover': 'anthropic/claude-sonnet-5', 'judge': 'anthropic/claude-sonnet-5', 'check': 'anthropic/claude-sonnet-5'}},
    'F7': {'name': 'Híbrido: Perplexity + RSS, juiz Sonnet', 'kind': 'perplexity', 'rss': True, 'models': {
        'discover_open': 'perplexity/sonar-pro', 'discover_press': 'perplexity/sonar',
        'discover_trends': 'perplexity/sonar', 'judge': 'anthropic/claude-sonnet-5', 'check': 'perplexity/sonar'}},
}
WEB_PLUGIN = [{'id': 'web', 'engine': 'native', 'max_results': 8}]
# A busca nativa da Anthropic injeta páginas inteiras (526 mil tokens numa chamada, US$ 1,25 na rodada de 2026-10-06);
# pelo Exa chegam trechos curtos.
WEB_PLUGIN_BY_PREFIX = {'anthropic/': [{'id': 'web', 'engine': 'exa', 'max_results': 6}]}
# Juiz e revisão escrevem até 5 oportunidades com critérios; modelos que raciocinam gastam parte disso pensando.
JUDGE_TOKENS = 9000
DOCTOR_MODEL = 'openai/gpt-5.4'
LETTERS = 'ABCDEFGHIJ'


def _web_plugin(model):
    return next((plugin for prefix, plugin in WEB_PLUGIN_BY_PREFIX.items() if str(model).startswith(prefix)), WEB_PLUGIN)


def _json_mode(model):
    """Só pede ``response_format`` a quem aceita; os demais recebem o pedido de JSON no próprio prompt."""
    return str(model).startswith(('openai/', 'google/', 'deepseek/', 'gpt-'))


# ---------------------------------------------------------------------------
# Preços e medição
# ---------------------------------------------------------------------------
_PRICES: dict = {}
_PRICES_LOCK = threading.Lock()


def prices():
    """Tabela pública do OpenRouter: USD por token de entrada, saída e por busca."""
    with _PRICES_LOCK:
        if not _PRICES:
            body = requests.get('https://openrouter.ai/api/v1/models', timeout=30).json()
            for item in body.get('data') or []:
                p = item.get('pricing') or {}
                _PRICES[item['id']] = {'in': float(p.get('prompt') or 0), 'out': float(p.get('completion') or 0),
                                       'web': float(p.get('web_search') or 0), 'req': float(p.get('request') or 0)}
    return _PRICES


def price_of(model):
    table = prices()
    return table.get(model) or table.get(f'openai/{model}') or {'in': 0, 'out': 0, 'web': 0, 'req': 0}


def _chars(messages):
    return sum(len(str(item.get('content') or '')) for item in messages)


@dataclass
class Call:
    flow: str
    stage: str
    kind: str                      # llm | firecrawl | python
    model: str
    route: str                     # openai | openrouter | firecrawl | python
    regime: str = ''               # custo (USD → token) | tokens (1:1) | firecrawl | gratis
    sim_usd: float = 0.0
    sim_tokens: int = 0            # tokens Cadu simulados (o que reservaríamos)
    real_usd: float | None = None  # custo do provedor informado (OpenRouter) ou calculado pela tabela
    real_tokens: int = 0           # tokens Cadu debitados de fato
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    ok: bool = True
    note: str = ''
    label: str = ''                # versão dos prompts na chamada
    preview: str = ''              # começo da resposta, para depurar formato


@dataclass
class Meter:
    calls: list = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, call):
        with self.lock:
            self.calls.append(call)


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def _text(message):
    from ..services.openrouter_service import message_text
    return message_text(message or {})


def google_news(query, recency_days, limit=12):
    """Google Notícias por RSS (gratuito): manchete, data e veículo de origem."""
    when = f' when:{min(recency_days, 30)}d' if recency_days else ''
    url = f'https://news.google.com/rss/search?q={quote_plus(query + when)}&hl=pt-BR&gl=BR&ceid=BR:pt-419'
    root = ET.fromstring(requests.get(url, headers=UA, timeout=15).content)
    items = []
    for node in root.iter('item'):
        source = node.find('source')
        items.append({'title': (node.findtext('title') or '').rsplit(' - ', 1)[0], 'url': node.findtext('link') or '',
                      'published_at': node.findtext('pubDate') or '',
                      'source_url': source.get('url') if source is not None else '',
                      'source_name': source.text if source is not None else ''})
        if len(items) >= limit:
            break
    return items


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
class Lab:
    def __init__(self, client_id, user_id, scenario, *, overrides=None, run_id=None, dry_run=False):
        self.client_id, self.user_id, self.scenario = int(client_id), int(user_id), scenario
        self.prompt_set, self.prompt_label = dict(prompts.V1_0), prompts.VERSION
        self.dry_run = dry_run  # só simula: nenhuma chamada paga, nenhum débito
        self.run_id = run_id or datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S') + '-' + uuid4().hex[:6]
        self.meter = Meter()
        self.flows = json.loads(json.dumps(FLOWS))
        for key, model in (overrides or {}).items():
            flow, stage = key.split('.', 1)
            self.flows[flow]['models'][stage] = model
        self.web_context = SimpleNamespace(client_id=self.client_id, user_id=self.user_id, conversation_id=None)
        from ..cadu_credit_connector import CaduCreditConnector
        self.credits = CaduCreditConnector()
        self.token_price_usd = float(self.credits._commercial_token_price_usd(self.client_id))

    # ---- contexto ------------------------------------------------------------
    def context(self):
        scenario = self.scenario
        brand = {'name': scenario.get('brand_name'), 'sector': scenario.get('sector'), 'facts': scenario.get('facts') or [],
                 'site': scenario.get('site') or ''}
        if scenario.get('brand_ref'):
            try:
                from ..cadu_planner.context import load_plan_context
                loaded = load_plan_context(self.client_id, scenario.get('brand_ref'), scenario.get('project_ref'))
                b, p = loaded.get('brand') or {}, loaded.get('project') or {}
                facts = [f"{item['label']}: {item['value']}" for item in (b.get('fields') or []) + (p.get('fields') or [])
                         if item.get('value')]
                brand.update(name=b.get('name') or brand['name'], sector=b.get('sector') or brand['sector'],
                             site=b.get('website_url') or brand['site'], facts=(facts or brand['facts'])[:14])
            except Exception as exc:  # noqa: BLE001 — o cenário inline basta
                brand['context_error'] = type(exc).__name__
        days = int(scenario.get('recency_days') or 30)
        return SimpleNamespace(
            brand=brand, focus=scenario.get('focus') or '', places=scenario.get('places') or 'Brasil',
            lenses=', '.join(scenario.get('lenses') or []), recency_days=days,
            recency='day' if days <= 1 else 'week' if days <= 7 else 'month' if days <= 31 else 'year',
            topic=' '.join(part for part in [scenario.get('focus'), brand['name'], brand['sector']] if part)[:240],
            today=datetime.now(timezone.utc).date().isoformat(),
            since=datetime.now(timezone.utc) - timedelta(days=days))

    # ---- chamadas pagas --------------------------------------------------------
    def _to_tokens(self, usd):
        return int(Decimal(str(usd)) / Decimal(str(self.token_price_usd)) + 1) if usd else 0

    def ai(self, flow, stage, model, messages, *, max_tokens=1800, provider='openrouter', json_mode=True,
           plugins=None, web_requests=0):
        price = price_of(model)
        sim_in = int(_chars(messages) / CHARS_PER_TOKEN)
        sim_out = int(min(max_tokens * OUTPUT_FILL, 3_000))  # o limite alto é folga, não o tamanho típico
        sim_usd = sim_in * price['in'] + sim_out * price['out'] + web_requests * (price['web'] or 0.005) + price['req']
        regime = 'tokens' if provider == 'openai' else 'custo'
        sim_tokens = (sim_in + sim_out) if regime == 'tokens' else self._to_tokens(sim_usd)
        call = Call(flow, stage, 'llm', model, provider, regime, round(sim_usd, 6), sim_tokens, label=self.prompt_label)
        options = {'max_tokens': max_tokens, 'timeout': 150, 'temperature': 0.1, 'provider': provider}
        if json_mode:
            options['response_format'] = {'type': 'json_object'}
        if plugins:
            options['plugins'] = plugins
        if self.dry_run:
            call.note = 'simulado (dry-run)'
            self.meter.add(call)
            return {}, []
        from ..services.cadu_ai_connector import CaduAIConnector
        started = time.monotonic()
        try:
            result = CaduAIConnector().complete(
                messages, client_id=self.client_id, user_id=self.user_id,
                idempotency_key=f'radar-lab:{self.run_id}:{self.prompt_label}:{flow}:{stage}', app=APP,
                stage=f'radar-lab:{flow}:{stage}', estimated_tokens=max(2_000, sim_tokens * 2), model=model,
                metadata={'radar_lab_run': self.run_id, 'flow': flow, 'stage': stage, 'prompt_version': self.prompt_label},
                **options)
        except Exception as exc:  # noqa: BLE001 — a falha entra no relatório
            call.ok, call.note, call.seconds = False, f'{type(exc).__name__}: {str(exc)[:160]}', time.monotonic() - started
            self.meter.add(call)
            return {}, []
        call.seconds = round(time.monotonic() - started, 1)
        usage = result.get('usage') or {}
        call.input_tokens = int(usage.get('prompt_tokens') or usage.get('input_tokens') or 0)
        call.output_tokens = int(usage.get('completion_tokens') or usage.get('output_tokens') or 0)
        cost = usage.get('cost') or result.get('actual_cost_usd')
        call.real_usd = round(float(cost), 6) if cost else round(call.input_tokens * price['in'] + call.output_tokens * price['out'], 6)
        if not cost:
            call.note = 'custo do provedor calculado pela tabela (a OpenAI direta não informa USD)'
        call.real_tokens = int(((result.get('cadu_charge') or {}).get('tokens_cobrados')) or 0)
        message = result.get('message') if isinstance(result.get('message'), dict) else {}
        call.preview = _text(message)[:400]
        self.meter.add(call)
        return message, citations(message)

    def _firecrawl_charged(self, request_id):
        from ..db import get_db
        with get_db().cursor() as cur:
            cur.execute('''SELECT COALESCE(SUM(tokens_cobrados), 0) AS tokens FROM cadu_tools_token_usage
                            WHERE id_cliente = %s AND idempotency_key LIKE %s''',
                        (self.client_id, f'%{request_id}%'))
            return int((cur.fetchone() or {}).get('tokens') or 0)

    def firecrawl_search(self, flow, stage, query, *, limit, include_domains=None, recency='month', hydrate=True):
        from ..cadu_workspace import web_search
        request_id = f'radar-lab:{self.run_id}:{flow}:{stage}'
        sim = self.credits.estimate_firecrawl_tokens('search', client_id=self.client_id, results=limit)
        if hydrate:
            sim += self.credits.estimate_firecrawl_tokens('scrape', client_id=self.client_id, pages=min(limit, 4))
        call = Call(flow, stage, 'firecrawl', 'firecrawl/search', 'firecrawl', 'firecrawl', sim_tokens=sim)
        if self.dry_run:
            call.note = 'simulado (dry-run)'
            self.meter.add(call)
            return []
        started = time.monotonic()
        try:
            result = web_search.search(self.web_context, {
                'query': query, 'depth': 'fast', 'limit': limit, 'recency': recency, 'include_content': hydrate,
                'include_domains': include_domains or [], 'request_id': request_id})
            rows = result.get('sources') or []
            call.note = f"{len(rows)} fontes, {result.get('sources_read', 0)} lidas"
        except Exception as exc:  # noqa: BLE001
            rows, call.ok, call.note = [], False, f'{type(exc).__name__}: {str(exc)[:160]}'
        call.seconds = round(time.monotonic() - started, 1)
        call.real_tokens = self._firecrawl_charged(request_id)
        call.real_usd = round(call.real_tokens * self.token_price_usd, 6)
        self.meter.add(call)
        return rows

    def read_pages(self, flow, stage, urls):
        """Firecrawl primeiro; o que falhar é lido de graça pelo leitor Python."""
        from ..cadu_workspace import web_search
        urls = [url for url in urls if url][:4] or ([f'https://exemplo.com.br/{i}' for i in range(4)] if self.dry_run else [])
        if not urls:
            return []
        request_id = f'radar-lab:{self.run_id}:{flow}:{stage}'
        call = Call(flow, stage, 'firecrawl', 'firecrawl/scrape', 'firecrawl', 'firecrawl',
                    sim_tokens=self.credits.estimate_firecrawl_tokens('scrape', client_id=self.client_id, pages=len(urls)))
        if self.dry_run:
            call.note = 'simulado (dry-run)'
            self.meter.add(call)
            return []
        started = time.monotonic()
        pages = {}
        try:
            for item in (web_search.read(self.web_context, {'urls': urls, 'request_id': request_id}).get('sources') or []):
                if item.get('content'):
                    pages[item.get('url')] = {**item, 'reader': 'firecrawl'}
        except Exception as exc:  # noqa: BLE001
            call.ok, call.note = False, f'{type(exc).__name__}: {str(exc)[:120]}'
        call.seconds = round(time.monotonic() - started, 1)
        call.real_tokens = self._firecrawl_charged(request_id)
        call.real_usd = round(call.real_tokens * self.token_price_usd, 6)
        self.meter.add(call)
        missing = [url for url in urls if url not in pages]
        if missing:
            free = Call(flow, f'{stage}-python', 'python', 'python/html', 'python', 'gratis')
            started, read = time.monotonic(), 0
            for url in missing:
                try:
                    pages[url] = {'url': url, **python_read(url), 'reader': 'python'}
                    read += 1
                except Exception:  # noqa: BLE001
                    continue
            free.seconds, free.note = round(time.monotonic() - started, 1), f'{read}/{len(missing)} lidas'
            self.meter.add(free)
        return list(pages.values())

    # ---- peças comuns dos fluxos ------------------------------------------------
    def _facts(self, message, cited):
        data = _json(_text(message))
        facts = [item for item in (data.get('fatos') or []) if isinstance(item, dict) and item.get('fato')]
        known = {item['url'] for item in cited}
        for item in facts:
            if item.get('url') and item['url'] not in known:
                cited.append({'url': item['url'], 'title': item.get('veiculo') or ''})
        return facts, cited

    def _packet(self, facts, pages, extra=()):
        """Evidências numeradas S1..Sn: fato com URL, página lida ou item de busca."""
        by_url = {page.get('url'): page for page in pages}
        packet = []
        for item in [*facts, *extra]:
            url = item.get('url') or ''
            page = by_url.pop(url, None)
            packet.append({'url': url, 'title': item.get('title') or item.get('veiculo') or item.get('fato', '')[:120],
                           'published_at': item.get('published_at') or item.get('data') or (page or {}).get('published_at'),
                           'excerpt': str((page or {}).get('content') or item.get('excerpt') or item.get('fato') or '')[:1400]})
        for page in by_url.values():
            packet.append({'url': page.get('url'), 'title': page.get('title') or page.get('page_title'),
                           'published_at': page.get('published_at'), 'excerpt': str(page.get('content') or '')[:1400]})
        unique, seen = [], set()
        for item in packet:
            key = item['url'] or item['title']
            if key and key not in seen:
                seen.add(key)
                unique.append(item)
        if self.dry_run and not unique:
            # Pacote de tamanho típico, para a simulação do juiz não sair barata demais.
            unique = [{'url': f'https://exemplo.com.br/{i}', 'title': 'Manchete de exemplo ' * 3,
                       'published_at': '2026-10-01', 'excerpt': 'texto ' * 230} for i in range(10)]
        return [{'id': f'S{index + 1}', **item} for index, item in enumerate(unique[:14])]

    def _msgs(self, name, **values):
        return prompts.messages(name, prompt_set=self.prompt_set, **values)

    def _parse(self, flow, message, packet):
        """Lista de oportunidades do juiz ou da revisão; notas e quadrante saem do scoring.py."""
        by_id = {item['id']: item for item in packet}
        if self.dry_run:
            message = {'content': json.dumps({'opportunities': [
                {'title': f'Oportunidade simulada {i + 1}', 'thesis': 'tese ' * 30, 'signals': [{'source_id': 'S1'}]}
                for i in range(5)]})}
        opportunities = []
        for item in (_json(_text(message)).get('opportunities') or [])[:5]:
            if not isinstance(item, dict) or not item.get('title'):
                continue
            penalties = _criteria(item.get('penalties'), scoring.PENALTY_CAPS)
            editorial = scoring.editorial_score(_criteria(item.get('editorial'), scoring.EDITORIAL_WEIGHTS), penalties)
            paid = scoring.paid_score(_criteria(item.get('paid'), scoring.PAID_WEIGHTS), penalties)
            used = [by_id[sig.get('source_id')] for sig in item.get('signals') or []
                    if isinstance(sig, dict) and sig.get('source_id') in by_id]
            opportunities.append({
                'flow': flow, 'title': str(item['title'])[:240], 'thesis': str(item.get('thesis') or '')[:1200],
                'editorial': editorial, 'paid': paid, 'quadrant': scoring.quadrant(editorial.score, paid.score),
                'sources': [{'id': src['id'], 'url': src['url'], 'title': src['title'], 'published_at': src['published_at']}
                            for src in used],
                'places': [str(p.get('place')) for p in item.get('places') or [] if isinstance(p, dict) and p.get('place')][:5],
                'channels': [str(c)[:60] for c in item.get('channels') or []][:6],
                'window': str(item.get('window') or '')[:120], 'verdict': 'nao_verificado', 'check_notes': '',
                'other_sources': []})
        return opportunities

    def _judge(self, flow, ctx, discovered_text, packet, stage='judge'):
        spec = self.flows[flow]
        model = spec['models']['judge']
        payload = prompts.judge_payload(ctx.topic, ctx.brand, discovered_text, packet, places=ctx.places, lenses=ctx.lenses)
        message, _ = self.ai(flow, stage, model, self._msgs('judge', max_opportunities=5, payload=payload),
                             max_tokens=JUDGE_TOKENS, provider=spec.get('judge_provider', 'openrouter'), json_mode=_json_mode(model))
        return self._parse(flow, message, packet)

    def _revise(self, flow, ctx, state, opportunities, round_no):
        """Uma volta do loop: o juiz reescreve a própria lista a partir das notas do revisor."""
        spec = self.flows[flow]
        model = spec['models']['judge']
        current = [{'titulo': item['title'], 'tese': item['thesis'], 'janela': item['window'], 'canais': item['channels'],
                    'evidencias_usadas': [src.get('id') for src in item['sources']],
                    'fontes': [{'id': src.get('id'), 'nivel': src.get('tier'), 'abre': src.get('url_status'),
                                'na_janela': src.get('in_window')} for src in item['sources']],
                    'verificacao': item['verdict'], 'nota_do_revisor': (item.get('review') or {}).get('media'),
                    'comentario_do_revisor': (item.get('review') or {}).get('nota')} for item in opportunities]
        payload = prompts.revise_payload(ctx.topic, ctx.brand, current, state['packet'], places=ctx.places)
        message, _ = self.ai(flow, f'revise-r{round_no}', model, self._msgs('revise', max_opportunities=5, payload=payload),
                             max_tokens=JUDGE_TOKENS, provider=spec.get('judge_provider', 'openrouter'), json_mode=_json_mode(model))
        revised = self._parse(flow, message, state['packet'])
        self._check(flow, ctx, revised, state['packet'], stage=f'check-r{round_no}')
        self.annotate(ctx, revised, state['packet'])
        return revised

    def _check(self, flow, ctx, opportunities, packet, stage='check'):
        if not opportunities:
            return
        kind, model = self.flows[flow]['kind'], self.flows[flow]['models']['check']
        if kind == 'evidence':
            payload = json.dumps({'oportunidades': [{'index': i, 'title': o['title'], 'thesis': o['thesis'], 'sources': o['sources']}
                                                   for i, o in enumerate(opportunities)], 'evidencias': packet}, ensure_ascii=False)
            message, cited = self.ai(flow, stage, model, self._msgs('verify', payload=payload), max_tokens=3000,
                                     json_mode=_json_mode(model))
        else:
            claims = '\n'.join(f"{index}. {item['title']} — {item['thesis']}" for index, item in enumerate(opportunities))
            message, cited = self.ai(flow, stage, model,
                                     self._msgs('reality_check', recency_days=ctx.recency_days, today=ctx.today, claims=claims),
                                     max_tokens=3000, json_mode=False, web_requests=1,
                                     plugins=_web_plugin(model) if kind == 'web' else None)
        self._apply_verdicts(opportunities, _json(_text(message)).get('results') or [], cited)

    @staticmethod
    def _apply_verdicts(opportunities, results, cited):
        for result in results:
            if not isinstance(result, dict) or not str(result.get('index', '')).isdigit():
                continue
            index = int(result['index'])
            if index >= len(opportunities):
                continue
            item = opportunities[index]
            verdict = result.get('verdict') if result.get('verdict') in ('confirmado', 'parcial', 'contestado') else 'nao_verificado'
            item['verdict'] = verdict
            item['check_notes'] = str(result.get('notes') or result.get('contradiction') or '')[:400]
            item['contradicted'] = bool(str(result.get('contradiction') or '').strip()) or verdict == 'contestado'
            item['other_sources'] = [str(url) for url in result.get('other_sources') or [] if str(url).startswith('http')][:5]
        for item in opportunities:
            # Mesma regra do pipeline R1: evidência fraca baixa as duas notas.
            points = {'contestado': 20, 'nao_verificado': 12, 'parcial': 6}.get(item['verdict'])
            if points:
                for key, weights in (('editorial', scoring.EDITORIAL_WEIGHTS), ('paid', scoring.PAID_WEIGHTS)):
                    item[key] = scoring.weighted(item[key].criteria, weights, {**item[key].penalties, 'baixa_confianca': points})
                item['quadrant'] = 'ignorar' if item['verdict'] == 'contestado' else scoring.quadrant(item['editorial'].score, item['paid'].score)

    # ---- descoberta (uma vez por fluxo; as versões de prompt reaproveitam o pacote) ----
    def _base(self, ctx):
        domains = source_base.press_domains(ctx.places)
        return domains, dict(topic=ctx.topic, places=ctx.places, lenses=ctx.lenses, recency_days=ctx.recency_days,
                             brand_facts='; '.join(ctx.brand['facts']) or 'não informado', sector=ctx.brand.get('sector') or '',
                             domains=', '.join(domains))

    def _collect(self, results, domains):
        facts, cited, texts = [], [], []
        allowed = {source_base.root(d) for d in domains}
        for stage, (message, urls) in results.items():
            found, urls = self._facts(message, list(urls))
            if stage == 'discover_press':
                # Plano B do filtro de domínio: o que não é da lista curada sai.
                found = [f for f in found if source_base.root(f.get('url', '')) in allowed]
            facts += found
            cited += urls
            texts.append(_text(message)[:2500])
        return facts, cited, texts

    def discover_perplexity(self, flow, ctx):
        m = self.flows[flow]['models']
        domains, base = self._base(ctx)
        stages = ('discover_open', 'discover_press', 'discover_trends')
        results = self._parallel({stage: (lambda s=stage: self.ai(
            flow, s, m[s], self._msgs(s, **base), max_tokens=1800, json_mode=False, web_requests=1)) for stage in stages})
        facts, cited, texts = self._collect(results, domains)
        pages = self.read_pages(flow, 'extract', [item['url'] for item in cited])
        extra = self._rss(flow, ctx) if self.flows[flow].get('rss') else []
        return {'packet': self._mark_rss(self._packet(facts, pages, extra=extra), extra), 'text': '\n\n'.join(texts)}

    def discover_web(self, flow, ctx):
        model = self.flows[flow]['models']['discover']
        domains, base = self._base(ctx)
        results = self._parallel({stage: (lambda s=stage: self.ai(
            flow, s, model, self._msgs(s, **base), max_tokens=3000, json_mode=False, plugins=_web_plugin(model), web_requests=1))
            for stage in ('discover_open', 'discover_press')})
        facts, cited, texts = self._collect(results, domains)
        packet = self._packet(facts, [], extra=[{'url': c['url'], 'title': c['title']} for c in cited])
        return {'packet': packet, 'text': '\n\n'.join(texts)}

    def discover_evidence(self, flow, ctx):
        domains = source_base.press_domains(ctx.places)
        query = ' '.join(part for part in [ctx.focus, ctx.brand['name']] if part) or ctx.topic
        rss = self._rss(flow, ctx)
        found = self.firecrawl_search(flow, 'search', f'{query} {ctx.places}', limit=8,
                                      include_domains=domains[:20], recency=ctx.recency)
        if not found:
            # Com muitos domínios no filtro o Firecrawl costuma voltar vazio: tenta a web aberta.
            found = self.firecrawl_search(flow, 'search-open', f'{query} {ctx.places}', limit=8, recency=ctx.recency)
        unread = [item['url'] for item in found if not item.get('content')]
        pages = [item for item in found if item.get('content')] + (self.read_pages(flow, 'extract', unread) if unread else [])
        return {'packet': self._mark_rss(self._packet([], pages, extra=rss), rss), 'text': ''}

    def _rss(self, flow, ctx):
        """Google Notícias (grátis): marca + (termo OR termo) e (termos) + praça."""
        started = time.monotonic()
        terms = [t.strip() for t in re.split(r',|;|\be\b', ctx.focus) if len(t.strip()) > 2][:5]
        ors = ' OR '.join(f'"{t}"' if ' ' in t else t for t in terms)
        queries = [f"{ctx.brand['name']} ({ors})" if ors else ctx.brand['name'], f'({ors}) {ctx.places.split(",")[0]}' if ors else '']
        news, seen = [], set()
        try:
            for rss_query in [q for q in queries if q]:
                for item in google_news(rss_query, ctx.recency_days):
                    if item['title'] not in seen:
                        seen.add(item['title'])
                        news.append(item)
            note = f'{len(news)} manchetes'
        except Exception as exc:  # noqa: BLE001
            note = type(exc).__name__
        self.meter.add(Call(flow, 'google_news', 'python', 'python/rss', 'python', 'gratis',
                            seconds=round(time.monotonic() - started, 1), note=note))
        return [{'url': item['url'], 'title': f"{item['title']} ({item['source_name']})", 'published_at': item['published_at'],
                 'excerpt': item['title'], 'domain_hint': item['source_url']} for item in news]

    @staticmethod
    def _mark_rss(packet, rss):
        hints = {item['url']: item['domain_hint'] for item in rss}
        for item in packet:
            if item['url'] in hints:
                item['source_domain'] = source_base.host(hints[item['url']])
        return packet

    def discover(self, flow, ctx):
        kind = self.flows[flow]['kind']
        runner = {'perplexity': self.discover_perplexity, 'web': self.discover_web, 'evidence': self.discover_evidence}[kind]
        return runner(flow, ctx)

    def _parallel(self, jobs, workers=None):
        from flask import current_app
        app = current_app._get_current_object()

        def run(function):
            with app.app_context():
                return function()

        with ThreadPoolExecutor(max_workers=max(1, workers or len(jobs))) as pool:
            futures = {key: pool.submit(run, function) for key, function in jobs.items()}
            return {key: future.result() for key, future in futures.items()}

    # ---- medição determinística e revisor ---------------------------------------
    def annotate(self, ctx, opportunities, packet):
        """Nível de cada fonte, se abre, se está na janela, e o selo de confiança."""
        domain_of = {item['url']: item.get('source_domain') for item in packet}
        urls = sorted({src['url'] for item in opportunities for src in item['sources'] if src['url']})
        with ThreadPoolExecutor(max_workers=8) as pool:
            status = dict(zip(urls, pool.map(check_url, urls)))
        for item in opportunities:
            for src in item['sources']:
                look_url = domain_of.get(src['url']) or src['url']
                src.update(source_base.lookup(look_url, ctx.brand.get('site')))
                src['url_status'] = status.get(src['url'], 'sem_url')
                when = _date(src.get('published_at'))
                src['in_window'] = None if when is None else when >= ctx.since
            # Link quebrado não sustenta nada: fica fora do selo.
            alive = [domain_of.get(src['url']) or src['url'] for src in item['sources'] if src['url_status'] != 'quebrado']
            item['confidence'] = source_base.confidence(
                alive + item.get('other_sources', []),
                ctx.brand.get('site'), contradicted=item.get('contradicted', False))
            if item['confidence'] == 'baixa':
                item['quadrant'] = 'ignorar'

    def review(self, ctx, by_flow, tag):
        """Nota cega: os fluxos viram letras embaralhadas a cada passada."""
        flows = [flow for flow, items in by_flow.items() if items]
        random.Random(f'{self.run_id}:{tag}').shuffle(flows)
        mapping = {flow: LETTERS[index] for index, flow in enumerate(flows)}
        systems = {mapping[flow]: [{
            'id': f'{mapping[flow]}{index + 1}', 'title': item['title'], 'thesis': item['thesis'],
            'editorial': item['editorial'].score, 'paid': item['paid'].score, 'quadrant': item['quadrant'],
            'janela': item['window'], 'selo_confianca': item['confidence'], 'veredito': item['verdict'],
            'fontes': [{'dominio': s.get('domain'), 'nivel': s.get('tier'), 'abre': s.get('url_status'),
                        'data': s.get('published_at'), 'na_janela': s.get('in_window'), 'url': s['url']} for s in item['sources']]}
            for index, item in enumerate(by_flow[flow])] for flow in flows}
        if not systems:
            return {}
        payload = json.dumps({'hoje': ctx.today, 'janela_dias': ctx.recency_days, 'marca': ctx.brand, 'tema': ctx.focus,
                              'pracas': ctx.places, 'sistemas': systems}, ensure_ascii=False)
        message, _ = self.ai('REV', f'review-{tag}', REVIEW_MODEL, self._msgs('review', payload=payload), max_tokens=7000,
                             json_mode=False)
        verdict = _json(_text(message))
        back = {letter: flow for flow, letter in mapping.items()}
        verdict['mapping'] = mapping
        verdict['winner_flow'] = back.get(verdict.get('vencedor'))
        scores = {}
        for row in verdict.get('opportunities') or []:
            if isinstance(row, dict) and row.get('id'):
                values = [row.get(key) for key in ('veracidade', 'recencia', 'aderencia', 'acao', 'novidade')]
                numbers = [float(v) for v in values if isinstance(v, (int, float))]
                scores[row['id']] = {**row, 'media': round(sum(numbers) / len(numbers), 2) if numbers else None}
        for flow in flows:
            for index, item in enumerate(by_flow[flow]):
                item['review'] = scores.get(f'{mapping[flow]}{index + 1}')
        return verdict

    # ---- avaliação com loop de revisão ----------------------------------------------
    def evaluate(self, ctx, states, flows, *, revise_rounds=2, target=4.2):
        """Juiz → checagem → nota cega; quem fica abaixo da meta revisa a própria lista, até ``revise_rounds`` voltas.

        Cada volta reavalia todos os fluxos juntos; os que não revisaram mostram o ruído do revisor.
        Fica a melhor versão de cada fluxo.
        """
        live = [flow for flow in flows if states.get(flow)]

        def first(flow):
            items = self._judge(flow, ctx, states[flow]['text'], states[flow]['packet'])
            self._check(flow, ctx, items, states[flow]['packet'])
            self.annotate(ctx, items, states[flow]['packet'])
            return items

        current = self._parallel({flow: (lambda f=flow: first(f)) for flow in live}, workers=4)
        reviews = [self.review(ctx, current, f'{self.prompt_label}-r0')]
        history = {flow: [self._snapshot(current[flow], 0, False)] for flow in live}
        best = {flow: current[flow] for flow in live}
        for round_no in range(1, revise_rounds + 1):
            # Para quem já tem MIN_GOOD oportunidades boas e média na meta; o resto revisa.
            todo = [flow for flow in live if current[flow]
                    and (len(_good(best[flow])) < MIN_GOOD or (_avg(best[flow]) or 0) < target)]
            if not todo:
                break
            # Revisa sempre a melhor versão: se a volta anterior piorou, não se constrói em cima dela.
            revised = self._parallel({flow: (lambda f=flow: self._revise(f, ctx, states[f], best[f], round_no))
                                      for flow in todo}, workers=4)
            for flow in todo:
                if revised[flow]:
                    current[flow] = revised[flow]
            reviews.append(self.review(ctx, current, f'{self.prompt_label}-r{round_no}'))
            for flow in live:
                history[flow].append(self._snapshot(current[flow], round_no, flow in todo))
                if (_points(current[flow]), _avg(current[flow]) or 0) > (_points(best[flow]), _avg(best[flow]) or 0):
                    best[flow] = current[flow]
        return {'label': self.prompt_label, 'by_flow': best,
                'score': {flow: _points(best[flow]) for flow in live},
                'avg': {flow: _avg(best[flow]) for flow in live}, 'history': history, 'reviews': reviews}

    @staticmethod
    def _snapshot(items, round_no, revised):
        return {'round': round_no, 'avg': _avg(items), 'points': _points(items), 'good': len(_good(items)),
                'n': len(items or []), 'revised': revised}

    def doctor(self, ctx, evaluation):
        """Médico de prompts: diagnóstico da avaliação → até 3 mudanças nos prompts editáveis."""
        notes = sorted(((item.get('review') or {}).get('media') or 0, flow, item['title'], (item.get('review') or {}).get('nota'))
                       for flow, items in evaluation['by_flow'].items() for item in items)
        final_review = evaluation['reviews'][-1] if evaluation['reviews'] else {}
        diagnosis = {
            'media_do_revisor_por_fluxo_1_a_5': evaluation['avg'],
            'pontos_por_fluxo': evaluation['score'],
            'como_ler_pontos': 'soma das notas (1 a 5) das oportunidades boas: nota >= 4 e selo de confiança diferente de baixa',
            'oportunidades_boas_por_fluxo': {flow: len(_good(items)) for flow, items in evaluation['by_flow'].items()},
            'piores_oportunidades': [{'fluxo': f, 'titulo': t, 'nota': n, 'comentario': c} for n, f, t, c in notes[:12]],
            'resumo_por_sistema': final_review.get('systems'),
            'falhas': {flow: {'fontes_c': sum(s.get('tier') == 'C' for o in items for s in o['sources']),
                              'links_quebrados': sum(s.get('url_status') == 'quebrado' for o in items for s in o['sources']),
                              'sem_fonte': sum(not o['sources'] for o in items),
                              'nao_verificadas': sum(o['verdict'] == 'nao_verificado' for o in items)}
                       for flow, items in evaluation['by_flow'].items()}}
        current = {name: self.prompt_set[name][0] for name in prompts.EDITABLE}
        payload = json.dumps({'prompts_atuais': current, 'diagnostico': diagnosis}, ensure_ascii=False)
        message, _ = self.ai('DOC', f'doctor-{self.prompt_label}', DOCTOR_MODEL, self._msgs('prompt_doctor', payload=payload),
                             max_tokens=9000, json_mode=_json_mode(DOCTOR_MODEL))
        return _json(_text(message)).get('changes') or []

    # ---- orquestração -----------------------------------------------------------
    def run(self, flows=('F1', 'F2', 'F3'), *, revise_rounds=2, target=4.2, prompt_loops=1):
        prices()
        ctx = self.context()
        started = time.monotonic()
        durations = {}

        def timed(flow):
            began = time.monotonic()
            try:
                return self.discover(flow, ctx)
            except Exception as exc:  # noqa: BLE001 — um fluxo quebrado não derruba os outros
                self.meter.add(Call(flow, 'discover', 'llm', '', '', ok=False, note=f'{type(exc).__name__}: {str(exc)[:200]}'))
                return None
            finally:
                durations[flow] = round(time.monotonic() - began, 1)

        states = self._parallel({flow: (lambda f=flow: timed(f)) for flow in flows}, workers=4)
        evaluations = [self.evaluate(ctx, states, flows, revise_rounds=revise_rounds, target=target)]
        best_index, best_set = 0, dict(self.prompt_set)
        changes_log = []
        for loop in range(1, prompt_loops + 1):
            # O médico sempre lê e edita a melhor versão até aqui, nunca uma candidata que perdeu.
            self.prompt_set, self.prompt_label = best_set, evaluations[best_index]['label']
            changes = self.doctor(ctx, evaluations[best_index])
            candidate, accepted, rejected = prompts.apply_changes(best_set, changes)
            changes_log.append({'label': f'1.{loop}', 'from': evaluations[best_index]['label'],
                                'accepted': accepted, 'rejected': rejected})
            if not accepted:
                break
            self.prompt_set, self.prompt_label = candidate, f'1.{loop}'
            evaluations.append(self.evaluate(ctx, states, flows, revise_rounds=revise_rounds, target=target))
            if _mean(evaluations[-1]['score']) > _mean(evaluations[best_index]['score']):
                best_index, best_set = len(evaluations) - 1, candidate
        return self.summary(ctx, states, evaluations, best_index, best_set, changes_log, durations,
                            round(time.monotonic() - started, 1))

    def summary(self, ctx, states, evaluations, best_index, best_set, changes_log, durations, total_seconds):
        calls = [asdict(call) for call in self.meter.calls]
        best = evaluations[best_index]
        flows = {}
        for flow, opportunities in best['by_flow'].items():
            mine = [c for c in calls if c['flow'] == flow]
            srcs = [s for item in opportunities for s in item['sources']]
            flows[flow] = {
                'name': self.flows[flow]['name'], 'kind': self.flows[flow]['kind'], 'models': self.flows[flow]['models'],
                'discover_seconds': durations.get(flow), 'opportunities': len(opportunities),
                'review_avg': best['avg'].get(flow), 'points': best['score'].get(flow), 'good': len(_good(opportunities)),
                'history': {ev['label']: [f"{h['points']} ({h['good']}/{h['n']})" for h in ev['history'].get(flow, [])]
                            for ev in evaluations},
                'evidence': len((states.get(flow) or {}).get('packet') or []),
                'sources': len(srcs),
                'sources_ab_pct': _pct(sum(s.get('tier') in ('A', 'B') for s in srcs), len(srcs)),
                'urls_ok_pct': _pct(sum(s.get('url_status') in ('ok', 'bloqueado') for s in srcs), len(srcs)),
                'in_window_pct': _pct(sum(bool(s.get('in_window')) for s in srcs), sum(s.get('in_window') is not None for s in srcs)),
                'confidence': {level: sum(o['confidence'] == level for o in opportunities) for level in ('alta', 'media', 'baixa')},
                'sim_tokens': sum(c['sim_tokens'] for c in mine), 'real_tokens': sum(c['real_tokens'] for c in mine),
                'provider_usd': round(sum(c['real_usd'] or 0 for c in mine), 4),
                'failed_calls': sum(not c['ok'] for c in mine)}
        serial = {flow: [{**item, 'editorial': item['editorial'].score, 'paid': item['paid'].score,
                          'editorial_breakdown': asdict(item['editorial']), 'paid_breakdown': asdict(item['paid'])}
                         for item in items] for flow, items in best['by_flow'].items()}
        noise = []
        for ev in evaluations:
            for flow, rows in ev['history'].items():
                for before, after in zip(rows, rows[1:]):
                    if not after['revised'] and before['avg'] is not None and after['avg'] is not None:
                        noise.append(abs(after['avg'] - before['avg']))
        return {'run_id': self.run_id, 'scenario': self.scenario, 'context': {**vars(ctx), 'since': ctx.since.isoformat()},
                'token_price_usd': self.token_price_usd, 'radar_r1_reserve': 15_207, 'seconds': total_seconds,
                'flows': flows, 'calls': calls, 'opportunities': serial,
                'versions': [{'label': ev['label'], 'mean': _mean(ev['score']), 'score': ev['score'],
                              'winner': (ev['reviews'][-1] or {}).get('winner_flow') if ev['reviews'] else None} for ev in evaluations],
                'best_version': best['label'], 'prompt_changes': changes_log,
                'best_prompts': {name: best_set[name][0] for name in prompts.EDITABLE},
                'reviewer_noise': round(sum(noise) / len(noise), 2) if noise else None,
                'review': best['reviews'][-1] if best['reviews'] else {}}


GOOD_SCORE, MIN_GOOD = 4.0, 3


def _good(items):
    """Oportunidades que um planejador usaria: nota do revisor ≥ 4 e selo de confiança diferente de baixa."""
    return [item for item in items or [] if ((item.get('review') or {}).get('media') or 0) >= GOOD_SCORE
            and item.get('confidence') != 'baixa']


def _points(items):
    """Objetivo do loop: soma das notas das oportunidades boas. Cortar item bom perde pontos; item fraco não soma."""
    return round(sum(item['review']['media'] for item in _good(items)), 2)


def _avg(items):
    values = [(item.get('review') or {}).get('media') for item in items or []]
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 2) if values else None


def _mean(scores):
    values = [value for value in (scores or {}).values() if value is not None]
    return round(sum(values) / len(values), 3) if values else 0


def _pct(part, whole):
    return round(100 * part / whole) if whole else None


def _criteria(raw, allowed):
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for key, value in raw.items():
        if key not in allowed:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        clean[key] = max(0, min(allowed[key] if allowed is scoring.PENALTY_CAPS else 100, number))
    return clean


def report_markdown(result):
    """Relatório: fluxos, versões de prompt, loop de revisão, custo simulado x real e oportunidades."""
    ctx = result['context']
    lines = [f"# Radar Lab — {result['run_id']}", '',
             f"Cenário **{result['scenario'].get('name')}** · tema: {ctx['focus'] or '—'} · praças: {ctx['places']} · "
             f"janela: {ctx['recency_days']} dias · 1 token Cadu = US$ {result['token_price_usd']:.8f} · "
             f"tempo total {result['seconds']} s", '',
             f"Melhor versão de prompts: **{result['best_version']}** · ruído médio da média do revisor (fluxo sem mudança, "
             f"de uma passada para outra): {result['reviewer_noise'] if result['reviewer_noise'] is not None else '—'} ponto(s)", '',
             '## Comparação dos fluxos (melhor versão de cada um)', '',
             'Critério: **pontos** = soma das notas do revisor das oportunidades **boas** (nota ≥ 4 e selo ≠ baixa). '
             'Cortar uma oportunidade boa perde pontos; uma fraca não soma.', '',
             '| Fluxo | Tipo | Pontos | Boas/total | Média revisor | Pontos por volta: pontos (boas/total) | Evidências | Fontes A/B | URLs abrem | Na janela | Selo a/m/b | Tokens sim. | Tokens debitados | US$ provedor |',
             '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    ranked = sorted(result['flows'].items(), key=lambda kv: (-(kv[1]['points'] or 0), -(kv[1]['review_avg'] or 0)))
    for flow, row in ranked:
        conf = row['confidence']
        hist = ' · '.join(f"v{label}: {' → '.join(values)}"
                          for label, values in row['history'].items() if values)
        lines.append(f"| {flow} {row['name']} | {row['kind']} | **{row['points']}** | {row['good']}/{row['opportunities']} | "
                     f"{row['review_avg'] or '—'} | {hist} | "
                     f"{row['evidence']} | {_p(row['sources_ab_pct'])} | {_p(row['urls_ok_pct'])} | {_p(row['in_window_pct'])} | "
                     f"{conf['alta']}/{conf['media']}/{conf['baixa']} | {_n(row['sim_tokens'])} | {_n(row['real_tokens'])} | "
                     f"{row['provider_usd']:.4f} |")
    calls = result['calls']
    shared = [c for c in calls if c['flow'] in ('REV', 'DOC')]
    lines += ['', f"Revisor e médico de prompts (compartilhados): {_n(sum(c['real_tokens'] for c in shared))} tokens debitados, "
              f"US$ {sum(c['real_usd'] or 0 for c in shared):.4f}. Total da rodada: {_n(sum(c['real_tokens'] for c in calls))} tokens, "
              f"US$ {sum(c['real_usd'] or 0 for c in calls):.4f}.", '', '## Versões de prompt', '',
              '| Versão | Pontos médios por fluxo | Vencedor do revisor | Pontos por fluxo |', '|---|---|---|---|']
    for version in result['versions']:
        notes = ', '.join(f"{flow} {score}" for flow, score in sorted(version['score'].items()))
        lines.append(f"| {version['label']} | {version['mean']} | {version['winner'] or '—'} | {notes} |")
    for change in result['prompt_changes']:
        lines += ['', f"**Médico de prompts → v{change['label']}** (a partir da v{change['from']}): "
                  f"{len(change['accepted'])} mudança(s) aceita(s), {len(change['rejected'])} recusada(s)."]
        for item in change['accepted']:
            lines.append(f"- `{item.get('prompt')}`: {item.get('why', '')}")
        for item in change['rejected']:
            lines.append(f"- recusada `{item.get('prompt')}`: {item.get('motivo')}")
    review = result.get('review') or {}
    if review.get('winner_flow'):
        back = {letter: flow for flow, letter in (review.get('mapping') or {}).items()}
        lines += ['', f"**Revisor ({REVIEW_MODEL}), última passada da melhor versão:** vencedor {review['winner_flow']}. "
                  f"{review.get('por_que', '')}"]
        for system in review.get('systems') or []:
            lines.append(f"- {back.get(system.get('system'), system.get('system'))}: {system.get('resumo', '')} "
                         f"Melhor em: {system.get('melhor_em', '')}. Pior em: {system.get('pior_em', '')}.")
    lines += ['', '## Custo por chamada: simulado x real', '',
              '| Versão | Fluxo | Etapa | Modelo | Rota | Regime | Simulado | Debitado | US$ provedor | Entrada/saída | Tempo | Nota |',
              '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for c in calls:
        lines.append(f"| {c.get('label', '')} | {c['flow']} | {c['stage']} | {c['model']} | {c['route']} | {c['regime']} | "
                     f"{_n(c['sim_tokens'])} | {_n(c['real_tokens'])} | {(c['real_usd'] or 0):.5f} | "
                     f"{_n(c['input_tokens'])}/{_n(c['output_tokens'])} | {c['seconds']} s | {'' if c['ok'] else 'FALHOU '}{c['note']} |")
    lines += ['', '## Oportunidades (melhor versão de cada fluxo)', '']
    for flow, row in ranked:
        lines += [f"### {flow} — {row['name']} · revisor {row['review_avg'] or '—'}", '']
        for item in result['opportunities'].get(flow, []):
            rev = item.get('review') or {}
            lines.append(f"- **{item['title']}** · {item['quadrant']} · ed {item['editorial']} / pago {item['paid']} · "
                         f"selo {item['confidence']} · verificação {item['verdict']} · revisor {rev.get('media', '—')}")
            lines.append(f"  {item['thesis']}")
            for src in item['sources']:
                lines.append(f"  - [{src.get('tier')}] {src.get('domain')} · {src.get('url_status')} · "
                             f"{src.get('published_at') or 's/ data'} · {src['url']}")
            if rev.get('nota'):
                lines.append(f"  Revisor: {rev['nota']}")
        lines.append('')
    return '\n'.join(lines)


def _n(value):
    """Milhar com ponto, sem tocar no resto da linha."""
    return f'{int(value or 0):,}'.replace(',', '.')


def _p(value):
    return '—' if value is None else f'{value}%'


__all__ = ['FLOWS', 'Lab', 'report_markdown', 'QUADRANTS']
