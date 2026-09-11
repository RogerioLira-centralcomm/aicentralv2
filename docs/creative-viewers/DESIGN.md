# Ambientes de mídia — evidências e direção

Captura: 8 de setembro de 2026. Método: Firecrawl `branding,images` e
`screenshot` nas páginas oficiais. Os screenshots são evidência de desenvolvimento
armazenada apenas no cache local `.firecrawl/`; não são usados como backgrounds,
assets ou conteúdo editorial no produto.

## Vocabulário compartilhado

- Base Centralcomm: papel `#F3F7F6`, tinta `#183436`, ouro `#C9A95F`,
  linha `#D9E3E3` e branco `#FFFFFF`.
- Portais: barra de rede, masthead, navegação curta, ticker, grade editorial e
  slot publicitário real.
- CTV: navegação em overlay, hero com profundidade, slot real, rail 16:9 e
  controles discretos.
- Fontes proprietárias observadas servem apenas como evidência. O runtime usa
  pilhas locais (`Avenir Next`, `Segoe UI`, Arial e sans-serif).
- Todo ambiente mostra: “Simulação de ambiente · sem afiliação com o veículo”.

```text
Portal
┌ rede ─────────────────────────────────────────────────────┐
│ masthead / logo oficial / busca                           │
├ navegação ────────────────────────────────────────────────┤
│ manchete fictícia │      slot publicitário      │ rail    │
└───────────────────────────────────────────────────────────┘

CTV
┌ logo / navegação                                      ○  ┐
│ hero fictício               ┌ slot publicitário ┐        │
│                             └────────────────────┘        │
│ [ rail 16:9 ][ rail 16:9 ][ rail 16:9 ][ rail 16:9 ]     │
└───────────────────────────────────────────────────────────┘
```

## Perfis observados

### G1

- Fonte: <https://g1.globo.com/>
- Observado: vermelho `#C4170C`, base clara, Open Sans/Globotipo, masthead
  vermelho, títulos editoriais grandes e grid com bastante respiro.
- Inferido para o shell: ritmo editorial espaçado, rede escura discreta e slot
  como parte da grade, sem copiar notícias reais.
- Logo: SVG selecionado pelo `branding` da home oficial, salvo como
  `aicentralv2/static/images/creative-viewers/g1.svg`.

### CNN Brasil

- Fonte: <https://www.cnnbrasil.com.br/>
- Observado: logo SVG transparente, CNN Sans, navegação densa, vermelho,
  preto e branco, ticker econômico e hierarquia de breaking news.
- Inferido para o shell: masthead compacto, navegação densa e ticker,
  preservando uma leitura mais urgente que a do G1.
- Logo: SVG oficial retornado pela home, salvo como `cnn-brasil.svg`.

### SBT News

- Fonte: <https://sbtnews.sbt.com.br/>
- Observado: Public Sans, azul `#006EFF`, azul-marinho `#051E41`, botões
  arredondados e organização editorial equilibrada.
- Inferido para o shell: masthead azul-marinho/azul, menos densidade que CNN,
  presença de vídeo e chamadas de broadcast.
- Logo: SVG selecionado pelo `branding`, salvo como `sbt-news.svg`.

### Netflix

- Fonte: <https://www.netflix.com/br/>
- Observado: fundo preto, vermelho `#E50914`, Netflix Sans, hero de alto
  contraste, controles contidos e navegação sobre a imagem.
- Inferido para o shell: canvas preto, luz vermelha localizada, hero à esquerda,
  rail cinematográfico e seleção branca.
- Logo: PNG oficial retornado pelo `branding`, salvo como `netflix.png`.

### Disney+

- Fonte: <https://www.disneyplus.com/pt-br>
- Observado: fundo `#040714`, ciano `#33DDFF`, azul profundo, tipografia
  Inspire e CTAs em formato pílula.
- Inferido para o shell: fundo azul-noturno, luz ciano, maior separação entre
  hero e rail e sensação de franquias/família.
- Logo: PNG oficial retornado pelo `branding`, salvo como `disney-plus.png`.

### HBO Max

- Fonte: <https://www.hbomax.com/br/pt>
- Observado: fundo `#120C1D`, Max Sans/Inter, roxos e azul acinzentado,
  superfícies premium e raios de luz suaves.
- Inferido para o shell: canvas púrpura quase preto, hero compacto, rail denso e
  acabamento premium.
- Logo: PNG oficial retornado pelo `branding`, salvo como `hbo-max.png`.

## Redes sociais

Os shells sociais são aparelhos, não galeria de cards. O anúncio preenche o
poço (`data-ad-well`) no pixel do formato. Disclaimer igual aos portais.

```text
Instagram / Facebook / TikTok / Shorts
┌ status / logo ────────────────────────────────────────────┐
│ header do post (avatar, nome, patrocinado)                │
│ ┌ poço da mídia (1:1, 4:5 ou 9:16) ─────────────────────┐ │
│ │ criativo                                                │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ações / caption / rail — chrome da rede, sem afiliação    │
└───────────────────────────────────────────────────────────┘

LinkedIn desktop / YouTube watch
┌ barra da rede ────────────────────────────────────────────┐
│ card ou player                                            │
│ ┌ poço 1.91:1 ou 16:9 ──────────────────────────────────┐ │
│ │ criativo                                                │ │
│ └─────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

### Instagram

- Fonte: <https://www.instagram.com/>
- Observado: fundo `#FAFAFA`, tinta `#262626`, acento magenta/laranja no
  avatar, post com header, poço e ações em linha.
- Inferido: telefone 390×844; feed 1:1 e 4:5 sem letterbox; Story/Reels em
  full-bleed com faixa de progresso e caption na safe area inferior.
- Logo: marca geométrica local em `instagram.svg`.

### LinkedIn

- Fonte: <https://www.linkedin.com/>
- Observado: canvas `#F3F2EF`, azul `#0A66C2`, card branco, tipografia
  profissional.
- Inferido: desktop para Share 1.91:1; compactação mobile para quadrado e
  retrato 4:5. O anúncio preenche o card, sem barra de reações inventada
  por cima da peça.
- Logo: marca local em `linkedin.svg`.

### TikTok

- Fonte: <https://www.tiktok.com/>
- Observado: canvas preto, acentos ciano `#25F4EE` e rosa `#FE2C55`, rail
  direito e caption inferior.
- Inferido: full-bleed 9:16 no telefone; copy e CTA dentro da safe area,
  longe do rail.
- Logo: marca local em `tiktok.svg`.

### YouTube

- Fonte: <https://www.youtube.com/>
- Observado: player 16:9, chrome de watch escuro, vermelho `#FF0000`.
- Inferido: In-feed preenche o player; Shorts no telefone, mesmo gesto do
  vertical com caption e rail.
- Logo: marca local em `youtube.svg`.

## Uso e licenciamento

As marcas pertencem aos respectivos titulares. Os arquivos foram obtidos das
homes oficiais exclusivamente para identificar o contexto de simulação de mídia.
Não implicam parceria, endosso ou afiliação. O produto não incorpora screenshots,
fotografias, textos editoriais ou fontes proprietárias dos sites.
