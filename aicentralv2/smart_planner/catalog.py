"""Catálogo de canais, praças e campos — espelho do PHP campaign-options."""

import re

CHANNEL_CATALOG = {
    "google_ads": {"label": "Google Ads", "group": "performance", "desc": "Busca, Display, Performance Max"},
    "gpt_ads": {"label": "GPT ADS", "group": "performance", "desc": "Anúncios em respostas do ChatGPT"},
    "youtube": {"label": "YouTube", "group": "video", "desc": "Vídeos, Shorts, In-Stream"},
    "meta_ads": {"label": "Meta Ads", "group": "social", "desc": "Facebook, Instagram, Audience Network"},
    "tiktok": {"label": "TikTok", "group": "social", "desc": "Feed, TopView, Branded Hashtag"},
    "linkedin": {"label": "LinkedIn", "group": "social", "desc": "Feed, InMail, segmentação B2B"},
    "uber": {"label": "Uber", "group": "apps", "desc": "Ambiente de mobilidade e deslocamento"},
    "99": {"label": "99", "group": "apps", "desc": "Ambiente de mobilidade e deslocamento"},
    "ifood": {"label": "iFood", "group": "apps", "desc": "Ambiente de pedidos e consumo"},
    "dv360": {"label": "Rede de portais e sites", "group": "programmatic", "desc": "Display e vídeo em portais e sites"},
    "spotify": {"label": "Spotify", "group": "audio", "desc": "Áudio, podcasts e display"},
    "netflix": {"label": "Netflix", "group": "ctv", "desc": "CTV no plano com anúncios"},
    "prime_video": {"label": "Prime Video", "group": "ctv", "desc": "CTV e patrocínio de conteúdo"},
    "disney": {"label": "Disney+", "group": "ctv", "desc": "CTV, ESPN e Star"},
    "hbo_max": {"label": "Max (HBO)", "group": "ctv", "desc": "CTV, filmes e esportes"},
    "globoplay": {"label": "Globoplay", "group": "ctv", "desc": "CTV, novelas e ao vivo"},
    "serasa": {"label": "Serasa (mídia)", "group": "data", "desc": "Display e mobile dentro do app Serasa"},
    "serasa_dados": {"label": "Serasa (dados)", "group": "data", "desc": "Segmentação de crédito", "tipo": "dados"},
    "g1": {"label": "G1", "group": "portais", "desc": "Notícias, display e native"},
    "uol": {"label": "UOL", "group": "portais", "desc": "Portal, display e native"},
    "r7": {"label": "R7", "group": "portais", "desc": "Portal, display e vídeo"},
    "cnn": {"label": "CNN Brasil", "group": "portais", "desc": "Notícias, display e vídeo"},
    "interativos": {
        "label": "Interativos",
        "group": "portais",
        "desc": "Hotspot, Quiz, Cube e outros formatos só em portais",
    },
    "places": {
        "label": "Places",
        "group": "places",
        "desc": "Aeroportos, shoppings e eventos — pontos e apps no sítio",
    },
    "ooh": {"label": "OOH / Painéis", "group": "ooh", "desc": "Painéis digitais e mobiliário"},
}

