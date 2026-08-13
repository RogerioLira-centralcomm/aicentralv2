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


def _wasender_message_from_payload(payload):
    data = payload.get('data') if isinstance(payload, dict) else {}
    messages = data.get('messages') if isinstance(data, dict) else None
    if isinstance(messages, list):
        return messages[0] if messages else None
    if isinstance(messages, dict):
        return messages
    return None


def _wasender_message_id(payload, message_data=None):
    message_data = message_data or _wasender_message_from_payload(payload) or {}
    key = message_data.get('key') if isinstance(message_data, dict) else {}
    for source in (key, message_data, payload.get('data') if isinstance(payload, dict) else {}, payload):
        if isinstance(source, dict):
            for k in ('id', 'message_id', 'messageId', 'msgId'):
                if source.get(k):
                    return str(source[k])
    return None


def _wasender_provider_status(payload):
    for source in (payload.get('data') if isinstance(payload, dict) else {}, payload):
        if isinstance(source, dict):
            for k in ('status', 'message_status', 'messageStatus'):
                if source.get(k):
                    return str(source[k])
    return payload.get('event') if isinstance(payload, dict) else None


def _extrair_nome_remetente(message_data):
    if not isinstance(message_data, dict):
        return None
    for key in ('pushName', 'notifyName', 'senderName', 'name'):
        val = message_data.get(key)
        if val:
            return str(val).strip()
    return None


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
            msg_id = wa.criar_mensagem(
                conversa_id,
                texto,
                direcao='outbound',
                status='enviado',
                created_by=session.get('user_id'),
                provider=provider_meta.get('provider'),
                provider_message_id=provider_meta.get('provider_message_id'),
                provider_status=provider_meta.get('provider_status'),
                provider_payload=provider_meta.get('provider_payload'),
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
        'message.status', 'messages.status',
    ):
        return jsonify({'success': True, 'ignored': True, 'reason': 'event_not_handled'})

    if event in ('messages.update', 'message.status', 'messages.status'):
        updated = wa.atualizar_mensagem_provider(
            provider_message_id=provider_message_id,
            provider_status=_wasender_provider_status(payload),
            provider_payload=payload,
        )
        return jsonify({'success': True, 'updated': updated})

    if not message_data:
        if provider_message_id:
            updated = wa.atualizar_mensagem_provider(
                provider_message_id=provider_message_id,
                provider_status=_wasender_provider_status(payload),
                provider_payload=payload,
            )
            return jsonify({'success': True, 'updated': updated})
        return jsonify({'success': True, 'ignored': True, 'reason': 'no_message'})

    key = message_data.get('key') or {}
    if key.get('fromMe') is True:
        return jsonify({'success': True, 'ignored': True, 'reason': 'from_me'})

    sender = key.get('cleanedSenderPn') or key.get('cleanedParticipantPn') or ''
    if not sender:
        remote = key.get('remoteJid') or ''
        if isinstance(remote, str) and '@' in remote:
            sender = remote.split('@')[0]
        elif remote:
            sender = remote

    texto = (message_data.get('messageBody') or '').strip()
    if not texto:
        raw_msg = message_data.get('message') or {}
        if isinstance(raw_msg, dict):
            texto = (raw_msg.get('conversation') or '').strip()
            if not texto and raw_msg.get('extendedTextMessage'):
                texto = (raw_msg['extendedTextMessage'].get('text') or '').strip()

    if not sender:
        return jsonify({'success': True, 'ignored': True, 'reason': 'missing_sender'})

    if not texto:
        return jsonify({'success': True, 'ignored': True, 'reason': 'missing_text'})

    try:
        if provider_message_id and wa.mensagem_provider_existe(provider_message_id):
            wa.atualizar_mensagem_provider(
                provider_message_id=provider_message_id,
                provider_status='received',
                provider_payload=payload,
            )
            return jsonify({'success': True, 'duplicate': True})

        telefone = normalizar_telefone_whatsapp(sender)
        nome = _extrair_nome_remetente(message_data)
        conversa_id = wa.obter_ou_criar_conversa_por_telefone(telefone, nome_contato=nome)
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
            'Wasender inbound (whatsapp) salvo: conversa=%s msg=%s telefone=%s',
            conversa_id, msg_id, telefone,
        )
        return jsonify({'success': True, 'id': msg_id, 'conversa_id': conversa_id})
    except Exception as e:
        current_app.logger.error('Erro api_wasender_webhook whatsapp: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
