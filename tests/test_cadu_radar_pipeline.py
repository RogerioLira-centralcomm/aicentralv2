"""Pipeline do Radar (fluxo F1) sem rede nem banco: etapas, notas, checagem de realidade e selo."""
import json

import pytest
from flask import Flask

from aicentralv2.cadu_radar import pipeline, scoring


@pytest.fixture
def runner(monkeypatch):
    run = pipeline.Runner('run-1', 7, 9, 'volta às aulas', None, None, {'recency_days': 30})
    monkeypatch.setattr(run, '_save_steps', lambda: None)
    return run


def reply(payload, tokens=100):
    return {'message': {'content': json.dumps(payload)}, 'cadu_charge': {'tokens_cobrados': tokens}}, tokens


PACKET = [{'id': 'S1', 'title': 'Matrículas crescem 12%', 'url': 'https://g1.globo.com/a', 'published_at': '2026-09-20', 'excerpt': 'texto'}]


def opportunity(editorial=90, paid=85):
    return {'title': 'Crédito estudantil na volta às aulas', 'thesis': 'Janela aberta.',
            'signals': [{'source_id': 'S1', 'headline': 'Matrículas crescem', 'source_type': 'news'}],
            'editorial': {key: editorial for key in scoring.EDITORIAL_WEIGHTS},
            'paid': {**{key: paid for key in scoring.PAID_WEIGHTS}, 'inventado': 100},
            'penalties': {'saturacao': 99},
            'places': [{'place': 'São Paulo', 'interest': 80, 'audience': 70, 'context': 60, 'reason': 'maior base'}],
            'channels': ['Social', 'Portais'], 'window': 'até 15/02'}


def test_judge_scores_in_python_and_caps_penalties(monkeypatch, runner):
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: reply({'opportunities': [opportunity()]}, 1200))
    items = runner._judge({'facts': []}, 'tema', 'achados', PACKET)
    item = items[0]
    assert item['editorial'].penalties == {'saturacao': 15}  # teto da penalidade, não o valor pedido
    assert item['editorial'].score == 75 and item['paid'].score == 70
    assert item['quadrant'] == 'integrada'
    assert item['signals'][0]['url'] == 'https://g1.globo.com/a'
    assert item['places'][0].score > 0
    assert runner._step('judge')['tokens'] == 1200 and runner._step('judge')['status'] == 'done'


def test_judge_survives_json_cut_at_the_token_limit(monkeypatch, runner):
    full = json.dumps({'opportunities': [opportunity(), opportunity()]})
    cut = full[:full.rindex('"title"') + 20]  # a segunda oportunidade veio cortada
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: ({'message': {'content': cut}, 'cadu_charge': {'tokens_cobrados': 5}}, 5))
    assert len(runner._judge({'facts': []}, 'tema', '', PACKET)) == 1


def test_reality_check_drops_contested_opportunities_to_ignore(monkeypatch, runner):
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: reply({'opportunities': [opportunity(), opportunity()]}))
    items = runner._judge({'facts': []}, 'tema', '', PACKET)
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: reply({'results': [
        {'index': 0, 'verdict': 'confirmado', 'other_sources': ['https://www.estadao.com.br/x']},
        {'index': 1, 'verdict': 'contestado', 'contradiction': 'Dado de 2023.'}]}, 300))
    items = runner._verify(items)
    assert items[0]['quadrant'] == 'integrada' and items[0]['verification']['verdict'] == 'confirmado'
    assert items[1]['quadrant'] == 'ignorar' and items[1]['editorial'].penalties['baixa_confianca'] == 20
    assert runner._step('verify')['detail'] == '1 confirmadas, 1 contestadas'


def test_unverified_gets_a_smaller_penalty_than_contested(monkeypatch, runner):
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: reply({'opportunities': [opportunity()]}))
    items = runner._judge({'facts': []}, 'tema', '', PACKET)
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: reply({'results': []}))  # o checador não respondeu sobre o índice 0
    items = runner._verify(items)
    assert items[0]['verification']['verdict'] == 'nao_verificado'
    assert items[0]['editorial'].penalties['baixa_confianca'] == 12


def test_confidence_seal_uses_source_tiers_and_ignores_broken_links(monkeypatch, runner):
    monkeypatch.setattr(pipeline, 'check_url', lambda url: 'quebrado' if 'quebrado' in url else 'ok')
    strong = {'quadrant': 'integrada', 'verification': {'verdict': 'confirmado', 'other_sources': []},
              'signals': [{'url': 'https://g1.globo.com/a', 'published_at': '2026-10-01'},
                          {'url': 'https://www.estadao.com.br/b', 'published_at': '2026-10-02'}]}
    weak = {'quadrant': 'integrada', 'verification': {'verdict': 'confirmado', 'other_sources': []},
            'signals': [{'url': 'https://blog.qualquer.com/a'}, {'url': 'https://g1.globo.com/quebrado'}]}
    runner._annotate([strong, weak], {'site': ''})
    assert strong['verification']['confidence'] == 'alta' and strong['quadrant'] == 'integrada'
    # Fonte C sozinha + link A/B quebrado não sustentam nada: baixa e fora dos alertas.
    assert weak['verification']['confidence'] == 'baixa' and weak['quadrant'] == 'ignorar'
    assert weak['signals'][1]['url_status'] == 'quebrado'


