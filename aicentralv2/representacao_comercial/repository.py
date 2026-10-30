"""Persistência da trilha de representação comercial."""

from __future__ import annotations

import os
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import current_app

from aicentralv2.representacao_comercial.domain import CODIGO_SERVICO_NF_COMISSAO
from aicentralv2.representacao_comercial.parceiros import (
    VENCIMENTO_D_PLUS_2,
    VENCIMENTO_DIA_20,
    metadados_trilha,
)


def _upload_dir_pi_rep():
    base = current_app.static_folder
    path = os.path.join(base, "uploads", "pi_representacao")
    os.makedirs(path, exist_ok=True)
    return path


def listar_relatorios_pi(id_pi: int) -> List[Dict[str, Any]]:
    from aicentralv2.db import get_db

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM cadu_pi_representacao_relatorio
            WHERE id_pi = %s
            ORDER BY created_at DESC
            """,
            (id_pi,),
        )
        return [dict(r) for r in cur.fetchall()]


def criar_relatorio_pi(
    id_pi: int,
    *,
    tipo: str,
    periodo_inicio=None,
    periodo_fim=None,
    arquivo_path=None,
    arquivo_nome=None,
    observacoes=None,
    created_by=None,
) -> int:
    from aicentralv2.db import get_db

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cadu_pi_representacao_relatorio (
                id_pi, tipo, periodo_inicio, periodo_fim,
                arquivo_path, arquivo_nome, observacoes, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                id_pi,
                tipo,
                periodo_inicio,
                periodo_fim,
                arquivo_path,
                arquivo_nome,
                observacoes,
                created_by,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return int(row["id"])


def marcar_relatorio_enviado_cliente(rel_id: int) -> bool:
    from aicentralv2.db import get_db

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cadu_pi_representacao_relatorio
            SET enviado_cliente_em = DATE_TRUNC('second', CURRENT_TIMESTAMP)
            WHERE id = %s
            """,
            (rel_id,),
        )
        conn.commit()
        return cur.rowcount > 0


def checklist_cotacao_representacao(cotacao_id: int) -> Dict[str, Any]:
    from aicentralv2.db import get_db, obter_anexos_cotacao, obter_cotacao_por_id
    from aicentralv2.representacao_comercial.domain import (
        DESCRICAO_ANEXO_PLANILHA_PARCEIRO,
        DESCRICAO_ANEXO_PROPOSTA_PDF_PARCEIRO,
        eh_representacao_comercial,
    )
    from aicentralv2.representacao_comercial.parceiros import (
        FLUXO_PDF_REPASSA,
        resolver_trilha_parceiro,
    )

    cotacao = obter_cotacao_por_id(cotacao_id)
    if not cotacao or not eh_representacao_comercial(cotacao):
        return {"aplicavel": False}
    trilha = cotacao.get("trilha_representacao") or resolver_trilha_parceiro(
        cotacao.get("id_parceiro"), cotacao.get("parceiro_nome")
    )
    meta = metadados_trilha(trilha)
    anexos = obter_anexos_cotacao(cotacao_id) or []
    descricoes = {(a.get("descricao") or "").strip() for a in anexos if not a.get("deleted_at")}
    if meta["fluxo_proposta"] == FLUXO_PDF_REPASSA:
        doc_ok = DESCRICAO_ANEXO_PROPOSTA_PDF_PARCEIRO in descricoes
        doc_label = "PDF do parceiro"
    else:
        doc_ok = DESCRICAO_ANEXO_PLANILHA_PARCEIRO in descricoes
        doc_label = "Planilha do parceiro"
    return {
        "aplicavel": True,
        "trilha": trilha,
        "trilha_label": meta["rotulo"],
        "fluxo_proposta": meta["fluxo_proposta"],
        "documento_esperado": doc_label,
        "documento_ok": doc_ok,
        "proposta_pronta": bool(cotacao.get("proposta_representacao_pronta")),
        "parceiro_id": cotacao.get("id_parceiro"),
    }


