"""E-mail "o que será feito" do Radar, sem enviar nada."""
from flask import Flask

from aicentralv2.cadu_radar import notify

BASE = dict(name='Apolo', concept='consumo consciente no fim do ano', brand='Cemig', places='Minas Gerais', recency_days=30,
            estimated_tokens=1624, run_url='https://planner.centralcomm.media/radar?run=x', radars_url='https://planner.centralcomm.media/radares')


def test_email_lists_what_will_be_done_and_the_cost():
    subject, text, html = notify.compose(**BASE)
    assert subject == 'Seu radar começou: consumo consciente no fim do ano'
    assert '«consumo consciente no fim do ano» em Minas Gerais, nos últimos 30 dias' in text
    assert 'link que abre' in text and 'ângulos para a marca Cemig' in text
    assert 'até 1.624 tokens' in text and BASE['run_url'] in text and BASE['run_url'] in html
    assert 'repetir' not in text  # sem radar ativo, sem frase de repetição


def test_email_mentions_the_schedule_only_for_an_active_radar():
    _, text, html = notify.compose(**BASE, repeat=3)
    assert 'vai se repetir 3 vezes por dia (às 8h, 13h e 18h' in text and 'Meus radares' in html and BASE['radars_url'] in text
    assert 'repetir' not in notify.compose(**BASE, repeat=7)[1]  # frequência desconhecida não vira promessa


def test_email_without_concept_falls_back_to_the_brand_and_escapes_html():
    subject, text, html = notify.compose(**{**BASE, 'concept': '', 'name': '<script>x</script>'})
    assert subject == 'Seu radar começou: Cemig' and '<script>' not in html and '&lt;script&gt;' in html


def test_run_started_skips_users_without_email_and_never_raises(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, '_send', lambda *args: sent.append(args))
    with Flask(__name__).app_context():
        kwargs = dict(concept='tema', brand='Cemig', params={'places': 'BH', 'recency_days': 7}, estimated_tokens=500, run_url='u', radars_url='r', background=False)
        assert notify.run_started({'name': 'Ana Souza', 'email': ''}, **kwargs) is False and sent == []
        assert notify.run_started({'name': 'Ana Souza', 'email': 'ana@x.com'}, **kwargs) is True
    (_, to_email, to_name, subject, text, html), = sent
    assert to_email == 'ana@x.com' and 'Olá, Ana!' in text and 'últimos 7 dias' in text  # só o primeiro nome


def test_a_provider_failure_is_swallowed(monkeypatch):
    from aicentralv2.services import brevo_service

    class Broken:
        def enviar_email(self, **kwargs):
            raise RuntimeError('brevo fora')

    monkeypatch.setattr(brevo_service, 'get_brevo_service', lambda: Broken())
    app = Flask(__name__)
    notify._send(app, 'ana@x.com', 'Ana', 's', 't', 'h')  # não levanta


def test_api_403_returns_the_reason_instead_of_a_generic_html_page():
    from werkzeug.exceptions import Forbidden

    from aicentralv2.cadu_family import routes
    app = Flask(__name__)
    with app.test_request_context('/familia/api/planner/radar/runs', method='POST'):
        response, status = routes.forbidden(Forbidden(description='Migração em modo de consulta. Gravações não estão habilitadas.'))
        assert status == 403 and response.get_json() == {'error': 'Migração em modo de consulta. Gravações não estão habilitadas.'}


def test_api_403_without_a_description_is_not_shown_in_english():
    from werkzeug.exceptions import Forbidden

    from aicentralv2.cadu_family import routes
    with Flask(__name__).test_request_context('/familia/api/planner/radar/runs', method='POST'):
        response, status = routes.forbidden(Forbidden())
        assert status == 403 and response.get_json() == {'error': 'Você não tem permissão para esta ação.'}
