"""Shoppings e lugares de BH, SP e RJ. Tráfego anual a validar quando não há dado do operador."""

from __future__ import annotations

from .schema import normalize_payload

ADDRESSABLE_NOTE = (
    "Únicos ≈ movimentos de 4 semanas × 0,62. "
    "Endereçáveis em apps e portais ≈ únicos × 0,38. "
    "Os raios não se somam."
)
APPS = ["Display no app", "Vídeo vertical", "Interstitial"]
PORTALS = ["Portais no celular", "Portais premium"]


def _metric(value, label, *, year=2025, source="", source_status="estimate", note=""):
    return {
        "value": value,
        "label": label,
        "year": year,
        "source": source,
        "source_status": source_status,
        "note": note,
    }


def _fence(item):
    row = dict(item)
    row.setdefault("reach_status", "estimate")
    row.setdefault("formats", APPS + PORTALS)
    return row


def _geo(lat, lng, zoom=15):
    return {"lat": lat, "lng": lng, "zoom": zoom}


def _offer(lead, lines):
    return {"lead": lead, "lines": [{"title": title, "body": body} for title, body in lines]}

TRAFFIC_NOTE = "Visitas no ano. Não é device único nem presença no raio."
WEEKS_NOTE = "Anual ÷ 13. Movimentos físicos, não devices únicos."
INVEST_NOTE = "Ordem de grandeza para o recorte no celular, 4 semanas. Não é cotação."
VENUE_METHOD = (
    "Visitas do lugar não são o que a campanha compra. "
    "O número do ponto é quem dá para alcançar neste raio, no celular, em 4 semanas. "
    "O investimento de 4 semanas é ordem de grandeza — não é cotação. "
    "Os raios não se somam."
)


def _weeks(annual: int) -> int:
    return int(round(annual / 13))


def _addr(weeks: int) -> int:
    return int(round(weeks * 0.62 * 0.38))


def _reach(addressable: int, lo=0.75, hi=1.25) -> str:
    low = int(round(addressable * lo / 1000) * 1000)
    high = int(round(addressable * hi / 1000) * 1000)
    if high < 1000:
        return f"{max(low, 1)}–{max(high, 2)} mil"
    return f"{low // 1000}–{high // 1000} mil".replace("–0–", "–")


def _invest(addressable: int) -> dict:
    if addressable >= 250_000:
        label, mid = "R$ 55–95 mil", 75_000
    elif addressable >= 150_000:
        label, mid = "R$ 40–70 mil", 55_000
    elif addressable >= 80_000:
        label, mid = "R$ 28–48 mil", 38_000
    elif addressable >= 40_000:
        label, mid = "R$ 18–32 mil", 25_000
    else:
        label, mid = "R$ 12–22 mil", 17_000
    return {
        "value": mid,
        "label": label,
        "source": INVEST_NOTE,
        "source_status": "to_validate",
        "note": INVEST_NOTE,
    }


def _venue(
    *,
    slug,
    place_type,
    city,
    title,
    code,
    operator,
    subtitle,
    annual,
    annual_label,
    annual_source,
    neighborhoods,
    profile,
    geo,
    points,
    offer,
    defense,
    hero_url="",
    four_weeks=None,
    addressable=None,
):
    weeks = four_weeks if four_weeks is not None else _weeks(annual)
    addr = addressable if addressable is not None else _addr(weeks)
    return {
        "slug": slug,
        "place_type": place_type,
        "city": city,
        "status": "published",
        "title": title,
        "code": code,
        "operator": operator,
        "subtitle": subtitle,
        "payload": normalize_payload(
            {
                "metrics": {
                    "passengers": _metric(
                        annual,
                        annual_label,
                        source=annual_source,
                        source_status="to_validate",
                        note=TRAFFIC_NOTE,
                    ),
                    "four_weeks": _metric(
                        weeks,
                        f"~{weeks // 1000} mil" if weeks >= 1000 else f"~{weeks}",
                        source="Derivado do tráfego anual",
                        source_status="to_validate",
                        note=WEEKS_NOTE,
                    ),
                    "addressable": _metric(
                        addr,
                        _reach(addr),
                        source="Estimativa endereçável no sítio, 4 semanas",
                        source_status="estimate",
                        note=ADDRESSABLE_NOTE,
                    ),
                },
                "investment": _invest(addr),
                "defense": defense,
                "catchment": {"neighborhoods": neighborhoods, "profile": profile},
                "geo": geo,
                "points": [_fence(item) for item in points],
                "media": {"hero_url": hero_url},
                "offer": _offer(*offer),
                "methodology": {"title": "Como o número é feito", "body": VENUE_METHOD},
            }
        ),
    }


def _core(prefix, name, lat, lng, *, kind="marco", radius=180, reach="", commercial="", invest="", formats=None):
    return {
        "id": f"{prefix}-core",
        "name": name,
        "kind": kind,
        "lat": lat,
        "lng": lng,
        "radius_m": radius,
        "radius_label": f"{radius} m",
        "reach": reach,
        "formats": formats or ["Display no app", "Portais"],
        "audiences": ["Quem entrou no sítio"],
        "commercial": commercial,
        "defense": commercial,
        "investment": invest,
        "source": "Sítio",
    }


def _food(prefix, lat, lng, *, reach="", commercial=""):
    return {
        "id": f"{prefix}-food",
        "name": "Praça de alimentação",
        "kind": "pessoas",
        "lat": lat,
        "lng": lng,
        "radius_m": 120,
        "radius_label": "120 m",
        "reach": reach,
        "formats": ["Vídeo vertical", "Display"],
        "audiences": ["Gastronomia"],
        "commercial": commercial,
        "defense": commercial,
        "investment": "R$ 12–22 mil",
        "source": "Praça",
    }


