import json

from aicentralv2.cadu_workspace.conversations.orchestration import choose_mode, classify


def test_routes_media_plan_to_planning_at_high_complexity():
    route = classify('Monte um plano de mídia para Black Friday com budget de R$ 150 mil.')
    assert route == {'solution': 'planejamento', 'complexity': 'alta'}


def test_routes_project_news_to_research_without_requesting_a_model():
    route = classify('Pesquise notícias e novidades que podem afetar o projeto selecionado.')
    assert route == {'solution': 'pesquisa', 'complexity': 'media'}


def test_explicit_research_starters_select_a_bounded_paid_research_plan():
    from aicentralv2.cadu_workspace.conversations.research import plan_for
    assert plan_for('Faça uma atualização de mercado recente para a marca.')['id'] == 'market'
    assert plan_for('Faça uma pesquisa aprofundada (deep research) do projeto.')['id'] == 'deep'
    assert plan_for('Compare duas ideias para a campanha.') is None


def test_external_research_is_attached_as_evidence_not_project_truth():
    import json
    from aicentralv2.cadu_workspace.conversations.research import attach
    packet = attach('{"contexto_projeto_privado":{"projeto":{"nome":"Reserva"}}}', {
        'label': 'Atualização de mercado', 'content': 'Fato com fonte.',
        'sources': [{'title': 'Fonte oficial', 'url': 'https://example.com', 'excerpt': 'Trecho.'}],
    })
    values = json.loads(packet)
    assert values['contexto_projeto_privado']['projeto']['nome'] == 'Reserva'
    assert values['pesquisa_externa_atual']['orientacao'].startswith('Trate como evidência externa')


def test_market_research_uses_the_perplexity_plan_and_keeps_citations(monkeypatch):
    from aicentralv2.cadu_workspace.conversations import research
    captured = {}
    def provider(messages, **kwargs):
        captured.update(kwargs)
        return {'model': 'perplexity/sonar-pro', 'usage': {'total_tokens': 12, 'cost': 0.001},
                'message': {'content': 'Atualização validada.', 'citations': [{'title': 'Fonte', 'url': 'https://example.com', 'text': 'Evidência.'}]}}
    monkeypatch.setattr(research, 'chat_completion', provider)
    result = research.execute(research.plan_for('Atualização de mercado recente'), 'Atualização de mercado recente', '{}')
    assert captured['model'] == 'perplexity/sonar-pro'
    assert captured['provider'] == 'openrouter'
    assert result['sources'] == [{'title': 'Fonte', 'url': 'https://example.com', 'excerpt': 'Evidência.'}]


def test_uses_matching_installed_skill_and_never_the_client_mode():
    selected, route = choose_mode([
        {'id': 'ideias', 'active': True},
        {'id': 'planejamento', 'prompt': 'Planeje mídia.'},
    ], 'Faça um planejamento com cronograma e KPIs.')
    assert selected['id'] == 'planejamento'
    assert route['solution'] == 'planejamento'


def test_uses_the_account_default_when_a_specialization_is_not_installed():
    selected, route = choose_mode([{'id': 'ideias', 'active': True}], 'Pesquise o mercado de telecom.')
    assert selected['id'] == 'ideias'
    assert route == {'solution': 'pesquisa', 'complexity': 'media'}


def test_payload_keeps_automatic_route_inside_the_server_owned_skill_context():
    import json
    from aicentralv2.cadu_workspace.conversations.service import build_run
    run = build_run('run', 'conversation', {'id': 1, 'name': 'Ana', 'organization_id': 2},
                    {'client_id': 3, 'client_name': 'Cliente'}, {'id': 'planejamento', 'prompt': 'Planeje.'},
                    'planner', '', {'dify_conversation_id': None, 'total_mensagens': 0}, 'Monte um plano.', [], None, '',
                    {'solution': 'planejamento', 'complexity': 'alta'})
    context = json.loads(run['payload']['inputs']['skill_context'])
    assert run['payload']['inputs']['skill_id'] == 'orquestrador'
    assert context['orquestracao'] == {'especializacao': 'planejamento', 'solucao': 'planejamento', 'complexidade': 'alta'}
    assert 'contexto_projeto_privado' in context['fronteiras_de_contexto']['projeto_context']
    assert 'base_cadu_global_publicada' in context['fronteiras_de_contexto']['projeto_context']


def test_payload_preserves_long_dify_skill_instructions():
    from aicentralv2.cadu_workspace.conversations.service import build_run
    prompt = 'x' * 26000
    run = build_run('run', 'conversation', {'id': 1, 'name': 'Ana', 'organization_id': 2},
                    {'client_id': 3, 'client_name': 'Cliente'}, {'id': 'planejamento', 'prompt': prompt},
                    'planner', '', {'dify_conversation_id': None, 'total_mensagens': 0}, 'Monte um plano.', [], None, '')
    context = json.loads(run['payload']['inputs']['skill_context'])
    assert context['diretrizes_especificas'] == prompt
    assert 'não cria documentos' in context['limites_de_artefato']


def test_media_plan_payload_requires_strategy_audiences_mix_and_optimization():
    from aicentralv2.cadu_workspace.conversations.service import build_run
    run = build_run('run', 'conversation', {'id': 1, 'name': 'Ana', 'organization_id': 2},
                    {'client_id': 3, 'client_name': 'Cliente'}, {'id': 'planejamento', 'prompt': 'Use o tom da marca.'},
                    'planner', '', {'dify_conversation_id': None, 'total_mensagens': 0}, 'Monte um plano de mídia.', [], None, '',
                    {'solution': 'planejamento', 'complexity': 'alta'})
    directives = json.loads(run['payload']['inputs']['skill_context'])['diretrizes_especificas']
    for required in ('Campaign Snapshot', 'audiências em camadas', 'percentuais somam 100%', 'regra de otimização',
                     'Não use, cite ou calcule CPM'):
        assert required in directives
    assert directives.endswith('Use o tom da marca.')


