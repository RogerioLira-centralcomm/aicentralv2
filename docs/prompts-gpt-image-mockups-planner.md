# Instruções para o GPT Image 2.5: mockups do Planner marketplace

Use junto com o plano `docs/plano-planner-marketplace-canais.md`. Anexe as imagens indicadas em cada prompt como referência. Gere em 2 ou 3 variações e escolha.

## Como usar

| Item | Regra |
|---|---|
| Referências a anexar | **R1** lista de Canais atual · **R2** ficha do canal 99 atual · **R3** grade de pontos do marketplace Aqui Ads · **R4** assistente em tela dividida do Aqui Ads |
| Tamanho | Desktop 1536×1024 (ou 1792×1024). Mobile 1024×1536 |
| Formato de saída | PNG, sem moldura de navegador, sem mockup de laptop |
| Idioma do texto | Português do Brasil, com acentos corretos |
| Pedir sempre | "Interface de produto realista e nítida, texto legível, sem texto inventado ilegível" |
| Revisão | Conferir acentos e números. Se um logo sair torto, trocar por quadrado neutro com a inicial |

## Bloco de estilo (cole no início de todo prompt)

```
Você é um designer de produto sênior. Crie o mockup de uma tela de aplicação web (SaaS de planejamento de mídia), em alta fidelidade, vista de frente, em tela cheia, sem moldura de navegador.

Linguagem visual a PRESERVAR da referência R1/R2 (nossa interface atual): barra lateral esquerda clara de 240 px com logo "Planner" e itens Início, Novo planejamento, Planos, Radar, Canais (ativo, fundo verde claro), Audiências, Formatos, Interativos, Portais, Places; fundo branco quase neutro; texto grafite; cor de ação verde-escuro (#1F5C3F); cantos arredondados de 10 a 12 px; bordas finas cinza muito claro; sombra sutil; tipografia sans-serif limpa (Inter ou similar); espaçamento generoso; faixa de créditos do mês e avatar "Apolo · CENTRALCOMM" no rodapé da barra lateral.

Padrões a ADOTAR da referência R3 (marketplace): cards com fotografia grande no topo e selos pequenos sobre a foto; trio de métricas com ícone e rótulo pequeno; sem preço (no lugar, o botão "Adicionar ao plano" e um link discreto "Solicitar cotação"); botão de ação em contorno verde dentro do card e um coração de salvar; chips de filtro arredondados no topo; alternador de exibição em dois botões (grade e lista); banner intercalado colorido entre linhas de cards.

Proibido: qualquer preço, custo ou valor em reais (o produto não exibe valores, tudo é cotado; onde a referência mostra preço, use o botão "Solicitar cotação"), mapa, banner de cookies, laranja da marca de terceiros, logotipos reais legíveis de terceiros que você não saiba reproduzir com fidelidade (use o logo como quadrado com a inicial se tiver dúvida), textos em inglês, lorem ipsum, dados absurdos.
```

## Prompt 1: lista de Canais (desktop)

Anexar: R1, R3.

```
[BLOCO DE ESTILO]

TELA: "Canais" do Planner, redesenhada como marketplace.

Cabeçalho da página: título "Canais", subtítulo "Onde a campanha aparece e o papel que cada canal cumpre no plano." À direita, dois seletores: "Todas as marcas" e "Sem projeto".

Abaixo: campo de busca largo "Buscar por nome, descrição ou categoria", chips de categoria com contagem: "Todos 37" (ativo, preenchido grafite), "Streaming 11", "Mobilidade 4", "Portais 8", "Programática 5", "Interativos 3", "Mais filtros". À direita, o alternador de exibição com dois ícones (grade ativa, lista).

Grade de 4 colunas de cards verticais brancos, cada um com:
- foto 16:9 no topo mostrando um anúncio real em contexto (ex.: anúncio dentro do app, banner em portal de notícias, anúncio em TV conectada), cantos superiores arredondados;
- sobre a foto, no canto superior esquerdo, logo do canal em quadrado branco de 28 px e um selo "Streaming"; no canto superior direito, selo "Mensurável";
- nome do canal em semibold;
- uma linha de descrição curta, em cinza;
- trio de métricas com ícone: "Alcance +50M", "Viewability 86%", "Conclusão 92%";
- botão "Adicionar ao plano" em contorno verde, largura total menos o botão de coração.

Canais nos cards: Spotify, Netflix, Globoplay, Uber, iFood, G1, Amazon Ads, Prime Video. Um card (Netflix) já está "No plano": botão verde preenchido "No plano ✓".

Entre a primeira e a segunda linha, um banner largo lilás-claro (tom suave que combine com o verde da marca, não laranja) com ilustração simples de um robô-mascote amigável, título "Não sabe por onde começar?", texto "Conte o objetivo e o Cadu monta o plano com você." e botão escuro "Planejar".

Barra fixa no rodapé da área de conteúdo: "3 canais no plano" com mini logos empilhados e botão verde "Revisar plano →".

Mantenha a barra lateral exatamente como na referência R1, com "Canais" ativo.
```

