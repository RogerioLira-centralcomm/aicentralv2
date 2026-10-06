"""Pipeline do Radar (v1.5: buzz e ângulos) sem rede nem banco."""
import json
from datetime import timedelta

import pytest
from flask import Flask

from aicentralv2.cadu_radar import db as radar_db, pipeline


@pytest.fixture
def runner(monkeypatch):
    run = pipeline.Runner('run-1', 7, 9, 'consumo consciente', None, None, {'recency_days': 30, 'places': 'Minas Gerais'})
    monkeypatch.setattr(run, '_save_steps', lambda: None)
    monkeypatch.setattr(run, '_notify_finished', lambda brand: None)
    return run


CTX = {'brand': 'Cemig', 'sector': 'Energia', 'project': None, 'site': 'https://www.cemig.com.br', 'facts': []}


def day(runner, days_ago):
    return (runner.today - timedelta(days=days_ago)).isoformat()


def buzz_item(runner, subject, url, days_ago=3, **extra):
    return {'assunto': subject, 'por_que_em_alta': 'muita gente comentando', 'data': day(runner, days_ago) if days_ago is not None else '',
            'local': 'Brasil', 'veiculo': 'g1', 'url': url, **extra}


def test_buzz_keeps_only_recent_dated_linked_items(monkeypatch, runner):
    seen = {}
    items = [buzz_item(runner, 'Bandeira verde', 'https://g1.globo.com/a'),
             buzz_item(runner, 'Antigo', 'https://g1.globo.com/b', days_ago=800),        # 2024: fora da janela
             buzz_item(runner, 'Sem data', 'https://g1.globo.com/c', days_ago=None),     # página sem data costuma ser velha
             buzz_item(runner, 'Do futuro', 'https://g1.globo.com/d', days_ago=-20),
             buzz_item(runner, 'Sem link', '', days_ago=1),
             buzz_item(runner, 'Repetido', 'https://g1.globo.com/a/', days_ago=2),       # mesma URL com barra no fim
             buzz_item(runner, 'Outro', 'https://www.estadao.com.br/e', days_ago=10)]

    def ai(stage, model, messages, max_tokens, json_mode=True, web=False):
        seen['prompt'] = messages[0]['content']
        return json.dumps({'buzz': items}), 120

    monkeypatch.setattr(runner, '_ai', ai)
    kept = runner._buzz(CTX, 'tema')
    assert [item['assunto'] for item in kept] == ['Bandeira verde', 'Outro']
    assert [item['id'] for item in kept] == ['B1', 'B2']
    assert f'Hoje é {runner.today.isoformat()}' in seen['prompt']  # o modelo recebe a data real, não a do treino
    assert runner._step('buzz')['tokens'] == 120 and '7 achados, 2 dentro da janela' in runner._step('buzz')['detail']


def test_buzz_survives_json_cut_at_the_token_limit(monkeypatch, runner):
    full = json.dumps({'buzz': [buzz_item(runner, 'Um', 'https://g1.globo.com/a'), buzz_item(runner, 'Dois', 'https://g1.globo.com/b')]})
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: (full[:full.rindex('"assunto"') + 12], 5))
    assert [item['assunto'] for item in runner._buzz(CTX, 'tema')] == ['Um']


def test_check_drops_broken_links_and_labels_source_tiers(monkeypatch, runner):
    monkeypatch.setattr(pipeline, 'check_url', lambda url: 'quebrado' if 'quebrado' in url else 'ok')
    buzz = [{'id': 'B1', 'url': 'https://g1.globo.com/quebrado', 'assunto': 'a'},
            {'id': 'B2', 'url': 'https://blog.qualquer.com/post', 'assunto': 'b'},
            {'id': 'B3', 'url': 'https://www.gov.br/aneel/x', 'assunto': 'c'}]
    alive = runner._check(buzz, CTX)
    assert [(item['id'], item['tier']) for item in alive] == [('B1', 'C'), ('B2', 'A')]  # reindexado; blog = C, gov.br = A
    assert runner._step('check')['detail'] == '2 com link aberto, 1 descartados'


def test_angles_must_rest_on_a_listed_buzz(monkeypatch, runner):
    buzz = [{'id': 'B1', 'assunto': 'Bandeira verde', 'por_que': 'x', 'data': day(runner, 2), 'veiculo': 'g1', 'local': 'Brasil'}]
    angles = [{'titulo': 'Conta verde não é conta barata', 'gancho': 'Explicar a fatura.', 'por_que_agora': 'bandeira verde em outubro',
               'formatos': ['carrossel'], 'canais': ['Instagram'], 'janela': 'até novembro', 'buzz': ['B1', 'B9']},
              {'titulo': 'Inventado', 'gancho': 'x', 'buzz': ['B9']},      # só aponta para buzz que não existe
              {'titulo': 'Sem apoio', 'gancho': 'x', 'buzz': []},
              {'gancho': 'sem título', 'buzz': ['B1']}]
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: (json.dumps({'angulos': angles}), 300))
    result = runner._angles(CTX, 'tema', buzz)
    assert [item['titulo'] for item in result] == ['Conta verde não é conta barata']
    assert result[0]['buzz'] == ['B1']  # o id inexistente sai
    assert runner._step('angles')['detail'] == '1 ângulos'


