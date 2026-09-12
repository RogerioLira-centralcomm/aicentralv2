# Trocar (Trocr)

Editor generativo de criativo a partir de **uma imagem de entrada**. Troca um item da peça — headline, apoio, preço, CTA, pessoas, fundo — e guarda cada tentativa no histórico.

A mesa vive em `/parametros/modelagem-criativos/trocar`. Na tela o produto se chama **Trocr**. O chrome da Modelagem não muda.

Não é a Mesa de Conceito 15s. Não monta roteiro, não fecha HTML de canal e não recorta camadas. Uma foto basta.

Documento de UX da tela: [`docs/trocr-editor-refactor.md`](trocr-editor-refactor.md). Este arquivo é o contrato: fluxo, payload, prompts, modos e limites.

Diagnóstico e plano de incrementos: [`docs/trocar-reliability.md`](trocar-reliability.md). Em conflito com o código, vale o símbolo citado lá.

---

## 1. O que a funcionalidade faz

1. O usuário solta um still (PNG ou JPG).
2. Visão LLM lê textos e análise (não é Tesseract).
3. A mesa preenche headline, apoio, datas, local, preço e CTA.
4. O usuário marca o que **preservar** e o que **alterar**, e pode escrever uma instrução livre.
5. O servidor escolhe a rota em `build_swap_plan()`:
   - **noop** — nada para trocar. 200, sem PNG, sem versão.
   - **blocked** — conflito sem confirmação, ou typeset sem região (`REQUIRE_REGION` ligado).
   - **typeset** — Pillow pinta o tipo na foto. Sem Image 2. Custo zero.
   - **recrop** — Image 2 só vira o formato; Pillow pinta o tipo depois.
   - **image** — GPT Image 2 redesenha o still.
6. A imagem gerada entra no histórico como nova versão. A original não some.
7. **Usar como base** troca a referência da próxima edição e relê o OCR.

Autenticação: `admin_required` na página, `admin_required_api` nas rotas JSON.

---

## 2. Tecnologias

| Camada | Tecnologia | Onde |
|---|---|---|
| Página | Flask + Jinja | `modelagem_desk("trocar")` |
| CSS | `modelagem_criativos.css` | `?v=96` no desk |
| Cliente | `mc-trocar.js` (IIFE, sem framework) | `static/js/mc-trocar.js` |
| OCR | OpenRouter `openai/gpt-4o-mini` visão | `read_swap_reference` |
| Imagem | OpenRouter `openai/gpt-image-2` | `swap_reference` modo `image` / `recrop` |
| Typeset | Pillow (PIL) | `_paint_typeset` |
| Fonte do tipo | Avenir Next Condensed → Arial Bold → DejaVu → default | `_typeset_font` |
| Marca | `build_brand_context` + logo oficial | `_swap_brand` |
| Persistência | `brand_profile.trocr` + arquivo + memória | `_read_trocr` / `_write_trocr` |
| Stills | `save_trocr_still` → `GET /swap/still/<arquivo>` (auth); legado em `/static/uploads/creative_generated/` | `_persist_still` |
| Auth LLM | `resolve_api_key()` (integração OpenRouter ou `OPENROUTER_API_KEY`) | generator da modelagem |
| Custo | `annotate_cost` (USD + BRL) | `creative_modeling_fx` |

Variáveis de ambiente:

| Variável | Default | Uso |
|---|---|---|
| `CREATIVE_FORMAT_SWAP_READ_MODEL` | `openai/gpt-4o-mini` | OCR |
| `CREATIVE_FORMAT_SWAP_READ_TEMPERATURE` | `0` | OCR |
| `CREATIVE_FORMAT_SWAP_READ_MAX_TOKENS` | `1200` | OCR |
| `OPENROUTER_API_KEY` | — | fallback se a integração não resolver |
| `USD_BRL_RATE` | cotação dinâmica | quote em reais |
| `CREATIVE_FORMAT_SWAP_STRICT_PLAN` | ligado | hash do preview tem de bater na geração |
| `CREATIVE_FORMAT_SWAP_REQUIRE_REGION` | ligado | typeset sem bbox bloqueia; confirmar não fura |

O Image 2 está fixo em `SWAP_MODEL = "openai/gpt-image-2"`. Não há modelo de rascunho mais barato ainda.

---

## 3. Mapa de arquivos

