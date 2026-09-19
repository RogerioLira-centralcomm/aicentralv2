# Cadu — planejamento revisado de projetos, arquivos e indexação

Status: Fases 0–4 em execução; primeira entrega aplicada no código.

Entrega aplicada:

- UI e MCP usam `project_index_service.py` para persistir fontes indexadas;
- chunks novos recebem `resource_id` determinístico;
- o Resource Registry informa quantidade de chunks e estado de indexação;
- evidências do chat preservam `resource_id`, `source_id`, `chunk_id`, hash e
  modo de recuperação quando esses dados existem;
- o formato antigo de fontes continua compatível com históricos já gravados.
- reprocessamento de notas e arquivos pode usar fila durável com retry/backoff;
- novas notas e uploads usam a mesma fila durável quando
  `CADU_PROJECT_INDEX_ASYNC_ENABLED` está ativo, retornando `202` com o job;
- o worker `project-index-worker-once` foi registrado para processamento
  supervisionado;
- a fila é opcional até a migration `add_cadu_project_index_jobs.sql` ser
  aplicada, preservando o caminho síncrono em ambientes antigos.

## 1. Decisão arquitetural

O Cadu não precisa criar agora uma nova plataforma de indexação nem substituir
`cadu_ci_projeto_arquivos` por uma entidade genérica. A base atual já possui o
fluxo essencial de conhecimento privado por projeto:

```
Projeto Cadu
    ↓
Arquivo / nota / URL
    ↓
Extração de texto + armazenamento privado
    ↓
Chunks
    ├── busca lexical PostgreSQL
    └── embedding pgvector
    ↓
Contexto recuperado do projeto
    ↓
Conversas, Workspace e MCP
```

O planejamento revisado adota três decisões:

1. `cadu_ci_projetos` continua sendo o limite de contexto, autorização e
   cobrança.
2. `cadu_ci_projeto_arquivos` continua sendo a fonte canônica de arquivos e
   materiais indexáveis do projeto.
3. `cadu_project_resources` evolui como um registro transversal de recursos,
   não como um segundo repositório de conteúdo. Ele organiza arquivos,
   artifacts, planos, relatórios, imagens, análises e links que já existem em
   outros módulos.

Em outras palavras: o Resource Registry aponta e contextualiza; o pipeline de
indexação lê e prepara conteúdo; o Context API recupera evidências. Nenhuma
camada deve duplicar o binário, o texto extraído ou as regras do domínio de
origem.

## 2. O que já existe hoje

### Projeto como unidade de isolamento

`cadu_ci_projetos` já concentra:

- cliente/organização do projeto;
- status ativo ou arquivado;
- descrição, instruções, público, tom de voz e posicionamento;
- contadores de arquivos e conversas;
- vínculo com marcas e demais objetos do Workspace.

O filtro de `id_cliente` aparece nas consultas do projeto, fontes, chunks e
busca. Esse isolamento deve permanecer obrigatório em qualquer API nova.

### Arquivo como fonte privada

`cadu_ci_projeto_arquivos` já registra:

- nome, MIME, tamanho e caminho privado;
- texto extraído;
- estado de indexação (`pending`, `queued`, `indexing`, `completed`,
  `error`, `paused`);
- palavras e tokens processados;
- finalidade (`knowledge_source` ou `project_attachment`);
- categoria e classificação contextual;
- mensagem de erro e datas de atualização.

Os uploads nativos aceitam PDF, DOCX, TXT, CSV, Markdown, JSON e HTML. Notas
de projeto e URLs públicas também entram na mesma tabela. URLs são importadas
com extração assíncrona e cobrança específica.

### Indexação textual e híbrida

`project_sources.py` faz validação, extração e normalização. O pipeline atual
é centralizado em `project_knowledge.py`:

```
texto extraído
  → split semântico por parágrafos e headings
  → sobreposição entre chunks
  → embedding text-embedding-3-small
  → hash do conteúdo
  → gravação lexical + pgvector
```

`cadu_ci_chunks` já possui `search_vector`, `embedding`,
`embedding_model`, `content_hash`, ordem, título, metadata e tokens. A busca
do chat combina ranking lexical e vetorial, sempre limitada ao projeto e ao
cliente, com fallback lexical quando a credencial de embedding não está
disponível.

### Reprocessamento e custo

O Workspace permite baixar, reprocessar e remover fontes que pertencem ao
projeto. O MCP possui upload autorizado com token curto e idempotência por
`request_id`. Indexação e reindexação passam por cobrança de tokens e não
devem ser duplicadas em novos adapters.

