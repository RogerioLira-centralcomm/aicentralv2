"""Lab do Radar: fluxos de pesquisa comparados lado a lado, com custo simulado e real.

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
from html.parser import HTMLParser
from types import SimpleNamespace
from urllib.parse import quote_plus
from uuid import uuid4

import requests

from . import prompts, scoring, sources as source_base
from .contracts import QUADRANTS

APP = 'Cadu Radar'
REVIEW_MODEL = 'anthropic/claude-haiku-4.5'
CHARS_PER_TOKEN = 3.6       # português, medido grosso
OUTPUT_FILL = 0.6           # fração do max_tokens que costuma sair
UA = {'User-Agent': 'Mozilla/5.0 (compatible; CaduRadarLab/1.0; +https://centralcomm.media)'}

# Os três fluxos. Modelos trocáveis pela linha de comando (``--model F1.judge=...``).
FLOWS = {
    'F1': {'name': 'Perplexity + imprensa', 'models': {
        'discover_open': 'perplexity/sonar-pro', 'discover_press': 'perplexity/sonar',
        'discover_trends': 'perplexity/sonar', 'judge': 'openai/gpt-5.4-mini', 'check': 'perplexity/sonar'}},
    'F2': {'name': 'OpenAI nativo', 'models': {
        'discover_open': 'openai/gpt-5-mini', 'discover_press': 'openai/gpt-5-mini',
        'judge': 'gpt-5-mini', 'check': 'openai/gpt-5-mini'}},
    'F3': {'name': 'Evidência primeiro (Firecrawl + Python)', 'models': {
        'judge': 'google/gemini-2.5-flash', 'check': 'deepseek/deepseek-v3.2'}},
}


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
def _json(text):
    text = str(text or '').strip()
    text = re.sub(r'^```(?:json)?|```$', '', text, flags=re.M).strip()
    match = re.search(r'\{.*\}', text, re.S)
    try:
        return json.loads(match.group(0) if match else text)
    except (ValueError, AttributeError):
        return {}


def _text(message):
    from ..services.openrouter_service import message_text
    return message_text(message or {})


def citations(message):
    """URLs citadas, venham do Perplexity (_cadu_citations) ou de anotações url_citation."""
    found = []
    raw = (message or {}).get('_cadu_citations') or []
    if isinstance(raw, dict):
        raw = raw.get('search_results') or raw.get('citations') or []
    for item in raw if isinstance(raw, list) else []:
        url = item if isinstance(item, str) else (item.get('url') or item.get('link') or '') if isinstance(item, dict) else ''
        title = item.get('title') if isinstance(item, dict) else ''
        if url:
            found.append({'url': str(url), 'title': str(title or '')})
    for note in (message or {}).get('annotations') or []:
        cite = (note or {}).get('url_citation') if isinstance(note, dict) else None
        if isinstance(cite, dict) and cite.get('url'):
            found.append({'url': cite['url'], 'title': cite.get('title') or ''})
    seen, unique = set(), []
    for item in found:
        key = item['url'].split('#')[0].rstrip('/').split('?utm_')[0]
        if key not in seen:
            seen.add(key)
            unique.append({**item, 'url': key})
    return unique


def _date(value):
    text = str(value or '').strip()
    if not text:
        return None
    for parse in (lambda v: datetime.fromisoformat(v.replace('Z', '+00:00')), parsedate_to_datetime):
        try:
            parsed = parse(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    match = re.search(r'(20\d\d)-(\d\d)-(\d\d)', text)
    return datetime(int(match[1]), int(match[2]), int(match[3]), tzinfo=timezone.utc) if match else None


class _Text(HTMLParser):
    SKIP = {'script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'noscript'}

    def __init__(self):
        super().__init__()
        self.parts, self.depth, self.title, self._in_title = [], 0, '', False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        self._in_title = tag == 'title'

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.depth and len(data.strip()) > 40:
            self.parts.append(' '.join(data.split()))


def python_read(url, limit=6000):
    """Leitura gratuita por HTTP + parser da biblioteca padrão (reserva do Firecrawl)."""
    response = requests.get(url, headers=UA, timeout=12, allow_redirects=True)
    response.raise_for_status()
    parser = _Text()
    parser.feed(response.text[:600_000])
    return {'title': parser.title.strip()[:220], 'content': '\n'.join(parser.parts)[:limit]}


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


def check_url(url):
    """'ok', 'bloqueado' (existe, mas recusa robô) ou 'quebrado'."""
    try:
        response = requests.get(url, headers=UA, timeout=10, allow_redirects=True, stream=True)
        response.close()
    except requests.RequestException:
        return 'quebrado'
    if response.status_code < 400:
        return 'ok'
    return 'bloqueado' if response.status_code in (401, 402, 403, 429, 451) else 'quebrado'


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
class Lab:
    def __init__(self, client_id, user_id, scenario, *, overrides=None, run_id=None, dry_run=False):
        self.client_id, self.user_id, self.scenario = int(client_id), int(user_id), scenario
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
        sim_out = int(max_tokens * OUTPUT_FILL)
        sim_usd = sim_in * price['in'] + sim_out * price['out'] + web_requests * (price['web'] or 0.005) + price['req']
        regime = 'tokens' if provider == 'openai' else 'custo'
        sim_tokens = (sim_in + sim_out) if regime == 'tokens' else self._to_tokens(sim_usd)
        call = Call(flow, stage, 'llm', model, provider, regime, round(sim_usd, 6), sim_tokens)
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
                idempotency_key=f'radar-lab:{self.run_id}:{flow}:{stage}', app=APP, stage=f'radar-lab:{flow}:{stage}',
                estimated_tokens=max(2_000, sim_tokens * 2), model=model,
                metadata={'radar_lab_run': self.run_id, 'flow': flow, 'stage': stage, 'prompt_version': prompts.VERSION},
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
        self.meter.add(call)
        message = result.get('message') if isinstance(result.get('message'), dict) else {}
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

    def _judge(self, flow, ctx, discovered_text, packet, provider='openrouter'):
        model = self.flows[flow]['models']['judge']
        payload = prompts.judge_payload(ctx.topic, ctx.brand, discovered_text, packet, places=ctx.places, lenses=ctx.lenses)
        message, _ = self.ai(flow, 'judge', model, prompts.messages('judge', max_opportunities=5, payload=payload),
                             max_tokens=3200, provider=provider)
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
                'sources': [{'url': src['url'], 'title': src['title'], 'published_at': src['published_at']} for src in used],
                'places': [str(p.get('place')) for p in item.get('places') or [] if isinstance(p, dict) and p.get('place')][:5],
                'channels': [str(c)[:60] for c in item.get('channels') or []][:6],
                'window': str(item.get('window') or '')[:120], 'verdict': 'nao_verificado', 'check_notes': '',
                'other_sources': []})
        return opportunities

    def _reality_check(self, flow, ctx, opportunities, *, plugins=None):
        if not opportunities:
            return
        claims = '\n'.join(f"{index}. {item['title']} — {item['thesis']}" for index, item in enumerate(opportunities))
        message, cited = self.ai(flow, 'check', self.flows[flow]['models']['check'],
                                 prompts.messages('reality_check', recency_days=ctx.recency_days, today=ctx.today, claims=claims),
                                 max_tokens=1600, json_mode=False, plugins=plugins, web_requests=1)
        self._apply_verdicts(opportunities, _json(_text(message)).get('results') or [], cited)

    def _internal_verify(self, flow, opportunities, packet):
        if not opportunities:
            return
        payload = json.dumps({'oportunidades': [{'index': i, 'title': o['title'], 'thesis': o['thesis'], 'sources': o['sources']}
                                               for i, o in enumerate(opportunities)], 'evidencias': packet}, ensure_ascii=False)
        message, _ = self.ai(flow, 'check', self.flows[flow]['models']['check'], prompts.messages('verify', payload=payload),
                             max_tokens=1600)
        self._apply_verdicts(opportunities, _json(_text(message)).get('results') or [], [])

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

    # ---- os três fluxos -------------------------------------------------------
    def flow_f1(self, ctx):
        """Perplexity aberto + Perplexity só na imprensa curada + buscas em alta → lê → juiz → checagem externa."""
        m = self.flows['F1']['models']
        domains = source_base.press_domains(ctx.places)
        base = dict(topic=ctx.topic, places=ctx.places, lenses=ctx.lenses, recency_days=ctx.recency_days,
                    brand_facts='; '.join(ctx.brand['facts']) or 'não informado', sector=ctx.brand.get('sector') or '',
                    domains=', '.join(domains))
        jobs = {'discover_open': m['discover_open'], 'discover_press': m['discover_press'], 'discover_trends': m['discover_trends']}
        results = self._parallel({stage: (lambda s=stage, model=model: self.ai(
            'F1', s, model, prompts.messages(s, **base), max_tokens=1800, json_mode=False, web_requests=1))
            for stage, model in jobs.items()})
        facts, cited, texts = [], [], []
        for stage, (message, urls) in results.items():
            found, urls = self._facts(message, list(urls))
            if stage == 'discover_press':
                # Plano B do filtro de domínio: o que não é da lista curada sai.
                allowed = {source_base.root(d) for d in domains}
                found = [f for f in found if source_base.root(f.get('url', '')) in allowed]
            facts += found
            cited += urls
            texts.append(_text(message)[:2500])
        pages = self.read_pages('F1', 'extract', [item['url'] for item in cited])
        packet = self._packet(facts, pages)
        opportunities = self._judge('F1', ctx, '\n\n'.join(texts), packet)
        self._reality_check('F1', ctx, opportunities)
        return opportunities, packet

    def flow_f2(self, ctx):
        """Busca nativa da OpenAI (plugin web do OpenRouter) → juiz na OpenAI direta → checagem com busca nativa."""
        m = self.flows['F2']['models']
        domains = source_base.press_domains(ctx.places)
        base = dict(topic=ctx.topic, places=ctx.places, lenses=ctx.lenses, recency_days=ctx.recency_days,
                    brand_facts='; '.join(ctx.brand['facts']) or 'não informado', domains=', '.join(domains))
        web = [{'id': 'web', 'engine': 'native', 'max_results': 8}]
        results = self._parallel({stage: (lambda s=stage: self.ai(
            'F2', s, m[s], prompts.messages(s, **base), max_tokens=2200, json_mode=False, plugins=web, web_requests=1))
            for stage in ('discover_open', 'discover_press')})
        facts, cited, texts = [], [], []
        for message, urls in results.values():
            found, urls = self._facts(message, list(urls))
            facts += found
            cited += urls
            texts.append(_text(message)[:2500])
        packet = self._packet(facts, [], extra=[{'url': c['url'], 'title': c['title']} for c in cited])
        opportunities = self._judge('F2', ctx, '\n\n'.join(texts), packet, provider='openai')
        self._reality_check('F2', ctx, opportunities, plugins=web)
        return opportunities, packet

    def flow_f3(self, ctx):
        """Sem buscador com IA: Google Notícias (RSS) + Firecrawl na imprensa curada, leitura Python → juiz → verificador."""
        domains = source_base.press_domains(ctx.places)
        query = ' '.join(part for part in [ctx.focus, ctx.brand['name']] if part) or ctx.topic
        started = time.monotonic()
        # O RSS exige todas as palavras de uma frase longa: o tema vira marca + (termo OR termo).
        terms = [t.strip() for t in re.split(r',|;|\be\b', ctx.focus) if len(t.strip()) > 2][:5]
        ors = ' OR '.join(f'"{t}"' if ' ' in t else t for t in terms)
        queries = [f"{ctx.brand['name']} ({ors})" if ors else ctx.brand['name'], f'({ors}) {ctx.places.split(",")[0]}' if ors else '']
        try:
            news, seen = [], set()
            for rss_query in [q for q in queries if q]:
                for item in google_news(rss_query, ctx.recency_days):
                    if item['title'] not in seen:
                        seen.add(item['title'])
                        news.append(item)
            note = f'{len(news)} manchetes'
        except Exception as exc:  # noqa: BLE001
            news, note = [], f'{type(exc).__name__}'
        self.meter.add(Call('F3', 'google_news', 'python', 'python/rss', 'python', 'gratis',
                            seconds=round(time.monotonic() - started, 1), note=note))
        found = self.firecrawl_search('F3', 'search', f'{query} {ctx.places}', limit=8,
                                      include_domains=domains[:20], recency=ctx.recency)
        rss = [{'url': item['url'], 'title': f"{item['title']} ({item['source_name']})",
                'published_at': item['published_at'], 'excerpt': item['title'], 'domain_hint': item['source_url']}
               for item in news]
        unread = [item['url'] for item in found if not item.get('content')]
        pages = [item for item in found if item.get('content')] + (self.read_pages('F3', 'extract', unread) if unread else [])
        packet = self._packet([], pages, extra=rss)
        hints = {item['url']: item['domain_hint'] for item in rss}
        for item in packet:
            if item['url'] in hints:
                item['source_domain'] = source_base.host(hints[item['url']])
        opportunities = self._judge('F3', ctx, '', packet)
        self._internal_verify('F3', opportunities, packet)
        return opportunities, packet

    def _parallel(self, jobs):
        from flask import current_app
        app = current_app._get_current_object()

        def run(function):
            with app.app_context():
                return function()

        with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
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

    def review(self, ctx, by_flow):
        letters = list(by_flow)
        random.Random(self.run_id).shuffle(letters)
        mapping = {flow: 'ABC'[index] for index, flow in enumerate(letters)}
        systems = {}
        for flow, opportunities in by_flow.items():
            systems[mapping[flow]] = [{
                'id': f'{mapping[flow]}{index + 1}', 'title': item['title'], 'thesis': item['thesis'],
                'editorial': item['editorial'].score, 'paid': item['paid'].score, 'quadrant': item['quadrant'],
                'janela': item['window'], 'selo_confianca': item['confidence'], 'veredito': item['verdict'],
                'fontes': [{'dominio': s.get('domain'), 'nivel': s.get('tier'), 'abre': s.get('url_status'),
                            'data': s.get('published_at'), 'na_janela': s.get('in_window'), 'url': s['url']} for s in item['sources']]}
                for index, item in enumerate(opportunities)]
        payload = json.dumps({'hoje': ctx.today, 'janela_dias': ctx.recency_days, 'marca': ctx.brand, 'tema': ctx.focus,
                              'pracas': ctx.places, 'sistemas': systems}, ensure_ascii=False)
        message, _ = self.ai('REV', 'review', REVIEW_MODEL, prompts.messages('review', payload=payload), max_tokens=3500,
                             json_mode=False)
        verdict = _json(_text(message))
        verdict['mapping'] = mapping
        scores = {}
        for row in verdict.get('opportunities') or []:
            if isinstance(row, dict) and row.get('id'):
                values = [row.get(key) for key in ('veracidade', 'recencia', 'aderencia', 'acao', 'novidade')]
                numbers = [float(v) for v in values if isinstance(v, (int, float))]
                scores[row['id']] = {**row, 'media': round(sum(numbers) / len(numbers), 2) if numbers else None}
        for flow, opportunities in by_flow.items():
            for index, item in enumerate(opportunities):
                item['review'] = scores.get(f'{mapping[flow]}{index + 1}')
        return verdict

    # ---- orquestração -----------------------------------------------------------
    def run(self, flows=('F1', 'F2', 'F3')):
        prices()
        ctx = self.context()
        runners = {'F1': self.flow_f1, 'F2': self.flow_f2, 'F3': self.flow_f3}
        started = {}

        def timed(flow):
            started[flow] = time.monotonic()
            try:
                return runners[flow](ctx)
            except Exception as exc:  # noqa: BLE001 — um fluxo quebrado não derruba os outros
                self.meter.add(Call(flow, 'flow', 'llm', '', '', ok=False, note=f'{type(exc).__name__}: {str(exc)[:200]}'))
                return [], []
            finally:
                started[flow] = round(time.monotonic() - started[flow], 1)

        outputs = self._parallel({flow: (lambda f=flow: timed(f)) for flow in flows})
        by_flow = {}
        for flow, (opportunities, packet) in outputs.items():
            self.annotate(ctx, opportunities, packet)
            by_flow[flow] = opportunities
        review = self.review(ctx, by_flow) if any(by_flow.values()) else {}
        return self.summary(ctx, by_flow, review, started)

    def summary(self, ctx, by_flow, review, durations):
        calls = [asdict(call) for call in self.meter.calls]
        flows = {}
        for flow, opportunities in by_flow.items():
            mine = [c for c in calls if c['flow'] == flow]
            srcs = [s for item in opportunities for s in item['sources']]
            reviewed = [item['review']['media'] for item in opportunities if (item.get('review') or {}).get('media') is not None]
            flows[flow] = {
                'name': self.flows[flow]['name'], 'models': self.flows[flow]['models'], 'seconds': durations.get(flow),
                'opportunities': len(opportunities),
                'review_avg': round(sum(reviewed) / len(reviewed), 2) if reviewed else None,
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
                         for item in items] for flow, items in by_flow.items()}
        return {'run_id': self.run_id, 'prompt_version': prompts.VERSION, 'scenario': self.scenario,
                'context': {**vars(ctx), 'since': ctx.since.isoformat()}, 'token_price_usd': self.token_price_usd,
                'radar_r1_reserve': 15_207, 'flows': flows, 'calls': calls, 'opportunities': serial, 'review': review}


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
    """Relatório para ler e comparar: fluxos, custo simulado x real por chamada e oportunidades."""
    lines = [f"# Radar Lab — {result['run_id']}", '',
             f"Prompts v{result['prompt_version']} · cenário **{result['scenario'].get('name')}** · "
             f"tema: {result['context']['focus'] or '—'} · praças: {result['context']['places']} · "
             f"janela: {result['context']['recency_days']} dias · 1 token Cadu = US$ {result['token_price_usd']:.8f}", '',
             '## Comparação dos fluxos', '',
             '| Fluxo | Oport. | Nota revisor (1–5) | Fontes A/B | URLs abrem | Na janela | Selo alta/média/baixa | Tokens simulados | Tokens debitados | US$ provedor | Tempo |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for flow, row in result['flows'].items():
        conf = row['confidence']
        lines.append(f"| {flow} {row['name']} | {row['opportunities']} | {row['review_avg'] or '—'} | {_p(row['sources_ab_pct'])} | "
                     f"{_p(row['urls_ok_pct'])} | {_p(row['in_window_pct'])} | {conf['alta']}/{conf['media']}/{conf['baixa']} | "
                     f"{_n(row['sim_tokens'])} | {_n(row['real_tokens'])} | {row['provider_usd']:.4f} | {row['seconds']} s |")
    review = result.get('review') or {}
    mapping = review.get('mapping') or {}
    if review.get('vencedor'):
        back = {letter: flow for flow, letter in mapping.items()}
        lines += ['', f"**Revisor ({REVIEW_MODEL}):** vencedor {back.get(review['vencedor'], review['vencedor'])}. {review.get('por_que', '')}"]
        for system in review.get('systems') or []:
            lines.append(f"- {back.get(system.get('system'), system.get('system'))}: {system.get('resumo', '')} "
                         f"Melhor em: {system.get('melhor_em', '')}. Pior em: {system.get('pior_em', '')}.")
    lines += ['', '## Custo por chamada: simulado x real', '',
              '| Fluxo | Etapa | Modelo | Rota | Regime | Simulado (tokens Cadu) | Debitado (tokens Cadu) | US$ provedor | Entrada/saída | Tempo | Nota |',
              '|---|---|---|---|---|---|---|---|---|---|---|']
    for c in result['calls']:
        lines.append(f"| {c['flow']} | {c['stage']} | {c['model']} | {c['route']} | {c['regime']} | {_n(c['sim_tokens'])} | "
                     f"{_n(c['real_tokens'])} | {(c['real_usd'] or 0):.5f} | {_n(c['input_tokens'])}/{_n(c['output_tokens'])} | "
                     f"{c['seconds']} s | {'' if c['ok'] else 'FALHOU '}{c['note']} |")
    lines += ['', '## Oportunidades', '']
    for flow, items in result['opportunities'].items():
        lines += [f"### {flow} — {result['flows'][flow]['name']}", '']
        for item in items:
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
