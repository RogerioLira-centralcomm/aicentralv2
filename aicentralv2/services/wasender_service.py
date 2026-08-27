import base64
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class WasenderApiError(Exception):
    """Erro controlado ao comunicar com a WasenderAPI."""


MEDIA_MESSAGE_KEYS = {
    'imageMessage': 'image',
    'videoMessage': 'video',
    'audioMessage': 'audio',
    'documentMessage': 'document',
    'stickerMessage': 'sticker',
}

MEDIA_LABELS = {
    'gif': '[GIF]',
    'image': '[Imagem]',
    'video': '[Vídeo]',
    'audio': '[Áudio]',
    'document': '[Documento]',
    'sticker': '[Sticker]',
}


def _base_url() -> str:
    return (os.getenv('WASENDER_API_BASE_URL') or 'https://www.wasenderapi.com/api').rstrip('/')


def _whatsapp_media_dir() -> Path:
    return Path(__file__).resolve().parent.parent / 'static' / 'media' / 'whatsapp'


def _desembrulhar_mensagem(raw_msg: Any) -> Dict[str, Any]:
    """WhatsApp às vezes envolve mídia em ephemeralMessage / viewOnceMessage."""
    if not isinstance(raw_msg, dict):
        return {}
    atual = raw_msg
    for _ in range(4):
        wrapped = None
        for key in ('ephemeralMessage', 'viewOnceMessage', 'viewOnceMessageV2', 'documentWithCaptionMessage'):
            val = atual.get(key) if isinstance(atual, dict) else None
            if isinstance(val, dict) and isinstance(val.get('message'), dict):
                wrapped = val['message']
                break
        if not wrapped:
            break
        atual = wrapped
    return atual if isinstance(atual, dict) else {}


def normalizar_media_key(media_key: Any) -> Optional[str]:
    if media_key is None:
        return None
    if isinstance(media_key, str):
        return media_key.strip() or None
    if isinstance(media_key, (bytes, bytearray)):
        return base64.b64encode(media_key).decode('ascii')
    if isinstance(media_key, dict):
        data = media_key.get('data')
        if isinstance(data, list):
            try:
                return base64.b64encode(bytes(int(x) & 0xFF for x in data)).decode('ascii')
            except (TypeError, ValueError):
                return None
    return str(media_key).strip() or None


def _is_gif_media(info: Dict[str, Any], message_key: str) -> bool:
    if not isinstance(info, dict):
        return False
    if info.get('gifPlayback') in (True, 'true', 'True', 1, '1'):
        return True
    mime = (info.get('mimetype') or '').lower()
    if 'gif' in mime:
        return True
    if message_key == 'imageMessage' and mime == 'image/webp' and info.get('isAnimated'):
        return True
    return False


