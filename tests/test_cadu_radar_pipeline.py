"""Pipeline do Radar sem rede nem banco: etapas, notas e verificação."""
import json

import pytest
from flask import Flask

from aicentralv2.cadu_radar import pipeline, scoring


@pytest.fixture
def runner(monkeypatch):
    run = pipeline.Runner('run-1', 7, 9, 'volta às aulas', None, None)
    monkeypatch.setattr(run, '_save_steps', lambda: None)
    return run


def reply(payload, tokens=100):
    return {'message': {'content': json.dumps(payload)}, 'cadu_charge': {'tokens_cobrados': tokens}}, tokens


PACKET_SOURCES = [{'title': 'Matrículas crescem 12%', 'url': 'https://exemplo.com/a', 'published_at': '2026-09-20', 'content': 'texto'}]


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
    items, packet = runner._judge({'facts': []}, 'tema', {'text': 'achados'}, PACKET_SOURCES)
    item = items[0]
    assert item['editorial'].penalties == {'saturacao': 15}  # teto da penalidade, não o valor pedido
    assert item['editorial'].score == 75 and item['paid'].score == 70
    assert item['quadrant'] == 'integrada'
    assert item['signals'][0]['url'] == 'https://exemplo.com/a'
    assert item['places'][0].score > 0
    assert runner._step('judge')['tokens'] == 1200 and runner._step('judge')['status'] == 'done'
    assert packet[0]['id'] == 'S1'


def test_verify_drops_contested_opportunities_to_ignore(monkeypatch, runner):
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: reply({'opportunities': [opportunity(), opportunity()]}))
    items, packet = runner._judge({'facts': []}, 'tema', {'text': ''}, PACKET_SOURCES)
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: reply({'results': [
        {'index': 0, 'verdict': 'confirmado', 'corroborating_sources': 3},
        {'index': 1, 'verdict': 'contestado', 'notes': 'Dado de 2023.'}]}, 300))
    items = runner._verify(items, packet)
    assert items[0]['quadrant'] == 'integrada' and items[0]['verification']['verdict'] == 'confirmado'
    assert items[1]['quadrant'] == 'ignorar' and items[1]['editorial'].penalties['baixa_confianca'] == 20
    assert runner._step('verify')['detail'] == '1 confirmadas, 1 contestadas'


def test_one_failed_discovery_flow_does_not_stop_the_other(monkeypatch, runner):
    app = Flask(__name__)
    calls = []
    monkeypatch.setattr(runner, '_context', lambda: {'brand': None, 'sector': None, 'project': None, 'facts': []})
    monkeypatch.setattr(runner, '_discover', lambda ctx, topic: (_ for _ in ()).throw(RuntimeError('perplexity fora')))
    monkeypatch.setattr(runner, '_search', lambda topic: PACKET_SOURCES)
    monkeypatch.setattr(runner, '_extract', lambda discovered, sources: calls.append(('extract', discovered, sources)) or sources)
    monkeypatch.setattr(runner, '_judge', lambda *a: ([], []))
    monkeypatch.setattr(runner, '_verify', lambda items, packet: items)
    monkeypatch.setattr(runner, '_save', lambda items: calls.append(('save', items)))
    monkeypatch.setattr(pipeline, '_finish', lambda run_id, status, error=None: calls.append(('finish', status)))
    with app.app_context():
        runner.execute()
    assert calls[0] == ('extract', {'text': '', 'urls': []}, PACKET_SOURCES)
    assert runner._step('discover')['status'] == 'failed'
    assert calls[-1] == ('finish', 'done')


def test_start_run_refuses_when_disabled():
    app = Flask(__name__)
    app.config['CADU_RADAR_ENABLED'] = False
    with app.app_context(), pytest.raises(pipeline.RadarDisabled):
        pipeline.start_run(1, 2, focus='tema')


def test_steps_declare_the_parallel_pair_first():
    steps = pipeline._initial_steps()
    assert [step['key'] for step in steps if step['parallel']] == ['discover', 'search']
    assert all(step['status'] == 'pending' and step['tokens'] == 0 for step in steps)
