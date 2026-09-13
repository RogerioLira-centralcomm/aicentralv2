"""Catálogo comercial de canais para o CRM v3.

Lê `cadu_canais` e `cadu_formatos` quando a base responde. Se o banco
não estiver no request (testes, mock), devolve o fallback com os mesmos
campos que a sidebar e o gerador esperam.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


CANAIS_MIDIA = (
    "Netflix", "Spotify", "Serasa", "Disney", "HBO", "Amazon",
    "iFood", "Uber", "99", "Logan", "Interativos",
)

CANAIS_EXCLUIDOS = frozenset({"the-trade-desk", "telegram", "ttd"})

GRUPOS = (
    "Portais",
    "Streaming",
    "Mobilidade",
    "Sociais",
    "Dados",
    "Programática",
    "DOOH",
    "Interativos",
)

_GRUPO_POR_SLUG = {
    "g1-globo": "Portais",
    "r7": "Portais",
    "uol": "Portais",
    "cnn-brasil": "Portais",
    "sbt": "Portais",
    "experian-portal": "Portais",
    "tudogostoso": "Portais",
    "techtudo": "Portais",
    "ge-globo-esporte": "Portais",
    "infomoney": "Portais",
    "netflix": "Streaming",
    "globoplay": "Streaming",
    "paramount-plus": "Streaming",
    "samsung-tv-plus": "Streaming",
    "disney-plus": "Streaming",
    "prime-video": "Streaming",
    "hbo-max": "Streaming",
    "spotify": "Streaming",
    "deezer": "Streaming",
    "amazon-music": "Streaming",
    "podcast-ads": "Streaming",
    "waze": "Mobilidade",
    "ifood": "Mobilidade",
    "uber": "Mobilidade",
    "99": "Mobilidade",
    "logan": "Mobilidade",
    "youtube": "Sociais",
    "instagram": "Sociais",
    "tiktok": "Sociais",
    "linkedin": "Sociais",
    "kwai": "Sociais",
    "twitch": "Sociais",
    "serasa": "Dados",
    "experian-dmp": "Dados",
    "google-dv360": "Programática",
    "eletromidia": "DOOH",
    "interativos": "Interativos",
}

DISPOSITIVOS = ("ctv", "mobile", "desktop", "tablet", "audio", "app", "ooh")
DISPOSITIVO_LABEL = {
    "ctv": "CTV",
    "mobile": "mobile",
    "desktop": "desktop",
    "tablet": "tablet",
    "audio": "áudio",
    "app": "app",
    "ooh": "OOH",
}
_DISPOSITIVOS_POR_TIPO = {
    "audio": ["audio", "mobile"],
    "ctv": ["ctv"],
    "video": ["ctv", "mobile"],
    "social": ["mobile"],
    "portal": ["desktop", "mobile"],
    "programatica": ["desktop", "mobile", "ctv"],
    "ooh": ["ooh"],
    "gaming": ["desktop", "mobile"],
    "mobile": ["mobile", "app"],
    "messaging": ["mobile"],
    "data": ["desktop", "mobile"],
    "interativo": ["desktop", "mobile"],
}
_DISPOSITIVOS_POR_CHAVE = {
    "ctv-16x9": ["ctv"],
    "story-9x16": ["mobile"],
    "audio-bar": ["audio", "mobile"],
    "feed-1x1": ["mobile"],
    "feed-4x5": ["mobile"],
    "iab-mobile": ["mobile"],
    "linkedin-landscape": ["desktop", "mobile"],
    "iab-billboard": ["desktop"],
    "iab-leaderboard": ["desktop", "mobile"],
    "iab-medium": ["desktop", "mobile"],
}

SERASA_KIT_2027 = {
    "titulo": "Serasa Ads e Centralcomm — 2027",
    "tipo": "apresentacao",
    "url": (
        "https://docs.google.com/presentation/d/"
        "1FU_nO_iHRGIOG4qW2XG3iuaNZyrjlqOJ_XqDiT5ILzI/edit"
    ),
    "fatos": [
        "Parceria exclusiva MG e RJ",
        "+100M CPFs 18+ cadastrados",
        "+10,2M CNPJs totais médios/mês",
        "+500 segmentações 1st e 3rd party",
        "Score, histórico de pagador, intenção de compra, renda presumida",
    ],
    "cortes": [
        "Imóveis RJ, score 500+, classe ABC, 30 dias: ECS 190.970 / Meta 1.514.181 / TikTok 58.035",
        "Automotivo RJ, score 500+, ABC: ECS 426.770 / Meta 4.061.559 / TikTok 102.218",
        "Viajantes RJ, score 500+, ABC: ECS 502.190 / Meta 1.211.725 / TikTok 40.296",
        "Nação do Futebol RJ: ECS 253.591 / Meta 1.423.062 / TikTok 71.435",
    ],
}

INTERATIVOS_FALLBACK = [
    {"nome": "Cube", "taxa": "3-6%", "tempo": "15-30s", "melhor_para": "storytelling, produto", "extra": "4x vs display", "chave": "iab-medium", "w": 300, "h": 250, "label": "300×250", "dispositivos": ["desktop", "mobile"]},
    {"nome": "Scratch", "taxa": "5-10%", "tempo": "10-20s", "melhor_para": "cupom, gamificação", "extra": "6x vs display", "chave": "iab-medium", "w": 300, "h": 250, "label": "300×250", "dispositivos": ["desktop", "mobile"]},
    {"nome": "Hot Spots", "taxa": "3-6%", "tempo": "15-30s", "melhor_para": "imóveis, decoração", "extra": "", "chave": "iab-medium", "w": 300, "h": 250, "label": "300×250", "dispositivos": ["desktop", "mobile"]},
    {"nome": "360° Viewer", "taxa": "4-7%", "tempo": "20-40s", "melhor_para": "imóveis, turismo", "extra": "5x vs display", "chave": "iab-medium", "w": 300, "h": 250, "label": "300×250", "dispositivos": ["desktop", "mobile"]},
    {"nome": "Poll / Quiz", "taxa": "6-12%", "tempo": "15-30s", "melhor_para": "first-party data", "extra": "8x vs display", "chave": "iab-medium", "w": 300, "h": 250, "label": "300×250", "dispositivos": ["desktop", "mobile"]},
    {"nome": "Countdown", "taxa": "2-4%", "tempo": "5-10s", "melhor_para": "lançamentos", "extra": "", "chave": "iab-medium", "w": 300, "h": 250, "label": "300×250", "dispositivos": ["desktop", "mobile"]},
    {"nome": "Video Interactive", "taxa": "4-8%", "tempo": "20-45s", "melhor_para": "demo", "extra": "5x vs display", "chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "16:9", "dispositivos": ["ctv", "mobile"]},
]

_FORMAT_DEFAULT = {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}
_FORMAT_BY_TIPO = {
    "audio": {"chave": "audio-bar", "w": 728, "h": 90, "label": "15s/30s"},
    "ctv": {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "16:9"},
    "video": {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "16:9"},
    "social": {"chave": "feed-1x1", "w": 1080, "h": 1080, "label": "1:1"},
    "portal": {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"},
    "programatica": {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"},
    "ooh": {"chave": "iab-billboard", "w": 970, "h": 250, "label": "970×250"},
    "gaming": {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "16:9"},
    "mobile": {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"},
    "messaging": {"chave": "feed-4x5", "w": 1080, "h": 1350, "label": "4:5"},
    "data": {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "Audiência"},
    "interativo": {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"},
}
_FORMAT_LOOKUP = (
    ("sponsored playlist", {"chave": "audio-bar", "w": 728, "h": 90, "label": "Playlist"}),
    ("sponsored sessions", {"chave": "audio-bar", "w": 728, "h": 90, "label": "Sessão"}),
    ("host-read", {"chave": "audio-bar", "w": 728, "h": 90, "label": "Host-read"}),
    ("podcast ads", {"chave": "audio-bar", "w": 728, "h": 90, "label": "Podcast"}),
    ("audio ads", {"chave": "audio-bar", "w": 728, "h": 90, "label": "15s/30s"}),
    ("alexa", {"chave": "audio-bar", "w": 728, "h": 90, "label": "Alexa"}),
    ("video takeover", {"chave": "iab-billboard", "w": 970, "h": 250, "label": "970×250"}),
    ("trueview", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "In-stream"}),
    ("bumper", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "6s"}),
    ("shorts", {"chave": "story-9x16", "w": 1080, "h": 1920, "label": "9:16"}),
    ("stories", {"chave": "story-9x16", "w": 1080, "h": 1920, "label": "9:16"}),
    ("reels", {"chave": "story-9x16", "w": 1080, "h": 1920, "label": "9:16"}),
    ("topview", {"chave": "story-9x16", "w": 1080, "h": 1920, "label": "9:16"}),
    ("spark ads", {"chave": "story-9x16", "w": 1080, "h": 1920, "label": "9:16"}),
    ("splash", {"chave": "story-9x16", "w": 1080, "h": 1920, "label": "9:16"}),
    ("in-feed", {"chave": "feed-1x1", "w": 1080, "h": 1080, "label": "1:1"}),
    ("feed ads", {"chave": "feed-1x1", "w": 1080, "h": 1080, "label": "1:1"}),
    ("shopping", {"chave": "feed-1x1", "w": 1080, "h": 1080, "label": "1:1"}),
    ("explore ads", {"chave": "feed-4x5", "w": 1080, "h": 1350, "label": "4:5"}),
    ("discovery", {"chave": "feed-4x5", "w": 1080, "h": 1350, "label": "4:5"}),
    ("message ads", {"chave": "feed-4x5", "w": 1080, "h": 1350, "label": "Inbox"}),
    ("sponsored messages", {"chave": "feed-4x5", "w": 1080, "h": 1350, "label": "Inbox"}),
    ("sponsored content", {"chave": "linkedin-landscape", "w": 1200, "h": 627, "label": "1.91:1"}),
    ("dynamic ads", {"chave": "feed-1x1", "w": 1080, "h": 1080, "label": "1:1"}),
    ("text ads", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "Texto"}),
    ("pause ads", {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}),
    ("pre-roll", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "Pre-roll"}),
    ("mid-roll", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "Mid-roll"}),
    ("video ads", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "16:9"}),
    ("video interactive", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "16:9"}),
    ("masthead", {"chave": "iab-billboard", "w": 970, "h": 250, "label": "Masthead"}),
    ("takeover", {"chave": "iab-billboard", "w": 970, "h": 250, "label": "970×250"}),
    ("home screen", {"chave": "iab-billboard", "w": 970, "h": 250, "label": "Home"}),
    ("first screen", {"chave": "iab-billboard", "w": 970, "h": 250, "label": "First screen"}),
    ("native", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "728×90"}),
    ("rich media", {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}),
    ("display", {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}),
    ("branded content", {"chave": "linkedin-landscape", "w": 1200, "h": 627, "label": "1.91:1"}),
    ("branded recipes", {"chave": "feed-4x5", "w": 1080, "h": 1350, "label": "Receita"}),
    ("branded hashtag", {"chave": "story-9x16", "w": 1080, "h": 1920, "label": "9:16"}),
    ("branded effects", {"chave": "story-9x16", "w": 1080, "h": 1920, "label": "Efeito"}),
    ("branded podcast", {"chave": "audio-bar", "w": 728, "h": 90, "label": "Branded"}),
    ("newsletter", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "E-mail"}),
    ("webinars", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "Webinar"}),
    ("push notification", {"chave": "iab-mobile", "w": 320, "h": 50, "label": "320×50"}),
    ("e-mail", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "E-mail"}),
    ("lookalike", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "Lookalike"}),
    ("custom segments", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "Segmento"}),
    ("data enrichment", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "CRM match"}),
    ("audiências", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "DMP"}),
    ("pins", {"chave": "iab-medium", "w": 300, "h": 250, "label": "Pin"}),
    ("arrow", {"chave": "iab-medium", "w": 300, "h": 250, "label": "Seta"}),
    ("search ads", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "Busca"}),
    ("live ads", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "Ao vivo"}),
    ("homepage carousel", {"chave": "iab-billboard", "w": 970, "h": 250, "label": "Carousel"}),
    ("premium video", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "16:9"}),
    ("hot spots", {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}),
    ("360", {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}),
    ("scratch", {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}),
    ("countdown", {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}),
    ("poll", {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}),
    ("cube", {"chave": "iab-medium", "w": 300, "h": 250, "label": "300×250"}),
    ("ctv", {"chave": "ctv-16x9", "w": 1920, "h": 1080, "label": "16:9"}),
    ("dooh", {"chave": "iab-billboard", "w": 970, "h": 250, "label": "DOOH"}),
    ("audio", {"chave": "audio-bar", "w": 728, "h": 90, "label": "Áudio"}),
    ("in-app", {"chave": "feed-1x1", "w": 1080, "h": 1080, "label": "In-app"}),
    ("receipt", {"chave": "iab-leaderboard", "w": 728, "h": 90, "label": "Recibo"}),
    ("cupom", {"chave": "feed-1x1", "w": 1080, "h": 1080, "label": "Cupom"}),
)

_ASSISTENTE_POR_TIPO = {
    "audio": {
        "quando": "Branding com atenção alta e completion — o anúncio não se pula.",
        "passos": [
            "Mostre completion e tempo de escuta, não só alcance.",
            "Peça o momento (treino, foco, deslocamento) e o objetivo da campanha.",
            "Feche um teste com áudio 15s/30s antes de playlist patrocinada.",
        ],
        "evitar": "Tratar áudio como display barato. Sem skip, o criativo precisa ser curto.",
        "proximo_passo": "Agendar apresentação com referência de 15s e mínimo de verba.",
    },
    "ctv": {
        "quando": "Awareness premium, brand safety e conclusão de vídeo.",
        "passos": [
            "Abra com viewability e completion — o número que o portal não entrega.",
            "Pergunte título, gênero ou faixa horária que o cliente quer associar.",
            "Deixe o mínimo claro e ofereça um bloco, não um CPM solto.",
        ],
        "evitar": "Comparar CTV com YouTube só por preço. O ambiente e o skip são outros.",
        "proximo_passo": "Marcar reunião de apresentação com a ficha e o deck do canal.",
    },
    "video": {
        "quando": "Alcance de vídeo com intenção de busca ou descoberta.",
        "passos": [
            "Separe in-stream, shorts e discovery — cada um tem um job.",
            "Pergunte se o cliente já tem criativo 6s, 15s e 9:16.",
            "Sugira um teste curto antes de masthead.",
        ],
        "evitar": "Vender só alcance sem formato. Shorts e bumper não substituem in-stream.",
        "proximo_passo": "Gerar um roteiro de apresentação com os formatos e o mínimo.",
    },
    "social": {
        "quando": "Alcance, consideração ou conversão com criativo nativo do feed.",
        "passos": [
            "Mostre o formato (1:1, 4:5, 9:16) antes do CPM.",
            "Pergunte objetivo: awareness, tráfego ou venda.",
            "Traga uma segmentação concreta (interesse, lookalike, base).",
        ],
        "evitar": "Prometer o mesmo criativo em todos os cortes. Reels não é feed.",
        "proximo_passo": "Abrir a sessão de formatos e marcar uma apresentação.",
    },
    "portal": {
        "quando": "Contexto editorial, cobertura nacional ou recorte de nicho.",
        "passos": [
            "Mostre pageviews e o recorte (notícia, esporte, finanças).",
            "Ofereça display + native ou takeover — não só banner.",
            "Pergunte praça e se precisa de branded.",
        ],
        "evitar": "Vender portal como programática genérica. O contexto é o produto.",
        "proximo_passo": "Enviar a ficha e agendar apresentação do inventário.",
    },
    "data": {
        "quando": "O cliente precisa de intenção real, score ou recorte financeiro.",
        "passos": [
            "Mostre o recorte (CPF, score, renda, corte de praça), não o catálogo inteiro.",
            "Compare o universo do canal com Meta/TikTok do mesmo corte.",
            "Peça o vertical (imóvel, auto, crédito) para trazer um número.",
        ],
        "evitar": "Falar em 'dados' sem um corte. Sem recorte, vira DMP genérica.",
        "proximo_passo": "Abrir a sessão de segmentação e marcar a apresentação do kit.",
    },
    "programatica": {
        "quando": "Escala em display, vídeo, CTV ou DOOH com otimização.",
        "passos": [
            "Pergunte se o cliente já tem DSP ou se precisa de operação.",
            "Separe open auction de PMP premium.",
            "Feche um piloto com um objetivo (viewability, conclusão ou visita).",
        ],
        "evitar": "Prometer o inventário todo no mesmo CPM.",
        "proximo_passo": "Montar um piloto com um formato e um KPI.",
    },
    "ooh": {
        "quando": "Presença urbana, trajeto ou impacto em pontos premium.",
        "passos": [
            "Mostre o ponto (elevador, metrô, aeroporto) e o perfil do fluxo.",
            "Pergunte cidade e período.",
            "Ofereça um circuito, não uma tela isolada.",
        ],
        "evitar": "Vender DOOH como banner digital. O ponto é o produto.",
        "proximo_passo": "Levar o mapa de inventário na reunião.",
    },
    "gaming": {
        "quando": "Público jovem e sessão longa, difícil de achar em TV aberta.",
        "passos": [
            "Fale tempo de sessão e comunidade, não só UU.",
            "Pergunte se a marca aguenta live e chat.",
            "Ofereça pre-roll ou branded com criador.",
        ],
        "evitar": "Tratar Twitch como YouTube. A sessão e o tom são outros.",
        "proximo_passo": "Agendar apresentação com um exemplo de integração.",
    },
    "mobile": {
        "quando": "Drive-to-store ou momento de deslocamento.",
        "passos": [
            "Mostre o formato no mapa (pin, seta, takeover em parada).",
            "Pergunte loja, praça e raio.",
            "Feche um teste de visita, não só impressão.",
        ],
        "evitar": "Vender Waze como display mobile genérico.",
        "proximo_passo": "Levar um recorte de lojas e agendar a apresentação.",
    },
    "messaging": {
        "quando": "Audiência técnica ou recorte de canais públicos.",
        "passos": [
            "Explique que o anúncio vive no canal, não no inbox privado.",
            "Pergunte o tema (finanças, tech, cripto).",
            "Ofereça um teste curto de sponsored message.",
        ],
        "evitar": "Prometer remarketing clássico. Aqui o contexto manda.",
        "proximo_passo": "Gerar um texto de apresentação e marcar follow-up.",
    },
    "interativo": {
        "quando": "O cliente precisa de tempo na peça, não só impressão.",
        "passos": [
            "Escolha o formato pelo job: Hot Spots para imóvel, Poll para dado, Cube para produto.",
            "Mostre taxa e tempo de interação versus display.",
            "Feche como add-on em portal ou programática.",
        ],
        "evitar": "Empilhar todos os formatos na mesma campanha.",
        "proximo_passo": "Abrir a sessão de formatos e indicar um para o vertical do cliente.",
    },
}

_SEG_KEYWORDS = (
    "segmenta", "target", "classe", "público", "score", "b2b", "feminina",
    "jovem", "gen z", "intenção", "momento", "time", "regional", "decisor",
    "renda", "lookalike", "primeiro", "acr", "operadora",
)


_CATALOG_PATH = Path(__file__).with_name("crm_v3_canais_catalog.json")
_LOGOS_DIR = Path(__file__).resolve().parent / "static" / "images" / "canais"
_VIEWERS_DIR = "/static/images/creative-viewers"
_CANAIS_DIR = "/static/images/canais"

_LOCAL_LOGOS = {
    "netflix": f"{_VIEWERS_DIR}/netflix.png",
    "disney-plus": f"{_VIEWERS_DIR}/disney-plus.png",
    "hbo-max": f"{_VIEWERS_DIR}/hbo-max.png",
    "prime-video": f"{_VIEWERS_DIR}/prime-video.svg",
    "g1-globo": f"{_VIEWERS_DIR}/g1.svg",
    "youtube": f"{_VIEWERS_DIR}/youtube.svg",
    "instagram": f"{_VIEWERS_DIR}/instagram.svg",
    "tiktok": f"{_VIEWERS_DIR}/tiktok.svg",
    "linkedin": f"{_VIEWERS_DIR}/linkedin.svg",
    "cnn-brasil": f"{_VIEWERS_DIR}/cnn-brasil.svg",
    "sbt": f"{_VIEWERS_DIR}/sbt-news.svg",
}
_LOGO_ALIAS = {
    "experian-dmp": "experian-portal",
}


def _index_canais_logos() -> Dict[str, str]:
    mapping = dict(_LOCAL_LOGOS)
    if _LOGOS_DIR.is_dir():
        for path in sorted(_LOGOS_DIR.iterdir()):
            if path.suffix.lower() in {".png", ".svg", ".jpg", ".jpeg", ".webp"}:
                mapping[path.stem] = f"{_CANAIS_DIR}/{path.name}"
    for slug, alvo in _LOGO_ALIAS.items():
        if alvo in mapping:
            mapping[slug] = mapping[alvo]
    return mapping


_RESOLVED_LOGOS = _index_canais_logos()


def _resolver_logo(slug: str, logo_path: str = "") -> str:
    global _RESOLVED_LOGOS
    encontrado = _RESOLVED_LOGOS.get(slug or "") or (logo_path or "")
    if encontrado:
        return encontrado
    _RESOLVED_LOGOS = _index_canais_logos()
    return _RESOLVED_LOGOS.get(slug or "") or (logo_path or "")


def _lookup_formato(nome: str, tipo: str = "") -> Dict[str, Any]:
    texto = (nome or "").casefold()
    escolhido = None
    tamanho = 0
    for needle, meta in _FORMAT_LOOKUP:
        if needle in texto and len(needle) > tamanho:
            escolhido = meta
            tamanho = len(needle)
    if not escolhido:
        escolhido = _FORMAT_BY_TIPO.get(tipo or "") or _FORMAT_DEFAULT
    return dict(escolhido)


def _normalizar_dispositivos(raw: Any, *, tipo: str = "", chave: str = "") -> List[str]:
    seen = []
    for item in raw if isinstance(raw, (list, tuple)) else []:
        key = str(item or "").strip().casefold()
        aliases = {"tv": "ctv", "smart tv": "ctv", "connected tv": "ctv", "celular": "mobile", "app": "app"}
        key = aliases.get(key, key)
        if key in DISPOSITIVOS and key not in seen:
            seen.append(key)
    if seen:
        return seen
    if chave in _DISPOSITIVOS_POR_CHAVE:
        return list(_DISPOSITIVOS_POR_CHAVE[chave])
    return list(_DISPOSITIVOS_POR_TIPO.get(tipo or "") or ["desktop", "mobile"])


def rotulo_dispositivos(dispositivos: Any) -> str:
    labels = [DISPOSITIVO_LABEL.get(item, item) for item in (dispositivos or []) if item]
    return " · ".join(labels)


def _normalizar_formato(fmt: Any, tipo: str = "") -> Dict[str, Any]:
    if isinstance(fmt, str):
        base = _lookup_formato(fmt, tipo)
        return {
            "nome": fmt,
            "chave": base["chave"],
            "w": base["w"],
            "h": base["h"],
            "label": base["label"],
            "melhor_para": "",
            "dispositivos": _normalizar_dispositivos([], tipo=tipo, chave=base["chave"]),
        }
    if not isinstance(fmt, dict):
        return {}
    nome = str(fmt.get("nome") or "").strip()
    base = _lookup_formato(nome, tipo) if nome else dict(_FORMAT_BY_TIPO.get(tipo or "") or _FORMAT_DEFAULT)
    chave = fmt.get("chave") or base.get("chave") or "iab-medium"
    out = {
        "nome": nome,
        "chave": chave,
        "w": fmt.get("w") or base.get("w") or 300,
        "h": fmt.get("h") or base.get("h") or 250,
        "label": fmt.get("label") or base.get("label") or "",
        "melhor_para": fmt.get("melhor_para") or "",
        "dispositivos": _normalizar_dispositivos(fmt.get("dispositivos"), tipo=tipo, chave=chave),
    }
    for extra in ("taxa", "tempo", "extra"):
        if fmt.get(extra):
            out[extra] = fmt[extra]
    return out


def _parece_formato(texto: str) -> bool:
    blob = (texto or "").casefold()
    return any(needle in blob for needle, _ in _FORMAT_LOOKUP)


def _oferta_de(item: Dict[str, Any]) -> List[str]:
    out = []
    if item.get("alcance"):
        out.append(item["alcance"])
    if item.get("viewability") is not None:
        out.append(f"Viewability {item['viewability']}%")
    if item.get("investimento_minimo"):
        out.append(f"Mínimo {item['investimento_minimo']}")
    for linha in item.get("diferenciais") or []:
        if any(marca in linha for marca in ("%", "+", "R$")) and linha not in out:
            out.append(linha)
        if len(out) >= 5:
            break
    return out[:5]


def _opcoes_exemplo(opcoes: Any) -> str:
    if isinstance(opcoes, list):
        return ", ".join(str(item).strip() for item in opcoes[:3] if str(item).strip())
    return str(opcoes or "").strip()


def mapear_segmentacoes(raw: Any) -> List[Dict[str, str]]:
    """Normaliza lista comercial ou o JSON antigo `segmentacao` do cadu_canais."""
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, dict) and (item.get("nome") or "").strip():
                out.append({
                    "nome": str(item.get("nome") or "").strip(),
                    "quando": str(item.get("quando") or "").strip(),
                    "exemplo": str(item.get("exemplo") or "").strip() or _opcoes_exemplo(item.get("opcoes")),
                })
            elif isinstance(item, str) and item.strip():
                out.append({"nome": item.strip(), "quando": "", "exemplo": ""})
        return out[:8]
    if isinstance(raw, dict):
        out = []
        for key, val in raw.items():
            label = str(key or "").replace("_", " ").strip()
            if isinstance(val, dict):
                nome = str(val.get("nome") or label).strip()
                if not nome:
                    continue
                out.append({
                    "nome": nome,
                    "quando": str(val.get("quando") or label).strip(),
                    "exemplo": str(val.get("exemplo") or "").strip() or _opcoes_exemplo(val.get("opcoes")),
                })
            elif isinstance(val, list) and val:
                out.append({
                    "nome": label.title() or "Segmentação",
                    "quando": label,
                    "exemplo": _opcoes_exemplo(val),
                })
        return out[:8]
    return []


def _segmentacoes_de(item: Dict[str, Any]) -> List[Dict[str, str]]:
    prontas = mapear_segmentacoes(item.get("segmentacoes"))
    if not prontas:
        prontas = mapear_segmentacoes(item.get("segmentacao"))
    if prontas:
        return prontas[:8]
    if _eh_serasa(item):
        return [
            {"nome": "Imóveis RJ", "quando": "score 500+, classe ABC, 30 dias", "exemplo": "ECS 190.970 / Meta 1.514.181 / TikTok 58.035"},
            {"nome": "Automotivo RJ", "quando": "score 500+, ABC", "exemplo": "ECS 426.770 / Meta 4.061.559 / TikTok 102.218"},
            {"nome": "Viajantes RJ", "quando": "score 500+, ABC", "exemplo": "ECS 502.190 / Meta 1.211.725 / TikTok 40.296"},
            {"nome": "Nação do Futebol RJ", "quando": "interesse esportivo + score", "exemplo": "ECS 253.591 / Meta 1.423.062 / TikTok 71.435"},
        ]
    extraidas = []
    for linha in item.get("diferenciais") or []:
        baixo = linha.casefold()
        if any(chave in baixo for chave in _SEG_KEYWORDS):
            extraidas.append({"nome": linha, "quando": item.get("categoria") or "", "exemplo": ""})
    if extraidas:
        return extraidas[:6]
    tipo = item.get("tipo") or ""
    padrao = {
        "audio": [{"nome": "Momento do dia", "quando": "treino, foco, deslocamento", "exemplo": "Workout / relax / focus"}],
        "ctv": [{"nome": "Títulos e gêneros", "quando": "associação de marca a conteúdo", "exemplo": "Top 10, família, esportes"}],
        "video": [{"nome": "Intenção de busca", "quando": "descoberta ou consideração", "exemplo": "Palavras e canais afins"}],
        "social": [{"nome": "Interesses e lookalike", "quando": "alcance ou conversão", "exemplo": "Base do cliente + afinidade"}],
        "portal": [{"nome": "Contexto editorial", "quando": "notícia, nicho ou praça", "exemplo": "Home, seção, regional"}],
        "data": [{"nome": "Score e momento financeiro", "quando": "crédito, imóvel, auto", "exemplo": "Corte de praça + renda"}],
        "programatica": [{"nome": "Audiência e PMP", "quando": "escala com controle", "exemplo": "Open auction vs deal premium"}],
        "ooh": [{"nome": "Ponto e fluxo", "quando": "cidade e trajeto", "exemplo": "Elevador AB, metrô, aeroporto"}],
        "gaming": [{"nome": "Comunidade e categoria", "quando": "live e jogo", "exemplo": "FPS, mobile, just chatting"}],
        "mobile": [{"nome": "Raio e loja", "quando": "drive-to-store", "exemplo": "Pin no mapa + navegação"}],
        "messaging": [{"nome": "Tema do canal", "quando": "finanças, tech, cripto", "exemplo": "Canais públicos afins"}],
        "interativo": [{"nome": "Vertical da peça", "quando": "imóvel, varejo, dado", "exemplo": "Hot Spots vs Poll"}],
    }.get(tipo, [{"nome": "Público do canal", "quando": item.get("categoria") or "campanha", "exemplo": item.get("alcance") or ""}])
    return padrao


def _assistente_de(item: Dict[str, Any]) -> Dict[str, Any]:
    atual = item.get("assistente") if isinstance(item.get("assistente"), dict) else {}
    base = dict(_ASSISTENTE_POR_TIPO.get(item.get("tipo") or "") or _ASSISTENTE_POR_TIPO["portal"])
    if _eh_serasa(item):
        base = {
            "quando": "O cliente precisa de intenção de compra, score ou recorte financeiro — não só interesse.",
            "passos": [
                "Mostre o corte (imóvel, auto, viagem) com ECS vs Meta vs TikTok.",
                "Abra a sessão de segmentação e escolha um universo.",
                "Feche apresentação com o kit 2027 e o mínimo do portal ou da DMP.",
            ],
            "evitar": "Falar em '+100M' sem um recorte. Sem corte, o número não vende.",
            "proximo_passo": "Gerar a apresentação e marcar a reunião com o deck.",
        }
    if item.get("slug") == "interativos":
        base = dict(_ASSISTENTE_POR_TIPO["interativo"])
    passos = atual.get("passos") or base["passos"]
    if isinstance(passos, str):
        passos = [passos]
    return {
        "quando": (atual.get("quando") or base["quando"]).strip(),
        "passos": [str(p).strip() for p in passos if str(p).strip()][:6],
        "evitar": (atual.get("evitar") or base["evitar"]).strip(),
        "proximo_passo": (atual.get("proximo_passo") or base["proximo_passo"]).strip(),
    }


def _catalogo_por_slug() -> Dict[str, Dict[str, Any]]:
    try:
        rows = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        str(row.get("slug") or ""): row
        for row in rows
        if isinstance(row, dict) and row.get("slug")
    }


def _aplicar_kit(item: Dict[str, Any]) -> Dict[str, Any]:
    catalogo = _catalogo_por_slug().get(item.get("slug") or "") or {}
    if catalogo.get("formatos") and not item.get("formatos"):
        item["formatos"] = catalogo.get("formatos") or []
    if catalogo.get("segmentacoes") and not item.get("segmentacoes"):
        item["segmentacoes"] = catalogo.get("segmentacoes") or []
    if catalogo.get("assistente") and not item.get("assistente"):
        item["assistente"] = catalogo.get("assistente") or {}
    item["logo"] = _resolver_logo(item.get("slug") or "", item.get("logo") or "")
    tipo = item.get("tipo") or ""
    originais = list(item.get("beneficios") or [])
    formatos = [_normalizar_formato(fmt, tipo) for fmt in (item.get("formatos") or [])]
    formatos = [fmt for fmt in formatos if fmt.get("nome")]
    if not formatos:
        formatos = [_normalizar_formato(nome, tipo) for nome in originais if _parece_formato(nome)]
    if not formatos and originais:
        formatos = [_normalizar_formato(originais[0], tipo)]
    if not formatos:
        meta = _FORMAT_BY_TIPO.get(tipo) or _FORMAT_DEFAULT
        formatos = [{
            "nome": item.get("categoria") or item.get("nome") or "Formato",
            "chave": meta["chave"],
            "w": meta["w"],
            "h": meta["h"],
            "label": meta["label"],
            "melhor_para": item.get("descricao") or "",
            "dispositivos": _normalizar_dispositivos([], tipo=tipo, chave=meta["chave"]),
        }]
    item["formatos"] = formatos
    item["categoria"] = _GRUPO_POR_SLUG.get(item.get("slug") or "") or item.get("categoria") or ""
    if _eh_serasa(item):
        item["beneficios"] = list(SERASA_KIT_2027["fatos"])
        item["diferenciais"] = (
            list(item.get("diferenciais") or [])[:2] + SERASA_KIT_2027["cortes"]
        )
        item["arquivos"] = [_arquivo_serasa()]
        item["alcance"] = item.get("alcance") or "+100M CPFs 18+"
    elif originais and all(_parece_formato(nome) for nome in originais):
        oferta = _oferta_de(item)
        if oferta:
            item["beneficios"] = oferta
    item["segmentacoes"] = _segmentacoes_de(item)
    item["assistente"] = _assistente_de(item)
    return item


def _fallback_canais() -> List[Dict[str, Any]]:
    try:
        bruto = json.loads(_CATALOG_PATH.read_text())
    except Exception:
        bruto = []
    canais = []
    for row in bruto:
        item = _canal(
            row.get("slug") or "",
            row.get("nome") or "",
            row.get("categoria") or "",
            row.get("tipo") or "",
            alcance=row.get("alcance") or "",
            viewability=row.get("viewability"),
            minimo=row.get("investimento_minimo") or "",
            beneficios=row.get("beneficios") or [],
            diferenciais=row.get("diferenciais") or [],
            logo=row.get("logo_path") or "",
            cor=row.get("cor") or "",
            descricao=row.get("descricao") or "",
            formatos=row.get("formatos") or [],
            segmentacoes=row.get("segmentacoes") or [],
            assistente=row.get("assistente") or {},
        )
        canais.append(_aplicar_kit(item))
    if not any(c.get("slug") == "interativos" for c in canais):
        canais.append(_aplicar_kit(_canal(
            "interativos", "Interativos", "Formatos", "interativo",
            alcance="Add-on rich media em programática e portais",
            beneficios=["Taxa de engajamento 2–12% conforme formato", "Tempo de interação 5–45s"],
            diferenciais=["Hot Spots e 360° para imóveis", "Poll/Quiz até 8x vs display"],
            formatos=list(INTERATIVOS_FALLBACK),
            segmentacoes=[
                {"nome": "Hot Spots e 360°", "quando": "imóvel e decoração", "exemplo": "Lançamento com planta"},
                {"nome": "Poll / Quiz", "quando": "first-party data", "exemplo": "Pergunta no portal"},
                {"nome": "Cube e Scratch", "quando": "produto e cupom", "exemplo": "Varejo no 300×250"},
                {"nome": "Video Interactive", "quando": "demo em CTV ou mobile", "exemplo": "15–45s"},
            ],
            cor="#0F766E",
        )))
    canais = _completar_canais_midia(canais)
    if canais:
        return canais
    return _completar_canais_midia([_aplicar_kit(item) for item in _fallback_canais_minimo()])


def _completar_canais_midia(canais: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    extras = [
        _canal(
            "ifood", "iFood", "Mobilidade", "mobile",
            alcance="+50M usuários BR", viewability=90, minimo="R$ 8.000",
            beneficios=["In-App Ads", "Splash Screen", "Push Notification"],
            diferenciais=["Momento de fome e decisão de pedido", "Público classe C forte", "Cupom no app"],
            descricao="App de delivery com o maior volume de pedidos do Brasil. Ideal para food, varejo e cupom no momento da fome.",
            formatos=[
                {"nome": "Splash Screen", "dispositivos": ["mobile", "app"], "melhor_para": "abertura do pedido"},
                {"nome": "In-App Ads", "dispositivos": ["mobile", "app"], "melhor_para": "durante o fluxo"},
                {"nome": "Push Notification", "dispositivos": ["mobile", "app"], "melhor_para": "cupom e volta"},
            ],
            segmentacoes=[
                {"nome": "Momento da fome", "quando": "almoço e jantar", "exemplo": "11h–14h e 19h–22h"},
                {"nome": "Ticket e categoria", "quando": "food vs mercado", "exemplo": "Pedido médio da praça"},
                {"nome": "Praça e raio", "quando": "loja e dark kitchen", "exemplo": "3 km do PDV"},
                {"nome": "Cupom no app", "quando": "conversão", "exemplo": "Primeira compra da semana"},
            ],
            cor="#EA1D2C",
            assistente={
                "quando": "O cliente quer cupom, delivery ou impacto no momento da fome.",
                "passos": [
                    "Mostre splash e in-app no instante do pedido, não só banner.",
                    "Pergunte praça, ticket médio e se tem oferta pronta.",
                    "Feche um teste com cupom no app.",
                ],
                "evitar": "Vender iFood como display mobile genérico.",
                "proximo_passo": "Gerar a apresentação com splash + cupom e marcar o follow-up.",
            },
        ),
        _canal(
            "uber", "Uber", "Mobilidade", "mobile",
            alcance="+30M usuários BR", viewability=88, minimo="R$ 10.000",
            beneficios=["In-App Banner", "Splash", "Receipt Ads"],
            diferenciais=["Passageiro em deslocamento", "Recibo com alta leitura", "Cidades e aeroportos"],
            descricao="Plataforma de mobilidade com anúncios no app e no recibo. Bom para marca e drive-to-store.",
            formatos=[
                {"nome": "Splash", "dispositivos": ["mobile", "app"], "melhor_para": "abertura da corrida"},
                {"nome": "In-App Ads", "dispositivos": ["mobile", "app"], "melhor_para": "durante o deslocamento"},
                {"nome": "Receipt Ads", "dispositivos": ["mobile"], "melhor_para": "leitura no recibo"},
            ],
            segmentacoes=[
                {"nome": "Aeroporto e centro", "quando": "marca em deslocamento", "exemplo": "Chegada GRU/CGH/GIG"},
                {"nome": "Horário da corrida", "quando": "pico vs noite", "exemplo": "7h–9h e 18h–21h"},
                {"nome": "Recibo", "quando": "alta leitura", "exemplo": "Fim da viagem"},
                {"nome": "Cidade", "quando": "praça", "exemplo": "SP, RJ, BH"},
            ],
            cor="#000000",
            assistente={
                "quando": "O cliente precisa de marca no deslocamento ou no recibo da corrida.",
                "passos": [
                    "Separe splash, banner no app e recibo — cada um tem um job.",
                    "Pergunte cidades e se o objetivo é marca ou loja.",
                    "Ofereça um circuito de aeroporto ou centro.",
                ],
                "evitar": "Tratar Uber como Waze. Aqui o anúncio vive no app e no recibo.",
                "proximo_passo": "Gerar a apresentação com um formato e uma praça.",
            },
        ),
        _canal(
            "99", "99", "Mobilidade", "mobile",
            alcance="+20M usuários BR", viewability=86, minimo="R$ 8.000",
            beneficios=["In-App Ads", "Splash Screen", "Cupom no app"],
            diferenciais=["Forte nas capitais", "Público complementar à Uber", "Cupom nativo"],
            descricao="App de transporte com penetração nacional. Complementa Uber no recorte de praça e classe.",
            formatos=[
                {"nome": "Splash Screen", "dispositivos": ["mobile", "app"], "melhor_para": "abertura"},
                {"nome": "In-App Ads", "dispositivos": ["mobile", "app"], "melhor_para": "durante a corrida"},
                {"nome": "Cupom no app", "dispositivos": ["mobile", "app"], "melhor_para": "conversão"},
            ],
            segmentacoes=[
                {"nome": "Capitais", "quando": "complemento da Uber", "exemplo": "SP, RJ, BH, Recife"},
                {"nome": "Classe e ticket", "quando": "cupom nativo", "exemplo": "Corrida econômica"},
                {"nome": "Horário", "quando": "pico urbano", "exemplo": "Manhã e fim de expediente"},
                {"nome": "Praça forte 99", "quando": "não empilhar com Uber", "exemplo": "Cidades onde a 99 lidera"},
            ],
            cor="#FFDD00",
            assistente={
                "quando": "Complemento de Uber nas capitais, com cupom nativo.",
                "passos": [
                    "Mostre a diferença de praça e classe versus Uber.",
                    "Pergunte se o cliente quer cupom ou só marca.",
                    "Feche um teste nas capitais onde a 99 é mais forte.",
                ],
                "evitar": "Empilhar 99 e Uber no mesmo slide sem recorte.",
                "proximo_passo": "Gerar a apresentação com o recorte de capitais.",
            },
        ),
        _canal(
            "logan", "Logan", "DOOH", "ooh",
            alcance="Circuitos urbanos e trajetos", viewability=94, minimo="R$ 12.000",
            beneficios=["Mídia em veículo", "Circuitos urbanos", "DOOH mobile"],
            diferenciais=["Impacto no trajeto", "Praça e rota sob medida", "Complemento de campanha OOH"],
            descricao="Mídia em trajetos e circuitos urbanos. Use quando o cliente precisa de presença no caminho, não só na tela.",
            formatos=[
                {"nome": "Mídia em veículo", "dispositivos": ["ooh"], "melhor_para": "trajeto"},
                {"nome": "Circuitos urbanos", "dispositivos": ["ooh"], "melhor_para": "rota e cidade"},
                {"nome": "DOOH mobile", "dispositivos": ["ooh", "mobile"], "melhor_para": "apoio digital"},
            ],
            segmentacoes=[
                {"nome": "Rota", "quando": "caminho casa–trabalho", "exemplo": "Corredor da cidade"},
                {"nome": "Cidade e período", "quando": "circuito fechado", "exemplo": "2 semanas em SP"},
                {"nome": "Complemento OOH", "quando": "já tem rua ou metrô", "exemplo": "Mesmo período da Eletromidia"},
                {"nome": "Classe do trajeto", "quando": "AB vs massa", "exemplo": "Centro vs periferia"},
            ],
            cor="#1F4B8F",
            assistente={
                "quando": "O cliente precisa de presença no trajeto, não só na tela.",
                "passos": [
                    "Mostre o circuito (rota, cidade, período), não uma tela isolada.",
                    "Pergunte se complementa OOH estático ou digital.",
                    "Feche um mapa de trajetos na reunião.",
                ],
                "evitar": "Vender Logan como banner digital. O ponto é o caminho.",
                "proximo_passo": "Levar o mapa de circuitos na apresentação.",
            },
        ),
    ]
    slugs = {item.get("slug") for item in canais}
    for extra in extras:
        if extra["slug"] not in slugs:
            canais.append(_aplicar_kit(extra))
    return canais


def _fallback_canais_minimo() -> List[Dict[str, Any]]:
    return [
        _canal(
            "netflix", "Netflix", "CTV / Streaming", "ctv",
            alcance="+20M assinantes BR", viewability=99, minimo="R$ 50.000",
            beneficios=["Viewability 99%", "Completion 97%", "2h/dia de consumo"],
            diferenciais=["Ambiente premium sem skip", "CTV com atenção alta"],
            cor="#E50914",
        ),
        _canal(
            "spotify", "Spotify", "Streaming de Áudio", "audio",
            alcance="+50M ouvintes", viewability=98, minimo="R$ 15.000",
            beneficios=["45 min/dia", "Completion 95%"],
            diferenciais=["Áudio com intenção de escuta"],
            cor="#1DB954",
        ),
        _canal(
            "serasa", "Serasa", "Dados e portal", "data",
            alcance="+100M CPFs 18+", viewability=85, minimo="R$ 10.000",
            beneficios=SERASA_KIT_2027["fatos"],
            diferenciais=["Intenção real de compra, não só interesse"] + SERASA_KIT_2027["cortes"],
            arquivos=[_arquivo_serasa()],
            cor="#7C3AED",
        ),
        _canal(
            "disney-plus", "Disney+", "CTV / Streaming", "ctv",
            alcance="+15M assinantes BR", viewability=98, minimo="R$ 40.000",
            beneficios=["Completion 96%"],
            diferenciais=["Família e franquias"],
            cor="#113CCF",
        ),
        _canal(
            "hbo-max", "Max (HBO)", "CTV / Streaming", "ctv",
            alcance="+10M assinantes BR", viewability=98, minimo="R$ 45.000",
            beneficios=["Completion 95%"],
            diferenciais=["Premium adulto"],
            cor="#7B2CBF",
        ),
        _canal(
            "prime-video", "Prime Video", "CTV / Streaming", "ctv",
            alcance="+12M assinantes BR", viewability=97, minimo="R$ 35.000",
            beneficios=["Completion 94%"],
            diferenciais=["Shoppable com dados Amazon"],
            cor="#00A8E1",
        ),
        _canal(
            "g1-globo", "G1 / Globo.com", "Portais Premium", "portal",
            alcance="+150M pageviews/mês", viewability=72, minimo="R$ 10.000",
            beneficios=["80M UU"],
            diferenciais=["Contexto editorial"],
            cor="#C4170C",
        ),
        _canal(
            "interativos", "Interativos", "Formatos", "interativo",
            alcance="Add-on rich media em programática e portais",
            viewability=None, minimo="",
            beneficios=["Taxa de engajamento 2–12% conforme formato", "Tempo de interação 5–45s"],
            diferenciais=["Hot Spots e 360° para imóveis", "Poll/Quiz até 8x vs display"],
            formatos=list(INTERATIVOS_FALLBACK),
            segmentacoes=[
                {"nome": "Hot Spots e 360°", "quando": "imóvel e decoração", "exemplo": "Lançamento com planta"},
                {"nome": "Poll / Quiz", "quando": "first-party data", "exemplo": "Pergunta no portal"},
                {"nome": "Cube e Scratch", "quando": "produto e cupom", "exemplo": "Varejo no 300×250"},
                {"nome": "Video Interactive", "quando": "demo em CTV ou mobile", "exemplo": "15–45s"},
            ],
            cor="#0F766E",
        ),
    ]


def _canal(
    slug, nome, categoria, tipo, alcance="", viewability=None, minimo="",
    beneficios=None, diferenciais=None, arquivos=None, formatos=None, cor="",
    logo="", descricao="", segmentacoes=None, assistente=None,
):
    return {
        "slug": slug,
        "nome": nome,
        "categoria": categoria,
        "tipo": tipo,
        "alcance": alcance or "",
        "viewability": viewability,
        "investimento_minimo": minimo or "",
        "beneficios": beneficios or [],
        "diferenciais": diferenciais or [],
        "arquivos": arquivos or [],
        "formatos": formatos or [],
        "cor": cor or "",
        "logo": logo or "",
        "descricao": descricao or "",
        "segmentacoes": segmentacoes or [],
        "assistente": assistente or {},
        "inicial": (nome[:1] or "?").upper(),
    }


def _arquivo_serasa():
    return {
        "titulo": SERASA_KIT_2027["titulo"],
        "tipo": SERASA_KIT_2027["tipo"],
        "url": SERASA_KIT_2027["url"],
    }


def _query_db_canais() -> Optional[List[Dict[str, Any]]]:
    try:
        from flask import current_app, has_app_context
        if has_app_context() and current_app.config.get("TESTING"):
            return None
        from .db import get_db
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT slug, nome, categoria, tipo, alcance, viewability,
                       investimento_minimo, formatos_resumo, diferenciais,
                       logo_path, cor, descricao, segmentacao, segmentacoes, formatos
                FROM cadu_canais
                WHERE is_active IS TRUE
                ORDER BY ordem NULLS LAST, nome
                """
            )
            rows = cur.fetchall() or []
    except Exception:
        return None
    if not rows:
        return None
    canais = []
    for row in rows:
        slug = (row.get("slug") or "").strip()
        nome = (row.get("nome") or "").strip()
        if not nome:
            continue
        item = _canal(
            slug or _slugify(nome),
            nome,
            row.get("categoria") or "",
            row.get("tipo") or "",
            alcance=row.get("alcance") or "",
            viewability=row.get("viewability"),
            minimo=row.get("investimento_minimo") or "",
            beneficios=_lista(row.get("formatos_resumo")),
            diferenciais=_lista(row.get("diferenciais")),
            logo=row.get("logo_path") or "",
            cor=row.get("cor") or "",
            descricao=row.get("descricao") or "",
            formatos=row.get("formatos") or [],
            segmentacoes=mapear_segmentacoes(row.get("segmentacoes"))
            or mapear_segmentacoes(row.get("segmentacao")),
        )
        canais.append(_aplicar_kit(item))
    if not any(c["slug"] == "interativos" for c in canais):
        canais.append(_aplicar_kit(_canal_interativos_db()))
    return canais


