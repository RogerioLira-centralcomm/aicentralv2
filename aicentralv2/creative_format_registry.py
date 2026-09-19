"""Registro canônico de formatos da Biblioteca — uma chave, muitos aliases."""

from __future__ import annotations

DISCLAIMER = "Simulação de ambiente · sem afiliação com o veículo"

PLACEMENT_ZONES = frozenset({"leaderboard", "rail", "in_feed", "sticky"})
VIEWER_TYPES = frozenset({
    "portal", "ctv", "social_vertical", "social_feed", "linkedin",
    "youtube_infeed", "isolated",
})
SOURCE_TYPES = frozenset({
    "client_creative",
    "client_assets_recomposed",
    "generated_mock",
    "internal_demo",
    "smart_placeholder",
})
PUBLIC_LABELS = {
    "generated_mock": "Mock demonstrativo",
    "internal_demo": "Prova de conceito",
    "smart_placeholder": "Placeholder de formato",
    "client_creative": "Criativo fornecido pelo cliente",
    "client_assets_recomposed": "Variante recomposta para demonstração",
}


def _fmt(
    key,
    *,
    label,
    width,
    height,
    family,
    density,
    channels,
    devices,
    placement_zones,
    viewer_types,
    required,
    optional=(),
    forbidden=(),
    fit="contain",
    safe_areas=None,
    recomposition=None,
    geometry_family=None,
    iab_cousin=None,
    kind="banner",
    aliases=(),
):
    return {
        "format_key": key,
        "label": label,
        "aliases": list(aliases),
        "width": width,
        "height": height,
        "family": family,
        "geometry_family": geometry_family or family,
        "iab_cousin": iab_cousin,
        "density": density,
        "channels": list(channels),
        "devices": list(devices),
        "placement_zones": list(placement_zones),
        "fit": fit,
        "required_elements": list(required),
        "optional_elements": list(optional),
        "forbidden_elements": list(forbidden) + ["portal_chrome", "social_reactions"],
        "safe_areas": safe_areas or {"inset_pct": 0},
        "viewer_types": list(viewer_types),
        "kind": kind,
        "recomposition_rules": recomposition or {
            "preserve": list(required),
            "drop_when_compact": ["support", "legal", "product", "lifestyle"],
            "siblings": [],
        },
    }


PORTAL_FORBIDDEN = ("ctv_button", "site_menu", "social_reactions")
CTV_FORBIDDEN = ("site_button", "pill_cta", "price", "site_menu", "portal_chrome")
SOCIAL_FORBIDDEN = ("portal_chrome", "ctv_qr")

