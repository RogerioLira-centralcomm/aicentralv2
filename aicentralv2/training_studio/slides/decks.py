"""Páginas projetáveis da Imersão — conteúdo oficial das 9 sessões."""

from ...places.catalog import CONGONHAS, CONFINS, GALEAO, SANTOS_DUMONT
from ..agenda import SESSIONS
from ..logos import logo_path


def _metric(label, value, note=""):
    return {"label": label, "value": value, "note": note}


def _card(title, text, meta=""):
    return {"title": title, "text": text, "meta": meta}


def _logo(key, name, text):
    return {"key": key, "name": name, "src": logo_path(key), "text": text}


def _place(place):
    payload = place.get("payload") or {}
    media = payload.get("media") or {}
    metrics = payload.get("metrics") or {}
    points = []
    for point in payload.get("points") or []:
        if not point.get("image_url"):
            continue
        points.append(
            {
                "src": point["image_url"],
                "alt": f"{place.get('code')} {point.get('name')}",
                "caption": point.get("name") or "",
            }
        )
    return {
        "code": place.get("code") or "",
        "title": place.get("title") or "",
        "subtitle": place.get("subtitle") or "",
        "hero": media.get("hero_url") or "",
        "map": media.get("map_url") or "",
        "pax": (metrics.get("passengers") or {}).get("label") or "",
        "addressable": (metrics.get("addressable") or {}).get("label") or "",
        "points": points[:2],
    }


def _session_meta(slug):
    for item in SESSIONS:
        if item["slug"] == slug:
            return item
    raise KeyError(slug)


def _deck(slug, slides):
    item = _session_meta(slug)
    return {
        "slug": slug,
        "titulo": item["titulo"],
        "horario": f"{item['horario_inicio']}–{item['horario_fim']}",
        "facilitadores": list(item.get("facilitadores") or []),
        "tipo": item.get("tipo") or "bloco",
        "slides": slides,
    }