### Resource Registry já iniciado

`project_resource_service.py` já materializa recursos de várias origens:

- arquivos de projeto;
- artifacts e documentos;
- planos do Planner;
- relatórios do Connect;
- imagens de documentos;
- análises do Creative Analyzer;
- links externos;
- itens do Studio.

O registro já tem ID UUID determinístico, versão, hash, localização, metadata,
status, eventos, jobs de reconciliação e relações. A tela do projeto já exibe
esse catálogo e o MCP já expõe `projects.list_resources`.

Isso significa que o conceito de recurso universal já existe em forma inicial.
O próximo passo é completar sua ligação com o pipeline de conhecimento, e não
criar uma nova tabela paralela para o mesmo arquivo.

## 3. Limites atuais que o planejamento precisa respeitar

Há duas camadas que ainda não são uma só:

```
cadu_ci_projeto_arquivos + cadu_ci_chunks
    = conteúdo indexado e consultável

cadu_project_resources
    = catálogo transversal e relações entre objetos
```

Hoje o Resource Registry conhece o arquivo e seu status, mas não é ainda o
contrato completo de conteúdo. Por exemplo:

- nem todo recurso do catálogo possui texto indexado;
- `resource_id` ainda não é usado como referência de citação nos chunks e nas
  respostas;
- recursos de artifacts, planos, relatórios, imagens e análises ainda são
  principalmente metadados no registro;
- reconciliação é materializada por job, mas algumas telas também reconciliam
  no carregamento;
- as relações automáticas existentes ainda são poucas, como duplicidade por
  hash e relação genérica entre report e media plan;
- a extração de URL continua em fluxo assíncrono legado enquanto a migração de
  jobs de indexação não cobre essa entrada; notas e uploads já não fazem os
  embeddings dentro da requisição quando a fila está ativa;
- imagens, planilhas, apresentações, áudio e vídeo ainda não possuem uma
  pipeline multimodal comum de indexação.

Esses limites definem o escopo real. Conectores externos e grafo de
conhecimento completo são fases posteriores, não o primeiro incremento.

## 4. Arquitetura-alvo revisada

```
                         CADU WORKSPACE
                              │
                    Projeto + cliente + permissões
                              │
             ┌────────────────┴────────────────┐
             │                                 │
      SOURCE INGESTION                    RESOURCE REGISTRY
  nota · upload · URL · MCP          arquivos · artifacts · planos
             │                       reports · imagens · análises
             ▼                                 │
      cadu_ci_projeto_arquivos                 │
             │                                 │
             ▼                                 ▼
       EXTRACTION / INDEXER             RESOURCE ID + metadata
       texto · chunks · hash            relações · eventos · status
             │                                 │
             └────────────────┬────────────────┘
                              ▼
                       PROJECT CONTEXT API
                    fontes · citações · recursos
                              │
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
             Workspace      Chat          MCP
```

O recurso universal não significa que todos os objetos precisam ter o mesmo
conteúdo. Ele significa que o Cadu terá uma identidade, status, localização,
proveniência e capability consistentes para cada objeto.

## 5. Contratos canônicos

### `ProjectSource`

Representa o material que pode ser armazenado e processado pelo projeto.

```
project_ref
source_id
name
mime_type
storage_locator
purpose
category
extracted_text
content_hash
indexing_status
```

Inicialmente é uma projeção de `cadu_ci_projeto_arquivos`; não deve substituir
a tabela existente.

### `ProjectResource`

Representa qualquer objeto conectado ao projeto.

```
resource_id
project_ref
source_system
source_id
resource_type
title
purpose
category
status
version
content_hash
locator
metadata
```

É a projeção já iniciada em `cadu_project_resources`. O ID deve ser usado por
citações, relações, observabilidade e MCP.

### `ContextEvidence`

É o contrato que chega ao chat ou agente.

```
resource_id
source_id
chunk_id
title
excerpt
score
retrieval_mode
version
source_updated_at
```

Toda resposta factual deve conseguir apontar para `resource_id` e, quando
vier de texto, para `chunk_id`. O agente recebe evidência; não recebe acesso
direto às tabelas.

## 6. Plano de implementação

### Fase 0 — consolidar o inventário e o contrato atual

Objetivo: tornar explícito o que já é fonte, anexo, recurso e evidência.

