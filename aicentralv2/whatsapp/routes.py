"""Rotas da página WhatsApp Comercial (WasenderAPI)."""
from pathlib import Path
from typing import Optional

from flask import render_template, request, jsonify, session, current_app, send_file, abort, url_for

from ..auth import login_required
from ..services.wasender_service import (
    WasenderApiError,
    _desembrulhar_mensagem,
    arquivo_audio_completo,
    detectar_midia_mensagem,
    enviar_mensagem_audio,
    enviar_mensagem_texto,
    label_midia,
    processar_midia_inbound,
    salvar_audio_outbound_upload,
)
from ..db import normalizar_telefone_whatsapp
from . import bp
from . import db_whatsapp as wa


def _jsonify_rows(rows):
    out = []
    for row in rows or []:
        d = dict(row)
        for k, v in list(d.items()):
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
        _enriquecer_midia_mensagem(d)
        out.append(d)
    return out


def _media_url_publica(path: str) -> str:
    """URL absoluta para arquivos locais (player no browser)."""
    if not path:
        return ''
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return _public_app_url(path)


def _reconstruir_message_data(payload):
    """Extrai estrutura de mensagem do payload Wasender (vários formatos)."""
    if not isinstance(payload, dict):
        return None
    cached = payload.get('_message_data')
    if isinstance(cached, dict):
        return cached
    data = payload.get('data')
    if not isinstance(data, dict):
        return None
    messages = data.get('messages')
    if isinstance(messages, dict):
        return messages
    key = data.get('key')
    message = data.get('message')
    if isinstance(key, dict) and isinstance(message, dict):
        out = {'key': key, 'message': message}
        mb = data.get('messageBody')
        if mb:
            out['messageBody'] = mb
        return out
    return None


def _caminho_static_relativo(rel_path: str) -> Optional[Path]:
    if not rel_path or not str(rel_path).startswith('/static/'):
        return None
    rel = str(rel_path).lstrip('/')
    if rel.startswith('static/'):
        rel = rel[len('static/'):]
    static_root = current_app.static_folder or 'static'
    return Path(static_root) / rel


def _arquivo_midia_valido(rel_path: str, min_bytes: int = 256) -> bool:
    path = _caminho_static_relativo(rel_path)
    if not path or not path.is_file():
        return False
    try:
        return path.stat().st_size >= min_bytes
    except OSError:
        return False


def _url_midia_utilizavel(media):
    """Só URLs locais/permanentes — URLs temporárias da Wasender expiram."""
    if not isinstance(media, dict):
        return None
    local = media.get('local_url')
    if local and _arquivo_midia_valido(local):
        return local
    url = (media.get('url') or '').strip()
    if not url:
        return None
    base = (current_app.config.get('BASE_URL') or '').rstrip('/')
    if base and url.startswith(base):
        return url
    if url.startswith('/static/'):
        return url
    return None


def _segundos_esperados(media):
    if not isinstance(media, dict):
        return None
    raw = media.get('seconds')
    if raw is None:
        return None
    try:
        return max(1, int(float(raw)))
    except (TypeError, ValueError):
        return None


def _url_stream_audio(conversa_id, mensagem_id):
    return url_for(
        'whatsapp.api_stream_audio',
        conversa_id=conversa_id,
        mensagem_id=mensagem_id,
    )


