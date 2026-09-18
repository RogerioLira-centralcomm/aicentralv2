# Plano de evolução do Cadu Studio

## Objetivo

Unificar criação, edição, adaptação de formatos, versões, descarte e entrega em um fluxo persistente por projeto. O usuário deve conseguir começar sem projeto, vincular depois, levar uma criação para o Trocr, finalizar um trabalho e retomá-lo sem perder a conclusão anterior.

Este plano evolui a base existente. Não cria uma segunda biblioteca ou um segundo conceito de projeto.

## O que já existe e deve ser preservado

- `cx_studio_projects` e `cx_studio_project_revisions`: projeto e revisões com controle de concorrência.
- `cx_studio_creation_runs`, `cx_studio_creation_directions` e `cx_studio_image_generations`: histórico e idempotência das gerações.
- `cx_studio_project_items`: referências, direções, imagens e vídeos do projeto.
- Mesa de criação com áreas `Mesa`, `Aprovadas` e `Retiradas`.
- Handoff da criação para o Trocr com imagem, cliente e projeto.
- Histórico do Trocr em runs, com original, base ativa, versão ativa e revisão CAS.
- Biblioteca pessoal para criações sem projeto e `deleted_at` para remoção lógica.
- Brevo e tokens visuais do produto `studio`.

## Decisões de produto

### Projeto, trabalho e sessão

- **Projeto** organiza vários trabalhos relacionados à mesma marca ou campanha.
- **Trabalho** é uma cadeia de criação e edição iniciada pelo usuário.
- **Sessão** é uma etapa editável dessa cadeia: criação, edição ou adaptação.
- Uma sessão pode existir sem projeto. Ela aparece em `Sessões livres` e pode ser vinculada depois.
- Uma sessão finalizada não volta ao estado editável. `Continuar editando` cria uma sessão filha com a peça final como base.
- Sessões filhas mantêm o mesmo `root_session_id`. Isso preserva a primeira entrega e impede e-mail duplicado na mesma cadeia de trabalho.
- Um projeto pode ter vários trabalhos independentes. Cada trabalho pode enviar um único e-mail na primeira finalização.

### Referência automática

- O editor usa como referência automática o **último resultado aceito**, não simplesmente a última geração.
- Gerar uma tentativa não troca a base silenciosamente.
- `Usar como base` atualiza `base_item_id`, registra evento e executa nova leitura/OCR.
- Pessoas, logos, produto, nomes e textos marcados como protegidos entram como invariantes do prompt derivado.
- Uma microcorreção como `trocar HORAA por HORAS` deve usar a peça aceita mais recente e escopo localizado.

### Finalização

- `Salvar` mantém a sessão aberta e nunca envia e-mail.
- `Finalizar trabalho` exige uma peça final escolhida e nenhum job pendente.
- A finalização cria um snapshot imutável, registra métricas e agenda o primeiro e-mail por `root_session_id`.
- Salvar novamente, abrir a finalização ou continuar em sessão filha não envia outro e-mail.
- Um novo trabalho independente dentro do mesmo projeto pode ter sua própria primeira finalização e seu próprio e-mail.

### Descarte e exclusão física

- `Retiradas` é uma área recuperável, não exclusão imediata.
- Finalizar marca como descartáveis as tentativas não escolhidas e referências temporárias sem uso.
- A exclusão física roda em worker após a transação e somente quando o ativo:
  - não é a peça final;
  - não é referência de sessão ativa;
  - não está ligado a outro projeto ou entrega;
  - não é necessário pelo e-mail ou por auditoria financeira;
  - ultrapassou o prazo de segurança configurado.
- Banco e storage usam `mark and sweep`: primeiro `pending_delete`, depois remoção do objeto, por último `deleted_at`.
- Falha no storage não desfaz a finalização. O worker tenta novamente com idempotência.

## Fluxo consolidado

