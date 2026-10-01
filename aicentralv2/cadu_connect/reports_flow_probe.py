"""Conversion probe: what a visitor can do on a page, what measures it and what confirms it.

The default is read-only analysis of the page HTML. Everything here is evidence
from that page; nothing implies measured traffic. A real form submit is a
separate, explicit and rate-limited action, never part of the default analysis.
"""
import json
import re
import secrets
import time
import uuid
from collections import Counter
from html.parser import HTMLParser
from threading import BoundedSemaphore, Lock
from urllib.parse import urljoin, urlparse

SITE_KINDS = ('landing', 'institucional', 'multipagina', 'ecommerce')
MAX_FIELDS_TO_SUBMIT = 12
ANALYZE_COOLDOWN_SECONDS = 20
SUBMIT_DAILY_LIMIT = 3

CAPTCHA_RE = re.compile(r'recaptcha|hcaptcha|turnstile|captcha|data-sitekey', re.I)
SUCCESS_RE = re.compile(r'obrigad|thank|sucesso|success|enviad|recebemos|entraremos em contato|mensagem enviada|cadastro realizado', re.I)
COMMERCE_RE = re.compile(r'carrinho|cart\b|checkout|add[- ]to[- ]cart|adicionar ao carrinho|comprar|finalizar compra', re.I)
PRICE_RE = re.compile(r'R\$\s?\d[\d.,]*|\$\s?\d[\d.,]*', re.I)
CARD_RE = re.compile(r'card|cart[aã]o|cvv|cvc|cc-(?:number|exp|csc)|validade', re.I)
SEARCH_NAMES = {'q', 's', 'search', 'busca', 'pesquisa', 'query'}
NAV_HINTS = re.compile(r'sobre|about|servi[cç]os|services|contato|contact|blog|cases|produtos|products|empresa|equipe', re.I)
LANDING_PATH_RE = re.compile(r'^/(?:lp|landing|landing-page|campanha|campaign|oferta|promo)(?:[-/]|$)', re.I)

_probe_slots = BoundedSemaphore(2)
_last_analysis = {}
_last_lock = Lock()


