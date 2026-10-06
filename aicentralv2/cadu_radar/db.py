"""Transação do Radar sobre a conexão da requisição.

``get_db()`` devolve a conexão compartilhada do contexto (``g.db``). Usar ``with get_db() as conn``
FECHA essa conexão ao sair (psycopg 3), e toda consulta seguinte do mesmo contexto falha com
"the connection is closed". Aqui o commit é explícito e a conexão continua aberta.
"""
from __future__ import annotations

from contextlib import contextmanager

from ..db import get_db


@contextmanager
def transaction():
    """Cursor numa transação: commit ao sair, rollback se der erro, conexão sempre aberta."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
