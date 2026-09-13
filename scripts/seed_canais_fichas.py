"""Corta canais, aplica grupos e grava formatos/segmentações iniciais."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicentralv2.crm_v3_canais import (  # noqa: E402
    CANAIS_EXCLUIDOS,
    _CATALOG_PATH,
    _GRUPO_POR_SLUG,
    _normalizar_formato,
)

SEEDS = {
    "spotify": {
        "formatos": [
            {"nome": "Audio Ads", "dispositivos": ["audio", "mobile"], "melhor_para": "branding com completion alta"},
            {"nome": "Sponsored Playlist", "dispositivos": ["audio", "mobile"], "melhor_para": "descoberta de marca no hábito"},
            {"nome": "Video Takeover", "dispositivos": ["mobile"], "melhor_para": "lançamento com tela cheia"},
            {"nome": "Podcast Ads", "dispositivos": ["audio", "mobile"], "melhor_para": "host-read e afinidade"},
        ],
        "segmentacoes": [
            {"nome": "Momento do dia", "quando": "treino, foco, deslocamento", "exemplo": "Workout 6h–9h nas capitais"},
            {"nome": "Gênero musical", "quando": "associação de marca a cena", "exemplo": "Sertanejo, funk, pop"},
            {"nome": "Playlist habit", "quando": "frequência semanal", "exemplo": "Ouvintes de Discover Weekly"},
            {"nome": "Praça e idioma", "quando": "campanha regional", "exemplo": "SP + RJ em português"},
        ],
    },
    "deezer": {
        "formatos": [
            {"nome": "Audio Ads", "dispositivos": ["audio", "mobile"], "melhor_para": "branding no fluxo"},
            {"nome": "Sponsored Playlist", "dispositivos": ["audio", "mobile"], "melhor_para": "descoberta"},
            {"nome": "Display", "dispositivos": ["mobile"], "melhor_para": "apoio visual ao áudio"},
        ],
        "segmentacoes": [
            {"nome": "Gênero e humor", "quando": "afinidade cultural", "exemplo": "MPB, eletrônica, foco"},
            {"nome": "Dispositivo de escuta", "quando": "carro vs fone", "exemplo": "Mobile em trânsito"},
            {"nome": "Praça", "quando": "teste regional", "exemplo": "Capitais do Sudeste"},
            {"nome": "Frequência", "quando": "usuário diário", "exemplo": "7+ sessões/semana"},
        ],
    },
    "amazon-music": {
        "formatos": [
            {"nome": "Audio Ads", "dispositivos": ["audio", "mobile", "ctv"], "melhor_para": "casa e Echo"},
            {"nome": "Alexa", "dispositivos": ["audio"], "melhor_para": "marca na rotina da casa"},
            {"nome": "Display", "dispositivos": ["mobile"], "melhor_para": "apoio ao áudio"},
        ],
        "segmentacoes": [
            {"nome": "Casa conectada", "quando": "Echo e Fire", "exemplo": "Ouvintes com device Amazon"},
            {"nome": "Intenção de compra", "quando": "varejo e Prime", "exemplo": "Categorias do marketplace"},
            {"nome": "Gênero", "quando": "cena musical", "exemplo": "Pop e sertanejo"},
            {"nome": "Prime", "quando": "alto ticket", "exemplo": "Assinantes Prime Music"},
        ],
    },
    "netflix": {
        "formatos": [
            {"nome": "Video Ads", "dispositivos": ["ctv"], "melhor_para": "branding sem skip"},
            {"nome": "Pre-roll", "dispositivos": ["ctv"], "melhor_para": "abertura de sessão"},
            {"nome": "Pause Ads", "dispositivos": ["ctv"], "melhor_para": "marca no intervalo"},
        ],
        "segmentacoes": [
            {"nome": "Títulos em alta", "quando": "associação a hit", "exemplo": "Top 10 da semana"},
            {"nome": "Gênero", "quando": "família, drama, esportes", "exemplo": "Séries YA vs documentário"},
            {"nome": "Horário de sessão", "quando": "prime time vs late", "exemplo": "20h–23h CTV"},
            {"nome": "Household", "quando": "casa e compartilhado", "exemplo": "Contas com mais de um perfil"},
        ],
    },
    "globoplay": {
        "formatos": [
            {"nome": "Video Ads", "dispositivos": ["ctv", "mobile"], "melhor_para": "novela e jornal"},
            {"nome": "Pre-roll", "dispositivos": ["ctv", "mobile"], "melhor_para": "abertura de capítulo"},
            {"nome": "Mid-roll", "dispositivos": ["ctv"], "melhor_para": "intervalo de jornal"},
        ],
        "segmentacoes": [
            {"nome": "Jornalismo", "quando": "notícia ao vivo", "exemplo": "Jornal Nacional e edições locais"},
            {"nome": "Ficção", "quando": "novela e série Globo", "exemplo": "Capítulo das 21h"},
            {"nome": "Esporte", "quando": "jogo e mesa", "exemplo": "Transmissão de futebol"},
            {"nome": "Praça Globo", "quando": "afiliada", "exemplo": "SP, RJ, MG, NE"},
        ],
    },
    "paramount-plus": {
        "formatos": [
            {"nome": "Video Ads", "dispositivos": ["ctv"], "melhor_para": "filmes e esportes"},
            {"nome": "Pre-roll", "dispositivos": ["ctv"], "melhor_para": "abertura"},
            {"nome": "Mid-roll", "dispositivos": ["ctv"], "melhor_para": "intervalo"},
        ],
        "segmentacoes": [
            {"nome": "Esportes", "quando": "futebol e NFL", "exemplo": "Jogos e mesas"},
            {"nome": "Filmes e franquias", "quando": "marca em conteúdo", "exemplo": "Cinema Paramount"},
            {"nome": "Horário", "quando": "noite CTV", "exemplo": "Prime time"},
            {"nome": "Praça", "quando": "teste BR", "exemplo": "Sudeste"},
        ],
    },
    "samsung-tv-plus": {
        "formatos": [
            {"nome": "Video Ads", "dispositivos": ["ctv"], "melhor_para": "FAST sem assinatura"},
            {"nome": "Pause Ads", "dispositivos": ["ctv"], "melhor_para": "marca no canal FAST"},
        ],
        "segmentacoes": [
            {"nome": "Canal FAST", "quando": "conteúdo linear", "exemplo": "Notícia, filme, kids"},
            {"nome": "Modelo de TV", "quando": "Samsung no living", "exemplo": "Tizen 2023+"},
            {"nome": "Horário", "quando": "linear noturno", "exemplo": "19h–23h"},
            {"nome": "Praça", "quando": "capitals", "exemplo": "SP e RJ"},
        ],
    },
    "disney-plus": {
        "formatos": [
            {"nome": "Video Ads", "dispositivos": ["ctv"], "melhor_para": "família e franquia"},
            {"nome": "Pre-roll", "dispositivos": ["ctv"], "melhor_para": "abertura"},
            {"nome": "Pause Ads", "dispositivos": ["ctv"], "melhor_para": "marca na pausa"},
        ],
        "segmentacoes": [
            {"nome": "Família e kids", "quando": "Pixar e animação", "exemplo": "Perfis infantis"},
            {"nome": "Franquias", "quando": "Marvel, Star Wars, Star", "exemplo": "Lançamento de temporada"},
            {"nome": "Horário casa", "quando": "fim de semana", "exemplo": "Sábado tarde CTV"},
            {"nome": "Household", "quando": "conta compartilhada", "exemplo": "Mais de um perfil ativo"},
        ],
    },
    "prime-video": {
        "formatos": [
            {"nome": "Video Ads", "dispositivos": ["ctv", "mobile"], "melhor_para": "branding no Prime"},
            {"nome": "Pre-roll", "dispositivos": ["ctv"], "melhor_para": "abertura de título"},
            {"nome": "Pause Ads", "dispositivos": ["ctv"], "melhor_para": "marca no intervalo"},
        ],
        "segmentacoes": [
            {"nome": "Assinante Prime", "quando": "alto ticket e conveniência", "exemplo": "Contas Prime ativas"},
            {"nome": "Intenção Amazon", "quando": "varejo e shoppable", "exemplo": "Categoria marketplace 30d"},
            {"nome": "Esportes", "quando": "futebol e TNF", "exemplo": "Jogos no Prime"},
            {"nome": "Fire TV", "quando": "sala de estar", "exemplo": "Households com Fire Stick"},
        ],
    },
    "hbo-max": {
        "formatos": [
            {"nome": "Video Ads", "dispositivos": ["ctv"], "melhor_para": "premium adulto"},
            {"nome": "Pre-roll", "dispositivos": ["ctv"], "melhor_para": "abertura"},
            {"nome": "Mid-roll", "dispositivos": ["ctv"], "melhor_para": "intervalo longo"},
        ],
        "segmentacoes": [
            {"nome": "Séries HBO", "quando": "lançamento de temporada", "exemplo": "Drama e fantasia"},
            {"nome": "Cinema Warner", "quando": "filme recente", "exemplo": "Janela digital"},
            {"nome": "Esporte Discovery", "quando": "evento", "exemplo": "Olímpicos e e-sports"},
            {"nome": "Adulto premium", "quando": "marca de ticket alto", "exemplo": "Perfis 25–54 ABC"},
        ],
    },
    "g1-globo": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "cobertura nacional"},
            {"nome": "Native Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "leitura no feed"},
            {"nome": "Takeover", "dispositivos": ["desktop"], "melhor_para": "home de impacto"},
            {"nome": "Video Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "player de notícia"},
            {"nome": "Branded Content", "dispositivos": ["desktop", "mobile"], "melhor_para": "reportagem patrocinada"},
        ],
        "segmentacoes": [
            {"nome": "Home nacional", "quando": "awareness amplo", "exemplo": "Primeira tela G1"},
            {"nome": "Editoria", "quando": "contexto da notícia", "exemplo": "Economia, política, agro"},
            {"nome": "Regional", "quando": "praça e afiliada", "exemplo": "G1 Minas, G1 Rio, G1 SP"},
            {"nome": "Mobile vs desktop", "quando": "formato da peça", "exemplo": "Feed mobile 9:16 vs home desktop"},
            {"nome": "Horário de pauta", "quando": "pico de leitura", "exemplo": "7h–9h e 18h–21h"},
        ],
    },
    "r7": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "cobertura Record"},
            {"nome": "Native Ads", "dispositivos": ["mobile"], "melhor_para": "feed"},
            {"nome": "Video Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "player"},
        ],
        "segmentacoes": [
            {"nome": "Home R7", "quando": "awareness", "exemplo": "Primeira tela"},
            {"nome": "Entretenimento", "quando": "famosos e TV", "exemplo": "Seção de famosos"},
            {"nome": "Regional", "quando": "praça Record", "exemplo": "SP e interior"},
            {"nome": "Mobile", "quando": "leitura no app/site", "exemplo": "Feed 300×250"},
        ],
    },
    "uol": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "escala"},
            {"nome": "Native Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "conteúdo"},
            {"nome": "Takeover", "dispositivos": ["desktop"], "melhor_para": "home"},
            {"nome": "Video Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "player"},
        ],
        "segmentacoes": [
            {"nome": "Home UOL", "quando": "massa nacional", "exemplo": "Primeira tela"},
            {"nome": "Vertical", "quando": "economia, esporte, lifestyle", "exemplo": "UOL Economia"},
            {"nome": "E-mail e produtos", "quando": "base própria", "exemplo": "Assinantes UOL"},
            {"nome": "Mobile", "quando": "leitura rápida", "exemplo": "Feed"},
        ],
    },
    "cnn-brasil": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "contexto noticioso"},
            {"nome": "Video Ads", "dispositivos": ["desktop", "ctv", "mobile"], "melhor_para": "player e TV"},
            {"nome": "Branded Content", "dispositivos": ["desktop", "mobile"], "melhor_para": "especial"},
        ],
        "segmentacoes": [
            {"nome": "Jornalismo hard news", "quando": "credibilidade", "exemplo": "Home e vivo"},
            {"nome": "Business", "quando": "decisor", "exemplo": "CNN Money"},
            {"nome": "Horário ao vivo", "quando": "pauta quente", "exemplo": "Manhã e noite"},
            {"nome": "ABC", "quando": "marca premium", "exemplo": "Leitores 25–54"},
        ],
    },
    "sbt": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "portal SBT"},
            {"nome": "Video Ads", "dispositivos": ["desktop", "mobile", "ctv"], "melhor_para": "player e TV"},
            {"nome": "Branded Content", "dispositivos": ["desktop", "mobile"], "melhor_para": "entretenimento"},
        ],
        "segmentacoes": [
            {"nome": "Entretenimento", "quando": "programa e famosos", "exemplo": "SBT News + programação"},
            {"nome": "Família", "quando": "massa", "exemplo": "Tarde e domingo"},
            {"nome": "Regional", "quando": "afiliada", "exemplo": "Interior e capitais"},
            {"nome": "Mobile", "quando": "notícia rápida", "exemplo": "Feed SBT News"},
        ],
    },
    "experian-portal": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "intenção no portal"},
            {"nome": "Native Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "conteúdo de crédito"},
        ],
        "segmentacoes": [
            {"nome": "Momento de crédito", "quando": "consulta e score", "exemplo": "Visitantes do Serasa"},
            {"nome": "Imóveis e auto", "quando": "intenção alta", "exemplo": "Páginas de consulta"},
            {"nome": "Classe e renda", "quando": "corte financeiro", "exemplo": "ABC presumido"},
            {"nome": "Praça", "quando": "MG e RJ", "exemplo": "Parceria Centralcomm"},
        ],
    },
    "experian-dmp": {
        "formatos": [
            {"nome": "Custom segments", "dispositivos": ["desktop", "mobile", "ctv"], "melhor_para": "ativar em mídia"},
            {"nome": "Lookalike", "dispositivos": ["desktop", "mobile"], "melhor_para": "escala da base"},
            {"nome": "Data enrichment", "dispositivos": ["desktop"], "melhor_para": "CRM match"},
        ],
        "segmentacoes": [
            {"nome": "Score e pagador", "quando": "crédito e imóvel", "exemplo": "Score 500+ ABC"},
            {"nome": "Intenção 30 dias", "quando": "auto, viagem, casa", "exemplo": "Corte RJ vs Meta"},
            {"nome": "CNPJ", "quando": "B2B", "exemplo": "Porte e CNAE"},
            {"nome": "Lookalike da base", "quando": "escala controlada", "exemplo": "CRM do cliente"},
        ],
    },
    "tudogostoso": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "receita"},
            {"nome": "Branded recipes", "dispositivos": ["mobile"], "melhor_para": "marca na cozinha"},
            {"nome": "Native Ads", "dispositivos": ["mobile"], "melhor_para": "feed de receita"},
        ],
        "segmentacoes": [
            {"nome": "Ocasião", "quando": "almoço, festa, diet", "exemplo": "Receitas de domingo"},
            {"nome": "Ingrediente", "quando": "marca de alimento", "exemplo": "Páginas com o produto"},
            {"nome": "Mobile cozinha", "quando": "uso na bancada", "exemplo": "Sessão mobile longa"},
            {"nome": "Frequência", "quando": "cozinheiro habitual", "exemplo": "4+ visitas/mês"},
        ],
    },
    "techtudo": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "review"},
            {"nome": "Native Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "guia de compra"},
            {"nome": "Video Ads", "dispositivos": ["mobile"], "melhor_para": "unboxing"},
        ],
        "segmentacoes": [
            {"nome": "Categoria de gadget", "quando": "consideração", "exemplo": "Celular, notebook, game"},
            {"nome": "Guia de compra", "quando": "alta intenção", "exemplo": "Comparativos"},
            {"nome": "Lançamento", "quando": "janela de review", "exemplo": "Semana do unboxing"},
            {"nome": "Mobile", "quando": "leitura técnica", "exemplo": "Feed"},
        ],
    },
    "ge-globo-esporte": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "jogo e tabela"},
            {"nome": "Video Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "lance"},
            {"nome": "Takeover", "dispositivos": ["desktop"], "melhor_para": "clássico"},
        ],
        "segmentacoes": [
            {"nome": "Time", "quando": "paixão", "exemplo": "Páginas do clube"},
            {"nome": "Rodada", "quando": "ao vivo e pós-jogo", "exemplo": "Domingo 16h–20h"},
            {"nome": "Modalidade", "quando": "futebol vs olímpico", "exemplo": "ge futebol"},
            {"nome": "Praça do time", "quando": "regional", "exemplo": "ge Rio, ge Minas"},
        ],
    },
    "infomoney": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "decisor financeiro"},
            {"nome": "Native Ads", "dispositivos": ["desktop"], "melhor_para": "análise"},
            {"nome": "Newsletter", "dispositivos": ["desktop"], "melhor_para": "base assinante"},
        ],
        "segmentacoes": [
            {"nome": "Investidor", "quando": "renda variável e fundos", "exemplo": "Seção de mercados"},
            {"nome": "Horário de pregão", "quando": "abertura e fechamento", "exemplo": "9h–11h e 17h"},
            {"nome": "ABC alto", "quando": "marca financeira", "exemplo": "Leitores 30–55"},
            {"nome": "Newsletter", "quando": "relação contínua", "exemplo": "Base própria"},
        ],
    },
    "youtube": {
        "formatos": [
            {"nome": "TrueView", "dispositivos": ["ctv", "mobile", "desktop"], "melhor_para": "consideração"},
            {"nome": "Bumper", "dispositivos": ["ctv", "mobile"], "melhor_para": "recall 6s"},
            {"nome": "Shorts", "dispositivos": ["mobile"], "melhor_para": "alcance vertical"},
            {"nome": "Masthead", "dispositivos": ["desktop", "mobile"], "melhor_para": "lançamento"},
        ],
        "segmentacoes": [
            {"nome": "Intenção de busca", "quando": "consideração", "exemplo": "Palavras do vertical"},
            {"nome": "Afinidade de canal", "quando": "criador", "exemplo": "Canais de casa e auto"},
            {"nome": "YouTube no CTV", "quando": "sala", "exemplo": "TV Android e Chromecast"},
            {"nome": "Remarketing", "quando": "quem já viu", "exemplo": "Viewers 7d"},
        ],
    },
    "instagram": {
        "formatos": [
            {"nome": "Stories", "dispositivos": ["mobile"], "melhor_para": "alcance diário"},
            {"nome": "Reels", "dispositivos": ["mobile"], "melhor_para": "descoberta"},
            {"nome": "Feed Ads", "dispositivos": ["mobile"], "melhor_para": "consideração"},
            {"nome": "Shopping", "dispositivos": ["mobile"], "melhor_para": "catálogo"},
        ],
        "segmentacoes": [
            {"nome": "Interesses", "quando": "alcance", "exemplo": "Casa, moda, comida"},
            {"nome": "Lookalike da base", "quando": "conversão", "exemplo": "CRM 1%"},
            {"nome": "Stories vs Reels", "quando": "formato da peça", "exemplo": "9:16 só"},
            {"nome": "Praça", "quando": "loja e cidade", "exemplo": "Raio 5 km"},
        ],
    },
    "tiktok": {
        "formatos": [
            {"nome": "In-feed", "dispositivos": ["mobile"], "melhor_para": "descoberta"},
            {"nome": "TopView", "dispositivos": ["mobile"], "melhor_para": "lançamento"},
            {"nome": "Spark Ads", "dispositivos": ["mobile"], "melhor_para": "impulsionar criador"},
        ],
        "segmentacoes": [
            {"nome": "Interesse e comportamento", "quando": "Gen Z e millennial", "exemplo": "Beleza, humor, game"},
            {"nome": "Spark de creator", "quando": "prova social", "exemplo": "Vídeo orgânico impulsionado"},
            {"nome": "Praça", "quando": "cidade", "exemplo": "Capitais"},
            {"nome": "Retarget", "quando": "view 50%", "exemplo": "7 dias"},
        ],
    },
    "linkedin": {
        "formatos": [
            {"nome": "Sponsored Content", "dispositivos": ["desktop", "mobile"], "melhor_para": "B2B"},
            {"nome": "Message Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "inbox"},
            {"nome": "Dynamic Ads", "dispositivos": ["desktop"], "melhor_para": "vaga e marca"},
        ],
        "segmentacoes": [
            {"nome": "Cargo e senioridade", "quando": "decisor", "exemplo": "C-level e gerência"},
            {"nome": "Setor", "quando": "vertical", "exemplo": "Imobiliário, financeiro"},
            {"nome": "Empresa e porte", "quando": "ABM", "exemplo": "Lista de contas"},
            {"nome": "Geo profissional", "quando": "praça B2B", "exemplo": "SP e RJ"},
        ],
    },
    "kwai": {
        "formatos": [
            {"nome": "In-feed", "dispositivos": ["mobile"], "melhor_para": "massa classe C"},
            {"nome": "Splash", "dispositivos": ["mobile"], "melhor_para": "abertura do app"},
        ],
        "segmentacoes": [
            {"nome": "Classe C e interior", "quando": "volume", "exemplo": "Praças fora do eixo"},
            {"nome": "Entretenimento curto", "quando": "recall simples", "exemplo": "15s vertical"},
            {"nome": "Idade", "quando": "18–34", "exemplo": "Feed"},
            {"nome": "Praça", "quando": "Nordeste e interior", "exemplo": "Cidades 200k+"},
        ],
    },
    "twitch": {
        "formatos": [
            {"nome": "Video Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "live"},
            {"nome": "Display", "dispositivos": ["desktop"], "melhor_para": "painel"},
        ],
        "segmentacoes": [
            {"nome": "Categoria de jogo", "quando": "FPS, mobile, just chatting", "exemplo": "Canais do gênero"},
            {"nome": "Creator", "quando": "comunidade", "exemplo": "Streamers BR"},
            {"nome": "Horário de live", "quando": "noite", "exemplo": "20h–1h"},
            {"nome": "Desktop vs mobile", "quando": "formato", "exemplo": "PC gamer"},
        ],
    },
    "eletromidia": {
        "formatos": [
            {"nome": "DOOH", "dispositivos": ["ooh"], "melhor_para": "circuito urbano"},
            {"nome": "Takeover", "dispositivos": ["ooh"], "melhor_para": "estação e aeroporto"},
        ],
        "segmentacoes": [
            {"nome": "Circuito", "quando": "metrô, rua, aeroporto", "exemplo": "Linha 4 e T3"},
            {"nome": "Fluxo e horário", "quando": "pico", "exemplo": "7h–9h e 18h–20h"},
            {"nome": "Classe do ponto", "quando": "AB vs massa", "exemplo": "Aeroporto vs terminal"},
            {"nome": "Praça", "quando": "cidade", "exemplo": "SP e RJ"},
        ],
    },
    "google-dv360": {
        "formatos": [
            {"nome": "Display", "dispositivos": ["desktop", "mobile"], "melhor_para": "escala"},
            {"nome": "Video Ads", "dispositivos": ["ctv", "mobile"], "melhor_para": "YouTube e CTV"},
            {"nome": "Native Ads", "dispositivos": ["desktop", "mobile"], "melhor_para": "open web"},
        ],
        "segmentacoes": [
            {"nome": "PMP vs open", "quando": "controle vs escala", "exemplo": "Deal premium G1"},
            {"nome": "1st party", "quando": "CRM e site", "exemplo": "Audience lists"},
            {"nome": "CTV inventory", "quando": "sala", "exemplo": "Apps conectados"},
            {"nome": "Brand safety", "quando": "notícia e UGC", "exemplo": "Exclusões e floors"},
        ],
    },
    "waze": {
        "formatos": [
            {"nome": "Pins", "dispositivos": ["mobile", "app"], "melhor_para": "loja no mapa"},
            {"nome": "Arrow", "dispositivos": ["mobile", "app"], "melhor_para": "desvio e parada"},
            {"nome": "Takeover", "dispositivos": ["mobile", "app"], "melhor_para": "abertura do app"},
        ],
        "segmentacoes": [
            {"nome": "Raio da loja", "quando": "drive-to-store", "exemplo": "3 km do PDV"},
            {"nome": "Trajeto", "quando": "casa–trabalho", "exemplo": "Manhã na Marginal"},
            {"nome": "Categoria no mapa", "quando": "intenção local", "exemplo": "Posto, farmácia, mall"},
            {"nome": "Praça", "quando": "cidade e corredor", "exemplo": "SP + ABC"},
        ],
    },
    "podcast-ads": {
        "formatos": [
            {"nome": "Host-read", "dispositivos": ["audio", "mobile"], "melhor_para": "confiança do host"},
            {"nome": "Audio Ads", "dispositivos": ["audio", "mobile"], "melhor_para": "rede"},
            {"nome": "Branded podcast", "dispositivos": ["audio"], "melhor_para": "série própria"},
        ],
        "segmentacoes": [
            {"nome": "Tema do show", "quando": "afinidade", "exemplo": "Negócios, true crime, futebol"},
            {"nome": "Host", "quando": "autoridade", "exemplo": "Programa X"},
            {"nome": "Download semanal", "quando": "frequência", "exemplo": "Ouvintes 4+ eps"},
            {"nome": "Praça do ouvinte", "quando": "regional", "exemplo": "Sudeste"},
        ],
    },
}


def main() -> None:
    rows = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    kept = []
    for row in rows:
        slug = (row.get("slug") or "").strip()
        if slug in CANAIS_EXCLUIDOS:
            continue
        if slug in _GRUPO_POR_SLUG:
            row["categoria"] = _GRUPO_POR_SLUG[slug]
        seed = SEEDS.get(slug)
        if seed:
            tipo = row.get("tipo") or ""
            row["formatos"] = [
                _normalizar_formato(item, tipo) for item in seed.get("formatos") or []
            ]
            row["segmentacoes"] = seed.get("segmentacoes") or []
        kept.append(row)
    _CATALOG_PATH.write_text(
        json.dumps(kept, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(kept)} canais gravados")


if __name__ == "__main__":
    main()
