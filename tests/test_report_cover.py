import uuid
from unittest import mock

from flask import Blueprint, Flask

from aicentralv2.cadu_connect import report_cover
from aicentralv2.cadu_tool_billing import InsufficientToolCredits

REPORT = {'id': 5, 'campaign_name': 'Rel Campanha', 'media_campaign_id': 100,
          'document': {'objective': 'Lançamento do perfume com foco em geração de leads.', 'start_date': '2026-09-01', 'end_date': '2026-09-30'}}


class FakeCursor:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.sink.append((sql, params))


class FakeDb:
    def __init__(self):
        self.executed, self.committed = [], False

    def cursor(self):
        return FakeCursor(self.executed)

    def commit(self):
        self.committed = True


def app_client():
    app = Flask(__name__)
    app.secret_key = 'test'
    bp = Blueprint('cover', __name__)
    report_cover.register(bp)
    app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    return client


def patched(**extra):
    return [mock.patch.object(report_cover, '_selection', return_value={'client_id': 7, 'user_id': 1, 'role': 'admin'}),
            mock.patch.object(report_cover, '_write_guard'),
            mock.patch.object(report_cover, '_rows', return_value=[REPORT]),
            mock.patch.object(report_cover, 'build_previews', return_value=[{'platforms': ['google_ads', 'meta_ads'], 'total': 30, 'previous': 20}]),
            *extra.values()]


def run(patches, call):
    for item in patches:
        item.start()
    try:
        return call()
    finally:
        mock.patch.stopall()


def test_prompt_uses_the_report_and_forbids_text_and_numbers():
    prompt = report_cover.build_cover_prompt(REPORT, {'platforms': ['google_ads', 'meta_ads'], 'total': 30, 'previous': 20})
    assert 'Rel Campanha' in prompt and 'Lançamento do perfume' in prompt and 'Google Ads, Meta Ads' in prompt
    assert 'crescimento' in prompt and 'Não escreva nenhum texto, número' in prompt
    assert '30' not in prompt, 'os números do relatório não vão para a imagem'


def test_brief_returns_prompt_and_estimate_without_generating():
    generate = mock.patch('aicentralv2.cadu_workspace.media_creation_service.generate_studio_image')
    response = run(patches=patched(e=mock.patch.object(report_cover, '_estimate', return_value=5100)) + [generate],
                   call=lambda: app_client().get('/api/v2/reports/workspaces/5/cover'))
    assert response.status_code == 200
    assert response.json['estimate'] == 5100 and response.json['aspect_ratio'] == '4:5'
    assert 'Rel Campanha' in response.json['prompt']


def test_generation_requires_cost_confirmation():
    response = run(patches=patched(), call=lambda: app_client().post('/api/v2/reports/workspaces/5/cover',
                                                                     json={'prompt': 'Capa', 'request_id': str(uuid.uuid4())}))
    assert response.status_code == 400


def test_generation_charges_through_the_studio_and_links_the_cover_to_the_report():
    db = FakeDb()
    request_id = str(uuid.uuid4())
    result = {'image_url': 'https://studio/x.png', 'session_id': 'sess-1', 'studio_url': 'https://studio/s', 'charged_credits': 4980, 'remaining_credits': 10}
    with mock.patch('aicentralv2.cadu_workspace.media_creation_service.generate_studio_image', return_value=result) as generate, \
            mock.patch('aicentralv2.db.get_db', return_value=db):
        response = run(patches=patched(), call=lambda: app_client().post('/api/v2/reports/workspaces/5/cover', json={
            'prompt': 'Capa do relatório', 'request_id': request_id, 'confirmed_cost': True}))
    assert response.status_code == 200
    assert response.json['cover_url'] == 'https://studio/x.png' and response.json['charged_credits'] == 4980
    context, arguments = generate.call_args.args
    assert (context.client_id, context.user_id) == (7, 1)
    assert arguments == {'request_id': request_id, 'prompt': 'Capa do relatório', 'aspect_ratio': '4:5', 'quality': 'padrão'}
    sql, params = db.executed[0]
    assert '"reports_report_id": 5' in params[0] and '"reports_campaign_id": 100' in params[0] and params[1] == 'sess-1'
    assert db.committed


def test_insufficient_credits_answers_402():
    with mock.patch('aicentralv2.cadu_workspace.media_creation_service.generate_studio_image', side_effect=InsufficientToolCredits('Saldo insuficiente')):
        response = run(patches=patched(), call=lambda: app_client().post('/api/v2/reports/workspaces/5/cover', json={
            'prompt': 'Capa', 'request_id': str(uuid.uuid4()), 'confirmed_cost': True}))
    assert response.status_code == 402