## Prompt 2: ficha do Canal (desktop)

Anexar: R2, R3.

```
[BLOCO DE ESTILO]

TELA: ficha de um canal, "Spotify", no Planner, redesenhada como página de produto de marketplace.

Topo: breadcrumb "Canais / Spotify". À direita, botão verde preenchido "Adicionar ao plano" e um botão secundário de coração "Salvar".

Hero: à esquerda, um carrossel de fotos grande (60% da largura) com um anúncio de áudio exibido no celular e um banner de vídeo na tela do app; pontos de paginação e miniaturas abaixo. À direita (40%): logo do Spotify em quadrado de 56 px, nome "Spotify", selos "Streaming · áudio", "Mensurável"; descrição de duas linhas; grade 2×3 de métricas (nenhum valor em reais, nenhum preço) com rótulo pequeno e número grande: "Alcance +50M ouvintes", "Tempo médio 2h10", "Viewability 86%", "Conclusão 92%", "Engajamento 1,4%", "Modelo de compra Leilão e reserva".

Navegação interna fixa logo abaixo, em abas com contagem: "Visão geral", "Formatos 6", "Audiências 8", "Exemplos 12", "Como comprar", "Novidades 3". "Visão geral" ativa, sublinhado verde.

Conteúdo, em seções com título à esquerda e corpo à direita, separadas por linha fina:
1. "Papel no plano": três cartões pequenos (Alcance em áudio, Frequência em deslocamento, Complemento ao digital).
2. "Quando usar cada segmentação": cartões em 2 colunas com "QUANDO" e "EXEMPLO" em caixa-alta pequena, como na referência R2.
3. "Formatos": faixa horizontal de cartões, cada um com a miniatura da peça renderizada na proporção correta (áudio 30s com capa, display 300×250, vídeo 9:16), nome, dimensões e botão "+ Adicionar".
4. "Audiências neste canal": faixa de cartões com ícone, nome ("Ouvintes de podcast", "Heavy users de playlist"), tamanho estimado e botão "+ Adicionar".
5. "Exemplos de anúncios": galeria em mosaico com 6 imagens de anúncios em contexto, legenda com marca e formato; legenda com marca e formato.

À direita, coluna estreita fixa com o resumo "No seu plano" (itens adicionados e total estimado).

Barra lateral esquerda idêntica à referência R2, com "Canais" ativo.
```

## Prompt 3: Formatos como vitrine (desktop)

Anexar: R1, R3.

```
[BLOCO DE ESTILO]

TELA: "Formatos" do Planner como vitrine visual.

Cabeçalho "Formatos", subtítulo "Todas as peças que cada canal aceita, com o tamanho certo.". Chips por família com contagem: "Todos 112", "Display 34", "Vídeo 28", "CTV 12", "Áudio 9", "Interativos 14", "Social 15". Filtro lateral compacto por canal com logos.

Grade de 4 colunas. Cada card: área superior cinza-clara com a peça renderizada na proporção real do formato, centralizada, dentro de um mini frame de dispositivo (telefone para 9:16, TV para 16:9, retângulo para display 300×250 e 728×90), sempre com um anúncio plausível de uma marca fictícia; abaixo, nome do formato, dimensões em chip ("300×250"), tipo ("Display"), e linha "Roda em" com 3 mini logos de canais e "+4". Botão "Adicionar ao plano" em contorno e coração.

Um card em destaque mostra o tamanho 970×250 com a proporção larga bem visível.

Barra lateral esquerda como em R1 com "Formatos" ativo.
```

## Prompt 4: Audiências (desktop)

Anexar: R1, R3.

