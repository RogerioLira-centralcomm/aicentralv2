"""Persistência da mesa de assinaturas."""

from contextlib import contextmanager

from psycopg.types.json import Json


class DocumentoNaoEncontrado(LookupError):
    pass


class AssinaturasRepository:
    def __init__(self, connection=None):
        self._connection = connection

    @property
    def conn(self):
        if self._connection is not None:
            return self._connection
        from .. import db

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

    def criar_documento(self, dados):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_documento (
                    titulo, arquivo_nome, uuid_d4sign, uuid_safe, status,
                    tipo_vinculo, id_vinculo, vinculo_nome, criado_por
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    dados["titulo"],
                    dados.get("arquivo_nome"),
                    dados.get("uuid_d4sign"),
                    dados.get("uuid_safe"),
                    dados.get("status") or "aguardando_assinaturas",
                    dados.get("tipo_vinculo") or "interno",
                    dados.get("id_vinculo"),
                    dados.get("vinculo_nome"),
                    dados.get("criado_por"),
                ),
            )
            return cursor.fetchone()["id"]

    def criar_signatarios(self, id_documento, signers):
        with self._write() as cursor:
            for index, signer in enumerate(signers):
                cursor.execute(
                    """
                    INSERT INTO cx_documento_signatario (
                        id_documento, id_contato, email, nome, key_signer, ordem
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        id_documento,
                        signer.get("id_contato"),
                        str(signer.get("email") or "").strip().lower(),
                        signer.get("nome"),
                        signer.get("key_signer"),
                        signer.get("ordem", index),
                    ),
                )

    def obter(self, id_documento):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.*, c.nome_completo AS criado_por_nome
                  FROM cx_documento d
                  LEFT JOIN tbl_contato_cliente c
                    ON c.id_contato_cliente = d.criado_por
                 WHERE d.id = %s
                """,
                (int(id_documento),),
            )
            row = cursor.fetchone()
        if not row:
            raise DocumentoNaoEncontrado(id_documento)
        row["signatarios"] = self.listar_signatarios(id_documento)
        return row

    def obter_por_uuid(self, uuid_d4sign):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM cx_documento WHERE uuid_d4sign = %s",
                (str(uuid_d4sign),),
            )
            return cursor.fetchone()

    def listar_signatarios(self, id_documento):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, id_contato, email, nome, key_signer, ordem, status, assinado_em
                  FROM cx_documento_signatario
                 WHERE id_documento = %s
                 ORDER BY ordem, id
                """,
                (int(id_documento),),
            )
            return cursor.fetchall() or []

    def listar(self, filtros=None):
        filtros = filtros or {}
        clauses = ["TRUE"]
        params = []
        status = str(filtros.get("status") or "").strip()
        if status:
            clauses.append("d.status = %s")
            params.append(status)
        tipo = str(filtros.get("tipo_vinculo") or "").strip()
        if tipo:
            clauses.append("d.tipo_vinculo = %s")
            params.append(tipo)
        if filtros.get("id_vinculo"):
            clauses.append("d.id_vinculo = %s")
            params.append(int(filtros["id_vinculo"]))
        email = str(filtros.get("email") or "").strip().lower()
        if email and filtros.get("minhas"):
            clauses.append(
                "EXISTS ("
                " SELECT 1 FROM cx_documento_signatario s"
                " WHERE s.id_documento = d.id AND lower(s.email) = %s"
                ")"
            )
            params.append(email)
        if filtros.get("enviados_por"):
            clauses.append("d.criado_por = %s")
            params.append(int(filtros["enviados_por"]))
        query = str(filtros.get("q") or "").strip()
        if query:
            clauses.append(
                "(d.titulo ILIKE %s OR COALESCE(d.vinculo_nome, '') ILIKE %s)"
            )
            params.extend([f"%{query}%", f"%{query}%"])
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT d.*, c.nome_completo AS criado_por_nome
                  FROM cx_documento d
                  LEFT JOIN tbl_contato_cliente c
                    ON c.id_contato_cliente = d.criado_por
                 WHERE {' AND '.join(clauses)}
                 ORDER BY d.updated_at DESC, d.id DESC
                 LIMIT 200
                """,
                params,
            )
            rows = cursor.fetchall() or []
        for row in rows:
            row["signatarios"] = self.listar_signatarios(row["id"])
        return rows

    def contar_pendencias(self, email):
        email = str(email or "").strip().lower()
        if not email:
            return 0
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                  FROM cx_documento_signatario s
                  JOIN cx_documento d ON d.id = s.id_documento
                 WHERE lower(s.email) = %s
                   AND s.status = 'pendente'
                   AND d.status IN ('aguardando_assinaturas', 'parcialmente_assinado')
                """,
                (email,),
            )
            row = cursor.fetchone() or {}
        return int(row.get("total") or 0)

    def atualizar_status(self, id_documento, status):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_documento
                   SET status = %s, updated_at = NOW()
                 WHERE id = %s
                """,
                (status, int(id_documento)),
            )

    def marcar_signatario(self, id_documento, email, status, quando=None):
        email = str(email or "").strip().lower()
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_documento_signatario
                   SET status = %s,
                       assinado_em = COALESCE(%s, NOW())
                 WHERE id_documento = %s
                   AND lower(email) = %s
                """,
                (status, quando, int(id_documento), email),
            )

    def registrar_evento(self, id_documento, type_post, payload):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_documento_evento (id_documento, type_post, payload)
                VALUES (%s, %s, %s)
                """,
                (int(id_documento), str(type_post or ""), Json(payload or {})),
            )

    def listar_colaboradores(self, query=""):
        like = f"%{query.strip()}%" if query else "%"
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id_contato_cliente AS id,
                       c.nome_completo AS label,
                       c.email
                  FROM tbl_contato_cliente c
                  JOIN tbl_cliente cli ON cli.id_cliente = c.pk_id_tbl_cliente
                 WHERE UPPER(TRIM(COALESCE(cli.nome_fantasia, ''))) = 'CENTRALCOMM'
                   AND COALESCE(c.status, TRUE) = TRUE
                   AND COALESCE(c.email, '') <> ''
                   AND (c.nome_completo ILIKE %s OR c.email ILIKE %s)
                 ORDER BY c.nome_completo
                 LIMIT 40
                """,
                (like, like),
            )
            return cursor.fetchall() or []

    def listar_clientes(self, query="", agencia=False):
        like = f"%{query.strip()}%" if query else "%"
        extra = ""
        if agencia:
            extra = """
              AND (
                COALESCE((ag.key IS TRUE), false)
                OR LOWER(TRIM(COALESCE(ag.display, ''))) IN ('sim', 's')
              )
            """
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT cli.id_cliente AS id,
                       COALESCE(cli.nome_fantasia, cli.razao_social) AS label
                  FROM tbl_cliente cli
                  LEFT JOIN tbl_agencia ag ON ag.id_agencia = cli.pk_id_tbl_agencia
                 WHERE COALESCE(cli.status, TRUE) = TRUE
                   AND (cli.nome_fantasia ILIKE %s OR cli.razao_social ILIKE %s)
                   {extra}
                 ORDER BY label ASC NULLS LAST
                 LIMIT 40
                """,
                (like, like),
            )
            return cursor.fetchall() or []

    def listar_pis(self, query=""):
        like = f"%{query.strip()}%" if query else "%"
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id_pi AS id,
                       TRIM(CONCAT_WS(' · ',
                            NULLIF(p.codigo_pi_cc, ''),
                            NULLIF(p.titulo_pi, '')
                       )) AS label
                  FROM cadu_pi p
                 WHERE COALESCE(p.codigo_pi_cc, '') ILIKE %s
                    OR COALESCE(p.titulo_pi, '') ILIKE %s
                 ORDER BY p.id_pi DESC
                 LIMIT 20
                """,
                (like, like),
            )
            return cursor.fetchall() or []
