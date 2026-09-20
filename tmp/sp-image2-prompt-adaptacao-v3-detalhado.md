# Prompt detalhado de adaptação — Smart Planner público v3

## Arquivo de referência

Use como imagem-base de edição:

`tmp/sp-centralx-public-one-page-mockup-v3-demografia.png`

Preserve a composição geral, a ordem dos conteúdos e a linguagem visual de produto da última versão. Esta é uma adaptação controlada, não uma nova direção criativa.

## Objetivo da adaptação

Refinar o mockup público do Comercial Planner da CentralComm para ficar mais leve, mais legível e mais próximo de uma página real do produto. A página deve parecer um relatório executivo público produzido pela CentralComm, não uma peça de publicidade, uma apresentação e nem um dashboard genérico.

O resultado deve continuar sendo uma página única compacta, com poucos níveis de hierarquia, texto respirado, dados fáceis de escanear e demografia genérica claramente marcada como hipótese ou validação pendente.

## Bloqueio de marca do template

Manter obrigatoriamente a marca CentralComm do template público atual. A logo não é uma sugestão visual e não pode ser removida, substituída ou reinterpretada:

- manter a logo oficial CentralComm no canto esquerdo da barra superior;
- manter o texto de produto “Planejamento de mídia” ao lado da logo;
- manter a identificação do produto como “Planejamento de mídia”, sem acrescentar o nome de outro produto;
- usar o asset real fornecido pelo template (`house.logo`, com fallback para `/static/images/cc_logo.png`), nunca uma logo desenhada pelo Image 2;
- preservar proporção, área de respiro e variante de contraste da logo;
- não aplicar filtro, inverter cores, redesenhar, simplificar ou trocar a logo por um monograma;
- repetir a assinatura CentralComm apenas no rodapé se ela já existir no template, sem criar uma terceira presença decorativa;
- no mockup, representar a logo como área reservada fiel à posição do template e deixar a aplicação final para HTML.

## Design system correto

Use exclusivamente a linguagem do Design System do produto Comercial Planner/Tailwind existente:

- tema de produto `data-theme="centralcomm"`;
- fonte Inter;
- `#FFFFFF` como superfície principal;
- `#F8F9FA` como base secundária;
- `#DEE2E6` para bordas e separadores discretos;
- `#1F2937` para texto principal de produto;
- `#1E4D4F` para ação primária e sinais da marca;
- `#153638` para áreas de maior contraste;
- `#F3B71B` apenas como destaque pontual, nunca como grande superfície;
- `#9CCF31` somente como status ou sinal mínimo, não como cor dominante;
- raio de 4px a 8px nos controles e painéis;
- sombra muito discreta, equivalente a produto administrativo;
- botões retangulares, sem pílulas;
- grid, flex, borders, spacing e estados visuais compatíveis com Tailwind/DaisyUI;
- sem linguagem do CentralComm Ads, sem estética de criativo IAB e sem paleta editorial inventada.

## Alterações obrigatórias

### 1. Reduzir bordas

- Remover aproximadamente metade das bordas visíveis da versão v3.
- Não envolver todos os blocos em cards individuais.
- Manter apenas:
  - a superfície geral do relatório;
  - o painel de resumo executivo;
  - separadores horizontais essenciais;
  - a área de mix e defesa quando necessário para leitura.
- Substituir bordas por espaço, alinhamento, mudança sutil de fundo e hierarquia tipográfica.
- Evitar aparência de formulário ou dashboard cheio de caixas.
- Não usar linhas verticais decorativas em excesso.

### 2. Melhorar respiro de texto

- Aumentar line-height do corpo para aproximadamente 1.5–1.6.
- Separar título, subtítulo, label e parágrafo com margens claras.
- Manter largura de leitura entre 45 e 72 caracteres por linha.
- Nunca comprimir um parágrafo para caber em uma altura fixa.
- Nunca cortar texto no final do bloco.
- Nunca quebrar palavras no meio.
- Nunca posicionar texto sobre outro texto ou sobre ícones.
- Quando um texto for longo, aumentar o bloco verticalmente em vez de reduzir a fonte.
- Corpo mínimo de 14px na referência visual; implementação final deve respeitar a escala do produto.

