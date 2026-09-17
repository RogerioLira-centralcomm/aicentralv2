"""Premissas comerciais para a one-page pública de Places.

Os dados deste módulo são deliberadamente apresentados como estimativas de
planejamento. Eles não substituem um relatório do parceiro de location data.
"""

from __future__ import annotations

from copy import deepcopy


# Fontes consultadas via Firecrawl em 15/09/2026. Elas oferecem o ranking
# nacional; o cruzamento com o contexto do ponto é uma estimativa comercial,
# não uma leitura de audiência geolocalizada.
INVENTORY_SOURCES = (
    {"title": "Similarweb — sites mais acessados no Brasil (ago/2026)", "url": "https://www.similarweb.com/pt/top-websites/brazil/"},
    {"title": "Mobile Time / AppMagic — apps mais baixados no Brasil (mai/2026)", "url": "https://www.mobiletime.com.br/noticias/22/06/2026/apps-mais-baixados-br265/"},
)

PORTALS_BY_CITY = {
    "bh": ("G1", "Globo.com", "UOL", "CNN Brasil", "R7", "O Tempo", "Estado de Minas", "Metrópoles", "Exame", "InfoMoney"),
    "sp": ("G1", "Globo.com", "UOL", "CNN Brasil", "R7", "Folha de S.Paulo", "Estadão", "Metrópoles", "Exame", "InfoMoney"),
    "rj": ("G1", "Globo.com", "UOL", "CNN Brasil", "R7", "O Globo", "Extra", "Metrópoles", "Exame", "GE"),
}


def _items(names: tuple[str, ...], why: str) -> list[dict]:
    return [{"name": name, "why": why, "confidence": "estimate"} for name in names[:10]]


def _app_ranking(place_type: str, point: dict) -> tuple[tuple[str, ...], str]:
    """Retorna dez apps prováveis, priorizando a ocasião do ponto."""
    name = str(point.get("name") or "").casefold()
    kind = str(point.get("kind") or "").casefold()
    if place_type == "aeroporto":
        if "estacion" in name or kind == "mobilidade":
            return (("Google Maps", "Waze", "Uber", "99", "WhatsApp", "Google", "Instagram", "Spotify", "iFood", "Mercado Livre"), "rota, retirada e coordenação de chegada ou saída")
        return (("WhatsApp", "Google Maps", "Uber", "99", "LATAM", "GOL", "Azul", "Instagram", "YouTube", "Spotify"), "coordenação e entretenimento na jornada de viagem")
    if place_type == "shopping":
        if "praça" in name or "gastronomia" in name:
            return (("WhatsApp", "Instagram", "iFood", "Google Maps", "TikTok", "YouTube", "Mercado Livre", "Uber", "99", "Spotify"), "escolha de alimentação, encontro e permanência no mall")
        if "estacion" in name:
            return (("Google Maps", "Waze", "Uber", "99", "WhatsApp", "Instagram", "Google", "Mercado Livre", "iFood", "Spotify"), "acesso, retirada e decisão de compra antes ou depois da visita")
        return (("WhatsApp", "Instagram", "Google", "TikTok", "YouTube", "Mercado Livre", "iFood", "Uber", "99", "Pinterest"), "descoberta de marcas, comparação e combinação da visita")
    if "acesso" in name or "metrô" in name or "ônibus" in name:
        return (("Google Maps", "Waze", "Uber", "99", "WhatsApp", "Instagram", "TikTok", "Spotify", "iFood", "YouTube"), "rota, encontro e deslocamento no acesso ao lugar")
    return (("WhatsApp", "Instagram", "TikTok", "Google Maps", "Uber", "99", "YouTube", "Spotify", "iFood", "Facebook"), "descoberta, combinação da visita e entretenimento durante a permanência")


