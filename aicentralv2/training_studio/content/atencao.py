"""Sessão 1 — comprem atenção, não impressão."""

from .markup import block, h2, h3, metrics_row, notes, p, page, sources, ul

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
        notes(
            "<strong>Palco · 15 min.</strong> Uma página, uma ideia. "
            "Números para saturação e bases incomparáveis — não para alcance."
        )
        + page(
            "title",
            h2("Comprem atenção, não impressão")
            + p("A unidade de valor vem antes do mix."),
        )
        + page(
            "copy",
            h3("Pergunta da sala")
            + p(
                "No último plano que vocês aprovaram, a unidade de valor "
                "era a mesma do KPI do cliente?"
            ),
        )
        + page(
            "split",
            block(
                "tese",
                h3("Viewability é a porta. Não é o impacto.")
                + p(
                    "MRC continua sendo a porta técnica. Quem fecha plano em "
                    "impressão viewable compra oportunidade, não olhar."
                )
                + p(
                    "IAB + CIMM, nov/2025: atenção complementa viewability. "
                    "Não substitui. Não vira KPI único."
                ),
            ),
        )
        + page(
            "copy",
            block(
                "dado",
                h3("O Brasil não é o mundo médio")
                + metrics_row(
                    [
                        {"value": "185 milhões", "label": "Internet BR", "note": "out/2025"},
                        {"value": "150 milhões", "label": "Identidades", "note": "não é UU"},
                        {"value": "9h09", "label": "Tela BR", "note": "jan/2025"},
                        {"value": "6h38", "label": "Mundo adulto", "note": "GWI"},
                    ]
                )
                + p(
                    "Datar no palco. Não misturar jan/25 com out/25. "
                    "Identidade não é indivíduo."
                ),
            ),
        )
        + page(
            "split",
            block(
                "dado",
                h3("Ad reach não é MAU")
                + ul(
                    [
                        "YouTube: 150 milhões",
                        "Instagram: 147 milhões — 87,3% dos adultos 18+",
                        "TikTok: 131 milhões com 18+",
                        "Facebook: 109 milhões",
                        "LinkedIn: 90 milhões de <strong>membros cadastrados</strong>, não MAU",
                    ]
                )
                + p("Comparar 90 mi do LinkedIn com 147 mi do Instagram é erro de mesa."),
            ),
        )
        + page(
            "copy",
            block(
                "tese",
                h3("Três métricas. Três autorizações.")
                + ul(
                    [
                        "<strong>Lumen</strong> — formato × formato. Não autoriza ROAS.",
                        "<strong>TVision</strong> — CTV/TV. Não autoriza feed.",
                        "<strong>Adelaide AU</strong> — planning. Não traduzir em segundos.",
                    ]
                )
                + p(
                    "Uma unidade de valor para a primeira onda — e o que ela "
                    "<em>não</em> prova."
                ),
            ),
        )
        + sources(
            '<a href="https://datareportal.com/reports/digital-2025-global-overview-report">Digital 2025 Global Overview</a>',
            '<a href="https://datareportal.com/reports/digital-2026-brazil">Digital 2026 Brazil</a>',
            '<a href="https://www.iab.com/wp-content/uploads/2025/11/CIMM_IAB_Attention_Measurement_Playbook_for_Marketers_November_2025.pdf">IAB + CIMM, nov/2025</a>',
            '<a href="https://lumen-research.com/white-papers/attentive-seconds-one-currency-to-rule-them-all/">Lumen — Attentive seconds</a>',
            '<a href="https://lumen-research.com/blog/viewability-tv-ads/">Lumen + TVision</a>',
            '<a href="https://www.adelaidemetrics.com/blog/attention-metrics-vs-viewability-vs-duration">Adelaide — AU</a>',
        )
    )
