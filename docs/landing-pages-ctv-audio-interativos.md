# Canais de CTV e Áudio + Formatos Interativos — briefing para landing pages

> Fonte: catálogo do Cadu Planner (tabelas `cadu_canais` e `cadu_formatos`, registros ativos), extraído em 29/10/2026. Textos são os mesmos que o Planner mostra; os números vêm com as fontes registradas no próprio catálogo.

## Como usar este documento

- **Imagens**: todas as URLs são públicas e absolutas (`https://planner.centralcomm.media/static/...` ou CDNs externas). Logos são os que o Planner resolve hoje; "capas" são ilustrações feitas no Studio (marcar como ilustrativas se a página distinguir foto de ilustração); "galeria" são fotos de banco de imagem (Unsplash) usadas nas LPs legadas.

- **Preço fica fora**: o Planner não mostra investimento mínimo nem preço de canal; as landing pages devem seguir a mesma regra.

- **Bloco `lp_data`**: quando existe, já é copy pensada para LP (headline, subhead, badge, stats, meta title/description). Use como ponto de partida. O `hero_headline` traz `<span class="gradient-text">` para destacar a segunda linha.

- **Segmentações com exemplo**: cada uma tem "quando usar" e um exemplo de campanha — bom material para seções de casos de uso.

- Marcas citadas são de terceiros: não reproduzir identidade visual além do logo.

## Índice