def _atencao():
    return [
        {
            "layout": "title",
            "kicker": "Sessão 1 · 09:30–09:45",
            "title": "Comprem atenção, não impressão",
            "lede": "A unidade de valor vem antes do mix.",
            "meta": "Alexandre Borges · Apolo Lira",
        },
        {
            "layout": "statement",
            "kicker": "Pergunta da sala",
            "title": "No último plano que vocês aprovaram, a unidade de valor era a mesma do KPI do cliente?",
            "note": "Abrir com a pergunta. Os números existem para provar saturação e bases incomparáveis — não para impressionar alcance.",
        },
        {
            "layout": "split",
            "kicker": "Tese",
            "title": "Viewability é a porta. Não é o impacto.",
            "left": {
                "title": "O que a mesa já compra",
                "lines": [
                    "MRC: 50% dos pixels por 1s no display, 2s no vídeo",
                    "Fecha plano em impressão viewable",
                    "Compra oportunidade, não olhar",
                ],
            },
            "right": {
                "title": "IAB + CIMM, nov/2025",
                "lines": [
                    "Atenção complementa viewability",
                    "Não substitui a porta técnica",
                    "Não vira KPI único de campanha",
                ],
            },
            "footnote": "Attention Measurement Playbook for Marketers — IAB / CIMM",
        },
        {
            "layout": "metrics",
            "kicker": "Saturação · datar no palco",
            "title": "O Brasil não é o mundo médio",
            "metrics": [
                _metric("Brasil", "9h09", "Digital 2025, jan/2025"),
                _metric("Mundo adulto", "6h38", "GWI / Digital 2025"),
            ],
            "footnote": "Frequência sobe. Substituição fica opaca. O Digital 2026 não republicou 9h09 na página livre.",
        },
        {
            "layout": "metrics",
            "kicker": "Digital 2026 Brazil · out/2025",
            "title": "185 milhões online. 150 milhões de identidades.",
            "metrics": [
                _metric("População", "213 mi", "Brasil"),
                _metric("Internet", "185 mi", "86,9%"),
                _metric("Redes", "150 mi", "identidades, 70,4%"),
                _metric("Mundo online", "5,56 bi", "Digital 2025"),
            ],
            "footnote": "Identidade não é indivíduo único. Não misturar jan/25 com out/25.",
        },
        {
            "layout": "chart",
            "kicker": "Ad reach · final de 2025",
            "title": "Não some estas bases. LinkedIn nem entra na coluna.",
            "chart": {
                "id": "atencao-reach",
                "type": "bar",
                "labels": ["YouTube", "Instagram", "TikTok 18+", "Facebook", "LinkedIn*"],
                "data": [150, 147, 131, 109, 90],
                "suffix": " mi",
                "caption": "Alcance de anúncio, Digital 2026 Brazil. *LinkedIn = membros cadastrados, não MAU.",
            },
            "footnote": "Ferramentas das plataformas. Ad reach ≠ MAU. 90 mi do LinkedIn não se compara com 147 mi do Instagram.",
        },
        {
            "layout": "cards",
            "kicker": "Três métricas, três autorizações",
            "title": "Não some Lumen com Adelaide.",
            "cards": [
                _card(
                    "Lumen",
                    "Olho no anúncio. MPU ~8% olhado, ~1,3s. 1.000 TVs ~6.000 attentive seconds.",
                    "Autoriza formato × formato. Não autoriza ROAS.",
                ),
                _card(
                    "TVision",
                    "Pessoa na sala + olho na TV. UK: ~20% sem ninguém; 30s ~11,8s de atenção visual.",
                    "Autoriza CTV/TV. Não autoriza feed mobile.",
                ),
                _card(
                    "Adelaide AU",
                    "0 a 100. Qualidade do placement. Não é duração de olhar.",
                    "Autoriza planning. Não traduzir AU em segundos.",
                ),
            ],
        },
        {
            "layout": "statement",
            "kicker": "Regra de briefing",
            "title": "Uma unidade de valor para a primeira onda. E o que ela não prova.",
            "lede": "Viewability, attentive second, AU, VTR qualificado ou CPA de teste. Sem isso, o mix vira lista de logos.",
            "note": "Não definir MRC. Não listar 16 canais. Não tratar ad reach como MAU.",
        },
    ]


