# Cadu Orchestrator — mapa de evolução e integrações

Status: arquitetura refinada em execução. A Fase 1 foi iniciada com Provider Registry, três configurações Dify, seleção por `ExecutionMode` e sessão de provider separada por Conversation/runtime. Prompts, schemas finais de cada domínio e publicação de tools mutáveis continuam deliberadamente abertos.

## 1. Estado atual

- O Harness V2 já resolve contexto, rota, modo, budgets, tools, artifacts, journal, checkpoints e observabilidade.
- Existe uma única configuração Dify V2: `CADU_CONVERSATIONS_V2_DIFY_URL` e `CADU_CONVERSATIONS_V2_DIFY_KEY`.
- `fast`, `analysis` e `agentic` existem como modos do Harness, mas ainda chegam ao mesmo runtime Dify.
- O MCP interno já expõe Workspace, projetos, arquivos, artifacts, marcas, Planner e Reports em diferentes níveis.
- Planner, Studio, Creative Analyzer e Reports possuem APIs e regras próprias que não devem ser duplicadas dentro dos agentes.

## 2. Arquitetura proposta

```text
Cadu UI / Sidebars / agentes externos
                ↓
          Cadu Harness
  contexto → rota → política → budget
                ↓
        Runtime Selector
        ├── Dify Fast
        ├── Dify Analyst
        └── Dify Operator
                ↓
        Tool Orchestrator
        ├── Native Python adapters
        ├── Cadu MCP
        └── APIs internas por produto
                ↓
 Workspace · Planner · Studio · Reports
```

O Harness continua sendo o cérebro operacional. Os três agentes Dify são runtimes especializados de linguagem; não controlam tenant, permissões, cobrança, histórico canônico ou escrita direta no banco.

## 3. Três agentes Dify

| Agente | Quando usar | Responsabilidade | Tools | Limites iniciais |
|---|---|---|---|---|
| `cadu-fast` | Ajustes, respostas curtas, síntese simples | Responder rapidamente com contexto mínimo | Nenhuma ou uma leitura | 1 chamada, até 1 tool, 30 s |
| `cadu-analyst` | Diagnóstico, comparação, pesquisa e recomendação | Trabalhar evidências e produzir decisão explicável | Leituras de Workspace, Planner e Reports | Até 2 chamadas, 8 tools, 120 s |
| `cadu-operator` | Criar, atualizar, analisar mídia ou executar trabalho em etapas | Propor plano, gerar artifacts e solicitar ações | Catálogo reduzido por plano; escritas passam pelo Harness | Até 3 chamadas, 12 tools, checkpoints, 240 s |

### Topologia recomendada no Dify

Na primeira etapa, usar três apps Chatflow independentes. Isso mantém o transporte atual por `/chat-messages`, streaming e cancelamento, evitando introduzir simultaneamente o contrato diferente de `/workflows/run`.

- `cadu-fast`: fluxo curto, modelo rápido, sem memória ampla e sem nodes de tool.
- `cadu-analyst`: fluxo com validação de evidências, saída estruturada e modelo de maior capacidade.
- `cadu-operator`: fluxo com planejamento e propostas de ação, mas sem credenciais para escrever diretamente nos produtos.

Depois da estabilização, etapas determinísticas longas do Operator podem migrar para Workflow. Essa mudança deve ser interna ao `ProviderRegistry`, sem alterar o contrato da UI.

### Regra de roteamento

1. Router determinístico escolhe domínio, ação e complexidade.
2. Policy Engine define o modo permitido e o budget.
3. Runtime Selector escolhe uma das três configurações Dify.
4. Tool Orchestrator entrega apenas as tools necessárias para aquela rota.
5. Toda mutação vira proposta de ação; o Harness revalida permissão, idempotência, créditos e confirmação.
6. Fallback entre agentes só ocorre antes de uma mutação ou cobrança. Uma execução parcialmente realizada não é reiniciada às cegas.

### Continuidade entre agentes

Uma Conversation do Cadu pode alternar entre os três agentes. Ela não pode depender de um único `dify_conversation_id`.

- histórico, artifacts, decisões e Items permanecem canônicos no CentralX;
- cada runtime mantém sua própria sessão de provider, vinculada por `conversation_id + runtime_id`;
- ao trocar de agente, o Harness envia um resumo canônico e as evidências necessárias, não o histórico privado do outro runtime;
- trocar de agente não duplica mensagem, tool, cobrança ou artifact;
- prompt, modelo, workflow e contrato usados em cada Turn ficam versionados na observabilidade.

## 4. Contrato comum entre Harness e Dify

Todos os agentes recebem o mesmo envelope mínimo:

```text
task
execution_mode
response_policy
request_context resumido
evidence selecionada
available_actions permitidas
output_contract
```

