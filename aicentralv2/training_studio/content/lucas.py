"""Sessões 7 e 8 — Lucas Facchini."""

from .markup import block, h2, h3, notes, p, page, sources, ul

NOTAS_INTERATIVOS = {
    "tese": "Interativo é prova de atenção quando o mecanismo obriga o gesto.",
    "nao_repetir": "Não redefinir atenção. Não virar catálogo de 30 peças.",
    "pergunta": "Este brief paga o interativo — ou um display viewable resolve a first-wave?",
    "tempo": "15 minutos",
}

NOTAS_PROGRAMATICA = {
    "tese": "Trinta formatos agrupados por família. Aberto não é qualquer impressão.",
    "nao_repetir": "Não relistar os 16 logos. Sem MRC 101.",
    "pergunta": "Portal ou feed — qual inventário autoriza o KPI da primeira onda?",
    "tempo": "15 minutos",
}

FONTES_INTERATIVOS = [
    {
        "url": "oficial:interativo-first-wave",
        "titulo": "Mesa Centralcomm — interativo como prova de first-wave",
        "resumo": "O mecanismo (toque, escolha, play) autoriza atenção sem painel Lumen.",
    },
]

FONTES_PROGRAMATICA = [
    {
        "url": "oficial:catalogo-formatos",
        "titulo": "Catálogo de formatos CentralX — famílias de segmentação",
        "resumo": "Agrupar ~30 formatos por família. Aberto ≠ qualquer impressão.",
    },
    {
        "url": "https://www.iab.com/wp-content/uploads/2025/11/CIMM_IAB_Attention_Measurement_Playbook_for_Marketers_November_2025.pdf",
        "titulo": "IAB / CIMM 2025 — atenção como filtro",
        "resumo": "Complementa viewability. Não substitui.",
    },
]


def html_interativos():
    return (
        notes(
            "<strong>Palco · 15 min.</strong> O gesto e o que ele autoriza."
        )
        + page(
            "title",
            h2("O gesto prova a first-wave")
            + p("Toque, escolha, play, shop. Não é novidade."),
        )
        + page(
            "copy",
            h3("Pergunta da sala")
            + p(
                "Este brief paga o interativo — ou um display viewable "
                "resolve a first-wave?"
            ),
        )
        + page(
            "split",
            block(
                "tese",
                ul(
                    [
                        "<strong>Toque</strong> prova interrupção.",
                        "<strong>Escolha</strong> prova consideração.",
                        "<strong>Playable</strong> prova tempo de sessão.",
                        "<strong>Shoppable</strong> prova intenção de SKU.",
                    ]
                )
                + p(
                    "Quando é caro: verba abaixo do floor, criativo sem estado, "
                    "CPA cego. Quando é o único jeito: precisa provar atenção "
                    "sem currency visual."
                ),
            ),
        )
        + sources("Mesa Centralcomm — formatos interativos como prova de first-wave")
    )


def html_programatica():
    return (
        notes(
            "<strong>Palco · 15 min.</strong> Agrupar. Portal versus feed."
        )
        + page(
            "title",
            h2("Aberto não é qualquer impressão")
            + p("Agrupar ~30 formatos. Deal, qualidade, contexto."),
        )
        + page(
            "copy",
            h3("Pergunta da sala")
            + p("Portal ou feed — qual inventário autoriza o KPI da primeira onda?"),
        )
        + page(
            "split",
            block(
                "tese",
                h3("O que a família prova na first-wave")
                + ul(
                    [
                        "<strong>Display de impacto</strong> — viewability + adjacência.",
                        "<strong>Vídeo curto</strong> — VTR / atenção.",
                        "<strong>Sessão / CTV</strong> — completion / attentive seconds.",
                        "<strong>Áudio</strong> — completion 15s/30s.",
                        "<strong>Interativo</strong> — interação qualificada.",
                        "<strong>Native</strong> — tempo na peça, não clique vão.",
                    ]
                ),
            ),
        )
        + page(
            "copy",
            block(
                "tese",
                h3("Portal versus feed")
                + p(
                    "Editorial ganha em construção. Feed ganha em volume. "
                    "Escala sem first-wave é a quebra do Max."
                ),
            ),
        )
        + sources(
            "Catálogo de formatos CentralX — famílias de segmentação",
            "IAB / CIMM 2025 — atenção como filtro de qualidade da impressão",
        )
    )
