"""Decks 16:9 da Imersão — um por sessão e a manhã inteira."""

from .decks import SESSION_DECKS, morning_deck, session_deck, session_index
from .live import deck_from_html, deck_from_sessao, pages_from_html, slides_payload


__all__ = [
    "SESSION_DECKS",
    "deck_from_html",
    "deck_from_sessao",
    "morning_deck",
    "pages_from_html",
    "session_deck",
    "session_index",
    "slides_payload",
]