Todos devolvem Items estruturados, não HTML arbitrário:

- `message`: resposta breve ao usuário;
- `activity`: progresso público;
- `citation`: fonte utilizada;
- `table`: comparação estruturada;
- `artifact_patch`: criação ou atualização editável;
- `action_proposal`: ação que depende do Harness;
- `confirmation`: decisão solicitada ao usuário;
- `error`: falha pública normalizada.

O Dify não recebe catálogo completo, segredos, SQL, dados de outro tenant nem conteúdo sem finalidade autorizada.

### Protocolo de tool e action

Na primeira camada, o Dify não faz function calling livre. O Harness pré-resolve as leituras previstas pela rota e envia evidências normalizadas. O Operator pode devolver `action_proposal`, mas somente o Harness converte essa proposta em uma action tipada.

```text
proposta do modelo
  → validar schema
  → resolver capability e adapter
  → estimar efeito/custo
  → solicitar confirmação quando necessário
  → executar com idempotency key
  → persistir receipt/checkpoint
  → devolver Item público
```

Uma action aprovada contém parâmetros normalizados e hash. A confirmação não autoriza parâmetros diferentes nem uma segunda execução.

## 5. Camada de integração

| Camada | Usar quando | Exemplo |
|---|---|---|
| Native adapter Python | Serviço está no mesmo monólito e a regra já existe | Planner plans, artifacts, Resource Registry |
| Cadu MCP | Capacidade precisa ser reutilizada por Conversas, sidebars e agentes externos | Projetos, arquivos, marcas, Planner, Reports |
| API interna | Produto tem runtime, upload ou job especializado | Studio e Creative Analyzer |
| Provider direto | Somente dentro do adapter proprietário | Dify, geração de imagem, análise multimodal |

Uma tool MCP deve chamar o serviço canônico. Ela não replica regra de negócio, cálculo de crédito, validação de projeto ou persistência.

### Separar consultas de comandos

- **Queries**: leitura repetível, cacheável e sem confirmação; podem ser pré-resolvidas antes do Dify.
- **Draft commands**: criam rascunho reversível; exigem idempotência, mas podem dispensar confirmação conforme policy.
- **Commands**: publicam, cobram, arquivam, enviam, compartilham ou alteram estado relevante; exigem confirmação e receipt.
- **Jobs**: operações demoradas; retornam imediatamente `job_id`, estado e estimativa, nunca prendem o Turn HTTP.

O catálogo deve declarar `effect`, `risk`, `async`, `estimated_cost`, `requires_confirmation`, `idempotent` e `reversible`. Apenas `effect` é insuficiente para governar ferramentas de domínios diferentes.

## 6. Domínios de tools

### Workspace e projetos

Já disponíveis: contexto atual, projetos, busca, fontes, Resource Registry, inspeção de formato e upload autorizado.

Próxima camada:

- abrir e obter metadados de um recurso;
- substituir arquivo criando versão;
- renomear, classificar, vincular e arquivar;
- alterar finalidade entre anexo e fonte com confirmação;
- listar versões, relações e itens que precisam de adapter;
- pesquisar por intenção no Context Graph.

### Artifacts e documentos

Já disponíveis: listar, abrir, criar rascunho, atualizar com versão esperada e arquivar internamente.

Próxima camada: diff entre versões, rollback como nova versão, comentário, publicação e vínculo explícito com fontes.

### Planner

Já disponíveis via MCP: ler briefing e plano de mídia.

Capacidades existentes no Cadu a adaptar parcialmente:

- listar/criar/atualizar planos;
- briefing, objetivo, período, verba, KPI e status;
- audiências, canais, formatos, interativos e places;
- seleção de itens e distribuição de investimento;
- revisão de briefing, plano e documentos;
- documentos: criar, editar, duplicar, revisar e compartilhar;
- Link Tester: executar teste, consultar histórico e abrir resultado;
- cotações e publicação, sempre com confirmação.

Primeiro pacote sugerido: leituras de catálogo, `planner.link_test`, atualização de briefing e drafts de documento. Publicação e cotação ficam no pacote seguinte.

### Studio e Creative Analyzer

Capacidades existentes no Cadu:

- gerar direções e criar imagens;
- cobrar e persistir cada criação;
- analisar imagens;
- analisar vídeos e frames;
- consultar histórico e resultado;
- vincular criação ou análise a projeto e marca.

Formato MCP proposto: `estimate → create job → get job → get asset → attach`. Upload de análise usa autorização curta fora do JSON-RPC. Vídeo generativo permanece fora do primeiro pacote.

### Reports

Já disponíveis via MCP:

- `reports.list_project_reports`;
- `reports.get_report_metrics`;
- `reports.compare_report_to_plan`.

Regras atuais preservadas: somente métricas revisadas por uma pessoa são evidência factual; o agente não escolhe automaticamente um plano ou relatório ambíguo.