class _ProbeParser(HTMLParser):
    """One pass over the HTML: forms with their fields, links, calls to action and page signals."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms, self.links, self.ctas = [], [], []
        self.schema_types, self.title_parts, self.h1_parts = set(), [], []
        self.sections = 0
        self.price_hits = 0
        self.text_parts = []
        self._form = None
        self._labels, self._label_for, self._label_text = {}, None, []
        self._capture = None  # 'title' | 'h1' | 'button' | 'a' | 'ld'
        self._capture_buffer = []
        self._a_href = None

    def handle_starttag(self, tag, attrs):
        attrs = {key: (value or '') for key, value in attrs}
        blob = ' '.join([attrs.get('class', ''), attrs.get('id', ''), attrs.get('src', ''), attrs.get('name', '')])
        if tag == 'form':
            self._form = {'id': attrs.get('id', '')[:80], 'action': attrs.get('action', '')[:500],
                          'method': (attrs.get('method') or 'get').lower(), 'fields': [], 'submit_label': '',
                          'has_password': False, 'has_card': False, 'has_file': False, 'has_captcha': False}
            self.forms.append(self._form)
        if self._form is not None and (CAPTCHA_RE.search(blob) or 'data-sitekey' in attrs):
            self._form['has_captcha'] = True
        if tag in ('input', 'select', 'textarea') and self._form is not None:
            self._field(tag, attrs)
        if tag == 'label':
            self._label_for, self._label_text = attrs.get('for', ''), []
        if tag == 'section':
            self.sections += 1
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
            self._a_href = attrs['href']
        if tag in ('title', 'h1', 'button', 'a'):
            self._capture, self._capture_buffer = tag, []
        if tag == 'script' and 'ld+json' in attrs.get('type', '').lower():
            self._capture, self._capture_buffer = 'ld', []
        if tag == 'button' and self._form is not None and attrs.get('type', 'submit').lower() == 'submit':
            self._capture = 'submit'

    def _field(self, tag, attrs):
        kind = attrs.get('type') or ('textarea' if tag == 'textarea' else tag)
        kind = kind.lower()
        name = (attrs.get('name') or attrs.get('id') or '')[:80]
        autocomplete = attrs.get('autocomplete', '').lower()
        if kind == 'password':
            self._form['has_password'] = True
        if kind == 'file':
            self._form['has_file'] = True
        if CARD_RE.search(' '.join([name, autocomplete, attrs.get('placeholder', '')])):
            self._form['has_card'] = True
        if kind in ('hidden', 'button', 'reset', 'image'):
            return
        if kind == 'submit':
            self._form['submit_label'] = (attrs.get('value') or self._form['submit_label'])[:80]
            return
        if len(self._form['fields']) < 40:
            self._form['fields'].append({'tag': tag, 'name': name, 'type': kind[:32], 'id': attrs.get('id', '')[:80],
                                         'label': (attrs.get('aria-label') or '')[:100], 'placeholder': attrs.get('placeholder', '')[:100],
                                         'required': 'required' in attrs, 'autocomplete': autocomplete[:40], 'options': []})

    def handle_endtag(self, tag):
        if tag == 'form':
            self._form = None
        if tag == 'label' and self._label_for:
            self._labels[self._label_for] = ' '.join(self._label_text)[:100]
            self._label_for = None
        if self._capture and (tag == self._capture or (self._capture == 'submit' and tag == 'button') or (self._capture == 'ld' and tag == 'script')):
            text = ' '.join(' '.join(self._capture_buffer).split())
            if self._capture == 'title':
                self.title_parts.append(text)
            elif self._capture == 'h1':
                self.h1_parts.append(text)
            elif self._capture == 'submit' and self._form is not None and text:
                self._form['submit_label'] = text[:80]
            elif self._capture in ('button', 'a') and text and len(text) <= 60 and len(self.ctas) < 40:
                self.ctas.append({'label': text, 'href': self._a_href if self._capture == 'a' else ''})
            elif self._capture == 'ld':
                self._collect_schema(text)
            self._capture = None

    def handle_data(self, data):
        value = ' '.join(data.split())
        if not value:
            return
        if self._label_for is not None:
            self._label_text.append(value)
        if self._capture:
            self._capture_buffer.append(value)
        if sum(len(part) for part in self.text_parts) < 6000:
            self.text_parts.append(value)
        if PRICE_RE.search(value):
            self.price_hits += 1

    def _collect_schema(self, text):
        try:
            data = json.loads(text)
        except ValueError:
            return
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item[:50])
            elif isinstance(item, dict):
                kinds = item.get('@type')
                for kind in (kinds if isinstance(kinds, list) else [kinds]):
                    if isinstance(kind, str):
                        self.schema_types.add(kind)
                stack.extend(value for value in item.values() if isinstance(value, (dict, list)))


def parse_page(html, url=''):
    """Structured summary of one page. Never raises on malformed HTML."""
    parser = _ProbeParser()
    try:
        parser.feed(html or '')
        parser.close()
    except Exception:
        pass
    for form in parser.forms:
        for field in form['fields']:
            if not field['label']:
                field['label'] = parser._labels.get(field['id']) or field['placeholder'] or field['name']
    base = urlparse(url)
    internal = []
    for href in parser.links:
        target = urlparse(urljoin(url, href)) if url else urlparse(href)
        if href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        if base.hostname and target.hostname and target.hostname.lower().removeprefix('www.') != base.hostname.lower().removeprefix('www.'):
            continue
        path = target.path or '/'
        if path != (base.path or '/') and path not in internal:
            internal.append(path)
    return {'title': ' '.join(parser.title_parts)[:200], 'h1': ' '.join(parser.h1_parts)[:200], 'forms': parser.forms,
            'internal_paths': internal[:200], 'ctas': parser.ctas, 'sections': parser.sections, 'schema_types': sorted(parser.schema_types),
            'price_hits': parser.price_hits, 'text': ' '.join(parser.text_parts)[:6000],
            'whatsapp': any('wa.me/' in href or 'api.whatsapp.com' in href or href.startswith('whatsapp:') for href in parser.links),
            'phone': any(href.startswith('tel:') for href in parser.links)}


def classify_form(form):
    """Purpose of a form, from its own fields: lead, newsletter, search, login, payment or other."""
    types = {field['type'] for field in form['fields']}
    names = {field['name'].lower() for field in form['fields']}
    if form['has_password']:
        return 'login'
    if form['has_card']:
        return 'payment'
    if 'search' in types or (len(form['fields']) == 1 and names & SEARCH_NAMES):
        return 'search'
    contact = [field for field in form['fields'] if field['type'] in ('email', 'tel') or re.search(r'e-?mail|telefone|celular|phone|whats|nome|name', field['name'] + field['label'], re.I)]
    if len(form['fields']) == 1 and any(field['type'] == 'email' for field in form['fields']):
        return 'newsletter'
    if contact and len(form['fields']) >= 2:
        return 'lead'
    return 'other'


def submit_safety(form):
    """(allowed, reason). A real submit is only ever considered for lead forms without protection."""
    kind = classify_form(form)
    if form['has_captcha']:
        return False, 'O formulário tem proteção anti-robô; o Cadu não a contorna.'
    if kind in ('login', 'payment', 'search'):
        return False, {'login': 'Formulário de acesso: nunca é enviado.', 'payment': 'Formulário de pagamento: nunca é enviado.',
                       'search': 'Busca do site: não é uma conversão.'}[kind]
    if form['has_file']:
        return False, 'O formulário pede arquivo; não é enviado em teste.'
    if not form['fields']:
        return False, 'Formulário sem campos visíveis.'
    if len(form['fields']) > MAX_FIELDS_TO_SUBMIT:
        return False, f'O formulário tem mais de {MAX_FIELDS_TO_SUBMIT} campos.'
    return True, ''


def fake_values(form, token=None):
    """Clearly fictitious values per field. Documents are never invented: they are reported as unfilled."""
    token = token or secrets.token_hex(3)
    values, unfilled = {}, []
    for field in form['fields']:
        name, kind = field['name'], field['type']
        hint = ' '.join([name, field['label'], field['autocomplete']]).lower()
        value = None
        if kind == 'email' or re.search(r'e-?mail', hint):
            value = f'teste.cadu.{token}@example.invalid'
        elif kind == 'tel' or re.search(r'telefone|celular|phone|whats|tel\b', hint):
            value = '(11) 90000-0000'
        elif re.search(r'cpf|cnpj|rg\b|document', hint):
            value = None
        elif re.search(r'empresa|company|organiza', hint):
            value = 'Empresa de Teste Cadu'
        elif re.search(r'nome|name', hint):
            value = 'Teste Cadu Reports'
        elif kind == 'textarea' or re.search(r'mensagem|message|assunto|comentario|coment[aá]rio', hint):
            value = 'Mensagem de teste automático do Cadu Reports. Pode ignorar.'
        elif kind == 'checkbox':
            value = bool(field['required'])
        elif kind in ('select', 'select-one', 'radio'):
            value = field['options'][0] if field['options'] else None
        elif kind in ('text', 'number', 'url'):
            value = 'Teste Cadu' if field['required'] else None
        if value is None and field['required'] and kind not in ('checkbox',):
            unfilled.append(name or field['label'])
        elif value is not None and name:
            values[name] = value
    return {'values': values, 'unfilled': unfilled}


def guess_site_kind(summary, path='/'):
    """A suggestion by rules, with reasons. The person confirms or changes it."""
    reasons, scores = [], Counter()
    commerce = int(bool(COMMERCE_RE.search(summary['text'] + ' ' + ' '.join(cta['label'] for cta in summary['ctas']))))
    commerce += int('Product' in summary['schema_types'] or 'Offer' in summary['schema_types'])
    commerce += int(summary['price_hits'] >= 3)
    if commerce >= 2:
        scores['ecommerce'] += 3
        reasons.append('Sinais de loja: preços, carrinho ou dados estruturados de produto.')
    paths = summary['internal_paths']
    navigation = sum(1 for item in paths if NAV_HINTS.search(item))
    if LANDING_PATH_RE.search(path or ''):
        scores['landing'] += 2
        reasons.append('O endereço indica uma página de campanha.')
    if summary['forms'] and len(paths) <= 8:
        scores['landing'] += 2
        reasons.append('Poucos links internos e um formulário: a jornada acontece na própria página.')
    if len(paths) >= 25:
        scores['multipagina'] += 3
        reasons.append(f'{len(paths)} links internos: o site tem muitas páginas.')
    elif len(paths) >= 9 or navigation >= 3:
        scores['institucional'] += 3
        reasons.append('Menu com seções institucionais (sobre, serviços, contato).')
    if not scores:
        scores['institucional'] += 1
        reasons.append('Sem sinais fortes; assumido como institucional.')
    ranked = scores.most_common()
    kind, top = ranked[0]
    gap = top - (ranked[1][1] if len(ranked) > 1 else 0)
    return {'kind': kind, 'confidence': 'alta' if gap >= 3 else 'media' if gap >= 1 else 'baixa', 'reasons': reasons}


def classify_outcome(before_url, after_url, after_text=''):
    """What confirms a submit: a new confirmation page, a message on the same page, or nothing observable."""
    before, after = urlparse(before_url), urlparse(after_url)
    moved = (after.netloc, after.path.rstrip('/')) != (before.netloc, before.path.rstrip('/'))
    if moved and SUCCESS_RE.search(after.path):
        return {'type': 'redirect_confirmation', 'path': after.path or '/', 'label': 'Página de confirmação'}
    if moved:
        return {'type': 'redirect', 'path': after.path or '/', 'label': 'Redirecionou para outra página, sem sinal de confirmação'}
    if SUCCESS_RE.search(after_text or ''):
        return {'type': 'in_page_message', 'path': before.path or '/', 'label': 'Mensagem de sucesso na própria página'}
    return {'type': 'no_confirmation_signal', 'path': before.path or '/', 'label': 'Nenhum sinal de confirmação observado'}


def _node(kind, title, path, *, stage, event_name='', description='', fields=None, entry=False, host=None):
    node = {'id': str(uuid.uuid4()), 'type': kind, 'title': title[:120], 'path': path or '/', 'stage': stage, 'origin': 'probe'}
    if event_name:
        node['event_name'] = event_name
    if description:
        node['description'] = description[:2000]
    if fields:
        labels = ', '.join(field['label'] or field['name'] for field in fields[:12])
        node['description'] = ((description + ' ') if description else '') + f'Campos: {labels}.'
    if entry:
        node['isEntry'] = True
    if host:
        node['host'] = host
    return node


STAGE_ORDER = ('source', 'entry', 'exploration', 'intent', 'conversion', 'support')
TAG_CHANNELS = {'Google Ads': ('traffic.google_search', 'google', 'Google Ads · Search'), 'Meta Pixel': ('traffic.meta', 'meta', 'Meta Ads'),
                'TikTok Pixel': ('traffic.tiktok', 'tiktok', 'TikTok Ads'), 'LinkedIn Insight': ('traffic.linkedin', 'linkedin', 'LinkedIn Ads')}


def _source_nodes(tags):
    """Where visitors may come from: paid channels only when the page carries that channel's tag, plus organic and direct."""
    nodes = []
    for name in tags:
        if name in TAG_CHANNELS:
            kind, platform, title = TAG_CHANNELS[name]
            node = _node('source', title, '', stage='source', description=f'Sugerido porque a página carrega a tag {name}. Confirme se há campanha ativa.')
            node.update({'kind': kind, 'source': platform})
            nodes.append(node)
    for kind, platform, title in (('traffic.organic_search', 'organic', 'Busca orgânica'), ('traffic.direct', 'direct', 'Acesso direto')):
        node = _node('source', title, '', stage='source', description='Origem comum a qualquer site.')
        node.update({'kind': kind, 'source': platform})
        nodes.append(node)
    return nodes


