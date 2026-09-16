"""Explicit customer surface; no automatic exposure of internal routes."""
PRODUCTS = {
    'workspace': {'name': 'Workspace', 'navigation': (
        ('Trabalho', ('inicio', 'conversas', 'workflows', 'projetos', 'marcas')),
        ('Organização', ('equipe', 'integracoes', 'planos', 'consumo', 'faturamento', 'perfil')),
    ), 'modules': {
        'inicio': ('Início', None),
        'conversas': ('Conversas', None), 'workflows': ('Workflows', None),
        'projetos': ('Projetos', None),
        'marcas': ('Marcas', None), 'perfil': ('Perfil', '/configuracoes-perfil'),
        'equipe': ('Equipe', '/configuracoes-equipe'),
        'integracoes': ('Integrações do Workspace', '/integracoes'), 'planos': ('Planos', '/planos'),
        'consumo': ('Créditos e consumo', '/configuracoes-consumo'),
        'faturamento': ('Faturamento', '/checkout-plano'),
    }},
    'planner': {'name': 'SmartPlanner', 'navigation': (
        ('Planejar', ('inicio', 'planos', 'audiencias', 'canais', 'formatos', 'interativos', 'places')),
        ('Entregas', ('docs',)),
    ), 'modules': {
        'inicio': ('Visão geral', None),
        'planos': ('Planos de mídia', None), 'audiencias': ('Audiências', '/audiencias'),
        'canais': ('Canais', '/canais'), 'formatos': ('Formatos', '/formatos'),
        'interativos': ('Interativos', '/interativos'), 'docs': ('Docs', '/smart-docs'),
        'places': ('Places', '/places'),
    }},
    'studio': {'name': 'Studio', 'navigation': (
        ('Produção', ('inicio', 'criacao')),
        ('Ferramentas', ('link-tester', 'creative-analyzer', 'copy-ads')),
    ), 'modules': {
        'inicio': ('Visão geral', None),
        'criacao': ('Criar', None), 'link-tester': ('Link Tester', '/ferramentas-link-tester'),
        'creative-analyzer': ('Creative Analyzer', '/creative-analyzer'),
        'copy-ads': ('Copy Ads', '/ferramentas-copy'),
    }},
    'connect': {'name': 'Connect', 'navigation': (
        ('Operação', ('inicio', 'relatorios')),
    ), 'modules': {'inicio': ('Visão geral', None), 'relatorios': ('Relatórios', None)}},
}
LANDINGS = {
    'workspace': {
        'title': 'O que vamos realizar hoje?',
        'intro': 'Projetos, marcas e conta em um só lugar.',
        'heading': 'Organize o contexto do seu trabalho',
        'body': 'Sua conta já está vinculada ao ambiente correto. Reúna projetos e marcas antes de continuar nas outras soluções.',
        'image': 'cadu-hub.png',
        'links': [('projetos', 'Organizar projetos', 'Encontre os projetos do seu ambiente.'),
                  ('marcas', 'Gerenciar marcas', 'Mantenha as referências da marca no Workspace.')],
    },
    'planner': {
        'title': 'Seu próximo plano começa aqui',
        'intro': 'Objetivos, públicos e entregáveis em linguagem de cliente.',
        'heading': 'Planejar antes de produzir',
        'body': 'Organize objetivos, investimento e referências para transformar estratégia em um plano claro.',
        'image': 'planner.png',
        'links': [('planos', 'Planos de mídia', 'Acompanhe a integração da experiência de planejamento.'),
                  ('audiencias', 'Explorar audiências', 'Consulte referências para o seu planejamento.'),
                  ('places', 'Explorar Places', 'Veja produtos, pontos e alcance dos lugares publicados.')],
    },
    'studio': {
        'title': 'Sua mesa de produção',
        'intro': 'Ferramentas criativas com o contexto da sua marca.',
        'heading': 'Prepare sua produção',
        'body': 'Selecione cliente, marca e projeto. O cadastro de marcas fica no Workspace; as ferramentas criativas ficam aqui.',
        'image': 'studio.png',
        'links': [('copy-ads', 'Preparar Copy Ads', 'Revise textos e limites por formato. A geração automática ainda não está integrada.'),
                  ('link-tester', 'Link Tester', 'Acompanhe a integração da ferramenta de teste de links.'),
                  ('creative-analyzer', 'Creative Analyzer', 'Acompanhe a integração da análise de criativos.')],
    },
    'connect': {
        'title': 'Relatórios no contexto certo',
        'intro': 'Organize a leitura dos resultados por cliente e projeto.',
        'heading': 'Comece pelo cliente',
        'body': 'Selecione o cliente autorizado para consultar seus relatórios. A integração das ações de organização está em validação.',
        'image': 'connect.png',
        'links': [('relatorios', 'Consultar relatórios', 'Veja os registros disponíveis para o cliente selecionado.')],
    },
}
PROFILES = {
    'workspace': 'Organização de marcas e projetos',
    'planner': 'Objetivos, públicos e planejamento de mídia',
    'connect': 'Ferramentas conectadas ao contexto de projetos e marcas',
}
ADMIN_MODULES = {'equipe', 'integracoes', 'planos', 'faturamento'}
