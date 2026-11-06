"""Estratégias de mídia: vocabulário, canais e divisão de verba por faixa.

Uma estratégia combina pelo menos dois canais pagos em um fluxo (alcance,
consideração, remarketing, conversão), diz que formatos e criativos precisa,
se exige link de conversão, como usa remarketing e lista de clientes e o que
será medido na operação. A verba é mostrada em R$ (exceção pedida pelo
usuário à regra de "sem preço" do Descobrir) e varia por faixa: em verbas
menores, canais com mínimo acima da sua fatia saem e voltam nas faixas
maiores.
"""

from __future__ import annotations

import re
import unicodedata

FAIXAS = (10_000, 20_000, 30_000, 50_000, 75_000, 100_000, 150_000)
ARREDONDA = 500  # valores por canal em múltiplos de R$ 500

OBJETIVOS = {
    "reconhecimento": "Reconhecimento de marca",
    "lancamento": "Lançamento",
    "consideracao": "Consideração e tráfego",
    "leads": "Geração de leads",
    "vendas-online": "Vendas online",
    "vendas-whatsapp": "Vendas no WhatsApp",
    "loja-fisica": "Visitas à loja",
    "app": "Instalações e uso de app",
    "retencao": "Retenção e recompra",
}

PAPEIS = ("Alcance", "Consideração", "Conversão", "Remarketing", "Dados")

DESTINOS = {
    "landing": "Landing page",
    "site": "Site ou e-commerce",
    "whatsapp": "WhatsApp",
    "formulario": "Formulário nativo",
    "app": "Loja de apps",
    "loja": "Loja física",
    "marketplace": "Marketplace",
}

FONTES_KPI = ("Plataforma", "GA4", "Pixel e API de conversões", "CRM", "Pesquisa de lift", "Painel Centralcomm")

# Canais que a mídia usa mas que não estão (ou não estão assim) no catálogo do Planner.
_G = "/static/images/canais/google-ads.png"
CANAIS_EXTRAS = {
    "google-search": {"nome": "Google Search", "logo": _G, "categoria": "Busca"},
    "google-pmax": {"nome": "Google Performance Max", "logo": _G, "categoria": "Busca"},
    "google-demand-gen": {"nome": "Google Demand Gen", "logo": _G, "categoria": "Busca"},
    "google-app": {"nome": "Google App Campaigns", "logo": _G, "categoria": "Busca"},
    "meta-ads": {"nome": "Meta (Facebook e Instagram)", "logo": "/static/images/canais/meta.svg", "categoria": "Sociais"},
}

# Nós do fluxo que não recebem verba: destinos e dados próprios do cliente.
NOS_FLUXO = {
    "landing": {"nome": "Landing page", "icone": "layout"},
    "site": {"nome": "Site / e-commerce", "icone": "globe"},
    "whatsapp": {"nome": "WhatsApp", "icone": "whatsapp", "logo": "/static/images/canais/whatsapp.svg"},
    "formulario": {"nome": "Formulário nativo", "icone": "file"},
    "app": {"nome": "App", "icone": "sparkles"},
    "loja": {"nome": "Loja física", "icone": "pin"},
    "crm": {"nome": "Lista de clientes", "icone": "users"},
    "marketplace": {"nome": "Marketplace", "icone": "tag"},
}

