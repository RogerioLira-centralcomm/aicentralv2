"""Shared intent boundary for project searches and project readouts."""

import re
import unicodedata


def is_overview_query(query: str) -> bool:
    text = unicodedata.normalize("NFKD", str(query or "")).encode("ascii", "ignore").decode("ascii").lower()
    text = " ".join(text.split())
    return bool(
        re.search(r"\b(?:visao geral|panorama|dossie)\b.{0,90}\b(?:projeto|campanha)\b", text)
        or re.search(r"\b(?:tudo|completo)\b.{0,60}\b(?:sobre|do|de)\s+(?:esse|este|o)?\s*(?:projeto|campanha)\b", text)
        or re.search(r"\b(?:o que|que)\s+(?:voce\s+)?(?:sabe|conhece)\s+(?:sobre|do|desse|deste)\s+(?:esse|este|o)?\s*(?:projeto|campanha)\b", text)
        or re.search(r"\b(?:do que se trata|sobre o que e)\s+(?:esse|este|o)?\s*(?:projeto|campanha)\b", text)
        or re.search(r"\b(?:leitura de partida|resumo geral|apresentacao geral)\b.{0,90}\b(?:projeto|campanha)\b", text)
    )
