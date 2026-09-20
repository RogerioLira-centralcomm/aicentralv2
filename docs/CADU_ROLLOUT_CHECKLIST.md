# Cadu Workspace — checklist de rollout e rollback

## Escopo versionado

- shell React compartilhado entre Home, projeto, projetos e marcas;
- Dock dentro da área de trabalho, abaixo da navbar;
- conteúdo principal em largura total;
- catálogo único de navegação entre produtos;
- modelos isolados de anexos, uploads, contexto e histórico;
- bundle Vite gerado em `aicentralv2/static/cadu_workspace/conversations/react/`.

## Contratos preservados

- autenticação e sessão continuam no backend Flask;
- endpoints de contexto, histórico, mensagens, uploads, runs e artefatos não mudam;
- streaming continua usando o protocolo atual;
- fontes de projeto continuam preparadas por `projects.prepare_source_upload`;
- rotas e templates legados permanecem disponíveis para rollback.

## Antes de publicar

- executar `npm run build:conversations`;
- executar os testes Node de conversas;
- executar os testes Python de projeto;
- executar `npm run test:workspace-layout`;
- confirmar `git diff --check`;
- revisar o diff e excluir arquivos fora do escopo;
- validar Home, projeto, projetos e marcas em sessão autenticada;
- conferir desktop e mobile, menus, diálogos, upload e abertura de artefato.

## Critérios de bloqueio

- overflow horizontal em qualquer superfície;
- Dock fora da área de trabalho ou visível no mobile;
- perda de contexto de projeto ou marca;
- falha em upload comum ou fonte de projeto;
- stream sem evento terminal;
- artefato salvo sem controle de versão;
- rota legada indisponível.

## Rollback

1. restaurar o bundle React anterior;
2. manter backend e banco sem migração destrutiva;
3. direcionar o detalhe de projeto para a rota legada já preservada;
4. confirmar contexto, upload e conversas na superfície anterior;
5. registrar a falha antes de retomar o rollout.

## Pendência externa

A inspeção visual autenticada exige uma sessão válida e acesso ao banco configurado. Ela não deve ser executada contra dados compartilhados sem autorização explícita para esse ambiente.
