from pathlib import Path

from flask import Flask, render_template

from aicentralv2.creative_modeling_routes import _host_redirect, modelagem_desk


def app():
    result = Flask(__name__)
    result.config.update(CENTRALX_URL='https://centralx.centralcomm.media',
                         STUDIO_URL='https://studio.centralcomm.media',
                         WORKSPACE_URL='https://workspace.centralcomm.media')
    return result


def test_centralx_legacy_studio_path_redirects_with_query():
    with app().test_request_context('/parametros/modelagem-criativos/video?client=12', base_url='https://centralx.centralcomm.media'):
        response = _host_redirect('studio')
    assert response.status_code == 302
    assert response.location == 'https://studio.centralcomm.media/parametros/modelagem-criativos/video?client=12'


def test_workspace_legacy_brand_path_moves_into_workspace_shell():
    with app().test_request_context('/parametros/modelagem-criativos/marcas?crm_client_id=7', base_url='https://workspace.centralcomm.media'):
        response = modelagem_desk.__wrapped__('marcas')
    assert response.status_code == 302
    assert response.location == 'https://workspace.centralcomm.media/marcas?crm_client_id=7'


def test_workspace_brand_path_keeps_the_native_brand_identifier():
    with app().test_request_context(
        '/parametros/modelagem-criativos/marcas?crm_client_id=7&creative_client_id=31',
        base_url='https://workspace.centralcomm.media',
    ):
        response = modelagem_desk.__wrapped__('marcas')
    assert response.status_code == 302
    assert response.location == (
        'https://workspace.centralcomm.media/workspace/app/marcas/31'
        '?crm_client_id=7&creative_client_id=31'
    )


def test_unconfigured_development_host_does_not_redirect():
    development = Flask(__name__)
    with development.test_request_context('/parametros/modelagem-criativos/video', base_url='http://localhost:5000'):
        assert _host_redirect('studio') is None


def test_video_workspace_renders_its_runtime_scripts_in_portal_shell():
    root = Path(__file__).resolve().parents[1]
    studio = Flask(
        __name__,
        template_folder=str(root / 'aicentralv2' / 'templates'),
        static_folder=str(root / 'aicentralv2' / 'static'),
    )
    studio.secret_key = 'test'
    studio.config.update(
        STUDIO_URL='https://studio.test', WORKSPACE_URL='https://workspace.test',
        CADU_URL='https://cadu.test', AUTH_URL='https://auth.test',
    )
    studio.context_processor(lambda: {
        'product_url': lambda product, path='/': f'https://{product}.test{path}',
        'studio_url': lambda endpoint, **values: f'/{endpoint}',
    })
    with studio.test_request_context('/video', base_url='https://studio.test'):
        html = render_template(
            'cadu_studio/desk.html', mc_title='Studio', mc_page='video',
            panel='parametros/_mc_video.html', mc_studio_js=False,
            mc_page_js='js/mc-cadu-video.js', mc_trocr_csrf='csrf',
        )
    assert 'js/mc-desk-brand.js' in html
    assert 'js/mc-cadu-nav.js' in html
    assert 'js/mc-cadu-video.js' in html


def test_studio_navigation_has_one_authoritative_active_state():
    root = Path(__file__).resolve().parents[1]
    css = (root / 'aicentralv2' / 'static' / 'css' / 'cadu-studio-navigation.css').read_text()

    assert css.count('.mc-cadu-bar--studio .mc-cadu-nav > a[aria-current="page"]') == 1
    assert 'background: #263b39;' in css
    assert 'color: #8fe8d1;' in css
    assert 'outline: 3px solid #8fe8d1;' in css