```text
Projeto ou sessão livre
        ↓
Sessão de criação
        ↓
direções → gerações → resultado aceito
        ↓
Editar esta peça
        ↓
Sessão de edição no Trocr
        ↓
versões → comparação → peça aprovada
        ↓
Adaptar formatos (opcional, por recomposição)
        ↓
Salvar e continuar  OU  Finalizar trabalho
                              ↓
                    snapshot + métricas + e-mail único
                              ↓
                    Continuar em nova sessão filha
```

## Estados

### Sessão

`draft → active → ready → finalizing → finalized → archived`

Estados excepcionais: `failed` e `cancelled`.

- `draft`: criada, ainda sem operação útil.
- `active`: contém referências, prompts, gerações ou edições.
- `ready`: existe resultado selecionado e elegível para finalizar.
- `finalizing`: snapshot e eventos sendo gravados.
- `finalized`: snapshot concluído; sessão somente leitura.
- `archived`: removida da lista principal, mas preservada.

### Ativo

`working → accepted → final | discarded → pending_delete → deleted`

Uma peça final nunca entra em `pending_delete` automaticamente.

## Persistência SQL

### 1. Sessões

Criar `cx_studio_sessions`:

```sql
id UUID PRIMARY KEY
root_session_id UUID NOT NULL
parent_session_id UUID NULL
project_id UUID NULL
client_id INTEGER NOT NULL
user_id INTEGER NOT NULL
studio_type VARCHAR(24) -- create, edit, adapt
status VARCHAR(24)
title VARCHAR(160)
revision INTEGER NOT NULL DEFAULT 1
active_item_id UUID NULL
base_item_id UUID NULL
original_prompt TEXT
optimized_prompt TEXT
prompt_language VARCHAR(16)
prompt_version VARCHAR(40)
metadata JSONB
started_at TIMESTAMPTZ
finalized_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

Regras:

- `project_id` é opcional para sessões livres.
- toda consulta usa `client_id` e, quando livre, `user_id`;
- `revision` implementa CAS e evita sobrescrever outra aba;
- `root_session_id = id` na sessão raiz;
- sessão finalizada rejeita PATCH de conteúdo.

### 2. Ativos e relação sessão–ativo

Criar `cx_studio_assets` como catálogo canônico independente de projeto. Isso é necessário porque uma sessão livre também precisa de lineage, status e limpeza segura. `cx_studio_project_items` continua como vínculo e feed do projeto durante a migração, com `asset_id` opcional apontando para o ativo canônico.

O ativo guarda proprietário, projeto opcional, URL, chave de storage, origem, status e metadados. Vincular uma sessão livre a um projeto atualiza o vínculo; não duplica o binário.

Criar `cx_studio_session_items` em vez de duplicar ativos:

```sql
session_id UUID NOT NULL
item_id UUID NOT NULL
role VARCHAR(24) -- reference, base, attempt, accepted, final, discard
position INTEGER
created_at TIMESTAMPTZ
PRIMARY KEY (session_id, item_id, role)
```

`cx_studio_project_items` continua sendo o catálogo do ativo. A nova tabela registra o papel do ativo em cada sessão.

### 3. Eventos

Criar `cx_studio_session_events`:

```sql
id BIGSERIAL PRIMARY KEY
session_id UUID NOT NULL
event_type VARCHAR(48) NOT NULL
request_id VARCHAR(160) NULL
payload JSONB NOT NULL DEFAULT '{}'
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

Índice único parcial em `(session_id, request_id, event_type)` quando `request_id` existir. Eventos mínimos:

- `session_started`
- `prompt_submitted`
- `prompt_optimized`
- `generation_started`
- `generation_completed`
- `generation_failed`
- `asset_accepted`
- `base_changed`
- `edit_completed`
- `format_created`
- `handoff_created`
- `saved`
- `finalization_requested`
- `finalized`
- `email_queued`
- `email_sent`
- `trash_marked`
- `asset_deleted`

### 4. Finalizações

Criar `cx_studio_finalizations`:

