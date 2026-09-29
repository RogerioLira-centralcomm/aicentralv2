# Reports com Untitled UI — diagnóstico e plano

Data: 29/09/2026. Escopo: interface React ativa de Reports, suas 11 áreas, editor e monitoramento de fluxos. O diagnóstico abaixo é o baseline anterior à execução. O progresso atual está registrado ao fim do documento.

## Diagnóstico

O Reports possui um shell com `SolutionSidebar`, `ReportsPageHeader` e `ReportsFilterBar`, mas o restante da interface é composto sobretudo por controles HTML e CSS específicos. `main.jsx` tem cerca de 1.400 linhas e concentra as áreas e seus formulários; `styles.css` tem 649 linhas, além de 156 linhas de `flow-workspace.css`. Há 81 ocorrências de elementos e padrões de formulário, tabela e abas no arquivo principal. Esses números indicam concentração e repetição; a decisão de componente deve vir da inspeção de cada fluxo, não apenas dessa contagem.

| Prioridade | Problema observado | Evidência atual | Efeito / decisão |
| --- | --- | --- | --- |
| P0 | O kit ainda não é componente de Reports | `package.json` contém React 18, Vite 6 e Tailwind 3; não contém `react-aria-components`, `@untitledui/icons` ou fonte do kit. `vite.reports.config.mjs` compila CSS próprio. | Uma troca de cores/classes não atende ao pedido. Fazer prova de integração do componente oficial em build isolado de Reports antes de migrar páginas. |
| P0 | Identidade visual tem fontes contraditórias | `tokens.css` define a skin Reports em laranja (`#c17b35`); `styles.css` inicia com `--r-blue:#2871d2` e depois sobrescreve o root do Reports com `#175cd3`; `SolutionSidebar` recebe `accent="#2871d2"`. | Definir uma escala azul semântica para a superfície Reports já usada nas telas. Auditar consumidores do token laranja e eliminar as sobrescritas divergentes. |
| P0 | Shell e telas usam anatomias diferentes | Cabeçalho e barra de filtros estão em `PageChrome.jsx`; contas, campanhas, importações, links, acessos e fluxos montam cabeçalhos, abas, controles e ações independentes em `main.jsx`. | Um `ReportsPageLayout` deve definir breadcrumb, título, contexto do cliente, ações, filtros e largura. Páginas devem compor esse contrato. |
| P1 | Densidade e legibilidade oscilam | Há estilos antigos de 10–12 px e overrides posteriores que elevam parte dos textos; cartões, tabelas e controles variam de 31 a 40 px. | Fixar escalas para dados densos, rótulos, corpo, métricas, toque e foco. Preservar densidade analítica sem encolher controles interativos. |
| P1 | CSS acumula camadas de correção | `styles.css` contém base, resets locais, regras repetidas e media queries por área; `flow-workspace.css` acrescenta outra camada. | Migrar por componente, remover seletores substituídos na mesma etapa e medir regressões em outras páginas. Evitar novos overrides globais. |
| P1 | Abas e confirmações têm comportamento disperso | Fluxos/importações montam `role=tab` manualmente; revogação, publicação e restauração usam `window.confirm`. | Usar Tabs e Dialog oficiais com foco, teclado, Escape, retorno de foco e consequências explícitas. Manter confirmação curta e contextual. |
| P1 | Tabelas e ações por linha não têm contrato único | Contas, campanhas, importações, eventos, links e acessos usam tabelas/listas com ações, truncamento e vazio diferentes. | Um `ReportsDataTable` deve padronizar header, sort permitido, ações, carregamento, vazio, erro, paginação e overflow no tablet. Não esconder colunas necessárias por regra CSS genérica. |
| P1 | Estado de dados é pouco uniforme | Algumas páginas preservam dados na falha; outras usam `Empty` genérico; o shell pode bloquear tudo quando `data.ready` é falso. | Criar estados por capacidade: carregando, sem dados, sem permissão, fonte desconectada, parcial, desatualizado e falha com tentar novamente. Mostrar fonte e atualização perto da métrica. |
| P1 | Fluxos têm necessidades próprias | Editor tem paleta, canvas e inspector; monitoramento tem métricas e conexões. O bloqueio de celular já existe para Flow. | Compartilhar shell e primitivas; manter canvas como composição especializada. Editor sem contadores, monitoramento com contadores. Tablet exige teclado físico/virtual, toque e foco estável. |
| P2 | Contexto de cliente, campanha, projeto e marca precisa de hierarquia | Cabeçalho troca `client_id`, mas páginas adicionam contexto de campanha e associação opcional de projeto em locais próprios. | Mostrar cliente como escopo persistente; campanha/projeto/marca como associações visíveis, opcionais e autorizadas. Um filtro não deve sugerir posse ou herança de dados que o backend não garante. |