**CTV / Streaming de vídeo**: [Netflix](#netflix), [Globoplay](#globoplay), [Paramount+](#paramount-plus), [Samsung TV Plus](#samsung-tv-plus), [Disney+](#disney-plus), [Prime Video](#prime-video), [Max (HBO)](#hbo-max)

**Áudio / Streaming de áudio**: [Spotify](#spotify), [Deezer](#deezer), [Amazon Music](#amazon-music), [Podcast Ads (Rede)](#podcast-ads)

**Multicanal com CTV e áudio**: [Logan](#logan)

**Formatos interativos (rich media)**: [29 formatos](#formatos-interativos)

**Imagens**: [tabela de imagens por canal, com URL pública e arquivo local](#imagens-dos-canais-criadas-para-o-cadu-planner)

## Visão rápida

| Canal | Tipo | Alcance | Únicos | Tempo médio | Viewability | Completion | Compra |
|---|---|---|---|---|---|---|---|
| Netflix | CTV | +20M assinantes BR | 20M | 2h/dia | 99% | 97% | CPM |
| Globoplay | CTV | +25M assinantes | 25M | 1.5h/dia | 98% | 94% | CPM, CPV |
| Paramount+ | CTV | +8M assinantes BR | 8M | 1.2h/dia | 97% | 93% | CPM |
| Samsung TV Plus | CTV | +22,4M usuários BR | 20M | 1h12min/dia | 97% | 95% | CPM, CPV, Reserva (Home Screen) |
| Disney+ | CTV | +15M assinantes BR | 15M | 1.5h/dia | 98% | 96% | CPM |
| Prime Video | CTV | +12M assinantes BR | 12M | 1.3h/dia | 97% | 94% | CPM |
| Max (HBO) | CTV | +10M assinantes BR | 10M | 1.4h/dia | 98% | 95% | CPM |
| Spotify | AUDIO | +56M usuários BR | 50M | 45 min/dia | 98% | 95% | CPM, CPCV |
| Deezer | AUDIO | +16M ouvintes BR | 16M | 38 min/dia | 96% | 93% | CPM |
| Amazon Music | AUDIO | +8M ouvintes BR | 8M | 32 min/dia | 97% | 94% | CPM, CPCV |
| Podcast Ads (Rede) | AUDIO | +40M ouvintes BR | 40M ouvintes | 45 min/episódio | 95% | 92% | CPM, Flat Fee (sponsorship) |
| Logan | OOH | 100M+ usuários únicos via SDK de push | 100M+ (SDK de push) | — | 94% | — | — |


## Imagens dos canais criadas para o Cadu Planner

Todas as imagens abaixo são as que o Planner exibe hoje nas fichas de canal. Cada linha tem a **URL pública completa** (`https://planner.centralcomm.media/static/...`, responde 200 sem login) e o **caminho local** no repositório, para abrir o arquivo direto no computador.

- **Logo**: logo oficial que o Planner usa no card e na ficha.
- **Capa**: ilustração feita no Studio (1680×944). A `-b` é um segundo ângulo. São ilustrativas, não fotos reais.
- **Simulação de anúncio**: mockup da peça no ambiente do canal (1200×800), com marca de exemplo. Aparecem na ficha como "conceitos de ativação" — não são campanhas reais desses anunciantes; nas LPs, rotular como simulação.
- **Tela de referência**: telas e catálogos usados pelos visualizadores de criativo do Studio.

### Netflix (`netflix`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Netflix | — | Logo do canal | 64×64 | [abrir](https://planner.centralcomm.media/static/images/creative-viewers/netflix.png) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/creative-viewers/netflix.png` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/netflix.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/netflix.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/netflix-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/netflix-b.webp` |
| Simulação de anúncio | Dove · Vídeo antes do conteúdo | Pre-roll · CTV | Anúncio antes do título escolhido. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/netflix-pre-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/netflix-pre-roll.jpg` |
| Simulação de anúncio | Nescau · Intervalo | Mid-roll | Entre os blocos do episódio. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/netflix-mid-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/netflix-mid-roll.jpg` |
| Simulação de anúncio | Itambé · Anúncio na pausa | Pause Ad | Aparece quando a pessoa pausa. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/netflix-pause-ad.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/netflix-pause-ad.jpg` |
| Simulação de anúncio | Mercado Livre · No celular | Vídeo · mobile | Assistir de qualquer lugar. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/netflix-mobile.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/netflix-mobile.jpg` |
| Simulação de anúncio | Coca-Cola · No tablet | Vídeo · tablet | Uso em casa e em viagem. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/netflix-tablet.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/netflix-tablet.jpg` |
| Tela de referência | netflix-catalog | — | Visualizador de criativo do Studio | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/creative-viewers/catalog/netflix-catalog.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/creative-viewers/catalog/netflix-catalog.svg` |
| Tela de referência | netflix-top10 | — | Visualizador de criativo do Studio | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/creative-viewers/catalog/netflix-top10.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/creative-viewers/catalog/netflix-top10.svg` |

### Globoplay (`globoplay`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Globoplay | — | Logo do canal | 180×180 | [abrir](https://planner.centralcomm.media/static/images/canais/globoplay.png) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/globoplay.png` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/globoplay.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/globoplay.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/globoplay-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/globoplay-b.webp` |
| Simulação de anúncio | Unimed · Vídeo antes do conteúdo | Pre-roll · CTV | Anúncio antes da novela, série ou filme. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/globoplay-pre-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/globoplay-pre-roll.jpg` |
| Simulação de anúncio | Coca-Cola · Intervalo comercial | Mid-roll | Entre os blocos do conteúdo. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/globoplay-mid-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/globoplay-mid-roll.jpg` |
| Simulação de anúncio | Dove · Destaque na home | Display · home | Primeira tela do streaming. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/globoplay-home-takeover.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/globoplay-home-takeover.jpg` |
| Simulação de anúncio | Nescau · No celular | Vídeo · mobile | Assistir de qualquer lugar. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/globoplay-mobile.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/globoplay-mobile.jpg` |
| Simulação de anúncio | Itambé · Patrocínio de evento ao vivo | Patrocínio | Marca em transmissões ao vivo. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/globoplay-patrocinio-evento.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/globoplay-patrocinio-evento.jpg` |

### Paramount+ (`paramount-plus`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Paramount+ | — | Logo do canal | 256×256 | [abrir](https://planner.centralcomm.media/static/images/canais/paramount-plus.png) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/paramount-plus.png` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/paramount-plus.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/paramount-plus.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/paramount-plus-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/paramount-plus-b.webp` |
| Simulação de anúncio | Nescau · Vídeo antes do conteúdo | Pre-roll · CTV | Anúncio antes do filme ou série. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/paramount-plus-pre-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/paramount-plus-pre-roll.jpg` |
| Simulação de anúncio | Itambé · Intervalo | Mid-roll | Entre os blocos do conteúdo. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/paramount-plus-mid-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/paramount-plus-mid-roll.jpg` |
| Simulação de anúncio | Danone · Anúncio na pausa | Pause Ad | Aparece ao pausar o conteúdo. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/paramount-plus-pause-ad.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/paramount-plus-pause-ad.jpg` |
| Simulação de anúncio | Coca-Cola · No celular | Vídeo · mobile | Assistir de qualquer lugar. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/paramount-plus-mobile.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/paramount-plus-mobile.jpg` |
| Simulação de anúncio | Dove · Banner na home | Display · home | Destaque na entrada. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/paramount-plus-home-banner.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/paramount-plus-home-banner.jpg` |

### Samsung TV Plus (`samsung-tv-plus`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Samsung TV Plus | — | Logo do canal | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/canais/samsung-tv-plus.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/samsung-tv-plus.svg` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/samsung-tv-plus.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/samsung-tv-plus.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/samsung-tv-plus-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/samsung-tv-plus-b.webp` |
| Simulação de anúncio | Coca-Cola · Canal patrocinado | Canal FAST | A marca patrocina um canal linear gratuito. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/samsung-tv-plus-canal-fast.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/samsung-tv-plus-canal-fast.jpg` |
| Simulação de anúncio | Dove · Vídeo no intervalo | Vídeo · intervalo | Anúncio entre os blocos do canal. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/samsung-tv-plus-pre-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/samsung-tv-plus-pre-roll.jpg` |
| Simulação de anúncio | Mercado Livre · Banner na home da TV | Display · home TV | Primeira tela da smart TV. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/samsung-tv-plus-home-banner.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/samsung-tv-plus-home-banner.jpg` |
| Simulação de anúncio | Itambé · Anúncio interativo | Interativo · controle remoto | Responde ao controle remoto. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/samsung-tv-plus-interativo.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/samsung-tv-plus-interativo.jpg` |
| Simulação de anúncio | Danone · Sala em família | Audiência em casa | Alcance de toda a casa. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/samsung-tv-plus-familia.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/samsung-tv-plus-familia.jpg` |

### Disney+ (`disney-plus`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Disney+ | — | Logo do canal | 180×180 | [abrir](https://planner.centralcomm.media/static/images/creative-viewers/disney-plus.png) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/creative-viewers/disney-plus.png` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/disney-plus.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/disney-plus.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/disney-plus-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/disney-plus-b.webp` |
| Simulação de anúncio | Itambé · Vídeo antes do conteúdo | Pre-roll · CTV | Anúncio antes do filme ou série. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/disney-plus-pre-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/disney-plus-pre-roll.jpg` |
| Simulação de anúncio | Danone · Anúncio na pausa | Pause Ad | Aparece quando a pessoa pausa o conteúdo. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/disney-plus-pause-ad.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/disney-plus-pause-ad.jpg` |
| Simulação de anúncio | Coca-Cola · Banner na home | Display · home | Destaque na entrada do streaming. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/disney-plus-home-banner.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/disney-plus-home-banner.jpg` |
| Simulação de anúncio | Havaianas · No celular | Vídeo · mobile | Mesma mensagem fora da sala. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/disney-plus-mobile.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/disney-plus-mobile.jpg` |
| Simulação de anúncio | Nescau · Coleção patrocinada | Coleção patrocinada | Marca associada a uma seleção de títulos. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/disney-plus-patrocinio-colecao.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/disney-plus-patrocinio-colecao.jpg` |
| Tela de referência | disney-catalog | — | Visualizador de criativo do Studio | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/creative-viewers/catalog/disney-catalog.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/creative-viewers/catalog/disney-catalog.svg` |

### Prime Video (`prime-video`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Prime Video | — | Logo do canal | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/canais/prime-video.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/prime-video.svg` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/prime-video.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/prime-video.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/prime-video-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/prime-video-b.webp` |
| Simulação de anúncio | L’Oréal Paris Revitalift | Pre-roll CTV · 16:9 | Conceito de pre-roll CTV 16:9 para demonstrar o formato no Prime Video. | 1672×941 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/loreal-prime-video-revitalift-concept.png) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/loreal-prime-video-revitalift-concept.png` |
| Simulação de anúncio | Danone · Intervalo | Mid-roll | Entre os blocos do episódio. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/prime-video-mid-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/prime-video-mid-roll.jpg` |
| Simulação de anúncio | Coca-Cola · Anúncio na pausa | Pause Ad | Aparece ao pausar o conteúdo. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/prime-video-pause-ad.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/prime-video-pause-ad.jpg` |
| Simulação de anúncio | Dove · Banner na home | Display · home | Destaque na entrada. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/prime-video-home-banner.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/prime-video-home-banner.jpg` |
| Simulação de anúncio | Nescau · No celular | Vídeo · mobile | Assistir de qualquer lugar. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/prime-video-mobile.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/prime-video-mobile.jpg` |
| Simulação de anúncio | Itambé · Compra na TV | Anúncio interativo | O espectador adiciona o produto ao carrinho pela TV. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/prime-video-compra-na-tv.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/prime-video-compra-na-tv.jpg` |
| Tela de referência | prime-video | — | Visualizador de criativo do Studio | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/creative-viewers/prime-video.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/creative-viewers/prime-video.svg` |

### Max (HBO) (`hbo-max`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Max (HBO) | — | Logo do canal | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/canais/hbo-max.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/hbo-max.svg` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/hbo-max.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/hbo-max.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/hbo-max-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/hbo-max-b.webp` |
| Simulação de anúncio | Coca-Cola · Vídeo antes do conteúdo | Pre-roll · CTV | Anúncio antes da série ou filme. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/hbo-max-pre-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/hbo-max-pre-roll.jpg` |
| Simulação de anúncio | Dove · Anúncio na pausa | Pause Ad | Aparece ao pausar o conteúdo. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/hbo-max-pause-ad.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/hbo-max-pause-ad.jpg` |
| Simulação de anúncio | Nescau · Banner na home | Display · home | Destaque na entrada. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/hbo-max-home-banner.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/hbo-max-home-banner.jpg` |
| Simulação de anúncio | Itambé · No celular | Vídeo · mobile | Assistir de qualquer lugar. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/hbo-max-mobile.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/hbo-max-mobile.jpg` |
| Simulação de anúncio | Danone · Intervalo | Mid-roll | Entre os blocos do episódio. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/hbo-max-mid-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/hbo-max-mid-roll.jpg` |
| Tela de referência | hbo-max | — | Visualizador de criativo do Studio | 222×160 | [abrir](https://planner.centralcomm.media/static/images/creative-viewers/hbo-max.png) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/creative-viewers/hbo-max.png` |
| Tela de referência | hbo-catalog | — | Visualizador de criativo do Studio | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/creative-viewers/catalog/hbo-catalog.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/creative-viewers/catalog/hbo-catalog.svg` |
| Tela de referência | hbo-cinema | — | Visualizador de criativo do Studio | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/creative-viewers/catalog/hbo-cinema.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/creative-viewers/catalog/hbo-cinema.svg` |

### Spotify (`spotify`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Spotify | — | Logo do canal | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/canais/spotify.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/spotify.svg` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/spotify.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/spotify.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/spotify-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/spotify-b.webp` |
| Simulação de anúncio | Dove · Anúncio de áudio | Áudio · 30 s | Entre as músicas, com capa da marca. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/spotify-audio-ad.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/spotify-audio-ad.jpg` |
| Simulação de anúncio | Nescau · Video Takeover | Vídeo · tela ativa | Vídeo que roda quando o app está aberto. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/spotify-video-takeover.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/spotify-video-takeover.jpg` |
| Simulação de anúncio | Nike · Takeover na home | Display · home | Destaque total na entrada do app. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/spotify-home-takeover.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/spotify-home-takeover.jpg` |
| Simulação de anúncio | Danone · Playlist patrocinada | Playlist da marca | Curadoria no tom da marca. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/spotify-playlist.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/spotify-playlist.jpg` |
| Simulação de anúncio | Nespresso · Em podcasts | Áudio · podcast | Mensagem dentro do episódio. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/spotify-podcast.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/spotify-podcast.jpg` |

### Deezer (`deezer`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Deezer | — | Logo do canal | 777×548 | [abrir](https://planner.centralcomm.media/static/images/canais/deezer.png) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/deezer.png` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/deezer.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/deezer.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/deezer-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/deezer-b.webp` |
| Simulação de anúncio | Nescau · Anúncio de áudio | Áudio · 30 s | Entre as músicas, com capa da marca. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/deezer-audio-ad.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/deezer-audio-ad.jpg` |
| Simulação de anúncio | Itambé · Banner no player | Display · player | Imagem clicável enquanto o áudio toca. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/deezer-banner-player.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/deezer-banner-player.jpg` |
| Simulação de anúncio | Danone · Playlist da marca | Playlist patrocinada | Curadoria no tom da marca. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/deezer-playlist.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/deezer-playlist.jpg` |
| Simulação de anúncio | Coca-Cola · Takeover na home | Display · home | Destaque total na entrada do app. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/deezer-home-takeover.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/deezer-home-takeover.jpg` |
| Simulação de anúncio | Dove · Vídeo por recompensa | Video reward | A pessoa assiste e ganha tempo sem anúncios. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/deezer-video-reward.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/deezer-video-reward.jpg` |

### Amazon Music (`amazon-music`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Amazon Music | — | Logo do canal | 256×256 | [abrir](https://planner.centralcomm.media/static/images/canais/amazon-music.png) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/amazon-music.png` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/amazon-music.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/amazon-music.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/amazon-music-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/amazon-music-b.webp` |
| Simulação de anúncio | Dove · Anúncio de áudio | Áudio · 30 s | Entre as músicas, com capa da marca na tela. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/amazon-music-audio-ad.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/amazon-music-audio-ad.jpg` |
| Simulação de anúncio | Nescau · Banner no player | Display · player | Imagem clicável enquanto o áudio toca. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/amazon-music-banner-player.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/amazon-music-banner-player.jpg` |
| Simulação de anúncio | Itambé · Playlist patrocinada | Playlist da marca | Playlist com o tom da marca. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/amazon-music-playlist-patrocinada.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/amazon-music-playlist-patrocinada.jpg` |
| Simulação de anúncio | Danone · Em casa, no alto-falante | Áudio · smart speaker | Alcança a pessoa em casa, pela voz. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/amazon-music-alexa.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/amazon-music-alexa.jpg` |
| Simulação de anúncio | Coca-Cola · Takeover de sessão | Sessão patrocinada | Sem anúncios de concorrentes por um período. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/amazon-music-takeover.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/amazon-music-takeover.jpg` |

### Podcast Ads (Rede) (`podcast-ads`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Podcast Ads (Rede) | — | Logo do canal | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/canais/podcast-ads.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/podcast-ads.svg` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/podcast-ads.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/podcast-ads.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/podcast-ads-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/podcast-ads-b.webp` |
| Simulação de anúncio | Itambé · Lido pelo apresentador | Host-read · 30-60 s | A recomendação vem da voz que a pessoa já confia. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/podcast-ads-host-read.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/podcast-ads-host-read.jpg` |
| Simulação de anúncio | Danone · Antes do episódio | Pre-roll · áudio | Mensagem curta no início. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/podcast-ads-pre-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/podcast-ads-pre-roll.jpg` |
| Simulação de anúncio | Coca-Cola · No meio do episódio | Mid-roll · áudio | Maior atenção, no meio do conteúdo. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/podcast-ads-mid-roll.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/podcast-ads-mid-roll.jpg` |
| Simulação de anúncio | Dove · Banner no app | Display · player | Imagem clicável enquanto o episódio toca. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/podcast-ads-banner-app.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/podcast-ads-banner-app.jpg` |
| Simulação de anúncio | Nescau · Série patrocinada | Naming de série | A marca apresenta uma série de episódios. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/podcast-ads-serie-patrocinada.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/podcast-ads-serie-patrocinada.jpg` |

### Logan (`logan`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Logan | — | Logo do canal | 790×231 | [abrir](https://planner.centralcomm.media/static/images/canais/logan.png) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/logan.png` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/logan.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/logan.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/logan-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/logan-b.webp` |
| Simulação de anúncio | Danone · Outdoor de estrada | OOH · outdoor | Visibilidade em rodovias e grandes avenidas. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/logan-frontlight.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/logan-frontlight.jpg` |
| Simulação de anúncio | Coca-Cola · Painel de LED | DOOH · LED | Troca de mensagem por horário e por dia. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/logan-led-avenida.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/logan-led-avenida.jpg` |
| Simulação de anúncio | Nike · Empena de prédio | OOH · empena | Grande formato que domina a paisagem. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/logan-empena.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/logan-empena.jpg` |
| Simulação de anúncio | Nescau · Relógio de rua | Mobiliário urbano | Presença no caminho a pé. | 800×1200 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/logan-mobiliario.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/logan-mobiliario.jpg` |
| Simulação de anúncio | Nespresso · Aeroporto | OOH · aeroporto | Público de maior renda em viagem. | 1200×800 | [abrir](https://planner.centralcomm.media/static/images/channel-creatives/logan-aeroporto.jpg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/channel-creatives/logan-aeroporto.jpg` |

### Formatos interativos (`interativos`)

| Tipo | Título | Formato | Descrição | Tamanho (px) | URL pública | Arquivo local |
|---|---|---|---|---|---|---|
| Logo | Formatos interativos | — | Logo do canal | vetor (SVG) | [abrir](https://planner.centralcomm.media/static/images/canais/interativos.svg) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/interativos.svg` |
| Capa | Capa 1 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/interativos.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/interativos.webp` |
| Capa | Capa 2 | — | Ilustração de capa da ficha | 1680×944 | [abrir](https://planner.centralcomm.media/static/images/canais/capas/interativos-b.webp) | `/Users/apololira/PhpstormProjects/centralx/aicentralv2/aicentralv2/static/images/canais/capas/interativos-b.webp` |

Total: 107 imagens.

---

# CTV / Streaming de vídeo


---

## Netflix
<a id="netflix"></a>

`slug: netflix` · categoria **Streaming** · tipo **ctv** · cor da marca `#E50914`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/creative-viewers/netflix.png)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/netflix.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/netflix-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/creative-viewers/netflix.png
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/netflix.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/netflix-b.webp

### Descrição

A maior plataforma de streaming de vídeo do mundo. Plano com anúncios oferece acesso a audiência premium em ambiente brand safe.

**Perfil de audiência**: No Brasil, o plano com anúncios da Netflix atingia 29,2 milhões de pessoas ativas por mês em 2023, com evolução recente da base de assinantes com ads.

**Melhor uso**: Melhor para awareness e consideração com alta atenção em streaming premium, especialmente para campanhas que querem combinar segmentação avançada e mensuração cross-media.

### Copy pronta para LP (`lp_data`)

- **Badge**: Streaming #1 no mundo – 325M assinantes
- **Headline**: Sua marca onde o Brasil<br><span class="gradient-text">presta atenção</span>
- **Subhead**: A Netflix superou 325 milhões de assinantes e dobrou sua receita de anúncios para US$1,5 bilhão em 2025.
- **Meta title**: Anuncie na Netflix | Onde o Brasil assiste
- **Meta description**: Alcance mais de 325 milhões de assinantes globais na plataforma onde passam 2h por dia.
- **Stat principal**: **2h** — por dia de atenção na tela
- **Stat secundaria**: **97%** — completam o anúncio (sem skip)
- **Stat terciaria**: **325M** — assinantes globais (Q4 2025)

### Números

- **Alcance**: +20M assinantes BR
- **Usuários únicos**: 20M
- **Tempo médio**: 2h/dia
- **Viewability (%)**: 99
- **Completion rate (%)**: 97
- **Taxa de engajamento (%)**: 95
- **Prazo de entrega**: 10 dias úteis
- **Integração**: Microsoft Advertising (Xandr)
- **Modelo de compra**: CPM
- **Brand safety**: Netflix Content Guidelines, DoubleVerify
- **Medição**: Nielsen Streaming; Comscore

**Demografia**

- Gênero: 48% homens / 52% mulheres
- Idade: 18–24: 22% · 25–34: 32% · 35–44: 26% · 45–54: 13% · 55+: 7%
- Classe: C: 26% · AB: 70% · DE: 4%

### Diferenciais

- Ambiente 100% brand safe - conteúdo curado
- Audiência premium e engajada
- Sem skip - completion rate de 97%
- Targeting por títulos populares (Top 10)

### Formatos

Resumo: Video Ads 15s/30s · Pre-roll · Mid-roll

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Video Ads (pre-roll/mid-roll) | 16:9 | video branding em conteúdos sob demanda | ctv, mobile, desktop, tablet, app |
| Pause Ads | 300×250 | presença de marca em momentos de pausa do usuário | ctv, mobile, desktop, tablet, app |
| Pre-roll | Pre-roll | abertura de sessão | ctv |

**Especificações técnicas**

- **Video Ad** — peso: até 100MB; duracao: 15s ou 30s; formato: MP4 H.264
- **Pre-roll** — peso: até 50MB; duracao: 15s; formato: MP4 1080p

#### Formato detalhado: Pre-Roll Ad

*Vídeo antes do conteúdo na Netflix*

- **Descrição**: Anúncio de vídeo exibido antes do episódio ou filme na Netflix. Ambiente premium, sem competição de outras marcas.
- **Como funciona**: O vídeo é exibido antes do conteúdo que o assinante escolheu assistir. Non-skip. Ambiente controlado e brand-safe.
- **Dica de criativo**: Contexto premium = criativo premium. Qualidade cinematográfica obrigatória. O público está relaxado e atento.
- **Funil**: awareness
- **Melhor para**: Branding premium, reach qualificado, CTV
- **Dimensões**: 1920x1080 (16:9) obrigatório
- **Duração**: 15s ou 30s
- **Peso máx.**: Sem limite (entrega via Netflix)
- **Arquivos**: MP4 (via Microsoft/Netflix)
- **Specs**: Resolução: 1920x1080 mínimo (4K recomendado) | Bitrate: 15Mbps+ | Codec: H.264 ou H.265 | Áudio: AAC, -24 LUFS | Non-skip | Entrega via Microsoft Advertising | Plano com anúncios: assinantes do tier básico

#### Formato detalhado: Mid-Roll Ad

*Vídeo no intervalo natural do conteúdo*

- **Descrição**: Anúncio inserido em breaks naturais durante séries e filmes. Maior completion rate — o assinante quer voltar ao conteúdo.
- **Como funciona**: Inserido em pontos de pausa natural da narrativa (como intervalo comercial de TV, mas em streaming).
- **Dica de criativo**: O assinante quer voltar à série — seu anúncio tem atenção garantida. Mensagem clara, CTA memorável.
- **Funil**: awareness
- **Melhor para**: Alta completion rate, atenção total
- **Dimensões**: 1920x1080 (16:9) obrigatório
- **Duração**: 15s ou 30s
- **Peso máx.**: Sem limite
- **Arquivos**: MP4
- **Specs**: Mesmos specs do Pre-Roll | Inserido em break natural do conteúdo | Non-skip | Completion rate ~95% | Frequência controlada pela Netflix | Máximo 4 minutos de ads por hora

#### Formato detalhado: Pause Ad

*Banner exibido quando o assinante pausa o conteúdo*

- **Descrição**: Quando o assinante pausa a série ou filme, um banner estático aparece na tela. Non-intrusive e alta visibilidade.
- **Como funciona**: O banner aparece quando o assinante clica em pausar. Permanece visível enquanto o conteúdo está pausado. Desaparece ao retomar.
- **Dica de criativo**: O assinante ESCOLHEU pausar — está pegando comida, conversando. Use mensagem contextual e QR Code para capturar.
- **Funil**: awareness
- **Melhor para**: Não intrusivo, alta visibilidade, momento natural
- **Dimensões**: 1920x1080 (16:9) | Formato adaptável
- **Peso máx.**: 5 MB
- **Arquivos**: JPG, PNG
- **Specs**: Exibido no momento de pausa | Estático (sem vídeo) | Permanece enquanto pausado | Desaparece ao retomar | Clicável com QR Code | Brand + mensagem + CTA | Sem som | Frequência: 1 por pausa

#### Formato detalhado: Binge Ad

*Recompensa para quem assiste episódios seguidos*

- **Descrição**: Após o assinante assistir 3 episódios seguidos com anúncios, o próximo episódio é livre de ads. Sua marca patrocina essa recompensa.
- **Como funciona**: Após 3 episódios com ads, aparece mensagem: "O próximo episódio é cortesia de [Sua Marca]". Gera goodwill e associação positiva.
- **Dica de criativo**: Sua marca é a "heroína" — o assinante te agradece. Mensagem curta, calorosa e generosa. Não venda, presenteie.
- **Funil**: awareness
- **Melhor para**: Brand love, percepção positiva, destaque
- **Dimensões**: 1920x1080 (16:9)
- **Duração**: 5-10 segundos (mensagem)
- **Peso máx.**: 5 MB
- **Arquivos**: JPG, PNG, MP4
- **Specs**: Tela de mensagem customizável | Logo da marca em destaque | "Próximo episódio sem anúncios, cortesia de [Marca]" | Após 3 episódios consecutivos | Associação emocional positiva | Via reserva

#### Formato detalhado: Title Sponsorship

*Patrocínio de título específico na Netflix*

- **Descrição**: Sua marca é associada a um título (série ou filme) específico. Aparece nos anúncios exibidos durante aquele conteúdo.
- **Como funciona**: Todos os breaks de anúncio daquele título mostram exclusivamente ou prioritariamente sua marca. Associação premium.
- **Dica de criativo**: Alinhe o posicionamento da marca com o gênero/tema do título. Patrocinar uma série de culinária se você é food funciona perfeitamente.
- **Funil**: awareness
- **Melhor para**: Afinidade de conteúdo, premium máximo
- **Dimensões**: 1920x1080 (16:9)
- **Duração**: 15s e 30s
- **Peso máx.**: Sem limite
- **Arquivos**: MP4
- **Specs**: Exclusividade no título escolhido | Todos os pre-rolls e mid-rolls do título | Presença no card de resumo pré-play | Via reserva direta | Disponibilidade por temporada/período

### Segmentações disponíveis

- **Temporal**: Dayparting (manhã, tarde, noite, madrugada); Dia da semana (úteis vs fins de semana); Horário nobre (prime time); Sazonalidade
- **Contextual / Conteúdo**: Gênero de conteúdo (Drama, Ação, Comédia, Documentário, Anime, Reality, Romance, Terror, Suspense, Sci-Fi); Top 10 Titles; Novos lançamentos e estreias; Conteúdo original Netflix vs licenciado; Séries vs Filmes; Conteúdo por idioma/país de origem
- **Geográfica**: País; Região/Estado
- **Demográfica**: Idade (18-65+); Gênero
- **Comportamental**: Binge Watchers (maratonistas); Frequência de uso (heavy/medium/light viewers); Novo assinante vs recorrente; Assinante do plano com anúncios; Perfil de engajamento (tempo médio de sessão)
- **Dados Exclusivos Netflix**: Viewing history signals; Content affinity score; Engagement score; Completion behavior

### Segmentações com exemplo de uso

- **Rotativo (sem segmentação)**
  - Quando: campanha de cobertura ampla no plano com anúncios
  - Exemplo: Inserção de vídeo ads distribuídos em diferentes títulos e gêneros, sem filtro adicional de conteúdo.
- **Por gênero de conteúdo**
  - Quando: campanha alinhada ao contexto editorial
  - Exemplo: Segmentação para exibir anúncios apenas em séries de comédia ou filmes de ação.
- **Top 10 Netflix**
  - Quando: campanhas que priorizam títulos de maior audiência
  - Exemplo: Compra de inventário em filmes e séries listados no Top 10 diário da Netflix.
- **Primeira impressão do dia**
  - Quando: lançamentos e comunicações que buscam alto impacto na primeira sessão do usuário
  - Exemplo: Garantir que o primeiro anúncio exibido ao usuário em seu dia na Netflix seja da marca da campanha.
- **Interesse (Ads Suite, +100 opções)**
  - Quando: campanhas orientadas a perfis de audiência com base em comportamento de consumo
  - Exemplo: Segmentar usuários com interesse em esportes, kids & family ou true crime usando a camada de dados da Netflix Ads Suite.
- **Categorias de audiência (17 categorias)**
  - Quando: planejamento mais granular em clusters de conteúdo/consumo
  - Exemplo: Comprar mídia em categorias como entretenimento jovem adulto ou lifestyle, conforme taxonomia da plataforma.
- **Audiências 1st party (Amazon Audiences via programático)**
  - Quando: campanhas com compra programática que usam dados de terceiros integrados
  - Exemplo: Usar audiências Amazon para orientar compras programáticas de inventário Netflix no Brasil e México.
- **Momento de maratona (binge behavior)**
  - Quando: campanhas que consideram o comportamento de assistir vários episódios em sequência
  - Exemplo: Ativar criativos específicos em blocos de anúncios antes dos três primeiros episódios de uma série, respeitando novos formatos binge ad anunciados pela Netflix.

### Fontes

- https://about.netflix.com/pt_br/news/netflix-and-embratur-announce-cooperation-agreement
- https://about.netflix.com/pt_br/news/netflix-third-season-of-ads-and-a-look-ahead-at-whats-next-brazil
- https://about.netflix.com/pt_br/news/one-year-into-netflix-ads
- https://telaviva.com.br/12/11/2024/netflix-lancara-tecnologia-de-publicidade-interna-em-2025


---

## Globoplay
<a id="globoplay"></a>

`slug: globoplay` · categoria **Streaming** · tipo **ctv** · cor da marca `#F7941D`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/globoplay.png)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/globoplay.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/globoplay-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/canais/globoplay.png
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/globoplay.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/globoplay-b.webp

### Descrição

Principal plataforma de streaming brasileira com conteúdo exclusivo Globo, novelas, séries e jornalismo.

**Perfil de audiência**: A audiência publicitária do Globoplay é formada por usuários com dados de perfil ligados ao Globo ID, incluindo idade, gênero, interesses e até renda/poder de compra em ativações ao vivo.

**Melhor uso**: Bom para alcance premium com segmentação por dados próprios da Globo, especialmente em campanhas com vídeo, cobertura regional e ativações em conteúdo ao vivo.

### Copy pronta para LP (`lp_data`)

- **Badge**: Streaming #1 do Brasil – 25M assinantes
- **Meta title**: Anuncie no Globoplay | O streaming do Brasil
- **Stat principal**: **1,5h** — por dia de conteúdo consumido
- **Stat secundaria**: **94%** — completion rate
- **Stat terciaria**: **+86%** — crescimento da receita de ads (2024)

### Números

- **Alcance**: +25M assinantes
- **Usuários únicos**: 25M
- **Tempo médio**: 1.5h/dia
- **Viewability (%)**: 98
- **Completion rate (%)**: 94
- **Taxa de engajamento (%)**: 91
- **Prazo de entrega**: 7 dias úteis
- **Integração**: Globo Ads / DV360
- **Modelo de compra**: CPM, CPV
- **Brand safety**: Globo Content Guidelines
- **Medição**: Kantar IBOPE; Nielsen

**Demografia**

- Gênero: 42% homens / 58% mulheres
- Idade: 18–24: 18% · 25–34: 28% · 35–44: 26% · 45–54: 17% · 55+: 11%
- Classe: C: 35% · AB: 58% · DE: 7%

### Diferenciais

- Conteúdo exclusivo brasileiro (novelas, BBB, séries)
- Transmissão ao vivo de eventos
- Integração com TV Globo
- Audiência feminina forte (58%)

### Formatos

Resumo: Video Ads 15s/30s · Pre-roll · Mid-roll · Pause Ads · Branded Content

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Video Ads | 16:9 | novela e jornal | ctv, mobile |
| Pre-roll | Pre-roll | abertura de capítulo | ctv, mobile |
| Mid-roll | Mid-roll | intervalo de jornal | ctv |

**Especificações técnicas**

- **Video Ad** — peso: até 80MB; duracao: 15s ou 30s; formato: MP4 H.264
- **Pause Ad** — peso: até 500KB; formato: JPG/PNG; dimensao: 1920x1080

### Segmentações disponíveis

- **Temporal**: Horário nobre (20h-23h); Transmissões ao vivo de eventos (BBB, futebol, F1); Dayparting; Dia da semana
- **Contextual / Conteúdo**: Por programa/novela específica (BBB, novela das 9, Fantástico); Gênero de conteúdo (novela, série, jornalismo, reality, esportes, humor); Ao vivo vs VOD; Conteúdo exclusivo Globoplay vs simulcast TV Globo; Canais ao vivo (Globo, GloboNews, Multishow, etc.)
- **Geográfica**: País; Estado/UF; Cidade; Região (Sul, Sudeste, Nordeste, etc.)
- **Demográfica**: Idade (18-65+); Gênero; Classe social (via Kantar/IBOPE)
- **Comportamental**: Frequência de uso (diário, semanal, esporádico); Assinante vs usuário free; Perfil de consumo (novelas, séries, esportes, notícias); Heavy viewers vs light viewers
- **Dados Exclusivos Globoplay**: Dados Kantar IBOPE; Integração com ecossistema Globo (TV + digital); Histórico de visualização; Dados de Globo ID
- **Dispositivo / Plataforma**: Smart TV; Mobile (iOS/Android); Desktop/Web; Tablet; Chromecast; Apple TV; Fire TV

### Segmentações com exemplo de uso

- **Novelas**
  - Quando: Lançamento de capítulos e episódios com alta retenção
  - Exemplo: Veicular Video Ads ou Pre-roll alinhados à estreia de capítulos ou temporadas de novelas presentes na plataforma
- **Jornalismo e telejornais**
  - Quando: Blocos de notícias e coberturas jornalísticas de maior alcance
  - Exemplo: Inserir Mid-roll ou Video Ads de curta duração durante intervalos de telejornais ou reportagens relevantes
- **Reality shows (ex.: BBB)**
  - Quando: Exibições semanais, recaps e conteúdos ao vivo relacionados ao reality
  - Exemplo: Campanhas com Pre-roll e Pause Ads para aproveitar picos de audiência em episódios e conteúdos complementares
- **Eventos ao vivo**
  - Quando: Transmissões ao vivo (esportes, shows, eventos especiais)
  - Exemplo: Utilizar Pre-roll e anúncios durante a transmissão ao vivo para alcance em tempo real e engajamento imediato
- **Audiência feminina**
  - Quando: Lançamentos de produtos/serviços com apelo principal ao público feminino
  - Exemplo: Segmentação para público feminino (plataforma indica ~58% feminino) com criativos e mensagens otimizadas para esse perfil
- **CTV-first / tela grande**
  - Quando: Campanhas que priorizam experiência imersiva e storytelling em sala de estar
  - Exemplo: Utilizar Video Ads 16:9 otimizados para CTV para maior impacto visual e recall de marca

### Fontes

- https://ajuda.globoads.globo.com/s/article/Perguntas-frequentes-sobre-an%C3%BAncios-digitais
- https://globoads.globo.com/para-o-seu-negocio/anunciar-no-globoplay
- https://globoads.globo.com/para-o-seu-negocio/anunciar-no-globoplay/intervalo-globoplay
- https://globoads.globo.com/upfront/2026/globoplay


---

## Paramount+
<a id="paramount-plus"></a>

`slug: paramount-plus` · categoria **Streaming** · tipo **ctv** · cor da marca `#0064FF`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/paramount-plus.png)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/paramount-plus.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/paramount-plus-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/canais/paramount-plus.png
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/paramount-plus.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/paramount-plus-b.webp

### Descrição

Streaming premium com conteúdo exclusivo da Paramount, MTV, Nickelodeon, Comedy Central e mais.

**Perfil de audiência**: Público amplo de streaming premium no Brasil.

**Melhor uso**: Mais indicado para awareness e consideração de marca em ambiente premium de streaming, com reforço em esportes e entretenimento.

### Copy pronta para LP (`lp_data`)

- **Badge**: Streaming familiar + esportes – 8M assinantes BR
- **Meta title**: Anuncie no Paramount+ | Famílias, esportes e entretenimento

### Números

- **Alcance**: +8M assinantes BR
- **Usuários únicos**: 8M
- **Tempo médio**: 1.2h/dia
- **Viewability (%)**: 97
- **Completion rate (%)**: 93
- **Taxa de engajamento (%)**: 88
- **Prazo de entrega**: 7 dias úteis
- **Integração**: Deal ID via DSP
- **Modelo de compra**: CPM
- **Brand safety**: Paramount Guidelines, IAS
- **Medição**: Nielsen; Comscore

**Demografia**

- Gênero: 45% homens / 55% mulheres
- Idade: 18–24: 20% · 25–34: 28% · 35–44: 30% · 45–54: 14% · 55+: 8%
- Classe: C: 32% · AB: 62% · DE: 6%

### Diferenciais

- Conteúdo infantil premium (Nickelodeon)
- Público jovem via MTV
- Filmes em lançamento
- Futebol - Champions League

### Formatos

Resumo: Video Ads · Pre-roll · Pause Ads · Branded Content

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Pause Ads | 300×250 | momentos de pausa no streaming em tela de TV | ctv |
| Pre-roll | Pre-roll | abertura de conteúdo em streaming | ctv |
| Video Ads | 16:9 | vídeo em conteúdo premium de streaming | ctv |
| Branded Content | 1.91:1 | projetos customizados com conteúdo premium | ctv |

**Especificações técnicas**

- **Video Ad** — peso: até 75MB; duracao: 15s ou 30s; formato: MP4 H.264
- **Pause Ad** — peso: até 400KB; formato: JPG/PNG; dimensao: 1920x1080

### Segmentações disponíveis

- **Temporal**: Dayparting; Horários de programação infantil; Eventos esportivos ao vivo
- **Contextual / Conteúdo**: Por canal/marca (Nickelodeon, MTV, Comedy Central, BET, Smithsonian); Gênero de conteúdo (infantil, comédia, drama, esportes, reality); Conteúdo infantil (Nick Jr., Bob Esponja, Patrulha Canina); Esportes ao vivo (Champions League, Libertadores)
- **Geográfica**: País; Estado/Região; Cidade
- **Demográfica**: Idade (18-65+); Gênero; Perfil familiar (com/sem filhos)
- **Comportamental**: Famílias com crianças (perfis kids); Heavy viewers vs light viewers; Público jovem (consumidores MTV); Fãs de esportes
- **Dispositivo / Plataforma**: Smart TV; Mobile (iOS/Android); Desktop/Web; Tablet; Console (PS/Xbox)

### Segmentações com exemplo de uso

- **Esportes**
  - Quando: futebol e NFL
  - Exemplo: Jogos e mesas
- **Filmes e franquias**
  - Quando: marca em conteúdo
  - Exemplo: Cinema Paramount
- **Horário**
  - Quando: noite CTV
  - Exemplo: Prime time
- **Praça**
  - Quando: teste BR
  - Exemplo: Sudeste

### Fontes

- https://adsmanager.paramount.com/insights/ctv-advertising-platforms
- https://legal.paramount.com/br/pt/pplus/termsofuse
- https://paramountforbusiness.com.br/
- https://www.centralcomm.media/canal/paramount-plus
- https://www.meioemensagem.com.br/midia/stremings-publicidade


---

## Samsung TV Plus
<a id="samsung-tv-plus"></a>

`slug: samsung-tv-plus` · categoria **Streaming** · tipo **ctv** · cor da marca `#1428A0`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/samsung-tv-plus.svg)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/samsung-tv-plus.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/samsung-tv-plus-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/canais/samsung-tv-plus.svg
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/samsung-tv-plus.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/samsung-tv-plus-b.webp

### Descrição

Streaming gratuito pré-instalado em mais de 20 milhões de Smart TVs Samsung no Brasil. Acesso direto à tela inicial — sem app, sem login.

**Perfil de audiência**: Públicos mencionados publicamente pela Samsung incluem famílias da geração millennial e espectadores influentes. A própria Samsung Ads também cita audiência premium com 68% classe A/B em materiais comerciais do Brasil.

**Melhor uso**: Boa opção para branding, alcance incremental e segmentação em CTV/streaming com ambiente premium e inventário de TV conectada.

### Números

- **Alcance**: +22,4M usuários BR
- **Usuários únicos**: 20M
- **Tempo médio**: 1h12min/dia
- **Viewability (%)**: 97
- **Completion rate (%)**: 95
- **Taxa de engajamento (%)**: 88
- **Prazo de entrega**: 7 dias úteis
- **Integração**: Samsung Ads DSP / DV360 / The Trade Desk
- **Modelo de compra**: CPM, CPV, Reserva (Home Screen)
- **Brand safety**: Samsung Ads Guidelines, Ambiente 100% curado
- **Medição**: Samsung Analytics; Nielsen DAR; ACR Cross-device

**Demografia**

- Gênero: 50% homens / 50% mulheres
- Idade: 18–24: 14% · 25–34: 27% · 35–44: 30% · 45–54: 18% · 55+: 11%
- Classe: C: 28% · AB: 68% · DE: 4%

### Diferenciais

- Acesso à tela inicial — primeiro ponto de contato ao ligar a TV
- Audiência premium: 68% classe A/B
- Dados exclusivos de ACR
- Sem necessidade de app ou login
- Samsung é líder de mercado de TVs no Brasil (34%)
- Mensuração cross-device

### Formatos

Resumo: Video Ads (Pre/Mid-roll) · Home Screen Ads · First Screen Takeover · Masthead · Native Ads

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Video Ads | 16:9 | FAST sem assinatura | ctv |
| Pause Ads | 300×250 | marca no canal FAST | ctv |

**Especificações técnicas**

- **Video Ad** — peso: até 50MB; duracao: 15s ou 30s; formato: MP4 H.264
- **Home Screen Ad** — peso: até 300KB; formato: JPG/PNG; dimensao: 1920x1080
- **First Screen Takeover** — peso: até 50MB; formato: MP4/JPG; dimensao: 1920x1080
- **Masthead** — peso: até 200KB; formato: JPG/PNG; dimensao: 1920x360

### Segmentações disponíveis

- **Contextual / Conteúdo**: Canal ao vivo em exibição; Categoria de conteúdo; Conteúdo on demand vs ao vivo
- **Geográfica**: País; Estado/UF; Cidade; Região metropolitana; CEP
- **Demográfica**: Idade; Gênero; Renda presumida (baseada no modelo de TV); Perfil familiar
- **Comportamental**: Frequência de uso da TV; Tempo de tela diário; Hábitos de consumo de conteúdo; First Screen viewers
- **Dados Exclusivos Samsung (ACR)**: ACR - Automatic Content Recognition; Dados de apps instalados e usados na TV; Histórico completo de conteúdo assistido; Cross-device via ecossistema Samsung; Samsung = 34% das TVs no Brasil
- **Dispositivo / Modelo**: Modelo de TV Samsung (QLED, Neo QLED, Crystal UHD, The Frame); Tamanho de tela (32" a 85"+); Ano de fabricação
- **Audiências Customizadas**: Retargeting; CRM Match via Samsung Ads DSP; Lookalike Audiences; Segmentos cross-device

### Segmentações com exemplo de uso

- **Socioeconômica**
  - Quando: Campanhas de posicionamento premium ou lançamento de produto com foco em alto poder aquisitivo
  - Exemplo: Alvo em Classe A/B (audiência premium: 68% Classe A/B)
- **Geográfica**
  - Quando: Ativações regionais, promoções locais ou lançamento por mercado
  - Exemplo: Segmentar por estado ou cidade — ex.: São Paulo capital
- **Por conteúdo / gênero**
  - Quando: Quando a mensagem precisa estar alinhada ao tipo de programa (esporte, notícias, entretenimento)
  - Exemplo: Usuários que consomem canais de esporte para promoção de produtos relacionados a fitness
- **Comportamental (ACR)**
  - Quando: Campanhas orientadas a intenção ou afinidade usando sinais de ACR
  - Exemplo: Público com sinais de interesse em automóveis identificado via dados ACR
- **Tela inicial / descoberta**
  - Quando: Lançamentos e campanhas de awareness que se beneficiam de alta visibilidade imediata
  - Exemplo: Home Screen Takeover para promover nova série ou produto no primeiro ponto de contato
- **Dayparting (horário)**
  - Quando: Otimização de entrega para horários com maior engajamento do público-alvo
  - Exemplo: Exibir criativos focados em família no horário nobre (ex.: 20h–23h)

### Fontes

- https://news.samsung.com/br/samsung-ads-chega-ao-brasil-como-nova-opcao-de-midia-nas-tvs-samsung
- https://news.samsung.com/br/samsung-tv-plus-atinge-88-milhoes-de-usuarios-ativos-mensais-globalmente
- https://news.samsung.com/br/samsung-tv-plus-inicia-2026-com-mais-de-100-milhoes-de-usuarios-ativos-mensais
- https://variety.com/2025/tv/global/sofa-digital-fast-brazil-1236410625
- https://www.centralcomm.media/canal/samsung-tv-plus
- https://www.samsung.com/br/tvs/smart-tv/samsung-tv-plus/


---

## Disney+
<a id="disney-plus"></a>

`slug: disney-plus` · categoria **Streaming** · tipo **ctv** · cor da marca `#1A6DFF`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/creative-viewers/disney-plus.png)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/disney-plus.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/disney-plus-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/creative-viewers/disney-plus.png
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/disney-plus.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/disney-plus-b.webp

### Descrição

Streaming premium da Disney com conteúdo Marvel, Star Wars, Pixar, National Geographic e Star.

**Perfil de audiência**: Público amplo de streaming no Brasil, com forte presença de entretenimento familiar e esportes.

**Melhor uso**: Bom para awareness e consideração em streaming premium, especialmente em entretenimento, família e esportes, com forte apelo para marcas que buscam contexto seguro e segmentação por audiência.

### Copy pronta para LP (`lp_data`)

- **Badge**: Streaming premium familiar
- **Meta title**: Anuncie no Disney+ | Famílias e fans imersos
- **Stat principal**: **1,5h** — por dia de sessão familiar
- **Stat secundaria**: **96%** — completam o anúncio
- **Stat terciaria**: **+72%** — crescimento de streaming income (Q1 2026)

### Números

- **Alcance**: +15M assinantes BR
- **Usuários únicos**: 15M
- **Tempo médio**: 1.5h/dia
- **Viewability (%)**: 98
- **Completion rate (%)**: 96
- **Taxa de engajamento (%)**: 92
- **Prazo de entrega**: 10 dias úteis
- **Integração**: Disney Ads / DSP
- **Modelo de compra**: CPM
- **Brand safety**: Disney Content Guidelines
- **Medição**: Nielsen; Comscore

**Demografia**

- Gênero: 48% homens / 52% mulheres
- Idade: 18–24: 20% · 25–34: 30% · 35–44: 28% · 45–54: 14% · 55+: 8%
- Classe: C: 28% · AB: 68% · DE: 4%

### Diferenciais

- Conteúdo premium familiar
- Franquias icônicas (Marvel, Star Wars)
- Ambiente 100% brand safe
- Audiência premium engajada

### Formatos

Resumo: Video Ads 15s/30s · Pre-roll · Mid-roll

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Video Ads 15s/30s (pre-roll e mid-roll) | 16:9 | campanhas em ambiente premium de streaming, em conteúdos on demand e ao vivo | ctv |
| Pause Ads | 300×250 | presença de marca no momento em que o usuário pausa o conteúdo, sem interromper a experiência | ctv |
| Pause+ (Billboard / Trivia / Carousel dentro de Pause Ads) | 300×250 | experiências interativas de marca durante a pausa, com unidades mais ricas (billboard, trivia, carrossel) | ctv |
| Gateway Go | 16:9 | ações de performance ou consideração com oferta/lembrança que o usuário pode acionar via clique, QR code ou notificações | ctv, mobile |
| Ad Selector | 16:9 | campanhas focadas em engajamento, permitindo ao usuário escolher qual criativo assistir | ctv |

**Especificações técnicas**

- **Video Ad** — peso: até 100MB; duracao: 15s ou 30s; formato: MP4 H.264

### Segmentações disponíveis

- **Contextual / Conteúdo**: Por franquia (Marvel, Star Wars, Pixar, Disney Animation, National Geographic); Gênero de conteúdo; Conteúdo infantil vs adulto (Star); Lançamentos e estreias exclusivas
- **Geográfica**: País; Estado/Região; Cidade
- **Demográfica**: Idade (18-65+); Gênero; Perfil familiar (com/sem filhos); Idioma
- **Comportamental**: Famílias (perfis kids ativos); Fãs de franquias específicas; Heavy viewers vs light viewers; Assinante do plano com anúncios
- **Dados Exclusivos Disney**: Disney first-party data; Perfil de afinidade por franquia; Disney Select audiences
- **Dispositivo / Plataforma**: Smart TV; Mobile; Desktop/Web; Tablet; Console; Chromecast; Apple TV; Fire TV

### Segmentações com exemplo de uso

- **Plano Disney+ Padrão com anúncios (assinantes ad-supported)**
  - Quando: ao comprar inventário em vídeo em conteúdos on demand de assinantes do plano com anúncios
  - Exemplo: segmentar campanhas apenas para quem está no plano Padrão com anúncios, que exibe intervalos comerciais antes e durante a maioria dos filmes e séries.
- **Conteúdos ao vivo e eventos especiais**
  - Quando: em transmissões ao vivo, reprises e eventos especiais dentro do Disney+ que aceitam anúncios em todos os planos
  - Exemplo: ativar campanhas em conteúdos ao vivo e eventos especiais, com inserções antes/depois da reprodução, patrocínios e placements.
- **Franquias e marcas de conteúdo Disney**
  - Quando: ao planejar campanhas associadas a universos como Marvel, Star Wars, Pixar, National Geographic e Star
  - Exemplo: comprar pacotes ou posicionamentos em conteúdos de franquias específicas para reforço de afinidade com fãs de Marvel ou Star Wars.
- **Momento de pausa do conteúdo (Pause / Pause+)**
  - Quando: quando o usuário aciona o pause durante um filme ou série
  - Exemplo: segmentar a entrega de Pause Ads ou Pause+ para impactar o usuário apenas quando ele pausa o conteúdo, aproveitando o momento de atenção estática.
- **Experiências interativas DXC (Gateway Go, Pause+, Ad Selector)**
  - Quando: ao usar formatos avançados que pedem ação do usuário (clique, escolha de criativo, interação com trivia/carrossel)
  - Exemplo: ativar Gateway Go com ofertas clicáveis ou Ad Selector permitindo ao usuário escolher o filme ou criativo da marca que deseja ver.
- **Promoções e produtos Disney (owned media)**
  - Quando: em campanhas de cross-promo dentro dos próprios planos com ou sem anúncios
  - Exemplo: usar espaços de promoções e patrocínios para divulgar outros produtos/serviços Disney dentro de Disney+.

### Fontes

- https://imprensa.disney.com.br/novidades/magia-comercial-as-campanhas-e-ativacoes-de-2024-inspiradas-em-historias-e-personagens-disney
- https://mercadoeconsumo.com.br/02/07/2024/retail-media/mercado-ads-anuncia-alianca-com-disney-para-retail-media-com-70-da-sua-capacidade-vendida/
- https://telaviva.com.br/17/12/2025/disney-e-amazon-ads-anunciam-colaboracao-programatica-no-brasil/
- https://www.centralcomm.media/canal/disney-plus
- https://www.disneyplus.com/en-br
- https://www.senalnews.com/es/digital/mas-de-60-anunciantes-eligen-disney-para-llegar-a-audiencias-de-america-latina


---

## Prime Video
<a id="prime-video"></a>

`slug: prime-video` · categoria **Streaming** · tipo **ctv** · cor da marca `#00A8E1`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/prime-video.svg)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/prime-video.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/prime-video-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/canais/prime-video.svg
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/prime-video.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/prime-video-b.webp

### Descrição

Streaming da Amazon com conteúdo original, filmes e séries. Integração com ecossistema Amazon.

**Perfil de audiência**: Prime Video no Brasil passou a ter anúncios limitados a partir de 2025, com opção sem anúncios para quem desejar. O serviço se posiciona como alcance amplo em streaming premium, com foco em membros Prime e audiência de entretenimento/esportes ao vivo.

**Melhor uso**: Indicado para awareness e consideração em ambiente de streaming premium, especialmente em campanhas que queiram combinar vídeo, entretenimento e sinais first-party da Amazon.

### Copy pronta para LP (`lp_data`)

- **Badge**: Streaming + Esportes + Dados Amazon
- **Meta title**: Anuncie no Prime Video | Esportes ao vivo, filmes e dados Amazon
- **Stat principal**: **128M** — assinantes Prime nos EUA
- **Stat secundaria**: **+22%** — crescimento da receita de ads YoY
- **Stat terciaria**: **US$21,3B** — receita de ads Amazon Q4 2025

### Números

- **Alcance**: +12M assinantes BR
- **Usuários únicos**: 12M
- **Tempo médio**: 1.3h/dia
- **Viewability (%)**: 97
- **Completion rate (%)**: 94
- **Taxa de engajamento (%)**: 88
- **Prazo de entrega**: 7 dias úteis
- **Integração**: Amazon DSP
- **Modelo de compra**: CPM
- **Brand safety**: Amazon Brand Safety
- **Medição**: Amazon Attribution; Nielsen

**Demografia**

- Gênero: 52% homens / 48% mulheres
- Idade: 18–24: 18% · 25–34: 32% · 35–44: 28% · 45–54: 14% · 55+: 8%
- Classe: C: 24% · AB: 72% · DE: 4%

### Diferenciais

- Dados de compra Amazon integrados
- Audiência Prime alto ticket
- Thursday Night Football
- Cross-device com Fire TV

### Formatos

Resumo: Video Ads 15s/30s · Pre-roll · Pause Ads

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Video Ads | 16:9 | branding no Prime | ctv, mobile |
| Pre-roll | Pre-roll | abertura de título | ctv |
| Pause Ads | 300×250 | marca no intervalo | ctv |

**Especificações técnicas**

- **Video Ad** — peso: até 100MB; duracao: 15s ou 30s; formato: MP4 H.264

### Segmentações disponíveis

- **Contextual / Conteúdo**: Gênero de conteúdo; Conteúdo original Amazon vs licenciado; Thursday Night Football / esportes ao vivo; Séries vs Filmes
- **Geográfica**: País; Estado/UF; Cidade; CEP
- **Demográfica**: Idade (18-65+); Gênero; Renda presumida; Idioma
- **Comportamental**: Compradores Prime (assinantes ativos); Hábitos de compra na Amazon; Heavy viewers vs light viewers; Usuários Fire TV vs outros
- **Dados Exclusivos Amazon**: Histórico de compras na Amazon; Dados de navegação no marketplace; Prime membership data; Amazon Attribution; Dados Fire TV; Cross-device via ecossistema Amazon
- **Audiências Customizadas**: Amazon Audiences: In-Market; Amazon Audiences: Lifestyle; CRM Match via Amazon DSP; Lookalike Audiences; Retargeting

### Segmentações com exemplo de uso

- **Membros Prime**
  - Quando: Quando a campanha mira audiência engajada com maior propensão à compra e retenção.
  - Exemplo: Alvo: membros Prime que consomem séries originais e ofertas exclusivas.
- **Dados de compra Amazon**
  - Quando: Quando quiser alinhar criativos a comportamento de compra e intenção de compra clara.
  - Exemplo: Alvo: usuários que demonstraram interesse ou compraram categorias relacionadas ao produto anunciado.
- **Fãs de esportes / transmissões ao vivo**
  - Quando: Durante eventos esportivos ou para aproveitar alto engajamento em transmissões ao vivo.
  - Exemplo: Alvo: espectadores de transmissões como Thursday Night Football para promoções relacionadas a esportes.
- **Proprietários de Fire TV / cross-device**
  - Quando: Quando a estratégia exige alcance otimizado em TV conectada e mensuração cross-device.
  - Exemplo: Alvo: usuários com Fire TV para promover apps, serviços ou ofertas específicas para TV.
- **Contextual por gênero/conteúdo**
  - Quando: Quando a mensagem deve estar alinhada ao tipo de conteúdo assistido (série, filme, comédia).
  - Exemplo: Alvo: espectadores de comédias para campanhas de marcas com tom leve e humorístico.
- **Demografia e perfil de renda**
  - Quando: Para campanhas de produtos/serviços premium ou segmentação por poder aquisitivo.
  - Exemplo: Alvo: públicos com perfil de maior poder aquisitivo para lançamentos de marca premium.

### Fontes

- https://advertising.amazon.com/library/news/unboxed-prime-video-advertising
- https://advertising.amazon.com/products/prime-video-ads
- https://www.aboutamazon.com.br/noticias/entretenimento/agora-voce-pode-interagir-com-marcas-enquanto-assiste-streaming-sem-perder-nenhuma-cena
- https://www.aboutamazon.com.br/noticias/entretenimento/uma-atualizacao-sobre-o-prime-video


---

## Max (HBO)
<a id="hbo-max"></a>

`slug: hbo-max` · categoria **Streaming** · tipo **ctv** · cor da marca `#5822B4`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/hbo-max.svg)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/hbo-max.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/hbo-max-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/canais/hbo-max.svg
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/hbo-max.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/hbo-max-b.webp

### Descrição

Streaming premium com conteúdo HBO, Warner Bros, DC e Discovery. Séries aclamadas e filmes blockbuster.

**Perfil de audiência**: Público amplo e premium, com plano com anúncios voltado a consumidores que aceitam publicidade em troca de preço mais acessível.

**Melhor uso**: Boa opção para campanhas de alcance e brand safety em ambiente premium de streaming, especialmente em lançamentos, franquias fortes e eventos ao vivo.

### Copy pronta para LP (`lp_data`)

- **Badge**: Streaming premium HBO – 10M assinantes BR
- **Meta title**: Anuncie no Max (HBO) | Séries premium, audiência premium
- **Stat principal**: **1,4h** — por dia em séries e filmes premium
- **Stat secundaria**: **95%** — completion rate
- **Stat terciaria**: **70%** — audiência classe A/B

### Números

- **Alcance**: +10M assinantes BR
- **Usuários únicos**: 10M
- **Tempo médio**: 1.4h/dia
- **Viewability (%)**: 98
- **Completion rate (%)**: 95
- **Taxa de engajamento (%)**: 90
- **Prazo de entrega**: 10 dias úteis
- **Integração**: Warner Bros Discovery Ads
- **Modelo de compra**: CPM
- **Brand safety**: HBO Content Guidelines
- **Medição**: Nielsen; Comscore

**Demografia**

- Gênero: 50% homens / 50% mulheres
- Idade: 18–24: 22% · 25–34: 32% · 35–44: 26% · 45–54: 13% · 55+: 7%
- Classe: C: 26% · AB: 70% · DE: 4%

### Diferenciais

- Séries premium (House of the Dragon, The Last of Us)
- Conteúdo HBO aclamado pela crítica
- Audiência premium e engajada
- Ambiente brand safe

### Formatos

Resumo: Video Ads 15s/30s · Pre-roll · Mid-roll

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Video Ads | 16:9 | branding em streaming premium | ctv |
| Pre-roll | Pre-roll | impacto de abertura | ctv |
| Mid-roll | Mid-roll | captura de atenção durante consumo longo | ctv |
| Pause ads | 300×250 | mensagem de alta lembrança em pausa | ctv |
| Takeover | 970×250 | domínio de um conteúdo/abertura do dia | ctv |
| Brand Block | 16:9 | exclusividade em conteúdo | ctv |
| Sequential Ads | 16:9 | narrativa sequencial em campanhas | ctv |

**Especificações técnicas**

- **Video Ad** — peso: até 100MB; duracao: 15s ou 30s; formato: MP4 H.264

### Segmentações disponíveis

- **Contextual / Conteúdo**: Gênero de conteúdo; Por série/título (House of the Dragon, The Last of Us, Succession, White Lotus); Por marca (HBO, Warner Bros, DC, Discovery, CNN); Conteúdo premium HBO vs catálogo Warner/Discovery
- **Geográfica**: País; Estado/Região; Cidade
- **Demográfica**: Idade (18-65+); Gênero; Idioma
- **Comportamental**: Heavy viewers vs light viewers; Binge watchers; Fãs de séries HBO premium; Assinante do plano com anúncios
- **Dados Exclusivos WBD/Max**: Warner Bros Discovery first-party data; Perfil de afinidade por conteúdo; Cross-platform data (Discovery+, CNN, HBO)
- **Dispositivo / Plataforma**: Smart TV; Mobile; Desktop/Web; Tablet; Console; Apple TV; Chromecast

### Segmentações com exemplo de uso

- **Brand safety por conteúdo premium**
  - Quando: quando a campanha precisa aparecer ao lado de séries e filmes premium
  - Exemplo: inserção em conteúdo de alto valor de marca dentro do catálogo Max
- **Contexto de conteúdo em gêneros**
  - Quando: quando a compra usa afinidade editorial por gênero ou tema
  - Exemplo: esportes, drama, infantil, documentários
- **Eventos ao vivo**
  - Quando: quando a campanha quer acompanhar transmissões live
  - Exemplo: Paulistão com inserção dinâmica de anúncios
- **1st party do plano com anúncios**
  - Quando: quando a ativação considera somente inventário do plano Básico com anúncios
  - Exemplo: entrega para assinantes do plano ad-supported
- **Frequência e controle de exposição**
  - Quando: quando a campanha exige limitação de repetição
  - Exemplo: limite de frequência por marca
- **Segurança de marca**
  - Quando: quando a compra precisa de ambientes selecionados e qualificados
  - Exemplo: associação a conteúdo selecionado de alta qualidade

### Fontes

- https://www.adnews.com.br/max-chega-ao-brasil-com-novas-oportunidades-comerciais
- https://www.centralcomm.media/canal/hbo-max
- https://www.omelete.com.br/hbo-max/max-e-hbo-bateram-110-milhoes-de-assinantes
- https://www.thedailytelevision.com/articulo/publicidad/max-abre-nuevas-oportunidades-comerciales-para-anunciantes-en-latam
- https://www.wbdforbrands.com.br/landing/oportunidades-hbo-max/


---

# Áudio / Streaming de áudio


---

## Spotify
<a id="spotify"></a>

`slug: spotify` · categoria **Streaming** · tipo **audio** · cor da marca `#1DB954`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/spotify.svg)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/spotify.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/spotify-b.webp)  
![Pessoa ouvindo música com fones](https://images.unsplash.com/photo-1611339555312-e607c8352fd7?w=800&q=80)  
![Jovem curtindo playlist](https://images.unsplash.com/photo-1625786682948-2168238883d2?w=800&q=80)  
![Momento de música e concentração](https://images.unsplash.com/photo-1661922030470-1519f30ac424?w=800&q=80)  

- Logo: https://planner.centralcomm.media/static/images/canais/spotify.svg
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/spotify.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/spotify-b.webp
- Pessoa ouvindo música com fones: https://images.unsplash.com/photo-1611339555312-e607c8352fd7?w=800&q=80
- Jovem curtindo playlist: https://images.unsplash.com/photo-1625786682948-2168238883d2?w=800&q=80
- Momento de música e concentração: https://images.unsplash.com/photo-1661922030470-1519f30ac424?w=800&q=80

### Descrição

A maior plataforma de streaming de áudio do mundo, com mais de 50 milhões de ouvintes no Brasil. Ideal para campanhas de awareness e branding com alta taxa de completion.

**Perfil de audiência**: Spotify é uma plataforma massiva de streaming no Brasil, com alcance em usuários de música e podcasts, especialmente em audiências mobile e em momentos de atenção ativa.

**Melhor uso**: Melhor para alcance em áudio com alta atenção, reforço de marca e ativações combinando áudio, vídeo e display.

### Copy pronta para LP (`lp_data`)

- **Badge**: Áudio #1 no mundo – 696M ouvintes
- **Headline**: Sua marca nos fones<br><span class="gradient-text">de quem decide</span>
- **Subhead**: Com 696 milhões de ouvintes mensais e parceria inédita com Amazon DSP, o Spotify escala anúncios programáticos em 2026.
- **Meta title**: Anuncie no Spotify | Onde o Brasil escuta
- **Meta description**: Mais de 696 milhões de ouvintes globais. Áudio programático escala em 2026 com parcerias Amazon DSP e Yahoo.
- **Stat principal**: **45 min** — por dia com os fones no ouvido
- **Stat secundaria**: **95%** — completam o anúncio de áudio
- **Stat terciaria**: **696M** — ouvintes mensais globais (2025)

**Cards de formato da LP**

| Ícone (Font Awesome) | Nome | Descrição |
|---|---|---|
| `fa-volume-up` | Áudio 15s ou 30s | Anúncio entre músicas ou episódios. Não skipável, 95% completion. |
| `fa-list` | Playlist patrocinada | Sua marca no topo de playlists curadas. |
| `fa-tv` | Video Takeover | Display em tela cheia quando o app está aberto. |
| `fa-podcast` | Podcast Ads | Anúncios em podcasts brasileiros de alto alcance. |
| `fa-clock` | Sponsored Sessions | 30 minutos de música sem interrupção em troca de um anúncio. |

### Números

- **Alcance**: +56M usuários BR
- **Usuários únicos**: 50M
- **Tempo médio**: 45 min/dia
- **Viewability (%)**: 98
- **Completion rate (%)**: 95
- **Taxa de engajamento (%)**: 92
- **Prazo de entrega**: 5 dias úteis
- **Integração**: Deal ID via DSP (DV360, TTD)
- **Modelo de compra**: CPM, CPCV
- **Brand safety**: IAS, DoubleVerify, MOAT
- **Medição**: Nielsen DAR; Comscore; Kantar

**Demografia**

- Gênero: 52% homens / 48% mulheres
- Idade: 18–24: 28% · 25–34: 35% · 35–44: 22% · 45–54: 10% · 55+: 5%
- Classe: C: 30% · AB: 65% · DE: 5%

### Diferenciais

- Único player com acesso a playlists patrocinadas no Brasil
- Segmentação por momento do dia (workout, relax, focus)
- Dados exclusivos de humor e atividade do usuário
- Audio ads não skipáveis com 95%+ completion rate

### Formatos

Resumo: Audio Ads 15s/30s · Sponsored Playlist · Video Takeover · Podcast Ads · Sponsored Sessions

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Audio Ads (Music & Podcasts / Audio Everywhere) | 15s/30s | cobertura em escala em música e podcasts com presença constante de marca entre faixas de áudio | audio, mobile, desktop, tablet, app |
| Video Ads (Video Takeover / Mobile Overlay) | 970×250 | impacto visual com som ligado em momentos de tela ativa dentro do app | mobile, desktop, tablet, app |
| Sponsored Session | 15s/30s | troca clara de valor para brand awareness e consideração, oferecendo sessão sem anúncios após ver o vídeo | mobile, app |
| Sponsored Playlist | Playlist | associação prolongada da marca a playlists de alto consumo em momentos de uso recorrente | mobile, desktop, tablet, app, audio |
| Podcast Ads | Podcast | afinidade e profundidade de mensagem em conteúdos de nicho e audiências engajadas | audio, mobile, desktop, tablet, app |

**Especificações técnicas**

- **Audio Ad** — peso: até 1MB; duracao: 15s ou 30s; formato: MP3/OGG 192kbps
- **Video Takeover** — peso: até 50MB; formato: MP4 H.264; dimensao: 1920x1080
- **Display Companion** — peso: até 200KB; formato: JPG/PNG; dimensao: 640x640

### Segmentações disponíveis

- **Temporal**: Momento do dia (manhã, tarde, noite, madrugada); Dia da semana (úteis vs fins de semana); Sazonalidade (verão, inverno, festas, volta às aulas)
- **Contextual**: Playlist por contexto (Discover Weekly, Release Radar, Daily Mix); Categoria de podcast (true crime, comédia, negócios, saúde, etc.); Episódio de podcast específico; Gênero editorial curado pelo Spotify; Momento cultural/sazonal (Carnaval, Natal, Verão)
- **Geográfica**: País; Estado/Região; Cidade; CEP/Código postal
- **Demográfica**: Idade (faixas 13-65+); Gênero; Idioma
- **Comportamental**: Gênero musical preferido; Artista/Banda; Momento de escuta (workout, relax, focus, commute, cooking, party, sleep); Humor/Atividade do usuário; Frequência de escuta (heavy/medium/light listeners); Ouvintes de Podcast; Usuários Free vs Premium
- **Dados Exclusivos Spotify**: Spotify Wrapped data (perfil de gosto anual); Podcast preferences e histórico; Music taste profile (perfil de gosto musical); Real-time context signals (atividade atual do usuário)
- **Dispositivo / Plataforma**: iOS; Android; Desktop (Mac/Windows); Web Player; Smart Speaker (Alexa, Google Home); Connected TV (Smart TVs, Chromecast, Apple TV); Console (PlayStation, Xbox); Carro (Android Auto, Apple CarPlay)
- **Audiências Customizadas**: Streaming Intelligence (comportamento de escuta); CRM Match (upload de base de clientes); Lookalike Audiences; Retargeting (ouviu anúncio anterior); SAI - Spotify Advertising Intelligence

### Segmentações com exemplo de uso

- **Conteúdo: Música vs Podcasts**
  - Quando: ao definir se a campanha deve priorizar música, podcasts ou ambos no gerenciador de anúncios e nas linhas de pedido
  - Exemplo: marca de bens de consumo veicula Audio Ads em música para alcance amplo e reserva Podcast Ads apenas em programas de culinária e bem‑estar para aprofundar a mensagem
- **Momento de tela ativa (screen-on)**
  - Quando: ao comprar formatos de vídeo e Sponsored Session, que só são entregues quando o app está em foco na tela
  - Exemplo: campanha de lançamento usa Video Takeover direcionado a sessões em que o usuário está com o app em foco, garantindo exposição visual completa
- **Tipo de sessão de escuta (sessão patrocinada vs sessão regular)**
  - Quando: ao optar por Sponsored Session em vez de vídeo padrão, construindo experiência de ~30 minutos sem anúncios
  - Exemplo: marca de telecom ativa Sponsored Session para usuários free em mobile, oferecendo meia hora de música sem interrupções após o vídeo
- **Playlist e propriedade de inventário (Owned & Operated Playlists)**
  - Quando: ao selecionar Sponsored Playlist em listas proprietárias com grande volume de ouvintes recorrentes
  - Exemplo: marca de bebidas patrocina playlist de hits nacionais, com presença em todos os intervalos comerciais da playlist e destaque na página
- **Contexto de uso em áudio sem tela (screenless audio)**
  - Quando: ao focar em Audio Ads que alcançam usuários em momentos sem atenção à tela, como fones ou carro
  - Exemplo: marca automotiva direciona áudio para sessões de direção, priorizando mensagem sonora clara e call to action simples
- **Dispositivo e ambiente de app**
  - Quando: ao escolher entre entrega em mobile, desktop ou outros dispositivos, especialmente para formatos de vídeo
  - Exemplo: varejo prioriza Mobile Overlay e Video Takeover em smartphones, com criativos otimizados para mobile e landing pages responsivas
- **Segmentação por programa de podcast**
  - Quando: ao planejar compra de Podcast Ads em programas específicos alinhados ao público da marca
  - Exemplo: fintech concentra inserções em podcasts de finanças pessoais e empreendedorismo, usando host-read para aumentar credibilidade junto ao público.
- **Formato de troca de valor (value exchange advertising)**
  - Quando: ao usar Sponsored Session ou playlists patrocinadas que oferecem benefício claro ao usuário em troca de atenção ao anúncio
  - Exemplo: marca de e-commerce ativa Sponsored Session comunicando explícito “assista ao nosso vídeo e ganhe 30 minutos de música sem anúncios”, reforçando percepção positiva de marca.

### Fontes

- https://ads.spotify.com/en-US/display-advertising/
- https://ads.spotify.com/pt-BR/ad-formats/
- https://ads.spotify.com/pt-BR/ad-measurement/
- https://ads.spotify.com/pt-BR/experiencias-publicitarias/
- https://ads.spotify.com/pt-BR/noticias-insights/spotify-musica-ao-vivo-brasil/
- https://adshelp.spotify.com/HelpCenter/s/article/Campanhas-anuncios-e-grupos-de-anuncios-BR?language=pt_BR


---

## Deezer
<a id="deezer"></a>

`slug: deezer` · categoria **Streaming** · tipo **audio** · cor da marca `#A238FF`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/deezer.png)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/deezer.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/deezer-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/canais/deezer.png
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/deezer.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/deezer-b.webp

### Descrição

Plataforma de streaming musical com forte presença no Brasil e América Latina. Parceria exclusiva com operadoras de telecom.

**Melhor uso**: Boa para alcance incremental em audiência engajada com música e áudio, especialmente em campanhas de awareness e consideração com segmentação contextual e demográfica.

### Copy pronta para LP (`lp_data`)

- **Badge**: Áudio premium Brasil – 16M ouvintes
- **Headline**: Sua marca nos fones<br><span class="gradient-text">do Brasil inteiro</span>
- **Subhead**: Com 16 milhões de ouvintes e parcerias exclusivas com Vivo, Tim e Claro, o Deezer oferece áudio ads com 93% de completion rate.
- **Meta title**: Anuncie no Deezer | Áudio que conecta marcas no Brasil
- **Meta description**: 16 milhões de ouvintes no Brasil. Parceria exclusiva com Vivo, Tim e Claro. Áudio ads com 93% de completion rate.
- **Stat principal**: **38 min** — por dia ouvindo música e podcasts
- **Stat secundaria**: **93%** — completion rate em áudio ads
- **Stat terciaria**: **16M** — ouvintes ativos no Brasil

### Números

- **Alcance**: +16M ouvintes BR
- **Usuários únicos**: 16M
- **Tempo médio**: 38 min/dia
- **Viewability (%)**: 96
- **Completion rate (%)**: 93
- **Taxa de engajamento (%)**: 88
- **Prazo de entrega**: 5 dias úteis
- **Integração**: Deal ID via DSP
- **Modelo de compra**: CPM
- **Brand safety**: IAS, DoubleVerify
- **Medição**: Nielsen DAR; Comscore

**Demografia**

- Gênero: 48% homens / 52% mulheres
- Idade: 18–24: 25% · 25–34: 32% · 35–44: 25% · 45–54: 12% · 55+: 6%
- Classe: C: 38% · AB: 55% · DE: 7%

### Diferenciais

- Parceria exclusiva com Vivo, Tim e Claro
- Audiência com alto poder aquisitivo
- Flow - algoritmo de recomendação proprietário
- Forte presença em podcasts brasileiros

### Formatos

Resumo: Audio Ads 15s/30s · Display Ads · Sponsored Sessions · Podcast Ads

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Audio Ads | 15s/30s | mensagem em momentos de escuta com atenção plena | audio, mobile, desktop, tablet, app |
| Display Banner | 300×250 | reforço visual da campanha de áudio | mobile, desktop, tablet, app |
| Video / Pre-roll | Pre-roll | impacto de marca no início da sessão de escuta | mobile, desktop, tablet, app |
| Sponsored Editorial Playlist | 15s/30s | associação de marca a playlists curadas de alta afinidade | mobile, desktop, tablet, app |
| Sponsored Session / Escuta Patrocinada | 15s/30s | gerar percepção de marca generosa oferecendo sessão sem anúncios | audio, mobile, desktop, tablet, app |
| Sponsored Track | 15s/30s | descoberta imediata e aumento de plays de conteúdo específico | audio, mobile, desktop, tablet, app |

**Especificações técnicas**

- **Audio Ad** — peso: até 1MB; duracao: 15s ou 30s; formato: MP3 192kbps
- **Display Banner** — peso: até 150KB; formato: JPG/PNG/GIF; dimensao: 300x250

### Segmentações disponíveis

- **Contextual**: Flow (algoritmo de recomendação proprietário Deezer); Playlists editoriais e temáticas; Categoria de podcast; Gênero musical em reprodução
- **Geográfica**: País; Estado/UF; Cidade; Região metropolitana
- **Demográfica**: Idade (faixas 18-65+); Gênero; Idioma
- **Comportamental**: Gênero musical preferido; Frequência de escuta; Momento de escuta (workout, relax, estudo, festa); Ouvintes de Podcast; Usuários Free vs Premium; Novos usuários vs recorrentes
- **Dados Exclusivos Deezer**: Parceria exclusiva com operadoras (Vivo, Tim, Claro); Segmentação por operadora de telecom; Dados de usuários vinculados a planos de telefonia; Perfil de gosto musical via Flow
- **Dispositivo / Plataforma**: iOS; Android; Desktop; Web; Smart Speaker; Connected TV
- **Audiências Customizadas**: CRM Match; Lookalike Audiences; Retargeting

### Segmentações com exemplo de uso

- **Perfil Demográfico**
  - Quando: planejamento e setup de campanha
  - Exemplo: segmentação por idade e gênero para ajustar criativos a públicos como jovens adultos ou famílias.
- **Geo por País, Região e Cidade**
  - Quando: ativação em mercados ou praças específicas
  - Exemplo: campanhas focadas em Brasil, com recortes por estados ou grandes capitais para varejo e serviços locais.
- **Interesses Musicais e Afinidade de Gênero**
  - Quando: conteúdo e criação de playlists ou faixas patrocinadas
  - Exemplo: direcionar anúncios para ouvintes de rock, sertanejo ou eletrônico de acordo com o posicionamento da marca.
- **Contexto de Playlist / Momento de Uso**
  - Quando: estratégias de momento da jornada
  - Exemplo: ativar campanhas em playlists de treino, trabalho, relax ou festas para alinhar mensagem ao contexto de escuta.
- **Similaridade com Artistas / Conteúdo**
  - Quando: promoção de faixas patrocinadas ou colaborações
  - Exemplo: boostar uma faixa de artista novo para usuários que escutam artistas semelhantes, aumentando afinidade e conversão.
- **Device Targeting**
  - Quando: definição de formato e criativo
  - Exemplo: separar estratégias para usuários mobile versus desktop, ajustando duração, call to action e criativos.
- **Momento da Sessão de Escuta**
  - Quando: compra de formatos como pre-roll ou escuta patrocinada
  - Exemplo: impactar o usuário no início da sessão com pre-roll em vídeo ou oferecer uma sessão sem anúncios após um spot de áudio.
- **First-party Audio Behaviour**
  - Quando: otimização contínua via plataforma parceira
  - Exemplo: usar padrões de frequência de escuta, horários e tipos de conteúdo para refinar a entrega de campanhas ao longo do tempo.

### Fontes

- https://newsroom-deezer.com/2025/07/deezer-azerion-deal-in-brazil/
- https://newsroom-deezer.com/br/2025/07/deezer-e-azerion-anunciam-parceria-exclusiva-para-vendas-publicitarias-no-brasil/
- https://newsroom-deezer.com/br/2026/03/deezer-for-business-deezer-anuncia-plataforma-de-parcerias-reformulada-para-acelerar-nova-fase-de-crescimento/
- https://sensortower.com/blog/2024-q4-br-leading-3-Music---Podcasts-brands
- https://support.deezer.com/hc/en-gb/articles/36339056473629-Distribute-Deezer-in-Latin-America-if-you-are-an-ISP
- https://www.centralcomm.media/canal/deezer


---

## Amazon Music
<a id="amazon-music"></a>

`slug: amazon-music` · categoria **Streaming** · tipo **audio** · cor da marca `#FF9900`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/amazon-music.png)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/amazon-music.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/amazon-music-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/canais/amazon-music.png
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/amazon-music.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/amazon-music-b.webp

### Descrição

Serviço de streaming da Amazon com integração ao ecossistema Prime e dispositivos Alexa.

**Melhor uso**: Boa opção para awareness e consideração em momentos de escuta contínua, com alcance em ambientes sem tela e reforço visual via companion banner.

### Números

- **Alcance**: +8M ouvintes BR
- **Usuários únicos**: 8M
- **Tempo médio**: 32 min/dia
- **Viewability (%)**: 97
- **Completion rate (%)**: 94
- **Taxa de engajamento (%)**: 85
- **Prazo de entrega**: 7 dias úteis
- **Integração**: Amazon DSP
- **Modelo de compra**: CPM, CPCV
- **Brand safety**: Amazon Brand Safety
- **Medição**: Amazon Attribution; Nielsen

**Demografia**

- Gênero: 55% homens / 45% mulheres
- Idade: 18–24: 18% · 25–34: 30% · 35–44: 28% · 45–54: 15% · 55+: 9%
- Classe: C: 24% · AB: 72% · DE: 4%

### Diferenciais

- Integração com dados de compra Amazon
- Ads interativos via Alexa
- Audiência Prime com alto ticket médio
- Cross-device com Echo e Fire TV

### Formatos

Resumo: Audio Ads · Display Ads · Alexa Interactive Ads

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Audio Ads (spots em streaming) | 15s/30s | impacto em momentos de escuta em música e áudio premium no tier com anúncios do Amazon Music | audio, mobile, desktop, tablet, ctv |
| Podcast Audio Ads | 15s/30s | mensagens de marca em ambientes de podcast via inventário Amazon Music/Wondery/APD | audio, mobile, desktop, tablet |
| Programmatic 3P Audio (via Amazon DSP) | Áudio | escala e frequência em ecossistema de streaming de áudio além do Amazon Music, em compra única | audio, mobile, desktop, tablet, ctv |
| Programmatic 3P Audio (APD/Twitch/Spotify/iHeart/SiriusXM) | Áudio | escala e frequência em ecossistema de streaming de áudio além do Amazon Music, em compra única | audio, mobile, desktop, tablet, ctv |

**Especificações técnicas**

- **Audio Ad** — peso: até 1MB; duracao: 10s a 30s; formato: MP3/AAC
- **Alexa Interactive** — peso: N/A; duracao: 15s + resposta; formato: Audio + Script

### Segmentações disponíveis

- **Contextual**: Gênero musical em reprodução; Playlists temáticas; Estações de rádio por gênero; Interações com Alexa Skills
- **Geográfica**: País; Estado/UF; Cidade; CEP
- **Demográfica**: Idade; Gênero; Renda presumida; Idioma
- **Comportamental**: Gênero musical preferido; Frequência de escuta; Interações com Alexa (comandos de voz); Hábitos de compra na Amazon; Assinantes Prime vs não-Prime
- **Dados Exclusivos Amazon**: Histórico de compras na Amazon; Dados de navegação no marketplace; Status Prime; Alexa usage patterns; Amazon Attribution; Dados de Fire TV e Echo
- **Dispositivo / Plataforma**: iOS; Android; Desktop; Web; Echo / Alexa (Smart Speakers); Fire TV; Fire Tablet; Sonos e speakers compatíveis
- **Audiências Customizadas**: Amazon Audiences: In-Market; Amazon Audiences: Lifestyle; Amazon Audiences: Contextual; CRM Match via Amazon DSP; Lookalike Audiences; Retargeting

### Segmentações com exemplo de uso

- **Sinal de compra e comportamento em e-commerce Amazon**
  - Quando: campanhas focadas em conversão ou consideração para produtos vendidos na Amazon ou em categorias de varejo
  - Exemplo: segmentar ouvintes expostos a categorias como eletrônicos, beleza ou supermercado com base em sinais 1st party da Amazon
- **Contexto de audição em música streaming**
  - Quando: posicionamento de marca alinhado a gêneros, moods ou playlists específicos no Amazon Music
  - Exemplo: campanhas de bem-estar em playlists de relaxamento ou rotinas matinais, usando o tier com anúncios do Amazon Music como contexto de consumo
- **Dispositivo e ambiente (Echo, Fire TV, mobile, desktop)**
  - Quando: mensagens adaptadas ao ambiente de uso (casa, multitarefa, tela ligada ou só áudio)
  - Exemplo: priorizar inventário em smart speakers Echo para mensagens de rotina doméstica, ou em Fire TV/CTV para campanhas que combinam áudio em telas conectadas
- **Momento de escuta e dia/horário**
  - Quando: campanhas que querem estar presentes em rotinas específicas como commuting, trabalho ou fim de semana
  - Exemplo: otimizar entrega de spots em horários de pico de escuta, como início da manhã e fim de tarde
- **Segmentação por tipo de conteúdo (música vs. podcasts)**
  - Quando: definir se a mensagem é mais adequada para consumo rápido em música ou aprofundamento em podcasts
  - Exemplo: usar standard audio para awareness em música e podcast audio ads para storytelling em programas específicos distribuídos via Amazon Music/Wondery
- **Cobertura omnicanal via Amazon DSP**
  - Quando: campanhas que integram áudio a outros formatos (display, vídeo) dentro do stack Amazon Ads
  - Exemplo: usar audio ads em Amazon Music e 3P streaming combinados a display/vídeo na mesma estratégia de DSP, aplicando as mesmas audiências de Amazon Ads

### Fontes

- https://advertising.amazon.com/pt-br/resources/ad-specs
- https://advertising.amazon.com/pt-br/resources/faq
- https://advertising.amazon.com/pt-br/solutions/products/audio-ads?ref_=a20m_us_fnav_p_aa
- https://advertising.amazon.com/resources/ad-specs/audio-ads
- https://www.centralcomm.media/canal/amazon-music


---

## Podcast Ads (Rede)
<a id="podcast-ads"></a>

`slug: podcast-ads` · categoria **Streaming** · tipo **audio** · cor da marca `#8B5CF6`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/podcast-ads.svg)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/podcast-ads.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/podcast-ads-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/canais/podcast-ads.svg
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/podcast-ads.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/podcast-ads-b.webp

