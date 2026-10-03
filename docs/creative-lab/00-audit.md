# Creative Lab — Fase 0 · Auditoria e spikes

Data: 2026-10-03 · Situação: **auditoria concluída, nenhum código de feature escrito.** Aguardando aprovação para a Fase 1.
Brief de origem: "Creative Lab — Brief para Claude Code (v2)". Pedido adicional do dono: usar **marcas e auditoria de marca do Workspace** como payload; prompts de **gerar** e de **editar**; gerar **uma imagem por vez**; começar **só por modelos do OpenRouter**, com **um JSON por modelo**; **Higgsfield fora** por enquanto; mesa de testes com troca de referências (logo, pessoa, produto), análise de resultado, custo e tempo; validação com **TypeSafe** confrontando prompt × original × resultado para descobrir o que ajustar no "sistema" de cada modelo.

Snapshot do catálogo usado nesta auditoria: [`openrouter-catalog-2026-10-03.json`](openrouter-catalog-2026-10-03.json).

---

## 1. Correções ao brief (o que não bate com o repositório)

| Brief presume | Realidade | Consequência |
|---|---|---|
| PHP puro | **Python 3.13 + Flask** (`aicentralv2/`), Jinja, PostgreSQL (psycopg), ilhas **React + Vite** (`frontend/*`, `vite.*.config.mjs`), Tailwind | Lab = blueprint Flask + página Jinja de bootstrap + ilha React |
| Untitled UI React | Removido do Studio. Kit próprio `frontend/cadu-studio-ui/` (`tokens.css`, `StudioNavbar`, `StudioDialog`, `island.jsx`), **Studio sempre escuro** | Lab usa `cadu-studio-ui`; nada de shadcn/Untitled |
| Feature flag genérica | Não há sistema de flags. Padrão do repo: `@admin_required` + rotas `/lab/*` registradas fora do nav (`register_modeling_ux_lab`, `creative_modeling_routes.py:2397`) + flags de ambiente (`CREATIVE_*`) | Lab: `@admin_required` + `CREATIVE_LAB_ENABLED` (env/config); sem flag → 404 |
| Ideogram 4 / Z-Image Turbo "conforme spike" | **Não existem no OpenRouter.** Só no Higgsfield | Fora da Fase 1 (Higgsfield adiado) |
| TypeSafe valida imagens | **Jev aceita só texto** (docs.typesafe.ai/concepts/state: "Images, audio, and video are not supported (yet)") | Validação precisa de um passo **Observador** (imagem → JSON) antes do TypeSafe. Ver §6 |

---

## 2. Pipeline de produção atual (não tocar)

| Etapa | Onde | Observação para o Lab |
|---|---|---|
| Entrada Criar | `creative_media/studio_create.py` (`create`, `create_image`) | Director = `system_prompt(count)` (~1,2k palavras, gpt-5-nano) |
| Contexto de marca no Criar | `studio_create.clean_context` (`:145`), `brand_identity_guard` (`:259`), `official_logo_reference` (`:333`) | Reutilizável **por leitura** |
| Edição | `creative_media/studio_prompt.py` (compiler v1) + `_openai_edit_image` | `protected_literals` é o ponto frágil já conhecido |
| Chamada ao provider | `services/openrouter_service.py` → `generate_image` (`:951`) | **OpenAI direto primeiro, OpenRouter como fallback.** `build_image_payload` tem hacks fixos por modelo (`gemini-3`/`seedream` removem `quality`) e limita refs a 4 |
| Pós-processamento (Composer) | `studio_create.apply_brand_logo` (`:1252`), `creative_media/banner_compose.py` (tipografia Pillow), `brand_fonts.py` | Existe: logo e texto aplicados depois por código |
| Storage | `creative_media/storage.py` (`instance/creative_media`), `creative_modeling_storage.public_studio_asset_url` | Referências para o OpenRouter **precisam ser HTTPS público ou data URL** |
| Custo/crédito | `creative_media/studio_costs.py` (catálogo fixo + 12%/ref), `cadu_tool_billing.charge_from_provider` | Lab **não debita crédito do cliente**; registra custo real do provider |
| Fila | `creative_media/queue_worker.py` (arquivos + PG), `cadu_workspace/brand_audit_jobs.py` (`claim(max_running)`, lease, `fail_stale`) | O padrão de `brand_audit_jobs` (claim + lease) é o molde da fila do Lab |

