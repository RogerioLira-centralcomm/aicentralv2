"""Catálogo de canais, praças e campos — espelho do PHP campaign-options."""

CHANNEL_CATALOG = {
    "google_ads": {"label": "Google Ads", "group": "performance", "desc": "Busca, Display, Performance Max"},
    "gpt_ads": {"label": "GPT ADS", "group": "performance", "desc": "Anúncios em respostas do ChatGPT"},
    "youtube": {"label": "YouTube", "group": "video", "desc": "Vídeos, Shorts, In-Stream"},
    "meta_ads": {"label": "Meta Ads", "group": "social", "desc": "Facebook, Instagram, Audience Network"},
    "tiktok": {"label": "TikTok", "group": "social", "desc": "Feed, TopView, Branded Hashtag"},
    "linkedin": {"label": "LinkedIn", "group": "social", "desc": "Feed, InMail, segmentação B2B"},
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
    "ooh": {"label": "OOH / Painéis", "group": "ooh", "desc": "Painéis digitais e mobiliário"},
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
    "praca": "exatamente nacional, interior, geolocalizada ou vazio.",
    "praca_detalhe": "as praças citadas: cidades, estados, raio.",
    "verba": "o valor como foi dito, incluindo periodicidade (ex.: \"R$ 80 mil por mês\").",
    "periodo": "datas ou duração (ex.: \"setembro e outubro de 2026\", \"90 dias\").",
    "canais": "array de ids do catálogo de canais.",
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
    "video": "Vídeo",
    "social": "Social",
    "programmatic": "Programática",
    "audio": "Áudio",
    "ctv": "CTV e streaming",
    "data": "Dados",
    "portais": "Portais",
    "ooh": "OOH",
}

CHANNEL_SHOWCASE = (
    "netflix", "prime_video", "disney", "hbo_max", "globoplay", "spotify",
    "youtube", "tiktok", "meta_ads", "linkedin", "google_ads", "dv360",
    "serasa", "gpt_ads", "g1", "uol", "cnn", "ooh",
)

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
        items = [(key, meta) for key, meta in CHANNEL_CATALOG.items() if meta.get("group") == group_key]
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
        return {"tom": "medio", "titulo": "Regular", "texto": "Complete os pontos ao lado antes de gerar."}
    return {"tom": "baixo", "titulo": "Incompleto", "texto": "Faltam informações importantes."}
