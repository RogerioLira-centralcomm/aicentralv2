"""Trilha comercial de representação (Logan, Serasa, etc.)."""

from .domain import eh_representacao_comercial, representacao_habilitada
from .parceiros import (
    FLUXO_PDF_REPASSA,
    FLUXO_PLANILHA,
    TRILHA_GENERICO,
    TRILHA_LOGAN,
    TRILHA_SERASA,
    metadados_trilha,
    resolver_trilha_parceiro,
    sincronizar_trilha_cotacao,
)

__all__ = [
    "eh_representacao_comercial",
    "representacao_habilitada",
    "resolver_trilha_parceiro",
    "metadados_trilha",
    "sincronizar_trilha_cotacao",
    "TRILHA_LOGAN",
    "TRILHA_SERASA",
    "TRILHA_GENERICO",
    "FLUXO_PLANILHA",
    "FLUXO_PDF_REPASSA",
]
