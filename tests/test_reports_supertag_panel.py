"""Super Tag panel: snippet with named HTML comments, the Google Tag Manager loader, creating conversion rules of every
type through the real /connect blueprint (with the app-wide error pages registered) and readable 400 messages."""
import json
import uuid
from unittest import mock

import pytest
from flask import Flask

from aicentralv2.cadu_connect import reports_supertag
from aicentralv2.cadu_connect import reports_supertag_leads as leads
from aicentralv2.error_pages import register_error_pages
from tests.test_reports_supertag import FakeDb

SITE_ID = str(uuid.uuid4())
BASE = 'https://reports.example.test'


@pytest.fixture(scope='module')
def app():
    """Same wiring as production: uniform error pages per status code plus the real Reports blueprint."""
    from aicentralv2.cadu_connect.routes import bp
    flask_app = Flask(__name__, template_folder='../aicentralv2/templates', static_folder='../aicentralv2/static')
    flask_app.config.update(SECRET_KEY='test-secret', CONNECT_URL=BASE)
    register_error_pages(flask_app)
    flask_app.register_blueprint(bp)
    return flask_app


# ---------------------------------------------------------------- snippets

def test_snippet_is_wrapped_in_named_comments(app):
    with app.test_request_context('/'):
        snippet = reports_supertag._supertag_snippet({'public_id': 'abc123', 'label': 'Loja Centro', 'allowed_host': 'loja.com.br'})
    assert snippet.splitlines() == [
        '<!-- Cadu Super Tag · Loja Centro (loja.com.br) -->',
        f'<script async src="{BASE}/v1/supertag.js" data-cadu-site="abc123"></script>',
        '<!-- End Cadu Super Tag -->']


@pytest.mark.parametrize('site,title', [
    ({'label': 'site.com.br', 'allowed_host': 'site.com.br'}, 'Cadu Super Tag · site.com.br'),
    ({'label': '', 'allowed_host': 'site.com.br'}, 'Cadu Super Tag · site.com.br'),
    ({}, 'Cadu Super Tag'),
    ({'label': 'Promo --> <script>alert(1)</script> ---', 'allowed_host': 'a.com'}, None),
])
def test_comment_name_can_never_close_or_break_the_comment(app, site, title):
    with app.test_request_context('/'):
        first = reports_supertag._supertag_snippet({'public_id': 'abc', **site}).splitlines()[0]
    inner = first[len('<!-- '):-len(' -->')]
    assert first.startswith('<!-- ') and first.endswith(' -->')
    assert '--' not in inner and '>' not in inner and '<' not in inner and not inner.endswith('-')
    if title:
        assert inner == title


def test_gtm_snippet_injects_the_same_tag_with_the_site_id(app):
    with app.test_request_context('/'):
        gtm = reports_supertag._supertag_gtm_snippet({'public_id': 'abc123', 'label': 'Loja', 'allowed_host': 'loja.com.br'})
    lines = gtm.splitlines()
    assert lines[0] == '<!-- Cadu Super Tag · Loja (loja.com.br) -->' and lines[-1] == '<!-- End Cadu Super Tag -->'
    assert "d.createElement('script')" in gtm and 's.async = true;' in gtm
    assert f"s.src = '{BASE}/v1/supertag.js?id=abc123';" in gtm
    assert "s.setAttribute('data-cadu-site', 'abc123');" in gtm
    # GTM's editor only takes ES5 in custom HTML.
    assert '=>' not in gtm and 'let ' not in gtm and 'const ' not in gtm and '`' not in gtm


# ---------------------------------------------------------------- creating conversion rules

def _patch(app, payload, config=None, csrf='tok'):
    current = {'id': SITE_ID, 'label': 'Loja', 'allowed_host': 'loja.com.br', 'config': config or {}, 'config_version': 1}
    captured = {}

    def answer(sql, params=()):
        if 'FOR UPDATE' in sql:
            return [current]
        if sql.lstrip().startswith('UPDATE cadu_reports_supertag_sites'):
            captured['config'] = json.loads(params[2])
            return [{'id': SITE_ID, 'public_id': 'abc', 'label': 'Loja', 'allowed_host': 'loja.com.br', 'enabled': True,
                     'config': captured['config'], 'config_version': 2, 'created_at': None, 'updated_at': None,
                     'revoked_at': None}]
        return []
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['family_csrf'] = 'tok'
    with mock.patch.object(reports_supertag, '_selection', return_value={'client_id': 7, 'role': 'admin'}), \
            mock.patch.object(reports_supertag, 'get_db', return_value=FakeDb()), \
            mock.patch.object(reports_supertag, '_rows', side_effect=answer):
        # Same request the panel sends: fetch() without an Accept header, JSON body and the CSRF header.
        response = client.patch(f'/connect/api/v2/reports/supertag/sites/{SITE_ID}', data=json.dumps(payload),
                                headers={'Content-Type': 'application/json', 'X-CSRF-Token': csrf})
    return response, captured