### Descrição

Publicidade em podcasts brasileiros via redes de podcast (Spotify, iHeartMedia, Podtag, etc.).

**Perfil de audiência**: No Brasil, a segmentação pública da Spotify Ads para podcasts indica alcance por idade, gênero e localização. O material em português também menciona entrega em desktop, mobile, web player, TV, carro e smart speaker, sugerindo uso amplo e digital-first.

**Melhor uso**: Boa opção para awareness e consideração com segmentação básica e mensuração de alcance, frequência e conclusão em ambientes de áudio premium.

### Números

- **Alcance**: +40M ouvintes BR
- **Usuários únicos**: 40M ouvintes
- **Tempo médio**: 45 min/episódio
- **Viewability (%)**: 95
- **Completion rate (%)**: 92
- **Taxa de engajamento (%)**: 88
- **Prazo de entrega**: 10 dias úteis
- **Integração**: Spotify Ad Studio / Podtag / iHeart / DSP
- **Modelo de compra**: CPM, Flat Fee (sponsorship)
- **Brand safety**: Content vetted
- **Medição**: Chartable; Podtrac; Spotify Analytics

**Demografia**

- Gênero: 52% homens / 48% mulheres
- Idade: 18–24: 22% · 25–34: 35% · 35–44: 25% · 45–54: 12% · 55+: 6%
- Classe: C: 28% · AB: 68% · DE: 4%