def _garantir_arquivo_audio(msg):
    """Garante arquivo local completo; re-baixa inbound se truncado."""
    payload = msg.get('provider_payload') or {}
    if not isinstance(payload, dict):
        return None, None

    media = payload.get('_media') or {}
    expected = _segundos_esperados(media)
    local = media.get('local_url')
    mimetype = (media.get('mimetype') or 'audio/ogg').split(';')[0].strip()

    if local:
        path = _caminho_static_relativo(local)
        if msg.get('direcao') == 'outbound':
            if path and '/outbound/' in str(local) and path.is_file():
                return path, mimetype
            return None, None
        if path and arquivo_audio_completo(path, expected):
            return path, mimetype
        if path and path.is_file():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    if msg.get('direcao') == 'outbound':
        return None, None

    message_data = _reconstruir_message_data(payload)
    if not message_data:
        return None, None

    api_key = (current_app.config.get('WASENDER_API_KEY') or '').strip()
    if not api_key:
        return None, None

    media_meta = processar_midia_inbound(api_key, message_data)
    if not media_meta or not media_meta.get('local_url'):
        return None, None

    payload_update = dict(payload)
    payload_update['_message_data'] = message_data
    payload_update['_media'] = media_meta
    wa.atualizar_mensagem_media_meta(msg['id'], payload_update)

    path = _caminho_static_relativo(media_meta['local_url'])
    mimetype = (media_meta.get('mimetype') or 'audio/ogg').split(';')[0].strip()
    if path and path.is_file():
        return path, mimetype
    return None, None


def _aplicar_midia_enriquecida(d, media):
    if not isinstance(media, dict):
        return d
    url = _url_midia_utilizavel(media)
    d['media_type'] = media.get('type')
    if url:
        d['media_url'] = _media_url_publica(url)
    if media.get('seconds') is not None:
        d['media_seconds'] = media.get('seconds')
    if media.get('ptt'):
        d['media_ptt'] = True
    if media.get('mimetype'):
        d['media_mimetype'] = media.get('mimetype')
    return d


def _finalizar_urls_audio(d):
    texto = (d.get('texto') or '').strip()
    if not d.get('media_type') and texto in ('[Áudio de voz]', '[Áudio]', '[audio]'):
        d['media_type'] = 'audio'
        d['media_ptt'] = True
    if d.get('media_type') == 'audio' and d.get('id') and d.get('conversa_id'):
        d['media_url'] = _url_stream_audio(d['conversa_id'], d['id'])
        d['media_repairable'] = False
    return d


def _enriquecer_midia_mensagem(d):
    """Enriquece resposta JSON com metadados de mídia já persistidos (sem rede)."""
    try:
        payload = d.get('provider_payload')
        if not isinstance(payload, dict):
            return _finalizar_urls_audio(d)

        media = payload.get('_media')
        if isinstance(media, dict):
            d = _aplicar_midia_enriquecida(d, media)
            if not d.get('media_url') and _reconstruir_message_data(payload):
                d['media_repairable'] = True
            return _finalizar_urls_audio(d)

        message_data = _reconstruir_message_data(payload)
        if isinstance(message_data, dict):
            media_type, media_info = detectar_midia_mensagem(message_data)
            if media_type:
                _aplicar_midia_enriquecida(d, {
                    'type': media_type,
                    'seconds': (media_info or {}).get('seconds'),
                    'ptt': (media_info or {}).get('ptt'),
                })
                d['media_repairable'] = not d.get('media_url')
    except Exception as exc:
        current_app.logger.warning('Falha ao enriquecer mídia msg=%s: %s', d.get('id'), exc)
    return _finalizar_urls_audio(d)


def _webhook_secret_ok():
    expected = (current_app.config.get('WASENDER_WEBHOOK_SECRET') or '').strip()
    auth = request.headers.get('Authorization', '')
    provided = (
        request.headers.get('X-Webhook-Signature')
        or request.headers.get('X-Wasender-Secret')
        or request.headers.get('X-Webhook-Secret')
        or request.args.get('secret')
        or ''
    ).strip()
    if auth.lower().startswith('bearer '):
        provided = auth.split(' ', 1)[1].strip()
    if not expected:
        current_app.logger.warning('WASENDER_WEBHOOK_SECRET não configurado; webhook Wasender bloqueado.')
        return False
    if provided != expected:
        current_app.logger.warning(
            'Wasender webhook (whatsapp) rejeitado: secret inválido (headers: %s)',
            {k: v for k, v in request.headers.items() if 'webhook' in k.lower() or 'wasender' in k.lower()},
        )
        return False
    return True