### 3. Ajustar tipografia

- Usar apenas Inter.
- Título da página: peso 700 ou 800, entre 32px e 40px, no máximo duas linhas.
- Título de seção: 20px a 24px, peso 600 ou 700.
- Headline do resumo executivo: 24px a 30px, no máximo três linhas.
- Corpo e defesa: 14px a 16px, line-height generoso.
- Dados e valores: 16px a 20px, peso 600.
- Metadados: 12px, sentence case, sem excesso de tracking.
- Não usar labels em caixa alta como decoração.
- Não usar serif, monospace, itálico ornamental ou fonte condensada.
- Não usar uma headline gigantesca que domine a página inteira.

### 4. Cabeçalho e hero

Manter a barra superior do produto:

- logo CentralComm e “Planejamento de mídia” à esquerda;
- “Planejamento de mídia”;
- status de atualização;
- “Falar sobre este plano”;
- “Copiar link”;
- “Salvar PDF”.

No hero:

- título: “Estacionamento de Confins”;
- anunciante abaixo do título;
- facts em uma única linha responsiva;
- Anunciante;
- Objetivo: Tráfego;
- Público;
- Período: 60 dias;
- não repetir os mesmos facts no hero e no resumo executivo;
- não inserir imagem de fundo;
- não inserir foto de aeroporto, carro, avião ou celular;
- usar apenas o espaço, a tipografia e uma pequena regra de cor para dar presença.

### 5. Resumo executivo

Manter um único painel de resumo executivo, com header teal discreto ou faixa de identificação:

- label: “Leitura executiva”;
- headline: “Transformar intenção de viagem em tráfego qualificado para reserva online.”;
- corpo curto, entre três e cinco linhas;
- coluna lateral com informações realmente úteis e não repetidas;
- espaço generoso entre headline e corpo;
- área de leitura sem imagem;
- contraste compatível com WCAG;
- nenhum texto cortado.

### 6. Estratégia em ação

Manter três colunas abertas e alinhadas:

1. **Captura de demanda**
   - busca por pessoas com intenção ativa;
   - canal: Google Ads.

2. **Contexto**
   - presença em portais e sites relevantes no momento de planejamento;
   - canal: Rede de portais e sites.

3. **Proximidade**
   - reforço em mapas e buscas locais para quem está em Confins e entorno;
   - canal: Places.

Regras:

- ícones lineares pequenos e discretos;
- sem caixas individuais pesadas;
- separação feita principalmente por espaço e alinhamento;
- no máximo três linhas de explicação por coluna;
- tags retangulares pequenas, nunca pills grandes.

### 7. Ecossistema e demografia lado a lado

Manter uma seção em grid de duas colunas, com o mesmo início e a mesma altura visual:

#### Coluna esquerda — Ecossistema de distribuição

Mostrar no máximo oito itens. Cada linha deve conter:

- logo oficial ou espaço reservado para logo HTML;
- nome do canal;
- papel curto;
- status confirmado ou planejado.

Itens principais do exemplo:

- Google Ads — Busca e performance para alta intenção — Ativo;
- Rede de portais e sites — Cobertura contextual — Ativo;
- Places — Presença em mapas e buscas locais — Ativo;
- Extensões sociais — Reforço de alcance e engajamento — Planejado.

Não listar todos os portais. Não usar “programática”, “Google Display” ou “rede Google” como título. Não inventar logos; reservar aplicação posterior em HTML quando necessário.

#### Coluna direita — Perfil demográfico

Adicionar perfil genérico, sem inventar percentuais, alcance ou pesquisa. Usar exatamente estes tipos de informação:

