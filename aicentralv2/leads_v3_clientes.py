"""Leads v3 ↔ CRM v3: cliente que volta para lead e lead que volta a ser cliente.

Cliente → lead (clique do executivo no CRM v3):
- bloqueia se houver PI em andamento (nem finalizado nem cancelado);
- reabre o lead de onde o cliente veio (ou cria um), em Nutrição, com o executivo do cliente;
- leva os contatos do cliente que o lead ainda não tem;
- marca como Expirada as cotações em aberto (rascunho, enviada, em acompanhamento, próximo de aprovar),
  com nota do motivo; aprovadas, rejeitadas e expiradas ficam como estão;
- planejamentos não mudam (continuam ligados ao cliente);
- o cliente fica inativo (tbl_cliente.status = FALSE) e sai da lista do CRM v3.

Lead → cliente, quando o lead veio de um cliente: reativa o mesmo cadastro em vez de criar outro.
"""

from __future__ import annotations

from datetime import datetime

from .leads_v3_prospeccao import ProspeccaoError

# Cotação nesses estados ainda pode virar negócio: vai para Expirada quando o cliente volta a ser lead.
COTACAO_FECHADA = {"aprovada", "rejeitada", "expirada"}
PI_ENCERRADO = ("Finalizado", "Cancelado")


def _colunas(cursor, tabela):
    cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s", [tabela])
    return {r["column_name"]: r["data_type"] for r in cursor.fetchall()}


def _slug_cotacao(rotulo):
    from .crm_v3_data import COTACAO_STATUS_ALIASES

    raw = str(rotulo or "").strip().casefold()
    return COTACAO_STATUS_ALIASES.get(raw) or raw.replace(" ", "-")


def pis_em_andamento(cursor, cliente_id):
    cursor.execute(
        """
        SELECT p.id_pi, p.codigo_pi_cc, p.titulo_pi, ssp.display AS situacao
          FROM cadu_pi p
          LEFT JOIN cadu_pi_sub_status ssp ON ssp.key = p.id_sub_status_pi
         WHERE p.id_cliente = %s AND COALESCE(ssp.display, '') <> ALL(%s)
         ORDER BY p.id_pi DESC
         LIMIT 20
        """,
        [cliente_id, list(PI_ENCERRADO)],
    )
    return cursor.fetchall()


def cotacoes_em_aberto(cursor, cliente_id):
    cols = _colunas(cursor, "cadu_cotacoes")
    vivas = "AND c.deleted_at IS NULL" if "deleted_at" in cols else ""
    cursor.execute(
        f"""
        SELECT c.id, c.nome_campanha, c.status::text AS status_bruto, COALESCE(st.descricao, c.status::text) AS rotulo
          FROM cadu_cotacoes c
          LEFT JOIN cadu_cotacoes_status st ON TRIM(c.status::text) = st.id::text
         WHERE c.client_id = %s {vivas}
         ORDER BY c.id
        """,
        [cliente_id],
    )
    return [r for r in cursor.fetchall() if _slug_cotacao(r["rotulo"]) not in COTACAO_FECHADA]


def _expirar_cotacoes(cursor, cotacoes, nota):
    """Põe as cotações em Expirada no mesmo formato da coluna (FK numérica ou rótulo) e anota o motivo."""
    if not cotacoes:
        return 0
    cols = _colunas(cursor, "cadu_cotacoes")
    cursor.execute("SELECT id FROM cadu_cotacoes_status WHERE LOWER(TRIM(descricao)) = 'expirada' LIMIT 1")
    status_row = cursor.fetchone()
    numerica = cols.get("status") in ("integer", "smallint", "bigint")
    for cot in cotacoes:
        if numerica or str(cot["status_bruto"] or "").strip().isdigit():
            if not status_row:
                raise ProspeccaoError("Não achei o status 'Expirada' nas cotações. Fale com o suporte.")
            valor = status_row["id"] if numerica else str(status_row["id"])
        else:
            valor = "Expirada"
        sets, params = ["status = %s"], [valor]
        if "observacoes" in cols:
            sets.append("observacoes = TRIM(BOTH E'\\n' FROM COALESCE(observacoes, '') || E'\\n' || %s)")
            params.append(nota)
        if "updated_at" in cols:
            sets.append("updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)")
        cursor.execute(f"UPDATE cadu_cotacoes SET {', '.join(sets)} WHERE id = %s", [*params, cot["id"]])
    return len(cotacoes)


def _cliente(cursor, cliente_id, *, travar=False):
    cursor.execute(
        f"SELECT id_cliente, nome_fantasia, razao_social, cnpj, status, vendas_central_comm FROM tbl_cliente WHERE id_cliente = %s"
        f"{' FOR UPDATE' if travar else ''}",
        [cliente_id],
    )
    cliente = cursor.fetchone()
    if not cliente:
        raise ProspeccaoError("Cliente não encontrado.")
    return cliente


