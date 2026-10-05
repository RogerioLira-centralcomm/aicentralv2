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
        "id": "abstract-screens",
        "failure": "invented_data",
        "evidence": {"sample": "lab-ab-2026-10-03", "count": 1, "of": 12},
        "status": "applied",
        "applies_to": "image_prompt + reviewer",
        "note": "O modelo inventou conta e consumo na tela do celular (R$ 184,90, 289 kWh). Telas só com formas; revisor rejeita número fora do pedido.",
    },
    {
        "id": "ad-craft",
        "failure": "extra_elements / composition",
        "evidence": {"sample": "lab-2026-10-03 + ab-2026-10-03", "count": 30, "of": 134},
        "status": "applied",
        "applies_to": "image_prompt",
        "note": "Uma cena só, foco único, área do texto calma, luz comercial, cor da marca na cena: o que separou as peças aprovadas das rejeitadas.",
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


_SUPPORT = re.compile(r"(?:texto de apoio|apoio|subt[ií]tulo)\s*:\s*(.+?)(?=\s*(?:t[ií]tulo|headline|chamada|destaque|bot[aã]o|cta|button)\s*:|\n|$)",
                      re.I)
_HIGHLIGHT = re.compile(r"destaque\s*:\s*(.+?)(?=\s*(?:t[ií]tulo|headline|chamada|texto de apoio|apoio|bot[aã]o|cta|button)\s*:|\n|$)", re.I)


def highlight_copy(briefing: str) -> str:
    """The literal highlight written as "Destaque: ..." in the briefing (the phrase the piece is about)."""
    match = _HIGHLIGHT.search(briefing or "")
    return " ".join(match.group(1).split()).strip("\"“”'") if match else ""


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
        lines.append("DO NOT ADD: icons, badges, seals, stickers, extra buttons, charts, captions or decorative words that the "
                     "briefing did not ask for. Phone, laptop and app screens show only abstract interface shapes: no "
                     "readable words, numbers, prices, dates or charts on any screen.")
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
    extra = [line for line in offers if line.casefold() not in headline.casefold() and not _offer_in(line, headline)]
    return (" ".join([headline, *extra]).strip(), kept)


def _offer_in(line: str, headline: str) -> bool:
    """True when the line's offer ("+20% EXTRA") is already in the headline: the line is not glued in a second time."""
    from .banner_compose import _OFFER_SPAN
    match = _OFFER_SPAN.search(line)
    return bool(match) and len(match.group(1).strip()) > 1 and match.group(1).strip().casefold() in headline.casefold()


def protect(headline: str, support: list[str], briefing: str, room: int) -> tuple[str, list[str]]:
    """Offer and highlight never leave the piece: what the edit dropped comes back into the headline."""
    kept_text = " ".join([headline, *support]).casefold()
    lost = [line for line in support_copy(briefing) if _OFFER.search(line) and line.casefold() not in kept_text
            and not _offer_in(line, kept_text)]
    headline, support = with_offer(headline, [*lost, *support], room)
    highlight = highlight_copy(briefing)
    if highlight and highlight.casefold() not in headline.casefold():
        # The highlight is the hero, never a support line (a 300×600 has room for one support line and the director
        # put "DIA DAS MÃES" there: it came out small and the seal stayed empty).
        support = [line for line in support if line.casefold() != highlight.casefold()
                   and highlight.casefold() not in line.casefold()]
        headline = f"{headline} {highlight}".strip()
    return headline, support


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
        # Offer and highlight are untouchable in every copy field: a briefing line with a number/%/price, or the
        # "Destaque:", that the edit dropped comes back (it becomes the hero; measured: the director cut "+20% EXTRA"
        # from the support and "NA PALMA DA MÃO" from the title of a 300×250).
        headline, support = protect(headline, support, briefing, budget.get("apoio_max_linhas", 0))
    copy = {
        # The offer number is what sells: an edit that dropped it is refused (the Studio falls back to the briefing).
        "headline": headline,
        "support": support[:budget.get("apoio_max_linhas", 0)],
        # A long button keeps its verb phrase: "Comprar agora no site" -> "Comprar agora".
        "cta": _trim_words(cta, cta_words) if cta and cta_words and from_briefing(cta, briefing) else "",
    }
    return copy if copy["headline"] else None


def budget_instruction(budget: dict, width: int, height: int, typeset: bool = False) -> str:
    """The budget in plain numbers, for the director to count against."""
    size = f"{width}x{height}" if width and height else "este formato"
    support = ("sem texto de apoio" if not budget["apoio_max_linhas"] else
               f"no máximo {budget['apoio_max_linhas']} linha(s) de apoio com até {budget['apoio_max_palavras_por_linha']} palavras cada "
               "(cada item separado por · no pedido é uma linha; escolha as mais importantes)")
    cta = "sem botão" if not budget["cta_max_palavras"] else f"botão com até {budget['cta_max_palavras']} palavras"
    text = (f"ORÇAMENTO DE TEXTO DE {size} ({budget['tamanho']}): título com no máximo {budget['titulo_max_palavras']} palavras; "
            f"{support}; {cta}. Conte as palavras de cada campo de \"copy\" antes de responder e corte o que passar.")
    if typeset:
        text += (" NESTE FORMATO O STUDIO APLICA O TEXTO E O LOGO POR CÓDIGO: o campo \"prompt\" descreve só a imagem (cena, "
                 "sujeito, luz, cores e uma área calma para o texto) e não cita nenhum título, frase, botão, preço ou logo.")
    return text


def fits(copy: dict | None, budget: dict, briefing: str = "") -> bool:
    """The headline within the budget; the protected highlight does not count (it is set as the hero)."""
    if not copy:
        return False
    words = len(copy["headline"].split())
    highlight = highlight_copy(briefing)
    if highlight and highlight.casefold() in copy["headline"].casefold():
        words -= len(highlight.split())
    return words <= budget["titulo_max_palavras"]


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


def ad_craft_line(*, text_free: bool) -> str:
    """How an ad picture is built (learned from the Lab's approved vs rejected pieces), in one line."""
    if not applied("ad-craft"):
        return ""
    copy_area = ("Keep the copy area of the layout calm and empty: plain background there, no subject, hands, phones or "
                 "objects crossing it." if text_free else
                 "Give the copy a calm, high-contrast area so it reads at a glance.")
    return ("AD CRAFT: one focal subject, sharp and well lit with natural commercial light; a clean background with "
            "breathing room; the brand colors living in the wardrobe, props or background accents; nothing decorative "
            "the brief did not ask for. " + copy_area)


def scene_only(prompt: str, copy: list[str]) -> str:
    """Drop the sentences of a scene prompt that quote the copy (the model would paint them on a text-free piece)."""
    strings = [item.casefold() for item in copy if item and len(item) >= 3]
    # The offer numbers too ("+20%", "R$ 99"): a sentence that names the number makes the model paint it.
    numbers = {match.group(0) for item in copy if item for match in re.finditer(r"\d[\d.,]*\s*%?", item)}
    words = re.compile(r"\b(t[ií]tulo|headline|bot[aã]o|cta|texto|slogan|chamada|logo|cupom|oferta)\b", re.I)
    sentences = re.split(r"(?<=[.!?;])\s+", str(prompt or ""))
    kept = [item for item in sentences if not words.search(item) and not any(text in item.casefold() for text in strings)
            and not any(number.strip() in item for number in numbers)]
    return " ".join(kept) if kept else prompt


_PLACEMENT = re.compile(
    r"\b(à esquerda|a esquerda|à direita|a direita|no centro|centralizad\w*|no topo|na base|no canto|metade|terço|"
    r"lado (esquerdo|direito)|left|right|centered|centre|center|top|bottom|corner|half|third|composi[çc][ãa]o|composition|layout|zona|zone)\b",
    re.I)


def without_placement(prompt: str) -> str:
    """Drop the sentences that place things on the canvas (the layout by position decides placement)."""
    sentences = re.split(r"(?<=[.!?;])\s+", str(prompt or ""))
    kept = [item for item in sentences if not _PLACEMENT.search(item)]
    return " ".join(kept) if kept else prompt
