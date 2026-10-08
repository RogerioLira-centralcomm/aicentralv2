"""ads.txt parsing, programmatic detection and portal filter building (no network, no database)."""
import io
import pytest
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_planner import portal_ads, portals


def test_parse_ads_txt_keeps_valid_records_and_counts_invalid_lines():
    text = """# comment
contact=ads@example.com
google.com, pub-123, DIRECT, f08c47fec0942fa0
rubiconproject.com,456,reseller   # inline comment
not a record
x.com, , DIRECT
"""
    records, invalid = portal_ads.parse_ads_txt(text)
    assert [r['system'] for r in records] == ['google.com', 'rubiconproject.com']
    assert records[1]['relationship'] == 'RESELLER'
    assert invalid == 2


@pytest.mark.parametrize('html,status', [
    ('<script src="https://securepubads.g.doubleclick.net/tag/js/gpt.js"></script>', 'detected'),
    ('<ins class="adsbygoogle"></ins>', 'adsense_native'),
    ('<html><body>sem anúncios</body></html>', 'not_detected'),
])
def test_detect_programmatic(html, status):
    assert portal_ads.detect_programmatic(html)[0] == status


def test_check_ads_txt_rejects_soft_404_html(monkeypatch):
    monkeypatch.setattr(portal_ads, '_fetch', lambda *a, **k: ('ok', 'text/html', '<!DOCTYPE html><html>404</html>', ''))
    assert portal_ads.check_ads_txt('example.com')['status'] == 'invalid'


def test_check_ads_txt_valid_summarises_sellers(monkeypatch):
    body = 'google.com, pub-1, DIRECT\ngoogle.com, pub-2, RESELLER\nopenx.net, 9, RESELLER\n'
    monkeypatch.setattr(portal_ads, '_fetch', lambda *a, **k: ('ok', 'text/plain', body, ''))
    result = portal_ads.check_ads_txt('example.com')
    assert result['status'] == 'valid' and result['records'] == 3 and result['systems_total'] == 2
    assert result['sellers'][0] == {'system': 'google.com', 'direct': 1, 'reseller': 1}


def test_check_portal_marks_ads_txt_declared_when_tags_are_script_loaded(monkeypatch):
    monkeypatch.setattr(portal_ads, '_public_host', lambda host: True)
    monkeypatch.setattr(portal_ads, 'check_ads_txt', lambda *a, **k: {'status': 'valid', 'records': 5, 'sellers': []})
    monkeypatch.setattr(portal_ads, 'check_home', lambda *a, **k: {'status': 'ok', 'programmatic_status': 'not_detected', 'signals': []})
    assert portal_ads.check_portal('example.com')['home']['programmatic_status'] == 'ads_txt_declared'


def test_filters_build_parameterised_clause():
    clause, params = portals._filters('g1', 'Esportes, Tecnologia e games', 'regional', 'sp,rj', 'valid', 'any')
    assert 'ANY' in clause and '%s' in clause and 'g1' not in clause
    assert ['Esportes', 'Tecnologia e games'] in params and ['SP', 'RJ'] in params


@pytest.mark.parametrize('kwargs', [{'scope': 'x'}, {'uf': 'S1'}, {'ads_txt': 'x'}, {'programmatic': 'x'}])
def test_filters_reject_unknown_values(kwargs):
    base = dict(query='', category='', scope='', uf='', ads_txt='', programmatic='')
    with pytest.raises(BadRequest):
        portals._filters(**{**base, **kwargs})


HEADER = 'name,domain,category,description,public_attributes,scope,uf,monthly_visits,metrics_source_url,metrics_checked_at\n'


def test_import_requires_approval_unless_pending_allowed():
    row = 'Foo,foo.com.br,Notícias,,"[{""atributo"":""status_curadoria"",""valor"":""pendente""}]",regional,PR,,,\n'
    with pytest.raises(BadRequest):
        portals.import_curated_csv(io.StringIO(HEADER + row), dry_run=True)
    assert portals.import_curated_csv(io.StringIO(HEADER + row), dry_run=True, allow_pending=True)['rows'] == 1


def test_import_metrics_need_a_source_and_pending_mode_skips_bad_rows():
    bad = 'Foo,foo.com.br,Notícias,,[],regional,PR,1000,,\n'
    good = 'Bar,bar.com.br,Notícias,,[],nacional_premium,,,,\n'
    result = portals.import_curated_csv(io.StringIO(HEADER + bad + good), dry_run=True, allow_pending=True)
    assert result['rows'] == 1 and 'métricas exigem' in result['skipped'][0]


def test_check_portal_never_raises_so_one_host_cannot_abort_a_batch(monkeypatch):
    import http.client
    monkeypatch.setattr(portal_ads, '_check_portal', lambda *a: (_ for _ in ()).throw(http.client.IncompleteRead(b'')))
    assert portal_ads.check_portal('example.com') == {'domain': 'example.com', 'status': 'error'}


@pytest.mark.parametrize('status,transient', [('dns_failed', True), ('unreachable', True), ('http_503', True), ('error', True),
                                              ('missing', False), ('valid', False), ('http_403', False)])
def test_transient_failures_are_distinguished_from_definitive_results(status, transient):
    assert portal_ads._transient(status) is transient


def test_bulk_add_only_accepts_portals():
    from aicentralv2.cadu_planner import selections
    with pytest.raises(BadRequest):
        selections.add_many(1, 2, {'kind': 'canais', 'resource_ids': [1]})


def test_import_rejects_domain_that_does_not_resolve(monkeypatch):
    import io
    from aicentralv2.cadu_planner import portal_ads, portals
    monkeypatch.setattr(portal_ads, 'domain_resolves', lambda host: host != 'morto.example')
    header = 'name,domain,category,public_attributes\n'
    rows = ('Vivo,vivo.example,Notícias,"[{""atributo"":""status_curadoria"",""valor"":""aprovado""}]"\n'
            'Morto,morto.example,Notícias,"[{""atributo"":""status_curadoria"",""valor"":""aprovado""}]"\n')
    result = portals.import_curated_csv(io.StringIO(header + rows), dry_run=True, allow_pending=True, check_dns=True)
    assert result['rows'] == 1
    assert any('DNS' in reason for reason in result['skipped'])
