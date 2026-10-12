"""Funções publicadas de cada solução, agrupadas como no menu do cliente.

Fonte: ``cadu_family/catalog.py`` (navegação do cliente) e os módulos já
lançados. Fora desta lista ficam funções não lançadas ou em integração
(Studio mesa infinita, Portais e veículos, Site & Jornada, Sites e funis,
Creative Analyzer). Não citar preço, custo ou investimento aqui: vitrines
são orçadas (ver cotação), e os valores vêm do catálogo de planos.
"""

SOLUTION_FUNCTIONS = {
    "workspace": [
        {"title": "Trabalho", "items": [
            {"name": "Conversas", "description": "Converse com agentes de IA com o contexto do projeto e da marca já carregado."},
            {"name": "Projetos", "description": "Organize campanhas com briefing, arquivos, links e decisões em um só lugar."},
            {"name": "Marcas", "description": "Mantenha referências de marca, como identidade, tom e logos, disponíveis para todos os projetos."},
        ]},
        {"title": "Organização", "items": [
            {"name": "Equipe", "description": "Convide pessoas e defina quem administra a conta. Usuários são ilimitados em todos os planos."},
            {"name": "Integrações", "description": "Conecte as fontes autorizadas, como reuniões, arquivos e contas, ao Workspace."},
            {"name": "Planos", "description": "Veja o plano atual e solicite a mudança de plano."},
            {"name": "Créditos e consumo", "description": "Acompanhe tokens usados, saldo disponível e pacotes extras."},
            {"name": "Faturamento", "description": "Histórico de faturas e dados de cobrança da conta."},
            {"name": "Perfil", "description": "Dados pessoais e preferências da sua conta."},
        ]},
    ],
    "planner": [
        {"title": "Planejar", "items": [
            {"name": "Planos de mídia", "description": "Monte o plano em etapas: briefing, objetivo e KPIs, praças, audiências, canais, formatos e verba."},
            {"name": "Radar de Oportunidades", "description": "Pesquise oportunidades de mídia a partir do objetivo e do público, com créditos por etapa."},
            {"name": "Meus radares", "description": "Reúna as pesquisas do Radar salvas por você para revisar depois."},
            {"name": "Audiências", "description": "Consulte o catálogo de audiências e compare públicos para o seu plano."},
            {"name": "Canais", "description": "Compare canais, o papel de cada um no plano e os formatos aceitos. Solicite cotação quando estiver pronto."},
            {"name": "Formatos", "description": "Escolha formatos e especificações técnicas de cada peça, por canal."},
            {"name": "Interativos", "description": "Formatos interativos e suas especificações para campanhas que pedem interação."},
            {"name": "Locais", "description": "Explore produtos, pontos e alcance dos locais publicados."},
        ]},
    ],
    "studio": [
        {"title": "Produção", "items": [
            {"name": "Criar", "description": "Geração de imagens, edições avançadas, variações por formato e criação de vídeos com a marca do projeto."},
        ]},
    ],
    "reports": [
        {"title": "Operação", "items": [
            {"name": "Relatórios", "description": "Consulte resultados por cliente autorizado e por projeto."},
            {"name": "Google Ads", "description": "Conecte contas do Google Ads e acompanhe gasto e campanhas junto com o projeto."},
            {"name": "Página 360", "description": "Calor e conversões por página monitorada, ligados ao gasto de mídia."},
        ]},
    ],
    "skills": [
        {"title": "Métodos", "items": [
            {"name": "Skills", "description": "Escolha métodos prontos e aplique-os ao contexto do projeto. Não compra nem ativa mídia."},
            {"name": "Inteligência de audiências", "description": "Pesquisa e recomendação de audiências do catálogo por mercado, funil, geografia e canal."},
            {"name": "Inteligência de canais", "description": "Compara e recomenda canais do inventário com dados comerciais e formatos disponíveis."},
            {"name": "Inteligência de formatos", "description": "Seleciona formatos compatíveis com canal, dispositivo e objetivo."},
            {"name": "Planejamento de mídia", "description": "Cria e revisa planos com tese, mix, verba, período, KPIs e riscos."},
        ]},
    ],
}
