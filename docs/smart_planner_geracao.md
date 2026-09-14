# Smart Planner — geração de documentos

Auditoria do fluxo que monta a **página única** e o **planejamento completo**: tela, motores GPT, prompts, processamento e fontes. Código lido em `aicentralv2/smart_planner/` (setembro 2026).

Todas as chamadas de texto passam pelo OpenRouter (`chat_completion` em `ai.py`). Imagem, quando existisse no pipeline, usaria `openai/gpt-image-2` (`CREATIVE_IMAGE_MODEL`). Override global: `SMART_PLANNER_MODEL` só substitui `draft`, `improve`, `final`, `sheet` e `compose`.

---

## 1. A tela “Gerar documentos” gera o quê?

### O que o usuário vê

Não existe mais uma página viva em `/smart-planner/<token>/gerar`. A rota **redireciona para a revisão**. O botão **Gerar documentos** (rodapé da revisão) faz isto:

1. Exige objetivo e ao menos um canal (senão foca o campo).
2. Salva a revisão (`POST /smart-planner/api/<token>/revisao`).
3. Abre o diálogo `#sp-gen`: **Página única** ou **Planejamento completo**, com prévia de custo.
4. Chama `POST /smart-planner/api/<token>/gerar` com `{ plan_mode }`.
5. Overlay “Gerando…” e redirect para `/conclusao`.

A seção HTML `step_id == 'gerar'` ainda existe no `wizard.html` (tabela de seções + passos), mas **não é alcançada** — o bloco `canais`/`gerar` é morto de propósito (rotas redirecionam).

### O que o backend realmente faz

`planner.run_generation(token, mode)`:

| Escolha | Chamadas reais | Persistência |
|---|---|---|
| `one_page` | 1× mercado + monta a folha (`materialize_folha`) | `dados.folha`, `plan_content` = folha, `geracao.passes = 1` |
| `completo` | 1× mercado + monta a folha (se ainda não houver) + 3 passagens de markdown + 1× quadro | `mercado`, rascunhos, `planejamento`, `plan_content` = quadro 4 seções, `geracao.passes = 3` |

A folha **sempre** entra no completo como tese (`## Página única` no pack do plano). O diálogo está certo nesse ponto.

### Veredito: gera corretamente?

**Texto e estrutura: sim, com ressalvas.** O POST chega, o modo é gravado, a conclusão aponta para o quadro interno e (se houver) o link público. O completo usa a folha e não a contradiz no prompt do quadro.

**Não bate com o que a UI / prévia promete:**

1. **Imagens da folha não rodam na geração.** `images.apply_sheet_art` existe, tem teste isolado, e **ninguém chama** em `build_one_page`, `materialize_folha` ou `run_generation`. A skill e o passo “Imagens da folha” da tela morta mentem. Pitches prontos usam PNG estático; folha gerada por IA fica com `image_prompt` e sem `image_url` exclusivo.
2. **Papel `sheet` (gpt-5.4) nunca é usado.** A folha usa `draft` → `improve` → `final` (mini + 5.4 + 5.4), ou **zero LLM** se casar um pitch (Montana Grill, BH Airport, BDMG, Minas Máquinas).
3. **Prévia de custo** (`preview_steps`): one_page = mercado + sheet; completo = mercado + sheet + draft + improve + final + compose. O real não inclui `sheet` e, no one_page com pitch, nem as 3 passagens. Completo com pitch paga mercado + 3 planos + compose, sem as 3 da folha.
4. **`geracao.passes = 1` na one_page** mesmo quando a folha rodou 3 chats.
5. Overlay do JS fala “Escrevendo a tese…” no completo e “Montando a folha…” na one_page — não lista mercado / passagens / quadro.

O quadro interno (`/canvas`) **não é externo**. O link público (`/smart-planner/p/<token>`) é o documento do cliente.

---

## 2. Motores (papéis)

Defaults em `models.ROLES`. Cada um tem `temperature`, `top_k`, `max_tokens` e USD estimado para prévia.

