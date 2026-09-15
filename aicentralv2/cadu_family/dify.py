"""Server-side Dify transport. Browser input cannot select a key, user or host."""
import json
import os
from urllib.parse import urlparse

import requests
from flask import current_app


class DifyUnavailable(RuntimeError):
    pass


def settings():
    key = current_app.config.get('CADU_DIFY_API_KEY') or os.getenv('CADU_DIFY_API_KEY', '')
    url = current_app.config.get('CADU_DIFY_BASE_URL') or os.getenv('CADU_DIFY_BASE_URL', 'https://api.dify.ai/v1')
    if not key:
        raise DifyUnavailable('A integração Dify precisa ser configurada no servidor.')
    if urlparse(url).scheme != 'https' or not urlparse(url).hostname:
        raise DifyUnavailable('O endereço Dify precisa usar HTTPS.')
    return url.rstrip('/'), {'Authorization': 'Bearer ' + key}


def events(payload):
    url, headers = settings()
    try:
        with requests.post(url + '/chat-messages', json=payload, headers=headers,
                           stream=True, timeout=(10, 90), allow_redirects=False) as response:
            if response.status_code != 200:
                raise DifyUnavailable('O Dify não conseguiu iniciar a resposta. Tente novamente.')
            parts = []
            for line in response.iter_lines():
                line = line.decode('utf-8')
                if line.startswith('data:'):
                    parts.append(line[5:].lstrip())
                elif not line and parts:
                    raw = '\n'.join(parts)
                    parts = []
                    if raw == '[DONE]':
                        return
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        raise DifyUnavailable('A resposta do Dify chegou em um formato inválido.')
                    if isinstance(event, dict):
                        yield event
            if parts:
                event = json.loads('\n'.join(parts))
                if isinstance(event, dict):
                    yield event
    except requests.RequestException as exc:
        raise DifyUnavailable('A conexão com o Dify foi interrompida. A resposta parcial foi preservada.') from exc


def upload(file, user):
    url, headers = settings()
    try:
        with requests.post(url + '/files/upload', headers=headers, data={'user': user},
                           files={'file': (file.filename, file.stream, file.mimetype)},
                           timeout=(10, 90), allow_redirects=False) as response:
            if response.status_code not in (200, 201):
                raise DifyUnavailable('O Dify não aceitou o arquivo.')
            result = response.json()
            if not result.get('id'):
                raise DifyUnavailable('O upload não retornou uma referência válida.')
            return result['id']
    except requests.RequestException as exc:
        raise DifyUnavailable('Não foi possível enviar o arquivo ao Dify.') from exc


def stop(task_id, user):
    url, headers = settings()
    if not task_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in task_id):
        raise DifyUnavailable('A geração ainda está iniciando. Tente novamente.')
    with requests.post(url + '/chat-messages/' + task_id + '/stop', headers=headers,
                       json={'user': user}, timeout=(10, 20), allow_redirects=False) as response:
        if response.status_code != 200:
            raise DifyUnavailable('Não foi possível interromper a geração no Dify.')
