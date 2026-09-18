# Skins editoriais do link público — CentralComm

## Decisão de produto

O hero não será escolhido pela praça. A praça pode sugerir uma atmosfera dentro do conteúdo do plano, mas a identidade visual do relatório público será escolhida por uma skin CentralComm ou herdada de uma marca aprovada.

O gestor escolhe a skin no CentralX, vê uma prévia, aplica e pode pedir uma nova variação ao agente. A página pública recebe apenas o resultado aprovado: tokens, logo correta, imagem de apoio e instruções de composição.

## Catálogo de cinco skins

### 1. Papel Editorial

Relatório de decisão com papel claro, tinta azul-petróleo, regras finas e uma imagem de hero que desaparece em fade para o papel. É a skin padrão para qualquer cliente sem sistema de marca aprovado.

- Hero: título grande à esquerda, imagem recortada à direita, fade horizontal para `paper`.
- Gráficos: barras horizontais, números grandes, linhas de leitura.
- Elemento ilustrativo: pequeno marcador 3D de papel dobrado ou volume de dados, quase plano.
- Melhor uso: planos executivos, leitura de mix e defesa comercial.

### 2. Sinal / Radar

Skin mais analítica, com blocos de dados, linhas de conexão e um “radar” abstrato que traduz jornada, canais e audiência.

- Hero: headline curta sobre uma malha de sinais; imagem ocupa só 35% da área.
- Gráficos: barras, anéis finos e nós de jornada.
- Elemento ilustrativo: esfera translúcida com pontos conectados, sem aparência de dashboard SaaS.
- Melhor uso: planos de performance, tráfego, retargeting e dados.

### 3. Órbita Suave

Skin contemporânea com formas 3D leves, translúcidas e muito espaço negativo. O visual sugere movimento sem virar uma peça de anúncio.

- Hero: uma forma orbital 3D ancorada no canto direito; texto fica em superfície limpa.
- Gráficos: trilhas de jornada com pontos de passagem.
- Elemento ilustrativo: anéis, cápsulas e esfera fosca em baixa saturação.
- Melhor uso: mobilidade, viagens, tecnologia e planos com jornada multicanal.

### 4. Moldura de Marca

Skin para quando cliente ou agência tem identidade aprovada no CRM v3. O sistema CentralComm organiza a página, mas a marca vinculada lidera a cor, logo e personalidade.

- Hero: cor primária da marca como campo de assinatura; imagem sempre recebe overlay de contraste.
- Gráficos: usam a paleta secundária aprovada, nunca cores aleatórias.
- Elemento ilustrativo: motivo visual extraído da auditoria da marca, sem inventar símbolo.
- Melhor uso: clientes com `brand_profile`, logo e leitura de marca aprovados.

### 5. Noite de Apresentação

Skin premium escura para propostas de reunião, com palco azul profundo, pontos de luz discretos e acento dourado CentralComm.

- Hero: grande headline branca, imagem atmosférica no fundo e fade escuro para leitura.
- Gráficos: barras e números em papel claro dentro do palco, com poucos acentos.
- Elemento ilustrativo: objeto 3D fosco, como prisma, cubo ou lente, sem brilho cromado.
- Melhor uso: propostas comerciais, apresentações para diretoria e planos com forte defesa.

## Contrato de dados

Persistir no plano, sem alterar o conteúdo editorial:

```json
{
  "public_design": {
    "skin_id": "paper-editorial",
    "selection_mode": "manual|auto|brand",
    "brand_ref": "crm:client:190",
    "brand_source": "crm_v3_brand_profile",
    "brand_revision": "approved-revision-id",
    "tokens": {
      "paper": "#F7F5EF",
      "ink": "#10252D",
      "accent": "#D5AA3B",
      "line": "#D8E2DF",
      "logo_variant": "dark-on-paper"
    },
    "hero": {
      "asset_url": "/static/images/smart_planner/generated/...png",
      "prompt": "...",
      "status": "approved|draft|requested"
    },
    "illustration": {
      "kind": "orbital|signal-network|paper-volume|brand-motif|prism",
      "asset_url": "",
      "status": "approved|draft|none"
    },
    "agent_note": "Instrução curta para recompor o HTML público"
  }
}
```