| Papel | Label | Modelo default | Temp | Max tokens | Onde entra de verdade | Só na prévia? |
|---|---|---|---|---|---|---|
| `extract` | Extrair campos | `openai/gpt-5-mini` | 0.1 | 4000 | Processar briefing | — |
| `narrative` | Redigir briefing | `openai/gpt-5-mini` | 0.2 | 6000 | Processar / rebrief | — |
| `digest` | Resumir referência | `openai/gpt-5-nano` | 0.15 | 700 (busca sobe a 1800) | Busca sem Firecrawl | — |
| `review` | Revisar referência | `openai/gpt-5-mini` | 0.1 | 2000 | Toda URL / PDF / imagem / busca capturada | — |
| `vision` | Ler imagem | `openai/gpt-5-mini` | 0.1 | 1800 | Upload PNG/JPG/WEBP | — |
| `market` | Mercado | `openai/gpt-5-mini` | 0.2 | 2500 | **Sempre** no `run_generation` | — |
| `draft` | Passagem 1 | `openai/gpt-5-mini` | 0.3 | 8000 | Folha (sem pitch) **e** plano completo | — |
| `improve` | Passagem 2 | `openai/gpt-5.4` | 0.2 | 8000 | Folha (sem pitch) **e** plano completo | — |
| `final` | Passagem 3 | `openai/gpt-5.4` | 0.1 | 8000 | Folha (sem pitch) **e** plano completo | — |
| `compose` | Montar quadro | `openai/gpt-5-mini` | 0.15 | 5000 | Só `completo` (`generate_canvas`) | — |
| `sheet` | Redigir folha | `openai/gpt-5.4` | 0.2 | 2500 | **Ninguém chama** | Sim |
| imagem | GPT Image 2 | `openai/gpt-image-2` | — | — | Função pronta, **fora do POST /gerar** | UI morta |

Timeout: texto 90s; draft/improve/final do **plano** sobem a 120s. Folha usa o default 90s.

---

## 3. Tabela de prompts e o que o processamento faz

Ordem = jornada do usuário, não ordem alfabética.

### 3.1 Captura de referências (passo 1, antes de gerar)

| ID | Arquivo | Papel | System / essência | User / material | Processamento detalhado | Saída |
|---|---|---|---|---|---|---|
| R1 | `references.REVIEW_SYSTEM` + JSON | `review` | Revisa apoio de mídia. Joga fora menu, cookie, rodapé, CTA, markdown. Prosa PT. Não inventa verba/KPI/cliente/prazo/marca. Só JSON. | Tipo, rótulo, lista de campos do `FIELD_SCHEMA`, material cru até 20k. Pede `notas`, `fatos`, `papel` (`marca\|campanha\|mercado\|visual`). | Roda depois de scrape/PDF/visão/busca. Se o cru tem &lt; 80 chars, pula o modelo e devolve o texto. Busca força `papel=mercado`. | `notas` limpas, `fatos` só se o material afirmar, papel. |
| R2 | `references.search_web` (fallback) | `digest` | Resume dados públicos de mercado para plano de mídia. | “Pesquise dados atuais sobre: {query}”. Resumo factual PT, fontes nomeadas. Não inventa verba/KPI/audiência. Opcional: 800 chars do briefing. | Só se **não** houver Firecrawl útil. Prefixa `Fonte: conhecimento do modelo, não é página capturada.` | Texto de mercado sintético. |
| R3 | `references._read_image` | `vision` | Transcreva texto visível e o que importa para mídia. Não invente verba/KPI/marca ausente. | Imagem em data-URL. | Upload PNG/JPG/JPEG/WEBP. Depois cai no R1. | Transcrição + descrição. |
| — | Firecrawl (sem prompt GPT) | — | — | URL ou 2 hits da busca | Scrape `onlyMainContent` markdown, 40s, até 40k. Fallback HTML se não houver chave. PDF: PyPDF2/pypdf, 40 páginas, 40k. | Texto cru para R1. |

Papel default por tipo: URL → marca; arquivo → campanha; imagem → visual; busca → mercado.

### 3.2 Processar briefing (`POST .../processar`)