def _park(prefix, lat, lng, *, reach="", commercial=""):
    return {
        "id": f"{prefix}-park",
        "name": "Estacionamento",
        "kind": "mobilidade",
        "lat": lat,
        "lng": lng,
        "radius_m": 250,
        "radius_label": "250 m",
        "reach": reach,
        "formats": APPS,
        "audiences": ["Mobilidade"],
        "commercial": commercial,
        "defense": commercial,
        "investment": "R$ 12–22 mil",
        "source": "Pátios",
    }


def _halo(prefix, name, lat, lng, *, reach="", commercial="", radius=800):
    return {
        "id": f"{prefix}-halo",
        "name": name,
        "kind": "halo",
        "lat": lat,
        "lng": lng,
        "radius_m": radius,
        "radius_label": "800 m" if radius == 800 else f"{radius / 1000:.1f} km".replace(".0", ""),
        "reach": reach,
        "formats": PORTALS + ["Display"],
        "audiences": ["Quem está no bairro"],
        "commercial": commercial,
        "defense": commercial,
        "investment": "R$ 10–18 mil",
        "source": "Bairro",
    }


BH_SHOPPING = _venue(
    slug="bh-shopping",
    place_type="shopping",
    city="bh",
    title="BH Shopping",
    code="BHS",
    operator="Allos · Belvedere",
    subtitle="O mall da BR-356. Quem entrou no complexo não é quem só passou em Belvedere.",
    annual=12_000_000,
    annual_label="~12 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Belvedere", "Santa Lúcia", "Mangabeiras"],
    profile="Quem compra no mall e quem mora no Belvedere. O complexo não é o bairro.",
    geo=_geo(-19.9747, -43.9469, 16),
    points=[
        _core("bhs", "Mall", -19.9747, -43.9469, reach="160–260 mil", commercial="Quem cruzou a porta do BH Shopping. Recorte que a campanha compra primeiro.", invest="R$ 28–48 mil", radius=220),
        _food("bhs", -19.9749, -43.9464, reach="55–90 mil", commercial="Quem parou para comer. Raio curto, intenção alta."),
        _park("bhs", -19.9754, -43.9476, reach="70–110 mil", commercial="Quem veio de carro pela BR-356. Não some ao mall."),
        _halo("bhs", "Belvedere", -19.9688, -43.9552, reach="40–70 mil", commercial="O bairro. Separado de quem entrou no mall."),
    ],
    offer=(
        "No BH Shopping você compra quem entrou no complexo — Belvedere é outro recorte.",
        [
            ("No mall", "Display e portais para quem cruzou a porta."),
            ("Na praça", "Vídeo para quem parou para comer."),
            ("No bairro", "Portais no Belvedere, sem fingir que a pessoa entrou."),
        ],
    ),
    defense={
        "lead": "É o mall regional do sul de BH.",
        "body": "Quem entra no complexo tem ticket e tempo de permanência. Belvedere ao lado é halo — escala sem misturar com a loja.",
    },
)

PATIO_SAVASSI = _venue(
    slug="patio-savassi",
    place_type="shopping",
    city="bh",
    title="Pátio Savassi",
    code="PSV",
    operator="Aliansce Sonae / Allos · Savassi",
    subtitle="O mall no miolo da Savassi. A porta é uma; a praça da Savassi é outra.",
    annual=4_200_000,
    annual_label="~4,2 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Savassi", "Funcionários", "Lourdes"],
    profile="Quem entra no Pátio e quem só almoça na Savassi. O mall não é a praça.",
    geo=_geo(-19.9369, -43.9358, 17),
    points=[
        _core("psv", "Mall", -19.9369, -43.9358, reach="55–95 mil", commercial="Quem cruzou a porta do Pátio. Recorte curto e denso.", invest="R$ 18–32 mil", radius=150),
        _food("psv", -19.9371, -43.9354, reach="22–38 mil", commercial="Quem parou na praça interna."),
        _park("psv", -19.9374, -43.9363, reach="18–32 mil", commercial="Quem veio de carro. Não some ao mall."),
        _halo("psv", "Praça da Savassi", -19.93725, -43.9339, reach="40–70 mil", commercial="A praça e os bares. Não é presença no mall.", radius=600),
    ],
    offer=(
        "No Pátio você compra quem entrou — a praça da Savassi é o halo.",
        [
            ("No mall", "Display para quem cruzou a porta."),
            ("Na praça interna", "Vídeo no almoço."),
            ("Na Savassi", "Portais para quem só passou na rua."),
        ],
    ),
    defense={
        "lead": "É o shopping mais colado na vida da Savassi.",
        "body": "O raio do mall é curto de propósito. Quem está na praça não entra na conta de quem comprou na loja.",
    },
)

MINAS_SHOPPING = _venue(
    slug="minas-shopping",
    place_type="shopping",
    city="bh",
    title="Minas Shopping",
    code="MNS",
    operator="Ancar Ivanhoe · São Gabriel",
    subtitle="O mall da Cristiano Machado. Quem entrou não é o fluxo da avenida.",
    annual=8_000_000,
    annual_label="~8 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["São Gabriel", "Silveira", "Ipiranga"],
    profile="Quem compra no Minas e quem só cruza a Cristiano Machado. O prédio não é a avenida.",
    geo=_geo(-19.8872, -43.9215, 16),
    points=[
        _core("mns", "Mall", -19.8872, -43.9215, reach="110–180 mil", commercial="Quem cruzou a porta do Minas Shopping.", invest="R$ 28–48 mil", radius=200),
        _food("mns", -19.8875, -43.9210, reach="40–70 mil", commercial="Quem parou para comer."),
        _park("mns", -19.8866, -43.9222, reach="50–85 mil", commercial="Quem veio de carro. Não some ao mall."),
        _halo("mns", "Cristiano Machado", -19.8805, -43.9288, reach="45–75 mil", commercial="A avenida. Separado de quem entrou.", radius=900),
    ],
    offer=(
        "No Minas você compra o mall — a Cristiano Machado é outro recorte.",
        [
            ("No mall", "Display e portais para quem entrou."),
            ("Na praça", "Vídeo na alimentação."),
            ("Na avenida", "Portais para quem só passou."),
        ],
    ),
    defense={
        "lead": "É o mall de escala da zona nordeste.",
        "body": "A Cristiano Machado traz volume. A campanha que quer loja compra o prédio; a que quer avenida compra o halo.",
    },
)