```
aicentralv2/creative_format_lab/swap.py          núcleo: OCR, prompt, risco, modos, typeset
aicentralv2/creative_format_lab/swap_schema.py   contrato Pydantic + adaptador legado
aicentralv2/creative_format_lab/swap_plan.py     plano único, hash, conflitos, no-op
aicentralv2/creative_format_lab/service.py       FormatLabService.swap / read_swap / preview / history
aicentralv2/creative_modeling_service.py         fachada para as rotas
aicentralv2/creative_modeling_routes.py          HTTP
aicentralv2/creative_format_lab/engineer.py      reusa o OCR do Trocr no lab 15s
aicentralv2/templates/parametros/_mc_trocar.html página
aicentralv2/templates/parametros/trocr/*         canvas, inspetor, versões, estados
aicentralv2/static/js/mc-trocar.js               store e fluxo
aicentralv2/static/css/modelagem_criativos.css   visual
tests/test_creative_format_lab.py                CreativeFormatLabSwapTest
tests/test_modelagem_criativos.py                desk e rotas
```

Partials da tela:

| Componente | Arquivo |
|---|---|
| Página | `_mc_trocar.html` |
| Etapas | `trocr/_flow_sidebar.html` |
| Canvas / comparar | `trocr/_canvas.html` |
| Inspetor | `trocr/_inspector.html` |
| Textos | `trocr/_ocr_fields.html` |
| Análise | `trocr/_analysis.html` |
| Preservar / alterar | `trocr/_preserve_alter.html` |
| Prompt | `trocr/_prompt.html` |
| Geração | `trocr/_generate.html` |
| Versões | `trocr/_versions.html` |
| Erro / toast | `trocr/_states.html` |
| Lab visual | `/lab/trocr/states` (fora do nav) |

---

## 4. Fluxo do usuário

```
Upload → OCR → Análise → Edição → Geração → Revisão
```

1. **Upload.** Drop zone ou file input. A imagem vira `v1 · Original`. Se o usuário não escolheu formato, o cliente estima 16:9 / 9:16 / 4:5 / 1:1 pela proporção do arquivo.
2. **OCR.** O cliente redimensiona o lado longo para 1280 px (JPEG 0.82) só para a leitura. A geração usa a imagem cheia. `POST /swap/read`.
3. **Análise.** Checkboxes de fundo, imagens, grafismo, logo, título, secundário, CTA e apoios. Selos `role=person`, datas, local e `logo_text` viram **locks** (“Fica na peça”).
4. **Edição.** Campos editáveis + preservar/alterar + nota livre + formato + qualidade. `POST /swap/prompt` a cada ~220 ms (debounce). A UI mostra o preview em português; o Image 2 recebe o prompt em inglês.
5. **Geração.** Rascunho ou produção chama `POST /swap`. Steps visuais: Análise → Montagem do prompt → Geração → Finalização.
6. **Revisão.** Nova versão no histórico. Comparar, zoom, download, tela cheia. **Usar como base** invalida o cache daquela versão e relê.

Ver uma versão só muda o canvas. Não relê. Duplicar copia imagem e contexto, sem IA.

Estados da faixa: `upload`, `ocr`, `analysis`, `edit`, `generate`, `review`. Erro acionável: tentar de novo, editar insumos, voltar.

---

## 5. Versões

IDs `v1`, `v2`, `v3`… Toda geração faz `push`. Teto no servidor: 60 versões.

| Campo | Papel |
|---|---|
| `activeId` | o que o canvas mostra |
| `baseId` | referência da próxima edição (`baseVersion()`) |
| `origin` | `original` · `edited` · `draft` · `production` · `typeset` · `recrop` |
| `parent_id` | versão de origem (`baseId` no momento da geração) |
| `revision` | CAS do histórico no servidor |

Regras:

- A original não exclui — a UI esconde o botão e o servidor recolocá se o POST omitir ou tentar trocar o PNG.
- Nenhuma geração substitui a anterior.
- `revision` divergente → 409; a mesa recarrega o histórico.
- Trocar a marca persiste o histórico atual e carrega o da nova marca.
- Sem marca, a chave é o usuário (`user-{id}`).
- Still novo não vai para URL estática pública. Legado `/static/uploads/creative_generated/` continua válido.

Origens na UI:

| `origin` | Nome na tira |
|---|---|
| `original` | Original |
| `typeset` | Tipo na foto |
| `recrop` | Recorte + tipo |
| `draft` | Rascunho |
| `production` | Produção |

---

## 6. Rotas de geração

