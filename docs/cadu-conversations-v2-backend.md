# Cadu Conversations V2 — contrato do backend

Este runtime é paralelo ao chat legado. O browser não chama o Dify nem escolhe
credenciais, tenant, ferramentas ou IDs de autorização.

## Fluxo

1. `RequestContext` deriva identidade e seleção da sessão validada.
2. O router determinístico escolhe domínio, ação e política.
3. O `ContextResolver` executa apenas as ferramentas declaradas pela rota.
4. O `PromptAssembler` envia ao app Dify V2 uma tarefa e evidências compactas.
5. O normalizador limita perguntas, ações e conteúdo antes da persistência.
6. Artefatos são objetos versionados; não são inferidos do Markdown final.

## Dify V2

Criar um app separado, configurado por:

- `CADU_CONVERSATIONS_V2_DIFY_URL`
- `CADU_CONVERSATIONS_V2_DIFY_KEY`
- `CADU_CONVERSATIONS_V2_ENABLED`

Variáveis esperadas pelo app:

- `core`
- `task`
- `current_context`
- `evidence`
- `response_policy`
- `output_contract`

O app deve responder JSON com:

```json
{
  "answer": "string",
  "confidence": "low|medium|high",
  "assumptions": [],
  "questions": [],
  "actions": [],
  "artifact_patch": {
    "title": "string",
    "summary": "string",
    "fields": [
      {"key": "string", "value": "string", "state": "confirmed|inferred|assumed|missing|conflicting"}
    ]
  },
  "citations": []
}
```

O Dify não autoriza ferramentas, não seleciona tenant, não grava artefatos e
não é a fonte canônica do histórico.

## Endpoints iniciais

- `GET /workspace/conversas-v2-lab` (laboratório autenticado para QA)
- `GET /workspace/api/v2/capabilities`
- `POST /workspace/api/v2/route`
- `POST /workspace/api/v2/mcp-token`
- `POST /workspace/api/v2/artifacts`
- `GET/PATCH /workspace/api/v2/artifacts/{id}`
- `POST /workspace/mcp`

Todos exigem sessão autenticada. POST/PATCH exigem o CSRF da família Cadu em
`X-CSRF-Token`. O endpoint de token emite uma delegação assinada de cinco
minutos contendo apenas o tenant, projeto, objeto e capabilities já validados.
Outros agentes usam essa delegação como `Authorization: Bearer ...` no MCP;
IDs livres enviados pelo agente nunca definem a autorização.

O laboratório permite injetar cenários simples, briefing, busca no projeto,
decisão e comparação de relatório. Ele mostra separadamente resposta,
perguntas, ações, eventos de execução e o artefato estruturado; não substitui
o frontend definitivo e não acessa o Dify diretamente pelo navegador.

Para criar novas tools ou preparar exposição a agentes do cliente, seguir
`docs/cadu-mcp-server-playbook.md`. O catálogo separa `internal` de
`customer_agent` e mantém handlers independentes do transporte.

## Aplicação da migration

Executar `python3 migrations/run_add_cadu_conversations_v2.py` antes de
habilitar criação de artefatos. O runner aplica e valida a migration aditiva;
ele não ativa a flag e não altera mensagens ou conversas legadas.
