"""Quem usa a Cadu Análise na v1: só a equipe CentralComm, até o lançamento do Skills.

Com ``CADU_SKILLS_ENABLED=true`` (lançamento) ou ``CADU_REVIEW_PUBLIC=true`` a
revisão abre para qualquer conta logada ou chave válida.
"""
import os

from ..product_flags import skills_enabled

INTERNAL_ONLY_MESSAGE = 'A Cadu Análise está em teste interno com a equipe CentralComm.'


def public() -> bool:
    return skills_enabled() or (os.getenv('CADU_REVIEW_PUBLIC') or '').strip().lower() in {'1', 'true', 'yes', 'on', 'sim'}


def allowed_for_session(session) -> bool:
    return bool(session.get('user_id')) and (public() or bool(session.get('is_centralcomm')))


def allowed_for_user(user_id) -> bool:
    if public():
        return True
    from .repository import is_internal_user
    return bool(user_id) and is_internal_user(user_id)
