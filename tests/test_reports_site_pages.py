from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_site_pages as pages
from aicentralv2.cadu_connect.reports_site_pages import slug_name


def test_names_come_from_the_address():
    assert slug_name('/') == 'Página inicial'
    assert slug_name('/audiencia/empresarios-pro') == 'Audiencia · Empresarios Pro'
    assert slug_name('/en/contact') == 'En · Contact'
    assert slug_name('/blog/2026/black_friday.html') == 'Blog · 2026 · Black Friday'
    assert slug_name('/%C3%A1rea-cliente') == 'Área Cliente'
    assert slug_name('/a/b/c/d/e') == 'C · D · E'


class FakeDb:
    commits = 0

    def commit(self):
        FakeDb.commits += 1


def _client(monkeypatch, rows, hosts=('www.cliente.com.br',)):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    blueprint = Blueprint('site_pages', __name__)
    pages.register(blueprint)
    app.register_blueprint(blueprint)
    calls = []

    def recorder(sql, params=()):
        calls.append((sql, params))
        if 'FROM cadu_reports_supertag_sites' in sql:
            return [{'allowed_host': host} for host in hosts]
        return rows(sql, params)

    monkeypatch.setattr(pages, '_rows', recorder)
    monkeypatch.setattr(pages, 'get_db', lambda: FakeDb())
    monkeypatch.setattr(pages, '_selection', lambda *_: {'client_id': 7})
    monkeypatch.setattr(pages, '_write_guard', lambda *_: None)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    return client, calls


def test_search_returns_urls_for_the_catalog_of_an_owned_domain(monkeypatch):
    def rows(sql, params):
        if 'FROM cadu_reports_site_catalogs' in sql:
            from datetime import timedelta
            return [{'refreshed_at': None, 'page_count': 2, 'truncated': False, 'age': timedelta(hours=1)}]
        if 'FROM cadu_reports_site_pages' in sql:
            assert params[:2] == (7, 'www.cliente.com.br') and '%oferta%' in params
            return [{'host': 'www.cliente.com.br', 'path': '/oferta', 'name': 'Oferta', 'title': None}, {'host': 'www.cliente.com.br', 'path': '/', 'name': 'Página inicial', 'title': 'Cliente'}]
        raise AssertionError(sql)
    client, _ = _client(monkeypatch, rows)
    response = client.get('/api/v2/reports/flow/site-pages?q=oferta')
    assert response.status_code == 200
    assert response.json['hosts'] == ['www.cliente.com.br'] and response.json['page_count'] == 2
    assert [page['url'] for page in response.json['pages']] == ['https://www.cliente.com.br/oferta', 'https://www.cliente.com.br']


def test_other_domains_are_not_crawled(monkeypatch):
    client, calls = _client(monkeypatch, lambda sql, params: [])
    assert client.get('/api/v2/reports/flow/site-pages?host=interno.local').status_code == 400
    assert client.post('/api/v2/reports/flow/site-pages/refresh', json={'host': 'outro.com'}).status_code == 400
    assert client.post('/api/v2/reports/flow/site-pages/titles', json={'host': 'outro.com', 'paths': ['/a']}).status_code == 400
    assert not any('cadu_reports_site_pages' in sql for sql, _ in calls)


def test_a_client_without_a_site_gets_a_clear_notice(monkeypatch):
    client, _ = _client(monkeypatch, lambda sql, params: [], hosts=())
    body = client.get('/api/v2/reports/flow/site-pages').json
    assert body['hosts'] == [] and body['pages'] == [] and 'Cole a URL' in body['notice']


def test_an_empty_catalog_is_built_from_the_sitemap_with_one_bulk_insert(monkeypatch):
    from datetime import timedelta
    state = {'built': False}

    def rows(sql, params):
        if 'FROM cadu_reports_site_catalogs' in sql:
            return [{'refreshed_at': None, 'page_count': 3, 'truncated': False, 'age': timedelta(0)}] if state['built'] else []
        if 'INSERT INTO cadu_reports_site_catalogs' in sql:
            state['built'] = True
        return []
    monkeypatch.setattr('aicentralv2.cadu_connect.reports_flow._site_sitemap_urls',
                        lambda root, host, limit: (['https://www.cliente.com.br/a', 'https://www.cliente.com.br/b?x=1', 'https://www.cliente.com.br/a'], False))
    client, calls = _client(monkeypatch, rows)
    assert client.get('/api/v2/reports/flow/site-pages').status_code == 200
    inserts = [params for sql, params in calls if 'INSERT INTO cadu_reports_site_pages' in sql]
    assert len(inserts) == 1 and inserts[0][2] == ['/', '/a', '/b']
    assert any('DELETE FROM cadu_reports_site_pages' in sql for sql, _ in calls)


def test_titles_are_fetched_for_a_few_visible_pages_and_cached(monkeypatch):
    stored = []

    def rows(sql, params):
        if 'SELECT path FROM cadu_reports_site_pages' in sql:
            return [{'path': '/oferta'}, {'path': '/contato'}]
        if sql.startswith('UPDATE cadu_reports_site_pages'):
            stored.append(params)
            return []
        if 'SELECT host,path,name,title' in sql:
            return [{'host': 'www.cliente.com.br', 'path': '/oferta', 'name': 'Oferta', 'title': 'Oferta de Outubro'},
                    {'host': 'www.cliente.com.br', 'path': '/contato', 'name': 'Contato', 'title': None}]
        raise AssertionError(sql)
    fetched = []

    def fake_fetch(url, host):
        fetched.append((url, host))
        return {'title': '  Oferta   de Outubro ', 'h1': ''} if url.endswith('/oferta') else None
    monkeypatch.setattr('aicentralv2.cadu_connect.reports_flow._fetch_site_page', fake_fetch)
    client, _ = _client(monkeypatch, rows)
    response = client.post('/api/v2/reports/flow/site-pages/titles', json={'paths': ['/oferta', '/contato', '/ja-visto']})
    assert response.status_code == 200
    assert sorted(fetched) == [('https://www.cliente.com.br/contato', 'www.cliente.com.br'), ('https://www.cliente.com.br/oferta', 'www.cliente.com.br')]
    assert ('Oferta de Outubro', 7, 'www.cliente.com.br', '/oferta') in stored
    assert (None, 7, 'www.cliente.com.br', '/contato') in stored
    assert response.json['pages'][0]['title'] == 'Oferta de Outubro'


def test_titles_reject_bad_requests(monkeypatch):
    client, _ = _client(monkeypatch, lambda sql, params: [])
    for paths in ([], ['sem-barra'], ['/a'] * 9, 'texto', None):
        assert client.post('/api/v2/reports/flow/site-pages/titles', json={'paths': paths}).status_code == 400