def test_angles_are_capped_at_five(monkeypatch, runner):
    buzz = [{'id': 'B1', 'assunto': 'a', 'por_que': '', 'data': day(runner, 1), 'veiculo': 'g1', 'local': ''}]
    many = [{'titulo': f'Ângulo {index}', 'gancho': 'g', 'buzz': ['B1']} for index in range(9)]
    monkeypatch.setattr(runner, '_ai', lambda *a, **k: (json.dumps({'angulos': many}), 1))
    assert len(runner._angles(CTX, 'tema', buzz)) == pipeline.MAX_ANGLES


def test_execute_without_buzz_skips_angles_and_finishes(monkeypatch, runner):
    calls = []
    monkeypatch.setattr(runner, '_context', lambda: CTX)
    monkeypatch.setattr(runner, '_buzz', lambda ctx, topic: [])
    monkeypatch.setattr(runner, '_angles', lambda *a: calls.append('angles') or [])
    monkeypatch.setattr(runner, '_save', lambda buzz, angles: calls.append(('save', buzz, angles)))
    monkeypatch.setattr(pipeline, 'check_url', lambda url: 'ok')
    monkeypatch.setattr(pipeline, '_finish', lambda run_id, status, error=None: calls.append(status))
    runner.execute()
    assert calls == [('save', [], []), 'done'] and runner._step('angles')['status'] == 'skipped'


def test_execute_runs_buzz_check_angles_save_in_order(monkeypatch, runner):
    order = []
    monkeypatch.setattr(runner, '_context', lambda: CTX)
    monkeypatch.setattr(runner, '_buzz', lambda ctx, topic: order.append('buzz') or [{'id': 'B1', 'url': 'https://g1.globo.com/a'}])
    monkeypatch.setattr(runner, '_check', lambda buzz, ctx: order.append('check') or buzz)
    monkeypatch.setattr(runner, '_angles', lambda ctx, topic, buzz: order.append('angles') or ['a'])
    monkeypatch.setattr(runner, '_save', lambda buzz, angles: order.append('save'))
    monkeypatch.setattr(pipeline, '_finish', lambda run_id, status, error=None: order.append(status))
    runner.execute()
    assert order == ['buzz', 'check', 'angles', 'save', 'done']


def test_start_run_refuses_when_disabled():
    app = Flask(__name__)
    app.config['CADU_RADAR_ENABLED'] = False
    with app.app_context(), pytest.raises(pipeline.RadarDisabled):
        pipeline.start_run(1, 2, focus='tema')


def test_steps_are_four_and_none_is_parallel():
    steps = pipeline._initial_steps()
    assert [step['key'] for step in steps] == ['buzz', 'check', 'angles', 'save']
    assert not any(step['parallel'] for step in steps)
    assert all(step['status'] == 'pending' and step['tokens'] == 0 for step in steps)


def test_params_keep_only_place_and_a_known_window():
    cleaned = pipeline.clean_params({'places': '  BH   e   SP ', 'recency_days': '7', 'lenses': ['x'], 'sources': {'press': False}})
    assert cleaned == {'places': 'BH e SP', 'recency_days': 7}
    assert pipeline.clean_params(None) == {'places': '', 'recency_days': 30}
    assert pipeline.clean_params({'recency_days': 'abc'})['recency_days'] == 30
    assert pipeline.clean_params({'recency_days': 15})['recency_days'] == 30


def test_estimate_is_priced_in_usd_not_fixed_tokens(monkeypatch):
    from decimal import Decimal

    from aicentralv2 import cadu_credit_connector
    monkeypatch.setattr(cadu_credit_connector.CaduCreditConnector, '_commercial_token_price_usd', lambda self, client: Decimal('0.0002'))
    assert pipeline.estimate_tokens(1) == 500  # US$ 0,10 a US$ 0,0002 por token
    monkeypatch.setattr(cadu_credit_connector.CaduCreditConnector, '_commercial_token_price_usd', lambda self, client: Decimal('0.0001'))
    assert pipeline.estimate_tokens(1) == 1000


