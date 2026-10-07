"""Critical audit of a site's readiness for AI agents (the Link Tester's "agentic" analysis).

It answers four questions in order of how much each one can hurt: can an agent *reach* the site (robots.txt, CDN/WAF),
can it *read* what it reaches (server-rendered text, semantics), does the site *guide* it (llms.txt, sitemap) and does it
*describe itself* in machine terms (JSON-LD). Hard failures cap the score no matter how much else is in place.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html import unescape
from time import monotonic
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from . import reports_link_tester as lt

FETCH_TIMEOUT = 6
BODY_LIMIT = 400_000
BOTS = (  # (user-agent token, vendor, purpose) · "search"/"user" bots decide whether AI answers can cite the site
    ('OAI-SearchBot', 'OpenAI', 'search'), ('ChatGPT-User', 'OpenAI', 'user'), ('GPTBot', 'OpenAI', 'training'),
    ('Claude-SearchBot', 'Anthropic', 'search'), ('Claude-User', 'Anthropic', 'user'), ('ClaudeBot', 'Anthropic', 'training'),
    ('PerplexityBot', 'Perplexity', 'search'), ('Perplexity-User', 'Perplexity', 'user'),
    ('Google-Extended', 'Google', 'training'), ('Applebot-Extended', 'Apple', 'training'), ('CCBot', 'Common Crawl', 'training'),
)
PROBE_AGENTS = {  # real user-agent strings: a CDN/WAF rule blocks these even when robots.txt allows them
    'GPTBot': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot',
    'ClaudeBot': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)',
    'PerplexityBot': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)',
}
BLOCK_STATUS = {401, 403, 406, 429, 451, 503}
CHALLENGE = re.compile(r'cf-chl|just a moment|attention required|captcha|access denied|bot detection|px-captcha', re.I)
RICH_TYPES = {'product', 'offer', 'faqpage', 'article', 'newsarticle', 'blogposting', 'service', 'localbusiness', 'event',
              'howto', 'softwareapplication', 'recipe', 'jobposting', 'course', 'review', 'aggregaterating'}
IDENTITY_TYPES = {'organization', 'localbusiness', 'website', 'person', 'corporation', 'onlinestore', 'store'}
SEVERITY_ORDER = {'critical': 0, 'warning': 1, 'info': 2, 'ok': 3}


def _get(url, agent=None, accept=None, limit=BODY_LIMIT, follow=3):
    """One bounded, SSRF-safe GET that never raises: {status, headers, body, content_type, error, final_url, ms}."""
    started, current = monotonic(), url
    try:
        for _ in range(follow + 1):
            parsed = lt._url(current)
            lt._public_host(parsed)
            response = requests.get(parsed.geturl(), allow_redirects=False, stream=True, timeout=FETCH_TIMEOUT,
                                    headers={'User-Agent': agent or lt.USER_AGENT, 'Accept': accept or 'text/html,text/plain,application/xml,application/json;q=0.9,*/*;q=0.5'})
            try:
                location = response.headers.get('Location')
                if 300 <= response.status_code < 400 and location:
                    current = urljoin(current, location)
                    continue
                content_type = response.headers.get('Content-Type', '').lower()
                chunks, total = [], 0
                for chunk in response.iter_content(16384):
                    total += len(chunk)
                    chunks.append(chunk)
                    if total >= limit:
                        break
                body = b''.join(chunks).decode(response.encoding or 'utf-8', errors='replace')
                return {'status': response.status_code, 'headers': dict(response.headers), 'body': body, 'content_type': content_type,
                        'error': None, 'final_url': parsed.geturl(), 'ms': round((monotonic() - started) * 1000)}
            finally:
                response.close()
        return {'status': None, 'headers': {}, 'body': '', 'content_type': '', 'error': 'redirects', 'final_url': current, 'ms': 0}
    except Exception as error:  # network, TLS, SSRF refusal: all mean "not available" to the audit
        return {'status': None, 'headers': {}, 'body': '', 'content_type': '', 'error': type(error).__name__, 'final_url': current, 'ms': 0}


def _looks_html(fetched):
    head = fetched['body'][:400].lstrip().lower()
    return 'html' in fetched['content_type'] or head.startswith(('<!doctype', '<html', '<head', '<body'))


def _text_words(html):
    clean = re.sub(r'(?is)<(script|style|noscript|svg|template)\b.*?</\1>', ' ', html or '')
    clean = re.sub(r'(?s)<!--.*?-->', ' ', clean)
    return len(re.findall(r'\w{2,}', unescape(re.sub(r'<[^>]+>', ' ', clean)), re.U))


def _tag_attr(html, tag, attr):
    match = re.search(rf'<{tag}\b[^>]*\b{attr}=["\']([^"\']*)', html or '', re.I)
    return unescape(match.group(1)).strip() if match else None


def _json_ld(html):
    types, invalid = set(), 0
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html or '', re.I | re.S):
        try:
            data = json.loads(unescape(block).strip())
        except ValueError:
            invalid += 1
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                value = node.get('@type')
                for item in ([value] if isinstance(value, str) else value if isinstance(value, list) else []):
                    if isinstance(item, str):
                        types.add(item.rsplit('/', 1)[-1])
                stack.extend(node.get('@graph') or [])
    return sorted(types), invalid


def _robots(fetched):
    valid = fetched['status'] == 200 and not _looks_html(fetched) and bool(re.search(r'(?im)^\s*(user-agent|sitemap)\s*:', fetched['body']))
    parser, sitemaps = None, []
    if valid:
        parser = RobotFileParser()
        parser.parse(fetched['body'].splitlines())
        sitemaps = re.findall(r'(?im)^\s*sitemap\s*:\s*(\S+)', fetched['body'])[:5]
    return valid, parser, sitemaps


def _llms(fetched):
    body = fetched['body'] if fetched['status'] == 200 and not _looks_html(fetched) else ''
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    links = re.findall(r'\[[^\]]+\]\(([^)\s]+)', body)
    return {'valid': bool(body.strip()), 'has_title': bool(lines and re.match(r'#\s+\S', lines[0])),
            'has_summary': any(line.startswith('>') for line in lines[:8]),
            'sections': sum(1 for line in lines if re.match(r'##\s+\S', line)), 'links': len(links), 'link_urls': links[:60], 'bytes': len(body.encode())}


def _sitemap(fetched, page_url):
    body = fetched['body'] if fetched['status'] == 200 and not _looks_html(fetched) else ''
    index = '<sitemapindex' in body[:2000].lower()
    valid = index or '<urlset' in body[:2000].lower()
    locs = re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', body)
    dates = sorted(re.findall(r'<lastmod>\s*(\d{4}-\d{2}-\d{2})', body))
    page = urlparse(page_url)
    key = (page.hostname or '', page.path.rstrip('/') or '/')
    listed = any((urlparse(loc).hostname or '', urlparse(loc).path.rstrip('/') or '/') == key for loc in locs) if valid and not index else None
    return {'valid': valid, 'index': index, 'urls': len(locs), 'last_modified': dates[-1] if dates else None, 'lists_page': listed}


def analyze(common):
    final = common['final_parsed']
    base = f'{final.scheme}://{final.netloc}/'
    raw_html, rendered_html = common.get('raw_html') or common['html'], common.get('rendered_html') or ''
    page_url, headers = common['final_url'], {k.lower(): v for k, v in (common.get('headers') or {}).items()}
    capture = common.get('capture') or {}

    jobs = {'robots.txt': (urljoin(base, 'robots.txt'), {}), 'llms.txt': (urljoin(base, 'llms.txt'), {}),
            'llms-full.txt': (urljoin(base, 'llms-full.txt'), {'limit': 60_000}), 'sitemap.xml': (urljoin(base, 'sitemap.xml'), {}),
            'agent-card': (urljoin(base, '.well-known/agent-card.json'), {'limit': 60_000}),
            'markdown': (page_url, {'accept': 'text/markdown', 'limit': 20_000})}
    jobs.update({f'bot:{name}': (page_url, {'agent': agent, 'limit': 30_000}) for name, agent in PROBE_AGENTS.items()})
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {name: pool.submit(_get, url, **options) for name, (url, options) in jobs.items()}
        got = {name: future.result() for name, future in futures.items()}

    robots_valid, parser, robots_sitemaps = _robots(got['robots.txt'])
    path = final.path or '/'
    bot_access = []
    for name, vendor, purpose in BOTS:
        bot_access.append({'name': name, 'vendor': vendor, 'purpose': purpose, 'blocked': bool(parser and not parser.can_fetch(name, path))})
    search_bots = [bot for bot in bot_access if bot['purpose'] in {'search', 'user'}]
    blocked_search = [bot['name'] for bot in search_bots if bot['blocked']]
    blocked_training = [bot['name'] for bot in bot_access if bot['purpose'] == 'training' and bot['blocked']]

    waf = []
    for name in PROBE_AGENTS:
        probe = got[f'bot:{name}']
        challenged = probe['status'] == 200 and bool(CHALLENGE.search(probe['body'][:6000])) and _text_words(probe['body']) < 120
        waf.append({'name': name, 'status': probe['status'], 'blocked': (probe['status'] in BLOCK_STATUS and common['status'] < 400) or challenged,
                    'unreachable': probe['status'] is None})
    waf_blocked = [item['name'] for item in waf if item['blocked']]

    llms = _llms(got['llms.txt'])
    sitemap_sources = [('sitemap.xml', got['sitemap.xml'])]
    sitemap = _sitemap(got['sitemap.xml'], page_url)
    if not sitemap['valid'] and robots_sitemaps:
        declared = _get(urljoin(base, robots_sitemaps[0]))
        candidate = _sitemap(declared, page_url)
        if candidate['valid']:
            sitemap, sitemap_sources = candidate, [(robots_sitemaps[0], declared)]
    # Spot-check the links llms.txt hands to agents: dead links there are worse than none.
    own = [urljoin(base, link) for link in llms['link_urls'] if urlparse(urljoin(base, link)).hostname == final.hostname][:5]
    with ThreadPoolExecutor(max_workers=5) as pool:
        link_checks = list(pool.map(lambda link: (link, _get(link, limit=2000)['status']), own)) if own else []
    dead_links = [link for link, status in link_checks if not status or status >= 400]

    raw_words, rendered_words = _text_words(raw_html), _text_words(rendered_html)
    js_dependent = bool(rendered_words >= 120 and raw_words < rendered_words * 0.4)
    thin_unverified = not rendered_words and raw_words < 80
    schema_types, schema_invalid = _json_ld(raw_html)
    lowered = {item.lower() for item in schema_types}
    robots_meta = ' '.join(re.findall(r'<meta[^>]+name=["\'](?:robots|googlebot)["\'][^>]+content=["\']([^"\']*)', raw_html, re.I)).lower()
    x_robots = headers.get('x-robots-tag', '').lower()
    noindex = 'noindex' in robots_meta or 'noindex' in x_robots
    noai = 'noai' in robots_meta or 'noai' in x_robots
    title, description = lt._title(raw_html), lt._meta(raw_html, 'description')
    h1, h2 = len(re.findall(r'<h1\b', raw_html, re.I)), len(re.findall(r'<h2\b', raw_html, re.I))
    images = re.findall(r'<img\b[^>]*>', raw_html, re.I)
    with_alt = sum(1 for tag in images if re.search(r'\balt=["\'][^"\']+', tag, re.I))
    semantic = bool(re.search(r'<(main|article)\b', raw_html, re.I))
    lang = _tag_attr(raw_html, 'html', 'lang')
    canonical = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*>', raw_html, re.I)
    markdown_alt = bool(re.search(r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\']text/markdown', raw_html, re.I))
    negotiated = got['markdown']['status'] == 200 and 'markdown' in got['markdown']['content_type']
    agent_card = got['agent-card']['status'] == 200 and not _looks_html(got['agent-card']) and got['agent-card']['body'].lstrip().startswith('{')
    truncated = len(raw_html.encode()) >= lt.MAX_HTML_BYTES
    https = final.scheme == 'https'

    findings = []

    def add(severity, category, title, detail, fix=''):
        findings.append({'severity': severity, 'category': category, 'title': title, 'detail': detail, 'fix': fix})

    # ---- Acesso (30)
    access = 0
    if robots_valid:
        access += 4
        add('ok', 'Acesso', 'robots.txt válido', f'{len(robots_sitemaps)} sitemap(s) declarado(s).' if robots_sitemaps else 'Não declara sitemap.')
        if not robots_sitemaps:
            add('info', 'Acesso', 'robots.txt sem linha Sitemap', 'Agentes e buscadores descobrem o sitemap mais rápido quando ele é declarado.', 'Adicione "Sitemap: https://seu-dominio/sitemap.xml" ao robots.txt.')
    elif got['robots.txt']['status'] == 200:
        add('critical', 'Acesso', 'robots.txt devolve HTML, não regras', 'A URL responde 200, mas com a página do site (rota coringa de SPA). Crawlers tratam como arquivo inválido.', 'Sirva um robots.txt de texto puro em /robots.txt.')
    else:
        add('warning', 'Acesso', 'Sem robots.txt', 'Sem regras explícitas, nada diz a agentes o que podem ler e o site perde a chance de declarar o sitemap.', 'Publique /robots.txt liberando OAI-SearchBot, ChatGPT-User, Claude-SearchBot, PerplexityBot.')
    if search_bots:
        access += round(10 * (len(search_bots) - len(blocked_search)) / len(search_bots))
    if blocked_search:
        add('critical', 'Acesso', 'Robôs de busca de IA bloqueados no robots.txt', 'Bloqueados: ' + ', '.join(blocked_search) + '. O site não pode ser lido nem citado nas respostas desses assistentes.', 'Remova o Disallow para esses agentes (ou o "User-agent: * / Disallow: /").')
    elif robots_valid:
        add('ok', 'Acesso', 'Busca de IA liberada no robots.txt', 'OAI-SearchBot, ChatGPT-User, Claude-SearchBot e PerplexityBot podem ler esta página.')
    if blocked_training:
        add('info', 'Acesso', 'Treinamento de modelos bloqueado', 'Bloqueados: ' + ', '.join(blocked_training) + '. É uma escolha legítima e não afeta citações em respostas.')
    reachable = [item for item in waf if not item['unreachable']]
    waf_points = 12 if not waf_blocked and reachable else 0
    access += waf_points
    if waf_blocked:
        add('critical', 'Acesso', 'CDN/WAF barra robôs de IA', 'Com o user-agent de ' + ', '.join(waf_blocked) + ' o site respondeu bloqueio ou desafio, mesmo que o robots.txt permita. Para o agente, o site não existe.', 'Libere esses user-agents (e os IPs publicados pelos provedores) na regra de bot do Cloudflare/WAF.')
    elif not reachable:
        add('warning', 'Acesso', 'Teste de bloqueio por WAF inconclusivo', 'Não foi possível completar a requisição com user-agents de robôs.', 'Repita a análise; se persistir, verifique limite de requisições no servidor.')
    else:
        add('ok', 'Acesso', 'Sem bloqueio por WAF', 'GPTBot, ClaudeBot e PerplexityBot recebem a mesma página que um visitante.')
    if noindex or noai:
        add('critical', 'Acesso', 'Página marca noindex/noai', ('noindex' if noindex else 'noai') + ' encontrado em meta robots ou X-Robots-Tag. Agentes e buscadores devem ignorar a página.', 'Remova a diretiva se a página deve ser encontrada.')
    else:
        access += 4

    # ---- Conteúdo legível (25)
    content = 0
    if js_dependent:
        add('critical', 'Conteúdo', 'O texto só existe depois do JavaScript', f'O HTML entregue tem ~{raw_words} palavras; renderizado, ~{rendered_words}. A maioria dos agentes não executa JavaScript e enxerga uma página quase vazia.', 'Renderize no servidor (SSR/SSG) o conteúdo principal.')
    elif thin_unverified:
        add('warning', 'Conteúdo', 'Pouco texto no HTML entregue', f'Só ~{raw_words} palavras no HTML. Se o site depende de JavaScript, agentes não leem o conteúdo.', 'Garanta que o texto principal esteja no HTML inicial.')
    elif raw_words >= 300:
        content += 12
        add('ok', 'Conteúdo', 'Texto legível sem JavaScript', f'~{raw_words} palavras no HTML entregue.')
    elif raw_words >= 100:
        content += 7
        add('warning', 'Conteúdo', 'Pouco conteúdo textual', f'Apenas ~{raw_words} palavras. Agentes têm pouco para citar.', 'Descreva oferta, público, preços e perguntas frequentes em texto.')
    else:
        add('warning', 'Conteúdo', 'Página quase sem texto', f'~{raw_words} palavras.', 'Inclua descrição textual do produto/serviço.')
    if truncated:
        add('warning', 'Conteúdo', 'HTML muito pesado', 'O HTML passa de 1 MB; agentes truncam e perdem o final da página.', 'Reduza o HTML inline (scripts, estilos, dados embutidos).')
    content += (3 if h1 == 1 else 0) + (2 if semantic else 0) + (1 if lang else 0) + (2 if h2 else 0)
    if h1 != 1:
        add('warning', 'Conteúdo', 'Sem H1 único' if h1 == 0 else f'{h1} títulos H1', 'O H1 diz ao agente qual é o assunto da página.', 'Use exatamente um H1 que nomeie a página.')
    if not semantic:
        add('info', 'Conteúdo', 'Sem <main> ou <article>', 'Marcação semântica ajuda o agente a separar o conteúdo de menus e rodapé.', 'Envolva o conteúdo principal em <main>.')
    if not lang:
        add('info', 'Conteúdo', 'Idioma não declarado', 'Falta o atributo lang em <html>.', 'Use <html lang="pt-BR">.')
    if title and 10 <= len(title) <= 70:
        content += 3
    else:
        add('warning', 'Conteúdo', 'Título ausente' if not title else f'Título com {len(title)} caracteres', 'O <title> é o rótulo que o agente usa ao citar a página (ideal: 10 a 70 caracteres).', 'Escreva um título descritivo e único.')
    if description and 50 <= len(description) <= 180:
        content += 2
    else:
        add('info', 'Conteúdo', 'Meta description ausente ou fora do tamanho', 'Ideal entre 50 e 180 caracteres.', 'Resuma a página em uma frase.')
    if images and with_alt / len(images) < 0.6:
        add('info', 'Conteúdo', 'Imagens sem texto alternativo', f'{len(images) - with_alt} de {len(images)} imagens sem alt: invisíveis para agentes.', 'Descreva cada imagem relevante no atributo alt.')
    content = min(content, 25)

    # ---- Guias para IA (25)
    guide = 0
    if llms['valid']:
        guide += 8
        quality = (2 if llms['has_title'] else 0) + (1 if llms['has_summary'] else 0) + (2 if llms['sections'] else 0) + (2 if llms['links'] >= 3 else 0)
        quality = quality if not dead_links else max(0, quality - 2)
        guide += quality
        add('ok', 'Guias', 'llms.txt publicado', f'{llms["links"]} link(s), {llms["sections"]} seção(ões).')
        if not llms['has_title']:
            add('warning', 'Guias', 'llms.txt sem título (#)', 'O padrão exige "# Nome do site" na primeira linha.', 'Comece o arquivo com "# Nome do site".')
        if not llms['has_summary']:
            add('info', 'Guias', 'llms.txt sem resumo', 'Falta o bloco "> resumo" logo após o título.', 'Adicione 1 a 2 frases em citação (>) explicando o que o site oferece.')
        if not llms['sections'] or llms['links'] < 3:
            add('warning', 'Guias', 'llms.txt sem estrutura útil', f'{llms["sections"]} seção(ões) e {llms["links"]} link(s).', 'Liste as páginas-chave em seções "## Nome" com links [título](url): descrição.')
        if dead_links:
            add('critical', 'Guias', 'llms.txt aponta para páginas quebradas', f'{len(dead_links)} de {len(link_checks)} links verificados falham: ' + ', '.join(dead_links[:3]), 'Corrija ou remova os links quebrados.')
    elif got['llms.txt']['status'] == 200:
        add('critical', 'Guias', 'llms.txt devolve HTML', 'A rota responde 200, mas com a página do site, não com o guia. Parece existir e não funciona.', 'Sirva um arquivo de texto/markdown em /llms.txt.')
    else:
        add('warning', 'Guias', 'Sem llms.txt', 'O site não oferece ao agente um mapa em markdown do que importa.', 'Publique /llms.txt com título, resumo e links das páginas principais.')
    full = got['llms-full.txt']
    if full['status'] == 200 and not _looks_html(full) and len(full['body']) > 200:
        add('ok', 'Guias', 'llms-full.txt publicado', 'Versão completa do conteúdo para leitura de uma vez.')
    if sitemap['valid']:
        guide += 7
        add('ok', 'Guias', 'sitemap.xml válido', f'{sitemap["urls"]} URL(s)' + (f', última alteração {sitemap["last_modified"]}.' if sitemap['last_modified'] else '.'))
        if sitemap['lists_page'] is False:
            add('warning', 'Guias', 'A página testada não está no sitemap', 'Ela existe, mas o site não a declara.', 'Inclua esta URL no sitemap.')
        elif sitemap['lists_page'] is True:
            guide += 3
        elif sitemap['index']:
            guide += 3
        if sitemap['last_modified'] and sitemap['last_modified'] < f'{date.today().year - 1}-01-01':
            add('info', 'Guias', 'Sitemap sem atualização recente', f'Última data: {sitemap["last_modified"]}.', 'Gere o sitemap automaticamente com lastmod real.')
    else:
        add('warning' if got['sitemap.xml']['status'] != 200 else 'critical', 'Guias', 'Sem sitemap.xml válido', 'Sem mapa, o agente depende de seguir links e perde páginas.' if got['sitemap.xml']['status'] != 200 else 'A rota responde 200 com HTML.', 'Publique /sitemap.xml e declare no robots.txt.')

    # ---- Dados estruturados (15)
    data = 0
    if schema_types:
        data += 6 + (2 if not schema_invalid else 0)
        if lowered & IDENTITY_TYPES:
            data += 5
        else:
            add('warning', 'Dados', 'JSON-LD sem identidade da empresa', 'Há dados estruturados (' + ', '.join(schema_types[:4]) + '), mas nenhum Organization/LocalBusiness/WebSite.', 'Adicione Organization com nome, logo, redes sociais e contato.')
        if lowered & RICH_TYPES:
            data += 2
        else:
            add('info', 'Dados', 'Sem tipo de conteúdo rico', 'Faltam Product, Service, FAQPage, Article ou Event conforme o assunto da página.', 'Descreva a oferta com o tipo schema.org correspondente.')
        add('ok', 'Dados', 'JSON-LD encontrado', 'Tipos: ' + ', '.join(schema_types[:6]) + '.')
    else:
        add('critical', 'Dados', 'Sem dados estruturados', 'Nenhum JSON-LD no HTML entregue: o agente precisa adivinhar quem é a empresa e o que ela vende.', 'Inclua JSON-LD (Organization + o tipo da página).')
    if schema_invalid:
        add('critical', 'Dados', 'JSON-LD inválido', f'{schema_invalid} bloco(s) com JSON quebrado são ignorados por todos os leitores.', 'Valide o JSON-LD no Schema Markup Validator.')

    # ---- Sinais avançados (5)
    advanced = 0
    if markdown_alt or negotiated:
        advanced += 3
        add('ok', 'Avançado', 'Versão em markdown disponível', 'Agentes podem ler a página sem ruído de HTML.')
    else:
        add('info', 'Avançado', 'Sem versão markdown da página', 'Servir text/markdown (ou <link rel="alternate" type="text/markdown">) reduz o custo e o ruído para o agente.', 'Opcional: exponha a versão .md das páginas-chave.')
    if agent_card:
        advanced += 2
        add('ok', 'Avançado', 'Agent card publicado', '/.well-known/agent-card.json permite que agentes descubram capacidades do site.')
    if not https:
        add('critical', 'Acesso', 'Destino sem HTTPS', 'Agentes e navegadores desconfiam de conteúdo sem HTTPS.', 'Redirecione tudo para HTTPS.')

    categories = [{'name': 'Acesso', 'score': min(access, 30), 'max': 30, 'question': 'O agente consegue entrar?'},
                  {'name': 'Conteúdo', 'score': content, 'max': 25, 'question': 'Ele consegue ler o que encontra?'},
                  {'name': 'Guias', 'score': min(guide, 25), 'max': 25, 'question': 'O site mostra o caminho?'},
                  {'name': 'Dados', 'score': min(data, 15), 'max': 15, 'question': 'Ele entende quem é a empresa?'},
                  {'name': 'Avançado', 'score': advanced, 'max': 5, 'question': 'Há sinais emergentes?'}]
    raw_score = sum(item['score'] for item in categories)
    caps = []
    for condition, limit, reason in ((common['status'] >= 400, 20, 'A página respondeu com erro.'), (noindex, 30, 'A página pede para não ser indexada.'),
                                     (bool(waf_blocked), 40, 'O WAF/CDN bloqueia robôs de IA.'), (js_dependent, 55, 'O conteúdo depende de JavaScript.'),
                                     (bool(blocked_search), 55, 'O robots.txt bloqueia robôs de busca de IA.'), (not https, 60, 'O destino não usa HTTPS.')):
        if condition:
            caps.append({'limit': limit, 'reason': reason})
    score = max(0, min([raw_score] + [item['limit'] for item in caps]))
    findings.sort(key=lambda item: SEVERITY_ORDER[item['severity']])
    label = 'Pronto para agentes' if score >= 85 else 'Parcialmente legível' if score >= 65 else 'Frágil para agentes' if score >= 40 else 'Invisível para agentes'
    problems = [item for item in findings if item['severity'] in {'critical', 'warning'}]
    summary = (caps[0]['reason'] + ' ' if caps else '') + (f'{len([f for f in findings if f["severity"] == "critical"])} problema(s) crítico(s) e {len([f for f in findings if f["severity"] == "warning"])} ponto(s) de atenção.' if problems else 'Sem problemas relevantes para agentes de IA.')
    return {'kind': 'agentic', 'score': score, 'status_label': label, 'summary': summary,
            'evidence': {'domain': final.hostname, 'categories': categories, 'findings': findings, 'caps': caps, 'raw_score': raw_score,
                         'resources': {'robots.txt': {'url': got['robots.txt']['final_url'], 'status': got['robots.txt']['status'], 'available': robots_valid},
                                       'llms.txt': {'url': got['llms.txt']['final_url'], 'status': got['llms.txt']['status'], 'available': llms['valid']},
                                       'llms-full.txt': {'url': full['final_url'], 'status': full['status'], 'available': full['status'] == 200 and not _looks_html(full) and len(full['body']) > 200},
                                       'sitemap.xml': {'url': sitemap_sources[0][1]['final_url'], 'status': sitemap_sources[0][1]['status'], 'available': sitemap['valid']}},
                         'bot_access': bot_access, 'waf_probe': waf, 'schema_types': schema_types, 'schema_invalid': schema_invalid,
                         'llms_quality': {k: v for k, v in llms.items() if k != 'link_urls'} | {'dead_links': len(dead_links), 'checked_links': len(link_checks)},
                         'sitemap': sitemap, 'content': {'raw_words': raw_words, 'rendered_words': rendered_words or None, 'js_dependent': js_dependent,
                                                         'h1': h1, 'h2': h2, 'images': len(images), 'images_with_alt': with_alt, 'title': title, 'description': description},
                         'screenshot': capture.get('screenshot')},
            'alerts': [item['title'] for item in problems]}
