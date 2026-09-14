"""Intervalo."""

from .markup import h2, notes, p, page

NOTAS = {
    "tese": "Escolher o briefing e a unidade de valor.",
    "nao_repetir": "",
    "pergunta": "Fintech, beleza ou food — qual moeda?",
    "tempo": "10 minutos",
}

FONTES = []


def html():
    return (
        notes("Quem quiser já escolhe o briefing da banca e a unidade de valor.")
        + page(
            "title",
            h2("Intervalo · escolher a moeda")
            + p("10h35–10h45. Fintech R$ 80 mil · beleza R$ 250 mil · food R$ 800 mil."),
        )
        + page(
            "copy",
            p("Pensar família + moeda + se o brief pede lugar físico."),
        )
    )
