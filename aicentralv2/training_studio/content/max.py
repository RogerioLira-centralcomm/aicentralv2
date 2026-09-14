"""Sessão 6 — o plano quebra no formato."""

from .markup import block, h2, h3, notes, p, page, sources, ul

NOTAS = {
    "tese": "Campanha quebra de formato, criativo e recorte — não só de verba.",
    "nao_repetir": "Não relistar canais. Não redefinir atenção. Sem “criativo é importante” sem regra.",
    "pergunta": "Qual métrica da primeira onda deste formato autoriza escalar?",
    "tempo": "35 minutos",
}

FONTES = [
    {
        "url": "oficial:patologias-2026",
        "titulo": "Tese de mesa — patologias de campanha 2026",
        "resumo": "Recorte sem volume, estático em short-form, métrica de vaidade no lugar de first-wave.",
    },
]


def html():
    return (
        notes(
            "<strong>Palco · 35 min.</strong> Quatro quebras, depois o método."
        )
        + page(
            "title",
            h2("O plano quebra no formato")
            + p("A verba erra menos do que o criativo copiado."),
        )
        + page(
            "copy",
            h3("Pergunta da sala")
            + p("Qual métrica da primeira onda deste formato autoriza escalar?"),
        )
        + page(
            "split",
            block(
                "tese",
                h3("Quatro quebras")
                + ul(
                    [
                        "<strong>Recorte sem volume.</strong> First-wave sem n não escala.",
                        "<strong>Estático no short-form.</strong> Se o asset é 1:1, a família social já perdeu.",
                        "<strong>Formato copiado.</strong> Takeover não vira bumper.",
                        "<strong>Vaidade no lugar de first-wave.</strong> A moeda da abertura não estava no KPI.",
                    ]
                ),
            ),
        )
        + page(
            "copy",
            block(
                "tese",
                h3("First-wave por formato. Depois escala.")
                + p(
                    "Atenção na sessão. VTR no vídeo. CTR qualificado no editorial. "
                    "CPA de teste na utilidade. Presença no Places."
                )
                + p("Sem first-wave, a banca zera o grupo — mesmo com mix bonito."),
            ),
        )
        + sources("Tese de mesa Centralcomm / Imersão 28 set — patologias de campanha 2026")
    )
