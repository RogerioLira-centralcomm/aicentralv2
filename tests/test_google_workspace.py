from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from flask import Flask
from cryptography.fernet import Fernet

from aicentralv2.services.google_workspace import (
    SCOPES,
    _encryption_key,
    authorization_url,
    exchange_code,
    list_calendar_events,
    list_meet_conference_records,
    list_meet_transcripts,
    service_matrix,
    sync_calendar_events,
    sync_drive,
)


def test_google_workspace_token_key_can_come_from_encrypted_database_configuration():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', GOOGLE_TOKEN_ENCRYPTION_KEY='')
    token_key = Fernet.generate_key().decode()
    config = {
        'configured': True,
        'token_encryption_key': token_key,
    }
    with app.test_request_context('/'):
        with patch(
            'aicentralv2.services.integration_credentials.get_configuration',
            return_value=config,
        ):
            assert _encryption_key() == token_key


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


def test_google_workspace_service_matrix_explains_missing_authorization():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test',
        GOOGLE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        GOOGLE_ADS_DEVELOPER_TOKEN='developer-token',
    )
    config = {
        'configured': True,
        'source': 'environment',
        'client_id': 'workspace-client.apps.googleusercontent.com',
        'client_secret': 'secret',
        'redirect_uri': 'https://auth.centralcomm.media/auth/google/workspace/callback',
    }
    with app.test_request_context('/'):
        with patch('aicentralv2.services.integration_credentials.get_configuration', return_value=config), \
             patch('aicentralv2.services.google_workspace._available', return_value=True), \
             patch('aicentralv2.services.google_workspace.get_connection', return_value=None):
            result = service_matrix(44)
    assert result['summary']['enabled_count'] == 0
    assert {item['status'] for item in result['services']} == {'needs_authorization'}
    assert result['configuration']['missing'] == []


def test_google_workspace_service_matrix_marks_all_capabilities_ready():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test',
        GOOGLE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
        GOOGLE_ADS_DEVELOPER_TOKEN='developer-token',
    )
    config = {
        'configured': True,
        'source': 'environment',
        'client_id': 'workspace-client.apps.googleusercontent.com',
        'client_secret': 'secret',
        'redirect_uri': 'https://auth.centralcomm.media/auth/google/workspace/callback',
    }
    connection = {'status': 'connected', 'granted_scopes': ' '.join(SCOPES)}
    with app.test_request_context('/'):
        with patch('aicentralv2.services.integration_credentials.get_configuration', return_value=config), \
             patch('aicentralv2.services.google_workspace._available', return_value=True), \
             patch('aicentralv2.services.google_workspace.get_connection', return_value=connection):
            result = service_matrix(44)
    assert result['summary'] == {'enabled_count': 6, 'total_count': 6, 'pending_count': 0}
    assert all(item['status'] == 'enabled' for item in result['services'])


def test_google_drive_sync_consumes_changes_cursor_and_archives_removed_files():
    response = Mock(ok=True, status_code=200)
    response.json.return_value = {
        'changes': [
            {'file': {'id': 'file-1', 'name': 'Briefing atualizado', 'mimeType': 'application/pdf'}},
            {'fileId': 'file-2', 'removed': True},
        ],
        'newStartPageToken': 'cursor-2',
    }
    connection = {'id': 'connection-1', 'sync_state': {'drive_change_token': 'cursor-1'}}
    with patch('aicentralv2.services.google_workspace.get_connection', return_value=connection), \
         patch('aicentralv2.services.google_workspace._access_token', return_value='access'), \
         patch('aicentralv2.services.google_workspace._encrypted_token', return_value='encrypted'), \
         patch('aicentralv2.services.google_workspace.requests.get', return_value=response) as get, \
         patch('aicentralv2.services.google_workspace._upsert_drive_changes') as upsert, \
         patch('aicentralv2.services.google_workspace._persist_drive_sync_state') as persist:
        result = sync_drive(44, limit=25)

    assert result == {
        'provider': 'google_drive', 'mode': 'incremental', 'synced': 1,
        'archived': 1, 'next_page_token': None,
    }
    upsert.assert_called_once_with('connection-1', [response.json.return_value['changes'][0]['file']], ['file-2'])
    persist.assert_called_once_with('connection-1', {'drive_change_token': 'cursor-2'})
    assert get.call_args.kwargs['params']['pageToken'] == 'cursor-1'