def _place(nodes):
    """Left-to-right by stage; rows inside a stage. The editor can reorganise afterwards."""
    rows = Counter()
    for node in nodes:
        column = STAGE_ORDER.index(node['stage']) if node['stage'] in STAGE_ORDER else 2
        node['x'] = 80 + column * 360
        node['y'] = 80 + rows[column] * 170
        rows[column] += 1
    return nodes


def _chain(nodes, label='Passo observado'):
    return [{'id': str(uuid.uuid4()), 'from': nodes[i]['id'], 'to': nodes[i + 1]['id'], 'label': label} for i in range(len(nodes) - 1)]


def build_proposal(kind, evidence, path='/', outcome=None):
    """Nodes and edges for the chosen kind of site. Every node says it came from the probe."""
    forms = [form for form in evidence['summary']['forms'] if submit_safety(form)[0]]
    form = forms[0] if forms else None
    tags = {tag['name'] for tag in evidence['media']['tags'] if tag['detected']}
    warnings = []
    if not tags:
        warnings.append('Nenhum pixel ou tag de mídia foi encontrado na página.')
    if form and not any('form' in event.lower() or 'lead' in event.lower() or 'submit' in event.lower() for event in evidence['media']['events']):
        warnings.append('O formulário não dispara evento de conversão identificável.')
    if outcome is None:
        warnings.append('A confirmação do envio não foi verificada; a análise não envia o formulário.')
    elif outcome['type'] in ('no_confirmation_signal', 'redirect'):
        warnings.append('Sem página ou mensagem de obrigado: a conversão não fica visível para a medição.')
    nodes = []
    if kind == 'landing':
        page = _node('page', 'Landing page', path, stage='entry', entry=True, description='Página de entrada observada pelo teste.')
        # Steps the Super Tag measures on its own: half-page scroll, WhatsApp click and form submit.
        nodes = [page, _node('event', 'Leu metade da página', path, stage='exploration', event_name='scroll_depth',
                             description='Medido pela Super Tag quando a rolagem passa de 50%.')]
        if evidence['summary']['whatsapp']:
            nodes.append(_node('whatsapp', 'Clicou no WhatsApp', path, stage='intent'))
        if form:
            nodes.append(_node('form', form['submit_label'] or 'Formulário', path, stage='intent', fields=form['fields'],
                               description='Envio medido pela Super Tag.'))
        nodes.append(_conversion_node(path, outcome))
    elif kind == 'institucional':
        page = _node('page', 'Página inicial', path, stage='entry', entry=True)
        contact = next((item for item in evidence['summary']['internal_paths'] if re.search(r'contato|contact|fale|orcamento', item, re.I)), None)
        nodes = [page]
        if contact:
            nodes.append(_node('page', 'Contato', contact, stage='intent', description='Caminho de contato encontrado no menu.'))
        if form:
            nodes.append(_node('form', form['submit_label'] or 'Formulário', contact or path, stage='intent', fields=form['fields']))
        if evidence['summary']['whatsapp']:
            nodes.append(_node('whatsapp', 'Clicou no WhatsApp', path, stage='intent'))
        nodes.append(_conversion_node(contact or path, outcome))
    elif kind == 'ecommerce':
        links = evidence['summary']['internal_paths']
        cart = next((item for item in links if re.search(r'carrinho|cart', item, re.I)), '/carrinho')
        checkout = next((item for item in links if re.search(r'checkout|finalizar', item, re.I)), '/checkout')
        # view_item/add_to_cart are custom events the store sends (CaduSuperTag.trackEvent('add_to_cart')); the warning says so.
        nodes = [_node('page', 'Início', path, stage='entry', entry=True),
                 _node('event', 'Viu um produto', path, stage='exploration', event_name='view_item'),
                 _node('event', 'Adicionou ao carrinho', path, stage='intent', event_name='add_to_cart'),
                 _node('page', 'Carrinho', cart, stage='intent'),
                 _node('page', 'Finalização de compra', checkout, stage='intent'),
                 _node('conversion', 'Compra concluída', checkout, stage='conversion', event_name='purchase',
                       description='Evento padrão de compra. Confirme a página de pedido recebido no seu site.')]
        warnings.append('Os caminhos de carrinho e checkout seguem o padrão encontrado; confirme-os no editor.')
        warnings.append("Produto visto e carrinho precisam que a loja chame CaduSuperTag.trackEvent('view_item') e trackEvent('add_to_cart').")
    else:
        return {'kind': kind, 'use_catalog': True, 'nodes': [], 'edges': [], 'warnings': warnings,
                'note': 'Para sites com muitas páginas, monte o fluxo pelo explorador de páginas.'}
    edges = _chain(nodes)
    entry = next(node for node in nodes if node.get('isEntry'))
    sources = _source_nodes(tags)
    edges += [{'id': str(uuid.uuid4()), 'from': source['id'], 'to': entry['id'], 'label': 'Chega por', 'variant': 'planned'} for source in sources]
    return {'kind': kind, 'use_catalog': False, 'nodes': _place(sources + nodes), 'edges': edges, 'warnings': warnings}