# One presentation format per channel. These defaults are a safe fallback for
# older plans; new plans receive an explicit recommendation from the generator.
# A video-shaped format is a planning instruction only. Smart Planner produces
# a static concept image and never invokes a video generator.
PRIMARY_FORMATS = {
    "google_ads": {"id": "responsive_search", "label": "Anúncio responsivo de pesquisa", "surface": "display"},
    "gpt_ads": {"id": "sponsored_answer_card", "label": "Card patrocinado em resposta", "surface": "display"},
    "youtube": {"id": "video_16_9_15s", "label": "Vídeo horizontal · 15s", "surface": "ctv", "duration_seconds": 15},
    "meta_ads": {"id": "vertical_9_16", "label": "Imagem vertical · 9:16", "surface": "app"},
    "tiktok": {"id": "video_9_16_15s", "label": "Vídeo vertical · 15s", "surface": "app", "duration_seconds": 15},
    "linkedin": {"id": "feed_1_1", "label": "Imagem de feed · 1:1", "surface": "app"},
    "uber": {"id": "display_in_app", "label": "Display no app · 1:1", "surface": "app"},
    "99": {"id": "display_in_app", "label": "Display no app · 1:1", "surface": "app"},
    "ifood": {"id": "display_in_app", "label": "Display no app · 1:1", "surface": "app"},
    "dv360": {"id": "display_300_250", "label": "Display · 300 × 250", "surface": "display"},
    "spotify": {"id": "audio_companion_1_1", "label": "Imagem companion · 1:1", "surface": "app"},
    "netflix": {"id": "ctv_16_9_30s", "label": "Vídeo CTV · 30s", "surface": "ctv", "duration_seconds": 30},
    "prime_video": {"id": "ctv_16_9_30s", "label": "Vídeo CTV · 30s", "surface": "ctv", "duration_seconds": 30},
    "disney": {"id": "ctv_16_9_30s", "label": "Vídeo CTV · 30s", "surface": "ctv", "duration_seconds": 30},
    "hbo_max": {"id": "ctv_16_9_30s", "label": "Vídeo CTV · 30s", "surface": "ctv", "duration_seconds": 30},
    "globoplay": {"id": "ctv_16_9_30s", "label": "Vídeo CTV · 30s", "surface": "ctv", "duration_seconds": 30},
    "serasa": {"id": "in_app_1_1", "label": "Imagem in-app · 1:1", "surface": "app"},
    "g1": {"id": "native_16_9", "label": "Native editorial · 16:9", "surface": "portal"},
    "uol": {"id": "native_16_9", "label": "Native editorial · 16:9", "surface": "portal"},
    "r7": {"id": "native_16_9", "label": "Native editorial · 16:9", "surface": "portal"},
    "cnn": {"id": "native_16_9", "label": "Native editorial · 16:9", "surface": "portal"},
    "interativos": {"id": "hotspot", "label": "Hotspot interativo", "surface": "portal"},
    "places": {"id": "place_landscape", "label": "Imagem no ponto · horizontal", "surface": "place"},
    "ooh": {"id": "dooh_landscape", "label": "Painel digital · horizontal", "surface": "display"},
}

PRACA_OPTIONS = {
    "nacional": {"label": "Nacional", "hint": "Cobertura Brasil inteiro"},
    "interior": {"label": "Interior", "hint": "Cidades do interior / interiorização"},
    "geolocalizada": {"label": "Geolocalizada", "hint": "Cidades, UFs, raios ou polígonos"},
}

DEVICE_OPTIONS = {
    "mobile": "Mobile",
    "desktop": "Desktop",
    "tv": "TV / CTV",
    "paineis": "Painéis de rua / OOH",
}

OBJETIVO_OPTIONS = {
    "reconhecimento": "Reconhecimento",
    "consideracao": "Consideração",
    "conversao": "Conversão",
    "trafego": "Tráfego",
    "leads": "Leads",
    "vendas": "Vendas",
    "retencao": "Retenção",
}

FIELD_SCHEMA = {
    "campanha": "nome da campanha ou do que está sendo anunciado. Vazio se não houver.",
    "cliente": "anunciante (marca que anuncia). Em briefing de agência, a palavra cliente = anunciante. Vazio se o material não nomear. Nunca use 'clientes da marca' aqui — isso é público.",
    "agencia": "agência que representa o anunciante. Vazio se o anunciante for direto.",
    "objetivo": "um de: reconhecimento, consideracao, conversao, trafego, leads, vendas, retencao. Vazio se não der para dizer.",
    "objetivo_texto": "o objetivo como o anunciante descreveu, com as palavras dele.",
    "contexto": "o que motivou a campanha: momento, histórico, concorrência, sazonalidade.",
    "publico": "quem precisa ser impactado, em texto corrido: comportamento, consumo de mídia, momento de vida ou de compra.",
    "audiencia_modelada": "objeto com segmentos, faixa_etaria, genero, classe_social, regiao, bairro, universo_estimado e impacto_estimado; cada número precisa ter fonte ou status a_validar.",
    "praca": "exatamente nacional, interior, geolocalizada ou vazio.",
    "praca_detalhe": "as praças citadas: cidades, estados, raio.",
    "verba": "o valor como foi dito, incluindo periodicidade (ex.: \"R$ 80 mil por mês\").",
    "periodo": "datas ou duração (ex.: \"setembro e outubro de 2026\", \"90 dias\").",
    "canais": "array de ids do catálogo de canais.",
    "places": "array de {slug, point_ids, apps} só com slugs e pontos do catálogo injetado. Vazio se o material não citar um venue publicado.",
    "interativos": "objeto {formats: []} só se um portal (g1, uol, r7, cnn) estiver nos canais. Formatos: hotspot, cartas, quiz, cube, scratch, 360, countdown, video.",
    "criativos": "materiais disponíveis ou possíveis: formatos, durações, restrições.",
    "dispositivos": "array de ids de dispositivos/superfícies.",
    "kpis": "array de métricas de sucesso citadas.",
    "observacoes": "toda informação relevante sem campo próprio.",
    "nao_informado": "array com os nomes dos campos que o anunciante disse não ter.",
}