A função `build_swap_plan(payload)` escolhe a rota **antes** de chamar o modelo. `swap_mode()` só decide typeset/recrop/image.

```
se não há alteração efetiva, nota, force_image, override nem recrop
    → noop
senão se typeset sem região (REQUIRE_REGION, default ligado)
    → blocked
senão se aspect_hint ≠ aspect_ratio e há patches de tipo
    → recrop
senão se force_image
    → image
senão se alter ⊆ {headline, secondary, cta, price}
    → typeset
senão
    → image
```

`needs_recrop` compara `aspect_hint` (lido no still) com `aspect_ratio` (saída pedida). Sem `aspect_ratio`/`output`, `resolve_aspect_ratio` usa `ratio_from_size(ref_width, ref_height)`, depois o hint, depois `16:9`.

### 6.1 Risco alto (`swap_risk`)

High quando **preserva pessoas** (ou ≥4 faces / selos `person`) **e** altera tipo (`headline`, `secondary`, `cta`, `price`).

Motivo: cartela de elenco. O Image 2 embaralha português nos selos (`Mumuzinho` → `Mumuzinho` com letra extra, `Entrada franca` → `Entradada franceça`).

Type-only (só headline/apoio/CTA/preço) também cai em typeset, mesmo sem elenco. O checkbox **Redesenhar a peça no Image 2** (`force_image`) força o modo `image`.

### 6.2 Typeset (Pillow)

Sem Image 2. `quote.estimated_cost_usd = 0`, `model = "typeset"`. Se o payload traz `regions`/`bbox_px` do mesmo tamanho da referência, a pintura fica recortada nessa caixa e `qa.status` vem `pass` ou `fail`. Sem região, `qa.status` é `unchecked` e o slot legado continua.

1. `typeset_patches` monta slots a partir de `alter`. Se `alter` tem `cta` e há 2+ elements `role=cta` com texto, sai um patch por pill com o próprio `bbox_px`.
2. `_slots_for` escolhe a grade. Em 16:9, se o tipo está em cima/esquerda (`TYPESET_SLOTS_TOP`), usa essa grade; senão a grade “tipo no centro/direita”.
3. `_canvas_field` acha a cor de campo (luma &lt; 232 — navy entra, branco do tipo não).
4. `_locate_type` procura glifos no slot (cromáticos ou claros).
5. `_cover_type` pinta **só os pixels do glifo** (raio 4), não o retângulo inteiro — para não comer a pessoa.
6. `_draw_copy` escreve o texto novo, fonte condensada, ink contrastante. CTA usa a tinta amostrada quando há `cover` — não força mais `(17, 17, 17)`. Headline larga (`width/height ≥ 2.4`) alinha à esquerda.

Slots 16:9 (tipo à direita / centro):

| Slot | x, y, w, h (fração) |
|---|---|
| headline | 0.40, 0.14, 0.36, 0.34 |
| secondary | 0.40, 0.52, 0.34, 0.16 |
| cta | 0.76, 0.34, 0.20, 0.28 |
| price | 0.40, 0.70, 0.30, 0.10 |

Slots 16:9 topo (`TYPESET_SLOTS_TOP`) — TIM Black, tipo à esquerda:

| Slot | x, y, w, h |
|---|---|
| headline | 0.04, 0.10, 0.50, 0.28 |
| secondary | 0.04, 0.40, 0.22, 0.22 |
| dates | 0.50, 0.08, 0.28, 0.20 |
| price | 0.16, 0.40, 0.26, 0.20 |
| cta | 0.04, 0.78, 0.40, 0.14 |

Há grades também para 9:16, 4:5 e 1:1.

`typeset_all` só pinta headline/apoio/preço extra se o payload pedir. Recrop **não** liga mais esse atalho.

### 6.3 Recrop

Image 2 recebe um prompt só de recorte: mesma pessoa, guarda-roupa, luz e campo de marca. **Não** manda as linhas novas no prompt do Image 2. Depois `typeset_reference` pinta headline / apoio / preço / CTA no still recortado.

Passes: `["image", "typeset"]`. Custo = cotação do Image 2 (o typeset é de graça).

### 6.4 Image

Uma passagem Image 2. Até 2 referências: still + logo oficial (produção, ou se `use_brand_context` não for falso). Se `logo` está em `preserve`, a logo oficial **não** entra.

---

## 7. APIs