```
[BLOCO DE ESTILO]

TELA: "Audiências" do Planner, visual e conectada aos canais.

Cabeçalho "Audiências", busca, chips de categoria ("Demografia", "Interesse", "Comportamento", "Momento de vida", "Profissão"). Grade de 3 colunas de cards: no topo uma ilustração vetorial simples e acolhedora representando o perfil (sem rostos fotográficos), nome ("Mães de crianças até 6 anos"), tamanho estimado em destaque ("12,4 mi de pessoas"), barra fina de distribuição por faixa etária, linha "Onde está" com mini logos de 4 canais e "+3", botão "Adicionar ao plano" e coração.

Mantenha o mesmo padrão de card do prompt de Canais para consistência.
```

## Prompt 5: "Planejar" (assistente em tela dividida)

Anexar: R4, R1.

```
[BLOCO DE ESTILO]

TELA: assistente de planejamento em tela dividida, inspirado na referência R4, mas na identidade do Planner (verde, não laranja).

Cabeçalho superior simples: logo "Planner" à esquerda, "Planejar" com selo "Beta" ao centro-direita, e "Sair" à direita.

Metade esquerda (45%): painel de fundo verde muito claro com título grande "Planejar" e selo "Beta", subtítulo "Conte sua ideia, trace um objetivo e deixe o restante com o Cadu.". Abaixo, uma ilustração vetorial editorial e colorida (estilo flat moderno, personagens estilizados sem rosto detalhado) de uma pessoa montando um plano de mídia, cercada por telas de celular, TV e painel urbano mostrando peças de campanha de uma marca fictícia, com linha de tempo e cursores. Paleta: verdes, amarelo-mostarda, lilás e grafite.

Metade direita: pergunta "Qual é o objetivo da sua campanha?" com indicador de passo "1 de 5". Quatro cartões de resposta empilhados, cada um com título e descrição: "Gerar awareness — Fazer a marca ser lembrada por mais gente.", "Lançar um produto — Impacto alto e burburinho para um lançamento.", "Gerar leads e vendas — Foco em ação e conversão.", "Campanha sazonal — Datas comemorativas e picos de venda.". Abaixo, campo "ou escreva um objetivo personalizado" com placeholder "Digite seu objetivo…". Rodapé com botão "Voltar" e botão verde "Continuar". Uma lista discreta dos passos seguintes: Objetivo · Verba e período · Praça · Audiência · Revisão.
```

## Prompt 6: versão mobile da lista de Canais

Anexar: o resultado aprovado do Prompt 1.

```
[BLOCO DE ESTILO]

Adapte a tela de Canais aprovada para celular (390×844), mesma identidade: cabeçalho compacto com menu, busca, chips rolando na horizontal, cards de largura total em uma coluna com foto 16:9, selos, trio de métricas em linha, preço e botão "Adicionar ao plano", e barra fixa inferior "3 canais no plano · Revisar plano". Sem barra lateral; navegação por menu hambúrguer.
```

## Prompts de apoio: imagens para preencher os cards

**Uso apenas para compor os mockups de design.** O produto usa só imagens reais do acervo; nenhuma imagem gerada vai para a interface. Gerar sem logos legíveis de terceiros.

### Foto de anúncio em contexto (capa de canal)

```
Fotografia realista, 16:9, de um anúncio {FORMATO: ex. banner de vídeo / anúncio em app / painel digital / TV conectada} do canal {CANAL}, exibido em {CONTEXTO: ex. celular na mão de uma pessoa num ônibus / sala de estar com TV}, marca anunciante fictícia "{MARCA}", peça com título curto em português "{TITULO}". Luz natural, profundidade de campo suave, enquadramento limpo, sem texto ilegível, sem logotipo real de terceiros. Estética de portfólio de agência.
```

### Peça renderizada para miniatura de formato

```
Mock plano, fundo cinza muito claro, mostrando um anúncio {DIMENSÃO: 300×250 / 728×90 / 970×250 / 9:16} com layout publicitário profissional de uma marca fictícia "{MARCA}", título "{TITULO}", botão de chamada "{CTA}", imagem de produto nítida. Proporção exata {PROPORÇÃO}. Sem moldura de dispositivo, sem texto ilegível.
```

### Ilustração para card de audiência

```
Ilustração vetorial flat, acolhedora, 4:3, representando o perfil "{AUDIENCIA}" em uma cena do cotidiano, personagens estilizados sem traços de rosto detalhados, paleta de verdes, mostarda, lilás e grafite, fundo verde muito claro, sem texto.
```

## Checklist de conferência dos mockups

