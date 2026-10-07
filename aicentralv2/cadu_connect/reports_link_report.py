"""One detailed, sectioned report for a Link Tester run, shared by the page inside the tool and the public link.

Both sources become the same structure:
    {header, indicators, modules, sections: [{id, title, icon, tone, summary, blocks: [...]}], screenshots}
Block types the renderers understand:
    kv      rows: [{label, value, tone?, mono?}]
    chips   items: [{label, tone, detail?}]
    checks  items: [{title, status, severity?, detail?, fix?, group?}]   status: ok | warn | bad | info | skip
    list    items: [{text, tone}]
    table   columns: [...], rows: [[...]]
    chain   steps: [{status, url}]
    bars    items: [{label, value, max, tone?, detail?}]
    text    text
Values are already worded for people; the renderers only lay them out.
"""
from __future__ import annotations

TONE_BY_STATUS = {'pass': 'ok', 'passed': 'ok', 'ok': 'ok', 'fail': 'bad', 'failed': 'bad', 'error': 'bad', 'critical': 'bad',
                  'warning': 'warn', 'warn': 'warn', 'attention': 'warn', 'info': 'info', 'skip': 'skip', 'skipped': 'skip', 'na': 'skip'}
SEVERITY_TONE = {'critical': 'bad', 'high': 'bad', 'medium': 'warn', 'warning': 'warn', 'low': 'info', 'info': 'info', 'ok': 'ok'}
MODULE_NAMES = {'infra': 'Infraestrutura', 'tags': 'Tags', 'conversion': 'Conversão', 'compliance': 'Compliance', 'agentic': 'Agentes de IA',
                'ads': 'Anúncios', 'llms': 'llms.txt', 'page': 'Página', 'robots': 'Robôs', 'sitemap': 'Sitemap', 'technical': 'Técnico',
                'performance': 'Performance', 'media_readiness': 'Prontidão de mídia'}
EFFORT = {'low': 'baixo', 'medium': 'médio', 'high': 'alto'}


def _obj(value):
    return value if isinstance(value, dict) else {}


def _arr(value):
    return value if isinstance(value, list) else []


def _yes(value, yes='Sim', no='Não', good=True):
    if value is None:
        return {'value': '–', 'tone': 'skip'}
    return {'value': yes if value else no, 'tone': ('ok' if value else 'bad') if good else ('bad' if value else 'ok')}


def _row(label, value=None, tone=None, mono=False, **extra):
    if isinstance(value, dict):
        return {'label': label, **value, **({'mono': True} if mono else {})}
    return {'label': label, 'value': '–' if value in (None, '') else value, **({'tone': tone} if tone else {}), **({'mono': True} if mono else {})}


def _score_tone(score):
    score = score or 0
    return 'ok' if score >= 80 else 'warn' if score >= 50 else 'bad'


def _section(sections, id_, title, icon, blocks, summary='', tone=None):
    clean = []
    for block in blocks:
        if not block:
            continue
        for key in ('rows', 'items', 'steps'):
            if key in block:
                block[key] = [item for item in block[key] if item]
        if block.get('rows') or block.get('items') or block.get('steps') or block.get('text'):
            clean.append(block)
    blocks = clean
    if blocks:
        sections.append({'id': id_, 'title': title, 'icon': icon, 'summary': summary, 'tone': tone, 'blocks': blocks})


# --------------------------------------------------------------------------------------------- Reports runs

