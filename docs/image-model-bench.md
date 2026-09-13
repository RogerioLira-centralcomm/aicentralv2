# Bancada de modelos de imagem

Plano para escolher o modelo OpenRouter que substitui (ou convive com) `openai/gpt-image-2` nas mesas do lab.

**Status:** guardado. O fluxo completo do Trocr ainda não rodou ponta a ponta nesta linha. Não gerar lote até existir página de teste com prompts reais das mesas.

Página de teste: ainda não existe. Quando existir, ela reusa os prompts das mesas — não prompts genéricos.

Contratos que alimentam a página:

| Mesa | Doc | Prompt / payload |
|---|---|---|
| Trocr | [`trocar.md`](trocar.md) | `build_optimized_prompt` + still + `preserve` / `alter` |
| Camadas | [`camadas.md`](camadas.md) | `GROUND_PROMPT` (limpar poço) |
| Design System Ads | [`design-system-ads.md`](design-system-ads.md) | trilhas, até 2 `input_references` |
| Places | [`places.md`](places.md) | hero / mapa / ponto, fotoreal sem texto |

Script CLI antigo (t2i genérico, sem still): `scripts/openrouter_image_bench.py`. Não é o teste que decide o Trocr.

---

## 1. Por que não um t2i genérico

O lab tem dois jobs pagos distintos. Typeset do Trocr é Pillow — custo zero — e **não entra** na bancada.

| Uso | Tipo | O que o modelo tem que acertar | Qualidade hoje |
|---|---|---|---|
| Trocar item / redesenhar | i2i, 1–2 refs | identidade + PT exato + só o item | rascunho `medium`, produção `high` |
| Trocar recorte | i2i depois typeset | virar formato sem redesenhar | idem |
| Gerar (Ads, conceito, Places) | t2i, às vezes refs | texto no frame **ou** fotoreal | `high` / `2K` |
| Camadas · limpar poço | i2i | fundo vazio, sem gente/tipo | `GROUND_PROMPT` |

Paisagem sem texto não escolhe modelo para o Trocr. O caso difícil é editar um still sem destruir cara, selo e português.

---

## 2. Dois jobs (quando a página existir)

### Job A — Trocar item (decide o Trocr)

- Still: `tests/fixtures/creatives/arraial-1x1.png`
- `preserve`: people, logo, colors, style, graphic
- `alter`: só a headline
- Troca: `Te encontro no` → `Te vejo no`
- Prompt: o `build_optimized_prompt` da mesa, não texto inventado
- `input_references`: o PNG do arraial
- Qualidade de screening: `medium` (a mesa nunca manda `low` no Trocr)

Passa só se:

1. as 6 caras continuam as mesmas;
2. pills e datas não mudam letra (`Zé Vaqueiro`, `Mumuzinho`, `Pisanafulô`);
3. só a headline muda, e o PT fica exato;
4. não inventa neon, UI, pessoa extra, glow.

### Job B — Gerar (decide Ads / Places / conceito)

- t2i, 16:9, menor tier que o modelo aceita
- headline exatamente `CENTRALCOMM`, apoio `mídia que chega`
- sem still

Places fotoreal fica de desempate, não de screening.

---

## 3. Shortlist OpenRouter

Primeiro corte (5 modelos):

| Slug | Papel |
|---|---|
| `openai/gpt-image-2` | baseline |
| `openai/gpt-image-2.5-flare` | sucessor direto |
| `google/gemini-3.1-flash-image` | Nano Banana 2, único com `512` no gerar |
| `bytedance-seed/seedream-5-0-lite` | fotoreal / i2i |
| `black-forest-labs/flux.2-klein-4b` | iteração barata |

Nano Banana Pro (`google/gemini-3-pro-image`) só entra se o Flash empatar no texto. Typeset, Recraft, Grok e Flux Pro/Max ficam de fora do primeiro corte.

Menor custo **não é o mesmo parâmetro** em todos: OpenAI usa `quality`; Gemini usa `resolution`; Seedream 5 Lite já começa em `2K`; Flux cobra por megapixel.

API: `GET /api/v1/images/models`, `GET /api/v1/images/models/{slug}/endpoints`, `POST /api/v1/images`. Cobrar `usage.cost` (USD) e converter. Enviar só os campos que o endpoint aceita.

---

## 4. Como julgar (nessa ordem)

1. **Lock** — cara / pill / logo intactos (Job A)
2. **Copy** — PT exato, sem hífen, sem letra a mais
3. **Escopo** — só o item pedido mudou
4. **Custo real** — `usage.cost` em BRL
5. **Tempo** — rascunho do Trocr precisa ser usável

Modelo barato que redesenha o arraial perde. Modelo um pouco mais caro que trava identidade ganha no Trocr. No Gerar, o critério inverte: texto no frame + R$ por peça.

Câmbio de referência do plano: USD 1 = R$ 5,1254 (fechamento 11/09/2026). Produção atual Image 2 `high` 16:9 ≈ US$ 0,13 / R$ 0,67 por imagem. Lote de screening (5 modelos × 2 jobs) ≈ R$ 2–3,50.

---

## 5. Página de teste (depois)

Quando o fluxo do Trocr estiver estável:

1. Página no lab (fora do produto do cliente), no espírito de `/lab/trocr/states`.
2. Cada card é um **prompt vivo da mesa**, não um string solto: Job A chama `build_optimized_prompt`; Job B puxa o prompt de Ads/Places/conceito que a mesa já montou.
3. Mesmo still, mesmo aspecto, um clique gera o lote nos slugs da shortlist.
4. Grade lado a lado + `usage.cost` em BRL + tempo.
5. Typeset não aparece como “modelo”.

Não implementar a página nesta linha. O bloqueio atual: fluxo completo do Trocr ainda não rodou; `OPENROUTER_API_KEY` / segredo da integração não estava no ambiente local quando o CLI foi tentado.
