from aicentralv2.cadu_workspace.conversations.orchestration import choose_mode, classify


def test_routes_media_plan_to_planning_at_high_complexity():
    route = classify('Monte um plano de mídia para Black Friday com budget de R$ 150 mil.')
    assert route == {'solution': 'planejamento', 'complexity': 'alta'}


def test_routes_project_news_to_research_without_requesting_a_model():
    route = classify('Pesquise notícias e novidades que podem afetar o projeto selecionado.')
    assert route == {'solution': 'pesquisa', 'complexity': 'media'}


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
    from aicentralv2.cadu_workspace.conversations.service import build_run
    run = build_run('run', 'conversation', {'id': 1, 'name': 'Ana', 'organization_id': 2},
                    {'client_id': 3, 'client_name': 'Cliente'}, {'id': 'planejamento', 'prompt': 'Planeje.'},
                    'planner', '', {'dify_conversation_id': None, 'total_mensagens': 0}, 'Monte um plano.', [], None, '',
                    {'solution': 'planejamento', 'complexity': 'alta'})
    assert 'solução=planejamento; complexidade=alta' in run['payload']['inputs']['skill_context']
