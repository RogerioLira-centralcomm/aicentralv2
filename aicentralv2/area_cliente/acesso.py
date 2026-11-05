"""Quem pode entrar na Área do Cliente.

A liberação é por contato (``tbl_contato_cliente.area_cliente_acesso``), feita
pela equipe CentralComm no CRM v3. Enquanto a migração
``add_area_cliente_acesso_contato.sql`` não roda num banco, tudo aqui trata a
coluna como ``FALSE`` em vez de quebrar o CRM ou a área.
"""

from __future__ import annotations

import logging

import psycopg

logger = logging.getLogger(__name__)


def _db():
    from .. import db
    return db


def _sem_coluna(conn, exc) -> bool:
    """Coluna ainda não migrada: desfaz a transação e sinaliza o fallback."""
    if isinstance(exc, psycopg.errors.UndefinedColumn):
        conn.rollback()
        logger.warning("area_cliente_acesso ainda não existe neste banco.")
        return True
    return False


def flags_por_cliente(cliente_id) -> dict[str, bool]:
    """{id_contato: liberado} dos contatos de um cliente (vazio sem a coluna)."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_contato_cliente, area_cliente_acesso
                  FROM tbl_contato_cliente
                 WHERE pk_id_tbl_cliente = %s
                """,
                (cliente_id,),
            )
            return {str(r["id_contato_cliente"]): bool(r["area_cliente_acesso"]) for r in cursor.fetchall()}
    except Exception as exc:
        if _sem_coluna(conn, exc):
            return {}
        conn.rollback()
        raise


def definir_acesso(contato_id, ativo: bool, autor_id=None) -> dict | None:
    """Liga/desliga o acesso de um contato e registra na auditoria.

    Devolve ``{"id", "cliente_id", "ativo"}`` ou ``None`` se o contato não existe.
    Levanta ``RuntimeError`` se a migração ainda não foi aplicada.
    """
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_contato_cliente, pk_id_tbl_cliente, nome_completo, email,
                       area_cliente_acesso
                  FROM tbl_contato_cliente
                 WHERE id_contato_cliente = %s
                """,
                (contato_id,),
            )
            antes = cursor.fetchone()
            if not antes:
                return None
            cursor.execute(
                """
                UPDATE tbl_contato_cliente
                   SET area_cliente_acesso = %s, data_modificacao = NOW()
                 WHERE id_contato_cliente = %s
                """,
                (bool(ativo), contato_id),
            )
        conn.commit()
    except Exception as exc:
        if _sem_coluna(conn, exc):
            raise RuntimeError("A Área do Cliente ainda não foi habilitada neste banco.") from exc
        conn.rollback()
        raise

    if bool(antes["area_cliente_acesso"]) != bool(ativo):
        try:
            from ..audit import registrar_acao_admin
            registrar_acao_admin(
                user_id=autor_id,
                acao="APPROVE" if ativo else "REVOKE",
                modulo="area_cliente",
                descricao=(
                    f"{'Liberou' if ativo else 'Revogou'} a Área do Cliente para "
                    f"{antes['nome_completo'] or antes['email']}"
                ),
                registro_id=int(contato_id),
                registro_tipo="contato",
                dados_anteriores={"area_cliente_acesso": bool(antes["area_cliente_acesso"])},
                dados_novos={"area_cliente_acesso": bool(ativo)},
            )
        except Exception:
            logger.warning("Não foi possível auditar a liberação da Área do Cliente.", exc_info=True)

    return {"id": str(contato_id), "cliente_id": str(antes["pk_id_tbl_cliente"]), "ativo": bool(ativo)}


def liberacoes_por_cliente(cliente_id) -> dict[str, dict]:
    """{id_contato: última liberação/revogação} de todos os contatos do cliente."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (l.registro_id)
                       l.registro_id, l.data_acao, l.acao, u.nome_completo AS autor_nome
                  FROM tbl_admin_audit_log l
                  JOIN tbl_contato_cliente c ON c.id_contato_cliente = l.registro_id
                  LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = l.fk_id_usuario
                 WHERE l.modulo = 'area_cliente' AND c.pk_id_tbl_cliente = %s
                 ORDER BY l.registro_id, l.data_acao DESC
                """,
                (cliente_id,),
            )
            rows = cursor.fetchall()
    except Exception:
        conn.rollback()
        logger.warning("Auditoria da Área do Cliente indisponível.", exc_info=True)
        return {}
    return {str(r["registro_id"]): _liberacao(r) for r in rows}


def _liberacao(row) -> dict:
    return {
        "acao": row["acao"],
        "autor": row["autor_nome"] or "",
        "em": row["data_acao"].strftime("%d/%m/%Y") if row["data_acao"] else "",
    }


def ultima_liberacao(contato_id) -> dict | None:
    """Quem liberou e quando (última entrada de auditoria do contato)."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT l.data_acao, l.acao, u.nome_completo AS autor_nome
                  FROM tbl_admin_audit_log l
                  LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente = l.fk_id_usuario
                 WHERE l.modulo = 'area_cliente' AND l.registro_id = %s
                 ORDER BY l.data_acao DESC
                 LIMIT 1
                """,
                (contato_id,),
            )
            row = cursor.fetchone()
    except Exception:
        conn.rollback()
        logger.warning("Auditoria da Área do Cliente indisponível.", exc_info=True)
        return None
    return _liberacao(row) if row else None


_CONTEXTO_SQL = """
    SELECT c.id_contato_cliente, c.nome_completo, c.email, c.foto_url, c.status,
           c.pk_id_tbl_cliente, {flag} AS area_cliente_acesso,
           cli.nome_fantasia, cli.status AS cliente_status,
           vend.nome_completo AS executivo_nome, vend.email AS executivo_email,
           vend.telefone AS executivo_telefone, vend.foto_url AS executivo_foto_url
      FROM tbl_contato_cliente c
      JOIN tbl_cliente cli ON cli.id_cliente = c.pk_id_tbl_cliente
      LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = cli.vendas_central_comm
     WHERE c.id_contato_cliente = %s
