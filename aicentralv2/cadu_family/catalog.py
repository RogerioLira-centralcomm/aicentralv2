"""Explicit customer surface; no automatic exposure of internal routes."""
PRODUCTS = {
    'workspace': {'name': 'Workspace', 'navigation': (
        ('Trabalho', ('inicio', 'conversas', 'clientes', 'projetos', 'marcas')),
        ('Organização', ('equipe', 'integracoes', 'planos', 'consumo', 'faturamento', 'perfil')),
    ), 'modules': {
        'inicio': ('Início', None),
        'conversas': ('Conversas', None),
        'clientes': ('Clientes', None), 'projetos': ('Projetos', None),
        'marcas': ('Marcas', None), 'perfil': ('Perfil', '/configuracoes-perfil'),
        'equipe': ('Equipe', '/configuracoes-equipe'),
        'integracoes': ('Integrações do Workspace', '/integracoes'), 'planos': ('Planos', '/planos'),
        'consumo': ('Créditos e consumo', '/configuracoes-consumo'),
        'faturamento': ('Faturamento', '/checkout-plano'),
    }},
    'planner': {'name': 'SmartPlanner', 'navigation': (
        ('Planejar', ('inicio', 'planos', 'audiencias', 'canais', 'formatos', 'interativos', 'places')),
        ('Entregas', ('docs', 'cotacoes')),
    ), 'modules': {
        'inicio': ('Visão geral', None),
        'planos': ('Planos de mídia', None), 'audiencias': ('Audiências', '/audiencias'),
        'canais': ('Canais', '/canais'), 'formatos': ('Formatos', '/formatos'),
        'interativos': ('Interativos', '/interativos'), 'docs': ('Docs', '/smart-docs'),
        'places': ('Places', '/places'),
        'cotacoes': ('Cotações', '/cotacoes'),
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
        'intro': 'Clientes, marcas, projetos e conta em um só lugar.',
        'heading': 'Defina o contexto do seu trabalho',
        'body': 'Selecione um cliente autorizado e reúna suas marcas e projetos antes de continuar nas outras soluções.',
        'image': 'cadu-hub.png',
        'links': [('clientes', 'Selecionar um cliente', 'Consulte os clientes que sua conta pode acessar.'),
                  ('projetos', 'Organizar projetos', 'Encontre os projetos vinculados ao cliente selecionado.'),
                  ('marcas', 'Gerenciar marcas', 'Mantenha as referências da marca no Workspace.')],
    },
    'planner': {
        'title': 'Seu próximo plano começa aqui',
        'intro': 'Objetivos, públicos e entregáveis em linguagem de cliente.',
        'heading': 'Planejar antes de produzir',
        'body': 'Organize objetivos, investimento e referências. Cotações têm uma área própria e não dependem de um catálogo.',
        'image': 'planner.png',
        'links': [('planos', 'Planos de mídia', 'Acompanhe a integração da experiência de planejamento.'),
                  ('audiencias', 'Explorar audiências', 'Consulte referências para o seu planejamento.'),
                  ('places', 'Explorar Places', 'Veja produtos, pontos e alcance dos lugares publicados.'),
                  ('cotacoes', 'Consultar cotações', 'Acesse as cotações do cliente selecionado.')],
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
    'workspace': 'Organização de clientes, marcas e projetos',
    'planner': 'Objetivos, públicos e planejamento de mídia',
    'connect': 'Análise de relatórios e organização por cliente',
}
ADMIN_MODULES = {'equipe', 'integracoes', 'planos', 'faturamento'}
