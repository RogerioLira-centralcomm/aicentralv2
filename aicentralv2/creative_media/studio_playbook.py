"""What the Creative Lab has taught the Studio, as data: the seed of the Studio's own creative agent.

Each rule comes from a Lab sample (TypeSafe failures counted over real generations) and is applied to the
image prompt only while ``status`` is "applied". A rule is promoted from the Lab's grouped suggestions after
review, never automatically; ``evidence`` keeps the count and the sample it came from, so a later round can
check whether the failure actually went down and retire the rule if it did not.
"""

from __future__ import annotations

import re

VERSION = "2026-10-03.1"

RULES = [
    {
        "id": "exact-copy-block",
        "failure": "text_rendering",
        "evidence": {"sample": "lab-2026-10-03", "count": 24, "of": 122},
        "status": "applied",
        "applies_to": "image_prompt",
        "note": "Texto saiu errado em todos os modelos. Listar cada string literal, uma por linha, entre aspas.",
    },
    {
        "id": "no-extra-elements",
        "failure": "extra_elements",
        "evidence": {"sample": "lab-2026-10-03", "count": 19, "of": 122},
        "status": "applied",
        "applies_to": "image_prompt",
        "note": "Elementos não pedidos (ícones, selos, telas com texto). Proibir explicitamente no fim do prompt.",
    },
    {
        "id": "brand-colors-first",
        "failure": "palette_off",
        "evidence": {"sample": "lab-2026-10-03", "count": 58, "of": 122},
        "status": "rejected",
        "applies_to": "image_prompt",
        "note": "Contagem inflada pela métrica antiga (área total da imagem). Medir de novo com a métrica v2 antes de agir.",
    },
]


_SUPPORT = re.compile(r"(?:texto de apoio|apoio|subt[ií]tulo)\s*:\s*(.+?)(?=\s*(?:t[ií]tulo|headline|chamada|bot[aã]o|cta|button)\s*:|\n|$)",
                      re.I)


def support_copy(briefing: str) -> list[str]:
    """Literal support lines written as "Texto de apoio: A · B" in the briefing."""
    match = _SUPPORT.search(briefing or "")
    if not match:
        return []
    return [" ".join(part.split()) for part in match.group(1).split(" · ") if part.strip()][:3]


def applied(rule_id: str) -> bool:
    return any(rule["id"] == rule_id and rule["status"] == "applied" for rule in RULES)


def prompt_lines(copy: list[str], *, text_free: bool) -> list[str]:
    """Lines appended to the image prompt by the applied rules."""
    lines = []
    strings = [item for item in copy if item]
    if strings and not text_free and applied("exact-copy-block"):
        lines.append("EXACT COPY (render letter by letter, accents, numbers and punctuation included; each string on its own "
                     "line; write nothing else):\n" + "\n".join(f'"{item}"' for item in strings))
    if applied("no-extra-elements"):
        lines.append("DO NOT ADD: icons, badges, seals, stickers, extra buttons, phone or app screens with readable text, "
                     "charts, captions or decorative words that the briefing did not ask for.")
    return lines


# How much copy a piece can carry, by size. The director edits the briefing's copy down to this (cutting, never
# rewriting or inventing), so a 320x50 is not asked to hold a paragraph and a 300x250 does not get three lines of support.
COPY_BUDGETS = (
    # (name, test, headline words, support lines, words per support line, CTA words)
    ("micro", lambda w, h: w * h < 8000 or min(w, h) < 40, 4, 0, 0, 0),
    ("faixa", lambda w, h: max(w, h) / min(w, h) >= 3 and min(w, h) < 130, 6, 0, 0, 3),
    ("pequeno", lambda w, h: w * h < 90_000, 6, 0, 0, 4),
    ("medio", lambda w, h: w * h < 260_000, 8, 1, 10, 4),
    ("grande", lambda w, h: True, 10, 2, 14, 5),
)


def copy_budget(width: int, height: int) -> dict:
    """The copy budget of a delivery size (unknown size: the large budget)."""
    w, h = int(width or 0), int(height or 0)
    for name, test, headline, lines, line_words, cta in COPY_BUDGETS:
        if w and h and test(w, h):
            break
    else:
        name, _, headline, lines, line_words, cta = COPY_BUDGETS[-1]
    return {"tamanho": name, "titulo_max_palavras": headline, "apoio_max_linhas": lines,
            "apoio_max_palavras_por_linha": line_words, "cta_max_palavras": cta}


def _words(text: str) -> list[str]:
    return re.findall(r"[\w%$+]+", str(text or "").casefold())


def from_briefing(text: str, briefing: str, share: float = 0.8) -> bool:
    """True when the edited copy is made of the briefing's own words (the director may cut, never invent)."""
    words, source = _words(text), set(_words(briefing))
    return bool(words) and sum(1 for word in words if word in source) / len(words) >= share


_DANGLING = {"a", "o", "as", "os", "e", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "para", "pra",
             "com", "por", "pelo", "pela", "ao", "à", "um", "uma", "todo", "toda", "todos", "todas", "seu", "sua"}


