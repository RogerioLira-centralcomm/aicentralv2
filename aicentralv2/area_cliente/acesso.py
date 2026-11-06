"""Quem pode entrar na Área do Cliente.

Aberta por padrão: todo contato ativo de cliente ativo (quem já entra no Cadu)
acessa a área. A equipe CentralComm só bloqueia, no CRM v3 ou na edição do
cliente no CentralX: o cliente inteiro (``tbl_cliente.area_cliente_bloqueada``)
ou um contato (``tbl_contato_cliente.area_cliente_bloqueado``). Enquanto a
migração ``add_area_cliente_bloqueio.sql`` não roda num banco, ninguém está
bloqueado, em vez de quebrar o CRM ou a área.
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
        logger.warning("Colunas de bloqueio da Área do Cliente ainda não existem neste banco.")
        return True
    return False


def flags_por_cliente(cliente_id) -> dict[str, bool]:
    """{id_contato: tem acesso} dos contatos de um cliente, pelo bloqueio do contato.

    O bloqueio do cliente inteiro fica em ``cliente_bloqueado``; sem a coluna, todos têm acesso.
    """
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_contato_cliente, area_cliente_bloqueado
                  FROM tbl_contato_cliente
                 WHERE pk_id_tbl_cliente = %s
                """,
                (cliente_id,),
            )
            return {str(r["id_contato_cliente"]): not r["area_cliente_bloqueado"] for r in cursor.fetchall()}
    except Exception as exc:
        if _sem_coluna(conn, exc):
            return {}
        conn.rollback()
        raise


def cliente_bloqueado(cliente_id) -> bool:
    """True se a área está desligada para o cliente inteiro (False sem a coluna)."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT area_cliente_bloqueada FROM tbl_cliente WHERE id_cliente = %s", (cliente_id,))
            row = cursor.fetchone()
            return bool(row and row["area_cliente_bloqueada"])
    except Exception as exc:
        if _sem_coluna(conn, exc):
            return False
        conn.rollback()
        raise


def _auditar(autor_id, ativo, descricao, registro_id, registro_tipo, antes, depois):
    try:
        from ..audit import registrar_acao_admin
        registrar_acao_admin(
            user_id=autor_id, acao="APPROVE" if ativo else "REVOKE", modulo="area_cliente",
            descricao=descricao, registro_id=int(registro_id), registro_tipo=registro_tipo,
            dados_anteriores=antes, dados_novos=depois,
        )
    except Exception:
        logger.warning("Não foi possível auditar o acesso à Área do Cliente.", exc_info=True)


def definir_acesso(contato_id, ativo: bool, autor_id=None) -> dict | None:
    """Libera (desbloqueia) ou bloqueia um contato e registra na auditoria.

    Devolve ``{"id", "cliente_id", "ativo"}`` ou ``None`` se o contato não existe.
    Levanta ``RuntimeError`` se a migração ainda não foi aplicada.
    """
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_contato_cliente, pk_id_tbl_cliente, nome_completo, email,
                       area_cliente_bloqueado
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
                   SET area_cliente_bloqueado = %s, data_modificacao = NOW()
                 WHERE id_contato_cliente = %s
                """,
                (not ativo, contato_id),
            )
        conn.commit()
    except Exception as exc:
        if _sem_coluna(conn, exc):
            raise RuntimeError("A Área do Cliente ainda não foi habilitada neste banco.") from exc
        conn.rollback()
        raise

    tinha = not antes["area_cliente_bloqueado"]
    if tinha != bool(ativo):
        _auditar(autor_id, ativo,
                 f"{'Liberou' if ativo else 'Bloqueou'} a Área do Cliente para {antes['nome_completo'] or antes['email']}",
                 contato_id, "contato", {"area_cliente_bloqueado": not tinha}, {"area_cliente_bloqueado": not ativo})
    # Só quem estava bloqueado e voltou recebe o aviso; a liberação padrão é silenciosa.
    if ativo and not tinha:
        try:
            from . import emails
            contato = _contato_para_email(contato_id)
            if contato.get("status") and contato.get("email") and not cliente_bloqueado(antes["pk_id_tbl_cliente"]):
                emails.acesso_liberado(contato)
        except Exception:
            logger.warning("E-mail de acesso liberado não enviado.", exc_info=True)

    return {"id": str(contato_id), "cliente_id": str(antes["pk_id_tbl_cliente"]), "ativo": bool(ativo)}


