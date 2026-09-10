"""Persistência do fechamento financeiro do PI."""

from contextlib import contextmanager

from psycopg.types.json import Json


class SchemaFinanceiroAusente(RuntimeError):
    """Tabelas de fechamento ainda não migradas."""


def _is_missing_relation(exc):
    text = str(exc).lower()
    return "does not exist" in text or "undefinedtable" in text


class PiFechamentoRepository:
    def __init__(self, connection=None):
        self._connection = connection

    @property
    def conn(self):
        if self._connection is not None:
            return self._connection
        from . import db

        return db.get_db()

    @contextmanager
    def _write(self):
        conn = self.conn
        try:
            with conn.cursor() as cursor:
                yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _safe_read(self, callback, default=None):
        try:
            return callback()
        except Exception as exc:
            if _is_missing_relation(exc):
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                return default
            raise

    def obter_status(self, id_pi):
        def _read():
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id_pi, status_financeiro, updated_por, updated_at
                      FROM cadu_pi_financeiro
                     WHERE id_pi = %s
                    """,
                    (id_pi,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

        return self._safe_read(_read)

    def listar_status(self, ids_pi):
        ids = [int(item) for item in (ids_pi or []) if item]
        if not ids:
            return {}

        def _read():
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id_pi, status_financeiro
                      FROM cadu_pi_financeiro
                     WHERE id_pi = ANY(%s)
                    """,
                    (ids,),
                )
                return {row["id_pi"]: row["status_financeiro"] for row in cursor.fetchall()}

        return self._safe_read(_read, {}) or {}

    def upsert_status(self, id_pi, status, autor_id=None):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cadu_pi_financeiro (id_pi, status_financeiro, updated_por)
                VALUES (%s, %s, %s)
                ON CONFLICT (id_pi) DO UPDATE
                   SET status_financeiro = EXCLUDED.status_financeiro,
                       updated_por = EXCLUDED.updated_por,
                       updated_at = date_trunc('second', CURRENT_TIMESTAMP)
                """,
                (id_pi, status, autor_id),
            )

    def proxima_versao(self, id_pi):
        def _read():
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(versao), 0) + 1 AS proxima
                      FROM cadu_pi_resultado_fechamento
                     WHERE id_pi = %s
                    """,
                    (id_pi,),
                )
                row = cursor.fetchone()
                return int(row["proxima"]) if row else 1

        return self._safe_read(_read, 1) or 1

    def obter_resultado(self, id_pi, versao=None):
        def _read():
            with self.conn.cursor() as cursor:
                if versao is None:
                    cursor.execute(
                        """
                        SELECT *
                          FROM cadu_pi_resultado_fechamento
                         WHERE id_pi = %s
                         ORDER BY versao DESC
                         LIMIT 1
                        """,
                        (id_pi,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT *
                          FROM cadu_pi_resultado_fechamento
                         WHERE id_pi = %s AND versao = %s
                        """,
                        (id_pi, versao),
                    )
                row = cursor.fetchone()
                return dict(row) if row else None

        return self._safe_read(_read)

    def listar_resultados_lote(self, ids_pi):
        ids = [int(item) for item in (ids_pi or []) if item]
        if not ids:
            return {}

        def _read():
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT ON (id_pi) *
                      FROM cadu_pi_resultado_fechamento
                     WHERE id_pi = ANY(%s)
                     ORDER BY id_pi, versao DESC
                    """,
                    (ids,),
                )
                return {row["id_pi"]: dict(row) for row in cursor.fetchall()}

        return self._safe_read(_read, {}) or {}

    def listar_campanhas(self, id_pi, versao):
        def _read():
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                      FROM cadu_pi_resultado_campanha
                     WHERE id_pi = %s AND versao = %s
                     ORDER BY id
                    """,
                    (id_pi, versao),
                )
                return [dict(row) for row in cursor.fetchall()]

        return self._safe_read(_read, []) or []

    def gravar_resultado(self, payload):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cadu_pi_resultado_fechamento (
                    id_pi, versao, gasto_midia_realizado, gasto_midia_previsto,
                    pct_gasto_midia, objetivo_contratado, objetivo_atingido,
                    pct_objetivo, valor_bruto, valor_liquido, margem_cc,
                    tech_fee, com_vendas, pl_incentivos, impostos,
                    margem_liquida_calculada, zona_lucratividade, zonas_json,
                    saude_pi, saude_json, desvio_aceitavel_pct, lucrativo,
                    observacoes_operacao, payload_json, fechado_por
                ) VALUES (
                    %(id_pi)s, %(versao)s, %(gasto_midia_realizado)s,
                    %(gasto_midia_previsto)s, %(pct_gasto_midia)s,
                    %(objetivo_contratado)s, %(objetivo_atingido)s,
                    %(pct_objetivo)s, %(valor_bruto)s, %(valor_liquido)s,
                    %(margem_cc)s, %(tech_fee)s, %(com_vendas)s,
                    %(pl_incentivos)s, %(impostos)s,
                    %(margem_liquida_calculada)s, %(zona_lucratividade)s,
                    %(zonas_json)s, %(saude_pi)s, %(saude_json)s,
                    %(desvio_aceitavel_pct)s, %(lucrativo)s,
                    %(observacoes_operacao)s, %(payload_json)s, %(fechado_por)s
                )
                RETURNING id
                """,
                {
                    **payload,
                    "zonas_json": Json(payload.get("zonas_json")),
                    "saude_json": Json(payload.get("saude_json")),
                    "payload_json": Json(payload.get("payload_json")),
                },
            )
            return cursor.fetchone()["id"]

    def gravar_campanhas(self, rows):
        if not rows:
            return
        with self._write() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT INTO cadu_pi_resultado_campanha (
                        id_pi, id_campanha, versao, plataforma, nome_campanha,
                        gasto_realizado, gasto_previsto, pct_gasto,
                        obj_contratado, obj_atingido, pct_objetivo,
                        preco_unitario_orcado, preco_unitario_realizado,
                        periodo_inicio, periodo_fim, status_nome, link_dash,
                        flags_json
                    ) VALUES (
                        %(id_pi)s, %(id_campanha)s, %(versao)s, %(plataforma)s,
                        %(nome_campanha)s, %(gasto_realizado)s, %(gasto_previsto)s,
                        %(pct_gasto)s, %(obj_contratado)s, %(obj_atingido)s,
                        %(pct_objetivo)s, %(preco_unitario_orcado)s,
                        %(preco_unitario_realizado)s, %(periodo_inicio)s,
                        %(periodo_fim)s, %(status_nome)s, %(link_dash)s,
                        %(flags_json)s
                    )
                    """,
                    {**row, "flags_json": Json(row.get("flags_json"))},
                )

    def finalizar_handoff(self, id_pi):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cadu_pi_campanha
                   SET id_status = (
                       SELECT id FROM cadu_pi_camp_status
                        WHERE descricao = 'Finalizada' LIMIT 1
                   ),
                       updated_at = date_trunc('second', CURRENT_TIMESTAMP)
                 WHERE id_pi = %s
                """,
                (id_pi,),
            )
            campanhas = cursor.rowcount
            cursor.execute(
                """
                UPDATE cadu_pi
                   SET id_sub_status_pi = (
                       SELECT key FROM cadu_pi_sub_status
                        WHERE display = 'Em faturamento' LIMIT 1
                   ),
                       id_status_pi = (
                           SELECT id FROM cadu_pi_aux_status
                            WHERE descricao = 'Faturamento' LIMIT 1
                       ),
                       updated_at = date_trunc('second', CURRENT_TIMESTAMP)
                 WHERE id_pi = %s
                """,
                (id_pi,),
            )
            return campanhas
