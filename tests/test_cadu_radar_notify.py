"""E-mail de conclusão do Radar e tempo poupado, sem enviar nada."""
from datetime import datetime, timezone

from flask import Flask

from aicentralv2.cadu_radar import notify, time_saved

ANGLES = [{'title': 'Conta verde não é conta barata', 'thesis': 'Explicar a fatura de outubro.',
           'score_breakdown': {'why_now': 'Bandeira verde em outubro.', 'formats': ['carrossel', 'reels', 'story'], 'channels': ['Instagram', 'TikTok'],
                               'window': 'até novembro'}},
          {'title': 'Fim de ano sem susto', 'thesis': 'Dicas de economia.', 'score_breakdown': {}}]
BUZZ = [{'headline': 'Bandeira verde em outubro', 'source': 'g1', 'url': 'https://g1.globo.com/a', 'published_at': datetime(2026, 9, 25, tzinfo=timezone.utc)},
        {'headline': 'IPCA-15', 'source': 'CNN Brasil', 'url': 'https://cnnbrasil.com.br/b', 'published_at': '2026-09-24'}]
BASE = dict(name='Apolo', concept='consumo consciente no fim do ano', brand='Cemig', places='Minas Gerais', recency_days=30, angles=ANGLES, buzz=BUZZ,
            saved=time_saved.estimate(2, 2), tokens=1624, run_url='https://planner.centralcomm.media/radar?run=x', radars_url='https://planner.centralcomm.media/radares')


def test_time_saved_counts_only_what_was_delivered_and_shows_the_account():
    saved = time_saved.estimate(4, 4)
    assert saved['minutes'] == 30 + 4 * 5 + 4 * 15 == 110 and saved['label'] == '2 h'
    assert [(line['key'], line['count'], line['minutes']) for line in saved['lines']] == [('buzz', 1, 30), ('check', 4, 20), ('angle', 4, 60)]
    assert time_saved.estimate(5, 0) == {'minutes': 0, 'label': '', 'lines': [], 'note': ''}  # sem ângulo, nada poupado
    assert time_saved.estimate(0, 1)['minutes'] == 30 + 15  # sem buzz verificado, não há fonte para conferir
    assert '(× 4)' in time_saved.account(saved) and 'ângulo' in time_saved.account(saved)


def test_email_delivers_angles_buzz_time_saved_and_cost():
    subject, text, html = notify.compose(**BASE)
    assert subject == 'Seu radar terminou: 2 ângulos sobre consumo consciente no fim do ano'
    assert 'Encontramos 2 assuntos em buzz em Minas Gerais e montamos 2 ângulos para a marca Cemig falar de «consumo consciente no fim do ano»' in text
    assert 'Tempo economizado: cerca de 1 h de pesquisa e ideação.' in text and 'A conta:' in text
    assert '1. Conta verde não é conta barata' in text and 'Por que agora: Bandeira verde em outubro.' in text
    assert 'Formatos e canais: carrossel, reels, Instagram, TikTok' in text  # dois formatos e até três canais
    assert '- Bandeira verde em outubro (g1, 25/09): https://g1.globo.com/a' in text and '(CNN Brasil, 24/09)' in text
    assert 'usou 1.624 tokens' in text and BASE['run_url'] in text and BASE['radars_url'] in text
    assert 'Ver os ângulos e criar o planejamento' in html and 'Tempo economizado' in html


def test_email_without_angles_is_honest_and_claims_no_time_saved():
    subject, text, html = notify.compose(**{**BASE, 'angles': [], 'buzz': [], 'saved': time_saved.estimate(0, 0)})
    assert subject == 'Seu radar terminou: sem buzz recente sobre consumo consciente no fim do ano'
    assert 'Não encontramos buzz com data recente e link que abre' in text and 'economizado' not in text and 'economizado' not in html


