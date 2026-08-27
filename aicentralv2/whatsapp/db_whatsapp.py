"""Persistência de conversas e mensagens WhatsApp (página Comercial)."""
from psycopg.types.json import Json

from ..db import get_db, normalizar_telefone_whatsapp, variantes_telefone_whatsapp


def obter_conversa(conversa_id):
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT id, telefone, nome_contato, status, ultimo_preview,
                   ultimo_evento_em, unread_count, created_by, created_at, updated_at
            FROM whatsapp_conversas
            WHERE id = %s
        ''', (conversa_id,))
        return cursor.fetchone()


def listar_conversas(busca=None, apenas_nao_lidas=False):
    conn = get_db()
    with conn.cursor() as cursor:
        params = []
        filtros = []
        if apenas_nao_lidas:
            filtros.append('unread_count > 0')
        if busca:
            termo = f'%{busca.strip()}%'
            filtros.append('(telefone ILIKE %s OR COALESCE(nome_contato, \'\') ILIKE %s OR COALESCE(ultimo_preview, \'\') ILIKE %s)')
            params.extend([termo, termo, termo])
        where = f"WHERE {' AND '.join(filtros)}" if filtros else ''
        cursor.execute(f'''
            SELECT id, telefone, nome_contato, status, ultimo_preview,
                   ultimo_evento_em, unread_count, created_by, created_at, updated_at
            FROM whatsapp_conversas
            {where}
            ORDER BY ultimo_evento_em DESC NULLS LAST, created_at DESC
        ''', params)
        return cursor.fetchall()


def criar_conversa(telefone, nome_contato=None, created_by=None):
    telefone = normalizar_telefone_whatsapp(telefone) or str(telefone or '').strip()
    if not telefone:
        raise ValueError('Telefone obrigatório.')
    variantes = variantes_telefone_whatsapp(telefone)
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id
                FROM whatsapp_conversas
                WHERE regexp_replace(COALESCE(telefone, ''), '\\D', '', 'g') = ANY(%s::text[])
                ORDER BY created_at DESC
                LIMIT 1
            ''', (variantes,))
            existente = cursor.fetchone()
            if existente:
                if nome_contato:
                    cursor.execute('''
                        UPDATE whatsapp_conversas
                        SET nome_contato = COALESCE(%s, nome_contato),
                            updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                        WHERE id = %s
                    ''', (nome_contato, existente['id']))
                conn.commit()
                return existente['id']

            cursor.execute('''
                INSERT INTO whatsapp_conversas (telefone, nome_contato, created_by)
                VALUES (%s, %s, %s)
                RETURNING id
            ''', (telefone, nome_contato, created_by))
            novo_id = cursor.fetchone()['id']
        conn.commit()
        return novo_id
    except Exception:
        conn.rollback()
        raise


def obter_conversa_por_telefone(telefone):
    telefone = normalizar_telefone_whatsapp(telefone)
    if not telefone:
        return None
    variantes = variantes_telefone_whatsapp(telefone)
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT id, telefone, nome_contato, status, ultimo_preview,
                   ultimo_evento_em, unread_count, created_by, created_at, updated_at
            FROM whatsapp_conversas
            WHERE regexp_replace(COALESCE(telefone, ''), '\\D', '', 'g') = ANY(%s::text[])
            ORDER BY ultimo_evento_em DESC NULLS LAST
            LIMIT 1
        ''', (variantes,))
        return cursor.fetchone()


def obter_ou_criar_conversa_por_telefone(telefone, nome_contato=None):
    return criar_conversa(telefone, nome_contato=nome_contato)


def atualizar_conversa_status(conversa_id, status='aberta', unread_count=None):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if unread_count is None:
                cursor.execute('''
                    UPDATE whatsapp_conversas
                    SET status = %s, updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s RETURNING id
                ''', (status, conversa_id))
            else:
                cursor.execute('''
                    UPDATE whatsapp_conversas
                    SET status = %s, unread_count = %s,
                        updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s RETURNING id
                ''', (status, unread_count, conversa_id))
            row = cursor.fetchone()
        conn.commit()
        return row is not None
    except Exception:
        conn.rollback()
        raise


def listar_mensagens(conversa_id):
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT id, conversa_id, direcao, texto, status, provider,
                   provider_message_id, provider_status, provider_payload,
                   created_by, created_at
            FROM whatsapp_mensagens
            WHERE conversa_id = %s
            ORDER BY created_at ASC, id ASC
        ''', (conversa_id,))
        return cursor.fetchall()