**Regra para o Lab:** não chamar `generate_image` nem `build_image_payload`. Eles fazem fallback silencioso de rota e podam parâmetros por `if` de nome de modelo — exatamente o que o Lab precisa medir. O Lab ganha seu próprio conector OpenRouter (arquivo novo), reaproveitando só funções puras: `image_reference`, `_absolute_provider_reference`, `_download_reference_bytes` (validação de URL pública/assinatura), `is_real_person_block`.

---

## 3. Marcas e auditoria de marca como payload

Fonte única: a mesma do Workspace.

- Marca = linha em `cx_clients` (`brand_profile` JSONB, `analysis_metadata`, `primary_color`, `secondary_color`, `logo_url`/`display_logo`).
- Contexto canônico já pronto: `cadu_workspace/brand_mcp_service.brand_context()` e `GET /workspace/api/brands/<id>/context` — cores, fontes, identidade (`brand_summary`, `tone_of_voice`, `mandatory_elements`, `forbidden_elements`, `visual_motifs`), mercado, campanhas, `field_provenance`.
- Auditoria: `cadu_workspace_brand_audit_runs` (input, sources, costs, reviews) e **`cadu_workspace_brand_identity_fields`** (por campo: `status` `verified|probable|…|needs_review`, `confidence`, `evidence_count`, `last_verified_at`). Regras de publicação em `brand_reliability.py` (`PUBLISHABLE_FIELD_STATES = {'verified'}`).
- Assets: `cx_client_brand_assets` (`role`, `asset_path`, `sha256`, `width/height`, `status`, `is_primary`).

**Proposta de BrandSnapshot do Lab** (congelado no experimento):

```jsonc
{
  "brand_id": 123, "brand_ref": "studio:123", "audit_job_id": "…", "snapshot_at": "…",
  "fields": {
    "palette":            {"value": ["#0B1F3A", "#F2B705"], "status": "verified", "confidence": 0.94},
    "fonts":              {"value": [...], "status": "probable", "confidence": 0.7},
    "tone_of_voice":      {"value": "…", "status": "verified"},
    "mandatory_elements": {"value": [...], "status": "verified"},
    "forbidden_elements": {"value": [...], "status": "needs_review"}
  },
  "logo": {"asset_id": 88, "sha256": "…", "is_primary": true},
  "payload_policy": "verified_only | verified_and_probable | all"
}
```

O seletor `payload_policy` vira **variável de teste**: "o modelo melhora quando mandamos só campos verificados?" é um Reference/Prompt Test legítimo.

---

## 4. Spike OpenRouter (feito com chamada real, só leitura)

`GET /api/v1/images/models` respondeu **57 modelos**, sem autenticação. `GET …/{id}/endpoints` traz preço granular e chaves de passthrough. Confirmado:

| Modelo (slug real) | Refs máx. | Parâmetros próprios | Preço (endpoint) | Passthrough |
|---|---|---|---|---|
| `openai/gpt-image-2` (baseline) | 16 | `quality` auto/low/medium/high, `background` auto/opaque, `output_compression` | token: in-img 8e-6, in-txt 5e-6, out-img 3e-5 | `moderation` |
| `openai/gpt-image-2.5-sunburst` | 16 | `quality` até `xhigh`/`max`, `background` **transparent** | mesmo esquema por token | `moderation` |
| `openai/gpt-image-2.5-flare` | 16 | idem Sunburst | idem | `moderation` |
| `qwen/qwen-image-3-pro` | 4 | `resolution` 1K/2K, `seed`, ratios até 4:1 | US$ 0,04 (1K) / 0,075 (2K) + 0,003/ref | — |
| `qwen/qwen-image-3` | 4 | idem | US$ 0,03 + 0,003/ref | — |
| `recraft/recraft-v4.1` · `-utility` | **1** | só `aspect_ratio`, `n` | US$ 0,035 | `style`, `controls`, `text_layout` |
| `recraft/recraft-v4.1-pro` · `-utility-pro` | **1** | idem | US$ 0,21 | idem |
| `recraft/recraft-v4.1-flash` | **0** (só gera) | idem | — | — |
| `google/gemini-3.1-flash-image` | 14 | `resolution` 512–4K | token out 6e-5 | `cachedContent` |
| `bytedance-seed/seedream-5-0-pro` | 14 | `resolution`, `seed` | US$ 0,045 / 0,09 high | — |
| `black-forest-labs/flux-3-image` | 10 | `resolution` 768–4K | US$ 0,041 (768) → 0,607 (4K) | `safety_tolerance` |