def test_google_calendar_and_meet_use_the_shared_workspace_connection():
    connection = {'id': 'connection-1'}
    calendar_response = Mock(ok=True, status_code=200)
    calendar_response.json.return_value = {'items': [{'id': 'event-1', 'summary': 'Reunião'}]}
    meet_response = Mock(ok=True, status_code=200)
    meet_response.json.return_value = {'conferenceRecords': [{'name': 'conferenceRecords/1'}]}
    with patch('aicentralv2.services.google_workspace.get_connection', return_value=connection), \
         patch('aicentralv2.services.google_workspace._access_token', return_value='access'), \
         patch('aicentralv2.services.google_workspace._encrypted_token', return_value='encrypted'), \
         patch('aicentralv2.services.google_workspace.requests.get', side_effect=[calendar_response, meet_response]) as get:
        events = list_calendar_events(44, limit=10)
        records = list_meet_conference_records(44, limit=10)

    assert events == [{'id': 'event-1', 'summary': 'Reunião'}]
    assert records == [{'name': 'conferenceRecords/1'}]
    assert get.call_args_list[0].args[0].endswith('/calendar/v3/calendars/primary/events')
    assert get.call_args_list[1].args[0].endswith('/v2/conferenceRecords')


def test_google_meet_transcripts_use_conference_record_parent():
    connection = {'id': 'connection-1'}
    response = Mock(ok=True, status_code=200)
    response.json.return_value = {'transcripts': [{'name': 'conferenceRecords/1/transcripts/1'}]}
    with patch('aicentralv2.services.google_workspace.get_connection', return_value=connection), \
         patch('aicentralv2.services.google_workspace._access_token', return_value='access'), \
         patch('aicentralv2.services.google_workspace._encrypted_token', return_value='encrypted'), \
         patch('aicentralv2.services.google_workspace.requests.get', return_value=response) as get:
        result = list_meet_transcripts(44, 'conferenceRecords/1', limit=5)
    assert result[0]['name'].endswith('/transcripts/1')
    assert get.call_args.args[0].endswith('/v2/conferenceRecords/1/transcripts')


def test_google_calendar_sync_uses_saved_sync_token_and_persists_next_token():
    connection = {'id': 'connection-1', 'sync_state': {'calendar_sync_token': 'calendar-1'}}
    response = Mock(ok=True, status_code=200)
    response.json.return_value = {
        'items': [{'id': 'event-1', 'status': 'confirmed'}, {'id': 'event-2', 'status': 'cancelled'}],
        'nextSyncToken': 'calendar-2',
    }
    with patch('aicentralv2.services.google_workspace.get_connection', return_value=connection), \
         patch('aicentralv2.services.google_workspace._access_token', return_value='access'), \
         patch('aicentralv2.services.google_workspace._encrypted_token', return_value='encrypted'), \
         patch('aicentralv2.services.google_workspace.requests.get', return_value=response) as get, \
         patch('aicentralv2.services.google_workspace._upsert_calendar_events') as upsert, \
         patch('aicentralv2.services.google_workspace._persist_drive_sync_state') as persist:
        result = sync_calendar_events(44, limit=20)
    assert result == {'provider': 'google_calendar', 'mode': 'incremental', 'synced': 1, 'archived': 1}
    assert get.call_args.kwargs['params']['syncToken'] == 'calendar-1'
    upsert.assert_called_once_with('connection-1', response.json.return_value['items'])
    persist.assert_called_once_with('connection-1', {'calendar_sync_token': 'calendar-2'})