Todas sob `/parametros`. Envelope: `{ "success": true, "data": { ... } }`. Erro: `{ "success": false, "message": "..." }`.

### 7.1 `POST /parametros/api/format-lab/swap/read`

Lê o still. Sem `text_callable` (chave ausente) devolve `status: unavailable`, não 500 nem leitura vazia “ok”. JSON inválido → `invalid`. Provedor caiu → `provider_error`. Sem texto útil → `unreadable`. Overflow → `partial`.

**Request**

```json
{
  "reference": "data:image/jpeg;base64,...",
  "strict": false
}
```

Aceita também `image` ou `reference_url` (`https://` / `http://` / `data:image/`).

`strict: true` usa `READ_STRICT_SYSTEM` (glifo a glifo, não corrige português). O lab 15s chama assim. A mesa Trocar não envia `strict`.

**Response (`data`)**

```json
{
  "headline": "Internet extra que cabe no mês",
  "support": "ATÉ 110GB",
  "subtitle": "",
  "price": "R$ 169,99/mês",
  "cta": "Conferir planos",
  "disclaimer": "",
  "logo_text": "TIM",
  "dates": "",
  "venue": "",
  "aspect_hint": "16:9",
  "style": "fundo azul-marinho, pessoa à direita, tipo à esquerda",
  "elements": [
    { "id": "face_01", "role": "person", "kind": "face", "text": "", "note": "modelo à direita", "source": "ocr" },
    { "id": "logo_01", "role": "logo", "kind": "logo", "text": "TIM", "note": "canto superior esquerdo", "source": "ocr" }
  ],
  "faces": 1,
  "locks": ["TIM"],
  "locks_overflow": false,
  "overflow": [],
  "analysis": {
    "background": true,
    "images": true,
    "graphic": false,
    "logo": true,
    "headline": true,
    "secondary": true,
    "cta": true,
    "supports": true
  },
  "status": "completed",
  "error": ""
}
```

Limites de truncagem no servidor: headline 80, support 160, price 40, cta 40, até 20 elements.

Roles válidos: `logo`, `headline`, `support`, `cta`, `product`, `price`, `person`, `background`, `graphic`.

O cliente manda a imagem **downscalada**. O servidor não redimensiona de novo.

### 7.2 `POST /parametros/api/format-lab/swap/prompt`

Monta prompt + preview + quote + risco **sem gerar**.

**Request** — mesmo corpo de `editFields()` no JS (sem `reference` obrigatório):

```json
{
  "client_id": 12,
  "brand_name": "TIM",
  "headline": "Internet extra que cabe no mês",
  "support": "ATÉ 80GB",
  "price": "R$ 149,90/mês",
  "cta": "Assine agora",
  "note": "Manter a modelo e o navy.",
  "instruction": "Manter a modelo e o navy.",
  "aspect_ratio": "16:9",
  "aspect_hint": "16:9",
  "dates": "",
  "venue": "",
  "subtitle": "",
  "elements": [{ "role": "person", "text": "", "note": "direita" }],
  "faces": 1,
  "force_image": false,
  "presentation": "final",
  "quality": "production",
  "use_brand_context": true,
  "preserve": ["layout", "people", "logo", "colors", "style"],
  "alter": ["price"],
  "prompt_override": null
}
```

`note` e `instruction` são o mesmo campo da UI (`#mcSwapNote`).

**Response**

```json
{
  "prompt": "Edit the attached advertising reference. …",
  "preview": "Edite o criativo preservando a identidade visual da marca TIM. …",
  "quality": "production",
  "aspect_ratio": "16:9",
  "quote": {
    "estimated_cost_usd": 0,
    "cost_usd": 0,
    "spent_brl": 0,
    "model": "typeset",
    "passes": 0,
    "quality": "typeset"
  },
  "risk": { "level": "high", "reason": "Cartela com elenco. …" },
  "mode": "typeset",
  "locks": ["24, 25 e 26 de julho", "Mineirinho", "TIM"],
  "plan_id": "pln_ab12cd34ef56",
  "plan_hash": "…sha256…",
  "planner_version": "trocr-plan-4",
  "operations": [{"field": "price", "from": "R$ 169,99/mês", "to": "R$ 149,90/mês"}],
  "conflicts": [],
  "noop": false,
  "blocked": false
}
```

Se `prompt_override` vier preenchido, `prompt` é esse texto (até 4000 chars). A UI só envia override se o usuário editou o box ou clicou **Usar prompt**.