Achados que mudam o desenho:

1. **Cada família tem um "botão de custo" diferente**: OpenAI = `quality`; Qwen/Seedream/Gemini/Flux = `resolution`; Recraft = nenhum (preço fixo). O CreativeSpec fala em `quality: draft|standard|high`; o adapter traduz e registra no AdaptationPlan.
2. **Recraft aceita 1 referência** → em teste com mockup+produto+logo, 2 viram texto ou pós-processo. O AdaptationPlan tem que mostrar isso.
3. **Passthrough relevante**: Recraft `style`/`controls`/`text_layout` e `moderation` na OpenAI são onde o "sistema" do modelo pode ser ajustado além do prompt.
4. **OpenAI direto ≠ OpenRouter**: o direto aceita `size` livre (`WxH`); o OpenRouter só `aspect_ratio`. O benchmark Direct × OpenRouter precisa registrar isso.
5. **Não verificado ainda (exige chave + gasto)**: se `usage.cost` vem em toda resposta de imagem; latência real; comportamento com pessoa real (`is_real_person_block`). Primeira chamada paga da Fase 1 confirma.
6. `OPENROUTER_API_KEY` não está no `.env` local; a chave é resolvida pelo `integration_credentials` (banco). O `.env` aponta para o banco remoto → **toda gravação do Lab vai para o banco de produção**.

Higgsfield: não testado (pedido do dono). Ideogram 4, Z-Image Turbo, SOUL, Marketing Studio ficam `unavailable` no catálogo até a Fase 4.

---

## 5. Um JSON por modelo (manifesto de adapter)

Arquivos versionados em `aicentralv2/creative_lab/models/<slug>.json`. O catálogo do OpenRouter dá as **capacidades** (fonte de verdade, em runtime, cacheado em `lab_model_catalog`); o JSON guarda o que é **nosso**: como falar com o modelo.

```jsonc
// creative_lab/models/qwen--qwen-image-3-pro.json
{
  "model_key": "qwen-image-3-pro",
  "provider": "openrouter",
  "provider_model_id": "qwen/qwen-image-3-pro",
  "adapter": "qwen",                // família → código do adapter
  "profile_version": 3,             // sobe a cada ajuste aprovado
  "quality_map": {"draft": {"resolution": "1K"}, "standard": {"resolution": "1K"}, "high": {"resolution": "2K"}},
  "tasks": {"generate": true, "edit": true},
  "reference_policy": {
    "order": ["COMPOSITION", "PRODUCT", "PERSON", "STYLE", "LOGO"],
    "logo": "composer_overlay",     // nunca pedir ao modelo para desenhar o logo
    "overflow": "describe_in_prompt"
  },
  "prompt_profile": {
    "language": "en",               // ou "pt" — variável testável
    "max_chars": 2000,
    "structure": ["subject", "composition", "references", "text_exact", "brand", "avoid"],
    "text_rendering": "quote_exact_strings",
    "preamble": "…",                // o "sistema" do modelo — o que o loop TypeSafe sugere mudar
    "negative_style": "inline_avoid_clause"
  },
  "passthrough": {},
  "known_failure_modes": []         // preenchido pelas avaliações
}
```

O AdaptationPlan é calculado de `capabilities (catálogo) × manifesto × CreativeSpec`. Ajustes no `prompt_profile` nascem como **proposta** (`lab_presets` `pending_review`) e só viram nova `profile_version` com aprovação. Nada disso toca o Studio de produção.

Shortlist da Fase 1 (só OpenRouter): `gpt-image-2` (baseline, OpenRouter **e** OpenAI direto), `gpt-image-2.5-sunburst`, `qwen-image-3-pro`, `recraft-v4.1`. Fase 3 amplia: `gpt-image-2.5-flare`, `qwen-image-3`, `recraft-v4.1-utility`/`-pro`, `gemini-3.1-flash-image`, `seedream-5-0-pro`, `flux-3-image`.

