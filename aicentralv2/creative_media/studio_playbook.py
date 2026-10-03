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


_SUPPORT = re.compile(r"^\s*(?:texto de apoio|apoio|subt[ií]tulo)\s*:\s*(.+)$", re.I | re.M)


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