def _canais():
    return [
        {
            "layout": "title",
            "kicker": "Sessão 2 · 09:45–10:00",
            "title": "De onde sai a verba",
            "lede": "Cada família tem regra de substituição. Não é census.",
            "meta": "Alexandre Borges · Apolo Lira",
        },
        {
            "layout": "statement",
            "kicker": "Pergunta da sala",
            "title": "De qual família vocês tirariam 20% do budget deste brief — e para onde mandariam?",
            "note": "Não repetir 185 mi / 9h09. Outdoor fica na sessão Places.",
        },
        {
            "layout": "cards",
            "kicker": "O mapa",
            "title": "Quatro famílias. Um case por família, no máximo.",
            "cards": [
                _card("Social e profissional", "Feed × short-form. B2B × consumer.", "Intenção ou volume de vídeo curto"),
                _card("Editorial e portais", "Contexto e brand safety contra CPM do feed.", "Primeira onda de construção"),
                _card("Utilidade e commerce", "Atenção em tarefa, não em lazer.", "Hábito e deslocamento"),
                _card("Ambientes de sessão", "Completion e dwell longo.", "Paga floor. Perde se a verba não chega."),
            ],
        },
        {
            "layout": "family",
            "kicker": "Social e profissional",
            "title": "Feed versus short-form. Member versus MAU.",
            "logos": [
                _logo("linkedin", "LinkedIn", "90 mi members — não MAU. Tiro verba se o KPI for reach consumer ou o criativo só existir em 9:16."),
                _logo("instagram", "Instagram", "147 mi ad reach. Tiro se o brief for B2B de consideração e o feed canibalizar frequência."),
                _logo("tiktok", "TikTok", "131 mi 18+. Estático aqui é desperdício. Tiro se o KPI for completion longo ou o legal bloquear UGC."),
            ],
        },
        {
            "layout": "family",
            "kicker": "Editorial e portais",
            "title": "Adjacência jornalística contra performance cega.",
            "logos": [
                _logo("g1", "g1", "Display, native, takeover. Tiro se o inventário aberto estiver sem deal e sem adjacência."),
                _logo("cnn", "CNN Brasil", "~36,5 mi/mês no portal (2024, catálogo). Tiro se o brief for massa e o CPM não pagar o contexto."),
                _logo("sbt", "SBT", "Portal, +SBT, SBT News. Copa 2026 é janela, não share. Tiro se o adjacente não aguentar news premium."),
                _logo("serasa", "Serasa", "Intenção de crédito. Serve o briefing A. Tiro se o legal não assinar cobrança / score."),
            ],
        },
        {
            "layout": "family",
            "kicker": "Utilidade e commerce",
            "title": "Incrementality contra a mídia do próprio app.",
            "logos": [
                _logo("uber", "Uber", "Dwell de espera, não de feed. Tiro se o brief for consideração longa e o criativo precisar de som."),
                _logo("99", "99", "Mesma família, outra base. Não somar UU. Tiro se já houver teto de frequência em mobility."),
                _logo("ifood", "iFood", "Canibaliza mídia própria. Tiro se o incremental não aparecer."),
                _logo("amazon", "Amazon", "Retail media + áudio. Prime Video não entra aqui. Tiro se não houver SKU."),
            ],
        },
        {
            "layout": "family",
            "kicker": "Ambientes de sessão",
            "title": "Completion contra TV e portal. Floor contra verba.",
            "logos": [
                _logo("spotify", "Spotify", "Áudio não skipável. Tiro se o criativo só existir em vídeo."),
                _logo("netflix", "Netflix", "Ambiente curado. Floor alto. Tiro se a first-wave não pagar o mínimo."),
                _logo("prime", "Prime Video", "Pre-roll, mid-roll, pause. Tiro se não houver ponte com Amazon Ads."),
                _logo("disney", "Disney+", "Família e franquia. Tiro se o recorte for adulto."),
                _logo("hbo", "Max / HBO", "Premium. Mesma lógica de floor do Netflix."),
            ],
        },
        {
            "layout": "statement",
            "kicker": "Fecho",
            "title": "A família ganha ou perde. O logo não decide.",
            "lede": "Escrevam a regra: tiro 20% daqui se… Sem regra, o mapa vira census.",
        },
    ]