def test_audience_catalog_cards_never_expose_commercial_pricing(monkeypatch):
    from aicentralv2.cadu_workspace.conversations import catalog_tools
    monkeypatch.setattr(catalog_tools.catalog, 'detail', lambda *_: {
        'id': 7, 'name': 'Beleza premium', 'description': 'Afinidade com perfumaria.',
        'cpm_custo': 12.5, 'cpm_venda': 25, 'preco': 1000, 'data_groups': {'cpm': 12.5},
    })
    card = catalog_tools.project({'tool': 'audience_detail', 'tool_input': '{"id": 7}'}, 'planner')
    assert card['records'] == [{'id': 7, 'name': 'Beleza premium', 'description': 'Afinidade com perfumaria.'}]


def test_payload_exposes_only_safe_file_metadata_to_the_prompt():
    import json
    from aicentralv2.cadu_workspace.conversations.service import build_run
    run = build_run('run', 'conversation', {'id': 1, 'name': 'Ana', 'organization_id': 2},
                    {'client_id': 3, 'client_name': 'Cliente'}, {'id': 'ideias', 'prompt': 'Ajude.'},
                    'workspace', '', {'dify_conversation_id': None, 'total_mensagens': 0}, 'Leia o arquivo.',
                    [{'provider_id': 'private-file-id', 'name': 'briefing.pdf', 'kind': 'document'}], None, '')
    files = json.loads(run['payload']['inputs']['files_context'])
    assert files['arquivos_anexados'] == [{'nome': 'briefing.pdf', 'tipo': 'document'}]
    assert 'private-file-id' not in run['payload']['inputs']['files_context']


def test_context_packet_keeps_workspace_and_base_cadu_in_distinct_fields(monkeypatch):
    from aicentralv2.cadu_workspace.conversations import service
    from aicentralv2.cadu_skills import knowledge

    monkeypatch.setattr(knowledge, 'context', lambda query: [
        {'fonte': 'Identidade Centralcomm', 'tipo': 'markdown', 'trecho': 'Institucional.'}
    ])
    packet = service.contextual_packet('{"projeto":{"nome":"Lançamento"},"fontes_verificadas":[{"fonte":"Briefing","trecho":"Privado"}]}', 'plano')
    values = __import__('json').loads(packet)
    assert values['contexto_projeto_privado']['projeto']['nome'] == 'Lançamento'
    assert values['base_cadu_global_publicada'][0]['fonte'] == 'Identidade Centralcomm'
    sources = service.project_sources(packet)
    assert {item['title'] for item in sources} == {'Briefing', 'Base Cadu — Identidade Centralcomm'}


def test_context_packet_can_carry_the_curated_media_catalog():
    from aicentralv2.cadu_workspace.conversations import service
    packet = json.loads(service.contextual_packet('', 'plano', {'canais_e_formatos': [{'nome': 'Meta Ads'}]}))
    assert packet['catalogo_midia_cadu']['canais_e_formatos'][0]['nome'] == 'Meta Ads'


def test_context_packet_can_carry_team_workspace_records():
    from aicentralv2.cadu_workspace.conversations import service
    packet = json.loads(service.contextual_packet('', 'projeto', team_workspace={'projetos_da_equipe': [{'nome': 'Lançamento'}]}))
    assert packet['workspace_da_equipe']['projetos_da_equipe'][0]['nome'] == 'Lançamento'


def test_payload_includes_compact_user_memory_when_relevant(monkeypatch):
    import json
    from aicentralv2.cadu_workspace.conversations import memory
    from aicentralv2.cadu_workspace.conversations.service import build_run
    monkeypatch.setattr(memory, 'context_packet', lambda *args: '{"memoria_usuario":{"preferencias":["respostas diretas"]}}')
    project_context = '{"contexto_projeto_privado":{"projeto_ref":"ci:42"}}'
    run = build_run('run', 'conversation', {'id': 1, 'name': 'Ana', 'organization_id': 2},
                    {'client_id': 3, 'client_name': 'Cliente'}, {'id': 'ideias', 'prompt': 'Ajude.'},
                    'workspace', project_context, {'dify_conversation_id': None, 'total_mensagens': 0},
                    'Escreva uma análise.', [], None, '')
    assert json.loads(run['payload']['inputs']['user_memory_context'])['memoria_usuario']['preferencias'] == ['respostas diretas']
    assert set(run['payload']['inputs']) == {'skill_id', 'profile', 'skill_context', 'files_context',
                                              'projeto_context', 'user_memory_context', 'user_profile_context'}


def test_profile_context_is_live_cadastro_data_not_a_memory(monkeypatch):
    from aicentralv2.cadu_workspace.conversations import memory
    from aicentralv2.cadu_workspace.conversations.service import build_run
    monkeypatch.setattr(memory, 'context_packet', lambda *args: '')
    run = build_run('run', 'conversation', {'id': 1, 'name': 'Ana', 'email': 'ana@centralcomm.media',
                     'role_name': 'Diretora de mídia', 'organization_id': 2},
                    {'client_id': 3, 'client_name': 'Centralcomm'}, {'id': 'ideias', 'prompt': 'Ajude.'},
                    'workspace', '', {'dify_conversation_id': None, 'total_mensagens': 0}, 'Escreva um e-mail.', [], None, '')
    profile = json.loads(run['payload']['inputs']['user_profile_context'])
    assert profile == {'nome': 'Ana', 'email': 'ana@centralcomm.media',
                       'empresa_atual': 'Centralcomm', 'cargo': 'Diretora de mídia'}