def _conversion_node(path, outcome):
    if outcome and outcome['type'] == 'redirect_confirmation':
        return _node('conversion', outcome['label'], outcome['path'], stage='conversion', description='Página de confirmação observada após o envio.')
    if outcome and outcome['type'] == 'in_page_message':
        return _node('conversion', 'Confirmação na página', path, stage='conversion', event_name='generate_lead',
                     description='Mensagem de sucesso observada na própria página.')
    return _node('conversion', 'Conversão (a confirmar)', path, stage='conversion', event_name='generate_lead',
                 description='Evento sugerido. A confirmação do envio ainda não foi observada.')


def analyze_html(html, url, path='/', site_kind=None, outcome=None):
    """Evidence for one page: forms and their safety, tags, events, kind of site and a proposal."""
    from .reports_link_tester import _media
    summary = parse_page(html, url)
    media = _media({'html': html or '', 'capture': {}})['evidence']
    guess = guess_site_kind(summary, path)
    selected_kind = site_kind if site_kind in SITE_KINDS else guess['kind']
    forms = []
    for index, form in enumerate(summary['forms']):
        allowed, reason = submit_safety(form)
        forms.append({**form, 'index': index, 'purpose': classify_form(form), 'can_submit': allowed, 'blocked_reason': reason})
    evidence = {'summary': summary, 'media': media}
    return {'url': url, 'title': summary['title'], 'h1': summary['h1'], 'site_kind': guess,
            'forms': forms, 'tags': media['tags'], 'events': media['events'], 'whatsapp': summary['whatsapp'], 'phone': summary['phone'],
            'consent_detected': media['compliance']['consent_detected'], 'method': 'html',
            'limits': ['Análise do HTML entregue pelo servidor. Tags carregadas por script só aparecem na leitura renderizada.',
                       'O formulário não foi enviado.'],
            'selected_kind': selected_kind, 'proposal': build_proposal(selected_kind, evidence, path, outcome),
            '_evidence': evidence}


