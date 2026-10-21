"""Persistência de destinatários e logs de e-mail da cotação."""

from contextlib import contextmanager


class CotacaoNaoEncontradaError(LookupError):
    pass


class CotacaoComunicacaoRepository:
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
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def obter_cotacao(self, id_cotacao):
        from . import db

        cotacao = db.obter_cotacao_por_id(id_cotacao)
        if not cotacao:
            raise CotacaoNaoEncontradaError("Cotação não encontrada.")
        return cotacao

    def listar_contatos_disponiveis(self, cotacao):
        from . import db

        empresas = []
        for empresa_id in (
            cotacao.get("client_id"),
            cotacao.get("agencia_id"),
            cotacao.get("id_parceiro"),
        ):
            if empresa_id is None:
                continue
            empresa_id = int(empresa_id)
            if empresa_id not in empresas:
                empresas.append(empresa_id)
        resultado = []
        for empresa_id in empresas:
            for row in db.obter_contatos_para_operacao(empresa_id) or []:
                item = dict(row)
                item["pk_id_tbl_cliente"] = empresa_id
                resultado.append(item)
        return resultado

    def listar_destinatarios(self, id_cotacao):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.id, d.id_contato_cliente, d.papel, d.padrao,
                       c.nome_completo, c.email, c.telefone,
                       c.pk_id_tbl_cliente
                  FROM cadu_cotacao_destinatario d
                  JOIN tbl_contato_cliente c
                    ON c.id_contato_cliente = d.id_contato_cliente
                 WHERE d.id_cotacao = %s
                 ORDER BY d.papel, d.padrao DESC, c.nome_completo
                """,
                (id_cotacao,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def listar_destinatarios_sugeridos(self, cotacao):
        empresas = (
            ("cliente_final", cotacao.get("client_id")),
            ("agencia", cotacao.get("agencia_id")),
            ("parceiro", cotacao.get("id_parceiro")),
        )
        resultado = []
        with self.conn.cursor() as cursor:
            for papel, empresa_id in empresas:
                if not empresa_id:
                    continue
                cursor.execute(
                    """
                    SELECT c.id_contato_cliente, c.pk_id_tbl_cliente, c.nome_completo,
                           c.email, c.telefone, s.display AS setor,
                           COALESCE(c.responsavel_setor, FALSE) AS responsavel_setor
                      FROM tbl_contato_cliente c
                      LEFT JOIN tbl_setor s ON s.id_setor = c.pk_id_tbl_setor
                     WHERE COALESCE(c.status, TRUE) = TRUE
                       AND c.pk_id_tbl_cliente = %s
                       AND COALESCE(c.responsavel_setor, FALSE) = TRUE
                       AND NULLIF(TRIM(c.email), '') IS NOT NULL
                     ORDER BY c.nome_completo
                    """,
                    (int(empresa_id),),
                )
                for idx, row in enumerate(cursor.fetchall()):
                    resultado.append(
                        {
                            **dict(row),
                            "papel": papel,
                            "padrao": idx == 0,
                            "sugerido": True,
                        }
                    )
        return resultado

    def substituir_destinatarios(self, id_cotacao, destinatarios, autor_id):
        cotacao = self.obter_cotacao(id_cotacao)
        normalizados = []
        vistos = set()
        padroes = set()
        for item in destinatarios:
            contato_id = int(item["id_contato_cliente"])
            papel = str(item.get("papel", "")).strip()
            if papel not in ("agencia", "cliente_final", "parceiro"):
                raise ValueError("Papel deve ser agencia, cliente_final ou parceiro.")
            if contato_id in vistos:
                raise ValueError("O mesmo contato não pode ser repetido.")
            padrao = bool(item.get("padrao", False))
            if padrao and papel in padroes:
                raise ValueError("Só pode haver um contato padrão por papel.")
            vistos.add(contato_id)
            if padrao:
                padroes.add(papel)
            normalizados.append((contato_id, papel, padrao))

        esperado = {
            "cliente_final": cotacao.get("client_id"),
            "agencia": cotacao.get("agencia_id"),
            "parceiro": cotacao.get("id_parceiro"),
        }
        if any(papel == "agencia" for _, papel, _ in normalizados) and not esperado["agencia"]:
            raise ValueError("Esta cotação não possui agência.")
        if any(papel == "parceiro" for _, papel, _ in normalizados) and not esperado["parceiro"]:
            raise ValueError("Esta cotação não possui parceiro.")

        ids = [item[0] for item in normalizados]
        contatos = {}
        if ids:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id_contato_cliente, pk_id_tbl_cliente, email
                      FROM tbl_contato_cliente
                     WHERE COALESCE(status, TRUE) = TRUE
                       AND id_contato_cliente = ANY(%s)
                    """,
                    (ids,),
                )
                contatos = {
                    row["id_contato_cliente"]: {
                        "empresa_id": row["pk_id_tbl_cliente"],
                        "email": str(row.get("email") or "").strip(),
                    }
                    for row in cursor.fetchall()
                }
        for contato_id, papel, _ in normalizados:
            contato = contatos.get(contato_id)
            if not contato:
                raise ValueError("Contato inválido ou inativo.")
            if not contato["email"]:
                raise ValueError("Todos os destinatários precisam ter e-mail.")
            empresa_esperada = esperado.get(papel)
            if empresa_esperada and int(contato["empresa_id"]) != int(empresa_esperada):
                raise ValueError("Contato não pertence ao papel informado.")

        with self._write() as cursor:
            cursor.execute(
                "DELETE FROM cadu_cotacao_destinatario WHERE id_cotacao = %s",
                (id_cotacao,),
            )
            for contato_id, papel, padrao in normalizados:
                cursor.execute(
                    """
                    INSERT INTO cadu_cotacao_destinatario
                           (id_cotacao, id_contato_cliente, papel, padrao, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (id_cotacao, contato_id, papel, padrao, autor_id),
                )
        return self.listar_destinatarios(id_cotacao)

    def listar_emails(self, id_cotacao, limite=50):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, tipo, assunto, destinatario_nome, destinatario_email,
                       status, brevo_message_id, erro, criado_por, enviado_em,
                       created_at
                  FROM cadu_cotacao_email_log
                 WHERE id_cotacao = %s
                 ORDER BY created_at DESC, id DESC
                 LIMIT %s
                """,
                (id_cotacao, limite),
            )
            return [dict(row) for row in cursor.fetchall()]

    def obter_email_log(self, id_cotacao, log_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, tipo, assunto, destinatario_nome, destinatario_email,
                       status, brevo_message_id, erro, criado_por, enviado_em,
                       created_at, html
                  FROM cadu_cotacao_email_log
                 WHERE id_cotacao = %s AND id = %s
                """,
                (id_cotacao, log_id),
            )
            row = cursor.fetchone()
            if not row:
                raise LookupError("E-mail não encontrado.")
            return dict(row)

    def criar_email_log(self, id_cotacao, tipo, assunto, destinatario, html, autor_id):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cadu_cotacao_email_log
                       (id_cotacao, tipo, assunto, destinatario_nome,
                        destinatario_email, html, status, criado_por)
                VALUES (%s, %s, %s, %s, %s, %s, 'pendente', %s)
                RETURNING id
                """,
                (
                    id_cotacao,
                    tipo,
                    assunto,
                    destinatario.get("nome") or destinatario.get("nome_completo"),
                    destinatario["email"],
                    html,
                    autor_id,
                ),
            )
            return cursor.fetchone()["id"]

    def concluir_email_log(self, log_id, resultado):
        sucesso = bool(resultado.get("success"))
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cadu_cotacao_email_log
                   SET status = %s, brevo_message_id = %s, erro = %s,
                       enviado_em = CASE WHEN %s THEN date_trunc('second', CURRENT_TIMESTAMP) ELSE NULL END,
                       updated_at = date_trunc('second', CURRENT_TIMESTAMP)
                 WHERE id = %s
                """,
                (
                    "sucesso" if sucesso else "erro",
                    resultado.get("messageId"),
                    None if sucesso else str(resultado.get("error") or "Falha no envio"),
                    sucesso,
                    log_id,
                ),
            )
