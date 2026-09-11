"""Catálogo 15s: CTV e banners IAB, adapters e composições 4|5."""

from ..creative_skills.visual import list_visual_skills

DURATION_SECONDS = 15
SCENE_COUNTS = (4, 5)

FORMATS = (
    {
        "key": "video-linear-15",
        "family": "horizontal-15",
        "label": "Video 15s",
        "adapter": "generic_ctv",
        "platform_label": "16:9",
        "canvas": {"width": 1920, "height": 1080},
        "aspect_ratio": "16:9",
        "orientation": "horizontal",
        "size_label": "1920×1080",
        "group": "15s",
        "kind": "video",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "video-cta-15",
        "family": "horizontal-15",
        "label": "Video 15s + CTA",
        "adapter": "generic_ctv",
        "platform_label": "16:9",
        "canvas": {"width": 1920, "height": 1080},
        "aspect_ratio": "16:9",
        "orientation": "horizontal",
        "size_label": "1920×1080",
        "group": "15s",
        "kind": "video",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "video-qr-15",
        "family": "horizontal-15",
        "label": "Video 15s + QR",
        "adapter": "youtube_ctv",
        "platform_label": "16:9",
        "canvas": {"width": 1920, "height": 1080},
        "aspect_ratio": "16:9",
        "orientation": "horizontal",
        "size_label": "1920×1080",
        "group": "15s",
        "kind": "video",
        "duration": 15,
        "has_qr": True,
        "has_cta_scene": True,
    },
    {
        "key": "iab-billboard",
        "family": "iab-horizontal",
        "label": "Billboard",
        "adapter": "iab_horizontal",
        "platform_label": "970×250",
        "canvas": {"width": 970, "height": 250},
        "aspect_ratio": "97:25",
        "orientation": "horizontal",
        "size_label": "970×250",
        "group": "horizontal",
        "kind": "banner",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "iab-leaderboard",
        "family": "iab-horizontal",
        "label": "Leaderboard",
        "adapter": "iab_horizontal",
        "platform_label": "728×90",
        "canvas": {"width": 728, "height": 90},
        "aspect_ratio": "728:90",
        "orientation": "horizontal",
        "size_label": "728×90",
        "group": "horizontal",
        "kind": "banner",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "iab-medium",
        "family": "iab-box",
        "label": "Medium rectangle",
        "adapter": "iab_box",
        "platform_label": "300×250",
        "canvas": {"width": 300, "height": 250},
        "aspect_ratio": "6:5",
        "orientation": "horizontal",
        "size_label": "300×250",
        "group": "retangulo",
        "kind": "banner",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "iab-halfpage",
        "family": "iab-vertical",
        "label": "Half page",
        "adapter": "iab_vertical",
        "platform_label": "300×600",
        "canvas": {"width": 300, "height": 600},
        "aspect_ratio": "1:2",
        "orientation": "vertical",
        "size_label": "300×600",
        "group": "vertical",
        "kind": "banner",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "iab-skyscraper",
        "family": "iab-vertical",
        "label": "Skyscraper",
        "adapter": "iab_vertical",
        "platform_label": "160×600",
        "canvas": {"width": 160, "height": 600},
        "aspect_ratio": "4:15",
        "orientation": "vertical",
        "size_label": "160×600",
        "group": "vertical",
        "kind": "banner",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "iab-mobile",
        "family": "iab-horizontal",
        "label": "Mobile banner",
        "adapter": "iab_horizontal",
        "platform_label": "320×50",
        "canvas": {"width": 320, "height": 50},
        "aspect_ratio": "32:5",
        "orientation": "horizontal",
        "size_label": "320×50",
        "group": "horizontal",
        "kind": "banner",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "feed-1x1",
        "family": "social-square",
        "label": "Feed 1:1",
        "adapter": "iab_box",
        "platform_label": "1080×1080",
        "canvas": {"width": 1080, "height": 1080},
        "aspect_ratio": "1:1",
        "orientation": "square",
        "size_label": "1080×1080",
        "group": "social",
        "kind": "social",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "feed-4x5",
        "family": "social-portrait",
        "label": "Feed 4:5",
        "adapter": "iab_box",
        "platform_label": "1080×1350",
        "canvas": {"width": 1080, "height": 1350},
        "aspect_ratio": "4:5",
        "orientation": "vertical",
        "size_label": "1080×1350",
        "group": "social",
        "kind": "social",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "story-9x16",
        "family": "social-story",
        "label": "Stories",
        "adapter": "iab_vertical",
        "platform_label": "1080×1920",
        "canvas": {"width": 1080, "height": 1920},
        "aspect_ratio": "9:16",
        "orientation": "vertical",
        "size_label": "1080×1920",
        "group": "social",
        "kind": "social",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "reels-9x16",
        "family": "social-story",
        "label": "Reels",
        "adapter": "iab_vertical",
        "platform_label": "1080×1920",
        "canvas": {"width": 1080, "height": 1920},
        "aspect_ratio": "9:16",
        "orientation": "vertical",
        "size_label": "1080×1920",
        "group": "social",
        "kind": "social",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "shorts-9x16",
        "family": "social-story",
        "label": "Shorts",
        "adapter": "iab_vertical",
        "platform_label": "1080×1920",
        "canvas": {"width": 1080, "height": 1920},
        "aspect_ratio": "9:16",
        "orientation": "vertical",
        "size_label": "1080×1920",
        "group": "social",
        "kind": "social",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "linkedin-landscape",
        "family": "social-landscape",
        "label": "LinkedIn",
        "adapter": "iab_horizontal",
        "platform_label": "1200×627",
        "canvas": {"width": 1200, "height": 627},
        "aspect_ratio": "1200:627",
        "orientation": "horizontal",
        "size_label": "1200×627",
        "group": "social",
        "kind": "social",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
    {
        "key": "youtube-infeed",
        "family": "horizontal-15",
        "label": "In-feed 16:9",
        "adapter": "generic_ctv",
        "platform_label": "1920×1080",
        "canvas": {"width": 1920, "height": 1080},
        "aspect_ratio": "16:9",
        "orientation": "horizontal",
        "size_label": "1920×1080",
        "group": "15s",
        "kind": "video",
        "duration": 15,
        "has_qr": False,
        "has_cta_scene": True,
    },
)

FORMAT_ALIASES = {
    "ctv-video-linear-30": "video-linear-15",
    "ctv-video-cta": "video-cta-15",
    "ctv-video-qr": "video-qr-15",
    "iab-banner": "iab-medium",
    "iab-half-page": "iab-halfpage",
    "iab-medium-rectangle": "iab-medium",
}

ADAPTERS = {
    "generic_ctv": {
        "label": "Generic CTV",
        "platform_label": "16:9",
        "prototype": "ctv/generic_ctv",
    },
    "netflix": {
        "label": "Netflix",
        "platform_label": "NETFLIX",
        "prototype": "ctv/netflix",
    },
    "youtube_ctv": {
        "label": "YouTube CTV",
        "platform_label": "YOUTUBE CTV",
        "prototype": "ctv/youtube_ctv",
    },
    "iab_horizontal": {
        "label": "IAB horizontal",
        "platform_label": "IAB",
        "prototype": "iab/horizontal",
    },
    "iab_vertical": {
        "label": "IAB vertical",
        "platform_label": "IAB",
        "prototype": "iab/vertical",
    },
    "iab_box": {
        "label": "IAB retângulo",
        "platform_label": "IAB",
        "prototype": "iab/box",
    },
}

FORMAT_GROUPS = (
    {"key": "15s", "label": "15s na TV"},
    {"key": "horizontal", "label": "Faixa horizontal"},
    {"key": "vertical", "label": "Coluna vertical"},
    {"key": "retangulo", "label": "Retângulo"},
    {"key": "social", "label": "Social"},
)

CHANNELS = (
    {"key": "ctv", "label": "CTV"},
    {"key": "youtube", "label": "YouTube"},
    {"key": "programmatic", "label": "Programática"},
    {"key": "portal", "label": "Portal"},
    {"key": "instagram", "label": "Instagram"},
    {"key": "facebook", "label": "Facebook"},
    {"key": "tiktok", "label": "TikTok"},
    {"key": "linkedin", "label": "LinkedIn"},
)

FORMAT_CHANNELS = {
    "video-linear-15": ("ctv", "youtube"),
    "video-cta-15": ("ctv", "youtube"),
    "video-qr-15": ("youtube",),
    "youtube-infeed": ("youtube",),
    "iab-billboard": ("portal", "programmatic"),
    "iab-leaderboard": ("portal", "programmatic"),
    "iab-mobile": ("portal", "programmatic"),
    "iab-medium": ("portal", "programmatic"),
    "iab-halfpage": ("portal", "programmatic"),
    "iab-skyscraper": ("portal", "programmatic"),
    "feed-1x1": ("instagram", "facebook", "linkedin"),
    "feed-4x5": ("instagram", "facebook"),
    "story-9x16": ("instagram", "facebook"),
    "reels-9x16": ("instagram", "tiktok", "youtube"),
    "shorts-9x16": ("youtube", "tiktok"),
    "linkedin-landscape": ("linkedin",),
}

PLATE_KIT_KEYS = (
    "iab-leaderboard",
    "iab-mobile",
    "iab-billboard",
    "iab-medium",
    "feed-1x1",
    "feed-4x5",
    "reels-9x16",
    "story-9x16",
    "iab-halfpage",
    "iab-skyscraper",
    "linkedin-landscape",
    "youtube-infeed",
    "video-linear-15",
    "shorts-9x16",
)

COMPOSITIONS = {
    "A": {
        "label": "Gancho → Benefício → Prova → CTA",
        "purposes": ("hook", "benefit", "proof", "cta"),
    },
    "B": {
        "label": "Problema → Solução → Experiência → CTA",
        "purposes": ("problem", "solution", "experience", "cta"),
    },
    "C": {
        "label": "Marca → Produto → Estilo → CTA",
        "purposes": ("brand", "product", "lifestyle", "cta"),
    },
    "D": {
        "label": "Pergunta → Descoberta → Benefício → CTA",
        "purposes": ("question", "discovery", "benefit", "cta"),
    },
}

COMPOSITIONS_5 = {
    "A": {
        "label": "Gancho → Contexto → Benefício → Prova → CTA",
        "purposes": ("hook", "context", "benefit", "proof", "cta"),
    },
    "B": {
        "label": "Problema → Contexto → Solução → Experiência → CTA",
        "purposes": ("problem", "context", "solution", "experience", "cta"),
    },
    "C": {
        "label": "Marca → Produto → Estilo → Prova → CTA",
        "purposes": ("brand", "product", "lifestyle", "proof", "cta"),
    },
    "D": {
        "label": "Pergunta → Descoberta → Benefício → Prova → CTA",
        "purposes": ("question", "discovery", "benefit", "proof", "cta"),
    },
}

SCENE_FILES = {
    "scene_01": "scene-01.html",
    "scene_02": "scene-02.html",
    "scene_03": "scene-03.html",
    "scene_04": "scene-04.html",
    "scene_05": "scene-03.html",
}

SCENE_TIMECODES = {
    4: {
        "scene_01": ("00:01 / 00:15", 8),
        "scene_02": ("00:04 / 00:15", 28),
        "scene_03": ("00:08 / 00:15", 55),
        "scene_04": ("00:12 / 00:15", 88),
    },
    5: {
        "scene_01": ("00:01 / 00:15", 6),
        "scene_02": ("00:03 / 00:15", 22),
        "scene_03": ("00:06 / 00:15", 42),
        "scene_04": ("00:09 / 00:15", 64),
        "scene_05": ("00:12 / 00:15", 88),
    },
}

QR_TIMECODES = {
    4: {"scene_03": ("00:09 / 00:15", 62), "scene_04": ("00:12 / 00:15", 88)},
    5: {"scene_04": ("00:09 / 00:15", 64), "scene_05": ("00:12 / 00:15", 88)},
}

END_CARD_PURPOSES = {"cta", "response"}
END_CARD_SCENES = {"scene_04", "scene_05"}
LOGO_ON_PURPOSES = {
    "brand",
}

PLATE_LAYOUTS = {
    "split": {
        "label": "Produto à direita",
        "note": "Tipo à esquerda. O produto flutua no preto. Sem moldura e sem chrome do canal.",
    },
    "hero": {
        "label": "Foto no quadro",
        "note": "O key visual ocupa o 16:9. O tipo lê sobre a esquerda escurecida.",
    },
    "center": {
        "label": "Cartão final",
        "note": "Marca e produto no eixo. Um verbo embaixo. É o still de fechamento.",
    },
}

PURPOSE_PLATES = {
    "hook": "split",
    "brand": "split",
    "problem": "split",
    "question": "split",
    "benefit": "split",
    "product": "split",
    "solution": "split",
    "proof": "hero",
    "lifestyle": "hero",
    "experience": "hero",
    "discovery": "hero",
    "context": "hero",
    "cta": "center",
    "response": "center",
}


def plate_for(purpose):
    key = str(purpose or "").strip().lower()
    return PURPOSE_PLATES.get(key) or "split"


LOGO_OFF_PURPOSES = {
    "product",
    "lifestyle",
    "proof",
    "experience",
    "discovery",
    "context",
    "benefit",
    "solution",
}


def last_scene_id(scene_count=None):
    try:
        count = int(scene_count or 0)
    except (TypeError, ValueError):
        count = 0
    if count >= 5:
        return "scene_05"
    if count == 4:
        return "scene_04"
    return ""


def is_end_card(purpose=None, scene_id=None, scene_count=None):
    if str(purpose or "").strip().lower() in END_CARD_PURPOSES:
        return True
    sid = str(scene_id or "").strip()
    last = last_scene_id(scene_count)
    if last:
        return sid == last
    return sid in END_CARD_SCENES and sid == "scene_05"


def logo_visible_for(purpose, scene_id=None, scene_count=None):
    if is_end_card(purpose, scene_id, scene_count):
        return True
    key = str(purpose or "").strip().lower()
    if key in LOGO_ON_PURPOSES:
        return True
    return False


ROLE_MAP = {
    "hook": "gancho",
    "context": "contexto",
    "benefit": "beneficio",
    "proof": "prova",
    "cta": "fechamento",
    "problem": "gancho",
    "solution": "beneficio",
    "experience": "prova",
    "brand": "gancho",
    "product": "contexto",
    "lifestyle": "prova",
    "question": "gancho",
    "discovery": "contexto",
    "response": "prova",
}

DEFAULT_COPY = {
    "hook": ("Sua história entra em cena.", "Abertura com marca e mensagem principal."),
    "context": ("O contexto ocupa o quadro.", "Segundo beat: o mundo da marca, sem oferta ainda."),
    "benefit": ("Mais contexto para a sua mensagem.", "Apresente benefício, universo e posicionamento."),
    "proof": ("Conteúdo que gera conexão.", "Momento emocional com uso real do produto ou serviço."),
    "cta": ("Finalize com uma ação clara.", "Call to action direto e fácil de entender."),
    "problem": ("O problema aparece na sala.", "Nomeie a tensão antes da marca resolver."),
    "solution": ("A marca entra como resposta.", "Mostre o valor sem complicar a leitura na TV."),
    "experience": ("A experiência ocupa o quadro.", "Uso real, ambiente e presença da marca."),
    "brand": ("A marca ocupa o primeiro segundo.", "Assinatura limpa, sem oferta ainda."),
    "product": ("O produto entra em cena.", "Objeto, tela ou detalhe reconhecível."),
    "lifestyle": ("O estilo de vida fecha o meio.", "Pessoa, cidade e hábito — sem site."),
    "question": ("Uma pergunta prende o quadro.", "Hook interrogativo, leitura imediata."),
    "discovery": ("A descoberta abre o benefício.", "Revele o que muda para quem assiste."),
    "response": ("Facilite a resposta do usuário.", "Reserve o QR e a continuação no mobile."),
}

CTA_DEFAULTS = {
    "video-linear-15": "Saiba mais",
    "video-cta-15": "Assista agora",
    "video-qr-15": "Acesse agora",
    "ctv-video-linear-30": "Saiba mais",
    "ctv-video-cta": "Assista agora",
    "ctv-video-qr": "Acesse agora",
    "iab-billboard": "Saiba mais",
    "iab-leaderboard": "Saiba mais",
    "iab-mobile": "Saiba mais",
    "iab-medium": "Saiba mais",
    "iab-halfpage": "Saiba mais",
    "iab-skyscraper": "Saiba mais",
    "feed-1x1": "Saiba mais",
    "feed-4x5": "Saiba mais",
    "story-9x16": "Saiba mais",
    "reels-9x16": "Assista",
    "shorts-9x16": "Assista",
    "linkedin-landscape": "Saiba mais",
    "youtube-infeed": "Assista",
}

OBJECTIVES = (
    "Reconhecimento",
    "Consideração",
    "Conversão",
    "Lançamento",
)


def clamp_scene_count(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 4
    return 5 if number == 5 else 4


def resolve_format_key(format_key):
    key = str(format_key or "").strip()
    return FORMAT_ALIASES.get(key, key)


def format_entry(format_key):
    key = resolve_format_key(format_key)
    for item in FORMATS:
        if item["key"] == key:
            return decorate_format(item)
    return None


def decorate_format(item):
    data = dict(item)
    data["channels"] = [
        dict(channel)
        for channel in CHANNELS
        if channel["key"] in FORMAT_CHANNELS.get(data["key"], ())
    ]
    data["channel_keys"] = list(FORMAT_CHANNELS.get(data["key"], ()))
    data["in_plate_kit"] = data["key"] in PLATE_KIT_KEYS
    return data


def plate_kit_formats():
    return [format_entry(key) for key in PLATE_KIT_KEYS if format_entry(key)]


def is_qr_format(format_key):
    key = resolve_format_key(format_key)
    return key.endswith("qr") or key.endswith("qr-15")


def is_cta_format(format_key):
    key = resolve_format_key(format_key)
    return "cta" in key


def composition_purposes(variant, scene_count=4):
    key = str(variant or "A").strip().upper()
    count = clamp_scene_count(scene_count)
    table = COMPOSITIONS_5 if count == 5 else COMPOSITIONS
    item = table.get(key) or table["A"]
    return list(item["purposes"])


def scene_timecode(scene_id, scene_count=4, qr=False):
    count = clamp_scene_count(scene_count)
    table = QR_TIMECODES[count] if qr and scene_id in QR_TIMECODES[count] else SCENE_TIMECODES[count]
    return table.get(scene_id) or SCENE_TIMECODES[count]["scene_01"]


def scene_duration(index, scene_count=4):
    count = clamp_scene_count(scene_count)
    if count == 5:
        return 3.0
    return 3.75 if index < 4 else 3.75


def catalog_payload():
    return {
        "family": "horizontal-15",
        "duration": DURATION_SECONDS,
        "scene_counts": list(SCENE_COUNTS),
        "formats": [decorate_format(item) for item in FORMATS],
        "format_groups": [dict(item) for item in FORMAT_GROUPS],
        "channels": [dict(item) for item in CHANNELS],
        "plate_formats": plate_kit_formats(),
        "adapters": dict(ADAPTERS),
        "objectives": list(OBJECTIVES),
        "plates": {
            key: dict(item)
            for key, item in PLATE_LAYOUTS.items()
        },
        "purpose_plates": dict(PURPOSE_PLATES),
        "compositions": {
            key: {"label": item["label"], "purposes": list(item["purposes"])}
            for key, item in COMPOSITIONS.items()
        },
        "compositions_5": {
            key: {"label": item["label"], "purposes": list(item["purposes"])}
            for key, item in COMPOSITIONS_5.items()
        },
        "intents": [
            {"key": "create", "label": "Criar"},
            {"key": "reconstruct", "label": "Recriar"},
            {"key": "adapt", "label": "Adaptar"},
            {"key": "refine", "label": "Refinar"},
            {"key": "html", "label": "HTML"},
        ],
        "packs": {
            "create": ["orchestrator", "create", "format", "implement", "validate"],
            "reconstruct": ["orchestrator", "reconstruct", "format", "implement", "validate"],
            "adapt": ["orchestrator", "create", "refine", "format", "implement", "validate"],
            "refine": ["orchestrator", "refine", "validate"],
            "html": ["orchestrator", "implement", "format", "validate"],
            "storyboard": ["orchestrator", "create", "refine", "format"],
        },
        "base_skills": [
            {"id": "create", "label": "Conceito", "locked": True},
            {"id": "implement", "label": "HTML", "locked": True},
            {"id": "video-15", "label": "Video 15s", "locked": True},
        ],
        "visual_skills": list_visual_skills(),
        "quote": {
            "prompt_passes": 2,
            "video": False,
            "image": False,
        },
    }