## Sistema visual alvo

Untitled UI React fornece a anatomia e o comportamento das primitivas. CADU fornece marca, contexto do cliente, nomes e regras de dados. Usar componentes oficiais de base ou wrappers finos `Cadu*` quando já existirem. Registrar versão do CLI e proveniência dos arquivos. Não usar componentes PRO sem licença. O guia oficial lista `react-aria-components`, ícones e utilitários; a configuração de tema usa recursos do Tailwind 4. O bundle atual de Reports não utiliza isso, portanto a primeira entrega é uma fronteira de build e CSS própria. Não executar `untitledui init` na raiz.

| Região | Composição planejada |
| --- | --- |
| Shell | `SolutionSidebar` existente + `ReportsPageLayout` com cliente, breadcrumb, título, descrição curta e ações. Respeitar a navegação de solução já existente. |
| Filtros | Filter bar oficial composta com Select, Date Picker quando disponível, badges de filtros ativos, Limpar e Atualizar. URL preserva cliente, filtros, período e seção. |
| Dados | Metric cards, tabelas, badges e alertas com tokens Reports; fonte, período, unidade, fuso e atualização onde pertinentes. |
| Formulários | Input/Select/Textarea/Checkbox/Upload oficiais; label, ajuda, validação perto do campo, pending e retorno. Formulário longo em página ou drawer amplo. |
| Navegação local | Tabs para seções reais; menus de linha para ações secundárias; diálogo apenas para confirmação ou poucos campos. |
| Fluxos | Paleta e inspector usam primitivas comuns; canvas, nós e conectores permanecem especializados. Análise usa os mesmos nós com métricas sem colocar números no editor. |
| Feedback | Alert, toast/status, skeleton, empty/error e progresso real. Cor sempre acompanhada de texto/ícone acessível. |

Tokens: mapear `--r-*` para os tokens semânticos CADU e `--colors-*` do kit, sob `[data-cadu-skin="reports"]`. Preservar a leitura visual azul de Reports e separar success/warning/danger da escala de marca. Definir tipografia, raio, borda, sombra e motion uma vez. Reavaliar `tokens.css:130` antes de alterar, porque a declaração laranja pode ter consumidores fora do bundle.

## Mapa das telas

| Área | Falha principal de composição | Primeira migração |
| --- | --- | --- |
| Visão geral | Cartões e filtros sem contrato uniforme de fonte/frescor | Page layout, metric cards, alertas e barras de comparação |
| Contas | Cadastro ao lado da lista e edição inline com controles diferentes | Data table, drawer de criação, edição por linha com salvar/cancelar |
| Campanhas | Lista, detalhe e configurações misturam navegação local e formulários | Header de detalhe, Tabs, tabela, contexto de conta e associação |
| Relatórios | Biblioteca, criação, briefing e evidência possuem densidades distintas | Cards/lista, drawer de criação, página de detalhe e revisão ampla |
| Importações | Upload, mapeamento, revisão, divergências e histórico comprimidos em uma área | Etapas claras, uploader, tabela de amostra, revisão lado a lado e resumo |
| Dados de mídia | Instalação e saúde de fontes disputam espaço com lista | Página em etapas, status por fonte, diagnóstico e conexão |
| Super Tag | Instalação, privacidade e verificação precisam de contexto | Página por site, seções de configuração, snippet e estado de coleta |
| Fluxos | Lista, editor e análise têm superfícies e ações diferentes | Shell compartilhado; lista de fluxos, editor e monitor como views separadas |
| Eventos | Busca, filtros e tabela de eventos ad hoc | Filter bar local, data table, detalhe de evento e código copiável |
| Link Tester | Entrada, cadeia de redirecionamentos e associação no mesmo cartão | Formulário + diagnóstico em áreas separadas; associação inline confirmada |
| Acessos | Formulário e lista pouco distinguem papel, escopo e consequência | Tabela de pessoas, drawer curto de concessão, diálogo de revogação |