# Formatos e otimizações de partida por canal. O admin preenche a partir daqui
# ao incluir um canal; cada estratégia pode trocar.
PADRAO_CANAL = {
    "google-search": (["Search Ads (RSA)"], [
        "Marca, concorrentes e genéricos em campanhas separadas",
        "Lance por conversão (CPA ou ROAS desejado) depois de 30 conversões no mês",
        "Negativação semanal de termos de pesquisa",
        "Sitelinks, chamada, local e snippets em todos os grupos"]),
    "google-pmax": (["Performance Max"], [
        "Sinais de público com a lista de clientes e visitantes do site",
        "Feed do Merchant Center com títulos e imagens otimizados",
        "Exclusão de termos de marca para não canibalizar a busca",
        "Grupos de recursos por categoria de produto"]),
    "google-demand-gen": (["Demand Gen"], [
        "Público semelhante a partir da lista de clientes",
        "Imagens 1:1 e 4:5 com vídeo vertical no mesmo grupo",
        "Otimização para conversão com valor quando houver e-commerce"]),
    "google-app": (["App Campaigns"], [
        "Otimização para ação no app (cadastro, compra), não só instalação",
        "Firebase ou MMP integrado (AppsFlyer, Adjust)",
        "Grupos de recursos com vídeo vertical e HTML5"]),
    "meta-ads": (["Feed Ad (Vídeo)", "Stories & Reels", "Carousel Ads"], [
        "Pixel com API de Conversões (CAPI) e deduplicação de eventos",
        "Posicionamentos Advantage+ e público aberto com sinais",
        "3 a 5 criativos por conjunto, renovados a cada 2 ou 3 semanas",
        "Teste A/B de público semelhante contra público aberto"]),
    "youtube": (["YouTube In-Stream Skipável", "YouTube Bumper (6s)"], [
        "Sequência de anúncios: bumper de 6s abre, in-stream completa",
        "Frequência de 2 a 3 impressões por semana",
        "Segmentos personalizados por termos de busca e sites visitados"]),
    "tiktok": (["In-Feed Ads", "Spark Ads"], [
        "Criativo nativo com criadores, gancho nos primeiros 2 segundos",
        "Pixel com Events API",
        "Spark Ads em posts orgânicos que já performaram"]),
    "kwai": (["In-Feed (vídeo vertical)"], [
        "Criativo popular, direto, com legenda grande",
        "Otimização por clique no link ou conversa no WhatsApp"]),
    "linkedin": (["Lead Gen Form", "Single Image Ad", "Document Ad"], [
        "Segmentação por cargo, senioridade e tamanho de empresa",
        "Matched Audiences com a lista de contas-alvo (ABM)",
        "Formulário com no máximo 4 campos pré-preenchidos"]),
    "twitch": (["Pre-roll em live", "Patrocínio de canal"], [
        "Patrocínio de criadores do nicho com cupom próprio"]),
    "spotify": (["Audio Ad", "Video Takeover"], [
        "Segmentação por momento e playlist (treino, foco, trânsito)",
        "Companion banner clicável",
        "Frequência por usuário controlada"]),
    "deezer": (["Audio Ad"], ["Segmentação por gênero musical e momento"]),
    "amazon-music": (["Audio Ad"], ["Combinar com Amazon Ads para fechar o ciclo de compra"]),
    "podcast-ads": (["Podcast Ads"], [
        "Leitura pelo apresentador (host-read) com cupom exclusivo",
        "Inserção dinâmica por tema do episódio"]),
    "netflix": (["Pre-Roll Ad", "Mid-Roll Ad"], [
        "Frequência por domicílio controlada",
        "Medição de lift de busca da marca durante a veiculação",
        "QR code no fim do vídeo"]),
    "globoplay": (["Pre-roll", "Mid-roll"], ["Frequência por domicílio", "Segmentação por gênero de programa"]),
    "prime-video": (["Pre-Roll Ad", "Pause Ad"], ["Público de compradores Amazon", "Frequência por domicílio"]),
    "disney-plus": (["Pre-roll"], ["Frequência por domicílio"]),
    "hbo-max": (["Pre-roll"], ["Frequência por domicílio"]),
    "paramount-plus": (["Pre-roll"], ["Frequência por domicílio"]),
    "samsung-tv-plus": (["CTV Pre-Roll"], ["Segmentação por canal FAST e horário", "QR code na tela"]),
    "eletromidia": (["DOOH Billboard"], [
        "Programação por horário, dia e clima",
        "Telas perto dos pontos de venda",
        "Retargeting no celular de quem passou pelas telas"]),
    "uber": (["Journey Ads", "Post-Checkout"], [
        "Segmentação por destino da viagem (shoppings, aeroportos, escritórios)",
        "Horários de pico do público-alvo"]),
    "99": (["Banner no app"], ["Raio em volta das lojas e horários de pico"]),
    "ifood": (["Banner na home", "Busca patrocinada"], [
        "Segmentação por categoria e região de entrega", "Cupom exclusivo para medir a venda"]),
    "g1-globo": (["Takeover Home", "Native Ad", "Branded Content"], [
        "Viewability mínima de 70%", "Pixel de remarketing na peça para marcar leitores"]),
    "uol": (["Native Ad", "Billboard 970x250"], ["Viewability mínima de 70%", "Editorias com afinidade"]),
    "r7": (["Native Ad", "Billboard 970x250"], ["Viewability mínima de 70%"]),
    "cnn-brasil": (["Billboard 970x250", "Pre-roll Vídeo"], ["Daypart nos horários de maior audiência", "Brand safety por editoria"]),
    "sbt": (["Pre-roll +SBT", "Smart TV +SBT"], ["Combinar digital e Smart TV no mesmo programa"]),
    "infomoney": (["Native Ad", "Newsletter Sponsor"], ["Editorias de investimento e negócios", "Newsletter para público qualificado"]),
    "ge-globo-esporte": (["Billboard 970x250", "Pre-roll"], ["Daypart em dia de jogo", "Editorias de times e campeonatos"]),
    "tudogostoso": (["Branded Content", "Native Ad"], ["Receitas patrocinadas com o produto como ingrediente"]),
    "techtudo": (["Native Ad", "Branded Content"], ["Reviews e comparativos patrocinados"]),
    "experian-portal": (["Native Ad"], ["Público com interesse em crédito"]),
    "google-dv360": (["Display responsivo", "In-Banner Video", "CTV Pre-Roll"], [
        "PMP com portais premium em vez de open exchange",
        "Brand safety e listas de exclusão",
        "Remarketing por pixel do site e da landing page"]),
    "logan": (["Display mobile geolocalizado"], ["Geofence em volta das lojas e de concorrentes", "Medição de visita à loja"]),
    "experian-dmp": (["Audiências Serasa (dados)"], ["Audiência por renda, crédito e propensão de compra ativada na DSP"]),
    "amazon-ads": (["Sponsored Products", "Sponsored Brands", "Amazon DSP"], [
        "Palavras-chave de concorrentes e categorias", "Remarketing de quem viu o produto na Amazon"]),
    "interativos": (["Rich Media / Quiz"], ["Medir tempo de interação e taxa de engajamento", "Remarketing de quem interagiu"]),
}

