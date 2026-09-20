from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from flask import Flask

from aicentralv2.services.google_workspace import SCOPES, authorization_url, exchange_code


def test_google_workspace_authorization_requests_workspace_capabilities():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test')
    config = {
        'configured': True,
        'client_id': 'workspace-client.apps.googleusercontent.com',
        'client_secret': 'secret',
        'redirect_uri': 'https://auth.centralcomm.media/auth/google/workspace/callback',
    }
    with app.test_request_context('/'):
        with patch('aicentralv2.services.integration_credentials.get_configuration', return_value=config):
            query = parse_qs(urlparse(authorization_url('state', code_challenge='challenge')).query)
    assert query['state'] == ['state']
    assert query['redirect_uri'] == ['https://auth.centralcomm.media/auth/google/workspace/callback']
    assert query['code_challenge'] == ['challenge']
    assert 'https://www.googleapis.com/auth/drive' in query['scope'][0]
    assert 'https://www.googleapis.com/auth/meetings.space.created' in query['scope'][0]
    assert 'https://www.googleapis.com/auth/adwords' in query['scope'][0]


def test_google_workspace_exchange_keeps_pkce_verifier_and_identity():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test')
    response = Mock(ok=True)
    response.json.return_value = {'id_token': 'signed', 'refresh_token': 'refresh', 'scope': 'scope-a'}
    identity = {'sub': 'google-1', 'email': 'cliente@empresa.com', 'email_verified': True}
    config = {
        'configured': True,
        'client_id': 'workspace-client.apps.googleusercontent.com',
        'client_secret': 'secret',
        'redirect_uri': 'https://auth.centralcomm.media/auth/google/workspace/callback',
    }
    with app.test_request_context('/'):
        with patch('aicentralv2.services.integration_credentials.get_configuration', return_value=config), \
             patch('aicentralv2.services.google_workspace.requests.post', return_value=response) as post, \
             patch('aicentralv2.services.google_workspace.id_token.verify_oauth2_token', return_value=identity):
            result = exchange_code('code', code_verifier='verifier')
    assert result['google_email'] == 'cliente@empresa.com'
    assert result['refresh_token'] == 'refresh'
    assert post.call_args.kwargs['data']['code_verifier'] == 'verifier'