- documentar todas as entradas atuais: nota, upload, URL e upload MCP;
- documentar o mapeamento entre arquivo, chunk e resource;
- adicionar checks de migração para `cadu_ci_projetos`,
  `cadu_ci_projeto_arquivos`, `cadu_ci_chunks` e Resource Registry;
- medir fontes por status, categoria, formato, tamanho, chunks, erros e
  tokens;
- garantir que arquivos antigos sem texto ou embedding apareçam como
  `needs_reindex`, nunca como prontos;
- definir `resource_id` como identificador público interno para citações.

Aceite: uma fonte aberta na UI, no chat ou no MCP tem o mesmo `source_id`,
`resource_id`, status e finalidade.

### Fase 1 — uma única fachada de ingestão

Objetivo: remover a duplicação entre rotas HTTP e MCP.

- manter `project_sources.py` como camada de validação e extração;
- manter `project_knowledge.py` como camada de chunking e embeddings;
- extrair de `routes.py` e `project_source_service.py` um serviço único de
  ingestão/reindexação;
- padronizar estados, erros, hash, metadata e cobrança;
- fazer UI, URL e MCP chamarem o mesmo serviço;
- não criar um segundo processo de indexação para o Resource Registry.

Aceite: uma nova fonte criada por qualquer entrada produz a mesma sequência
de persistência e o mesmo formato de chunk.

### Fase 2 — ligar Resource Registry ao conteúdo indexado

Objetivo: fazer o registro transversal apontar para material consultável sem
duplicá-lo.

- adicionar ao recurso uma referência estável ao `source_id` quando a origem
  for `cadu_ci_projeto_arquivos`;
- expor `indexing_status`, `chunk_count`, `embedding_model`,
  `content_hash` e `last_indexed_at` como estado derivado ou metadata;
- registrar eventos `created`, `changed`, `indexed`, `index_error`, `deleted`
  e `permission_changed`;
- substituir a reconciliação apenas no carregamento por eventos após
  mutações, mantendo reconciliação manual como reparo;
- arquivar recursos que sumiram da origem sem apagar imediatamente seu
  histórico de eventos.

Aceite: o cartão de recurso informa se é indexável, indexado, somente anexo,
desatualizado ou requer adapter.

### Fase 3 — Context API e citações consistentes

Objetivo: centralizar recuperação para UI, Conversas e MCP.

- criar uma função de busca de projeto que aceite filtros por categoria,
  finalidade, tipo de recurso e status;
- manter busca híbrida em `cadu_ci_chunks` como primeira implementação;
- devolver `ContextEvidence`, em vez de strings formatadas específicas do
  chat;
- incluir resource ID, arquivo, chunk, versão e modo de recuperação;
- manter o filtro obrigatório por `client_id` e `project_ref`;
- adaptar `workspace.get_project_context` e
  `workspace.search_project_content` para consumirem essa fachada;
- fazer o chat continuar apresentando fontes legíveis, mas derivadas de
  evidências estruturadas.

Aceite: uma busca feita no chat e no MCP retorna os mesmos resultados,
respeitando apenas limites de quantidade e apresentação.

### Fase 4 — indexação durável e incremental

Objetivo: evitar que uma requisição web carregue todo o custo de indexação.

- criar jobs específicos de ingestão/indexação, separados do job de
  reconciliação do catálogo;
- persistir `queued`, `running`, `completed`, `failed`, `retry_at` e erro
  público;
- detectar conteúdo inalterado por hash antes de cobrar e gerar embeddings;
- reprocessar somente fontes alteradas ou que falharam;
- aplicar retries com limite e backoff;
- reservar e reconciliar cobrança por job idempotente;
- exibir progresso no detalhe do projeto e no MCP.

Aceite: upload, reprocessamento e reparo podem ser retomados sem duplicar
chunks, embeddings ou cobrança.

### Fase 5 — adapters de formatos e multimodalidade

Objetivo: ampliar o que já é um arquivo de projeto, preservando o mesmo
contrato de fonte e evidência.

Ordem sugerida:

1. XLSX/CSV: abas, cabeçalhos, linhas e resumo tabular;
2. PPTX: slides, títulos, notas e elementos textuais;
3. imagens: OCR, dimensões, objetos, texto visível e tags descritivas;
4. vídeo/áudio: metadados, transcrição e timestamps;
5. PDF escaneado: OCR por página com indicação de confiança.

Cada adapter deve declarar:

```
can_extract
can_index_text
can_index_visual
can_preview
requires_external_service
estimated_cost
```

