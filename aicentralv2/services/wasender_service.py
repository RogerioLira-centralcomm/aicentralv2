import os
from typing import Any, Dict, Optional

import requests


class WasenderApiError(Exception):
    """Erro controlado ao comunicar com a WasenderAPI."""


def _base_url() -> str:
    return (os.getenv('WASENDER_API_BASE_URL') or 'https://www.wasenderapi.com/api').rstrip('/')


def _extract_message_id(payload: Dict[str, Any]) -> Optional[str]:
    def _from_key_obj(key_obj):
        if isinstance(key_obj, dict) and key_obj.get('id'):
            return str(key_obj['id'])
        return None

    data = payload.get('data')
    if isinstance(data, dict):
        found = _from_key_obj(data.get('key'))
        if found:
            return found
        messages = data.get('messages')
        if isinstance(messages, list) and messages:
            found = _from_key_obj((messages[0] or {}).get('key'))
            if found:
                return found
        message = data.get('message')
        if isinstance(message, dict):
            found = _from_key_obj(message.get('key'))
            if found:
                return found
            for key_name in ('id', 'message_id', 'messageId', 'msgId'):
                if message.get(key_name):
                    return str(message[key_name])
        for key_name in ('id', 'message_id', 'messageId', 'msgId'):
            if data.get(key_name):
                return str(data[key_name])
    for key in ('id', 'message_id', 'messageId', 'msgId'):
        if payload.get(key):
            return str(payload[key])
    return None


def _normalize_status(raw) -> str:
    if raw is None:
        return 'sent'
    code_map = {
        '0': 'error', '1': 'pending', '2': 'sent', '3': 'delivered', '4': 'read', '5': 'played',
        'sent': 'sent', 'delivered': 'delivered', 'read': 'read', 'pending': 'pending', 'error': 'error',
    }
    val = str(raw).strip()
    if val in code_map:
        return code_map[val]
    return code_map.get(val.lower(), val.lower())


def _extract_status(payload: Dict[str, Any]) -> str:
    data = payload.get('data')
    if isinstance(data, dict):
        update = data.get('update')
        if isinstance(update, dict) and update.get('status') is not None:
            return str(update.get('status'))
        for key in ('status', 'message_status', 'messageStatus'):
            if data.get(key) is not None:
                return str(data[key])
    for key in ('status', 'message_status', 'messageStatus'):
        if payload.get(key) is not None:
            return str(payload[key])
    return 'sent'


def enviar_mensagem_texto(api_key: str, telefone_destino: str, texto: str, timeout: int = 20) -> Dict[str, Any]:
    """Envia uma mensagem de texto pela WasenderAPI."""
    if not api_key:
        raise WasenderApiError('API key da WasenderAPI não configurada.')
    if not telefone_destino:
        raise WasenderApiError('Telefone de destino obrigatório.')
    if not texto:
        raise WasenderApiError('Texto da mensagem obrigatório.')

    try:
        resp = requests.post(
            f'{_base_url()}/send-message',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={'to': telefone_destino, 'text': texto},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise WasenderApiError(f'Erro ao comunicar com WasenderAPI: {exc}') from exc

    try:
        payload = resp.json()
    except ValueError:
        payload = {'raw': resp.text}

    if resp.status_code >= 400:
        detail = payload.get('message') or payload.get('error') or resp.text
        raise WasenderApiError(f'WasenderAPI retornou HTTP {resp.status_code}: {detail}')

    return {
        'provider': 'wasenderapi',
        'provider_message_id': _extract_message_id(payload),
        'provider_status': _normalize_status(_extract_status(payload)),
        'provider_payload': payload,
    }