def _canal_interativos_db() -> Dict[str, Any]:
    formatos = list(INTERATIVOS_FALLBACK)
    try:
        from .db import get_db
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT nome, taxa_engajamento, tempo_interacao, melhor_para,
                       dados_extras
                FROM cadu_formatos
                WHERE is_interativo IS TRUE AND is_active IS TRUE
                ORDER BY ordem NULLS LAST, nome
                """
            )
            rows = cur.fetchall() or []
        if rows:
            formatos = []
            for row in rows:
                extras = row.get("dados_extras") or {}
                if not isinstance(extras, dict):
                    extras = {}
                formatos.append({
                    "nome": row.get("nome") or "",
                    "taxa": row.get("taxa_engajamento") or "",
                    "tempo": row.get("tempo_interacao") or "",
                    "melhor_para": row.get("melhor_para") or "",
                    "extra": extras.get("engagementMultiplier") or "",
                })
    except Exception:
        pass
    canal = _canal(
        "interativos", "Interativos", "Formatos", "interativo",
        alcance="Add-on rich media em programática e portais",
        beneficios=["Engajamento medido por formato", "Tempo de interação 5–45s"],
        diferenciais=["Hot Spots e 360° para imóveis"],
        formatos=formatos,
        segmentacoes=[
            {"nome": "Hot Spots e 360°", "quando": "imóvel e decoração", "exemplo": "Lançamento com planta"},
            {"nome": "Poll / Quiz", "quando": "first-party data", "exemplo": "Pergunta no portal"},
            {"nome": "Cube e Scratch", "quando": "produto e cupom", "exemplo": "Varejo no 300×250"},
            {"nome": "Video Interactive", "quando": "demo em CTV ou mobile", "exemplo": "15–45s"},
        ],
        cor="#0F766E",
    )
    return canal


def _lista(valor) -> List[str]:
    if not valor:
        return []
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]
    return [str(valor).strip()]


def _slugify(nome: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in nome).strip("-")


def _eh_serasa(canal: Dict[str, Any]) -> bool:
    blob = f"{canal.get('slug') or ''} {canal.get('nome') or ''}".lower()
    return "serasa" in blob or "experian" in blob


def listar_canais() -> List[Dict[str, Any]]:
    canais = _completar_canais_midia(_query_db_canais() or _fallback_canais())
    canais = [
        item for item in canais
        if (item.get("slug") or "") not in CANAIS_EXCLUIDOS
    ]
    return sorted(canais, key=lambda item: (item.get("nome") or "").casefold())


def grupos_canais(canais: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    presentes = {item.get("categoria") for item in (canais or listar_canais()) if item.get("categoria")}
    return [nome for nome in GRUPOS if nome in presentes]


def nomes_canais() -> List[str]:
    nomes = [item["nome"] for item in listar_canais() if item.get("nome")]
    for extra in CANAIS_MIDIA:
        if extra not in nomes:
            nomes.append(extra)
    return nomes


def resolver_canal(nome: str) -> Optional[Dict[str, Any]]:
    alvo = (nome or "").strip().casefold()
    if not alvo:
        return None
    canais = listar_canais()
    for item in canais:
        if (item.get("nome") or "").casefold() == alvo:
            return item
        if (item.get("slug") or "").casefold() == alvo:
            return item
    for item in canais:
        nome_item = (item.get("nome") or "").casefold()
        slug = (item.get("slug") or "").casefold()
        if alvo in nome_item or nome_item in alvo or alvo in slug:
            return item
    if "interativ" in alvo:
        return next((item for item in canais if item.get("slug") == "interativos"), None)
    return None


def inferir_canal(titulo: str, atual: str = "") -> str:
    if (atual or "").strip():
        encontrado = resolver_canal(atual)
        return encontrado["nome"] if encontrado else atual.strip()
    texto = (titulo or "").casefold()
    if "interativ" in texto:
        return "Interativos"
    for nome in nomes_canais():
        if nome and nome.casefold() in texto:
            return nome
    return ""


def ficha_canal_texto(nome: str, registro: str = "") -> str:
    canal = resolver_canal(nome)
    if not canal:
        return ""
    linhas = [
        f"FICHA TÉCNICA — {canal['nome']}",
        "Amarre estes números ao registro. Não troque o assunto da atividade pelo nome do canal.",
        "Use somente estes números. Sem número aqui, não escreva 'métrica'.",
    ]
    if canal.get("alcance"):
        linhas.append(f"Alcance: {canal['alcance']}")
    if canal.get("viewability") is not None:
        linhas.append(f"Viewability: {canal['viewability']}%")
    if canal.get("investimento_minimo"):
        linhas.append(f"Investimento mínimo: {canal['investimento_minimo']}")
    if canal.get("beneficios"):
        linhas.append("Números e benefícios: " + "; ".join(canal["beneficios"][:6]))
    if canal.get("diferenciais"):
        linhas.append("Diferenciais: " + "; ".join(canal["diferenciais"][:6]))
    formatos = _formatos_para_registro(canal.get("formatos") or [], registro)
    if formatos:
        blocos = []
        for item in formatos[:5]:
            pedaco = item["nome"]
            if item.get("label"):
                pedaco += f" {item['label']}"
            if item.get("taxa"):
                pedaco += f" {item['taxa']}"
            if item.get("tempo"):
                pedaco += f" / {item['tempo']}"
            if item.get("extra"):
                pedaco += f" ({item['extra']})"
            if item.get("melhor_para"):
                pedaco += f" — {item['melhor_para']}"
            blocos.append(pedaco)
        linhas.append("Formatos: " + " | ".join(blocos))
    segs = canal.get("segmentacoes") or []
    if segs:
        blocos = []
        for item in segs[:6]:
            pedaco = item.get("nome") or ""
            if item.get("quando"):
                pedaco += f" ({item['quando']})"
            if item.get("exemplo"):
                pedaco += f" — {item['exemplo']}"
            if pedaco:
                blocos.append(pedaco)
        if blocos:
            linhas.append("Segmentações: " + " | ".join(blocos))
    assistente = canal.get("assistente") or {}
    if assistente.get("quando"):
        linhas.append("Quando indicar: " + assistente["quando"])
    if assistente.get("passos"):
        linhas.append("O que fazer: " + "; ".join(assistente["passos"][:5]))
    arquivos = canal.get("arquivos") or []
    if arquivos:
        linhas.append(
            "Material de venda: "
            + "; ".join(item.get("titulo") or item.get("url") or "" for item in arquivos[:3])
        )
    return "\n".join(linhas)


def _formatos_para_registro(formatos: List[Dict[str, Any]], registro: str) -> List[Dict[str, Any]]:
    if not formatos:
        return []
    texto = (registro or "").casefold()
    if any(palavra in texto for palavra in ("imob", "lançament", "lancament")):
        prioridade = ("hot spots", "360", "countdown", "cube", "scratch")
        ordenados = sorted(
            formatos,
            key=lambda item: next(
                (idx for idx, chave in enumerate(prioridade) if chave in (item.get("nome") or "").casefold()),
                99,
            ),
        )
        return ordenados
    return formatos


def canal_publico(canal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "slug": canal.get("slug") or "",
        "nome": canal.get("nome") or "",
        "categoria": canal.get("categoria") or "",
        "tipo": canal.get("tipo") or "",
        "alcance": canal.get("alcance") or "",
        "viewability": canal.get("viewability"),
        "investimento_minimo": canal.get("investimento_minimo") or "",
        "beneficios": canal.get("beneficios") or [],
        "diferenciais": canal.get("diferenciais") or [],
        "arquivos": canal.get("arquivos") or [],
        "formatos": canal.get("formatos") or [],
        "cor": canal.get("cor") or "",
        "logo": canal.get("logo") or "",
        "descricao": canal.get("descricao") or "",
        "segmentacoes": canal.get("segmentacoes") or [],
        "assistente": canal.get("assistente") or {},
        "inicial": canal.get("inicial") or (canal.get("nome") or "?")[:1].upper(),
    }


def _connect_canais_db():
    import psycopg
    from psycopg.rows import dict_row

    from .db import get_db_config

    cfg = dict(get_db_config())
    cfg.pop("row_factory", None)
    return psycopg.connect(**cfg, row_factory=dict_row)


def garantir_colunas_ficha() -> None:
    conn = _connect_canais_db()
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE cadu_canais ADD COLUMN IF NOT EXISTS segmentacoes jsonb")
            cur.execute("ALTER TABLE cadu_canais ADD COLUMN IF NOT EXISTS formatos jsonb")
        conn.commit()
    finally:
        conn.close()


def persistir_ficha_db(canal: Dict[str, Any]) -> None:
    slug = (canal.get("slug") or "").strip()
    if not slug or slug in CANAIS_EXCLUIDOS:
        return
    from psycopg.types.json import Json

    categoria = _GRUPO_POR_SLUG.get(slug) or canal.get("categoria") or ""
    formatos = [_normalizar_formato(fmt, canal.get("tipo") or "") for fmt in (canal.get("formatos") or [])]
    formatos = [fmt for fmt in formatos if fmt.get("nome")]
    segmentacoes = mapear_segmentacoes(canal.get("segmentacoes"))
    conn = _connect_canais_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cadu_canais
                SET categoria = COALESCE(NULLIF(%s, ''), categoria),
                    segmentacoes = %s,
                    formatos = %s,
                    updated_at = NOW()
                WHERE slug = %s
                """,
                (categoria, Json(segmentacoes), Json(formatos), slug),
            )
            if cur.rowcount == 0:
                cur.execute(
                    """
                    INSERT INTO cadu_canais (
                        slug, nome, categoria, tipo, alcance, viewability,
                        investimento_minimo, descricao, cor, logo_path,
                        formatos_resumo, diferenciais, segmentacoes, formatos,
                        is_active, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        TRUE, NOW()
                    )
                    """,
                    (
                        slug,
                        canal.get("nome") or slug,
                        categoria,
                        canal.get("tipo") or "",
                        canal.get("alcance") or "",
                        canal.get("viewability"),
                        canal.get("investimento_minimo") or "",
                        canal.get("descricao") or "",
                        canal.get("cor") or "",
                        canal.get("logo") or "",
                        Json([fmt.get("nome") for fmt in formatos if fmt.get("nome")]),
                        Json(canal.get("diferenciais") or []),
                        Json(segmentacoes),
                        Json(formatos),
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def sincronizar_canais_db() -> Dict[str, int]:
    garantir_colunas_ficha()
    from psycopg.types.json import Json

    canais = _completar_canais_midia(_fallback_canais())
    conn = _connect_canais_db()
    updated = inserted = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cadu_canais
                SET is_active = FALSE, updated_at = NOW()
                WHERE slug = ANY(%s)
                """,
                (list(CANAIS_EXCLUIDOS),),
            )
            cur.execute("SELECT slug, segmentacao FROM cadu_canais")
            taxonomia = {row["slug"]: row.get("segmentacao") for row in cur.fetchall()}
            for canal in canais:
                slug = canal.get("slug") or ""
                if slug in CANAIS_EXCLUIDOS:
                    continue
                segs = mapear_segmentacoes(canal.get("segmentacoes")) or mapear_segmentacoes(taxonomia.get(slug))
                formatos = [fmt for fmt in (canal.get("formatos") or []) if fmt.get("nome")]
                categoria = _GRUPO_POR_SLUG.get(slug) or canal.get("categoria") or ""
                cur.execute(
                    """
                    UPDATE cadu_canais
                    SET categoria = COALESCE(NULLIF(%s, ''), categoria),
                        segmentacoes = %s,
                        formatos = %s,
                        is_active = TRUE,
                        updated_at = NOW()
                    WHERE slug = %s
                    """,
                    (categoria, Json(segs), Json(formatos), slug),
                )
                if cur.rowcount:
                    updated += 1
                    continue
                persistir_ficha_db({**canal, "segmentacoes": segs, "formatos": formatos})
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return {"updated": updated, "inserted": inserted}