SHOPPING_DEL_REY = _venue(
    slug="shopping-del-rey",
    place_type="shopping",
    city="bh",
    title="Shopping Del Rey",
    code="DRY",
    operator="Aliansce Sonae / Allos · Padre Eustáquio",
    subtitle="O mall da Pampulha de baixo. Quem entrou não é o bairro do Del Rey.",
    annual=7_200_000,
    annual_label="~7,2 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Padre Eustáquio", "Carlos Prates", "Alto Caiçaras"],
    profile="Quem compra no Del Rey e quem mora em Padre Eustáquio. O mall não é o bairro.",
    geo=_geo(-19.9230, -43.9598, 16),
    points=[
        _core("dry", "Mall", -19.9230, -43.9598, reach="95–160 mil", commercial="Quem cruzou a porta do Del Rey.", invest="R$ 28–48 mil", radius=200),
        _food("dry", -19.9233, -43.9593, reach="35–60 mil", commercial="Quem parou na praça."),
        _park("dry", -19.9236, -43.9606, reach="45–75 mil", commercial="Quem veio de carro."),
        _halo("dry", "Padre Eustáquio", -19.9178, -43.9665, reach="35–60 mil", commercial="O bairro. Não é presença no mall."),
    ],
    offer=(
        "No Del Rey você compra quem entrou — Padre Eustáquio é halo.",
        [
            ("No mall", "Display para quem cruzou a porta."),
            ("Na praça", "Vídeo no almoço e no jantar."),
            ("No bairro", "Portais em Padre Eustáquio."),
        ],
    ),
    defense={
        "lead": "É o mall de conveniência da Pampulha baixa.",
        "body": "Família e bairro. Quem quer o corredor da Pampulha não compra este raio — compra o entorno.",
    },
)

MERCADO_CENTRAL_BH = _venue(
    slug="mercado-central-bh",
    place_type="evento",
    city="bh",
    title="Mercado Central",
    code="MCB",
    operator="Mercado Central · Centro de Belo Horizonte",
    subtitle="O mercado fica. O sábado e a terça são recortes diferentes. Compre o quarteirão, não o Centro inteiro.",
    annual=3_800_000,
    annual_label="~3,8 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Centro", "Lourdes", "Funcionários"],
    profile="Quem entra no mercado e quem só passa na Augusto de Lima. O quarteirão não é o Centro.",
    geo=_geo(-19.9227, -43.9426, 17),
    points=[
        _core("mcb", "Mercado", -19.9227, -43.9426, kind="marco", reach="50–85 mil", commercial="Quem entrou no quarteirão do Mercado Central.", invest="R$ 18–32 mil", radius=160),
        {
            "id": "mcb-boxes",
            "name": "Boxes e bares",
            "kind": "pessoas",
            "lat": -19.9229,
            "lng": -43.9423,
            "radius_m": 100,
            "radius_label": "100 m",
            "reach": "22–40 mil",
            "formats": ["Vídeo vertical", "Display"],
            "audiences": ["Gastronomia"],
            "commercial": "Quem parou no box e no bar. Intenção alta, raio curto.",
            "defense": "Quem parou no box e no bar. Intenção alta, raio curto.",
            "investment": "R$ 12–22 mil",
            "source": "Interior",
        },
        _halo("mcb", "Augusto de Lima", -19.9208, -43.9385, reach="40–70 mil", commercial="A avenida e o Centro. Não é quem entrou no mercado.", radius=700),
    ],
    offer=(
        "No Mercado você compra o quarteirão — o Centro é outro recorte.",
        [
            ("No mercado", "Display para quem entrou."),
            ("Nos boxes", "Vídeo para quem parou para comer e beber."),
            ("No Centro", "Portais na Augusto de Lima."),
        ],
    ),
    defense={
        "lead": "É o ponto de encontro gastronômico do Centro.",
        "body": "Sábado pesa. Terça é outro volume. A campanha compra o quarteirão, não os 400 mil do hipercentro.",
    },
)

SHOPPING_MORUMBI = _venue(
    slug="shopping-morumbi",
    place_type="shopping",
    city="sp",
    title="Shopping Morumbi",
    code="SMB",
    operator="Multiplan · Santo Amaro",
    subtitle="O mall da Roque Petroni. Quem entrou não é o fluxo da Berrini.",
    annual=18_000_000,
    annual_label="~18 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Santo Amaro", "Brooklin", "Morumbi"],
    profile="Quem compra no Morumbi e quem trabalha na Berrini. O mall não é o escritório.",
    geo=_geo(-23.6232, -46.6989, 16),
    points=[
        _core("smb", "Mall", -23.6232, -46.6989, reach="240–400 mil", commercial="Quem cruzou a porta do Morumbi. Recorte de escala.", invest="R$ 40–70 mil", radius=240),
        _food("smb", -23.6235, -46.6983, reach="80–130 mil", commercial="Quem parou na praça."),
        _park("smb", -23.6240, -46.6998, reach="90–150 mil", commercial="Quem veio de carro pela Roque Petroni."),
        _halo("smb", "Berrini", -23.6108, -46.6972, reach="70–120 mil", commercial="O escritório. Não entrou no mall.", radius=1000),
    ],
    offer=(
        "No Morumbi você compra o mall — a Berrini é outro recorte.",
        [
            ("No mall", "Display e portais para quem entrou."),
            ("Na praça", "Vídeo no almoço."),
            ("Na Berrini", "Portais para o escritório."),
        ],
    ),
    defense={
        "lead": "É o mall de escala do sudoeste paulistano.",
        "body": "Volume real. A Berrini ao lado é halo de escritório — não some à loja.",
    },
)

