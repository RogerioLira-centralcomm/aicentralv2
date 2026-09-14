"""Sessão 6 — onde o plano quebra em 2026."""

from .markup import block, h2, h3, notes, p, sources, ul

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
        h2("Onde o plano quebra em 2026")
        + notes(
            "<strong>Palco · 35 min.</strong> Quatro patologias, depois o "
            "método first-wave. Amarra Cadu e a moeda. Sem census."
        )
        + block(
            "tese",
            p(
                "A verba erra menos do que o formato. Em 2026 a mesa já viu "
                "o padrão: recorte sem volume, estático em ambiente de vídeo "
                "curto, peça copiada de outro canal, métrica de vaidade no "
                "lugar da first-wave. Isso não é opinião de criativo — é "
                "falha de unidade de valor no briefing.",
            ),
        )
        + block(
            "tese",
            h3("Quatro quebras")
            + ul(
                [
                    "<strong>Recorte sem volume.</strong> Segmentação que parece precisa e entrega ruído. First-wave sem n suficiente não autoriza escala.",
                    "<strong>Estático no short-form.</strong> TikTok e Reels não pagam banner. Se o único asset é 1:1, a família social já perdeu — voltar à regra de substituição.",
                    "<strong>Formato copiado.</strong> Takeover de portal não vira bumper. Playable não vira display. O Lucas detalha o mecanismo; aqui vale a proibição.",
                    "<strong>Vaidade no lugar de first-wave.</strong> Alcance, likes, viewability sozinha. A moeda da abertura não estava no KPI.",
                ]
            ),
        )
        + block(
            "tese",
            h3("Método: first-wave por formato")
            + p(
                "Definir a métrica da primeira onda <em>por formato</em>: "
                "atenção ou AU no ambiente de sessão; VTR no vídeo; CTR "
                "qualificado no editorial; CPA de teste na utilidade; "
                "presença no recorte no Places. Rodar correção em ciclo "
                "curto. Só então escalar.",
                "O Cadu já deixou o loop escrito. Esta sessão só torna o "
                "loop obrigatório. Sem first-wave, a banca zera o grupo — "
                "mesmo com mix “bonito”.",
            ),
        )
        + sources(
            "Tese de mesa Centralcomm / Imersão 28 set — patologias de campanha 2026",
        )
    )
