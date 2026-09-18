import json


def test_provider_diagnostics_are_never_customer_content():
    from aicentralv2.cadu_workspace.conversations.service import (
        is_operational_failure_leak,
        safe_tool_fallback,
    )

    leaked = ('Síntese: a consulta à base de audiências falhou por autenticação. '
              'Evidência: 401 / API Key inválida.')
    assert is_operational_failure_leak(leaked)
    replacement = safe_tool_fallback({'project_ref': 'ci:42'})
    assert 'API' not in replacement
    assert '401' not in replacement
    assert 'projeto selecionado' in replacement


def test_stopped_markdown_fragment_is_not_a_message():
    from aicentralv2.cadu_workspace.conversations.service import has_displayable_answer

    assert not has_displayable_answer('**')
    assert not has_displayable_answer('  ---  ')
    assert has_displayable_answer('Uma recomendação que pode ser revisada.')


def test_unavailable_research_keeps_context_without_exposing_provider_details():
    from aicentralv2.cadu_workspace.conversations.research import attach_unavailable

    packet = json.loads(attach_unavailable(
        '{"contexto_projeto_privado":{"projeto":{"nome":"Reserva"}}}',
        {'label': 'Atualização de mercado'},
    ))
    research = packet['pesquisa_externa_atual']
    assert packet['contexto_projeto_privado']['projeto']['nome'] == 'Reserva'
    assert research['status'] == 'nao_consultada_nesta_resposta'
    assert 'API' not in json.dumps(research)
    assert '401' not in json.dumps(research)