def _trim_words(text: str, limit: int) -> str:
    """First ``limit`` words, never ending on a preposition or article, never a lone verb ("Fale com a gente" stays)."""
    words = text.split()[:limit]
    while len(words) > 1 and words[-1].casefold() in _DANGLING:
        words.pop()
    if len(words) < 2 < len(text.split()):
        return text  # a button cut to one word says nothing: keep the briefing's own (short) button
    return " ".join(words)


_OFFER = re.compile(r"\d|%|R\$", re.I)


def with_offer(headline: str, support: list[str], room: int) -> tuple[str, list[str]]:
    """The offer never leaves the piece: a support line with a number/%/price that has no room goes into the headline."""
    kept, offers = [], []
    for index, line in enumerate(support):
        (kept if index < room or not _OFFER.search(line) else offers).append(line)
    kept = kept[:room]
    extra = [line for line in offers if line.casefold() not in headline.casefold()]
    return (" ".join([headline, *extra]).strip(), kept)


def _briefing_headline(briefing: str) -> str:
    from .banner_compose import extract_copy
    return extract_copy(briefing)[0]


def edited_copy(raw, briefing: str, budget: dict) -> dict | None:
    """The director's copy, kept only where it comes from the briefing; support trimmed to the budget."""
    if not isinstance(raw, dict):
        return None
    headline = " ".join(str(raw.get("headline") or "").split())[:140]
    cta = " ".join(str(raw.get("cta") or "").split())[:40]
    # Each "·"-separated item is its own line; a line over the word budget is dropped whole, never cut mid-phrase.
    lines = [" ".join(part.split()) for item in (raw.get("support") or []) for part in str(item or "").split("·") if part.strip()]
    per_line = budget.get("apoio_max_palavras_por_linha", 0)
    # An offer line (number, %, price) is exempt from the word limit: it may still go into the headline.
    support = [line[:160] for line in lines if from_briefing(line, briefing)
               and (len(line.split()) <= per_line or _OFFER.search(line))]
    cta_words = budget.get("cta_max_palavras", 0)
    original = _briefing_headline(briefing)
    keeps_offer = not re.search(r"\d|%", original) or bool(re.search(r"\d|%", headline))
    headline = headline if headline and keeps_offer and from_briefing(headline, briefing) else ""
    if headline:
        headline, support = with_offer(headline, support, budget.get("apoio_max_linhas", 0))
    copy = {
        # The offer number is what sells: an edit that dropped it is refused (the Studio falls back to the briefing).
        "headline": headline,
        "support": support[:budget.get("apoio_max_linhas", 0)],
        # A long button keeps its verb phrase: "Comprar agora no site" -> "Comprar agora".
        "cta": _trim_words(cta, cta_words) if cta and cta_words and from_briefing(cta, briefing) else "",
    }
    return copy if copy["headline"] else None


def budget_instruction(budget: dict, width: int, height: int) -> str:
    """The budget in plain numbers, for the director to count against."""
    size = f"{width}x{height}" if width and height else "este formato"
    support = ("sem texto de apoio" if not budget["apoio_max_linhas"] else
               f"no máximo {budget['apoio_max_linhas']} linha(s) de apoio com até {budget['apoio_max_palavras_por_linha']} palavras cada "
               "(cada item separado por · no pedido é uma linha; escolha as mais importantes)")
    cta = "sem botão" if not budget["cta_max_palavras"] else f"botão com até {budget['cta_max_palavras']} palavras"
    return (f"ORÇAMENTO DE TEXTO DE {size} ({budget['tamanho']}): título com no máximo {budget['titulo_max_palavras']} palavras; "
            f"{support}; {cta}. Conte as palavras de cada campo de \"copy\" antes de responder e corte o que passar.")


def fits(copy: dict | None, budget: dict) -> bool:
    return bool(copy) and len(copy["headline"].split()) <= budget["titulo_max_palavras"]


def copy_fit_messages(briefing: str, budget: dict, width: int, height: int, previous: dict | None = None) -> list[dict]:
    """A short, single-purpose request: cut the briefing's copy to the budget, nothing else."""
    system = ("Você edita o texto de uma peça publicitária para caber no tamanho dela. Use somente palavras do pedido, na "
              "mesma grafia (acentos, números, %, cupom); pode cortar palavras e trechos, nunca reescrever, traduzir, "
              "abreviar ou inventar. Ordem de corte: palavras de ligação > nome da marca (o logo já a identifica) > "
              "detalhes e prazos > benefício. Número, %, preço, cupom e o nome da oferta nunca saem do título. O resultado "
              'precisa ler bem em português. Responda só JSON: {"headline":"...","support":["..."],"cta":"..."}.')
    user = budget_instruction(budget, width, height) + "\n\nPEDIDO:\n" + briefing
    if previous:
        user += (f"\n\nSua resposta anterior tinha {len(previous.get('headline', '').split())} palavras no título "
                 f"({previous.get('headline', '')}); o máximo é {budget['titulo_max_palavras']}. Corte mais.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
