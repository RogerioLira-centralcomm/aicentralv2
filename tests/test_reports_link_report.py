"""The sectioned Link Tester report shared by the page in the tool and the public link."""
import datetime
from pathlib import Path

from flask import Flask, render_template

from aicentralv2.cadu_connect import reports_link_report as report

NOW = datetime.datetime(2026, 10, 7, 12, 0, tzinfo=datetime.timezone.utc)
TEMPLATES = Path(__file__).resolve().parents[1] / 'aicentralv2' / 'templates'
BLOCK_TYPES = {'kv', 'chips', 'checks', 'list', 'table', 'chain', 'bars', 'text'}


def reports_run(kind, evidence):
    return {'source': 'reports', 'kind': kind, 'mode': kind, 'score': 72, 'status_label': 'Atenção', 'final_url': 'https://a.com/', 'original_url': 'https://a.com/',
            'author': 'Apolo', 'created_at': NOW, 'result': {'kind': kind, 'summary': 'Resumo.', 'alerts': ['Sem UTM.'], 'highlights': [{'tone': 'warn', 'text': 'Sem UTM.'}],
                                                             'evidence': evidence}}


LEGACY = {'source': 'cadu_php', 'kind': 'media', 'score': 77, 'status_label': 'Bom', 'final_url': 'https://www.cemig.com.br/', 'author': 'João', 'created_at': NOW,
          'type_label': 'Análise completa (Cadu anterior)', 'screenshots': {'desktop': '/x?device=desktop', 'mobile': None},
          'analysis': {'http_status': {'code': 200, 'is_success': True}, 'ssl': {'valid': True, 'days_left': 20}, 'robots': {'google_ads_ready': False, 'adsbot_access_test': {'accessible': False, 'http_code': 403}},
                       'tags': {'ga4': {'name': 'GA4', 'detected': True, 'category': 'analytics'}, 'meta': {'name': 'Meta Pixel', 'detected': False, 'category': 'ads'}},
                       'events': {'has_data_layer': False, 'conversion_gaps': [{'element': 'WhatsApp', 'expected_event': 'whatsapp_click', 'recommendation': 'Crie o evento.'}]},
                       'site_agentic': {'scores_by_layer': {'llms': 0, 'page': 85}, 'check_results': [{'title': 'llms.txt existe', 'status': 'fail', 'category': 'llms', 'message': 'Crie /llms.txt',
                                                                                                      'analysis_improve': 'nota interna'}]},
                       'prioritized_recommendations': {'items': [{'title': 'Instale o Meta Pixel', 'severity': 'high', 'estimatedScoreGain': 8, 'effort': 'medium'}]}}}


def assert_well_formed(built):
    assert built['header']['score'] is not None
    for section in built['sections']:
        assert section['id'] and section['title'] and section['blocks']
        for block in section['blocks']:
            assert block['type'] in BLOCK_TYPES
            assert all(item is not None for item in block.get('rows', []) + block.get('items', []))


def test_every_reports_kind_builds_sections_and_indicators():
    destination = report.build(reports_run('destination', {'http_status': 200, 'redirects': [{'url': 'https://a.com/', 'status': 200}], 'utm': {}, 'ssl': {'valid': True}}))
    media = report.build(reports_run('media', {'supertag': {'detected': True, 'via': 'gtm', 'public_ids': ['abc']}, 'platforms': [{'name': 'Google', 'score': 67, 'missing': ['Google Ads']}],
                                               'inventory': {'platforms': [{'name': 'Google Tag Manager', 'ids': ['GTM-1'], 'where': 'code', 'script_loads': 1}], 'scripts': {'external': 3}, 'events': {}, 'consent': {}}}))
    agentic = report.build(reports_run('agentic', {'categories': [{'name': 'Acesso', 'score': 30, 'max': 30}], 'findings': [{'severity': 'critical', 'title': 'Sem llms.txt', 'category': 'Guias'}],
                                                   'caps': [{'limit': 40, 'reason': 'WAF bloqueia.'}], 'bot_access': [{'name': 'GPTBot', 'blocked': True, 'purpose': 'training'}],
                                                   'resources': {'llms.txt': {'available': False, 'status': 404}}, 'content': {'raw_words': 10}}))
    for built in (destination, media, agentic):
        assert_well_formed(built)
        assert built['indicators']
    assert [s['id'] for s in destination['sections']][:2] == ['resposta', 'utm']
    assert any(s['id'] == 'supertag' for s in media['sections'])
    assert [s['id'] for s in agentic['sections']][0] == 'travas'


def test_php_analysis_is_read_into_the_same_sections_without_internal_notes():
    built = report.build(LEGACY)
    assert_well_formed(built)
    ids = [s['id'] for s in built['sections']]
    for expected in ('desempenho', 'seguranca', 'robos', 'tags', 'eventos', 'agentes', 'recomendacoes'):
        assert expected in ids
    assert 'nota interna' not in str(built)          # the PHP method note is not advice for the client
    assert '+8 pontos' in str(built)                   # estimated gain survives
    ssl = next(i for i in built['indicators'] if i['key'] == 'ssl')
    assert ssl['tone'] == 'warn'                       # 20 days left


def test_public_page_renders_every_block_type():
    app = Flask('t', template_folder=str(TEMPLATES))
    with app.app_context(), app.test_request_context():
        for run in (LEGACY, reports_run('destination', {'http_status': 200, 'redirects': [{'url': 'https://a.com/', 'status': 301}, {'url': 'https://a.com/x', 'status': 200}], 'utm': {'utm_source': ['g']}})):
            html = render_template('cadu_connect/public_link_test.html', report=report.build(run))
            assert 'class="gauge"' in html and 'nav class="toc"' in html and '<details class="card section"' in html