def _lead_do_cliente(cursor, cliente_id):
    cursor.execute(
        """
        SELECT id, status FROM cadu_leads
         WHERE convertido_cliente_id = %s OR cliente_origem_id = %s
         ORDER BY updated_at DESC NULLS LAST, id DESC
         LIMIT 1
        """,
        [cliente_id, cliente_id],
    )
    return cursor.fetchone()


def _contatos_do_cliente(cursor, cliente_id):
    cursor.execute(
        """
        SELECT nome_completo AS nome, email, telefone FROM tbl_contato_cliente
         WHERE pk_id_tbl_cliente = %s AND COALESCE(TRIM(nome_completo), '') <> ''
         ORDER BY 1
        """,
        [cliente_id],
    )
    return cursor.fetchall()


def previa_volta(cursor, cliente_id):
    """O que acontece se o cliente voltar para lead: para a tela confirmar antes."""
    cliente = _cliente(cursor, cliente_id)
    lead = _lead_do_cliente(cursor, cliente_id)
    return {
        "cliente": {"id": cliente["id_cliente"], "nome": cliente["nome_fantasia"] or cliente["razao_social"], "ativo": bool(cliente["status"])},
        "pis_em_andamento": pis_em_andamento(cursor, cliente_id),
        "cotacoes_em_aberto": [{"id": c["id"], "nome": c["nome_campanha"], "status": c["rotulo"]} for c in cotacoes_em_aberto(cursor, cliente_id)],
        "contatos": len(_contatos_do_cliente(cursor, cliente_id)),
        "lead_existente": lead["id"] if lead else None,
    }


def cliente_para_lead(cursor, cliente_id, *, usuario_id, usuario_nome=None, motivo=None, agora=None):
    agora = agora or datetime.now()
    cliente = _cliente(cursor, cliente_id, travar=True)
    if not cliente["status"]:
        lead = _lead_do_cliente(cursor, cliente_id)
        if lead:
            raise ProspeccaoError("Este cliente já voltou para leads.")
    pis = pis_em_andamento(cursor, cliente_id)
    if pis:
        lista = ", ".join(str(p.get("codigo_pi_cc") or p.get("titulo_pi") or p["id_pi"]) for p in pis[:5])
        raise ProspeccaoError(f"O cliente tem {len(pis)} PI em andamento ({lista}). Finalize ou cancele antes de enviar para leads.")
    nome = cliente["nome_fantasia"] or cliente["razao_social"] or "Cliente"
    motivo = " ".join(str(motivo or "").split())[:300] or None
    lead = _lead_do_cliente(cursor, cliente_id)
    if lead:
        cursor.execute(
            """
            UPDATE cadu_leads
               SET status = 'nutricao', convertido_cliente_id = NULL, cliente_origem_id = %s, voltou_de_cliente_em = %s,
                   id_executivo = COALESCE(%s, id_executivo), updated_at = CURRENT_TIMESTAMP
             WHERE id = %s
            """,
            [cliente_id, agora, cliente["vendas_central_comm"], lead["id"]],
        )
        lead_id, reaberto = lead["id"], True
    else:
        cursor.execute(
            """
            INSERT INTO cadu_leads (nome, empresa, email, fonte, origem, status, tipo_lead, id_executivo, atribuido_em,
                                    cnpj, cliente_origem_id, voltou_de_cliente_em)
            VALUES (%s, %s, '', 'outro', 'crm', 'nutricao', 'cliente', %s, CASE WHEN %s::int IS NOT NULL THEN NOW() END,
                    %s, %s, %s)
            RETURNING id
            """,
            [nome, nome, cliente["vendas_central_comm"], cliente["vendas_central_comm"], cliente["cnpj"] or None, cliente_id, agora],
        )
        lead_id, reaberto = cursor.fetchone()["id"], False

    cursor.execute("SELECT LOWER(COALESCE(email, '')) AS email, LOWER(TRIM(nome)) AS nome FROM cadu_lead_contatos WHERE id_lead = %s", [lead_id])
    existentes = cursor.fetchall()
    emails = {r["email"] for r in existentes if r["email"]}
    nomes = {r["nome"] for r in existentes if r["nome"]}
    levados = 0
    for c in _contatos_do_cliente(cursor, cliente_id):
        email = (c["email"] or "").strip().lower()
        if (email and email in emails) or c["nome"].strip().lower() in nomes:
            continue
        cursor.execute(
            "INSERT INTO cadu_lead_contatos (id_lead, nome, email, telefone, origem_dado) VALUES (%s, %s, %s, %s, 'manual')",
            [lead_id, c["nome"].strip(), email or None, (c["telefone"] or "").strip() or None],
        )
        emails.add(email); nomes.add(c["nome"].strip().lower())
        levados += 1

    cotacoes = cotacoes_em_aberto(cursor, cliente_id)
    expiradas = _expirar_cotacoes(cursor, cotacoes, f"[{agora.strftime('%d/%m/%Y')}] Expirada: o cliente voltou para leads"
                                                    + (f" ({motivo})" if motivo else "") + ".")
    cursor.execute("UPDATE tbl_cliente SET status = FALSE WHERE id_cliente = %s", [cliente_id])
    partes = [f"Voltou de cliente para lead pelo CRM{f': {motivo}' if motivo else ''}."]
    if levados:
        partes.append(f"{levados} contato{'s' if levados > 1 else ''} do cliente {'vieram' if levados > 1 else 'veio'} junto.")
    if expiradas:
        partes.append(f"{expiradas} cotaç{'ões' if expiradas > 1 else 'ão'} em aberto marcada{'s' if expiradas > 1 else ''} como Expirada.")
    partes.append("Planejamentos continuam ligados ao cliente.")
    cursor.execute(
        """
        INSERT INTO cadu_lead_atividades (id_lead, tipo, descricao, id_usuario, usuario_nome)
        VALUES (%s, 'status_change', %s, %s, %s)
        """,
        [lead_id, " ".join(partes), usuario_id, usuario_nome],
    )
    return {"lead_id": lead_id, "reaberto": reaberto, "contatos": levados, "cotacoes_expiradas": expiradas}


