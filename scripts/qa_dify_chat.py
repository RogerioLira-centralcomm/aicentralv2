"""Small, repeatable Dify chat QA suite.

Run on the application host after configuring CADU_DIFY_API_KEY (or the
encrypted Dify credential):
    python scripts/qa_dify_chat.py

The script never prints credentials or full provider events. It reports the
first-token latency, total duration, terminal state and answer size for short,
medium and high-complexity Cadu requests.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests


# Executing ``python scripts/qa_dify_chat.py`` makes ``scripts/`` the first
# import root. Add the repository root explicitly so the QA uses the same
# application and credential resolver as Gunicorn, regardless of the caller's
# current directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.agent_v2.guardrails import normalize_response
from aicentralv2.cadu_workspace.agent_v2.prompt_assembler import build_payload
from aicentralv2.cadu_workspace.agent_v2.response_policy import policy_for, requested_answer_chars
from aicentralv2.cadu_workspace.agent_v2.router import route_request


CASES = (
    ('curta', 'O que é CPM?', 'baixa'),
    ('media', 'Quais audiências recomendadas para uma campanha de seguros?', 'media'),
    ('alta', 'Monte um plano de mídia de R$ 150 mil para Black Friday, com fases, canais e KPIs.', 'alta'),
    ('mercado', 'Quais notícias e tendências podem impactar uma empresa de telecom?', 'media'),
    ('texto_longo', 'Crie um resumo sobre o Rock in Rio com cerca de 600 palavras, organizado do começo até 2026.', 'alta'),
)


def stream_case(base_url, api_key, label, query, expected_complexity):
    context = RequestContext(
        organization_id=1, client_id=1, user_id=1, conversation_id=None,
        surface='conversations', capabilities=('workspace', 'planner', 'reports', 'artifacts'),
    )
    route = route_request(query)
    policy = policy_for(route)
    requested_chars = requested_answer_chars(query)
    if requested_chars:
        policy['max_answer_chars'] = max(policy['max_answer_chars'], requested_chars)
    payload = build_payload(
        message=query, request=context, route=route,
        resolved={'qa': True, 'expected_complexity': expected_complexity},
        policy=policy, user_label='qa-cadu-v2', execution_mode='analysis',
        max_context_chars=16000,
    )
    started, first_token, answer_chunks, terminal = time.monotonic(), None, [], None
    with requests.post(base_url.rstrip('/') + '/chat-messages', headers={'Authorization': 'Bearer ' + api_key},
                       json=payload, stream=True, timeout=(10, 120)) as response:
        response.raise_for_status()
        for raw in response.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith('data:'):
                continue
            event = json.loads(raw[5:].lstrip())
            kind = event.get('event')
            if kind in ('message', 'agent_message') and isinstance(event.get('answer'), str):
                first_token = first_token or time.monotonic()
                answer_chunks.append(event['answer'])
            if kind == 'message_end':
                terminal = 'completed'
                break
            if kind == 'error':
                terminal = 'failed'
                break
    finished = time.monotonic()
    answer = ''.join(answer_chunks)
    contract = 'invalid'
    error = ''
    try:
        normalized = normalize_response(answer, policy)
        answer_chars = len(normalized.answer)
        contract = 'valid'
        if label == 'texto_longo' and answer_chars < 1800:
            contract = 'too_short'
    except Exception as exc:
        answer_chars = len(answer)
        error = f'{type(exc).__name__}: {exc}'
    status = terminal or 'incomplete'
    if contract != 'valid':
        status = 'failed_contract'
    return {'case': label, 'expected_complexity': expected_complexity, 'status': status,
            'contract': contract, 'error': error,
            'first_token_ms': round(((first_token or finished) - started) * 1000),
            'total_ms': round((finished - started) * 1000), 'answer_chars': answer_chars}


def main():
    key = os.getenv('CADU_DIFY_API_KEY', '').strip()
    base_url = os.getenv('CADU_DIFY_BASE_URL', 'https://api.dify.ai/v1').strip()
    # Production normally stores this credential in the CentralX vault. Keep
    # env vars useful for isolated CI, but exercise the same resolution path
    # used by the chat when this script runs on the application host.
    if not key:
        try:
            from aicentralv2 import create_app
            from aicentralv2.services.integration_credentials import resolve_dify_configuration
            app = create_app()
            with app.app_context():
                resolved_url, resolved_key = resolve_dify_configuration()
            key = str(resolved_key or '').strip()
            base_url = str(resolved_url or base_url).strip()
        except Exception as exc:
            raise SystemExit(
                'Não foi possível carregar a configuração Dify pela aplicação: '
                f'{type(exc).__name__}: {exc}'
            ) from exc
    if not key:
        raise SystemExit('A credencial Dify não está configurada no cofre CentralX nem em CADU_DIFY_API_KEY.')
    results = [stream_case(base_url, key, *case) for case in CASES]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