def cooldown_ok(flow_id, seconds=ANALYZE_COOLDOWN_SECONDS, now=None):
    """One analysis per flow every few seconds; keeps a button from becoming a crawler."""
    now = time.monotonic() if now is None else now
    with _last_lock:
        last = _last_analysis.get(flow_id)
        if last is not None and now - last < seconds:
            return False, int(seconds - (now - last)) + 1
        _last_analysis[flow_id] = now
        if len(_last_analysis) > 2000:
            for key in sorted(_last_analysis, key=_last_analysis.get)[:500]:
                _last_analysis.pop(key, None)
    return True, 0


# Requests that prove a tag actually fired (not just that its code is on the page).
NETWORK_TAGS = {
    'Meta Pixel': ('facebook.com/tr', 'connect.facebook.net'),
    'GA4': ('google-analytics.com/g/collect', 'analytics.google.com/g/collect'),
    'Google Ads': ('googleadservices.com/pagead', 'googleads.g.doubleclick.net', 'google.com/pagead'),
    'GTM': ('googletagmanager.com/gtm.js',),
    'TikTok Pixel': ('analytics.tiktok.com',),
    'LinkedIn Insight': ('px.ads.linkedin.com', 'snap.licdn.com'),
    'Microsoft Clarity': ('clarity.ms',),
}


