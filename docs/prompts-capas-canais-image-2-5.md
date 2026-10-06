# Capas dos canais com GPT Image 2.5 (OpenAI direto)

Tabela para gerar uma capa por canal no Studio. Atualizada em 2026-10-06: **26 canais** na vitrine. Ficaram de fora os 10 canais da categoria Portais (agora na área própria Portais e veículos, que usará **prints reais dos portais**, nunca imagem criada) e o Waze, que não existe mais.

> **Atenção à decisão anterior:** ficou combinado que a vitrine usaria só imagens reais, sem fallback gerado. Estas capas são **geradas por IA**. Se entrarem no produto, mostram uma cena genérica, não o anúncio real do canal. Recomendo manter um selo discreto "Ilustração" na foto e substituir por foto real quando houver. Nenhuma capa reproduz logotipo, interface ou anúncio real de terceiros.

## Como chamar

| Item | Valor |
|---|---|
| Modelo do Studio | `gpt-image-2.5-sunburst--openai` (id na API: `gpt-image-2.5-sunburst`) |
| Rota | `POST /v1/images/generations` (a mesma de produção; com referência vira `images/edits`) |
| Tamanho | `1680x944` (16:9; a API exige largura e altura divisíveis por 16, por isso não é 1664x936). Para o carrossel da ficha, repetir em `1680x1264` (4:3) se precisar |
| Qualidade | `medium` para rascunho e lote, `high` para a versão final |
| Idioma do prompt | inglês, até 3.800 caracteres (perfil do modelo no Lab) |
| Cota | 429 é esperado em lote: gerar 4 por vez e respeitar o `retry-after` |
| Saída | converter para WebP (qualidade 85) e salvar em `aicentralv2/static/images/canais/capas/{slug}.webp` |
| Campo a preencher | `cadu_canais.imagem_path` com `/static/images/canais/capas/{slug}.webp` |

## Prompt completo (modelo para o Studio)

O Studio monta cada pedido assim; só o bloco **NÚCLEO** muda por canal (coluna da tabela).

```
You are rendering a finished editorial photograph for an advertising media catalog. Follow the brief literally; never add logos, brand names or readable text that were not requested.

TASK: One wide 16:9 photograph used as the cover of a media channel card.
SUBJECT AND COMPOSITION: {NÚCLEO}
STYLE: realistic commercial photography, natural light, shallow depth of field, clean modern composition, a subtle emerald green accent (#1DBF73) somewhere in the scene (clothing, object or light), neutral warm skin tones, no heavy filters.
TEXT ON SCREENS AND SURFACES: any screen or surface may show only abstract shapes and layout blocks. If a headline is requested, render exactly this string and nothing else: "{TEXTO}".
BRAND: the only brand shown is the fictional advertiser VÉRTICE (outdoor sportswear, simple mountain-peak mark in white). No real logos, trademarks, app icons or interface chrome from any real service.
AVOID: real brand logos, recognizable celebrities, distorted hands, extra fingers, garbled text, watermarks, collage borders, stock-photo cliches, dark muddy shadows.
```

## Tabela dos 26 canais