def _normalizar_provider_status(raw):
    """Converte códigos Wasender (0-5) e strings para sent/delivered/read."""
    if raw is None:
        return None
    val = str(raw).strip()
    mapping = {
        '0': 'error', '1': 'pending', '2': 'sent', '3': 'delivered', '4': 'read', '5': 'played',
        'ERROR': 'error', 'PENDING': 'pending', 'SENT': 'sent',
        'DELIVERED': 'delivered', 'READ': 'read', 'PLAYED': 'played',
        'error': 'error', 'pending': 'pending', 'sent': 'sent',
        'delivered': 'delivered', 'read': 'read', 'played': 'played',
        'failed': 'error', 'in_progress': 'sent', 'IN_PROGRESS': 'sent',
        'received': 'received',
    }
    if val in mapping:
        return mapping[val]
    lower = val.lower()
    return mapping.get(lower, lower)


def _wasender_message_from_payload(payload):
    """Wasender envia data.messages como objeto (não array) desde 2024+."""
    data = payload.get('data') if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return None
    messages = data.get('messages')
    if isinstance(messages, dict):
        return messages
    if isinstance(messages, list):
        return messages[0] if messages else None
    # fallback: data já é a mensagem
    if data.get('key') or data.get('messageBody') or data.get('message'):
        return data
    return None


def _wasender_message_id(payload, message_data=None):
    message_data = message_data or _wasender_message_from_payload(payload) or {}
    if isinstance(message_data, dict):
        key = message_data.get('key')
        if isinstance(key, dict) and key.get('id'):
            return str(key['id'])
    data = payload.get('data') if isinstance(payload, dict) else {}
    if isinstance(data, dict):
        key = data.get('key')
        if isinstance(key, dict) and key.get('id'):
            return str(key['id'])
        for k in ('id', 'message_id', 'messageId', 'msgId'):
            if data.get(k):
                return str(data[k])
    if isinstance(message_data, dict):
        for k in ('id', 'message_id', 'messageId', 'msgId'):
            if message_data.get(k):
                return str(message_data[k])
    return None


def _wasender_provider_status(payload):
    data = payload.get('data') if isinstance(payload, dict) else {}
    if isinstance(data, dict):
        update = data.get('update')
        if isinstance(update, dict) and update.get('status') is not None:
            return _normalizar_provider_status(update.get('status'))
        receipt = data.get('receipt')
        if isinstance(receipt, dict):
            if receipt.get('readTimestamp'):
                return 'read'
            if receipt.get('receiptTimestamp'):
                return 'delivered'
        for k in ('status', 'message_status', 'messageStatus'):
            if data.get(k) is not None:
                return _normalizar_provider_status(data.get(k))
    for source in (payload,):
        if isinstance(source, dict):
            for k in ('status', 'message_status', 'messageStatus'):
                if source.get(k) is not None:
                    return _normalizar_provider_status(source.get(k))
    return None


def _extrair_nome_remetente(message_data):
    if not isinstance(message_data, dict):
        return None
    for key in ('pushName', 'notifyName', 'senderName', 'name'):
        val = message_data.get(key)
        if val:
            return str(val).strip()
    return None


def _extrair_texto_mensagem(message_data):
    if not isinstance(message_data, dict):
        return ''
    media_type, media_info = detectar_midia_mensagem(message_data)
    if media_type and isinstance(media_info, dict):
        caption = (media_info.get('caption') or '').strip()
        if caption:
            return caption
    texto = (message_data.get('messageBody') or '').strip()
    placeholders = {
        '[gif]', '[imagem]', '[image]', '[vídeo]', '[video]', '[sticker]',
        '[áudio]', '[audio]', '[áudio de voz]', '[audio de voz]',
        'audio', 'áudio', 'voice message', 'voice note', 'mensagem de voz',
    }
    if media_type and (not texto or texto.lower() in placeholders):
        return label_midia(media_type, media_info)
    if texto:
        return texto
    raw_msg = message_data.get('message') or {}
    if isinstance(raw_msg, dict):
        inner = _desembrulhar_mensagem(raw_msg)
        texto = (inner.get('conversation') or '').strip()
        if texto:
            return texto
        ext = inner.get('extendedTextMessage')
        if isinstance(ext, dict):
            return (ext.get('text') or '').strip()
        reaction = inner.get('reactionMessage')
        if isinstance(reaction, dict):
            emoji = (reaction.get('text') or '').strip()
            if emoji:
                return emoji
        if media_type:
            return label_midia(media_type, media_info)
    return ''


