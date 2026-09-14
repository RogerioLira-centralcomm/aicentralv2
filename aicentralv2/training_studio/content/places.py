"""Sessão 3 — DOOH, geofencing e os 4 aeroportos do Places."""

from ...places.catalog import CONGONHAS, CONFINS, GALEAO, SANTOS_DUMONT
from .markup import block, esc, figure, h2, h3, notes, p, sources, ul

NOTAS = {
    "tese": "Tela no lugar não é audiência do lugar. Places vende o recorte, não o aeroporto inteiro.",
    "nao_repetir": "Não somar os 4 aeroportos. Não gerar hero. Mall e Ibirapuera só numa frase.",
    "pergunta": "Neste brief, vocês estão comprando o saguão ou quem mora no entorno?",
    "tempo": "20 minutos",
}

FONTES = [
    {
        "url": "oficial:anac-2025",
        "titulo": "ANAC — movimento de passageiros 2025",
        "resumo": "CGH 24.583.610 · GIG 17.836.134 · CNF 13.183.039 · SDU 6.184.233. Não somar.",
    },
    {
        "url": "oficial:ibge-censo-2022",
        "titulo": "IBGE Censo 2022 — bacias residenciais Places",
        "resumo": "Quem mora no entorno. Não é presença no terminal.",
    },
    {
        "url": "oficial:places-metodologia",
        "titulo": "CentralX Places — metodologia",
        "resumo": "4 semanas = anual ÷ 13. Únicos ≈ movimentos × 0,62. Endereçáveis ≈ únicos × 0,38.",
    },
]

AIRPORTS = (CONGONHAS, GALEAO, CONFINS, SANTOS_DUMONT)


def _metric(place, key, fallback=""):
    metrics = ((place.get("payload") or {}).get("metrics") or {})
    item = metrics.get(key) or {}
    return item.get("label") or fallback


def _media(place):
    return (place.get("payload") or {}).get("media") or {}


def _point_figure(place, kind):
    for point in (place.get("payload") or {}).get("points") or []:
        if point.get("kind") == kind and point.get("image_url"):
            return figure(
                point["image_url"],
                f"{place.get('code')} {point.get('name')}",
                "ts-place-point",
            )
    return ""


def _airport_card(place, regra, caption="", points=""):
    media = _media(place)
    hero = media.get("hero_url") or ""
    mapa = media.get("map_url") or ""
    code = place.get("code")
    title = place.get("title")
    pax = _metric(place, "passengers")
    addressable = _metric(place, "addressable")
    return (
        f'<article class="ts-place" data-place="{esc(place.get("slug"))}" id="place-{esc(place.get("slug"))}">'
        f"{figure(hero, f'Hero {code} {title}', 'ts-place-hero')}"
        f"{figure(mapa, f'Mapa {code}', 'ts-place-map')}"
        f"<h3>{esc(code)} · {esc(title)}</h3>"
        f"<p class=\"ts-place-kicker\">{esc(place.get('subtitle'))}</p>"
        + p(
            f"<strong>ANAC 2025.</strong> {esc(pax)} passageiros no ano. "
            f"Endereçáveis no recorte principal, 4 semanas (estimate, não somar "
            f"com outros pontos): {esc(addressable)}."
        )
        + (points or "")
        + (p(caption) if caption else "")
        + p(f"<strong>Não misturar.</strong> {regra}")
        + "</article>"
    )


