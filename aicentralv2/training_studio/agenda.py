"""Grade e roteiros da Imersão em Mídias Complexas — só este treinamento."""

CHANNELS = [
    {"key": "linkedin", "name": "LinkedIn", "site": "https://www.linkedin.com"},
    {"key": "instagram", "name": "Instagram", "site": "https://www.instagram.com"},
    {"key": "tiktok", "name": "TikTok", "site": "https://www.tiktok.com"},
    {"key": "g1", "name": "g1", "site": "https://g1.globo.com"},
    {"key": "cnn", "name": "CNN Brasil", "site": "https://www.cnnbrasil.com.br"},
    {"key": "sbt", "name": "SBT", "site": "https://www.sbt.com.br"},
    {"key": "serasa", "name": "Serasa", "site": "https://www.serasa.com.br"},
    {"key": "uber", "name": "Uber", "site": "https://www.uber.com"},
    {"key": "99", "name": "99", "site": "https://99app.com"},
    {"key": "ifood", "name": "iFood", "site": "https://www.ifood.com.br"},
    {"key": "amazon", "name": "Amazon", "site": "https://www.amazon.com.br"},
    {"key": "spotify", "name": "Spotify", "site": "https://www.spotify.com"},
    {"key": "netflix", "name": "Netflix", "site": "https://www.netflix.com"},
    {"key": "prime", "name": "Prime Video", "site": "https://www.primevideo.com"},
    {"key": "disney", "name": "Disney+", "site": "https://www.disneyplus.com"},
    {"key": "hbo", "name": "Max / HBO", "site": "https://www.max.com"},
]


def _p(*parts):
    return "".join(f"<p>{part}</p>" for part in parts)


def _channel_placeholder(channel):
    name = channel["name"]
    key = channel["key"]
    return (
        f'<section class="ts-canal" data-canal="{key}" id="canal-{key}">'
        f"<!-- CANAL:{key} -->"
        f"<h2>{name}</h2>"
        "<p><strong>Estrutura de audiência.</strong> A pesquisa de mercado ainda não "
        "preencheu este bloco. Use o botão Enriquecer ou peça ao agente.</p>"
        "<p><strong>Case.</strong> Pendente — um case real com o máximo de dados "
        "disponíveis (objetivo, verba quando pública, formato, resultado).</p>"
        f"<p><strong>Por que {name} interessa ao anunciante.</strong> Pendente.</p>"
        f"<!-- /CANAL:{key} -->"
        "</section>"
    )


def html_mercado():
    canais = "".join(_channel_placeholder(item) for item in CHANNELS)
    return (
        "<h2>Mercado global e o mapa de canais</h2>"
        + _p(
            "Alexandre Borges e Apolo Lira abrem a Imersão em Mídias Complexas "
            "(28 de setembro, 9h–12h30). Os dois se alternam neste bloco de 45 minutos: "
            "primeiro o recorte global de usuários e tempo de tela, depois cada canal "
            "com audiência, um case real e a defesa de por que ele importa para o "
            "anunciante final.",
            "Trabalhamos com o que o mercado publica. Número sem fonte fica marcado "
            "como pendente — não inventamos UU, share ou ROAS.",
            "Canais desta manhã: LinkedIn, Instagram, TikTok, portais (g1, CNN, SBT, "
            "Serasa), Uber, 99, iFood, Amazon, Spotify, Netflix, Prime Video, Disney+ e Max/HBO.",
        )
        + canais
    )


