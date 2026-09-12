"""Seed e constantes dos Places. Números de passageiros: ANAC 2025."""

from __future__ import annotations

from .brand import zone_color
from .schema import normalize_payload

ANAC_2025 = "ANAC — movimento de passageiros 2025"
FOUR_WEEKS_NOTE = "Anual ÷ 13. Movimentos físicos, não devices únicos."
# Confins 7.350 + Lagoa Santa 75.145 + Vespasiano 129.246 (IBGE).
CNF_CATCHMENT_POP = 211_741
CNF_CATCHMENT_KM2 = 42.462 + 229.741 + 70.456
# Campo Belo 71.034 + Moema 81.899 (IBGE / SMUL). Áreas: 8,77 + 9,08 km².
CGH_CATCHMENT_POP = 152_933
CGH_CATCHMENT_KM2 = 8.77 + 9.08
# Centro 23.642 + Glória 7.120 + Catete 22.295 + Flamengo 43.099 (IPP / IBGE).
SDU_CATCHMENT_POP = 96_156
SDU_CATCHMENT_KM2 = 5.425 + 1.140 + 0.681 + 1.646


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


def _point(item):
    return item


def _geo(lat, lng, zoom=15):
    return {"lat": lat, "lng": lng, "zoom": zoom}


CONFINS = {
    "slug": "confins",
    "place_type": "aeroporto",
    "city": "bh",
    "status": "published",
    "title": "Confins",
    "code": "CNF",
    "operator": "BH Airport (Motiva / Zurich) · Minas Gerais",
    "subtitle": "Audiência qualificada no principal hub aéreo de Minas Gerais.",
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
                    "560–760 mil",
                    source="Faixa comercial do corredor de acesso, 4 semanas",
                    source_status="estimate",
                    note="Halo. Não some ao core nem às demais zonas.",
                ),
                "neighborhoods": ["Confins", "Lagoa Santa", "Vespasiano", "corredor MG-010"],
                "profile": "Viajante regional, negócios de Belo Horizonte, fluxo doméstico e internacional.",
            },
            "audiences": [
                ["Visitante recente", "Presença no aeroporto em janelas de 7, 15 ou 30 dias."],
                ["Viajante frequente", "Recorrência em visitas distintas, com critério objetivo."],
                ["Domestic traveler", "Audiência associada ao fluxo doméstico."],
                ["International traveler", "Audiência premium ligada à zona internacional."],
                ["Airport mobility", "Chegada, saída, estacionamento e mobilidade."],
                ["Audience extension", "Ampliação de escala preservando contexto aeroportuário."],
            ],
            "geo": _geo(-19.624445, -43.971944, 14),
            "points": [
                _point({"id": "cnf-terminal", "name": "Terminal BH Airport", "kind": "terminal", "lat": -19.624445, "lng": -43.971944, "source": "Sítio do aeroporto"}),
                _point({"id": "cnf-confins", "name": "Confins", "kind": "bairro", "lat": -19.6283, "lng": -43.9931, "source": "Sede municipal"}),
                _point({"id": "cnf-lagoa", "name": "Lagoa Santa", "kind": "bairro", "lat": -19.6276, "lng": -43.8898, "source": "Sede municipal"}),
                _point({"id": "cnf-vespasiano", "name": "Vespasiano", "kind": "pessoas", "lat": -19.6918, "lng": -43.9239, "source": "Sede municipal"}),
            ],
            "media": {
                "hero_url": "/static/images/places/confins-hero.jpg",
                "map_url": "/static/images/places/confins-map.jpg",
            },
            "zones": [
                _zone(
                    {
                        "id": "CNF-01",
                        "type": "CORE",
                        "name": "Terminal Core",
                        "radius": "Área funcional",
                        "reach": "870 mil – 1,02 mi",
                        "description": "Polígono do terminal principal e frente operacional de passageiros. É a camada mais ampla de presença aeroportuária.",
                        "formats": ["Display mobile", "Vídeo in-app", "Interstitial", "Portais mobile"],
                        "audiences": ["Airport Visitor", "Recent Traveler", "Audience Core"],
                        "commercial": "Awareness premium, entrada de campanha e formação da principal base de visitantes.",
                        "polygon": "43,43 57,38 64,45 61,57 50,61 41,55",
                    }
                ),
                _zone(
                    {
                        "id": "CNF-02",
                        "type": "DEPARTURES",
                        "name": "Embarque doméstico",
                        "radius": "Check-in + inspeção + embarque",
                        "reach": "450 mil – 560 mil",
                        "description": "Área funcional ampliada do check-in doméstico até inspeção e embarque, reduzindo dependência de um raio circular.",
                        "formats": ["Vídeo vertical", "Rich media", "Banner mobile", "Portais"],
                        "audiences": ["Domestic Traveler", "Recent Traveler", "Frequent Traveler"],
                        "commercial": "Bancos, telecom, turismo, varejo e serviços ligados à jornada de saída.",
                        "polygon": "60,44 78,40 84,48 80,60 65,59 58,53",
                    }
                ),
                _zone(
                    {
                        "id": "CNF-03",
                        "type": "PREMIUM",
                        "name": "Internacional / Premium",
                        "radius": "Área internacional funcional",
                        "reach": "A validar",
                        "description": "Zona da jornada internacional, do processamento de passageiros ao embarque. O fluxo internacional do CNF em 2025 ficou na casa de 4–5% do movimento (BH Airport / ANAC); o alcance desta zona permanece a validar na plataforma de location data.",
                        "formats": ["Vídeo premium", "Rich media", "Interstitial", "Display"],
                        "audiences": ["International Traveler", "Premium Audience", "Qualified Retargeting"],
                        "commercial": "Luxo, cartões, automóveis, seguros, turismo e produtos de alto ticket.",
                        "polygon": "18,43 40,39 43,53 36,61 20,58 13,50",
                    }
                ),
                _zone(
                    {
                        "id": "CNF-04",
                        "type": "MOBILITY",
                        "name": "Mobilidade e estacionamentos",
                        "radius": "Conjunto de mobilidade",
                        "reach": "300 mil – 460 mil",
                        "description": "Área integrada de estacionamentos, curbside e circulação terrestre, criada como contexto de mobilidade.",
                        "formats": ["Display mobile", "In-app video", "Geo retargeting", "Portais"],
                        "audiences": ["Airport Mobility", "Driver / Passenger", "Companion Audience"],
                        "commercial": "Mobilidade, apps, automóveis, combustíveis e conveniência.",
                        "polygon": "37,64 66,62 73,73 64,83 39,84 30,75",
                    }
                ),
                _zone(
                    {
                        "id": "CNF-05",
                        "type": "HALO",
                        "name": "Corredor de acesso",
                        "radius": "Corredor 1–1,5 km",
                        "reach": "560 mil – 760 mil",
                        "description": "Corredor de influência viária para expansão de cobertura, separado da audiência core.",
                        "formats": ["Display", "Vídeo", "Portais mobile", "Desktop"],
                        "audiences": ["Proximity Audience", "Recent Traveler", "Audience Extension"],
                        "commercial": "Escala adicional e reforço de frequência sem tratar proximidade como presença no terminal.",
                        "polygon": "5,73 31,68 35,80 20,91 4,88",
                    }
                ),
            ],
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
    "subtitle": "Audiência qualificada no aeroporto mais urbano do país.",
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
            },
            "catchment": {
                "population": _metric(
                    CGH_CATCHMENT_POP,
                    "153 mil",
                    source="IBGE Censo 2022 / SMUL — distritos Campo Belo e Moema",
                    source_status="official",
                    note="71.034 + 81.899. Recorte distrital que contém o aeroporto; o halo de ~1 km é um subconjunto.",
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
                    "1,10–1,40 mi",
                    source="Faixa comercial do halo urbano, 4 semanas",
                    source_status="estimate",
                    note="Separado do terminal. Não some às zonas internas.",
                ),
                "neighborhoods": ["Campo Belo", "Moema"],
                "profile": "Executivo urbano, ponte aérea, alta renda e mobilidade por apps.",
            },
            "audiences": [
                ["Público executivo", "Alta incidência de viagens de negócios e ponte aérea."],
                ["Viajante urbano", "Passageiros integrados ao tecido urbano de São Paulo."],
                ["Mobility audience", "Táxi, apps, embarque e desembarque."],
                ["Recent visitor", "Base reimpactável após a visita."],
                ["Business traveler", "Recorrência e contexto de negócios."],
                ["Audience extension", "Cobertura complementar no entorno imediato."],
            ],
            "geo": _geo(-23.626111, -46.656389, 15),
            "points": [
                _point({"id": "cgh-terminal", "name": "Terminal T1", "kind": "terminal", "lat": -23.626111, "lng": -46.656389, "source": "Sítio do aeroporto"}),
                _point({"id": "cgh-campo-belo", "name": "Campo Belo", "kind": "bairro", "lat": -23.6267, "lng": -46.6694, "source": "Distrito"}),
                _point({"id": "cgh-moema", "name": "Moema", "kind": "densidade", "lat": -23.6017, "lng": -46.6631, "source": "Distrito"}),
            ],
            "media": {
                "hero_url": "/static/images/places/congonhas-hero.jpg",
                "map_url": "/static/images/places/congonhas-map.jpg",
            },
            "zones": [
                _zone(
                    {
                        "id": "CGH-01",
                        "type": "CORE",
                        "name": "Terminal T1",
                        "radius": "Polígono do terminal",
                        "reach": "1,45 mi – 1,88 mi",
                        "description": "Área funcional do terminal, evitando diluir a audiência em pistas e tecido urbano adjacente.",
                        "formats": ["Display mobile", "Interstitial", "Vídeo in-app", "Portais mobile"],
                        "audiences": ["Executives", "Recent Traveler", "Business Traveler"],
                        "commercial": "Principal ponto para awareness e construção de público de alto valor.",
                        "polygon": "56,30 72,30 79,40 73,54 58,56 50,45",
                    }
                ),
                _zone(
                    {
                        "id": "CGH-02",
                        "type": "DEPARTURES",
                        "name": "Embarque / acesso principal",
                        "radius": "Frente de embarque",
                        "reach": "900 mil – 1,15 mi",
                        "description": "Área funcional da frente de embarque e acesso viário imediato, com alto sinal de intenção.",
                        "formats": ["Vídeo vertical", "Rich media", "Banner mobile"],
                        "audiences": ["Active Departure", "Business Traveler", "Recent Visitor"],
                        "commercial": "Impacto rápido, frequência controlada e contexto executivo.",
                        "polygon": "58,54 76,51 83,60 75,72 59,69 53,61",
                    }
                ),
                _zone(
                    {
                        "id": "CGH-03",
                        "type": "MOBILITY",
                        "name": "Desembarque / Táxi e apps",
                        "radius": "Saída + mobilidade",
                        "reach": "820 mil – 1,05 mi",
                        "description": "Desembarque integrado às áreas de táxi, apps e circulação urbana imediata.",
                        "formats": ["In-app video", "Display mobile", "Rich media"],
                        "audiences": ["Arrivals", "Mobility Audience", "Post-Visit Retargeting"],
                        "commercial": "Apps, mobilidade, conveniência e serviços urbanos.",
                        "polygon": "75,38 93,39 96,53 89,63 76,59 70,49",
                    }
                ),
                _zone(
                    {
                        "id": "CGH-04",
                        "type": "HALO",
                        "name": "Halo urbano",
                        "radius": "Entorno ~1 km",
                        "reach": "1,10 mi – 1,40 mi",
                        "description": "Camada de escala no entorno, tratada separadamente da presença aeroportuária para preservar qualidade.",
                        "formats": ["Display", "Vídeo", "Portais mobile", "Desktop"],
                        "audiences": ["Proximity Audience", "Urban Mobility", "Audience Extension"],
                        "commercial": "Cobertura complementar e reforço de campanha em contexto urbano.",
                        "polygon": "1,50 28,48 35,61 27,79 3,80",
                    }
                ),
            ],
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
    "subtitle": "Audiência qualificada no aeroporto mais estratégico do Rio.",
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
            },
            "catchment": {
                "population": _metric(
                    SDU_CATCHMENT_POP,
                    "96 mil",
                    source="IPP / IBGE Censo 2022 — Centro, Glória, Catete e Flamengo",
                    source_status="official",
                    note="23.642 + 7.120 + 22.295 + 43.099. Bacia do halo. As duas pistas não entram como zona comercial.",
                ),
                "density": _metric(
                    round(SDU_CATCHMENT_POP / SDU_CATCHMENT_KM2),
                    "~10,8 mil hab/km²",
                    source="IPP / IBGE Censo 2022 — densidade ponderada dos 4 bairros",
                    source_status="official",
                    note="96.156 hab / 8,89 km². Densidade do entorno, não do sítio aeroportuário.",
                ),
                "impacted": _metric(
                    None,
                    "260–340 mil",
                    source="Faixa comercial do halo Centro/Glória, 4 semanas",
                    source_status="estimate",
                    note="Halo urbano. Não some ao terminal.",
                ),
                "neighborhoods": ["Centro", "Glória", "Catete", "Flamengo"],
                "profile": "Ponte aérea, executivos, turismo urbano e mobilidade VLT e apps.",
            },
            "audiences": [
                ["Ponte aérea", "Contexto forte de conexão Rio–São Paulo."],
                ["Executivos e negócios", "Audiência de alto valor no centro do Rio."],
                ["Turismo urbano", "Integração imediata com centro e atrações."],
                ["Mobilidade", "VLT, táxi, apps e desembarque."],
                ["Recent traveler", "Retargeting após a passagem."],
                ["Audience extension", "Cobertura complementar no entorno central."],
            ],
            "geo": _geo(-22.910278, -43.163056, 15),
            "points": [
                _point({"id": "sdu-terminal", "name": "Terminal de passageiros", "kind": "terminal", "lat": -22.910278, "lng": -43.163056, "source": "Sítio do aeroporto"}),
                _point({"id": "sdu-centro", "name": "Centro", "kind": "bairro", "lat": -22.9068, "lng": -43.1729, "source": "IPP"}),
                _point({"id": "sdu-gloria", "name": "Glória", "kind": "bairro", "lat": -22.9205, "lng": -43.1735, "source": "IPP"}),
                _point({"id": "sdu-catete", "name": "Catete", "kind": "pessoas", "lat": -22.9266, "lng": -43.1769, "source": "IPP"}),
                _point({"id": "sdu-flamengo", "name": "Flamengo", "kind": "densidade", "lat": -22.9320, "lng": -43.1749, "source": "IPP"}),
            ],
            "media": {
                "hero_url": "/static/images/places/sdu-hero.jpg",
                "map_url": "/static/images/places/sdu-map.jpg",
            },
            "methodology": {
                "trust": (
                    "O SDU tem duas pistas paralelas — elas não são zonas comerciais. "
                    "O polígono final de mídia deve ser calibrado na plataforma de location data."
                ),
            },
            "zones": [
                _zone(
                    {
                        "id": "SDU-01",
                        "type": "CORE",
                        "name": "Terminal de passageiros",
                        "radius": "Polígono do terminal",
                        "reach": "280 mil – 360 mil",
                        "description": "Área funcional principal do terminal no lado oeste do sítio aeroportuário, sem incluir as duas pistas.",
                        "formats": ["Display mobile", "Vídeo in-app", "Portais mobile"],
                        "audiences": ["Executives", "Recent Traveler", "Travel Audience"],
                        "commercial": "Awareness premium e construção de audiência da ponte aérea.",
                        "polygon": "34,38 49,37 55,49 48,62 34,62 29,49",
                    }
                ),
                _zone(
                    {
                        "id": "SDU-02",
                        "type": "DEPARTURES",
                        "name": "Embarque / acesso terminal",
                        "radius": "Saguão + acesso",
                        "reach": "220 mil – 300 mil",
                        "description": "Área ampliada do saguão e acesso de embarque, acompanhando o fluxo funcional do terminal.",
                        "formats": ["Mobile banner", "Rich media", "Vídeo vertical"],
                        "audiences": ["Active Departure", "Travel Planner", "7D Retargeting"],
                        "commercial": "Mensagens de alta intenção na entrada da jornada de viagem.",
                        "polygon": "22,53 36,51 41,66 33,77 19,72 16,61",
                    }
                ),
                _zone(
                    {
                        "id": "SDU-03",
                        "type": "MOBILITY",
                        "name": "Desembarque / VLT / Táxi e apps",
                        "radius": "Desembarque + mobilidade",
                        "reach": "180 mil – 260 mil",
                        "description": "Área funcional de desembarque integrada à mobilidade terrestre e transporte público.",
                        "formats": ["In-app video", "Display mobile", "Portais mobile"],
                        "audiences": ["Arrivals", "Urban Mobility", "Post-Visit Retargeting"],
                        "commercial": "Mobilidade, turismo, hotelaria, serviços e conveniência.",
                        "polygon": "18,34 34,32 38,48 30,56 16,50 12,41",
                    }
                ),
                _zone(
                    {
                        "id": "SDU-04",
                        "type": "HALO",
                        "name": "Halo Centro / Glória",
                        "radius": "Entorno ~1 km",
                        "reach": "260 mil – 340 mil",
                        "description": "Camada de extensão urbana, separada da presença no terminal para evitar inflar o core.",
                        "formats": ["Display", "Vídeo", "Portais mobile", "Desktop"],
                        "audiences": ["Proximity Audience", "Recent Traveler", "Audience Extension"],
                        "commercial": "Cobertura adicional no contexto central do Rio e reforço de frequência.",
                        "polygon": "0,8 26,5 34,25 28,39 8,45 0,35",
                    }
                ),
            ],
        }
    ),
}

SEED_PLACES = (CONFINS, CONGONHAS, SANTOS_DUMONT)

CITY_ORDER = ("bh", "sp", "rj")
TYPE_ORDER = ("aeroporto", "shopping", "evento")


def seed_by_slug(slug: str) -> dict | None:
    for item in SEED_PLACES:
        if item["slug"] == slug:
            return item
    return None