- **Faixa etária:** adultos em idade ativa — A validar;
- **Classe social:** perfis com intenção de viagem e consumo — A validar;
- **Região:** Confins, RMBH e rotas de viagem — A validar;
- **Comportamento:** pesquisa de viagens, mobilidade e reserva online.

O título deve ser “Perfil demográfico”. Usar “A validar” com discrição, sem transformar o bloco em alerta. A demografia é uma leitura de planejamento, não um dado de audiência confirmado.

As duas colunas devem ficar lado a lado no desktop e empilhar no mobile sem perder a ordem. Não colocar a demografia dentro do card de canais.

### 8. Mix e defesa

Manter a área abaixo do grid de canais/demografia, com duas colunas:

#### Mix

Exibir barras horizontais simples e legíveis:

- Google Ads — 55%;
- Rede de portais e sites — 37%;
- Places — 8%.

Os números devem aparecer somente porque foram fornecidos no planejamento. O gráfico deve ser pequeno, sem donut complexo, sem efeitos 3D e sem rótulos sobrepostos.

#### Defesa

Usar uma defesa de até 70 palavras:

“A estratégia equilibra performance e cobertura, unindo canais de alta intenção a ambientes editoriais e buscas locais, para maximizar o alcance de viajantes e gerar tráfego qualificado para reserva online.”

Adicionar uma pequena lista de premissas apenas se houver espaço. Não repetir todo o briefing.

### 9. Contato

Manter uma faixa final compacta:

- avatar pequeno;
- nome do executivo;
- cargo;
- frase curta;
- botão retangular “Conversar no WhatsApp”;
- QR/link apenas como apoio, sem competir com o CTA.

## Direção de composição

```text
┌──────────────────────────────────────────────────────────────┐
│ CentralComm · Planejamento de mídia · ações                  │
├──────────────────────────────────────────────────────────────┤
│ Plano de mídia executivo                                     │
│ Estacionamento de Confins                                    │
│ anunciante                         objetivo  público período  │
├──────────────────────────────────────────────────────────────┤
│ Resumo executivo                                             │
│ tese curta e corpo respirado          fatos úteis             │
├──────────────────────────────────────────────────────────────┤
│ Como a estratégia vira ação                                  │
│ captura de demanda | contexto | proximidade                   │
├──────────────────────────────┬───────────────────────────────┤
│ Ecossistema de distribuição  │ Perfil demográfico            │
│ canais agrupados              │ faixa, classe, região, uso   │
├──────────────────────────────┴───────────────────────────────┤
│ Mix de mídia                 │ Defesa                       │
├──────────────────────────────────────────────────────────────┤
│ contato executivo + WhatsApp + compartilhamento              │
└──────────────────────────────────────────────────────────────┘
```

## Restrições finais

- Não adicionar imagem grande.
- Não adicionar hero fotográfico.
- Não usar CentralComm Ads como referência visual.
- Não remover, esconder, trocar ou redesenhar a logo oficial CentralComm do template.
- Não substituir `house.logo` por uma marca inventada ou por texto sem o asset oficial disponível.
- Não usar creme, terracota, neon ou layout de anúncio.
- Não criar um card para cada frase.
- Não repetir facts.
- Não inventar dados demográficos quantitativos.
- Não transformar “A validar” em destaque.
- Não gerar logos finais dentro da imagem.
- Não usar texto falso, texto cortado ou texto ilegível.
- Não utilizar a imagem gerada como página final.

## Nota para implementação

O mockup serve somente como referência. A versão real deve ser montada no Comercial Planner com HTML semântico, CSS existente, tokens do `design-system.css`, componentes compatíveis com o tema `centralcomm` e JavaScript vanilla para ações de navegação, cópia, PDF e WhatsApp. A barra superior deve continuar usando somente a logo real da CentralComm recebida em `house.logo`, com fallback para `/static/images/cc_logo.png`; a imagem gerada nunca deve fornecer a logo. Não exibir nem mencionar o nome de outro produto na página pública. O layout deve ser responsivo, acessível, imprimível e compatível com os dados reais do plano.
