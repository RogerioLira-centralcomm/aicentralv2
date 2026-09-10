"""Persistência PostgreSQL do Studio de Treinamentos."""

from contextlib import contextmanager
from decimal import Decimal

from psycopg.types.json import Json

from .schema import ensure_schema, seed_imersao


class TrainingNotFoundError(LookupError):
    pass


class TrainingConflictError(ValueError):
    pass


def _money(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _serialize(row):
    if not row:
        return row
    data = dict(row)
    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = float(value)
    return data


class TrainingStudioRepository:
    def __init__(self, connection=None):
        self._connection = connection
        self._ready = False

    @property
    def conn(self):
        if self._connection is not None:
            return self._connection
        from .. import db

        return db.get_db()

    def ready(self, created_by=None):
        if not self._ready:
            ensure_schema(self.conn)
            self._ready = True
        return seed_imersao(self.conn, created_by=created_by)

    @contextmanager
    def _write(self):
        try:
            with self.conn.cursor() as cursor:
                yield cursor
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def get_treinamento(self, treinamento_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, titulo, descricao, slug, guia_estilo, created_by, created_at
                  FROM cx_treinamentos
                 WHERE id = %s
                """,
                (treinamento_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise TrainingNotFoundError("Treinamento não encontrado.")
        return _serialize(row)

    def update_treinamento(self, treinamento_id, data):
        fields = []
        values = []
        if "titulo" in data:
            fields.append("titulo = %s")
            values.append(str(data.get("titulo") or "").strip()[:200])
        if "descricao" in data:
            fields.append("descricao = %s")
            values.append(str(data.get("descricao") or "").strip())
        if "guia_estilo" in data:
            fields.append("guia_estilo = %s")
            values.append(Json(data.get("guia_estilo") or {}))
        if not fields:
            return self.get_treinamento(treinamento_id)
        values.append(treinamento_id)
        with self._write() as cursor:
            cursor.execute(
                f"UPDATE cx_treinamentos SET {', '.join(fields)} WHERE id = %s",
                values,
            )
            if cursor.rowcount == 0:
                raise TrainingNotFoundError("Treinamento não encontrado.")
        return self.get_treinamento(treinamento_id)

    def get_sessao(self, sessao_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.id, s.treinamento_id, s.slug, s.titulo, s.conteudo_html,
                       s.ordem, s.horario_inicio, s.horario_fim, s.facilitadores,
                       s.tipo, s.created_at, s.updated_at,
                       t.titulo AS treinamento_titulo,
                       t.descricao AS treinamento_descricao,
                       t.guia_estilo
                  FROM cx_treinamento_sessoes s
                  JOIN cx_treinamentos t ON t.id = s.treinamento_id
                 WHERE s.id = %s
                """,
                (sessao_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise TrainingNotFoundError("Sessão não encontrada.")
        data = _serialize(row)
        data["fontes"] = self.list_fontes(sessao_id)
        data["imagens"] = self.list_imagens(sessao_id)
        data["consumo"] = self.consumo(sessao_id)
        data["facilitadores"] = list(data.get("facilitadores") or [])
        return data

    def list_sessoes(self, treinamento_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, treinamento_id, slug, titulo, ordem, horario_inicio,
                       horario_fim, facilitadores, tipo, updated_at
                  FROM cx_treinamento_sessoes
                 WHERE treinamento_id = %s
                 ORDER BY ordem, id
                """,
                (treinamento_id,),
            )
            rows = []
            for row in cursor.fetchall():
                item = _serialize(row)
                item["facilitadores"] = list(item.get("facilitadores") or [])
                rows.append(item)
        return rows

    def get_sessao_by_slug(self, treinamento_id, slug):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id FROM cx_treinamento_sessoes
                 WHERE treinamento_id = %s AND slug = %s
                """,
                (treinamento_id, slug),
            )
            row = cursor.fetchone()
        if not row:
            raise TrainingNotFoundError("Sessão não encontrada.")
        return self.get_sessao(row["id"])

    def update_sessao(self, sessao_id, data):
        fields = ["updated_at = NOW()"]
        values = []
        if "titulo" in data:
            fields.append("titulo = %s")
            values.append(str(data.get("titulo") or "").strip()[:200] or "Sessão")
        if "conteudo_html" in data:
            fields.append("conteudo_html = %s")
            values.append(str(data.get("conteudo_html") or ""))
        values.append(sessao_id)
        with self._write() as cursor:
            cursor.execute(
                f"UPDATE cx_treinamento_sessoes SET {', '.join(fields)} WHERE id = %s",
                values,
            )
            if cursor.rowcount == 0:
                raise TrainingNotFoundError("Sessão não encontrada.")
        return self.get_sessao(sessao_id)

    def list_fontes(self, sessao_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, sessao_id, url, titulo, resumo, incluido_no_contexto, created_at
                  FROM cx_treinamento_fontes
                 WHERE sessao_id = %s
                 ORDER BY created_at DESC, id DESC
                """,
                (sessao_id,),
            )
            return [_serialize(row) for row in cursor.fetchall()]

    def add_fonte(self, sessao_id, url, titulo, resumo):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_fontes (sessao_id, url, titulo, resumo)
                VALUES (%s, %s, %s, %s)
                RETURNING id, sessao_id, url, titulo, resumo, incluido_no_contexto, created_at
                """,
                (sessao_id, url, (titulo or "")[:300], resumo or ""),
            )
            return _serialize(cursor.fetchone())

    def apply_fonte(self, sessao_id, fonte_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_treinamento_fontes
                   SET incluido_no_contexto = TRUE
                 WHERE id = %s AND sessao_id = %s
                RETURNING id, sessao_id, url, titulo, resumo, incluido_no_contexto, created_at
                """,
                (fonte_id, sessao_id),
            )
            row = cursor.fetchone()
        if not row:
            raise TrainingNotFoundError("Fonte não encontrada.")
        return _serialize(row)

    def context_fontes(self, sessao_id):
        return [item for item in self.list_fontes(sessao_id) if item.get("incluido_no_contexto")]

    def list_imagens(self, sessao_id, limit=24):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, sessao_id, asset_url, thumb_url, prompt, created_at
                  FROM cx_treinamento_imagens
                 WHERE sessao_id = %s
                 ORDER BY created_at DESC, id DESC
                 LIMIT %s
                """,
                (sessao_id, int(limit)),
            )
            return [_serialize(row) for row in cursor.fetchall()]

    def add_imagem(self, sessao_id, asset_url, prompt, thumb_url=None):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_imagens (sessao_id, asset_url, thumb_url, prompt)
                VALUES (%s, %s, %s, %s)
                RETURNING id, sessao_id, asset_url, thumb_url, prompt, created_at
                """,
                (sessao_id, asset_url, thumb_url or asset_url, prompt or ""),
            )
            return _serialize(cursor.fetchone())

    def add_agent_message(self, sessao_id, role, content, tool_used=None, display=None):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_agent_mensagens (
                    sessao_id, role, content, tool_used, display_payload
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, sessao_id, role, content, tool_used, display_payload, created_at
                """,
                (sessao_id, role, content or "", tool_used, Json(display or {})),
            )
            return _serialize(cursor.fetchone())

    def list_agent_messages(self, sessao_id, limit=40):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, sessao_id, role, content, tool_used, display_payload, created_at
                  FROM cx_treinamento_agent_mensagens
                 WHERE sessao_id = %s
                 ORDER BY created_at DESC, id DESC
                 LIMIT %s
                """,
                (sessao_id, int(limit)),
            )
            rows = [_serialize(row) for row in cursor.fetchall()]
        rows.reverse()
        return rows

    def add_ledger(self, treinamento_id, sessao_id, kind, model, usage, cost_usd, cost_brl, rate, source):
        usage = usage or {}
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_treinamento_ai_ledger (
                    treinamento_id, sessao_id, kind, provider, model,
                    prompt_tokens, completion_tokens,
                    cost_usd, cost_brl, usd_brl_rate, usd_brl_source
                )
                VALUES (%s, %s, %s, 'openrouter', %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    treinamento_id,
                    sessao_id,
                    kind,
                    model,
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    Decimal(str(_money(cost_usd))),
                    Decimal(str(_money(cost_brl))),
                    Decimal(str(_money(rate))) if rate else None,
                    source,
                ),
            )
            return cursor.fetchone()["id"]

    def consumo(self, sessao_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(cost_usd), 0) AS cost_usd,
                       COALESCE(SUM(cost_brl), 0) AS cost_brl
                  FROM cx_treinamento_ai_ledger
                 WHERE sessao_id = %s
                """,
                (sessao_id,),
            )
            totals = _serialize(cursor.fetchone()) or {"cost_usd": 0, "cost_brl": 0}
            cursor.execute(
                """
                SELECT kind,
                       COALESCE(SUM(cost_usd), 0) AS cost_usd,
                       COALESCE(SUM(cost_brl), 0) AS cost_brl
                  FROM cx_treinamento_ai_ledger
                 WHERE sessao_id = %s
                 GROUP BY kind
                """,
                (sessao_id,),
            )
            by_kind = {
                row["kind"]: {
                    "cost_usd": _money(row["cost_usd"]),
                    "cost_brl": _money(row["cost_brl"]),
                }
                for row in cursor.fetchall()
            }
        return {
            "cost_usd": _money(totals.get("cost_usd")),
            "cost_brl": _money(totals.get("cost_brl")),
            "by_kind": by_kind,
        }

    def consumo_treinamento(self, treinamento_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(cost_usd), 0) AS cost_usd,
                       COALESCE(SUM(cost_brl), 0) AS cost_brl
                  FROM cx_treinamento_ai_ledger
                 WHERE treinamento_id = %s
                """,
                (treinamento_id,),
            )
            totals = _serialize(cursor.fetchone()) or {"cost_usd": 0, "cost_brl": 0}
        return {
            "cost_usd": _money(totals.get("cost_usd")),
            "cost_brl": _money(totals.get("cost_brl")),
            "by_kind": {},
        }
