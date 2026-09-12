# Trocr — confiabilidade

Diagnóstico do código em produção e plano de incrementos. Complementa [`trocar.md`](trocar.md) (contrato) e [`trocr-editor-refactor.md`](trocr-editor-refactor.md) (UX). Em conflito, vale o símbolo citado aqui.

Não existe `AGENTS.md` no repositório. Pydantic 2 (`>=2.9,<3`) já é dependência; o padrão do lab é `creative_format_lab/spec.py`. 409 já mapeia `CreativeConflictError`.

**Fase 1:** baseline. **Fase 2:** schema. **Fase 3:** plano/hash/conflitos/no-op + OCR com `status`. **Fase 4:** seleção + typeset com máscara. **Fase 5:** tipografia, CTAs, roteamento, prompts. **Fase 6:** histórico com CAS/`parent_id`. **Fase 7:** slot cego. **Fase 8 (esta sessão):** rascunho manda `quality=medium` no Image 2; duas pills de CTA sem caixa saem da tinta.

---

## Fluxo atual real

```text
mesa (mc-trocar.js)
  → POST /parametros/api/format-lab/swap/read     OCR visão
  → POST /parametros/api/format-lab/swap/prompt   preview + quote + mode
  → POST /parametros/api/format-lab/quote         kind=swap
  → POST /parametros/api/format-lab/swap          gera PNG
  → GET|POST /parametros/api/format-lab/swap/history
  → GET  /parametros/api/format-lab/swap/still/<arquivo>   still autenticado
```

Upload → OCR → análise → edição → geração → revisão. Autenticação: `admin_required` / `admin_required_api`. Geração síncrona. Jobs (`create_generation_job`) existem na Modelagem; o Trocr não os usa.

`build_swap_plan()` escolhe o modo. `swap_mode()` continua sendo o roteador de execução:

1. `noop` se não há alteração efetiva, nota, `force_image`, override nem recrop
2. `blocked` se typeset sem região (`CREATIVE_FORMAT_SWAP_REQUIRE_REGION`, default ligado)
3. `recrop` se `aspect_hint ≠ aspect_ratio` e há patches de tipo
4. `image` se `force_image`
5. `typeset` se `alter ⊆ {headline, secondary, cta, price}`
6. senão `image`

---

## Persistência

| superfície | papel |
|---|---|
| `brand_profile.trocr` | sessão por marca (`client-{id}`) |
| arquivo `save_trocr_session` | espelho em disco (`/static/uploads/creative_trocr/`) |
| `repository.trocr_sessions` | memória de teste |
| `user-{id}` | fallback sem marca; também recebe cópia quando há marca |
| `/static/uploads/creative_generated/` | stills legados; URL pública |
| `instance/trocr_stills/` | stills novos; só via `GET /swap/still/<arquivo>` autenticado |

IDs `v1`, `v2` vêm do cliente. Teto 60. `parent_id` e `revision` (CAS) no servidor. Debounce 400 ms. Original omitida ou com PNG trocado é restaurada. 409 se a revisão divergir.

---

## Problemas confirmados