### 7.3 `POST /parametros/api/format-lab/swap`

Gera a versão.

**Request** — `editFields()` + `quality` + `reference` da base ativa (imagem **cheia**, não o JPEG 1280).

**Response** (campos comuns)

```json
{
  "prompt": "…",
  "preview": "…",
  "reference": "data:image/png;base64,…",
  "logo_used": false,
  "aspect_ratio": "16:9",
  "quality": "typeset",
  "model": "typeset",
  "mode": "typeset",
  "risk": { "level": "high", "reason": "…" },
  "patches": [{ "slot": "price", "text": "R$ 149,90/mês" }],
  "png_data_url": "data:image/png;base64,…",
  "image_url": "/static/uploads/creative_generated/….png",
  "quote": { "…" },
  "brand_name": "TIM"
}
```

`image_url` só existe se `save_generated_base64` gravou. A UI aceita `image_url` **ou** `png_data_url`.

No modo `recrop` entram `passes: ["image", "typeset"]`.

No modo `image`, `quality` é `draft` ou `production`; `patches` não vem.

No modo `noop`: `png_data_url` vazio, `model: noop`, sem `image_url`, sem gravar versão. Hash obsoleto ou conflito sem `confirm_conflicts` → 409.

### 7.4 `GET|POST /parametros/api/format-lab/swap/history`

**GET** `?client_id=12` — carrega a sessão.

**POST** — persiste (debounce 400 ms no cliente). Mandar `revision` da última leitura. Sem `revision` o legado ainda grava (incrementa). Com `revision` errada → 409.

```json
{
  "client_id": 12,
  "active_id": "v3",
  "base_id": "v1",
  "aspect_ratio": "16:9",
  "revision": 2,
  "versions": [
    {
      "id": "v1",
      "attempt": 1,
      "name": "Original",
      "origin": "original",
      "quality": "",
      "status": "ready",
      "created_at": "2026-09-12T10:00:00.000Z",
      "image": "data:image/png;base64,…",
      "thumb": "data:image/jpeg;base64,…",
      "parent_id": "",
      "ocr": { "headline": "…", "analysis": {} },
      "analysis": {}
    }
  ]
}
```

O servidor converte data URL em still autenticado (`/parametros/api/format-lab/swap/still/<hex>.png`) e devolve `image_url` / `thumb_url` / `revision` / `parent_id`. Data URLs não ficam no `brand_profile`. OCR/analysis são slim: sem `png_data_url` nem strings `data:`.

URL remota (`http`/`https`) não entra no histórico. Original omitida ou com PNG trocado é restaurada a partir da sessão gravada.

Chave: `client-{id}` se há marca; senão `user-{user_id}`. Com marca, também espelha em `user-{id}`.

### 7.5 `GET /parametros/api/format-lab/swap/still/<arquivo>`

Still privado. `admin_required_api` + cookie. Nome `32 hex` + `.png|.jpg|.webp`. Arquivo em `instance/trocr_stills/`, fora de `/static`. `<img src>` same-origin envia a sessão.

### 7.6 `POST /parametros/api/format-lab/quote`

```json
{ "kind": "swap", "quality": "production", "...editFields" }
```

Devolve o `quote` do `build_swap_plan`. Sem `kind: swap` a rota cotiza o lab de conceito 15s. No-op / bloqueado: `image_api_cost_usd: 0`, `label: Sem geração`.

Estimativas:

| Modo / qualidade | USD | Model |
|---|---|---|
| typeset | 0.00 | `typeset` |
| image draft | 0.14 | `openai/gpt-image-2` |
| image / recrop production | 0.22 | `openai/gpt-image-2` |

---

## 8. Payload do cliente (`editFields`)

Montado em `mc-trocar.js`. É o contrato da mesa.

