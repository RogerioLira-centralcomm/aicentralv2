"""Logos reais do catálogo CentralX — sem Firecrawl no caminho crítico."""

CHANNEL_LOGOS = {
    "linkedin": "/static/images/creative-viewers/linkedin.svg",
    "instagram": "/static/images/creative-viewers/instagram.svg",
    "tiktok": "/static/images/canais/tiktok.png",
    "g1": "/static/images/canais/g1-globo.svg",
    "cnn": "/static/images/creative-viewers/cnn-brasil.svg",
    "sbt": "/static/images/canais/sbt.png",
    "serasa": "/static/images/canais/experian-portal.png",
    "uber": "/static/images/canais/uber.png",
    "99": "/static/images/canais/99.svg",
    "ifood": "/static/images/canais/ifood.svg",
    "amazon": "/static/images/canais/amazon-music.png",
    "spotify": "/static/images/canais/spotify.svg",
    "netflix": "/static/images/creative-viewers/netflix.png",
    "prime": "/static/images/canais/prime-video.svg",
    "disney": "/static/images/creative-viewers/disney-plus.png",
    "hbo": "/static/images/canais/hbo-max.svg",
}


def logo_path(key):
    return CHANNEL_LOGOS.get(key) or ""
