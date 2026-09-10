"""Contrato de família IAB e geometria nativa dos formatos."""

from __future__ import annotations

import math
import re

from .creative_modeling_generation import (
    SUPPORTED_IMAGE_ASPECT_RATIOS,
    normalize_image_aspect_ratio,
)


COMPOSE_FAMILIES = frozenset({
    "rectangle", "wide_banner", "half_page", "slate_16x9",
})
SOCIAL_PAINT_FAMILIES = frozenset({
    "square_1x1", "story_9x16", "landscape_social",
})
SOCIAL_FORMAT_SLUGS = frozenset({
    "instagram-feed", "instagram-story", "tiktok-vertical",
    "facebook-feed", "linkedin-share",
})
PORTAL_UNIT_SLUGS = frozenset({
    "hotspot", "cartas", "puxe-descubra", "arraste-descubra", "quiz",
    "native-infeed",
})
FORMAT_IAB_FAMILY = {
    "iab-medium-rectangle": {
        "family": "rectangle",
        "size": (300, 250),
        "iab_cousin": "medium_rectangle",
    },
    "iab-leaderboard": {
        "family": "wide_banner",
        "size": (728, 90),
        "iab_cousin": "leaderboard",
    },
    "iab-mobile-banner": {
        "family": "wide_banner",
        "size": (320, 50),
        "iab_cousin": "mobile_banner",
    },
    "iab-half-page": {
        "family": "half_page",
        "size": (300, 600),
        "iab_cousin": "half_page",
    },
    "netflix-pause-banner": {
        "family": "wide_banner",
        "size": (1920, 300),
        "iab_cousin": "billboard",
    },
    "hbomax-pause-ad": {
        "family": "slate_16x9",
        "size": (1920, 1080),
        "iab_cousin": "video_companion",
    },
    "disney-pause-plus": {
        "family": "slate_16x9",
        "size": (1920, 1080),
        "iab_cousin": "video_companion",
    },
    "disney-branded-slate": {
        "family": "slate_16x9",
        "size": (1920, 1080),
        "iab_cousin": "video_companion",
    },
    "netflix-logo-bumper": {
        "family": "sequence_16x9",
        "size": (1920, 1080),
        "iab_cousin": "digital_video",
    },
    "netflix-anuncio-simulado": {
        "family": "sequence_16x9",
        "size": (1920, 1080),
        "iab_cousin": "digital_video",
    },
    "hbomax-interactive-midroll": {
        "family": "sequence_16x9",
        "size": (1920, 1080),
        "iab_cousin": "digital_video",
    },
    "video-outstream": {
        "family": "sequence_16x9",
        "size": (1920, 1080),
        "iab_cousin": "digital_video",
    },
    "instagram-feed": {
        "family": "square_1x1",
        "size": (1080, 1080),
        "iab_cousin": "social_feed",
    },
    "facebook-feed": {
        "family": "square_1x1",
        "size": (1080, 1080),
        "iab_cousin": "social_feed",
    },
    "instagram-story": {
        "family": "story_9x16",
        "size": (1080, 1920),
        "iab_cousin": "social_story",
    },
    "tiktok-vertical": {
        "family": "story_9x16",
        "size": (1080, 1920),
        "iab_cousin": "social_story",
    },
    "linkedin-share": {
        "family": "landscape_social",
        "size": (1200, 627),
        "iab_cousin": "social_landscape",
    },
}

