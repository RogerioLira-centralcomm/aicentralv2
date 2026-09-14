"""Sessões 7 e 8 — Lucas Facchini."""

from .markup import block, h2, h3, notes, p, sources, ul

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
        h2("Interativo como prova, não como novidade")
        + notes(
            "<strong>Palco · 15 min.</strong> A sala já conhece playable e "
            "shoppable. Mostrar o gesto e o que ele autoriza na first-wave."
        )
        + block(
            "tese",
            p(
                "Toque, escolha, play, shop. O mecanismo obriga o corpo. "
                "Isso autoriza uma first-wave que o display viewable não "
                "autoriza — sem precisar de painel Lumen na praça. Não "
                "autoriza branding de 30 dias com uma peça.",
                "Toque prova interrupção. Escolha prova consideração. "
                "Playable prova tempo de sessão. Shoppable prova intenção "
                "de SKU. Cada gesto autoriza um KPI diferente — não "
                "agrupar tudo como “interativo” no mix.",
                "Quando é caro demais: verba de teste abaixo do floor, "
                "criativo sem estado, brief de CPA cego. Quando é o único "
                "jeito: precisa provar atenção em ambiente sem currency "
                "visual e o gesto faz parte da oferta.",
            ),
        )
        + sources(
            "Mesa Centralcomm — formatos interativos como prova de first-wave",
        )
    )


def html_programatica():
    return (
        h2("Famílias de formato e programática de alto padrão")
        + notes(
            "<strong>Palco · 15 min.</strong> Agrupar. Portal versus feed "
            "como decisão de inventário. Sem 30 slides iguais."
        )
        + block(
            "tese",
            h3("Agrupar os ~30, não listar")
            + ul(
                [
                    "<strong>Display de impacto</strong> (takeover, billboard) — prova contexto; first-wave = viewability + adjacência.",
                    "<strong>Vídeo curto</strong> — prova interrupção; first-wave = VTR / atenção.",
                    "<strong>Vídeo de sessão / CTV</strong> — prova dwell; first-wave = completion / attentive seconds.",
                    "<strong>Áudio</strong> — prova hábito; first-wave = completion de 15s/30s.",
                    "<strong>Interativo</strong> — prova gesto; first-wave = interação qualificada.",
                    "<strong>Native / editorial</strong> — prova leitura; first-wave = tempo na peça, não clique vão.",
                ]
            )
            + p(
                "O que a família prova na primeira onda não é o que ela "
                "prova depois. Escala sem first-wave é a quebra do Max.",
            ),
        )
        + block(
            "tese",
            h3("Programática de alto padrão")
            + p(
                "Deal, qualidade de inventário, controle de contexto. "
                "“Aberto” não é qualquer impressão. Sem brand safety e sem "
                "adjacência, o CPM barato devolve a saturação do primeiro "
                "bloco — 9h09 de tela, zero unidade de valor.",
                "Portal versus feed: o editorial ganha quando o brief pede "
                "construção e adjacência; o feed ganha quando pede volume "
                "e recorte. É a mesma regra de substituição da sessão 2, "
                "agora no formato.",
            ),
        )
        + sources(
            "Catálogo de formatos CentralX — famílias de segmentação",
            "IAB / CIMM 2025 — atenção como filtro de qualidade da impressão",
        )
    )