class SqlSpy:
    """Registra o SQL que o pipeline manda; o Postgres real recusa `jsonb || json`, então o cast é obrigatório."""
    def __init__(self):
        self.statements = []

    def cursor(self):
        spy = self

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                spy.statements.append(' '.join(sql.split()))

            def fetchone(self):
                return None

        return Cursor()

    def commit(self):
        pass

    def rollback(self):
        pass


def test_step_progress_concatenates_cost_as_jsonb(monkeypatch):
    spy = SqlSpy()
    monkeypatch.setattr(pipeline, '_db', lambda: spy)
    pipeline.Runner('run-3', 7, 9, 'tema', None, None)._save_steps()
    sql, = [item for item in spy.statements if item.startswith('UPDATE cadu_radar_runs SET steps')]
    assert 'cost = cost || %s::jsonb' in sql and 'lease_until' in sql


def test_save_writes_buzz_as_signals_and_angles_as_opportunities(monkeypatch, runner):
    spy = SqlSpy()
    monkeypatch.setattr(radar_db, 'get_db', lambda: spy)
    monkeypatch.setattr(pipeline, '_db', lambda: spy)
    buzz = [{'id': 'B1', 'assunto': 'Bandeira verde', 'por_que': 'x', 'data': day(runner, 2), 'veiculo': 'g1', 'url': 'https://g1.globo.com/a',
             'tier': 'A', 'domain': 'g1.globo.com', 'url_status': 'ok', 'local': ''}]
    angles = [{'titulo': 'Ângulo', 'gancho': 'g', 'por_que_agora': 'p', 'formatos': [], 'canais': [], 'janela': 'j', 'buzz': ['B1']}]
    runner._save(buzz, angles)
    assert sum(item.startswith('INSERT INTO cadu_radar_signals') for item in spy.statements) == 1
    assert sum(item.startswith('INSERT INTO cadu_radar_opportunities') for item in spy.statements) == 1
    assert not any('editorial_score' in item for item in spy.statements)  # sem notas: o Radar não pontua mais


def test_dead_run_expiry_also_covers_runs_without_a_lease(monkeypatch):
    spy = SqlSpy()
    monkeypatch.setattr(radar_db, 'get_db', lambda: spy)
    pipeline._expire_dead_runs(5)
    sql, = spy.statements
    # Runs do pipeline antigo não têm lease: contam 20 minutos desde a criação em vez de travar a marca para sempre.
    assert "COALESCE(lease_until, created_at + INTERVAL '20 minutes') < NOW()" in sql


def test_each_call_authorizes_its_own_usd_estimate_not_a_fixed_floor(monkeypatch, runner):
    """A reserva da busca é em US$; um piso fixo por chamada faria o run falhar com saldo entre a reserva e o piso."""
    from decimal import Decimal

    from aicentralv2 import cadu_credit_connector
    from aicentralv2.services import cadu_ai_connector
    seen = {}

    class FakeAI:
        def complete(self, messages, **kwargs):
            seen['estimated'] = kwargs['estimated_tokens']
            return {'message': {'content': '{}'}, 'cadu_charge': {'tokens_cobrados': 1}}

    monkeypatch.setattr(cadu_ai_connector, 'CaduAIConnector', FakeAI)
    monkeypatch.setattr(cadu_credit_connector.CaduCreditConnector, '_commercial_token_price_usd', lambda self, client: Decimal('0.0002'))
    runner._ai('buzz', 'perplexity/sonar-pro', [{'role': 'user', 'content': 'x'}], 100)
    assert seen['estimated'] == 250 < pipeline.estimate_tokens(7)  # US$ 0,05 a US$ 0,0002; abaixo da reserva total


def test_execute_sends_the_completion_email_only_after_the_run_is_marked_done(monkeypatch):
    run = pipeline.Runner('run-9', 7, 9, 'tema', None, None, {})
    monkeypatch.setattr(run, '_save_steps', lambda: None)
    order = []
    monkeypatch.setattr(run, '_context', lambda: CTX)
    monkeypatch.setattr(run, '_buzz', lambda ctx, topic: [])
    monkeypatch.setattr(run, '_save', lambda buzz, angles: order.append('save'))
    monkeypatch.setattr(run, '_notify_finished', lambda brand: order.append(('email', brand)))
    monkeypatch.setattr(pipeline, '_finish', lambda run_id, status, error=None: order.append(status))
    run.execute()
    assert order == ['save', 'done', ('email', 'Cemig')]  # o resultado já está salvo e a busca concluída quando o e-mail sai


def test_a_failing_completion_email_never_breaks_the_run(monkeypatch):
    run = pipeline.Runner('run-10', 7, 9, 'tema', None, None, {})

    def boom(*args, **kwargs):
        raise RuntimeError('banco fora')

    monkeypatch.setattr(pipeline, 'get_run', boom)
    run._notify_finished('Cemig')  # não levanta