def test_one_failed_search_does_not_stop_the_others(monkeypatch, runner):
    app = Flask(__name__)
    calls = []
    monkeypatch.setattr(runner, '_context', lambda: {'brand': None, 'sector': None, 'project': None, 'site': '', 'facts': []})

    def discover(stage, values):
        if stage == 'discover_press':
            raise RuntimeError('perplexity fora')
        return {'text': stage, 'facts': [{'fato': 'a', 'url': 'https://g1.globo.com/a'}], 'cited': []}

    monkeypatch.setattr(runner, '_discover', discover)
    monkeypatch.setattr(runner, '_extract', lambda found, domains: calls.append(sorted(found)) or (PACKET, ''))
    monkeypatch.setattr(runner, '_judge', lambda *a: [])
    monkeypatch.setattr(runner, '_verify', lambda items: items)
    monkeypatch.setattr(runner, '_annotate', lambda items, ctx: None)
    monkeypatch.setattr(runner, '_save', lambda items: calls.append('save'))
    monkeypatch.setattr(pipeline, '_finish', lambda run_id, status, error=None: calls.append(status))
    with app.app_context():
        runner.execute()
    assert runner._step('discover_press')['status'] == 'failed'
    assert calls[0] == ['discover_open', 'discover_press', 'discover_trends']
    assert calls[-1] == 'done'


def test_disabled_sources_are_skipped_and_not_called(monkeypatch):
    run = pipeline.Runner('run-2', 7, 9, 'tema', None, None, {'sources': {'press': False, 'trends': True}})
    monkeypatch.setattr(run, '_save_steps', lambda: None)
    assert run._step('discover_press')['status'] == 'skipped' and run._step('discover_trends')['status'] == 'pending'
    called = []
    monkeypatch.setattr(run, '_context', lambda: {'brand': None, 'sector': None, 'project': None, 'site': '', 'facts': []})
    monkeypatch.setattr(run, '_discover', lambda stage, values: called.append(stage) or {'text': '', 'facts': [], 'cited': [{'url': 'u'}]})
    monkeypatch.setattr(run, '_extract', lambda found, domains: ([], ''))
    monkeypatch.setattr(run, '_judge', lambda *a: [])
    monkeypatch.setattr(run, '_verify', lambda items: items)
    monkeypatch.setattr(run, '_annotate', lambda items, ctx: None)
    monkeypatch.setattr(run, '_save', lambda items: None)
    monkeypatch.setattr(pipeline, '_finish', lambda *a, **k: None)
    with Flask(__name__).app_context():
        run.execute()
    assert sorted(called) == ['discover_open', 'discover_trends']


def test_start_run_refuses_when_disabled():
    app = Flask(__name__)
    app.config['CADU_RADAR_ENABLED'] = False
    with app.app_context(), pytest.raises(pipeline.RadarDisabled):
        pipeline.start_run(1, 2, focus='tema')


def test_steps_declare_the_three_parallel_searches_first():
    steps = pipeline._initial_steps()
    assert [step['key'] for step in steps if step['parallel']] == ['discover_open', 'discover_press', 'discover_trends']
    assert all(step['status'] == 'pending' and step['tokens'] == 0 for step in steps)


def test_params_are_cleaned_to_what_the_search_understands():
    cleaned = pipeline.clean_params({'lenses': ['Reputação', 'inventada', 'Regulação', 'Concorrência', 'Sazonalidade e datas'],
                                     'places': '  BH   e   SP ', 'recency_days': '7', 'objective': 'x', 'sources': {'press': False}})
    assert cleaned['lenses'] == ['Reputação', 'Regulação', 'Concorrência']  # até 3, só as conhecidas
    assert cleaned['places'] == 'BH e SP' and cleaned['recency_days'] == 7 and cleaned['objective'] == 'ambos'
    assert cleaned['sources'] == {'press': False, 'trends': True}
    assert pipeline.clean_params(None)['recency_days'] == 30 and pipeline.clean_params({'recency_days': 'abc'})['recency_days'] == 30
    assert pipeline.clean_params({'recency_days': 15})['recency_days'] == 30


def test_estimate_is_priced_in_usd_not_fixed_tokens(monkeypatch):
    from aicentralv2 import cadu_credit_connector
    from decimal import Decimal
    monkeypatch.setattr(cadu_credit_connector.CaduCreditConnector, '_commercial_token_price_usd', lambda self, client: Decimal('0.0002'))
    assert pipeline.estimate_tokens(1) == 750  # US$ 0,15 a US$ 0,0002 por token
    monkeypatch.setattr(cadu_credit_connector.CaduCreditConnector, '_commercial_token_price_usd', lambda self, client: Decimal('0.0001'))
    assert pipeline.estimate_tokens(1) == 1500
