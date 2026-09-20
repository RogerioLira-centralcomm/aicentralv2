# Cadu Workspace — auditoria do frontend

Atualizado em 20 de setembro de 2026.

## Escopo e direção

O Workspace já possui uma evolução React válida. A migração deve consolidar essa base, não criar outro frontend em paralelo. A Home, a Dock, a navbar e o dossiê React de projeto são superfícies em evolução que precisam ser preservadas.

Decisões confirmadas:

- backend Python/Flask permanece;
- Conversas 2.0 é a origem da experiência de Chat;
- Dock e navbar existentes permanecem;
- o canvas usa toda a largura disponível;
- limites de largura são reservados a blocos de leitura;
- rotas e superfícies legadas continuam como rollback durante a migração;
- Planner, Studio, Reports e Skills não fazem parte deste ciclo.

## Arquitetura atual

### Backend e renderização

- `aicentralv2/cadu_workspace/routes.py`: rotas, montagem de dados e ações do Workspace.
- `aicentralv2/templates/cadu_workspace/`: templates Flask atuais e superfícies de compatibilidade.
- `aicentralv2/templates/cadu_workspace/workspace_home_chat.html`: bootstrap da Home React.
- `aicentralv2/templates/cadu_workspace/project_detail_react.html`: bootstrap do detalhe React de projeto.
- `aicentralv2/templates/cadu_workspace/conversations_v2_lab.html`: entrada da experiência React de Conversas 2.0.

### Frontend React

- `frontend/conversations-v2/`: Chat, streaming, anexos, tool calls e artefatos.
- `frontend/cadu-design-system/`: tokens, temas e componentes compartilhados do Workspace.
- `frontend/cadu-studio-editor/`: superfície React independente do Studio, fora deste escopo.
- `vite.conversations.config.mjs`: gera um bundle único usado pela Home, projetos, marcas e Conversas 2.0.

O entrypoint `frontend/conversations-v2/main.jsx` escolhe a superfície pelo bootstrap:

- `homeMode` → `WorkspaceHome`;
- `projectMode` → `WorkspaceProject`;
- `brandsMode` → `WorkspaceBrands`;
- `projectsMode` → `WorkspaceProjects`;
- sem modo de catálogo → `App`, a experiência de conversa.

### Frontend legado

Ainda existem templates, CSS e JavaScript Vanilla em:

- `aicentralv2/static/css/cadu-workspace*.css`;
- `aicentralv2/static/js/cadu-workspace*.js`;
- `aicentralv2/static/cadu_workspace/conversations/`;
- templates legados de projetos, marcas, documentos e configurações.

Essa camada não pode ser removida até que cada rota e ação possua cobertura equivalente no React.

## Build e dependências

- React 18 e React DOM 18.
- Vite 6.
- Tailwind 3 para outras superfícies e bundles legados.
- DaisyUI ainda consta nas dependências de desenvolvimento.
- Untitled UI e React Aria não estão instalados.
- Build do Workspace React: `npm run build:conversations`.

O design system atual usa CSS próprio. A adoção de primitives externos deve ser seletiva e motivada por acessibilidade ou comportamento que ainda não exista.

## Rotas principais

| Rota | Superfície | Tecnologia | Compatibilidade |
| --- | --- | --- | --- |
| `/app` | Home do Workspace | React + bootstrap Flask | principal |
| `/workspace/app/visao-geral` | Home anterior | Flask/Vanilla | rollback |
| `/conversas` | Conversas | legado integrado ao runtime v2 | preservada |
| Conversas 2.0 | Chat principal | React | evolução principal |
| `/projetos` | catálogo de projetos | React por padrão | `?legacy=1` preservado |
| `/projetos/<id>` | dossiê do projeto | React por padrão | `?legacy=1` preservado |
| `/marcas` | catálogo de marcas | React por padrão | legado preservado |
| `/docs` | documentos | Flask/Vanilla | mapear antes de renomear |

As rotas antigas sob `/workspace/app/...` redirecionam para as entradas limpas quando aplicável.

## Contratos usados pelo frontend

### Home

- projetos e marcas preparados pelo `dashboard`;
- cards de continuidade montados por `_workspace_continuity_feed`;
- atalhos da Dock em `/workspace/api/dock/shortcuts`;
- saldo e consumo fornecidos pelo backend do Workspace.

### Conversas 2.0

- mensagens;
- contexto compartilhado;
- histórico;
- uploads;
- runs e cancelamento;
- artefatos;
- streaming de eventos;
- MCP para fontes de projeto.

### Projeto

- atualização de contexto;
- criação de nota;
- upload e indexação de fonte;
- importação de URL;
- atalhos externos;
- alteração de status;
- ações para Planner e Studio.

## Componentes reutilizáveis

- `ThemeProvider`;
- `CaduDock`;
- `CaduSolutionSwitcher`;
- `ProjectSelector`;
- `WorkspaceAccountControl` e `WorkspaceAccountMenu`;
- `WorkspaceComposer`;
- `ResumeCardCollection`;
- `VisualIdentity`;
- `CaduDialog`;
- `ArtifactPane`;
- componentes de conversa, respostas e confirmação.

## Problemas identificados

### Shell compartilhado

Uma regra posterior alterou `.cadu-ds-home-shell` para `display:block`. A Home acomoda a Dock dentro de `.cadu-ds-home-workarea`, mas o detalhe de projeto mantinha a Dock como filha direta do shell. O resultado era uma faixa escura horizontal com os atalhos centralizados. A correção é fazer o projeto usar a mesma composição estrutural da Home.

### Largura

Home, composer e projeto ainda possuíam limites de 1040–1180px. Isso contrariava a decisão de usar toda a largura disponível. O canvas deve ser fluido, mantendo `max-width` apenas em textos que precisam de legibilidade.

### CSS acumulado

`frontend/cadu-design-system/styles.css` contém regras sucessivas para os mesmos seletores. A consolidação deve ser incremental, acompanhada por testes visuais, porque a ordem da cascata hoje faz parte do comportamento.

### Chat concentrado

`frontend/conversations-v2/App.jsx` concentra histórico, contexto, anexos, streaming, runs e artefatos. A extração deverá preservar os contratos existentes e ocorrer depois da estabilização visual.

### Estado híbrido

React e templates legados coexistem. Essa coexistência é intencional no momento, mas exige uma matriz de destino antes de qualquer remoção.

## Baseline de verificação

- `npm run build:conversations`: aprovado; há apenas avisos de bases de browsers desatualizadas.
- testes Node de conversa e integração do Workspace: 20 aprovados antes das mudanças.
- testes Python inicialmente não coletaram porque o comando foi executado sem o repositório no `PYTHONPATH`; repetir com `PYTHONPATH=.`.

## Riscos

- colisões de cascata ao editar o CSS compartilhado;
- regressão em rotas legadas ainda usadas por favoritos e ações administrativas;
- perda de contexto de projeto ao alterar navegação;
- duplicação de componentes ao introduzir primitives externas cedo demais;
- alteração acidental de streaming, uploads ou MCP durante refatoração visual.

## Regra de preservação

Antes de remover ou substituir qualquer implementação, confirmar sua rota, API, estados, permissões, edge cases e testes dependentes. Nenhuma funcionalidade deve desaparecer silenciosamente.
