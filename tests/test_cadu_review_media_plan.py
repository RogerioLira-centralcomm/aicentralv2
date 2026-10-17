import io

import pytest
from openpyxl import Workbook

from aicentralv2.cadu_review import media_plan, media_plan_parser as parser
from aicentralv2.services.typesafe_service import TypeSafeError


def _xlsx(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Plano'
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


PLAN_ROWS = [
    ['Cliente:', 'Marca Exemplo'],
    ['Objetivo:', 'Awareness da nova linha'],
    ['Período:', '01/11/2026 a 30/11/2026'],
    [],
    ['Veículo', 'Formato', 'Modelo de compra', 'CPM (R$)', 'Impressões', 'Investimento líquido', 'Início', 'Fim'],
    ['Meta', 'Reels', 'CPM', 12, 1_000_000, 12_000, '01/11/2026', '30/11/2026'],
    ['YouTube', 'Pre-roll', 'CPM', 25, 400_000, 10_000, '01/11/2026', '30/11/2026'],   # conta: daria 10.000 ✓
    ['Programática DV360', 'Display', 'CPM', 90, 100_000, 5_000, '05/11/2026', '20/12/2026'],  # conta errada, CPM alto, fora do período
    ['Total', '', '', '', '', 30_000],
]


def _choice(choice, options):
    rest = (1 - 0.8) / (len(options) - 1)
    return {'type': 'choice', 'choice': choice, 'confidence': 0.7,
            'probabilities': {option: (0.8 if option == choice else rest) for option in options}}


def fake_typesafe(state, questions):
    picks = {'canais_objetivo': 'adequado', 'canais_publico': 'sem_contexto', 'funil': 'lacunas',
             'mensuracao': 'ausente', 'riscos': 'baixo', 'lacunas': 'lacunas_menores', 'parecer': 'aprovar'}
    assert state['lines'] and {'canal', 'investimento'} <= set(state['lines'][0])
    assert all('untrusted' in question['instructions']['question'] for question in questions.values())
    return {'model': 'jev-test', 'usage': {'input_tokens': 3000, 'output_tokens': 200},
            'answers': {key: _choice(picks[key], list(question['criteria'])) for key, question in questions.items()}}


def test_number_handles_brazilian_and_american_formats():
    assert parser.number('R$ 1.234,56') == 1234.56
    assert parser.number('1,234.56') == 1234.56
    assert parser.number('12.000') == 12000
    assert parser.number('15%') == 15
    assert parser.number('—') is None


def test_parse_finds_header_context_and_total():
    plan = parser.parse(_xlsx(PLAN_ROWS), 'plano.xlsx')
    assert [row['canal'] for row in plan['lines']] == ['Meta', 'YouTube', 'Programática DV360']
    assert plan['context']['objetivo'] == 'Awareness da nova linha'
    assert plan['lines'][0]['modelo'] == 'cpm'
    assert plan['lines'][0]['inicio'] == '2026-11-01'
    assert plan['totals'][-1]['investimento'] == 30_000


def test_review_flags_math_costs_and_period():
    result = media_plan.review_file(_xlsx(PLAN_ROWS), 'plano.xlsx', call=fake_typesafe)
    status = {item['id']: item['status'] for item in result['findings']}
    assert len(result['findings']) == 14
    assert status['soma'] in {'erro', 'ok'}
    assert status['conta_entrega'] == 'erro'          # DV360: 100 mil × 90 / 1000 = 9.000 ≠ 5.000
    assert status['custos'] == 'atencao'              # CPM 90 em programática
    assert status['periodo'] == 'atencao'             # DV360 termina em dezembro
    assert status['canais_publico'] == 'na'
    # TypeSafe disse aprovar; o código encontrou erro, então o parecer sobe para ajustes.
    assert result['summary']['verdict'] == 'aprovar_com_ajustes'
    assert result['tokens_estimados'] == 3200
    assert '**Parecer: Aprovar com ajustes**' in media_plan.to_markdown(result)


def test_sum_mismatch_is_an_error():
    rows = PLAN_ROWS[:-1] + [['Total', '', '', '', '', 40_000]]
    result = media_plan.review_file(_xlsx(rows), 'plano.xlsx', call=fake_typesafe)
    soma = next(item for item in result['findings'] if item['id'] == 'soma')
    assert soma['status'] == 'erro' and 'diferença' in soma['detail']


def test_typesafe_outage_keeps_deterministic_checks():
    def down(state, questions):
        raise TypeSafeError('A API TypeSafe está temporariamente indisponível.')
    result = media_plan.review_file(_xlsx(PLAN_ROWS), 'plano.xlsx', call=down)
    assert result['summary']['partial'] is True
    assert result['typesafe']['status'] == 'indisponivel'
    assert {item['status'] for item in result['findings'] if item['group'] == 'Estratégia'} == {'na'}


def test_csv_with_semicolons_and_gross_net():
    content = ('Canal;Formato;Compra;Valor bruto;Valor líquido\n'
               'Spotify;Áudio;CPM;10.000,00;8.000,00\n'
               'Google Search;Texto;CPC;5.000,00;4.000,00\n').encode('utf-8')
    plan = parser.parse(content, 'plano.csv')
    assert plan['lines'][0]['investimento'] == 8000
    assert plan['lines'][0]['investimento_bruto'] == 10000
    result = media_plan.review_plan(plan, context={'verba': '12.000'}, call=fake_typesafe)
    soma = next(item for item in result['findings'] if item['id'] == 'soma')
    assert soma['status'] == 'ok' and 'Desconto' in soma['detail']


def test_rejects_unknown_layout():
    with pytest.raises(parser.PlanParseError):
        parser.parse(b'nome;idade\nana;30\n', 'x.csv')


# --- Acesso, MCP e página (sem banco) ---------------------------------------------------------

from aicentralv2.cadu_review import access, repository, service
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.registry import ToolError, ToolInputError, load_builtin_tools
from aicentralv2.cadu_workspace.mcp.tools import review as review_tool


@pytest.fixture()
def quiet(monkeypatch):
    """Sem banco e com TypeSafe simulado."""
    monkeypatch.setattr(repository, 'record_run', lambda **kwargs: None)
    monkeypatch.setattr('aicentralv2.services.typesafe_service.system_one', fake_typesafe)
    monkeypatch.delenv('CADU_SKILLS_ENABLED', raising=False)
    monkeypatch.delenv('CADU_REVIEW_PUBLIC', raising=False)


def _context():
    return RequestContext(client_id=12, user_id=7, conversation_id=None, surface='workspace', capabilities=('planner',))


def test_access_is_internal_until_launch(quiet, monkeypatch):
    assert access.allowed_for_session({'user_id': 1, 'is_centralcomm': True})
    assert not access.allowed_for_session({'user_id': 1, 'is_centralcomm': False})
    assert not access.allowed_for_session({})
    monkeypatch.setenv('CADU_REVIEW_PUBLIC', 'true')
    assert access.allowed_for_session({'user_id': 1})


def test_mcp_tool_is_registered_free_and_public():
    from aicentralv2.cadu_mcp_catalog import module_for_tool
    from aicentralv2.cadu_public_mcp import auth, usage
    from aicentralv2.cadu_public_mcp.routes import PUBLIC_TOOLS, PUBLIC_WRITE_TOOLS
    assert 'review.media_plan' in load_builtin_tools()._tools
    assert 'review.media_plan' in PUBLIC_TOOLS and 'review.media_plan' not in PUBLIC_WRITE_TOOLS
    assert usage.tool_cost('review.media_plan') == 0
    assert module_for_tool('review.media_plan') == 'marketing'
    assert auth.required_scope('review.media_plan') == 'resources:read'


def test_mcp_tool_reviews_base64_file(quiet, monkeypatch):
    import base64
    monkeypatch.setattr(access, 'allowed_for_user', lambda user_id: True)
    result = review_tool.review_media_plan(_context(), {
        'filename': 'plano.xlsx', 'content_base64': base64.b64encode(_xlsx(PLAN_ROWS)).decode(), 'publico': 'adultos 25-44'})
    assert result['summary']['verdict'] == 'aprovar_com_ajustes'
    assert result['context']['publico'] == 'adultos 25-44'
    assert result['markdown'].startswith('# Revisão de plano de mídia')
    assert 'lines' not in result and result['billing']['tokens_cobrados'] == 0


def test_mcp_tool_accepts_csv_text_and_rejects_outsiders(quiet, monkeypatch):
    monkeypatch.setattr(access, 'allowed_for_user', lambda user_id: True)
    csv_text = 'Canal;Formato;Compra;Investimento\nMeta;Reels;CPM;1000\nYouTube;Bumper;CPM;500\n'
    assert review_tool.review_media_plan(_context(), {'filename': 'plano', 'content_text': csv_text})['file']['lines'] == 2
    with pytest.raises(ToolInputError):
        review_tool.review_media_plan(_context(), {'filename': 'plano.csv'})
    monkeypatch.setattr(access, 'allowed_for_user', lambda user_id: False)
    with pytest.raises(ToolError, match='teste interno'):
        review_tool.review_media_plan(_context(), {'filename': 'plano.csv', 'content_text': csv_text})


def test_service_records_failed_parse(monkeypatch):
    calls = []
    monkeypatch.setattr(repository, 'record_run', lambda **kwargs: calls.append(kwargs))
    with pytest.raises(parser.PlanParseError):
        service.review_media_plan(b'a;b\n1;2\n', 'x.csv', channel='web', client_id=1, user_id=2)
    assert calls[0]['status'] == 'failed' and calls[0]['error_code'] == 'parse'


def test_web_page_and_upload_for_internal_team(quiet, monkeypatch):
    import os
    os.environ.setdefault('DB_HOST', '127.0.0.1')
    os.environ.setdefault('DB_PORT', '1')
    from tests.shared_app import get_app
    monkeypatch.setattr('aicentralv2.cadu_connect.reports_access.reports_only', lambda: False)
    app = get_app()
    app.config['TESTING'] = True
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, cliente_id=12, is_centralcomm=True, family_csrf='tok', user_type='client')
    page = client.get('/skills/analise/plano-de-midia')
    assert page.status_code == 200 and 'Revisão de plano de mídia' in page.get_data(as_text=True)
    assert client.get('/skills/analise/plano-de-midia/skill.zip').status_code == 200
    anonymous = app.test_client().get('/skills/analise/plano-de-midia/skill.zip')
    assert anonymous.status_code == 200 and anonymous.mimetype == 'application/zip'
    denied = client.post('/skills/api/analise/plano-de-midia', data={'file': (io.BytesIO(b'x'), 'p.csv')})
    assert denied.status_code == 403
    response = client.post('/skills/api/analise/plano-de-midia', headers={'X-CSRF-Token': 'tok'},
                           data={'file': (io.BytesIO(_xlsx(PLAN_ROWS)), 'plano.xlsx'), 'verba': 'R$ 27.000'},
                           content_type='multipart/form-data')
    body = response.get_json()
    assert response.status_code == 200, body
    assert body['result']['summary']['criteria'] == 14
    with client.session_transaction() as session:
        session['is_centralcomm'] = False
    assert client.get('/skills/analise/plano-de-midia').status_code == 404