def marcar_proposta_representacao_pronta(cotacao_id: int, pronta: bool = True) -> bool:
    from aicentralv2.db import get_db

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cadu_cotacoes
            SET proposta_representacao_pronta = %s,
                updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
            WHERE id = %s
            """,
            (bool(pronta), cotacao_id),
        )
        conn.commit()
        return cur.rowcount > 0


def _calcular_vencimento(competencia: date, vencimento_tipo: str) -> date:
    if vencimento_tipo == VENCIMENTO_D_PLUS_2:
        return date.today() + timedelta(days=2)
    ultimo = monthrange(competencia.year, competencia.month)[1]
    dia = min(20, ultimo)
    return date(competencia.year, competencia.month, dia)


def listar_nf_comissao(id_parceiro: Optional[int] = None) -> List[Dict[str, Any]]:
    from aicentralv2.db import get_db

    conn = get_db()
    with conn.cursor() as cur:
        if id_parceiro:
            cur.execute(
                """
                SELECT n.*, c.nome_fantasia AS parceiro_nome
                FROM cadu_nf_comissao_representacao n
                LEFT JOIN tbl_cliente c ON c.id_cliente = n.id_parceiro
                WHERE n.id_parceiro = %s
                ORDER BY n.competencia DESC
                """,
                (id_parceiro,),
            )
        else:
            cur.execute(
                """
                SELECT n.*, c.nome_fantasia AS parceiro_nome
                FROM cadu_nf_comissao_representacao n
                LEFT JOIN tbl_cliente c ON c.id_cliente = n.id_parceiro
                ORDER BY n.competencia DESC
                LIMIT 200
                """
            )
        return [dict(r) for r in cur.fetchall()]


def criar_nf_comissao_mes(id_parceiro: int, competencia: date, id_pis: List[int]) -> int:
    from aicentralv2.db import get_db, obter_cadu_pi_por_id
    from aicentralv2.representacao_comercial.parceiros import resolver_trilha_parceiro

    trilha = resolver_trilha_parceiro(id_parceiro, None)
    venc = _calcular_vencimento(competencia, metadados_trilha(trilha)["vencimento_nf"])
    total = 0.0
    itens = []
    for id_pi in id_pis:
        pi = obter_cadu_pi_por_id(id_pi)
        if not pi or int(pi.get("id_parceiro") or 0) != int(id_parceiro):
            continue
        from aicentralv2.db import parse_valor_monetario_para_float

        val = pi.get("comissao_prevista_estimada") or pi.get("comissao_parceiro") or 0
        v = parse_valor_monetario_para_float(val) or 0.0
        total += v
        itens.append((id_pi, v, pi.get("codigo_pi_cc"), pi.get("numero_io")))

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cadu_nf_comissao_representacao (
                id_parceiro, competencia, valor_comissao, codigo_servico,
                vencimento, status, discriminacao
            ) VALUES (%s, %s, %s, %s, %s, 'rascunho', %s)
            ON CONFLICT (id_parceiro, competencia) DO UPDATE
            SET valor_comissao = EXCLUDED.valor_comissao,
                vencimento = EXCLUDED.vencimento,
                updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (
                id_parceiro,
                competencia.replace(day=1),
                round(total, 2),
                CODIGO_SERVICO_NF_COMISSAO,
                venc,
                _discriminacao_nf(itens, competencia),
            ),
        )
        nf_id = int(cur.fetchone()["id"])
        cur.execute("DELETE FROM cadu_nf_comissao_pi WHERE id_nf_comissao = %s", (nf_id,))
        for id_pi, v, _cod, _io in itens:
            cur.execute(
                """
                INSERT INTO cadu_nf_comissao_pi (id_nf_comissao, id_pi, valor_comissao_pi)
                VALUES (%s, %s, %s)
                ON CONFLICT (id_nf_comissao, id_pi) DO UPDATE
                SET valor_comissao_pi = EXCLUDED.valor_comissao_pi
                """,
                (nf_id, id_pi, v),
            )
        conn.commit()
        return nf_id


def _discriminacao_nf(itens, competencia: date) -> str:
    linhas = [
        f"Comissão de representação comercial — competência {competencia.strftime('%m/%Y')}.",
        f"Código de serviço {CODIGO_SERVICO_NF_COMISSAO}.",
    ]
    for id_pi, v, cod, io in itens:
        ref = cod or f"PI #{id_pi}"
        if io:
            ref += f" / IO {io}"
        linhas.append(f"{ref}: R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    return "\n".join(linhas)


def registrar_recebimento_nf(nf_id: int, valor_recebido: float, recebido_em: Optional[date] = None) -> Dict[str, Any]:
    from aicentralv2.db import get_db

    recebido_em = recebido_em or date.today()
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT valor_comissao FROM cadu_nf_comissao_representacao WHERE id = %s",
            (nf_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "Nota não encontrada"}
        esperado = float(row["valor_comissao"] or 0)
        divergencia = round(valor_recebido - esperado, 2)
        status = "conciliada" if abs(divergencia) < 0.02 else "divergente"
        cur.execute(
            """
            UPDATE cadu_nf_comissao_representacao
            SET valor_recebido = %s,
                recebido_em = %s,
                status = %s,
                updated_at = DATE_TRUNC('second', CURRENT_TIMESTAMP)
            WHERE id = %s
            """,
            (valor_recebido, recebido_em, status, nf_id),
        )
        conn.commit()
        return {
            "ok": True,
            "esperado": esperado,
            "recebido": valor_recebido,
            "divergencia": divergencia,
            "status": status,
        }


def metricas_gestao_representacao() -> Dict[str, Any]:
    from aicentralv2.db import get_db

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN c.tipo_de_contrato = 'operacao_propria'
                    THEN COALESCE(p.val_margem_cc, 0) ELSE 0 END), 0) AS receita_margem_propria,
                COALESCE(SUM(CASE WHEN c.tipo_de_contrato = 'representacao_comercial'
                    OR p.modo_operacao = 'representacao'
                    THEN COALESCE(p.comissao_prevista_estimada, 0) ELSE 0 END), 0) AS receita_comissao_rep,
                COALESCE(SUM(CASE WHEN c.tipo_de_contrato = 'representacao_comercial'
                    OR p.modo_operacao = 'representacao'
                    THEN COALESCE(
                        NULLIF(REGEXP_REPLACE(COALESCE(p.vr_bruto_pi, ''), '[^0-9,.-]', '', 'g'), '')::numeric,
                        0)
                    ELSE 0 END), 0) AS volume_intermediado
            FROM cadu_pi p
            LEFT JOIN cadu_cotacoes c ON c.id = p.cotacao_id
            """
        )
        row = cur.fetchone() or {}
    return {
        "receita_margem_propria": float(row.get("receita_margem_propria") or 0),
        "receita_comissao_representacao": float(row.get("receita_comissao_rep") or 0),
        "volume_intermediado_parceiros": float(row.get("volume_intermediado") or 0),
    }
