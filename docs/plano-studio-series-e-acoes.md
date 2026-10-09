# Studio: séries, ações explícitas e mesa infinita

Plano de 2026-10-09. Lançamento em **5 dias (2026-10-14)**. Por decisão do usuário, vai direto para a interface, sem A/B no Lab
antes (exceção à regra "medir no Lab antes do Studio"; medir depois do lançamento).

## Ideia central

Criar e Editar já compartilham o modelo de dados (trabalho → sessões → itens → revisões; base aceita; sessão filha).
O que muda é a interface: **uma mesa só**, um canvas infinito organizado automaticamente, onde criar, ajustar,
variar e adaptar são **ações escolhidas** pelo usuário, não inferidas da frase.

Tudo é **prototipagem em imagem** (sem HTML): anúncio, ilustrações (set), landing de vendas, landing institucional,
site (várias telas) e post orgânico.

## Entradas

| Origem | Como chega | O que a mesa faz |
|---|---|---|
| Plano pronto (Planner, pauta do Radar, briefing colado) | Várias peças num texto só | **Decompositor** quebra em lista de peças; usuário revisa (2+ peças) antes de gerar |
| Do zero | Uma ideia | **Modal de tipos** (cards com ícones) e começa uma série |
| Imagem de fora (porta Editar) | Uma imagem | Abre a mesa com uma peça, já em "Ajustar esta peça" |

## Ações (seletor no chat flutuante)

| Ação | Base | Preserva | Resultado |
|---|---|---|---|
| Ajustar esta peça | Peça selecionada (★ base aceita) | Tudo menos o pedido | Nova versão da peça |
| Nova variação | Peça selecionada como âncora | Campanha, marca, estilo | Peça irmã na série |
| Adaptar formato | Peça aprovada | Mensagem e composição | Mesma peça em outro tamanho (inclui desktop → mobile) |
| Iniciar série | Pedido ou plano | Regras da série | Lista decomposta |

Padrão do seletor: com seleção → Ajustar; série aberta sem seleção → Nova variação; mesa vazia ou texto longo → Iniciar série.
O usuário sempre vê e pode trocar antes de enviar. Com várias peças selecionadas, a instrução vale para todas.

## Receitas por tipo

| Tipo | Receita |
|---|---|
| Anúncio | A atual (diretor, uma chamada, compositor por código, revisor) |
| Ilustrações | Sem compositor; 1ª aprovada vira âncora de estilo; revisor julga consistência |
| Landing de vendas | Mockup de página; herói com oferta, prova, benefícios, CTA repetido |
| Landing institucional | Mockup; marca, propósito, credibilidade |
| Site | Série de telas; home aprovada vira âncora de header, grid, tipografia |
| Post orgânico | Feed/carrossel/story; tom de voz; carrossel é série com âncora |

## Mesa infinita

- **Layout automático**: séries em faixas horizontais; peças em colunas; versões empilhadas abaixo (★ no topo);
  variações e adaptações em ramo ligadas à origem; retiradas numa zona recolhida. Item novo entra com animação.
  Arrastar à mão fixa a posição até "Reorganizar".
- **HUD fixo**: chat flutuante embaixo ao centro; projeto/marca/séries no canto superior esquerdo; baixar/compartilhar/
  finalizar no superior direito; minimapa no inferior direito; zoom e "Ver tudo" no inferior esquerdo; inspetor
  flutuante à direita só com seleção.
- **Navegação**: arrastar o fundo, espaço+arrastar, trackpad; Ctrl+rolagem/pinça com zoom no cursor; Shift+1 ver tudo,
  Shift+2 seleção, Shift+0 100%. Nível de detalhe por zoom. Só renderiza o que está visível; miniaturas no zoom baixo.
- **Seleção e download**: clique, Shift+clique, laço; "todas da série", "todas as ★"; ZIP `série/peça/versão`.
- Canvas próprio e enxuto (sem tldraw/React Flow): itens são só imagens e o layout é automático.

## Recorte dos 5 dias

| Dia | Entrega |
|---|---|
| 1 | App React da mesa: carrega o histórico do projeto/sessão, layout automático, pan/zoom, minimapa, seleção, ZIP |
| 2 | Chat flutuante com seletor de ação ligado aos endpoints atuais (criar, editar/swap, variação, formato) |
| 3 | Decompositor (endpoint novo, Haiku) e lista de peças revisável com fila de geração |
| 4 | Modal de tipos e receitas por tipo no diretor (prompts) |
| 5 | QA em tela, ajustes, troca do link "Criar" para a mesa nova |

Fica para depois: post orgânico a partir de pauta do Radar, MCP (decompositor, marca, revisor), A/B das receitas no Lab.

## Análise de fluxos e prompts para os tipos novos (2026-10-09)

O pipeline do Criar foi feito para anúncio; os tipos novos passavam por ele com receita colada no pedido.

1. **Diretor só de anúncio** ("diretor criativo de mídia… peça publicitária", cópia título/apoio/CTA, 130 palavras).
   A receita do tipo ia no texto do pedido, não no contexto. → `creation_type` estruturado + playbook por tipo.
2. **Âncora copiava composição**: usava `variation_base`, cujo prompt dizia "finished ad… keep the layout zones".
   → **Feito:** âncora entra como referência `style` (papel já existente); variação recebe `creation_type` e, fora de
   anúncio, um texto de série que não copia objeto nem layout. Anúncio continua idêntico. Âncora explícita no inspetor (⚓).
3. **Dois modos de marca**: `branded_creative` (anúncio completo) e `neutral_asset` (ignora a marca inteira).
   → modo `brand_asset`: paleta, tipografia, motivos e proibições, sem logo carimbado nem cópia de anúncio.
4. **Revisor fixo em "paid social ad"** (`studio_review.py`): critério de CTA/cópia para ilustração e página.
   → critério por tipo (consistência com a âncora; hierarquia de seções; tom de voz).
5. **Estrutura só para anúncio** (`ad_masks`). → máscaras por código para landing (dobras, desktop/mobile), site
   (home/interna/contato), carrossel (capa/miolo/fecho) e grade de set de ilustração.
6. **Referência sem "como usar"** no Quadro. → papel por referência: Estrutura, Estilo, Identidade, Elemento.
7. Desdobrar anúncio para IAB perde o texto por código (guardar `copy` aprovado na versão e usar o compositor);
   decompositor conhece só 10 formatos e não entende dobras/páginas; ficha de estilo da série extraída da âncora.

Ordem: 1) âncora como estilo (feito) · 2) `creation_type` + playbook + `brand_asset` · 3) revisor por tipo ·
4) papel da referência · 5) máscaras de página/site · 6) desdobrar anúncio com compositor e decompositor com catálogo.
