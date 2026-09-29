# Plano de normalização visual · Cadu Workspace com Untitled UI React

## Resultado esperado

Usar o **Untitled UI React como kit de componentes e referência de implementação** para manter um layout previsível entre as superfícies do Workspace. A identidade CADU fica em tokens e skins semânticas, não em forks de componentes e correções CSS locais.

O primeiro escopo é o Workspace: Home, Marcas, Projetos, detalhe de Marca, detalhe de Projeto e Conta. Conversas é uma superfície irmã que compartilha infraestrutura e componentes neutros, mas mantém seu tema escuro. Studio, Planner, Reports e Skills entram nas fases seguintes, cada qual preservando o papel semântico da própria skin.

## Estado atual observado

- O cliente usa React 18.3, Vite 6 e CSS próprio. A dependência raiz `tailwindcss` é 3.4; não há `@untitledui/icons`, `react-aria-components` ou fonte de componentes Untitled UI instalada.
- `frontend/cadu-design-system` já é a base compartilhada: tokens em `tokens.css`, `ThemeProvider`, Dock, selectors, Dialog e componentes de Workspace.
- O mesmo entry point `frontend/conversations-v2/main.jsx` escolhe Home/Marca/Projeto/Conta ou Conversas pelo bootstrap. O bundle importa os estilos compartilhados e monta Conversas em tema escuro e as superfícies Workspace em tema claro.
- Existem temas semânticos CADU em `tokens.css` para Workspace, Conversas, Planner, Studio, Reports e Skills. Alguns estilos ainda estão em folhas extensas e específicas por tela.
- A navegação global é a `CaduDock`; áreas de contexto usam componentes adicionais como `WorkspaceContextSidebar`, `WorkspaceNavbar` e chrome legado/móvel.
- Há documentação anterior sobre o papel da Dock e do Workspace. Essa documentação será reconciliada com o padrão de componentes, sem descartar decisões de navegação/contexto que continuam válidas.

## Decisão de adoção

Tratar o Untitled UI React como **fonte real dos componentes**, não só como inspiração visual. Usar os componentes/documentação licenciados e dependências oficiais; registrar versão, proveniência do código copiado e diferenças CADU. Não iniciar um app novo na raiz com o CLI: o Workspace já tem rotas, templates, bootstrap, autenticação, tema e build.