def reativar_cliente(cursor, lead_id, *, usuario_id, usuario_nome=None):
    """Lead que veio de um cliente volta a ser cliente: reativa o mesmo cadastro e leva os contatos novos."""
    cursor.execute("SELECT id, cliente_origem_id, convertido_cliente_id FROM cadu_leads WHERE id = %s FOR UPDATE", [lead_id])
    lead = cursor.fetchone()
    if not lead:
        raise ProspeccaoError("Lead não encontrado.")
    if lead["convertido_cliente_id"]:
        raise ProspeccaoError("Este lead já é cliente.")
    if not lead["cliente_origem_id"]:
        raise ProspeccaoError("Este lead não veio de um cliente; use a conversão normal.")
    cliente = _cliente(cursor, lead["cliente_origem_id"], travar=True)
    cliente_id = cliente["id_cliente"]
    cursor.execute(
        "SELECT LOWER(COALESCE(email, '')) AS email, LOWER(TRIM(nome_completo)) AS nome FROM tbl_contato_cliente WHERE pk_id_tbl_cliente = %s",
        [cliente_id],
    )
    existentes = cursor.fetchall()
    emails = {r["email"] for r in existentes if r["email"]}
    nomes = {r["nome"] for r in existentes if r["nome"]}
    cursor.execute("SELECT nome, email, telefone FROM cadu_lead_contatos WHERE id_lead = %s AND COALESCE(TRIM(nome), '') <> ''", [lead_id])
    levados = 0
    for c in cursor.fetchall():
        email = (c["email"] or "").strip().lower()
        if (email and email in emails) or c["nome"].strip().lower() in nomes:
            continue
        cursor.execute(
            "INSERT INTO tbl_contato_cliente (pk_id_tbl_cliente, nome_completo, email, telefone) VALUES (%s, %s, %s, %s)",
            [cliente_id, c["nome"].strip(), email or None, c["telefone"]],
        )
        emails.add(email); nomes.add(c["nome"].strip().lower())
        levados += 1
    cursor.execute("UPDATE tbl_cliente SET status = TRUE WHERE id_cliente = %s", [cliente_id])
    cursor.execute(
        """
        UPDATE cadu_leads SET status = 'fechado_ganho', convertido_cliente_id = %s, data_conversao = NOW(), updated_at = CURRENT_TIMESTAMP
         WHERE id = %s
        """,
        [cliente_id, lead_id],
    )
    cursor.execute(
        "INSERT INTO cadu_lead_atividades (id_lead, tipo, descricao, id_usuario, usuario_nome) VALUES (%s, 'status_change', %s, %s, %s)",
        [lead_id, f"Voltou a ser cliente: cadastro {cliente['nome_fantasia'] or cliente_id} reativado no CRM"
                  + (f", com {levados} contato{'s' if levados > 1 else ''} novo{'s' if levados > 1 else ''}." if levados else "."),
         usuario_id, usuario_nome],
    )
    return {"cliente_id": cliente_id, "contatos": levados}