def _reports_sections(result):
    kind, ev = result.get('kind'), _obj(result.get('evidence'))
    inventory = _obj(ev.get('inventory'))
    sections, indicators, modules = [], [], []

    redirects = _arr(ev.get('redirects'))
    if kind == 'destination':
        status = ev.get('http_status')
        indicators += [{'key': 'http', 'label': 'Status', 'value': f'HTTP {status}' if status else '–', 'tone': 'ok' if status and status < 400 else 'bad', 'target': 'resposta'},
                       {'key': 'ssl', 'label': 'HTTPS', 'value': 'Válido' if _obj(ev.get('ssl')).get('valid') else 'Inválido', 'tone': 'ok' if _obj(ev.get('ssl')).get('valid') else 'bad', 'target': 'seguranca'},
                       {'key': 'time', 'label': 'Resposta', 'value': f'{ev.get("elapsed_ms")} ms' if ev.get('elapsed_ms') is not None else '–', 'tone': 'ok' if (ev.get('elapsed_ms') or 0) < 1500 else 'warn', 'target': 'resposta'},
                       {'key': 'utm', 'label': 'UTMs', 'value': str(len(_obj(ev.get('utm')))), 'tone': 'ok' if ev.get('utm') else 'warn', 'target': 'utm'},
                       {'key': 'redirects', 'label': 'Saltos', 'value': str(max(0, len(redirects) - 1)), 'tone': 'ok' if len(redirects) <= 2 else 'warn', 'target': 'resposta'}]
        _section(sections, 'resposta', 'Resposta e caminho do clique', 'route', [
            {'type': 'chain', 'title': 'Caminho do clique', 'steps': [{'status': step.get('status'), 'url': step.get('url')} for step in redirects]},
            {'type': 'kv', 'rows': [_row('HTTP', status, 'ok' if status and status < 400 else 'bad'), _row('Tempo de resposta', f'{ev.get("elapsed_ms")} ms' if ev.get('elapsed_ms') is not None else None),
                                    _row('URL final', ev.get('final_url'), mono=True)]}])
        utm = _obj(ev.get('utm'))
        _section(sections, 'utm', 'Parâmetros UTM', 'tag', [
            {'type': 'kv', 'rows': [_row(key, (values or [''])[0] or 'vazio', 'ok' if (values or [''])[0] else 'bad', mono=True) for key, values in utm.items()]} if utm
            else {'type': 'text', 'text': 'Nenhum parâmetro utm_ no link: a mídia não será atribuída à campanha nos relatórios.'}],
            tone='ok' if utm else 'warn')
        ssl = _obj(ev.get('ssl'))
        _section(sections, 'seguranca', 'HTTPS', 'lock', [{'type': 'kv', 'rows': [_row('Certificado', _yes(ssl.get('valid'), 'Válido', 'Não validado')),
                                                                              _row('Validade', ssl.get('expires_at')), _row('Emissor', ssl.get('issuer'))]}])
        _section(sections, 'pagina', 'Página de destino', 'file', [{'type': 'kv', 'rows': [_row('Título', ev.get('title')), _row('Descrição', ev.get('description'))]}])

    if kind == 'media':
        supertag = _obj(ev.get('supertag'))
        platforms = _arr(inventory.get('platforms'))
        conv = _obj(ev.get('conversion'))
        consent = _obj(inventory.get('consent'))
        indicators += [{'key': 'supertag', 'label': 'Super Tag', 'value': 'Instalada' if supertag.get('detected') else 'Ausente', 'tone': 'ok' if supertag.get('detected') else 'warn', 'target': 'supertag'},
                       {'key': 'tags', 'label': 'Plataformas', 'value': str(len(platforms)), 'tone': 'ok' if platforms else 'bad', 'target': 'plataformas'},
                       {'key': 'conv', 'label': 'Conversões', 'value': str(int(bool(conv.get('forms'))) + int(bool(conv.get('whatsapp'))) + int(bool(conv.get('phone')))), 'tone': 'ok' if (conv.get('forms') or conv.get('whatsapp') or conv.get('phone')) else 'warn', 'target': 'conversao'},
                       {'key': 'events', 'label': 'Eventos', 'value': str(sum(len(v) for v in _obj(inventory.get('events')).values())), 'tone': 'ok' if inventory.get('events') else 'warn', 'target': 'eventos'},
                       {'key': 'consent', 'label': 'Consentimento', 'value': ', '.join(_arr(consent.get('tools'))) or 'Ausente', 'tone': 'ok' if consent.get('tools') else 'warn', 'target': 'consentimento'}]
        modules += [{'key': item['name'], 'label': item['name'], 'score': item['score']} for item in _arr(ev.get('platforms'))]
        _section(sections, 'supertag', 'Cadu Super Tag', 'star', [{'type': 'kv', 'rows': [
            _row('Situação', _yes(supertag.get('detected'), 'Instalada', 'Não encontrada')),
            _row('Onde', {'code': 'No código da página', 'gtm': 'Injetada pelo Google Tag Manager'}.get(supertag.get('via'))),
            _row('Site cadastrado', supertag.get('site_label')), _row('ID', ', '.join(_arr(supertag.get('public_ids'))) or None, mono=True)]}],
            tone='ok' if supertag.get('detected') else 'warn')
        _section(sections, 'plataformas', 'Plataformas e IDs', 'grid', [
            {'type': 'table', 'columns': ['Plataforma', 'IDs', 'Onde', 'Cargas'],
             'rows': [[item['name'], ', '.join(_arr(item.get('ids'))) or '–', 'No código' if item.get('where') == 'code' else 'Injetada (GTM/JS)', str(item.get('script_loads') or '–')] for item in platforms]},
            {'type': 'bars', 'title': 'Cobertura por plataforma de mídia', 'items': [{'label': item['name'], 'value': item['score'], 'max': 100, 'tone': _score_tone(item['score']),
                                                                                     'detail': ('Falta: ' + ', '.join(item['missing'])) if item.get('missing') else 'Completa'} for item in _arr(ev.get('platforms'))]}],
            summary=f'{len(platforms)} plataforma(s) detectada(s)')
        _section(sections, 'conversao', 'Conversão na página', 'target', [{'type': 'kv', 'rows': [
            _row('Formulários', conv.get('forms') or 0, 'ok' if conv.get('forms') else 'warn'), _row('WhatsApp', _yes(conv.get('whatsapp'))), _row('Telefone', _yes(conv.get('phone'))),
            *[_row(f'Formulário {index + 1}', f'{form.get("fields")} campo(s) · envia para {form.get("action_host")}' + (' (externo)' if form.get('external') else ''), 'warn' if form.get('external') else None)
              for index, form in enumerate(_arr(inventory.get('forms'))[:6])]]}])
        events = _obj(inventory.get('events'))
        _section(sections, 'eventos', 'Eventos de conversão', 'bolt', [
            {'type': 'kv', 'rows': [_row(source, ', '.join(names), mono=True) for source, names in events.items()]} if events
            else {'type': 'text', 'text': 'Nenhum evento encontrado no código. Formulários e WhatsApp sem evento não aparecem nas plataformas de mídia.'}],
            tone='ok' if events else 'warn')
        _section(sections, 'consentimento', 'Consentimento e privacidade', 'shield', [{'type': 'kv', 'rows': [
            _row('Ferramenta de consentimento', ', '.join(_arr(consent.get('tools'))) or 'Nenhuma', 'ok' if consent.get('tools') else 'warn'),
            _row('Consent Mode do Google', _yes(consent.get('consent_mode'), 'Ativo', 'Não detectado')),
            _row('Aviso de cookies', _yes(_obj(ev.get('compliance')).get('consent_detected'))), _row('Política de privacidade', _yes(_obj(ev.get('compliance')).get('privacy_policy_detected')))]}])
        findings = _arr(ev.get('tag_findings'))
        _section(sections, 'achados-tags', 'Achados nas tags', 'alert', [{'type': 'checks', 'items': [
            {'title': item['title'], 'status': SEVERITY_TONE.get(item['severity'], 'info'), 'detail': item.get('detail'), 'fix': item.get('fix')} for item in findings]}],
            summary=f'{len(findings)} achado(s)', tone='warn' if findings else 'ok')

    if kind == 'agentic':
        categories = _arr(ev.get('categories'))
        modules += [{'key': item['name'], 'label': item['name'], 'score': round(item['score'] * 100 / item['max']) if item['max'] else 0,
                     'detail': f'{item["score"]}/{item["max"]} · {item.get("question", "")}'} for item in categories]
        bots = _arr(ev.get('bot_access'))
        waf = _arr(ev.get('waf_probe'))
        resources = _obj(ev.get('resources'))
        content = _obj(ev.get('content'))
        blocked = [bot['name'] for bot in bots if bot['blocked'] and bot.get('purpose') != 'training']
        indicators += [{'key': 'bots', 'label': 'Robôs de busca', 'value': 'Liberados' if not blocked else f'{len(blocked)} bloqueado(s)', 'tone': 'ok' if not blocked else 'bad', 'target': 'robos'},
                       {'key': 'waf', 'label': 'WAF/CDN', 'value': 'Sem bloqueio' if not any(item.get('blocked') for item in waf) else 'Bloqueia', 'tone': 'ok' if not any(item.get('blocked') for item in waf) else 'bad', 'target': 'robos'},
                       {'key': 'llms', 'label': 'llms.txt', 'value': 'Publicado' if _obj(resources.get('llms.txt')).get('available') else 'Ausente', 'tone': 'ok' if _obj(resources.get('llms.txt')).get('available') else 'warn', 'target': 'guias'},
                       {'key': 'sitemap', 'label': 'Sitemap', 'value': 'Válido' if _obj(resources.get('sitemap.xml')).get('available') else 'Ausente', 'tone': 'ok' if _obj(resources.get('sitemap.xml')).get('available') else 'warn', 'target': 'guias'},
                       {'key': 'js', 'label': 'Texto sem JS', 'value': 'Depende de JS' if content.get('js_dependent') else f'{content.get("raw_words") or 0} palavras', 'tone': 'bad' if content.get('js_dependent') else 'ok', 'target': 'conteudo'}]
        if ev.get('caps'):
            _section(sections, 'travas', 'O que limita a nota', 'lock', [{'type': 'list', 'items': [{'text': f'{cap["reason"]} A nota não passa de {cap["limit"]}.', 'tone': 'bad'} for cap in ev['caps']]}], tone='bad')
        findings = _arr(ev.get('findings'))
        by_category = {}
        for item in findings:
            by_category.setdefault(item.get('category') or 'Outros', []).append(item)
        _section(sections, 'checagens', 'Checagens', 'check', [{'type': 'checks', 'items': [
            {'title': item['title'], 'status': SEVERITY_TONE.get(item['severity'], 'info') if item['severity'] != 'ok' else 'ok', 'severity': item['severity'],
             'detail': item.get('detail'), 'fix': item.get('fix'), 'group': item.get('category')} for item in findings]}],
            summary=f'{sum(1 for item in findings if item["severity"] in ("critical", "warning"))} problema(s) · {sum(1 for item in findings if item["severity"] == "ok")} ok')
        _section(sections, 'robos', 'Robôs de IA e WAF', 'robot', [
            {'type': 'chips', 'title': 'robots.txt', 'items': [{'label': bot['name'], 'tone': ('muted' if bot.get('purpose') == 'training' else 'bad') if bot['blocked'] else 'ok',
                                                               'detail': f'{bot.get("vendor")} · {"busca" if bot.get("purpose") == "search" else "usuário" if bot.get("purpose") == "user" else "treinamento"}'} for bot in bots]},
            {'type': 'kv', 'title': 'Acesso com o user-agent do robô (CDN/WAF)', 'rows': [_row(item['name'], 'Bloqueado' if item.get('blocked') else (f'HTTP {item["status"]}' if item.get('status') else 'Sem resposta'),
                                                                                          'bad' if item.get('blocked') else 'ok' if item.get('status') else 'warn') for item in waf]}])
        llms = _obj(ev.get('llms_quality'))
        sitemap = _obj(ev.get('sitemap'))
        _section(sections, 'guias', 'llms.txt e sitemap', 'map', [
            {'type': 'kv', 'title': 'Arquivos do domínio', 'rows': [_row(name, 'Válido' if item.get('available') else ('Responde HTML' if item.get('status') == 200 else f'HTTP {item["status"]}' if item.get('status') else 'Ausente'),
                                                                         'ok' if item.get('available') else 'bad') for name, item in resources.items()]},
            {'type': 'kv', 'title': 'Qualidade do llms.txt', 'rows': [_row('Título (#)', _yes(llms.get('has_title'))), _row('Resumo (>)', _yes(llms.get('has_summary'))),
                                                                      _row('Seções', llms.get('sections')), _row('Links', llms.get('links')),
                                                                      _row('Links quebrados', f'{llms.get("dead_links", 0)} de {llms.get("checked_links", 0)}', 'bad' if llms.get('dead_links') else 'ok')]} if llms.get('valid') else None,
            {'type': 'kv', 'title': 'Sitemap', 'rows': [_row('URLs', sitemap.get('urls')), _row('Índice de sitemaps', _yes(sitemap.get('index'))),
                                                        _row('Última alteração', sitemap.get('last_modified')), _row('Página testada listada', _yes(sitemap.get('lists_page')))]} if sitemap.get('valid') else None])
        _section(sections, 'conteudo', 'Conteúdo legível', 'file', [{'type': 'kv', 'rows': [
            _row('Palavras no HTML entregue', content.get('raw_words')), _row('Palavras após JavaScript', content.get('rendered_words')),
            _row('Depende de JavaScript', _yes(content.get('js_dependent'), good=False)), _row('H1', content.get('h1'), 'ok' if content.get('h1') == 1 else 'warn'),
            _row('H2', content.get('h2')), _row('Imagens com alt', f'{content.get("images_with_alt", 0)} de {content.get("images", 0)}'),
            _row('Título', content.get('title')), _row('Descrição', content.get('description'))]},
            {'type': 'chips', 'title': 'Dados estruturados (JSON-LD)', 'items': [{'label': name, 'tone': 'ok'} for name in _arr(ev.get('schema_types'))]
             or [{'label': 'Nenhum tipo encontrado', 'tone': 'bad'}]}])

    if inventory:
        scripts = _obj(inventory.get('scripts'))
        _section(sections, 'javascript', 'JavaScript e tecnologias', 'code', [
            {'type': 'kv', 'rows': [_row('Scripts externos', scripts.get('external')), _row('De terceiros', scripts.get('third_party')),
                                    _row('Injetados após carregar', scripts.get('injected')), _row('Bloqueantes no código', scripts.get('blocking_in_code'), 'warn' if (scripts.get('blocking_in_code') or 0) >= 5 else None),
                                    _row('Inline', f'{scripts.get("inline_in_code", 0)} ({scripts.get("inline_kb", 0)} KB)')]},
            {'type': 'table', 'title': 'Por origem', 'columns': ['Domínio', 'Scripts', 'Injetados', 'Origem'],
             'rows': [[item['host'], str(item['scripts']), str(item['injected']), 'próprio' if item['origin'] == 'first_party' else 'terceiro'] for item in _arr(scripts.get('by_host'))]}])

    review = _obj(result.get('review'))
    if review:
        _section(sections, 'revisao', 'Revisão do Cadu', 'sparkle', [
            {'type': 'text', 'text': review.get('summary')},
            {'type': 'checks', 'items': [{'title': f'{item.get("plataforma") or ""}: {item.get("problema")}'.strip(': '), 'status': {'critico': 'bad', 'atencao': 'warn'}.get(item.get('gravidade'), 'info'),
                                          'detail': item.get('evidencia'), 'fix': item.get('correcao')} for item in _arr(review.get('problems'))]},
            {'type': 'list', 'title': 'Verificar no GTM', 'items': [{'text': text, 'tone': 'info'} for text in _arr(review.get('check_in_gtm'))]},
            {'type': 'list', 'title': 'Perguntar ao cliente', 'items': [{'text': text, 'tone': 'info'} for text in _arr(review.get('questions'))]}],
            summary=f'Veredito: {review.get("verdict") or "–"}', tone={'pronto': 'ok', 'bloqueado': 'bad'}.get(review.get('verdict'), 'warn'))
    alerts = _arr(result.get('alerts'))
    if alerts and kind != 'agentic':
        _section(sections, 'atencao', 'Pontos de atenção', 'alert', [{'type': 'list', 'items': [{'text': text, 'tone': 'warn'} for text in alerts]}], tone='warn')
    return sections, indicators, modules