O guia oficial para Vite orienta a instalação manual em projetos existentes e documenta `@untitledui/icons`, `react-aria-components`, `tailwindcss-react-aria-components`, `tailwind-merge`, `tailwindcss-animate`, Tailwind e `@tailwindcss/vite`. O exemplo de tema usa diretivas `@theme`. A configuração atual do CentralX é Tailwind 3.4, portanto o plano exige um spike de compatibilidade antes de definir a versão final e tocar nos builds existentes. Fontes: [instalação React](https://www.untitledui.com/react/docs/installation), [integração Vite](https://www.untitledui.com/react/integrations/vite), [theming](https://www.untitledui.com/react/docs/theming).

## Princípios para manter o padrão

1. **Untitled UI define a anatomia:** espaçamento, escala de texto, campos, botões, menus, diálogos, tabs, tabelas, badges e estados.
2. **CADU define semântica e marca:** tokens de identidade, skins por produto, logo, nomenclatura e conteúdo. Componentes não ganham estilos locais sem uma razão documentada.
3. **Uma API por primitiva:** telas usam `CaduButton`, `CaduInput`, `CaduDialog` etc. como wrappers finos dos componentes Untitled UI, com props públicas consistentes.
4. **Tokens primeiro:** mapear cores, tipografia, raio, sombras, foco e motion para variáveis. Evitar valores hex e medidas repetidos em folhas de páginas.
5. **Acessibilidade vem do componente:** preferir React Aria para diálogo, menu, combobox, tabs, checkbox e tooltip; manter teclado, foco e leitores de tela.
6. **Uma mudança visual, uma fonte:** não acrescentar um override em CSS de tela quando a correção pertence ao token ou componente compartilhado.
7. **Tema escuro fica isolado:** o skin Conversations continua escuro e não pode receber reset, cores ou estilos globais acidentalmente introduzidos pela migração do Workspace.

## Plano de skins CADU

| Token do kit | Token semântico CADU | Responsabilidade |
| --- | --- | --- |
| `brand` / escala de marca | `--cadu-accent-*` | Ação primária e foco, alterada pela skin do produto |
| `foreground` | `--cadu-ink` | Texto principal |
| `muted-foreground` | `--cadu-muted` | Texto secundário e metadados |
| `background` | `--cadu-canvas` | Fundo da superfície |
| `card` / `popover` | `--cadu-surface*` | Superfícies e menus elevados |
| `border` / `input` | `--cadu-line` | Divisórias e campos |
| `success`, `warning`, `danger`, `info` | tokens semânticos de estado atuais | Resultado e estado, nunca decoração |
| `radius`, `shadow`, `font` | escalas CADU compartilhadas | Forma e tipografia consistentes |

Mapear Workspace para sua cor de ação existente. Não selecionar o roxo padrão sem revisão: o guia oficial informa que a opção `brand` mantém o roxo do kit. As demais skins só alteram tokens semânticos da solução; layout e componente permanecem os mesmos.

## Arquitetura de componentes-alvo

```text
frontend/cadu-design-system/
├── tokens.css                 # aliases semânticos CADU → tokens do kit
├── ThemeProvider.jsx          # define skin por superfície e aplica data attrs
├── primitives/                # wrappers CADU sobre componentes Untitled UI
│   ├── Button.jsx
│   ├── Input.jsx
│   ├── Select.jsx
│   ├── Dialog.jsx
│   ├── DropdownMenu.jsx
│   ├── Tabs.jsx
│   ├── Badge.jsx
│   ├── Tooltip.jsx
│   └── DataTable.jsx
├── patterns/                  # composições estáveis do Workspace
│   ├── WorkspaceShell.jsx
│   ├── WorkspaceDock.jsx
│   ├── ContextHeader.jsx
│   ├── PageHeader.jsx
│   ├── EmptyState.jsx
│   └── FeedbackRegion.jsx
└── components/                # domínios: Home, Brand, Project, Account…
```

Os nomes são propostos; antes de criá-los, mapear e reaproveitar `CaduDialog`, `CaduDock`, `WorkspaceNavbar`, `WorkspaceContextSidebar`, `WorkspaceMobileChrome`, `WorkspaceHome` e demais peças existentes. Migrar um componente por vez e remover o componente duplicado somente quando os consumidores estiverem convertidos.

## Matriz de normalização do Workspace

| Área | Padrões a normalizar | Ordem sugerida |
| --- | --- | --- |
| Shell global | Dock, troca de solução, marca ativa, conteúdo, menu de conta, notificações | 1 |
| Cabeçalhos e contexto | breadcrumb, título, descrição, ações e abas de Marca/Projeto | 2 |
| Controles básicos | botões, busca, campo, select, checkbox, menu e diálogo | 3 |
| Home e continuidade | composer, projetos recentes, cards, estado vazio, shortcuts manager | 4 |
| Marcas e Projetos | filtros, busca, listas, cards, menus de ações e criar/editar | 5 |
| Detalhe de Marca | cabeçalho, abas, editor, auditoria e módulos | 6 |
| Detalhe de Projeto | contexto, abas, recursos, produção, atividade e modais | 7 |
| Conta | cabeçalho, tabs, perfil, equipe, uso, integrações e plano | 8 |
| Mobile | dock/drawer, navegação de contexto, formulário e tabelas | em paralelo a cada área |

## Compatibilidade do build: primeira decisão técnica

### Spike de compatibilidade (feito; primeiro componente integrado)

1. Conferidos os entry points existentes: Workspace e Conversas compartilham React 18.3, Vite 6 e a mesma folha CSS.
2. Conferida a saída oficial do CLI Untitled UI React v8 em app Vite descartável. O `Button` oficial usa React Aria Components e classes/tokens de Tailwind 4.
3. Confirmado que a folha global oficial não pode entrar no entry compartilhado sem risco de propagar preflight e seletores base para Conversas escuro.
4. Adicionada a primeira ponte de tokens semânticos em `frontend/cadu-design-system/tokens.css`, escopada à skin Workspace e sem folha/utilitário novo ativo.
5. Registradas a proveniência e as regras do CLI em `frontend/cadu-design-system/UNTITLED-UI.md`.
6. A fronteira Tailwind 4 exclusiva do Workspace está em `frontend/cadu-design-system/untitled-kit`; o CSS compilado não inclui preflight e só é carregado nos templates React do Workspace.
7. O Button oficial v8 foi integrado por `CaduButton` nas vitrines de Marcas/Projetos e nas ações de criação. O próximo componente é Input/Dialog, seguido pelas demais ações e formulários.

Não executar `npx untitledui init` sobre a raiz do CentralX: o comando foi documentado para gerar scaffold, e o projeto tem build, templates e configurações próprios. O Vite atual também não tem React Router configurado; não instalar navegação nova sem que a arquitetura de URL peça isso.

### Opções que o spike precisa comparar

- **Migração Tailwind 4 compartilhada:** menor duplicação de runtime no longo prazo, mas exige auditoria de todos os pipelines Tailwind do monorepo e regressão visual das superfícies.
- **Fronteira de estilos por Workspace:** reduz o impacto inicial, mas deve provar que os componentes reais do kit, fontes, CSS e utilitários compilam sem contaminar o bundle compartilhado de Conversas.
- **Não recomendado:** manter Tailwind 3, copiar apenas o visual e anunciar o kit como adotado. Isso repete o problema que originou o plano.

## Fases de execução

### Fase 0 — Inventário e decisões

- Conferir licença, pacote/CLI, versões suportadas e fonte oficial do React kit.
- Inventariar páginas, templates, entry points, CSS compartilhado, componentes e estados visuais do Workspace.
- Tirar capturas de baseline desktop/mobile e registrar fluxos principais sem mudar comportamento.
- Aprovar qual superfície-piloto representa melhor o Workspace e confirmar estratégia Tailwind no spike.

**Saída:** mapa de consumidores, tabela de tokens, matriz de compatibilidade e decisão técnica registrada.

### Fase 1 — Fundação e piloto real

- Configurar dependências e build conforme a opção aprovada.
- Mapear tokens oficiais para tokens CADU e manter o accent atual do Workspace.
- Implementar Button, Input, Dialog e Tooltip reais, com wrappers leves e API CADU.
- Migrar uma superfície curta de Workspace que exerça tema, estados, modal, foco e responsividade; sugestão: lista de Marcas ou Gerenciador de atalhos.
- Confirmar que Conversas continua escura e inalterada.

**Saída:** primeira tela realmente montada com o kit, sem regressões e com padrão reutilizável.

### Fase 2 — Chrome e navegação

- Normalizar Dock, troca de solução, cabeçalho, breadcrumb, tabs de contexto, menus de conta e navegação mobile.
- Reconciliar docs de Dock e sidebar contextual; distinguir navegação global de navegação de contexto.
- Preservar URLs, deep links, estado selecionado, permissões e semântica de voltar/avançar.

### Fase 3 — Primitivas e padrões comuns

- Migrar controles, menus, tabelas, badges, toast/feedback, empty/loading/error states.
- Padronizar estado disabled, pending, success, warning, destructive e focus-visible.
- Eliminar overrides duplicados onde os componentes normalizados já atendem.

### Fase 4 — Migração de páginas do Workspace

- Migrar Home → Marcas/Projetos → detalhes → Conta, seguindo a matriz.
- Manter comportamento e payloads; separar refactor visual de mudanças de produto.
- Migrar mobile junto com cada página para evitar uma segunda rodada divergente.

### Fase 5 — Governança e expansão

- Documentar como criar páginas com wrappers e tokens; novas telas deixam de usar controles ad hoc.
- Criar revisão visual de componentes para prevenir regressões em cada skin e viewport.
- Após estabilizar Workspace, migrar Planner, Studio, Reports e Skills uma skin por vez usando a mesma camada.

## Contratos dos wrappers CADU

| Wrapper | Contrato mínimo |
| --- | --- |
| `CaduButton` | `variant`, `size`, `loading`, `disabled`, `iconLeading`, `iconTrailing`, `type`, `onPress`; loading anuncia estado e preserva largura |
| `CaduModal` | `label`, `onClose`, `initialFocusRef`, `closeOnBackdrop`; usa o Modal de React Aria do kit, prende e restaura foco |
| `CaduInput` | `label`, `hint`, `error`, `leading`, `trailing`, `required`, `disabled`; associações ARIA completas |
| `CaduDialog` | `open`, `onOpenChange`, `title`, `description`, `size`, `closeOnEscape`; foco preso/restaurado e nome acessível |
| `CaduTabs` | seleção controlada, URL opcional, navegação por teclado e painel associado |
| `CaduBadge` | variante semântica, conteúdo textual sempre presente, sem comunicar estado só pela cor |
| `CaduTooltip` | acionamento acessível por foco/hover, atraso consistente e sem duplicar nome acessível |
| `CaduDataTable` | colunas tipadas, sort e empty/loading/error state previsíveis; responsividade definida por padrão |

Os wrappers não escondem APIs essenciais de acessibilidade ou interação do kit. Variações novas entram no wrapper quando podem ser reutilizadas; particularidade de domínio fica na composição, não na primitiva.

## Critérios de aceite

- Um componente de tela comum usa wrappers CADU com implementação baseada no código real Untitled UI, não classes copiadas manualmente sem proveniência.
- O tema de Workspace vem de uma única escala de tokens; skins do produto só sobrescrevem tokens semânticos necessários.
- O shell, cabeçalhos, botões, campos, menus, tabs, diálogos e estados vazios têm mesma geometria e interação nas páginas convertidas.
- Conversas mantém o tema escuro; CSS novo não altera sua tipografia, superfícies, cor ou altura.
- Home, Marca, Projeto, Conta, troca de solução, permissões, rotas e estado de contexto continuam funcionando.
- Desktop, tablet e mobile mantêm foco visível, teclado, leitor de tela, reduced motion e feedback de erro/sucesso.
- A diferença visual em cada fase pode ser comparada ao baseline; divergências intencionais ficam documentadas.
- Builds oficiais do Workspace e de superfícies acopladas passam antes de remover o CSS antigo.

## Fora do escopo inicial

- Redesenhar todos os produtos ao mesmo tempo.
- Alterar navegação, conteúdo, permissões ou fluxos de dados durante a migração de estilo.
- Substituir tokens CADU por nomes `brand` diretos em toda a aplicação.
- Trocar Vite/React Router ou executar o scaffold de um app novo sem necessidade comprovada.
- Uniformizar Conversas com tema claro.

## Fontes internas

- `frontend/cadu-design-system/tokens.css`
- `frontend/cadu-design-system/ThemeProvider.jsx`
- `frontend/cadu-design-system/components/`
- `frontend/conversations-v2/main.jsx`
- `vite.conversations.config.mjs`
- `package.json` e `tailwind.config.js`
- `docs/cadu-workspace-dock-ux-plan.md`
- `docs/cadu-marketing-workspace-experience.md`
