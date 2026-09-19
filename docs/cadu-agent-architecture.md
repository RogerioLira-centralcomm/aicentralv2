# Cadu Agent Architecture — Harness, MCP e Orquestração

Status: arquitetura canônica e plano incremental  
Atualizado em: 19 de setembro de 2026

## 1. Decisão central

O **Cadu Harness é o cérebro operacional do agente**. Ele recebe a intenção do
usuário, resolve o contexto autorizado, escolhe capacidades, controla execução,
normaliza resultados, persiste estado e entrega eventos para a interface.

O **MCP não é o cérebro do Cadu**. Ele é um protocolo e uma camada padronizada
para expor capacidades semânticas do produto ao Harness e, com autorização
própria, a agentes externos do cliente.

```text
Cadu UI
   ↓
Cadu Harness
   ├── Conversation / Turn Manager
   ├── Context Resolver
   ├── Router
   ├── Task Planner
   ├── Model Runtime
   ├── Tool Orchestrator
   ├── Artifact Manager
   ├── Version Manager
   ├── Event / Streaming Layer
   ├── Permission Layer
   └── Observability
            ↓
        Tool Layer
        ├── Native Tools
        ├── Skills
        └── Cadu MCP
              ├── Workspace
              ├── Planner
              ├── Studio
              └── Reports
```

Consequências dessa decisão:

- prompts não autorizam ações nem escolhem tenant;
- Dify não é fonte canônica de histórico, permissões ou artifacts;
- MCP não decide estratégia, sequência de tarefas ou política de resposta;
- ferramentas não expõem banco ou CRUD físico;
- interfaces não precisam conhecer provider, credenciais ou detalhes internos;
- o mesmo turno pode ser exibido em Conversas ou em uma sidebar de produto.

## 2. Harness versus MCP

| Responsabilidade | Cadu Harness | Cadu MCP |
|---|---:|---:|
| Interpretar pedido e escolher modo | Sim | Não |
| Resolver contexto mínimo | Sim | Não |
| Planejar etapas e orçamento | Sim | Não |
| Selecionar tools permitidas | Sim | Apenas filtra catálogo autorizado |
| Executar modelo | Sim | Não |
| Normalizar resposta | Sim | Não |
| Persistir Conversation/Turn/Items | Sim | Não |
| Gerenciar artifacts e versões | Sim | Expõe operações semânticas |
| Autorizar tenant/usuário | Sim | Revalida contexto delegado |
| Expor capacidades a agentes externos | Indiretamente | Sim |
| Transportar chamadas padronizadas | Opcional | Sim |

O Harness pode chamar uma capacidade Python diretamente quando ela está no
mesmo processo. O registro semântico é compartilhado com o MCP para impedir que
o comportamento interno e o comportamento externo criem duas implementações.

## 3. Fluxo canônico de uma interação

```text
User Request
  → Request Context
  → Intent Router
  → Context Resolver
  → Task Planner
  → Capability / Tool Selection
  → Execution
  → Result Normalization
  → Persistence
  → Event Stream
  → UI Projection
```

1. A UI envia mensagem, `conversation_id`, superfície e objeto ativo.
2. O servidor deriva usuário, organização e permissões da sessão ou delegação.
3. O Router classifica domínio, ação, complexidade e modo de resposta.
4. O Context Resolver carrega somente as evidências pedidas pela rota.
5. O Task Planner cria etapas limitadas e identifica efeitos que exigem
   confirmação.
6. O Model Runtime recebe tarefa, evidências e contrato de saída compacto.
7. O Tool Orchestrator executa somente tools autorizadas e orçadas.
8. O normalizador aplica guardrails e converte a saída em Items tipados.
9. Turn, Items, telemetria e versões são persistidos antes da confirmação final.
10. A Event Layer envia estados estáveis, sem raciocínio privado ou payloads de
    provider.

## 4. Modelo de estado: Conversation → Turn → Items

### Conversation

