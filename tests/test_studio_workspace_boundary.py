from flask import Flask

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
    assert response.location == 'https://workspace.centralcomm.media/familia/workspace/marcas/sistema?crm_client_id=7'


def test_unconfigured_development_host_does_not_redirect():
    development = Flask(__name__)
    with development.test_request_context('/parametros/modelagem-criativos/video', base_url='http://localhost:5000'):
        assert _host_redirect('studio') is None