FAMILY_BUDGET = {
    "wide_banner": {
        "max_marks": 1,
        "max_headlines": 1,
        "max_ctas": 1,
        "max_icons": 0,
        "max_copy_blocks": 1,
        "allow_leader_lines": False,
        "summary": "1 marca, 1 linha, 1 CTA; zero ícones ou linhas líderes",
    },
    "rectangle": {
        "max_marks": 1,
        "max_headlines": 1,
        "max_ctas": 1,
        "max_icons": 0,
        "max_copy_blocks": 2,
        "allow_leader_lines": False,
        "summary": "1 headline, 1 CTA, um sujeito; sem barra de ícones",
    },
    "half_page": {
        "max_marks": 1,
        "max_headlines": 1,
        "max_ctas": 1,
        "max_icons": 0,
        "max_copy_blocks": 3,
        "allow_leader_lines": False,
        "summary": "até 3 blocos de texto e 1 CTA",
    },
    "slate_16x9": {
        "max_marks": 1,
        "max_headlines": 1,
        "max_ctas": 1,
        "max_icons": 0,
        "max_copy_blocks": 1,
        "allow_leader_lines": False,
        "summary": "1 marca, copy curta, 1 CTA; sem barra de ícones",
    },
    "sequence_16x9": {
        "max_marks": 1,
        "max_headlines": 1,
        "max_ctas": 1,
        "max_icons": 0,
        "max_copy_blocks": 1,
        "allow_leader_lines": False,
        "summary": "continuidade de quadro; compositor só no endcard",
    },
    "portal_unit": {
        "max_marks": 1,
        "max_headlines": 1,
        "max_ctas": 1,
        "max_icons": 3,
        "max_copy_blocks": 2,
        "allow_leader_lines": True,
        "summary": "respeitar a mecânica; no máximo 3 marcadores ligados",
    },
    "square_1x1": {
        "max_marks": 1,
        "max_headlines": 1,
        "max_ctas": 1,
        "max_icons": 0,
        "max_copy_blocks": 2,
        "allow_leader_lines": False,
        "summary": "peça social completa: 1 headline, 1 CTA, marca intacta",
    },
    "story_9x16": {
        "max_marks": 1,
        "max_headlines": 1,
        "max_ctas": 1,
        "max_icons": 0,
        "max_copy_blocks": 2,
        "allow_leader_lines": False,
        "summary": "story vertical: copy curta, 1 CTA, safe area superior/inferior",
    },
    "landscape_social": {
        "max_marks": 1,
        "max_headlines": 1,
        "max_ctas": 1,
        "max_icons": 0,
        "max_copy_blocks": 2,
        "allow_leader_lines": False,
        "summary": "paisagem social: 1 headline, 1 CTA, sem chrome de feed",
    },
}

HYGIENE_INSTRUCTIONS = {
    "chrome": (
        "Remove all icon rows, dangling leader lines, extra pills, player "
        "chrome and decorative UI. Keep at most one headline, one CTA and "
        "one brand mark. Do not invent new objects."
    ),
    "geometry": (
        "Recenter the subject inside the target advertising rectangle. "
        "Preserve brand identity and CTA. Do not add chrome, icons or "
        "new copy."
    ),
}


def parse_default_size(value):
    match = re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", str(value or ""))
    if not match:
        return None
    width, height = int(match.group(1)), int(match.group(2))
    if width < 1 or height < 1:
        return None
    return width, height


def format_family_spec(slug, default_size=None):
    slug = str(slug or "").strip()
    mapped = dict(FORMAT_IAB_FAMILY.get(slug) or {})
    if slug in PORTAL_UNIT_SLUGS:
        mapped.setdefault("family", "portal_unit")
    size = parse_default_size(default_size) or mapped.get("size")
    family = mapped.get("family") or _family_from_size(size)
    spec = {
        "slug": slug,
        "family": family,
        "size": size,
        "iab_cousin": mapped.get("iab_cousin"),
        "target_size": f"{size[0]}x{size[1]}" if size else None,
        "budget": _budget_for(family, None),
        "composable": family in COMPOSE_FAMILIES,
    }
    return spec


def resolve_format_geometry(context, behavior_spec=None):
    context = context if isinstance(context, dict) else {}
    behavior = behavior_spec if isinstance(behavior_spec, dict) else (
        context.get("behavior_spec") or {}
    )
    spec = format_family_spec(
        context.get("format_slug") or context.get("slug"),
        context.get("default_size"),
    )
    override = behavior.get("element_budget")
    if isinstance(override, dict) and override:
        spec["budget"] = _budget_for(spec["family"], override)
    return spec


def default_render_mode(family):
    if family in {
        "rectangle", "wide_banner", "half_page", "slate_16x9",
    } | SOCIAL_PAINT_FAMILIES:
        return "native"
    return "mockup"


def should_compose(family, render_mode, position=1, scene_count=1):
    if render_mode != "native":
        return False
    if family in {"rectangle", "wide_banner", "half_page", "slate_16x9"}:
        return True
    if family == "sequence_16x9":
        return int(position or 1) >= int(scene_count or 1)
    return False


def canvas_mismatch(target_size, provider_aspect_ratio):
    if not target_size:
        return False
    width, height = target_size
    requested = f"{width}:{height}"
    provider = normalize_image_aspect_ratio(provider_aspect_ratio or requested)
    if provider not in SUPPORTED_IMAGE_ASPECT_RATIOS:
        return True
    actual = width / height
    pw, ph = (float(part) for part in provider.split(":", 1))
    return abs(math.log(actual / (pw / ph))) > 0.12