def test_email_without_concept_falls_back_to_the_brand_and_escapes_html():
    subject, text, html = notify.compose(**{**BASE, 'concept': '', 'name': '<script>x</script>', 'angles': [{'title': '<b>x</b>', 'thesis': 'a&b'}]})
    assert subject.endswith('sobre Cemig') and '<script>' not in html and '&lt;script&gt;' in html and '<b>x</b>' not in html


def test_run_finished_sends_to_the_owner_and_uses_the_first_name(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, '_send', lambda *args: sent.append(args))
    run = {'opportunities': ANGLES, 'signals': BUZZ, 'focus': 'tema', 'params': {'places': 'BH', 'recency_days': 7}, 'tokens': 125, 'trigger': 'manual'}
    with Flask(__name__).app_context():
        assert notify.run_finished({'name': 'Ana Souza', 'email': ''}, run=run, brand='Cemig', run_url='u', radars_url='r') is False
        assert notify.run_finished({'name': 'Ana Souza', 'email': 'ana@x.com'}, run=run, brand='Cemig', run_url='u', radars_url='r') is True
    (_, to_email, to_name, subject, text, html), = sent
    assert to_email == 'ana@x.com' and 'Olá, Ana!' in text and 'em BH' in text


def test_a_scheduled_radar_without_news_stays_quiet_but_a_manual_search_always_answers(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, '_send', lambda *args: sent.append(args))
    user = {'name': 'Ana', 'email': 'ana@x.com'}
    with Flask(__name__).app_context():
        empty = {'opportunities': [], 'signals': [], 'focus': 'tema', 'params': {}, 'tokens': 0}
        assert notify.run_finished(user, run={**empty, 'trigger': 'agendado'}, brand=None, run_url='u', radars_url='r') is False
        assert notify.run_finished(user, run={**empty, 'trigger': 'manual'}, brand=None, run_url='u', radars_url='r') is True
        assert notify.run_finished(user, run={**empty, 'trigger': 'agendado', 'opportunities': ANGLES, 'signals': BUZZ}, brand=None, run_url='u', radars_url='r') is True
    assert len(sent) == 2


def test_a_provider_failure_is_swallowed(monkeypatch):
    from aicentralv2.services import brevo_service

    class Broken:
        def enviar_email(self, **kwargs):
            raise RuntimeError('brevo fora')

    monkeypatch.setattr(brevo_service, 'get_brevo_service', lambda: Broken())
    notify._send(Flask(__name__), 'ana@x.com', 'Ana', 's', 't', 'h')  # não levanta


def test_api_403_returns_the_reason_instead_of_a_generic_html_page():
    from werkzeug.exceptions import Forbidden

    from aicentralv2.cadu_family import routes
    with Flask(__name__).test_request_context('/familia/api/planner/radar/runs', method='POST'):
        response, status = routes.forbidden(Forbidden(description='Migração em modo de consulta. Gravações não estão habilitadas.'))
        assert status == 403 and response.get_json() == {'error': 'Migração em modo de consulta. Gravações não estão habilitadas.'}


def test_api_403_without_a_description_is_not_shown_in_english():
    from werkzeug.exceptions import Forbidden

    from aicentralv2.cadu_family import routes
    with Flask(__name__).test_request_context('/familia/api/planner/radar/runs', method='POST'):
        response, status = routes.forbidden(Forbidden())
        assert status == 403 and response.get_json() == {'error': 'Você não tem permissão para esta ação.'}


def test_buzz_date_keeps_the_reporting_day_whatever_the_database_timezone():
    from zoneinfo import ZoneInfo
    stored = datetime(2026, 10, 1, tzinfo=timezone.utc).astimezone(ZoneInfo('America/Sao_Paulo'))  # 30/09 21:00 no fuso do banco
    assert notify._day(stored) == '01/10' and notify._day(datetime(2026, 10, 1, tzinfo=timezone.utc)) == '01/10'
    assert notify._day('2026-10-01') == '01/10' and notify._day(None) == ''