| # | ID | Canal | Categoria | O que a capa mostra | Núcleo do prompt (inglês) | Texto exato | Arquivo |
|---|---|---|---|---|---|---|---|
| 1 | 56 | 99 | Mobilidade | Splash e In-App no app de corrida | A passenger in the back seat of a yellow compact taxi at dusk, holding a phone that shows a generic ride-hailing app splash screen with a full-screen advertisement; city lights blurred through the window. | `Mais conforto para o seu caminho.` | `99.webp` |
| 2 | 55 | Uber | Mobilidade | Anúncio no app e no recibo | Close-up of a hand holding a phone in the back of a dark sedan, the screen showing a generic ride receipt page with a small sponsored banner under the fare; warm interior light, city night outside. | `Mais conforto para o seu caminho.` | `uber.webp` |
| 3 | 54 | iFood | Mobilidade | Splash e In-App em app de delivery | A person on a sofa choosing dinner on a phone, the screen showing a generic food-delivery app home with a sponsored banner at the top; a bowl of pasta on the coffee table, cozy evening light. | `Mais conforto para o seu caminho.` | `ifood.webp` |
| 4 | 57 | Logan | Mobilidade | Mídia em veículo e circuitos urbanos | A city bus wrapped with a clean outdoor sportswear advertisement driving along a busy avenue at golden hour, pedestrians on the sidewalk, slight motion blur; wide street-level view. | `Mais conforto para o seu caminho.` | `logan.webp` |
| 5 | 1 | Spotify | Streaming | Audio Ads, takeover e playlist patrocinada | A runner in earbuds checking a phone that shows a generic music streaming app with a sponsored playlist cover and a banner ad, city park at sunrise, shallow depth of field. | `Mais conforto para o seu caminho.` | `spotify.webp` |
| 6 | 2 | Deezer | Streaming | Audio Ads e sessões patrocinadas | A young woman wearing headphones at a café table with a phone showing a generic music app with a sponsored session card; warm window light, laptop and coffee nearby. | `Mais conforto para o seu caminho.` | `deezer.webp` |
| 7 | 3 | Amazon Music | Streaming | Audio Ads e Alexa | A cozy living room with a smart speaker on a shelf glowing softly and a person relaxing with a tablet showing a generic music app with a display ad; late afternoon light. | `Mais conforto para o seu caminho.` | `amazon-music.webp` |
| 8 | 21 | Podcast Ads (Rede) | Streaming | Host-read e DAI | A podcast studio with a host speaking into a microphone on a boom arm, a laptop beside showing an audio waveform and a sponsor card; warm practical lights, headphones on the desk. | `Mais conforto para o seu caminho.` | `podcast-ads.webp` |
| 9 | 4 | Netflix | Streaming | Anúncios em vídeo 15/30s | A person on a sofa watching a living-room TV showing a generic streaming service ad break with a full-screen outdoor sportswear commercial; dim room, TV glow on the walls. | `Mais conforto para o seu caminho.` | `netflix.webp` |
| 10 | 5 | Globoplay | Streaming | Pre-roll, mid-roll e pause ads | A family on a sofa watching a TV that shows a generic streaming player with a paused frame and a sponsored overlay on the side; evening living room, snacks on the table. | `Mais conforto para o seu caminho.` | `globoplay.webp` |
| 11 | 6 | Paramount+ | Streaming | Anúncios em vídeo e pause ads | A couple watching a wall-mounted TV showing a generic streaming app home screen with a large sponsored hero banner; modern apartment, plants, warm lamp light. | `Mais conforto para o seu caminho.` | `paramount-plus.webp` |
| 12 | 8 | Samsung TV Plus | Streaming | Home screen e first screen takeover | A wide living room with a large smart TV whose home screen shows a full-width sponsored takeover banner and a row of thumbnails; a person holding a remote, sunny afternoon. | `Mais conforto para o seu caminho.` | `samsung-tv-plus.webp` |
| 13 | 34 | Disney+ | Streaming | Anúncios em vídeo | Two children and a parent on a rug watching a tablet that shows a generic family streaming service with a short ad break; cheerful warm light, toys in the background. | `Mais conforto para o seu caminho.` | `disney-plus.webp` |
| 14 | 35 | Prime Video | Streaming | Pre-roll e pause ads | A person with a laptop in bed watching a generic streaming player with an ad break overlay; bedside lamp, cozy bedroom, shallow depth of field. | `Mais conforto para o seu caminho.` | `prime-video.webp` |
| 15 | 36 | Max (HBO) | Streaming | Anúncios em vídeo | A dark home cinema room with a projector screen showing a generic premium streaming ad break; two viewers silhouetted, dramatic cool light. | `Mais conforto para o seu caminho.` | `hbo-max.webp` |
| 16 | 23 | Serasa Data (DMP) | Dados | Audiências 3rd party e lookalike | An abstract data-driven scene: a laptop showing a clean dashboard with audience segment bubbles in emerald green and black, a person pointing at a segment; modern office, no readable numbers. | — | `experian-dmp.webp` |
| 17 | 30 | YouTube | Sociais | TrueView, bumper e masthead | A teenager and a parent watching a smart TV that shows a generic video platform home with a large masthead ad on top; sofa, daylight through curtains. | `Mais conforto para o seu caminho.` | `youtube.webp` |
| 18 | 31 | Instagram | Sociais | Feed, Stories e Reels | A hand holding a phone in a café showing a generic photo-sharing app Stories ad full screen with a swipe-up cue; latte art on the table, soft daylight. | `Mais conforto para o seu caminho.` | `instagram.webp` |
| 19 | 32 | TikTok | Sociais | In-feed e TopView | A young person holding a phone vertically, the screen showing a generic short-video app with a full-screen in-feed ad; colorful bedroom with neon accent light, shallow depth of field. | `Mais conforto para o seu caminho.` | `tiktok.webp` |
| 20 | 33 | LinkedIn | Sociais | Conteúdo patrocinado e mensagens | A professional at a laptop in a co-working space, the screen showing a generic professional network feed with a sponsored post; glass walls, plants, daylight. | `Mais conforto para o seu caminho.` | `linkedin.webp` |
| 21 | 7 | Kwai | Sociais | In-feed e splash | Friends laughing around a phone showing a generic short-video app with an in-feed ad, outdoor plaza at golden hour, candid mood. | `Mais conforto para o seu caminho.` | `kwai.webp` |
| 22 | 20 | Twitch | Sociais | Pre-roll, display e vídeo premium | A gamer at a desk with a dual monitor setup, one screen showing a generic live-streaming platform with a pre-roll ad and a side banner; RGB-lit room kept in green and black tones. | `Mais conforto para o seu caminho.` | `twitch.webp` |
| 23 | 17 | Eletromidia | DOOH | Telas de elevador, metrô e aeroportos | A modern office elevator with a vertical digital screen showing a clean outdoor sportswear ad, two commuters in business casual looking at it; reflective steel walls. | `Mais conforto para o seu caminho.` | `eletromidia.webp` |
| 24 | 18 | Google DV360 | Programática | Display, vídeo, native, áudio, CTV e DOOH | A split composition of one desk scene: laptop with a generic website showing a banner ad, a phone with a video ad, a smart TV in the background with a commercial and a tablet with a native card; all connected by thin emerald lines, bright studio light. | `Mais conforto para o seu caminho.` | `google-dv360.webp` |
| 25 | 58 | Amazon Ads / Marketplace | Programática | Produtos e marcas patrocinados | A shopper on a sofa with a tablet showing a generic online marketplace search results page with a sponsored product row at the top; shipping boxes on the floor, warm light. | `Mais conforto para o seu caminho.` | `amazon-ads.webp` |
| 26 | 53 | Interativos | Interativos | Rich media, cube, scratch, 360° | A hand interacting with a phone showing a generic interactive ad: a rotating 3D product cube of a sneaker with finger-drag arrows; clean studio background in light mint, floating UI shapes. | `Mais conforto para o seu caminho.` | `interativos.webp` |

## Ordem sugerida de geração

| Lote | Canais | Por quê |
|---|---|---|
| 1 | Spotify, Netflix, Instagram, Eletromidia | Maior visibilidade na lista; valida o estilo antes do resto |
| 2 | Demais Streaming e Sociais | Mesma linguagem de tela em casa ou no celular |
| 3 | Mobilidade | Cenas de uso cotidiano |
| 4 | Dados, Programática e Interativos | Cenas conceituais; revisar com mais cuidado |

## Conferência de cada imagem

| Item | Ok? |
|---|---|
| Nenhum logotipo, ícone de app ou texto real de terceiros | |
| Mãos e dedos corretos | |
| Somente o texto exato pedido (ou nenhum) | |
| Um toque de verde-esmeralda presente, sem excesso | |
| Legível em 280 px de largura (tamanho do card) | |
| Corte seguro: assunto fora das bordas 8% | |