def compose_layout(family, size):
    width, height = size
    if family == "wide_banner":
        return {
            "visual": (0, 0, int(width * 0.28), height),
            "headline": (int(width * 0.30), int(height * 0.18), int(width * 0.46), int(height * 0.64)),
            "cta": (int(width * 0.80), int(height * 0.22), int(width * 0.18), int(height * 0.56)),
            "logo": (int(width * 0.02), int(height * 0.18), int(height * 0.64), int(height * 0.64)),
        }
    if family == "rectangle":
        return {
            "visual": (0, 0, width, int(height * 0.58)),
            "headline": (12, int(height * 0.60), width - 24, int(height * 0.22)),
            "cta": (width - 118, height - 40, 106, 28),
            "logo": (10, 10, 36, 36),
        }
    if family == "half_page":
        return {
            "visual": (0, 0, width, int(height * 0.48)),
            "headline": (16, int(height * 0.52), width - 32, int(height * 0.22)),
            "cta": (16, height - 56, width - 32, 40),
            "logo": (16, 16, 40, 40),
        }
    if family == "story_9x16":
        return {
            "visual": (0, int(height * 0.10), width, int(height * 0.58)),
            "headline": (int(width * 0.08), int(height * 0.70), int(width * 0.84), int(height * 0.12)),
            "cta": (int(width * 0.14), int(height * 0.86), int(width * 0.72), int(height * 0.06)),
            "logo": (int(width * 0.08), int(height * 0.04), 72, 72),
        }
    if family == "square_1x1":
        return {
            "visual": (0, 0, width, int(height * 0.62)),
            "headline": (int(width * 0.07), int(height * 0.64), int(width * 0.86), int(height * 0.16)),
            "cta": (int(width * 0.22), int(height * 0.84), int(width * 0.56), int(height * 0.10)),
            "logo": (int(width * 0.05), int(height * 0.05), 64, 64),
        }
    if family == "landscape_social":
        return {
            "visual": (0, 0, int(width * 0.52), height),
            "headline": (int(width * 0.56), int(height * 0.22), int(width * 0.38), int(height * 0.28)),
            "cta": (int(width * 0.56), int(height * 0.68), int(width * 0.28), int(height * 0.16)),
            "logo": (int(width * 0.56), int(height * 0.08), 64, 64),
        }
    if family == "portal_unit" and height > width * 1.15:
        return {
            "visual": (0, 0, width, int(height * 0.52)),
            "headline": (16, int(height * 0.56), width - 32, int(height * 0.20)),
            "cta": (16, height - 56, width - 32, 40),
            "logo": (16, 16, 40, 40),
        }
    if family == "portal_unit" and width > height * 1.15:
        return {
            "visual": (0, 0, int(width * 0.42), height),
            "headline": (int(width * 0.46), int(height * 0.22), int(width * 0.32), int(height * 0.56)),
            "cta": (int(width * 0.80), int(height * 0.28), int(width * 0.16), int(height * 0.44)),
            "logo": (int(width * 0.02), int(height * 0.16), int(height * 0.60), int(height * 0.60)),
        }
    return {
        "visual": (0, 0, width, height),
        "headline": (int(width * 0.08), int(height * 0.72), int(width * 0.54), int(height * 0.12)),
        "cta": (int(width * 0.70), int(height * 0.78), int(width * 0.22), int(height * 0.10)),
        "logo": (int(width * 0.08), int(height * 0.08), 72, 72),
    }


def hygiene_instruction(intent, family=None):
    key = str(intent or "").strip().lower()
    text = HYGIENE_INSTRUCTIONS.get(key)
    if not text:
        return ""
    budget = FAMILY_BUDGET.get(family) or {}
    if budget.get("summary"):
        return f"{text} Element budget: {budget['summary']}."
    return text


def _family_from_size(size):
    if not size:
        return "portal_unit"
    width, height = size
    ratio = width / height
    if height <= 90 or ratio >= 4:
        return "wide_banner"
    if ratio <= 0.62 and height >= 1000:
        return "story_9x16"
    if ratio <= 0.6:
        return "half_page"
    if 0.95 <= ratio <= 1.08:
        return "square_1x1"
    if 0.9 <= ratio <= 1.4:
        return "rectangle"
    if 1.85 <= ratio <= 2.05:
        return "landscape_social"
    if 1.6 <= ratio <= 1.9:
        return "slate_16x9"
    return "portal_unit"


def _budget_for(family, override):
    base = dict(FAMILY_BUDGET.get(family) or FAMILY_BUDGET["portal_unit"])
    if isinstance(override, dict):
        for key in (
            "max_marks", "max_headlines", "max_ctas", "max_icons",
            "max_copy_blocks", "allow_leader_lines", "summary",
        ):
            if key in override:
                base[key] = override[key]
    return base


ELEMENT_LABELS = (
    ("title", "Título"),
    ("hook", "Gancho"),
    ("text", "Texto"),
    ("images", "Imagens"),
    ("background", "Fundo"),
    ("logo", "Logo"),
    ("cta", "CTA"),
)