FORMATS = (
    _fmt(
        "iab-billboard",
        label="Billboard",
        width=970, height=250,
        family="rich-display", density="rich",
        geometry_family="wide_banner", iab_cousin="billboard",
        channels=("portal", "programmatic"),
        devices=("desktop",),
        placement_zones=("leaderboard",),
        viewer_types=("portal", "isolated"),
        required=("logo", "headline", "cta"),
        optional=("product", "support", "legal"),
        forbidden=PORTAL_FORBIDDEN,
        aliases=("billboard", "iab-billboard-970x250"),
        recomposition={
            "preserve": ["logo", "headline", "cta"],
            "drop_when_compact": [],
            "siblings": ["iab-leaderboard", "iab-medium", "iab-halfpage", "iab-mobile"],
        },
    ),
    _fmt(
        "iab-leaderboard",
        label="Leaderboard",
        width=728, height=90,
        family="compact-display", density="compact",
        geometry_family="wide_banner", iab_cousin="leaderboard",
        channels=("portal", "programmatic"),
        devices=("desktop", "mobile"),
        placement_zones=("leaderboard", "sticky"),
        viewer_types=("portal", "isolated"),
        required=("logo", "headline", "cta"),
        optional=(),
        forbidden=PORTAL_FORBIDDEN + ("product", "lifestyle", "legal"),
        aliases=("leaderboard",),
        recomposition={
            "preserve": ["logo", "headline", "cta"],
            "drop_when_compact": ["product", "support", "legal", "lifestyle"],
            "siblings": ["iab-billboard", "iab-mobile"],
        },
    ),
    _fmt(
        "iab-medium",
        label="Medium rectangle",
        width=300, height=250,
        family="standard-display", density="standard",
        geometry_family="rectangle", iab_cousin="medium_rectangle",
        channels=("portal", "programmatic"),
        devices=("desktop", "mobile"),
        placement_zones=("in_feed",),
        viewer_types=("portal", "isolated"),
        required=("logo", "headline", "cta"),
        optional=("product", "lifestyle"),
        forbidden=PORTAL_FORBIDDEN,
        aliases=("iab-medium-rectangle", "iab-banner", "medium-rectangle"),
        recomposition={
            "preserve": ["logo", "headline", "cta"],
            "drop_when_compact": ["support", "legal"],
            "siblings": ["iab-billboard", "iab-halfpage", "iab-leaderboard"],
        },
    ),
    _fmt(
        "display-300x300",
        label="Square display",
        width=300, height=300,
        family="standard-display", density="standard",
        geometry_family="square_1x1", iab_cousin="square_display",
        channels=("portal", "programmatic", "app"),
        devices=("desktop", "mobile"),
        placement_zones=("in_feed",),
        viewer_types=("portal", "isolated"),
        required=("logo", "headline", "cta"),
        optional=("product", "lifestyle", "support"),
        forbidden=PORTAL_FORBIDDEN,
        aliases=("square-display", "display-square-300"),
        recomposition={
            "preserve": ["logo", "headline", "cta"],
            "drop_when_compact": ["support", "legal"],
            "siblings": ["iab-medium", "feed-1x1", "iab-halfpage"],
        },
    ),
    _fmt(
        "iab-halfpage",
        label="Half page",
        width=300, height=600,
        family="rich-display", density="rich",
        geometry_family="half_page", iab_cousin="half_page",
        channels=("portal", "programmatic"),
        devices=("desktop",),
        placement_zones=("rail",),
        viewer_types=("portal", "isolated"),
        required=("logo", "headline", "cta"),
        optional=("product", "support", "legal"),
        forbidden=PORTAL_FORBIDDEN,
        aliases=("iab-half-page", "half-page"),
        recomposition={
            "preserve": ["logo", "headline", "product", "cta"],
            "drop_when_compact": [],
            "siblings": ["iab-skyscraper", "iab-medium", "iab-billboard"],
        },
    ),
    _fmt(
        "iab-skyscraper",
        label="Skyscraper",
        width=160, height=600,
        family="compact-display", density="compact",
        geometry_family="half_page", iab_cousin="skyscraper",
        channels=("portal", "programmatic"),
        devices=("desktop",),
        placement_zones=("rail",),
        viewer_types=("portal", "isolated"),
        required=("logo", "headline", "cta"),
        optional=("product",),
        forbidden=PORTAL_FORBIDDEN,
        aliases=("skyscraper", "iab-wide-skyscraper"),
        recomposition={
            "preserve": ["logo", "headline", "cta"],
            "drop_when_compact": ["support", "legal", "lifestyle"],
            "siblings": ["iab-halfpage"],
        },
    ),
    _fmt(
        "iab-mobile",
        label="Mobile banner",
        width=320, height=50,
        family="compact-display", density="compact",
        geometry_family="wide_banner", iab_cousin="mobile_banner",
        channels=("portal", "programmatic"),
        devices=("mobile",),
        placement_zones=("sticky",),
        viewer_types=("portal", "isolated"),
        required=("logo", "headline", "cta"),
        optional=(),
        forbidden=PORTAL_FORBIDDEN + ("product", "lifestyle", "legal"),
        aliases=("iab-mobile-banner", "mobile-banner"),
        recomposition={
            "preserve": ["logo", "headline", "cta"],
            "drop_when_compact": ["product", "support", "legal", "lifestyle"],
            "siblings": ["iab-leaderboard"],
        },
    ),
    _fmt(
        "native-infeed",
        label="Native in-feed",
        width=300, height=250,
        family="native", density="standard",
        geometry_family="portal_unit",
        channels=("portal",),
        devices=("desktop", "mobile"),
        placement_zones=("in_feed",),
        viewer_types=("portal",),
        required=("headline", "image"),
        optional=("logo", "support", "cta"),
        forbidden=PORTAL_FORBIDDEN + ("billboard_chrome",),
        kind="native",
        aliases=("native",),
    ),
    _fmt(
        "hotspot",
        label="Hotspot",
        width=300, height=250,
        family="interactive", density="standard",
        geometry_family="portal_unit",
        channels=("portal",),
        devices=("desktop", "mobile"),
        placement_zones=("in_feed",),
        viewer_types=("portal",),
        required=("image", "hotspot"),
        optional=("logo", "headline", "cta"),
        forbidden=PORTAL_FORBIDDEN,
        kind="interactive",
        aliases=("hotspots",),
    ),
    _fmt(
        "cartas",
        label="Cartas",
        width=300, height=250,
        family="interactive", density="standard",
        geometry_family="portal_unit",
        channels=("portal",),
        devices=("desktop", "mobile"),
        placement_zones=("in_feed",),
        viewer_types=("portal",),
        required=("card_front", "card_back"),
        optional=("logo", "cta"),
        forbidden=PORTAL_FORBIDDEN,
        kind="interactive",
        aliases=("flip", "cartas-flip"),
    ),
    _fmt(
        "puxe-descubra",
        label="Puxe e descubra",
        width=300, height=250,
        family="interactive", density="standard",
        geometry_family="portal_unit",
        channels=("portal",),
        devices=("desktop", "mobile"),
        placement_zones=("in_feed",),
        viewer_types=("portal",),
        required=("cover", "reveal"),
        optional=("logo", "cta"),
        forbidden=PORTAL_FORBIDDEN,
        kind="interactive",
        aliases=("reveal",),
    ),
    _fmt(
        "arraste-descubra",
        label="Arraste e descubra",
        width=300, height=250,
        family="interactive", density="standard",
        geometry_family="portal_unit",
        channels=("portal",),
        devices=("desktop", "mobile"),
        placement_zones=("in_feed",),
        viewer_types=("portal",),
        required=("before", "after", "handle"),
        optional=("logo", "cta"),
        forbidden=PORTAL_FORBIDDEN,
        kind="interactive",
        aliases=("compare", "before-after"),
    ),
    _fmt(
        "quiz",
        label="Quiz",
        width=300, height=250,
        family="interactive", density="standard",
        geometry_family="portal_unit",
        channels=("portal",),
        devices=("desktop", "mobile"),
        placement_zones=("in_feed",),
        viewer_types=("portal",),
        required=("question", "choices", "result"),
        optional=("logo", "cta"),
        forbidden=PORTAL_FORBIDDEN,
        kind="interactive",
        aliases=("quiz-infeed",),
    ),
    _fmt(
        "video-linear-15",
        label="Video 15s",
        width=1920, height=1080,
        family="ctv-15", density="rich",
        geometry_family="slate_16x9", iab_cousin="digital_video",
        channels=("ctv", "youtube"),
        devices=("tv",),
        placement_zones=(),
        viewer_types=("ctv",),
        required=("headline",),
        optional=("logo", "product", "lifestyle"),
        forbidden=CTV_FORBIDDEN,
        safe_areas={"inset_pct": 6},
        kind="video",
        aliases=("ctv-video-linear-30", "ctv-linear", "netflix-anuncio-simulado"),
        recomposition={
            "preserve": ["headline", "logo"],
            "drop_when_compact": ["price", "site_button"],
            "siblings": ["video-cta-15", "video-qr-15", "youtube-infeed"],
        },
    ),
    _fmt(
        "video-cta-15",
        label="Video 15s + CTA",
        width=1920, height=1080,
        family="ctv-15", density="rich",
        geometry_family="slate_16x9", iab_cousin="digital_video",
        channels=("ctv", "youtube"),
        devices=("tv",),
        placement_zones=(),
        viewer_types=("ctv",),
        required=("headline", "cta_instruction"),
        optional=("logo", "product"),
        forbidden=CTV_FORBIDDEN,
        safe_areas={"inset_pct": 6},
        kind="video",
        aliases=("ctv-video-cta",),
    ),
    _fmt(
        "video-qr-15",
        label="Video 15s + QR",
        width=1920, height=1080,
        family="ctv-15", density="rich",
        geometry_family="slate_16x9", iab_cousin="digital_video",
        channels=("youtube",),
        devices=("tv",),
        placement_zones=(),
        viewer_types=("ctv",),
        required=("headline", "qr", "cta_instruction"),
        optional=("logo",),
        forbidden=CTV_FORBIDDEN,
        safe_areas={"inset_pct": 6},
        kind="video",
        aliases=("ctv-video-qr",),
    ),
    _fmt(
        "youtube-infeed",
        label="In-feed 16:9",
        width=1920, height=1080,
        family="youtube", density="standard",
        geometry_family="slate_16x9",
        channels=("youtube",),
        devices=("desktop", "tv"),
        placement_zones=(),
        viewer_types=("youtube_infeed", "ctv"),
        required=("headline",),
        optional=("logo", "thumbnail"),
        forbidden=CTV_FORBIDDEN,
        kind="video",
        aliases=(),
    ),
    _fmt(
        "feed-1x1",
        label="Feed 1:1",
        width=1080, height=1080,
        family="social-square", density="standard",
        geometry_family="square_1x1",
        channels=("instagram", "facebook", "linkedin"),
        devices=("mobile", "desktop"),
        placement_zones=(),
        viewer_types=("social_feed",),
        required=("headline",),
        optional=("logo", "product", "cta"),
        forbidden=SOCIAL_FORBIDDEN,
        kind="social",
        aliases=("instagram-feed", "facebook-feed", "linkedin-feed"),
    ),
    _fmt(
        "feed-4x5",
        label="Feed 4:5",
        width=1080, height=1350,
        family="social-portrait", density="standard",
        geometry_family="portrait_4x5",
        channels=("instagram", "facebook"),
        devices=("mobile",),
        placement_zones=(),
        viewer_types=("social_feed",),
        required=("headline",),
        optional=("logo", "product", "cta"),
        forbidden=SOCIAL_FORBIDDEN,
        kind="social",
        aliases=("instagram-feed-4x5", "linkedin-portrait"),
    ),
    _fmt(
        "story-9x16",
        label="Stories",
        width=1080, height=1920,
        family="social-story", density="standard",
        geometry_family="story_9x16",
        channels=("instagram", "facebook"),
        devices=("mobile",),
        placement_zones=(),
        viewer_types=("social_vertical",),
        required=("headline",),
        optional=("logo", "cta"),
        forbidden=SOCIAL_FORBIDDEN,
        safe_areas={"inset_pct": 8, "bottom_chrome": True},
        kind="social",
        aliases=("instagram-story",),
    ),
    _fmt(
        "reels-9x16",
        label="Reels",
        width=1080, height=1920,
        family="social-story", density="standard",
        geometry_family="story_9x16",
        channels=("instagram", "tiktok", "youtube"),
        devices=("mobile",),
        placement_zones=(),
        viewer_types=("social_vertical",),
        required=("headline",),
        optional=("logo", "cta"),
        forbidden=SOCIAL_FORBIDDEN + ("static_only",),
        safe_areas={"inset_pct": 8, "bottom_chrome": True},
        kind="social",
        aliases=("instagram-reels", "tiktok-vertical"),
    ),
    _fmt(
        "shorts-9x16",
        label="Shorts",
        width=1080, height=1920,
        family="social-story", density="standard",
        geometry_family="story_9x16",
        channels=("youtube", "tiktok"),
        devices=("mobile",),
        placement_zones=(),
        viewer_types=("social_vertical",),
        required=("headline",),
        optional=("logo", "cta"),
        forbidden=SOCIAL_FORBIDDEN + ("static_only",),
        safe_areas={"inset_pct": 8, "bottom_chrome": True},
        kind="social",
        aliases=("youtube-shorts",),
    ),
    _fmt(
        "linkedin-landscape",
        label="LinkedIn",
        width=1200, height=627,
        family="social-landscape", density="standard",
        geometry_family="landscape_social",
        channels=("linkedin",),
        devices=("desktop",),
        placement_zones=(),
        viewer_types=("linkedin",),
        required=("headline",),
        optional=("logo", "product", "cta"),
        forbidden=SOCIAL_FORBIDDEN,
        kind="social",
        aliases=("linkedin-share",),
    ),
)