`selection_mode=brand` só pode ser usado quando o perfil de marca foi lido e aprovado. `selection_mode=auto` escolhe uma das cinco skins pela leitura do plano, mas não escolhe logo ou cor de cliente sem evidência.

## Ligação com CRM v3

1. O editor lista marcas de clientes finais e agências disponíveis para o usuário.
2. Cada item mostra nome, logo, cores detectadas, status da leitura e prontidão.
3. Ao selecionar uma marca, o CentralX carrega somente:
   - `brand_profile.design_system_ads` aprovado;
   - `brand_profile.brand_summary`, `creative_guidelines`, `visual_motifs` e `fonts`;
   - logo e variantes existentes no CRM;
   - evidências visuais marcadas como oficiais.
4. A marca não altera automaticamente o texto do plano. Ela altera a camada visual do relatório.
5. Se a marca não tiver sistema aprovado, o editor mostra “usar skin CentralComm” e oferece “solicitar leitura da marca”.

## Tratamento de logo

- Nunca aplicar filtro CSS para transformar logo branca em escura.
- Preferir variante aprovada `dark-on-paper` em fundos claros.
- Se existir somente logo branca, trocar a superfície do hero para `ink` ou `brand-primary`.
- Se nenhuma variante funcionar com contraste 4.5:1, bloquear a aplicação e pedir uma versão de logo ao gestor.
- A logo é renderizada no HTML; o GPT Image 2 nunca recebe a tarefa de desenhar logo ou texto.

## Modal de seleção no CentralX

Título: **Escolha a pele do link público**

Coluna esquerda:

- cards das cinco skins;
- preview pequeno do hero;
- nome, intenção e status.

Coluna direita:

- marca atual do plano;
- seletor “CentralComm / Agência / Cliente final”;
- logo e paleta detectadas;
- aviso de contraste;
- botão `Aplicar skin`;
- botão `Pedir outra variação`.

Ao aplicar, salvar `public_design` e invalidar o cache do documento público. A alteração deve gerar uma revisão visual, não uma nova geração do texto do plano.

## Card de canais no one page

Adicionar um card editorial de “Ecossistema de distribuição”, preferencialmente depois da estratégia e antes da defesa. O card transforma muitos canais em uma leitura executiva curta:

- limite visual de oito itens;
- logos vindas do catálogo oficial de canais, nunca geradas pela IA;
- cada item com logo, nome e papel curto, como “Ambiente proprietário”, “Extensão B2B” ou “Cobertura contextual”;
- redes sociais entram como extensão ou possibilidade, sem sugerir contratação já realizada;
- portais em grande quantidade devem ser agrupados em “Rede de portais” ou “Rede de conteúdo”, sem listar domínios e sem usar “programática” ou “Google” como título;
- usar “+ rede de portais qualificados” como overflow quando houver itens além do limite;
- quantidade de portais só deve aparecer quando vier de dado confirmado do plano;
- o card precisa funcionar mesmo quando houver apenas dois ou três canais.

Contrato sugerido:

```json
{
  "type": "channels",
  "title": "Ecossistema de distribuição",
  "items": [
    {"id": "serasa", "label": "Serasa", "logo": "", "role": "Ambiente proprietário"},
    {"id": "meta", "label": "Meta", "logo": "", "role": "Extensão social"},
    {"id": "linkedin", "label": "LinkedIn", "logo": "", "role": "Extensão B2B"},
    {"id": "display-network", "label": "Rede de portais", "logo": "", "role": "Cobertura contextual"}
  ],
  "overflow_label": "+ rede de portais qualificados"
}
```

## Fluxo do agente