SLOT_LABELS = {
    "visual": "Imagens",
    "headline": "Título",
    "cta": "CTA",
    "logo": "Logo",
}

ORIENTATION_LABELS = {
    "horizontal": "Horizontal",
    "vertical": "Vertical",
    "square": "Quadrado",
}

READING_LABELS = {
    "horizontal": "esquerda para a direita",
    "vertical": "cima para baixo",
    "square": "do centro para as bordas",
}

_ELEMENT_TO_SLOT = {
    "images": "visual",
    "background": "visual",
    "title": "headline",
    "hook": "headline",
    "text": "headline",
    "logo": "logo",
    "cta": "cta",
}

_FAMILY_LAYOUT = {
    "wide_banner": (
        "Faixa rasa. Visual à esquerda, título no centro, CTA à direita. Nada empilha.",
        "Shallow horizontal strip. Visual left, headline center, CTA right. Do not stack.",
    ),
    "rectangle": (
        "Bloco. Visual na metade de cima, título abaixo, CTA no canto inferior direito.",
        "Block. Visual in the top half, headline below, CTA bottom-right.",
    ),
    "half_page": (
        "Coluna. Visual em cima, título no meio, texto e CTA ancorados embaixo.",
        "Column. Visual on top, headline mid, copy and CTA anchored at the bottom.",
    ),
    "slate_16x9": (
        "Paisagem 16:9. Visual preenche. Título na terça inferior esquerda, CTA à direita.",
        "16:9 landscape. Visual fills. Headline lower-left third, CTA on the right.",
    ),
    "sequence_16x9": (
        "Filme 16:9. Cada quadro preenche o retângulo. Copy e CTA só quando o beat pedir.",
        "16:9 film frame. Each still fills the rectangle. Copy and CTA only when the beat allows.",
    ),
    "story_9x16": (
        "Retrato 9:16. Visual no centro útil. Copy abaixo. CTA acima da safe area inferior.",
        "9:16 portrait. Visual in the usable center. Copy below. CTA above the lower safe area.",
    ),
    "square_1x1": (
        "Quadrado. Visual no bloco superior, título na faixa de baixo, CTA no rodapé.",
        "Square. Visual in the upper block, headline in the lower band, CTA in the footer.",
    ),
    "landscape_social": (
        "Paisagem social. Visual à esquerda, título e CTA empilhados à direita.",
        "Social landscape. Visual left, headline and CTA stacked on the right.",
    ),
    "portal_unit": (
        "Unidade do portal. Os elementos sentam nas zonas do retângulo deste formato.",
        "Portal unit. Place elements in this rectangle's modeled zones.",
    ),
}

_STATIC_FAMILY_BEATS = {
    "wide_banner": (
        "composicao_final",
        "Faixa horizontal",
        "Uma linha só: visual à esquerda, título no centro útil, CTA à direita. Não empilhar.",
        ["background", "images", "title", "text", "logo", "cta"],
    ),
    "half_page": (
        "composicao_final",
        "Coluna vertical",
        "Uma coluna: visual no terço superior, título no meio, texto e CTA ancorados embaixo.",
        ["background", "images", "title", "text", "logo", "cta"],
    ),
    "rectangle": (
        "composicao_final",
        "Retângulo",
        "Visual na metade de cima, título logo abaixo, CTA no canto inferior direito, logo no canto.",
        ["background", "images", "title", "text", "logo", "cta"],
    ),
    "story_9x16": (
        "composicao_final",
        "Story vertical",
        "Retrato 9:16. Visual no centro útil. Copy abaixo. CTA acima da safe area. Logo fora do recorte de UI.",
        ["background", "images", "title", "text", "logo", "cta"],
    ),
    "square_1x1": (
        "composicao_final",
        "Feed quadrado",
        "Quadrado. Visual no bloco de cima, título na faixa de baixo, CTA centrado no rodapé.",
        ["background", "images", "title", "text", "logo", "cta"],
    ),
    "landscape_social": (
        "composicao_final",
        "Paisagem social",
        "Horizontal social: visual à esquerda, título e CTA empilhados à direita.",
        ["background", "images", "title", "text", "logo", "cta"],
    ),
    "slate_16x9": (
        "composicao_final",
        "Slate 16:9",
        "Quadro paisagem. Visual preenche. Título na terça inferior esquerda, CTA à direita.",
        ["background", "images", "title", "text", "logo", "cta"],
    ),
}