JK_IGUATEMI = _venue(
    slug="jk-iguatemi",
    place_type="shopping",
    city="sp",
    title="JK Iguatemi",
    code="JKI",
    operator="Iguatemi · Vila Olímpia",
    subtitle="O mall da JK. Ticket alto. A Faria Lima da Vila Olímpia é outro recorte.",
    annual=6_500_000,
    annual_label="~6,5 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Vila Olímpia", "Itaim Bibi", "Brooklin"],
    profile="Quem compra no JK e quem trabalha na Vila Olímpia. O mall não é o escritório.",
    geo=_geo(-23.5906, -46.6878, 16),
    points=[
        _core("jki", "Mall", -23.5906, -46.6878, reach="85–140 mil", commercial="Quem cruzou a porta do JK Iguatemi. Recorte premium.", invest="R$ 28–48 mil", radius=180),
        _food("jki", -23.5909, -46.6873, reach="30–55 mil", commercial="Quem parou na gastronomia."),
        _park("jki", -23.5912, -46.6885, reach="35–60 mil", commercial="Quem veio de carro."),
        _halo("jki", "Vila Olímpia", -23.5958, -46.6860, reach="55–95 mil", commercial="O escritório. Não entrou no mall."),
    ],
    offer=(
        "No JK você compra quem entrou — a Vila Olímpia é halo.",
        [
            ("No mall", "Display e portais premium."),
            ("Na praça", "Vídeo no almoço e no jantar."),
            ("No bairro", "Portais para o escritório."),
        ],
    ),
    defense={
        "lead": "É o Iguatemi da Vila Olímpia, não o da Faria Lima.",
        "body": "Ticket alto, raio curto. Quem trabalha no bairro não entra na conta de quem comprou na loja.",
    },
)

SHOPPING_ELDORADO = _venue(
    slug="shopping-eldorado",
    place_type="shopping",
    city="sp",
    title="Shopping Eldorado",
    code="ELD",
    operator="Sonae Sierra · Pinheiros",
    subtitle="O mall da Rebouças. Quem entrou não é o fluxo de Pinheiros.",
    annual=14_000_000,
    annual_label="~14 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Pinheiros", "Alto de Pinheiros", "Vila Madalena"],
    profile="Quem compra no Eldorado e quem circula em Pinheiros. O mall não é o bairro.",
    geo=_geo(-23.5725, -46.6962, 16),
    points=[
        _core("eld", "Mall", -23.5725, -46.6962, reach="190–310 mil", commercial="Quem cruzou a porta do Eldorado.", invest="R$ 40–70 mil", radius=220),
        _food("eld", -23.5728, -46.6956, reach="65–110 mil", commercial="Quem parou na praça."),
        _park("eld", -23.5732, -46.6971, reach="75–120 mil", commercial="Quem veio de carro pela Rebouças."),
        _halo("eld", "Pinheiros", -23.5668, -46.6912, reach="60–100 mil", commercial="O bairro. Não é o mall.", radius=900),
    ],
    offer=(
        "No Eldorado você compra o mall — Pinheiros é outro recorte.",
        [
            ("No mall", "Display e portais para quem entrou."),
            ("Na praça", "Vídeo na alimentação."),
            ("No bairro", "Portais em Pinheiros."),
        ],
    ),
    defense={
        "lead": "É o mall de Pinheiros, com escala de regional.",
        "body": "A Rebouças traz o carro. A Vila Madalena ao lado é halo — não some à loja.",
    },
)

VILLA_LOBOS = _venue(
    slug="parque-villa-lobos",
    place_type="evento",
    city="sp",
    title="Parque Villa-Lobos",
    code="VLB",
    operator="Governo do Estado de São Paulo",
    subtitle="O parque fica. O domingo e o show são recortes. Compre o gramado, não os 10 milhões do ano.",
    annual=5_500_000,
    annual_label="~5,5 mi",
    annual_source="Estimativa de visitantes no ano",
    neighborhoods=["Alto de Pinheiros", "Villa Lobos", "Jaguaré"],
    profile="Quem corre no gramado e quem mora no Alto de Pinheiros. O evento não é o entorno.",
    geo=_geo(-23.5468, -46.7247, 15),
    points=[
        _core("vlb", "Portão e gramado", -23.5468, -46.7247, kind="marco", reach="70–120 mil", commercial="Quem entrou pelo portão. Onde o parque começa.", invest="R$ 18–32 mil", radius=300),
        {
            "id": "vlb-gramado",
            "name": "Gramado",
            "kind": "pessoas",
            "lat": -23.5476,
            "lng": -46.7262,
            "radius_m": 400,
            "radius_label": "400 m",
            "reach": "90–150 mil",
            "formats": ["Vídeo vertical", "Display"],
            "audiences": ["Lazer e esporte"],
            "commercial": "Quem ficou no gramado. Domingo é outro volume.",
            "defense": "Quem ficou no gramado. Domingo é outro volume.",
            "investment": "R$ 14–26 mil",
            "source": "Parque",
        },
        _halo("vlb", "Alto de Pinheiros", -23.5528, -46.7125, reach="50–85 mil", commercial="O bairro. Não é quem entrou no parque.", radius=1000),
    ],
    offer=(
        "No Villa-Lobos você compra o portão ou o domingo — não o ano inteiro.",
        [
            ("No portão", "Display para quem entra."),
            ("No gramado", "Vídeo para o domingo e a corrida."),
            ("No bairro", "Portais no Alto de Pinheiros."),
        ],
    ),
    defense={
        "lead": "É o parque de lazer do oeste.",
        "body": "Domingo pesa. Show no gramado é outro recorte. O entorno residencial não é presença no parque.",
    },
)

