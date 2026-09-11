#!/usr/bin/env python
"""Seed idempotente do catálogo inicial de Modelagem de Criativos."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Json


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

LAYER_DESCRIPTIONS = {
    "hotspot": {
        "base_scene": "wide establishing shot relevant to the client sector, with 3 to 4 subtle circular markers overlaid on key visual points of interest",
        "reveal_labels": "each marker connects via a thin leader line to a small pill-shaped label revealing additional information on hover/tap",
    },
    "cartas": {
        "foreground_card": "one card mid-flip, angled in 3D perspective to suggest the flip gesture, showing the campaign hero image or message",
        "background_cards": "edges of 2 more cards peeking from behind, hinting at unrevealed content",
    },
    "puxe-descubra": {
        "curtain_layer": "soft fabric-like curtain in the brand primary tone, being pulled upward, occupying top 35 percent of frame, realistic fold, wrinkles, and shadow at the edge",
        "revealed_layer": "the campaign scene revealed underneath, occupying bottom 65 percent of frame, with clear depth separation from the curtain above",
    },
    "arraste-descubra": {
        "split_comparison": "vertical split-screen with a draggable divider handle in the center (small circular icon with left-right arrows), comparing two versions or options related to the campaign message, each side labeled with its specification",
    },
    "quiz": {
        "question_card": "centered question card over a softly blurred contextual background relevant to the client sector, with 2 to 3 tappable pill-shaped answer options below, subtle progress dots indicating question depth",
    },
    "native-infeed": {
        "editorial_visual": "scene styled to match the visual tone of surrounding editorial content on the host publication, not obviously an ad, natural editorial photography quality",
        "sponsor_disclosure": "small honest sponsor disclosure label placed discreetly near the headline area",
    },
    "video-outstream": {
        "hook_3s": "first 3 seconds communicate the brand name and core message visually, without relying on audio (many placements autoplay muted)",
        "body": "main campaign message and scene, shot in high production value style matching the brand tone",
        "endcard": "static end card with brand logo centered and one clear call to action text, held for the last 2 seconds",
    },
    "netflix-logo-bumper": {
        "particle_intro": "black background, thin streaks of light and particles converging toward center, same visual rhythm as a streaming platform opening ident but in the brand primary tone instead of platform red",
        "logo_reveal": "particles resolve into the brand logo, brief hold with subtle glow, then soft fade to black",
    },
    "netflix-anuncio-simulado": {
        "context_card": "dark UI card in the visual language of a streaming platform content row, small eyebrow text with sponsor label, generous negative space, cinematic still",
        "brand_scene": "campaign scene shot in cinematic, moody, high-production-value style consistent with premium streaming original content, not commercial or salesy lighting",
    },
    "netflix-pause-banner": {
        "sponsor_icon": "compact brand or product visual anchored at the left edge, fully contained and immediately recognizable",
        "message": "short Brazilian Portuguese headline and one supporting line centered vertically in a dark premium horizontal banner",
        "cta": "small high-contrast call-to-action button aligned to the right with generous safe margins",
    },
    "hbomax-pause-ad": {
        "pause_frame": "calm, static composition suited to a paused-screen moment, brand logo placed discreetly, low visual urgency, elegant and minimal",
    },
    "hbomax-interactive-midroll": {
        "video_body": "mid-roll video scene with a subtle interactive layer cue hinted at the bottom of frame, suggesting click-reveal or carousel interaction",
    },
    "disney-pause-plus": {
        "pause_card": "clean pause-frame composition with either a static billboard message, a short brand trivia question, or a small product carousel — one of the three, not all",
    },
    "disney-branded-slate": {
        "sponsor_card": "presented-by style card shown before content starts, minimal composition, premium cinematic still of the brand hero product or scene",
    },
    "iab-medium-rectangle": {
        "background": "compact high-contrast background with one focal area and protected negative space for short copy",
        "content": "single product or scene, concise headline zone, brand mark and one clear call to action sized for 300 by 250 pixels",
    },
    "iab-leaderboard": {
        "background": "wide horizontal scene with visual continuity across the full banner and no critical detail near the edges",
        "content": "brand mark, short headline and call to action arranged in a left-to-right reading flow for 728 by 90 pixels",
    },
    "iab-half-page": {
        "background": "tall editorial background with depth and a stable central focal point suitable for a 300 by 600 placement",
        "content": "vertical story hierarchy with hero visual, short message, supporting detail and call to action",
    },
    "iab-mobile-banner": {
        "background": "very compact horizontal background with strong tonal separation and no decorative detail",
        "content": "brand mark, ultra-short message and compact call to action legible at 320 by 50 pixels",
    },
    "instagram-feed": {
        "background": "square photographic field with one subject and protected margins for locked copy",
        "content": "complete social advertisement: verbatim headline, optional support line, logo and one CTA",
    },
    "instagram-story": {
        "background": "vertical 9:16 photographic field with safe zones at top and bottom",
        "content": "full-bleed story piece with locked copy, logo and one CTA clear of UI chrome",
    },
    "tiktok-vertical": {
        "background": "vertical 9:16 photographic field with generous side and caption-safe margins",
        "content": "complete vertical ad: locked headline, logo and one CTA, no platform chrome",
    },
    "facebook-feed": {
        "background": "square feed field with a single focal subject and quiet negative space",
        "content": "complete feed advertisement with locked copy, logo and one CTA",
    },
    "linkedin-share": {
        "background": "landscape professional scene with left-to-right reading and calm lighting",
        "content": "complete share image: locked headline, logo and one CTA without feed chrome",
    },
    "instagram-feed-4x5": {
        "background": "editorial paper field in 4:5, one hero product and protected margins",
        "content": "complete feed still: headline, hero, brand lockup and legal, no app chrome",
    },
    "instagram-reels": {
        "background": "vertical 9:16 photographic field with safe zones at top and bottom",
        "content": "full-bleed Reels piece with locked copy, logo and one CTA clear of UI chrome",
    },
    "linkedin-feed": {
        "background": "square professional field with one subject and quiet negative space",
        "content": "complete LinkedIn feed advertisement with locked copy, logo and one CTA",
    },
    "linkedin-portrait": {
        "background": "4:5 professional still with a single focal subject",
        "content": "complete LinkedIn portrait advertisement with locked copy, logo and one CTA",
    },
    "youtube-infeed": {
        "background": "16:9 cinematic still that fills the watch player",
        "content": "complete in-feed advertisement: locked headline, logo and one CTA, no player chrome",
    },
    "youtube-shorts": {
        "background": "vertical 9:16 photographic field with caption-safe margins",
        "content": "complete Shorts advertisement: locked headline, logo and one CTA",
    },
}

CATEGORIES = (
    ("programatica", "Programática"),
    ("streaming", "Streaming"),
    ("social", "Redes sociais"),
)

CHANNELS = (
    (
        "netflix",
        "Netflix",
        "ctv_streaming",
        "smart_tv_16x9",
        "Premium streaming content displayed on a 16:9 smart TV screen.",
        "streaming",
    ),
    (
        "hbomax",
        "HBO Max",
        "ctv_streaming",
        "smart_tv_16x9",
        "Premium streaming content displayed on a 16:9 smart TV screen.",
        "streaming",
    ),
    (
        "disneyplus",
        "Disney+",
        "ctv_streaming",
        "smart_tv_16x9",
        "Premium streaming content displayed on a 16:9 smart TV screen.",
        "streaming",
    ),
    (
        "primevideo",
        "Prime Video",
        "ctv_streaming",
        "smart_tv_16x9",
        "Premium streaming content displayed on a 16:9 smart TV screen.",
        "streaming",
    ),
    (
        "portal_generico",
        "Portais Premium",
        "portal",
        "desktop_browser",
        "Premium news or content portal displayed in a desktop browser.",
        "programatica",
    ),
    (
        "meta_social",
        "Meta",
        "social",
        "smartphone_feed",
        "Social feed and story placements on Meta apps.",
        "social",
    ),
    (
        "tiktok_social",
        "TikTok",
        "social",
        "smartphone_vertical",
        "Vertical short-form social placement.",
        "social",
    ),
    (
        "linkedin_social",
        "LinkedIn",
        "social",
        "desktop_feed",
        "Professional landscape share placement.",
        "social",
    ),
    (
        "youtube_social",
        "YouTube",
        "social",
        "desktop_watch",
        "In-feed landscape and Shorts placements on YouTube.",
        "social",
    ),
)

FORMATS = (
    ("hotspot", "Hotspot", "Hotspot", "portal_generico", "click_expand", "image"),
    ("cartas", "Cartas", "Cards", "portal_generico", "card_flip", "image"),
    (
        "puxe-descubra",
        "Puxe e Descubra",
        "Pull and Discover",
        "portal_generico",
        "layered_reveal",
        "image",
    ),
    (
        "arraste-descubra",
        "Arraste e Descubra",
        "Drag and Discover",
        "portal_generico",
        "drag_compare",
        "image",
    ),
    ("quiz", "Quiz", "Quiz", "portal_generico", "quiz_flow", "image"),
    (
        "native-infeed",
        "Native In-Feed",
        "Native In-Feed",
        "portal_generico",
        "editorial_mimicry",
        "image",
    ),
    (
        "video-outstream",
        "Vídeo Outstream",
        "Outstream Video",
        "portal_generico",
        "image_carousel",
        "image",
    ),
    (
        "netflix-logo-bumper",
        "Netflix — Bumper logo",
        "Netflix — Logo bumper",
        "netflix",
        "image_carousel",
        "image",
    ),
    (
        "netflix-anuncio-simulado",
        "Netflix — Anúncio simulado",
        "Netflix — Simulated ad",
        "netflix",
        "image_carousel",
        "image",
    ),
    (
        "netflix-pause-banner",
        "Netflix — Banner na pausa",
        "Netflix — Pause banner",
        "netflix",
        "static_on_pause",
        "image",
    ),
    (
        "hbomax-pause-ad",
        "HBO Max — Pause Ad",
        "HBO Max — Pause Ad",
        "hbomax",
        "static_on_pause",
        "image",
    ),
    (
        "hbomax-interactive-midroll",
        "HBO Max — Mid-roll Interativo",
        "HBO Max — Interactive Mid-roll",
        "hbomax",
        "image_carousel",
        "image",
    ),
    (
        "disney-pause-plus",
        "Disney+ — Pause+",
        "Disney+ — Pause+",
        "disneyplus",
        "interactive_on_pause",
        "image",
    ),
    (
        "disney-branded-slate",
        "Disney+ — Branded Slate",
        "Disney+ — Branded Slate",
        "disneyplus",
        "sponsorship_card",
        "image",
    ),
    (
        "iab-medium-rectangle",
        "IAB Medium Rectangle 300×250",
        "IAB Medium Rectangle 300x250",
        "portal_generico",
        "static_display",
        "image",
    ),
    (
        "iab-leaderboard",
        "IAB Leaderboard 728×90",
        "IAB Leaderboard 728x90",
        "portal_generico",
        "static_display",
        "image",
    ),
    (
        "iab-half-page",
        "IAB Half Page 300×600",
        "IAB Half Page 300x600",
        "portal_generico",
        "static_display",
        "image",
    ),
    (
        "iab-mobile-banner",
        "IAB Mobile Banner 320×50",
        "IAB Mobile Banner 320x50",
        "portal_generico",
        "static_display",
        "image",
    ),
    (
        "instagram-feed",
        "Instagram — Feed 1080×1080",
        "Instagram — Feed 1080x1080",
        "meta_social",
        "static_display",
        "image",
    ),
    (
        "instagram-story",
        "Instagram — Story 1080×1920",
        "Instagram — Story 1080x1920",
        "meta_social",
        "static_display",
        "image",
    ),
    (
        "facebook-feed",
        "Facebook — Feed 1080×1080",
        "Facebook — Feed 1080x1080",
        "meta_social",
        "static_display",
        "image",
    ),
    (
        "tiktok-vertical",
        "TikTok — Vertical 1080×1920",
        "TikTok — Vertical 1080x1920",
        "tiktok_social",
        "static_display",
        "image",
    ),
    (
        "linkedin-share",
        "LinkedIn — Share 1200×627",
        "LinkedIn — Share 1200x627",
        "linkedin_social",
        "static_display",
        "image",
    ),
    (
        "instagram-feed-4x5",
        "Instagram — Feed 1080×1350",
        "Instagram — Feed 1080x1350",
        "meta_social",
        "static_display",
        "image",
    ),
    (
        "instagram-reels",
        "Instagram — Reels 1080×1920",
        "Instagram — Reels 1080x1920",
        "meta_social",
        "static_display",
        "image",
    ),
    (
        "linkedin-feed",
        "LinkedIn — Feed 1080×1080",
        "LinkedIn — Feed 1080x1080",
        "linkedin_social",
        "static_display",
        "image",
    ),
    (
        "linkedin-portrait",
        "LinkedIn — Retrato 1080×1350",
        "LinkedIn — Portrait 1080x1350",
        "linkedin_social",
        "static_display",
        "image",
    ),
    (
        "youtube-infeed",
        "YouTube — In-feed 1920×1080",
        "YouTube — In-feed 1920x1080",
        "youtube_social",
        "static_display",
        "image",
    ),
    (
        "youtube-shorts",
        "YouTube — Shorts 1080×1920",
        "YouTube — Shorts 1080x1920",
        "youtube_social",
        "static_display",
        "image",
    ),
)

CHANNEL_BRAND = {
    "netflix": ("#E50914", "#141414"),
    "hbomax": ("#5822B4", "#0B0714"),
    "disneyplus": ("#113CCF", "#071B47"),
    "primevideo": ("#00A8E1", "#0F171E"),
    "portal_generico": ("#1E4D4F", "#F8F9FA"),
    "meta_social": ("#1877F2", "#F8F9FA"),
    "tiktok_social": ("#111111", "#FE2C55"),
    "linkedin_social": ("#0A66C2", "#F3F6F8"),
    "youtube_social": ("#FF0000", "#0F0F0F"),
}

FORMAT_SPECS = {
    "netflix-pause-banner": {
        "aspect_ratio": "32:5",
        "default_size": "1920x300",
        "safe_area": {"top": 24, "right": 40, "bottom": 24, "left": 40, "unit": "px"},
        "responsive_rules": "Keep a compact horizontal composition with product at left, short message in the center and CTA at right.",
    },
    "iab-medium-rectangle": {
        "aspect_ratio": "6:5",
        "default_size": "300x250",
        "safe_area": {"top": 12, "right": 12, "bottom": 12, "left": 12, "unit": "px"},
        "responsive_rules": "Keep copy under 35 characters and preserve a single focal subject.",
    },
    "iab-leaderboard": {
        "aspect_ratio": "91:11",
        "default_size": "728x90",
        "safe_area": {"top": 8, "right": 16, "bottom": 8, "left": 16, "unit": "px"},
        "responsive_rules": "Use a horizontal reading flow; never crop the logo or CTA.",
    },
    "iab-half-page": {
        "aspect_ratio": "1:2",
        "default_size": "300x600",
        "safe_area": {"top": 20, "right": 16, "bottom": 20, "left": 16, "unit": "px"},
        "responsive_rules": "Use a vertical story hierarchy with at most three text blocks.",
    },
    "iab-mobile-banner": {
        "aspect_ratio": "32:5",
        "default_size": "320x50",
        "safe_area": {"top": 5, "right": 8, "bottom": 5, "left": 8, "unit": "px"},
        "responsive_rules": "Use logo plus ultra-short message; minimum effective type size 12 px.",
    },
    "instagram-feed": {
        "aspect_ratio": "1:1",
        "default_size": "1080x1080",
        "safe_area": {"top": 48, "right": 48, "bottom": 48, "left": 48, "unit": "px"},
        "responsive_rules": "Paint the complete locked advertisement; keep copy away from the edges.",
    },
    "instagram-story": {
        "aspect_ratio": "9:16",
        "default_size": "1080x1920",
        "safe_area": {"top": 160, "right": 64, "bottom": 220, "left": 64, "unit": "px"},
        "responsive_rules": "Keep locked copy and CTA inside the vertical safe area.",
    },
    "tiktok-vertical": {
        "aspect_ratio": "9:16",
        "default_size": "1080x1920",
        "safe_area": {"top": 140, "right": 80, "bottom": 240, "left": 80, "unit": "px"},
        "responsive_rules": "Leave caption-safe margins; do not invent platform chrome.",
    },
    "facebook-feed": {
        "aspect_ratio": "1:1",
        "default_size": "1080x1080",
        "safe_area": {"top": 48, "right": 48, "bottom": 48, "left": 48, "unit": "px"},
        "responsive_rules": "Complete feed piece with locked copy; no like-bar or comments.",
    },
    "linkedin-share": {
        "aspect_ratio": "1.91:1",
        "default_size": "1200x627",
        "safe_area": {"top": 36, "right": 48, "bottom": 36, "left": 48, "unit": "px"},
        "responsive_rules": "Landscape reading flow; keep headline and CTA fully visible.",
    },
    "instagram-feed-4x5": {
        "aspect_ratio": "4:5",
        "default_size": "1080x1350",
        "safe_area": {"top": 56, "right": 48, "bottom": 72, "left": 48, "unit": "px"},
        "responsive_rules": "Fill the 4:5 card with no letterbox; keep copy off the edges.",
    },
    "instagram-reels": {
        "aspect_ratio": "9:16",
        "default_size": "1080x1920",
        "safe_area": {"top": 160, "right": 64, "bottom": 220, "left": 64, "unit": "px"},
        "responsive_rules": "Keep locked copy and CTA inside the vertical safe area.",
    },
    "linkedin-feed": {
        "aspect_ratio": "1:1",
        "default_size": "1080x1080",
        "safe_area": {"top": 48, "right": 48, "bottom": 48, "left": 48, "unit": "px"},
        "responsive_rules": "Complete feed piece with locked copy; no reactions bar.",
    },
    "linkedin-portrait": {
        "aspect_ratio": "4:5",
        "default_size": "1080x1350",
        "safe_area": {"top": 56, "right": 48, "bottom": 72, "left": 48, "unit": "px"},
        "responsive_rules": "Fill the portrait card; keep headline and CTA fully visible.",
    },
    "youtube-infeed": {
        "aspect_ratio": "16:9",
        "default_size": "1920x1080",
        "safe_area": {"top": 48, "right": 64, "bottom": 80, "left": 64, "unit": "px"},
        "responsive_rules": "Fill the 16:9 player; do not invent watch chrome.",
    },
    "youtube-shorts": {
        "aspect_ratio": "9:16",
        "default_size": "1080x1920",
        "safe_area": {"top": 140, "right": 80, "bottom": 240, "left": 80, "unit": "px"},
        "responsive_rules": "Leave caption-safe margins; do not invent Shorts chrome.",
    },
}


def _layers(slug):
    return [
        {"role": role, "description_template": description}
        for role, description in LAYER_DESCRIPTIONS[slug].items()
    ]


def main():
    conn = psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    )
    try:
        with conn.cursor() as cursor:
            for slug, name in CATEGORIES:
                cursor.execute(
                    """
                    INSERT INTO cx_format_categories (slug, name)
                    VALUES (%s, %s)
                    ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
                    """,
                    (slug, name),
                )

            cursor.execute("SELECT id, slug FROM cx_format_categories")
            category_ids = {row["slug"]: row["id"] for row in cursor.fetchall()}
            for slug, name, channel_type, device, context, category in CHANNELS:
                primary_color, secondary_color = CHANNEL_BRAND[slug]
                cursor.execute(
                    """
                    INSERT INTO cx_channels (
                        slug, name, channel_type, device_mockup,
                        screen_context_template, category_id,
                        partner_primary_color, partner_secondary_color
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (slug) DO UPDATE SET
                        name = EXCLUDED.name,
                        channel_type = EXCLUDED.channel_type,
                        device_mockup = EXCLUDED.device_mockup,
                        screen_context_template = EXCLUDED.screen_context_template,
                        category_id = EXCLUDED.category_id,
                        partner_primary_color = EXCLUDED.partner_primary_color,
                        partner_secondary_color = EXCLUDED.partner_secondary_color
                    """,
                    (
                        slug,
                        name,
                        channel_type,
                        device,
                        context,
                        category_ids[category],
                        primary_color,
                        secondary_color,
                    ),
                )

            cursor.execute("SELECT id, slug FROM cx_channels")
            channel_ids = {row["slug"]: row["id"] for row in cursor.fetchall()}
            for slug, name_pt, name_en, channel, mechanic, media_type in FORMATS:
                engine = (
                    "gpt_image_2" if media_type == "image" else "higgsfield"
                )
                spec = FORMAT_SPECS.get(slug, {})
                aspect_ratio = spec.get("aspect_ratio", "16:9")
                default_size = spec.get("default_size", "1920x1080")
                descriptions = LAYER_DESCRIPTIONS[slug]
                roles = list(descriptions)
                cursor.execute(
                    """
                    INSERT INTO cx_format_templates (
                        slug, name_pt, name_en, channel_id, mechanic,
                        media_type, engine, aspect_ratio, default_size,
                        safe_area, responsive_rules, background_guidance,
                        foreground_guidance, layers, required_fields, optional_fields,
                        forbidden_elements, use_cases_by_market,
                        status, is_active
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
                        '{}'::jsonb, 'formato_aberto', TRUE
                    )
                    ON CONFLICT (slug) DO UPDATE SET
                        name_pt = EXCLUDED.name_pt,
                        name_en = EXCLUDED.name_en,
                        channel_id = EXCLUDED.channel_id,
                        mechanic = EXCLUDED.mechanic,
                        media_type = EXCLUDED.media_type,
                        engine = EXCLUDED.engine,
                        aspect_ratio = EXCLUDED.aspect_ratio,
                        default_size = EXCLUDED.default_size,
                        safe_area = EXCLUDED.safe_area,
                        responsive_rules = EXCLUDED.responsive_rules,
                        background_guidance = EXCLUDED.background_guidance,
                        foreground_guidance = EXCLUDED.foreground_guidance,
                        layers = EXCLUDED.layers,
                        is_active = TRUE
                    """,
                    (
                        slug,
                        name_pt,
                        name_en,
                        channel_ids.get(channel),
                        mechanic,
                        media_type,
                        engine,
                        aspect_ratio,
                        default_size,
                        Json(spec.get("safe_area", {})),
                        spec.get("responsive_rules"),
                        descriptions.get(roles[0]) if roles else None,
                        descriptions.get(roles[-1]) if roles else None,
                        Json(_layers(slug)),
                    ),
                )
        conn.commit()

        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM cx_format_templates")
            total = cursor.fetchone()["total"]
        if total < len(FORMATS):
            raise RuntimeError(f"Seed incompleto: {total} formatos encontrados.")
        print(
            "Catálogo de Modelagem de Criativos populado: "
            f"{len(CATEGORIES)} categorias, {len(CHANNELS)} canais, "
            f"{len(FORMATS)} formatos."
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