def enrich_point_inventory(payload: dict, *, place_type: str, city: str, overwrite: bool = False) -> dict:
    """Inclui estimativas Top 10 por ponto sem alegar uma medição por raio."""
    result = deepcopy(payload)
    portals = PORTALS_BY_CITY.get(city, PORTALS_BY_CITY["sp"])
    for point in result.get("points") or []:
        apps, app_why = _app_ranking(place_type, point)
        portal_why = f"notícias e contexto local durante {str(point.get('name') or 'a permanência').lower()}"
        if overwrite or not point.get("apps"):
            point["apps"] = _items(apps, app_why)
        if overwrite or not point.get("portals"):
            point["portals"] = _items(portals, portal_why)
    research = result.setdefault("research", {})
    known_urls = {item.get("url") for item in research.get("sources") or [] if isinstance(item, dict)}
    research["sources"] = list(research.get("sources") or []) + [item for item in INVENTORY_SOURCES if item["url"] not in known_urls]
    return result


CHANNEL_IDENTITIES = {
    "whatsapp": {"short": "W", "color": "#25D366", "url": "https://www.whatsapp.com/", "icon": "images/canais/whatsapp.svg"},
    "instagram": {"short": "IG", "color": "#E4405F", "url": "https://www.instagram.com/", "icon": "images/creative-viewers/instagram.svg"},
    "youtube": {"short": "YT", "color": "#FF0000", "url": "https://www.youtube.com/", "icon": "images/creative-viewers/youtube.svg"},
    "google maps": {"short": "G", "color": "#4285F4", "url": "https://maps.google.com/", "icon": "images/canais/google-dv360.svg"},
    "google": {"short": "G", "color": "#4285F4", "url": "https://www.google.com.br/", "icon": "images/canais/google-dv360.svg"},
    "uber": {"short": "U", "color": "#000000", "url": "https://www.uber.com/br/pt-br/", "icon": "images/canais/uber.png"},
    "99": {"short": "99", "color": "#FFDD00", "url": "https://99app.com/", "icon": "images/canais/99.svg"},
    "g1": {"short": "g1", "color": "#C4170C", "url": "https://g1.globo.com/", "icon": "images/canais/g1-globo.svg"},
    "globo": {"short": "G", "color": "#E56B19", "url": "https://www.globo.com/", "icon": "images/canais/globoplay.png"},
    "tiktok": {"short": "TT", "color": "#111111", "url": "https://www.tiktok.com/", "icon": "images/canais/tiktok.png"},
    "spotify": {"short": "S", "color": "#1ED760", "url": "https://open.spotify.com/", "icon": "images/canais/spotify.svg"},
    "latam": {"short": "LA", "color": "#5C0F8B", "url": "https://www.latamairlines.com/br/pt"},
    "gol": {"short": "GOL", "color": "#F58220", "url": "https://www.voegol.com.br/"},
    "azul": {"short": "AZ", "color": "#005DAA", "url": "https://www.voeazul.com.br/"},
    "mercado livre": {"short": "ML", "color": "#FFE600", "url": "https://www.mercadolivre.com.br/"},
    "linkedin": {"short": "in", "color": "#0A66C2", "url": "https://www.linkedin.com/", "icon": "images/creative-viewers/linkedin.svg"},
    "ifood": {"short": "iF", "color": "#EA1D2C", "url": "https://www.ifood.com.br/", "icon": "images/canais/ifood.svg"},
    "facebook": {"short": "f", "color": "#1877F2", "url": "https://www.facebook.com/", "icon": "images/creative-viewers/facebook.svg"},
    "pinterest": {"short": "P", "color": "#BD081C", "url": "https://br.pinterest.com/"},
    "magalu": {"short": "M", "color": "#0086FF", "url": "https://www.magazineluiza.com.br/"},
    "uol": {"short": "UOL", "color": "#6F2C91", "url": "https://www.uol.com.br/", "icon": "images/canais/uol.png"},
    "sympla": {"short": "SY", "color": "#0095FF", "url": "https://www.sympla.com.br/"},
    "bandsintown": {"short": "BI", "color": "#00B4B3", "url": "https://www.bandsintown.com/"},
}