| Campo | Origem | Notas |
|---|---|---|
| `client_id` | `#mcSwapClient` | opcional |
| `brand_name` | nome do cliente selecionado | |
| `headline` | `#mcSwapHeadline` | max 80 |
| `support` | `#mcSwapSupport` | max 160 |
| `price` | `#mcTrocrPrice` | max 40 |
| `cta` | `#mcSwapCta` | max 40; segundo botão em `#mcTrocrCta2` → `elements[].role=cta` |
| `note` / `instruction` | `#mcSwapNote` | mesmo valor |
| `dates` | `#mcTrocrDates` | independente de `subtitle` |
| `subtitle` | `#mcTrocrSubtitle` | não copia datas |
| `logo_text` | `#mcTrocrLogo` | texto da marca no quadro |
| `disclaimer` | `#mcTrocrDisclaimer` | texto legal visível |
| `venue` | `#mcTrocrVenue` | |
| `aspect_ratio` | rádio `mcSwapOut` | 16:9 · 9:16 · 4:5 · 1:1 |
| `aspect_hint` | último OCR | detectado, não o pedido |
| `elements` | OCR | lista crua |
| `faces` | `elements` com `kind=face` | selo de nome não conta |
| `force_image` | `#mcTrocrForceImage` | força Image 2 |
| `presentation` | rádio apresentação | só chrome do canvas (`final` / `mobile` / `portal` / `ctv`) |
| `quality` | rádio qualidade | `draft` · `production` |
| `use_brand_context` | `#mcTrocrBrandContext` | default true |
| `preserve` | checkboxes | ver tokens |
| `alter` | checkboxes | ver tokens |
| `prompt_override` | textarea se editado/travado | senão omitido |
| `reference` | `baseVersion().image` | só em `/swap` e `/read` |
| `base_id` | versão-base da mesa | entra no hash no lugar do PNG |
| `plan_hash` | último preview | se vier, tem de bater |
| `confirm_conflicts` | `#mcTrocrConfirmConflicts` | não entra no hash |
| `ref_width` / `ref_height` | still natural | obrigatório para validar a bbox |
| `regions` | seleção no canvas | `{ price: [x0, y0, x1, y1] }` |

Tokens **preserve**: `layout`, `background`, `people`, `product`, `logo`, `text_position`, `colors`, `graphic`, `style`.

Tokens **alter**: `price`, `cta`, `headline`, `secondary`, `people`, `product`, `background`, `colors`, `graphic`.

`TYPE_ONLY` = `{headline, secondary, cta, price}`. Typeset só roda se o risco é high **e** `alter` está contido nesse conjunto.

Locks no servidor (`apply_swap_schema`): selos `kind=name_pill`, `logo_text`, `disclaimer`, `dates` e `venue`. Acima de 12 a lista **não** é cortada; `locks_overflow` fica verdadeiro (não se mistura com texto longo). Copy acima do limite gera erro na geração; no OCR vira `overflow[]` sem corte. `kind` inválido cai em `face`/`name_pill`/`type`. IDs repetidos viram o próximo livre (`cta_02`). Bbox sem `ref_width`/`ref_height` não é inventada.

---

## 9. Prompts

Há **três** textos. Não misturar.

### 9.1 OCR — `READ_SYSTEM`

Visão. Temperatura 0. User: *“Leia os elementos editáveis deste still.”* + imagem.

```
Você lê um still de anúncio. Extraia só o que está visível.
Não invente oferta, preço, nome ou slogan. Copy em português do Brasil exatamente como aparece, com acento.
Cartela de evento: cada selo de nome é um element role=person. Datas vão em dates. Local vai em venue.
O grito da peça (É de graça, Entrada franca, etc.) vai em support ou cta — nunca some.
Bandeirola, fitas ou padrão repetido = graphic true.
style descreve o que se vê (cor do campo, luz, recorte). Nunca repita estas instruções.
Se um texto estiver ilegível, deixe vazio. Não corrija português. Retorne JSON puro:
{ headline, support, subtitle, price, cta, disclaimer, logo_text, dates, venue,
  aspect_hint, style, elements[{role,text,note}], analysis{…} }
```

`READ_STRICT_SYSTEM` acrescenta:

```
VALIDAÇÃO: transcreva glifo a glifo. Se o still escreveu Mumuzinho ou franceça, copie o erro.
Não normalize para o nome famoso nem corrija acento.
```

### 9.2 Prompt do Image 2 — `build_optimized_prompt` (inglês)

Uma string. `prompt_override` curto-circuita tudo.

Núcleo (modo `image`, sem `alter`):