| problema | arquivo / símbolo |
|---|---|
| OCR sem provedor ou JSON inválido vira leitura vazia “ok” — **corrigido na fase 3** | `status`: `unavailable` / `provider_error` / `invalid` / `unreadable` / `partial` / `completed` |
| `subtitle` era cópia de `dates` — **corrigido na fase 2** | `swap_schema.apply_swap_schema`; `#mcTrocrSubtitle` |
| `support` (campo) vs `secondary` (token `alter`) | `swap.ALTER_LABELS`; `typeset_patches` |
| `note` canônico; `instruction` só alias de entrada — **fase 2** | `swap_schema.copy_from_payload` |
| `logo_text` e `disclaimer` no payload — **fase 2** | `editFields()`; `#mcTrocrLogo` / `#mcTrocrDisclaimer` |
| `faces` = `kind=face` — **fase 2**; `swap_risk` ainda conta `role=person` | `editFields`; `swap_risk` |
| Pessoa (`face`) ≠ selo (`name_pill`) — **fase 2** | `swap_schema.infer_kind` |
| Copy acima do limite: erro na geração; OCR marca `overflow` — **fase 2** | `copy_from_payload`; `normalize_read` |
| Locks acima de 12: lista completa + `locks_overflow` — **fase 2** | `apply_swap_schema` |
| Recrop pinta headline/apoio/preço mesmo sem autorização — **corrigido na fase 3** | `typeset_all` só se explícito; recrop não força mais |
| Texto sem pessoas cai no Image 2 — **corrigido na fase 5** | `swap_mode`: `alter ⊆ TYPE_ONLY` → typeset; `force_image` força Image 2 |
| Slot cego: &lt;40 px de tinta → `_fill_slot` no retângulo — **corrigido na fase 7** | sem tinta no slot da grade não preenche; cromático &gt;25% do slot é foto, não tipo; `_fill_slot` só na região do usuário |
| CTA sempre tinta quase preta — **corrigido na fase 5** | `_patch_ink("cta")` usa tinta amostrada quando há `cover` |
| Draft não muda o payload do Image 2 — **corrigido na fase 8** | Trocr manda `image_quality`; draft → `medium`, production → `high`. Mesa/Camadas não passam o campo |
| Quote typeset = US$ 0 (custo operacional, não só API) | `quote_swap` |
| Image 2 sem máscara no cliente | `CreativeModelingGenerator.generate_image` — só `input_references` |
| Logo oficial entra só porque a marca está ligada — **corrigido na fase 3** | se `logo` ∈ preserve, não anexa logo oficial |
| Stills gerados acessíveis em URL estática — **novos na fase 6** | `save_trocr_still` + `GET /swap/still/<arquivo>`; legado público permanece |
| Sem CSRF nas rotas format-lab — **POST do Trocr na fase 6** | `X-Trocr-CSRF-Token`; GET history/still sem header |
| Preview e execução recalculam o plano à parte — **corrigido na fase 3** | `plan_hash`; hash obsoleto → 409 |
| `prompt_override` substitui o prompt inteiro | `build_optimized_prompt` |
| Aspecto no servidor prioriza hint/OCR — **corrigido na fase 5** | `resolve_aspect_ratio` → `aspect_ratio`/`output`, senão `ratio_from_size(ref_*)`, senão `aspect_hint`, senão `16:9` |
| Canvas `object-fit: contain` + zoom sem conversão — **corrigido na fase 4** | overlay `#mcTrocrPickRegion`; `regions` + `ref_width`/`ref_height` |

---

## Hipóteses não comprovadas

- Fantasmas TIM Black desta semana (lab anterior; não re-medido nesta fase).
- Exploitabilidade real de CSRF (SameSite do cookie não inspecionado ponta a ponta).
- Corrida de duas abas no `POST /history`.
- Se o Image 2 no OpenRouter ignora `quality` mesmo quando enviado (agora o Trocr manda `medium`/`high`).
- Necessidade de OpenCV ou PaddleOCR — nenhum dos dois está em `requirements.txt`.
- Consumidores de `read_swap_reference` além do Trocr e do `engineer.apply_still_read`.

Não tratar hipótese como bug. Não inventar suporte a máscara no Image 2.

---

## Divergências doc × código

[`trocar.md`](trocar.md) descreve typeset como “custo zero”. Draft e production agora diferem no HTTP do Image 2 (`medium` vs `high`); o modelo continua `openai/gpt-image-2`. Fluxo, rotas e modos batem.

---

## Infraestrutura que se reaproveita

- Flask / Jinja / `mc-trocar.js` / Pillow — manter.
- Pydantic: `spec.py`, `creative_agents/contract.py`.
- Auth: `admin_required_api`.
- Persistência Trocr já existente (`_read_trocr` / `_write_trocr`).
- OpenRouter: `POST https://openrouter.ai/api/v1/images`, timeout 180s, até 2 referências.
- Testes: `python3 -m unittest tests.test_creative_format_lab.CreativeFormatLabSwapTest`.
- Sem Redis/Celery no Trocr. Sem `cv2`. Sem download automático de modelo.

---

## Compatibilidade e migração

Payload legado (`headline`, `support`, `alter[]`, `preserve[]`, `note`) continua válido até a fase de schema. Adaptador deve:

- Não inventar bbox a partir de nota.
- Não fundir `dates` e `subtitle` em migração ambígua — preservar os dois e sinalizar.
- Não apagar `prompt_override`; marcar como avançado quando o plano existir.
- Histórico: acrescentar campos (`qa`, `plan_hash`, `parent_id`) sem invalidar sessões gravadas.

Flags (fase 3, ligadas no código):

| variável | default | efeito |
|---|---|---|
| `CREATIVE_FORMAT_SWAP_STRICT_PLAN` | ligado | se o cliente manda `plan_hash`, tem de bater; legado sem hash ainda executa |
| `CREATIVE_FORMAT_SWAP_REQUIRE_REGION` | ligado | typeset sem bbox bloqueia; “Confirmar” não fura; Image 2 / recrop seguem sem caixa |