def _wasender_reaction_from_payload(payload):
    """Wasender envia messages.reaction com data como array (não data.messages)."""
    data = payload.get('data') if isinstance(payload, dict) else None
    items = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    for item in items:
        if not isinstance(item, dict):
            continue
        reaction = item.get('reaction')
        if not isinstance(reaction, dict):
            continue
        emoji = (reaction.get('text') or '').strip()
        if not emoji:
            continue
        key = item.get('key') or reaction.get('key') or {}
        return emoji, key
    return None, None


def _telefone_de_remote_jid(remote):
    if not remote or not isinstance(remote, str):
        return None
    if '@' in remote:
        return normalizar_telefone_whatsapp(remote.split('@')[0])
    return normalizar_telefone_whatsapp(remote)


def _extrair_telefone_key(key):
    """Contato da conversa: remetente (inbound) ou destinatário (outbound fromMe)."""
    if not isinstance(key, dict):
        return None
    from_me = key.get('fromMe') is True
    if from_me:
        tel = _telefone_de_remote_jid(key.get('remoteJid') or '')
        if tel:
            return tel
    sender = key.get('cleanedSenderPn') or key.get('cleanedParticipantPn') or ''
    if sender:
        return normalizar_telefone_whatsapp(sender)
    return _telefone_de_remote_jid(key.get('remoteJid') or '')


def _telefone_destino_payload(payload, message_data=None):
    data = payload.get('data') if isinstance(payload, dict) else {}
    if isinstance(data, dict):
        key = data.get('key')
        if isinstance(key, dict):
            tel = _extrair_telefone_key(key)
            if tel:
                return tel
    message_data = message_data or _wasender_message_from_payload(payload) or {}
    key = message_data.get('key') if isinstance(message_data, dict) else {}
    return _extrair_telefone_key(key)


def _processar_status_webhook(payload, event, provider_message_id, message_data=None):
    status = _wasender_provider_status(payload)
    telefone = _telefone_destino_payload(payload, message_data)
    current_app.logger.info(
        'Wasender status update: event=%s msg_id=%s status=%s tel=%s',
        event, provider_message_id, status, telefone,
    )
    updated = wa._aplicar_status_update(
        provider_message_id,
        status,
        provider_payload=payload,
        telefone_destino=telefone,
    )
    if not updated and provider_message_id:
        current_app.logger.warning(
            'Wasender status não aplicado: msg_id=%s status=%s',
            provider_message_id, status,
        )
    return updated


def _processar_reaction(payload, event):
    emoji, key = _wasender_reaction_from_payload(payload)
    if not emoji:
        return {'success': True, 'ignored': True, 'reason': 'empty_reaction'}
    if isinstance(key, dict) and key.get('fromMe') is True:
        return {'success': True, 'ignored': True, 'reason': 'from_me'}

    telefone = _extrair_telefone_key(key)
    if not telefone:
        return {'success': True, 'ignored': True, 'reason': 'missing_sender'}

    provider_message_id = None
    if isinstance(key, dict) and key.get('id'):
        provider_message_id = f"reaction:{key['id']}:{emoji}"

    if provider_message_id and wa.mensagem_provider_existe(provider_message_id):
        return {'success': True, 'duplicate': True, 'reason': 'provider_id_exists'}

    conversa_id = wa.obter_ou_criar_conversa_por_telefone(telefone)
    if wa.mensagem_inbound_duplicada(conversa_id, emoji, provider_message_id):
        return {'success': True, 'duplicate': True, 'reason': 'recent_inbound'}

    msg_id = wa.criar_mensagem(
        conversa_id,
        emoji,
        direcao='inbound',
        status='recebido',
        provider='wasenderapi',
        provider_message_id=provider_message_id,
        provider_status='received',
        provider_payload=payload,
        incrementar_unread=True,
    )
    current_app.logger.info(
        'Wasender reaction (whatsapp) salva: event=%s conversa=%s msg=%s telefone=%s emoji=%s',
        event, conversa_id, msg_id, telefone, emoji,
    )
    return {'success': True, 'id': msg_id, 'conversa_id': conversa_id, 'reaction': True}


