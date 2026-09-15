"""Catálogo público inicial e metadados das skills próprias."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent

CADU_MEDIA_PLANNING = {
    "slug": "cadu-media-planning",
    "name": "Planejamento de mídia Cadu",
    "category": "Planejamento de mídia",
    "summary": "Transforma briefing, contexto de marca e os canais da CentralX em um plano defendível.",
    "description": "Estratégia, mix, verba, formatos, voo, KPIs e critérios de otimização conectados à realidade comercial da agência.",
    "credit_cost": 2,
    "model": "openai/gpt-4o-mini",
    "featured": True,
    "path": ROOT / "media-planning" / "SKILL.md",
    "prompts": (
        "Monte um mix inicial para uma campanha regional de consideração.",
        "Revise este plano e identifique inconsistências de verba e KPI.",
        "Compare os melhores canais disponíveis para alcançar decisores B2B.",
    ),
}

PUBLIC_SKILLS = (CADU_MEDIA_PLANNING,)

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
        })
    return tuple(items)


DIRECTORY_SKILLS = _directory()


def get_public_skill(slug: str):
    return next((item for item in PUBLIC_SKILLS if item["slug"] == slug), None)
