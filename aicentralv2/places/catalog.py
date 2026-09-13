"""Seed e constantes dos Places. Passageiros: ANAC 2025. Alcance de ponto: endereçável."""

from __future__ import annotations

from .brand import zone_color
from .schema import normalize_payload

ANAC_2025 = "ANAC — movimento de passageiros 2025"
FOUR_WEEKS_NOTE = "Anual ÷ 13. Movimentos físicos, não devices únicos."
ADDRESSABLE_NOTE = (
    "Únicos ≈ movimentos de 4 semanas × 0,62. "
    "Endereçáveis em apps e portais ≈ únicos × 0,38. "
    "Os raios não se somam."
)
# Confins 7.350 + Lagoa Santa 75.145 + Vespasiano 129.246 (IBGE).
CNF_CATCHMENT_POP = 211_741
CNF_CATCHMENT_KM2 = 42.462 + 229.741 + 70.456
# Campo Belo 71.034 + Moema 81.899 (IBGE / SMUL). Áreas: 8,77 + 9,08 km².
CGH_CATCHMENT_POP = 152_933
CGH_CATCHMENT_KM2 = 8.77 + 9.08
# Centro 23.642 + Glória 7.120 + Catete 22.295 + Flamengo 43.099 (IPP / IBGE).
SDU_CATCHMENT_POP = 96_156
SDU_CATCHMENT_KM2 = 5.425 + 1.140 + 0.681 + 1.646
# RA Ilha do Governador 211.018 hab / 40,81 km² (IPP / IBGE Censo 2022).
GIG_CATCHMENT_POP = 211_018
GIG_CATCHMENT_KM2 = 40.81

APPS = ["Display no app", "Vídeo vertical", "Interstitial"]
PORTALS = ["Portais no celular", "Portais premium"]


def _metric(value, label, *, year=2025, source=ANAC_2025, source_status="official", note=""):
    return {
        "value": value,
        "label": label,
        "year": year,
        "source": source,
        "source_status": source_status,
        "note": note,
    }


def _zone(item):
    item = dict(item)
    item.setdefault("color", zone_color(item.get("type")))
    item.setdefault("reach_status", "estimate" if item.get("reach") != "A validar" else "to_validate")
    return item


def _fence(item):
    item = dict(item)
    item.setdefault("reach_status", "estimate")
    item.setdefault("formats", APPS + PORTALS)
    return item


def _geo(lat, lng, zoom=15):
    return {"lat": lat, "lng": lng, "zoom": zoom}


def _offer(lead, lines):
    return {"lead": lead, "lines": [{"title": title, "body": body} for title, body in lines]}


