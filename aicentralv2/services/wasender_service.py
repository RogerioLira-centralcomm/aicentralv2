import os
from typing import Any, Dict, Optional

import requests


class WasenderApiError(Exception):
    """Erro controlado ao comunicar com a WasenderAPI."""


def _base_url() -> str:
    return (os.getenv('WASENDER_API_BASE_URL') or 'https://www.wasenderapi.com/api').rstrip('/')


def _extract_message_id(payload: Dict[str, Any]) -> Optional[str]:
    for key in ('id', 'message_id', 'messageId', 'msgId'):
        if payload.get(key):
            return str(payload[key])
    data = payload.get('data')
    if isinstance(data, dict):
        for key in ('id', 'message_id', 'messageId', 'msgId'):
            if data.get(key):
                return str(data[key])
        message = data.get('message')
        if isinstance(message, dict):
            for key in ('id', 'message_id', 'messageId', 'msgId'):
                if message.get(key):
                    return str(message[key])
    return None


def _extract_status(payload: Dict[str, Any]) -> str:
    for key in ('status', 'message_status', 'messageStatus'):
        if payload.get(key):
            return str(payload[key])
    data = payload.get('data')
    if isinstance(data, dict):
        for key in ('status', 'message_status', 'messageStatus'):
            if data.get(key):
                return str(data[key])
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
        'provider_status': _extract_status(payload),
        'provider_payload': payload,
    }