Próxima camada:

- importar fonte para um relatório;
- acompanhar processamento e revisão;
- listar fontes, períodos, fornecedores e conflitos;
- criar análise como artifact versionado;
- comparar períodos, campanhas e planos;
- registrar insight, decisão e recomendação no Context Graph;
- exportar ou compartilhar relatório com confirmação.

## 7. Conexões novas

Cada conexão entra por um adapter com o mesmo contrato:

```text
authorize → estimate → execute/read → normalize → persist → charge → observe
```

O registro da conexão precisa declarar:

- domínio e capabilities;
- efeitos `read`, `draft` ou `write`;
- autenticação e escopo por tenant;
- idempotência e política de retry;
- custo e reserva de créditos;
- timeout, cancelamento e estado terminal;
- dados persistidos e política de retenção;
- formato de erro público;
- eventos enviados ao journal.

### Connection Registry

Criar um registro canônico de conectores, separado do catálogo de tools. Ele identifica provider, credencial, saúde, limites e versão do adapter. Uma mesma capacidade pode trocar de provider sem mudar o nome público da tool.

Estados mínimos: `active`, `degraded`, `disabled`, `reauth_required`. O Router não envia trabalho para um conector degradado sem decidir explicitamente entre fallback, resposta parcial ou espera.

Webhooks e callbacks entram pelo mesmo registro, com assinatura validada, deduplicação por event ID e reconciliação com o job original. O callback nunca escolhe tenant a partir de parâmetros livres.

## 8. Fluxos principais

### Pedido analítico

```text
mensagem → Router → cadu-analyst → tools de leitura → resposta + citações
```

### Criação de imagem

```text
mensagem → cadu-operator → proposta de direção → estimate
→ confirmação → job Studio → asset persistido → Resource Registry → chat
```

### Arquivo enviado ao projeto

```text
inspect support → upload → classificar finalidade → registrar recurso
→ extrair/indexar se autorizado → reconciliar Context Graph → disponibilizar às tools
```

### Comparação em Reports

```text
selecionar relatório revisado + plano → cadu-analyst
→ comparação estruturada → artifact opcional → relação no projeto
```

## 9. Pontos que faltavam no desenho original

### Segurança de contexto e conteúdo

- arquivos, páginas, relatórios e resultados de tools são dados não confiáveis, não instruções;
- o Prompt Assembler delimita evidência e remove tentativas de prompt injection conhecidas;
- dados pessoais e segredos são redigidos antes de telemetria e Dify;
- autorização é revalidada na execução, não somente quando o plano é criado;
- URLs passam por proteção contra SSRF, redirect privado e download excessivo.

### Consistência e concorrência

- toda mutação recebe `request_id` e chave idempotente do servidor;
- updates usam versão esperada ou lock do recurso;
- retries de job não repetem cobrança nem publicação;
- falha depois de efeito externo gera estado `reconciliation_required`, não retry cego;
- ações compostas usam saga/checkpoints; não simulam transação distribuída.

### Proveniência e atualização

- cada evidência registra resource ID, versão, finalidade, revisão humana e instante de leitura;
- Reports registra período, fornecedor e revisão usada na análise;
- respostas antigas não são tratadas como atuais depois que uma fonte muda;
- atualização de recurso invalida apenas caches e embeddings derivados dele;
- artifacts registram quais fontes e versões sustentaram cada revisão.

### Custo, latência e capacidade

- budget é reservado antes de provider ou job pago;
- custo real é reconciliado depois, com receipt do provider;
- cache só é permitido para query estável e tenant-scoped;
- circuit breaker evita repetir chamadas em provider degradado;
- cada domínio define timeout e tamanho máximo próprios;
- fila possui prioridade, limite por tenant e proteção contra um cliente monopolizar workers.

### Qualidade e evolução

- prompts, workflows, models, policies e tool schemas têm versão independente;
- conjunto de casos de avaliação cobre respostas simples, análise, artifacts, arquivos maliciosos, Reports conflitantes e cancelamento;
- novos agentes rodam em shadow mode antes de receber tráfego pago;
- rollout por tenant e percentual, com rollback para um runtime anterior;
- feedback do usuário se liga ao Turn, runtime e versões utilizadas.

### UX e retomada

- UI mostra qual ação está em andamento, mas não detalhes internos do workflow;
- job continua depois de fechar o chat e reaparece ao reabrir a Conversation;
- confirmação mostra efeito, custo, destino e possibilidade de desfazer;
- resposta parcial permanece visível em falha recuperável;
- sidebars e Conversas usam os mesmos Items e não criam históricos paralelos.

## 10. Plano de implementação por fases

### Fase 0 — contratos e inventário