def definir_acesso_cliente(cliente_id, ativo: bool, autor_id=None) -> dict | None:
    """Liga/desliga a área para o cliente inteiro (todos os contatos). Sem e-mail em massa."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id_cliente, nome_fantasia, area_cliente_bloqueada FROM tbl_cliente WHERE id_cliente = %s",
                           (cliente_id,))
            antes = cursor.fetchone()
            if not antes:
                return None
            cursor.execute("UPDATE tbl_cliente SET area_cliente_bloqueada = %s WHERE id_cliente = %s", (not ativo, cliente_id))
        conn.commit()
    except Exception as exc:
        if _sem_coluna(conn, exc):
            raise RuntimeError("A Área do Cliente ainda não foi habilitada neste banco.") from exc
        conn.rollback()
        raise
    tinha = not antes["area_cliente_bloqueada"]
    if tinha != bool(ativo):
        _auditar(autor_id, ativo,
                 f"{'Liberou' if ativo else 'Bloqueou'} a Área do Cliente para a empresa {antes['nome_fantasia']}",
                 cliente_id, "cliente", {"area_cliente_bloqueada": not tinha}, {"area_cliente_bloqueada": not ativo})
    return {"cliente_id": str(cliente_id), "ativo": bool(ativo)}


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
                 WHERE l.modulo = 'area_cliente' AND l.registro_tipo = 'contato' AND c.pk_id_tbl_cliente = %s
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


def _contato_para_email(contato_id) -> dict:
    """Dados do contato para o e-mail de acesso; diz só SE há senha, nunca o hash."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT email, nome_completo, status, pk_id_tbl_cliente,
                       (NULLIF(senha, '') IS NOT NULL) AS tem_senha
                  FROM tbl_contato_cliente WHERE id_contato_cliente = %s
                """,
                (contato_id,),
            )
            return dict(cursor.fetchone() or {})
    except Exception:
        conn.rollback()
        raise


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
                 WHERE l.modulo = 'area_cliente' AND l.registro_tipo = 'contato' AND l.registro_id = %s
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
    SELECT c.id_contato_cliente, c.nome_completo, c.email, c.foto_url, c.status, c.user_type,
           c.pk_id_tbl_cliente, {contato} AS contato_bloqueado, {cliente} AS cliente_bloqueado,
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

    ``liberado``: contato ativo, cliente ativo e nenhum dos dois bloqueado.
    O ``cliente_id`` vem do cadastro atual do contato, nunca da sessão ou da URL.
    """
    if not user_id:
        return None
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(_CONTEXTO_SQL.format(contato="c.area_cliente_bloqueado", cliente="cli.area_cliente_bloqueada"), (user_id,))
            row = cursor.fetchone()
    except Exception as exc:
        if not _sem_coluna(conn, exc):
            conn.rollback()
            raise
        with conn.cursor() as cursor:
            cursor.execute(_CONTEXTO_SQL.format(contato="FALSE", cliente="FALSE"), (user_id,))
            row = cursor.fetchone()
    if not row:
        return None

    nome = (row["nome_completo"] or "").strip() or (row["email"] or "").split("@")[0]
    partes = nome.split()
    iniciais = ((partes[0][:1] + (partes[-1][:1] if len(partes) > 1 else "")) if partes else "?").upper()
    from ..auth import is_reserved_org_name

    liberado = bool(row["status"] and row["cliente_status"]
                    and not row["contato_bloqueado"] and not row["cliente_bloqueado"])
    return {
        "user_id": int(row["id_contato_cliente"]),
        "nome": nome,
        "primeiro_nome": partes[0] if partes else nome,
        "iniciais": iniciais,
        "email": row["email"] or "",
        "foto_url": row["foto_url"] or "",
        "cliente_id": int(row["pk_id_tbl_cliente"]),
        "cliente_nome": row["nome_fantasia"] or "Cliente",
        "executivo": _executivo(row),
        "liberado": liberado,
        # Toda a equipe CentralComm (cliente 174) pode ver a área como qualquer cliente com PI no ano.
        "pode_ver_como": liberado and is_reserved_org_name(row["nome_fantasia"]),
        "ver_como": False,
    }