CONFINS = {
    "slug": "confins",
    "place_type": "aeroporto",
    "city": "bh",
    "status": "published",
    "title": "Confins",
    "code": "CNF",
    "operator": "BH Airport (Motiva / Zurich) · Minas Gerais",
    "subtitle": "Quem voa por Minas e quem cruza a MG-010. Encontre essa gente no celular.",
    "payload": normalize_payload(
        {
            "metrics": {
                "passengers": _metric(13_183_039, "13,2 mi"),
                "four_weeks": _metric(
                    1_014_080,
                    "~1,01 mi",
                    source="Derivado do movimento ANAC 2025",
                    source_status="estimate",
                    note=FOUR_WEEKS_NOTE,
                ),
                "addressable": _metric(
                    240_000,
                    "190–280 mil",
                    source="Estimativa endereçável no terminal, 4 semanas",
                    source_status="estimate",
                    note=ADDRESSABLE_NOTE,
                ),
            },
            "catchment": {
                "population": _metric(
                    CNF_CATCHMENT_POP,
                    "212 mil",
                    source="IBGE Censo 2022 — Confins, Lagoa Santa e Vespasiano",
                    source_status="official",
                    note="7.350 + 75.145 + 129.246. Municípios do corredor, não presença no terminal.",
                ),
                "density": _metric(
                    round(CNF_CATCHMENT_POP / CNF_CATCHMENT_KM2),
                    "~620 hab/km²",
                    source="IBGE Censo 2022 — densidade ponderada pela área dos 3 municípios",
                    source_status="official",
                    note="211.741 hab / 342,66 km². Densidade da bacia, não do sítio aeroportuário.",
                ),
                "impacted": _metric(
                    None,
                    "80–130 mil",
                    source="Halo do corredor MG-010, 4 semanas, endereçável",
                    source_status="estimate",
                    note="Halo. Não some ao terminal.",
                ),
                "neighborhoods": ["Confins", "Lagoa Santa", "Vespasiano", "corredor MG-010"],
                "profile": "Quem trabalha em Belo Horizonte, famílias no feriado e o fluxo do norte da RMBH. O terminal concentra o embarque; a MG-010 pega quem só passou.",
            },
            "audiences": [
                ["Quem passou pelo terminal", "Presença no saguão em 7, 15 ou 30 dias."],
                ["Quem voa de novo", "Recorrência com critério objetivo — não é um único embarque."],
                ["Doméstico", "O grosso do movimento de Confins."],
                ["Internacional", "Fatia pequena (~4–5%). Vale para ticket alto, não para escala."],
                ["Quem busca o carro ou o app", "Estacionamento, curbside e descida."],
                ["Quem só passou na estrada", "Halo da MG-010. Não misturar com quem entrou no terminal."],
            ],
            "geo": _geo(-19.624445, -43.971944, 13),
            "points": [
                _fence(
                    {
                        "id": "cnf-terminal",
                        "name": "Terminal",
                        "kind": "terminal",
                        "lat": -19.624445,
                        "lng": -43.971944,
                        "radius_m": 350,
                        "radius_label": "350 m",
                        "reach": "190–280 mil",
                        "formats": ["Display no app", "Vídeo no saguão", "Portais"],
                        "audiences": ["Quem está no saguão", "Quem passou e segue na cidade"],
                        "commercial": "Quem está no saguão, no check-in e na espera. É o recorte que a campanha compra primeiro.",
                        "source": "Sítio do terminal",
                        "note": "Polígono do prédio. Não inclui pista.",
                        "image_url": "/static/images/places/generated/confins-cnf-terminal-pt-da9534f8.png",
                    }
                ),
                _fence(
                    {
                        "id": "cnf-embarque",
                        "name": "Embarque doméstico",
                        "kind": "embarque",
                        "lat": -19.6256,
                        "lng": -43.9748,
                        "radius_m": 250,
                        "radius_label": "250 m",
                        "reach": "95–140 mil",
                        "formats": ["Vídeo vertical", "Display no app"],
                        "audiences": ["Quem está embarcando", "Voo doméstico"],
                        "commercial": "Quem está saindo. Banco, telecom e varejo cabem neste raio curto.",
                        "source": "Check-in ao gate doméstico",
                        "note": "Subconjunto do terminal. Não some ao core.",
                        "image_url": "/static/images/places/generated/confins-cnf-embarque-pt-05e645ef.png",
                    }
                ),
                _fence(
                    {
                        "id": "cnf-internacional",
                        "name": "Internacional",
                        "kind": "premium",
                        "lat": -19.6229,
                        "lng": -43.9756,
                        "radius_m": 200,
                        "radius_label": "200 m",
                        "reach": "8–14 mil",
                        "reach_status": "to_validate",
                        "formats": ["Vídeo", "Display"],
                        "audiences": ["Quem voa para fora", "Ticket alto"],
                        "commercial": "Pouca gente, ticket alto. Luxo, cartão e seguro. O volume ainda calibra na plataforma.",
                        "source": "Área internacional · ~4–5% do movimento",
                        "note": "A validar na plataforma de location data.",
                        "image_url": "/static/images/places/generated/confins-cnf-internacional-pt-ef5b59a6.png",
                    }
                ),
                _fence(
                    {
                        "id": "cnf-mobilidade",
                        "name": "Estacionamento",
                        "kind": "mobilidade",
                        "lat": -19.6278,
                        "lng": -43.9684,
                        "radius_m": 400,
                        "radius_label": "400 m",
                        "reach": "70–110 mil",
                        "formats": ["Display no app", "7 e 15 dias"],
                        "audiences": ["Quem busca o carro", "Quem espera na porta"],
                        "commercial": "Quem busca o carro ou o app. Combustível, transporte e conveniência.",
                        "source": "Curbside e pátios",
                        "image_url": "/static/images/places/generated/confins-cnf-mobilidade-pt-1a41febf.png",
                    }
                ),
                _fence(
                    {
                        "id": "cnf-corredor",
                        "name": "MG-010",
                        "kind": "halo",
                        "lat": -19.6402,
                        "lng": -43.9548,
                        "radius_m": 1200,
                        "radius_label": "1,2 km",
                        "reach": "80–130 mil",
                        "formats": ["Portais", "Display"],
                        "audiences": ["Quem só passou na estrada"],
                        "commercial": "Quem só passou na estrada. Separado de quem entrou no saguão.",
                        "source": "Acesso viário",
                        "image_url": "/static/images/places/generated/confins-cnf-corredor-pt-7316f28c.png",
                    }
                ),
            ],
            "media": {
                "hero_url": "/static/images/places/generated/confins-hero-29d2ce76.png",
                "map_url": "/static/images/places/generated/confins-map-611e4c35.png",
            },
            "zones": [
                _zone(
                    {
                        "id": "CNF-01",
                        "type": "CORE",
                        "name": "Terminal",
                        "radius": "350 m",
                        "reach": "190–280 mil",
                        "description": "Prédio do terminal e frente de passageiros. É o recorte que a campanha compra primeiro.",
                        "formats": APPS + PORTALS,
                        "audiences": ["Visitante do aeroporto", "Viajante recente"],
                        "commercial": "Entrada da campanha. Não some aos outros raios.",
                        "polygon": "43,43 57,38 64,45 61,57 50,61 41,55",
                    }
                ),
                _zone(
                    {
                        "id": "CNF-02",
                        "type": "DEPARTURES",
                        "name": "Embarque doméstico",
                        "radius": "250 m",
                        "reach": "95–140 mil",
                        "description": "Check-in, inspeção e gate doméstico.",
                        "formats": ["Vídeo vertical", "Rich media"] + PORTALS,
                        "audiences": ["Embarque ativo", "Viajante doméstico"],
                        "commercial": "Alta intenção na saída.",
                        "polygon": "60,44 78,40 84,48 80,60 65,59 58,53",
                    }
                ),
                _zone(
                    {
                        "id": "CNF-03",
                        "type": "PREMIUM",
                        "name": "Internacional",
                        "radius": "200 m",
                        "reach": "8–14 mil",
                        "reach_status": "to_validate",
                        "description": "Jornada internacional. Em 2025 ficou em ~4–5% do movimento.",
                        "formats": ["Vídeo premium", "Rich media"],
                        "audiences": ["Internacional", "Ticket alto"],
                        "commercial": "Pouco volume, recorte caro.",
                        "polygon": "18,43 40,39 43,53 36,61 20,58 13,50",
                    }
                ),
                _zone(
                    {
                        "id": "CNF-04",
                        "type": "MOBILITY",
                        "name": "Estacionamento e apps",
                        "radius": "400 m",
                        "reach": "70–110 mil",
                        "description": "Pátios, curbside e descida.",
                        "formats": APPS,
                        "audiences": ["Mobilidade"],
                        "commercial": "Apps e conveniência.",
                        "polygon": "37,64 66,62 73,73 64,83 39,84 30,75",
                    }
                ),
                _zone(
                    {
                        "id": "CNF-05",
                        "type": "HALO",
                        "name": "Corredor MG-010",
                        "radius": "1,2 km",
                        "reach": "80–130 mil",
                        "description": "Estrada de acesso. Separado do terminal.",
                        "formats": PORTALS + ["Display"],
                        "audiences": ["Proximidade"],
                        "commercial": "Escala sem fingir que a pessoa entrou no saguão.",
                        "polygon": "5,73 31,68 35,80 20,91 4,88",
                    }
                ),
            ],
            "offer": _offer(
                "Em Confins você alcança quem está no terminal e quem passou pela MG-010.",
                [
                    ("No saguão", "Display no app e vídeo no saguão para quem circula no terminal e no check-in."),
                    ("Na estrada", "Portais para quem passou pela MG-010 sem entrar no prédio."),
                    ("7 e 15 dias", "Quem já passou por Confins segue no celular fora do aeroporto."),
                ],
            ),
            "methodology": {
                "title": "Como o número é feito",
                "body": (
                    "Passageiros da ANAC não são o que a campanha compra. "
                    "O número do ponto é quem dá para alcançar neste raio, no celular, em 4 semanas. "
                    "Os raios não se somam — a mesma pessoa atravessa vários no mesmo dia."
                ),
                "steps": [],
                "trust": "",
            },
        }
    ),
}

