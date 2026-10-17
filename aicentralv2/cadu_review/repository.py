"""Registro das revisões: resumo e consumo, nunca o arquivo nem as linhas do plano."""
from __future__ import annotations

import hashlib
import json
import logging

logger = logging.getLogger(__name__)


def record_run(*, kind, channel, client_id, user_id=None, api_key_id=None, raw=None, result=None,
               file_type=None, status='succeeded', error_code=None):
    """Grava uma linha em cadu_review_runs; falha em silêncio (a revisão já foi entregue)."""
    from ..db import get_db
    result = result or {}
    summary = result.get('summary') or {}
    typesafe = result.get('typesafe') or {}
    connection = None
    try:
        connection = get_db()
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.cadu_review_runs') IS NOT NULL AS ready")
            if not cursor.fetchone()['ready']:
                return
            cursor.execute(
                '''INSERT INTO cadu_review_runs
                   (kind, channel, client_id, user_id, api_key_id, file_type, file_sha256, line_count, score,
                    verdict, partial, statuses, typesafe_model, typesafe_usage, tokens_estimados, tokens_cobrados,
                    status, error_code, duration_ms, prompt_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,0,%s,%s,%s,%s)''',
                (kind, channel, int(client_id), user_id, api_key_id,
                 file_type or (result.get('file') or {}).get('type'),
                 hashlib.sha256(raw).hexdigest() if raw else None,
                 (result.get('file') or {}).get('lines'), summary.get('score'), summary.get('verdict'),
                 bool(summary.get('partial')),
                 json.dumps({item['id']: item['status'] for item in result.get('findings') or ()}),
                 typesafe.get('model'), json.dumps(typesafe.get('usage') or {}),
                 int(result.get('tokens_estimados') or 0), status, error_code,
                 result.get('duration_ms'), result.get('version')))
        connection.commit()
    except Exception:
        logger.warning('Não foi possível registrar a revisão %s', kind, exc_info=True)
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass


def is_internal_user(user_id) -> bool:
    """Pessoa da organização CENTRALCOMM (mesma regra do login para session['is_centralcomm'])."""
    from ..db import get_db
    try:
        with get_db().cursor() as cursor:
            cursor.execute('''SELECT c.nome_fantasia FROM tbl_contato_cliente u
                              JOIN tbl_cliente c ON c.id_cliente = u.pk_id_tbl_cliente
                              WHERE u.id_contato_cliente = %s LIMIT 1''', (int(user_id),))
            row = cursor.fetchone()
    except Exception:
        logger.warning('Não foi possível conferir o acesso interno do usuário %s', user_id, exc_info=True)
        return False
    return bool(row) and str(row.get('nome_fantasia') or '').upper() == 'CENTRALCOMM'