# Slugs de CTV de veículo (DB) — sem zona de portal.
_CTV_VEHICLE = (
    "netflix-pause-banner",
    "netflix-logo-bumper",
    "hbomax-pause-ad",
    "hbomax-interactive-midroll",
    "disney-pause-plus",
    "disney-branded-slate",
)

_ALIAS_MAP = {}
_BY_KEY = {}
for _item in FORMATS:
    _BY_KEY[_item["format_key"]] = _item
    _ALIAS_MAP[_item["format_key"]] = _item["format_key"]
    for _alias in _item["aliases"]:
        _ALIAS_MAP[_alias] = _item["format_key"]

_ALIAS_MAP.update({
    "netflix-anuncio-simulado": "video-linear-15",
})
for _slug in _CTV_VEHICLE:
    _ALIAS_MAP.setdefault(_slug, _slug)


def resolve_format_key(raw):
    key = str(raw or "").strip()
    if not key:
        return None
    if key in _BY_KEY:
        return key
    return _ALIAS_MAP.get(key)


def entry(key):
    resolved = resolve_format_key(key)
    if not resolved:
        return None
    item = _BY_KEY.get(resolved)
    if not item:
        return None
    data = dict(item)
    data["aliases"] = list(item["aliases"])
    return data


def catalog_entries():
    return [entry(item["format_key"]) for item in FORMATS]