| ID | Constante | Papel | Prompt | Material que entra | Processamento | Saída persistida |
|---|---|---|---|---|---|---|
| B1 | `extract_fields` (inline) | `extract` | Extrator CentralX. Lista `FIELD_SCHEMA` + ids de canal + dispositivos. Copia campos já confirmados (`pistas`: cliente, agência, brand seed). JSON: `campos`, `score` 0–100, `bem_definido`, `falta_completar`. Nunca inventa. Canal só se o texto citar. Score pesa objetivo, público, verba, período, praça. | System: “responde apenas JSON”. User: prompt + `--- MATERIAL ---` até 40k. | `compose_material`: bloco “Briefing do usuário” + cada “Notas de apoio (kind: label) — papel …”. Pistas da Modelagem/CRM vencem cliente/agência; canais da seed **somam** aos extraídos. `apply_support_facts`: fatos das refs preenchem campo vazio; busca **não** pode gravar verba, KPIs, cliente, período, campanha, agência. | `analise_ia`, `quality_score`, colunas da sessão (cliente, objetivo, budget…). |
| B2 | `NARRATIVE_PROMPT` | `narrative` | Redator de briefing. Markdown fiel. Não inventa verba/prazo/canal/público/praça. Títulos `##` curtos. Preserva restrições. Sem agência/ferramenta/IA. | Campos já estruturados como verdade + origem (“texto do usuário”, “usuário + apoio”, “só refs”, ou rebrief) + material 40k. | Reescreve o dossiê numa narrativa única. | `briefing_compilado` = `briefing_melhorado`. |
| B3 | mesmo B2, origem diferente | `narrative` | Idem | Material original (`fonte.briefing` ou `input_text_original`) + campos **já parametrizados** (mix, verba, objetivo da revisão). | `rewrite_from_plan` / “Refazer briefing”. Mix da mesa vale mais que o rascunho antigo. | Sobrescreve os dois briefings. |

`input_text_original` permanece o texto cru do usuário. Chrome de URL não volta para o textarea.

### 3.3 Página única (`one_page.build_one_page` via `materialize_folha`)

Dois caminhos **mutuamente exclusivos**:

**A — Pitch estático** se `match_pitch(cliente, agência, briefing)` achar alias (montana, desafio, confins, bdmg, minas máquinas, staloin, etc.). **Nenhum chat.** Cards e `image_url` vêm de `STARTER_PITCHES`. Tema e densidade também.

**B — Três passagens JSON** (`_sheet_from_material`) se não houver pitch.

| ID | Constante | Papel | Prompt | User | Processamento | Schema |
|---|---|---|---|---|---|---|
| F1 | `ONE_PAGE_PROMPT` | `draft` | Redige folha para o **cliente final**, não a agência. Só JSON. Recomendação ≤ 2 frases. Criativo *no* canal. `stat` = número ou palavra de decisão; % sem lastro = premissa. Defesa fecha a reunião. Usa verba/canais/voo. Sem agência herói, sem CentralComm no texto, sem IA. Identidade da marca é verdade. | “Passagem 1 — rascunho das quatro peças.” + JSON do material. | Material: cliente, agência, presenter, `brand_prompt_block`, briefing 8k, planejamento 8k (vazio na 1ª geração), `campanha` (canais, mix, verba, praça, período, objetivo), `apoio` 6k. | `strategy`, `creative` (channel, surface `ctv\|portal\|app\|display`, `image_prompt`), `market` (stat, stat_label), `defense`. |
| F2 | `SHEET_IMPROVE` = F1 + “passagem 2, aprofunde sem mudar o schema, feche o mix” | `improve` | Idem | Material 8k + rascunho JSON 8k | Aperta tese ao voo/mix. | Mesmo JSON. |
| F3 | `SHEET_FINAL` = F1 + “passagem 3, versão final, aperte, sem peça oca” | `final` | Idem | Material 8k + documento 8k | Se o JSON falhar, cai no improve, depois no draft. | Mesmo JSON. |

Depois (sem modelo de texto):

- Logos: `cx_clients.logo_url` / `logo_upload_path`, senão `cliente_web_info.logo_url`, agência pelo vínculo.
- Presenter: CentralComm apoio (padrão) ou Serasa / Amazon / Logan como principal. Se principal, substitui “CentralComm” no body.
- Tema: família food/travel/finance/agro por alias ou pitch; fundo **estático** `bg-*.png`.
- Share + QR: `public_token`.
- `image_prompt` **não** vira imagem neste fluxo.