O sistema deve continuar aceitando um arquivo como anexo mesmo quando ainda
não houver adapter de indexação.

Aceite: o usuário distingue `anexo aceito`, `indexado`, `indexação parcial` e
`formato ainda não suportado`, sem perder o arquivo original.

### Fase 6 — relações úteis antes de um knowledge graph completo

Objetivo: melhorar contexto usando relações verificáveis, sem inferir uma
ontologia grande cedo demais.

- manter duplicidade por hash;
- ligar fonte a artifact, plano, relatório e análise quando a origem for
  conhecida;
- registrar relações explícitas de `derived_from`, `supports`, `references`,
  `produced_by`, `approved_by` e `version_of`;
- separar relação determinística de relação sugerida por IA;
- exibir confiança e evidência da relação;
- permitir confirmar ou rejeitar sugestões no projeto.

Aceite: perguntas como “qual briefing originou este plano?” só respondem
quando houver vínculo explícito ou evidência marcada como sugestão.

### Fase 7 — conectores externos

Objetivo: trazer fontes externas para o mesmo fluxo sem acoplar o MCP a cada
API.

Só iniciar depois das fases 1 a 4 estarem estáveis. O primeiro conector deve
ser escolhido por valor e capacidade de sincronização, provavelmente Google
Drive/Workspace.

Contrato inicial:

```
connect / refresh / disconnect
list / get / search
read / download / preview
changes / sync
capabilities
```

O conector cria ou atualiza uma fonte do projeto; não grava diretamente em
chunks. O pipeline existente decide extração, hash, chunking, embedding,
status e cobrança.

Aceite: remover ou perder permissão na origem atualiza o recurso e o índice
sem apagar silenciosamente o histórico local.

## 7. MCP após a consolidação

Não expor uma ferramenta por fornecedor. O catálogo deve permanecer semântico
ao Cadu:

```
projects.list
projects.get_context
projects.list_resources
resources.get
resources.search
resources.capabilities
resources.reindex
resources.history
```

As tools atuais de Workspace e projetos podem continuar existindo como
compatibilidade. Elas devem delegar para a Context API e para o Resource
Registry, sem consultar tabelas diretamente em cada tool.

Operações de escrita continuam separadas de consultas:

- adicionar/alterar arquivo: command com idempotência;
- reindexar: job cobrável e retomável;
- compartilhar ou alterar permissão: capability do conector, com confirmação;
- mover, apagar ou arquivar: command com versão esperada e receipt.

## 8. Observabilidade mínima

### Projeto

- total de recursos;
- fontes de conhecimento, anexos e recursos sem adapter;
- indexados, pendentes, alterados e com erro;
- chunks e embeddings por fonte;
- última indexação e última mudança.

### Pipeline

- tempo de extração, chunking e embedding;
- erro por formato e adapter;
- tokens estimados e cobrados;
- retries, jobs travados e idade da fila;
- taxa de reindexação evitada por hash.

### Recuperação

- modo lexical, vetorial ou híbrido;
- resource/chunk usados na resposta;
- latência e quantidade de evidências;
- consultas sem resultado;
- feedback de relevância quando disponível.

### Conectores futuros

- estado de autenticação;
- última sincronização;
- recursos descobertos, alterados, removidos e bloqueados;
- latência, rate limit e falhas;
- perda de permissão.

## 9. O que fica fora do próximo ciclo

- substituir as tabelas atuais por uma tabela universal de conteúdo;
- criar Google Drive, Dropbox ou SharePoint antes de estabilizar a ingestão
  local;
- indexar automaticamente todo artifact, relatório ou imagem sem definir o
  adapter e a proveniência;
- criar um grafo sem relações explícitas e auditáveis;
- expor dezenas de tools específicas de fornecedores;
- tratar toda mídia como texto ou fingir que um formato sem adapter está
  indexado;
- reindexar um projeto inteiro quando apenas uma fonte mudou.

## 10. Resultado esperado

Ao final do primeiro ciclo, o Cadu terá uma arquitetura unificada sem
descartar o que já funciona:

```
Projeto Cadu
  → fontes privadas e anexos
  → pipeline único de extração e indexação
  → chunks híbridos com hash e cobrança
  → Resource Registry como catálogo transversal
  → Context API com evidências citáveis
  → Workspace, Chat e MCP usando a mesma recuperação
```

O princípio operacional passa a ser:

**O projeto autoriza. A fonte preserva. O indexador prepara. O Resource
Registry organiza. A Context API recupera. O MCP disponibiliza.**