def tags_from_requests(urls):
    """Tag names whose collection endpoints were requested, in a stable order."""
    fired = []
    for name, needles in NETWORK_TAGS.items():
        if any(needle in str(url) for url in urls for needle in needles):
            fired.append(name)
    return fired


def render_with_browser(url):
    """Load the page with scripts running and list the requests it makes. Never captures images."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            requests_seen = []
            page.on('request', lambda request: requests_seen.append(request.url) if len(requests_seen) < 500 else None)
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(4000)
            return {'html': page.content(), 'requests': requests_seen}
        finally:
            browser.close()


def playwright_available():
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except Exception:
        return False


def _submit_with_browser(url, form_index, allowed_host):
    """One real submit with fictitious data. Network hosts seen are returned so pixels can be confirmed."""
    from playwright.sync_api import sync_playwright
    from .reports_flow import _host_allowed
    page_html = None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            hosts, urls = set(), []
            page.on('request', lambda request: (hosts.add(urlparse(request.url).hostname or ''), urls.append(request.url) if len(urls) < 800 else None))
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(1500)
            page_html = page.content()
            summary = parse_page(page_html, url)
            if form_index >= len(summary['forms']):
                return {'error': 'O formulário não foi encontrado na leitura renderizada.'}
            form = summary['forms'][form_index]
            allowed, reason = submit_safety(form)
            action_host = urlparse(urljoin(url, form['action'])).hostname if form['action'] else None
            if not allowed:
                return {'error': reason}
            if action_host and not _host_allowed(action_host, allowed_host):
                return {'error': 'O formulário envia para outro domínio; não é enviado em teste.'}
            fake = fake_values(form)
            if fake['unfilled']:
                return {'error': 'Campos obrigatórios sem valor de teste seguro: ' + ', '.join(fake['unfilled'][:5])}
            scope = page.locator('form').nth(form_index)
            for name, value in fake['values'].items():
                field = scope.locator(f'[name="{name}"]').first
                if field.count() == 0:
                    continue
                if isinstance(value, bool):
                    field.set_checked(value)
                elif (field.evaluate('el => el.tagName') or '').upper() == 'SELECT':
                    field.select_option(index=1 if field.locator('option').count() > 1 else 0)
                else:
                    field.fill(str(value))
            before = page.url
            fired_before = set(tags_from_requests(urls))
            scope.locator('[type=submit], button:not([type])').first.click(timeout=8000)
            page.wait_for_timeout(5000)
            return {'outcome': classify_outcome(before, page.url, page.inner_text('body')[:4000]),
                    'network_hosts': sorted(host for host in hosts if host)[:60], 'submitted': True,
                    'fired_on_submit': [name for name in tags_from_requests(urls) if name not in fired_before]}
        finally:
            browser.close()


def register(bp):
    from flask import abort, jsonify, request
    from ..auth import login_required_api
    from .reports_flow import _flow_row, _host_allowed, _safe_path
    from .reports_link_tester import _fetch
    from .reports_v1 import _selection, _write_guard, _rows

    @bp.route('/api/v2/reports/flow/flows/<flow_id>/probe', methods=['POST'])
    @login_required_api
    def flow_probe(flow_id):
        selected = _selection()
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        if flow.get('revoked_at'):
            abort(409, description='A tag deste fluxo foi revogada.')
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        path = payload.get('path') or '/'
        if not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or len(path) > 300:
            abort(400, description='Informe um caminho que comece com /.')
        host = flow['allowed_host']
        if not _host_allowed(host, host):
            abort(409, description='Domínio do fluxo inválido.')
        mode = payload.get('mode') or 'analyze'
        if mode not in ('analyze', 'submit'):
            abort(400)
        url = f'https://{host}{_safe_path(path)}'
        ok, wait = cooldown_ok(flow_id)
        if not ok:
            abort(429, description=f'Aguarde {wait}s para testar novamente.')
        if not _probe_slots.acquire(blocking=False):
            abort(429, description='Há testes em andamento. Tente novamente em instantes.')
        try:
            if mode == 'submit':
                return jsonify(_run_submit(flow, selected, url, payload))
            rendered = None
            if payload.get('render') is True:
                if not playwright_available():
                    abort(501, description='A leitura renderizada exige o navegador de testes, que não está instalado neste servidor.')
                try:
                    rendered = render_with_browser(url)
                except Exception:
                    abort(502, description='O navegador de testes não conseguiu abrir a página.')
                html = rendered['html']
            else:
                try:
                    status, _, html = _fetch(url, body=True)
                except Exception:
                    abort(502, description='Não foi possível ler a página agora.')
                if status >= 300:
                    abort(502, description=f'A página respondeu {status}; o teste não pôde ler o conteúdo.')
            result = analyze_html(html, url, path, payload.get('site_kind'))
            if rendered:
                result['method'] = 'rendered'
                result['fired_tags'] = tags_from_requests(rendered['requests'])
                result['limits'] = ['Página aberta com scripts em execução; os pixels listados como disparados fizeram requisições de verdade.',
                                    'O formulário não foi enviado.']
            result.pop('_evidence', None)
            result['submit_available'] = playwright_available()
            return jsonify(result)
        finally:
            _probe_slots.release()

    def _run_submit(flow, selected, url, payload):
        if payload.get('confirm_submit') is not True:
            abort(400, description='Confirme o envio de teste para continuar.')
        if not playwright_available():
            abort(501, description='O envio de teste exige o navegador de testes, que não está instalado neste servidor.')
        index = payload.get('form_index')
        if not isinstance(index, int) or index < 0 or index > 20:
            abort(400, description='Escolha o formulário a testar.')
        used = _rows("""SELECT COUNT(*)::int AS total FROM cadu_reports_flow_probe_runs
                        WHERE flow_id=%s AND mode='submit' AND created_at > NOW() - INTERVAL '1 day'""", (flow['id'],))
        if used and int(used[0]['total']) >= SUBMIT_DAILY_LIMIT:
            abort(429, description='Limite diário de envios de teste atingido para este fluxo.')
        try:
            result = _submit_with_browser(url, index, flow['allowed_host'])
        except Exception:
            abort(502, description='O navegador de testes não conseguiu concluir o envio.')
        if result.get('error'):
            abort(422, description=result['error'])
        try:
            _, _, html = _fetch(url, body=True)
            analysis = analyze_html(html, url, urlparse(url).path or '/', payload.get('site_kind'), result['outcome'])
            analysis.pop('_evidence', None)
            result['analysis'] = analysis
        except Exception:
            result['analysis'] = None
        _rows("INSERT INTO cadu_reports_flow_probe_runs (flow_id,client_id,mode,created_at) VALUES (%s,%s,'submit',NOW())",
              (flow['id'], selected['client_id']))
        return result