def _places():
    cgh, gig, cnf, sdu = (_place(CONGONHAS), _place(GALEAO), _place(CONFINS), _place(SANTOS_DUMONT))
    return [
        {
            "layout": "title",
            "kicker": "Sessão 3 · 10:00–10:20",
            "title": "O lugar não é a audiência",
            "lede": "Tela no lugar não é audiência do lugar.",
            "meta": "Apolo Lira · Alexandre Borges",
        },
        {
            "layout": "statement",
            "kicker": "Pergunta da sala",
            "title": "Neste brief, vocês estão comprando o saguão ou quem mora no entorno?",
            "note": "Conceito em 6 min, quatro aeroportos em 12, fechamento em 2. Mall e Ibirapuera: uma frase.",
        },
        {
            "layout": "split",
            "kicker": "Dois buys",
            "title": "Não misturem CPM de rua com saguão.",
            "left": {
                "title": "DOOH",
                "lines": [
                    "Oportunidade de ver no sítio",
                    "Dwell, ângulo, fluxo",
                    "Aeroporto: passageiro preso no processo, não na calçada",
                ],
            },
            "right": {
                "title": "Geofencing",
                "lines": [
                    "Compra a cerca. Cerca não é presença",
                    "Bacia IBGE ≠ quem embarcou",
                    "Halo (Moema, MG-010, Ilha) não soma com o terminal",
                ],
            },
        },
        {
            "layout": "cards",
            "kicker": "Metodologia Places",
            "title": "Vocês não compram Congonhas. Compram T1, ou Campo Belo, ou Moema.",
            "cards": [
                _card("4 semanas", "Movimento anual ÷ 13", "ANAC 2025 → recorte comercial"),
                _card("Únicos", "Movimentos × 0,62", "Hipótese de passagem"),
                _card("Endereçáveis", "Únicos × 0,38", "App e portal, 4 semanas"),
            ],
            "footnote": "Raios não se somam. Fonte: metodologia Places / ANAC 2025.",
        },
        {
            "layout": "chart",
            "kicker": "ANAC 2025 · não somar",
            "title": "Quatro aeroportos. Quatro buys.",
            "chart": {
                "id": "places-anac",
                "type": "bar",
                "labels": ["CGH", "GIG", "CNF", "SDU"],
                "data": [24.6, 17.8, 13.2, 6.2],
                "suffix": " mi",
                "caption": "Passageiros no ano. Congonhas 24.583.610 · Galeão 17.836.134 · Confins 13.183.039 · Santos Dumont 6.184.233.",
            },
            "footnote": "Bacia residencial é Censo 2022, não presença no terminal.",
        },
        {
            "layout": "place",
            "kicker": "Congonhas",
            "place": cgh,
            "rule": "T1, Campo Belo e Moema são três buys. A cidade em volta não é o saguão.",
        },
        {
            "layout": "place",
            "kicker": "Galeão",
            "place": gig,
            "rule": "Internacional é recorte. Não use 17,8 mi como se fosse o T2 internacional.",
        },
        {
            "layout": "place",
            "kicker": "Confins",
            "place": cnf,
            "rule": "Terminal versus corredor MG-010. Internacional ~4–5% — selo a validar.",
        },
        {
            "layout": "place",
            "kicker": "Santos Dumont",
            "place": sdu,
            "rule": "Pistas ficam fora do comercial. Terminal e VLT/Glória são os buys.",
        },
        {
            "layout": "list",
            "kicker": "Como entra no plano",
            "title": "Places é família. Não é extra criativo.",
            "lines": [
                "Unidade de valor: presença no recorte (7/15/30 dias) ou dwell no saguão — não UU nacional.",
                "First-wave: um aeroporto, um ponto. Escala só depois.",
                "Mall e evento (Diamond, Iguatemi, Ibirapuera, Expominas) usam o mesmo método — não cabem neste bloco.",
                "Na banca: se o brief tiver praça física, Places entra como família.",
            ],
        },
    ]


def _cadu():
    return [
        {
            "layout": "title",
            "kicker": "Sessão 4 · 10:20–10:35",
            "title": "Cadu começa na restrição",
            "lede": "Cadu é a mesa, não a demo de IA.",
            "meta": "Apolo Lira",
        },
        {
            "layout": "statement",
            "kicker": "Pergunta da sala",
            "title": "Qual restrição deste brief o Cadu não pode inventar?",
            "note": "Cinco passos no quadro. Places entra se o brief tiver lugar. Sem slide de produto.",
        },
        {
            "layout": "statement",
            "kicker": "Tese",
            "title": "O planejador desta sala não começa no Excel vazio. Começa com restrição.",
            "lede": "Moeda de valor, família de inventário, recorte Places se houver sítio. IA consulta o catálogo real. Não inventa mix.",
        },
        {
            "layout": "timeline",
            "kicker": "Cinco passos",
            "title": "Restrição → catálogo → first-wave → correção.",
            "steps": [
                _card("1. Briefing", "Objetivo, praça, verba, recorte, brand safety, open web, Places."),
                _card("2. Catálogo", "Famílias digitais + Places. Só o que se transaciona."),
                _card("3. Hipótese", "Percentual por família. Substituição escrita."),
                _card("4. First-wave", "Uma métrica por formato. A moeda da abertura."),
                _card("5. Correção", "Ciclo curto. Escalar só o que aguentou."),
            ],
        },
        {
            "layout": "list",
            "kicker": "O que o Cadu consulta",
            "title": "Se o dado não está no catálogo, o campo fica pendente.",
            "lines": [
                "Modelagem de criativos, operação de PI, Places, inteligência de marca.",
                "Canal fantasma não entra. Roadmap não entra.",
                "A banca cobra o que esta sessão fecha: unidade de valor, família, first-wave.",
            ],
        },
    ]