MERCADO_MUNICIPAL_SP = _venue(
    slug="mercado-municipal-sp",
    place_type="evento",
    city="sp",
    title="Mercado Municipal",
    code="MSP",
    operator="Prefeitura de São Paulo · Centro",
    subtitle="O Mercadão fica. O turista e o atacado são recortes. Compre o quarteirão.",
    annual=7_000_000,
    annual_label="~7 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Centro", "Bom Retiro", "Sé"],
    profile="Quem entra no Mercadão e quem só passa na Cantareira. O mercado não é o Centro.",
    geo=_geo(-23.5416, -46.6295, 17),
    points=[
        _core("msp", "Mercadão", -23.5416, -46.6295, kind="marco", reach="95–160 mil", commercial="Quem entrou no quarteirão do Mercado Municipal.", invest="R$ 28–48 mil", radius=180),
        {
            "id": "msp-boxes",
            "name": "Boxes e mezzanino",
            "kind": "pessoas",
            "lat": -23.5418,
            "lng": -46.6291,
            "radius_m": 110,
            "radius_label": "110 m",
            "reach": "40–70 mil",
            "formats": ["Vídeo vertical", "Display"],
            "audiences": ["Gastronomia e turismo"],
            "commercial": "Quem parou no sanduíche e no box. Intenção alta.",
            "defense": "Quem parou no sanduíche e no box. Intenção alta.",
            "investment": "R$ 14–26 mil",
            "source": "Interior",
        },
        _halo("msp", "Centro", -23.5455, -46.6348, reach="55–95 mil", commercial="O Centro. Não é quem entrou no Mercadão.", radius=800),
    ],
    offer=(
        "No Mercadão você compra o quarteirão — o Centro é halo.",
        [
            ("No mercado", "Display para quem entrou."),
            ("Nos boxes", "Vídeo para quem parou para comer."),
            ("No Centro", "Portais na Cantareira e na Sé."),
        ],
    ),
    defense={
        "lead": "É o mercado mais reconhecido de São Paulo.",
        "body": "Turista e atacado no mesmo quarteirão. A campanha compra o prédio, não o hipercentro.",
    },
)

BARRA_SHOPPING = _venue(
    slug="barra-shopping",
    place_type="shopping",
    city="rj",
    title="BarraShopping",
    code="BRS",
    operator="Multiplan · Barra da Tijuca",
    subtitle="O mall das Américas. Quem entrou no complexo não é quem só passou na Barra.",
    annual=22_000_000,
    annual_label="~22 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Barra da Tijuca", "Jacarepaguá", "Recreio"],
    profile="Quem compra no BarraShopping e quem circula na Barra. O complexo não é a avenida.",
    geo=_geo(-22.9974, -43.3583, 16),
    points=[
        _core("brs", "Mall", -22.9974, -43.3583, reach="290–480 mil", commercial="Quem cruzou a porta do BarraShopping. Recorte de escala.", invest="R$ 55–95 mil", radius=260),
        _food("brs", -22.9978, -43.3576, reach="90–150 mil", commercial="Quem parou na praça."),
        _park("brs", -22.9984, -43.3594, reach="110–180 mil", commercial="Quem veio de carro pelas Américas."),
        _halo("brs", "Barra da Tijuca", -22.9998, -43.3455, reach="80–140 mil", commercial="A Barra. Não é presença no mall.", radius=1200),
    ],
    offer=(
        "No BarraShopping você compra o complexo — a Barra é outro recorte.",
        [
            ("No mall", "Display e portais para quem entrou."),
            ("Na praça", "Vídeo na alimentação."),
            ("Na Barra", "Portais para quem só circula no bairro."),
        ],
    ),
    defense={
        "lead": "É o maior mall do Rio e um dos maiores do país.",
        "body": "Escala de verdade. A Av. das Américas ao lado é halo — não some a quem entrou na loja.",
    },
)

RIO_SUL = _venue(
    slug="rio-sul",
    place_type="shopping",
    city="rj",
    title="Rio Sul",
    code="RSL",
    operator="Multiplan · Botafogo",
    subtitle="O mall do túnel. Quem entrou não é o fluxo de Botafogo.",
    annual=10_000_000,
    annual_label="~10 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Botafogo", "Humaitá", "Urca"],
    profile="Quem compra no Rio Sul e quem trabalha em Botafogo. O mall não é o bairro.",
    geo=_geo(-22.9567, -43.1762, 16),
    points=[
        _core("rsl", "Mall", -22.9567, -43.1762, reach="130–220 mil", commercial="Quem cruzou a porta do Rio Sul.", invest="R$ 28–48 mil", radius=200),
        _food("rsl", -22.9570, -43.1757, reach="45–75 mil", commercial="Quem parou na praça."),
        _park("rsl", -22.9574, -43.1769, reach="55–90 mil", commercial="Quem veio de carro pelo túnel."),
        _halo("rsl", "Botafogo", -22.9512, -43.1825, reach="50–85 mil", commercial="O bairro. Não é o mall."),
    ],
    offer=(
        "No Rio Sul você compra quem entrou — Botafogo é halo.",
        [
            ("No mall", "Display para quem cruzou a porta."),
            ("Na praça", "Vídeo no almoço."),
            ("No bairro", "Portais em Botafogo."),
        ],
    ),
    defense={
        "lead": "É o mall de passagem entre Zona Sul e Centro.",
        "body": "O túnel traz o carro. Quem só trabalha em Botafogo não entra na conta da loja.",
    },
)