CHANNELS_BY_TYPE = {
    "aeroporto": (
        ("WhatsApp", "app", "coordenação da viagem e chegada"),
        ("Instagram", "app", "conteúdo e descoberta durante a espera"),
        ("YouTube", "app/site", "vídeo em sessões de maior permanência"),
        ("Google Maps", "app/site", "rota, terminal e deslocamento"),
        ("Uber", "app", "ida e saída do aeroporto"),
        ("99", "app", "mobilidade no acesso e desembarque"),
        ("G1", "site/app", "notícias nos intervalos da viagem"),
        ("Globo", "site/app", "vídeo, esporte e entretenimento"),
        ("TikTok", "app", "vídeo curto no tempo de espera"),
        ("Spotify", "app", "áudio no deslocamento"),
        ("LATAM", "app/site", "jornada de embarque e viagem"),
        ("GOL", "app/site", "jornada de embarque e viagem"),
        ("Azul", "app/site", "jornada de embarque e viagem"),
        ("Mercado Livre", "app/site", "compras antes e depois da viagem"),
        ("LinkedIn", "app/site", "viagens a trabalho e conteúdo profissional"),
    ),
    "shopping": (
        ("WhatsApp", "app", "decisão em grupo e contato com lojas"),
        ("Instagram", "app", "descoberta de marcas, moda e gastronomia"),
        ("YouTube", "app/site", "vídeo e pesquisa de produtos"),
        ("Google", "app/site", "busca por loja, preço e horário"),
        ("TikTok", "app", "tendências, beleza, moda e comida"),
        ("iFood", "app", "alimentação e conveniência"),
        ("Mercado Livre", "app/site", "comparação e compra de produtos"),
        ("Uber", "app", "chegada e saída do complexo"),
        ("99", "app", "mobilidade no entorno"),
        ("G1", "site/app", "notícias durante a permanência"),
        ("Spotify", "app", "áudio no deslocamento e lazer"),
        ("Facebook", "app/site", "comunidades, eventos e comércio local"),
        ("Pinterest", "app/site", "inspiração para moda, casa e beleza"),
        ("Magalu", "app/site", "varejo e comparação de ofertas"),
        ("UOL", "site/app", "notícias, esporte e entretenimento"),
    ),
    "evento": (
        ("WhatsApp", "app", "combinação de encontro e compartilhamento"),
        ("Instagram", "app", "registro, descoberta e conteúdo do lugar"),
        ("YouTube", "app/site", "vídeo ligado a cultura e entretenimento"),
        ("TikTok", "app", "vídeo curto antes, durante e depois da visita"),
        ("Google Maps", "app/site", "rota, acesso e pontos próximos"),
        ("Uber", "app", "chegada e saída"),
        ("99", "app", "mobilidade no entorno"),
        ("Spotify", "app", "música e áudio no deslocamento"),
        ("G1", "site/app", "agenda, cidade e notícias"),
        ("Globo", "site/app", "entretenimento, esporte e vídeo"),
        ("iFood", "app", "alimentação no entorno"),
        ("Facebook", "app/site", "eventos e comunidades"),
        ("UOL", "site/app", "notícias, esporte e entretenimento"),
        ("Sympla", "app/site", "descoberta e ingresso de eventos"),
        ("Bandsintown", "app/site", "agenda de shows e afinidade cultural"),
    ),
}

PREMIUM_PLACES = {
    "diamond-mall",
    "iguatemi-sao-paulo",
    "jk-iguatemi",
    "shopping-leblon",
}


def _ranking(place_type: str) -> list[dict]:
    rows = CHANNELS_BY_TYPE.get(place_type, CHANNELS_BY_TYPE["evento"])
    return [
        {"rank": index, "name": name, "kind": kind, "why": why, "confidence": "estimate"}
        for index, (name, kind, why) in enumerate(rows, start=1)
    ]


def _with_identity(item: dict, rank: int) -> dict:
    row = dict(item, rank=rank)
    identity = CHANNEL_IDENTITIES.get(str(item.get("name") or "").casefold(), {})
    row["short"] = identity.get("short") or str(item.get("name") or "?")[:2].upper()
    row["color"] = identity.get("color") or "#167A3A"
    row["url"] = identity.get("url") or ""
    row["icon"] = identity.get("icon") or ""
    return row