1. Edit the attached advertising reference. Keep the same composition, crop, hierarchy and number of frames.
2. Swap only the advertised brand, product and copy. Do not redesign the layout.
3. All visible text must be Brazilian Portuguese.
4. Spell every visible line exactly as written below. Do not scramble, hyphenate, invent or auto-correct Portuguese.
5. Do not invent a new visual effect: no neon light trails, sci-fi streaks, extra glow, lens flares or futuristic overlays that are not in the reference.
6. Keep the original lighting, color grade, materials and photography. Do not add a new light ribbon or energy streak.
7. Do not add player chrome, app UI or extra frames that are not in the reference.
8. Draft *or* production fidelity.
9. Output aspect ratio X. Recrop and rebalance composition for that frame.
10. Preserve exactly: … / Change only: …
11. Locks com contagem de letras: `Mumuzinho (Mumuzinho=9)`.
12. Paint each locked string glyph by glyph…
13. Brand / color / logo / tom / forbidden.
14. Copy: se o plano tem operações com `from ≠ to`, só essas linhas entram (`Headline exactly` + `Replace only the line '…'`). Senão o dump legado de headline/apoio/preço/CTA.
15. Nota livre do usuário.

Se há `alter`, o item 2 vira: *This is an item swap. Change only the listed items…*

Se `people` está em preserve: não redesenhar selos; typeset só as linhas de Change only.

Modo **recrop** substitui o núcleo:

```
Recrop the attached advertising still to the output frame. Keep the same person, wardrobe, lighting and brand color field.
Do not redesign the campaign. Do not invent a new effect, UI chrome or extra frame.
A later typesetting pass will replace headline, price, quota and CTAs. Prefer a clean field behind the type.
Do not invent a new offer, number or Portuguese line. If type must stay, clone it — do not add zeros to prices or quotas (199,90 not 1999,90; 1700 not 17000).
```

Sem as linhas `Headline exactly` — o typeset posterior escreve o tipo.

### 9.3 Preview da UI — `build_prompt_preview_pt` (português)

O que o textarea mostra. Não é o que o Image 2 recebe, salvo override. Se o plano tem operações com `from ≠ to`, o preview lista só essas trocas (`'linha velha' → 'linha nova'`), não o dump de preço/CTA intactos.

Exemplo typeset TIM:

```
Edite o criativo preservando a identidade visual da marca TIM.
Preserve layout, pessoas, logo, cores, estilo visual.
Altere preço.
Headline: 'Internet extra que cabe no mês'.
Apoio: 'ATÉ 110GB'.
Destaque o bloco de preço 'R$ 149,90/mês'.
CTA: 'Conferir planos'.
Formato de saída 16:9.
Versão de produção, alta fidelidade.
Tipo composto na foto. Elenco e selos ficam iguais à referência.
```

Recrop acrescenta: *O Image 2 só vira o formato. Preço, quota e headline entram na foto depois.*

---

## 10. Contexto de marca

Se `use_brand_context` não for `false` e houver `client_id`:

- `build_brand_context(client)` — nome, cor, tom, forbidden, `creative_line.gpt_image_instruction`.
- Logo oficial (`_official_logo_data_url`) entra como **segunda referência** do Image 2.
- O prompt manda: *Image 2 is the official brand logo lockup. Place that exact mark where the old logo sat.* Não typesetar o nome jurídico no lugar da marca.

Sem logo, pede o mark oficial pelo nome.

---

## 11. QA de copy (`score_swap_copy`)

Usado em testes e loops de lab — a mesa não chama na geração.

Mede se locks sobreviveram, se linhas proibidas vazaram, se números inflaram (`199,90` → `1999,90`) e se o blob parece embaralhado.

`looks_scrambled` dispara em:

- letra repetida 3+ vezes
- `entradada`, `franceça`, `franceca`, `graçça`, `vaqueiroo`
- `famíliaía`, `familiaia`, `planoso`, `contratator`, `conferir plan`

---

## 12. Relação com o resto da Modelagem

| Desk | Papel vs Trocar |
|---|---|
| Mesa / Lab 15s | Conceito com cenas. Reusa `read_swap_reference(..., strict=True)` se o still estiver anexado (`apply_still_read`). |
| Camadas | Recorta pessoa / papel / tipo. Sem Image 2 no default. Não gera versão de anúncio. |
| Bancada | HTML no retângulo de mídia. Trocar entrega still, não layout. |
| Placas | Sistema da marca, não edição de um still. |

O Trocar **não** entra no pipeline `pipeline.py` de 15s. É um atalho: referência + um item.

---

## 13. Testes

Classe `CreativeFormatLabSwapTest` em `tests/test_creative_format_lab.py`.

Cobertura principal:

- prompt pede português e proíbe neon
- Image 2 recebe referência + logo
- sem logo, uma referência só
- OCR parseia JSON e analysis
- cartela de elenco → typeset, Image 2 **não** roda
- typeset 16:9 não pinta a elipse da pessoa
- recrop: Image 2 depois typeset
- números inflados e `looks_scrambled`
- preview PT + histórico da mesa (`tests/test_modelagem_criativos.py`)