def _processar_inbound(payload, message_data, provider_message_id, event):
    key = message_data.get('key') or {}
    if key.get('fromMe') is True:
        return {'success': True, 'ignored': True, 'reason': 'from_me'}

    telefone = _extrair_telefone_key(key)
    media_type, _ = detectar_midia_mensagem(message_data)
    texto = _extrair_texto_mensagem(message_data)
    if not telefone:
        return {'success': True, 'ignored': True, 'reason': 'missing_sender'}
    if not texto and not media_type:
        msg_keys = list((_desembrulhar_mensagem(message_data.get('message') or {})).keys())
        current_app.logger.info(
            'Wasender inbound ignorado (missing_text): event=%s msg_id=%s keys=%s',
            event, provider_message_id, msg_keys,
        )
        return {'success': True, 'ignored': True, 'reason': 'missing_text'}

    if provider_message_id and wa.mensagem_provider_existe(provider_message_id):
        return {'success': True, 'duplicate': True, 'reason': 'provider_id_exists'}

    nome = _extrair_nome_remetente(message_data)
    conversa_id = wa.obter_ou_criar_conversa_por_telefone(telefone, nome_contato=nome)

    if wa.mensagem_inbound_duplicada(conversa_id, texto, provider_message_id):
        return {'success': True, 'duplicate': True, 'reason': 'recent_inbound'}

    payload_salvar = dict(payload) if isinstance(payload, dict) else {}
    payload_salvar['_message_data'] = message_data
    if media_type:
        api_key = (current_app.config.get('WASENDER_API_KEY') or '').strip()
        media_meta = processar_midia_inbound(api_key, message_data)
        if media_meta:
            payload_salvar['_media'] = media_meta
        else:
            current_app.logger.warning(
                'Wasender inbound mídia não descriptografada: tipo=%s msg_id=%s',
                media_type, provider_message_id,
            )

    msg_id = wa.criar_mensagem(
        conversa_id,
        texto,
        direcao='inbound',
        status='recebido',
        provider='wasenderapi',
        provider_message_id=provider_message_id,
        provider_status='received',
        provider_payload=payload_salvar,
        incrementar_unread=True,
    )
    current_app.logger.info(
        'Wasender inbound (whatsapp) salvo: event=%s conversa=%s msg=%s telefone=%s media=%s',
        event, conversa_id, msg_id, telefone, media_type,
    )
    return {'success': True, 'id': msg_id, 'conversa_id': conversa_id}


def _processar_outbound_upsert(message_data, provider_message_id):
    """Registra o key.id real do WhatsApp na mensagem enviada (substitui ID numérico da API)."""
    if not provider_message_id:
        return {'success': True, 'ignored': True, 'reason': 'no_provider_id'}
    key = message_data.get('key') or {}
    telefone = _extrair_telefone_key(key)
    if not telefone:
        return {'success': True, 'ignored': True, 'reason': 'no_telefone'}
    conversa = wa.obter_conversa_por_telefone(telefone)
    if not conversa:
        return {'success': True, 'ignored': True, 'reason': 'conversa_not_found'}
    texto = _extrair_texto_mensagem(message_data)
    linked = wa.registrar_provider_id_saida(conversa['id'], provider_message_id, texto or None)
    if linked:
        wa.atualizar_mensagem_provider(
            provider_message_id=provider_message_id,
            provider_status='sent',
        )
    return {'success': True, 'linked': linked}


