from pathlib import Path

from flask import Flask

from aicentralv2.cadu_planner.marketplace import bp
from aicentralv2.cadu_planner.catalog import _audience_data_groups


def _app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test',
        PLANNER_URL='https://planner.centralcomm.media',
        SERVER_NAME='planner.centralcomm.media',
    )
    app.add_url_rule('/familia/planner/audiencias', endpoint='cadu_family.page',
                     view_func=lambda product, module: f'{product}:{module}')
    app.add_url_rule('/familia/planner/audiencias/<int:audience_id>', endpoint='cadu_family.planner_audience_detail',
                     view_func=lambda audience_id: f'audience:{audience_id}')
    app.register_blueprint(bp)
    return app


def test_audience_marketplace_uses_the_canonical_planner_shell():
    client = _app().test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1

    response = client.get('/audiencias', headers={'Host': 'planner.centralcomm.media'})
    detail = client.get('/audiencias/42', headers={'Host': 'planner.centralcomm.media'})

    assert response.get_data(as_text=True) == 'planner:audiencias'
    assert detail.get_data(as_text=True) == 'audience:42'


def test_audience_marketplace_keeps_the_login_boundary():
    response = _app().test_client().get('/audiencias', headers={'Host': 'planner.centralcomm.media'})

    assert response.status_code == 302


def test_audience_cards_have_visual_title_and_direct_detail_link():
    content = (Path(__file__).resolve().parents[1] / 'aicentralv2/templates/cadu_planner/family/catalog.html').read_text(encoding='utf-8')

    assert 'planner-audience-card__detail' in content
    assert 'Imagem de contexto da audiência' in content
    assert "planner_url(module ~ '/' ~ row.id" in content
    assert 'planner-catalog-card__facts' in content


def test_audience_detail_exposes_database_variables_in_groups():
    groups = _audience_data_groups({
        'id': 1568,
        'nome': '18-24 anos',
        'cpm_venda': 260,
        'dados_validos': True,
        'tags': ['mobile-first'],
        'taxonomy': {'catalog_role': 'contexto'},
    })
    fields = {item['variable']: item for group in groups for item in group['fields']}

    assert fields['id']['value'] == '1568'
    assert fields['cpm_venda']['value'] == 'R$ 260,00'
    assert fields['dados_validos']['value'] == 'Sim'
    assert fields['mensagem_cotacao']['value'] == 'Não informado.'
    assert fields['taxonomy']['is_structured'] is True

    content = (Path(__file__).resolve().parents[1] / 'aicentralv2/templates/cadu_planner/family/audience_detail_page.html').read_text(encoding='utf-8')
    assert 'field.variable' in content
    assert 'Ficha completa da audiência' in content


def test_audience_experience_styles_cover_catalog_and_detail():
    content = (Path(__file__).resolve().parents[1] / 'aicentralv2/static/css/cadu-planner-audiences-experience.css').read_text(encoding='utf-8')

    assert '.planner-catalog--audiencias .planner-catalog-discovery' in content
    assert '.planner-audience-detail-layout' in content
    assert '.planner-audience-related' in content
