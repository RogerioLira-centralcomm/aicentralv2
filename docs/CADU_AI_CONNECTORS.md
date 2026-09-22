# Conectores globais de IA e créditos

## Fronteiras oficiais

- `services.openrouter_service.chat_completion`: normaliza mensagens e executa OpenAI/OpenRouter com failover.
- `services.cadu_ai_connector.CaduAIConnector`: autoriza, gera e debita em uma única operação de aplicação.
- `cadu_credit_connector.CaduCreditConnector`: única fronteira comercial de saldo e débito.
- `cadu_tool_billing.ToolTokenLedger`: implementação interna do ledger; não deve ser importada por produtos novos.

## Roteamento

`CADU_AI_PROVIDER_ORDER` define a prioridade global. O padrão é `openai,openrouter`.
OpenAI só entra na cadeia quando existe credencial e o modelo é compatível. Uma chamada que fixa
`provider="openai"` ou `provider="openrouter"` não recebe fallback implícito.

Cada resposta inclui:

- `provider`: provedor que concluiu a chamada;
- `provider_attempts`: provedores tentados, em ordem;
- `model` e `usage`: contrato normalizado usado na cobrança.

## Cobrança por cliente

Toda chamada comercial nova deve usar `CaduAIConnector.complete` com:

- `client_id` e `user_id` válidos;
- `idempotency_key` estável por execução;
- `app` e `stage` para atribuição;
- estimativa prévia de tokens;
- metadados do projeto, conversa ou artefato.

O conector autoriza antes da chamada e registra o consumo medido depois dela. O ledger persiste
`id_cliente`, usuário, modelo, tokens, custo, provedor e cadeia de fallback. Repetir a mesma chave
idempotente não pode gerar um segundo débito.

## Migração dos fluxos existentes

Fluxos que já fazem reserva ou cobrança transacional permanecem usando `CaduCreditConnector` para
evitar débito duplo. Eles já recebem o failover global através de `chat_completion` e passam a ter
os metadados de provedor incorporados automaticamente na cobrança.

Não é permitido escrever diretamente em `cadu_tools_token_usage` ou `cadu_credits_extras` fora das
duas fronteiras de crédito. Um teste de arquitetura protege essa regra.

### Exceções intencionais

- O agente do Video Studio usa `CaduAIConnector` diretamente.
- Conversas, pesquisa e tarefas longas autorizam e debitam no serviço envolvente,
  porque uma execução pode agrupar várias chamadas em uma única operação.
- Skills mantêm `reserve_run`/`finish_run`; a reserva é sua fronteira financeira e
  não pode ser combinada com débito por chamada.
- Smart Planner mantém seu ledger por sessão até o contrato HTTP propagar
  `client_id`, `user_id` e idempotência para cada geração.
- Places, CRM e Training não devem inventar um cliente pagador. A migração depende
  de suas rotas de entrada fornecerem o ator real.
