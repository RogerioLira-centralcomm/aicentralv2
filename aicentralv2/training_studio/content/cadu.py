"""Sessão 4 — Cadu começa na restrição."""

from .markup import block, h2, h3, notes, p, page, sources, ul

NOTAS = {
    "tese": "Cadu é a mesa, não a demo de IA. Restrição → catálogo → first-wave → correção.",
    "nao_repetir": "Não repetir 185 mi, 9h09, ANAC. Sem tour de feature.",
    "pergunta": "Qual restrição deste brief o Cadu não pode inventar?",
    "tempo": "15 minutos",
}

FONTES = [
    {
        "url": "oficial:skill-cadu",
        "titulo": "Skill Cadu / catálogo CentralX",
        "resumo": "Restrição → catálogo real → first-wave → correção. Sem inventar mix.",
    },
]


def html():
    return (
        notes(
            "<strong>Palco · 15 min.</strong> Cinco passos. Sem slide de produto."
        )
        + page(
            "title",
            h2("Cadu começa na restrição")
            + p("IA consulta o catálogo real. Não inventa mix."),
        )
        + page(
            "copy",
            h3("Pergunta da sala")
            + p("Qual restrição deste brief o Cadu não pode inventar?"),
        )
        + page(
            "split",
            block(
                "tese",
                h3("Cinco passos na mesa")
                + ul(
                    [
                        "<strong>1. Briefing.</strong> Objetivo, praça, verba, safety, Places.",
                        "<strong>2. Catálogo.</strong> Só o que se transaciona.",
                        "<strong>3. Hipótese.</strong> Percentual por família. Substituição escrita.",
                        "<strong>4. First-wave.</strong> Uma métrica por formato.",
                        "<strong>5. Correção.</strong> Escalar só o que aguentou.",
                    ]
                ),
            ),
        )
        + page(
            "copy",
            block(
                "tese",
                h3("Se o dado não está no catálogo, fica pendente.")
                + p(
                    "A banca cobra: unidade de valor, família, first-wave. "
                    "Roadmap não entra."
                ),
            ),
        )
        + sources("Skill Cadu / catálogo CentralX — estrutura de planejamento da imersão")
    )
