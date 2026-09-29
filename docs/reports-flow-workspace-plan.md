# Reports · plano da interface de Fluxos

## Objetivo

Transformar Fluxos em uma área de trabalho visual para desenhar e analisar jornadas. O editor deve ocupar a tela, colocar o canvas no centro da tarefa e manter criação, edição e leitura dos resultados no mesmo contexto. A referência de interação é o canvas de jornada do Funnelytics; a linguagem visual segue padrões do Untitled UI, com identidade CentralX.

O Funnelytics apresenta publicamente um canvas visual para mapear jornadas com drag and drop, associar dados ao mapa e organizar o trabalho com tags, notas, checklists e imagens. O CentralX deve aproveitar o paradigma de mapa livre e contexto analítico no canvas, sem copiar a paleta ou as funções de anotação sem relação direta com tracking de mídia e CRM. Fonte: [Funnelytics](https://funnelytics.io/).

## Diagnóstico da experiência atual

### Já existe

- Três visões por cliente: criar/listar, editar e acompanhar a jornada do site.
- Validação do domínio, criação de fluxo e criação/compartilhamento da Super Tag.
- Canvas com blocos de origem, página, formulário, evento, WhatsApp, conversão e erro.
- Arrastar blocos, selecionar, ligar blocos, alinhar automaticamente, ligar uma sequência e ajustar à grade.
- Busca na paleta, descoberta de páginas reais, propriedades do bloco selecionado e seleção de campanha em páginas descobertas.
- Autosave com estado pendente/salvando/salvo/erro, salvar manualmente, teste simulado, copiar snippet, publicar e despublicar.
- Leitura de métricas observadas e confirmadas no monitoramento da jornada.

### O que atrapalha o foco

1. O editor ainda vive dentro do shell completo do Reports. O CSS muda o shell apenas quando a sidebar já está recolhida; a preferência fica em `localStorage`, portanto a tela não garante o estado compacto ao abrir o editor.
2. A navegação Criar / Editar / Jornada do site continua visível durante edição, junto com o cabeçalho geral. Ela compete com o espaço do editor e parece uma seção de dashboard, não uma ferramenta de canvas.
3. A faixa superior do editor acumula seletor de fluxo, estado de salvamento, salvar, copiar tag, simular, despublicar/publicar. Em larguras médias ela quebra de forma difícil de escanear.
4. Paleta e páginas descobertas compartilham a mesma coluna. Blocos de construção e conteúdo real do site têm objetivos diferentes.
5. A busca da paleta altera o DOM diretamente, em vez de filtrar estado React. Isso complica acessibilidade, testes e manutenção.
6. O canvas depende principalmente de scroll, drag e botões direcionais. Não há navegação por teclado, desfazer/refazer, zoom/pan explícitos, minimapa ou modo de conexão guiado.
7. A ligação visual é desenhada com uma curva simples que parte sempre da direita de um bloco para a esquerda do outro. Ramificações, cruzamentos e conexões com rótulos ficam difíceis de interpretar.
8. A publicação só bloqueia fluxo sem blocos. Falta uma revisão que diga quais entradas, conexões, páginas, conversões ou configurações precisam de atenção e leve a pessoa ao bloco afetado.
9. Teste simulado já informa que os eventos são fictícios, mas precisa ficar visualmente separado de validação real da instalação e de dados observados.
10. O painel de propriedades não comunica claramente quais campos são editáveis por tipo, quais são metadados e quais valores afetam atribuição.

## Princípios visuais

### Tokens

- **Fundo:** `#f9fafb`; superfície principal `#ffffff`.
- **Texto:** `#101828` e secundário `#667085`.
- **Linhas:** `#eaecf0` e controles `#d0d5dd`.
- **Ação principal:** azul CentralX/Untitled UI `#175cd3`.
- **Estados semânticos:** verde para publicado/saudável, âmbar para pendente/atenção e vermelho para erro ou ação destrutiva.
- **Regra de cor:** não atribuir uma cor de destaque a cada tipo de bloco ou canal. Usar ícones monocromáticos; reservar cor para seleção, ação e estado. Logos de plataforma podem preservar as cores do ativo oficial, sem pintar os cards.
- **Tipografia e controles:** Inter já usada no Reports, escala curta, contorno fino, raio consistente entre 6 e 9 px, sombra mínima e foco visível.
- **Canvas:** cinza quase branco, grade pontilhada discreta e blocos brancos com borda; origem/saída recebem apenas uma indicação semântica sutil.

### Composição

```text
┌ mini-sidebar ┬─────────────────────────────────────────────────────────────┐
│ ícones       │ breadcrumb · nome do fluxo · estado salvo · ações             │
│ Reports      ├──────────────┬─────────────────────────┬────────────────────┤
│              │ blocos       │                         │ propriedades       │
│              │ / páginas    │       canvas livre      │ do bloco           │
│              │ descobertas  │                         │                    │
└──────────────┴──────────────┴─────────────────────────┴────────────────────┘
```

No desktop, o canvas recebe a maior parte da largura (alvo de 65–75%). A paleta ocupa cerca de 220 px; o inspetor, 280–320 px. Os painéis laterais podem recolher sem reduzir o canvas. Em telas estreitas, paleta e inspetor viram drawers; o canvas permanece como área de trabalho principal.

## Arquitetura da interface

Manter as rotas e APIs atuais e quebrar o componente `Flow` em componentes React menores. No primeiro corte, `Flow` permanece responsável por buscar dados e coordenar ações; editor, lista, toolbar, propriedades e canvas recebem estado e handlers por props. Um hook pode concentrar a edição local sem alterar o payload persistido.

```text
<FlowWorkspace>
  <FlowWorkspaceShell>
    <FlowMiniSidebar />
    <FlowWorkspaceHeader />
    <FlowCanvasEditor>
      <FlowToolPanel />
      <FlowCanvasViewport>
        <FlowCanvasToolbar />
        <FlowGraph />
        <FlowMinimap />
      </FlowCanvasViewport>
      <FlowInspector />
    </FlowCanvasEditor>
  </FlowWorkspaceShell>
</FlowWorkspace>
```

### Componentes e responsabilidades

| Componente | Responsabilidade e interação |
| --- | --- |
| `FlowWorkspace` | Controla modo (`list`, `editor`, `monitor`), cliente, fluxo selecionado, permissões e navegação por URL. Evita perder alterações ao trocar de fluxo ou sair. |
| `FlowWorkspaceShell` | Define a área de tela inteira e aplica a sidebar compacta no editor, sem sobrescrever a preferência salva fora dele. |
| `FlowMiniSidebar` | Barra de ícones estreita com tooltips, item Fluxos selecionado e controle para expandir a navegação temporariamente. Em mobile, substitui o rail por um botão de menu. |
| `FlowWorkspaceHeader` | Breadcrumb, nome editável, domínio, status Rascunho/Publicado, sincronização e ações. Mantém ação primária única: “Publicar” no rascunho; “Despublicar” como ação secundária no publicado. |
| `FlowListPage` | Tela inicial com busca, filtro de estado e lista/tabela de fluxos: nome, domínio, status, saúde da tag, atualização e abrir. Criação por botão que abre painel/modal lateral. |
| `FlowCreateDialog` | Campo de URL, validação do domínio, nome sugerido/editável, estado de Super Tag existente ou que será criada e CTA explícito. Erros ficam junto ao campo. |
| `FlowCanvasEditor` | Grade de três colunas responsiva; administra abertura/recolhimento de paleta e inspetor sem desmontar estado do grafo. |
| `FlowToolPanel` | Abas “Blocos” e “Páginas do site”. Busca React controlada; grupos de tipos; arrastar ou clicar para adicionar; análise/continuação da descoberta em seção independente. |
| `FlowCanvasViewport` | Área de pan/zoom, captura de teclado, drop de blocos, seleção por clique, seleção múltipla futura e fundo com grade. Aplica limites de escala e mantém coordenadas estáveis. |
| `FlowCanvasToolbar` | Zoom −/+, porcentagem, centralizar/ajustar, grade, alinhar, desfazer/refazer, simular e menu de ações secundárias. Exibe instrução contextual durante conexão. |
| `FlowGraph` | Renderiza nodes, edges e handles de conexão a partir do estado normalizado. Seleção e edição não dependem da posição em arrays. |
| `FlowNode` | Card por tipo com ícone monocromático, tipo, nome, URL/evento, badge de entrada/saída e estado. No modo de dados, pode mostrar sessões/avanço sem transformar a cor do card em legenda. |
| `FlowEdge` | Conexão SVG com pontos de entrada/saída, curvas roteadas, rótulo opcional e estado selecionado. Clique seleciona; Delete remove com confirmação quando necessário. |
| `FlowInspector` | Propriedades do node ou edge selecionado. Formulários por tipo, validação inline, associação de campanha, campos do formulário e ação remover. Estado vazio explica como selecionar. |
| `FlowValidationPanel` | Lista bloqueios e avisos antes de publicar. Cada item seleciona o node/edge, foca o painel e leva o canvas até ele. |
| `FlowSimulationPanel` | Configura cenário fictício, mostra sequência simulada e resultados claramente marcados como dados de teste; não mistura esses números com produção. |
| `FlowInstallPanel` | Estado da tag real, snippet, domínio autorizado, data do último evento real e instrução de validação. Separado de simulação. |
| `FlowMonitorView` | Acompanhamento de sessões, páginas, passagem entre nodes, conversões observadas e confirmações CRM, com definições e períodos explícitos. |
| `FlowToast` / `FlowConfirmDialog` | Feedback de salvar/copiar/testar/publicar; confirmação para despublicar, excluir node ou descartar alterações. Erros preservam o rascunho. |

## Modelo de estado React

Separar estado persistido do editor de estado transitório da interface.

```ts
type FlowEditorState = {
  flowId: string;
  name: string;
  status: 'draft' | 'published';
  nodes: FlowNodeData[];
  edges: FlowEdgeData[];
  selected: { kind: 'node' | 'edge'; id: string } | null;
  dirty: boolean;
  saveState: 'saved' | 'pending' | 'saving' | 'error';
  validation: { errors: FlowIssue[]; warnings: FlowIssue[] };
};

type FlowUiState = {
  activePanel: 'blocks' | 'site-pages';
  inspectorOpen: boolean;
  paletteOpen: boolean;
  zoom: number;
  pan: { x: number; y: number };
  snapToGrid: boolean;
  interaction: 'idle' | 'drag-node' | 'connect' | 'pan' | 'marquee';
  historyIndex: number;
};
```

Usar reducer para mudanças no grafo (`ADD_NODE`, `UPDATE_NODE`, `DELETE_NODE`, `ADD_EDGE`, `DELETE_EDGE`, `MOVE_NODES`, `APPLY_LAYOUT`, `UNDO`, `REDO`). O histórico guarda snapshots compactos ou comandos reversíveis, com limite definido; autosave só persiste o estado confirmado após o debounce. Busca, painel aberto, zoom e pan não marcam o fluxo como alterado.

## Interações prioritárias

### Criar e abrir

1. “Novo fluxo” abre modal/painel lateral sem perder o contexto da lista.
2. Validar domínio habilita a criação e apresenta nome do site, status HTTP e situação da tag.
3. Criar navega para `/reports?flow_view=edit&flow_id=…` e abre o editor focado; a descoberta de páginas pode começar com progresso e cancelamento visíveis.
4. Lista preserva busca, filtro, cliente e período ao voltar.

### Construir no canvas

- Clique ou drag and drop adiciona node; node novo recebe foco no inspetor e posição próxima ao centro visível.
- Handles de conexão aparecem em hover/seleção; arrastar de um handle a outro cria edge. Alternativa acessível: “Conectar a…” no inspetor.
- Edge mostra rótulo editável quando a jornada possui ramificação. Não conectar uma sequência automaticamente sem revisão; “Conectar em sequência” vira ação secundária com prévia e confirmação.
- Pan com espaço + arrastar ou botão do meio; zoom com controles visíveis, `Ctrl/Cmd + roda` opcional; “Ajustar” centraliza todos os nodes.
- Grade e snap seguem preferências locais; mover vários nodes e alinhamento são undoable.
- Ao adicionar página descoberta, abrir prévia dos dados detectados e escolher se será Entrada, Página, Formulário, Conversão ou Erro. Não inserir silenciosamente no canvas.

### Editar e salvar

- Inspetor acompanha seleção; alterar campo atualiza preview do node e marca rascunho pendente.
- Autosave com estado textual e indicador discreto. Em erro, manter alterações locais, oferecer tentar novamente e copiar diagnóstico técnico.
- Antes de trocar de fluxo ou sair: salvar automaticamente e só pedir decisão se o save falhar.
- Undo/redo cobre edição, movimento, conexão e exclusão; atalhos `Cmd/Ctrl+Z`, `Shift+Cmd/Ctrl+Z` ou `Ctrl+Y`.

### Validar, simular e publicar

- “Simular” abre painel com percurso fictício e aviso persistente “Simulação · não são eventos reais”.
- “Teste real da instalação” exige URL dentro do domínio autorizado, abre o site e espera o primeiro evento real; mostra aguardando/recebido/falhou separadamente.
- “Publicar” executa validação de domínio, pelo menos um ponto de entrada, caminho alcançável, node sem configuração obrigatória, conversão/saída configurada e ciclos inválidos. Apenas bloqueios impedem publicação; avisos podem ser aceitos.
- Resultado da publicação informa a versão/data publicada. Edições exigem despublicar ou gerar nova versão conforme regra de backend.
- Conversão observada pelo tracking nunca aparece como venda CRM confirmada; o monitor mantém fontes separadas.

## Sidebar e foco

- No editor desktop, recolher a sidebar para o rail de ícones (aprox. 56–64 px) ao entrar. Não remover a navegação nem bloquear acesso ao restante do Reports.
- Preservar a preferência anterior: modo de foco é temporário e não grava `collapsed` no `localStorage` global. Ao sair do editor, restaurar a preferência anterior.
- Deixar botão/atalho para expandir temporariamente; usar tooltip e `aria-label` em cada ícone.
- No editor mobile, sidebar vira drawer acionado por botão; não ocupar uma faixa permanente.
- Ocultar filtros globais que não afetam o grafo. Período continua disponível apenas em Monitor/Jornada.

## Regras de cor e sinais

Não introduzir paleta por tipo de canal. Usar: azul para seleção, links e ação primária; cinzas para estrutura e conteúdo; verde para publicado/saudável; âmbar para pendência/aviso; vermelho para erro/bloqueio. Ícones, nomes e rótulos fazem a distinção dos tipos. Em dados de performance, exibir números e legenda textual, nunca depender só da cor.

## Compatibilidade técnica

- Manter o contrato atual de `config.nodes` e `config.edges` durante a primeira fase; incluir campos novos somente se o backend já aceitar ou após migração explícita.
- Preservar `client_id`, permissões, domínio autorizado, referências de campanha e regra de leitura de fluxo publicado.
- Criar adaptador entre o estado de editor e o JSON existente para que zoom/pan/seleção/undo não sejam gravados junto da configuração de negócio.
- Descoberta de páginas, instalação da Super Tag, monitoramento e ingestão CRM continuam usando as APIs atuais.
- Não misturar métricas com dados simulados. Toda métrica no canvas precisa informar período, unidade e origem.

## Fases propostas

### Fase 1 — Workspace e hierarquia

- Sidebar compacta temporária no editor; retirar tabs do shell de edição; header fixo e três painéis claros.
- Criar/listar vira página dedicada; criação em modal/painel lateral.
- Busca de paleta passa para estado React e descoberta recebe aba própria.
- Tokens de cor/tipo/estados e responsividade desktop/tablet/mobile.

### Fase 2 — Canvas confiável

- Separar `FlowGraph`, `FlowNode`, `FlowEdge`, viewport e inspetor.
- Pan, zoom, fit, seleção clara, handles de edge, conexões curvas e rótulo de ramificação.
- Undo/redo e atalhos, mantendo todas as operações acessíveis por botão.

### Fase 3 — Qualidade de publicação

- Painel de validação com erros/avisos acionáveis e navegação até o bloco.
- Simulação e teste real com linguagem, estados e resultados independentes.
- Autosave robusto com recuperação local após falha e feedback claro.

### Fase 4 — Leitura analítica no mapa

- Modo “Mapa” com sessões alcançadas, passagem e queda por etapa.
- Período e origem explicitados; dados de tracking e CRM em trilhas distintas.
- Filtros de campanha/plataforma aplicados com contexto preservado ao sair do editor.

## Critérios de aceite

- Abrir um fluxo coloca canvas e conteúdo principal em foco, com sidebar compacta e opção de retornar à largura anterior.
- Criar, editar, selecionar, mover, conectar, configurar e excluir funcionam com mouse e teclado.
- Zoom, pan, fit, undo e redo não alteram o contrato persistido do fluxo.
- Busca de blocos e descoberta de páginas são React controlados, sem mutação direta de DOM.
- Toda alteração mostra pendente/salvando/salvo/erro e não se perde quando a API falha.
- Validação leva ao node ou conexão com problema e bloqueia publicação somente para erros definidos.
- Teste fictício, teste da tag real, eventos observados e confirmações CRM são visualmente e semanticamente distintos.
- A interface usa somente neutros, azul de ação e cores semânticas de estado; nodes e canais não viram um arco-íris.
- Lista, editor e monitor continuam responsivos, com foco acessível, labels e redução de movimento.