| Item | Ok? |
|---|---|
| Barra lateral idêntica à atual (itens e ordem) | |
| Verde da marca nas ações, nada de laranja de terceiros | |
| Português com acentos | |
| Sem mapa e sem banner de cookies | |
| Cada card tem foto, selos, métricas e botão, e nenhum valor em reais | |
| Ficha do canal tem navegação interna e blocos de formatos, audiências e exemplos | |
| Nenhum preço, custo ou valor em reais em tela alguma | |

---

## Prompts adicionais: Formatos (referência R5, vitrine de formatos da Aqui Ads)

Anexar: R5 (vitrine de formatos), R1.

### Prompt 7: vitrine de Formatos com prévia em escala

```
[BLOCO DE ESTILO]

TELA: "Formatos" do Planner, redesenhada com prévia em escala, inspirada na referência R5, mas na nossa identidade (verde, barra lateral do Planner).

Cabeçalho "Formatos", subtítulo "Escolha o tamanho certo para cada canal." Barra de filtros em uma linha: busca, "Ambiente de exibição", "Formato", "Tipo de mídia", "Canal", "Ordenar", e alternador Grade/Lista. Abaixo: "95 formatos encontrados" à esquerda; à direita "0 itens selecionados"; links "Selecionar todos · Limpar seleção".

Grade de 3 colunas de cards brancos. Em cada card:
- canto superior esquerdo: selo pequeno com ícone de pino e o ambiente ("Portais", "Streaming", "Mobilidade", "TV conectada");
- canto superior direito: checkbox;
- centro: um retângulo VERDE ESCURO desenhado exatamente na proporção do formato, com uma arte publicitária simples de marca fictícia dentro, e cotas pretas finas com setas indicando "largura 300 px" em cima e "altura 250 px" ao lado;
- rodapé: nome do formato em semibold ("Retângulo médio"), medida "(L)300 × (A)250 px" em cinza, botão "Ver detalhes" em contorno e botão verde pequeno "+ Adicionar".

Formatos variados e proporções diferentes nos 9 cards: 300×250, 728×90 (larga e baixa), 160×600 (alta e estreita), 970×250, 9:16 vídeo vertical em moldura de celular, 16:9 em moldura de TV, 300×600, 320×50 mobile, 1:1 social. Em um card sem arte, mostrar o retângulo tracejado com ícone, nunca imagem quebrada.

Barra fixa inferior: "3 formatos selecionados" e botão verde "Adicionar ao plano".

Sem banner de cookies. Barra lateral como R1 com "Formatos" ativo.
```

### Prompt 8: ficha do Formato

Anexar: R5, R2.

```
[BLOCO DE ESTILO]

TELA: ficha do formato "Retângulo médio 300×250" no Planner.

Topo: breadcrumb "Formatos / Retângulo médio", botão verde "Adicionar ao plano" e botão secundário "Criar no Studio".

Hero em duas colunas: à esquerda, a prévia grande em escala (retângulo com cotas) com abas "Em escala" (ativa) e "Em contexto"; à direita, selos "Display", "Estático", título, descrição de duas linhas, e três métricas: "Tamanhos 3 opções", "Peso máximo 150 KB", "Canais compatíveis 12".

Abaixo, abas fixas: "Especificações", "Boas práticas", "Onde usar 12", "Exemplos 6".
Especificações: tabela limpa com linhas Dimensões, Peso máximo, Arquivos aceitos (JPG, PNG, GIF, HTML5), Safe area, Observações; botão "Baixar template".
Boas práticas: duas colunas "Faça" (ícones de check verdes) e "Evite" (ícones de x vermelhos suaves), três itens cada.
Onde usar: faixa de cartões com logo do canal, nome e categoria.
Exemplos: mosaico de 6 anúncios reais em contexto.

Barra lateral como R1, "Formatos" ativo.
```

### Checklist adicional

| Item | Ok? |
|---|---|
| Proporção do retângulo bate com a medida escrita | |
| Cotas com seta e unidade em px | |
| Nenhum card com imagem quebrada | |
| Seleção em lote visível | |
| Verde da marca no lugar do laranja da referência | |

---

## Ilustrações do banner e dos estados vazios (para uso real no produto)

Referência de estilo: R8 (banner lilás com mascote). **Não copiar o personagem da referência**: ele é a marca de terceiros. Criar um mascote original do Planner.

### Regras comuns (cole no início de cada prompt)

