"""Sessão 3 — DOOH, geofencing e os 4 aeroportos do Places."""

from ...places.catalog import CONGONHAS, CONFINS, GALEAO, SANTOS_DUMONT
from .markup import block, esc, figure, h2, h3, notes, p, page, sources, ul

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
    code = place.get("code")
    title = place.get("title")
    pax = _metric(place, "passengers")
    addressable = _metric(place, "addressable")
    copy = (
        f'<article class="ts-place" data-place="{esc(place.get("slug"))}" id="place-{esc(place.get("slug"))}">'
        f"<h3>{esc(code)} · {esc(title)}</h3>"
        f"<p class=\"ts-place-kicker\">{esc(place.get('subtitle'))}</p>"
        + p(
            f"<strong>ANAC 2025.</strong> {esc(pax)} passageiros no ano. "
            f"Endereçáveis no recorte, 4 semanas (estimate): {esc(addressable)}."
        )
        + (p(caption) if caption else "")
        + p(f"<strong>Não misturar.</strong> {regra}")
        + "</article>"
    )
    art = figure(hero, f"{code} {title}", "ts-page-art ts-place-hero")
    extra = points or ""
    return page("split", copy + extra, art)


def html():
    cgh, gig, cnf, sdu = AIRPORTS
    return (
        notes(
            "<strong>Palco · 20 min.</strong> Conceito em 2 páginas, "
            "um aeroporto por página. Fotos da base. Mall: uma frase."
        )
        + page(
            "title",
            h2("O lugar não é a audiência")
            + p("Tela no lugar não é quem mora no entorno."),
        )
        + page(
            "split",
            block(
                "tese",
                h3("Dois buys")
                + p(
                    "DOOH: oportunidade de ver no sítio. Aeroporto não é "
                    "mobiliário urbano — o passageiro está no processo."
                )
                + p(
                    "Geofencing compra a cerca. Cerca não é presença. "
                    "Bacia IBGE ≠ quem embarcou. Halo não soma com o terminal."
                )
                + p(
                    "4 semanas = anual ÷ 13. Únicos ≈ × 0,62. Endereçáveis ≈ × 0,38. "
                    "Vocês não compram Congonhas. Compram T1, ou Campo Belo, ou Moema."
                ),
            ),
        )
        + page(
            "copy",
            block(
                "dado",
                h3("Os quatro aeroportos — não somar")
                + p(
                    "ANAC 2025: Congonhas 24,6 mi · Galeão 17,8 mi · "
                    "Confins 13,2 mi · Santos Dumont 6,2 mi."
                ),
            ),
        )
        + _airport_card(
            cgh,
            "T1, Campo Belo e Moema são três buys. A cidade em volta não é o saguão.",
            "Aeroporto no meio de São Paulo. O recorte que a campanha "
            "compra primeiro é o T1; Moema é halo de quem circula, não "
            "de quem voou.",
        )
        + _airport_card(
            gig,
            "Internacional é recorte. Não use o 17,8 mi como se fosse o T2 internacional.",
            "T2 na Ilha do Governador. Internacional de um lado; a "
            "Vinte de Janeiro do outro. A ilha é bacia, não embarque.",
        )
        + _airport_card(
            cnf,
            "Terminal versus corredor MG-010. Internacional ~4–5% — selo a validar.",
            "Quem voa por Minas e quem só cruza a MG-010. O "
            "internacional de Confins fica 8–14 mil endereçáveis — "
            "não escalar ticket alto em cima desse recorte sem validar.",
        )
        + _airport_card(
            sdu,
            "Pistas ficam fora do comercial. Terminal e VLT/Glória são os buys.",
            "Ponte no centro do Rio. 6,2 mi no ano (o book antigo com "
            "4,9 mi está defasado). Não vender a pista.",
        )
        + page(
            "copy",
            block(
                "tese",
                h3("Como entra no plano")
                + ul(
                    [
                        "Unidade de valor: presença no recorte ou dwell no saguão — não UU nacional.",
                        "First-wave: um aeroporto, um ponto. Escala só depois.",
                        "Mall e evento usam o mesmo método — não cabem neste bloco.",
                        "Na banca: se o brief tiver praça física, Places é família.",
                    ]
                ),
            ),
        )
        + sources(
            "ANAC — movimento de passageiros 2025 (CNF 13.183.039 · CGH 24.583.610 · SDU 6.184.233 · GIG 17.836.134)",
            "IBGE Censo 2022 — bacias residenciais Places (não são presença no terminal)",
            "CentralX Places — metodologia de 4 semanas, únicos e endereçáveis",
        )
    )
