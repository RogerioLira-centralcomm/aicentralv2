"""Build a non-destructive, auditable taxonomy draft from the CADU export.

The output is intentionally a proposal. Low-confidence records must be curated
before any database migration.
"""

from __future__ import annotations

import ast
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tmp" / "audience_catalog_analysis" / "audiences.csv"
OUT_DIR = ROOT / "output" / "audience-taxonomy-review"


def plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"\s+", " ", value).strip()


def canonical_display_name(value: str) -> str:
    """Remove import/vendor noise while preserving the audience meaning.

    The raw provider label remains in ``cadu_audiencias.nome`` and the
    provider relationship. This value is only the curated display name.
    """
    name = re.sub(r"\s+", " ", (value or "")).strip()
    provider_parenthetical = (
        r"\s*\((?:dados?(?: provenientes)?|segmento taxo|perfil|"
        r"aud[ií]ncia especial)?\s*"
        r"(?:serasa(?: experian)?|boa vista(?: servi[cç]os)?(?: scpc)?|"
        r"kantar(?: ibope)?|ibope|navegg|predicta|acxiom(?: mobile)?|"
        r"liveramp(?: mix)?|xandr|mosaic(?: business)?|hpe|rankmyapp|"
        r"catraca livre)(?:[^)]*)\)"
    )
    name = re.sub(provider_parenthetical, "", name, flags=re.I)
    provider_name = (
        r"(?:serasa(?: experian)?|boa vista(?: servi[cç]os)?(?: scpc)?|"
        r"kantar(?: ibope)?|ibope|navegg|predicta|acxiom(?: mobile)?|"
        r"liveramp(?: mix)?|xandr|mosaic(?: business)?|hpe|rankmyapp|catraca livre)"
    )
    name = re.sub(rf"[,.]?\s*com valida[cç][aã]o da\s+{provider_name}.*$", "", name, flags=re.I)
    name = re.sub(rf",?\s*baseados? em [^,]+,\s*usu[aá]rios da\s+{provider_name}.*$", "", name, flags=re.I)
    name = re.sub(rf",?\s*usu[aá]rios da\s+{provider_name}.*$", "", name, flags=re.I)
    name = re.sub(
        r"[,.]?\s*(?:com base em|baseados? em|utilizando|conforme|fornecidos? por|"
        r"provenientes? de)\s+dados?(?: demogr[aá]ficos)?\s+(?:da?|do)\s+"
        r"(?:serasa(?: experian)?|boa vista(?: servi[cç]os)?(?: scpc)?|kantar(?: ibope)?|ibope|acxiom(?: mobile)?|catraca livre)[^.]*\.?$",
        "",
        name,
        flags=re.I,
    )
    name = re.sub(r"\s*-\s*Dados?\s+(?:Serasa(?: Experian)?|Kantar(?: IBOPE)?|IBOPE).*$", "", name, flags=re.I)
    name = re.sub(r"^Audi[eê]ncias? Especiais?\s+(?:Navegg\s*-\s*)?", "", name, flags=re.I)
    name = re.sub(r"^Audi[eê]ncia Especial\s+(?:da\s+)?Navegg\s+interessada em\s+", "", name, flags=re.I)
    name = re.sub(r"^Audi[eê]ncia Especial de\s+", "", name, flags=re.I)
    name = re.sub(r"^Audi[eê]ncia Especial\s+RankMyApp/Banco ABC\s+focada em\s+", "", name, flags=re.I)
    name = re.sub(r"^P[uú]blico-alvo\s+Navegg\s+no mercado de\s+Sa[uú]de,?\s*interessado em\s+", "", name, flags=re.I)
    name = re.sub(r"^P[uú]blico-alvo\s+Navegg\s+no mercado de\s+", "", name, flags=re.I)
    name = re.sub(r"^P[uú]blico Persona de\s+", "", name, flags=re.I)
    name = re.sub(r"^P[uú]blico\s+Serasa:\s*", "", name, flags=re.I)
    name = re.sub(r"^P[uú]blico\s+Mosaic\s+Brasil\s*\([A-Z]\d+\)\s*-\s*", "", name, flags=re.I)
    name = re.sub(r"\(Base\s+Serasa/CBO\)", "(CBO)", name, flags=re.I)
    name = re.sub(r"\s*-\s*Kantar\s+IBOPE$", "", name, flags=re.I)
    name = re.sub(r"\s+baseado em dados\s+Kantar\s+IBOPE.*$", "", name, flags=re.I)
    name = re.sub(r"[, ]*com foco em conte[uú]do do\s+Catraca Livre.*$", "", name, flags=re.I)
    name = re.sub(r"[, ]*baseado em dados do parceiro\s+Catraca Livre.*$", "", name, flags=re.I)
    name = re.sub(r"\bSerasa(?: Experian)?\b", "", name, flags=re.I)
    name = re.sub(r"\bBoa Vista(?: Servi[cç]os)?(?: SCPC)?\b", "", name, flags=re.I)
    name = re.sub(r"\b(?:Kantar(?: IBOPE)?|IBOPE|Navegg|Predicta|Acxiom(?: Mobile)?|LiveRamp(?: Mix)?|Xandr)\b", "", name, flags=re.I)
    name = re.sub(r"(?:\s*\([^)]*\b(?:Mosaic|HPE|RankMyApp)[^)]*\))", "", name, flags=re.I)
    name = re.sub(r"(?:,?\s*(?:com valida[cç][aã]o da|com dados demogr[aá]ficos fornecidos pela|perfil socioecon[oô]mico espec[ií]fico da|dados provenientes da|baseados? em dados da|utilizando dados da))\s*$", "", name, flags=re.I)
    name = re.sub(r"[, ]*com perfil socioecon[oô]mico espec[ií]fico da\s*$", "", name, flags=re.I)
    name = re.sub(r"\s+com$", "", name, flags=re.I)
    name = re.sub(r"\(Base\s*/CBO\)", "(CBO)", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip(" -,. ")
    name = re.sub(r"\b(\d{2})\s+a\s+(\d{2})\s+anos\b", r"\1–\2 anos", name, flags=re.I)
    return name or value.strip()


def parse_array(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = ast.literal_eval(value)
        return [str(item) for item in parsed] if isinstance(parsed, (list, tuple)) else []
    except (ValueError, SyntaxError):
        return []


MARKETS: list[tuple[str, list[str]]] = [
    ("Imobiliário & Construção", [
        r"imove", r"imobili", r"habitacao", r"home.build", r"casa nova",
        r"construcao", r"construtor", r"reforma", r"materiais de construcao", r"arquitet",
        r"decoracao", r"urbanismo", r"condominio", r"obras? de infraestrutura",
        r"pintura e acabamento",
    ]),
    ("Finanças & Seguros", [
        r"financ", r"banc", r"credito", r"emprestim", r"cartao", r"pagamento",
        r"invest", r"acoes", r"renda fixa", r"tesouro", r"fundo", r"cripto",
        r"seguro", r"previdencia", r"fintech", r"copom", r"forex", r"cambio",
        r"trader", r"bolsa", r"score", r"adimpl", r"patrimonio",
    ]),
    ("Varejo & Consumo", [
        r"varejo", r"e.?commerce", r"comprador", r"compra online", r"loja",
        r"shopping", r"moda", r"vestuario", r"calcado", r"acessorio",
        r"eletron", r"eletrodom", r"smartphone", r"alimento", r"bebida", r"gastronom",
        r"food", r"restaurante", r"delivery", r"supermercado", r"pet",
        r"cerveja", r"vinho", r"vodka", r"whisk", r"cachaca", r"aguardente", r"drink",
        r"cachorro", r"gato", r"cosmetic", r"promoc", r"oferta", r"black friday",
        r"padaria", r"confeitaria", r"joalher", r"otica",
    ]),
    ("Serviços ao Consumidor", [
        r"advoca", r"juridic", r"contabil", r"servicos residenciais",
        r"servicos profissionais", r"servicos locais", r"telecom", r"telefonia",
        r"internet banda", r"assinatura", r"servico digital", r"delivery de servico",
        r"turismo", r"viage", r"ferias", r"voo", r"aereo", r"destino", r"hotel", r"pousada",
        r"hospitalidade",
    ]),
    ("Automotivo, Mobilidade & Logística", [
        r"automot", r"carro", r"veiculo", r"sedan", r"suv", r"hatch", r"pick.?up",
        r"minivan", r"moto", r"motorista", r"mobilidade", r"transporte", r"logistic",
        r"armazen", r"correio", r"courier", r"carga", r"3pl", r"4pl", r"posto de combust",
        r"postos de combust", r"oficinas? mecan",
    ]),
    ("Agronegócio", [
        r"agroneg", r"\bagro\b", r"agric", r"rurais?", r"pecuaria", r"pecuarista", r"fertiliz",
        r"insumo", r"produtor rural", r"produtores? de (grao|cafe|cana)", r"veterinaria", r"maquinas agr",
    ]),
    ("Saúde, Bem-estar & Beleza", [
        r"saude", r"medic", r"hospit", r"clinica", r"odont", r"farmac", r"drogaria",
        r"fitness", r"bem.estar", r"nutricao", r"dieta", r"beleza", r"skincare",
        r"maquiagem", r"higiene", r"maternidade", r"bebe", r"personal trainer",
    ]),
    ("Educação & Carreira", [
        r"educa", r"ensino", r"escola", r"estud", r"univers", r"academico",
        r"graduacao", r"pos.gradu", r"\bcursos?\b", r"idioma", r"vestibular", r"concurso",
        r"carreira", r"emprego", r"pedagog",
    ]),
    ("Entretenimento, Conteúdo & Esportes", [
        r"entreten", r"esporte", r"futebol", r"copa", r"olimpi", r"game", r"jogo",
        r"cinema", r"filme", r"serie", r"streaming", r"musica", r"show", r"noticia",
        r"politica", r"cultura", r"novela", r"comedia", r"drama", r"romance",
        r"acao", r"suspense", r"terror", r"reality", r"infantil",
    ]),
    ("B2B, Enterprise & Indústria", [
        r"\bb2b\b", r"empresa", r"empresari", r"empreendedor", r"socio", r"executiv",
        r"c.level", r"diretor", r"gestor", r"coordenador", r"decisor", r"profission",
        r"recursos humanos", r"\brh\b", r"industr", r"manufatura", r"atacad",
        r"distribuidor", r"startup", r"microempresa", r"pequenas empresas",
        r"medias empresas", r"grandes empresas", r"mosaic business", r"enterprise",
        r"setor publico", r"utilit", r"energia", r"software", r"consultoria em ti",
        r"data center", r"marketing digital", r"tecnologia", r"suporte tecnico ti",
    ]),
]


SUBMARKETS: dict[str, list[tuple[str, list[str]]]] = {
    "Imobiliário & Construção": [
        ("Compra e lançamentos", [r"compr", r"casa nova", r"lancamento"]),
        ("Aluguel", [r"alug", r"inquilin"]),
        ("Investimento imobiliário", [r"invest", r"leilao"]),
        ("Construção, reforma e materiais", [r"construcao", r"reforma", r"material", r"acabamento", r"obra"]),
        ("Arquitetura, decoração e urbanismo", [r"arquitet", r"decoracao", r"urbanismo"]),
        ("Empresas e profissionais imobiliários", [r"empresa", r"socio", r"profission", r"imobiliaria"]),
    ],
    "Finanças & Seguros": [
        ("Investimentos e patrimônio", [r"invest", r"acoes", r"renda fixa", r"tesouro", r"fundo", r"cripto", r"trader", r"patrimonio"]),
        ("Crédito e empréstimos", [r"credito", r"emprestim", r"financiamento"]),
        ("Cartões e pagamentos", [r"cartao", r"pagamento"]),
        ("Seguros e previdência", [r"seguro", r"previdencia"]),
        ("Bancos e fintechs", [r"banc", r"fintech", r"conta digital"]),
        ("Perfil e saúde financeira", [r"score", r"adimpl", r"renda", r"bom pagador", r"recuperacao"]),
        ("Educação e conteúdo financeiro", [r"educacao", r"economia", r"copom", r"morning call"]),
    ],
    "Varejo & Consumo": [
        ("Compradores e e-commerce", [r"comprador", r"e.?commerce", r"compra online", r"marketplace"]),
        ("Moda, beleza e acessórios", [r"moda", r"vestuario", r"calcado", r"acessorio", r"cosmetic", r"joalher", r"otica"]),
        ("Eletrônicos e eletrodomésticos", [r"eletron", r"eletrodom", r"smartphone"]),
        ("Casa, móveis e decoração", [r"casa", r"moveis", r"decoracao"]),
        ("Alimentos, bebidas e gastronomia", [r"alimento", r"bebida", r"cerveja", r"vinho", r"whisk", r"vodka", r"cachaca", r"food", r"gastronom", r"restaurante", r"padaria"]),
        ("Supermercados e delivery", [r"supermerc", r"delivery"]),
        ("Pets", [r"pet", r"cachorro", r"gato", r"animais de estimacao"]),
        ("Ofertas e sazonalidades", [r"oferta", r"promoc", r"black friday", r"prime day"]),
    ],
    "Serviços ao Consumidor": [
        ("Turismo e hospitalidade", [r"turismo", r"viage", r"ferias", r"hotel", r"pousada", r"voo"]),
        ("Jurídico e contabilidade", [r"jurid", r"advoca", r"contabil"]),
        ("Telecom e conectividade", [r"telecom", r"telefonia", r"internet"]),
        ("Serviços profissionais e locais", [r"servico", r"profissional", r"local"]),
    ],
    "B2B, Enterprise & Indústria": [
        ("Liderança e decisores", [r"c.level", r"executiv", r"diretor", r"decisor", r"socio"]),
        ("Funções corporativas", [r"recursos humanos", r"\brh\b", r"marketing", r"vendas", r"\bti\b", r"operacoes", r"financas"]),
        ("PMEs e empreendedores", [r"microempresa", r"pequena", r"media empresa", r"empreendedor"]),
        ("Enterprise e grandes empresas", [r"grande", r"enterprise", r"consolidada", r"influencia"]),
        ("Indústria e manufatura", [r"industr", r"manufatura"]),
        ("Tecnologia B2B", [r"software", r"consultoria em ti", r"data center", r"tecnologia"]),
        ("Atacado e distribuição", [r"atacad", r"distribui"]),
        ("Setor público e utilities", [r"setor publico", r"utilit", r"energia", r"agua"]),
    ],
    "Automotivo, Mobilidade & Logística": [
        ("Compra e troca de veículos", [r"compra", r"trocar", r"intencao"]),
        ("Categorias de veículos", [r"sedan", r"suv", r"hatch", r"pick.?up", r"minivan", r"moto"]),
        ("Serviços automotivos", [r"manutencao", r"posto", r"combustivel"]),
        ("Mobilidade urbana e aplicativos", [r"motorista", r"aplicativo", r"mobilidade urbana", r"passageiro"]),
        ("Logística e transporte de cargas", [r"logistic", r"transporte", r"carga", r"courier", r"armazen", r"3pl", r"4pl"]),
    ],
    "Agronegócio": [
        ("Produtores rurais", [r"produtor", r"agricult"]),
        ("Pecuária", [r"pecuaria", r"pecuarista"]),
        ("Insumos e fertilizantes", [r"insumo", r"fertiliz"]),
        ("Máquinas e equipamentos", [r"maquina", r"equipamento"]),
        ("Veterinária e saúde animal", [r"veterin"]),
        ("Agroindústria", [r"agroindustr"]),
    ],
    "Saúde, Bem-estar & Beleza": [
        ("Saúde e prevenção", [r"saude", r"prevenc"]),
        ("Planos de saúde", [r"plano", r"seguro saude"]),
        ("Profissionais e empresas de saúde", [r"profission", r"empresa", r"clinica", r"hospital", r"odont"]),
        ("Fitness e esporte praticado", [r"fitness", r"personal", r"pratic"]),
        ("Nutrição e alimentação saudável", [r"nutri", r"dieta", r"alimentacao saudavel"]),
        ("Beleza e cosméticos", [r"beleza", r"cosmetic", r"skincare", r"maquiagem"]),
        ("Maternidade e cuidados infantis", [r"matern", r"bebe", r"infantil"]),
        ("Produtos e equipamentos médicos", [r"utensilio", r"equipamento", r"produto medic"]),
    ],
    "Educação & Carreira": [
        ("Ensino básico e famílias", [r"ensino medio", r"escola", r"pais de estudante"]),
        ("Graduação e pós-graduação", [r"graduacao", r"pos", r"univers"]),
        ("Cursos e formação profissional", [r"\bcursos?\b", r"profissionalizante"]),
        ("Idiomas", [r"idioma", r"lingua estrangeira"]),
        ("Pré-vestibular e concursos", [r"vestibular", r"concurso", r"preparator"]),
        ("Carreira e emprego", [r"carreira", r"emprego"]),
    ],
    "Entretenimento, Conteúdo & Esportes": [
        ("Esportes e futebol", [r"esporte", r"futebol", r"copa", r"olimpi", r"nba", r"mma"]),
        ("Games", [r"game", r"jogo", r"playstation", r"xbox", r"nintendo"]),
        ("Cinema, séries e gêneros", [r"cinema", r"filme", r"serie", r"acao", r"comedia", r"drama", r"romance", r"suspense", r"terror", r"anime"]),
        ("Música e shows", [r"musica", r"show", r"rock", r"pop", r"funk", r"jazz", r"sertanejo", r"samba", r"pagode"]),
        ("Notícias e atualidades", [r"noticia", r"politica", r"mundo", r"internacional", r"news"]),
        ("Conteúdo infantil e familiar", [r"infantil", r"familia"]),
    ],
}


ROLE_RULES: list[tuple[str, list[str]]] = [
    ("inválido/quarentena", [r"unknown", r"sem.nome", r"audiencia desconhecida"]),
    ("tática de ativação", [
        r"retarget", r"remarket", r"lookalike", r"crm match", r"crm onboard",
        r"first.party", r"1st.party", r"keywords? context", r"brand safety",
    ]),
    ("formato/inventário", [
        r"video pre.roll", r"pre.roll", r"mid.roll", r"display", r"native ads?",
        r"branded content", r"pmp", r"programmatic guaranteed", r"takeover",
        r"daypart", r"horario nobre", r"grade manha", r"ao vivo", r"breaking news",
        r"amp pages?", r"mobile$", r"desktop$", r"tablet$", r"smart tv", r"ctv",
    ]),
    ("perfil transversal", [
        r"^mulheres?( geral| serasa| prime video)?$", r"^homens?( geral| serasa| prime video)?$",
        r"^\d{2}.?\d{2}( anos)?$", r"^\d{2}\+$", r"^jovens adultos( \(18.24\))?$",
        r"^adultos jovens( \(25.34\))?$", r"^adultos estabelecidos( \(35.44\))?$",
        r"^seniores?( \d+\+)?$", r"^geracao z$", r"^gen z( .*)?$", r"^millennials?( .*)?$",
        r"^classe [abcde].*$", r"^alta renda.*$", r"^media.*renda.*$", r"^baixa renda.*$",
        r"^renda familiar.*$", r"^familias? com filhos$", r"^pais e maes.*$",
        r"^aniversariantes?.*$", r"^estado civil.*$", r"^publico geral$",
        r"^pessoas de \d{2} a \d{2} anos.*$", r"^publico no brasil com renda familiar.*$",
        r"^publico demografico.*$", r"^familias? de classe.*$", r"^publico de alto poder aquisitivo.*$",
        r"^publico maduro.*alto padrao.*$", r"^meia idade e senior.*$",
        r"^pessoas com mais de \d+ anos.*$",
        r"^publico mosaic brasil.*$",
    ]),
    ("contexto/afinidade de conteúdo", [
        r"fas? de ", r"leitores?", r"readers?", r"viewers?", r"espectadores?",
        r"ouvintes?", r"conteudo", r"editorial", r"vertical", r"newsletter",
        r"podcast", r"webinar", r"programa de tv", r"genero musical",
    ]),
]


SIGNAL_RULES: list[tuple[str, list[str]]] = [
    ("intenção de compra", [r"intencao", r"in.market", r"jornada de compra", r"buscando", r"planejando"]),
    ("compra/consumo observado", [r"compradores?", r"compra frequente", r"consumidores?", r"usuarios? de aplicativo"]),
    ("visitação/localização", [r"visitantes?", r"visitacao", r"ponto de interesse", r"\bpoi\b", r"frequenta"]),
    ("cargo/função profissional", [r"profission", r"executiv", r"diretor", r"gestor", r"coordenador", r"c.level", r"decisor"]),
    ("empresa/firmográfico", [r"empresa", r"industr", r"microempresa", r"startup", r"mosaic business", r"socio"]),
    ("demográfico/socioeconômico", [r"mulher", r"homem", r"anos", r"idade", r"renda", r"classe ", r"familia", r"geracao", r"gen z"]),
    ("contextual/editorial", [r"keyword", r"context", r"noticia", r"editorial", r"brand safety"]),
    ("dados próprios/CRM", [r"crm", r"first.party", r"1st.party"]),
    ("modelado/lookalike", [r"lookalike", r"semelhante", r"modelad"]),
    ("retargeting", [r"retarget", r"remarket"]),
    ("interesse/afinidade", [r"interess", r"afinidade", r"fas? de", r"entusiasta", r"amantes?"]),
    ("consumo de conteúdo", [r"leitor", r"reader", r"viewer", r"espectador", r"ouvinte", r"assist", r"conteudo"]),
]


def matching(text: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    return [label for label, patterns in rules if any(re.search(p, text) for p in patterns)]


def business_scope(text: str) -> str:
    b2b = bool(re.search(
        r"\bb2b\b|empresa|empresari|empreendedor|socio|c.level|executiv|diretor|gestor|decisor|"
        r"profission|industr|atacad|distribui|microempresa|startup|enterprise|mosaic business",
        text,
    ))
    b2c = bool(re.search(
        r"consumidor|comprador|pessoas|familia|mulher|homem|jovem|adulto|fas? de|"
        r"interessados?|intencao de compra|visitantes?|ouvintes?|espectadores?",
        text,
    ))
    if b2b and b2c:
        return "Híbrido"
    if b2b:
        return "B2B"
    return "B2C" if b2c else "Transversal/indefinido"


def funnel_stages(signals: list[str], role: str) -> list[str]:
    stages: list[str] = []
    if any(s in signals for s in ("contextual/editorial", "consumo de conteúdo", "interesse/afinidade")):
        stages.extend(["Conhecimento", "Consideração"])
    if any(s in signals for s in ("intenção de compra", "compra/consumo observado", "visitação/localização")):
        stages.extend(["Consideração", "Conversão"])
    if "dados próprios/CRM" in signals:
        stages.append("Fidelização/base própria")
    if "retargeting" in signals:
        stages.append("Reengajamento")
    if not stages and role in {"perfil transversal", "formato/inventário"}:
        stages.append("Conhecimento")
    return list(dict.fromkeys(stages))


def classify(row: dict[str, str], duplicated_names: set[str]) -> dict[str, str]:
    name_text = plain(row.get("nome", ""))
    subcategory_text = plain(row.get("subcategoria", ""))
    taxonomy_text = plain(" ".join([row.get("nome", ""), row.get("subcategoria", "")]))
    role_hits = matching(name_text, ROLE_RULES)
    role = role_hits[0] if role_hits else "conceito de audiência"
    if (
        not role_hits
        and (row.get("plataforma") or row.get("fonte"))
        in {"G1 / Globo.com", "Prime Video", "CNN Brasil", "Netflix", "SBT", "InfoMoney", "Spotify Ads"}
    ):
        role = "contexto/afinidade de conteúdo"

    # The name is stronger evidence than the broken legacy subcategory. The
    # latter is only a fallback when the name itself carries no vertical cue.
    name_market_hits = matching(name_text, MARKETS)
    # When a named vertical coexists with a financial or corporate reference
    # (e.g. "Banco ABC focada em Agronegócio"), the named vertical is the
    # planner's primary entry point; the other market remains related.
    for specific_market in (
        "Agronegócio",
        "Automotivo, Mobilidade & Logística",
        "Imobiliário & Construção",
    ):
        if specific_market in name_market_hits:
            name_market_hits.remove(specific_market)
            name_market_hits.insert(0, specific_market)
    if (
        "B2B, Enterprise & Indústria" in name_market_hits
        and "Educação & Carreira" in name_market_hits
        and not re.search(r"educa|ensino|escola|estud|univers|academico|graduacao|\bcursos?\b|idioma|vestibular|concurso|pedagog", name_text)
    ):
        name_market_hits.remove("B2B, Enterprise & Indústria")
        name_market_hits.insert(0, "B2B, Enterprise & Indústria")
    market_hits = name_market_hits
    used_legacy_subcategory = False
    if not market_hits:
        market_hits = matching(subcategory_text, MARKETS)
        used_legacy_subcategory = bool(market_hits)
    signals = matching(name_text, SIGNAL_RULES)

    is_cross_market = role in {"tática de ativação", "formato/inventário", "perfil transversal"} or (
        role == "contexto/afinidade de conteúdo" and not market_hits
    )
    primary_market = "" if is_cross_market else (market_hits[0] if market_hits else "")
    related_markets = market_hits if is_cross_market else market_hits[1:]
    submarket = ""
    if primary_market:
        submarket_hits = matching(name_text, SUBMARKETS.get(primary_market, []))
        submarket = submarket_hits[0] if submarket_hits else "Outros / revisar"
    stages = funnel_stages(signals, role)

    if role == "inválido/quarentena":
        confidence = "alta"
        action = "quarentenar"
    elif plain(row.get("nome", "")) in duplicated_names:
        confidence = "média" if market_hits or is_cross_market else "baixa"
        action = "avaliar consolidação conceitual"
    elif is_cross_market:
        confidence = "alta" if role != "contexto/afinidade de conteúdo" else "média"
        action = "mapear"
    elif primary_market:
        confidence = "média" if (
            used_legacy_subcategory or len(name_market_hits) > 1 or submarket == "Outros / revisar"
        ) else "alta"
        action = "mapear"
    else:
        confidence = "baixa"
        action = "revisão editorial obrigatória"

    return {
        "id": row["id"],
        "nome_original": row["nome"],
        "nome_canonico_proposto": canonical_display_name(row["nome"]),
        "nome_normalizado_chave": plain(row["nome"]),
        "plataforma": row.get("plataforma") or row.get("fonte", ""),
        "categoria_atual": row.get("categoria", ""),
        "subcategoria_atual": row.get("subcategoria", ""),
        "papel_catalogo_proposto": role,
        "escopo_mercado": "transversal" if is_cross_market else "vertical",
        "mercado_principal_proposto": primary_market,
        "submercado_proposto": submarket,
        "mercados_relacionados_propostos": " | ".join(related_markets),
        "orientacao_b2b_b2c": business_scope(name_text),
        "tipos_sinal_propostos": " | ".join(signals),
        "estagios_funil_propostos": " | ".join(stages),
        "confianca_regra": confidence,
        "acao_migracao": action,
    }


def main() -> None:
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8")))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    duplicate_counts = Counter(plain(r["nome"]) for r in rows)
    duplicates = {name for name, count in duplicate_counts.items() if name and count > 1}
    mapped = [classify(row, duplicates) for row in rows]
    fields = list(mapped[0])
    output_csv = OUT_DIR / "taxonomy_draft.csv"
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(mapped)

    summary = {
        "total": len(mapped),
        "roles": Counter(r["papel_catalogo_proposto"] for r in mapped),
        "market_scope": Counter(r["escopo_mercado"] for r in mapped),
        "primary_markets": Counter(r["mercado_principal_proposto"] or "SEM MERCADO" for r in mapped),
        "confidence": Counter(r["confianca_regra"] for r in mapped),
        "migration_actions": Counter(r["acao_migracao"] for r in mapped),
        "mandatory_review_ids": [r["id"] for r in mapped if r["confianca_regra"] == "baixa"],
    }
    output_json = OUT_DIR / "taxonomy_draft_summary.json"
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