```sql
id UUID PRIMARY KEY
session_id UUID NOT NULL UNIQUE
root_session_id UUID NOT NULL
final_item_id UUID NOT NULL
snapshot JSONB NOT NULL
generation_count INTEGER NOT NULL
edit_count INTEGER NOT NULL
format_count INTEGER NOT NULL
handoff_count INTEGER NOT NULL
active_seconds INTEGER NOT NULL
estimated_minutes_saved INTEGER NOT NULL
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

O snapshot guarda URLs, dimensões, prompt aprovado, contexto de marca, créditos e versão de origem. Não guarda binário.

### 5. E-mail por outbox

Criar `cx_studio_delivery_outbox`:

```sql
id UUID PRIMARY KEY
root_session_id UUID NOT NULL
finalization_id UUID NOT NULL
recipient_email VARCHAR(320) NOT NULL
kind VARCHAR(40) NOT NULL DEFAULT 'first_finalization'
status VARCHAR(24) NOT NULL DEFAULT 'pending'
attempts INTEGER NOT NULL DEFAULT 0
provider_message_id VARCHAR(180)
last_error TEXT
available_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
sent_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
UNIQUE (root_session_id, kind)
```

A finalização e a criação da outbox acontecem na mesma transação. O envio Brevo ocorre fora da requisição e pode ser repetido com segurança.

### 6. Fila de exclusão

Criar `cx_studio_asset_deletions`:

```sql
id BIGSERIAL PRIMARY KEY
item_id UUID NOT NULL UNIQUE
storage_key TEXT NOT NULL
status VARCHAR(24) NOT NULL DEFAULT 'pending'
attempts INTEGER NOT NULL DEFAULT 0
available_at TIMESTAMPTZ NOT NULL
deleted_at TIMESTAMPTZ NULL
last_error TEXT
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

## APIs

Manter as rotas existentes e acrescentar contratos pequenos:

- `POST /studio/sessions` — cria sessão livre ou vinculada.
- `GET /studio/sessions?project_id=&status=` — lista sessões.
- `GET /studio/sessions/<id>` — abre sessão e seus itens.
- `PATCH /studio/sessions/<id>` — autosave com `expected_revision`.
- `POST /studio/sessions/<id>/accept` — escolhe resultado e base.
- `POST /studio/sessions/<id>/handoff` — cria sessão filha no editor de destino.
- `POST /studio/sessions/<id>/continue` — deriva sessão editável de uma finalizada.
- `POST /studio/sessions/<id>/finalize` — finalização idempotente.
- `POST /studio/sessions/<id>/discard` — marca itens retirados.
- `POST /studio/sessions/<id>/restore` — restaura item ainda não apagado.

Todas as mutações recebem `request_id`; save recebe `expected_revision`. O backend resolve escopo por sessão autenticada, nunca apenas pelo `client_id` enviado no navegador.

## Prompt e corretor

### Pipeline

1. Guardar o pedido original exatamente como digitado.
2. Detectar idioma no servidor.
3. Classificar intenção: criar, editar, corrigir texto, remover, recompor ou variar.
4. Extrair invariantes: pessoas, nomes, logo, produto, texto protegido e formato.
5. Produzir prompt técnico derivado em inglês quando o modelo responder melhor em inglês.
6. Manter entre aspas e no idioma original todo texto que deve aparecer na peça.
7. Gravar versão do corretor e hash dos insumos.
8. Mostrar no editor `Pedido original` e `Instrução otimizada`, com opção de editar ou restaurar.

O prompt derivado é dado de execução, não substitui a intenção do usuário. Conteúdo vindo de imagem, documento ou referência entra como evidência, nunca como instrução de sistema.

### Refinamento automático por contexto

- Criação: cena, público, objetivo, composição, proporção e identidade.
- Edição: mudança pedida + invariantes explícitas + base aceita.
- Correção de texto: caixa localizada, texto atual, texto exato de destino e `change only`.
- Formatos: recomposição P0–P3; nunca resize cego.

## Métricas e tempo economizado