CONGONHAS = {
    "slug": "congonhas",
    "place_type": "aeroporto",
    "city": "sp",
    "status": "published",
    "title": "Congonhas",
    "code": "CGH",
    "operator": "Aena Brasil · São Paulo",
    "subtitle": "O aeroporto no meio da cidade. T1, Campo Belo e Moema.",
    "payload": normalize_payload(
        {
            "metrics": {
                "passengers": _metric(24_583_610, "24,6 mi"),
                "four_weeks": _metric(
                    1_891_047,
                    "~1,89 mi",
                    source="Derivado do movimento ANAC 2025",
                    source_status="estimate",
                    note=FOUR_WEEKS_NOTE,
                ),
                "addressable": _metric(
                    470_000,
                    "380–560 mil",
                    source="Estimativa endereçável no T1, 4 semanas",
                    source_status="estimate",
                    note=ADDRESSABLE_NOTE,
                ),
            },
            "catchment": {
                "population": _metric(
                    CGH_CATCHMENT_POP,
                    "153 mil",
                    source="IBGE Censo 2022 / SMUL — distritos Campo Belo e Moema",
                    source_status="official",
                    note="71.034 + 81.899. Recorte distrital que contém o aeroporto.",
                ),
                "density": _metric(
                    round(CGH_CATCHMENT_POP / CGH_CATCHMENT_KM2),
                    "~8,6 mil hab/km²",
                    source="IBGE Censo 2022 — média dos distritos Campo Belo (8,77 km²) e Moema (9,08 km²)",
                    source_status="official",
                    note="152.933 hab / 17,85 km². O halo não é presença aeroportuária.",
                ),
                "impacted": _metric(
                    None,
                    "90–150 mil",
                    source="Halo Campo Belo / Moema, 4 semanas, endereçável",
                    source_status="estimate",
                    note="Separado do terminal. Não some.",
                ),
                "neighborhoods": ["Campo Belo", "Moema"],
                "profile": "Quem faz a ponte aérea, mora ao lado e pega o carro na Washington Luís. Aqui o aeroporto funciona como bairro.",
            },
            "audiences": [
                ["Ponte aérea", "Negócio e volta no mesmo dia."],
                ["Quem mora do lado", "Campo Belo e Moema — densidade alta, raio curto."],
                ["Quem pega o app na porta", "Táxi, descida e a avenida."],
                ["Quem passou e segue na cidade", "Retarget depois da visita."],
                ["Negócios", "Recorrência executiva."],
                ["Extensão no bairro", "Escala sem misturar com o T1."],
            ],
            "geo": _geo(-23.626111, -46.656389, 14),
            "points": [
                _fence(
                    {
                        "id": "cgh-terminal",
                        "name": "Terminal T1",
                        "kind": "terminal",
                        "lat": -23.626111,
                        "lng": -46.656389,
                        "radius_m": 300,
                        "radius_label": "300 m",
                        "reach": "380–560 mil",
                        "formats": ["Display no app", "Vídeo no T1", "Portais"],
                        "audiences": ["Quem está no T1", "Ponte aérea"],
                        "commercial": "O terminal no meio da cidade. Sem pista e sem o bairro.",
                        "source": "T1",
                        "image_url": "/static/images/places/generated/congonhas-cgh-terminal-pt-4976347b.png",
                    }
                ),
                _fence(
                    {
                        "id": "cgh-embarque",
                        "name": "Washington Luís",
                        "kind": "embarque",
                        "lat": -23.6279,
                        "lng": -46.6596,
                        "radius_m": 250,
                        "radius_label": "250 m",
                        "reach": "180–260 mil",
                        "formats": ["Vídeo vertical", "Display no app"],
                        "audiences": ["Quem está embarcando", "Negócios"],
                        "commercial": "A frente da Washington Luís. Quem está embarcando — raio curto.",
                        "source": "Acesso principal",
                        "image_url": "/static/images/places/generated/congonhas-cgh-embarque-pt-b31c703d.png",
                    }
                ),
                _fence(
                    {
                        "id": "cgh-apps",
                        "name": "Desembarque",
                        "kind": "mobilidade",
                        "lat": -23.6250,
                        "lng": -46.6538,
                        "radius_m": 250,
                        "radius_label": "250 m",
                        "reach": "160–230 mil",
                        "formats": ["Display no app", "7 e 15 dias"],
                        "audiences": ["Quem já chegou", "Quem pega o app"],
                        "commercial": "Quem já chegou. App, táxi e a saída para a cidade.",
                        "source": "Saída e ponto de apps",
                        "image_url": "/static/images/places/generated/congonhas-cgh-apps-pt-1495fb4d.png",
                    }
                ),
                _fence(
                    {
                        "id": "cgh-estacionamento",
                        "name": "Estacionamentos",
                        "kind": "mobilidade",
                        "lat": -23.6286,
                        "lng": -46.6541,
                        "radius_m": 350,
                        "radius_label": "350 m",
                        "reach": "120–180 mil",
                        "formats": ["Display no app"],
                        "audiences": ["Quem veio de carro"],
                        "commercial": "Quem veio de carro. Combustível e a volta para casa.",
                        "source": "Pátios",
                        "image_url": "/static/images/places/generated/congonhas-cgh-estacionamento-pt-4bdecbe2.png",
                    }
                ),
                _fence(
                    {
                        "id": "cgh-campo-belo",
                        "name": "Campo Belo",
                        "kind": "halo",
                        "lat": -23.6267,
                        "lng": -46.6694,
                        "radius_m": 800,
                        "radius_label": "800 m",
                        "reach": "90–150 mil",
                        "formats": ["Portais", "Display"],
                        "audiences": ["Quem mora do lado"],
                        "commercial": "Quem mora colado no aeroporto. Não é o T1.",
                        "source": "Distrito",
                        "image_url": "/static/images/places/generated/congonhas-cgh-campo-belo-pt-5ab929de.png",
                    }
                ),
                _fence(
                    {
                        "id": "cgh-moema",
                        "name": "Moema",
                        "kind": "halo",
                        "lat": -23.6017,
                        "lng": -46.6631,
                        "radius_m": 1000,
                        "radius_label": "1 km",
                        "reach": "80–140 mil",
                        "formats": ["Portais", "Display"],
                        "audiences": ["Quem circula em Moema"],
                        "commercial": "Escala em Moema. Separado do terminal de propósito.",
                        "source": "Distrito",
                        "image_url": "/static/images/places/generated/congonhas-cgh-moema-pt-27ebeb9b.png",
                    }
                ),
            ],
            "media": {
                "hero_url": "/static/images/places/generated/congonhas-hero-0239e4cd.png",
                "map_url": "/static/images/places/generated/congonhas-map-01079f3b.png",
            },
            "zones": [
                _zone(
                    {
                        "id": "CGH-01",
                        "type": "CORE",
                        "name": "Terminal T1",
                        "radius": "300 m",
                        "reach": "380–560 mil",
                        "description": "T1 sem pista e sem o bairro.",
                        "formats": APPS + PORTALS,
                        "audiences": ["Executivo", "Viajante recente"],
                        "commercial": "Principal recorte de Congonhas.",
                        "polygon": "56,30 72,30 79,40 73,54 58,56 50,45",
                    }
                ),
                _zone(
                    {
                        "id": "CGH-02",
                        "type": "DEPARTURES",
                        "name": "Embarque / Washington Luís",
                        "radius": "250 m",
                        "reach": "180–260 mil",
                        "description": "Frente de embarque na avenida.",
                        "formats": ["Vídeo vertical", "Rich media"],
                        "audiences": ["Embarque ativo"],
                        "commercial": "Intenção na saída.",
                        "polygon": "58,54 76,51 83,60 75,72 59,69 53,61",
                    }
                ),
                _zone(
                    {
                        "id": "CGH-03",
                        "type": "MOBILITY",
                        "name": "Desembarque e apps",
                        "radius": "250 m",
                        "reach": "160–230 mil",
                        "description": "Saída, táxi e app.",
                        "formats": APPS,
                        "audiences": ["Chegada"],
                        "commercial": "Mobilidade urbana.",
                        "polygon": "75,38 93,39 96,53 89,63 76,59 70,49",
                    }
                ),
                _zone(
                    {
                        "id": "CGH-04",
                        "type": "HALO",
                        "name": "Halo Campo Belo",
                        "radius": "800 m",
                        "reach": "90–150 mil",
                        "description": "Vizinhança. Separada do T1.",
                        "formats": PORTALS + ["Display"],
                        "audiences": ["Proximidade"],
                        "commercial": "Escala no bairro.",
                        "polygon": "1,50 28,48 35,61 27,79 3,80",
                    }
                ),
            ],
            "offer": _offer(
                "Alcance quem passa pelo T1, mora ao redor e sai pela Washington Luís.",
                [
                    ("No T1", "Display no app e vídeo no saguão para quem está no terminal."),
                    ("No bairro", "Portais e display no app para quem mora e circula perto do aeroporto."),
                    ("7 e 15 dias", "Quem já passou por Congonhas segue na cidade."),
                ],
            ),
            "methodology": {
                "title": "Como o número é feito",
                "body": (
                    "Passageiros da ANAC não são o que a campanha compra. "
                    "O T1 cabe em 300 metros; Campo Belo e Moema são outro recorte. "
                    "O número do ponto é quem dá para alcançar neste raio, no celular, em 4 semanas. "
                    "Os raios não se somam."
                ),
                "steps": [],
                "trust": "",
            },
        }
    ),
}