# Mínimo viável por canal (R$ no período). Abaixo disso o algoritmo não acha
# volume para aprender, então o canal sai da faixa.
MINIMO_CANAL = {
    "google-search": 3_000, "google-pmax": 4_000, "google-demand-gen": 4_000, "google-app": 5_000,
    "meta-ads": 3_000, "youtube": 5_000, "tiktok": 5_000, "kwai": 3_000, "linkedin": 6_000,
    "twitch": 8_000, "spotify": 8_000, "deezer": 6_000, "amazon-music": 6_000, "podcast-ads": 6_000,
    "netflix": 25_000, "globoplay": 20_000, "prime-video": 20_000, "disney-plus": 20_000, "hbo-max": 20_000,
    "paramount-plus": 15_000, "samsung-tv-plus": 12_000, "eletromidia": 15_000, "uber": 12_000, "99": 8_000,
    "ifood": 10_000, "g1-globo": 15_000, "uol": 8_000, "r7": 6_000, "cnn-brasil": 10_000, "sbt": 10_000,
    "infomoney": 8_000, "ge-globo-esporte": 10_000, "tudogostoso": 8_000, "techtudo": 8_000,
    "experian-portal": 6_000, "google-dv360": 5_000, "logan": 6_000, "experian-dmp": 4_000,
    "amazon-ads": 5_000, "interativos": 10_000,
}

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slug_url(texto, limite: int = 120) -> str:
    """Endereço legível a partir de um nome: sem acento, minúsculas e hífens.
    "Funil essencial: busca, social e remarketing" -> "funil-essencial-busca-social-e-remarketing"."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:limite].rstrip("-")


def url_slug(e: dict) -> str:
    """Endereço público da estratégia. Fica gravado em dados.url_slug (nome do cadastro, uma vez);
    sem ele, sai do nome atual. O ``slug`` interno continua sendo a chave das imagens e da semente."""
    return e.get("url_slug") or slug_url(e.get("nome")) or str(e.get("slug") or "")


def brl(valor) -> str:
    """R$ 12.500 (sem centavos)."""
    try:
        n = int(round(float(valor)))
    except (TypeError, ValueError):
        return "R$ 0"
    return "R$ " + f"{n:,}".replace(",", ".")


def brl_curto(valor) -> str:
    """R$ 10 mil, R$ 1,5 mi."""
    n = int(valor or 0)
    if n >= 1_000_000:
        return "R$ " + f"{n / 1_000_000:.1f}".replace(".", ",").replace(",0", "") + " mi"
    if n >= 1_000:
        return "R$ " + f"{n / 1_000:.1f}".replace(".", ",").replace(",0", "") + " mil"
    return brl(n)


def faixa_inicial(verba_minima) -> int:
    """Primeira faixa que cobre a verba mínima da estratégia."""
    for f in FAIXAS:
        if f >= int(verba_minima or 0):
            return f
    return FAIXAS[-1]


def recebe_verba(canal: dict) -> bool:
    return int(canal.get("peso") or 0) > 0 and canal.get("slug") not in NOS_FLUXO


def divisao(canais: list[dict], verba: int) -> dict:
    """Quanto vai para cada canal numa verba.

    Começa com todos os canais pagos pela proporção dos pesos. Enquanto algum
    canal não essencial ficar abaixo do mínimo dele, sai o de menor peso e a
    verba é redistribuída. Os valores são arredondados a R$ 500 e a sobra vai
    para o maior canal, então a soma bate com a verba.
    """
    verba = int(verba)
    pagos = [c for c in canais if recebe_verba(c)]
    ativos = list(pagos)
    while True:
        total = sum(int(c["peso"]) for c in ativos) or 1
        abaixo = [c for c in ativos if not c.get("essencial")
                  and verba * int(c["peso"]) / total < minimo(c)]
        if not abaixo:
            break
        ativos.remove(min(abaixo, key=lambda c: (int(c["peso"]), -minimo(c))))
    total = sum(int(c["peso"]) for c in ativos) or 1
    linhas = []
    for c in ativos:
        valor = int(verba * int(c["peso"]) / total // ARREDONDA * ARREDONDA)
        linhas.append({"slug": c["slug"], "papel": c.get("papel") or "", "valor": valor})
    if linhas:
        sobra = verba - sum(l["valor"] for l in linhas)
        max(linhas, key=lambda l: l["valor"])["valor"] += sobra
    for l in linhas:
        l["pct"] = round(100 * l["valor"] / verba, 1) if verba else 0
    linhas.sort(key=lambda l: -l["valor"])
    fora = [c["slug"] for c in pagos if c not in ativos]
    return {"verba": verba, "linhas": linhas, "fora": fora}


def minimo(canal: dict) -> int:
    v = canal.get("minimo")
    if v in (None, ""):
        return MINIMO_CANAL.get(canal.get("slug"), 3_000)
    return int(v)


def tabela_faixas(canais: list[dict], verba_minima: int) -> list[dict]:
    """Divisão em cada faixa, com a faixa marcada como disponível ou não."""
    inicio = faixa_inicial(verba_minima)
    saida = []
    for f in FAIXAS:
        d = divisao(canais, f)
        d["disponivel"] = f >= inicio
        saida.append(d)
    return saida


def entra_a_partir(canais: list[dict], verba_minima: int) -> dict:
    """Para cada canal pago, a menor faixa em que ele recebe verba."""
    inicio = faixa_inicial(verba_minima)
    saida = {}
    for f in FAIXAS:
        if f < inicio:
            continue
        for l in divisao(canais, f)["linhas"]:
            saida.setdefault(l["slug"], f)
    return saida
