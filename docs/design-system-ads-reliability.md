# Design System Ads — confiabilidade

Diagnóstico do código em produção e plano de incrementos. Complementa [`design-system-ads.md`](design-system-ads.md); em conflito, vale o símbolo citado aqui.

Não existe `AGENTS.md` no repositório. Pydantic 2 (`>=2.9,<3`). 409 já mapeia `CreativeConflictError`.

## Fluxo atual real

```text
mesa (mc-design-system.js)
  → /parametros/api/design-system/brand|campaign/*
  → CreativeModelingService
  → leitura: brand_profile.design_system_ads (canônica; CAS)
             GET: se o profile estiver vazio, mostra a projeção com revision=0
  → materialize / loop / compose / patch / approve / adapt
  → escrita: brand_profile + upsert cx_brand_visual_systems
  → specimen: /lab/design-system/marca|campanha → render_specimen
```

Campanha: `GET` devolve o stored se existir. `POST` (antes deste incremento) reherdava a marca atual e gravava por cima.

## Persistência

| superfície | papel |
|---|---|
| `cx_clients.brand_profile.design_system_ads` | **canônica na leitura** (`_stored_brand_design_system`) |
| `cx_brand_visual_systems.tokens` | projeção; GET órfã avisa; CAS nunca lê |
| `cx_campaigns.creative_brief.design_system_ads` | canônica da campanha |

`version` **não** é revisão do documento: `_append_pass` faz `version = max(1, version)`.

`revision` é o número do documento no JSON. Legado sem campo = 0. Cada persistência bem-sucedida grava `revision + 1` (0→1). CAS: `jsonb_set` no path `design_system_ads` com `WHERE design_system_ads_revision = :expected RETURNING` nas tabelas canônicas (coluna gerada do JSON). Probes e tabelas sem a coluna usam o path JSONB. 0 linhas e o cliente/campanha existe → `CreativeConflictError` → 409. Sem tabela de histórico.

Aprovação, patch e refine com `intent` exigem `expected_revision`. Loop, compose, refine sem intent, track, adapt e montar campanha aceitam o número da mesa; sem número, usam `stored_at_start`. Adapt com o mesmo arquétipo e `POST` da marca já existente não sobem `revision`.

Review (`review_fidelity`), `_review_tokens` (refine), compose de campanha e trilhas usam `prompt_context`. Nenhum recebe HTML nem screenshot do specimen.

P0–P3: `components.COMPONENTS`. Adapter já estaciona por densidade. Não inventar omissão nova.

## Tokens derivados

`DesignSystemAds._compile` preenche tokens ausentes, depois `css_vars`, `tailwind`, `contrast`, `backgrounds`, `rules`, `tracks`, `ad_copy`.

Antes deste incremento, o default de ink/highlight/fonte era a tinta CentralComm (`#1E4D4F`, `#F3B71B`, Inter) para qualquer payload incompleto.

## Problemas confirmados

| problema | arquivo / símbolo |
|---|---|
| Default teal/ouro/Inter em qualquer parse incompleto | **fechado:** `_compile` usa ink `#111111` e `ui-sans-serif` fora da casa; Inter só no preset |
| `muted` da casa na materialização | **fechado:** `NEUTRAL_MUTED` `#4B5563` |
| Fonte Inter se o extract não trouxer heading | **fechado:** `ingest._typefaces` não inventa Inter |
| Preview do catálogo cai em teal/Inter | **fechado:** preview usa `TYPE_STACK_FALLBACK`, ink `#111111` |
| Seed local + review sem modelo marcam `evidence.reviewed` | `refine.seed_local_compose`, `fidelity.mark_reviewed`, `catalog.inspect_loop` |
| POST da campanha reherda tokens da marca atual | `campaign.ensure_campaign_design_system` + `CreativeModelingService.ensure_campaign_design_system` |
| Sem política central do que a campanha pode mudar | `refine.apply_campaign_compose` |
| Body JSON solto nas rotas (não copiado inteiro, mas sem schema) | `api_patch_brand_design_system` |