## Viewports e interação

- Desktop 1440–1920: largura fluida, sidebar persistente, conteúdo com grid de 12 colunas e tabelas com densidade legível; painel lateral só quando apoiar a tarefa.
- Desktop compacto 1180–1439: ações secundárias em menu, filtros podem ocupar duas linhas; conteúdo principal preserva hierarquia.
- Tablet 768–1179: sidebar recolhível, tabela com rolagem horizontal e cabeçalho fixo quando necessário, drawers em largura adequada. Controles com alvo de toque e fonte de 16 px em campos editáveis para evitar zoom do teclado virtual; foco e scroll permanecem estáveis quando o teclado aparece. Suportar mouse, toque, caneta e teclado físico.
- Celular <768: páginas de leitura e tarefas simples devem continuar utilizáveis quando possível. O editor/monitoramento visual de Fluxos mostra a mensagem já definida para abrir em tablet ou computador. Não estender esse bloqueio a todo o Reports sem decisão de produto.
- Movimento: animações breves de mudanças de valor; `prefers-reduced-motion` remove movimento contínuo. Estado de saúde depende de texto e dado, não apenas de linha verde/amarela.

## Execução proposta

1. **Baseline e contrato:** capturas e inventário por área em 1440, 1024 e 768 px; registrar rota, estado real, papel de acesso, filtros e ações. Fixar escala azul/tokens e matriz de componentes.
2. **Prova técnica:** criar build/CSS isolado de Reports que compile um Button, Input, Tabs e Dialog oficiais do Untitled UI React v8, com React Aria e Tailwind compatíveis. Conferir ausência de preflight fora da raiz Reports e ausência de efeitos no Workspace/Conversations.
3. **Fundação:** wrappers CADU finos para botão, campo, select, badge, diálogo, abas, tabela e estados. Implementar `ReportsPageLayout`, `ReportsSectionHeader`, `ReportsMetric` e `ReportsStatus` com tokens Reports.
4. **Piloto:** converter **Contas** (tabela + criação + edição) e **PageChrome**. Exercita shell, filtro, tabela, formulário, estado e cliente sem depender do canvas. Comparar ao baseline em desktop/tablet.
5. **Operação diária:** Campanhas, Visão geral, Relatórios, Dados de mídia e Acessos. Corrigir filtros e estados por capacidade em conjunto, porque uma aparência nova não deve mascarar controles sem efeito.
6. **Jornadas complexas:** Importações, Super Tag, Eventos e Link Tester. Separar páginas longas de confirmação curta e manter evidência visível.
7. **Fluxos:** lista e cabeçalhos; paleta/inspector com primitivas comuns; por último editor e análise. Verificar canvas com mouse/toque/teclado e números só no monitoramento.
8. **Consolidação:** remover seletores substituídos, documentar APIs dos wrappers e revisar páginas em todos os viewports. Preservar deep links, `client_id`, permissões, chamadas e draft publicado durante a migração visual.

## Critérios de aceite

