"""Sessão 1 — atenção como moeda de compra."""

from .markup import block, h2, h3, notes, p, sources, ul

NOTAS = {
    "tese": (
        "O Brasil está saturado de tela. O plano médio ainda otimiza impressão. "
        "Escolham a unidade de valor antes do canal."
    ),
    "nao_repetir": "Não definir MRC. Não listar 16 canais. Não tratar ad reach como MAU.",
    "pergunta": "No último plano que vocês aprovaram, a unidade de valor era a mesma do KPI do cliente?",
    "tempo": "15 minutos",
}

FONTES = [
    {
        "url": "https://datareportal.com/reports/digital-2025-global-overview-report",
        "titulo": "Digital 2025 Global Overview — DataReportal / We Are Social",
        "resumo": "5,56 bi online, 6h38/dia (GWI), 2h21 em redes. Identidade ≠ indivíduo.",
    },
    {
        "url": "https://datareportal.com/reports/digital-2026-brazil",
        "titulo": "Digital 2026 Brazil — DataReportal (out/2025)",
        "resumo": "185 mi online, 150 mi redes. Ad reach ≠ MAU. 9h09 é jan/2025.",
    },
    {
        "url": "https://www.iab.com/wp-content/uploads/2025/11/CIMM_IAB_Attention_Measurement_Playbook_for_Marketers_November_2025.pdf",
        "titulo": "IAB + CIMM, Attention Measurement Playbook, nov/2025",
        "resumo": "Atenção complementa viewability. Não substitui. Não vira KPI sozinho.",
    },
    {
        "url": "https://lumen-research.com/white-papers/attentive-seconds-one-currency-to-rule-them-all/",
        "titulo": "Lumen — Attentive seconds",
        "resumo": "Olho no anúncio. MPU ~8% olhado, ~1,3s. Autoriza formato vs formato.",
    },
    {
        "url": "https://lumen-research.com/blog/viewability-tv-ads/",
        "titulo": "Lumen + TVision — TV attention (UK)",
        "resumo": "Pessoa na sala + olho na TV. 30s de TV ~11,8s de atenção visual.",
    },
    {
        "url": "https://www.adelaidemetrics.com/blog/attention-metrics-vs-viewability-vs-duration",
        "titulo": "Adelaide — viewability vs duration vs AU",
        "resumo": "AU 0–100 é qualidade do placement. Não traduzir em segundos.",
    },
]