def _coffee():
    return [
        {
            "layout": "title",
            "kicker": "Intervalo · 10:35–10:45",
            "title": "Intervalo · escolher a moeda",
            "lede": "Dez minutos. Escolher o briefing e a moeda.",
        },
        {
            "layout": "cards",
            "kicker": "Já pensar",
            "title": "Família + moeda + se o brief pede lugar físico.",
            "cards": [
                _card("Fintech", "R$ 80 mil · conta digital · GSP", "Briefing A"),
                _card("Beleza D2C", "R$ 250 mil · skincare · Sudeste", "Briefing B"),
                _card("Food", "R$ 800 mil · app + brand · nacional", "Briefing C"),
            ],
        },
    ]


def _max():
    return [
        {
            "layout": "title",
            "kicker": "Sessão 6 · 10:45–11:20",
            "title": "O plano quebra no formato",
            "lede": "A verba erra menos do que o formato.",
            "meta": "Max III",
        },
        {
            "layout": "statement",
            "kicker": "Pergunta da sala",
            "title": "Qual métrica da primeira onda deste formato autoriza escalar?",
            "note": "Quatro patologias, depois o método. Não relistar canais. Não redefinir atenção.",
        },
        {
            "layout": "cards",
            "kicker": "Quatro quebras",
            "title": "Falha de unidade de valor no briefing. Não é opinião de criativo.",
            "cards": [
                _card("Recorte sem volume", "Segmentação precisa no papel, ruído na entrega.", "First-wave sem n não autoriza escala."),
                _card("Estático no short-form", "TikTok e Reels não pagam banner.", "Se o asset é 1:1, a família social já perdeu."),
                _card("Formato copiado", "Takeover não vira bumper. Playable não vira display.", "O Lucas detalha o mecanismo."),
                _card("Vaidade no lugar de first-wave", "Alcance, likes, viewability sozinha.", "A moeda da abertura não estava no KPI."),
            ],
        },
        {
            "layout": "list",
            "kicker": "Método",
            "title": "First-wave por formato. Depois escala.",
            "lines": [
                "Atenção ou AU no ambiente de sessão.",
                "VTR no vídeo.",
                "CTR qualificado no editorial.",
                "CPA de teste na utilidade.",
                "Presença no recorte no Places.",
            ],
            "footnote": "O Cadu já deixou o loop escrito. Esta sessão torna o loop obrigatório.",
        },
        {
            "layout": "statement",
            "kicker": "Fecho",
            "title": "Sem first-wave, a banca zera o grupo — mesmo com mix bonito.",
        },
    ]


def _interativos():
    return [
        {
            "layout": "title",
            "kicker": "Sessão 7 · 11:20–11:35",
            "title": "O gesto prova a first-wave",
            "lede": "O mecanismo obriga o gesto. Não é novidade.",
            "meta": "Lucas Facchini",
        },
        {
            "layout": "statement",
            "kicker": "Pergunta da sala",
            "title": "Este brief paga o interativo — ou um display viewable resolve a first-wave?",
            "note": "A sala já conhece playable e shoppable. Mostrar o gesto e o que ele autoriza.",
        },
        {
            "layout": "cards",
            "kicker": "Quatro gestos, quatro KPIs",
            "title": "Não agrupem tudo como “interativo” no mix.",
            "cards": [
                _card("Toque", "Prova interrupção.", "First-wave de corte"),
                _card("Escolha", "Prova consideração.", "First-wave de decisão"),
                _card("Playable", "Prova tempo de sessão.", "First-wave de dwell"),
                _card("Shoppable", "Prova intenção de SKU.", "First-wave de SKU"),
            ],
        },
        {
            "layout": "split",
            "kicker": "Quando entra",
            "title": "Autoriza first-wave que o display viewable não autoriza.",
            "left": {
                "title": "Quando é caro demais",
                "lines": [
                    "Verba de teste abaixo do floor",
                    "Criativo sem estado",
                    "Brief de CPA cego",
                ],
            },
            "right": {
                "title": "Quando é o único jeito",
                "lines": [
                    "Precisa provar atenção sem currency visual",
                    "O gesto faz parte da oferta",
                    "Não autoriza branding de 30 dias com uma peça",
                ],
            },
        },
    ]