Rollback da fase 1: apagar este arquivo e o ponteiro em `trocar.md`. Nenhum runtime muda.

---

## Plano por prioridade

1. **Feito.** Baseline, testes de regressão, este documento.
2. **Feito.** Schema canônico + adaptador legado (P0).
3. **Feito.** Plano único, conflitos, no-op, OCR com status (P0).
4. **Feito.** Seleção manual + typeset com máscara + QA de pixels (P1, fatia vertical).
5. **Feito.** Tipografia, CTAs múltiplos, roteamento de formato, prompts derivados do plano (P1).
6. **Feito o executor.** Sessão em `swap_session.py`, CSRF nas POST, still legado hex pela rota autenticada. Sem jobs, multipart, PaddleOCR.
7. **Feito.** Slot cego não preenche foto.
8. **Feito.** Rascunho → `quality=medium` só no Trocr. Dois CTAs sem bbox: plano não bloqueia; typeset acha as pills na tinta.
9. **Feito.** Um CTA no pedido pinta só a pill da esquerda; a segunda não muda. Sem pill na tinta, recusa. Preço/headline sem caixa continuam bloqueados.

Segurança crítica (SSRF no typeset local, limite de megapixels, CSRF) entra junto da fatia que tocar o executor — não espera o P2 de jobs.

---

## Critérios de aceite da fase 1

- Testes Swap atuais passam (ver abaixo).
- Problemas confirmados citam arquivo e função.
- Hipóteses ficam separadas.
- Working tree de Ads / Camadas não é misturado nesta entrega além do ponteiro no contrato.
- Nenhuma chamada paga.
- Nenhuma dependência nova.

Aceite da fatia vertical (fase 4): selecionar preço em fundo liso, Pillow sem rede, pixels fora da bbox idênticos, versão com `qa.status` explícito.

---

## Dependências e bloqueios

- Sem `OPENROUTER_API_KEY` / integração: OCR e Image 2 não rodam; typeset Pillow sim (data URL).
- Sem fontes da marca no Pillow: Avenir/Arial/DejaVu — não afirmar “fonte oficial”.
- Sem autorização explícita: nenhuma chamada paga de Image 2 ou visão.
- PaddleOCR / `cv2`: só depois de licença, provisionamento e import opcional. Testes devem passar sem o pacote.

---

## Testes da fase 1

Comando (12 set 2026, `python3` 3.9, `PYTHONPATH=.`):

```bash
PYTHONPATH=. python3 -m unittest \
  tests.test_creative_format_lab.CreativeFormatLabSwapTest \
  tests.test_creative_format_lab.CreativeFormatLabRoutesTest.test_ler_referencia_do_trocar \
  tests.test_creative_format_lab.CreativeFormatLabRoutesTest.test_preview_do_prompt_do_trocar \
  tests.test_creative_format_lab.CreativeFormatLabRoutesTest.test_historico_do_trocar \
  tests.test_creative_format_lab.CreativeFormatLabDeskTest.test_mesa_registrada_no_shell \
  -q
```

**Resultado real:** `Ran 17 tests in 1.040s` — **OK**.

Inclui: prompt PT/EN, swap com logo stub, OCR parseado, typeset de cartela sem Image 2, typeset 16:9 sem pintar a pessoa, recrop + typeset, histórico por marca, rotas `/swap/read|prompt|history`, desk `trocar` no shell.

Não executado:

- `tests.test_modelagem_criativos` completo (contrato amplo da Modelagem; working tree de Ads sujo).
- Image 2 / gpt-4o-mini reais (opt-in, pago, sem autorização).
- Benchmark visual TIM Black / arraial ao vivo.
- Testes de CSRF, SSRF, duas abas, EXIF, overflow — ainda não existem.

Mocks de rota **não** são evidência visual.

---

## Fase 2 — o que mudou

- [`swap_schema.py`](../aicentralv2/creative_format_lab/swap_schema.py): `SwapCopy`, `SwapElement`, `SwapBox`, `SwapIntent`, `apply_swap_schema`, `normalize_read`.
- `prepare_swap` e `read_swap_reference` passam pelo adaptador. Payload legado continua válido.
- `dates` e `subtitle` independentes. Typeset de datas usa `dates`, não `subtitle`.
- `kind=face` vs `kind=name_pill`. IDs `cta_01`, `cta_02`, `face_01`.
- Limite comercial: `ValueError` acionável em geração; OCR guarda o texto e lista `overflow`.
- Locks excedentes permanecem; `locks_overflow` sinaliza.
- Mesa envia `logo_text`, `disclaimer`, `subtitle` próprio e `faces` só de `kind=face`.
- Sem plano/hash, sem região, sem Image 2, sem `typeset_all` corrigido (fica na fase 3).
- Refino: `_lock_list` e `locks_from_read` deixam de cortar; `locks_overflow` ≠ texto longo; IDs duplicados viram `cta_02`; `kind` inválido cai em `infer_kind`; bbox sem dimensão da referência não é inventada.