@pytest.mark.parametrize('rule,saved', [
    ({'type': 'path', 'match': 'exact', 'value': '/obrigado'}, {'type': 'path', 'match': 'exact', 'value': '/obrigado'}),
    ({'type': 'path', 'match': 'prefix', 'value': '/checkout/fim'}, {'type': 'path', 'match': 'prefix', 'value': '/checkout/fim'}),
    ({'type': 'path', 'match': 'segment', 'value': 'obrigad'}, {'type': 'path', 'match': 'segment', 'value': 'obrigad'}),
    ({'type': 'valid_form'}, {'type': 'valid_form'}),
    ({'type': 'valid_form', 'form_id': 'contato'}, {'type': 'valid_form', 'form_id': 'contato'}),
    ({'type': 'event_name', 'value': 'lead_enviado', 'name': 'lead'}, {'type': 'event_name', 'value': 'lead_enviado', 'name': 'lead'}),
])
def test_panel_creates_each_rule_type(app, rule, saved):
    response, captured = _patch(app, {'conversion_rules': [rule]})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert captured['config']['conversion_rules'] == [saved]
    site = response.get_json()['site']
    assert site['snippet'].startswith('<!-- Cadu Super Tag · Loja (loja.com.br) -->')
    assert 'createElement' in site['snippet_gtm']


@pytest.mark.parametrize('typed,stored', [
    ('obrigado', '/obrigado'),
    ('https://loja.com.br/obrigado?pedido=1#topo', '/obrigado'),
    ('/obrigado?utm_source=x', '/obrigado'),
    (' /obrigado ', '/obrigado'),
])
def test_addresses_are_accepted_as_people_paste_them(app, typed, stored):
    response, captured = _patch(app, {'conversion_rules': [{'type': 'path', 'match': 'exact', 'value': typed}]})
    assert response.status_code == 200
    assert captured['config']['conversion_rules'][0]['value'] == stored


def test_conversion_name_is_written_in_plain_words(app):
    response, captured = _patch(app, {'conversion_rules': [
        {'type': 'path', 'match': 'segment', 'value': '/sucesso/', 'name': 'Lead do Formulário'}]})
    assert response.status_code == 200
    assert captured['config']['conversion_rules'] == [{'type': 'path', 'match': 'segment', 'value': 'sucesso', 'name': 'lead_do_formulario'}]


def test_refused_rule_answers_json_with_a_readable_message(app):
    response, captured = _patch(app, {'conversion_rules': [{'type': 'event_name', 'value': 'lead-enviado'}]})
    assert response.status_code == 400 and not captured
    body = response.get_json()
    assert body is not None, 'a resposta precisa ser JSON, não a página de erro genérica'
    assert 'Nome do evento' in body['error'] and 'CaduSuperTag.event' in body['error']


def test_wrong_csrf_is_a_readable_403(app):
    response, captured = _patch(app, {'conversion_rules': []}, csrf='outro')
    assert response.status_code == 403 and not captured
    assert response.get_json()['error'] == 'Token de sessão inválido.'


def test_other_connect_pages_keep_the_uniform_error_page(app):
    app.jinja_env.globals.setdefault('product_url', lambda *args, **kwargs: '/')
    response = app.test_client().get('/connect/nao-existe')
    assert response.status_code == 404
    assert 'RESOURCE_NOT_FOUND' in response.get_data(as_text=True)


def test_rule_helpers():
    with Flask(__name__).test_request_context('/'):
        assert leads.conversion_name('  Página de Obrigado! ') == 'pagina_de_obrigado'
        assert leads.conversion_name('') is None
        assert leads.conversion_name('Lead_Site') == 'Lead_Site', 'nome já salvo não pode mudar ao salvar de novo'
        assert leads.conversion_path('obrigado/') == '/obrigado/'
