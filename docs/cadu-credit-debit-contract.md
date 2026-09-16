# Contrato de débito de créditos para ferramentas CADU

Toda ferramenta que chama um provedor de IA deve usar `ToolTokenLedger` e
`charge_from_provider` após receber o resultado. O saldo é único por cliente,
vem de `cadu_credits_extras` e é consumido por ordem de expiração.

1. Antes de enviar uma geração cara, estime o consumo e execute
   `ledger.assert_available(client_id, estimated_tokens)`.
2. Use uma `idempotency_key` por execução. Repetir uma requisição não pode
   cobrar duas vezes.
3. Ao receber o resultado, grave `tool`, `stage`, modelo, tokens de entrada e
   saída, custo interno e metadados com `charge_from_provider`.
4. Se `InsufficientToolCredits` for levantada, não envie a requisição ao
   provedor. A API deve responder com orientação para `/workspace/app/creditos`.
5. Não atualize `tokens_used` diretamente fora do ledger. O serviço faz o
   bloqueio, a alocação entre lotes e o registro em `cadu_tools_token_usage`
   na mesma transação.

O Chat de Conversas/Famílias registra seu consumo em `cadu_token_usage`; o
admin o apresenta separadamente do uso em `cadu_tools_token_usage`.
