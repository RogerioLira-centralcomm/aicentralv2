# Checklist de release da família Cadu

Este roteiro não substitui backup, revisão de infraestrutura ou janela de
mudança. Ele mantém escrita, chat e worker fechados até que cada dependência
tenha sido validada.

## 1. Antes do deploy

- Criar backup verificável do PostgreSQL.
- Confirmar `DB_HOST`, `DB_PORT`, `DB_NAME` e `DB_USER` do ambiente alvo.
- Manter `CADU_FAMILY_WRITES_ENABLED=0`, `CADU_FAMILY_CHAT_ENABLED=0` e
  `CADU_CHAT_WORKER_ENABLED=0`.
- Confirmar URLs canônicas de Auth, Workspace, Planner, Studio, Connect e
  Skills e o cookie compartilhado `.centralcomm.media`.
- Não definir `CADU_LEGACY_ASSET_BASE_URL` antes de validar a origem e o
  diretório dos anexos históricos.

## 2. Migrações, nesta ordem

1. `python migrations/run_add_cadu_chat_runtime.py`
2. `python migrations/run_add_cadu_tool_token_ledger.py`
3. `python migrations/run_add_connect_report_workspace.py`
4. `python migrations/run_add_connect_report_sources.py`
5. `python migrations/run_add_workspace_brand_audit_jobs.py`
6. `python migrations/run_add_workspace_brand_audit_history.py`
7. `python migrations/run_add_workspace_brand_audit_evidence.py`
8. `python migrations/run_add_workspace_brand_audit_versioning.py`
9. `python migrations/run_add_cadu_public_mcp_modules.py`

Os runners são atômicos, exigem banco explicitamente configurado e validam o
schema criado. Eles não habilitam flags e não inserem dados de demonstração.

## 3. Deploy com escrita fechada

- Publicar o código com as flags mutáveis em `0`.
- Testar login, logout e troca entre os cinco produtos.
- Abrir `/workspace/app`, projetos, marcas, equipe, plano, créditos,
  faturamento e integrações.
- Confirmar os redirecionamentos de `/familia/workspace/*`.
- Validar isolamento entre duas organizações e respostas 403/404.

## 4. Escrita do Workspace

- Habilitar somente `CADU_FAMILY_WRITES_ENABLED=1`.
- Criar e editar um projeto de teste controlado.
- Enviar, baixar, reprocessar e remover uma fonte nova.
- Criar e editar uma marca, enviar ativo e executar auditoria.
- Convidar, reenviar e cancelar um convite; revisar papéis e último admin.
- Validar registros existentes sem alterar links históricos.

## 5. Chat

- Configurar e validar `CADU_DIFY_API_KEY` e `CADU_DIFY_BASE_URL`.
- Habilitar `CADU_FAMILY_CHAT_ENABLED=1`, mantendo o worker em `0`, e testar
  uma conversa controlada no transporte síncrono.
- Configurar supervisor para `flask cadu_family chat-worker-once`.
- Habilitar `CADU_CHAT_WORKER_ENABLED=1` somente com o supervisor ativo.
- Testar concorrência, reload durante geração, cancelamento e retomada.
- Não redisparar automaticamente jobs já reclamados após falha; reconciliar
  provedor, cobrança e resultado antes de qualquer nova tentativa.

## 6. Auditoria profunda de marca

- Executar a migração da fila antes de ativar `CADU_BRAND_AUDIT_WORKER_ENABLED=1`.
- Configurar supervisor para `flask cadu_workspace brand-audit-worker-once`.
- Configurar supervisor para `flask cadu_workspace resource-registry-worker-once`; o comando processa um job por execução e usa claim concorrente com `SKIP LOCKED`.
- Confirmar que o deploy aplicou `migrations/add_cadu_project_link_icon_metadata.sql` e ativou `cadu-link-icon-worker@1.service` e `@2.service`; a fila limita a dois jobs ativos globalmente.
- Criar uma marca de teste e confirmar: estado em fila, claim durável, progresso,
  cobrança idempotente e e-mail apenas após os três pareceres ficarem prontos.
- Não redisparar jobs já reclamados: usar a ação de retentativa, que cria um novo
  job com o checkpoint de evidências salvo.

## 7. Aceite visual e operacional

- Revisar desktop, tablet e celular em Workspace, Planner, Studio, Connect e
  Skills.
- Conferir navegação, foco por teclado, estados vazios, loading e erros.
- Validar downloads e URLs assinadas antigas e novas com acesso permitido e
  negado entre organizações.
- Só remover templates e adaptadores antigos depois do aceite e de uma janela
  de observação sem uso das rotas de compatibilidade.

## 8. MCP público do Cadu

- Antes de executar a migration do MCP, confirmar backup verificável e banco
  alvo (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`). O runner exige host, nome
  e usuário explícitos, limita bloqueios/execução e valida as duas colunas.
- Publicar com módulos antigos preservados; novas autorizações começam pelo
  módulo Marketing e podem habilitar Projetos, Biblioteca, Mídia, Marcas,
  Google, Documentos, Conta e Relatórios.
- Validar em cliente elegível o ciclo completo: descoberta OAuth, registro,
  consentimento, autorização, `tools/list`, chamada real, refresh e revogação.
- Validar também conexão manual legada, seleção persistente de módulos,
  escopos de leitura/escrita/administração e a compra de créditos somente por
  administrador autorizado.
- Confirmar que o diagnóstico distingue endpoint disponível, OAuth disponível,
  conexão autorizada e ferramentas efetivamente testadas; validar erros sem
  exibir credenciais e que nenhuma ferramenta retorna como desconhecida.
- Medir ferramentas/schema carregados, chamadas por tarefa, latência, erros e
  créditos cobrados em tarefas de Marketing representativas antes de ampliar
  o catálogo padrão.
- Manter uma tarifa explícita para cada ferramenta pública: preço fixo, tarifa
  padrão atual de 1 crédito ou cobrança variável já feita pelo serviço de
  origem. Ferramenta nova sem política de cobrança definida deve falhar de
  forma visível até ser classificada; não herdar cobrança silenciosamente.
- A submissão pública do plugin é uma etapa separada: completar identidade,
  domínio, URLs legais/suporte, conta de revisão e aprovação no portal OpenAI.
  A preparação técnica e a migration não publicam nem submetem o plugin.