## Testes da fase 2

Mesmo comando da fase 1. **Resultado real:** `Ran 19 tests in 0.959s` — **OK**.

Novos: `test_schema_legado_nao_funde_dates_e_subtitle`, `test_schema_recusa_texto_acima_do_limite_e_nao_descarta_lock`.

---

## Fase 3 — o que mudou

- [`swap_plan.py`](../aicentralv2/creative_format_lab/swap_plan.py): `build_swap_plan`, `assert_swap_plan`, `PLANNER_VERSION = trocr-plan-3`.
- Preview e execução compartilham `plan_id` / `plan_hash`. Hash não inclui `confirm_conflicts` nem `quality`. A chave da referência é `base_id` / `reference_id` (a mesa não reenvia o PNG no debounce).
- Sem alteração efetiva: `mode=noop`, 200, sem PNG, sem versão, quote sem custo operacional fingido.
- Conflitos: `preserve_and_alter`, `field_without_operation`, `layout_vs_format`, `note_mismatch` (regex PT), `logo_locked` (informativo), `needs_region` se a flag ligar.
- `typeset_all` só se o payload pedir. Recrop pinta só o `alter` autorizado.
- Se `logo` ∈ preserve, a logo oficial não entra como segunda referência.
- OCR: `unavailable` / `provider_error` / `invalid` / `unreadable` / `partial` / `completed`. A mesa não tosta sucesso em vazio.
- UI: lista de conflitos, “Confirmar mesmo assim”, rota `noop`/`blocked`, faixa de status do OCR.
- Revisão: `assert_swap_plan` usa o primeiro conflito *blocking*; a mesa atualiza o plano mesmo com prompt editado e recarrega o hash imediatamente antes de gerar (evita 409 do debounce).
- Sem região, sem Image 2 pago, sem PaddleOCR, sem jobs.

## Testes da fase 3

Mesmo comando da fase 1. **Resultado real (após revisão):** `Ran 22 tests in 0.606s` — **OK**.

Novos: `test_plano_unico_hash_conflitos_e_noop`, `test_hash_obsoleto_vira_409_no_servico`, `test_noop_nao_grava_versao`.

## Fase 4 — o que mudou

- Typeset com região: recorta a bbox, pinta no recorte e cola de volta. Pixels fora da caixa não mudam.
- `score_typeset_qa` devolve `qa.status`: `pass` | `fail` | `unchecked` (sem máscara, slot legado).
- `fail` aborta a geração. A versão guarda `qa` e `plan_hash`.
- Typeset recusa `http(s)` (sem fetch) e still acima de 20 MP / 12 MB decodificados.
- Mesa: ferramenta de recorte no canvas, overlay, `regions` + `ref_width`/`ref_height` no payload.
- Hash do plano inclui a bbox (`trocr-plan-4`). Recrop com tamanho diferente da referência ignora a bbox original.
- Typeset sem região agora bloqueia (`REQUIRE_REGION` default ligado). Confirmar conflito não fura. Image 2 e recrop não exigem caixa (máscara só vale no Pillow do mesmo tamanho).
- Sem Image 2 pago, sem PaddleOCR, sem jobs.

## Testes da fase 4

Mesmo comando da fase 1. **Resultado real:** `Ran 23 tests in 0.714s` — **OK**.

Novos: `test_typeset_com_mascara_nao_mexe_fora_da_bbox`, `test_typeset_sem_regiao_nao_pinta_no_escuro`. **Resultado real (região obrigatória):** `Ran 24 tests in 0.669s` — **OK**.

## Fase 5 — o que mudou

- Type-only (`alter ⊆ {headline, secondary, cta, price}`) vai para typeset mesmo sem elenco. `force_image` e recrop continuam na frente.
- `resolve_aspect_ratio` lê o pedido do usuário; senão `ratio_from_size(ref_width, ref_height)`; senão `aspect_hint`; senão `16:9`.
- Prompt e preview só listam copy com `from ≠ to` nas operações do plano. Preço/CTA intactos não entram no dump.
- CTA não força mais fill branco + tinta `(17, 17, 17)`. Headline larga (`width/height ≥ 2.4`) alinha à esquerda.
- Dois ou mais elements `role=cta` com texto → um patch por pill, cada um com o próprio `bbox_px`.
- Mesa: segundo CTA (`#mcTrocrCta2`) entra em `elements` via `withCtas`.
- Sem Image 2 pago, sem PaddleOCR, sem jobs.