def criar_mensagem(
    conversa_id,
    texto,
    direcao='outbound',
    status='enviado',
    created_by=None,
    provider=None,
    provider_message_id=None,
    provider_status=None,
    provider_payload=None,
    incrementar_unread=False,
):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id FROM whatsapp_conversas WHERE id = %s', (conversa_id,))
            if not cursor.fetchone():
                raise ValueError('Conversa não encontrada.')

            if incrementar_unread:
                cursor.execute('SELECT pg_advisory_xact_lock(%s)', (conversa_id,))

            if provider_message_id:
                cursor.execute(
                    'SELECT id FROM whatsapp_mensagens WHERE provider_message_id = %s LIMIT 1',
                    (provider_message_id,),
                )
                existente = cursor.fetchone()
                if existente:
                    conn.commit()
                    return existente['id']

            if incrementar_unread and not provider_message_id:
                cursor.execute('''
                    SELECT id FROM whatsapp_mensagens
                    WHERE conversa_id = %s AND direcao = 'inbound' AND texto = %s
                      AND created_at >= (CURRENT_TIMESTAMP - interval '60 seconds')
                    LIMIT 1
                ''', (conversa_id, texto))
                recente = cursor.fetchone()
                if recente:
                    conn.commit()
                    return recente['id']

            cursor.execute('''
                INSERT INTO whatsapp_mensagens
                    (conversa_id, direcao, texto, status, created_by,
                     provider, provider_message_id, provider_status, provider_payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (provider_message_id) WHERE provider_message_id IS NOT NULL
                    AND btrim(provider_message_id) <> '' DO NOTHING
                RETURNING id, created_at
            ''', (
                conversa_id, direcao, texto, status, created_by,
                provider, provider_message_id, provider_status,
                Json(provider_payload) if provider_payload is not None else None,
            ))
            msg = cursor.fetchone()
            if not msg and provider_message_id:
                cursor.execute(
                    'SELECT id FROM whatsapp_mensagens WHERE provider_message_id = %s LIMIT 1',
                    (provider_message_id,),
                )
                row = cursor.fetchone()
                conn.commit()
                return row['id'] if row else None

            if incrementar_unread:
                cursor.execute('''
                    UPDATE whatsapp_conversas
                    SET ultimo_preview = %s,
                        ultimo_evento_em = %s,
                        unread_count = COALESCE(unread_count, 0) + 1,
                        updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s
                ''', (texto[:240], msg['created_at'], conversa_id))
            else:
                cursor.execute('''
                    UPDATE whatsapp_conversas
                    SET ultimo_preview = %s,
                        ultimo_evento_em = %s,
                        updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
                    WHERE id = %s
                ''', (texto[:240], msg['created_at'], conversa_id))
        conn.commit()
        return msg['id']
    except Exception:
        conn.rollback()
        raise


def mensagem_provider_existe(provider_message_id):
    if not provider_message_id:
        return False
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM whatsapp_mensagens WHERE provider_message_id = %s LIMIT 1',
            (provider_message_id,),
        )
        return cursor.fetchone() is not None