_ORIENTATION_BEATS = {
    "horizontal": {
        "hotspot": {
            "gancho": "Cena-base na faixa horizontal. O mundo existe; os marcadores ainda não ensinam.",
            "contexto": "Um marcador abre sobre a zona de visual, lido da esquerda para a direita.",
            "beneficio": "Outro ponto da mesma faixa torna o valor visível. Continua o mesmo anúncio.",
            "fechamento": "A faixa resolve. Marca e CTA só nas zonas da modelagem, se o formato tiver.",
        },
        "flip": {
            "gancho": "A face da frente do card, lida da esquerda para a direita.",
            "contexto": "A virada acontece no eixo horizontal. Mesmo card, outro instante.",
            "beneficio": "O verso traz a informação no mesmo retângulo paisagem.",
            "fechamento": "O card assenta na faixa. CTA só se o formato tiver.",
        },
        "reveal": {
            "gancho": "A camada da frente cobre a faixa da esquerda para a direita.",
            "contexto": "O gesto puxa na horizontal e começa a descobrir a segunda camada.",
            "beneficio": "O produto ou a oferta aparece sob a camada, ainda no mesmo banner.",
            "fechamento": "Estado final da faixa. CTA só se o formato tiver.",
        },
        "compare": {
            "gancho": "Estado A no lado esquerdo do retângulo horizontal.",
            "contexto": "O divisor é uma linha vertical no centro. Arraste na horizontal.",
            "beneficio": "Estado B no lado direito, mesmo enquadramento.",
            "fechamento": "A unidade inteira. CTA só se o formato tiver.",
        },
        "quiz": {
            "gancho": "A pergunta atravessa a faixa horizontal, sem resposta ainda.",
            "contexto": "As alternativas alinhadas na horizontal da mesma unidade.",
            "beneficio": "O feedback no mesmo retângulo paisagem.",
            "fechamento": "Marca no lugar. CTA só se o formato tiver.",
        },
        "carousel": {
            "gancho": "Primeiro quadro da faixa horizontal. Leitura da esquerda para a direita.",
            "contexto": "O produto entra no quadro seguinte da mesma faixa. Não é variação.",
            "beneficio": "O valor fica visível neste instante da sequência horizontal.",
            "fechamento": "Último quadro da faixa. CTA só se o formato tiver.",
        },
        "video": {
            "gancho": "Hook em paisagem. Atenção sem áudio nos primeiros segundos.",
            "contexto": "A história avança no mesmo filme 16:9.",
            "beneficio": "O valor fica claro antes do endcard, ainda em paisagem.",
            "fechamento": "Endcard no quadro horizontal. CTA só se o formato tiver.",
        },
    },
    "vertical": {
        "hotspot": {
            "gancho": "Cena-base na coluna vertical. Os marcadores ainda não ensinam.",
            "contexto": "Um marcador abre sobre o visual de cima. Leitura de cima para baixo.",
            "beneficio": "Outro ponto mais abaixo da mesma coluna torna o valor visível.",
            "fechamento": "A coluna resolve. CTA ancorado embaixo, só se o formato tiver.",
        },
        "flip": {
            "gancho": "A face da frente do card vertical.",
            "contexto": "A virada sobe ou desce no mesmo objeto alto.",
            "beneficio": "O verso traz a informação na coluna.",
            "fechamento": "O card assenta. CTA só se o formato tiver.",
        },
        "reveal": {
            "gancho": "A camada da frente cobre o retângulo de cima para baixo.",
            "contexto": "O gesto puxa na vertical e começa a descobrir o que está embaixo.",
            "beneficio": "O produto ou a oferta aparece sob a camada, na mesma coluna.",
            "fechamento": "Estado final da coluna. CTA só se o formato tiver.",
        },
        "compare": {
            "gancho": "Estado A na metade de cima do retângulo vertical.",
            "contexto": "O divisor é uma linha horizontal. Arraste de cima para baixo.",
            "beneficio": "Estado B na metade de baixo, mesmo enquadramento.",
            "fechamento": "A unidade inteira. CTA só se o formato tiver.",
        },
        "quiz": {
            "gancho": "A pergunta no topo da coluna, sem resposta ainda.",
            "contexto": "As alternativas empilhadas na mesma unidade vertical.",
            "beneficio": "O feedback abaixo das opções. Continua o mesmo quiz.",
            "fechamento": "Marca e CTA no rodapé, só se o formato tiver.",
        },
        "carousel": {
            "gancho": "Primeiro quadro do retrato. Leitura de cima para baixo.",
            "contexto": "O produto entra no quadro seguinte da mesma coluna. Não é variação.",
            "beneficio": "O valor fica visível neste instante da sequência vertical.",
            "fechamento": "Último quadro do retrato. CTA acima da safe area, só se o formato tiver.",
        },
        "video": {
            "gancho": "Hook vertical. Atenção sem áudio, produto no centro útil.",
            "contexto": "A história desce no mesmo filme 9:16.",
            "beneficio": "O valor fica claro antes do endcard, ainda em retrato.",
            "fechamento": "Endcard vertical. CTA acima da safe area, só se o formato tiver.",
        },
    },
    "square": {
        "hotspot": {
            "gancho": "Cena-base no quadrado. Os marcadores ainda não ensinam.",
            "contexto": "Um marcador abre sobre o visual do bloco superior.",
            "beneficio": "Outro ponto do mesmo quadrado torna o valor visível.",
            "fechamento": "O quadrado resolve. CTA no rodapé, só se o formato tiver.",
        },
        "flip": {
            "gancho": "A face da frente do card quadrado.",
            "contexto": "A virada no mesmo objeto 1:1.",
            "beneficio": "O verso traz a informação no quadrado.",
            "fechamento": "O card assenta. CTA só se o formato tiver.",
        },
        "reveal": {
            "gancho": "A camada da frente cobre o quadrado.",
            "contexto": "O gesto descobre a segunda camada no mesmo 1:1.",
            "beneficio": "O produto ou a oferta aparece sob a camada.",
            "fechamento": "Estado final do quadrado. CTA só se o formato tiver.",
        },
        "compare": {
            "gancho": "Estado A no quadrado, recorte idêntico.",
            "contexto": "O divisor atravessa o 1:1. Os dois estados do mesmo anúncio.",
            "beneficio": "Estado B, mesmo enquadramento quadrado.",
            "fechamento": "A unidade inteira. CTA só se o formato tiver.",
        },
        "quiz": {
            "gancho": "A pergunta no quadrado, sem resposta ainda.",
            "contexto": "As alternativas no mesmo 1:1.",
            "beneficio": "O feedback. Continua o mesmo quiz.",
            "fechamento": "Marca no lugar. CTA só se o formato tiver.",
        },
        "carousel": {
            "gancho": "Primeiro quadro do feed quadrado.",
            "contexto": "O produto entra no quadro seguinte do mesmo 1:1. Não é variação.",
            "beneficio": "O valor fica visível neste instante da sequência quadrada.",
            "fechamento": "Último quadro. CTA no rodapé, só se o formato tiver.",
        },
        "video": {
            "gancho": "Hook no quadrado. Atenção sem áudio.",
            "contexto": "A história avança no mesmo 1:1.",
            "beneficio": "O valor fica claro antes do endcard.",
            "fechamento": "Endcard quadrado. CTA só se o formato tiver.",
        },
    },
}

