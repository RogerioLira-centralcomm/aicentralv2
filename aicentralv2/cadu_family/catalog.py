"""Explicit customer surface; no automatic exposure of internal routes."""
PRODUCTS = {
    'workspace': {'name': 'Workspace', 'modules': {
        'clientes': ('Clientes', None), 'projetos': ('Projetos', None),
        'marcas': ('Marcas', None), 'perfil': ('Perfil', '/configuracoes-perfil'),
        'equipe': ('Equipe', '/configuracoes-equipe'),
        'integracoes': ('Integrações do Workspace', '/integracoes'), 'planos': ('Planos', '/planos'),
        'consumo': ('Créditos e consumo', '/configuracoes-consumo'),
        'faturamento': ('Faturamento', '/checkout-plano'),
    }},
    'planner': {'name': 'Planner', 'modules': {
        'planos': ('Planos de mídia', None), 'audiencias': ('Audiências', '/audiencias'),
        'canais': ('Canais', '/canais'), 'formatos': ('Formatos', '/formatos'),
        'interativos': ('Interativos', '/interativos'), 'docs': ('Docs', '/smart-docs'),
        'cotacoes': ('Cotações', '/cotacoes'),
    }},
    'studio': {'name': 'Studio', 'modules': {
        'criacao': ('Criação', None), 'link-tester': ('Link Tester', '/ferramentas-link-tester'),
        'creative-analyzer': ('Creative Analyzer', '/creative-analyzer'),
        'copy-ads': ('Copy Ads', '/ferramentas-copy'),
    }},
    'connect': {'name': 'Connect', 'modules': {'relatorios': ('Relatórios', None)}},
}
PROFILES = {
    'workspace': 'Organização de clientes, marcas e projetos',
    'planner': 'Objetivos, públicos e planejamento de mídia',
    'connect': 'Análise de relatórios e organização por cliente',
}
ADMIN_MODULES = {'equipe', 'integracoes', 'planos', 'faturamento'}