PLAN_MODES = ("completo", "one_page")

PLAN_MODE_LABELS = {
    "completo": "Plano completo",
    "one_page": "Página única",
}

CHANNEL_GROUPS = {
    "performance": "Performance",
    "social": "Social",
    "apps": "Apps e mobilidade",
    "video": "Vídeo",
    "ctv": "CTV e streaming",
    "portais": "Portais",
    "places": "Places",
    "programmatic": "Programática",
    "audio": "Áudio",
    "data": "Dados",
    "ooh": "OOH",
}

CHANNEL_SHOWCASE = (
    "google_ads", "gpt_ads", "meta_ads", "tiktok", "linkedin",
    "youtube", "netflix", "prime_video", "disney", "hbo_max", "globoplay",
    "g1", "uol", "r7", "cnn", "interativos", "places",
    "uber", "99", "ifood", "dv360", "spotify", "serasa", "serasa_dados", "ooh",
)

PORTAL_CHANNELS = ("g1", "uol", "r7", "cnn")
SPECIAL_MIX_IDS = frozenset({"places", "interativos"})
SPECIAL_SUGGESTED_PCT = 8
DEFAULT_PERIOD = "30 dias"
DEFAULT_VERBA = "A fechar"

INTERATIVOS_FORMATS = (
    {"id": "hotspot", "label": "Hotspot"},
    {"id": "cartas", "label": "Cartas"},
    {"id": "quiz", "label": "Quiz"},
    {"id": "cube", "label": "Cube"},
    {"id": "scratch", "label": "Scratch"},
    {"id": "360", "label": "360"},
    {"id": "countdown", "label": "Countdown"},
    {"id": "video", "label": "Vídeo"},
)

CHANNEL_LOGOS = {
    "google_ads": "/static/images/canais/google-dv360.svg",
    "gpt_ads": "",
    "youtube": "/static/images/creative-viewers/youtube.svg",
    "meta_ads": "/static/images/creative-viewers/facebook.svg",
    "tiktok": "/static/images/canais/tiktok.png",
    "linkedin": "/static/images/creative-viewers/linkedin.svg",
    "uber": "",
    "99": "",
    "ifood": "",
    "dv360": "/static/images/canais/google-dv360.svg",
    "spotify": "/static/images/canais/spotify.svg",
    "netflix": "/static/images/creative-viewers/netflix.png",
    "prime_video": "/static/images/creative-viewers/prime-video.svg",
    "disney": "/static/images/creative-viewers/disney-plus.png",
    "hbo_max": "/static/images/canais/hbo-max.svg",
    "globoplay": "/static/images/canais/globoplay.png",
    "serasa": "/static/images/canais/experian-portal.png",
    "serasa_dados": "/static/images/canais/experian-portal.png",
    "g1": "/static/images/canais/g1-globo.svg",
    "uol": "/static/images/canais/uol.png",
    "r7": "/static/images/canais/r7.png",
    "cnn": "/static/images/creative-viewers/cnn-brasil.svg",
    "interativos": "/static/images/canais/interativos.svg",
    "places": "",
    "ooh": "/static/images/canais/eletromidia.svg",
}

GROUP_KPIS = {
    "performance": ("Cliques", "CPC", "Conversões"),
    "social": ("Alcance", "CTR", "CPL"),
    "video": ("Visualizações", "CPV"),
    "ctv": ("Visualizações", "CPV"),
    "portais": ("Impressões", "Viewability", "Interação"),
    "places": ("Alcance no sítio", "Apps no ponto", "Endereço 4 semanas"),
    "programmatic": ("Impressões", "Viewability", "CTR"),
    "audio": ("Listeners", "Frequência"),
    "data": ("Cobertura da base", "Match rate"),
    "apps": ("Alcance", "Frequência", "Ações"),
    "ooh": ("Alcance de rua", "OTS", "Frequência"),
}

WIZARD_STEPS = (
    {"id": "briefing", "title": "Importar briefing", "hint": "Texto, URL, PDF ou imagem"},
    {"id": "revisao", "title": "Revisar briefing", "hint": "Narrativa, orçamento e mix"},
    {"id": "conclusao", "title": "Documentos", "hint": "Página única ou plano completo"},
)