## Hipóteses não comprovadas

- Consumidores externos do JSON além da mesa e `build_brand_context`.
- Jobs assíncronos de DS Ads (hoje o loop/trilha são request Flask).
- Checksum de asset no storage.
- Exportação além do specimen HTML.

## Skills e satélites

Os cinco Markdown em `.agents/skills/design-system-ads/` são orientação do agente. O runtime **não** os lê. Regras executáveis: `runtime_policy.py`. Contexto de prompt: `prompt_context.py` — **compose, refine, review, campaign e tracks** migrados. A proteção de campos (`filter_identity_patches` / `lock_campaign_tokens`) vale em qualquer tarefa. Preset CentralComm só com `resolve_preset_context` em `no_client` ou `house_client`. `ADS.PRESET.CENTRALCOMM.NO_CLIENT` no prompt é **elegibilidade** (o preset não cabe); o conteúdo do satélite `centralcomm-ads.md` não é carregado. `role: data` no JSON **não** é fronteira de segurança.

## Incrementos

1. **Feito.** Proveniência, fallback observável, herança protegida, comandos, sanitize, UI de aviso, testes I1/I4/I9.
2. **Feito.** `revision` + CAS; coluna gerada; fila coalescida; Playwright de duas abas (skip sem Chromium); projeção órfã avisada e CAS só no profile.
3. **Feito.** Política runtime no compose/refine + fingerprint SHA-256 + `ValidationReport` + formatos `ok|stale|unchecked`. Adapt só marca stale.
4. **Feito.** Validador de render opt-in (`POST …/validate-render` ou `DSA_RENDER_VALIDATE=1`). Sem browser: `render=skipped`. Loop não chama.
5. **Feito.** `ad_copy_by_format` + `needs_input`; loop não gera trilha se faltar produto (exceto CentralComm).
6. **Feito.** Lista derivada de pendências por formato (`ok|stale|needs_input|missing_track|needs_confirm`). Sem job.
7. **Feito.** Playwright de duas abas: aprovar numa, patch na outra → 409 “A marca mudou. Recarregue.” e a mesa recarrega sem adaptar. Skip sem Chromium. Distinto do render do incremento 4.
8. **Feito.** Trilhas no `prompt_context`. Projeção órfã: aviso na mesa, CAS só no profile, **Montar a marca** promove.

### Bordas do incremento 2

| borda | estado | pendência |
|---|---|---|
| JSONB | CAS e persistência Ads gravam só `{design_system_ads}`. Vizinhos (`trocr`, `creative_line`, `brand_summary`) usam `jsonb \|\|` sem essa chave. | Provar em CI com `CX_TEST_DATABASE_URL` se o job não tiver Postgres. |
| Projeção | `upsert_design_system_ads` depois do CAS. Canônico = `brand_profile.design_system_ads`. Revisão atrasada não sobrescreve. Falha do upsert não reabre o CAS. | GET órfã avisa e manda `revision=0`. **Montar a marca** promove a projeção. CAS nunca lê a projeção. |
| Fila mesma aba | Dois patches rápidos **coalescem**. Dois `writeJson` já enfileirados na mesma revisão: o segundo é **descartado** após o sucesso do primeiro, com “O ajuste anterior foi gravado…”. Não reetiqueta payload antigo. 409 continua “A marca mudou.” | Playwright de duas abas cobre o 409 da outra aba. |
| Identidade | `apply_compose` trava por status/proveniência (`approved`, `confirmed`, `inferred`). Sem blacklist de hex/fonte. Rascunho `fallback`/`unknown` ainda propõe. | Compose, refine, review, campaign e tracks usam `prompt_context`. |

### Evidência de testes (não misturar)