SANTOS_DUMONT = {
    "slug": "santos-dumont",
    "place_type": "aeroporto",
    "city": "rj",
    "status": "published",
    "title": "Santos Dumont",
    "code": "SDU",
    "operator": "Infraero · Rio de Janeiro",
    "subtitle": "A ponte no centro do Rio. Terminal de um lado; VLT e Glória do outro. As pistas ficam fora.",
    "payload": normalize_payload(
        {
            "metrics": {
                "passengers": _metric(6_184_233, "6,2 mi"),
                "four_weeks": _metric(
                    475_710,
                    "~476 mil",
                    source="Derivado do movimento ANAC 2025",
                    source_status="estimate",
                    note=FOUR_WEEKS_NOTE,
                ),
                "addressable": _metric(
                    120_000,
                    "95–150 mil",
                    source="Estimativa endereçável no terminal, 4 semanas",
                    source_status="estimate",
                    note=ADDRESSABLE_NOTE,
                ),
            },
            "catchment": {
                "population": _metric(
                    SDU_CATCHMENT_POP,
                    "96 mil",
                    source="IPP / IBGE Censo 2022 — Centro, Glória, Catete e Flamengo",
                    source_status="official",
                    note="23.642 + 7.120 + 22.295 + 43.099. Bacia do halo. As duas pistas não entram.",
                ),
                "density": _metric(
                    round(SDU_CATCHMENT_POP / SDU_CATCHMENT_KM2),
                    "~10,8 mil hab/km²",
                    source="IPP / IBGE Censo 2022 — densidade ponderada dos 4 bairros",
                    source_status="official",
                    note="96.156 hab / 8,89 km².",
                ),
                "impacted": _metric(
                    None,
                    "55–90 mil",
                    source="Halo Centro / Glória, 4 semanas, endereçável",
                    source_status="estimate",
                    note="Halo urbano. Não some ao terminal.",
                ),
                "neighborhoods": ["Centro", "Glória", "Catete", "Flamengo"],
                "profile": "Ponte aérea, escritório no centro, hotel na Glória e o VLT na porta. Compacto — o raio precisa ser curto.",
            },
            "audiences": [
                ["Ponte Rio–São Paulo", "O recorte que todo mundo reconhece."],
                ["Escritório no centro", "Quem desce e vai trabalhar."],
                ["Hotel e turismo", "Glória, centro e a volta no mesmo dia."],
                ["VLT, táxi e app", "A saída do terminal é a cidade."],
                ["Quem já voou", "Retarget depois da ponte."],
                ["Quem só circula no bairro", "Halo. Não é o saguão."],
            ],
            "geo": _geo(-22.910278, -43.163056, 14),
            "points": [
                _fence(
                    {
                        "id": "sdu-terminal",
                        "name": "Terminal",
                        "kind": "terminal",
                        "lat": -22.910278,
                        "lng": -43.163056,
                        "radius_m": 250,
                        "radius_label": "250 m",
                        "reach": "95–150 mil",
                        "formats": ["Display no app", "Portais"],
                        "audiences": ["Quem faz a ponte", "Quem já voou"],
                        "commercial": "O saguão. As duas pistas ficam de fora.",
                        "source": "Terminal oeste",
                        "note": "Pistas não são zona comercial.",
                        "image_url": "/static/images/places/generated/santos-dumont-sdu-terminal-pt-52d8757e.png",
                    }
                ),
                _fence(
                    {
                        "id": "sdu-embarque",
                        "name": "Embarque",
                        "kind": "embarque",
                        "lat": -22.9116,
                        "lng": -43.1663,
                        "radius_m": 200,
                        "radius_label": "200 m",
                        "reach": "70–110 mil",
                        "formats": ["Vídeo vertical", "Display no app"],
                        "audiences": ["Quem está embarcando"],
                        "commercial": "A entrada da ponte. Mensagem curta para quem está embarcando.",
                        "source": "Saguão e acesso",
                        "image_url": "/static/images/places/generated/santos-dumont-sdu-embarque-pt-6b5a800a.png",
                    }
                ),
                _fence(
                    {
                        "id": "sdu-vlt",
                        "name": "VLT",
                        "kind": "mobilidade",
                        "lat": -22.9088,
                        "lng": -43.1669,
                        "radius_m": 300,
                        "radius_label": "300 m",
                        "reach": "60–95 mil",
                        "formats": ["Display no app", "Portais"],
                        "audiences": ["Quem desceu", "Quem pega o VLT"],
                        "commercial": "Quem desceu. Hotel, app e o centro a dois pontos de VLT.",
                        "source": "Desembarque e mobilidade",
                        "image_url": "/static/images/places/generated/santos-dumont-sdu-vlt-pt-ddc51d4c.png",
                    }
                ),
                _fence(
                    {
                        "id": "sdu-centro",
                        "name": "Centro",
                        "kind": "halo",
                        "lat": -22.9068,
                        "lng": -43.1729,
                        "radius_m": 800,
                        "radius_label": "800 m",
                        "reach": "55–90 mil",
                        "formats": ["Portais", "Display"],
                        "audiences": ["Quem trabalha no centro"],
                        "commercial": "Quem trabalha e almoça no centro. Não é o saguão.",
                        "source": "IPP",
                        "image_url": "/static/images/places/generated/santos-dumont-sdu-centro-pt-8aa58887.png",
                    }
                ),
                _fence(
                    {
                        "id": "sdu-gloria",
                        "name": "Glória",
                        "kind": "halo",
                        "lat": -22.9205,
                        "lng": -43.1735,
                        "radius_m": 900,
                        "radius_label": "900 m",
                        "reach": "40–70 mil",
                        "formats": ["Portais"],
                        "audiences": ["Quem se hospeda", "Quem vai à orla"],
                        "commercial": "Hotel, orla e a descida para o Flamengo. Recorte à parte.",
                        "source": "IPP",
                        "image_url": "/static/images/places/generated/santos-dumont-sdu-gloria-pt-bdd4958e.png",
                    }
                ),
            ],
            "media": {
                "hero_url": "/static/images/places/generated/santos-dumont-hero-9df56602.png",
                "map_url": "/static/images/places/generated/santos-dumont-map-b988ab36.png",
            },
            "offer": _offer(
                "O SDU liga hotel, VLT e quem volta no mesmo dia.",
                [
                    ("No terminal", "Display no app e portais para quem faz a ponte."),
                    ("Na saída", "Vídeo vertical e display no app para quem está embarcando."),
                    ("No centro", "Portais para quem trabalha e almoça sem ter voado."),
                ],
            ),
            "methodology": {
                "title": "Como o número é feito",
                "body": (
                    "O SDU tem duas pistas paralelas — elas não são zona comercial. "
                    "O terminal cabe em 250 metros; Centro e Glória são halo. "
                    "Passageiros da ANAC não são o que a campanha compra. "
                    "O número do ponto é quem dá para alcançar neste raio, no celular, em 4 semanas. "
                    "Os raios não se somam."
                ),
                "steps": [],
                "trust": "",
            },
            "zones": [
                _zone(
                    {
                        "id": "SDU-01",
                        "type": "CORE",
                        "name": "Terminal",
                        "radius": "250 m",
                        "reach": "95–150 mil",
                        "description": "Terminal oeste. Sem as pistas.",
                        "formats": APPS + PORTALS,
                        "audiences": ["Ponte aérea"],
                        "commercial": "Recorte principal.",
                        "polygon": "34,38 49,37 55,49 48,62 34,62 29,49",
                    }
                ),
                _zone(
                    {
                        "id": "SDU-02",
                        "type": "DEPARTURES",
                        "name": "Embarque e acesso",
                        "radius": "200 m",
                        "reach": "70–110 mil",
                        "description": "Saguão e acesso.",
                        "formats": ["Mobile banner", "Rich media"],
                        "audiences": ["Embarque ativo"],
                        "commercial": "Alta intenção.",
                        "polygon": "22,53 36,51 41,66 33,77 19,72 16,61",
                    }
                ),
                _zone(
                    {
                        "id": "SDU-03",
                        "type": "MOBILITY",
                        "name": "Desembarque, VLT e apps",
                        "radius": "300 m",
                        "reach": "60–95 mil",
                        "description": "Saída e mobilidade.",
                        "formats": APPS,
                        "audiences": ["Chegada"],
                        "commercial": "Cidade na porta.",
                        "polygon": "18,34 34,32 38,48 30,56 16,50 12,41",
                    }
                ),
                _zone(
                    {
                        "id": "SDU-04",
                        "type": "HALO",
                        "name": "Halo Centro",
                        "radius": "800 m",
                        "reach": "55–90 mil",
                        "description": "Centro. Separado do terminal.",
                        "formats": PORTALS + ["Display"],
                        "audiences": ["Proximidade"],
                        "commercial": "Escala urbana.",
                        "polygon": "0,8 26,5 34,25 28,39 8,45 0,35",
                    }
                ),
            ],
        }
    ),
}

