"""Persistência SQL crua da Operação do PI (psycopg 3)."""

from contextlib import contextmanager


class PiNaoEncontradoError(LookupError):
    pass


class PropriedadeInvalidaError(ValueError):
    pass


class PiOperacaoRepository:
    def __init__(self, connection=None):
        self._connection = connection

    @property
    def conn(self):
        if self._connection is not None:
            return self._connection
        # Import tardio mantém as regras e testes puros utilizáveis sem libpq.
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

    def rollback(self):
        self.conn.rollback()

    def obter_pi(self, id_pi):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id_pi, p.codigo_pi_cc, p.codigo_pi_ag, p.titulo_pi,
                       p.id_cliente, p.id_agencia,
                       p."Id_parc_reg" AS id_parceiro,
                       p.id_resp_comercial,
                       p.id_pi_tipo, p.vr_bruto_pi, p.desvio_aceitavel_pct,
                       p.id_cont_cliente_midia, p.id_cont_cliente_financ,
                       p.id_cont_agen_midia, p.id_cont_agen_financ,
                       p.cotacao_id, cot.proposta_enviada_em,
                       cot.status AS cotacao_status,
                       p.id_sub_status_pi, p.id_status_pi, p.periodo_inicio,
                       p.periodo_fim, p.mes_ref_comp, p.observacoes_operacao,
                       p.updated_at,
                       cli.nome_fantasia AS cliente_nome,
                       ag.nome_fantasia AS agencia_nome,
                       parc.nome_fantasia AS parceiro_nome,
                       ss.display AS sub_status_descricao,
                       resp.nome_completo AS responsavel_comercial_nome,
                       resp.foto_url AS responsavel_comercial_foto_url
                  FROM cadu_pi p
                  LEFT JOIN tbl_cliente cli ON cli.id_cliente = p.id_cliente
                  LEFT JOIN tbl_cliente ag ON ag.id_cliente = p.id_agencia
                  LEFT JOIN tbl_cliente parc
                         ON parc.id_cliente = p."Id_parc_reg"
                  LEFT JOIN cadu_cotacoes cot ON cot.id = p.cotacao_id
                  LEFT JOIN cadu_pi_sub_status ss ON ss.key = p.id_sub_status_pi
                  LEFT JOIN tbl_contato_cliente resp
                         ON resp.id_contato_cliente = p.id_resp_comercial
                 WHERE p.id_pi = %s
                """,
                (id_pi,),
            )
            row = cursor.fetchone()
        if not row:
            raise PiNaoEncontradoError("PI não encontrado.")
        return dict(row)

    def listar_campanhas(self, id_pi):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id_campanha, c.id_pi, c.id_cliente, c.nome_campanha,
                       c.id_plataforma, c.id_objetivos_campanha,
                       c.valor_plataforma, c.custo_midia_orcado,
                       c.link_dash, c.id_status,
                       c.id_responsavel_operacao, c.periodo_inicio, c.periodo_fim,
                       c.obj_contratados, c.totalizador_atingido,
                       c.totalizador_gasto, c.updated_at,
                       st.descricao AS status_descricao,
                       plt.descricao AS plataforma_nome,
                       resp.nome_completo AS responsavel_operacao_nome,
                       resp.foto_url AS responsavel_operacao_foto_url
                  FROM cadu_pi_campanha c
                  LEFT JOIN cadu_pi_camp_status st ON st.id = c.id_status
                  LEFT JOIN cadu_pi_camp_plataforma plt
                         ON plt.id_plataforma = c.id_plataforma
                  LEFT JOIN tbl_contato_cliente resp
                         ON resp.id_contato_cliente = c.id_responsavel_operacao
                 WHERE c.id_pi = %s
                 ORDER BY c.id_campanha
                """,
                (id_pi,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def obter_campanha(self, id_campanha):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id_campanha, c.id_pi, c.id_cliente, c.nome_campanha,
                       c.id_plataforma, c.id_objetivos_campanha,
                       c.valor_plataforma, c.custo_midia_orcado,
                       c.link_dash, c.id_status,
                       c.id_responsavel_operacao, c.periodo_inicio, c.periodo_fim,
                       c.obj_contratados, c.totalizador_atingido,
                       c.totalizador_gasto, c.updated_at,
                       st.descricao AS status_descricao,
                       plt.descricao AS plataforma_nome,
                       resp.nome_completo AS responsavel_operacao_nome,
                       resp.foto_url AS responsavel_operacao_foto_url
                  FROM cadu_pi_campanha c
                  LEFT JOIN cadu_pi_camp_status st ON st.id = c.id_status
                  LEFT JOIN cadu_pi_camp_plataforma plt
                         ON plt.id_plataforma = c.id_plataforma
                  LEFT JOIN tbl_contato_cliente resp
                         ON resp.id_contato_cliente = c.id_responsavel_operacao
                 WHERE c.id_campanha = %s
                """,
                (id_campanha,),
            )
            row = cursor.fetchone()
        if not row:
            raise LookupError("Campanha não encontrada.")
        return dict(row)

    def listar_pis_cliente(self, cliente_id, limite=8):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id_pi, p.codigo_pi_cc, p.codigo_pi_ag, p.titulo_pi,
                       p.id_cliente, p.cotacao_id, p.vr_bruto_pi,
                       p.periodo_inicio, p.periodo_fim,
                       ss.display AS sub_status_descricao
                  FROM cadu_pi p
                  LEFT JOIN cadu_pi_sub_status ss ON ss.key = p.id_sub_status_pi
                 WHERE p.id_cliente = %s
                 ORDER BY p.updated_at DESC NULLS LAST, p.id_pi DESC
                 LIMIT %s
                """,
                (cliente_id, max(1, min(int(limite or 8), 20))),
            )
            return [dict(row) for row in cursor.fetchall()]

    def buscar_pis(self, termo, limite=8):
        termo = str(termo or "").strip()
        if len(termo) < 2:
            return []
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id_pi, p.codigo_pi_cc, p.codigo_pi_ag, p.titulo_pi,
                       p.id_cliente, p.cotacao_id, p.vr_bruto_pi,
                       p.id_sub_status_pi, p.periodo_inicio, p.periodo_fim,
                       cli.nome_fantasia AS cliente_nome,
                       ss.display AS sub_status_descricao,
                       resp.nome_completo AS responsavel_comercial_nome,
                       resp.foto_url AS responsavel_comercial_foto_url
                  FROM cadu_pi p
                  LEFT JOIN tbl_cliente cli ON cli.id_cliente = p.id_cliente
                  LEFT JOIN cadu_pi_sub_status ss ON ss.key = p.id_sub_status_pi
                  LEFT JOIN tbl_contato_cliente resp
                         ON resp.id_contato_cliente = p.id_resp_comercial
                 WHERE CAST(p.id_pi AS TEXT) ILIKE %s
                    OR COALESCE(p.codigo_pi_cc, '') ILIKE %s
                    OR COALESCE(p.codigo_pi_ag, '') ILIKE %s
                    OR COALESCE(p.titulo_pi, '') ILIKE %s
                    OR COALESCE(cli.nome_fantasia, '') ILIKE %s
                 ORDER BY p.updated_at DESC NULLS LAST, p.id_pi DESC
                 LIMIT %s
                """,
                tuple([f"%{termo}%"] * 5)
                + (max(1, min(int(limite or 8), 20)),),
            )
            return [dict(row) for row in cursor.fetchall()]

    def buscar_campanhas(self, termo, limite=8):
        termo = str(termo or "").strip()
        if len(termo) < 2:
            return []
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id_campanha, c.id_pi, c.id_cliente, c.nome_campanha,
                       c.link_dash, c.valor_plataforma, c.custo_midia_orcado,
                       c.obj_contratados, c.totalizador_atingido,
                       c.totalizador_gasto, c.periodo_inicio, c.periodo_fim,
                       st.descricao AS status_descricao,
                       plt.descricao AS plataforma_nome,
                       cli.nome_fantasia AS cliente_nome,
                       resp.nome_completo AS responsavel_operacao_nome,
                       resp.foto_url AS responsavel_operacao_foto_url,
                       p.codigo_pi_cc, p.codigo_pi_ag
                  FROM cadu_pi_campanha c
                  LEFT JOIN cadu_pi p ON p.id_pi = c.id_pi
                  LEFT JOIN cadu_pi_camp_status st ON st.id = c.id_status
                  LEFT JOIN cadu_pi_camp_plataforma plt
                         ON plt.id_plataforma = c.id_plataforma
                  LEFT JOIN tbl_cliente cli ON cli.id_cliente = c.id_cliente
                  LEFT JOIN tbl_contato_cliente resp
                         ON resp.id_contato_cliente = c.id_responsavel_operacao
                 WHERE CAST(c.id_campanha AS TEXT) ILIKE %s
                    OR COALESCE(c.nome_campanha, '') ILIKE %s
                    OR CAST(c.id_pi AS TEXT) ILIKE %s
                    OR COALESCE(p.codigo_pi_cc, '') ILIKE %s
                    OR COALESCE(p.codigo_pi_ag, '') ILIKE %s
                    OR COALESCE(cli.nome_fantasia, '') ILIKE %s
                 ORDER BY c.updated_at DESC NULLS LAST, c.id_campanha DESC
                 LIMIT %s
                """,
                tuple([f"%{termo}%"] * 6)
                + (max(1, min(int(limite or 8), 20)),),
            )
            return [dict(row) for row in cursor.fetchall()]

    def resumo_operacao(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id_sub_status_pi,
                       COALESCE(ss.display, 'Sem status') AS status_descricao,
                       COUNT(*) AS total_pis,
                       COALESCE(SUM(p.vr_bruto_pi), 0) AS valor_bruto
                  FROM cadu_pi p
                  LEFT JOIN cadu_pi_sub_status ss ON ss.key = p.id_sub_status_pi
                 GROUP BY p.id_sub_status_pi, ss.display
                 ORDER BY p.id_sub_status_pi
                """
            )
            pi_status = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT COALESCE(st.descricao, 'Sem status') AS status_descricao,
                       COUNT(*) AS total_campanhas,
                       COALESCE(SUM(c.obj_contratados), 0) AS objetivo_contratado,
                       COALESCE(SUM(c.totalizador_atingido), 0) AS objetivo_atingido,
                       COALESCE(SUM(c.totalizador_gasto), 0) AS total_gasto,
                       COALESCE(SUM(c.custo_midia_orcado), 0) AS custo_orcado
                  FROM cadu_pi_campanha c
                  LEFT JOIN cadu_pi_camp_status st ON st.id = c.id_status
                 GROUP BY c.id_status, st.descricao
                 ORDER BY c.id_status
                """
            )
            campanha_status = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT COALESCE(plt.descricao, 'Sem plataforma') AS plataforma,
                       COUNT(*) AS total_campanhas
                  FROM cadu_pi_campanha c
                  LEFT JOIN cadu_pi_camp_plataforma plt
                         ON plt.id_plataforma = c.id_plataforma
                 GROUP BY c.id_plataforma, plt.descricao
                 ORDER BY COUNT(*) DESC, plt.descricao
                """
            )
            plataformas = [dict(row) for row in cursor.fetchall()]
        return {
            "pis_por_status": pi_status,
            "campanhas_por_status": campanha_status,
            "campanhas_por_plataforma": plataformas,
        }

    def validar_campanhas(self, id_pi, ids_campanha):
        ids = sorted({int(item) for item in ids_campanha})
        if not ids:
            return []
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_campanha
                  FROM cadu_pi_campanha
                 WHERE id_pi = %s AND id_campanha = ANY(%s)
                """,
                (id_pi, ids),
            )
            encontrados = {row["id_campanha"] for row in cursor.fetchall()}
        if encontrados != set(ids):
            raise PropriedadeInvalidaError(
                "Uma ou mais campanhas não pertencem ao PI."
            )
        return ids

    def listar_contatos_disponiveis(self, id_pi):
        pi = self.obter_pi(id_pi)
        empresas = []
        for empresa_id in (pi.get("id_cliente"), pi.get("id_agencia")):
            if empresa_id is None:
                continue
            empresa_id = int(empresa_id)
            if empresa_id not in empresas:
                empresas.append(empresa_id)
        if not empresas:
            return []
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_contato_cliente, pk_id_tbl_cliente, nome_completo,
                       email, telefone
                  FROM tbl_contato_cliente
                 WHERE COALESCE(status, TRUE) = TRUE
                   AND pk_id_tbl_cliente = ANY(%s)
                 ORDER BY nome_completo
                """,
                (empresas,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def listar_destinatarios(self, id_pi):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT po.id, po.id_contato_cliente, po.papel, po.padrao,
                       c.nome_completo, c.email, c.telefone,
                       c.pk_id_tbl_cliente
                  FROM cadu_pi_contato_operacional po
                  JOIN tbl_contato_cliente c
                    ON c.id_contato_cliente = po.id_contato_cliente
                 WHERE po.id_pi = %s
                 ORDER BY po.papel, po.padrao DESC, c.nome_completo
                """,
                (id_pi,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def listar_destinatarios_sugeridos(self, id_pi):
        pi = self.obter_pi(id_pi)
        candidatos = (
            ("cliente_final", pi.get("id_cont_cliente_midia") or pi.get("id_cont_cliente_financ")),
            ("agencia", pi.get("id_cont_agen_midia") or pi.get("id_cont_agen_financ")),
        )
        ids = [contato_id for _, contato_id in candidatos if contato_id]
        if not ids:
            return []
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_contato_cliente, pk_id_tbl_cliente, nome_completo,
                       email, telefone
                  FROM tbl_contato_cliente
                 WHERE status = TRUE AND id_contato_cliente = ANY(%s)
                """,
                (ids,),
            )
            contatos = {
                row["id_contato_cliente"]: dict(row) for row in cursor.fetchall()
            }
        resultado = []
        for papel, contato_id in candidatos:
            contato = contatos.get(contato_id)
            if contato and contato.get("email"):
                resultado.append(
                    {
                        **contato,
                        "papel": papel,
                        "padrao": True,
                        "sugerido": True,
                    }
                )
        return resultado

    def substituir_destinatarios(self, id_pi, destinatarios, autor_id):
        pi = self.obter_pi(id_pi)
        normalizados = []
        vistos = set()
        padroes = set()
        for item in destinatarios:
            contato_id = int(item["id_contato_cliente"])
            papel = str(item.get("papel", "")).strip()
            if papel not in ("agencia", "cliente_final"):
                raise ValueError("Papel deve ser agencia ou cliente_final.")
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
            "cliente_final": pi["id_cliente"],
            "agencia": pi.get("id_agencia"),
        }
        if any(papel == "agencia" for _, papel, _ in normalizados) and not esperado["agencia"]:
            raise PropriedadeInvalidaError("Este PI não possui agência.")

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
            if not contato or contato["empresa_id"] != esperado[papel]:
                raise PropriedadeInvalidaError(
                    "Contato não pertence à empresa indicada pelo papel."
                )
            if not contato["email"]:
                raise PropriedadeInvalidaError(
                    "Contato selecionado não possui e-mail cadastrado."
                )

        with self._write() as cursor:
            cursor.execute(
                "DELETE FROM cadu_pi_contato_operacional WHERE id_pi = %s",
                (id_pi,),
            )
            for contato_id, papel, padrao in normalizados:
                cursor.execute(
                    """
                    INSERT INTO cadu_pi_contato_operacional
                           (id_pi, id_contato_cliente, papel, padrao, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (id_pi, contato_id, papel, padrao, autor_id),
                )
        return self.listar_destinatarios(id_pi)

    def listar_checklist(self, id_pi):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT cm.id, cm.id_pi, cm.id_campanha, cm.codigo,
                       cm.escopo, cm.fase, cm.ordem, cm.modo_conclusao,
                       cm.descricao, cm.evidencia,
                       cm.obrigatorio, cm.concluido, cm.concluido_em,
                       cm.concluido_por, cm.created_at,
                       c.nome_campanha, plt.descricao AS plataforma_nome,
                       u.nome_completo AS concluido_por_nome
                  FROM cadu_pi_checklist_material cm
                  LEFT JOIN cadu_pi_campanha c ON c.id_campanha = cm.id_campanha
                  LEFT JOIN cadu_pi_camp_plataforma plt
                         ON plt.id_plataforma = c.id_plataforma
                  LEFT JOIN tbl_contato_cliente u
                         ON u.id_contato_cliente = cm.concluido_por
                 WHERE cm.id_pi = %s
                 ORDER BY cm.ordem, cm.id_campanha NULLS FIRST, cm.id
                """,
                (id_pi,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def gerar_checklist(self, id_pi, itens, autor_id):
        campanha_ids = [
            item["id_campanha"]
            for item in itens
            if item.get("id_campanha") is not None
        ]
        self.validar_campanhas(id_pi, campanha_ids)
        with self._write() as cursor:
            for item in itens:
                descricao = str(item.get("descricao", "")).strip()
                if not descricao:
                    raise ValueError("Descrição do item é obrigatória.")
                cursor.execute(
                    """
                    INSERT INTO cadu_pi_checklist_material
                           (id_pi, id_campanha, codigo, escopo, fase, ordem,
                            modo_conclusao, descricao, obrigatorio, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        id_pi,
                        item.get("id_campanha"),
                        item.get("codigo"),
                        item.get("escopo") or (
                            "campanha" if item.get("id_campanha") else "pi"
                        ),
                        item.get("fase") or "preparacao",
                        int(item.get("ordem") or 0),
                        item.get("modo_conclusao") or "manual",
                        descricao,
                        bool(item.get("obrigatorio", True)),
                        autor_id,
                    ),
                )
        return self.listar_checklist(id_pi)

    def atualizar_item_checklist(self, id_pi, item_id, concluido, autor_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cadu_pi_checklist_material
                   SET concluido = %s,
                       concluido_em = CASE WHEN %s THEN date_trunc('second', CURRENT_TIMESTAMP) ELSE NULL END,
                       concluido_por = CASE WHEN %s THEN %s ELSE NULL END,
                       evidencia = CASE WHEN %s THEN 'Confirmado pela operação' ELSE NULL END,
                       updated_at = date_trunc('second', CURRENT_TIMESTAMP)
                 WHERE id = %s AND id_pi = %s
                   AND modo_conclusao = 'manual'
                RETURNING id
                """,
                (
                    concluido,
                    concluido,
                    concluido,
                    autor_id,
                    concluido,
                    item_id,
                    id_pi,
                ),
            )
            row = cursor.fetchone()
        if not row:
            raise PropriedadeInvalidaError(
                "Somente itens manuais deste PI podem ser alterados."
            )
        return next(item for item in self.listar_checklist(id_pi) if item["id"] == item_id)

    def concluir_itens_automaticos(self, id_pi, conclusoes):
        """Persiste marcos comprovados sem reabrir conclusões históricas."""
        if not conclusoes:
            return self.listar_checklist(id_pi)
        with self._write() as cursor:
            for item in conclusoes:
                cursor.execute(
                    """
                    UPDATE cadu_pi_checklist_material
                       SET concluido = TRUE,
                           concluido_em = COALESCE(
                               concluido_em,
                               date_trunc('second', CURRENT_TIMESTAMP)
                           ),
                           evidencia = COALESCE(evidencia, %s),
                           updated_at = date_trunc('second', CURRENT_TIMESTAMP)
                     WHERE id_pi = %s
                       AND codigo = %s
                       AND COALESCE(id_campanha, 0) = COALESCE(%s, 0)
                       AND modo_conclusao = 'automatico'
                    """,
                    (
                        item.get("evidencia"),
                        id_pi,
                        item["codigo"],
                        item.get("id_campanha"),
                    ),
                )
        return self.listar_checklist(id_pi)

    def listar_interacoes(self, id_pi):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT i.id, i.tipo, i.descricao, i.autor_id, i.created_at,
                       u.nome_completo AS autor_nome
                  FROM cadu_pi_interacao i
                  LEFT JOIN tbl_contato_cliente u
                         ON u.id_contato_cliente = i.autor_id
                 WHERE i.id_pi = %s
                 ORDER BY i.created_at DESC, i.id DESC
                """,
                (id_pi,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def criar_interacao(self, id_pi, tipo, descricao, autor_id):
        self.obter_pi(id_pi)
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cadu_pi_interacao (id_pi, tipo, descricao, autor_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id, tipo, descricao, autor_id, created_at
                """,
                (id_pi, tipo, descricao, autor_id),
            )
            return dict(cursor.fetchone())

    def listar_emails(self, id_pi, limite=50):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, tipo, assunto, destinatario_nome, destinatario_email,
                       status, brevo_message_id, erro, criado_por, enviado_em,
                       created_at
                  FROM cadu_pi_email_log
                 WHERE id_pi = %s
                 ORDER BY created_at DESC, id DESC
                 LIMIT %s
                """,
                (id_pi, limite),
            )
            return [dict(row) for row in cursor.fetchall()]

    def criar_email_log(self, id_pi, tipo, assunto, destinatario, html, autor_id):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cadu_pi_email_log
                       (id_pi, tipo, assunto, destinatario_nome,
                        destinatario_email, html, status, criado_por)
                VALUES (%s, %s, %s, %s, %s, %s, 'pendente', %s)
                RETURNING id
                """,
                (
                    id_pi,
                    tipo,
                    assunto,
                    destinatario.get("nome_completo"),
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
                UPDATE cadu_pi_email_log
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

    def listar_etapas(self, id_pi):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT etapa, concluida_em, concluida_por
                  FROM cadu_pi_operacao_etapa
                 WHERE id_pi = %s
                """,
                (id_pi,),
            )
            return {row["etapa"]: dict(row) for row in cursor.fetchall()}

    def obter_ultima_atualizacao(self, id_pi):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT l.data_acao, l.fk_id_usuario,
                       u.nome_completo AS usuario_nome
                  FROM tbl_admin_audit_log l
                  LEFT JOIN tbl_contato_cliente u
                    ON u.id_contato_cliente = l.fk_id_usuario
                 WHERE l.registro_id = %s
                   AND l.registro_tipo = 'cadu_pi'
                 ORDER BY l.data_acao DESC, l.id_log DESC
                 LIMIT 1
                """,
                (id_pi,),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    def sincronizar_etapas(self, id_pi, etapas_concluidas, autor_id):
        """Grava apenas conclusões novas; nunca é chamado por uma leitura GET."""
        with self._write() as cursor:
            for etapa in etapas_concluidas:
                cursor.execute(
                    """
                    INSERT INTO cadu_pi_operacao_etapa
                           (id_pi, etapa, concluida_em, concluida_por)
                    VALUES (%s, %s, date_trunc('second', CURRENT_TIMESTAMP), %s)
                    ON CONFLICT (id_pi, etapa) DO UPDATE
                       SET concluida_em = COALESCE(
                               cadu_pi_operacao_etapa.concluida_em,
                               EXCLUDED.concluida_em
                           ),
                           concluida_por = COALESCE(
                               cadu_pi_operacao_etapa.concluida_por,
                               EXCLUDED.concluida_por
                           ),
                           updated_at = date_trunc('second', CURRENT_TIMESTAMP)
                    """,
                    (id_pi, etapa, autor_id),
                )
        return self.listar_etapas(id_pi)