def html():
    return (
        h2("A atenção como moeda de compra")
        + notes(
            "<strong>Palco · 15 min.</strong> Abrir com a pergunta da sala. "
            "Os números existem para provar saturação e bases incomparáveis — "
            "não para impressionar alcance. Não definir viewability."
        )
        + block(
            "tese",
            h3("A unidade de valor vem antes do mix")
            + p(
                "Esta mesa já compra mídia. O que muda em 2026 não é o inventário: "
                "é a unidade que o briefing autoriza. Viewability MRC continua sendo "
                "a porta técnica — 50% dos pixels por 1s no display, 2s no vídeo. "
                "Ela não diz se alguém olhou. Quem ainda fecha plano em impressão "
                "viewable está comprando oportunidade, não impacto.",
                "O IAB e o CIMM, no <em>Attention Measurement Playbook</em> de "
                "novembro de 2025, fecham o ponto: atenção complementa viewability. "
                "Não a substitui. Não vira KPI único de campanha. É filtro de "
                "qualidade da impressão que vocês já sabem comprar.",
            ),
        )
        + block(
            "dado",
            h3("Saturação: o Brasil não é o mundo médio")
            + p(
                "Digital 2025 (We Are Social / DataReportal, início de 2025): "
                "<strong>5,56 bilhões</strong> de pessoas online — 67,9% da "
                "população mundial. +136 milhões no ano. 2,63 bilhões ainda "
                "offline. Identidades em redes: <strong>5,24 bilhões</strong> "
                "(63,9%). Identidade não é indivíduo único.",
                "Tempo do usuário adulto, GWI: <strong>6h38 por dia</strong> "
                "online — 3h46 no celular, 2h52 no computador. Tempo em redes: "
                "<strong>2h21 por dia</strong>, 10 minutos abaixo do início de 2023.",
                "Brasil, Digital 2026 DataReportal (dados de outubro de 2025): "
                "população 213 milhões. Internet: <strong>185 milhões</strong> "
                "(86,9%). Redes: <strong>150 milhões</strong> de identidades "
                "(70,4%). O tempo de tela de <strong>9h09 por dia</strong> "
                "(5h12 no smartphone, 3h57 no computador) é do Digital 2025, "
                "janeiro de 2025 — o relatório de 2026 não republicou o número "
                "na página livre. No palco, datar. Não misturar jan/25 com out/25.",
                "A tese para esta sala: 9h09 contra 6h38. Frequência sobe, "
                "substituição entre canais fica opaca, e o plano que soma bases "
                "de ad reach como se fossem pessoas únicas mente no slide 2.",
            ),
        )
        + block(
            "dado",
            h3("Ad reach não é MAU — e LinkedIn não entra na mesma coluna")
            + p(
                "Ferramentas das plataformas, final de 2025, Digital 2026 Brazil. "
                "É alcance de anúncio, não monthly active users:",
            )
            + ul(
                [
                    "YouTube: 150 milhões",
                    "Instagram: 147 milhões — 87,3% dos adultos 18+",
                    "TikTok: 131 milhões com 18+ — 80,3% dos adultos",
                    "Facebook: 109 milhões",
                    "LinkedIn: 90 milhões de <strong>membros cadastrados</strong>, não MAU",
                ]
            )
            + p(
                "LinkedIn publica member, não active. Comparar 90 milhões com "
                "147 milhões do Instagram é erro de mesa. O número serve para "
                "mostrar fragmentação e moedas incompatíveis — não para abrir "
                "o mapa de canais. O mapa vem no bloco seguinte.",
            ),
        )
        + block(
            "tese",
            h3("Três métricas, três autorizações de compra")
            + p(
                "<strong>Lumen — attentive seconds.</strong> Olho no anúncio. "
                "O white paper da casa: MPU com ~8% de chance de ser olhado e "
                "~1,3s quando olhado; 1.000 inserções de TV ~6.000 attentive "
                "seconds. Autoriza comparar formato contra formato na mesma "
                "moeda visual. Não autoriza ROAS.",
                "<strong>TVision — pessoa na sala + olho na TV.</strong> "
                "Segundo a segundo. Painel UK com Lumen: ~20% das TVs sem "
                "ninguém na sala; ~43% das peças notadas; 30s de TV ~11,8s "
                "de atenção visual. Autoriza CTV/TV. Não autoriza feed mobile.",
                "<strong>Adelaide AU — 0 a 100.</strong> Qualidade do placement, "
                "treinada em exposição, eye-tracking e outcome. Não é duração "
                "de olhar. Autoriza planning e otimização de inventário. "
                "Não traduzam AU em segundos e não somem AU com Lumen.",
                "Regra de briefing: escolher <em>uma</em> unidade de valor "
                "para a primeira onda — viewability, attentive second, AU, "
                "VTR qualificado ou CPA de teste — e escrever o que ela "
                "<em>não</em> prova. Sem isso, o mix vira lista de logos.",
            ),
        )
        + sources(
            '<a href="https://datareportal.com/reports/digital-2025-global-overview-report">Digital 2025 Global Overview — DataReportal / We Are Social</a>',
            '<a href="https://datareportal.com/reports/digital-2026-brazil">Digital 2026 Brazil — DataReportal (out/2025)</a>',
            '<a href="https://www.iab.com/wp-content/uploads/2025/11/CIMM_IAB_Attention_Measurement_Playbook_for_Marketers_November_2025.pdf">IAB + CIMM, Attention Measurement Playbook, nov/2025</a>',
            '<a href="https://lumen-research.com/white-papers/attentive-seconds-one-currency-to-rule-them-all/">Lumen — Attentive seconds</a>',
            '<a href="https://lumen-research.com/blog/viewability-tv-ads/">Lumen + TVision — TV attention (UK)</a>',
            '<a href="https://www.adelaidemetrics.com/blog/attention-metrics-vs-viewability-vs-duration">Adelaide — viewability vs duration vs AU</a>',
        )
    )