# --------------------------------------------------------------------------------------------- PHP analyses

def _legacy_sections(a):
    sections, indicators, modules = [], [], []
    http, redirects, perf, ssl = _obj(a.get('http_status')), _obj(a.get('redirects')), _obj(a.get('performance')), _obj(a.get('ssl'))
    robots, adsbot, meta = _obj(a.get('robots')), _obj(_obj(a.get('robots')).get('adsbot_access_test')), _obj(a.get('meta'))
    tags = [item for item in _obj(a.get('tags')).values() if isinstance(item, dict)]
    detected = [item for item in tags if item.get('detected')]
    conv, comp, events = _obj(a.get('conversion')), _obj(a.get('compliance')), _obj(a.get('events'))
    indicators += [{'key': 'http', 'label': 'Status', 'value': f'HTTP {http.get("code")}' if http.get('code') else '–', 'tone': 'ok' if http.get('is_success') else 'bad', 'target': 'desempenho'},
                   {'key': 'ssl', 'label': 'SSL', 'value': (f'{ssl.get("days_left")} dias' if ssl.get('days_left') is not None else 'Válido') if ssl.get('valid') else 'Inválido',
                    'tone': 'bad' if not ssl.get('valid') else 'warn' if (ssl.get('days_left') or 99) < 30 else 'ok', 'target': 'seguranca'},
                   {'key': 'robots', 'label': 'Google Ads', 'value': 'Pronto' if robots.get('google_ads_ready') else 'Atenção', 'tone': 'ok' if robots.get('google_ads_ready') else 'warn', 'target': 'robos'},
                   {'key': 'time', 'label': 'Resposta', 'value': f'{perf.get("response_time_ms")} ms' if perf.get('response_time_ms') is not None else '–', 'tone': 'ok' if perf.get('is_fast') else 'warn', 'target': 'desempenho'},
                   {'key': 'tags', 'label': 'Tags', 'value': str(len(detected)), 'tone': 'ok' if detected else 'bad', 'target': 'tags'},
                   {'key': 'conv', 'label': 'Conversão', 'value': str(conv.get('conversion_score', '–')), 'tone': _score_tone(conv.get('conversion_score')), 'target': 'conversao'}]
    scopes = _obj(a.get('scores_by_scope'))
    mr = _obj(_obj(a.get('media_readiness')).get('scores'))
    modules += [{'key': key, 'label': MODULE_NAMES.get(key, key), 'score': value} for key, value in scopes.items() if isinstance(value, (int, float))]
    if not modules:
        modules += [{'key': key, 'label': label, 'score': mr[key]} for key, label in (('tags_score', 'Tags'), ('conversion_score', 'Conversão'), ('compliance_score', 'Compliance'),
                                                                                      ('technical_score', 'Técnico'), ('performance_score', 'Performance'), ('ai_readiness_score', 'IA')) if isinstance(mr.get(key), (int, float))]

    _section(sections, 'desempenho', 'Resposta e desempenho', 'route', [
        {'type': 'kv', 'rows': [_row('HTTP', f'{http.get("code", "–")} {http.get("status_text", "")}'.strip(), 'ok' if http.get('is_success') else 'bad'),
                                _row('Soft 404', _yes(http.get('is_soft_404'), good=False)), _row('Página de erro', _yes(http.get('error_page_detected'), good=False)),
                                _row('Tempo de resposta', f'{perf.get("response_time_ms")} ms' if perf.get('response_time_ms') is not None else None, 'ok' if perf.get('is_fast') else 'warn'),
                                _row('Tamanho da página', f'{perf.get("page_size_kb")} KB' if perf.get('page_size_kb') is not None else None)]},
        {'type': 'chain', 'title': f'Redirecionamentos ({redirects.get("count", 0)})', 'steps': [{'status': step.get('status') or step.get('code'), 'url': step.get('url')} for step in _arr(redirects.get('chain')) if isinstance(step, dict)]
         or [{'status': redirects.get('http_code'), 'url': redirects.get('final_url')}]}])
    _section(sections, 'seguranca', 'Segurança (SSL)', 'lock', [{'type': 'kv', 'rows': [
        _row('Certificado', _yes(ssl.get('valid'), 'Válido', 'Inválido')), _row('Emissor', ssl.get('issuer_org') or ssl.get('issuer')),
        _row('Válido de', ssl.get('valid_from')), _row('Vence em', ssl.get('expires')),
        _row('Dias restantes', ssl.get('days_left'), 'bad' if (ssl.get('days_left') or 99) < 30 else 'warn' if (ssl.get('days_left') or 99) < 60 else 'ok'),
        _row('Protocolo', ssl.get('protocol')), _row('Tipo', ('EV' if ssl.get('is_ev') else 'Padrão') + (' · curinga' if ssl.get('is_wildcard') else '')),
        _row('Chave', f'{ssl.get("key_type", "")} {ssl.get("key_bits", "")}'.strip() or None), _row('Domínios cobertos', ', '.join(_arr(ssl.get('san_domains'))[:6]) or None, mono=True)]}])
    _section(sections, 'robos', 'Robôs de anúncios e indexação', 'robot', [{'type': 'kv', 'rows': [
        _row('Pronto para Google Ads', _yes(robots.get('google_ads_ready'))), _row('AdsBot do Google acessa', _yes(adsbot.get('accessible'))),
        _row('Código para o AdsBot', adsbot.get('http_code')), _row('Motivo do bloqueio', adsbot.get('block_reason')),
        _row('Permite indexação', _yes(robots.get('allows_indexing'))), _row('Permite anúncios', _yes(robots.get('allows_ads'))),
        _row('robots.txt', _yes(_obj(robots.get('robots_txt')).get('exists'), 'Existe', 'Ausente')),
        _row('Meta robots', _yes(_obj(robots.get('meta_robots')).get('allows'), 'Permite', 'Bloqueia')),
        _row('X-Robots-Tag', _yes(_obj(robots.get('x_robots_tag')).get('allows'), 'Permite', 'Bloqueia')),
        _row('Googlebot', _yes(_obj(robots.get('googlebot')).get('allows'), 'Permitido', 'Bloqueado')), _row('Facebook', _yes(_obj(robots.get('facebookbot')).get('allows'), 'Permitido', 'Bloqueado'))]}])
    _section(sections, 'pagina', 'Página e compartilhamento', 'file', [{'type': 'kv', 'rows': [
        _row('Título', meta.get('title')), _row('Tamanho do título', meta.get('title_length')), _row('Descrição', meta.get('description')),
        _row('Canonical', meta.get('canonical'), mono=True), _row('H1', meta.get('h1_count'), 'ok' if meta.get('h1_count') == 1 else 'warn'),
        _row('Mobile friendly', _yes(meta.get('is_mobile_friendly'))), _row('Favicon', _yes(meta.get('has_favicon'))),
        _row('Open Graph', ', '.join(name for name, key in (('título', 'og_title'), ('descrição', 'og_description'), ('imagem', 'og_image')) if meta.get(key)) or 'ausente', 'ok' if meta.get('og_image') else 'warn'),
        _row('Links / imagens', f'{meta.get("links_count", "–")} / {meta.get("images_count", "–")}')]}])
    by_category = {}
    for item in tags:
        by_category.setdefault(item.get('category') or 'outros', []).append(item)
    _section(sections, 'tags', 'Tags e tecnologias', 'grid', [
        {'type': 'chips', 'title': category.capitalize(), 'items': [{'label': item.get('name'), 'tone': 'ok' if item.get('detected') else 'muted',
                                                                     'detail': ', '.join(_arr(item.get('events'))[:4]) or None} for item in items]}
        for category, items in sorted(by_category.items(), key=lambda pair: -sum(1 for item in pair[1] if item.get('detected')))],
        summary=f'{len(detected)} de {len(tags)} detectadas · leitura do HTML (tags só via GTM podem faltar)')
    platforms = [item for item in _obj(a.get('media_platforms')).values() if isinstance(item, dict)]
    _section(sections, 'plataformas', 'Prontidão por plataforma', 'bars', [
        {'type': 'bars', 'items': [{'label': item.get('label') or item.get('platform'), 'value': item.get('readinessScore') or 0, 'max': 100, 'tone': _score_tone(item.get('readinessScore')),
                                    'detail': ('Falta: ' + ', '.join(_arr(item.get('missingTags')))) if item.get('missingTags') else None} for item in platforms]},
        {'type': 'list', 'title': 'Problemas', 'items': [{'text': f'{item.get("label")}: {issue if isinstance(issue, str) else issue.get("message") or issue.get("title")}', 'tone': 'warn'}
                                                         for item in platforms for issue in _arr(item.get('issues'))[:3]]}])
    gaps = _arr(events.get('conversion_gaps'))
    _section(sections, 'eventos', 'Eventos e lacunas de conversão', 'bolt', [
        {'type': 'kv', 'rows': [_row('dataLayer', _yes(events.get('has_data_layer'))), _row('Eventos', ', '.join(_arr(events.get('all_events'))) or 'nenhum', mono=True),
                                _row('Duplicados', ', '.join(map(str, _arr(events.get('duplicates')))) or 'nenhum')]} if events else None,
        {'type': 'checks', 'title': 'Elemento visível sem evento', 'items': [{'title': f'{gap.get("element") or gap.get("type")} sem o evento {gap.get("expected_event")}', 'status': 'warn',
                                                                            'fix': gap.get('recommendation')} for gap in gaps]}],
        tone='warn' if gaps else None)
    forms, wa, phones, cta, chat, email = (_obj(conv.get(key)) for key in ('forms', 'whatsapp', 'phone_numbers', 'cta_buttons', 'chat_widgets', 'email_links'))
    _section(sections, 'conversao', 'Conversão', 'target', [{'type': 'kv', 'rows': [
        _row('Nota de conversão', conv.get('conversion_score'), _score_tone(conv.get('conversion_score'))),
        _row('Formulários', f'{forms.get("count", 0)}' + ''.join(f' · {label}' for key, label in (('has_lead_form', 'lead'), ('has_contact_form', 'contato'), ('has_newsletter', 'newsletter')) if forms.get(key))),
        _row('WhatsApp', f'Sim · {wa.get("number")}' if wa.get('detected') and wa.get('number') else _yes(wa.get('detected'))),
        _row('Telefone', f'{phones.get("count", 0)}' + (' · click to call' if phones.get('has_click_to_call') else '')),
        _row('E-mail', email.get('count', 0)), _row('CTAs', f'{cta.get("count", 0)}' + (f' · {", ".join(_arr(cta.get("types"))[:6])}' if cta.get('types') else '')),
        _row('Chat', ', '.join(_arr(chat.get('providers'))) or ('Sim' if chat.get('detected') else 'Não')), _row('Popup', _yes(conv.get('popup_detected'), good=False))]}])
    consent = _obj(a.get('consent_analysis'))
    _section(sections, 'compliance', 'Compliance e consentimento', 'shield', [
        {'type': 'kv', 'rows': [_row('Política de privacidade', _yes(comp.get('has_privacy_policy'))), _row('Política de cookies', _yes(comp.get('has_cookie_policy'))),
                                _row('Banner de consentimento', _yes(comp.get('has_cookie_consent'))), _row('Consent Mode', _yes(comp.get('consent_mode'))),
                                _row('Menciona LGPD', _yes(comp.get('has_lgpd'))), _row('Termos de uso', _yes(comp.get('has_terms'))),
                                _row('Risco', consent.get('riskLabel'), {'high': 'bad', 'medium': 'warn', 'low': 'ok'}.get(consent.get('riskLevel'))) if consent else None]},
        {'type': 'list', 'title': 'Links encontrados', 'items': [{'text': f'{link.get("label") or link.get("type")}: {link.get("url")}', 'tone': 'info'} for link in _arr(comp.get('links')) if isinstance(link, dict)]}])
    page = _obj(a.get('page_content'))
    _section(sections, 'conteudo', 'Conteúdo da página', 'file', [
        {'type': 'kv', 'rows': [_row('Tipo de página', page.get('page_type')), _row('Idioma', page.get('language')), _row('Palavras', page.get('word_count'))]},
        {'type': 'chips', 'title': 'Chamadas para ação', 'items': [{'label': text, 'tone': 'info'} for text in _arr(page.get('cta_texts'))[:12]]},
        {'type': 'list', 'title': 'Títulos', 'items': [{'text': f'H{item.get("level")} · {item.get("text")}', 'tone': 'info'} for item in _arr(page.get('headings'))[:12] if isinstance(item, dict)]}])
    sa = _obj(a.get('site_agentic'))
    if sa:
        layers = _obj(sa.get('scores_by_layer') or a.get('scores_agentic_by_layer'))
        indicators.append({'key': 'agentic', 'label': 'Agentes de IA', 'value': str(a.get('score_agentic') or sa.get('score_total') or '–'), 'tone': _score_tone(a.get('score_agentic') or sa.get('score_total')), 'target': 'agentes'})
        _section(sections, 'agentes', 'Agentes de IA', 'robot', [
            {'type': 'bars', 'title': 'Nota por camada', 'items': [{'label': MODULE_NAMES.get(key, key), 'value': value, 'max': 100, 'tone': _score_tone(value)} for key, value in layers.items()]},
            {'type': 'checks', 'items': [{'title': item.get('title'), 'status': TONE_BY_STATUS.get(str(item.get('status')).lower(), 'skip'), 'severity': item.get('severity'),
                                          # `analysis_improve` is the PHP team's note on the method, not advice for the client.
                                          'detail': item.get('message'),
                                          'group': MODULE_NAMES.get(item.get('category'), item.get('category'))} for item in _arr(sa.get('check_results'))]}],
            summary=f'{sum(1 for item in _arr(sa.get("check_results")) if item.get("status") == "pass")} de {len(_arr(sa.get("check_results")))} checagens ok')
    checklist = _arr(_obj(a.get('media_readiness')).get('checklist'))
    _section(sections, 'checklist', 'Checklist de mídia', 'check', [{'type': 'checks', 'items': [
        {'title': item.get('title'), 'status': TONE_BY_STATUS.get(str(item.get('status')).lower(), 'info'), 'detail': item.get('explanation'),
         'fix': item.get('fixSuggestion') if item.get('status') != 'passed' else None} for item in checklist]}])
    recs = _arr(_obj(a.get('prioritized_recommendations')).get('items')) or _arr(_obj(_obj(a.get('media_readiness')).get('recommendations')).get('items')) or _arr(_obj(a.get('recommendations')).get('items'))
    legacy_recs = _obj(a.get('recommendations'))
    v1 = [{'title': item.get('text'), 'severity': item.get('priority')} for key in ('critical', 'errors', 'warnings', 'suggestions') for item in _arr(legacy_recs.get(key)) if isinstance(item, dict)]
    positives = [item.get('text') or item.get('title') for item in _arr(legacy_recs.get('positives')) + _arr(_obj(a.get('prioritized_recommendations')).get('positives')) if isinstance(item, dict)]
    items = recs or v1
    _section(sections, 'recomendacoes', 'Recomendações', 'sparkle', [
        {'type': 'checks', 'items': [{'title': item.get('title'), 'status': SEVERITY_TONE.get(item.get('severity'), 'info'), 'severity': item.get('severity'),
                                      'detail': ' · '.join(filter(None, [item.get('description'), item.get('impact')])) or None,
                                      'fix': ' · '.join(filter(None, [item.get('actionLabel'), item.get('effort') and f'esforço {EFFORT.get(item["effort"], item["effort"])}',
                                                                      item.get('estimatedScoreGain') is not None and f'+{item["estimatedScoreGain"]} pontos'])) or None}
                                     for item in items if isinstance(item, dict)]},
        {'type': 'list', 'title': 'O que já está certo', 'items': [{'text': text, 'tone': 'ok'} for text in positives if text]}],
        summary=f'{len(items)} recomendação(ões)')
    return sections, indicators, modules


