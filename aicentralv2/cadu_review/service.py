"""Porta única da revisão de plano: a página, o MCP e a API key passam por aqui."""
from __future__ import annotations

from . import media_plan, repository
from .media_plan_parser import CONTEXT_ALIASES, PlanParseError

CONTEXT_FIELDS = tuple(CONTEXT_ALIASES)


def context_from(values) -> dict:
    values = values or {}
    return {key: str(values.get(key) or '').strip()[:600] for key in CONTEXT_FIELDS if str(values.get(key) or '').strip()}


def review_media_plan(raw: bytes, filename: str, *, context=None, channel: str, client_id: int,
                      user_id=None, api_key_id=None, call=None) -> dict:
    """Revisa e registra. PlanParseError sobe com mensagem pronta para a pessoa."""
    try:
        result = media_plan.review_file(raw, filename, context=context_from(context), call=call)
    except PlanParseError as exc:
        repository.record_run(kind='media_plan', channel=channel, client_id=client_id, user_id=user_id,
                              api_key_id=api_key_id, raw=raw, status='failed', error_code='parse',
                              file_type=str(filename or '').rsplit('.', 1)[-1].lower()[:8])
        raise exc
    repository.record_run(kind='media_plan', channel=channel, client_id=client_id, user_id=user_id,
                          api_key_id=api_key_id, raw=raw, result=result)
    result['markdown'] = media_plan.to_markdown(result, filename)
    result['file']['name'] = str(filename or '')[:200]
    return result