def html():
    cgh, gig, cnf, sdu = AIRPORTS
    return (
        h2("DOOH, geofencing e Places")
        + notes(
            "<strong>Palco · 20 min.</strong> Conceito em 6 minutos, quatro "
            "aeroportos em 12, fechamento em 2. Usar as fotos da base. "
            "Mall e evento: uma frase. Não abrir o CMS."
        )
        + block(
            "tese",
            h3("Tela no lugar × audiência do lugar")
            + p(
                "DOOH é oportunidade de ver no sítio: dwell, ângulo, fluxo. "
                "Aeroporto não é mobiliário urbano — o passageiro está preso "
                "no processo, não na calçada. Programático de tela e face "
                "clássica são buys diferentes; não misturar CPM de rua com "
                "saguão.",
                "Geofencing compra a cerca. Cerca não é presença. Quem mora "
                "na bacia IBGE não é quem embarcou. Halo (MG-010, Moema, "
                "Ilha do Governador) não soma com o terminal. Movimento de "
                "4 semanas = anual ÷ 13. Únicos ≈ movimentos × 0,62. "
                "Endereçáveis em app e portal ≈ únicos × 0,38. Os raios "
                "não se somam. Fonte: metodologia Places / ANAC 2025.",
                "Places no CentralX transforma o lugar em SKU: recorte, "
                "formato (display no app, vídeo no saguão, portais) e "
                "one-page de venda. Vocês não compram “Congonhas”. Compram "
                "T1 300 m, ou Campo Belo, ou Moema.",
            ),
        )
        + block(
            "dado",
            h3("Os quatro aeroportos — não somar")
            + p(
                "Passageiros ANAC 2025: Congonhas 24,6 mi · Galeão 17,8 mi · "
                "Confins 13,2 mi · Santos Dumont 6,2 mi. Bacia residencial "
                "é Censo 2022, não presença no terminal. Fotos e mapas saem "
                "do acervo Places — nenhuma arte gerada neste bloco."
            )
            + _airport_card(
                cgh,
                "T1, Campo Belo e Moema são três buys. A cidade em volta não é o saguão.",
                "Aeroporto no meio de São Paulo. O recorte que a campanha "
                "compra primeiro é o T1; Moema é halo de quem circula, não "
                "de quem voou.",
                f"{_point_figure(cgh, 'terminal')}{_point_figure(cgh, 'halo')}",
            )
            + _airport_card(
                gig,
                "Internacional é recorte. Não use o 17,8 mi como se fosse o T2 internacional.",
                "T2 na Ilha do Governador. Internacional de um lado; a "
                "Vinte de Janeiro do outro. A ilha é bacia, não embarque.",
                f"{_point_figure(gig, 'terminal')}{_point_figure(gig, 'premium')}",
            )
            + _airport_card(
                cnf,
                "Terminal versus corredor MG-010. Internacional ~4–5% — selo a validar.",
                "Quem voa por Minas e quem só cruza a MG-010. O "
                "internacional de Confins fica 8–14 mil endereçáveis — "
                "não escalar ticket alto em cima desse recorte sem validar.",
                f"{_point_figure(cnf, 'terminal')}{_point_figure(cnf, 'halo')}",
            )
            + _airport_card(
                sdu,
                "Pistas ficam fora do comercial. Terminal e VLT/Glória são os buys.",
                "Ponte no centro do Rio. 6,2 mi no ano (o book antigo com "
                "4,9 mi está defasado). Não vender a pista.",
                f"{_point_figure(sdu, 'terminal')}{_point_figure(sdu, 'mobilidade')}",
            ),
        )
        + block(
            "tese",
            h3("Como entra no plano")
            + ul(
                [
                    "Unidade de valor: presença no recorte (7/15/30 dias) ou dwell no saguão — não UU nacional.",
                    "First-wave: um aeroporto, um ponto. Escala só depois.",
                    "O mesmo método vale para mall e evento (Diamond, Iguatemi, Ibirapuera, Expominas) — não cabem neste bloco.",
                    "Na banca: se o brief tiver praça física, Places é família, não “extra criativo”.",
                ]
            ),
        )
        + sources(
            "ANAC — movimento de passageiros 2025 (CNF 13.183.039 · CGH 24.583.610 · SDU 6.184.233 · GIG 17.836.134)",
            "IBGE Censo 2022 — bacias residenciais Places (não são presença no terminal)",
            "CentralX Places — metodologia de 4 semanas, únicos e endereçáveis",
        )
    )