_BEHAVIOR_ALIASES = {
    "static_display": "static",
    "interactive": "carousel",
    "click_expand": "reveal",
    "image_carousel": "carousel",
    "interactive_on_pause": "carousel",
    "puxe-descubra": "reveal",
    "arraste-descubra": "compare",
    "cartas": "flip",
    "video-outstream": "video",
}

_BEATS = {
    "static": [(
        "composicao_final",
        "Peça única",
        "Uma composição que conta o anúncio inteiro neste retângulo.",
        ["background", "images", "title", "text", "logo", "cta"],
    )],
    "hotspot": [
        ("gancho", "Gancho", "Cena-base do anúncio. O mundo existe; os marcadores ainda não ensinam.", ["background", "images", "hook", "logo"]),
        ("contexto", "Hotspot", "Um marcador abre sobre a mesma unidade e aponta o produto. Não é variação da cena 1.", ["images", "title", "text"]),
        ("beneficio", "Revelação", "Outro ponto da mesma peça torna o valor visível.", ["images", "text"]),
        ("fechamento", "Fechamento", "A unidade completa, marca no lugar. CTA só se o formato tiver.", ["images", "logo", "cta"]),
    ],
    "flip": [
        ("gancho", "Frente", "O card de frente: a primeira face do mesmo objeto.", ["background", "images", "hook", "logo"]),
        ("contexto", "Virada", "A virada em progresso. Mesmo card, outro instante.", ["images"]),
        ("beneficio", "Verso", "O verso traz a informação. Continua o mesmo anúncio.", ["images", "title", "text"]),
        ("fechamento", "Card resolvido", "O card assenta. CTA só se o formato tiver.", ["images", "logo", "cta"]),
    ],
    "reveal": [
        ("gancho", "Coberto", "A camada da frente ainda cobre o anúncio.", ["background", "images", "hook"]),
        ("contexto", "Puxar", "O gesto acontece: a segunda camada começa a aparecer.", ["images"]),
        ("beneficio", "Revelado", "O produto ou a oferta fica visível sob a camada.", ["images", "title", "text"]),
        ("fechamento", "Aberto", "Estado final da mesma unidade. CTA só se o formato tiver.", ["images", "logo", "cta"]),
    ],
    "compare": [
        ("gancho", "Estado A", "Um lado da comparação, recorte idêntico.", ["background", "images", "title"]),
        ("contexto", "Meio", "O divisor no centro. Os dois estados do mesmo anúncio.", ["images"]),
        ("beneficio", "Estado B", "O outro lado, mesmo enquadramento.", ["images", "text"]),
        ("fechamento", "Decisão", "A unidade inteira. CTA só se o formato tiver.", ["images", "logo", "cta"]),
    ],
    "quiz": [
        ("gancho", "Pergunta", "A pergunta do anúncio, sem resposta ainda.", ["background", "images", "title", "hook"]),
        ("contexto", "Opções", "As alternativas tapáveis da mesma unidade.", ["text", "images"]),
        ("beneficio", "Resposta", "O feedback. Continua o mesmo quiz.", ["text", "images"]),
        ("fechamento", "Fechamento", "Marca no lugar. CTA só se o formato tiver.", ["logo", "cta"]),
    ],
    "carousel": [
        ("gancho", "Gancho", "Primeiro quadro do mesmo anúncio animado.", ["background", "images", "hook"]),
        ("contexto", "Contexto", "O produto entra. Quadro seguinte, não variação.", ["images", "title", "text"]),
        ("beneficio", "Benefício", "O valor fica visível neste instante da sequência.", ["images", "text"]),
        ("fechamento", "Fechamento", "Último quadro. CTA só se o formato tiver.", ["images", "logo", "cta"]),
    ],
    "video": [
        ("gancho", "Hook", "Os primeiros segundos: atenção sem depender de áudio.", ["images", "hook", "background"]),
        ("contexto", "Corpo", "A história avança no mesmo filme.", ["images", "title", "text"]),
        ("beneficio", "Pico", "O valor fica claro antes do endcard.", ["images", "text"]),
        ("fechamento", "Endcard", "Quadro final. CTA só se o formato tiver.", ["images", "logo", "cta"]),
    ],
}