@bp.route('/')
@login_required
def index():
    return render_template('whatsapp/whatsapp.html')


@bp.route('/api/conversas')
@login_required
def api_listar_conversas():
    busca = (request.args.get('busca') or '').strip() or None
    tab = (request.args.get('tab') or 'todas').strip()
    apenas_nao_lidas = tab == 'nao_lidas'
    try:
        conversas = wa.listar_conversas(busca=busca, apenas_nao_lidas=apenas_nao_lidas)
        return jsonify({'success': True, 'conversas': _jsonify_rows(conversas)})
    except Exception as e:
        current_app.logger.error('Erro api_listar_conversas whatsapp: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/conversas', methods=['POST'])
@login_required
def api_criar_conversa():
    data = request.get_json() or {}
    telefone = (data.get('telefone') or '').strip()
    nome_contato = (data.get('nome_contato') or '').strip() or None
    if not telefone:
        return jsonify({'success': False, 'error': 'Telefone obrigatório.'}), 400
    try:
        conversa_id = wa.criar_conversa(telefone, nome_contato=nome_contato, created_by=session.get('user_id'))
        conversa = wa.obter_conversa(conversa_id)
        rows = _jsonify_rows([conversa] if conversa else [])
        return jsonify({'success': True, 'id': conversa_id, 'conversa': rows[0] if rows else None})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error('Erro api_criar_conversa whatsapp: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/conversas/<int:conversa_id>/mensagens')
