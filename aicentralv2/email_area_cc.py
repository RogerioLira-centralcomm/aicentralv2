"""Regras de cópia (CC) por área — Cotação/PI."""

from __future__ import annotations

from typing import Iterable, List, Optional, Union

EMAIL_APOLO = "apolo@centralcomm.media"
EMAIL_LUIZ = "luiz@centralcomm.media"
EMAIL_PEDRO = "pedro@centralcomm.media"
EMAIL_MAX = "max@centralcomm.media"
EMAIL_FINANCEIRO = "financeiro@centralcomm.media"

CC_OPERACAO: List[str] = [
    EMAIL_PEDRO,
    EMAIL_MAX,
    EMAIL_APOLO,
    EMAIL_LUIZ,
]

CC_FINANCEIRO: List[str] = [
    EMAIL_FINANCEIRO,
    EMAIL_PEDRO,
    EMAIL_MAX,
]


def _coletar_enderecos(valor: Optional[Union[str, Iterable[str]]]) -> set[str]:
    if not valor:
        return set()
    if isinstance(valor, str):
        items = [valor]
    else:
        items = list(valor)
    return {_normalizar_email(item) for item in items if _normalizar_email(item)}


def _normalizar_email(email: Optional[str]) -> str:
    return str(email or "").strip().lower()


def cc_comercial(executivo_email: Optional[str] = None) -> List[str]:
    """Executivo de vendas + apolo + luiz (sem deduplicar contra To)."""
    candidatos = [executivo_email, EMAIL_APOLO, EMAIL_LUIZ]
    return normalizar_cc(candidatos)


def normalizar_cc(
    emails: Iterable[str],
    *,
    excluir_to: Optional[Union[str, Iterable[str]]] = None,
    excluir_cc: Optional[Union[str, Iterable[str]]] = None,
) -> List[str]:
    excluir = _coletar_enderecos(excluir_to) | _coletar_enderecos(excluir_cc)
    vistos: set[str] = set()
    resultado: List[str] = []
    for raw in emails:
        email = _normalizar_email(raw)
        if not email or email in excluir or email in vistos:
            continue
        vistos.add(email)
        resultado.append(email)
    return resultado


def extrair_cc_emails_solicitados(payload) -> Optional[List[str]]:
    """None = usar padrão da área; lista (possivelmente vazia) = escolha explícita do usuário."""
    if not isinstance(payload, dict) or "cc_emails" not in payload:
        return None
    raw = payload["cc_emails"]
    if raw is None:
        return None
    if isinstance(raw, str):
        email = _normalizar_email(raw)
        return [email] if email else []
    if isinstance(raw, (list, tuple)):
        return [
            _normalizar_email(item)
            for item in raw
            if _normalizar_email(item)
        ]
    return []


def resolver_cc_envio(
    padrao: Iterable[str],
    cc_emails_solicitados: Optional[List[str]],
    *,
    excluir_to: Optional[Union[str, Iterable[str]]] = None,
    excluir_cc: Optional[Union[str, Iterable[str]]] = None,
) -> List[str]:
    base = list(padrao) if cc_emails_solicitados is None else cc_emails_solicitados
    return normalizar_cc(base, excluir_to=excluir_to, excluir_cc=excluir_cc)