| classe | o que prova | o que **não** prova |
|---|---|---|
| **Unitários** | `DesignSystemAdsRevisionTest`, `ConcurrencyTest` (FakeRepo), `IdentityProvenanceTest`, `projection_is_stale`, `ValidationTest` (fingerprint/stale), `RenderValidationTest` (métricas / skip) | Concorrência real de banco; fila do browser; duas abas |
| **Integração PostgreSQL** | `tests/test_design_system_ads_postgres.py` — duas conexões, vizinho + Ads; skip sem Postgres | Não corre em suite sem DSN |
| **JavaScript real** | `tests/js/mc_dsa_write_queue_test.js` via Node no módulo da mesa | Event loop do browser / duas abas |
| **OpenRouter mockado** | `DesignSystemAdsRuntimeComposeTest`, `RuntimeRefineTest` | Chamada real ao provedor |
| **Playwright (opt-in)** | Billboard CentralComm no Chromium; duas abas da mesa (aprovar / patch → 409 + recarga). Skip sem Playwright | CI sem browser |

Inspeção textual de `.js` / SQL **não** declara concorrência de banco nem fila do navegador.

### Endpoints mutáveis (revisão)

| endpoint | expected | ausente | CAS usa | captura | o que o body pode mudar |
|---|---|---|---|---|---|
| `POST .../tokens` | obrigatório | 400 | número do operador | no parse do comando | tokens, copy, DNA, arquétipo |
| `POST .../approve` | obrigatório | 400 | número do operador | no parse do comando | só `status` |
| `POST .../refine` com `intent` | obrigatório | 400 | número do operador | no parse do comando | ajuste local do catálogo (estado da tela) |
| `POST .../refine` sem `intent` | opcional | `stored_at_start` | pin do início | após `get_client`, antes do LLM | patches do refine, já filtrados |
| `POST .../loop` | opcional | `stored_at_start` | pin do início | após `get_client`, antes do loop | DNA/copy/tokens do passo |
| `POST .../compose` | opcional | `stored_at_start` | pin do início | após `get_client`, antes do LLM | resposta do compose, já filtrada |
| `POST .../tracks/<id>` | opcional | `stored_at_start` | pin do início | após `get_client`, antes da imagem | URL da trilha; se 409, não vira artefato |
| `POST .../adapt` | opcional | `stored_at_start` | pin só se o arquétipo mudou | antes do persist | arquétipo/fundo |
| `POST .../brand` | opcional | `stored_at_start` | pin só na 1ª materialização | se não existe stored | rascunho novo; existente não grava |
| `POST .../campaign` | opcional | `stored_at_start` | pin da campanha | após ler brief, antes do compose | copy/linha; herança da marca fica no snapshot |

`stored_at_start` fica só nos comandos que operam de propósito sobre o estado stored no início do request. Intent de refine é edição da tela: sem `expected_revision` não passa.

## Incremento 1 — o que mudou

- `evidence.provenance`: compose_mode, review.kind, fields[], needs_confirmation.
- Legado sem bloco → `unknown`. Preset CentralComm → `confirmed`. Inferência (cor/extract) → `inferred`. Default de compile → `fallback`.
- Defaults de compile **não-CentralComm**: ink `#111111`, highlight = ink. Teal/ouro só no preset da casa.
- Cliente/LLM não persistem `status`, `reviewed`, `provenance.confirmed`.
- Campanha stored não reherda tinta no remount. Compose só mutáveis.
- Review local ≠ review de modelo. `local_seed` visível na mesa.
- Banner distingue fallback, inferida, legado unknown e confirmada. Não mistura tudo em “Preview com fallback”.
- Console do processo é coluna da mesa: hop, modelo, tempo, tokens e um resultado. Dump do LLM só ao abrir a linha.

## Incremento 2 — o que mudou

