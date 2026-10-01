# Contrato do documento de fluxo

Fonte da verdade: `_normalize_flow_config` em `aicentralv2/cadu_connect/reports_flow.py`. O frontend replica as regras de bloqueio em `frontend/reports-v1/flowValidation.js`, e a paridade é verificada por `tests/frontend/reports-flow-validation-parity.test.cjs` e por `tests/test_reports_flow_contract.py`.

## Documento

| Campo | Tipo | Regra |
|---|---|---|
| `schema_version` | 3 | Um único formato, gravado e devolvido (`to_v3`). Documentos 1 e 2 ainda são aceitos na entrada e convertidos: campos espelhados (`data`, `position`, `source`/`target`, `*_handle`) são dobrados nos campos canônicos e caminhos `/configurar-…` viram passos planejados. Nada é gravado em formato antigo. |
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
| `forecast` | camada Previsão: em `source` `{visits, cost}`, em `conversion` `{value}`; números ≥ 0 (visitas até 1e9, custo até 1e12, valor até 1e9); vazios descartados, outros campos ignorados |
| `segment` | só em `source`: `{name, kind, description}`; `kind` em `prospeccao`, `interesses`, `palavras_chave`, `semelhante`, `remarketing`, `base`, `outro`. Cada público é uma origem própria |
| `media` | só em `source`: `objective` (`leads`, `vendas`, `trafego`, `alcance`, `engajamento`, `video`, `mensagens`, `relacionamento`), `creatives[]` (até 20: `{id, name, format, status, message?}`; formatos `imagem`, `video`, `carrossel`, `stories`, `texto`, `mensagem`; situação `rascunho`, `em_aprovacao`, `aprovado`), `setup[]` (até 20: `{id, text, done}`), `utm` (`source`, `medium`, `campaign`, `content`; letras, números, `.`, `-`, `_`) |
| `checklist` | só em `note`: até 30 itens `{text, done}`; texto até 200, itens vazios descartados |
| `title` | até 120, espaços normalizados |
| `path` | quando presente, começa com `/`, sem `?`/`#`, até 500. Um passo medido sem `path` só publica se estiver `planned` ou `in_production` |
| `status` | opcional: `planned`, `in_production`, `ready`, `live`. Sem `status`, vale `live` com endereço real e `ready` sem ele. Só `ready`/`live` com endereço real entram na medição (publicação de passos, jornada, ao vivo, monitor e ingestão) |
| `spec` | opcional, para passos planejados: `goal`, `suggested_path` (começa com `/`), `headline`, `content`, `cta`, `owner`, `due_date` (`AAAA-MM-DD`), `references`, `notes`; textos com limite por campo, chaves desconhecidas descartadas |
| `host` | opcional; precisa ser o domínio autorizado ou um subdomínio dele |
| `event_name` | `event`/`conversion`: `[A-Za-z][A-Za-z0-9_]{0,79}` |
| `x`, `y` | 0–10000 (posição livre; a etapa é semântica, não força coluna) |
| `kind` | `categoria.item` (ex.: `traffic.meta`); sempre presente; inválido volta ao padrão do tipo |
| `source` | plataforma da origem (`google`, `meta`, `organic`, `direct`…) |
| `stage` | `source`, `entry`, `exploration`, `intent`, `conversion`, `support` |
| `origin` | `manual`, `blueprint`, `probe`, `strategy` — quem criou o nó |
| outros textos | `role`, `role_source`, `pageType`, `pageTypeStatus`, `groupId`, `suggestedRole`, `pageGroup`, `discoveryPageId`, `stepId`, `event` (até 120) |
| `description` | texto livre |

## Conexão

`{id, from, to, from_port?, to_port?, variant?, label?, origin?, kind?, forecast?}`. `forecast.rate` é a taxa planejada (0–100) usada na camada Previsão; conexões que fecham ciclo são tratadas como retorno e não alimentam a previsão. As portas são `left-in`, `right-in`, `top-in` (entrada) e `right-out`, `left-out`, `bottom-out` (saída). `variant: planned` desenha a conexão tracejada, sem medição direta.

## Versões do plano (`GET|POST …/flows/<id>/plan-versions`)

- `POST {expected_revision, note?}` congela o rascunho atual em `cadu_reports_flow_plan_versions` para aprovação. Não altera `status`, `published_revision`, passos publicados nem a Super Tag. Rascunho vazio → 422; tabela ausente → 503. Publicar de novo a mesma revisão só atualiza a nota.
- `GET` devolve `{ready, versions[{revision, name, note, created_by, created_at}]}`, da mais recente para a mais antiga (até 50).
- “Ativar medição” continua sendo `POST …/publish`, com as pendências bloqueantes de sempre.

## Limpeza dos dados do Fluxos

`migrations/run_reset_reports_flows_v3.py` apaga todos os dados de fluxo (desenhos, versões, passos, sessões e eventos de fluxo, descobertas, monitor, prévias registradas) e as tags internas de fluxo que nenhuma tabela de fora do Fluxos usa. Mantém Super Tag, sites, eventos do site e chaves de importação. Por padrão só simula; para apagar: `RESET_REPORTS_FLOWS=1 python migrations/run_reset_reports_flows_v3.py --confirm`. Nunca roda no deploy.

## Plano sem site

- `POST …/flows` com `{name, plan_only: true, config}` e sem `allowed_host` cria o fluxo sem tag interna e sem instalação da Super Tag (`tag_id` e `site_id` nulos, `allowed_host` devolvido como `''`). Só aceita passos não medidos.
- O banco garante que um fluxo sem site continua `draft` (`reports_flow_plan_only_site`).
- Ações que dependem do site (explorar páginas, teste de conversão, prévias, montagem, monitor, teste, ativar medição) respondem `409 {error: 'site_required'}`.
- `POST …/flows/<id>/site {allowed_host}` conecta o site depois: valida os endereços já informados contra o domínio, cria a tag interna e liga a instalação da Super Tag. Fluxo que já tem site → 409.

## Jornada medida (`GET …/flows/<id>/journey`)

- `nodes[]`: `{id, sessions, events, entrances?, exits?, estimated_from?}`. Nós de origem recebem `sessions` pela origem da sessão (`estimated_from: 'origin'`).
- `edges[]`: `{id, from, to, sessions, rate, observation{status, sessions, rate, denominator}}`. `status` pode ser `measured`, `no_data`, `unmeasured` ou `no_origin`; “sem dados” nunca é zero.
- `origins[]`: `{platform, label, sessions}`. A plataforma vem de `utm_source` (campanha) ou do `referrer` (orgânico, social, outros sites), e sem origem conta como acesso direto (`reports_flow_metrics.origin_platform`).
- `funnel`: `{entries, conversions, rate}`.

## Teste de conversão (`POST …/flows/<id>/probe`)

Payload: `{path, mode: 'analyze'|'submit', site_kind?, form_index?, confirm_submit?}`. A análise nunca envia formulário nem captura tela. O envio exige `confirm_submit: true`, Playwright no servidor e o domínio autorizado; o limite é de 3 por dia por fluxo (`cadu_reports_flow_probe_runs`). Os nós propostos levam `origin: 'probe'`.
