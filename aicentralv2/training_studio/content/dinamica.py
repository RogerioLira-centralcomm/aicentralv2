"""Sessão 9 — banca de plano."""

from .markup import block, h2, h3, notes, p, sources, ul

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
        h2("Banca de plano")
        + notes(
            "<strong>Palco · 40 min.</strong> 20 para montar, 20 para "
            "bancar. Rubrica no quadro. Zerar grupo que não escrever a moeda."
        )
        + block(
            "dinamica",
            p(
                "Cada grupo recebe um briefing e um envelope. O mix usa o "
                "que veio nas sessões: unidade de valor, família digital, "
                "Places se a praça for física, first-wave, restrição Cadu. "
                "Não é palestra.",
            )
            + ul(
                [
                    "Famílias e % de verba — com regra de substituição",
                    "Formato e recorte",
                    "Unidade de valor da primeira onda",
                    "KPI que autoriza escala",
                    "Risco: brand safety, canibalização com mídia do app, frequência, cerca versus presença",
                ]
            ),
        )
        + h3("Briefing A — Fintech de conta digital · R$ 80 mil")
        + p(
            "Objetivo: aquisição de conta com cartão na Grande São Paulo, "
            "30 dias. Público 25–40, renda C+/B. Sem performance cega em "
            "open web sem brand safety. KPI de cliente: CPA de conta aberta "
            "e qualidade do primeiro depósito.",
            "A banca cobra: unidade de valor da first-wave (não o CPA "
            "final), se Serasa/editorial entra, se Places (Congonhas) faz "
            "sentido ou é vaidade de aeroporto.",
        )
        + h3("Briefing B — Beleza D2C · R$ 250 mil")
        + p(
            "Lançamento de skincare, 45 dias, Sudeste. Branding curto + "
            "conversão no e-commerce próprio. Mulheres 22–35. KPI de "
            "cliente: VTR/atenção no topo e ROAS na base.",
            "A banca cobra: qual família de sessão paga o topo, o que sai "
            "do short-form se o asset for estático, first-wave antes do ROAS.",
        )
        + h3("Briefing C — Rede de food · R$ 800 mil")
        + p(
            "Brand nacional + incremento de pedidos em app, 60 dias. "
            "Coexistir com mídia própria do marketplace e com TV/portal. "
            "KPI de cliente: ad recall e ticket incremental.",
            "A banca cobra: canibalização iFood, se DOOH/Places entra como "
            "família ou como enfeite, unidade de valor do incremento.",
        )
        + block(
            "dinamica",
            h3("Rubrica — sem inventar UU")
            + ul(
                [
                    "Moeda da abertura escrita no plano",
                    "Substituição entre famílias (incluindo Places, se couber)",
                    "First-wave distinta de escala",
                    "Restrição do brief respeitada",
                    "Risco nomeado",
                ]
            ),
        )
        + sources(
            "Briefings da Imersão em Mídias Complexas — 28 de setembro",
        )
    )