- congelar nomes de domínio, actions e Items;
- inventariar APIs canônicas, regras, credenciais, custos e tabelas de cada produto;
- classificar cada operação como query, draft, command ou job;
- definir matriz de confirmação, reversibilidade e exposição externa.

Aceite: nenhuma tool proposta duplica regra de negócio e todas possuem owner técnico e serviço canônico.

### Fase 1 — três runtimes sem novas mutações

- criar `ProviderRegistry` e configurações independentes para Fast, Analyst e Operator;
- persistir runtime, provider session, prompt/model/workflow version por Turn;
- implementar seleção, health check, circuit breaker e fallback seguro;
- executar shadow mode e comparar qualidade, custo e latência.

Aceite: os três runtimes respondem pelo mesmo contrato; alternar entre eles não perde histórico nem duplica cobrança.

### Fase 2 — leitura transversal

- ampliar queries de Planner e Reports;
- incluir Resource Registry, relações, versões e proveniência na evidência;
- tornar citações obrigatórias em análise factual;
- adicionar caching tenant-scoped e invalidação por versão.

Aceite: o Analyst responde com IDs e versões verificáveis e não carrega catálogos fora da rota.

### Fase 3 — primeira action controlada

- implementar `planner.link_test` como job idempotente;
- action proposal, estimate, confirmação, execução, receipt e retomada;
- testar timeout, cancelamento, retry e callback duplicado.

Aceite: repetir requisição ou reconectar não repete teste nem cobrança; resultado entra no projeto como recurso relacionado.

### Fase 4 — artifacts e CRUD de recursos

- abrir, renomear, classificar, substituir, versionar, relacionar e arquivar;
- promover anexo a fonte somente com consentimento;
- suportar formatos sem adapter como recursos preservados e claramente não processados;
- completar rollback e diff de artifacts.

Aceite: cada mudança é auditável, reversível quando aplicável e reconcilia índice e Context Graph.

### Fase 5 — Studio e Creative Analyzer

- contrato comum `estimate/create/get/cancel/attach`;
- imagem primeiro; Analyzer de imagem depois; Analyzer de vídeo em seguida;
- persistir prompt efetivo versionado, modelo, custo, marca, projeto e assets derivados;
- tratar sucesso parcial e reembolso/reconciliação.

Aceite: jobs sobrevivem à sessão do chat, consumo é idempotente e o asset aparece no projeto e no Turn.

### Fase 6 — Reports operacional

- upload/importação como job;
- revisão humana e estados de qualidade;
- comparação entre períodos, campanha e plano;
- insight/decisão como artifact relacionado às métricas e versões usadas;
- exportação e compartilhamento confirmados.

Aceite: nenhuma métrica não revisada vira fato e toda recomendação mantém proveniência.

### Fase 7 — abertura para agentes externos

- OAuth/OIDC, scopes, revogação e rate limit por aplicação;
- catálogo reduzido por exposure e consentimento;
- quotas separadas de UI e integrações;
- auditoria, política de retenção e documentação de compatibilidade.

Aceite: um agente externo não escolhe tenant, não amplia scopes e não executa command sem autorização vinculada.

## 11. Matriz executiva de prioridade

| Pacote | Valor | Risco | Dependência | Prioridade |
|---|---|---|---|---|
| Três runtimes + Provider Registry | Qualidade e custo por tipo de tarefa | Médio | Contrato comum | P0 |
| Leituras Planner/Reports | Respostas menos genéricas | Baixo | Proveniência | P0 |
| Link Tester agentic | Valida actions/jobs ponta a ponta | Médio | Confirmação + receipts | P0 |
| CRUD/versionamento de recursos | Gestão diária do projeto | Médio | Resource Registry | P1 |
| Studio imagem | Criação sem sair do chat | Alto | Jobs + créditos | P1 |
| Creative Analyzer | Diagnóstico visual no contexto | Alto | Upload + multimodal | P1 |
| Reports importação/exportação | Fecha ciclo plano→resultado | Alto | Revisão humana | P1 |
| Agentes externos | Escala do produto | Muito alto | OAuth + políticas maduras | P2 |

## 12. Decisões para a próxima revisão

- `cadu-operator` poderá solicitar várias actions no mesmo Turn ou apenas uma por checkpoint?
- Quais mutações do Planner podem ser draft sem confirmação?
- Qual serviço será canônico para jobs de Studio: tabelas atuais ou uma fila comum do Harness?
- Reports poderá importar automaticamente ou somente preparar upload para revisão humana?
- Quais formatos binários o Workspace deve guardar mesmo sem adapter de leitura?
- Qual retenção será aplicada a prompts efetivos, evidências e assets de provider?
- O primeiro rollout usará quais tenants piloto e quais métricas determinam promoção ou rollback?

Até essas decisões serem fechadas, nenhuma tool nova de escrita deve ser publicada para agentes externos.