"""


def contexto_usuario(user_id) -> dict | None:
    """Dados do contato logado, do cliente e do executivo, com o estado do acesso.

    ``liberado`` só é verdadeiro com contato ativo, cliente ativo e flag ligada.
    O ``cliente_id`` vem do cadastro atual do contato, nunca da sessão ou da URL.
    """
    if not user_id:
        return None
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(_CONTEXTO_SQL.format(flag="c.area_cliente_acesso"), (user_id,))
            row = cursor.fetchone()
    except Exception as exc:
        if not _sem_coluna(conn, exc):
            conn.rollback()
            raise
        with conn.cursor() as cursor:
            cursor.execute(_CONTEXTO_SQL.format(flag="FALSE"), (user_id,))
            row = cursor.fetchone()
    if not row:
        return None
    from ..campanha_acompanhamento_publico import _whatsapp

    nome = (row["nome_completo"] or "").strip() or (row["email"] or "").split("@")[0]
    partes = nome.split()
    iniciais = ((partes[0][:1] + (partes[-1][:1] if len(partes) > 1 else "")) if partes else "?").upper()
    executivo = None
    if row["executivo_nome"]:
        executivo = {
            "nome": row["executivo_nome"],
            "email": row["executivo_email"] or "",
            "whatsapp": _whatsapp(row["executivo_telefone"]),
            "foto_url": row["executivo_foto_url"] or "",
        }
    return {
        "user_id": int(row["id_contato_cliente"]),
        "nome": nome,
        "primeiro_nome": partes[0] if partes else nome,
        "iniciais": iniciais,
        "email": row["email"] or "",
        "foto_url": row["foto_url"] or "",
        "cliente_id": int(row["pk_id_tbl_cliente"]),
        "cliente_nome": row["nome_fantasia"] or "Cliente",
        "executivo": executivo,
        "liberado": bool(row["status"] and row["cliente_status"] and row["area_cliente_acesso"]),
    }