### Diferenciais

- Host-read ads com alta credibilidade
- 92% completion rate
- Audiência premium (68% classe AB)
- Contexto temático preciso

### Formatos

Resumo: Host-read Ads · Pre-recorded Ads · Dynamic Ad Insertion · Branded Podcast · Sponsorship

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Audio ads | 15s/30s | alcance em podcasts via compra automatizada ou reservada | audio, mobile, app, desktop, tablet |
| Host-read / testemunhal | Host-read | credibilidade do host e integração editorial | audio, mobile, app |
| Anúncio inserido dinamicamente | 15s/30s | escala com segmentação e substituição ao longo do tempo | audio, mobile, app, desktop, tablet |

**Especificações técnicas**

- **Host-read** — peso: N/A; duracao: 30s-60s; formato: Leitura pelo apresentador
- **Pre-recorded** — peso: até 1MB; duracao: 15s-30s; formato: MP3
- **Dynamic Insertion** — peso: até 1MB; duracao: 15s-30s; formato: MP3 via VAST/DAAST

### Segmentações disponíveis

- **Contextual / Conteúdo**: Categoria de podcast; Podcast específico; Episódio/tema; Host/apresentador
- **Demográfica**: Idade (18-65+); Gênero; Renda presumida
- **Comportamental**: Ouvintes frequentes; Subscribers; Completion rate de episódios
- **Audiências Customizadas**: CRM Match; Retargeting (ouviu episódio anterior); Lookalike

