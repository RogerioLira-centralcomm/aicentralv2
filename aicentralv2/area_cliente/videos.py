"""Vídeos do hub: visão geral, o que fazer com briefings/campanhas/relatórios/PIs e um por seção do Descobrir (mesmos nomes das seções: estrategias, canais, formatos, interativos, audiencias, portais).

Os IDs do YouTube ficam **aqui**, em um lugar só: troque ``youtube`` de cada item pelo ID do vídeo gravado (o trecho depois de
``v=`` na URL) e nada mais precisa mudar. Enquanto não há vídeo gravado, todos usam o vídeo modelo abaixo.
"""

from __future__ import annotations

VIDEO_MODELO = "M7lc1UVf-VE"        # vídeo de exemplo do YouTube (demo da API de player); trocar pelos vídeos da Centralcomm

VIDEOS = (
    {"slug": "visao-geral", "grupo": "Comece por aqui", "titulo": "Conheça o seu hub de mídia", "icone": "home", "youtube": VIDEO_MODELO,
     "resumo": "Um passeio de poucos minutos pelo hub: onde ver as campanhas, como pedir algo novo e como falar com o seu executivo."},
    {"slug": "operacao", "grupo": "Comece por aqui", "titulo": "Briefings, campanhas, relatórios e PIs", "icone": "layout", "youtube": VIDEO_MODELO,
     "resumo": "Como enviar um briefing, acompanhar campanhas no ar, abrir relatórios e consultar os seus PIs."},
    {"slug": "estrategias", "grupo": "Descobrir", "titulo": "Estratégias", "icone": "flow", "youtube": VIDEO_MODELO,
     "resumo": "Combinações de canais prontas para cada objetivo, com faixa de investimento."},
    {"slug": "canais", "grupo": "Descobrir", "titulo": "Canais", "icone": "broadcast", "youtube": VIDEO_MODELO,
     "resumo": "Onde a sua mídia pode rodar e o que cada canal faz melhor."},
    {"slug": "formatos", "grupo": "Descobrir", "titulo": "Formatos", "icone": "layout", "youtube": VIDEO_MODELO,
     "resumo": "Os formatos de anúncio disponíveis e como cada um aparece para o público."},
    {"slug": "interativos", "grupo": "Descobrir", "titulo": "Formatos interativos", "icone": "sparkles", "youtube": VIDEO_MODELO,
     "resumo": "Anúncios que o público toca, joga e explora."},
    {"slug": "audiencias", "grupo": "Descobrir", "titulo": "Audiências", "icone": "users", "youtube": VIDEO_MODELO,
     "resumo": "Como segmentamos público por perfil, interesse e comportamento."},
    {"slug": "portais", "grupo": "Descobrir", "titulo": "Portais", "icone": "globe", "youtube": VIDEO_MODELO,
     "resumo": "Os portais de conteúdo parceiros onde a sua marca pode aparecer."},
)
_POR_SLUG = {v["slug"]: v for v in VIDEOS}


def obter(slug: str | None) -> dict | None:
    return _POR_SLUG.get(slug or "visao-geral")


def vizinhos(slug: str) -> tuple[dict | None, dict | None]:
    """Vídeo anterior e próximo na ordem da lista (para os botões grandes)."""
    ids = [v["slug"] for v in VIDEOS]
    i = ids.index(slug)
    return (VIDEOS[i - 1] if i > 0 else None), (VIDEOS[i + 1] if i < len(VIDEOS) - 1 else None)


def grupos() -> list[tuple[str, list[dict]]]:
    saida: dict[str, list[dict]] = {}
    for v in VIDEOS:
        saida.setdefault(v["grupo"], []).append(v)
    return list(saida.items())


def embed_url(video: dict) -> str:
    """Embed sem cookies de rastreio, sem vídeos relacionados de outros canais ao fim."""
    return f"https://www.youtube-nocookie.com/embed/{video['youtube']}?rel=0&modestbranding=1&playsinline=1"


def destaque() -> dict:
    return _POR_SLUG["visao-geral"]