SHOPPING_LEBLON = _venue(
    slug="shopping-leblon",
    place_type="shopping",
    city="rj",
    title="Shopping Leblon",
    code="LBN",
    operator="Multiplan · Leblon",
    subtitle="O mall do Leblon. Ticket alto. A orla é outro recorte.",
    annual=5_800_000,
    annual_label="~5,8 mi",
    annual_source="Estimativa de visitas no ano",
    neighborhoods=["Leblon", "Ipanema", "Gávea"],
    profile="Quem compra no mall e quem está na orla. O prédio não é a praia.",
    geo=_geo(-22.9822, -43.2168, 17),
    points=[
        _core("lbn", "Mall", -22.9822, -43.2168, reach="75–125 mil", commercial="Quem cruzou a porta do Shopping Leblon. Recorte premium.", invest="R$ 28–48 mil", radius=160),
        _food("lbn", -22.9825, -43.2163, reach="28–48 mil", commercial="Quem parou na gastronomia."),
        _park("lbn", -22.9820, -43.2175, reach="30–50 mil", commercial="Quem veio de carro."),
        _halo("lbn", "Orla do Leblon", -22.9874, -43.2232, reach="45–80 mil", commercial="A praia. Não é presença no mall.", radius=800),
    ],
    offer=(
        "No Leblon você compra o mall — a orla é halo.",
        [
            ("No mall", "Display e portais premium."),
            ("Na praça", "Vídeo no almoço e no jantar."),
            ("Na orla", "Portais para quem só está na praia."),
        ],
    ),
    defense={
        "lead": "É o mall de ticket mais alto da Zona Sul.",
        "body": "Raio curto de propósito. Quem está na areia não entra na conta de quem comprou na loja.",
    },
)

MARACANA = _venue(
    slug="maracana",
    place_type="evento",
    city="rj",
    title="Maracanã",
    code="MAR",
    operator="Complexo Maracanã · Rio de Janeiro",
    subtitle="O estádio fica. O jogo passa. Compre o dia do evento, não o bairro do Maracanã.",
    annual=2_400_000,
    annual_label="Agenda",
    annual_source="O volume segue o jogo e o show, não o calendário do ano",
    neighborhoods=["Maracanã", "Tijuca", "Vila Isabel"],
    profile="Quem foi ao jogo e quem mora na Tijuca. O estádio não é o bairro.",
    geo=_geo(-22.9121, -43.2302, 16),
    four_weeks=180_000,
    addressable=42_000,
    points=[
        _core("mar", "Estádio", -22.9121, -43.2302, kind="marco", reach="25–50 mil", commercial="Quem passou a catraca. Só vale com jogo ou show.", invest="R$ 18–32 mil", radius=280),
        {
            "id": "mar-acesso",
            "name": "Acesso e metrô",
            "kind": "mobilidade",
            "lat": -22.9098,
            "lng": -43.2290,
            "radius_m": 350,
            "radius_label": "350 m",
            "reach": "18–35 mil",
            "formats": APPS,
            "audiences": ["Chegada"],
            "commercial": "Quem chegou de metrô ou a pé. Fora da catraca.",
            "defense": "Quem chegou de metrô ou a pé. Fora da catraca.",
            "investment": "R$ 12–22 mil",
            "source": "Acesso",
        },
        _halo("mar", "Tijuca", -22.9215, -43.2318, reach="40–70 mil", commercial="O bairro. Não é presença no jogo.", radius=1000),
    ],
    offer=(
        "No Maracanã você compra o dia do jogo — a Tijuca é outro recorte.",
        [
            ("No estádio", "Display para quem passou a catraca."),
            ("Na chegada", "Apps no metrô e no acesso."),
            ("No bairro", "Portais na Tijuca, sem somar ao jogo."),
        ],
    ),
    defense={
        "lead": "É o recorte de evento mais reconhecido do Rio.",
        "body": "Sem jogo o número cai. A campanha compra a janela do evento, não os 400 mil da Tijuca.",
    },
)

PARQUE_LAGE = _venue(
    slug="parque-lage",
    place_type="evento",
    city="rj",
    title="Parque Lage",
    code="PLG",
    operator="EAV Parque Lage · Jardim Botânico",
    subtitle="O parque e a escola ficam. O domingo e a exposição são recortes. Compre o portão.",
    annual=1_200_000,
    annual_label="~1,2 mi",
    annual_source="Estimativa de visitantes no ano",
    neighborhoods=["Jardim Botânico", "Lagoa", "Gávea"],
    profile="Quem entra no parque e quem mora no Jardim Botânico. O gramado não é o bairro.",
    geo=_geo(-22.9608, -43.2115, 16),
    points=[
        _core("plg", "Palacete e portão", -22.9608, -43.2115, kind="marco", reach="18–32 mil", commercial="Quem entrou pelo portão e pelo palacete.", invest="R$ 12–22 mil", radius=200),
        {
            "id": "plg-gramado",
            "name": "Gramado",
            "kind": "pessoas",
            "lat": -22.9614,
            "lng": -43.2122,
            "radius_m": 250,
            "radius_label": "250 m",
            "reach": "22–40 mil",
            "formats": ["Vídeo vertical", "Display"],
            "audiences": ["Lazer e cultura"],
            "commercial": "Quem ficou no gramado. Domingo é outro volume.",
            "defense": "Quem ficou no gramado. Domingo é outro volume.",
            "investment": "R$ 12–22 mil",
            "source": "Parque",
        },
        _halo("plg", "Jardim Botânico", -22.9665, -43.2188, reach="30–55 mil", commercial="O bairro. Não é quem entrou no parque."),
    ],
    offer=(
        "No Parque Lage você compra o portão — o Jardim Botânico é halo.",
        [
            ("No portão", "Display para quem entra."),
            ("No gramado", "Vídeo para o domingo."),
            ("No bairro", "Portais no Jardim Botânico."),
        ],
    ),
    defense={
        "lead": "É o parque-escola da Zona Sul, com foto e permanência.",
        "body": "Público jovem e cultural. O bairro ao lado é halo residencial — não some ao gramado.",
    },
)

