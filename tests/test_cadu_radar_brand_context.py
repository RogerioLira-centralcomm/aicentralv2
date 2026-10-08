from datetime import datetime, timezone
from unittest import mock

from aicentralv2.cadu_radar import brand_context

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def test_disabled_returns_empty_without_touching_the_database():
    with mock.patch.object(brand_context.repository, 'available') as available:
        result = brand_context.brand_radar(1, 31, enabled=False)
    available.assert_not_called()
    assert result['enabled'] is False and result['opportunities'] == [] and result['brandRef'] == 'studio:31'


def test_missing_tables_mean_unavailable():
    with mock.patch.object(brand_context.repository, 'available', return_value=False):
        result = brand_context.brand_radar(1, 31, enabled=True)
    assert result['enabled'] is True and result['available'] is False


def test_collects_opportunities_signals_runs_and_watches_for_the_brand():
    opportunity = {'id': 'o1', 'run_id': 'r1', 'title': 'Apagão e energia', 'thesis': 'Tese', 'quadrant': 'integrada', 'status': 'nova',
                   'editorial_score': 82, 'paid_score': 70, 'created_at': NOW,
                   'score_breakdown': {'window': 'até 15/10', 'why_now': 'Chuvas', 'buzz': [{'assunto': 'Chuva', 'veiculo': 'G1', 'data': '07/10', 'url': 'https://g1.example/x'}, {'assunto': 'sem link'}]}}
    signal = {'id': 's1', 'headline': 'Chuva forte', 'source': 'G1', 'url': 'https://g1.example/x', 'published_at': NOW, 'detected_at': NOW, 'focus': 'energia'}
    run = {'id': 'r1', 'status': 'done', 'focus': 'energia', 'trigger': 'manual', 'created_at': NOW, 'finished_at': NOW}
    watch_rows = [{'id': 'w1', 'name': 'Energia diário', 'status': 'ativo', 'frequency': 1, 'brand_ref': 'studio:31', 'last_run_at': NOW, 'next_run_at': None},
                  {'id': 'w2', 'name': 'Outra marca', 'status': 'ativo', 'frequency': 1, 'brand_ref': 'studio:99'}]
    with mock.patch.object(brand_context.repository, 'available', return_value=True), \
            mock.patch.object(brand_context.repository, 'watches_available', return_value=True), \
            mock.patch.object(brand_context.family, 'rows', side_effect=[[opportunity], [signal], [run]]) as rows, \
            mock.patch.object(brand_context.watches, 'list_watches', return_value=watch_rows):
        result = brand_context.brand_radar(5, 31, enabled=True)
    assert all(call.args[1][1] == 'studio:31' for call in rows.call_args_list)
    assert result['opportunities'][0]['sources'] == [{'title': 'Chuva', 'outlet': 'G1', 'date': '07/10', 'url': 'https://g1.example/x'}]
    assert result['opportunities'][0]['window'] == 'até 15/10'
    assert result['signals'][0]['title'] == 'Chuva forte' and result['runs'][0]['status'] == 'done'
    assert [item['id'] for item in result['watches']] == ['w1']


def test_database_errors_never_break_the_brand_page():
    with mock.patch.object(brand_context.repository, 'available', side_effect=RuntimeError('db down')):
        result = brand_context.brand_radar(1, 31, enabled=True)
    assert result['available'] is False and result['opportunities'] == []