### 3.4 Mercado (todo `run_generation`)

| ID | Constante | Papel | Prompt | Material | Processamento | Saída |
|---|---|---|---|---|---|---|
| M1 | `MARKET_PROMPT` | `market` | Analista de mídia BR. Até 8 bullets: categoria, concorrência típica, consumo de mídia, risco de verba. Número sem fonte = Premissa. Sem agência, ferramenta, audiência inventada. | Briefing 18k + bloco campanha + identidade Modelagem + apoio revisado. | Roda **antes** da folha e do plano. | `dados.mercado` (markdown). |

### 3.5 Planejamento completo (markdown, 12 seções)

Pack `_pack`: briefing 28k (passagem 1) ou 12k (2 e 3) + configuração da campanha + marca + **folha já escrita** + apoio + `## Dados de mercado`.

Bloco campanha (determinístico, sem LLM): canais com label/desc do catálogo, R$ e % do mix, praça, verba, período, objetivo, método, **voo mensal** (menor no começo, maior no meio e no fim).

| ID | Constante | Papel | Prompt | User | Processamento | Seções obrigatórias `##` |
|---|---|---|---|---|---|---|
| P1 | `PLAN_PROMPT` | `draft` | Planejador sênior BR, white-label, executável. Verba/%/voo são **lei**. Sem dado: “A definir” ou “Premissa:”. Nunca inventa prazo de produção, CPM, impressão ou responsável. Sem agência, consultoria, ferramenta, IA. | “Passagem 1 — rascunho. Cubra todas as seções.” + pack | Markdown normalizado. Vazio → erro. | Capa; Visão Geral (≤ 4 linhas); Objetivos e KPIs (SMART); Território e Praça; Inteligência de Audiência; Modelagem e Segmentação (tabela 6 cols); Estratégia e Mix (Canal \| % \| R$ \| Papel \| Justificativa, soma = verba); Números e Performance (sem CPM); Direção Criativa (sem cronograma); Fases do Voo (colunas mensais); Premissas; Próximos Passos (≤ 5, responsável “A definir”). |
| P2 | `IMPROVE_PROMPT` | `improve` | Aprofunda rascunho. Devolve o documento inteiro, sem comentários. Fecha números com verba e voo. Corta repetição. Não inventa. Sem agência/IA. | Pack (briefing 12k, **sem** lastro de mercado neste corte) + `## Rascunho` 28k | Se o chat falhar, mantém o draft. | Mesmo doc. |
| P3 | `FINAL_PROMPT` | `final` | 3ª passagem — o que o anunciante lê. Markdown limpo. Confere soma da verba, voo, KPI sem lastro = Premissa. Corta jargão e seção oca. | Pack 12k + `## Documento` 28k | Grava `planejamento_rascunho`, `planejamento_passagem2`, `planejamento`. | Mesmo doc. |

`review_plan` é alias de `finalize_plan`.

### 3.6 Quadro do plano completo

| ID | Constante | Papel | Prompt | User | Processamento | Schema |
|---|---|---|---|---|---|---|
| Q1 | `CANVAS_PROMPT` | `compose` | Monta o quadro a partir do briefing e do planejamento. Só JSON. Não inventa verba/canal/KPI. Body = o que fazer, peso, por quê. Completo: 4 seções, 2–3 cards. 1º card de strategy = recomendação em uma frase. Se houver voo, um card de media descreve as colunas. Marca = verdade. `pagina_unica` = tese; aprofundar, não contradizer. | JSON: plan_mode, meta, marca, briefing 12k, planejamento 20k, pagina_unica (texto dos cards), campanha. | `normalize_plan`: no máx. 6 cards/seção. | `context`, `strategy`, `media`, `execution`. Types: summary, kpi-group, allocation, audience, channel-mix, recommendation, creative, next-steps, table. |

One_page **não** chama Q1. O canvas da folha é o JSON da folha.