def test_csv_semicolon_with_decimal_comma_and_preamble():
    content = '\n'.join([
        'Objetivo:;Awareness', 'Período:;01/11/2026 a 30/11/2026', '',
        'Veículo;Formato;Modelo de compra;CPM;Impressões;Investimento',
        'Meta;Reels;CPM;12;1.000.000;12.000,00',
        'YouTube;Pre-roll;CPM;25;400.000;10.000,00',
        'Total;;;;;22.000,00']).encode('utf-8')
    plan = parser.parse(content, 'plano.csv')
    assert [row['investimento'] for row in plan['lines']] == [12000, 10000]
    assert plan['context']['objetivo'] == 'Awareness'


def test_number_scales_and_thousands():
    assert parser.number('R$ 250 mil') == 250_000
    assert parser.number('1,5 milhão') == 1_500_000
    assert parser.number('12,000') == 12_000
    assert parser.number('12,5') == 12.5
    assert parser.number('1,000,000') == 1_000_000


def test_gross_only_plan_uses_gross_total():
    content = ('Canal;Formato;Compra;Valor bruto\nSpotify;Áudio;CPM;10.000,00\nMeta;Reels;CPM;5.000,00\n'
               'Total;;;16.000,00\n').encode('utf-8')
    result = media_plan.review_plan(parser.parse(content, 'p.csv'), call=fake_typesafe)
    soma = next(item for item in result['findings'] if item['id'] == 'soma')
    assert soma['status'] == 'erro'


def test_concentration_normalizes_channel_names():
    content = ('Canal;Formato;Compra;Investimento\nMeta;Reels;CPM;400\nMETA ;Stories;CPM;300\n'
               'YouTube;Bumper;CPM;300\n').encode('utf-8')
    result = media_plan.review_plan(parser.parse(content, 'p.csv'), call=fake_typesafe)
    item = next(finding for finding in result['findings'] if finding['id'] == 'concentracao')
    assert item['status'] == 'atencao' and '70%' in item['detail']
