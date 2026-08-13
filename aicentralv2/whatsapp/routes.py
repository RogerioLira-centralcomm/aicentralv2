"""Rotas da página WhatsApp Comercial (WasenderAPI)."""
from flask import render_template, request, jsonify, session, current_app

from ..auth import login_required
from ..services.wasender_service import WasenderApiError, enviar_mensagem_texto
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
        out.append(d)
    return out


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
    texto = (message_data.get('messageBody') or '').strip()
    if texto:
        return texto
    raw_msg = message_data.get('message') or {}
    if isinstance(raw_msg, dict):
        texto = (raw_msg.get('conversation') or '').strip()
        if texto:
            return texto
        ext = raw_msg.get('extendedTextMessage')
        if isinstance(ext, dict):
            return (ext.get('text') or '').strip()
    return ''


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


def _processar_inbound(payload, message_data, provider_message_id, event):
    key = message_data.get('key') or {}
    if key.get('fromMe') is True:
        return {'success': True, 'ignored': True, 'reason': 'from_me'}

    telefone = _extrair_telefone_key(key)
    texto = _extrair_texto_mensagem(message_data)
    if not telefone:
        return {'success': True, 'ignored': True, 'reason': 'missing_sender'}
    if not texto:
        return {'success': True, 'ignored': True, 'reason': 'missing_text'}

    if provider_message_id and wa.mensagem_provider_existe(provider_message_id):
        return {'success': True, 'duplicate': True, 'reason': 'provider_id_exists'}

    nome = _extrair_nome_remetente(message_data)
    conversa_id = wa.obter_ou_criar_conversa_por_telefone(telefone, nome_contato=nome)

    if wa.mensagem_inbound_duplicada(conversa_id, texto, provider_message_id):
        return {'success': True, 'duplicate': True, 'reason': 'recent_inbound'}

    msg_id = wa.criar_mensagem(
        conversa_id,
        texto,
        direcao='inbound',
        status='recebido',
        provider='wasenderapi',
        provider_message_id=provider_message_id,
        provider_status='received',
        provider_payload=payload,
        incrementar_unread=True,
    )
    current_app.logger.info(
        'Wasender inbound (whatsapp) salvo: event=%s conversa=%s msg=%s telefone=%s',
        event, conversa_id, msg_id, telefone,
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


@bp.route('/api/conversas/<int:conversa_id>/mensagens', methods=['POST'])
@login_required
def api_enviar_mensagem(conversa_id):
    data = request.get_json() or {}
    texto = (data.get('texto') or '').strip()
    if not texto:
        return jsonify({'success': False, 'error': 'Mensagem obrigatória.'}), 400

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

        try:
            provider_meta = enviar_mensagem_texto(api_key, destino, texto)
            provider_status = _normalizar_provider_status(provider_meta.get('provider_status')) or 'sent'
            msg_id = wa.criar_mensagem(
                conversa_id,
                texto,
                direcao='outbound',
                status='enviado',
                created_by=session.get('user_id'),
                provider=provider_meta.get('provider'),
                provider_message_id=provider_meta.get('provider_message_id'),
                provider_status=provider_status,
                provider_payload=provider_meta.get('provider_payload'),
            )
            if not provider_meta.get('provider_message_id'):
                current_app.logger.warning(
                    'Wasender send sem provider_message_id: conversa=%s — status virá via webhook upsert/update',
                    conversa_id,
                )
        except WasenderApiError as exc:
            msg_id = wa.criar_mensagem(
                conversa_id,
                texto,
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
        'message.status', 'messages.status', 'message-receipt.update',
    ):
        return jsonify({'success': True, 'ignored': True, 'reason': 'event_not_handled'})

    try:
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