def _executivo(row) -> dict | None:
    from ..campanha_acompanhamento_publico import _whatsapp
    if not row.get("executivo_nome"):
        return None
    return {
        "nome": row["executivo_nome"],
        "email": row.get("executivo_email") or "",
        "whatsapp": _whatsapp(row.get("executivo_telefone")),
        "foto_url": row.get("executivo_foto_url") or "",
    }


_VER_COMO_SQL = """
    SELECT cli.id_cliente, cli.nome_fantasia,
           BOOL_OR(x.papel = 'agencia') AS agencia, COUNT(DISTINCT x.id_pi) AS n_pis
      FROM (
            SELECT pi.id_cliente AS id_cliente, pi.id_pi, 'cliente' AS papel FROM cadu_pi pi
             WHERE {filtro}
            UNION ALL
            SELECT pi.id_agencia, pi.id_pi, 'agencia' FROM cadu_pi pi
             WHERE pi.id_agencia IS NOT NULL AND {filtro}
           ) x
      JOIN tbl_cliente cli ON cli.id_cliente = x.id_cliente
     WHERE cli.status IS TRUE
     GROUP BY cli.id_cliente, cli.nome_fantasia
     ORDER BY cli.nome_fantasia
"""
# PIs validados no ano: fora "Em aprovação" (1) e "Cancelado" (6).
_PI_VALIDADO_NO_ANO = """COALESCE(pi.id_sub_status_pi, 0) NOT IN (1, 6)
              AND (EXTRACT(YEAR FROM pi.periodo_inicio) = %(ano)s OR EXTRACT(YEAR FROM pi.periodo_fim) = %(ano)s)"""


def clientes_para_ver_como(ano: int) -> list[dict]:
    """Clientes e agências ativos com PI validado no ano, para o modo "ver como"."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(_VER_COMO_SQL.format(filtro=_PI_VALIDADO_NO_ANO), {"ano": ano})
            rows = cursor.fetchall()
    except Exception:
        conn.rollback()
        raise
    return [{"id": int(r["id_cliente"]), "nome": r["nome_fantasia"] or f"Cliente {r['id_cliente']}",
             "tipo": "Agência" if r["agencia"] else "Cliente", "n_pis": int(r["n_pis"])} for r in rows]


def aplicar_ver_como(usuario: dict, cliente_id, ano: int, opcoes=None) -> dict | None:
    """Troca o cliente do usuário pelo escolhido, só se ele estiver na lista permitida."""
    if not usuario.get("pode_ver_como"):
        return None
    try:
        cliente_id = int(cliente_id)
    except (TypeError, ValueError):
        return None
    alvo = next((c for c in (opcoes if opcoes is not None else clientes_para_ver_como(ano)) if c["id"] == cliente_id), None)
    if not alvo:
        return None
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT vend.nome_completo AS executivo_nome, vend.email AS executivo_email,
                       vend.telefone AS executivo_telefone, vend.foto_url AS executivo_foto_url
                  FROM tbl_cliente cli
                  LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = cli.vendas_central_comm
                 WHERE cli.id_cliente = %s
                """,
                (cliente_id,),
            )
            row = cursor.fetchone() or {}
    except Exception:
        conn.rollback()
        raise
    return {
        **usuario,
        "cliente_id": alvo["id"], "cliente_nome": alvo["nome"], "executivo": _executivo(row),
        "ver_como": True, "ver_como_tipo": alvo["tipo"],
        "cliente_real_id": usuario["cliente_id"], "cliente_real_nome": usuario["cliente_nome"],
    }
