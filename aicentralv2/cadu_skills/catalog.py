"""Catálogo público inicial e metadados das skills próprias."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent

CADU_GOLD = {
    "slug": "cadu-gold",
    "name": "Cadu Gold — estratégia à entrega",
    "category": "Método completo",
    "summary": "A skill completa para transformar um briefing em decisão, plano, públicos, canais e especificação de produção.",
    "description": "Um especialista-orquestrador para quem precisa fechar a campanha inteira com o mesmo contexto, as mesmas premissas e um rastro claro de validações.",
    "credit_cost": 3,
    "model": "openai/gpt-4o-mini",
    "featured": True,
    "rank": 0,
    "status": "published",
    "is_testable": False,
    "image_url": "/static/images/cadu/skills/catalog-hero-media-intelligence.png",
    "instructions": "Você é o Cadu Gold. Congele briefing, objetivo, público, praça, período, verba, ativos e restrições. Produza uma tese, mix, canais, audiências, formatos, KPIs, riscos e validações como uma decisão única. Diferencie fato, evidência, premissa e pendência. Não invente preço, alcance, disponibilidade ou performance.",
    "path": ROOT / "gold" / "SKILL.md",
    "installable": True,
    "official": True,
    "tagline": "Uma campanha inteira, um contexto só, nenhuma decisão desconectada.",
    "capabilities": ("Tese e plano de mídia", "Canais, audiências e formatos compatíveis", "Especificação de produção", "Auditoria de riscos e pendências"),
    "use_steps": ("Envie o briefing e as restrições confirmadas.", "Peça a decisão completa ou uma auditoria do plano atual.", "Valide apenas as pendências comerciais indicadas."),
    "outputs": ("Campaign Snapshot", "Estratégia e mix", "Matriz de decisões", "Checklist de validação"),
    "prompts": ("Organize esta campanha do briefing à especificação de produção.",),
}

CADU_MEDIA_PLANNING = {
    "slug": "cadu-media-planning",
    "name": "Planejamento de mídia Cadu",
    "category": "Planejamento de mídia",
    "summary": "Transforma briefing, contexto de marca e os canais da CentralX em um plano defendível.",
    "description": "Estratégia, mix, verba, formatos, voo, KPIs e critérios de otimização conectados à realidade comercial da agência.",
    "credit_cost": 2,
    "model": "openai/gpt-4o-mini",
    "featured": True,
    "rank": 1,
    "status": "published",
    "is_testable": True,
    "image_url": "/static/images/cadu/products/skills.png",
    "instructions": """Você é o especialista de planejamento de mídia do Cadu. Congele objetivo, público, praça, período, verba, conversão, restrições e fontes num Campaign Snapshot. Crie uma única tese específica antes do mix. Selecione somente canais, audiências e formatos dos catálogos Cadu disponíveis; diferencie fato, evidência, premissa e pendência. Cada canal precisa de papel, audiência, um formato principal, KPI, risco, dependência e critério de otimização. Feche o mix em 100% e na verba confirmada. Não invente alcance, preço, CPM, disponibilidade ou resultado. Termine auditando conflitos entre snapshot, tese, mix, criação e mensuração.""",
    "path": ROOT / "media-planning" / "SKILL.md",
    "installable": True,
    "official": True,
    "tagline": "Do briefing ao plano auditável, sem inventar mídia.",
    "capabilities": (
        "Campaign Snapshot e tese única", "Mix, verba e voo consistentes",
        "Canais, audiências e formatos CentralX", "Auditoria final de conflitos",
    ),
    "use_steps": (
        "Informe objetivo, público, praça, período, verba e restrições.",
        "Peça uma tese e um mix inicial ou envie um plano para revisão.",
        "Valide pendências comerciais antes de aprovar ou ativar mídia.",
    ),
    "outputs": ("Resumo executivo", "Tabela de mix", "Voo", "KPIs", "Riscos e próximos passos"),
    "prompts": (
        "Monte um mix inicial para uma campanha regional de consideração.",
        "Revise este plano e identifique inconsistências de verba e KPI.",
        "Compare os melhores canais disponíveis para alcançar decisores B2B.",
    ),
}

CADU_OFFICIAL_SPECS = (
    {
        "slug": "cadu-channel-intelligence",
        "name": "Inteligência de canais Cadu",
        "category": "Inteligência de mídia",
        "summary": "Compara canais da CentralX com audiências e formatos realmente compatíveis.",
        "description": "Shortlist, papel de canal, adequação, riscos e validações comerciais com dados do catálogo Cadu.",
        "credit_cost": 1,
        "model": "openai/gpt-4o-mini",
        "featured": True,
        "rank": 101,
        "status": "published",
        "is_testable": True,
        "image_url": "/static/images/cadu/products/skills.png",
        "instructions": "Você é o especialista de canais do Cadu. Congele objetivo, público, praça, período, verba e ação esperada. Compare somente canais presentes no catálogo Cadu, validando para cada um audiência relacionada, formato compatível, dispositivo, mínimo comercial, qualidade e data do snapshot. Entregue Canal | Papel | Audiência | Formato | Evidência | Limitação | Validação. Diferencie dado, inferência e pendência; não invente preço, alcance, disponibilidade ou resultado.",
        "path": ROOT / "channel-intelligence" / "SKILL.md",
        "installable": True,
        "official": True,
        "tagline": "Escolha canais pelo papel que cumprem — e pela mídia que realmente suportam.",
        "capabilities": (
            "Shortlist por objetivo e público", "Relação canal–audiência",
            "Compatibilidade de formatos", "Riscos e validações comerciais",
        ),
        "use_steps": (
            "Descreva objetivo, público, praça, período e ação esperada.",
            "Peça uma comparação ou envie sua shortlist atual.",
            "Confirme as validações indicadas antes de fechar o mix.",
        ),
        "outputs": ("Matriz comparativa", "Recomendação", "Limitações", "Validações"),
        "prompts": (
            "Compare os canais Cadu adequados para este objetivo e público.",
            "Revise esta shortlist e encontre incompatibilidades de audiência ou formato.",
        ),
    },
    {
        "slug": "cadu-audience-intelligence",
        "name": "Inteligência de audiências Cadu",
        "category": "Dados e audiência",
        "summary": "Qualifica audiências por mercado, sinais, funil, canal, origem e qualidade.",
        "description": "Segmentação defendível com taxonomia, disponibilidade, restrições e evidências da base Cadu.",
        "credit_cost": 1,
        "model": "openai/gpt-4o-mini",
        "featured": True,
        "rank": 102,
        "status": "published",
        "is_testable": True,
        "image_url": "/static/images/cadu/products/skills.png",
        "instructions": "Você é o estrategista de audiências do Cadu. Traduza o briefing em mercado, B2B/B2C, sinais, funil, geografia e canais. Use somente audiências do catálogo; exclua itens inativos, inválidos ou em quarentena e sinalize dados estimados, vencidos ou não verificados. Use lacunas de verificação para orientar curadoria, sem promover status por conta própria. Não use preço de custo ou preço de venda. Não confunda conceito, afinidade, perfil, tática e formato. Entregue Audiência | Papel | Sinais | Funil | Mercado | Canal | Qualidade | Evidência | Restrição. Não invente tamanho, CPM, match rate ou performance.",
        "path": ROOT / "audience-intelligence" / "SKILL.md",
        "installable": True,
        "official": True,
        "tagline": "Transforme públicos disponíveis em segmentação defensável.",
        "capabilities": (
            "Busca por mercado e funil", "Qualidade e origem dos dados",
            "Canais de ativação", "Restrições e lacunas de verificação",
        ),
        "use_steps": (
            "Informe mercado, objetivo, geografia e canais possíveis.",
            "Peça públicos prioritários ou a auditoria de uma seleção existente.",
            "Use as lacunas de verificação para concluir a curadoria humana.",
        ),
        "outputs": ("Matriz de audiências", "Prioridades", "Exclusões", "Backlog de verificação"),
        "prompts": (
            "Encontre as audiências mais defensáveis para este briefing.",
            "Audite esta seleção de públicos por qualidade, canal e restrições.",
        ),
    },
    {
        "slug": "cadu-format-intelligence",
        "name": "Inteligência de formatos Cadu",
        "category": "Formatos e criação",
        "summary": "Escolhe formatos viáveis por canal, dispositivo, objetivo e capacidade criativa.",
        "description": "Formato principal, especificação, adaptação e checklist técnico conectados ao inventário Cadu.",
        "credit_cost": 1,
        "model": "openai/gpt-4o-mini",
        "featured": True,
        "rank": 103,
        "status": "published",
        "is_testable": True,
        "image_url": "/static/images/cadu/products/skills.png",
        "instructions": "Você é o especialista de formatos do Cadu. Confirme canal, objetivo, mensagem, dispositivo, placement, duração e ativos. Escolha um formato principal existente e compatível no catálogo, distinguindo formato, peça, placement, compra e add-on. Entregue Canal | Formato | Chave | Dimensão/duração | Dispositivo | Uso | Arquivos | Restrições | Validação. Não invente inventário e não afirme que vídeo, áudio ou animação foram produzidos.",
        "path": ROOT / "format-intelligence" / "SKILL.md",
        "installable": True,
        "official": True,
        "tagline": "Converta estratégia em uma entrega criativa tecnicamente viável.",
        "capabilities": (
            "Formato principal por canal", "Dimensão, dispositivo e placement",
            "Arquivos e elementos obrigatórios", "Checklist de produção e aceite",
        ),
        "use_steps": (
            "Informe canal, objetivo, mensagem, dispositivo e ativos disponíveis.",
            "Peça um formato principal ou audite uma especificação existente.",
            "Confirme requisitos comerciais ausentes antes da produção.",
        ),
        "outputs": ("Especificação técnica", "Formato principal", "Restrições", "Checklist de aceite"),
        "prompts": (
            "Escolha o formato principal para cada canal desta campanha.",
            "Transforme esta recomendação em checklist técnico de produção.",
        ),
    },
)

CADU_OFFICIAL_SKILLS = (CADU_GOLD, CADU_MEDIA_PLANNING, *CADU_OFFICIAL_SPECS)

# Avatares 3D próprios da família CentralComm. Cada skill tem uma presença
# reconhecível no catálogo, sem reaproveitar a arte genérica do produto.
_OFFICIAL_AVATARS = {
    "cadu-gold": "/static/images/cadu/skills/avatars/cadu-gold-3d.png",
    "cadu-media-planning": "/static/images/cadu/skills/avatars/media-planning-3d.png",
    "cadu-channel-intelligence": "/static/images/cadu/skills/avatars/channel-intelligence-3d.png",
    "cadu-audience-intelligence": "/static/images/cadu/skills/avatars/audience-intelligence-3d.png",
    "cadu-format-intelligence": "/static/images/cadu/skills/avatars/format-intelligence-3d.png",
}
_OFFICIAL_HEROES = {
    "cadu-gold": "/static/images/cadu/skills/heroes/cadu-gold-agency-hero.png",
    "cadu-media-planning": "/static/images/cadu/skills/heroes/media-planning-agency-hero.png",
    "cadu-channel-intelligence": "/static/images/cadu/skills/heroes/channel-intelligence-agency-hero.png",
    "cadu-audience-intelligence": "/static/images/cadu/skills/heroes/audience-intelligence-agency-hero.png",
    "cadu-format-intelligence": "/static/images/cadu/skills/heroes/format-intelligence-agency-hero.png",
}
for _official_skill in CADU_OFFICIAL_SKILLS:
    _official_skill["avatar_url"] = _OFFICIAL_AVATARS[_official_skill["slug"]]
    _official_skill["hero_url"] = _OFFICIAL_HEROES[_official_skill["slug"]]

# Referências exibidas separadamente da base legada. O snapshot foi conferido
# na página pública da skills.sh em 17/09/2026; não é um "Top 10" inventado
# de um único repositório. A ordem é a de destaque publicada pela fonte.
SKILLS_SH_HIGHLIGHTS = (
    ("grill-me", "grill-me", "mattpocock/skills", "1,2 mi", "https://www.skills.sh/mattpocock/skills/grill-me"),
    ("frontend-design", "frontend-design", "anthropics/skills", "895 mil", "https://www.skills.sh/anthropics/skills/frontend-design"),
    ("agent-browser", "agent-browser", "vercel-labs/agent-browser", "872,3 mil", "https://www.skills.sh/vercel-labs/agent-browser/agent-browser"),
    ("setup-matt-pocock-skills", "setup-matt-pocock-skills", "mattpocock/skills", "847,1 mil", "https://www.skills.sh/mattpocock/skills/setup-matt-pocock-skills"),
    ("grilling", "grilling", "mattpocock/skills", "718,2 mil", "https://www.skills.sh/mattpocock/skills/grilling"),
    ("lark-doc", "lark-doc", "open.feishu.cn", "702,8 mil", "https://www.skills.sh/site/open.feishu.cn/lark-doc"),
    ("teach", "teach", "mattpocock/skills", "667,2 mil", "https://www.skills.sh/mattpocock/skills/teach"),
    ("lark-markdown", "lark-markdown", "open.feishu.cn", "666,8 mil", "https://www.skills.sh/site/open.feishu.cn/lark-markdown"),
    ("lark-vc-agent", "lark-vc-agent", "open.feishu.cn", "644,9 mil", "https://www.skills.sh/site/open.feishu.cn/lark-vc-agent"),
    ("codebase-design", "codebase-design", "mattpocock/skills", "629,1 mil", "https://www.skills.sh/mattpocock/skills/codebase-design"),
)

MARKET_SKILLS = tuple({
    "slug": slug, "name": name, "creator": creator, "installs_display": installs,
    "installs": installs, "source_url": source_url, "metrics_source": "skills.sh",
    "category": "Referência de mercado", "summary": "Skill publicada e destacada na skills.sh.",
} for slug, name, creator, installs, source_url in SKILLS_SH_HIGHLIGHTS)

DIRECTORY_ROWS = """
short-video-production|Produção de vídeos curtos|Vídeo e áudio
copywriting-skills|Copywriting para campanhas|Conteúdo
image-editing|Edição inteligente de imagens|Imagem e design
traffic-acquisition|Aquisição de tráfego|Crescimento
jiaying-tool|Ferramentas para criadores|Criação
viral-creation|Criação de conteúdo viral|Conteúdo
brand-operation|Operação de marca|Marca
content-performance-analysis|Análise de desempenho de conteúdo|Dados
product-selection|Seleção de produtos|Estratégia
livestream-sales|Vendas em transmissões ao vivo|Vendas
graphic-content-creation|Criação de conteúdo gráfico|Imagem e design
meitu-xiuxiu|Tratamento visual com Meitu|Imagem e design
compliance|Conformidade de conteúdo|Governança
photo-editing-tools|Ferramentas para edição de fotos|Imagem e design
stable-design|Consistência de design|Imagem e design
excel-analytics|Análise de dados no Excel|Dados
cover-design|Design de capas|Imagem e design
store-operations|Operação de lojas digitais|Vendas
xinhong-data|Inteligência de dados Xinhong|Dados
topic-participation|Participação em temas relevantes|Conteúdo
private-domain|Audiência proprietária|Crescimento
monetization-strategy|Estratégia de monetização|Estratégia
content-marketing|Marketing de conteúdo|Conteúdo
viral-strategy|Estratégia de viralização|Crescimento
sentiment-monitoring|Monitoramento de sentimento|Dados
content-review|Revisão de conteúdo|Conteúdo
competitor-analysis|Análise de concorrentes|Estratégia
customer-service|Atendimento ao cliente|Relacionamento
title-writing|Criação de títulos|Conteúdo
script-writing|Criação de roteiros|Conteúdo
social-listening|Escuta de redes sociais|Dados
content-planning|Planejamento de conteúdo|Conteúdo
topic-analysis|Análise de temas|Dados
private-marketing|Marketing para bases próprias|Crescimento
advertising|Planejamento de publicidade|Mídia
growth-hacking|Experimentos de crescimento|Crescimento
seeding-copywriting|Copy para campanhas de influência|Conteúdo
xingtu-tool|Gestão de creators com Xingtu|Influência
canva|Criação visual no Canva|Imagem e design
personal-branding|Construção de marca pessoal|Marca
vlog-creation|Criação de vlogs|Vídeo e áudio
graphic-layout|Diagramação de peças gráficas|Imagem e design
account-integration|Integração de contas sociais|Operação
keyword-analysis|Análise de palavras-chave|Dados
account-positioning|Posicionamento de perfil|Marca
content-calendar|Calendário editorial|Conteúdo
seeding-content-creation|Conteúdo para campanhas de influência|Influência
huitun-data|Inteligência de dados Huitun|Dados
data-analytics|Análise de dados|Dados
live-streaming-content|Conteúdo para transmissões ao vivo|Vídeo e áudio
hashtag-optimization|Otimização de hashtags|Conteúdo
data-visualization|Visualização de dados|Dados
persona-building|Construção de personas|Estratégia
yizhuan|Conversão de conteúdo com Yizhuan|Conteúdo
user-persona-analysis|Análise de personas|Dados
trend-jacking|Aproveitamento de tendências|Conteúdo
live-promotion|Promoção de transmissões ao vivo|Crescimento
content-repurposing|Reaproveitamento de conteúdo|Conteúdo
community-management|Gestão de comunidades|Relacionamento
kol-collaboration|Colaboração com líderes de opinião|Influência
ai-marketing|Marketing com inteligência artificial|Estratégia
interaction-automation|Automação de interações|Automação
ju-mama|Gestão de mídia com Ju Mama|Mídia
sales-funnel|Construção de funil de vendas|Vendas
activity-planning|Planejamento de ações promocionais|Estratégia
content-layout|Organização visual de conteúdo|Imagem e design
conversion-optimization|Otimização de conversão|Crescimento
personal-branding-advanced|Marca pessoal avançada|Marca
fan-operations|Gestão de audiência e fãs|Relacionamento
copyright-protection|Proteção de direitos autorais|Governança
content-matrix|Matriz de conteúdo|Conteúdo
influencer-matrix|Matriz de influenciadores|Influência
audio-processing|Tratamento de áudio|Vídeo e áudio
qiangua-data|Inteligência de dados Qiangua|Dados
tutorial-creation|Criação de tutoriais|Conteúdo
content-seo|SEO para conteúdo|Conteúdo
monetization-funnel|Funil de monetização|Vendas
roi-analysis|Análise de retorno sobre investimento|Dados
influencer-outreach|Prospecção de influenciadores|Influência
team-collaboration|Colaboração entre equipes|Operação
publishing-timing|Melhor momento para publicar|Dados
tag-optimization|Otimização de etiquetas|Conteúdo
penalty-avoidance|Prevenção de penalizações|Governança
cold-start|Lançamento de novos perfis|Crescimento
seasonal-campaigns|Campanhas sazonais|Estratégia
viral-mechanisms|Mecanismos de viralização|Crescimento
comment-strategy|Estratégia para comentários|Relacionamento
interaction-content|Conteúdo interativo|Conteúdo
project-management|Gestão de projetos|Operação
after-sales|Relacionamento pós-venda|Relacionamento
product-launch|Lançamento de produtos|Estratégia
algorithm-mechanism|Entendimento de algoritmos|Dados
effect-monitoring|Monitoramento de resultados|Dados
content-scaling|Escala de produção de conteúdo|Conteúdo
crisis-management|Gestão de crises|Governança
community-guidelines|Diretrizes de comunidade|Governança
user-acquisition|Aquisição de usuários|Crescimento
account-security|Segurança de contas|Governança
profile-optimization|Otimização de perfil|Marca
trust-building|Construção de confiança|Marca
""".strip()

SUMMARY_BY_CATEGORY = {
    "Vídeo e áudio": "Estrutura produção, revisão e entrega de materiais audiovisuais.",
    "Conteúdo": "Organiza um processo editorial consistente, do briefing à revisão.",
    "Imagem e design": "Orienta decisões visuais e critérios de acabamento para peças de campanha.",
    "Crescimento": "Organiza hipóteses, canais e experimentos para ampliar resultados.",
    "Criação": "Transforma uma ideia em um fluxo de criação mais claro e replicável.",
    "Marca": "Ajuda a preservar posicionamento, identidade e consistência de marca.",
    "Dados": "Coleta sinais, compara resultados e transforma dados em decisões.",
    "Estratégia": "Conecta objetivo, contexto e escolhas em um plano executável.",
    "Vendas": "Estrutura conversão, abordagem e acompanhamento comercial.",
    "Governança": "Define verificações e limites para publicar com mais segurança.",
    "Relacionamento": "Melhora a conversa e a continuidade com clientes e comunidades.",
    "Mídia": "Apoia decisões de canal, formato, investimento e mensuração.",
    "Influência": "Organiza seleção, abordagem e colaboração com criadores.",
    "Operação": "Padroniza tarefas recorrentes e colaboração entre pessoas.",
    "Automação": "Reduz trabalho manual com uma sequência controlada de ações.",
}

# Snapshot público consultado em skills.sh em 16/09/2026. A plataforma expõe
# instalações, não avaliações em estrelas; mantemos esse nome para não sugerir
# uma métrica que a fonte não oferece. A ordem acompanha DIRECTORY_ROWS.
SKILLS_SH_INSTALLS = (
    745, 548, 416, 331, 329, 327, 322, 315, 311, 304, 299, 286, 273, 270,
    267, 264, 264, 263, 262, 262, 260, 256, 253, 252, 250, 241, 241, 239,
    236, 223, 223, 218, 199, 197, 196, 196, 193, 191, 188, 188, 188, 182,
    182, 181, 180, 180, 180, 179, 179, 178, 176, 175, 175, 173, 173, 172,
    171, 169, 169, 168, 168, 166, 166, 166, 165, 165, 164, 163, 163, 162,
    162, 162, 161, 160, 159, 159, 158, 158, 157, 157, 157, 157, 157, 156,
    156, 155, 155, 155, 155, 154, 154, 153, 153, 153, 152, 152, 152, 152,
    151, 151,
)


def _directory():
    items = []
    for position, row in enumerate(DIRECTORY_ROWS.splitlines(), start=1):
        slug, name, category = row.split("|")
        items.append({
            "slug": slug,
            "name": name,
            "category": category,
            "summary": SUMMARY_BY_CATEGORY[category],
            "source_url": f"https://www.skills.sh/vivy-yi/xiaohongshu-skills/{slug.lower()}",
            "position": position,
            "creator": "vivy-yi",
            "installs": SKILLS_SH_INSTALLS[position - 1],
            "metrics_source": "skills.sh",
        })
    return tuple(items)


DIRECTORY_SKILLS = _directory()


_TOP_SPECS = (
    (
        "copywriting-skills", "Copy para campanhas", "Conteúdo",
        "Transforma briefing e oferta em mensagens claras para anúncios, landing pages e CRM.",
        "Você é o especialista de copy do Cadu. Identifique público, promessa, prova, objeção e ação. Entregue até três alternativas curtas, sem clichês, superlativos vazios ou alegações sem fonte. Preserve termos obrigatórios e sinalize riscos de conformidade.",
        ("Crie três linhas de anúncio para uma campanha de consideração.", "Revise esta copy e deixe a promessa mais específica."),
    ),
    (
        "competitor-analysis", "Análise de concorrentes", "Estratégia",
        "Organiza concorrentes, posicionamentos, mensagens e espaços ainda pouco explorados.",
        "Você é o analista competitivo do Cadu. Separe fatos fornecidos, inferências e perguntas em aberto. Compare proposta, público, mensagem, canal e prova. Não presuma dados atuais nem invente participação de mercado. Termine com oportunidades testáveis.",
        ("Monte uma matriz simples para comparar três concorrentes.", "Quais espaços de comunicação parecem pouco explorados?"),
    ),
    (
        "content-planning", "Planejamento de conteúdo", "Conteúdo",
        "Converte objetivos de comunicação em pilares, pautas e uma cadência sustentável.",
        "Você é o planejador editorial do Cadu. Conecte cada pauta a um objetivo, público, formato e sinal de sucesso. Evite calendários volumosos sem tese. Entregue uma estrutura enxuta que uma equipe consiga produzir e medir.",
        ("Crie quatro pilares editoriais para esta marca.", "Organize duas semanas de conteúdo com uma meta por pauta."),
    ),
    (
        "script-writing", "Roteiros para campanhas", "Conteúdo",
        "Escreve roteiros curtos para peças audiovisuais sem gerar vídeo ou áudio.",
        "Você é o roteirista de teste do Cadu. Gere somente roteiro em texto: cenas, fala ou locução, texto em tela e duração estimada. Nunca prometa gerar, editar ou renderizar vídeo ou áudio. Limite a entrega a 60 segundos e preserve fatos fornecidos.",
        ("Escreva um roteiro vertical de 20 segundos.", "Transforme esta ideia em roteiro com cenas e texto na tela."),
    ),
    (
        "social-listening", "Escuta de redes sociais", "Dados",
        "Estrutura temas, sinais e perguntas para acompanhar conversas sobre uma marca.",
        "Você é o analista de escuta do Cadu. Trabalhe apenas com dados entregues pelo usuário. Agrupe temas, intenção, risco e oportunidade; diferencie volume de relevância e não simule acesso a redes sociais. Indique consultas e fontes necessárias.",
        ("Organize estes comentários por tema e intenção.", "Crie um plano de monitoramento para o lançamento."),
    ),
    (
        "data-analytics", "Análise de desempenho", "Dados",
        "Transforma tabelas e indicadores em diagnóstico, decisão e próximo teste.",
        "Você é o analista de desempenho do Cadu. Valide período, unidade, base de comparação e qualidade dos dados. Mostre cálculo quando houver números. Separe correlação de causalidade e termine com decisões e verificações prioritárias.",
        ("Leia estes indicadores e destaque três decisões.", "Compare os períodos e explique o que ainda não pode ser concluído."),
    ),
    (
        "brand-operation", "Operação de marca", "Marca",
        "Organiza regras, ativos e decisões para manter a marca consistente no trabalho diário.",
        "Você é o guardião operacional de marca do Cadu. Use somente regras e ativos fornecidos. Classifique o que é obrigatório, preferencial e proibido; encontre conflitos e produza um checklist curto para produção e aprovação.",
        ("Transforme estas regras de marca em checklist.", "Revise este briefing contra as restrições da marca."),
    ),
    (
        "conversion-optimization", "Otimização de conversão", "Crescimento",
        "Prioriza hipóteses para reduzir atrito e melhorar a próxima ação do público.",
        "Você é o especialista de conversão do Cadu. Mapeie etapa, intenção, fricção, evidência e métrica. Não trate opinião como resultado. Priorize poucas hipóteses por impacto, confiança e esforço e descreva como testar cada uma.",
        ("Encontre os principais atritos desta página.", "Priorize cinco testes para melhorar a conversão."),
    ),
    (
        "advertising", "Planejamento de publicidade", "Mídia",
        "Conecta mensagem, canal, formato e mensuração em uma campanha coerente.",
        "Você é o estrategista de publicidade do Cadu. Comece pela tarefa de comunicação e pela ação esperada. Relacione canais e formatos a papéis claros, sem inventar custos ou alcance. Entregue arquitetura, mensagens, KPIs e dependências.",
        ("Estruture uma campanha de lançamento em três fases.", "Relacione canais, formatos e KPI para esta campanha."),
    ),
)


def _top_skills():
    skills = [CADU_MEDIA_PLANNING]
    for rank, (slug, name, category, summary, instructions, prompts) in enumerate(_TOP_SPECS, start=2):
        skills.append({
            "slug": slug,
            "name": name,
            "category": category,
            "summary": summary,
            "description": summary,
            "credit_cost": 1,
            "model": "openai/gpt-4o-mini",
            "featured": rank <= 3,
            "rank": rank,
            "status": "published",
            "is_testable": True,
            "image_url": "/static/images/cadu/products/skills.png",
            "instructions": instructions,
            "prompts": prompts,
        })
    return tuple(skills)


TOP_SKILLS = _top_skills()
CATALOG_SKILLS = tuple({item["slug"]: item for item in (*TOP_SKILLS, *CADU_OFFICIAL_SKILLS)}.values())
PUBLIC_SKILLS = CATALOG_SKILLS
_TOP_SLUGS = {item["slug"] for item in TOP_SKILLS}
# O diretório original tem 100 referências externas. As 90 não promovidas
# permanecem para descoberta; skills próprias adicionais vêm do banco e também
# são executáveis quando publicadas com instruções.
DEFERRED_SKILLS = tuple(item for item in DIRECTORY_SKILLS if item["slug"] not in _TOP_SLUGS)[:90]


def get_public_skill(slug: str):
    return next((item for item in PUBLIC_SKILLS if item["slug"] == slug), None)