---

## 6. Validação com TypeSafe — desenho

O Jev não vê imagem. Então o loop tem três camadas:

```
imagem gerada ─┬─► Observador determinístico (custo zero, código)
               │     OCR pt-BR (tesseract, `por.traineddata` já no repo) · paleta dominante e ΔE vs paleta da marca
               │     · proporção/dimensão · hash perceptual vs referências (PRODUCT/PERSON) · área do logo
               │
               └─► Observador visual (1 chamada LLM com visão, JSON estrito, temperatura 0)
                     o que está na cena · texto lido · pessoas (quantas, coerentes com a ref?) · produto
                     preservado? · elementos proibidos presentes? · defeitos (mãos, letras, artefatos)
                                    │
     state = { spec, instrução original, director_prompt, model_prompt, adaptation_plan,
               brand_snapshot (só campos usados), observation_det, observation_visual }
                                    │
                                    ▼
                       TypeSafe System One (Jev) — perguntas tipadas
```

Perguntas (um request por run, todas sobre o mesmo state):

| id | tipo | pergunta |
|---|---|---|
| `text_exact` | noul | Todo texto obrigatório aparece exatamente como pedido (observação OCR × `mustIncludeText`)? |
| `brand_palette` | score | Quão aderente a paleta observada está à paleta verificada da marca? |
| `forbidden_present` | noul | Algum `forbidden_elements` da marca aparece na observação? |
| `reference_respected` | choice | `preserved / partially / ignored / not_applicable` para cada role enviada nativamente |
| `instruction_fidelity` | score | O resultado cumpre a instrução original (não só o prompt adaptado)? |
| `prompt_drift` | noul | O prompt adaptado perdeu algo da instrução original? (detecta erro do **nosso** adapter, não do modelo) |
| `primary_failure` | choice | `none / text_rendering / reference_ignored / palette_off / extra_elements / composition / identity_changed / prompt_lost_info` |

`primary_failure` + `prompt_drift` são o que alimenta "o que mudar no sistema daquele modelo": cada falha mapeia para um ajuste candidato no manifesto (ex.: `text_rendering` recorrente no Qwen → testar `language: en` + aspas; `reference_ignored` no Recraft → mover referência para `controls` via passthrough). O sistema **sugere**; o humano aprova. Agregados só com n ≥ 10 e mostrando n (Jev é mais preciso em inglês — state e perguntas em inglês; UI em pt-BR).

Custo da validação por run: observador visual (~US$ 0,001–0,01) + TypeSafe (tokens reportados em `usage`). Ambos gravados à parte do custo da geração.

Avaliação humana (notas 1–5, cega, pareada) continua — TypeSafe é **segundo avaliador**, e a concordância humano × TypeSafe é ela mesma uma métrica a acompanhar.

---

## 7. Mesa de testes — fluxo de tela

Rota proposta: **`/lab/criativo`** (padrão das demais páginas de lab: `@admin_required`, fora do nav). `/studio/lab` fica no blueprint do produto do cliente — evitar.

```
┌ Marca ▾ (Workspace)  · auditoria: 14 campos verificados · política: [verificados ▾]    custo hoje US$ 0,42 / teto 5 ┐
├───────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────┤
│ TAREFA  ( Gerar | Editar )    │  RESULTADO (um por vez)                                                               │
│ Template: 02 produto + logo ▾ │  ┌───────────────┐  modelo · provider · profile v3 · 23,4 s · US$ 0,041              │
│ Instrução (pt-BR)             │  │   imagem      │  AdaptationPlan: 2 nativas · 1 em texto · logo → composer         │
│ Referências (arrastar):       │  └───────────────┘  TypeSafe: texto ✓ 0,93 · paleta 7/10 · ref produto: parcial       │
│  [mockup·COMPOSITION] [produto]│  Falha principal: reference_ignored → sugestão: …   [Aceitar como proposta]          │
│  [logo·LOGO] [pessoa·PERSON]  │  Notas humanas (cego) 1–5 …                                                           │
│ Director Prompt (editável)    │──────────────────────────────────────────────────────────────────────────────────────│
│ Modelo ▾  qualidade ▾  ratio ▾│  HISTÓRICO do experimento (cards: modelo, custo, tempo, nota) → comparar 2            │
│ Prompt adaptado (somente ver) │                                                                                        │
│ [ Estimar US$ ]  [ Gerar 1 ]  │                                                                                        │
└───────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────┘
```

