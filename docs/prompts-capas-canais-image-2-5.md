# Capas dos canais com GPT Image 2.5 (OpenAI direto), versão 2

Tabela para gerar uma capa por canal no Studio. Atualizada em 2026-10-06: **26 canais** na vitrine, prompts **v2**. Ficaram de fora os 10 canais da categoria Portais (agora na área própria Portais e veículos, que usará **prints reais dos portais**, nunca imagem criada) e o Waze, que não existe mais.

> **Atenção:** estas capas são **geradas por IA** e mostram uma cena genérica, não o anúncio real do canal. Por isso aparecem com a etiqueta "Ilustração" e devem ser trocadas por foto real quando houver. Nenhuma reproduz logotipo, interface ou anúncio real de terceiros.

## O que mudou da v1 para a v2

| Problema da v1 | Correção na v2 |
|---|---|
| "Toque de verde" virou suéter ou moletom verde em quase todas as pessoas | Ninguém usa verde; o verde-esmeralda aparece só em **um objeto pequeno** nomeado no prompt |
| Streaming todo na mesma sala aconchegante à noite | Cada canal tem **ambiente, horário e pessoa** próprios (cozinha de manhã, avião, quarto de criança, terraço, home theater…) |
| Mesmo anúncio em todas | **Três títulos** da Vértice por categoria (Mais conforto para o seu caminho. / Vá mais longe. / Feito para o seu ritmo.) |
| Fone parecido com produto real | Fones e earbuds **genéricos** |

## Como chamar

| Item | Valor |
|---|---|
| Modelo do Studio | `gpt-image-2.5-sunburst--openai` (id na API: `gpt-image-2.5-sunburst`) |
| Rota | `POST /v1/images/generations` |
| Tamanho | `1680x944` (16:9; a API exige largura e altura divisíveis por 16, por isso não é 1664x936) |
| Qualidade | `medium` (usada nas 26 capas); `high` para uma versão final |
| Idioma do prompt | inglês, até 3.800 caracteres |
| Cota | 429 é esperado em lote; o serviço já espera e tenta de novo |
| Saída | WebP 85 em `aicentralv2/static/images/canais/capas/{slug}.webp` (principal) e `{slug}-b.webp` (segundo ângulo); a ficha lê pelo nome do arquivo |
| Script | `_gen/run_v2.py` (não versionado); prompts em `_gen/v2_cores.py` |

## Prompt completo (modelo)

```
You are rendering a finished editorial photograph for an advertising media catalog. Follow the brief literally; never add logos, brand names or readable text that were not requested.

TASK: One wide 16:9 photograph used as the cover of a media channel card.
SUBJECT AND COMPOSITION: {NÚCLEO}
STYLE: realistic commercial photography, natural light that fits the time of day described, shallow depth of field, clean modern composition, neutral warm skin tones, no heavy filters. People wear the colors described and NEVER green clothing. The emerald green (#1DBF73) appears only as the single small accent named in the brief.
TEXT ON SCREENS AND SURFACES: any screen or surface may show only abstract shapes and layout blocks. {TEXTO}
BRAND: the only brand shown is the fictional advertiser VÉRTICE (outdoor sportswear, simple mountain-peak mark in white). No real logos, trademarks, app icons or interface chrome from any real service. Headphones and earbuds are generic, never a recognizable product design.
AVOID: real brand logos, recognizable celebrities, green clothing, distorted hands, extra fingers, garbled text, watermarks, collage borders, stock-photo cliches, dark muddy shadows.
```

## Tabela dos 26 canais

