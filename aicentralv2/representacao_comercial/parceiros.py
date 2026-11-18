"""Resolução Logan / Serasa a partir de id_parceiro (tbl_cliente)."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

TRILHA_LOGAN = "logan"
TRILHA_SERASA = "serasa"
TRILHA_GENERICO = "generico"

FLUXO_PLANILHA = "planilha"
FLUXO_PDF_REPASSA = "pdf_repassa"

VENCIMENTO_DIA_20 = "dia_20"
VENCIMENTO_D_PLUS_2 = "d_plus_2"


def _parse_id_list(env_key: str) -> set[int]:
    raw = (os.getenv(env_key) or "").strip()
    if not raw:
        return set()
    out: set[int] = set()
    for part in re.split(r"[,;\s]+", raw):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            continue
    return out


LOGAN_PARCEIRO_IDS = _parse_id_list("REPRESENTACAO_LOGAN_PARCEIRO_IDS")
SERASA_PARCEIRO_IDS = _parse_id_list("REPRESENTACAO_SERASA_PARCEIRO_IDS")


def _normalizar_nome(nome: Optional[str]) -> str:
    if not nome:
        return ""
    return re.sub(r"\s+", " ", str(nome).strip().lower())


def resolver_trilha_parceiro(
    id_parceiro: Optional[int],
    nome_parceiro: Optional[str] = None,
) -> str:
    if id_parceiro is not None:
        pid = int(id_parceiro)
        if pid in LOGAN_PARCEIRO_IDS:
            return TRILHA_LOGAN
        if pid in SERASA_PARCEIRO_IDS:
            return TRILHA_SERASA
    nome = _normalizar_nome(nome_parceiro)
    if "logan" in nome:
        return TRILHA_LOGAN
    if "serasa" in nome or "experian" in nome:
        return TRILHA_SERASA
    return TRILHA_GENERICO


def metadados_trilha(trilha: str) -> Dict[str, Any]:
    trilha = (trilha or TRILHA_GENERICO).strip().lower()
    if trilha == TRILHA_LOGAN:
        return {
            "trilha": TRILHA_LOGAN,
            "rotulo": "Logan",
            "fluxo_proposta": FLUXO_PLANILHA,
            "vencimento_nf": VENCIMENTO_D_PLUS_2,
            "anexo_esperado": "planilha_parceiro",
        }
    if trilha == TRILHA_SERASA:
        return {
            "trilha": TRILHA_SERASA,
            "rotulo": "Serasa",
            "fluxo_proposta": FLUXO_PDF_REPASSA,
            "vencimento_nf": VENCIMENTO_DIA_20,
            "anexo_esperado": "proposta_pdf_parceiro",
        }
    return {
        "trilha": TRILHA_GENERICO,
        "rotulo": "Representação",
        "fluxo_proposta": FLUXO_PLANILHA,
        "vencimento_nf": VENCIMENTO_DIA_20,
        "anexo_esperado": "planilha_parceiro",
    }


def sincronizar_trilha_cotacao(cotacao: Dict[str, Any]) -> Dict[str, str]:
    nome_trilha = cotacao.get("plataforma_campanha") or cotacao.get("parceiro_nome")
    trilha = resolver_trilha_parceiro(
        cotacao.get("id_parceiro"),
        nome_trilha,
    )
    meta = metadados_trilha(trilha)
    return {
        "trilha_representacao": meta["trilha"],
        "fluxo_proposta_representacao": meta["fluxo_proposta"],
    }


def ids_fornecedores_dados() -> set[int]:
    """IDs de parceiro aceitos como fornecedor em cotações tipo Dados."""
    return set(LOGAN_PARCEIRO_IDS) | set(SERASA_PARCEIRO_IDS)


def parceiro_autorizado_fornecedor_dados(id_parceiro: Optional[int]) -> bool:
    if id_parceiro is None:
        return False
    return int(id_parceiro) in ids_fornecedores_dados()


def listar_opcoes_fornecedor_dados() -> list[Dict[str, Any]]:
    """Opções para select de fornecedor (Serasa / Logan) no workspace e na criação."""
    out: list[Dict[str, Any]] = []
    grupos = (
        (TRILHA_SERASA, SERASA_PARCEIRO_IDS, "Serasa"),
        (TRILHA_LOGAN, LOGAN_PARCEIRO_IDS, "Logan"),
    )
    for trilha, ids, rotulo in grupos:
        meta = metadados_trilha(trilha)
        fluxo = (
            "Planilha do parceiro"
            if meta.get("fluxo_proposta") == FLUXO_PLANILHA
            else "PDF do parceiro"
        )
        venc = meta.get("vencimento_nf") or ""
        vencimento = "D+2" if venc == VENCIMENTO_D_PLUS_2 else "dia 20"
        for pid in sorted(ids):
            out.append(
                {
                    "id_parceiro": pid,
                    "trilha": trilha,
                    "rotulo": rotulo,
                    "hint": f"{fluxo} · NF {vencimento}",
                }
            )
    return out


def validar_fornecedor_cotacao_dados(
    tipo_comercial: str,
    id_parceiro: Optional[int],
) -> None:
    """Legado — usar validar_plataforma_cotacao_dados."""

    from aicentralv2.cotacao_tipos import normalizar_tipo_comercial

    if normalizar_tipo_comercial(tipo_comercial, estrito=False) != "dados":
        return
    if not parceiro_autorizado_fornecedor_dados(id_parceiro):
        raise ValueError(
            "Informe o fornecedor de dados (Serasa ou Logan) na operação da cotação."
        )


def validar_plataforma_dados_valor(plataforma_campanha: Optional[str]) -> str:
    """Valida e retorna a descrição canônica da plataforma (catálogo PI, categoria Dados)."""
    from aicentralv2 import db

    plat = str(plataforma_campanha or "").strip()
    if not plat:
        raise ValueError(
            "Selecione a plataforma de dados cadastrada em Parâmetros (categoria Dados)."
        )
    ativas = db.listar_plataformas_dados_ativas() or []
    por_nome = {
        str(p.get("descricao") or "").strip().casefold(): str(p.get("descricao") or "").strip()
        for p in ativas
    }
    canon = por_nome.get(plat.casefold())
    if not canon:
        raise ValueError(
            "Plataforma de dados inválida ou inativa. Use o cadastro de plataformas (categoria Dados)."
        )
    return canon


def validar_plataforma_cotacao_dados(
    tipo_comercial: str,
    plataforma_campanha: Optional[str],
    *,
    exigir: bool = True,
) -> None:
    from aicentralv2.cotacao_tipos import normalizar_tipo_comercial

    if normalizar_tipo_comercial(tipo_comercial, estrito=False) != "dados":
        return
    if not exigir and not str(plataforma_campanha or "").strip():
        return
    validar_plataforma_dados_valor(plataforma_campanha)
