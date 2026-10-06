# Studio · Modelos atuais, custos e o que o Higgsfield acrescenta

Data: 2026-10-02 · Fontes: código do repositório (defaults e `.env`), páginas públicas do Higgsfield e preços
públicos de OpenAI/OpenRouter (links no fim). Preços de terceiros mudam: confirmar na fase 0 antes de decidir.

## 1. O que o Studio usa hoje

| Etapa | Modelo (padrão no código) | Rota | Observação |
|---|---|---|---|
| Direção criativa | `gpt-5-nano` | OpenAI direto; `gpt-4o-mini` no OpenRouter como redundância | barato, mas leu a máscara errado nos testes; corrigido entregando as zonas em texto |
| Criação de imagem | `gpt-image-2` | OpenAI direto; OpenRouter de redundância | agora no tamanho exato (até 3:1) |
| Edição com máscara | `gpt-image-2` (edit) | OpenAI | |
| Tipografia dos banners extremos | código (Pillow + fonte da marca) | local | custo zero |
| Conferência de margem | `gpt-5-mini` | OpenAI | **desligada** por padrão |
| Vídeo | `bytedance/seedance-2.5` | OpenRouter | reserva: `kwaivgi/kling-v3.0-pro` |
| Narração (TTS) | `google/gemini-3.1-flash-tts-preview` | OpenRouter | |
| Agentes de formato/roteiro | `gpt-5.4` / `gpt-5-nano` | OpenAI/OpenRouter | |

## 2. Quanto custa de verdade × quanto o Studio estima

### Imagem (gpt-image-2)

Preço público por imagem 1024×1024: **baixa US$ 0,006 · média US$ 0,053 · alta US$ 0,211** (cobrança por
token; o custo cresce com a área). Estimativa proporcional à área para os tamanhos que o Studio passou a pedir:

| Qualidade no Studio | Provedor | ~1,5 MP (feed, 300×250) | ~2,4 MP (story, 16:9) |
|---|---|---|---|
| Econômica | low | ~US$ 0,009 | ~US$ 0,014 |
| Padrão | medium | ~US$ 0,076 | ~US$ 0,12 |
| Alta (~3 MP) | high | ~US$ 0,60 | — |

Cada imagem de referência (máscara, logo, foto) soma tokens de entrada (US$ 8 por milhão), na faixa de
centavos.

**Como o Studio estima/cobra:** a pré-autorização usa `model_unit_usd` (US$ 0,006 rascunho / US$ 0,22
publicação, +12% por referência) e o catálogo de custo (`cadu_cost_catalog`) tem **US$ 0,22 fixos por imagem**
como fallback. Quando a OpenAI devolve `usage`, o débito final usa o custo real. Consequência: a
pré-autorização da qualidade Padrão/Alta bloqueia muito mais crédito do que a geração gasta (foi o que
travou o teste: "estima 24.640 tokens").

### Vídeo (Seedance 2.5)

| Rota | 480p | 720p | 1080p |
|---|---|---|---|
| OpenRouter (rota atual) | ~US$ 0,103/s | ~US$ 0,231/s | — (4K até US$ 2,08/s) |
| Higgsfield | US$ 0,2056/s | US$ 0,4622/s | US$ 1,1372/s |
| **Catálogo interno do Studio** | **US$ 1,271/s fixo** | | |

O catálogo interno cobra/estima **~5,5× o custo real de 720p** no OpenRouter. Um vídeo de 10 s em 720p custa
~US$ 2,31 e o Studio estima ~US$ 12,71.

## 3. O catálogo do Higgsfield (API, out/2026)

**Imagem (texto→imagem):** Soul 2 (desde US$ 0,0032), Marketing Studio Image 2.0 (US$ 0,0138 em 1k baixa →
US$ 0,6136 em 4k alta), Z-Image Turbo (US$ 0,015), Ideogram 4.0 (US$ 0,03), Recraft 4.1 (US$ 0,035),
Qwen Image 3 (desde US$ 0,04), Grok Imagine 2.0 (desde US$ 0,04), Soul Standard (desde US$ 0,0938).

**Edição:** só *workflows* que **geram** peças novas (Product shots, Graphic ads, Marketplace design, desde
US$ 0,0138). **Não aparece edição com máscara/inpainting genérica.**

**Vídeo:** Wan 3.0 (desde US$ 0,025/s), Wan 3.0 Prime (desde US$ 0,041/s), Kling 3.0 (US$ 0,042/s),
MiniMax H3 (US$ 0,065/s), Happy Horse (US$ 0,07/s), Grok Imagine Video (desde US$ 0,08/s), LTX 2.5 Fast/Pro
(US$ 0,09/0,12/s), Seedance 2.0 (desde US$ 0,0985/s), Seedance 2.5 (desde US$ 0,144/s), Genjutsu (motion
transfer, desde US$ 0,159/s), Cinema Studio 4.0 (desde US$ 0,2057/s).

Funcionamento: pagamento por uso em dólar (recarga mínima US$ 5), requisições **assíncronas** (envia →
recebe id → consulta ou webhook). Limites de taxa não estão publicados.

**Não está no catálogo:** gpt-image-2, Nano Banana, Seedream, Flux Kontext. A página do Marketing Studio
Image aceita parâmetros (`quality`, `moderation`, `resolution`, `aspect_ratio: auto`) e **não menciona
imagem de referência, logo nem máscara**.