Unidade durável de continuidade entre superfícies.

Campos mínimos:

```json
{
  "id": "uuid",
  "organization_id": 12,
  "user_id": 7,
  "title": "Lançamento do café premium",
  "project_ref": "ci:...",
  "brand_ref": "studio:81",
  "status": "active",
  "created_at": "...",
  "updated_at": "..."
}
```

Projeto e marca ficam vinculados à conversa. A superfície e o objeto ativo
podem mudar a cada Turn sem reescrever o vínculo canônico.

### Turn

Uma solicitação do usuário e sua execução correspondente.

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "request_id": "uuid",
  "surface": "planner",
  "active_object": {"type": "media_plan", "id": "..."},
  "mode": "analysis",
  "route": {"domain": "planner", "action": "analyze_plan"},
  "status": "completed",
  "started_at": "...",
  "finished_at": "..."
}
```

Estados recomendados:

```text
accepted → resolving_context → planning → executing → persisting → completed
                                                   └→ cancelled
                                                   └→ failed
```

Um Turn não deve ser executado duas vezes com o mesmo `request_id`.

### Items

Items são unidades tipadas e ordenadas de entrada, atividade e resultado. Eles
substituem a premissa de que toda resposta é apenas Markdown.

| Tipo | Finalidade |
|---|---|
| `message` | Texto do usuário ou resposta textual do Cadu |
| `activity` | Progresso público: consultando fontes, preparando briefing |
| `artifact` | Referência a objeto editável e versionado |
| `action` | Próximo passo seguro, com prompt ou operação declarada |
| `table` | Dados tabulares estruturados e acessíveis |
| `citation` | Fonte usada, com título, trecho e referência autorizada |
| `file` | Arquivo enviado ou produzido, com finalidade explícita |
| `image` / `video` | Mídia persistida, nunca apenas URL efêmera do provider |
| `error` | Falha pública sanitizada e recuperável |
| `version` | Versão criada, comparação ou possibilidade de rollback |
| `confirmation` | Efeito, custo e parâmetros aguardando aceite do usuário |

Contrato-base:

```json
{
  "id": "uuid",
  "turn_id": "uuid",
  "sequence": 4,
  "type": "artifact",
  "status": "ready",
  "content": {},
  "metadata": {},
  "created_at": "..."
}
```

O conteúdo específico deve ser validado por schema conforme o tipo. HTML
arbitrário não é um Item.

## 5. Streaming orientado a eventos

O stream público descreve mudanças de estado; ele não replica eventos crus do
Dify nem revela nomes internos de nodes, argumentos privados ou pensamentos.

Eventos canônicos:

```text
turn.accepted
route.selected
context.resolving
context.resolved
plan.created
tool.started
tool.completed
tool.failed
message.delta
message.completed
artifact.created
artifact.versioned
confirmation.required
turn.cancelled
turn.failed
turn.completed
```

Envelope:

```json
{
  "event": "artifact.created",
  "conversation_id": "uuid",
  "turn_id": "uuid",
  "sequence": 8,
  "occurred_at": "...",
  "data": {"artifact_id": "uuid", "type": "brief", "version": 1}
}
```

Regras:

- `sequence` é crescente por Turn;
- eventos podem ser reprocessados sem duplicar Items;
- cancelamento é terminal e bloqueia persistência tardia do provider;
- `turn.completed` só ocorre após persistência;
- a UI pode reconstruir o estado a partir dos Items sem depender do stream;
- erros públicos possuem código estável e mensagem útil, nunca stack trace.

## 6. Contexto canônico e mínimo

Entrada inicial:

```json
{
  "organization_id": 12,
  "user_id": 7,
  "conversation_id": "uuid",
  "surface": "planner",
  "project_ref": "ci:...",
  "brand_ref": "studio:81",
  "active_object": {"type": "media_plan", "id": "..."},
  "capabilities": ["workspace", "planner", "artifacts"]
}
```

Esse objeto identifica o contexto; ele não carrega o conteúdo completo do
projeto. O Context Resolver recupera evidências sob demanda.

Critérios para carregar contexto:

- a rota declara `needs_context` e `needs_tools`;
- cada fonte possui limite de caracteres/linhas/objetos;
- histórico é resumido e limitado, não reenviado integralmente;
- conteúdo recuperado é tratado como dado não confiável;
- uma capability ausente não pode ser simulada por prompt;
- dados de Studio ou Reports não entram em uma pergunta simples do Planner;
- o resolvedor registra o que consultou e o que ficou indisponível.

Exemplo:

> “Esse plano está muito concentrado em display?”

Carrega objeto ativo, alocações e objetivos do plano. Não carrega Studio,
Reports, arquivos gerais ou catálogo completo.

> “Isso explica o resultado de agosto?”

Adiciona Reports, período e métricas relevantes porque a nova intenção exige
comparação entre plano e resultado.

## 7. Capabilities de produto

### Workspace

- contexto atual;
- projetos e marcas;
- fontes e arquivos;
- membros e permissões;
- memória confirmada;
- atividade do projeto.

### Planner

- briefing;
- plano de mídia;
- objetivos, públicos, canais e formatos;
- investimentos e períodos;
- cenários e versões;
- análise e comparação de planos.

### Studio

- projetos criativos;
- assets e referências;
- imagens, vídeos e outputs;
- criação usando créditos do usuário;
- versões e vínculo com marca/projeto.

Studio deve ser integrado somente quando seus contratos de geração, cobrança,
persistência e status estiverem estabilizados. O MCP prepara o encaixe, mas não
deve publicar tools instáveis.

### Reports

- documentos e relatórios importados pelo usuário;
- métricas extraídas;
- períodos, canais e plataformas;
- comparações e análises derivadas.

Não presumir conexão direta com Meta Ads ou Google Ads. Reports organiza o que
foi importado ou conectado por fluxos autorizados.

## 8. Native Tools, Skills e MCP

### Native Tools

Funções do próprio runtime, executadas diretamente e com baixa latência.
Exemplos: recuperar contexto atual, persistir Item, criar artifact, verificar
permissão. Não precisam atravessar HTTP quando estão no mesmo processo.

### Skills

Instruções especializadas, critérios de qualidade e procedimentos de domínio.
Uma skill orienta **como pensar ou executar uma tarefa**, mas não concede acesso
a dados nem substitui autorização. Deve ser carregada apenas quando a rota a
selecionar.

### MCP

Contrato interoperável para descobrir e chamar capacidades semânticas. É útil
para modularidade, agentes de terceiros e fronteiras de processo. Não deve
conter planejamento geral nem regras duplicadas de negócio.

Ordem de decisão:

1. O Harness entende a intenção.
2. Seleciona skill quando há procedimento especializado.
3. Seleciona native tool ou MCP conforme fronteira operacional.
4. O Permission Layer revalida a operação.
5. O resultado volta como Item tipado.

## 9. Modos de execução

| Modo | Uso | Contexto | Tools | Saída esperada |
|---|---|---|---|---|
| `fast` | Resposta simples, reescrita, síntese curta | Mínimo | 0–1 | `message` |
| `analysis` | Diagnóstico, comparação, recomendação | Seletivo | 1–4 | `message`, `table`, `citation` |
| `agentic` | Trabalho com etapas e artifacts | Planejado | Orçamento explícito | `activity`, `artifact`, `action`, `version` |

O usuário pode escolher profundidade, mas o Router ainda aplica limites. Um
pedido simples não vira agentic apenas porque há muitas tools disponíveis.

Orçamentos mínimos por Turn:

- máximo de chamadas de modelo;
- máximo de chamadas de tools;
- máximo de contexto;
- máximo de tokens de saída;
- tempo total;
- custo estimado e limite de crédito;
- número máximo de perguntas ao usuário.

## 10. Arquivos e artifacts

Arquivos e artifacts são conceitos diferentes:

- **arquivo**: binário ou fonte enviada/produzida;
- **artifact**: objeto de trabalho estruturado, editável e versionado.

Todo upload precisa de finalidade explícita:

```text
conversation_only | project_attachment | project_knowledge | brand_asset
```

No armazenamento do projeto, intenção e classificação são dimensões diferentes:

- `purpose=knowledge_source` só existe por escolha explícita do usuário e autoriza extração/indexação;
- `purpose=project_attachment` guarda o arquivo no projeto sem colocá-lo no RAG;
- `category` descreve o papel do conteúdo (`brief`, `research`, `media_plan`, `report`, `brand_asset`, `reference`, `contract`, `spreadsheet`, `other`);
- o classificador pode sugerir `category`, mas nunca pode promover um anexo a fonte de conhecimento;
- o catálogo de projetos expõe contagens leves de fontes, anexos, artifacts, planos, relatórios e itens do Studio; conteúdo detalhado continua sob demanda.

`project_knowledge` permite extração e indexação; `project_attachment` não pode
ser usado como evidência automática. A escolha não é inferida pelo nome ou MIME.

Artifacts suportados inicialmente:

```text
brief | document | note | executive_summary | media_plan | scenario | research
```

Regras:

- criação começa como draft;
- atualização exige `expected_version`;
- conflito retorna a versão atual sem sobrescrever;
- publicação e arquivamento são efeitos separados;
- conteúdo grande fica no artifact, não dentro da mensagem;
- a conversa referencia o artifact por ID e versão.

## 11. Versionamento e rollback

Cada alteração cria uma versão imutável contendo conteúdo, autor, data e resumo
da mudança. O objeto principal aponta para `current_version`.

Rollback não apaga histórico: cria uma nova versão a partir de uma versão
anterior. Operações externas precisam de `request_id` idempotente e controle
otimista para evitar sobrescrita concorrente.

O mesmo padrão deve ser aplicado futuramente a briefings, planos, cenários,
criativos e relatórios derivados quando seus domínios oferecerem versão própria.

## 12. Autenticação, autorização e confirmação

Camadas atuais:

1. sessão Cadu autenticada;
2. contexto derivado no servidor;
3. CSRF em mutações originadas no navegador;
4. delegação MCP assinada, curta e restrita ao contexto;
5. allowlist por capability, exposure e effect;
6. verificação de ownership/tenant dentro do serviço de domínio.

Regras obrigatórias:

- nunca aceitar `client_id`, `organization_id` ou `user_id` como autoridade do
  payload do modelo;
- tools `write` exigem confirmação explícita e `request_id`;
- custo é verificado antes do provider pago;
- acesso é revalidado no momento da execução;
- tokens e credenciais nunca entram no prompt ou no stream;
- agente externo público exigirá OAuth 2.1/OIDC, scopes, consentimento,
  revogação e rate limit.

## 13. Observabilidade por Turn

Registrar:

- conversation, turn, request e runtime version;
- rota, modo e budgets;
- contexto solicitado e tamanho efetivamente carregado;
- tool, versão, status, duração e código de erro;
- modelo/provider lógico, sem chave ou payload secreto;
- tempo até primeiro evento e duração total;
- tokens de entrada/saída/cache;
- custo estimado, custo confirmado e chave idempotente;
- artifact/version produzidos;
- estado terminal e causa sanitizada.

Não registrar por padrão:

- prompt completo;
- documentos e arquivos integrais;
- tokens de autenticação;
- raciocínio privado do modelo;
- credenciais ou respostas cruas de providers.

Métricas operacionais:

```text
turn_success_rate
turn_cancel_rate
first_event_ms
turn_total_ms
context_chars
tool_calls_per_turn
tool_failure_rate
tokens_and_cost_per_mode
artifact_acceptance_rate
follow_up_question_rate
```

## 14. Mesma conversa em Conversas e sidebars

A superfície é uma projeção, não uma conversa separada.

- Workspace Conversas oferece histórico e artifacts completos.
- Planner injeta o plano ativo e destaca ações de planejamento.
- Studio injeta o projeto/asset ativo e destaca geração/edição.
- Reports injeta relatório/período ativo e destaca comparação.

Cada envio carrega `surface` e `active_object`. A Conversation preserva
histórico, projeto e marca. O Turn registra onde foi iniciado. A UI renderiza os
mesmos Items com densidade e ações adequadas ao espaço disponível.

Uma sidebar não deve carregar todas as tools do produto. Ela solicita as
capabilities permitidas para a superfície e o Router reduz o catálogo conforme
a intenção.

## 15. Dify e Model Runtime

Dify permanece como adaptador de Model Runtime enquanto entregar valor em
modelo, flow ou operação. Ele não controla:

- autenticação;
- tenant;
- catálogo efetivo de tools;
- persistência canônica;
- cobrança final;
- artifacts e versões;
- política de resposta;
- status terminal do Turn.

Para reduzir custo e latência:

- usar um app V2 separado do legado durante rollout;
- manter o flow curto para `fast` e `analysis`;
- não repetir no Dify contexto já resolvido pelo Harness;
- não ativar nodes genéricos em toda requisição;
- enviar contrato de saída estruturado;
- medir a latência do Dify separadamente do tempo de tools e persistência.

Se um fluxo Dify apenas replica Router, Planner ou autorização, ele deve ser
removido. Se oferece uma especialização real, permanece atrás do Model Runtime.

## 16. Critérios para não carregar tudo

Uma informação ou tool só entra no Turn quando pelo menos uma condição for
verdadeira:

1. a rota a declarou necessária;
2. o objeto ativo exige sua leitura;
3. uma etapa anterior produziu uma dependência explícita;
4. o usuário pediu a comparação/domínio;
5. uma policy obrigatória exige a verificação.

Não carregar quando:

- serve apenas como possibilidade futura;
- pertence a outra capability sem relação com o pedido;
- duplica dado já resumido;
- excede budget sem alterar a decisão;
- é um catálogo amplo que pode ser pesquisado;
- é uma fonte não autorizada ou sem finalidade definida.

## 17. Estado atual no repositório

| Componente | Situação | Implementação principal |
|---|---|---|
| RequestContext | Implementado | `agent_v2/contracts.py`, `request_context.py` |
| Router | Implementado, regras iniciais | `agent_v2/router.py` |
| Context Resolver | Implementado, catálogo parcial | `agent_v2/context_resolver.py` |
| Task Planner | Implementado, plano simples | `agent_v2/task_planner.py` |
| Model Runtime Dify V2 | Implementado | `agent_v2/provider.py` |
| Guardrails/normalização | Implementado | `agent_v2/guardrails.py`, `response_policy.py` |
| Streaming V2 | Implementado, eventos iniciais | `agent_v2/service.py`, `runtime-v2.js` |
| Cancelamento terminal | Implementado | `agent_v2/routes.py`, `service.py` |
| Artifacts/versionamento | Implementado | `artifacts/service.py` |
| MCP/registry | Implementado | `mcp/registry.py`, `mcp/routes.py` |
| Workspace/Planner/Reports tools | Parcial | `mcp/tools/` |
| Fontes de projeto | Implementado | `project_source_service.py` |
| Resource Registry do projeto | Parcial | `project_resource_service.py`, Workspace e `projects.list_resources` |
| Organização contínua | Fundação implementada | Jobs persistidos e hooks em fontes/artifacts; worker assíncrono ainda pendente |
| Marcas/logo/auditoria | Implementado | `brand_mcp_service.py`, `mcp/tools/brands.py` |
| Studio tools estáveis | Pendente | Publicar após contratos do Studio |
| ExecutionMode | Implementado | `fast`, `analysis` e `agentic` no contrato, router, budgets, persistência e UI |
| Turn Items genéricos | Parcial | Hoje mensagens, runs, tool calls e artifacts estão separados |
| Event journal/replay V2 | Implementado | Journal ordenado e leitura do Turn sem redisparar o provider |
| Planos e checkpoints agentic | Fundação implementada | Etapas e checkpoints persistidos; executor de retomada/confirmacão ainda pendente |
| OAuth para agentes externos | Pendente | Delegação curta atende uso iniciado no Cadu |
| Observabilidade CentralX | Implementado, primeira versão | Latência, tokens, custo estimado, tools, estado terminal, timeline e painel administrativo |

## 18. Plano de implementação

### Fase A — consolidar o Harness atual (concluída)

- formalizar `ExecutionMode` (`fast`, `analysis`, `agentic`);
- criar contrato único de `Turn` e `Item` sem remover tabelas saudáveis;
- adaptar eventos atuais ao envelope canônico;
- registrar first-event, duração, tokens, custo e estado terminal;
- tornar budgets executáveis, não apenas informativos.

### Fase B — persistência e retomada (fundação concluída)

- criar journal ordenado de eventos/Items;
- reabrir Turn sem redisparar provider;
- reconciliar cancelamento, falha, cobrança e resposta persistida;
- adicionar rollback de artifact como nova versão;
- implementar idempotência durável em todas as tools mutáveis.

### Fase C — orquestração de tools

- selecionar catálogo por rota, capability e exposure;
- adicionar confirmação tipada para efeitos e custos;
- executar plano de múltiplas etapas com limites;
- padronizar outputs de table, citation, file e version;
- impedir que modelo invoque nomes fora do plano autorizado.

### Fase D — sidebars

- extrair cliente de eventos e renderer de Items reutilizável;
- integrar primeiro Planner, depois Reports;
- integrar Studio somente após estabilização das tools de geração;
- manter uma Conversation entre superfícies;
- testar desktop, tablet, mobile, foco e reconexão.

### Fase E — MCP para agentes do cliente

- implementar OAuth 2.1/OIDC e consentimento por capability/effect;
- adicionar scopes, rate limit e revogação;
- emitir catálogo reduzido por usuário e organização;
- publicar documentação de compatibilidade e changelog;
- testar isolamento entre tenants e aplicações conectadas.

## 19. Critérios de aceite

- um pedido simples faz no máximo uma chamada de modelo e nenhuma tool
  desnecessária;
- resposta de briefing não despeja formulário no chat: cria artifact editável;
- no máximo duas perguntas essenciais em `artifact_first`;
- cancelamento não salva resposta tardia nem cobra resultado cancelado;
- mudança de superfície preserva Conversation e cria novo Turn contextual;
- toda escrita possui confirmação, idempotência e autorização revalidada;
- artifacts nunca são sobrescritos sem controle de versão;
- tools e contexto carregados aparecem na telemetria do Turn;
- falha de uma capability não expõe provider ou segredo;
- agente externo não consegue escolher tenant pelo payload;
- UI pode reconstruir o estado somente a partir de Conversation, Turns e Items.

## 20. Referências do repositório

- `docs/cadu-conversations-v2-backend.md`: contrato do runtime V2 atual;
- `docs/cadu-mcp-server-playbook.md`: regras para tools e servidores MCP;
- `docs/cadu-mcp-v1.html`: documentação navegável do MCP inicial;
- `docs/cadu-conversas-contratos.md`: inventário e contratos da migração;
- `docs/CADU_SKILLS_ARCHITECTURE.md`: arquitetura de skills;
- `docs/cadu-credit-debit-contract.md`: autorização e cobrança de créditos.

Este documento é a fonte de verdade para a divisão de responsabilidades entre
Harness, Model Runtime, tools, skills e MCP. Documentos de domínio podem detalhar
contratos próprios, mas não devem redefinir essa fronteira.