| # | Canal | Categoria | O que a capa mostra | Núcleo do prompt (inglês) | Texto exato | Arquivo |
|---|---|---|---|---|---|---|
| 1 | 99 | Mobilidade | Splash e In-App no app de corrida | Morning commute in the back seat of a yellow compact taxi on a rainy day: a man in a navy jacket holds a phone showing a generic ride-hailing app splash screen with a full-screen sportswear advertisement; wet window, soft city bokeh. Emerald accent: a small green air freshener hanging from the rear-view mirror. | `Vá mais longe.` | `99.webp` |
| 2 | Uber | Mobilidade | Anúncio no app e no recibo | Night ride: a woman in a beige trench coat in the back of a dark sedan holds a phone showing a generic ride receipt page with a small sponsored banner under the fare; city lights streaking past the window. Emerald accent: her phone case. | `Vá mais longe.` | `uber.webp` |
| 3 | iFood | Mobilidade | Splash e In-App em app de delivery | Bright midday at a dining table: a young man in a white t-shirt chooses lunch on a phone showing a generic food-delivery app home with a sponsored banner; a takeaway bag and noodles on the table, sunlight from a window. Emerald accent: a small emerald ceramic bowl. | `Vá mais longe.` | `ifood.webp` |
| 4 | Logan | Mobilidade | Mídia em veículo e circuitos urbanos | A city bus wrapped with a clean outdoor sportswear advertisement driving along a wet avenue at blue hour, headlights on, reflections on the asphalt; pedestrians with umbrellas on the sidewalk. Emerald accent: the bus stop light box. | `Mais conforto para o seu caminho.` | `logan.webp` |
| 5 | Spotify | Streaming | Audio Ads, takeover e playlist patrocinada | Sunrise on a city bridge: a runner in a white tank top and grey leggings pauses to check a phone showing a generic music streaming app with a sponsored playlist cover and a banner ad; generic wired earbuds, golden light, skyline in the distance. Emerald accent: a small wristband. | `Feito para o seu ritmo.` | `spotify.webp` |
| 6 | Deezer | Streaming | Audio Ads e sessões patrocinadas | Rainy afternoon in a café: a bearded man in a denim shirt with cream over-ear headphones holds a phone showing a generic music app with a sponsored session card; laptop and flat white on a wooden table, wet window behind. Emerald accent: his phone case. | `Feito para o seu ritmo.` | `deezer.webp` |
| 7 | Amazon Music | Streaming | Audio Ads e Alexa | Morning kitchen: a woman in her sixties in a light-blue cardigan cooks while a generic smart speaker on the counter glows softly, a tablet leaning against a bowl shows a generic music app with a display ad; bright daylight, fresh fruit. Emerald accent: the soft glow ring of the speaker. | `Feito para o seu ritmo.` | `amazon-music.webp` |
| 8 | Podcast Ads (Rede) | Streaming | Host-read e DAI | A two-host podcast studio: a man in a black sweater and a woman in a grey blazer speak into boom microphones, a laptop shows an audio waveform and a sponsor card; acoustic panels, warm practical lights. Emerald accent: an LED strip behind the desk. | `Feito para o seu ritmo.` | `podcast-ads.webp` |
| 9 | Netflix | Streaming | Anúncios em vídeo 15/30s | Late-night living room: a young couple in grey hoodies share a blanket on a sofa facing a big TV that shows a generic streaming ad break with a full-screen outdoor sportswear commercial; popcorn bowl, TV glow on the walls. Emerald accent: an LED bias light behind the TV. | `Mais conforto para o seu caminho.` | `netflix.webp` |
| 10 | Globoplay | Streaming | Pre-roll, mid-roll e pause ads | Bright Sunday afternoon: a large family of three generations (grandparents, parents, kids) in colorful yellow, red and white clothes sit together on a sofa facing a TV that shows a generic streaming player paused with a sponsored overlay on the side; natural light, snacks on the table. Emerald accent: one cushion. | `Mais conforto para o seu caminho.` | `globoplay.webp` |
| 11 | Paramount+ | Streaming | Anúncios em vídeo e pause ads | A woman in cream pajamas lying in bed in a calm bedroom at dusk watches a wall-mounted TV showing a generic streaming app home with a large sponsored hero banner; bedside lamp, a book. Emerald accent: her mug on the nightstand. | `Mais conforto para o seu caminho.` | `paramount-plus.webp` |
| 12 | Samsung TV Plus | Streaming | Home screen e first screen takeover | A bright minimalist apartment in full daylight: a man in a mustard-yellow sweater stands with a remote facing a large smart TV whose home screen shows a full-width sponsored takeover banner and a row of thumbnails; wooden floor, big window. Emerald accent: an armchair. | `Mais conforto para o seu caminho.` | `samsung-tv-plus.webp` |
| 13 | Disney+ | Streaming | Anúncios em vídeo | A kids' play tent on a bedroom rug: two children in pajamas and a parent in a white shirt watch a tablet showing a generic family streaming service with a short ad break; fairy lights, toys. Emerald accent: a toy dinosaur. | `Feito para o seu ritmo.` | `disney-plus.webp` |
| 14 | Prime Video | Streaming | Pre-roll e pause ads | A traveler in a navy hoodie on an airplane window seat watches a tablet showing a generic streaming player with an ad break overlay; cabin light, clouds in the window. Emerald accent: a neck pillow. | `Feito para o seu ritmo.` | `prime-video.webp` |
| 15 | Max (HBO) | Streaming | Anúncios em vídeo | A dark home cinema room: two friends in black clothes on a leather sofa face a projector screen showing a generic premium streaming ad break; dramatic cool light, a bowl of popcorn. Emerald accent: a small LED strip under the shelf. | `Mais conforto para o seu caminho.` | `hbo-max.webp` |
| 16 | Serasa Data (DMP) | Dados | Audiências 3rd party e lookalike | A bright analytics office: a woman in a white blouse points at a laptop showing a clean dashboard with audience-segment bubbles, a colleague in a charcoal jacket watches; whiteboard, glass wall, daylight, no readable numbers. Emerald accent: the segment bubbles on the screen. | — | `experian-dmp.webp` |
| 17 | YouTube | Sociais | TrueView, bumper e masthead | Open-plan home in the afternoon: a father in a grey shirt and his teenage daughter in an orange hoodie sit at a kitchen island facing a large smart TV that shows a generic video platform home with a big masthead ad; juice glasses, sunlight. Emerald accent: a mug. | `Feito para o seu ritmo.` | `youtube.webp` |
| 18 | Instagram | Sociais | Feed, Stories e Reels | A sunny rooftop terrace café: a woman in a white linen shirt holds up a phone showing a generic photo-sharing app Stories ad full screen with a swipe-up cue; iced coffee, city rooftops behind. Emerald accent: her phone case. | `Feito para o seu ritmo.` | `instagram.webp` |
| 19 | TikTok | Sociais | In-feed e TopView | A teenager in a red varsity jacket holds a phone vertically toward the camera in a colorful bedroom full of posters, the screen showing a generic short-video app with a full-screen in-feed ad; playful mood. Emerald accent: a glowing emerald mountain-shaped neon sign on the wall. | `Feito para o seu ritmo.` | `tiktok.webp` |
| 20 | LinkedIn | Sociais | Conteúdo patrocinado e mensagens | A bright co-working space: a man in a navy suit jacket works at a laptop showing a generic professional network feed with a sponsored post; glass walls, colleagues blurred behind. Emerald accent: his water bottle. | `Mais conforto para o seu caminho.` | `linkedin.webp` |
| 21 | Kwai | Sociais | In-feed e splash | Friends in yellow, orange and white clothes laughing around a phone on a beach boardwalk at sunset; the screen shows a generic short-video app with an in-feed ad, a kiosk and palm trees behind. Emerald accent: one friend wears an emerald cap. | `Feito para o seu ritmo.` | `kwai.webp` |
| 22 | Twitch | Sociais | Pre-roll, display e vídeo premium | A gamer in a black hoodie at a dual-monitor desk in a dark room: one screen shows a generic live-streaming platform with a pre-roll ad and a side banner; mechanical keyboard, RGB lighting. Emerald accent: the RGB glow in emerald. | `Mais conforto para o seu caminho.` | `twitch.webp` |
| 23 | Eletromidia | DOOH | Telas de elevador, metrô e aeroportos | A modern office elevator with a vertical digital screen showing a clean outdoor sportswear ad; two commuters in grey and navy business casual look at it, brushed-steel walls. Emerald accent: the elevator floor indicator light. | `Mais conforto para o seu caminho.` | `eletromidia.webp` |
| 24 | Google DV360 | Programática | Display, vídeo, native, áudio, CTV e DOOH | A wide table scene without people: a laptop with a generic website banner ad, a phone with a video ad, a tablet with a native card and a smart TV in the background with a commercial; bright studio light, a notebook and pen. Emerald accent: thin emerald lines connecting the screens. | `Mais conforto para o seu caminho.` | `google-dv360.webp` |
| 25 | Amazon Ads / Marketplace | Programática | Produtos e marcas patrocinados | A shopper in a grey sweatshirt on a sofa browses a tablet showing a generic online marketplace results page with a sponsored product row at the top; shipping boxes on the floor, afternoon light. Emerald accent: emerald packing tape on a box. | `Mais conforto para o seu caminho.` | `amazon-ads.webp` |
| 26 | Interativos | Interativos | Rich media, cube, scratch, 360° | Hands in white jacket sleeves interact with a phone showing a generic interactive ad: a rotating 3D product cube of a sneaker with finger-drag arrows; clean mint studio background and floating UI shapes. Emerald accent: the interface buttons. | `Mais conforto para o seu caminho.` | `interativos.webp` |

## Conferência de cada imagem

| Item | Ok? |
|---|---|
| Nenhum logotipo, ícone de app ou texto real de terceiros | |
| Ninguém de roupa verde; verde só no objeto combinado | |
| Mãos e dedos corretos | |
| Somente o texto exato pedido (ou nenhum) | |
| Legível em 280 px de largura (tamanho do card) | |
| Ambiente e horário diferentes dos canais vizinhos | |