Não inferir a economia apenas pela quantidade de cliques. Calcular com eventos e uma tabela de baselines versionada:

```text
manual_estimate =
  creation_baseline
  + edit_baseline × edições concluídas
  + format_baseline × formatos concluídos

saved_minutes = max(0, manual_estimate - active_minutes)
```

`active_minutes` soma intervalos de interação e limita períodos ociosos. O e-mail mostra `estimativa`, a regra utilizada e números auditáveis:

- gerações concluídas;
- edições concluídas;
- formatos produzidos;
- idas entre criação e edição;
- versões preservadas;
- créditos consumidos;
- duração ativa;
- estimativa conservadora de economia.

Não usar `tentativas com falha` como produtividade positiva.

## E-mail de primeira finalização

- Fundo escuro do Studio, sem preto absoluto.
- Logo central.
- Peça final em foco, cantos arredondados e `alt` descritivo.
- Resumo do projeto e da sessão.
- Métricas e estimativa de tempo economizado.
- CTA com URL autenticada para abrir o projeto.
- Fallback textual quando o cliente de e-mail bloquear a imagem.
- Asset privado não deve ser exposto por URL permanente pública. Usar publicação autorizada ou URL assinada compatível com a validade do e-mail.
- Se o destinatário não tiver acesso ao projeto, o CTA leva ao login e valida autorização após autenticação.

O e-mail é enviado uma única vez por `root_session_id`. Falha de e-mail não muda a sessão de `finalized` para erro.

## UX compartilhada

O Trocr continua sendo a referência de densidade e comportamento. Criação, edição e adaptação compartilham o mesmo shell, mas mantêm ferramentas próprias.

```text
┌ projeto / sessão ─ status ─ salvar ─ finalizar ┐
├ sessões e versões ┬ palco/canvas ┬ instruções  ┤
│ referências       │ peça ativa   │ prompt      │
│ tentativas        │ comparação   │ invariantes │
│ retiradas         │              │ formato     │
├───────────────────┴──────────────┴─────────────┤
│ créditos · operações · base ativa · jobs       │
└─────────────────────────────────────────────────┘
```

### Tema escuro

O Studio é sempre escuro, inspirado na clareza e contraste do ChatGPT, sem virar uma superfície totalmente preta:

| Token | Cor | Uso |
|---|---:|---|
| `studio-canvas` | `#212121` | fundo principal |
| `studio-panel` | `#2F2F2F` | painéis laterais |
| `studio-raised` | `#383838` | controles e superfícies elevadas |
| `studio-border` | `#4A4A4A` | divisores e foco estrutural |
| `studio-text` | `#ECECEC` | texto principal |
| `studio-muted` | `#B4B4B4` | texto secundário |
| `studio-accent` | `#7456E8` | ação principal do Studio |
| `studio-focus` | `#B7AAFF` | foco de teclado |
| `studio-success` | `#49A66D` | salvo/finalizado |
| `studio-danger` | `#E57373` | exclusão e falha |

Regras:

- nenhum painel usa `#000` como fundo;
- o canvas da peça pode usar checkerboard ou moldura neutra;
- uma única ação primária por contexto;
- `Salvar e continuar` e `Finalizar trabalho` nunca têm o mesmo peso;
- foco de teclado visível e contraste mínimo de 4.5:1;
- evitar cartões arredondados em toda parte; bordas e agrupamentos só quando expressarem estrutura;
- movimento apenas para confirmar ações e mudança de estado.

## Fases de implementação

### Fase 0 — Contratos e proteção da base

Entregas:

- registrar schemas de sessão, evento, finalização, outbox e deleção;
- feature flag por conta;
- congelar contratos atuais de criação, Trocr, projetos e biblioteca com testes;
- definir enumerações e transições válidas em um módulo único;
- definir política de retenção e baselines de tempo em configuração versionada.

QA antes do commit:

- testes de contrato das rotas existentes;
- teste de escopo por conta e usuário;
- teste de idempotência de geração já existente;
- `python -m compileall` dos módulos alterados;
- nenhuma alteração visual.

