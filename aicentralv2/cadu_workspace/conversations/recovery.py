"""Idempotency and narrowly scoped projections; never restart a provider run."""
import hashlib
import json

from flask import abort

from ...cadu_family import repository


def fingerprint(data):
    payload = {key: data.get(key) for key in ('message', 'mode', 'profile', 'conversation_id', 'files')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def existing_run(cur, run_id, user, client_id, request_hash):
    # Serialize this key across organizations as well as within a conversation.
    # A retry must be checked BEFORE the organization busy/balance checks.
    cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (run_id,))
    cur.execute('''SELECT r.id AS run_id, r.conversation_id, r.status, r.user_id,
                          r.client_id, r.request_hash, c.organization_id
                     FROM cadu_family_chat_runs r
                     JOIN cadu_family_conversation_context c ON c.conversation_id = r.conversation_id
                    WHERE r.id = %s''', (run_id,))
    row = cur.fetchone()
    if row is None:
        return None
    if (row['user_id'], row['client_id'], row['organization_id']) != (
            user['id'], client_id, user['organization_id']):
        abort(409, description='Identificador de envio indisponível.')
    if not row['request_hash'] or row['request_hash'] != request_hash:
        abort(409, description='Este identificador já foi usado em outro envio. Consulte o histórico.')
    return {'run_id': str(row['run_id']), 'conversation_id': row['conversation_id'],
            'status': row['status'], 'recovered': True}


def state(run_id, user, client_id):
    rows = repository.rows('''SELECT r.id AS run_id, r.conversation_id, r.status,
                                    r.created_at, r.finished_at
                               FROM cadu_family_chat_runs r
                               JOIN cadu_family_conversation_context c ON c.conversation_id = r.conversation_id
                               JOIN cadu_conversations t ON t.id = r.conversation_id
                              WHERE r.id = %s AND r.user_id = %s AND r.client_id = %s
                                AND c.organization_id = %s AND c.user_id = %s AND c.client_id = %s
                                AND t.id_contato_cliente = %s AND t.id_cliente = %s''',
                           (run_id, user['id'], client_id, user['organization_id'],
                            user['id'], client_id, user['id'], client_id))
    return rows[0] if rows else None