def html_cadu():
    return (
        "<h2>IA, produtos digitais e a Skill Cadu</h2>"
        + _p(
            "Apolo Lira conduz o segundo bloco (9h45–10h15) com o que a Centralcomm "
            "entrega de produto digital para o mercado: não um tour de features, "
            "uma estrutura de planejamento.",
            "Começamos pela Skill de mídia com inteligência de planejamento Cadu. "
            "A tese: o planejador não começa no Excel vazio — começa com contexto "
            "de canal, formato, audiência e restrição de budget já amarrados.",
            "<strong>Estrutura da Skill Cadu.</strong> 1) Briefing e restrições "
            "(objetivo, praça, verba, recorte de marca). 2) Leitura de canais e "
            "formatos disponíveis no catálogo CentralX. 3) Hipótese de mix e "
            "segmentação. 4) Métricas iniciais a observar na primeira onda. "
            "5) Loop de correção — o mesmo tema que o Max retoma depois do coffee.",
            "Os produtos digitais entram como prova: o que já roda no CentralX "
            "(modelagem de criativos, operação de PI, inteligência de marca) e o "
            "que a Skill precisa consultar para não alucinar mix.",
        )
    )


def html_coffee():
    return (
        "<h2>Coffee break — 15 minutos</h2>"
        + _p(
            "10h15–10h30. Intervalo curto. Quem quiser já escolhe o briefing da "
            "dinâmica (fintech, beleza D2C ou food) para não perder tempo na volta."
        )
    )


def html_dinamica():
    return (
        "<h2>Dinâmica: planejar mídia com briefings e budgets reais</h2>"
        + _p(
            "10h30–11h00. Não é palestra. Cada grupo recebe um briefing de marca "
            "diferente e um envelope de verba. O mix precisa usar o que acabamos de "
            "ver no mapa de canais. No fechamento, cada plano entra para análise e "
            "previsão de impacto (alcance, atenção, frequência e risco) — o motor "
            "de forecast fica na mesa seguinte; hoje o grupo entrega o plano.",
        )
        + "<h3>Briefing A — Fintech de conta digital · R$ 80 mil</h3>"
        + _p(
            "Objetivo: aquisição de conta corrente com cartão na Grande São Paulo, "
            "30 dias. Público 25–40 anos, renda C+/B. Restrição: sem performance "
            "cega em open web sem brand safety. KPI inicial: CPA de conta aberta e "
            "qualidade do primeiro depósito.",
            "Espaço do plano: canais, % do budget, formato, recorte de audiência, "
            "KPI da primeira onda.",
        )
        + "<h3>Briefing B — Beleza D2C · R$ 250 mil</h3>"
        + _p(
            "Objetivo: lançamento de linha de skincare, 45 dias, Sudeste. Mix de "
            "branding curto + conversão no e-commerce próprio. Público mulheres "
            "22–35. KPI inicial: VTR/atenção no topo e ROAS na base.",
            "Espaço do plano: canais, % do budget, formato, recorte de audiência, "
            "KPI da primeira onda.",
        )
        + "<h3>Briefing C — Rede de food · R$ 800 mil</h3>"
        + _p(
            "Objetivo: brand nacional + incremento de pedidos em app, 60 dias. "
            "Precisa coexistir com mídia própria do marketplace e com TV/portal "
            "para construção. KPI inicial: ad recall e ticket incremental.",
            "Espaço do plano: canais, % do budget, formato, recorte de audiência, "
            "KPI da primeira onda.",
        )
        + "<h3>Fechamento — análise e previsão</h3>"
        + _p(
            "Cada plano será lido contra os cases do bloco de mercado. O modelo "
            "já reserva marca, briefing, budget, plano, análise e previsão de "
            "impacto. Na sequência, o agente estima impacto sem inventar UU."
        )
    )


def html_max():
    return (
        "<h2>Formatos, criativos e segmentações: os problemas de 2026</h2>"
        + _p(
            "Max III (11h–11h45). Tese: campanha não quebra só de verba — quebra "
            "de formato errado, criativo que não segura atenção e segmentação que "
            "parece precisa e é só ruído.",
            "Os principais problemas das campanhas em 2026: excesso de recorte "
            "sem volume, criativo estático em ambiente de vídeo curto, formato "
            "copiado de outro canal, métrica de vaidade no lugar de métrica "
            "inicial acionável.",
            "Como melhorar métricas iniciais de forma contínua: definir a métrica "
            "da primeira onda por formato (atenção, VTR, CTR qualificado, CPA de "
            "teste), rodar correção em ciclo curto e só então escalar. Isso "
            "amarra com a Skill Cadu e com o que o Lucas traz de atenção.",
        )
    )