def _with_photos(place, hero, point="", heroes=None, points=None):
    payload = dict(place["payload"])
    media = dict(payload.get("media") or {})
    media["hero_url"] = hero
    gallery = []
    for index, url in enumerate(heroes or [hero]):
        gallery.append({"id": f"{place['slug']}-hero-{index}", "kind": "hero", "url": url, "selected": index == 0})
    core_id = (payload.get("points") or [{}])[0].get("id") or ""
    for index, url in enumerate(points or ([point] if point else [])):
        gallery.append(
            {
                "id": f"{place['slug']}-pt-{index}",
                "kind": "point",
                "point_id": core_id,
                "url": url,
                "selected": index == 0,
            }
        )
    media["gallery"] = gallery
    payload["media"] = media
    rows = list(payload.get("points") or [])
    if point and rows:
        rows[0] = dict(rows[0], image_url=point)
        payload["points"] = rows
    place["payload"] = normalize_payload(payload)
    return place


BH_SHOPPING = _with_photos(
    BH_SHOPPING,
    "/static/images/places/gallery/bh-shopping-hero-6d07d975.jpg",
    "/static/images/places/gallery/bh-shopping-point-b858874a.jpg",
    heroes=[
        "/static/images/places/gallery/bh-shopping-hero-6d07d975.jpg",
        "/static/images/places/gallery/bh-shopping-hero-4cddd28e.jpg",
        "/static/images/places/gallery/bh-shopping-hero-b858874a.jpg",
        "/static/images/places/gallery/bh-shopping-hero-908a5413.jpg",
    ],
    points=[
        "/static/images/places/gallery/bh-shopping-point-b858874a.jpg",
        "/static/images/places/gallery/bh-shopping-point-908a5413.jpg",
        "/static/images/places/gallery/bh-shopping-point-aeeaa837.jpg",
    ],
)
PATIO_SAVASSI = _with_photos(
    PATIO_SAVASSI,
    "/static/images/places/gallery/patio-savassi-hero-51123178.jpg",
    "/static/images/places/gallery/patio-savassi-hero-51123178.jpg",
    heroes=[
        "/static/images/places/gallery/patio-savassi-hero-51123178.jpg",
        "/static/images/places/gallery/patio-savassi-hero-e1082692.jpg",
        "/static/images/places/gallery/patio-savassi-hero-48b7971e.png",
    ],
    points=["/static/images/places/gallery/patio-savassi-hero-51123178.jpg"],
)
MINAS_SHOPPING = _with_photos(
    MINAS_SHOPPING,
    "/static/images/places/gallery/minas-shopping-hero-bfb6ac91.jpg",
    "/static/images/places/gallery/minas-shopping-point-85a6e313.jpg",
    heroes=[
        "/static/images/places/gallery/minas-shopping-hero-bfb6ac91.jpg",
        "/static/images/places/gallery/minas-shopping-hero-85a6e313.jpg",
        "/static/images/places/gallery/minas-shopping-hero-a6a97906.jpg",
    ],
    points=["/static/images/places/gallery/minas-shopping-point-85a6e313.jpg"],
)
SHOPPING_DEL_REY = _with_photos(
    SHOPPING_DEL_REY,
    "/static/images/places/gallery/shopping-del-rey-hero-179b69cc.jpg",
    "/static/images/places/gallery/shopping-del-rey-point-179b69cc.jpg",
    heroes=["/static/images/places/gallery/shopping-del-rey-hero-179b69cc.jpg"],
    points=[
        "/static/images/places/gallery/shopping-del-rey-point-179b69cc.jpg",
        "/static/images/places/gallery/shopping-del-rey-point-9e90e9d6.jpg",
    ],
)
MERCADO_CENTRAL_BH = _with_photos(
    MERCADO_CENTRAL_BH,
    "/static/images/places/gallery/mercado-central-bh-hero-542e14d7.jpg",
    "/static/images/places/gallery/mercado-central-bh-point-542e14d7.jpg",
    heroes=[
        "/static/images/places/gallery/mercado-central-bh-hero-542e14d7.jpg",
        "/static/images/places/gallery/mercado-central-bh-hero-4734c663.jpg",
        "/static/images/places/gallery/mercado-central-bh-hero-a898b226.jpg",
    ],
    points=["/static/images/places/gallery/mercado-central-bh-point-542e14d7.jpg"],
)
SHOPPING_MORUMBI = _with_photos(
    SHOPPING_MORUMBI,
    "/static/images/places/gallery/shopping-morumbi-hero-183dc36b.jpg",
    "/static/images/places/gallery/shopping-morumbi-point-183dc36b.jpg",
    heroes=[
        "/static/images/places/gallery/shopping-morumbi-hero-183dc36b.jpg",
        "/static/images/places/gallery/shopping-morumbi-hero-c5f274cb.jpg",
        "/static/images/places/gallery/shopping-morumbi-hero-575b3fd5.jpg",
    ],
    points=["/static/images/places/gallery/shopping-morumbi-point-183dc36b.jpg"],
)
JK_IGUATEMI = _with_photos(
    JK_IGUATEMI,
    "/static/images/places/gallery/jk-iguatemi-hero-6d730adf.jpg",
    "/static/images/places/gallery/jk-iguatemi-point-7d46fc7e.jpg",
    heroes=[
        "/static/images/places/gallery/jk-iguatemi-hero-6d730adf.jpg",
        "/static/images/places/gallery/jk-iguatemi-hero-d2dd8611.jpg",
        "/static/images/places/gallery/jk-iguatemi-hero-8b2defab.jpg",
    ],
    points=["/static/images/places/gallery/jk-iguatemi-point-7d46fc7e.jpg"],
)
SHOPPING_ELDORADO = _with_photos(
    SHOPPING_ELDORADO,
    "/static/images/places/gallery/shopping-eldorado-hero-38251cba.jpg",
    "/static/images/places/gallery/shopping-eldorado-point-117612d9.jpg",
    heroes=[
        "/static/images/places/gallery/shopping-eldorado-hero-38251cba.jpg",
        "/static/images/places/gallery/shopping-eldorado-hero-fa19fcc9.jpg",
    ],
    points=["/static/images/places/gallery/shopping-eldorado-point-117612d9.jpg"],
)
VILLA_LOBOS = _with_photos(
    VILLA_LOBOS,
    "/static/images/places/gallery/parque-villa-lobos-hero-a4db48b7.jpg",
    "/static/images/places/gallery/parque-villa-lobos-point-a4db48b7.jpg",
    heroes=[
        "/static/images/places/gallery/parque-villa-lobos-hero-a4db48b7.jpg",
        "/static/images/places/gallery/parque-villa-lobos-hero-0f57dc6f.jpg",
        "/static/images/places/gallery/parque-villa-lobos-hero-00b3c47c.jpg",
    ],
    points=["/static/images/places/gallery/parque-villa-lobos-point-a4db48b7.jpg"],
)
MERCADO_MUNICIPAL_SP = _with_photos(
    MERCADO_MUNICIPAL_SP,
    "/static/images/places/gallery/mercado-municipal-sp-hero-330abeb7.jpg",
    "/static/images/places/gallery/mercado-municipal-sp-point-31f95c0f.jpg",
    heroes=[
        "/static/images/places/gallery/mercado-municipal-sp-hero-330abeb7.jpg",
        "/static/images/places/gallery/mercado-municipal-sp-hero-90ebf699.jpg",
        "/static/images/places/gallery/mercado-municipal-sp-hero-066c9a4d.jpg",
    ],
    points=["/static/images/places/gallery/mercado-municipal-sp-point-31f95c0f.jpg"],
)
BARRA_SHOPPING = _with_photos(
    BARRA_SHOPPING,
    "/static/images/places/gallery/barra-shopping-hero-5e8b304d.jpg",
    "/static/images/places/gallery/barra-shopping-point-7afa07fa.jpg",
    heroes=[
        "/static/images/places/gallery/barra-shopping-hero-5e8b304d.jpg",
        "/static/images/places/gallery/barra-shopping-hero-1ed0b729.jpg",
        "/static/images/places/gallery/barra-shopping-hero-77ccad64.jpg",
    ],
    points=["/static/images/places/gallery/barra-shopping-point-7afa07fa.jpg"],
)
RIO_SUL = _with_photos(
    RIO_SUL,
    "/static/images/places/gallery/rio-sul-hero-16be8a3f.jpg",
    "/static/images/places/gallery/rio-sul-point-beccd264.png",
    heroes=[
        "/static/images/places/gallery/rio-sul-hero-16be8a3f.jpg",
        "/static/images/places/gallery/rio-sul-hero-ecacdcb1.jpg",
        "/static/images/places/gallery/rio-sul-hero-beccd264.png",
    ],
    points=["/static/images/places/gallery/rio-sul-point-beccd264.png"],
)
SHOPPING_LEBLON = _with_photos(
    SHOPPING_LEBLON,
    "/static/images/places/gallery/shopping-leblon-hero-395b5c56.jpg",
    "/static/images/places/gallery/shopping-leblon-point-cc89785e.jpg",
    heroes=["/static/images/places/gallery/shopping-leblon-hero-395b5c56.jpg"],
    points=["/static/images/places/gallery/shopping-leblon-point-cc89785e.jpg"],
)
MARACANA = _with_photos(
    MARACANA,
    "/static/images/places/gallery/maracana-hero-e06e36cd.jpg",
    "/static/images/places/gallery/maracana-hero-e06e36cd.jpg",
    heroes=["/static/images/places/gallery/maracana-hero-e06e36cd.jpg"],
    points=["/static/images/places/gallery/maracana-hero-e06e36cd.jpg"],
)
PARQUE_LAGE = _with_photos(
    PARQUE_LAGE,
    "/static/images/places/gallery/parque-lage-hero-57801413.png",
    "/static/images/places/gallery/parque-lage-point-57801413.png",
    heroes=[
        "/static/images/places/gallery/parque-lage-hero-57801413.png",
        "/static/images/places/gallery/parque-lage-hero-c5ce7404.jpg",
        "/static/images/places/gallery/parque-lage-hero-ceab7ea0.png",
    ],
    points=["/static/images/places/gallery/parque-lage-point-57801413.png"],
)

VENUE_PLACES = (
    BH_SHOPPING,
    PATIO_SAVASSI,
    MINAS_SHOPPING,
    SHOPPING_DEL_REY,
    MERCADO_CENTRAL_BH,
    SHOPPING_MORUMBI,
    JK_IGUATEMI,
    SHOPPING_ELDORADO,
    VILLA_LOBOS,
    MERCADO_MUNICIPAL_SP,
    BARRA_SHOPPING,
    RIO_SUL,
    SHOPPING_LEBLON,
    MARACANA,
    PARQUE_LAGE,
)
