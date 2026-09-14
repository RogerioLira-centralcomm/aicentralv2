"""Sessão 9 — banca de plano."""

from .markup import block, h2, h3, notes, p, page, sources, ul

NOTAS = {
    "tese": "Bancar o mix: moeda, família, first-wave, risco. Não escolher três canais.",
    "nao_repetir": "Não dar aula. Sem inventar UU.",
    "pergunta": "Qual unidade de valor autoriza este percentual de verba?",
    "tempo": "40 minutos — 20 montar, 20 bancar",
}

FONTES = [
    {
        "url": "oficial:briefings-imersao",
        "titulo": "Briefings da Imersão — 28 de setembro",
        "resumo": "R$ 80 mil fintech / 250 mil beleza / 800 mil food. Rubrica: moeda, substituição, first-wave, risco.",
    },
]


def html():
    return (
        notes(
            "<strong>Palco · 40 min.</strong> 20 para montar, 20 para bancar. "
            "Zerar grupo que não escrever a moeda."
        )
        + page(
            "title",
            h2("Banca: moeda, família, first-wave")
            + p("20 minutos para montar. 20 para bancar."),
        )
        + page(
            "copy",
            block(
                "dinamica",
                h3("O envelope")
                + ul(
                    [
                        "Famílias e % — com regra de substituição",
                        "Formato e recorte",
                        "Unidade de valor da primeira onda",
                        "KPI que autoriza escala",
                        "Risco nomeado",
                    ]
                ),
            ),
        )
        + page(
            "split",
            h3("Briefing A — Fintech · R$ 80 mil")
            + p(
                "Conta com cartão na GSP, 30 dias. 25–40, C+/B. "
                "Sem open web sem brand safety."
            )
            + p(
                "A banca cobra a moeda da first-wave — não o CPA final. "
                "Serasa entra? Congonhas é vaidade?"
            ),
        )
        + page(
            "split",
            h3("Briefing B — Beleza D2C · R$ 250 mil")
            + p("Skincare, 45 dias, Sudeste. VTR/atenção no topo, ROAS na base.")
            + p("O que sai do short-form se o asset for estático? First-wave antes do ROAS."),
        )
        + page(
            "split",
            h3("Briefing C — Rede de food · R$ 800 mil")
            + p("Brand + incremento de pedidos, 60 dias. Ad recall e ticket incremental.")
            + p("Canibalização iFood. Places é família ou enfeite?"),
        )
        + page(
            "copy",
            block(
                "dinamica",
                h3("Rubrica — sem inventar UU")
                + ul(
                    [
                        "Moeda da abertura escrita",
                        "Substituição entre famílias",
                        "First-wave distinta de escala",
                        "Restrição do brief respeitada",
                        "Risco nomeado",
                    ]
                ),
            ),
        )
        + sources("Briefings da Imersão em Mídias Complexas — 28 de setembro")
    )