- "Um por vez": cada clique = 1 run, 1 modelo, 1 imagem. Comparação nasce do histórico, não de disparo em lote. (Lote fica para a Fase 3.)
- Gerar = t2i com refs opcionais. Editar = imagem-base obrigatória (`role: BASE`) + instrução de mudança + `preserve`/`alter` (mesmo contrato do Trocr). Modelos com `input_references.max = 0` aparecem desabilitados para Editar.
- Pessoa: upload marcado `PERSON` exige checkbox de consentimento de uso de imagem; recusa do provider por pessoa real vira status `blocked_by_provider`, não erro genérico.

---

## 8. Modelo de dados (ajustado às convenções do repo)

Prefixo do repo é `cx_` para tabelas de criação. Proposta: `cx_lab_model_catalog`, `cx_lab_experiments`, `cx_lab_prompt_versions`, `cx_lab_runs`, `cx_lab_evaluations` (TypeSafe + observadores, separado de ratings), `cx_lab_ratings`, `cx_lab_pairwise`, `cx_lab_profile_proposals` (= `lab_presets` do brief, mas para o manifesto do modelo).
Imagens: `instance/creative_media/lab/<experiment>/<run>.png` + URL pública assinada só quando precisar virar referência. Retenção 90 dias. Migração SQL em `migrations/add_creative_lab.sql` + runner — **aplicar só com confirmação explícita** (o banco é o remoto de produção).

---

## 9. Riscos e dúvidas em aberto

1. **Banco = produção.** Todo experimento grava no banco remoto. Tabelas isoladas `cx_lab_*`, sem FK de escrita em tabelas do Studio.
2. **LGPD / terceiros.** Assets de marca de cliente e fotos de pessoas vão para OpenRouter → provedores (OpenAI, Alibaba, Recraft…). Precisa: flag por marca "não enviar ao Lab", registro de qual asset foi a qual provider, consentimento para `PERSON`. Qual cliente pode entrar no teste?
3. **Orçamento.** Teto diário e por experimento — que valor? Sugestão: US$ 5/dia, US$ 1/experimento sem confirmação.
4. **"Enriched mockup"** (estratégia D do Reference Test) — sem definição; fica placeholder até o dono definir.
5. **TypeSafe em pt-BR** tem precisão menor: state e perguntas em inglês, textos da marca vão como dados.
6. **Observador visual** é mais um modelo com viés. Fixar o modelo (ex. `openai/gpt-5-mini`) e versioná-lo; nunca o mesmo modelo que gerou a imagem.
7. `usage.cost` do OpenRouter para imagem ainda não confirmado em chamada paga.

---

## 10. Plano de fases (revisado com o pedido do dono)

| Fase | Entrega | Aceite |
|---|---|---|
| **1 · Núcleo** | `creative_lab/` (catálogo sync, manifestos JSON dos 4 modelos, CapabilityResolver, AdaptationPlan, conector OpenRouter próprio + OpenAI direto), fila `cx_lab_runs` (claim/lease), página `/lab/criativo` com marca do Workspace, Gerar 1 imagem, custo e tempo | gpt-image-2 Direct × OpenRouter + Qwen 3 Pro + Recraft 4.1 rodados 1 a 1; `npm run test:studio` verde |
| **2 · Referências + Editar** | upload com roles (logo, produto, pessoa, mockup, style), modo Editar, AdaptationPlan visível, BrandSnapshot com `payload_policy` | mesma tarefa com/sem logo nativo mostra o plano correto |
| **3 · Validação** | Observadores + TypeSafe por run, notas humanas cegas, pareado, sugestões de ajuste por modelo (`pending_review`) | 10 runs avaliados com concordância humano × TypeSafe medida |
| **4 · Prompt/Reference Test + ampliação** | versões de Director Prompt com diff, lote N amostras, teto de orçamento, +6 modelos OpenRouter | ranking por `task_type` com n mostrado |
| **5 · Higgsfield** | adapters, quando o dono liberar | — |

**Parar aqui e aguardar aprovação.**