@login_required
def api_listar_mensagens(conversa_id):
    try:
        conversa = wa.obter_conversa(conversa_id)
        if not conversa:
            return jsonify({'success': False, 'error': 'Conversa não encontrada.'}), 404
        mensagens = wa.listar_mensagens(conversa_id)
        return jsonify({'success': True, 'mensagens': _jsonify_rows(mensagens)})
    except Exception as e:
        current_app.logger.error('Erro api_listar_mensagens whatsapp: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def _public_app_url(path: str) -> str:
    base = (current_app.config.get('BASE_URL') or '').rstrip('/')
    if not base:
        base = request.url_root.rstrip('/')
    if not path.startswith('/'):
        path = f'/{path}'
    return f'{base}{path}'


def _reparar_midia_mensagem(mensagem_id, conversa_id):
    """Descriptografa e persiste mídia ausente (somente inbound)."""
    msg = wa.obter_mensagem(mensagem_id, conversa_id)
    if not msg:
        return None, 'Mensagem não encontrada.'
    if msg.get('direcao') == 'outbound':
        payload = msg.get('provider_payload') or {}
        media = payload.get('_media') if isinstance(payload, dict) else None
        if isinstance(media, dict) and _url_midia_utilizavel(media):
            row = dict(msg)
            _enriquecer_midia_mensagem(row)
            return row, None
        return None, 'Áudio enviado indisponível no servidor (arquivo outbound não encontrado).'

    payload = msg.get('provider_payload') or {}
    if not isinstance(payload, dict):
        payload = {}

    media = payload.get('_media')
    if isinstance(media, dict) and _url_midia_utilizavel(media):
        row = dict(msg)
        _enriquecer_midia_mensagem(row)
        return row, None

    message_data = _reconstruir_message_data(payload)
    if not message_data:
        return None, 'Metadados de mídia indisponíveis para esta mensagem.'

    api_key = (current_app.config.get('WASENDER_API_KEY') or '').strip()
    if not api_key:
        return None, 'WASENDER_API_KEY não configurada.'

    media_meta = processar_midia_inbound(api_key, message_data)
    if not media_meta or not _url_midia_utilizavel(media_meta):
        return None, 'Não foi possível descriptografar o áudio.'

    payload = dict(payload)
    payload['_message_data'] = message_data
    payload['_media'] = media_meta
    wa.atualizar_mensagem_media_meta(mensagem_id, payload)

    row = dict(msg)
    row['provider_payload'] = payload
    _enriquecer_midia_mensagem(row)
    return row, None


@bp.route('/api/conversas/<int:conversa_id>/mensagens/<int:mensagem_id>/audio')
@login_required
def api_stream_audio(conversa_id, mensagem_id):
    """Serve áudio validado; re-baixa do Wasender se o arquivo local estiver truncado."""
    try:
        msg = wa.obter_mensagem(mensagem_id, conversa_id)
        if not msg:
            abort(404)
        path, mimetype = _garantir_arquivo_audio(msg)
        if not path:
            abort(404)
        return send_file(
            path,
            mimetype=mimetype or 'audio/ogg',
            conditional=True,
            download_name=path.name,
        )
    except Exception as e:
        current_app.logger.error('Erro api_stream_audio whatsapp: %s', e, exc_info=True)
        abort(500)


@bp.route('/api/conversas/<int:conversa_id>/mensagens/<int:mensagem_id>/reparar-midia', methods=['POST'])
@login_required
def api_reparar_midia(conversa_id, mensagem_id):
    try:
        conversa = wa.obter_conversa(conversa_id)
        if not conversa:
            return jsonify({'success': False, 'error': 'Conversa não encontrada.'}), 404
        row, err = _reparar_midia_mensagem(mensagem_id, conversa_id)
        if err:
            return jsonify({'success': False, 'error': err}), 422
        for k, v in list(row.items()):
            if hasattr(v, 'isoformat'):
                row[k] = v.isoformat()
        return jsonify({'success': True, 'mensagem': row})
    except Exception as e:
        current_app.logger.error('Erro api_reparar_midia whatsapp: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/conversas/<int:conversa_id>/mensagens', methods=['POST'])
@login_required
def api_enviar_mensagem(conversa_id):
    audio_file = request.files.get('audio')
    data = request.get_json(silent=True) or {}
    texto = (data.get('texto') or request.form.get('texto') or '').strip()

    if not texto and not audio_file:
        return jsonify({'success': False, 'error': 'Mensagem ou áudio obrigatório.'}), 400

    api_key = (current_app.config.get('WASENDER_API_KEY') or '').strip()
    if not api_key:
        return jsonify({'success': False, 'error': 'WASENDER_API_KEY não configurada no .env.'}), 503

    try:
        conversa = wa.obter_conversa(conversa_id)
        if not conversa:
            return jsonify({'success': False, 'error': 'Conversa não encontrada.'}), 404

        destino = normalizar_telefone_whatsapp(conversa.get('telefone'))
        if not destino:
            return jsonify({'success': False, 'error': 'Conversa sem telefone de destino.'}), 400

        provider_payload_extra = None
        media_meta = None

        try:
            if audio_file:
                rel_path, mimetype = salvar_audio_outbound_upload(audio_file)
                if mimetype == 'audio/webm':
                    current_app.logger.warning(
                        'Áudio outbound permanece WebM (instale ffmpeg no servidor para converter para OGG).'
                    )
                audio_url = _public_app_url(rel_path)
                provider_meta = enviar_mensagem_audio(api_key, destino, audio_url)
                texto_salvar = '[Áudio de voz]'
                seconds = None
                duration_raw = (request.form.get('duration') or '').strip()
                if duration_raw:
                    try:
                        seconds = max(1, int(float(duration_raw.replace(',', '.'))))
                    except ValueError:
                        seconds = None
                media_meta = {
                    'type': 'audio',
                    'ptt': True,
                    'local_url': rel_path,
                    'url': audio_url,
                    'mimetype': mimetype,
                    'seconds': seconds,
                }
                provider_payload_extra = {'_media': media_meta, 'audioUrl': audio_url}
            else:
                provider_meta = enviar_mensagem_texto(api_key, destino, texto)
                texto_salvar = texto

            provider_status = _normalizar_provider_status(provider_meta.get('provider_status')) or 'sent'
            payload_salvar = dict(provider_meta.get('provider_payload') or {})
            if provider_payload_extra:
                payload_salvar.update(provider_payload_extra)

            msg_id = wa.criar_mensagem(
                conversa_id,
                texto_salvar,
                direcao='outbound',
                status='enviado',
                created_by=session.get('user_id'),
                provider=provider_meta.get('provider'),
                provider_message_id=provider_meta.get('provider_message_id'),
                provider_status=provider_status,
                provider_payload=payload_salvar,
            )
            if not provider_meta.get('provider_message_id'):
                current_app.logger.warning(
                    'Wasender send sem provider_message_id: conversa=%s — status virá via webhook upsert/update',
                    conversa_id,
                )
        except WasenderApiError as exc:
            texto_erro = texto or '[Áudio de voz]'
            msg_id = wa.criar_mensagem(
                conversa_id,
                texto_erro,
                direcao='outbound',
                status='erro',
                created_by=session.get('user_id'),
                provider='wasenderapi',
                provider_status='failed',
                provider_payload={'error': str(exc)},
            )
            mensagens = wa.listar_mensagens(conversa_id)
            return jsonify({
                'success': False,
                'id': msg_id,
                'error': str(exc),
                'mensagens': _jsonify_rows(mensagens),
            }), 502

        mensagens = wa.listar_mensagens(conversa_id)
        return jsonify({'success': True, 'id': msg_id, 'mensagens': _jsonify_rows(mensagens)})
    except Exception as e:
        current_app.logger.error('Erro api_enviar_mensagem whatsapp: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/conversas/<int:conversa_id>/status', methods=['PATCH'])
@login_required
def api_atualizar_status(conversa_id):
    data = request.get_json() or {}
    status = (data.get('status') or 'aberta').strip() or 'aberta'
    unread_count = data.get('unread_count')
    try:
        ok = wa.atualizar_conversa_status(conversa_id, status, unread_count)
        if not ok:
            return jsonify({'success': False, 'error': 'Conversa não encontrada.'}), 404
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error('Erro api_atualizar_status whatsapp: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/wasender/webhook', methods=['POST'])
def api_wasender_webhook():
    if not _webhook_secret_ok():
        return jsonify({'success': False, 'error': 'Webhook não autorizado.'}), 401

    payload = request.get_json(silent=True) or {}
    event = (payload.get('event') or '').strip()
    current_app.logger.info('Wasender webhook (whatsapp) recebido: event=%s', event or '(vazio)')
    message_data = _wasender_message_from_payload(payload)
    provider_message_id = _wasender_message_id(payload, message_data)

    if event and event not in (
        'messages.received', 'messages.upsert', 'messages.update',
        'messages.reaction',
        'message.status', 'messages.status', 'message-receipt.update',
    ):
        return jsonify({'success': True, 'ignored': True, 'reason': 'event_not_handled'})

    try:
        if event == 'messages.reaction':
            result = _processar_reaction(payload, event)
            return jsonify(result)

        # Atualizações de status (entregue / lida)
        if event in ('messages.update', 'message.status', 'messages.status', 'message-receipt.update'):
            updated = _processar_status_webhook(payload, event, provider_message_id, message_data)
            return jsonify({'success': True, 'updated': updated})

        if not message_data:
            return jsonify({'success': True, 'ignored': True, 'reason': 'no_message'})

        key = message_data.get('key') or {}
        from_me = key.get('fromMe') is True

        # Echo da mensagem enviada — vincula ID para status ✓✓ funcionar
        if event == 'messages.upsert' and from_me:
            result = _processar_outbound_upsert(message_data, provider_message_id)
            return jsonify(result)

        # Mensagem inbound (received ou upsert — dedupe evita duplicata)
        if event in ('messages.received', 'messages.upsert') and not from_me:
            result = _processar_inbound(payload, message_data, provider_message_id, event)
            return jsonify(result)

        return jsonify({'success': True, 'ignored': True, 'reason': 'event_not_handled'})
    except Exception as e:
        current_app.logger.error('Erro api_wasender_webhook whatsapp: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