GALEAO = {
    "slug": "galeao",
    "place_type": "aeroporto",
    "city": "rj",
    "status": "published",
    "title": "Galeão",
    "code": "GIG",
    "operator": "RIOgaleão · Rio de Janeiro",
    "subtitle": "O T2 na Ilha do Governador. Internacional de um lado; a Vinte de Janeiro do outro.",
    "payload": normalize_payload(
        {
            "metrics": {
                "passengers": _metric(17_836_134, "17,8 mi"),
                "four_weeks": _metric(
                    1_372_010,
                    "~1,37 mi",
                    source="Derivado do movimento ANAC 2025",
                    source_status="estimate",
                    note=FOUR_WEEKS_NOTE,
                ),
                "addressable": _metric(
                    320_000,
                    "260–390 mil",
                    source="Estimativa endereçável no T2, 4 semanas",
                    source_status="estimate",
                    note=ADDRESSABLE_NOTE,
                ),
            },
            "catchment": {
                "population": _metric(
                    GIG_CATCHMENT_POP,
                    "211 mil",
                    source="IPP / IBGE Censo 2022 — RA Ilha do Governador",
                    source_status="official",
                    note="211.018 hab. Ilha inteira, não presença no T2.",
                ),
                "density": _metric(
                    round(GIG_CATCHMENT_POP / GIG_CATCHMENT_KM2),
                    "~5,2 mil hab/km²",
                    source="IPP / IBGE Censo 2022 — densidade da RA Ilha do Governador",
                    source_status="official",
                    note="211.018 hab / 40,81 km². Halo da ilha, não o sítio aeroportuário.",
                ),
                "impacted": _metric(
                    None,
                    "55–95 mil",
                    source="Halo Ilha do Governador, 4 semanas, endereçável",
                    source_status="estimate",
                    note="Halo. Não some ao T2.",
                ),
                "neighborhoods": ["Galeão", "Portuguesa", "Jardim Guanabara"],
                "profile": "Bacia local com 211 mil habitantes. Alta densidade residencial na Ilha do Governador; fluxo de moradores, trabalhadores e passageiros no T2.",
            },
            "audiences": [
                ["Quem mora na Ilha do Governador", "Galeão, Portuguesa e Jardim Guanabara — halo, não o T2."],
                ["Quem embarca ou desembarca no T2", "O recorte do saguão. Display no app e vídeo."],
                ["Quem chega de voo internacional", "Cerca de um terço do movimento. O GIG tem e o SDU não."],
                ["Quem passa na Vinte de Janeiro", "A avenida de entrada. Quem só passou no acesso."],
                ["Quem já voou", "Retarget depois do embarque ou da chegada."],
                ["Quem espera no desembarque", "Acompanhante, app e a descida do T2."],
            ],
            "geo": _geo(-22.8112259, -43.2585631, 13),
            "points": [
                _fence(
                    {
                        "id": "gig-terminal",
                        "name": "Terminal T2",
                        "kind": "terminal",
                        "lat": -22.8112259,
                        "lng": -43.2585631,
                        "radius_m": 400,
                        "radius_label": "400 m",
                        "reach": "260–390 mil",
                        "formats": ["Display no app", "Vídeo no saguão", "Portais"],
                        "audiences": ["Quem está no T2", "Doméstico e internacional"],
                        "commercial": "O saguão que a campanha compra primeiro. Display no app, vídeo no saguão e portais.",
                        "source": "T2",
                        "note": "Polígono do prédio. As duas pistas não entram.",
                        "image_url": "/static/images/places/generated/galeao-gig-terminal-pt-5e3c674e.png",
                    }
                ),
                _fence(
                    {
                        "id": "gig-embarque",
                        "name": "Embarque",
                        "kind": "embarque",
                        "lat": -22.8148,
                        "lng": -43.2502,
                        "radius_m": 250,
                        "radius_label": "250 m",
                        "reach": "140–210 mil",
                        "formats": ["Vídeo vertical", "Display no app"],
                        "audiences": ["Quem está embarcando"],
                        "commercial": "Quem está saindo. Banco, telecom e varejo no raio curto.",
                        "source": "Check-in ao gate",
                        "note": "Subconjunto do T2. Não some ao core.",
                        "image_url": "/static/images/places/generated/galeao-gig-embarque-pt-203a2036.png",
                    }
                ),
                _fence(
                    {
                        "id": "gig-internacional",
                        "name": "Internacional",
                        "kind": "premium",
                        "lat": -22.8136,
                        "lng": -43.2472,
                        "radius_m": 300,
                        "radius_label": "300 m",
                        "reach": "80–130 mil",
                        "formats": ["Vídeo", "Display"],
                        "audiences": ["Quem voa para fora", "Ticket alto"],
                        "commercial": "Imigração e duty-free. Volume real — cerca de 32% do movimento.",
                        "source": "Área internacional · ~32% do movimento (RIOgaleão 2025)",
                        "image_url": "/static/images/places/generated/galeao-gig-internacional-pt-a9aed74f.png",
                    }
                ),
                _fence(
                    {
                        "id": "gig-estacionamento",
                        "name": "Estacionamento",
                        "kind": "mobilidade",
                        "lat": -22.8165,
                        "lng": -43.2460,
                        "radius_m": 400,
                        "radius_label": "400 m",
                        "reach": "100–150 mil",
                        "formats": ["Display no app", "7 e 15 dias"],
                        "audiences": ["Quem busca o carro", "Quem espera na porta"],
                        "commercial": "Quem busca o carro ou o app. Combustível e conveniência.",
                        "source": "Curbside e pátios do T2",
                        "image_url": "/static/images/places/generated/galeao-gig-estacionamento-pt-ab70235e.png",
                    }
                ),
                _fence(
                    {
                        "id": "gig-acesso",
                        "name": "Vinte de Janeiro",
                        "kind": "halo",
                        "lat": -22.8260776,
                        "lng": -43.2327675,
                        "radius_m": 1000,
                        "radius_label": "1 km",
                        "reach": "70–120 mil",
                        "formats": ["Portais", "Display"],
                        "audiences": ["Quem só passou no acesso"],
                        "commercial": "A avenida de entrada. Separado de quem entrou no T2.",
                        "source": "Acesso viário",
                        "image_url": "/static/images/places/generated/galeao-gig-acesso-pt-efd6188c.png",
                    }
                ),
                _fence(
                    {
                        "id": "gig-ilha",
                        "name": "Jardim Guanabara",
                        "kind": "halo",
                        "lat": -22.8128362,
                        "lng": -43.2007792,
                        "radius_m": 1200,
                        "radius_label": "1,2 km",
                        "reach": "55–95 mil",
                        "formats": ["Portais", "Display"],
                        "audiences": ["Quem mora na Ilha"],
                        "commercial": "Quem mora e circula na Ilha. Não é o saguão.",
                        "source": "IPP",
                        "image_url": "/static/images/places/generated/galeao-gig-ilha-pt-143e1a95.png",
                    }
                ),
            ],
            "media": {
                "hero_url": "/static/images/places/generated/galeao-hero-75062ae1.png",
                "map_url": "",
            },
            "offer": _offer(
                "No Galeão você compra o T2, o internacional e quem mora na Ilha.",
                [
                    ("No T2", "Display no app e vídeo no saguão para quem circula no terminal."),
                    ("No internacional", "Vídeo e display para quem chega de fora — cerca de um terço do movimento."),
                    ("Na Ilha", "Portais para quem mora em Galeão, Portuguesa e Jardim Guanabara."),
                ],
            ),
            "methodology": {
                "title": "Como o número é feito",
                "body": (
                    "O GIG tem duas pistas longas — elas não são zona comercial. "
                    "O T2 cabe em 400 metros; a Ilha é halo. "
                    "O internacional é recorte de verdade (~32% do movimento), não fatia residual. "
                    "Passageiros da ANAC não são o que a campanha compra. "
                    "O número do ponto é quem dá para alcançar neste raio, no celular, em 4 semanas. "
                    "Os raios não se somam."
                ),
                "steps": [],
                "trust": "",
            },
            "zones": [
                _zone(
                    {
                        "id": "GIG-01",
                        "type": "CORE",
                        "name": "Terminal T2",
                        "radius": "400 m",
                        "reach": "260–390 mil",
                        "description": "Prédio do T2. Sem pista.",
                        "formats": APPS + PORTALS,
                        "audiences": ["Visitante do aeroporto", "Viajante recente"],
                        "commercial": "Entrada da campanha. Não some aos outros raios.",
                        "polygon": "48,40 66,36 74,48 68,62 50,64 42,52",
                    }
                ),
                _zone(
                    {
                        "id": "GIG-02",
                        "type": "DEPARTURES",
                        "name": "Embarque",
                        "radius": "250 m",
                        "reach": "140–210 mil",
                        "description": "Check-in, inspeção e gate.",
                        "formats": ["Vídeo vertical", "Rich media"] + PORTALS,
                        "audiences": ["Embarque ativo"],
                        "commercial": "Alta intenção na saída.",
                        "polygon": "66,44 84,42 90,54 82,66 66,64 60,52",
                    }
                ),
                _zone(
                    {
                        "id": "GIG-03",
                        "type": "PREMIUM",
                        "name": "Internacional",
                        "radius": "300 m",
                        "reach": "80–130 mil",
                        "description": "Jornada internacional. Em 2025 ficou em ~32% do movimento.",
                        "formats": ["Vídeo premium", "Rich media"],
                        "audiences": ["Internacional", "Ticket alto"],
                        "commercial": "Volume real, ticket alto.",
                        "polygon": "28,38 48,36 52,52 44,62 28,60 22,48",
                    }
                ),
                _zone(
                    {
                        "id": "GIG-04",
                        "type": "MOBILITY",
                        "name": "Estacionamento e apps",
                        "radius": "400 m",
                        "reach": "100–150 mil",
                        "description": "Pátios, curbside e descida do T2.",
                        "formats": APPS,
                        "audiences": ["Mobilidade"],
                        "commercial": "Apps e conveniência.",
                        "polygon": "40,64 70,62 76,74 66,84 40,84 32,74",
                    }
                ),
                _zone(
                    {
                        "id": "GIG-05",
                        "type": "HALO",
                        "name": "Halo Ilha",
                        "radius": "1,2 km",
                        "reach": "55–95 mil",
                        "description": "Ilha do Governador. Separada do T2.",
                        "formats": PORTALS + ["Display"],
                        "audiences": ["Proximidade"],
                        "commercial": "Escala na Ilha sem fingir que a pessoa entrou no saguão.",
                        "polygon": "2,18 28,14 34,32 24,44 4,42",
                    }
                ),
            ],
        }
    ),
}

SEED_PLACES = (CONFINS, CONGONHAS, SANTOS_DUMONT, GALEAO)

CITY_ORDER = ("bh", "sp", "rj")
TYPE_ORDER = ("aeroporto", "shopping", "evento")


def seed_by_slug(slug: str) -> dict | None:
    for item in SEED_PLACES:
        if item["slug"] == slug:
            return item
    return None
