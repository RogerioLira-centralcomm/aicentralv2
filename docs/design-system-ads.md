# Design System Ads — Advertising Operating System

Documentação completa da mesa **Design System Ads** no CentralX: contrato, fluxos de **marca** e **campanha**, payloads, prompts, modelos e profundidade operacional.

> Isto **não** é o design system do site nem o tema DaisyUI do ERP. É o **Advertising Operating System** da marca: como ela se comporta em 300×250, 728×90, 970×250, 320×50, feed 1:1 / 4:5 e LinkedIn.

```text
Brand DNA
  → tokens de mídia
  → componentes de anúncio (P0–P3)
  → fundo (papel | lavagem | imagem)
  → adapter IAB
  → regras da IA
```

Mesa em produção:

[https://ai.centralcomm.media/parametros/modelagem-criativos/design-system](https://ai.centralcomm.media/parametros/modelagem-criativos/design-system)

---

## 1. O que a funcionalidade faz

A mesa monta, revisa e aprova a **linha de anúncio** de uma marca (ou de uma campanha que herda essa tinta) e a **recompõe** em formatos IAB/sociais — sem resize cego.

Uma peça de anúncio precisa de:

| obrigatório | preferido | proibido |
|---|---|---|
| tinta aprovada (`ink` / `paper` / `accent`) | fundo da campanha (lavagem ou imagem) | resize cego |
| logo com respiro | lifestyle ou packshot no poço visual | card SaaS, pílula, cream/terracotta, acid green |
| produto ou marca reconhecível | um ousado só (headline ou recorte) | chrome do ERP como tinta |
| copy curta + CTA 4.5:1 | | copy longa, produto minúsculo, legal ilegível |
| recompor por formato | | |

O specimen é o **anúncio**, não a folha do site. `970×250` não encolhe para `320×50`: P2 e P3 vão ao **poço visual**.

---

## 2. Superfície e rotas

### 2.1 Página da mesa

| | |
|---|---|
| URL | `/parametros/modelagem-criativos/design-system` |
| Produção | `https://ai.centralcomm.media/parametros/modelagem-criativos/design-system` |
| Desk | `MC_DESKS["design-system"]` em `creative_modeling_routes.py` |
| Template | `templates/parametros/_mc_design_system.html` |
| JS | `static/js/mc-design-system.js` |
| CSS | `static/css/modelagem_criativos.css` + tokens `--dsa-*` |

A mesa tem **uma superfície**: catálogo da marca à direita + palco IAB (iframe) ao centro. O palco abre ao clicar formato ou arquétipo.

Ações do topo:

- **Montar a marca** — cria o rascunho se faltar e roda o loop (DNA → contraste → review → trilhas).
- **Montar campanha** — herda a tinta, muda copy, linha e recortes.
- **Aprovar** — fecha o rascunho da marca (`status: approved`). Campanha não aprova.

### 2.2 Specimens (HTML da peça)

| URL | Quem |
|---|---|
| `/lab/design-system/marca/<client_id>?format=iab-billboard&layers=6` | marca |
| `/lab/design-system/campanha/<campaign_id>?format=iab-billboard&layers=8` | campanha |

Query: `format`, `layers` (4–40), `highlight` (id da camada marcada na lista).

Presets da casa:

- marca `centralcomm` → CentralComm Ads
- campanha `centralcomm-verao` → Verao

### 2.3 APIs (blueprint `/parametros`)

Todas exigem admin (`@admin_required_api`). Prefixo: `/parametros/api`.

#### Marca

| método | rota | o que faz |
|---|---|---|
| `GET` | `/design-system/brand/<client_id>` | lê o sistema (ou sugere sem persistir) |
| `POST` | `/design-system/brand/<client_id>` | materializa e grava o rascunho |
| `POST` | `/design-system/brand/<client_id>/loop` | um passo do loop contínuo |
| `POST` | `/design-system/brand/<client_id>/compose` | compose DNA + copy no OpenRouter |
| `POST` | `/design-system/brand/<client_id>/refine` | intent local **ou** refino com modelo |
| `POST` | `/design-system/brand/<client_id>/tokens` | patch de tokens / copy / DNA / arquétipo |
| `POST` | `/design-system/brand/<client_id>/tracks/<track_id>` | gera packshot / KV / lifestyle / wash |
| `POST` | `/design-system/brand/<client_id>/approve` | `status = approved` |
| `GET`/`POST` | `/design-system/brand/<client_id>/adapt` | recompõe no formato IAB |

#### Campanha

| método | rota | o que faz |
|---|---|---|
| `GET` | `/design-system/campaign/<campaign_id>` | lê (ou sugere herança da marca) |
| `POST` | `/design-system/campaign/<campaign_id>` | herda marca, compose da temporada, grava |
| `GET`/`POST` | `/design-system/campaign/<campaign_id>/adapt` | recompõe no formato IAB com recortes |

---

## 3. Tecnologias

| camada | tecnologia | onde |
|---|---|---|
| Backend | Flask + Pydantic (`DesignSystemAds`) | `aicentralv2/design_system_ads/` |
| Persistência marca | `cx_clients.brand_profile.design_system_ads` + `cx_brand_visual_systems` | JSONB |
| Persistência campanha | `cx_campaigns.creative_brief.design_system_ads` | JSONB |
| Chat (compose / review / refine) | OpenRouter `chat_completion` | `services/openrouter_service.py` |
| Compose / review | `openai/gpt-4o` | env `DESIGN_SYSTEM_ADS_COMPOSE_MODEL` |
| Refine de tokens | `openai/gpt-4o-mini` | env `DESIGN_SYSTEM_ADS_MODEL` |
| Imagem das trilhas | OpenRouter Images · `openai/gpt-image-2` | fundo opaco, até 2 `input_references` |
| CSS da peça | variáveis `--dsa-*` | compiladas no validator do schema |
| Tailwind | tema `dsa` em `static/css/tailwind/design-system.css` | `bg-dsa-paper`, `text-dsa-ink`, … |
| Tipo web | Google Fonts | specimen carrega a família extraída |
| Contraste | WCAG relativo, piso **4.5:1** | `ink` sobre `paper`, `cta_ink` sobre `accent` |
| Front da mesa | JS vanilla (IIFE) | `mc-design-system.js` |
| Preset da casa | tokens do tema `[data-theme="centralcomm"]` | teal `#1E4D4F`, ouro `#F3B71B` |
| Extract satélite | `extracted_design_system` / `normalized.json` | `ingest.py` |
| Formatos | catálogo do Format Lab | `creative_format_lab/catalog.py` |
| Skill do agente | `.agents/skills/design-system-ads/SKILL.md` | Advertising OS |

Env relevantes:

```bash
DESIGN_SYSTEM_ADS_COMPOSE_MODEL=openai/gpt-4o   # default
DESIGN_SYSTEM_ADS_MODEL=openai/gpt-4o-mini      # refine
OPENROUTER_API_KEY=...                          # chat + imagem
CREATIVE_IMAGE_MODEL=openai/gpt-image-2         # fallback global
```

Sem chave OpenRouter: o loop ainda anda com **seed local** (DNA a partir da evidência + copy da marca). Imagem de trilha exige chave.

---

## 4. Contrato — o payload `DesignSystemAds`

Framework: `design-system-ads`. Validado em `schema.py` (`DesignSystemAds`). Todo GET/POST da mesa devolve esse contrato **mais** metadados de catálogo (`payload_for`).

### 4.1 Campos persistidos

```json
{
  "framework": "design-system-ads",
  "id": "dsa-42-v1",
  "scope": "brand",
  "name": "Marca Ads",
  "source": "brand",
  "status": "draft",
  "version": 1,
  "client_id": 42,
  "logo_url": "https://…/logo.png",
  "tokens": {},
  "css_vars": {},
  "tailwind": {},
  "contrast": {},
  "ad_copy": {},
  "inherits_brand_id": null,
  "creative_line": "",
  "elements": [],
  "evidence": {},
  "dna": {},
  "backgrounds": [],
  "archetype": "brand",
  "rules": {},
  "tracks": [],
  "passes": [],
  "specimen_html": ""
}
```

| campo | valores | nota |
|---|---|---|
| `scope` | `brand` \| `campaign` | campanha herda tokens; muda copy e recortes |
| `status` | `draft` \| `approved` \| `archived` | só marca aprova na mesa |
| `source` | `brand` \| `extract-design-system` \| `tailwind-centralcomm` \| `campaign` | hierarquia de evidência |
| `archetype` | `brand` \| `product-hero` \| `lifestyle` \| `promotion` | escolhe fundo + formato default |
| `inherits_brand_id` | id do DS da marca | só campanha |

Defaults de token (validator):

| token | default | papel |
|---|---|---|
| `paper` | `#FFFFFF` | fundo sólido |
| `ink` | `#1E4D4F` | texto / sinal da marca |
| `accent` | = ink | fill do CTA |
| `muted` | `#3D4451` | apoio / legal |
| `cta_ink` | `#FFFFFF` | texto do botão |
| `highlight` | `#F3B71B` | acento — **nunca** CTA automático |
| `font-display` / `font-body` | `Inter` | título / apoio |
| `type-headline` | `72px` | escala master; o adapter IAB reduz |
| `type-support` | `28px` | |
| `type-cta` | `22px` | |
| `type-legal` | `14px` | |
| `cta-radius` | `0.25rem` | canto de anúncio, não pílula |
| `cta-pad` | `0.7em 1.2em` | miolo do botão |
| `cta-shadow` | `none` | |
| `safe` | `6%` | margem segura |
| `weight-display` | `700` | |
| `weight-cta` | `600` | |
| `tracking` | `-0.015em` | |
| `hairline` | = muted | filete |
| `ground` | `""` | URL da imagem de fundo |
| `ground-fit` | `cover` | |
| `ground-kind` | `paper` | `paper` \| `wash` \| `image` |
| `overlay` | `transparent` | véu sobre imagem/lavagem |
| `wash-strength` | `16%` | força da lavagem CSS |
| `grain` | `0.12` | |

Compilação automática no validator:

- `css_vars` — `--dsa-paper`, `--dsa-ink`, …
- `tailwind.theme.extend` — `colors.dsa.*`, `fontFamily.dsa-display`, `fontSize.dsa-headline`
- `contrast.pairs` — `ink_on_paper`, `cta_on_accent`; `passed` se ambos ≥ 4.5
- `backgrounds` — papel / lavagem / imagem
- `rules` — must / avoid / mandatory / park_first
- `tracks` — packshot, kv, lifestyle, wash
- `ad_copy` — limpa meta-copy e estoque

### 4.2 DNA

```json
{
  "name": "Acme",
  "personality": ["Acme em close", "filtro industrial", "tom técnico"],
  "must": ["logo de Acme com respiro", "CTA com 4.5:1"],
  "avoid": ["resize cego", "card SaaS"]
}
```

Traços genéricos **proibidos** na personalidade: `reconhecível`, `direta`, `de marca`.

### 4.3 Copy de anúncio

```json
{
  "headline": "A campanha chega inteira",
  "support": "Do cliente à tela, sem perder cor nem prazo.",
  "cta": "Começar agora",
  "legal": "CentralComm"
}
```

Limites por densidade IAB (`copy.fit_ad_copy`):

| densidade | headline | apoio | CTA | legal |
|---|---|---|---|---|
| compact | 32 | 0 | 14 | 22 |
| standard | 42 | 56 | 16 | 36 |
| rich | 56 | 80 | 18 | 48 |

Copy meta (sobre o laboratório) é descartada: `design system`, `tinta certa`, `herda o tema`, `Tailwind`, `ver o sistema`.  
Copy estoque também: `no primeiro olhar`, `Saiba mais`, `o que … promete, no tamanho do anúncio`.

### 4.4 Trilhas

| id | label | aspect | role | o que é |
|---|---|---|---|---|
| `packshot` | Produto | 1:1 | product | packshot recortável |
| `kv` | KV digital | 16:9 | ground | master com espaço para tipo |
| `lifestyle` | Lifestyle | 16:9 | visual | cena humana no mundo da marca |
| `wash` | Campo de tinta | 16:9 | ground | **CSS**, não foto de gradiente |

`wash` é lavagem: `overlay = color-mix(ink, wash-strength)`. GPT Image 2 **não** deve inventar campo de tinta.

Trilhas **obrigatórias** para o loop fechar: `packshot`, `kv`, `lifestyle`.  
`wash` é opcional.

### 4.5 Evidence / fidelidade

```json
{
  "source": "extract-design-system",
  "url": "https://marca.com",
  "sector": "Saneamento",
  "tone": "institucional",
  "summary": "…",
  "products": ["conta digital"],
  "palette": ["#0B3D2E"],
  "voice": { "density": "compact" },
  "assets": [{ "url": "…", "role": "product", "label": "pack" }],
  "reviewed": true,
  "fidelity": { "score": 0.88, "notes": [] }
}
```

O dossiê `compile_fidelity()` trava `paper/ink/accent/highlight`. Patch que muda de **família de cor** (hue > 35° ou delta RGB > 56) é descartado. Contraste 4.5:1 **escurece** a tinta; não a troca por teal da casa.

### 4.6 Payload da mesa (`payload_for`)

Além do contrato, a API devolve:

```json
{
  "exists": true,
  "preset": false,
  "table_html": "<table class='dsa-table'>…",
  "specimen_url": "/lab/design-system/marca/42?format=iab-billboard",
  "specimen_html": "…",
  "token_groups": [
    { "id": "cores", "label": "Cores", "tokens": [{ "id": "ink", "value": "#0B3D2E" }] }
  ],
  "intents": [
    { "id": "contrast", "label": "Contraste", "hint": "Tinta e leitura a 4.5:1." },
    { "id": "type", "label": "Tipo" },
    { "id": "cta", "label": "CTA" },
    { "id": "compact", "label": "Compacto" },
    { "id": "airy", "label": "Arejado" }
  ],
  "catalog": {
    "tagline": "Acme. filtro industrial, tom técnico.",
    "dna": {},
    "token_roles": [],
    "components": [],
    "iab_formats": [],
    "archetypes": [],
    "backgrounds": [],
    "effects": {},
    "flow": [
      { "id": "dna", "current": true, "done": false },
      { "id": "tokens" },
      { "id": "components" },
      { "id": "adapter" },
      { "id": "templates" },
      { "id": "rules" }
    ],
    "loop": {
      "step": "dna",
      "action": "compose",
      "track_id": "",
      "missing_tracks": [],
      "ready": false,
      "label": "Montar o DNA e a copy."
    },
    "curriculum": [],
    "training": []
  },
  "adapt": {
    "format": { "key": "iab-billboard", "width": 970, "height": 250, "density_tier": "rich" },
    "layer_count": 6,
    "layers": [],
    "well": { "x": 0, "y": 0, "w": 24, "h": 100 },
    "safe": { "pct": 5.0, "x": 5.0, "y": 5.0 },
    "tokens": { "type-headline": "34px" }
  },
  "layers": { "min": 4, "max": 40, "count": 6 },
  "elements": [],
  "creative_line": ""
}
```

---

## 5. Fluxo da MARCA

```text
cliente (logo, paleta, brand_profile, assets, extract?)
        │
        ▼
  materialize  ── CentralComm? → preset teal/ouro
        │         senão: paleta + fontes + extract
        ▼
  evidence + bind de trilhas (asset da marca antes de gerar)
        │
        ▼
  GET  → exists:false  (só sugere)
  POST → grava brand_profile + cx_brand_visual_systems
        │
        ▼
  loop (até 8 hops na mesa)
        compose  → DNA + copy (gpt-4o)
        contrast → heal 4.5:1 (local)
        review   → fidelidade (gpt-4o)
        track    → packshot / kv / lifestyle (gpt-image-2)
        rules    → compile_rules
        ready    → sistema pronto
        │
        ▼
  intents na mesa (contrast / type / cta / compact / airy)
  patch de tokens / DNA / copy (debounce 280ms)
        │
        ▼
  Aprovar → status approved
        │
        ▼
  Adapt IAB → specimen no iframe
```

### 5.1 Hierarquia de evidência

1. Sistema **aprovado** — não sobrescrever sem confirmação.
2. Preset CentralComm (`client_id = centralcomm` ou nome da casa).
3. `brand_profile.design_system_ads` / `cx_brand_visual_systems`.
4. Extract do site (`extracted_design_system`) → `ingest.py`.
5. `brand_profile` + `brand_dna` + logo + `brand_assets`.
6. Sem evidência: paper branco, ink da primária, fundo papel.

**Nunca** completar tinta faltante com teal da casa, salvo se a tinta extraída já for teal.

### 5.2 Materialização (`ensure_brand_design_system`)

1. Se já existe DS no profile → anexa evidência e devolve.
2. Se é CentralComm → preset Tailwind (`source: tailwind-centralcomm`, `reviewed: true`).
3. Senão:
   - DNA via `materialize_brand_dna`.
   - Paleta: `color_palette` → `primary_color` / `secondary_color`.
   - `ink = palette[0]`, `highlight = palette[1]`, `paper = #FFFFFF`, `accent = ink`.
   - Fontes do profile / DNA.
   - Se houver extract: `merge_extracted_tokens` (paper claro, ink legível, CTA 4.5:1, raio sem pílula) + `heal_contrast`.
4. `attach_client_evidence` — setor, tom, produtos, assets → trilhas.

### 5.3 Loop contínuo (`advance_loop` + `continueLoop`)

O backend avança **um** passo. A mesa (`Montar a marca`) chama `/loop` até 8 vezes.

| `loop.action` | passo do fluxo | o que roda |
|---|---|---|
| `compose` | dna | `compose_design_system` ou `seed_local_compose` |
| `contrast` | tokens | `improve_system("contrast")` |
| `review` | tokens | `review_fidelity` |
| `track` | components | mesa gera a trilha (`wash` é pulada — é CSS) |
| `rules` | rules | `compile_rules` |
| `ready` | templates | para; “Pronto. Abra um formato IAB.” |

Condições (nessa ordem):

1. Sem personalidade concreta, sem `must`, ou copy estoque → `compose`.
2. Contraste < 4.5 → `contrast`.
3. `evidence.reviewed` falso (exceto preset CentralComm) → `review`.
4. Falta URL em packshot/kv/lifestyle → `track`.
5. Sem `rules.must` → `rules`.
6. Senão → `ready`.

### 5.4 Intents locais (sem modelo)

`POST /refine` com `{ "intent": "contrast" }`. Sem `intent`, roda o refino com `gpt-4o-mini` (até 4 passes).

| intent | efeito |
|---|---|
| `contrast` | escurece ink; ajusta `cta_ink` / `accent` para 4.5:1 |
| `type` | `weight-display: 800`, tracking `-0.03em`, CTA 700 |
| `cta` | pad maior, raio `0.15rem`, sombra de mídia (toggle) |
| `compact` | `safe: 4%`, botão curto, tracking fechado |
| `airy` | `safe: 8%`, botão largo, tracking 0 |

### 5.5 Patch na mesa

`POST /tokens` — debounce 280 ms no input.

```json
{
  "tokens": { "ink": "#0B3D2E", "ground-kind": "wash", "wash-strength": "18%" },
  "ad_copy": { "headline": "…", "support": "…", "cta": "…", "legal": "…" },
  "dna": { "personality": "a, b, c", "must": "…", "avoid": "…" },
  "archetype": "product-hero"
}
```

Trocar arquétipo aplica o fundo correspondente e recompila `rules`.

### 5.6 Geração de trilha

`POST /tracks/<packshot|kv|lifestyle|wash>`

1. Monta prompt (`prompt_for_track`) com tinta, DNA, produto, setor, tom.
2. Anexa até 2 referências reais (produto/cena + logo) — lavagem não usa foto.
3. `generate_image` · `openai/gpt-image-2` · aspect da trilha · `background: opaque`.
4. Grava PNG em storage; atualiza `tracks[].url`.
5. KV vira `ground-kind: image`. Wash só aplica overlay CSS.

### 5.7 Adapt IAB da marca

```json
{
  "format": "iab-billboard",
  "layers": 6,
  "swaps": [["layer-headline", "layer-cta"]],
  "archetype": "brand"
}
```

Devolve o mesmo payload + `adapt.layers` (caixas `%`, z-index, parked, asset). O iframe recarrega `/lab/design-system/marca/<id>?format=…&layers=…`.

---

## 6. Fluxo da CAMPANHA

```text
campanha (nome, objective, campaign_text, cta_text, assets, campaign_pack)
        │
        ▼
  DS da marca  (cria se POST e a marca ainda não tem)
        │
        ▼
  herda TODOS os tokens
  scope = campaign
  inherits_brand_id = brand.id
  creative_line = oferta / objective
  elements[] = até 40 recortes (pack + assets)
  bind recortes → trilhas kv / lifestyle
        │
        ▼
  compose_campaign  (gpt-4o)  — NÃO reescreve ink/paper/accent
        creative_line
        ad_copy da oferta
        archetype (product-hero | lifestyle | promotion | brand)
        tracks kv + lifestyle com a linha da temporada
        ground-kind
        │
        ▼
  grava em creative_brief.design_system_ads
        │
        ▼
  Adapt IAB  → recortes entram no poço / roles
```

### 6.1 O que a campanha pode mudar

| herda da marca (travado) | muda na campanha |
|---|---|
| `paper`, `ink`, `accent`, `highlight` | `ad_copy` (oferta) |
| logo | `creative_line` |
| DNA / regras de tinta | arquétipo (promo ≠ institucional) |
| fontes e CTA shape | `ground-kind` (papel / lavagem / imagem) |
| | trilhas KV e lifestyle da temporada |
| | `elements[]` — recortes empilhados |

### 6.2 Origem dos recortes (`collect_campaign_elements`)

Ordem:

1. extras passados pelo service (`list_campaign_assets`)
2. `creative_brief.design_system_ads.elements` já gravados
3. `campaign_pack.sources[]` (`asset_url`, `name`)
4. `campaign.assets[]`

Roles inferidas por hint: `product`, `icon`, `chip`, `visual`. Sem hint: primeiro = `visual`, resto = `ornament-N`. Máximo = 40 (`MAX_LAYERS`).

`layer_count` default da campanha = `max(4, len(elements) + 3)`.

### 6.3 Copy da campanha (seed, sem modelo)

Headline: `headline` → extract.headline → bancada.title → primeira linha de `campaign_text` → nome.  
Apoio: extract.subhead/offer → objective → creative_line.  
CTA: `cta_text` → extract.cta → `Reservar`.  
Legal: da marca, senão o nome da campanha.

### 6.4 Preset Verao

`campaign_id = centralcomm-verao`:

```json
{
  "id": "centralcomm-verao",
  "name": "Verao",
  "headline": "Verao na linha certa",
  "cta_text": "Reservar",
  "creative_line": "Calor no visual, teal no CTA, ouro so no destaque."
}
```

---

## 7. Prompts

Todo chat vai em JSON. O user content é o **advertising brief** + `ask`. Até 4 imagens de referência (logo + assets).

### 7.1 Brief comum (`advertising_brief`)

Enviado em compose, review, refine e compose de campanha:

```json
{
  "framework": "design-system-ads",
  "scope": "brand",
  "name": "Acme Ads",
  "dna": {},
  "archetype": "brand",
  "tokens": {},
  "effects": {
    "wash-strength": "16%",
    "grain": "0.12",
    "overlay": "transparent",
    "hairline": "#3D4451",
    "cta-shadow": "none"
  },
  "contrast": { "pairs": {}, "min": 4.5, "passed": true },
  "copy": {},
  "creative_line": "",
  "rules": {},
  "backgrounds": [],
  "tracks": [],
  "evidence": {},
  "fidelity": {
    "locked_tokens": { "paper": "#FFFFFF", "ink": "#0B3D2E", "accent": "#0B3D2E", "highlight": "#C4A35A" },
    "sector": "",
    "tone": "",
    "products": [],
    "forbidden": [],
    "must": [],
    "logo_url": "",
    "assets": [],
    "stock_copy": false
  },
  "agent": {
    "role": "diretor de arte desta marca, não de um kit genérico",
    "wash_is_css": true,
    "generate_tracks": ["packshot", "kv", "lifestyle"],
    "prefer_assets": true,
    "materials": [],
    "avoid_image_defaults": [
      "cream #F4F1EA + terracotta",
      "acid green on near-black",
      "SaaS cards and soft grey shadows",
      "stock handshake or glass office",
      "website chrome, navbar, app UI",
      "reconhecível / direta / de marca"
    ]
  },
  "must": [
    "Advertising OS, not a website kit.",
    "Locked tokens in fidelity.locked_tokens stay in the same color family.",
    "Never replace brand ink with CentralComm teal unless that is already the ink.",
    "Prefer fidelity.assets on tracks before inventing a new image.",
    "Wash is CSS (wash-strength + ink), never a generated gradient photo.",
    "Short copy from this brand. Recompose IAB, never resize.",
    "Do not invent cream, terracotta, acid green or SaaS cards.",
    "DNA and copy come from this brand's evidence, never generic traits."
  ],
  "ask": "…"
}
```

### 7.2 Compose da marca

**Modelo:** `DESIGN_SYSTEM_ADS_COMPOSE_MODEL` · `openai/gpt-4o` · temp `0.25` · 1200 tokens.

System:

```text
Você é o diretor de arte desta marca.
Copy de anúncio em português, fiel aos pixels.
Nunca escreva sobre o laboratório ou o design system. JSON only.
```

Ask:

```text
Escreva o Advertising OS desta MARCA em português. Não é campanha.
Use fidelity: tinta travada, setor, tom, produtos, forbidden e assets.
JSON: dna{name,personality[3-5 traços concretos desta marca],must[],avoid[]},
archetype, ad_copy{headline,support,cta,legal} o que a marca vende e para quem,
patches[{token_id,css,reason}] só se o token falhar e só na família da tinta travada,
effects{wash-strength,grain,overlay,cta-shadow},
tracks[{id,prompt}] packshot,kv,lifestyle,wash com material, luz, recorte e hex, notes[].
Se fidelity.assets já tiver URL para uma trilha, não invente outra imagem.
Wash é CSS (wash-strength), não peça foto de gradiente.
Proibido: reconhecível, direta, de marca, Saiba mais, no primeiro olhar, design system,
tinta certa, herda o tema, Tailwind, cream, terracotta, card SaaS.
Wash é a lavagem DESTA tinta, não um campo genérico.
```

JSON esperado de volta:

```json
{
  "dna": {
    "name": "Acme",
    "personality": ["…"],
    "must": ["…"],
    "avoid": ["…"]
  },
  "archetype": "brand",
  "ad_copy": { "headline": "", "support": "", "cta": "", "legal": "" },
  "patches": [{ "token_id": "ink", "css": "#0A2F24", "reason": "…" }],
  "effects": { "wash-strength": "16%", "grain": "0.12" },
  "tracks": [{ "id": "packshot", "prompt": "…" }],
  "notes": ["…"]
}
```

### 7.3 Review de fidelidade

**Modelo:** gpt-4o · temp `0.15` · 900 tokens.

System:

```text
Você revisa fidelidade de Advertising OS.
A tinta extraída é lei. Copy de anúncio em português. JSON only.
```

Ask:

```text
Revise a FIDELIDADE deste Advertising OS contra fidelity
(tinta travada, setor, tom, produtos, assets).
JSON: passed, score 0-1, notes[], defects[],
dna{…} só se o DNA for genérico,
ad_copy{…} só se a copy for estoque ou meta,
patches[{token_id,css,reason}] só na família de fidelity.locked_tokens.
Proibido trocar ink/paper/accent por outra marca.
Nunca use teal CentralComm se a tinta da marca não for teal.
```

Sem modelo: score local 0.74 se contraste ok e copy limpa; senão 0.48. Marca `evidence.reviewed`.

### 7.4 Refine de tokens (até 4 passes)

**Modelo:** `DESIGN_SYSTEM_ADS_MODEL` · `openai/gpt-4o-mini` · temp `0.1` · 700 tokens.

System:

```text
You review an Advertising Design System.
DNA, contrast, type and CTA. Patches only. Never rewrite.
```

Ask:

```text
Review this Advertising OS. Return JSON: passed, score 0-1, defects[], notes[],
patches[{token_id,css,reason}]. Patch only tokens that fail ads (contrast, CTA, type).
Never rewrite the system. Never invent a generic palette.
```

Para se `passed`, se o score cair, ou se acabar o orçamento (`MAX_PASSES = 4`).

### 7.5 Compose da campanha

**Modelo:** gpt-4o · temp `0.35` · 900 tokens.

System:

```text
Você é o diretor de arte da campanha.
A tinta da marca está travada. Copy e KV mudam. JSON only.
```

Ask (brief ganha `scope: campaign` + bloco `campaign`):

```text
Escreva a CAMPANHA desta marca em português. Não reescreva ink, paper nem accent.
JSON: creative_line (uma frase da temporada), ad_copy{headline,support,cta,legal} da oferta,
archetype (product-hero|lifestyle|promotion|brand),
tracks[{id,prompt}] só kv e lifestyle com a linha da campanha,
ground-kind paper|wash|image, notes[].
Proibido: copiar a headline institucional da marca, Saiba mais, design system.
```

Bloco `campaign` no brief:

```json
{
  "name": "Verao",
  "objective": "…",
  "campaign_text": "…",
  "cta_text": "Reservar",
  "creative_line": "…"
}
```

### 7.6 Prompts de imagem (trilhas)

Gerados em `tracks.prompt_for_track`. Inglês, com hex da tinta e material real.

**Packshot**

```text
Studio packshot of the real {product} from {name}, clipped on {paper},
brand ink {ink} in the label or shadow, hard but soft-edged key light,
recognizable silhouette of THIS product, 28 percent of frame,
room on the right for type. Not a generic bottle.
{brief} Personality: …. Must: …. Avoid: ….
Headline space for: {headline}.
No website UI, no app chrome, no cream terracotta SaaS kit, no watermarks,
no generic stock. {extra}
```

Se houver referências anexadas, a mesa acrescenta:

```text
Use the attached brand images as the real product and mark.
Do not invent a different SKU, bottle or logo.
```

**KV 16:9**

```text
16:9 master key visual for {name} in {sector}.
Negative space for a 2-line headline and CTA.
Brand ink {ink} as the signal, paper {paper} as the field, highlight {highlight} only once.
{tone} tone. Art directed, not a website hero.
```

**Lifestyle**

```text
Lived scene of someone using {product} in the world of {name} in {sector},
ink {ink} in wardrobe or light, {tone} atmosphere,
no stock handshake, no office glass, no navbar.
```

**Wash** (raramente gerada; a mesa pula no loop)

```text
Abstract wash of {name} ink {ink} on {paper}, pigment and paper grain,
no photography, no logo, no UI. This is the brand's stain, not a gradient.
```

Payload de imagem OpenRouter:

```json
{
  "model": "openai/gpt-image-2",
  "prompt": "…",
  "aspect_ratio": "1:1",
  "quality": "high",
  "output_format": "png",
  "resolution": "2K",
  "background": "opaque",
  "input_references": ["data:image/png;base64,…", "data:image/png;base64,…"]
}
```

Máximo 2 referências: produto/cena + logo. Wash: zero fotos.

---

## 8. Componentes, densidade, arquétipos, IAB

### 8.1 Prioridade (P0 nunca some)

| role | P | some no compacto? |
|---|---|---|
| logo, headline, product | 0 | não |
| cta, visual, ground | 1 | CTA fica; visual pode ir ao poço |
| support | 2 | sim, no compacto |
| legal, chip, icon | 3 | sim |

### 8.2 Densidade

| densidade | formatos | o que cabe | copy |
|---|---|---|---|
| compact | 728×90, 320×50 | logo + headline + CTA | 32 / 0 / 14 |
| standard | 300×250, 160×600, stories | + produto ou lifestyle | 42 / 56 / 16 |
| rich | 970×250, 300×600, feed, LinkedIn | + apoio + legal | 56 / 80 / 18 |

`product-hero` ocupa o poço com packshot. Compacto não abre produto na área de copy.

### 8.3 Arquétipos

| id | fundo | lead | formato default | label |
|---|---|---|---|---|
| `brand` | wash | headline | iab-billboard | Marca |
| `product-hero` | paper | product | iab-medium | Produto |
| `lifestyle` | image | visual | iab-halfpage | Lifestyle |
| `promotion` | wash | cta | iab-medium | Promoção |

Promoção 300×250 ≠ institucional 300×250. O template muda com o objetivo.

### 8.4 Receitas IAB (`layouts.RECIPES`)

Caixas em `%` do canvas. `well` = poço onde extras se sobrepõem (`fan_in_well`).

| key | tamanho típico | densidade receita | park |
|---|---|---|---|
| `iab-billboard` | 970×250 | wide | chip |
| `iab-leaderboard` | 728×90 | thin | support, legal, icon, chip |
| `iab-mobile` | 320×50 | thin | support, legal, icon, chip |
| `iab-medium` | 300×250 | box | — |
| `iab-halfpage` | 300×600 | tall | — |
| `iab-skyscraper` | 160×600 | tall | — |
| `feed-1x1` | 1080×1080 | square | — |
| `feed-4x5` | 1080×1350 | tall | — |
| `story-9x16` | 1080×1920 | tall | support, chip, icon |
| `linkedin-landscape` | 1200×627 | wide | chip |

Famílias de compose: `wide_banner`, `rectangle`, `half_page`, `slate_16x9`, `square_1x1`, `portrait_4x5`, `story_9x16`, `landscape_social`.

Pilha: **4 a 40** camadas. Núcleo por arquétipo + densidade; extras = product / support / legal / icon / chip / `ornament-1…31`.

Camada:

```json
{
  "id": "layer-headline",
  "role": "headline",
  "label": "headline",
  "z": 41,
  "x": 32, "y": 18, "w": 40, "h": 36,
  "text": "A campanha chega inteira",
  "parked": false,
  "priority": 0,
  "overlap": false,
  "asset_url": ""
}
```

`swaps` troca só `x,y,w,h` entre duas camadas (sobe/desce na lista da mesa).

Tipo escala no adapter: teto da receita limitado pela altura da caixa (`type-headline` vira `34px` no billboard, `11px` no mobile leaderboard).

---

## 9. Fundos

Todo sistema nasce com três fundos. A **peça** escolhe um; o formato não inventa outro.

| kind | o que é | overlay |
|---|---|---|
| `paper` | `paper` sólido | `transparent` |
| `wash` | tinta da marca em véu | `color-mix(ink, wash-strength)` |
| `image` | lifestyle / packshot / KV | véu de ink ~34% se não houver overlay |

Lavagem é **CSS**. GPT Image 2 gera só packshot / KV / lifestyle que faltarem.

---

## 10. Persistência

```text
cx_clients.brand_profile.design_system_ads     ← cópia operacional
cx_brand_visual_systems.tokens                 ← índice único por client
  WHERE tokens->>'framework' = 'design-system-ads'
    AND status <> 'archived'

cx_campaigns.creative_brief.design_system_ads  ← DS da temporada
```

Migração: `migrations/add_design_system_ads.sql`.

Preset `centralcomm` **não** grava no banco — vive em `centralcomm.py`.

---

## 11. Front da mesa — comportamento

Arquivo: `static/js/mc-design-system.js`.

Estado: `clientId` (default `centralcomm`), `campaignId`, `format`, `layers`, `archetype`, `swaps`, `highlight`.

| ação do usuário | chamada |
|---|---|
| troca marca | `GET /brand/<id>` + adapt se existir |
| troca campanha | `GET /campaign/<id>` |
| Montar a marca | `POST /brand` se faltar + loop × 8 |
| Montar campanha | `POST /campaign/<id>` + adapt |
| Aprovar | `POST /approve` |
| swatch / efeito | `POST /tokens` (280 ms) |
| DNA / copy | `POST /tokens` |
| intent Contraste/Tipo/CTA | `POST /refine { intent }` |
| clique na trilha | `POST /tracks/<id>` |
| formato IAB / arquétipo | `POST /adapt` + iframe |
| range de camadas | `POST /adapt { layers }` |
| ↑↓ camada | `POST /adapt { swaps: [[a,b]] }` |
| clique na camada | `highlight` no specimen |

Copy de UI da mesa: português. Proibido na peça: “design system”, “tinta certa”, “herda o tema”, “Tailwind”, “ver o sistema”.

---

## 12. Mapa de arquivos

```text
aicentralv2/design_system_ads/
  schema.py         contrato, tokens, contraste, CSS, Tailwind
  materialize.py    marca ← profile / extract / preset
  ingest.py         extract-design-system → tokens de anúncio
  fidelity.py       dossiê, lock de tinta, bind de assets
  refine.py         compose, review, loop, intents, campaign compose
  catalog.py        catálogo + inspect_loop
  tracks.py         4 trilhas + prompts de imagem
  copy.py           copy de anúncio, estoque, limites IAB
  components.py     P0–P3, densidade, arquétipos, fundos
  layouts.py        receitas % IAB / social
  adapt.py          pilha 4–40, type scale, swaps
  campaign.py       herança, recortes, Verao
  centralcomm.py    preset da casa
  render.py         table_html, specimen, Google Fonts
  service.py        payload_for, fachada
  learn.py          currículo L1–L5 (treino com criativos reais)
  cutouts.py        recorte branco → transparente

aicentralv2/creative_modeling_service.py   orquestra persistência + OpenRouter
aicentralv2/creative_modeling_routes.py    rotas + MC_DESKS
aicentralv2/static/js/mc-design-system.js
aicentralv2/templates/parametros/_mc_design_system.html
aicentralv2/static/css/tailwind/design-system.css

.agents/skills/design-system-ads/SKILL.md
tests/test_design_system_ads.py
```

---

## 13. Treino com criativos reais (profundidade)

`learn.py` classifica **quatro eixos**, não só o nível. Print da timeline é superfície (L5), não a aula.

| eixo | o que decide | exemplo |
|---|---|---|
| nível | dificuldade + processo | L1 packshot → L4 elenco |
| conceito | o que a peça *é* | `packshot` ≠ `event-kv` ≠ `lifestyle` |
| template | como as camadas se arrumam | `product-left-type`, `quote-overlay` |
| formato | o retângulo | `feed-1x1`, `feed-4x5`, `linkedin-landscape` |

| nível | conceito | template | formato | lab |
|---|---|---|---|---|
| L1 | packshot | `isolated-product` | feed-1x1 | campaign-pack |
| L2 | product-kv / event-kv | `product-left-type` | LinkedIn ou 4:5 | swap/read |
| L3 | lifestyle | `overlay-card` | 4:5 / 9:16 | crop → campaign-pack |
| L4 | event-cast | `name-pills` | 1:1 | decompose |
| L5 | network-chrome | `crop-frame` | o da peça | recortar, depois a aula |

Retrato 4:5 **não** é lifestyle. Google Discovery: RSA fica **fora** da arte. Meta: “Saiba mais” é chrome, não CTA da marca.

O catálogo da mesa inclui `curriculum` e `training` para o agente — a UI do desk hoje não desenha o currículo; o loop de produção para em `ready` + palco IAB.

---

## 14. Regras da IA (compile_rules)

```json
{
  "archetype": { "ground": "wash", "lead": "headline", "label": "Marca" },
  "mandatory": ["logo", "headline"],
  "preferred": ["headline", "cta"],
  "park_first": ["legal", "chip", "icon", "support"],
  "must": ["logo com respiro", "CTA com 4.5:1"],
  "avoid": ["resize cego", "card SaaS"]
}
```

O agente de anúncio recebe o dossiê `fidelity` + `agent` (lavagem é CSS, defaults de imagem proibidos). Compose usa o brief, não o nome da marca sozinho.

---

## 15. Sequência operacional (marca → campanha → peça)

1. Abrir [a mesa](https://ai.centralcomm.media/parametros/modelagem-criativos/design-system).
2. Escolher a **marca** (ou deixar CentralComm Ads).
3. **Montar a marca** — loop assenta DNA, contraste, review e trilhas. GPT Image 2 só o que faltar; asset da marca entra como referência.
4. Ajustar tinta / copy / intents no catálogo. Contraste precisa passar 4.5:1.
5. **Aprovar** o rascunho da marca.
6. (Opcional) Escolher a **campanha** → **Montar campanha**. Tinta fica. Copy, linha, KV e recortes mudam.
7. Clicar formato IAB ou arquétipo. O palco mostra a peça recomposta.
8. Subir/descer camadas, marcar highlight, trocar fundo (papel / lavagem / imagem).
9. Specimen isolado: `/lab/design-system/marca/<id>?format=iab-medium&layers=8`.

---

## 16. O que isto não é

- Não é o tema DaisyUI (`docs/design-tokens.md`) nem `/design-system` / `/design-system-enterprise` (páginas de tokens do ERP).
- Não grave `design-system/` na raiz do ERP. O dado vive na marca e na campanha.
- Extract-design-system é **satélite**: lê um site. Esta mesa **decide o anúncio**.
- Campanha não reabre o loop de DNA da marca e não gera packshot institucional de novo — gera KV/lifestyle da temporada sobre a tinta travada.