def canvas_orientation(width, height):
    if not width or not height:
        return None
    ratio = width / height
    if ratio >= 1.15:
        return "horizontal"
    if ratio <= 0.87:
        return "vertical"
    return "square"


def _layout_copy(family):
    pair = _FAMILY_LAYOUT.get(family) or _FAMILY_LAYOUT["portal_unit"]
    return {"summary": pair[0], "prompt": pair[1]}


def _layout_slots(family, width, height):
    if not width or not height:
        return []
    raw = compose_layout(family, (width, height))
    slots = []
    for key, box in raw.items():
        x, y, slot_w, slot_h = box
        slots.append({
            "key": key,
            "label": SLOT_LABELS.get(key, key),
            "x": round(100 * x / width, 1),
            "y": round(100 * y / height, 1),
            "width": round(100 * slot_w / width, 1),
            "height": round(100 * slot_h / height, 1),
            "px": [int(x), int(y), int(slot_w), int(slot_h)],
        })
    return slots


def _slots_for_elements(slots, on_screen):
    wanted = {
        _ELEMENT_TO_SLOT[key]
        for key in on_screen
        if key in _ELEMENT_TO_SLOT
    }
    return [item for item in slots if item["key"] in wanted]


def _specialize_beat(role, label, job, on_screen, behavior, family, orientation):
    if behavior == "static" and family in _STATIC_FAMILY_BEATS:
        return _STATIC_FAMILY_BEATS[family]
    overlay = (_ORIENTATION_BEATS.get(orientation) or {}).get(behavior) or {}
    specialized = overlay.get(role) or job
    layout = _layout_copy(family)["summary"]
    if layout and layout not in specialized:
        specialized = f"{specialized} {layout}"
    return role, label, specialized, on_screen


def scene_count_for_format(format_row):
    slug = str((format_row or {}).get("slug") or "")
    if slug in SOCIAL_FORMAT_SLUGS:
        return 1
    behavior = (format_row or {}).get("behavior_spec") or {}
    return (
        1
        if behavior.get("type") == "static"
        and (format_row or {}).get("mechanic") == "static_display"
        else 4
    )


def _behavior_key(format_row):
    row = format_row if isinstance(format_row, dict) else {}
    behavior = row.get("behavior_spec") if isinstance(row.get("behavior_spec"), dict) else {}
    raw = str(
        behavior.get("type") or row.get("mechanic") or row.get("slug") or ""
    ).lower()
    mapped = _BEHAVIOR_ALIASES.get(raw, raw)
    if mapped in _BEATS:
        return mapped
    return "static" if mapped == "static" else "carousel"