- Ao menos um componente real do Untitled UI React aparece no build de Reports, com proveniência e dependências registradas; o plano não chama uma imitação CSS de integração.
- Todas as áreas usam o mesmo contrato de cabeçalho, ação primária, filtro quando aplicável, estados e cliente ativo.
- Tokens Reports têm uma fonte para marca, foco, sucesso, aviso, erro, tipografia e superfícies; CSS local cobre apenas composição específica.
- Abas, diálogos, drawers, menus e formulários funcionam com teclado e leitor de tela, inclusive fechar/retornar foco e erros associados.
- Editor visual não mostra contadores; análise mostra métricas e saúde com legenda textual. Dados simulados são identificados como tal.
- Troca de cliente limpa estados incompatíveis e toda ação continua limitada por `organization_id/client_id` no backend. Associações a campanhas/projetos/marcas mantêm validação própria.
- 1440, 1024 e 768 px não apresentam corte de ação, sobreposição ou scroll horizontal na página inteira; tabelas/canvas podem rolar dentro de suas próprias áreas.
- Builds e validação visual por tela convertida; comparar estados vazio, carregando, erro, parcial, salvo, somente leitura e dados densos antes de remover CSS antigo.

## Dependências já conhecidas

O plano [Workspace Untitled UI](cadu-workspace-untitledui-normalization.md) registra a estratégia de versão e a ponte de tokens, ainda sem componentes reais instalados. A [auditoria de formulários](../design/auditoria-formularios-workspace-planner-reports-2026-09-29.md) detalha a apresentação adequada de cada tarefa do Reports. O [plano de fluxos](reports-flow-platform-implementation.md) define persistência, monitoramento e comportamento; esta migração visual não substitui seus itens funcionais pendentes.

Referências oficiais consultadas: [instalação](https://www.untitledui.com/react/docs/installation), [Vite](https://www.untitledui.com/react/integrations/vite), [theming](https://www.untitledui.com/react/docs/theming).

## Progresso da execução — 29/09/2026

- Prova técnica concluída: componentes oficiais Button e Input v8 gerados pela CLI 0.1.68, dependências React Aria/ícones e pipeline Tailwind 4 isolado em `frontend/reports-v1/untitled-kit`. O build de Reports gera `untitled.css` e `app.js/app.css` sem alterar o pipeline Tailwind 3 do restante do projeto.
- Token de marca Reports consolidado em azul `#175cd3` no design system, sidebar, CSS inicial e gráfico. O CSS legado ainda possui valores pontuais antigos a eliminar durante cada migração.
- Piloto de Contas em andamento: ação oficial de criação, busca com Input, drawer acessível com React Aria, edição por linha somente quando solicitada e botões oficiais. PageChrome usa Button oficial nas ações compartilhadas. Controles Select e tabela ainda são legados.
- O piloto inicial não concluía os critérios de aceite; a continuação abaixo levou os controles e diálogos às demais áreas fora de Fluxos. A revisão visual com dados reais em desktop/tablet e a limpeza gradual do CSS legado seguem como validação de publicação.

## Continuação da migração — áreas fora de Fluxos

- Os controles de ação, texto, seleção e texto longo das demais áreas passaram a usar Button, InputBase, NativeSelect e TextAreaBase gerados pela CLI oficial. Checkboxes, arquivos, datas e cores continuam com controles nativos por serem especializados.
- Campanhas, biblioteca de Relatórios, Acessos e instalação da Super Tag usam painéis de criação em React Aria Dialog/Modal. Revogações de chave de ingestão, acesso e Super Tag usam confirmação contextual acessível.
- As abas de Campanhas, Eventos e Importações usam uma navegação controlada com setas, Home e End. As seções seguem preservando `client_id`, permissões, chamadas e estados existentes.
- O código de Fluxos, seu canvas e o CSS próprio estão sob outra frente de trabalho e ficaram fora desta continuação. O cabeçalho/filtro compartilhado já usava Button oficial antes desta etapa.
- O build de Reports passou após a migração. A comparação visual com dados reais em desktop e tablet ainda é necessária antes de declarar a migração pronta para publicação.