### 3.7 Imagem (código morto no /gerar)

| ID | Função | Modelo | Prompt | Quando deveria rodar | Estado |
|---|---|---|---|---|---|
| I1 | `theme.bg_prompt` / default | `openai/gpt-image-2` | Wash atmosférico 16:9, sem texto/logo/pessoa. | Fundo exclusivo se o `bg_url` ainda for o PNG de família. | Não chamado. |
| I2 | `creative.image_prompt` / default | idem | Mockup do anúncio *no* canal, logo do herói, sem agência. 4:3 app, 16:9 resto. | Card creative sem `image_url`. | Não chamado. |

---

## 4. Fontes de informação — folha menor vs plano maior

As duas bebem do **mesmo dossiê**. O completo **acrescenta** camadas; não troca a verdade.

### 4.1 Fontes comuns (os dois modos)

| Fonte | Origem | Como entra | O que o modelo pode usar | Travas |
|---|---|---|---|---|
| Texto do usuário | Textarea / `fonte.briefing` / `input_text_original` | Narrativa + pack | Objetivo, público, restrições, tom | Não some no processar |
| Referências revisadas | URL (Firecrawl), PDF, imagem (visão), busca | `apoio` / `apoio_notes`, fatos no extract | Marca, oferta, prova, mercado | Busca não sobrescreve verba/KPI/cliente/prazo/campanha/agência |
| Mesa da revisão | `campanha`: canais, mix, verba, base, período, praça, KPIs, objetivo, método | Bloco determinístico + JSON da folha | Lei para % e R$ | Executivo manda mais que o briefing antigo |
| Voo / ritmo | `pace.campaign_pace` | Colunas mensais no bloco campanha | Fases; menor–maior | Sem período não inventa semanas |
| Identidade Modelagem | `brand_for_client(crm_id)` → `brand_prompt_block` | nome, setor, tom, resumo, público, produtos, oportunidades, direção, canais | Posicionamento | Seed preservada (`preserve_seed`) |
| CRM / logos | `tbl_cliente`, `cx_clients`, `cliente_web_info`, vínculo agência | Branding da folha, não prosa | Nome e logo reais | Sem logo = nome; não inventa URL |
| Catálogo de canais | `CHANNEL_CATALOG` | Labels e desc no bloco | Papel do meio | Só ids válidos |
| Método de mix | `mix.py` (funil, alcance, frequência, eficiência, presença, manual) | `campanha.mix` + `canais_verba` | Justificativa do peso | Soma 100% na mesa |
| Presenter | `presenter_brand` | meta + troca de voz | Tom da folha | CentralComm some se outra marca for principal |
| Mercado gerado (M1) | GPT-5-mini neste run | `dados.mercado`; pack do **P1** | Categoria / risco | Premissa se não houver fonte |

### 4.2 Só a página única (menor)

| Fonte | Uso |
|---|---|
| `STARTER_PITCHES` | Se o nome casar, **substitui** o LLM: strategy, creative, market, defense, partners, theme, PNGs. Briefing/mix ainda vão no material se cair no caminho B, mas no A o pitch vence o texto. |
| Tema de mercado | Fundo e barras de densidade (premissa do pitch, não KPI). |
| `planejamento` já existente | Recorte 8k no material da folha se o completo rodou antes (regenerar folha). Na 1ª geração está vazio. |
| Skill / pitches João | Montana (Amazon/CTV), BH Airport (Logan/portal), BDMG (Serasa), Minas Máquinas (Serasa + geolocal). |

A folha **não** recebe as 12 seções do markdown. Não pede tabelas de segmentação, impressões ou próximos passos. Não chama `compose`.

### 4.3 Só o planejamento completo (maior)

| Fonte | Uso |
|---|---|
| Folha (tese) | `_folha_block` + `pagina_unica` no quadro. “Aprofunde, não contradiga.” |
| `dados.mercado` | Só na passagem 1 do markdown (`_pack(..., lastro)`). Improve/final **não** reenviam o lastro (só briefing + campanha + marca + apoio + rascunho). |
| Documento P1 / P2 | Cada passagem seguinte relê o markdown anterior (28k). |
| Quadro | Lê o markdown final 20k + folha em texto + briefing 12k. Produz cards, não um segundo plano longo. |