## 4. Que melhoria teríamos — por tarefa

### Criação de imagem

- **Trocar o gpt-image-2 por um modelo do Higgsfield, do jeito que o Studio funciona hoje: piora.** Todo o
  ganho recente (máscaras, zonas, logo no canto certo) depende de **mandar a máscara como imagem de
  referência** e de o modelo seguir instruções longas. Nenhum modelo de imagem listado documenta entrada de
  referência; Ideogram e Recraft são fortes em tipografia/design, Soul em estética fotográfica de pessoas,
  mas sem a máscara voltaríamos a layouts aleatórios.
- **Oportunidade real: visual sem texto + tipografia por código.** O motor de composição da fase 3 já escreve
  título/CTA/logo por código. Se ele valer para **todos** os formatos, o modelo só precisa gerar a cena — e
  aí um modelo barato e esteticamente forte (Soul 2 a US$ 0,0032, Z-Image Turbo a US$ 0,015) pode competir com
  o gpt-image-2 Padrão (~US$ 0,076): **até ~20× mais barato por peça**, com texto sempre nítido e editável.
  Precisa de A/B: aderência da cena ao "espaço calmo" das zonas sem a máscara como imagem é o risco.
- **Ideogram 4.0 (US$ 0,03)** é o candidato para peças em que o texto faz parte da arte (tipográfico).

### Edição

- **Sem ganho hoje.** O Higgsfield não oferece edição com máscara no catálogo; os workflows geram peças novas.
  A edição continua no gpt-image-2. Reavaliar quando houver inpainting no catálogo.

### Vídeo

- **Seedance 2.5 pelo Higgsfield custa ~2× o OpenRouter** (US$ 0,46 vs US$ 0,23 por segundo em 720p): migrar
  só por migrar encarece.
- **Ganho real: catálogo e ferramentas.** Opções muito mais baratas para rascunho e variação (Wan 3.0 a
  US$ 0,025/s, Kling 3.0 a US$ 0,042/s: um vídeo de 10 s sai por US$ 0,25–0,42 contra US$ 2,31 no Seedance
  720p), além de recursos próprios (Cinema Studio, Genjutsu motion transfer, movimentos de câmera DoP).
  Faz sentido como **segundo provedor de vídeo**, com Seedance 2.5 para a peça final.

## 5. Custo por peça — cenários

| Peça | Hoje | Alternativa | Diferença |
|---|---|---|---|
| Feed 4:5, Padrão | gpt-image-2 ~US$ 0,076 | Soul 2 sem texto + tipografia por código ~US$ 0,003 | −96% (depende do A/B) |
| Feed 4:5, Econômica | gpt-image-2 ~US$ 0,009 | Soul 2 ~US$ 0,003 | −65% |
| IAB 728×90 | gpt-image-2 sem texto ~US$ 0,009–0,08 + código | Soul 2/Z-Image + código | −60% a −96% |
| Vídeo 10 s 720p | Seedance OpenRouter ~US$ 2,31 | Kling 3.0 Higgsfield ~US$ 0,42 · Seedance Higgsfield ~US$ 4,62 | −82% · +100% |
| Edição com máscara | gpt-image-2 | — | sem alternativa |

## 6. Recomendação

1. **Corrigir o catálogo de custo interno já** (independe do Higgsfield): imagem por qualidade e área em vez
   de US$ 0,22 fixos; vídeo por resolução (US$ 0,10/0,23 por s) em vez de US$ 1,271. Hoje o Studio superestima
   e trava crédito à toa.
2. **Não trocar o motor de criação nem o de edição** pelo Higgsfield agora.
3. **Pilotar o Higgsfield em duas frentes**, com teto de gasto:
   - vídeo: Kling 3.0 / Wan 3.0 para rascunhos e variações; Seedance 2.5 segue no OpenRouter para a final;
   - criação "visual sem texto + tipografia por código" com Soul 2 e Z-Image Turbo, comparando com o
     gpt-image-2 nos 6 formatos-chave.
4. **Fase 0 obrigatória:** confirmar na API os preços (há divergência pública sobre o Seedance), limites de
   taxa e se algum modelo de imagem aceita imagem de referência.

## Fontes

- [Higgsfield — catálogo da API (Open Higgsfield)](https://open.higgsfield.ai/explore)
- [Higgsfield — Seedance 2.5 (preços e parâmetros)](https://open.higgsfield.ai/models/bytedance/seedance-2.5/text-to-video/playground)
- [Higgsfield — Marketing Studio Image](https://open.higgsfield.ai/models/marketing-studio/image/playground)
- [Higgsfield — Graphic ads](https://open.higgsfield.ai/models/workflows/graphic-ads/playground)
- [Higgsfield — Meet the Higgsfield API](https://higgsfield.ai/blog/higgsfield-api)
- [OpenRouter — Seedance 2.5](https://openrouter.ai/bytedance/seedance-2.5)
- [GPT Image 2 API pricing (aifreeapi, checado em set/2026)](https://www.aifreeapi.com/en/posts/openai-image-generation-api-pricing)
- [GPT Image 2 pricing (wavespeed)](https://wavespeed.ai/blog/posts/gpt-image-2-pricing-2026/)
