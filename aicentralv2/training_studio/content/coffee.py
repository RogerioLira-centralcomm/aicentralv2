"""Intervalo."""

from .markup import h2, notes, p

NOTAS = {
    "tese": "Escolher o briefing e a unidade de valor.",
    "nao_repetir": "",
    "pergunta": "Fintech, beleza ou food — qual moeda?",
    "tempo": "10 minutos",
}

FONTES = []


def html():
    return (
        h2("Coffee break — 10 minutos")
        + notes("Quem quiser já escolhe o briefing da banca e a unidade de valor.")
        + p(
            "10h35–10h45. Intervalo curto. Fintech (R$ 80 mil), beleza D2C "
            "(R$ 250 mil) ou food (R$ 800 mil). Pensar família + moeda + "
            "se o brief pede lugar físico."
        )
    )