### Segmentações com exemplo de uso

- **Programa específico**
  - Quando: quando o anunciante quer comprar inventário de um podcast ou série específica
  - Exemplo: compra local em programas originais e exclusivos no Brasil
- **Catálogo de originais e exclusivos**
  - Quando: quando a campanha quer cobertura dentro do ecossistema de podcasts do publisher
  - Exemplo: inventário em podcasts originais e exclusivos do Spotify
- **Catálogo global de originais e exclusivos**
  - Quando: quando a marca quer alcançar ouvintes brasileiros consumindo podcasts fora do Brasil
  - Exemplo: programas dos Estados Unidos, Reino Unido, México, Alemanha, Austrália e Suécia
- **Geografia**
  - Quando: quando a compra usa segmentação por localização no delivery dinâmico
  - Exemplo: anúncios inseridos dinamicamente com base na região do ouvinte
- **Categoria / contexto editorial**
  - Quando: quando a marca busca aderência temática do programa
  - Exemplo: podcasts de notícias, entretenimento ou cultura alinhados ao tema da campanha
- **Comportamento / audiência**
  - Quando: quando a compra usa dados de audiência e consumo para distribuição
  - Exemplo: segmentação por comportamento de escuta em inserção dinâmica

### Fontes

- https://ads.spotify.com/pt-BR/experiencias-publicitarias/podcast-ads-specs/
- https://ads.spotify.com/pt-BR/noticias-insights/guia-para-comecar-seus-anuncios-em-podcasts/
- https://help.adanalytics.spotify.com/about-ad-analytics
- https://newsroom.spotify.com/2025-04-02/the-three-key-takeaways-for-advertisers-from-our-spotify-advance-event/


