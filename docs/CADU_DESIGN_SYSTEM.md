# Cadu Design System — direção do Workspace

## Papel

O design system consolida o que já existe no Workspace React. Ele não substitui o produto por um kit externo e não cria uma segunda linguagem visual.

A ordem de decisão é:

1. reutilizar um componente existente;
2. generalizar o componente existente;
3. adaptar uma primitive externa quando houver uma lacuna real;
4. criar um componente novo.

## Direção visual

O Workspace é um ambiente editorial de trabalho orientado por conversa.

- navegação escura e compacta;
- canvas claro e contínuo;
- acento verde/teal;
- tipografia forte na identidade do contexto;
- superfícies silenciosas;
- divisores usados para organizar informação;
- poucos cards e nenhuma decoração sem função;
- Chat, contexto e resultado como hierarquia principal.

A Home e os catálogos ocupam toda a largura disponível. Limites de largura são usados apenas para preservar a leitura de títulos, descrições e conteúdo textual longo.

## Estrutura

```text
Navbar — largura total
┌──────────────────────────────────────────────┐
│ produto · agência/contexto · busca · conta   │
└──────────────────────────────────────────────┘
┌──────┬───────────────────────────────────────┐
│ Dock │ Canvas                                │
│ 64px │ Home / projeto / marca / catálogo     │
└──────┴───────────────────────────────────────┘
```

No mobile, a Dock desaparece e o canvas assume a largura integral. As ações essenciais continuam disponíveis pela navbar e pelos controles contextuais.

## Tokens

Os tokens vivem em `frontend/cadu-design-system/tokens.css`.

### Superfícies

- `--cadu-canvas`
- `--cadu-surface`
- `--cadu-surface-raised`
- `--cadu-surface-soft`
- `--cadu-bg`
- `--cadu-bg-subtle`

### Texto e bordas

- `--cadu-ink`
- `--cadu-muted`
- `--cadu-text`
- `--cadu-text-secondary`
- `--cadu-line`
- `--cadu-border`

### Produto e estado

- `--cadu-accent`
- `--cadu-accent-strong`
- `--cadu-accent-soft`
- `--cadu-success`
- `--cadu-warning`
- `--cadu-danger`
- `--cadu-info`
- `--cadu-focus`

### Estrutura

- `--cadu-radius-sm`
- `--cadu-radius-md`
- `--cadu-radius-lg`
- `--cadu-motion-fast`
- `--cadu-z-navbar`
- `--cadu-z-popover`
- `--cadu-z-dialog`
- `--cadu-z-toast`

## Skins

As skins alteram principalmente o accent. Tipografia, grid, spacing e padrões de interação permanecem compartilhados.

- Workspace: verde institucional;
- Conversations: teal luminoso sobre a superfície escura;
- Planner: azul;
- Studio: violeta;
- Reports: âmbar;
- Skills: violeta azulado.

Neste ciclo apenas Workspace e Conversations são superfícies de implementação. As outras skins funcionam como contrato futuro, não como autorização para migrar os demais produtos.

## Componentes estruturais existentes

- `ThemeProvider`
- `CaduDock`
- `CaduSolutionSwitcher`
- `ProjectSelector`
- `WorkspaceAccountControl`
- `WorkspaceAccountMenu`
- `WorkspaceComposer`
- `ResumeCardCollection`
- `VisualIdentity`
- `CaduDialog`

## Componentes AI-native existentes

- thread e mensagens;
- renderização de respostas estruturadas;
- anexos;
- confirmação de ações;
- tool calls e estados de execução;
- painel de artefato;
- estados de erro e retry.

Esses componentes têm prioridade sobre wrappers genéricos de UI.

## Acessibilidade

- foco visível em controles interativos;
- labels ou nomes acessíveis em botões icônicos;
- tooltip para itens da Dock;
- dialogs com fechamento por teclado;
- ordem de tabulação coerente;
- respeito a `prefers-reduced-motion`;
- nenhuma ação importante disponível apenas por hover.

## Regra de evolução

Toda alteração visual deve ser validada na Home, no catálogo de projetos, no catálogo de marcas, no detalhe do projeto e na conversa. Como essas superfícies compartilham o mesmo bundle e CSS, uma mudança aparentemente local pode alterar todas elas.