# --------------------------------------------------------------------------------------------- public API

TONE_RANK = {'bad': 0, 'warn': 1, 'info': 2, None: 2, 'ok': 3, 'skip': 4, 'muted': 4}


def _overview(sections):
    """Sections as a map to read first: problems first, each with its own count of issues when it has checks."""
    items = []
    for index, section in enumerate(sections):
        checks = [item for block in section['blocks'] if block['type'] == 'checks' for item in block['items']]
        issues = sum(1 for item in checks if item.get('status') in ('bad', 'warn'))
        tone = section.get('tone') or ('bad' if any(item.get('status') == 'bad' for item in checks) else 'warn' if issues else None)
        items.append({'id': section['id'], 'title': section['title'], 'tone': tone or 'info', 'summary': section.get('summary') or '',
                      'issues': issues, 'order': index})
    items.sort(key=lambda item: (TONE_RANK.get(item['tone'], 2), item['order']))
    return {'items': items, 'problems': sum(1 for item in items if item['tone'] in ('bad', 'warn')), 'total': len(items)}


def build(run):
    """``run`` as returned by ``reports_link_history.detail`` (either source)."""
    legacy = run.get('source') == 'cadu_php'
    if legacy:
        sections, indicators, modules = _legacy_sections(_obj(run.get('analysis')))
        shots = _obj(run.get('screenshots'))
        summary = None
    else:
        result = _obj(run.get('result'))
        sections, indicators, modules = _reports_sections(result)
        ev = _obj(result.get('evidence'))
        shots = {'desktop': ev.get('screenshot'), 'mobile': ev.get('screenshot_mobile'), 'note': ev.get('capture_note')}
        summary = result.get('summary')
    return {
        'header': {'score': run.get('score'), 'tone': _score_tone(run.get('score')), 'status_label': run.get('status_label'), 'kind': run.get('kind') or run.get('mode'),
                   'type_label': run.get('type_label'), 'source': run.get('source'), 'url': run.get('final_url') or run.get('original_url'),
                   'original_url': run.get('original_url'), 'author': run.get('author'), 'created_at': run.get('created_at'), 'summary': summary,
                   'highlights': _obj(run.get('result')).get('highlights') or []},
        'indicators': indicators, 'modules': modules, 'sections': sections, 'overview': _overview(sections),
        'screenshots': {'desktop': shots.get('desktop'), 'mobile': shots.get('mobile'), 'note': shots.get('note')},
    }
