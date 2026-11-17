"""Leituras do cadastro antigo (clientes, contatos, cotações, PIs): **somente leitura**.

A Entrada de PI nunca escreve em ``tbl_cliente``, ``cadu_pi`` ou ``cadu_cotacoes``.
"""

from __future__ import annotations

from . import normalizar as n


def _db():
    from .. import db
    return db


def _consulta(sql, params=(), *, uma=False):
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone() if uma else cursor.fetchall()
    except Exception:
        conn.rollback()
        raise


def cliente_por_cnpj(cnpj):
    digitos = n.cnpj_digitos(cnpj)
    if len(digitos) != 14:
        return None
    row = _consulta(
        """SELECT id_cliente, cnpj, razao_social, nome_fantasia, inscricao_estadual, inscricao_municipal, endereco, logradouro,
                  numero, complemento, bairro, cep, cidade, estado, email, telefone, vendas_central_comm,
                  observacoes_comerciais_adicionais, status
             FROM tbl_cliente WHERE regexp_replace(COALESCE(cnpj, ''), '\\D', '', 'g') = %s
            ORDER BY (status IS TRUE) DESC, id_cliente LIMIT 1""", (digitos,), uma=True)
    return dict(row) if row else None


def emails_dos_contatos(id_cliente) -> set:
    if not id_cliente:
        return set()
    rows = _consulta("SELECT lower(email) AS email FROM tbl_contato_cliente WHERE pk_id_tbl_cliente = %s AND COALESCE(email, '') <> ''", (id_cliente,))
    return {r["email"] for r in rows}


def pi_existente(numero):
    chave = n.chave_numero_pi(numero)
    if not chave:
        return None
    row = _consulta(
        """SELECT id_pi, COALESCE(codigo_pi_cc, codigo_pi_ag) AS codigo, titulo_pi FROM cadu_pi
            WHERE ltrim(upper(regexp_replace(COALESCE(codigo_pi_cc, ''), '[^0-9A-Za-z]', '', 'g')), '0') = %s
               OR ltrim(upper(regexp_replace(COALESCE(codigo_pi_ag, ''), '[^0-9A-Za-z]', '', 'g')), '0') = %s
            ORDER BY id_pi DESC LIMIT 1""", (chave, chave), uma=True)
    return dict(row) if row else None


def cotacoes_do_cliente(id_cliente, id_agencia=None, limite=40):
    """Cotações do cliente do PI (ou, sem cliente no cadastro, da agência). Mais recentes primeiro; as apagadas ficam de fora."""
    if not id_cliente and not id_agencia:
        return []
    rows = _consulta(
        """SELECT id, numero_cotacao, nome_campanha, periodo_inicio, periodo_fim, status, valor_total_proposta, budget_estimado,
                  plataforma_campanha, tipo_de_contrato, client_id, agencia_id
             FROM cadu_cotacoes
            WHERE deleted_at IS NULL AND (client_id = %s::integer OR (%s::integer IS NULL AND agencia_id = %s::integer))
            ORDER BY created_at DESC LIMIT %s""", (id_cliente, id_cliente, id_agencia, int(limite)))
    return [dict(r) for r in rows]


def cotacao_completa(id_cotacao):
    cab = _consulta(
        """SELECT id, numero_cotacao, nome_campanha, periodo_inicio, periodo_fim, status, valor_total_proposta, budget_estimado,
                  plataforma_campanha, tipo_de_contrato, client_id, agencia_id
             FROM cadu_cotacoes WHERE id = %s AND deleted_at IS NULL""", (id_cotacao,), uma=True)
    if not cab:
        return None
    linhas = _consulta(
        """SELECT plataforma, formatos, formato, objetivo_kpi, formato_compra, praca, segmentacao, volume_contratado,
                  valor_unitario, valor_unitario_negociado, investimento_bruto, investimento_liquido, valor_total, data_inicio,
                  data_fim, is_subtotal, is_header
             FROM cadu_cotacao_linhas WHERE cotacao_id = %s AND COALESCE(is_deleted, FALSE) = FALSE ORDER BY ordem, id""", (id_cotacao,))
    return {**dict(cab), "linhas": [dict(l) for l in linhas]}


def contexto(pi: dict) -> dict:
    """Tudo do cadastro que a leitura precisa: cliente, agência, executivo da conta, PI existente e e-mails de contato."""
    cliente = cliente_por_cnpj((pi.get("cliente") or {}).get("cnpj"))
    agencia = cliente_por_cnpj((pi.get("agencia") or {}).get("cnpj"))
    return {
        "cliente": cliente, "agencia": agencia,
        "cliente_id": (cliente or {}).get("id_cliente"), "agencia_id": (agencia or {}).get("id_cliente"),
        "executivo_id": (cliente or {}).get("vendas_central_comm"),
        "pi_existente": pi_existente(pi.get("numero_pi")),
        "emails": {"cliente": emails_dos_contatos((cliente or {}).get("id_cliente")), "agencia": emails_dos_contatos((agencia or {}).get("id_cliente"))},
        "observacoes": {"cliente": (cliente or {}).get("observacoes_comerciais_adicionais") or ""},
    }


def executivo_da_conta(id_cliente):
    """Executivo comercial (``vendas_central_comm``) da conta de quem envia pelo hub; None se a conta não tem."""
    if not id_cliente:
        return None
    row = _consulta("SELECT vendas_central_comm FROM tbl_cliente WHERE id_cliente = %s", (id_cliente,), uma=True)
    return (row or {}).get("vendas_central_comm")


def contato_por_id(id_contato):
    if not id_contato:
        return None
    row = _consulta(
        """SELECT c.id_contato_cliente, c.nome_completo, c.email, cli.nome_fantasia AS cliente_nome
             FROM tbl_contato_cliente c LEFT JOIN tbl_cliente cli ON cli.id_cliente = c.pk_id_tbl_cliente
            WHERE c.id_contato_cliente = %s""", (id_contato,), uma=True)
    return dict(row) if row else None