WIZARD_TRAIL = WIZARD_STEPS

RESUME_ACTIONS = {
    "briefing": "Continuar briefing",
    "revisao": "Gerar documentos",
    "conclusao": "Ver documentos",
    "canvas": "Abrir quadro",
}

RESUME_STATUS = {
    "briefing": "Em briefing",
    "revisao": "Em revisão",
    "conclusao": "Documentos prontos",
}


def plan_mode_label(mode: str) -> str:
    return PLAN_MODE_LABELS.get((mode or "").strip().lower(), PLAN_MODE_LABELS["completo"])


def resume_action(step: str, mode: str = "") -> str:
    mode = (mode or "").strip().lower()
    if step == "canvas":
        return "Abrir folha" if mode == "one_page" else "Abrir quadro"
    return RESUME_ACTIONS.get(step, "Abrir")


def resume_status(step: str, mode: str = "") -> str:
    mode = (mode or "").strip().lower()
    if step == "canvas":
        return "Folha pronta" if mode == "one_page" else "Quadro pronto"
    return RESUME_STATUS.get(step, "Em briefing")


def channels_by_group() -> list[tuple[str, str, list[tuple[str, dict]]]]:
    grouped = []
    for group_key, group_label in CHANNEL_GROUPS.items():
        items = []
        for key, meta in CHANNEL_CATALOG.items():
            if meta.get("group") != group_key:
                continue
            items.append((key, {**meta, "logo": CHANNEL_LOGOS.get(key, "")}))
        if items:
            grouped.append((group_key, group_label, items))
    return grouped


def channel_label(key: str) -> str:
    return CHANNEL_CATALOG.get(key, {}).get("label", key)


def media_channel_keys() -> list[str]:
    return [key for key, meta in CHANNEL_CATALOG.items() if meta.get("tipo") != "dados"]


def objetivo_label(value: str) -> str:
    return OBJETIVO_OPTIONS.get((value or "").strip().lower(), value or "")


def score_label(score: int) -> dict:
    try:
        score = int(score or 0)
    except (TypeError, ValueError):
        score = 0
    if score >= 85:
        return {"tom": "alto", "titulo": "Excelente", "texto": "Seu briefing está claro e completo."}
    if score >= 70:
        return {"tom": "alto", "titulo": "Muito bom", "texto": "Seu briefing está claro e completo."}
    if score >= 55:
        return {"tom": "medio", "titulo": "Bom", "texto": "Dá para gerar, mas ainda cabe detalhe."}
    if score >= 35:
        return {"tom": "medio", "titulo": "Regular", "texto": "Dá para gerar. Falta só fechar o que ainda está vazio."}
    return {"tom": "baixo", "titulo": "Incompleto", "texto": "Dá para gerar. Falta só preencher o essencial."}


def channel_logo(key: str) -> str:
    return CHANNEL_LOGOS.get(key, "")


def group_kpis_for(canais) -> list[str]:
    seen = []
    for key in canais or []:
        group = (CHANNEL_CATALOG.get(key) or {}).get("group")
        for item in GROUP_KPIS.get(group, ()):
            if item not in seen:
                seen.append(item)
    return seen


def apply_review_defaults(campos: dict) -> dict:
    out = dict(campos or {})
    if not str(out.get("periodo") or "").strip():
        out["periodo"] = DEFAULT_PERIOD
    if not str(out.get("verba") or "").strip():
        out["verba"] = DEFAULT_VERBA
        if not str(out.get("verba_base") or "").strip():
            out["verba_base"] = "mensal"
    return out


def review_score(campos: dict) -> int:
    data = campos or {}
    verba = str(data.get("verba") or "").strip().lower()
    # "A fechar"/"A definir" são estados editoriais, não orçamento informado.
    has_verba = bool(re.search(r"\d", verba)) and verba not in {"a fechar", "a definir", "não definida", "nao definida"}
    checks = (
        bool(str(data.get("campanha") or "").strip()),
        bool(str(data.get("objetivo") or "").strip()),
        bool(str(data.get("publico") or "").strip()),
        has_verba,
        bool(str(data.get("periodo") or "").strip()),
        bool(str(data.get("praca") or "").strip()),
        bool([item for item in (data.get("kpis") or []) if str(item).strip()]),
        bool(data.get("canais")),
    )
    return int(round(100 * sum(1 for item in checks if item) / len(checks)))
