# Cadu Workspace — plano de execução em seis fases

Este plano consolida o Workspace existente. As capturas aprovadas são referências de continuidade visual; não autorizam uma reconstrução do produto.

## Fase 1 — auditoria e baseline

- mapear frontend React, legado, templates, rotas e APIs;
- registrar componentes reutilizáveis e conflitos conhecidos;
- executar build e testes de referência;
- preservar o worktree existente;
- produzir `CADU_FRONTEND_AUDIT.md` e este plano.

Saída: mapa verificável do sistema sem alteração de comportamento.

## Fase 2 — shell, Dock, navbar e largura

- manter a Dock atual e sua persistência;
- manter a navbar horizontal;
- usar a mesma composição estrutural na Home e no detalhe de projeto;
- corrigir a Dock expandida horizontalmente no projeto;
- aplicar largura total ao canvas, composer e conteúdo de projeto;
- manter limites apenas em blocos de leitura;
- validar desktop, tablet e mobile.

Saída: Home e projeto estáveis, coerentes e sem overflow horizontal.

## Fase 3 — design system incremental

- consolidar tokens semânticos e temas;
- reduzir regras CSS conflitantes em blocos pequenos;
- generalizar componentes existentes antes de criar outros;
- melhorar teclado, foco, dialogs, tooltips e drag and drop;
- avaliar Untitled UI/React Aria somente para lacunas reais.

Saída: linguagem visual compartilhada sem aparência de template.

## Fase 4 — Cadu Chat e Home orientada por conversa

- preservar Conversas 2.0 como base;
- extrair gradualmente histórico, stream, anexos, contexto e artefatos de `App.jsx`;
- manter streaming, stop, retry, uploads, tool calls e aprovações;
- organizar a Home em Chat, continuar, atividade e recentes;
- usar apenas dados e endpoints reais.

Saída: Chat como ação principal do Workspace, sem perda funcional.

## Fase 5 — projetos, marcas e conhecimento

- preservar e evoluir o dossiê React de projeto;
- reconstruir contexto a partir da URL;
- unificar shell de projetos e marcas;
- organizar arquivos, fontes, links, memória e entregas;
- introduzir viewers somente para formatos suportados;
- criar adapters frontend para APIs legadas quando necessário.

Saída: projeto e marca funcionam como contextos persistentes do Chat.

## Fase 6 — artefatos, atividade e rollout

- consolidar `ArtifactPane` como painel contextual;
- montar atividade por adapter sobre fontes existentes;
- ampliar testes de fluxo, acessibilidade e responsividade;
- preservar aliases, fallback e rollback;
- remover legado apenas após confirmação de equivalência;
- documentar shell, design system, compatibilidade e dívida restante.

Saída: Workspace React verificável, reversível e pronto para expansão posterior.

## Relatório obrigatório por fase

Cada fase deve registrar:

- arquivos alterados, criados e removidos;
- testes e resultados;
- screenshots das superfícies principais;
- APIs e rotas preservadas;
- dívida restante;
- recomendação para a fase seguinte.

## Critério global de aceite

- backend Python preservado;
- APIs, autenticação, streaming, MCP e uploads preservados;
- Home e projeto em largura total;
- Dock e navbar coerentes entre superfícies;
- rotas antigas disponíveis durante a transição;
- build e testes aprovados;
- nenhuma perda funcional conhecida.

## Estado da execução — 20/09/2026

- Fase 1 concluída: auditoria, baseline e plano registrados.
- Fase 2 concluída no código: Dock preservada dentro da área de trabalho compartilhada, navbar mantida e Home, catálogos e projeto em largura total.
- Fase 3 concluída no escopo inicial: tokens semânticos, documentação e catálogo único de navegação entre produtos.
- Fase 4 avançada: validação, upload e montagem de anexos, payload de contexto, restauração do histórico e filtro de conversas recentes extraídos de `App.jsx`, sem mudança de contrato, streaming ou interface. A dependência de marca foi corrigida no callback de envio.
- Fase 5 em andamento: dossiê React, catálogos, fontes, memória e entregas compartilham o shell; a inspeção autenticada com dados reais permanece pendente.
- Fase 6 em andamento: teste Playwright responsivo e checklist de rollout/rollback adicionados; atividade e artefatos preservam as implementações existentes.

Validação atual: build Vite aprovado, testes Node de integração aprovados, teste Playwright de layout aprovado em 1440 px e 390 px, 28 testes Python de projeto aprovados e `git diff --check` sem erros. O teste de layout confirma largura total, Dock desktop/mobile e ausência de overflow nas superfícies Home, projeto e catálogo. A inspeção visual autenticada do conteúdo real continua pendente porque o ambiente local configurado tenta acessar um banco remoto.