### Fase 1 — Banco e repositórios

Entregas:

- migrations idempotentes;
- repositórios de sessão, evento, finalização, outbox e deleção;
- backfill: cada projeto continua válido sem sessão; sessões nascem sob demanda;
- índices por `client_id`, `project_id`, `root_session_id`, status e atualização;
- CAS de sessão.

QA backend antes do commit:

- migration em banco vazio e banco com dados;
- reaplicação da migration sem erro;
- constraints de tenant, status e unicidade;
- conflito de revisão retorna 409 e preserva a edição do cliente;
- sessão livre não aparece para outro usuário;
- projeto excluído trata sessões conforme a FK definida.

QA frontend antes do commit:

- contratos JSON simulados aceitos pelo código atual;
- tratamento de 409, 404 e sessão expirada por DOM/teste unitário;
- `node --check` em cada JavaScript alterado.

### Fase 2 — Ciclo de sessão e autosave

Entregas:

- criar/listar/abrir/salvar/arquivar sessões;
- organização por projeto e `Sessões livres`;
- autosave com debounce e revisão;
- recuperação de rascunho após reload;
- sessão finalizada somente leitura;
- `Continuar editando` cria filha.

QA backend:

- máquina de estados rejeita transições inválidas;
- saves concorrentes não sobrescrevem dados;
- continuação herda `root_session_id`, base e projeto;
- sessão livre pode ser vinculada sem mudar propriedade dos ativos.

QA frontend:

- criar sessão, trocar sessão e recarregar preserva estado;
- dirty state impede navegação silenciosa;
- autosave mostra `salvando`, `salvo` e erro acionável;
- navegação por teclado e atributos ARIA testados pelo DOM.

### Fase 3 — Criação e prompt derivado

Entregas:

- sessão criada automaticamente na primeira ação útil;
- original, idioma, prompt derivado e versão do corretor persistidos;
- resultado escolhido vira `accepted` e base padrão;
- referências e invariantes estruturadas;
- `Retiradas` vinculada à sessão, não só ao estado local.

QA backend:

- texto literal em português permanece literal no prompt inglês;
- nomes, logos e identidades protegidos não são traduzidos;
- retries com mesmo `request_id` não cobram nem geram duas vezes;
- resultado não escolhido não vira base.

QA frontend:

- exibição de original/otimizado sem substituir silenciosamente;
- aceitar, retirar, restaurar e usar como base atualizam o DOM e a API;
- falha do corretor permite gerar com o original;
- estado de loading não permite duplo envio.

### Fase 4 — Handoff para o Trocr e formatos

Entregas:

- handoff persistente cria sessão filha `edit`;
- Trocr recebe item, contexto, invariantes, prompt e lineage;
- `Usar como base` persiste no servidor;
- adaptação de formato cria sessão `adapt` e recompõe P0–P3;
- nenhuma passagem depende apenas de `sessionStorage`.

QA backend:

- handoff é idempotente;
- ativo pertence à conta e é acessível ao usuário;
- lineage criação → edição → formato é consultável;
- formato não altera a peça fonte;
- URLs privadas não atravessam escopos.

QA frontend:

- abrir editor após criação carrega a base correta;
- back/refresh não perde handoff;
- versão visualizada e base de edição permanecem distintas;
- `Continuar no editor` cria sessão uma única vez.

### Fase 5 — Finalização, e-mail e descarte

Entregas:

- pré-validação e endpoint idempotente de finalização;
- snapshot imutável;
- contagem de operações e economia estimada;
- outbox Brevo;
- e-mail escuro do Studio;
- mark-and-sweep dos descartes;
- reprocessamento de e-mail e deleção em worker.

QA backend:

- não finaliza sem item aceito ou com job pendente;
- chamadas repetidas devolvem a mesma finalização;
- constraint garante um e-mail por `root_session_id`;
- falha Brevo mantém finalização pronta e reprograma a outbox;
- limpeza nunca remove final, base ativa ou ativo compartilhado;
- auditoria de créditos permanece após apagar o binário descartado;
- links do e-mail exigem autorização.

