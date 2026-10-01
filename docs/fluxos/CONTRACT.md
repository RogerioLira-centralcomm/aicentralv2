# Contrato do documento de fluxo

Fonte da verdade: `_normalize_flow_config` em `aicentralv2/cadu_connect/reports_flow.py`. O frontend replica as regras de bloqueio em `frontend/reports-v1/flowValidation.js`, e a paridade é verificada por `tests/frontend/reports-flow-validation-parity.test.cjs` e por `tests/test_reports_flow_contract.py`.

## Documento

| Campo | Tipo | Regra |
|---|---|---|
| `schema_version` | 1 ou 2 | v2 é projetado para v1 ao salvar (`legacy_projection`); a leitura devolve v2 (`migrate_v1_to_v2`). |
| `nodes` | lista | até 200 |
| `edges` | lista | até 300 |
| `groups` | lista | `{id, name, memberIds[], bounds{x,y,width,height}}` |
| `site_kind` | opcional | `landing` \| `institucional` \| `multipagina` \| `ecommerce`; outro valor → 400 |
| `tags` | opcional | até 12 etiquetas de texto, até 40 caracteres cada; espaços normalizados e repetidas (sem diferenciar maiúsculas) descartadas |
| `strategy_id` | opcional | estratégia de origem do plano (`flowStrategies.js`), só informativo |
| demais chaves | livre | preservadas (`viewport`, `settings`, `dismissedSuggestions`…) |

Tamanho máximo serializado: 256 KB.

## Nó

| Campo | Regra |
|---|---|
| `id` | string única, até 80 |
| `type` | `source`, `page`, `form`, `event`, `condition`, `delay`, `segment`, `conversion`, `webhook`, `whatsapp`, `error`, `note` (anotação do plano: não é medida, não conta como passo solto e não é movida por “Organizar”) |
| `checklist` | só em `note`: até 30 itens `{text, done}`; texto até 200, itens vazios descartados |
| `title` | até 120, espaços normalizados |
| `path` | quando presente, começa com `/`, sem `?`/`#`, até 500. Um passo medido sem `path` real só publica se estiver `planned` ou `in_production` |
| `status` | opcional: `planned`, `in_production`, `ready`, `live`. Sem `status`, vale `live` com endereço real e `ready` sem ele. Só `ready`/`live` com endereço real entram na medição (publicação de passos, jornada, ao vivo, monitor e ingestão) |
| `spec` | opcional, para passos planejados: `goal`, `suggested_path` (começa com `/`), `headline`, `content`, `cta`, `owner`, `due_date` (`AAAA-MM-DD`), `references`, `notes`; textos com limite por campo, chaves desconhecidas descartadas |
| `host` | opcional; precisa ser o domínio autorizado ou um subdomínio dele |
| `event_name` | `event`/`conversion`: `[A-Za-z][A-Za-z0-9_]{0,79}` |
| `x`, `y` | 0–10000 (posição livre; a etapa é semântica, não força coluna) |
| `kind` | `categoria.item` (ex.: `traffic.meta`); preservado em v1 e v2; inválido é descartado |
| `source` | plataforma da origem (`google`, `meta`, `organic`, `direct`…) |
| `stage` | `source`, `entry`, `exploration`, `intent`, `conversion`, `support` |
| `origin` | `manual`, `blueprint`, `probe`, `strategy` — quem criou o nó |
| outros textos | `role`, `role_source`, `pageType`, `pageTypeStatus`, `groupId`, `suggestedRole`, `pageGroup`, `discoveryPageId`, `stepId`, `event` (até 120) |
| `description` | texto livre |

## Conexão

`{id, from, to, from_port?, to_port?, variant?, label?, origin?, kind?}`. As portas são `left-in`, `right-in`, `top-in` (entrada) e `right-out`, `left-out`, `bottom-out` (saída). `variant: planned` desenha a conexão tracejada, sem medição direta.

## Versões do plano (`GET|POST …/flows/<id>/plan-versions`)

- `POST {expected_revision, note?}` congela o rascunho atual em `cadu_reports_flow_plan_versions` para aprovação. Não altera `status`, `published_revision`, passos publicados nem a Super Tag. Rascunho vazio → 422; tabela ausente → 503. Publicar de novo a mesma revisão só atualiza a nota.
- `GET` devolve `{ready, versions[{revision, name, note, created_by, created_at}]}`, da mais recente para a mais antiga (até 50).
- “Ativar medição” continua sendo `POST …/publish`, com as pendências bloqueantes de sempre.

## Jornada medida (`GET …/flows/<id>/journey`)

- `nodes[]`: `{id, sessions, events, entrances?, exits?, estimated_from?}`. Nós de origem recebem `sessions` pela origem da sessão (`estimated_from: 'origin'`).
- `edges[]`: `{id, from, to, sessions, rate, observation{status, sessions, rate, denominator}}`. `status` pode ser `measured`, `no_data`, `unmeasured` ou `no_origin`; “sem dados” nunca é zero.
- `origins[]`: `{platform, label, sessions}`. A plataforma vem de `utm_source` (campanha) ou do `referrer` (orgânico, social, outros sites), e sem origem conta como acesso direto (`reports_flow_metrics.origin_platform`).
- `funnel`: `{entries, conversions, rate}`.

## Teste de conversão (`POST …/flows/<id>/probe`)

Payload: `{path, mode: 'analyze'|'submit', site_kind?, form_index?, confirm_submit?}`. A análise nunca envia formulário nem captura tela. O envio exige `confirm_submit: true`, Playwright no servidor e o domínio autorizado; o limite é de 3 por dia por fluxo (`cadu_reports_flow_probe_runs`). Os nós propostos levam `origin: 'probe'`.
