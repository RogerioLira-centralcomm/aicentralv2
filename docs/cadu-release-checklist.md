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

## 6. Aceite visual e operacional

- Revisar desktop, tablet e celular em Workspace, Planner, Studio, Connect e
  Skills.
- Conferir navegação, foco por teclado, estados vazios, loading e erros.
- Validar downloads e URLs assinadas antigas e novas com acesso permitido e
  negado entre organizações.
- Só remover templates e adaptadores antigos depois do aceite e de uma janela
  de observação sem uso das rotas de compatibilidade.