Fixture de cartela: `tests/fixtures/creatives/arraial-1x1.png`.

Rodar só o núcleo:

```bash
python -m unittest tests.CreativeFormatLabSwapTest -q
```

---

## 14. Lab desta sessão (set/2026)

Peça: still TIM Black 16:9 (110GB, R$ 169,99, CTAs Conferir planos / Contratar).

O que rodou de verdade:

| Passo | O que usamos | O que não usamos |
|---|---|---|
| OCR da mesa | precisava de OpenRouter | chave não resolveu neste ambiente |
| OCR do script | transcrição local (`READ0`) | gpt-4o-mini ao vivo |
| Geração | **typeset Pillow** em 4 edições | Image 2 (sem chave) |
| Preview da mesa | Flask `127.0.0.1:5078/.../trocar` | — |

Quatro typesets a partir do original:

1. Preço → `R$ 149,90/mês`
2. Headline → `Internet extra que cabe no mês`
3. Apoio → `ATÉ 80GB`
4. CTA → `Assine agora`

Fix commitado nesta linha: o recorte de campo parte da pele/navy e o typeset **não preenche o slot inteiro** (`_cover_type`). Teste: `test_typeset_16x9_nao_pinta_a_pessoa`.

Limites que o lab ainda viu no TIM Black 16:9:

- fantasma da headline antiga (cobertura de glifo incompleta)
- quota 80GB pode cair no slot errado se `secondary` / `dates` se misturam
- CTA não clonava o par de pills — **fase 5:** dois `role=cta` com bbox viram dois patches; mesa tem `#mcTrocrCta2`
- fontes do ERP (família TIM) não entram no Pillow; Avenir/Arial aproximam
- sem chave, a mesa mostra erro de OCR e deixa editar na mão; typeset continua possível

Scripts de lab ficaram em `/tmp` (`trocr_black_lab.py` e afins). Não entram no git.

---

## 15. Exemplo ponta a ponta (typeset)

Usuário solta o Black, marca **Pessoas / Logo / Cores / Estilo**, marca **Preço**, troca o campo para `R$ 149,90/mês`, clica produção.

1. `POST /swap/read` → `aspect_hint: 16:9`, `price: R$ 169,99/mês`, `faces ≥ 1`.
2. `POST /swap/prompt` → `mode: typeset`, `quote: $0`, preview em PT.
3. `POST /swap` com `preserve: [people, logo, colors, style]`, `alter: [price]`, `force_image: false`.
4. `swap_risk` = high. `alter ⊆ TYPE_ONLY`. Pillow pinta só o preço.
5. UI faz push `v2 · Tipo na foto`. Histórico POST.

Para forçar Image 2 no mesmo caso: marcar **Redesenhar a peça no Image 2**. Custo ~US$ 0,22. Risco de embaralhar tipo e selos.

Para virar 9:16: escolher Stories. `needs_recrop` → Image 2 recorta → typeset pinta as linhas. Sem chave, essa rota falha; typeset no mesmo aspect continua.

---

## 16. Limites conhecidos e próximos passos

Já no refactor de UX, ainda válidos:

- slider before/after
- upload multipart em vez de data URL
- modelo mais barato de rascunho
- cancelar job de geração

Do typeset, depois deste lab:

- inferir a segunda pill se o OCR só devolve um CTA (hoje precisa de 2 elements + bbox)
- slots 16:9 TIM (quota vs preço vs headline) com detector menos cego
- fonte da marca no Pillow, não só Avenir
- coverage de glifo com dilatação maior para matar fantasma
- OCR local de fallback quando a chave não resolve (hoje a mesa só falha e deixa o campo vazio)

---

## 17. Como operar sem inventar

- Typeset **não** redesenha pessoa, logo nem grafismo. Só cobre glifos e escreve.
- Image 2 **pode** redesenhar tudo, inclusive o que o prompt pediu para travar. Por isso cartela vai para typeset.
- O preview PT é didático. O modelo lê o inglês (ou o override).
- `presentation` não muda o PNG. É moldura no canvas.
- `quality` no typeset é ignorada (sempre `typeset`).
- Sem `OPENROUTER_API_KEY` / integração, OCR e Image 2 não rodam; typeset roda se a referência for data URL.