O completo é “folha + mercado + três redações longas + compressão em 4 seções”. Por isso a prévia custa mais e o diálogo avisa que a folha sai primeiro.

### 4.4 O que nenhum dos dois usa

- Não há API de audiência, CPM, DV360 ou CRM de mídia em tempo real.
- Não há web search **na hora do /gerar** (só se o usuário buscou no passo 1).
- Não há tabela PHP legado no prompt (só o contrato antigo no comentário do planner).
- Impressões / alcance no markdown, se existirem, devem nascer como **Premissa** — o modelo não consulta mediabuy.
- `apply_sheet_art` / GPT Image 2 fora deste POST.

---

## 5. Pipelines lado a lado

```
Revisão salva
    │
    ├─ one_page
    │     M1 mercado
    │     Folha: pitch estático  ──ou──  F1 draft → F2 improve → F3 final
    │     plan_content = folha
    │     [imagens: não rodam]
    │
    └─ completo
          M1 mercado
          Folha (igual acima, se ainda não existir)
          P1 draft → P2 improve → P3 final   (markdown 12 seções)
          Q1 compose                         (quadro 4 seções)
          plan_content = quadro
          folha permanece em dados.folha
```

### Tokens aproximados no pack

| Recorte | One page (B) | Completo P1 | Completo P2/P3 | Quadro |
|---|---|---|---|---|
| Briefing | 8k | 28k | 12k | 12k |
| Planejamento prévio | 8k | — | — | 20k |
| Apoio | 6k | 8k | 8k | (via folha + campanha) |
| Folha | — | texto dos cards | texto dos cards | `pagina_unica` |
| Mercado M1 | não vai para F1–F3 | sim | não | não |
| Campanha + brand | sim | sim | sim | sim |

---

## 6. Campos que o extrator pode achar (`FIELD_SCHEMA`)

`campanha`, `cliente`, `agencia`, `objetivo` (enum do funil), `objetivo_texto`, `contexto`, `publico`, `praca` (nacional / interior / geolocalizada), `praca_detalhe`, `verba`, `periodo`, `canais[]`, `criativos`, `dispositivos[]`, `kpis[]`, `observacoes`, `nao_informado[]`.

Canais válidos: Google Ads, GPT ADS, YouTube, Meta, TikTok, LinkedIn, DV360 (rede de portais), Spotify, Netflix, Prime Video, Disney+, Max, Globoplay, Serasa mídia, Serasa dados (não entra no mix de verba), G1, UOL, R7, CNN, OOH.

---

## 7. Arquivos

| Peça | Arquivo |
|---|---|
| Papéis e prévia | `smart_planner/models.py` |
| OpenRouter | `smart_planner/ai.py` |
| Briefing | `smart_planner/processor.py` |
| Refs | `smart_planner/references.py`, `materials.py` |
| Folha | `smart_planner/one_page.py` |
| Plano 12 seções | `smart_planner/planner.py` |
| Quadro | `smart_planner/canvas.py` |
| Arte (órfã no /gerar) | `smart_planner/images.py` |
| Mix / voo | `smart_planner/mix.py`, `pace.py` |
| Marca / logos | `smart_planner/brand.py`, `logos.py` |
| POST gerar | `smart_planner/routes.py` → `api_gerar` |
| Diálogo | `templates/smart_planner/wizard.html`, `static/js/smart_planner/wizard.js` |

---

## 8. Correções se a geração tiver que “bater” com a tela

1. Chamar `apply_sheet_art(plan)` no fim de `materialize_folha` (e decidir se pitch estático também regenera fundo).
2. Ou aposentar o papel `sheet` na prévia e contar `draft+improve+final` da folha — e o atalho de pitch (US$ 0 extra de texto).
3. Mandar `dados.mercado` também nas passagens 2 e 3 do completo, se a pesquisa tiver que sobreviver ao corte.
4. Apagar ou religar o step `gerar` no wizard para não documentar um fluxo morto.
5. Overlay do JS: mercado → folha → (completo: 3 passagens + quadro).
)