- Campo `revision` no JSON (`DesignSystemAds.revision`). `version` continua sendo passes.
- Persistência Ads: `jsonb_set(..., '{design_system_ads}', …)` com `WHERE design_system_ads_revision = :expected` em `cx_clients` / `cx_campaigns`. A coluna é gerada do JSON; o documento continua canônico. Não substitui `brand_profile` / `creative_brief` inteiros.
- Outros fluxos (`update_client_brand_profile`, bancada) mesclam vizinhos com `jsonb || (payload - 'design_system_ads')`.
- `upsert_design_system_ads` é projeção de `cx_brand_visual_systems` **depois** do CAS. Canônico na leitura: `brand_profile`. Upsert atrasado ou falho não regride o canônico.
- 409: “A marca mudou. Recarregue.” / “A campanha mudou. Recarregue.” Sem retry cego.
- `ApproveBrandCommand`, `PatchBrandCommand` e refine com `intent` exigem `expected_revision`. Sem número → 400.
- I8: `heal_contrast` não altera `status=approved`, salvo `force=True` (intent `contrast` no catálogo).
- Mesa coalescia patches da mesma aba. Job velho depois do sucesso local: “O ajuste anterior foi gravado. Este pedido usava o estado antigo e não foi reenviado.” Não reetiqueta o payload. 409 / outra aba: “A marca mudou.”
- 409 incrementa `writeEpoch`, cancela patch pendente e recarrega sem adaptar.
- Loop/trilha/campanha pinam a revisão **antes** da chamada externa. Persist nunca relê stored para escolher o expected. 409 não publica o artefato gerado.
- Campanha guarda `inherits_brand_revision` no snapshot da marca usada na geração. Remount não puxa a revisão nova da marca.
- Abrir a mesa ou o mesmo arquétipo não incrementa `revision`. Troca de arquétipo grava.
- CAS atômico na coluna gerada (tabelas canônicas) ou no path JSONB (probes). Sem transação aberta durante OpenRouter.

## Identidade no compose / refine

- LLM não muda token de identidade se `status=approved` ou proveniência `confirmed`/`inferred`.
- Qualquer valor é recusado nesse caso — não só teal/Inter.
- Teal/Inter já aprovados numa marca permanecem.
- Rascunho com `fallback`/`unknown` ainda aceita proposta de identidade.
- `role: data` no JSON do usuário não autoriza patch.

## Incremento 3 — o que mudou

- `design_system_ads/validate.py`: SHA-256 estável de tinta protegida, DNA, copy, URLs de trilha e `revision`. Sem HTML, sem `run`.
- `ValidationReport`: `passed`, `score`, `defects[]`, `notes[]`, `fingerprint`, `checked_formats[]`, `formats`, `render=skipped`. Não é o `DesignSystemPass`.
- Persistência grava só o resumo (`evidence.validation.fingerprint` + `formats`). Defeitos ficam na resposta.
- Formatos IAB/sociais: `ok | stale | unchecked`. Mudou tinta, copy, trilha ou `revision` → hash muda → formatos `stale`.
- Adapt não revalida sozinho; se o contrato divergiu, só marca stale.
- Console: uma linha `validação` com digest curto e quantos formatos ficaram stale. Sem dump do hash.
- `payload_for` expõe `fingerprint`, `fingerprint_short` e `validation`. Catálogo IAB ganha `valid`.

## Incremento 4 — o que mudou

- `design_system_ads/validate_render.py`: contraste do CTA no specimen, P0 visíveis no retângulo, legal não cortado, frame ≈ formato.
- Métricas puras são testáveis sem browser. Playwright reusa `_browser_instance` de `creative_html_compose.py`.
- Opt-in: `POST /parametros/api/design-system/brand|campaign/<id>/validate-render` ou `DSA_RENDER_VALIDATE=1`. Default `render=skipped`. Sem custo de imagem.
- Loop, compose e adapt **não** chamam o render. A mesa tem “Conferir peça”; o console ganha hop `render`.
- O resultado entra no `ValidationReport.render` (`skipped|passed|failed`) da resposta. Não grava o documento (não sobe `revision`).
- Migration `add_design_system_ads_revision.sql`: coluna gerada `design_system_ads_revision` em marca e campanha.

## Incremento 5 — o que mudou

