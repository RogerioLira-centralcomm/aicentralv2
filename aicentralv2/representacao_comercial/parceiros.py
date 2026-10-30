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
    trilha = resolver_trilha_parceiro(
        cotacao.get("id_parceiro"),
        cotacao.get("parceiro_nome"),
    )
    meta = metadados_trilha(trilha)
    return {
        "trilha_representacao": meta["trilha"],
        "fluxo_proposta_representacao": meta["fluxo_proposta"],
    }