1. Ler o plano e identificar hierarquia: tese, mix, audiência, gráficos, defesa e pendências.
2. Ler a marca selecionada somente se houver vínculo CRM e revisão aprovada.
3. Escolher ou receber a `skin_id`.
4. Produzir um `hero_prompt`, `illustration_prompt` e `agent_note`.
5. Gerar somente imagem atmosférica/ilustração; não gerar logo, gráfico ou texto.
6. Aplicar tokens e assets no template HTML público.
7. Retornar ao gestor:
   - resumo da mudança;
   - arquivos usados;
   - skin escolhida;
   - contraste e logo validados;
   - instruções de mudança no HTML;
   - opção de aprovar, destacar ou pedir outra variação.

## Cinco prompts para GPT Image 2

### Prompt 1 — Papel Editorial

Imagem atmosférica horizontal para hero de um relatório executivo de planejamento de mídia da CentralComm. Composição editorial premium, fundo de papel quente e uma única forma abstrata de papel dobrado com sombra suave, pequena camada de dados representada por barras e linhas muito discretas, luz lateral natural, azul-petróleo profundo e acento dourado mínimo, grande área negativa limpa no lado esquerdo para texto HTML, imagem desaparecendo suavemente no papel no lado esquerdo, textura sofisticada e baixa saturação. Não inserir nenhuma palavra, número, logotipo, gráfico legível, interface, pessoa ou marca. A imagem é apoio visual; o conteúdo e os dados serão renderizados no HTML.

### Prompt 2 — Sinal / Radar

Imagem horizontal abstrata para o hero de um relatório executivo de mídia CentralComm. Criar uma malha elegante de sinais: nós luminosos pequenos conectados por linhas finas, uma esfera translúcida central e camadas de profundidade muito sutis, sensação de audiência, jornada e retargeting, fundo azul-petróleo quase preto com lavagem azul suave e um pequeno acento dourado, contraste controlado e espaço negativo amplo no lado esquerdo para headline HTML. Estética editorial de dados, não dashboard e não tecnologia genérica. Sem texto, números, logos, ícones de aplicativo, marcas ou gráficos legíveis.

### Prompt 3 — Órbita Suave

Imagem horizontal de apoio para um plano executivo CentralComm, com uma composição 3D leve e sofisticada: anéis orbitais foscos, cápsulas arredondadas e uma esfera acetinada em movimento lento, representando uma jornada multicanal. Fundo claro de papel com azul-esverdeado e azul profundo, sombras macias, muito espaço negativo para texto, formas concentradas no lado direito, visual silencioso e premium. Sem neon, sem chrome, sem texto, sem logotipo, sem pessoas e sem elementos de interface. A imagem deve funcionar como atmosfera atrás de uma seção hero e não como anúncio completo.

### Prompt 4 — Moldura de Marca

Imagem horizontal de apoio para um relatório público CentralComm usando a identidade visual aprovada de uma marca parceira. Usar exclusivamente as cores fornecidas pelo sistema de marca, preservar o clima visual e os motivos oficiais descritos na referência, construir uma moldura abstrata e elegante ao redor de uma área central limpa para headline HTML, com luz e contraste suficientes para manter leitura. Não recriar ou desenhar o logotipo; não inserir texto; não inventar símbolos, mascotes ou produtos; não usar cores fora da paleta aprovada. A imagem deve parecer uma extensão editorial da marca, não um anúncio final.

### Prompt 5 — Noite de Apresentação

Imagem horizontal premium para o hero de uma proposta executiva da CentralComm. Palco azul profundo quase preto, um prisma ou cubo fosco com bordas suaves flutuando discretamente no lado direito, feixe de luz dourado muito controlado, atmosfera de sala de apresentação e decisão, profundidade cinematográfica, baixa saturação, superfície escura com espaço negativo no lado esquerdo para headline branca HTML. Sem brilho exagerado, sem glassmorphism, sem neon, sem texto, sem logotipo, sem números e sem gráficos legíveis.

## Regras do prompt do agente

- Sempre informar `skin_id`, cliente/agência selecionado, objetivo do plano e tipo de hero.
- Usar dados do plano para a atmosfera, nunca para desenhar texto dentro da imagem.
- A imagem deve reforçar a leitura do plano, não competir com os gráficos.
- Não usar a praça como identidade primária.
- Não gerar logo, nome do cliente, headline, CTA, QR ou percentuais dentro da imagem.