```
Ilustração vetorial editorial em estilo flat moderno, formas geométricas ousadas e arredondadas, contornos limpos sem traço fino, sombras apenas em blocos chapados, sem gradientes complexos, sem textura de pintura, sem texto nem letras na imagem, sem logotipos. Fundo TRANSPARENTE (PNG com canal alfa). Composição centralizada com margem de 8% em volta. Paleta fechada: verde Planner #1F5C3F e verde-claro #86D9A8, lilás #B8A6FF, mostarda #F5B83D, coral #FF6B4A, grafite #1D2433, branco #FFFFFF. Alta nitidez, bordas sem serrilhado.
```

### 1. Mascote do banner (arquivo `mascote-planner.png`, 1024×1024)

```
[REGRAS COMUNS]

Crie um mascote original e simpático para um produto de planejamento de mídia: uma criatura curiosa em forma de lupa-binóculo viva, corpo arredondado verde-escuro com UM olho grande e expressivo (íris verde-clara, pupila grafite, brilho branco), segurando com um braço rosa-coral um pequeno megafone mostarda. Sem boca visível, sensação de descoberta e entusiasmo. Pose de três quartos olhando para a direita, ligeiramente inclinada, braço levantado. Proporções fofas, sem rosto humano, sem referência a personagens existentes.
```

### 2. Banner completo (arquivo `banner-planejar.png`, 1600×360)

```
[REGRAS COMUNS]

Banner horizontal 1600×360 com fundo sólido lilás #CDBEFF e cantos arredondados de 24 px. À esquerda, o mascote do Planner (criatura verde-escura de um olho só, megafone mostarda, braço coral) saindo ligeiramente do canto inferior, tamanho grande. Deixe 60% da largura à direita LIVRE e limpa (sem elementos) para o texto ser aplicado depois em HTML. Pequenas formas decorativas discretas (círculos e estrelinhas de 4 pontas) em verde-claro e mostarda espalhadas só no lado esquerdo. Sem texto.
```

### 3. Cartão de passos (arquivo `passos-planejar.png`, 800×800)

```
[REGRAS COMUNS]

Ilustração para um cartão intermediário de grade, mostrando dois quadros de interface empilhados e levemente deslocados: o de cima com fundo lilás e uma imagem placeholder (ícone de montanha e sol) mais barras de texto cinzas; o de baixo com borda verde e outra imagem placeholder. Círculos numerados coral "1" e "2" (apenas os numerais dentro dos círculos) no canto de cada quadro. Uma mão rosa-coral com cursor de seta clicando no quadro de cima. Sensação de "monte seu plano em passos". Sem outro texto.
```

### 4. Estado vazio: nenhum canal encontrado (`vazio-busca.png`, 800×800)

```
[REGRAS COMUNS]

O mascote do Planner (criatura verde-escura de um olho só) olhando por uma lupa grande mostarda para uma prateleira vazia, com pequeno ponto de interrogação coral flutuando acima. Expressão curiosa, sem tristeza. Sem texto exceto o símbolo "?".
```

### 5. Estado vazio: plano sem itens (`vazio-plano.png`, 800×800)

```
[REGRAS COMUNS]

O mascote do Planner segurando uma prancheta em branco com um lápis, ao lado de uma pilha pequena de cartões coloridos (lilás, verde-claro, mostarda) ainda por organizar. Clima de "vamos começar". Sem texto.
```

### 6. Cabeçalho do assistente "Planejar" (`planejar-hero.png`, 1200×1200)

```
[REGRAS COMUNS]

Cena editorial para a tela do assistente "Planejar": uma pessoa estilizada sem traços faciais detalhados (pele em tom neutro variado, cabelo curto verde-escuro, blazer mostarda, calça lilás) em pé, com um tablet na mão, cercada por telas flutuantes de formatos de mídia (celular vertical, TV, painel urbano e banner horizontal) com peças de campanha abstratas coloridas, uma linha de tempo fina atravessando a cena e dois cursores de seta. O mascote do Planner pousado em cima do tablet. Equilíbrio entre verde, lilás e mostarda.
```

### Como me enviar

| Item | Regra |
|---|---|
| Formato | PNG com fundo transparente, nomes exatamente como acima |
| Tamanho | Pode mandar menores (por exemplo 512 px do lado maior), eu comprimo para WebP |
| Onde vão | `aicentralv2/static/images/planner/illustrations/` |
| Uso | Banner a cada 8 cards da lista de Canais, cartão de passos na grade, estados vazios e a tela do assistente |
| Conferir | Sem texto na imagem, olho único do mascote igual em todas, paleta fechada |
