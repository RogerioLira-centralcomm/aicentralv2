"""Briefing enviado pelo cliente para a Centralcomm montar o planejamento.

Grava em ``cadu_briefings`` como ``pendente`` e ``enviado_para_centralcomm``,
com o executivo da conta como responsável de vendas. A equipe recebe na tela
de Briefings do CentralX e segue o fluxo atual (iniciar cotação, devolver).
"""

from __future__ import annotations

import uuid
from datetime import date

CANAIS = (
    ("tv_ctv", "TV e CTV"),
    ("programatica", "Digital e programática"),
    ("social", "Redes sociais"),
    ("busca", "Busca"),
    ("audio", "Áudio e rádio"),
    ("ooh", "OOH e DOOH"),
    ("influencia", "Influenciadores"),
    ("sugestao", "Quero sugestão da Centralcomm"),
)
_CANAIS_ROTULO = dict(CANAIS)

STATUS_CLIENTE = {
    "rascunho": ("Rascunho", "gray"),
    "pendente": ("Enviado · em análise", "brand"),
    "aceito": ("Em planejamento", "success"),
    "rejeitado": ("Devolvido para ajustes", "warning"),
}

LIMITES = {"titulo": 160, "objetivo": 2000, "publico": 1000, "verba": 120, "descricao": 6000}


def _db():
    from .. import db
    return db


def _data(valor):
    try:
        return date.fromisoformat((valor or "").strip()) if valor else None
    except ValueError:
        return None


def validar(form) -> tuple[dict, dict]:
    """Normaliza o formulário. Devolve (dados, erros por campo)."""
    dados = {chave: (form.get(chave) or "").strip()[:limite] for chave, limite in LIMITES.items()}
    dados["canais"] = [c for c in form.getlist("canais") if c in _CANAIS_ROTULO]
    dados["inicio"] = _data(form.get("inicio"))
    dados["fim"] = _data(form.get("fim"))
    erros = {}
    if len(dados["titulo"]) < 3:
        erros["titulo"] = "Dê um nome para a campanha ou ação."
    if len(dados["objetivo"]) < 10:
        erros["objetivo"] = "Conte em uma ou duas frases o que você quer alcançar."
    if dados["inicio"] and dados["fim"] and dados["fim"] < dados["inicio"]:
        erros["fim"] = "O fim precisa ser depois do início."
    return dados, erros


def _texto_briefing(d: dict) -> str:
    linhas = [f"Objetivo: {d['objetivo']}"]
    if d["publico"]:
        linhas.append(f"Público e praças: {d['publico']}")
    if d["inicio"] or d["fim"]:
        ini = d["inicio"].strftime("%d/%m/%Y") if d["inicio"] else "a definir"
        fim = d["fim"].strftime("%d/%m/%Y") if d["fim"] else "a definir"
        linhas.append(f"Período desejado: {ini} a {fim}")
    if d["canais"]:
        linhas.append("Canais de interesse: " + ", ".join(_CANAIS_ROTULO[c] for c in d["canais"]))
    if d["verba"]:
        linhas.append(f"Verba prevista: {d['verba']}")
    if d["descricao"]:
        linhas.append("")
        linhas.append(d["descricao"])
    return "\n".join(linhas)


def enviar(usuario: dict, d: dict) -> int:
    """Cria o briefing do cliente da sessão. Devolve o id."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT cli.nome_fantasia, cli.vendas_central_comm, vend.nome_completo AS exec_nome,
                       vend.email AS exec_email
                  FROM tbl_cliente cli
                  LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = cli.vendas_central_comm
                 WHERE cli.id_cliente = %s
                """,
                (usuario["cliente_id"],),
            )
            cli = cursor.fetchone() or {}
            cursor.execute(
                """
                INSERT INTO cadu_briefings (
                    uuid, id_cliente, id_contato_cliente, cliente, titulo, status, progresso,
                    briefing_original, objetivo, budget, prazo, canais, responsavel,
                    responsavel_centralcomm, id_responsavel_vendas, email_destinatario,
                    enviado_para_centralcomm, data_envio, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, 'pendente', 0,
                    %s, %s, %s, %s, %s::jsonb, %s,
                    %s, %s, %s,
                    TRUE, NOW(), NOW(), NOW()
                )
                RETURNING id
                """,
                (
                    str(uuid.uuid4()), usuario["cliente_id"], usuario["user_id"], cli.get("nome_fantasia"),
                    d["titulo"], _texto_briefing(d), d["objetivo"], d["verba"] or None, d["inicio"],
                    _json([_CANAIS_ROTULO[c] for c in d["canais"]]), usuario["nome"],
                    cli.get("exec_nome"), cli.get("vendas_central_comm"), cli.get("exec_email"),
                ),
            )
            novo_id = cursor.fetchone()["id"]
        conn.commit()
        return int(novo_id)
    except Exception:
        conn.rollback()
        raise


def _json(valor):
    import json
    return json.dumps(valor, ensure_ascii=False)


def listar(cliente_id) -> list[dict]:
    """Briefings que o cliente (ou a Centralcomm por ele) enviou, mais recentes primeiro."""
    conn = _db().get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT b.id, b.titulo, b.status, b.objetivo, b.data_envio, b.created_at,
                       autor.nome_completo AS autor_nome
                  FROM cadu_briefings b
                  LEFT JOIN tbl_contato_cliente autor ON autor.id_contato_cliente = b.id_contato_cliente
                 WHERE b.id_cliente = %s AND b.deleted_at IS NULL
                   AND COALESCE(b.enviado_para_centralcomm, FALSE)
                 ORDER BY COALESCE(b.data_envio, b.created_at) DESC
                 LIMIT 50
                """,
                (cliente_id,),
            )
            rows = cursor.fetchall()
    except Exception:
        conn.rollback()
        raise
    saida = []
    for r in rows:
        rotulo, tom = STATUS_CLIENTE.get(r["status"], ("Enviado", "brand"))
        quando = r["data_envio"] or r["created_at"]
        saida.append({
            "id": r["id"], "titulo": r["titulo"] or "Briefing", "objetivo": r["objetivo"] or "",
            "status": rotulo, "tom": tom, "autor": r["autor_nome"] or "",
            "em": quando.strftime("%d/%m/%Y") if quando else "",
        })
    return saida