def _programatica():
    return [
        {
            "layout": "title",
            "kicker": "Sessão 8 · 11:35–11:50",
            "title": "Aberto não é qualquer impressão",
            "lede": "Agrupar ~30 formatos. Aberto não é qualquer impressão.",
            "meta": "Lucas Facchini",
        },
        {
            "layout": "statement",
            "kicker": "Pergunta da sala",
            "title": "Portal ou feed — qual inventário autoriza o KPI da primeira onda?",
            "note": "Sem 30 slides iguais. Sem MRC 101. Sem relistar os 16 logos.",
        },
        {
            "layout": "cards",
            "kicker": "Famílias de formato",
            "title": "O que a família prova na primeira onda não é o que ela prova depois.",
            "cards": [
                _card("Display de impacto", "Takeover, billboard. Prova contexto.", "Viewability + adjacência"),
                _card("Vídeo curto", "Prova interrupção.", "VTR / atenção"),
                _card("Sessão / CTV", "Prova dwell.", "Completion / attentive seconds"),
                _card("Áudio", "Prova hábito.", "Completion 15s/30s"),
                _card("Interativo", "Prova gesto.", "Interação qualificada"),
                _card("Native / editorial", "Prova leitura.", "Tempo na peça, não clique vão"),
            ],
        },
        {
            "layout": "split",
            "kicker": "Programática",
            "title": "Deal, qualidade, contexto. CPM barato devolve a saturação.",
            "left": {
                "title": "Portal",
                "lines": [
                    "Ganha em construção e adjacência",
                    "Brand safety é o produto",
                    "Mesma regra de substituição da sessão 2",
                ],
            },
            "right": {
                "title": "Feed",
                "lines": [
                    "Ganha em volume e recorte",
                    "Sem adjacência, o barato devolve 9h09 de tela",
                    "Zero unidade de valor",
                ],
            },
        },
        {
            "layout": "statement",
            "kicker": "Fecho",
            "title": "Escala sem first-wave é a quebra do Max.",
        },
    ]


