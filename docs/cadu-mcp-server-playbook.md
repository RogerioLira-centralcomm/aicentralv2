# Playbook — servidores MCP do Cadu

Documentação navegável da versão inicial: [`cadu-mcp-v1.html`](./cadu-mcp-v1.html).
Arquitetura do agente e fronteira entre Harness, tools, skills e MCP:
[`cadu-agent-architecture.md`](./cadu-agent-architecture.md).

Este documento é a referência para criar os próximos servidores MCP sem
duplicar autorização, regras de tenant ou consultas de produto.

## Decisão estrutural

O produto é dividido em três camadas:

```text
serviços de domínio Python
        ↓
Tool Registry do Cadu
        ├── chamada direta pelo runtime Cadu
        ├── MCP interno
        └── MCP para agentes do cliente
```

O protocolo MCP é um adaptador. Regras de produto nunca ficam em rotas MCP,
prompts ou no Dify.

## Componentes reutilizáveis

| Componente | Local | Reutilização |
|---|---|---|
| Contrato de contexto | `cadu_workspace/agent_v2/contracts.py` | Tenant, usuário, projeto, superfície e objeto ativo |
| Contexto autorizado | `cadu_workspace/agent_v2/request_context.py` | Cria contexto apenas de sessão/servidor |
| Registro de tools | `cadu_workspace/mcp/registry.py` | Catálogo, exposure, effect, schemas e execução in-process |
| Delegação curta | `cadu_workspace/mcp/authorization.py` | Agentes internos e testes integrados |
| Transporte HTTP | `cadu_workspace/mcp/routes.py` | JSON-RPC/Streamable HTTP stateless |
| Tools de domínio | `cadu_workspace/mcp/tools/` | Handlers sem dependência do transporte |

## Perfis de exposição

Toda ferramenta declara explicitamente onde pode aparecer:

- `internal`: Cadu Conversas e agentes operados pelo Cadu;
- `customer_agent`: agentes de mercado conectados pelo usuário;
- exposições futuras devem ser adicionadas por allowlist, nunca por exclusão.

Uma tool interna não aparece em `tools/list` para um agente do cliente e sua
execução direta com esse perfil também é recusada.

## Template de ferramenta

```python
@register_tool(
    name="planner.get_media_plan",
    description="Obtém um plano de mídia autorizado.",
    capability="planner",
    effect="read",
    version="1.0.0",
    exposures=("internal", "customer_agent"),
    requires_project=True,
    input_schema={
        "type": "object",
        "required": ["plan_id"],
        "properties": {"plan_id": {"type": "string"}},
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "required": ["id", "title"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
        },
    },
)
def get_media_plan(context: RequestContext, arguments: dict) -> dict:
    # O client_id vem exclusivamente do contexto assinado.
    return domain_service.get_plan(context.client_id, arguments["plan_id"])
```

## Convenções obrigatórias

### Nome

```text
dominio.verbo_objeto
```

Exemplos:

- `workspace.search_project_content`
- `planner.get_media_plan`
- `reports.compare_report_to_plan`

### Operação semântica

Uma tool representa uma intenção completa. Não criar ferramentas como
`select_table`, `run_sql`, `update_row` ou CRUD que revele o banco.

### Escopo

- IDs de tenant e usuário nunca são argumentos da tool;
- projeto vem do `RequestContext` ou é validado contra ele;
- retorno nunca inclui credenciais, campos comerciais privados ou IDs de
  provider sem necessidade de produto;
- resultados são limitados e ordenados deterministicamente.

### Efeito

- `read`: sem alteração; pode ser idempotente;
- `draft`: cria estado reversível e versionado;
- `write`: altera estado confirmado e exige política adicional.

Na delegação curta emitida por uma sessão autenticada, tools externas podem
criar rascunhos e executar escritas explicitamente confirmadas. Toda escrita
recebe `request_id`, permanece restrita ao tenant e registra seu estado no
domínio. OAuth, revogação por aplicativo e rate limit são obrigatórios antes
da distribuição pública em marketplaces.

### Versão

A versão da tool é independente da versão do servidor.

- mudança aditiva de saída: minor;
- correção sem alteração de contrato: patch;
- remoção, renomeação ou mudança semântica: nova tool ou major;
- não alterar silenciosamente o significado de um campo já publicado.

## Autorização interna e externa

### Interna

O endpoint `/workspace/api/v2/mcp-token` emite delegação assinada por cinco
minutos. Ela contém o contexto já autorizado e o perfil de exposição.

### Agentes do cliente

A delegação curta é suficiente para testes e conexões iniciadas dentro do
Cadu. Para distribuição pública, implementar um authorization server OAuth
2.1/OIDC com:

- consentimento por workspace;
- audience do servidor MCP;
- scopes por capability e efeito;
- revogação;
- expiração curta e refresh token protegido;
- metadata de Protected Resource;
- registro/auditoria da aplicação conectada.

Não reutilizar um token estático global e não aceitar `client_id` enviado pelo
agente como autorização.

Scopes sugeridos:

```text
cadu.workspace.read
cadu.planner.read
cadu.studio.read
cadu.reports.read
cadu.artifacts.draft
```

