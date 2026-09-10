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
