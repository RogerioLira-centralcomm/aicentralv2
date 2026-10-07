"""Link Tester history inside the tool: both sources, authors, and PHP prints that never expose the provider key."""
import datetime
from unittest import mock

from aicentralv2.cadu_connect import reports_link_history as history

NOW = datetime.datetime(2026, 10, 7, 12, 0, tzinfo=datetime.timezone.utc)
KEY_URL = 'https://api.screenshotone.com/take?access_key=SECRETKEY&url=https%3A%2F%2Fa.com'


def fake_rows(tables):
    def rows(sql, params=()):
        if 'to_regclass' in sql:
            return [{'ready': params[0].removeprefix('public.') in tables}]
        if 'FROM cadu_reports_link_test_runs' in sql and 'r.id = %s' not in sql:
            return [dict(row) for row in tables.get('cadu_reports_link_test_runs', [])]
        if 'FROM cadu_link_tests' in sql and 't.id = %s' in sql:
            return [dict(row) for row in tables.get('cadu_link_tests', []) if row['id'] == params[0]]
        if 'FROM cadu_link_tests' in sql:
            return [dict(row) for row in tables.get('cadu_link_tests', [])]
        return []
    return rows


LEGACY = {'id': 284, 'uuid': 'u', 'tipo_analise': 'completo', 'url_testada': 'https://www.cemig.com.br/', 'url_final': 'https://www.cemig.com.br/',
          'dominio': 'www.cemig.com.br', 'score_total': 77, 'ssl_valido': True, 'ssl_expira_em': None, 'ssl_emissor': None, 'tempo_resposta_ms': 211,
          'redirects_count': 0, 'screenshot_url': KEY_URL, 'created_at': NOW - datetime.timedelta(days=60), 'author': 'João',
          'analise_completa': {'screenshot': {'desktop': {'url': KEY_URL}, 'mobile': {'url': KEY_URL}}, 'readiness_label': 'Bom', 'meta': {'og_image': KEY_URL}}}
REPORTS = {'id': 'aaaaaaaa-0000-0000-0000-000000000001', 'source': 'reports', 'mode': 'media', 'original_url': 'https://cemig.com.br/', 'final_url': 'https://cemig.com.br/',
           'score': 54, 'status_label': 'Medição parcial', 'public_token': 't', 'created_at': NOW, 'media_campaign_id': None, 'report_workspace_id': None,
           'campaign_name': None, 'author': 'Apolo', 'has_screenshot': True}


def test_history_merges_both_sources_newest_first_with_authors():
    with mock.patch.object(history, '_rows', side_effect=fake_rows({'cadu_reports_link_test_runs': [REPORTS], 'cadu_link_tests': [LEGACY]})):
        runs = history.history(174)
    assert [run['id'] for run in runs] == [REPORTS['id'], 'php-284']
    assert [run['author'] for run in runs] == ['Apolo', 'João']
    assert runs[1]['source'] == 'cadu_php' and runs[1]['public_token'] is None
    assert {run['domain'] for run in runs} == {'cemig.com.br'}


def test_legacy_detail_never_exposes_the_screenshotone_key():
    with mock.patch.object(history, '_rows', side_effect=fake_rows({'cadu_link_tests': [LEGACY]})):
        run = history.detail(174, 'php-284')
    assert 'SECRETKEY' not in str(run)
    assert run['screenshots']['desktop'] == '/connect/api/v2/reports/link-tests/php-284/screenshot?device=desktop'
    assert run['analysis']['meta']['og_image'] is None


def test_unknown_ids_are_rejected_without_querying_other_clients():
    with mock.patch.object(history, '_rows', side_effect=fake_rows({'cadu_link_tests': [LEGACY]})):
        assert history.detail(174, 'php-abc') is None
        assert history.detail(174, 'not-a-uuid') is None
        assert history.detail(174, 'php-999') is None


def test_legacy_print_download_only_from_the_provider_host(tmp_path):
    from flask import Flask
    app = Flask('t', instance_path=str(tmp_path))
    hostile = {**LEGACY, 'analise_completa': {'screenshot': {'desktop': {'url': 'http://169.254.169.254/latest/meta-data'}}}, 'screenshot_url': None}
    with app.app_context(), mock.patch.object(history, '_rows', side_effect=fake_rows({'cadu_link_tests': [hostile]})), \
            mock.patch('aicentralv2.cadu_connect.reports_link_screenshots._download') as download:
        assert history.legacy_screenshot(174, 284, 'desktop') is None
        download.assert_not_called()