def _normalizar_info_midia(info: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(info)
    mk = normalizar_media_key(out.get('mediaKey'))
    if mk:
        out['mediaKey'] = mk
    return out


def detectar_midia_mensagem(message_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Retorna (tipo, objeto de mídia). GIFs vêm como videoMessage com gifPlayback."""
    if not isinstance(message_data, dict):
        return None, None
    raw_msg = _desembrulhar_mensagem(message_data.get('message') or {})
    if not raw_msg:
        return None, None
    for key, media_type in MEDIA_MESSAGE_KEYS.items():
        info = raw_msg.get(key)
        if isinstance(info, dict):
            info = _normalizar_info_midia(info)
            if key == 'documentMessage':
                mime = (info.get('mimetype') or '').lower()
                if mime.startswith('audio/'):
                    return 'audio', info
            if _is_gif_media(info, key):
                return 'gif', info
            return media_type, info
    return None, None


def preparar_message_data_para_decrypt(message_data: Dict[str, Any]) -> Dict[str, Any]:
    md = dict(message_data)
    raw_msg = _desembrulhar_mensagem(md.get('message') or {})
    raw_copy = dict(raw_msg)
    for key in MEDIA_MESSAGE_KEYS:
        if key in raw_copy and isinstance(raw_copy[key], dict):
            raw_copy[key] = _normalizar_info_midia(raw_copy[key])
    md['message'] = raw_copy
    return md


def label_midia(media_type: Optional[str], media_info: Optional[Dict[str, Any]] = None) -> str:
    if media_type == 'audio' and isinstance(media_info, dict) and media_info.get('ptt') in (True, 'true', 'True', 1, '1'):
        return '[Áudio de voz]'
    return MEDIA_LABELS.get(media_type or '', '[Mídia]')


def _ext_from_mimetype(mimetype: Optional[str], media_type: Optional[str]) -> str:
    if media_type == 'gif':
        return 'mp4'
    mime = (mimetype or '').split(';')[0].strip().lower()
    mapping = {
        'image/jpeg': 'jpg',
        'image/jpg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
        'image/gif': 'gif',
        'video/mp4': 'mp4',
        'audio/ogg': 'ogg',
        'audio/opus': 'ogg',
        'audio/mpeg': 'mp3',
        'audio/mp4': 'm4a',
        'audio/aac': 'aac',
        'application/pdf': 'pdf',
    }
    if mime in mapping:
        return mapping[mime]
    base_mime = mime.split(';')[0].strip()
    if base_mime in mapping:
        return mapping[base_mime]
    part = mime.split('/')[-1] if '/' in mime else 'bin'
    return re.sub(r'[^a-z0-9]+', '', part) or 'bin'


def decryptar_midia_mensagem(api_key: str, message_data: Dict[str, Any], timeout: int = 45) -> Optional[str]:
    """Descriptografa mídia via WasenderAPI e retorna publicUrl temporária."""
    if not api_key or not isinstance(message_data, dict):
        return None
    prepared = preparar_message_data_para_decrypt(message_data)
    key = prepared.get('key') or {}
    message = prepared.get('message') or {}
    msg_id = key.get('id') if isinstance(key, dict) else None
    if not msg_id or not isinstance(message, dict) or not message:
        return None
    media_type, media_info = detectar_midia_mensagem(prepared)
    if not media_type or not media_info:
        return None
    if not media_info.get('url') or not media_info.get('mediaKey'):
        logger.warning('Wasender mídia sem url/mediaKey: tipo=%s msg_id=%s', media_type, msg_id)
        return None

    payload = {
        'data': {
            'messages': {
                'key': key if isinstance(key, dict) else {'id': msg_id},
                'message': message,
            }
        }
    }
    try:
        resp = requests.post(
            f'{_base_url()}/decrypt-media',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=timeout,
        )
        body = resp.json() if resp.content else {}
    except (requests.RequestException, ValueError) as exc:
        logger.warning('Wasender decrypt-media erro rede/json: %s', exc)
        return None
    if resp.status_code >= 400 or not body.get('success'):
        logger.warning(
            'Wasender decrypt-media falhou: status=%s tipo=%s msg_id=%s body=%s',
            resp.status_code, media_type, msg_id, body,
        )
        return None
    public_url = body.get('publicUrl') or body.get('public_url')
    return str(public_url).strip() if public_url else None


def salvar_midia_local(public_url: str, file_id: str, mimetype: Optional[str], media_type: Optional[str]) -> Optional[str]:
    """Baixa mídia descriptografada e salva em static/media/whatsapp/."""
    if not public_url or not file_id:
        return None
    safe_id = re.sub(r'[^a-zA-Z0-9._-]+', '_', str(file_id))
    ext = _ext_from_mimetype(mimetype, media_type)
    dest_dir = _whatsapp_media_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f'{safe_id}.{ext}'
    try:
        resp = requests.get(public_url, timeout=60)
        resp.raise_for_status()
        dest_path.write_bytes(resp.content)
    except requests.RequestException:
        return None
    return f'/static/media/whatsapp/{safe_id}.{ext}'


def processar_midia_inbound(api_key: str, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Descriptografa e persiste mídia inbound; retorna metadados para provider_payload."""
    media_type, media_info = detectar_midia_mensagem(message_data)
    if not media_type or not media_info:
        return None
    key = message_data.get('key') or {}
    msg_id = key.get('id') if isinstance(key, dict) else None
    public_url = decryptar_midia_mensagem(api_key, message_data)
    local_url = None
    if public_url and msg_id:
        local_url = salvar_midia_local(
            public_url,
            msg_id,
            media_info.get('mimetype'),
            media_type,
        )
    return {
        'type': media_type,
        'ptt': bool(media_info.get('ptt') in (True, 'true', 'True', 1, '1')),
        'seconds': media_info.get('seconds'),
        'url': public_url,
        'local_url': local_url,
        'mimetype': media_info.get('mimetype'),
    }


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
        'in_progress': 'sent', 'received': 'received',
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