def aliases_for(key):
    item = entry(key)
    return list(item["aliases"]) if item else []


def public_label_for(source_type):
    return PUBLIC_LABELS.get(str(source_type or ""), "Prova de conceito")


def _blocked(code, format_key, viewer_slug, device, message):
    return {
        "status": "blocked",
        "code": code,
        "format_key": format_key or "",
        "viewer_slug": viewer_slug or "",
        "device": device or "",
        "message": message,
        "zone": None,
    }


def compatibility(format_key, channel=None, device=None, zone=None, viewer_slug=None):
    resolved = resolve_format_key(format_key)
    item = entry(resolved) if resolved else None
    if not item:
        return _blocked(
            "PLACEMENT_NOT_DEFINED",
            str(format_key or ""),
            viewer_slug,
            device,
            "Formato sem registro canônico.",
        )
    channel_key = str(channel or "").strip().lower()
    device_key = str(device or "").strip().lower()
    if device_key in {"celular"}:
        device_key = "mobile"
    if device_key in {"smart_tv", "streaming"}:
        device_key = "tv"
    zone_key = str(zone or "").strip() or None
    if zone_key == "":
        zone_key = None

    if channel_key and channel_key not in item["channels"]:
        return _blocked(
            "PLACEMENT_INCOMPATIBLE",
            item["format_key"],
            viewer_slug,
            device_key,
            f"Canal {channel_key} não autoriza {item['format_key']}.",
        )
    if device_key and device_key not in item["devices"]:
        return _blocked(
            "PLACEMENT_INCOMPATIBLE",
            item["format_key"],
            viewer_slug,
            device_key,
            f"Dispositivo {device_key} não autoriza {item['format_key']}.",
        )

    allowed_zones = list(item["placement_zones"])
    if device_key == "mobile" and "leaderboard" in allowed_zones and "sticky" in allowed_zones:
        expected = "sticky"
    elif device_key == "desktop" and "sticky" in allowed_zones and len(allowed_zones) > 1:
        expected = next((item_zone for item_zone in allowed_zones if item_zone != "sticky"), None)
    elif allowed_zones:
        expected = allowed_zones[0]
    else:
        expected = None

    if expected is None:
        if zone_key:
            return _blocked(
                "PLACEMENT_INCOMPATIBLE",
                item["format_key"],
                viewer_slug,
                device_key,
                "Formato de CTV ou social não usa zona de portal.",
            )
        return {
            "status": "ok",
            "code": "WELL",
            "format_key": item["format_key"],
            "viewer_slug": viewer_slug or "",
            "device": device_key,
            "message": "",
            "zone": None,
            "fit": item["fit"],
        }

    if zone_key and zone_key not in allowed_zones:
        return _blocked(
            "PLACEMENT_INCOMPATIBLE",
            item["format_key"],
            viewer_slug,
            device_key,
            f"Zona {zone_key} não autoriza {item['format_key']}.",
        )
    if zone_key and expected and zone_key != expected and not (
        item["format_key"] == "iab-leaderboard" and zone_key in allowed_zones
    ):
        return _blocked(
            "PLACEMENT_INCOMPATIBLE",
            item["format_key"],
            viewer_slug,
            device_key,
            f"Zona {zone_key} não combina com {device_key or 'desktop'}.",
        )
    return {
        "status": "ok",
        "code": "PLACED",
        "format_key": item["format_key"],
        "viewer_slug": viewer_slug or "",
        "device": device_key,
        "message": "",
        "zone": zone_key or expected,
        "fit": item["fit"],
    }


def default_zone(format_key, device=None):
    result = compatibility(format_key, device=device)
    if result["status"] != "ok":
        return None
    return result.get("zone")


def is_portal_unit(format_key):
    item = entry(format_key)
    return bool(item and item["kind"] in {"native", "interactive"})


def is_social(format_key):
    item = entry(format_key)
    return bool(item and item["kind"] == "social")


def is_ctv(format_key):
    item = entry(format_key)
    return bool(item and item["kind"] == "video")