QA frontend:

- modal de finalização informa exatamente o que será preservado e limpo;
- botão bloqueia durante request e não duplica evento;
- sucesso muda sessão para somente leitura;
- `Salvar` não chama endpoint de e-mail;
- `Continuar editando` abre filha e mantém a original concluída.

### Fase 6 — Equalização dos editores

Entregas:

- shell compartilhado;
- tokens escuros comuns;
- cabeçalho, status, histórico, créditos e barra de conclusão comuns;
- ferramentas específicas continuam separadas;
- migração progressiva da criação e Trocr sem reescrever os motores.

QA de código frontend:

- testes de componentes por DOM e eventos;
- contraste validado por cálculo de tokens, sem screenshot;
- ordem de tabulação, foco, atalhos e `aria-live`;
- estados vazio, erro, processando, pronto e finalizado;
- mobile validado por regras de layout e DOM, sem aprovação visual.

QA backend:

- nenhum contrato de geração, crédito, projeto ou histórico regressa;
- feature flag desativada mantém comportamento anterior.

### Fase 7 — Migração, observabilidade e remoção do legado

Entregas:

- telemetria de falha por etapa;
- reconciliação de eventos pendentes;
- importação opcional de runs do Trocr para sessões;
- métricas de finalização, retomada, e-mail e limpeza;
- remoção de caminhos legados somente após período de estabilidade.

QA final antes do commit de encerramento:

- suíte Studio/Trocr completa;
- testes frontend Node/Playwright em modo headless, apenas comportamento e DOM;
- build de CSS/JS;
- verificação de migration e consultas principais;
- teste de autorização cruzada;
- teste de retry/idempotência;
- teste de worker reiniciado no meio de e-mail e limpeza;
- revisão de diff para segredos, URLs públicas, logs com prompts ou dados pessoais;
- `git diff --check`;
- commit somente com todos os gates verdes.

## Política de QA e commits

- Um commit por fase concluída.
- Nenhum commit automático antes do QA backend e frontend da fase.
- Não usar screenshot, comparação visual ou aprovação manual de pixels como gate.
- Playwright pode ser usado somente para comportamento, acessibilidade e estado do DOM.
- Não chamar provedores reais nos testes; usar fakes determinísticos.
- E-mail validado por contrato HTML, escaping, links, idempotência e payload Brevo.
- Migrations validadas com dados anteriores e reaplicação.
- Testes de segurança e tenant são obrigatórios em todas as novas rotas.

Comandos-base por fase, ajustados aos arquivos tocados:

```bash
python -m pytest -q tests/test_studio_projects.py tests/test_studio_create.py tests/test_studio_creation_history_schema.py tests/test_trocr_session.py tests/test_trocr_workspace.py
node --test tests/frontend/trocr-new-piece.test.cjs
node --test tests/frontend/mc-studio-library.test.cjs
node --test tests/frontend/mc-studio-workflow.test.cjs
npm run build:studio
git diff --check
```

## Critérios de conclusão do programa

- Todo trabalho pertence a uma sessão persistida.
- Sessão livre pode virar sessão de projeto sem perder histórico.
- A última peça aceita é a base automática da próxima edição.
- Criação abre edição com lineage e contexto completos.
- Formatos são recompostos e ficam ligados à peça fonte.
- Finalização é idempotente, imutável e não depende do e-mail.
- Cada cadeia de trabalho envia no máximo um e-mail de primeira finalização.
- Salvar e continuar nunca envia e-mail.
- Descartes são recuperáveis antes da limpeza e apagados fisicamente com segurança.
- Métricas e tempo economizado são reproduzíveis a partir dos eventos.
- Criação e Trocr usam o mesmo shell escuro, com funções próprias.
- Todos os gates de backend e frontend passam antes de cada commit.
