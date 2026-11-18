"""Página Equipe do hub (só consulta): quem da empresa está cadastrado na plataforma e tem acesso ao hub, as pessoas das
agências (ou dos clientes, para quem é agência) com PIs em comum, e o time Centralcomm da conta.

O login é o mesmo do Cadu (``tbl_contato_cliente``), mas a liberação do hub é independente: contato e empresa ativos e
sem bloqueio do hub (``area_cliente_bloqueado`` / ``area_cliente_bloqueada``). Incluir ou tirar alguém é com o executivo.
"""

from __future__ import annotations

import logging

from . import dados

logger = logging.getLogger(__name__)

ANOS_PARCEIROS = 2          # empresas parceiras: PIs (não cancelados) que terminaram nos últimos 2 anos ou ainda vão rodar
MAX_PARCEIROS = 12

_PESSOAS_SQL = """
    SELECT c.id_contato_cliente AS id, c.nome_completo AS nome, c.email, c.foto_url, c.pk_id_tbl_cliente AS empresa_id,
           cargo.descricao AS cargo, cli.nome_fantasia AS empresa,
           (cli.status IS TRUE AND NOT COALESCE(cli.area_cliente_bloqueada, FALSE)
            AND NOT COALESCE(c.area_cliente_bloqueado, FALSE)) AS acesso_hub
      FROM tbl_contato_cliente c
      JOIN tbl_cliente cli ON cli.id_cliente = c.pk_id_tbl_cliente
      LEFT JOIN tbl_cargo_contato cargo ON cargo.id_cargo_contato = c.pk_id_tbl_cargo
     WHERE c.pk_id_tbl_cliente = ANY(%(empresas)s) AND c.status IS TRUE
     ORDER BY cli.nome_fantasia, c.nome_completo
"""

_PARCEIROS_SQL = """
    SELECT CASE WHEN pi.id_cliente = %(eu)s THEN pi.id_agencia ELSE pi.id_cliente END AS empresa_id,
           BOOL_OR(pi.id_cliente = %(eu)s) AS sou_cliente, MAX(pi.periodo_fim) AS ultimo
      FROM cadu_pi pi
     WHERE (pi.id_cliente = %(eu)s OR pi.id_agencia = %(eu)s)
       AND pi.id_agencia IS NOT NULL AND pi.id_agencia <> pi.id_cliente
       AND COALESCE(pi.id_sub_status_pi, 0) <> 6
       AND pi.periodo_fim >= CURRENT_DATE - (%(anos)s || ' years')::interval
     GROUP BY 1
     ORDER BY ultimo DESC NULLS LAST
     LIMIT %(limite)s
"""


def _iniciais(nome: str) -> str:
    partes = [p for p in str(nome or "").split() if p[:1].isalpha()]
    return ((partes[0][:1] + (partes[-1][:1] if len(partes) > 1 else "")) if partes else "?").upper()


def _pessoa(r: dict, eu_id) -> dict:
    return {"id": r["id"], "nome": r["nome"] or "Sem nome", "email": r.get("email") or "", "cargo": r.get("cargo") or "",
            "foto_url": r.get("foto_url") or "", "iniciais": _iniciais(r["nome"]), "acesso_hub": bool(r.get("acesso_hub")),
            "voce": r["id"] == eu_id}


def montar(usuario: dict) -> dict:
    """{empresa, pessoas, parceiros: [{nome, tipo, pessoas}], executivo}. Falha do banco vira lista vazia (a página avisa)."""
    eu = usuario["cliente_id"]
    try:
        parceiros = dados._fetch(_PARCEIROS_SQL, {"eu": eu, "anos": str(ANOS_PARCEIROS), "limite": MAX_PARCEIROS})
        ids = [eu] + [p["empresa_id"] for p in parceiros]
        linhas = dados._fetch(_PESSOAS_SQL, {"empresas": ids})
    except Exception:
        logger.warning("Equipe do hub indisponível.", exc_info=True)
        return {"empresa": usuario.get("cliente_nome"), "pessoas": [], "parceiros": [], "erro": True}
    por_empresa: dict = {}
    for r in linhas:
        por_empresa.setdefault(r["empresa_id"], {"nome": r["empresa"], "pessoas": []})["pessoas"].append(_pessoa(r, usuario.get("user_id")))
    lista_parceiros = []
    for p in parceiros:
        bloco = por_empresa.get(p["empresa_id"])
        if bloco and bloco["pessoas"]:
            # parceiros: sem e-mail (a página é da empresa; contato com a agência segue pelos canais de sempre)
            pessoas = [{**x, "email": ""} for x in bloco["pessoas"]]
            lista_parceiros.append({"nome": bloco["nome"], "tipo": "Agência" if p["sou_cliente"] else "Cliente", "pessoas": pessoas})
    proprias = (por_empresa.get(eu) or {}).get("pessoas", [])
    proprias.sort(key=lambda x: (not x["voce"], not x["acesso_hub"], x["nome"].lower()))
    return {"empresa": usuario.get("cliente_nome"), "pessoas": proprias, "parceiros": lista_parceiros, "erro": False}