def _dinamica():
    return [
        {
            "layout": "title",
            "kicker": "Sessão 9 · 11:50–12:30",
            "title": "Banca: moeda, família, first-wave",
            "lede": "20 minutos para montar. 20 para bancar.",
            "meta": "Time",
        },
        {
            "layout": "statement",
            "kicker": "Pergunta da banca",
            "title": "Qual unidade de valor autoriza este percentual de verba?",
            "note": "Não dar aula. Sem inventar UU. Zerar grupo que não escrever a moeda.",
        },
        {
            "layout": "list",
            "kicker": "O envelope",
            "title": "Não é escolher três canais.",
            "lines": [
                "Famílias e % de verba — com regra de substituição.",
                "Formato e recorte.",
                "Unidade de valor da primeira onda.",
                "KPI que autoriza escala.",
                "Risco: brand safety, canibalização com mídia do app, frequência, cerca versus presença.",
            ],
        },
        {
            "layout": "brief",
            "kicker": "Briefing A",
            "title": "Fintech de conta digital",
            "amount": "R$ 80 mil",
            "lede": "Aquisição de conta com cartão na Grande São Paulo, 30 dias. Público 25–40, renda C+/B.",
            "lines": [
                "Sem performance cega em open web sem brand safety.",
                "KPI do cliente: CPA de conta aberta e qualidade do primeiro depósito.",
                "A banca cobra a moeda da first-wave — não o CPA final.",
                "Serasa/editorial entra? Places (Congonhas) faz sentido ou é vaidade?",
            ],
        },
        {
            "layout": "brief",
            "kicker": "Briefing B",
            "title": "Beleza D2C",
            "amount": "R$ 250 mil",
            "lede": "Lançamento de skincare, 45 dias, Sudeste. Branding curto + conversão no e-commerce próprio.",
            "lines": [
                "Mulheres 22–35. KPI: VTR/atenção no topo e ROAS na base.",
                "Qual família de sessão paga o topo?",
                "O que sai do short-form se o asset for estático?",
                "First-wave antes do ROAS.",
            ],
        },
        {
            "layout": "brief",
            "kicker": "Briefing C",
            "title": "Rede de food",
            "amount": "R$ 800 mil",
            "lede": "Brand nacional + incremento de pedidos em app, 60 dias. Coexistir com mídia própria do marketplace e com TV/portal.",
            "lines": [
                "KPI do cliente: ad recall e ticket incremental.",
                "Canibalização iFood.",
                "DOOH/Places entra como família ou como enfeite?",
                "Unidade de valor do incremento.",
            ],
        },
        {
            "layout": "list",
            "kicker": "Rubrica",
            "title": "Cinco linhas. Sem inventar UU.",
            "lines": [
                "Moeda da abertura escrita no plano.",
                "Substituição entre famílias — incluindo Places, se couber.",
                "First-wave distinta de escala.",
                "Restrição do brief respeitada.",
                "Risco nomeado.",
            ],
        },
    ]


BUILDERS = {
    "atencao-mercado": _atencao,
    "mapa-canais": _canais,
    "dooh-places": _places,
    "ia-cadu": _cadu,
    "coffee": _coffee,
    "max-formatos": _max,
    "lucas-interativos": _interativos,
    "lucas-programatica": _programatica,
    "dinamica-planos": _dinamica,
}


def session_deck(slug):
    builder = BUILDERS.get(slug)
    if builder is None:
        raise KeyError(slug)
    return _deck(slug, builder())


def session_index():
    return [
        {
            "slug": item["slug"],
            "titulo": item["titulo"],
            "horario": f"{item['horario_inicio']}–{item['horario_fim']}",
            "facilitadores": list(item.get("facilitadores") or []),
            "tipo": item.get("tipo") or "bloco",
        }
        for item in SESSIONS
    ]


def morning_deck():
    slides = [
        {
            "layout": "title",
            "kicker": "Imersão em Mídias Complexas · 28 de setembro",
            "title": "Pessoas · Mídia · Resultados",
            "lede": "9h30–12h30. Mesa de especialistas. A unidade de valor vem antes do canal.",
            "meta": "MediaHacks Training · Centralcomm",
        },
        {
            "layout": "agenda",
            "kicker": "A manhã",
            "title": "Nove blocos. Uma rubrica.",
            "lines": session_index(),
        },
    ]
    for item in SESSIONS:
        deck = session_deck(item["slug"])
        body = list(deck["slides"])
        if item["tipo"] != "intervalo":
            slides.append(
                {
                    "layout": "section",
                    "kicker": deck["horario"],
                    "title": deck["titulo"],
                    "lede": " · ".join(deck["facilitadores"]) or "Intervalo",
                    "slug": item["slug"],
                }
            )
            if body and body[0].get("layout") == "title":
                body = body[1:]
        slides.extend(body)
    return {
        "slug": "manha",
        "titulo": "Imersão em Mídias Complexas",
        "horario": "09:30–12:30",
        "facilitadores": [],
        "tipo": "manha",
        "slides": slides,
    }


SESSION_DECKS = {slug: builder for slug, builder in BUILDERS.items()}