def _demographics(place_type: str, slug: str, city_label: str, neighborhoods: list[str]) -> dict:
    origin = ", ".join(neighborhoods[:3]) or city_label
    if place_type == "aeroporto":
        return {
            "age": "25–54 anos, com maior afinidade a trabalho e viagens em família",
            "gender": "Público misto; composição varia por rota e período",
            "income": "Renda média a alta, com recortes de maior ticket no embarque",
            "origin": f"Passageiros e acompanhantes de {city_label}; halo em {origin}",
        }
    if place_type == "shopping":
        income = "Renda média-alta a alta" if slug in PREMIUM_PLACES else "Renda média a média-alta"
        return {
            "age": "25–54 anos, com missões de compra, alimentação e lazer",
            "gender": "Público misto; categoria da campanha define o recorte final",
            "income": income,
            "origin": f"Frequentadores do mall e moradores do entorno de {origin}",
        }
    return {
        "age": "18–44 anos, com variação conforme evento, dia e programação",
        "gender": "Público misto; o evento define a composição real",
        "income": "Renda variada; afinidade cultural e ocasião são mais úteis que classe isolada",
        "origin": f"Visitantes do lugar e público do entorno de {origin}",
    }


def _targets(place_type: str) -> list[str]:
    if place_type == "aeroporto":
        return ["Viajantes a trabalho", "Viagens em família", "Mobilidade e chegada", "Compras e serviços de viagem"]
    if place_type == "shopping":
        return ["Compradores do mall", "Famílias e lazer", "Moda, beleza e casa", "Alimentação e conveniência"]
    return ["Visitantes do lugar", "Cultura e entretenimento", "Mobilidade e chegada", "Gastronomia no entorno"]


def default_audience_plan() -> dict:
    return {
        "window": "4 semanas",
        "title": "A campanha cria uma audiência que continua útil.",
        "steps": [
            {"title": "Capturar", "body": "Identificar dispositivos elegíveis que estiveram no recorte contratado."},
            {"title": "Qualificar", "body": "Separar ponto principal, subáreas e halo sem somar a mesma pessoa duas vezes."},
            {"title": "Ativar", "body": "Entregar mídia em apps e sites durante as quatro semanas do plano."},
            {"title": "Reutilizar", "body": "Levar a audiência validada para outras campanhas e novas mensagens."},
        ],
        "reuse_note": (
            "A reutilização depende do consentimento, do contrato com o parceiro de dados "
            "e da janela de retenção disponível em cada campanha."
        ),
    }


def enrich_public_payload(payload: dict, *, place_type: str, slug: str, city_label: str) -> dict:
    """Completa lacunas de planejamento sem substituir dados curados."""
    city = {"Belo Horizonte": "bh", "São Paulo": "sp", "Rio de Janeiro": "rj"}.get(city_label, "sp")
    result = enrich_point_inventory(payload, place_type=place_type, city=city)
    catchment = result.get("catchment") or {}
    curated = []
    for point in result.get("points") or []:
        for item in (point.get("apps") or []) + (point.get("portals") or []):
            name = item.get("name")
            if name and not any(row.get("name", "").lower() == name.lower() for row in curated):
                curated.append(
                    {
                        "rank": len(curated) + 1,
                        "name": name,
                        "kind": "app/site",
                        "why": item.get("why") or f"afinidade com {point.get('name') or 'o recorte'}",
                        "confidence": item.get("confidence") or "estimate",
                    }
                )
    ranking = result.get("channel_ranking") or curated
    for item in _ranking(place_type):
        if len(ranking) >= 15:
            break
        if not any(row.get("name", "").lower() == item["name"].lower() for row in ranking):
            ranking.append(item)
    result["channel_ranking"] = [_with_identity(item, index) for index, item in enumerate(ranking[:15], start=1)]
    defaults = _demographics(place_type, slug, city_label, catchment.get("neighborhoods") or [])
    current_demo = result.get("demographics") or {}
    result["demographics"] = {key: current_demo.get(key) or value for key, value in defaults.items()}
    if not result.get("target_audience"):
        result["target_audience"] = _targets(place_type)
    if not (result.get("income") or {}).get("label"):
        result["income"] = {
            "value": None,
            "label": result["demographics"]["income"],
            "year": None,
            "source": "Premissa de planejamento CentralComm",
            "source_status": "estimate",
            "note": "Validar com o parceiro de dados antes da contratação.",
        }
    defaults_plan = default_audience_plan()
    current_plan = result.get("audience_plan") or {}
    plan = {key: current_plan.get(key) or value for key, value in defaults_plan.items()}
    result["audience_plan"] = plan
    return result