def html_lucas_interativos():
    return (
        "<h2>Novos formatos interativos — 15 minutos</h2>"
        + _p(
            "Lucas Facchini (11h45–12h00). Recorte curto: o que mudou nos "
            "formatos interativos e por que atenção deixou de ser proxy fraco.",
            "Mostrar o mecanismo (toque, escolha, playable, shoppable) e o que "
            "isso faz na métrica inicial — sem transformar o bloco em catálogo.",
        )
    )


def html_lucas_formatos():
    return (
        "<h2>30 formatos, atenção, programática e portais</h2>"
        + _p(
            "Lucas Facchini (12h00–12h30). Agrupar cerca de 30 formatos por "
            "segmentação — não listar 30 slides iguais.",
            "Potencial de métricas de atenção atrelado ao formato: o que cada "
            "família consegue provar na primeira onda e o que só aparece depois.",
            "Programática de alto padrão: qualidade de inventário, controle de "
            "contexto e por que “aberto” não é o mesmo que “qualquer impressão”.",
            "Canais e portais: g1, CNN, SBT e o restante do ecossistema "
            "editorial — quando o portal ganha do feed e quando o feed ganha "
            "do portal.",
        )
    )


SESSIONS = [
    {
        "slug": "mercado-canais",
        "ordem": 1,
        "titulo": "Mercado global e canais",
        "horario_inicio": "09:00",
        "horario_fim": "09:45",
        "facilitadores": ["Alexandre Borges", "Apolo Lira"],
        "tipo": "bloco",
        "html": html_mercado,
    },
    {
        "slug": "ia-cadu",
        "ordem": 2,
        "titulo": "IA, produtos digitais e Skill Cadu",
        "horario_inicio": "09:45",
        "horario_fim": "10:15",
        "facilitadores": ["Apolo Lira"],
        "tipo": "bloco",
        "html": html_cadu,
    },
    {
        "slug": "coffee",
        "ordem": 3,
        "titulo": "Coffee break",
        "horario_inicio": "10:15",
        "horario_fim": "10:30",
        "facilitadores": [],
        "tipo": "intervalo",
        "html": html_coffee,
    },
    {
        "slug": "dinamica-planos",
        "ordem": 4,
        "titulo": "Dinâmica de planejamentos",
        "horario_inicio": "10:30",
        "horario_fim": "11:00",
        "facilitadores": ["Time"],
        "tipo": "bloco",
        "html": html_dinamica,
    },
    {
        "slug": "max-formatos",
        "ordem": 5,
        "titulo": "Formatos, criativos e segmentações 2026",
        "horario_inicio": "11:00",
        "horario_fim": "11:45",
        "facilitadores": ["Max III"],
        "tipo": "bloco",
        "html": html_max,
    },
    {
        "slug": "lucas-interativos",
        "ordem": 6,
        "titulo": "Formatos interativos",
        "horario_inicio": "11:45",
        "horario_fim": "12:00",
        "facilitadores": ["Lucas Facchini"],
        "tipo": "bloco",
        "html": html_lucas_interativos,
    },
    {
        "slug": "lucas-programatica",
        "ordem": 7,
        "titulo": "30 formatos, atenção e portais",
        "horario_inicio": "12:00",
        "horario_fim": "12:30",
        "facilitadores": ["Lucas Facchini"],
        "tipo": "bloco",
        "html": html_lucas_formatos,
    },
]


def session_html(item):
    builder = item.get("html")
    return builder() if callable(builder) else str(builder or "")