## Testes da fase 5

Mesmo comando da fase 1. **Resultado real:** `Ran 26 tests in 0.883s` — **OK**.

Novos: `test_texto_sem_elenco_e_regiao_vai_para_typeset`, `test_prompt_deriva_so_das_operacoes`. Testes Image 2 passam a mandar `force_image`.

## Fase 6 — o que mudou

- `save_swap_history` faz merge: original omitida volta; PNG da original não troca; `http(s)` não entra.
- `revision` incrementa a cada gravação. Cliente manda a revisão lida; divergência → 409. Sem campo, o legado ainda grava.
- Versões guardam `parent_id`. Append do swap usa `base_id` e `origin` do modo (`typeset`/`recrop`, não mais “produção” genérico).
- Swap devolve `history` (revisão + URLs). A mesa aplica e manda `revision` no persist.
- Stills novos: `instance/trocr_stills/` + `GET /parametros/api/format-lab/swap/still/<arquivo>` (`admin_required_api`).
- Histórico e still saíram de `FormatLabService` para [`swap_session.py`](../aicentralv2/creative_format_lab/swap_session.py).
- POST do Trocr exige `X-Trocr-CSRF-Token`. GET history/still não.
- Still legado com nome hex em `/static/uploads/creative_generated/` é reescrito para a rota autenticada na leitura. O arquivo público antigo continua no disco.
- Sem jobs, multipart, PaddleOCR, Image 2 pago.

## Testes da fase 6

Mesmo comando da fase 1 + `tests.test_trocr_session`. **Resultado real:** `Ran 32 tests in 0.880s` — **OK**.

## Fase 7 — o que mudou

- Typeset no slot da grade sem tinta suficiente não preenche o retângulo.
- Mancha cromática que ocupa mais de 25% do slot é tratada como foto, não como tipo.
- `_fill_slot` só roda na região que o usuário recortou.
- Cobertura de glifo com raio 6 (antes 4).
- Sem Image 2 pago, sem PaddleOCR, sem jobs.

## Testes da fase 7

Mesmo comando da fase 1 + `tests.test_trocr_session`. Novo: `test_typeset_slot_cego_nao_preenche_a_pessoa`. **Resultado real:** `Ran 33 tests in 1.056s` — **OK**.

## Fase 8 — o que mudou

- `image_quality()`: draft/rascunho → `medium`; production → `high`. Só o `FormatLabService.swap` injeta `image_quality` no `_image_callable`. Mesa 15s e Camadas não passam o campo — o default do gerador continua `high`.
- Dois ou mais `role=cta` com texto e sem bbox: o plano não bloqueia (`may_infer_cta_pills`). O hash não inclui caixa inferida (preview sem PNG continua batendo na geração).
- `locate_cta_pills` agrupa manchas cromáticas em pills (aspecto largo, não foto). `attach_inferred_cta_regions` preenche `bbox_px` na hora do typeset. Sem duas pills → erro acionável, não pinta no escuro.
- Sem Image 2 pago, sem PaddleOCR, sem jobs, sem inventar bbox a partir da nota.

## Testes da fase 8

Mesmo comando da fase 1 + `tests.test_trocr_session` + still autenticado. Novos: `test_rascunho_do_trocr_manda_qualidade_media`, `test_duas_pills_sem_caixa_nao_pintam_o_vao`. **Resultado real:** `Ran 35 tests in 1.686s` — **OK**.

## Fase 9 — o que mudou

- `may_infer_cta_pills` vale para um CTA sem bbox, não só para o par.
- Um texto + duas pills: pinta só a da esquerda. A segunda e o vão ficam iguais.
- `locate_cta_pills` devolve as pills da esquerda para a direita (não as de maior score).
- Sem pill cromática: erro acionável. Não inventa caixa a partir da nota. Preço/headline sem região seguem bloqueados.
- Sem Image 2 pago, sem PaddleOCR, sem jobs.

## Testes da fase 9

Mesmo comando da fase 8. Novo: `test_um_cta_pinta_so_a_pill_da_esquerda`.

## Checkpoint

**Concluído:** fases 1–9 do Trocr.

**Fora desta linha:** OCR geométrico, jobs, multipart, isolamento físico dos stills legados, modelo mais barato de rascunho. Mesa 15s e Camadas não entram aqui.