---

# Multicanal com CTV e áudio


---

## Logan
<a id="logan"></a>

`slug: logan` · categoria **Programática** · tipo **ooh** · cor da marca `#1F4B8F`

### Imagens

![Logo](https://planner.centralcomm.media/static/images/canais/logan.png)  
![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/logan.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/logan-b.webp)  

- Logo: https://planner.centralcomm.media/static/images/canais/logan.png
- Capa ilustrativa 1: https://planner.centralcomm.media/static/images/canais/capas/logan.webp
- Capa ilustrativa 2: https://planner.centralcomm.media/static/images/canais/capas/logan-b.webp

### Descrição

Plataforma multicanal de mídia e dados, com o motor Super Small Data para encontrar as audiências mais receptivas. Reúne OOH orientado por dados, rich media e display, CTV, vídeo in-app, áudio, WhatsApp, in-game e push.

**Perfil de audiência**: Audiência alcançada em canais digitais e físicos, sem perfil demográfico divulgado na página oficial.

**Melhor uso**: Bom para campanhas que combinam OOH, rich media, CTV, áudio, WhatsApp e push com seleção de público por dados, e para quem precisa de formatos interativos personalizados.

### Números

- **Alcance**: 100M+ usuários únicos via SDK de push
- **Usuários únicos**: 100M+ (SDK de push)
- **Viewability (%)**: 94
- **Medição**: Auditoria independente (informação da empresa)

### Diferenciais

- Super Small Data: seleção das audiências mais receptivas
- Mais de 120 formatos de rich media personalizados sem custo (informação da empresa)
- Resultados validados por auditoria independente (informação da empresa)

### Produtos

- Data Driven Out Of Home: campanhas de OOH ajustadas em tempo real para atingir públicos específicos
- Rich Media e Display: mais de 120 formatos interativos personalizados, produzidos sem custo pelo time da Logan (informação da empresa)
- Connected TV: vídeo programático interativo e personalizado
- In-App Video: vídeo em aplicativos móveis
- Áudio programático: rádio online, podcasts e conteúdo sob demanda
- WhatsApp Ads: dois formatos exclusivos, WhatsApp Chat e WhatsApp Engage
- In-game: banners, outdoors virtuais e skins em mais de 150 jogos
- Push Notifications: alcance por SDK integrado a operadoras regionais

### Formatos

Resumo: Data Driven OOH · Rich Media e Display · Connected TV · In-App Video · Áudio · WhatsApp Ads · In-game · Push

| Formato | Medida/duração | Melhor para | Dispositivos |
|---|---|---|---|
| Mídia em veículo | 970×250 | trajeto | ooh |
| Circuitos urbanos | 970×250 | rota e cidade | ooh |
| DOOH mobile | DOOH | apoio digital | ooh, mobile |

### Segmentações com exemplo de uso

- **Rota**
  - Quando: caminho casa–trabalho
  - Exemplo: Corredor da cidade
- **Cidade e período**
  - Quando: circuito fechado
  - Exemplo: 2 semanas em SP
- **Complemento OOH**
  - Quando: já tem rua ou metrô
  - Exemplo: Mesmo período da Eletromidia
- **Classe do trajeto**
  - Quando: AB vs massa
  - Exemplo: Centro vs periferia

### Fontes

- https://logan.ai/
- https://logan.ai/logan-ads/
- https://logan.ai/loganads/industria.html
- https://logan.ai/pt-br/logan-ads/
- https://propmark.com.br/logan-adota-zero-party-data-para-capturar-dados-sem-intermediarios/


---

# Formatos interativos
<a id="formatos-interativos"></a>

Catálogo de 29 formatos interativos para display e rich media, como cubo, flip, scratch, carrossel, hot spots, quiz, mini-games e vídeo interativo. Entram como complemento em programática e portais quando o objetivo é engajar, não só impactar.

![Capa ilustrativa 1](https://planner.centralcomm.media/static/images/canais/capas/interativos.webp)  
![Capa ilustrativa 2](https://planner.centralcomm.media/static/images/canais/capas/interativos-b.webp)  

- Hot Spots e 360° para imóveis
- Poll/Quiz até 8x vs display

Cada formato tem: imagem de referência (estática), link de **preview ao vivo no celular** (`creative_url`) e **galeria** (`gallery_url`) no ad server da CentralComm — bons para embutir em iframe ou botão "ver ao vivo". GIF legado (`gif_preview`) não é servido hoje e foi omitido.

| Formato | Categoria | Funil | Engajamento | Tempo de interação |
|---|---|---|---|---|
| [Cube](#fmt-cube) | Descoberta de produto | consideration | 3-6% | 15-30s |
| [Flip](#fmt-flip) | Experiência de marca | consideration | 2-4% | 8-15s |
| [Scratch](#fmt-scratch) | Descoberta | consideration, conversion | 5-10% | 10-20s |
| [Gallery / Carousel Swipe](#fmt-gallery) | Experiência de marca | consideration | 2-5% | 12-25s |
| [Hot Spots](#fmt-hot-spots) | Experiência de marca | consideration | 3-6% | 15-30s |
| [Video Interactive](#fmt-video-interactive) | Narrativa em vídeo | consideration | 4-8% | 20-45s |
| [Poll / Quiz](#fmt-poll-quiz) | Participação | consideration | 6-12% | 15-30s |
| [Wipe / Reveal](#fmt-wipe-reveal) | Experiência de marca | consideration | 3-5% | 10-20s |
| [360° Viewer](#fmt-viewer-360) | Experiência de marca | consideration | 4-7% | 20-40s |
| [Countdown Timer](#fmt-countdown) | Experiência de marca | conversion | 2-4% | 5-10s |
| [360 Spin](#fmt-interativo-360-spin) | Narrativa de marca |  | — | — |
| [3D Poster](#fmt-interativo-3d-poster) | Awareness de marca |  | — | — |
| [Animate Along Path](#fmt-interativo-animate-along-path) | Narrativa de marca |  | — | — |
| [Cards](#fmt-interativo-cards) | Descoberta de produto |  | — | — |
| [Carrousel](#fmt-interativo-carrousel) | Descoberta de produto |  | — | — |
| [Drag2Reveal](#fmt-interativo-drag2reveal) | Descoberta de produto |  | — | — |
| [Drag2Unblur](#fmt-interativo-drag2unblur) | Awareness de marca |  | — | — |
| [DragIt](#fmt-interativo-dragit) | Gamificação |  | — | — |
| [Hotspots (Shop the Look)](#fmt-interativo-hotspots-shop-the-look) | Descoberta de produto |  | — | — |
| [ImageFX](#fmt-interativo-imagefx) | Descoberta de produto |  | — | — |
| [Mini-game - Catch](#fmt-interativo-mini-game-catch) | Gamificação |  | — | — |
| [Mini-game - Clay pigeon](#fmt-interativo-mini-game-clay-pigeon) | Gamificação |  | — | — |
| [Mini-Site](#fmt-interativo-mini-site) | Narrativa de marca |  | — | — |
| [Questionnaire](#fmt-interativo-questionnaire) | Geração de leads |  | — | — |
| [Quiz](#fmt-interativo-quiz) | Gamificação |  | — | — |
| [Swatches](#fmt-interativo-swatches) | Descoberta de produto |  | — | — |
| [Tiles](#fmt-interativo-tiles) | Descoberta de produto |  | — | — |
| [Wheel de Fortune](#fmt-interativo-wheel-de-fortune) | Gamificação |  | — | — |
| [Xmas Calendar](#fmt-interativo-xmas-calendar) | Descoberta de produto |  | — | — |


## Descoberta de produto


### Cube
<a id="fmt-cube"></a>

*Cubo 3D rotativo com 6 faces interativas*

![Cube](https://ms.visarity.com/6d01f3aa-cbfe-4bb7-b25b-25e4396daa24.jpg)

Links: [imagem](https://ms.visarity.com/6d01f3aa-cbfe-4bb7-b25b-25e4396daa24.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-8e9d-bd08-bbd3-e0cdc) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-a0f8-9912-e64f-ca694&format=850eb8a1-e511-41eb-819e-79c7faadf3f9)

- **Descrição**: O popular 3D Cube apresenta muitas variações. Basta usar imagens estáticas para transformar o conteúdo numa bela animação 3D interativa. Experimente variações como Blocktower ou eCom Cube, otimizado para campanhas de e-commerce focadas em produtos. O formato inclui animação automática e interação do usuário, aceita imagens ou vídeo e pode apresentar claims, preços ou logotipos. É possível usar qualquer número de imagens; recomendamos 3 ou 4 trocas.
- **Como funciona**: O usuário gira o cubo tocando e arrastando. Cada face pode ter imagem, vídeo ou link diferente. Rotação automática opcional.
- **Dica de criativo**: Cada face conta parte da história. Use cores diferentes por face e garanta que o CTA esteja na face mais visível.
- **Melhor para**: Engajamento, storytelling interativo, produto
- **Funil**: consideration
- **Taxa de engajamento**: 3-6%
- **Tempo de interação**: 15-30s
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Peso máx.**: 500 KB (polite load)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Specs**: HTML5 com WebGL | 6 faces personalizáveis | Imagem por face: 600x600px | Rotação por touch/drag | Rotação automática opcional | Click por face (URLs diferentes) | Fallback para não-WebGL
- **Ganho vs display**: 4x vs display
- **Objetivo comercial**: Conversão
- **Mercados**: Automotivo, Beleza, Entretenimento, Alimentos e bebidas, Varejo e FMCG
- **Uso**: Exposição de produto, Interatividade


### Cards
<a id="fmt-interativo-cards"></a>

![Cards](https://ms.visarity.com/splash/0a284f3117dd0cda8aaba528cc228261.jpg)

Links: [imagem](https://ms.visarity.com/splash/0a284f3117dd0cda8aaba528cc228261.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-4ca8-a4e0-b6f0-b4bb7) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-5b5f-bd3d-02b8-a6348&format=4d121d7b-f2a6-40c8-aa79-36fd03d31a25)

- **Descrição**: O formato Cards apresenta vários conteúdos como uma pilha ou conjunto de cartões interativos. As pessoas podem navegar, deslizar, virar ou selecionar cartões para descobrir produtos, recursos, mensagens ou ofertas. É útil quando uma campanha precisa mostrar vários itens de forma compacta, sem sobrecarregar a visualização inicial. O formato permite narrativas de produto, comparação de recursos, coleções e revelações sequenciais.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Beleza, Finanças e seguros, Varejo e FMCG, Tecnologia, Viagens
- **Uso**: Exposição de produto, Interatividade


### Carrousel
<a id="fmt-interativo-carrousel"></a>

![Carrousel](https://ms.visarity.com/5d1f2c499df68dba42b9ce1d6cc43c0f.jpg)

Links: [imagem](https://ms.visarity.com/5d1f2c499df68dba42b9ce1d6cc43c0f.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-8a6e-8cd2-1ea5-a63d5) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-b241-aaed-8448-f5ddb&format=0396c198-c04b-4b4c-b914-b6a66d4cdea5%2C9ff293dd-32ff-4df2-b46c-9a904551b0a2)

- **Descrição**: O formato Carrousel permite navegar por várias cenas, produtos ou mensagens numa sequência horizontal ou rotativa. É indicado para campanhas que precisam mostrar uma linha de produtos, várias ofertas ou visuais diferentes de marca num único espaço. Pode combinar movimento automático com navegação controlada por deslize, arrasto ou clique. Cada item do carrossel pode levar a uma chamada para ação compartilhada ou individual.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Automotivo, Beleza, Varejo e FMCG, Viagens
- **Uso**: Exposição de produto, Interatividade


### Drag2Reveal
<a id="fmt-interativo-drag2reveal"></a>

![Drag2Reveal](https://ads.centralcomm.media/campaigns/v3ad-7602-95dd-db3a-5f262/splash.jpg?t=1695728403635)

Links: [imagem](https://ads.centralcomm.media/campaigns/v3ad-7602-95dd-db3a-5f262/splash.jpg?t=1695728403635) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-7602-95dd-db3a-5f262) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-7602-95dd-db3a-5f262&format=147b46f7-dcd1-4574-b538-cc2575e3f835)

- **Descrição**: Drag to Reveal é um formato altamente envolvente, perfeito para comparar produtos, como cores de cabelo ou imagens de antes e depois. Funciona especialmente bem para produtos de beleza. Inclui animação automática e interação por toque ou movimento do mouse. Também é possível alternar as imagens esquerda e direita, permitindo que a pessoa escolha livremente os produtos que quer comparar.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Automotivo, Beleza, Saúde, Varejo e FMCG
- **Uso**: Exposição de produto, Interatividade


### Hotspots (Shop the Look)
<a id="fmt-interativo-hotspots-shop-the-look"></a>

![Hotspots (Shop the Look)](https://ads.centralcomm.media/campaigns/v3ad-8077-ace8-3b5b-d0b16/splash.jpg?t=1677683411727)

Links: [imagem](https://ads.centralcomm.media/campaigns/v3ad-8077-ace8-3b5b-d0b16/splash.jpg?t=1677683411727) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-8077-ace8-3b5b-d0b16) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-8077-ace8-3b5b-d0b16&format=HOTSPOTS%2Ce0e5f2a8-ebd8-47cb-a5f1-f399b25b39b6)

- **Descrição**: O formato Hotspots apresenta uma imagem com diversos pontos interativos. Eles podem ser ativados por toque ou mouse-over para exibir informações adicionais, como nomes de produtos, preços ou dados técnicos. Também funciona muito bem com vídeo, criando uma ótima oportunidade para apresentar explicações de forma automática e interativa.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Automotivo, Beleza, Imobiliário, Varejo e FMCG, Tecnologia
- **Uso**: Exposição de produto, Interatividade


### ImageFX
<a id="fmt-interativo-imagefx"></a>

![ImageFX](https://ms.visarity.com/5499b709-d8ce-4f13-832a-41584ed34f71.jpg)

Links: [imagem](https://ms.visarity.com/5499b709-d8ce-4f13-832a-41584ed34f71.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-a9bb-a6a2-7b31-4bc90) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-322c-a3ce-fa19-d5c25&format=348b3fde-93f5-464e-8f9c-b85db1cff357%2C98646ee9-e1c3-4e8e-9142-3a46921fa5ad)

- **Descrição**: O formato Image FX transforma imagens 2D estáticas em belas animações 3D interativas. Precisa apenas de imagens estáticas e pode incluir botão de CTA, logotipo ou claims. Oferece mais de 20 efeitos, incluindo 3D Cube, Coverflow, Carousel e Stripes. Todos os efeitos incluem animação automática e interação por mouse-over ou deslize, com suporte a vídeo MP4. O formato suporta qualquer número de imagens.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Automotivo, Beleza, Entretenimento, Alimentos e bebidas, Varejo e FMCG
- **Uso**: Exposição de produto, Interatividade


### Swatches
<a id="fmt-interativo-swatches"></a>

![Swatches](https://ms.visarity.com/66356019f127debd9379b903e1e8b5f7.jpg)

Links: [imagem](https://ms.visarity.com/66356019f127debd9379b903e1e8b5f7.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-e1da-9c26-151d-a52a4) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-e1da-9c26-151d-a52a4&format=be6706b8-5a7e-4fdd-8444-7217e728f2e2)

- **Descrição**: O formato Swatches permite alternar entre cores, materiais, variantes ou estilos de produto. Ao selecionar uma amostra, o visual principal é atualizado para comparar opções diretamente no banner. É útil para campanhas de moda, beleza, automotivo, mobiliário e varejo, onde as variantes visuais influenciam a consideração. O formato transforma uma imagem de produto padrão numa experiência interativa semelhante a um configurador.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Automotivo, Beleza, Imobiliário, Varejo e FMCG
- **Uso**: Exposição de produto, Interatividade


### Tiles
<a id="fmt-interativo-tiles"></a>

![Tiles](https://ms.visarity.com/851dd445-4a3f-4fac-ae0e-65f3ab0ff469.jpg)

Links: [imagem](https://ms.visarity.com/851dd445-4a3f-4fac-ae0e-65f3ab0ff469.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-6882-a4a5-815f-c976a) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-6882-a4a5-815f-c976a&format=8a37d0b9-fcce-427a-858d-a3de67df9d84)

- **Descrição**: O formato Tiles organiza várias imagens, produtos ou mensagens numa grade interativa. As pessoas podem tocar ou passar o mouse sobre cada bloco para revelar conteúdo adicional, alternar estados ou avançar na peça. É útil para coleções de produtos, visões gerais de categorias, destaques de recursos e campanhas em que a comparação visual rápida importa. O layout em blocos oferece uma forma estruturada de apresentar vários ativos num único banner.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Beleza, Alimentos e bebidas, Varejo e FMCG, Tecnologia
- **Uso**: Exposição de produto, Interatividade


### Xmas Calendar
<a id="fmt-interativo-xmas-calendar"></a>

![Xmas Calendar](https://ms.visarity.com/splash/d7476b18259504d14a792223acc8c9fb.jpg)

Links: [imagem](https://ms.visarity.com/splash/d7476b18259504d14a792223acc8c9fb.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-ed76-a4a8-357c-427c0) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-ed76-a4a8-357c-427c0&format=c0f1e8f4-a059-4c53-bcd9-a64dc9c8e479)

- **Descrição**: O formato Xmas Calendar cria uma experiência de calendário do advento dentro do banner. As pessoas podem abrir a porta do dia para revelar produtos, ofertas, mensagens ou surpresas. Foi criado para campanhas sazonais e funciona especialmente bem quando uma marca quer construir engajamento recorrente durante um período de campanha. O formato pode apresentar vários produtos ou promoções numa estrutura familiar e lúdica.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Beleza, Entretenimento, Alimentos e bebidas, Varejo e FMCG
- **Uso**: Exposição de produto, Interatividade


## Experiência de marca


### Flip
<a id="fmt-flip"></a>

*Cartão que vira revelando o outro lado*

- **Descrição**: Banner com dois lados: frente e verso. O usuário clica/toca para virar como um cartão, revelando conteúdo adicional.
- **Como funciona**: O banner mostra o lado frontal. Ao clicar ou passar o mouse, vira com animação 3D revelando o verso com mais informações.
- **Dica de criativo**: A frente deve criar curiosidade ("Vire para descobrir"). O verso entrega a recompensa com CTA claro.
- **Melhor para**: Promoções, antes/depois, revelar benefícios
- **Funil**: consideration
- **Taxa de engajamento**: 2-4%
- **Tempo de interação**: 8-15s
- **Dimensões**: 300x250, 728x90, 300x600
- **Peso máx.**: 300 KB
- **Arquivos**: HTML5
- **Specs**: HTML5 | 2 faces (frente e verso) | Cada face: imagem ou HTML | Animação de flip suave | Click ou hover para virar | Click-through no verso
- **Objetivo comercial**: Alcance


### Gallery / Carousel Swipe
<a id="fmt-gallery"></a>

*Galeria de imagens navegável por swipe*

- **Descrição**: Galeria interativa com múltiplas imagens que o usuário navega por swipe ou setas. Cada imagem pode ter link próprio.
- **Como funciona**: O banner mostra uma imagem com indicadores de navegação. O usuário swipa ou clica em setas para ver as demais.
- **Dica de criativo**: Primeiro slide é o mais visto — coloque o hero ali. Indicadores visuais de "tem mais" incentivam o swipe.
- **Melhor para**: Múltiplos produtos, lookbook, catálogo visual
- **Funil**: consideration
- **Taxa de engajamento**: 2-5%
- **Tempo de interação**: 12-25s
- **Dimensões**: 300x250, 300x600, 728x90, 970x250
- **Peso máx.**: 500 KB total
- **Arquivos**: HTML5
- **Specs**: HTML5 | 3-10 imagens | Cada imagem: dimensão do banner | Navegação: swipe, setas, dots | Autoplay rotativo opcional | Click-through por imagem | Timer entre slides configurável
- **Objetivo comercial**: Alcance


### Hot Spots
<a id="fmt-hot-spots"></a>

*Pontos clicáveis sobre imagem com info pop-up*

- **Descrição**: Imagem com pontos de interesse clicáveis. Ao tocar em cada ponto, aparece pop-up com informações, preço ou link.
- **Como funciona**: O banner mostra uma imagem com ícones/pontos pulsantes. Ao clicar em cada ponto, um tooltip ou pop-up revela detalhes.
- **Dica de criativo**: Use para produtos em cenário (room setting, look completo). Os pontos devem ser óbvios — pulse e use cor contrastante.
- **Melhor para**: Produtos em contexto, e-commerce, imóveis, decoração
- **Funil**: consideration
- **Taxa de engajamento**: 3-6%
- **Tempo de interação**: 15-30s
- **Dimensões**: 300x250, 300x600, 728x90, 970x250
- **Peso máx.**: 400 KB
- **Arquivos**: HTML5
- **Specs**: HTML5 | Imagem de fundo | 3-8 hot spots posicionáveis | Pop-up por spot: texto, imagem, link | Animação pulsante nos spots | Close individual por spot | Click-through global ou por spot
- **Objetivo comercial**: Alcance


### Wipe / Reveal
<a id="fmt-wipe-reveal"></a>

*Arraste para revelar antes/depois*

- **Descrição**: Banner com slider que o usuário arrasta para revelar a transição entre duas imagens — antes e depois.
- **Como funciona**: O banner mostra duas imagens sobrepostas com um slider no meio. O usuário arrasta para ver a transição.
- **Dica de criativo**: Perfeito para antes/depois. O contraste entre as imagens deve ser dramático para incentivar o arraste.
- **Melhor para**: Antes/depois, transformação, reforma, beleza
- **Funil**: consideration
- **Taxa de engajamento**: 3-5%
- **Tempo de interação**: 10-20s
- **Dimensões**: 300x250, 300x600, 728x90
- **Peso máx.**: 400 KB
- **Arquivos**: HTML5 (Canvas)
- **Specs**: HTML5 com Canvas | 2 imagens (antes/depois) | Slider vertical ou horizontal | Drag para revelar | Posição inicial configurável | Click-through após interação
- **Objetivo comercial**: Alcance


### 360° Viewer
<a id="fmt-viewer-360"></a>

*Imagem ou vídeo 360 graus navegável*

- **Descrição**: Experiência imersiva onde o usuário gira uma visão 360° de um produto, espaço ou cenário arrastando com o dedo.
- **Como funciona**: O banner mostra uma imagem 360° que o usuário rotaciona tocando e arrastando. Pode incluir hot spots na cena.
- **Dica de criativo**: Para produtos, use fundo branco e gire o item. Para espaços (hotel, imóvel), coloque o usuário no centro da cena.
- **Melhor para**: Produtos, imóveis, turismo, experiência imersiva
- **Funil**: consideration
- **Taxa de engajamento**: 4-7%
- **Tempo de interação**: 20-40s
- **Dimensões**: 300x250, 300x600, expandido fullscreen
- **Peso máx.**: 1 MB (HTML5) + assets streaming
- **Arquivos**: HTML5 + imagens panorâmicas
- **Specs**: HTML5 com WebGL ou sprite sheet | Imagem equiretangular: 4096x2048 ou sprite com 36+ frames | Navegação por drag | Gyroscope no mobile (opcional) | Hot spots opcionais | Zoom opcional
- **Ganho vs display**: 5x vs display
- **Objetivo comercial**: Alcance


### Countdown Timer
<a id="fmt-countdown"></a>

*Banner com contagem regressiva em tempo real*

- **Descrição**: Banner com timer dinâmico contando regressivamente até uma data/evento específico. Gera urgência e FOMO.
- **Como funciona**: O banner exibe um countdown em tempo real (dias, horas, minutos, segundos) até a data configurada. Após zerar, muda para mensagem final.
- **Dica de criativo**: A urgência vende. "Faltam 02:15:33 para o desconto acabar" é mais poderoso que "Promoção por tempo limitado".
- **Melhor para**: Black Friday, lançamentos, eventos, promoções limitadas
- **Funil**: conversion
- **Taxa de engajamento**: 2-4%
- **Tempo de interação**: 5-10s
- **Dimensões**: 300x250, 728x90, 970x250, 320x50
- **Peso máx.**: 200 KB
- **Arquivos**: HTML5
- **Specs**: HTML5 | Timer dinâmico em tempo real | Data/hora alvo configurável | Timezone configurável | Estado pré-evento e pós-evento | Estilo visual customizável | Click-through para landing page | Atualiza sem refresh
- **Objetivo comercial**: Alcance


## Descoberta


### Scratch
<a id="fmt-scratch"></a>

*Raspadinha digital interativa*

- **Descrição**: O usuário "raspa" a superfície do banner com o dedo ou mouse, revelando uma oferta, imagem ou mensagem escondida.
- **Como funciona**: Uma camada superior cobre o conteúdo. O usuário arrasta o dedo/mouse para "raspar" e revelar o que está embaixo.
- **Dica de criativo**: A promessa de revelar algo cria urgência. Use "Raspe e descubra seu desconto" para promoções.
- **Melhor para**: Promoções, cupons, gamificação, engajamento
- **Funil**: consideration, conversion
- **Taxa de engajamento**: 5-10%
- **Tempo de interação**: 10-20s
- **Dimensões**: 300x250, 300x600, 320x480
- **Peso máx.**: 300 KB
- **Arquivos**: HTML5 (Canvas)
- **Specs**: HTML5 com Canvas | Camada superior: imagem ou cor | Camada inferior: oferta/conteúdo | Scratch area customizável | Threshold de revelação: 40-70% | Callback quando revelado
- **Ganho vs display**: 6x vs display
- **Objetivo comercial**: Conversão


## Narrativa em vídeo


### Video Interactive
<a id="fmt-video-interactive"></a>

*Vídeo com CTAs e overlays clicáveis*

- **Descrição**: Player de vídeo com elementos interativos sobrepostos: botões CTA, links em tempo real, quiz e decisões durante o vídeo.
- **Como funciona**: O vídeo toca normalmente, mas em momentos específicos aparecem botões, links ou perguntas sobre o conteúdo.
- **Dica de criativo**: Planeje os pontos de interação no storyboard. O CTA deve aparecer no momento de maior interesse, não no início.
- **Melhor para**: Product demos, storytelling interativo
- **Funil**: consideration
- **Taxa de engajamento**: 4-8%
- **Tempo de interação**: 20-45s
- **Dimensões**: 300x250, 300x600, 320x480 (expandido)
- **Peso máx.**: 1 MB (HTML5) + streaming vídeo
- **Duração**: Até 60s
- **Arquivos**: HTML5 + MP4
- **Specs**: HTML5 container + vídeo MP4 | Overlays em timestamps específicos | CTA buttons durante vídeo | Chapters/seções opcionais | Mute/unmute toggle | Fullscreen opcional | End card com CTA
- **Ganho vs display**: 5x vs display
- **Objetivo comercial**: Alcance


## Participação


### Poll / Quiz
<a id="fmt-poll-quiz"></a>

*Enquete ou quiz interativo no banner*

- **Descrição**: Banner com perguntas interativas — enquete de opinião ou quiz com resultados. Gera dados de first-party e alto engajamento.
- **Como funciona**: O banner apresenta uma pergunta com opções clicáveis. Após responder, mostra resultado e CTA personalizado.
- **Dica de criativo**: Perguntas devem ser divertidas e fáceis. "Qual seu estilo?" funciona melhor que "O que você prefere comprar?".
- **Melhor para**: First-party data, engajamento, segmentação
- **Funil**: consideration
- **Taxa de engajamento**: 6-12%
- **Tempo de interação**: 15-30s
- **Dimensões**: 300x250, 300x600, 320x480
- **Peso máx.**: 300 KB
- **Arquivos**: HTML5
- **Specs**: HTML5 | 1-5 perguntas | 2-4 opções por pergunta | Resultado personalizável por resposta | Dados capturados por interação | CTA final dinâmico | Barra de resultados (votos %) | Timer opcional
- **Ganho vs display**: 8x vs display
- **Objetivo comercial**: Conversão


## Narrativa de marca


### 360 Spin
<a id="fmt-interativo-360-spin"></a>

![360 Spin](https://ms.visarity.com/4cda7157-095c-49fe-a949-84b1a0dd88c3.jpg)

Links: [imagem](https://ms.visarity.com/4cda7157-095c-49fe-a949-84b1a0dd88c3.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-8092-8178-67b0-628ea) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-8092-8178-67b0-628ea&format=af249d1a-e6d3-4514-8bea-e72a17e6a314)

- **Descrição**: O formato 360 Spin cria transições entre uma série de imagens em tela cheia, dividindo-as em anéis circulares.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Alcance
- **Mercados**: Automotivo, Beleza, Entretenimento, Alimentos e bebidas, Viagens
- **Uso**: Foco na marca, Narrativa


### Animate Along Path
<a id="fmt-interativo-animate-along-path"></a>

![Animate Along Path](https://ms.visarity.com/ef07cb6e-312e-426f-a1cd-b7202c2b2dcb.jpg)

Links: [imagem](https://ms.visarity.com/ef07cb6e-312e-426f-a1cd-b7202c2b2dcb.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-93d3-8add-d9dd-4b5fc) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-2e2c-a512-8964-96f41&format=acddffdf-6589-43e8-a0fc-8ec7212ba926)

- **Descrição**: O formato Animate Along Path move um objeto, produto, personagem ou mensagem ao longo de uma trajetória predefinida. É útil para narrativas guiadas, conceitos baseados em rotas, jornadas de produto e campanhas em que o movimento deve direcionar a atenção dentro da peça. A animação pode ser executada automaticamente e combinada com gatilhos interativos ou elementos de marca. O formato transforma ativos estáticos numa sequência clara e dinâmica.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Alcance
- **Mercados**: Automotivo, Entretenimento, Tecnologia, Viagens
- **Uso**: Foco na marca, Narrativa


### Mini-Site
<a id="fmt-interativo-mini-site"></a>

![Mini-Site](https://ms.visarity.com/0b3d368b49a6a97f11859714ea7a8d34.jpg)

Links: [imagem](https://ms.visarity.com/0b3d368b49a6a97f11859714ea7a8d34.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-c49c-ae3b-beb3-f470e) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-a663-80f0-2352-a6cbb&format=b48d92ff-1779-4ffa-8708-df1fe1a02e46)

- **Descrição**: O formato Mini-Site leva uma pequena experiência de várias páginas para dentro do espaço publicitário. Pode combinar informações de produto, galerias de imagens, vídeos, ofertas e chamadas para ação numa unidade interativa. As pessoas navegam entre seções sem sair do banner, o que o torna adequado para campanhas que precisam de mais profundidade do que uma única cena. É uma boa opção para narrativas de marca, lançamentos de produtos, promoção de eventos e campanhas ricas em conteúdo.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Alcance
- **Mercados**: Automotivo, Educação, Finanças e seguros, Imobiliário, Viagens
- **Uso**: Foco na marca, Narrativa


## Awareness de marca


### 3D Poster
<a id="fmt-interativo-3d-poster"></a>

![3D Poster](https://ms.visarity.com/splash/cc6985f66429ad5392af6363cf68c9fc.jpg)

Links: [imagem](https://ms.visarity.com/splash/cc6985f66429ad5392af6363cf68c9fc.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-6410-baff-111b-cb86b) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-6410-baff-111b-cb86b&format=POSTER3D%2Ca05d353a-7fad-43e2-9cbf-6e7775a840c6)

- **Descrição**: O formato 3D Poster transforma uma imagem 2D em camadas numa cena 3D espetacular e animada. É ideal para cartazes de filmes e também funciona muito bem com imagens de produtos em camadas. Inclui animação automática e interação por mouse-over ou deslize. O recurso de giroscópio é compatível com dispositivos que o tenham ativado. É possível adicionar um vídeo MP4, por exemplo, para exibir um trailer sobre o cartaz 3D. O formato suporta qualquer número de cenas.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Alcance
- **Mercados**: Automotivo, Beleza, Entretenimento, Alimentos e bebidas, Viagens
- **Uso**: Foco na marca


### Drag2Unblur
<a id="fmt-interativo-drag2unblur"></a>

![Drag2Unblur](https://ms.visarity.com/8d0a40dd-a3ad-4abd-9e14-0d145a1af3e2.jpg)

Links: [imagem](https://ms.visarity.com/8d0a40dd-a3ad-4abd-9e14-0d145a1af3e2.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-7c9b-bb75-1c93-b10a6) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-7c9b-bb75-1c93-b10a6&format=4020666d-5940-45b0-93ea-ba6fc3e3e055)

- **Descrição**: Permita que a pessoa revele a imagem por trás de um painel de vidro fosco. A imagem parcialmente desfocada desperta curiosidade e estimula alto engajamento. O estilo sofisticado deste formato é ideal para marcas de luxo e beleza. Inclui animação automática e interação por toque ou movimento do mouse.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Alcance
- **Mercados**: Automotivo, Beleza, Entretenimento, Varejo e FMCG, Viagens
- **Uso**: Foco na marca, Interatividade


## Gamificação


### DragIt
<a id="fmt-interativo-dragit"></a>

![DragIt](https://ms.visarity.com/splash/425f822cd6ced8607e394209097b444c.jpg)

Links: [imagem](https://ms.visarity.com/splash/425f822cd6ced8607e394209097b444c.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-8228-a3a2-dd71-3986d) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-fc41-b708-c26a-7971b&format=9bd2f0df-0858-41f9-b12a-26311819a066)

- **Descrição**: O formato DragIt convida as pessoas a mover um objeto ou elemento visual pelo banner. O arrasto pode revelar conteúdo, completar um desafio, comparar estados ou conduzir a pessoa a um resultado de marca. É útil para demonstrações de produto lúdicas e mecânicas interativas simples que incentivam o envolvimento físico com a peça. O formato suporta toque e mouse e pode medir o início e o fim do arrasto.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Automotivo, Entretenimento, Alimentos e bebidas, Varejo e FMCG
- **Uso**: Jogável, Interatividade


### Mini-game - Catch
<a id="fmt-interativo-mini-game-catch"></a>

![Mini-game - Catch](https://ms.visarity.com/splash/16fcbf3a7a9410bcc60a6621e5f534a4.jpg)

Links: [imagem](https://ms.visarity.com/splash/16fcbf3a7a9410bcc60a6621e5f534a4.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-1ecf-8251-9593-b9dc9) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-1ecf-8251-9593-b9dc9&format=a4c28ddc-47d9-4c65-be6f-6c091297544b)

- **Descrição**: O formato Mini-game Catch transforma o banner numa experiência jogável simples. Itens caem do topo da peça e as pessoas os capturam movendo uma cesta, personagem, produto ou elemento de marca. É útil para campanhas que querem criar engajamento ativo, recompensar atenção ou conectar uma mensagem de produto a uma mecânica de jogo leve. Funciona especialmente bem para promoções, campanhas sazonais, lançamentos de entretenimento, marcas de alimentos e momentos de varejo ou FMCG.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Entretenimento, Alimentos e bebidas, Varejo e FMCG
- **Uso**: Jogável, Gamificação


### Mini-game - Clay pigeon
<a id="fmt-interativo-mini-game-clay-pigeon"></a>

![Mini-game - Clay pigeon](https://ms.visarity.com/splash/b8bd33c54a360f23d8c36545a0466408.jpg)

Links: [imagem](https://ms.visarity.com/splash/b8bd33c54a360f23d8c36545a0466408.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-c9c0-b425-aef7-32006) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-c9c0-b425-aef7-32006&format=bf9d6642-ed21-4628-9c12-e1ffe46384c5)

- **Descrição**: O formato Mini-game Clay pigeon transforma o banner numa experiência jogável rápida baseada em alvos. Objetos se movem pela peça e as pessoas tentam acertá-los ou selecioná-los com toque, clique ou interação semelhante. É útil para campanhas que buscam engajamento rápido, competição simples ou uma ligação lúdica entre a marca e a mecânica de jogo. Funciona bem para entretenimento, promoções de alimentos e bebidas, ativações de varejo e campanhas sazonais.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Entretenimento, Alimentos e bebidas, Varejo e FMCG
- **Uso**: Jogável, Gamificação


### Quiz
<a id="fmt-interativo-quiz"></a>

![Quiz](https://ms.visarity.com/splash/f20ff7b090fc5cdc2963e8ec4582c852.jpg)

Links: [imagem](https://ms.visarity.com/splash/f20ff7b090fc5cdc2963e8ec4582c852.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-3d0b-bf81-446c-a7cbd) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-3d0b-bf81-446c-a7cbd&format=913f8443-f6ac-4598-ba8d-64640a3b722e)

- **Descrição**: O formato Quiz transforma a mensagem da campanha num desafio interativo curto. As pessoas respondem a perguntas e recebem feedback, uma pontuação ou um resultado que pode se conectar diretamente à mensagem de marca ou à chamada para ação. É útil para campanhas de educação, entretenimento, recomendação de produto e awareness, nas quais a participação ativa aumenta a lembrança. O formato suporta interações de uma pergunta ou fluxos de quiz em várias etapas.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Educação, Entretenimento, Alimentos e bebidas, Saúde, Varejo e FMCG
- **Uso**: Jogável, Gamificação


### Wheel de Fortune
<a id="fmt-interativo-wheel-de-fortune"></a>

![Wheel de Fortune](https://ms.visarity.com/splash/daad7c40e5ce44bad5d5852da4b0fe7e.jpg)

Links: [imagem](https://ms.visarity.com/splash/daad7c40e5ce44bad5d5852da4b0fe7e.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-0fd3-ad53-c72e-e0b1f) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-057a-b569-4f5e-d6f9a&format=71f1dff6-3dde-40fc-b3ec-a7b909ddf023)

- **Descrição**: O formato Wheel de Fortune transforma o banner num jogo simples de girar e revelar. As pessoas giram uma roda para receber um prêmio, oferta, mensagem, produto ou resultado de campanha. É útil para promoções, sorteios, ações de fidelidade e campanhas que se beneficiam de suspense e feedback instantâneo. O formato cria um ciclo de interação claro e pode conectar o resultado diretamente a uma chamada para ação.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Entretenimento, Alimentos e bebidas, Varejo e FMCG, Telecomunicações, Viagens
- **Uso**: Jogável, Gamificação


## Geração de leads


### Questionnaire
<a id="fmt-interativo-questionnaire"></a>

![Questionnaire](https://ms.visarity.com/bbd83605-3a91-4ff3-8366-a2fa6b8aa1b5.jpg)

Links: [imagem](https://ms.visarity.com/bbd83605-3a91-4ff3-8366-a2fa6b8aa1b5.jpg) · [preview ao vivo](https://ads.centralcomm.media/preview/phone?creativeID=v3ad-3642-8f07-fc1d-b30ae) · [galeria](https://ads.centralcomm.media/gallery/?galleryID=9e83778e-a091-49ac-ada6-ea34ceba0cd8&creativeID=v3ad-3642-8f07-fc1d-b30ae&format=a9a9a11e-9527-4357-b9e3-ab649eee3452)

- **Descrição**: O formato Questionnaire guia as pessoas por uma ou mais perguntas dentro do banner. É útil para coletar preferências, qualificar interesse ou ajudar na descoberta do produto, serviço ou oferta certa. Cada resposta pode ativar a próxima etapa, revelar um resultado ou levar a uma chamada para ação personalizada. Funciona bem para campanhas que se beneficiam de participação ativa e caminhos de decisão simples.
- **Dimensões**: IAB desktop e mobile (conforme briefing)
- **Arquivos**: JPG/PNG, logo SVG/PNG; vídeo MP4 quando aplicável
- **Objetivo comercial**: Conversão
- **Mercados**: Automotivo, Educação, Finanças e seguros, Saúde, Varejo e FMCG
- **Uso**: Geração de leads, Interatividade