## Compatibilidade com a especificação MCP

O endpoint atual é stateless e suporta `initialize`, `tools/list` e
`tools/call`. Para clientes do protocolo `2026-07-28`, valida também
`Mcp-Method` e `Mcp-Name`. Erros esperados de ferramenta voltam como resultado
com `isError=true`; falhas de protocolo usam erro JSON-RPC.

O SDK Python oficial atual requer Python 3.10+. Este repositório ainda roda em
Python 3.9, portanto o transporte permanece pequeno e próprio. Ao atualizar o
runtime, substituir apenas `mcp/routes.py` por uma aplicação Streamable HTTP do
SDK oficial; `registry.py`, handlers e serviços de domínio permanecem.

Referências primárias:

- https://modelcontextprotocol.io/specification
- https://py.sdk.modelcontextprotocol.io/
- https://py.sdk.modelcontextprotocol.io/run/asgi/

## Como criar o próximo servidor/domínio

1. Confirmar quais objetos o produto realmente possui.
2. Definir de cinco a dez operações semânticas.
3. Classificar cada operação como `read`, `draft` ou `write`.
4. Criar handlers em `mcp/tools/<dominio>.py`.
5. Registrar o módulo em `load_builtin_tools()`.
6. Declarar schemas fechados com `additionalProperties: false`.
7. Adicionar `customer_agent` somente após revisar todos os campos de saída.
8. Testar tenant diferente, projeto diferente e exposure diferente.
9. Testar limites, erros utilizáveis e ordenação do catálogo.
10. Publicar changelog das tools expostas.

Não é necessário criar outro transporte HTTP para cada domínio. O servidor
Cadu publica um catálogo único filtrado pelas capabilities e pelo consentimento
do usuário. Um servidor separado só é indicado quando houver outro limite de
segurança, operação, domínio legal ou ciclo de deploy.

## Testes mínimos por ferramenta

- usuário autorizado recebe o objeto;
- objeto de outro tenant não é encontrado;
- ausência de projeto falha antes do handler;
- argumento desconhecido é recusado pelo schema/handler;
- exposure não permitida não lista nem executa a tool;
- retorno não contém campos classificados;
- lista possui limite e ordem estável;
- leitura repetida produz resultado equivalente;
- erro esperado não se transforma em erro interno.

## Observabilidade

Registrar sem conteúdo sensível:

- aplicação/agente conectado;
- usuário delegado;
- tenant;
- tool e versão;
- run e conversation;
- status;
- duração;
- tamanho de entrada e saída;
- código de erro;
- idempotency key para escrita.

Não registrar documento integral, prompt, token de acesso ou resposta privada.

## Critério para publicação externa

Uma tool só entra no catálogo `customer_agent` quando:

- possui schema de entrada e saída;
- consulta serviços com filtro de tenant obrigatório;
- não depende de sessão do navegador;
- tem documentação e exemplos;
- possui teste de isolamento;
- tem limite de volume;
- possui política de compatibilidade;
- foi classificada quanto a dados pessoais e comerciais;
- está incluída em auditoria e rate limit.

## Arquivos e fontes de projeto

O envio de binários usa duas etapas: `projects.prepare_source_upload` cria uma
autorização curta e registra duas decisões independentes. `use_as_knowledge`
define a finalidade (`knowledge_source` ou `project_attachment`) e somente a
primeira permite extração e RAG. `category` é opcional e classifica o papel do
arquivo (`brief`, `research`, `media_plan`, `report`, `brand_asset`,
`reference`, `contract`, `spreadsheet` ou `other`). A classificação automática
nunca muda a finalidade escolhida pelo usuário.

`workspace.list_projects` devolve uma projeção leve em `summary`: fontes,
anexos, artifacts, planos de mídia, relatórios, imagens e vídeos do Studio.
Os conteúdos permanecem em ferramentas específicas e são carregados apenas
quando necessários, evitando contexto, custo e latência desnecessários.

O cliente envia multipart para `/workspace/mcp/uploads` usando essa autorização.
O argumento `use_as_knowledge` é obrigatório e nunca pode ser inferido pelo
tipo ou nome do arquivo:

- `true`: extrai texto, indexa no RAG do projeto e cobra os créditos do usuário;
- `false`: mantém o arquivo privado como anexo, sem utilizá-lo como evidência.

Na versão inicial, imagens são aceitas como anexos. OCR ou entendimento visual
somente devem ser habilitados quando tiverem orçamento, consentimento e política
de retenção próprios.

## Marcas e auditoria

O MCP também expõe `brands.list`, `brands.create`,
`brands.prepare_logo_upload`, `brands.start_audit` e `brands.audit_status`.
O logo usa uma autorização multipart de dez minutos em
`/workspace/mcp/brand-uploads` (limite real de 5 MB). A auditoria nunca é acionada implicitamente pelo
cadastro ou pelo upload: exige uma chamada separada, administrador do tenant,
saldo disponível, `confirmed: true` e `request_id` idempotente. O resultado continua como proposta
pendente de revisão no Workspace.