- `ad_copy` continua o default da marca. `ad_copy_by_format` só o que muda (headline/support/cta no compacto).
- Adapt resolve default + override + corte da densidade. `320×50` encurta sem gravar o default.
- Compose lista campos bloqueados e pede `needs_input[]` se faltar DNA, produto ou legal. Não inventa.
- Loop: se `needs_input` e não for CentralComm, não gera trilha. Console e faixa `mcDsaNeedsInput`.
- Campanha herda variantes da marca e só mantém o que ainda difere do default da oferta.

## Incremento 6 — o que mudou

- `design_system_ads/pendencies.py`: lista derivada da proveniência, do fingerprint e do `needs_input`. Render só entra se já rodou e falhou.
- Prioridade por formato: `needs_input` → `stale` / specimen falhou → `missing_track` (casa isenta) → `needs_confirm`. `unchecked` não entra na lista.
- `payload_for` anexa `pendencies` e `iab_formats[].pending`. Console não duplica: processo = o que correu; pendências = o que falta.
- Mesa: bloco **Pendências** no catálogo, antes do IAB. Clique no formato reabre o palco.

## Incremento 7 — o que mudou

- 409 da outra aba mostra `A marca mudou. Recarregue.` (`error.message`), incrementa `writeEpoch` e recarrega com `skipAdapt`.
- `tests/test_design_system_ads_two_tabs.py`: duas páginas reais no Chromium sobre o serviço + CAS em memória. Sem Playwright/Chromium: skip.
- Não substitui o teste Node da fila na mesma aba nem o render do incremento 4.

## Incremento 8 — o que mudou

- `UNMIGRATED_TASKS` vazio. `generate_brand_track` carimba `ads-tracks-2026-09-12` e o run ganha `context`.
- Leitura canônica = `brand_profile`. Projeção só no GET, com `storage.orphan` e `revision=0` para o primeiro CAS.
- Mesa: faixa `mcDsaStorage`. Clique em **Montar a marca** grava a projeção no profile.

## Compatibilidade e rollback

Tokens no mesmo shape. Campos novos em `evidence`, `inherits_brand_version`, `revision` e `evidence.validation`. Coluna gerada é projeção do JSON; dropar a coluna não apaga o documento. Rollback: revert do commit + `DROP COLUMN IF EXISTS design_system_ads_revision`; JSON antigo trata `revision` ausente como 0 e formatos como `unchecked`.

## Ativação

Mesa e CAS valem no próximo deploy (a migration da coluna corre no `deploy.sh`). Render só sob demanda (`Conferir peça` ou `DSA_RENDER_VALIDATE=1`).

## Validação manual

1. Marca nova só com primária: aviso de fallback/inferência; ink não é o teal da casa marcado como aprovado.
2. CentralComm Ads: identidade confirmada, teal/ouro.
3. Sem OpenRouter: status `local_seed`; a mesa não afirma review de modelo.
4. Montar campanha, mudar ink da marca, montar de novo: tinta da campanha permanece.
5. Payload antigo (sem provenance) abre; campos `unknown`.
6. Duas abas: aprovar na primeira, patch na segunda → 409 “A marca mudou. Recarregue.”; a mesa recarrega.
7. Marca aprovada: ajuste de tipo/CTA não muda a tinta. Intent contraste ainda corrige.
8. Duas edições rápidas na mesma aba: um POST coalescido; se dois jobs já saíram, o segundo não reenvia.
9. Mudar ink: digest do console muda; billboard fica `stale`. Mesmo contrato (chaves em outra ordem) não muda o hash.
10. CentralComm → Conferir peça: hop `render` passa no billboard se o servidor tiver Chromium. Sem Playwright, `skipped`.
11. Marca com packshot, mudar ink: Pendências lista billboard `stale`. Marca sem produto: mobile `needs_input`. CentralComm aprovado: “Nenhuma pendência.”
12. Marca só na projeção: faixa de armazenamento; **Montar a marca** grava no profile com `revision=1`.

## Pendências concretas (não ampliar ainda)

- Review visual com screenshot/HTML do specimen.
- Job de CI com Postgres para `test_design_system_ads_postgres`.