def mensagem_inbound_duplicada(conversa_id, texto, provider_message_id=None, segundos=60):
    """Evita duplicata quando Wasender dispara received + upsert."""
    if provider_message_id and mensagem_provider_existe(provider_message_id):
        return True
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT id FROM whatsapp_mensagens
            WHERE conversa_id = %s
              AND direcao = 'inbound'
              AND texto = %s
              AND created_at >= (CURRENT_TIMESTAMP - make_interval(secs => %s))
            LIMIT 1
        ''', (conversa_id, texto, segundos))
        return cursor.fetchone() is not None


def registrar_provider_id_saida(conversa_id, provider_message_id, texto=None):
    """Substitui o provider_message_id da última outbound pelo key.id real do WhatsApp."""
    if not conversa_id or not provider_message_id:
        return False
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if texto:
                cursor.execute('''
                    UPDATE whatsapp_mensagens
                    SET provider_message_id = %s,
                        provider = COALESCE(provider, 'wasenderapi')
                    WHERE id = (
                        SELECT id FROM whatsapp_mensagens
                        WHERE conversa_id = %s AND direcao = 'outbound' AND texto = %s
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                    )
                    RETURNING id
                ''', (provider_message_id, conversa_id, texto))
            else:
                cursor.execute('''
                    UPDATE whatsapp_mensagens
                    SET provider_message_id = %s,
                        provider = COALESCE(provider, 'wasenderapi')
                    WHERE id = (
                        SELECT id FROM whatsapp_mensagens
                        WHERE conversa_id = %s AND direcao = 'outbound'
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                    )
                    RETURNING id
                ''', (provider_message_id, conversa_id))
            row = cursor.fetchone()
        conn.commit()
        return row is not None
    except Exception:
        conn.rollback()
        raise


def vincular_provider_id_saida(conversa_id, provider_message_id, texto=None):
    """Compat: vincula ID apenas se ainda não existir no banco."""
    if mensagem_provider_existe(provider_message_id):
        return True
    return registrar_provider_id_saida(conversa_id, provider_message_id, texto)


_STATUS_RANK = {
    'error': 0, 'pending': 1, 'sent': 2, 'delivered': 3, 'read': 4, 'played': 5,
}


def _status_rank(status):
    if not status:
        return 0
    return _STATUS_RANK.get(str(status).lower(), 0)


def _aplicar_status_update(provider_message_id, provider_status, provider_payload=None, telefone_destino=None):
    """Atualiza status; vincula key.id real se o banco ainda tiver ID numérico da API."""
    if not provider_message_id:
        return False
    if atualizar_mensagem_provider(
        provider_message_id=provider_message_id,
        provider_status=provider_status,
        provider_payload=provider_payload,
    ):
        return True
    if telefone_destino:
        conversa = obter_conversa_por_telefone(telefone_destino)
        if conversa:
            registrar_provider_id_saida(conversa['id'], provider_message_id)
            if atualizar_mensagem_provider(
                provider_message_id=provider_message_id,
                provider_status=provider_status,
                provider_payload=provider_payload,
            ):
                return True
            # fallback: última outbound da conversa (ID numérico antigo da API send)
            conn = get_db()
            try:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT id FROM whatsapp_mensagens
                        WHERE conversa_id = %s AND direcao = 'outbound'
                        ORDER BY created_at DESC, id DESC LIMIT 1
                    ''', (conversa['id'],))
                    row = cursor.fetchone()
                    if row:
                        cursor.execute('''
                            UPDATE whatsapp_mensagens
                            SET provider_message_id = %s
                            WHERE id = %s
                        ''', (provider_message_id, row['id']))
                conn.commit()
                if row:
                    return atualizar_mensagem_provider(
                        mensagem_id=row['id'],
                        provider_status=provider_status,
                        provider_payload=provider_payload,
                    )
            except Exception:
                conn.rollback()
                raise
    return False


def atualizar_mensagem_provider(
    mensagem_id=None,
    provider_message_id=None,
    provider_status=None,
    provider_payload=None,
):
    if not mensagem_id and not provider_message_id:
        return False
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if mensagem_id:
                cursor.execute(
                    'SELECT id, provider_status FROM whatsapp_mensagens WHERE id = %s',
                    (mensagem_id,),
                )
            else:
                cursor.execute(
                    'SELECT id, provider_status FROM whatsapp_mensagens WHERE provider_message_id = %s',
                    (provider_message_id,),
                )
            row = cursor.fetchone()
            if not row:
                return False

            novo_status = provider_status
            if provider_status and row.get('provider_status'):
                if _status_rank(provider_status) < _status_rank(row['provider_status']):
                    novo_status = row['provider_status']

            payload_json = Json(provider_payload) if provider_payload is not None else None
            if payload_json is not None:
                cursor.execute('''
                    UPDATE whatsapp_mensagens
                    SET provider_status = COALESCE(%s, provider_status),
                        provider_payload = %s::jsonb
                    WHERE id = %s RETURNING id
                ''', (novo_status, payload_json, row['id']))
            else:
                cursor.execute('''
                    UPDATE whatsapp_mensagens
                    SET provider_status = COALESCE(%s, provider_status)
                    WHERE id = %s RETURNING id
                ''', (novo_status, row['id']))
            updated = cursor.fetchone()
        conn.commit()
        return updated is not None
    except Exception:
        conn.rollback()
        raise


def atualizar_mensagem_media_meta(mensagem_id, provider_payload):
    """Persiste _media / _message_data após descriptografia tardia."""
    if not mensagem_id or not isinstance(provider_payload, dict):
        return False
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE whatsapp_mensagens
                SET provider_payload = %s::jsonb
                WHERE id = %s RETURNING id
            ''', (Json(provider_payload), mensagem_id))
            updated = cursor.fetchone()
        conn.commit()
        return updated is not None
    except Exception:
        conn.rollback()
        raise