def _layer_blob(format_row):
    row = format_row if isinstance(format_row, dict) else {}
    parts = [
        str(row.get("slug") or ""),
        str(row.get("mechanic") or ""),
        str(row.get("foreground_guidance") or ""),
        str(row.get("background_guidance") or ""),
    ]
    behavior = row.get("behavior_spec") if isinstance(row.get("behavior_spec"), dict) else {}
    parts.append(str(behavior.get("type") or ""))
    for item in row.get("layers") or []:
        if not isinstance(item, dict):
            continue
        parts.append(str(item.get("role") or ""))
        parts.append(str(item.get("description") or item.get("description_template") or ""))
    return " ".join(parts).lower()


def _element_flags(format_row, geometry, scene_count, behavior):
    blob = _layer_blob(format_row)
    budget = (geometry or {}).get("budget") or {}
    family = (geometry or {}).get("family") or ""
    has_cta = (
        "cta" in blob
        or "call to action" in blob
        or "endcard" in blob
        or (
            behavior == "static"
            and str((format_row or {}).get("mechanic") or "") == "static_display"
        )
        or family in SOCIAL_PAINT_FAMILIES
    )
    return {
        "title": (budget.get("max_headlines") or 0) > 0
            or any(token in blob for token in ("headline", "title", "message", "question")),
        "hook": scene_count > 1 or "hook" in blob or behavior == "video",
        "text": (budget.get("max_copy_blocks") or 0) > 0
            or any(token in blob for token in ("label", "copy", "text", "question")),
        "images": True,
        "background": True,
        "logo": (budget.get("max_marks") or 0) > 0
            or any(token in blob for token in ("logo", "sponsor", "marca")),
        "cta": has_cta,
    }


def format_direction(format_row):
    row = format_row if isinstance(format_row, dict) else {}
    if not any(
        row.get(key)
        for key in ("slug", "mechanic", "behavior_spec", "default_size", "layers", "format_slug")
    ):
        count = scene_count_for_format(row)
        return {
            "width": None,
            "height": None,
            "target_size": None,
            "size_label": None,
            "family": None,
            "orientation": None,
            "orientation_label": None,
            "reading": None,
            "behavior": None,
            "scene_count": count,
            "animated": count > 1,
            "elements": [],
            "layout": {"summary": None, "prompt": None, "slots": []},
            "beats": [],
        }
    if row.get("format_slug") and not row.get("slug"):
        row = {**row, "slug": row.get("format_slug")}
    geometry = resolve_format_geometry(row)
    size = geometry.get("size") or ()
    width = int(size[0]) if len(size) == 2 else None
    height = int(size[1]) if len(size) == 2 else None
    target = geometry.get("target_size") or row.get("default_size") or ""
    if not width or not height:
        match = re.search(r"(\d+)\s*[xX×]\s*(\d+)", str(target))
        if match:
            width, height = int(match.group(1)), int(match.group(2))
            target = f"{width}x{height}"
    scene_count = scene_count_for_format(row)
    behavior = _behavior_key(row)
    family = geometry.get("family") or _family_from_size(
        (width, height) if width and height else None
    )
    orientation = canvas_orientation(width, height)
    flags = _element_flags(row, geometry, scene_count, behavior)
    slots = _layout_slots(family, width, height)
    layout = {
        **_layout_copy(family),
        "slots": slots,
        "safe_area": row.get("safe_area") if isinstance(row.get("safe_area"), dict) else None,
    }
    templates = _BEATS["static"] if scene_count == 1 else _BEATS.get(behavior, _BEATS["carousel"])
    beats = []
    for position, template in enumerate(templates[:scene_count], start=1):
        role, label, job, on_screen = _specialize_beat(
            *template, behavior, family, orientation
        )
        visible = [
            key for key in on_screen
            if flags.get(key) and (key != "cta" or position == scene_count)
        ]
        beats.append({
            "position": position,
            "role": role,
            "label": label,
            "job": job,
            "on_screen": visible,
            "slots": _slots_for_elements(slots, visible),
        })
    return {
        "width": width,
        "height": height,
        "target_size": target or None,
        "size_label": f"{width} × {height} px" if width and height else None,
        "family": family,
        "orientation": orientation,
        "orientation_label": ORIENTATION_LABELS.get(orientation),
        "reading": READING_LABELS.get(orientation),
        "behavior": behavior,
        "scene_count": scene_count,
        "animated": scene_count > 1 or behavior == "video",
        "elements": [
            {"key": key, "label": label, "present": bool(flags.get(key))}
            for key, label in ELEMENT_LABELS
        ],
        "layout": layout,
        "beats": beats,
    }


def format_beat(format_row, position):
    direction = format_direction(format_row)
    for beat in direction.get("beats") or []:
        if int(beat.get("position") or 0) == int(position or 1):
            return beat
    return None
