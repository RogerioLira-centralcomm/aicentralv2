# Studio · Tamanhos corretos e máscaras — plano definitivo

Data: 2026-10-02 · Prazo de lançamento: ~10 dias · Motor: gpt-image-2 (OpenAI direto; OpenRouter como redundância)

## 1. Diagnóstico

Hoje o Studio pede ao provedor um de três tamanhos fixos (`_OPENAI_IMAGE_SIZES` em
`services/openrouter_service.py`) e depois corta ou preenche com desfoque até o formato de entrega
(`fit_generated_output` em `creative_media/studio_create.py`).

| Formato | Entrega | Pede | Recebe | Perde na geração |
|---|---|---|---|---|
| Feed 4:5 | 1080×1350 | 3:4 | 1024×1536 | 16,7% da altura |
| Feed 1:1 | 1080×1080 | 1:1 | 1024×1024 | 0% |
| Stories/Reels | 1080×1920 | 9:16 | 1024×1536 | 15,6% da largura |
| LinkedIn | 1200×627 | 16:9 | 1536×1024 | 21,6% da altura |
| YouTube in-feed | 1920×1080 | 16:9 | 1536×1024 | 15,6% da altura |
| IAB 300×250 | 300×250 | 4:3 | 1536×1024 | 20,0% da largura |
| Display 300×300 | 300×300 | 1:1 | 1024×1024 | 0% |
| IAB 300×600 | 300×600 | 9:16 | 1024×1536 | 25,0% da largura |
| IAB 160×600 | 160×600 | 9:16 | 1024×1536 | 60,0% da largura |
| IAB 970×250 | 970×250 | 21:9 | 1536×1024 | 61,3% da altura |
| IAB 728×90 | 728×90 | 21:9 | 1536×1024 | 81,5% da altura |
| IAB 320×50 | 320×50 | 21:9 | 1536×1024 | 76,6% da altura |

Consequências observadas:

- texto e CTA encostados na borda (Stories), porque o modelo compõe num canvas que depois é cortado;
- faixas borradas nas laterais (até o commit 70479f4f3, quando o corte era limitado a 4%/11%);
- "16:9" sai em 3:2 (a tabela mapeia 16:9 → 1536×1024);
- "21:9" não está na tabela: cai no padrão 1536×1024 e a máscara não é desenhada no canvas do provedor;
- banners extremos (728×90, 320×50, 970×250, 160×600) usam menos de 40% dos pixels gerados;
- a entrega é só em 1×: um 300×250 sai com 300×250 px, sem versão 2× para telas de alta densidade
  e sem controle de peso de arquivo.

Fato verificado em 2026-10-02: o gpt-image-2 aceita tamanho livre. `1024x1792` e `1008x1792` voltaram
exatamente nesse tamanho pela API da OpenAI.

## 2. Princípios

1. **Gerar no tamanho certo.** O pedido ao provedor já sai no ratio da peça; o corte vira exceção.
2. **Uma única fonte de verdade de tamanho.** Um "plano de tamanho" por formato alimenta máscara, prompt,
   provedor, recorte e exportação. Nenhum desses calcula tamanho por conta própria.
3. **Nunca preencher com desfoque.** Se o provedor não alcança o ratio, a peça é composta, não esticada.
4. **Elementos críticos dentro da margem segura, sempre.** Texto, CTA e logo são verificados depois da
   geração, não só pedidos no prompt.
5. **Entrega profissional.** Dimensão exata, 1× e 2×, peso dentro do limite do canal.

## 3. Plano de tamanho por formato (fonte única)

Novo módulo `creative_media/size_plan.py`, consumido por `ad_masks`, `studio_create` e pela exportação:

```
size_plan(width, height) -> {
  delivery: (W, H),            # tamanho contratado (1×)
  delivery_2x: (2W, 2H),       # alta densidade
  generation: (gw, gh),        # o que se pede ao gpt-image-2
  frame: (x, y, w, h),         # onde a entrega fica dentro da geração (1.0 quando o ratio é exato)
  strategy: "native" | "framed" | "composed",
  weight_budget_kb: int|None,  # limite de peso de arquivo do canal
}
```

Regras do tamanho de geração (gpt-image-2), **confirmadas na sonda de 2026-10-02**:
lados múltiplos de 16 (1000×1000 recusado); ratio máximo 3:1 (2000×640 recusado; 1920×640 e 640×1920 aceitos);
área mínima entre 0,59 MP e 0,65 MP (768×768 recusado, 1024×640 aceito); 3840×1280 aceito.
Alvo: ~1,5 MP na qualidade Econômica/Padrão e ~3 MP na Alta.

Limite de cota: a organização tem **5 imagens por minuto** no gpt-image-2. Com 2–4 variações por pedido e
mais de um usuário, isso estoura no lançamento. Entra na fase 1: fila com espera e nova tentativa em 429, e
pedido de aumento de cota à OpenAI.

| Formato | Geração proposta | Estratégia |
|---|---|---|
| Feed 4:5 | 1024×1280 | native |
| Feed 1:1 | 1024×1024 | native |
| Stories/Reels | 1008×1792 | native |
| LinkedIn 1200×627 | 1536×800 (crop < 0,5%) | native |
| YouTube 16:9 | 1792×1008 | native |
| IAB 300×250 | 1152×960 | native |
| Display 300×300 | 1024×1024 | native |
| IAB 300×600 | 800×1600 | native |
| IAB 160×600 (3,75:1) | 640×1920 + composição | composed |
| IAB 970×250 (3,88:1) | 1920×640 + composição | composed |
| IAB 728×90 (8,1:1) | visual 1920×640 + composição | composed |
| IAB 320×50 (6,4:1) | visual 1920×640 + composição | composed |

## 4. Banners extremos: composição em camadas

Para os formatos acima de 3:1 o modelo não escreve texto:

1. o gpt-image-2 gera **só o visual** (fundo/cena) no 3:1 mais próximo, com a zona de texto calma;
2. o Studio recorta a faixa do formato;
3. título, CTA e logo são **renderizados por código** (Pillow, ou HTML/canvas no navegador) com a
   tipografia da marca, nas zonas da máscara, em tamanho de pixel exato;
4. a peça é exportada em 1× e 2×.

Ganho: texto nítido em 320×50, nenhum corte de letra, controle total de margem. A geometria das zonas
vem da mesma máscara (`ad_masks`), então o desdobramento continua consistente entre formatos.

Pré-requisito: fontes da marca disponíveis no servidor. Sem a fonte, usa-se uma fonte neutra
licenciada (ex.: Inter) e a interface avisa.

## 5. Máscaras e contrato

- A máscara passa a ser desenhada **no tamanho de geração**; nos formatos native, `frame` = canvas inteiro
  e as faixas escuras desaparecem do desenho e do prompt.
- O contrato de layout continua com zonas em % e o enquadramento seguro numérico.
- **Verificação pós-geração** (nova): um modelo de visão devolve as caixas de texto, CTA e logo; se algo
  sair da margem segura, o Studio regera uma vez com a correção explícita ("o título começou em x=1%;
  comece em x=8%"). Fica registrado como métrica de aderência por família e formato.

## 6. Entrega e exportação

- dimensão exata do canal (1×) e 2×; arquivo nomeado com marca, formato e versão;
- formato: JPG para foto, PNG quando houver transparência ou texto fino; WebP opcional;
- peso: IAB com orçamento de carga inicial (referência 150 KB, a confirmar com o time de mídia); compressão
  progressiva até caber, com aviso quando não couber;
- metadados de cor sRGB.

## 7. Redundância (OpenRouter)

O caminho OpenRouter não aceita tamanho livre da mesma forma. Regra: quando a geração cair no OpenRouter,
o `size_plan` recalcula `frame` para o tamanho que voltou e o recorte usa esse frame; a peça é marcada
como "gerada pela rota de redundância" no log. Testar o fallback explicitamente na fase 1.

## 8. Fases (10 dias)

| Fase | Entrega | Critério de aceite |
|---|---|---|
| 0 · 0,5 dia | Sonda dos limites do gpt-image-2 (tamanhos, múltiplos, área, ratio máx.) | tabela de limites confirmada no código e no teste |
| 1 · 2 dias | `size_plan` + `size` opcional na rota OpenAI + máscara no tamanho de geração | todos os formatos native saem com 0% de corte; testes unitários por formato |
| 2 · 1 dia | Verificação pós-geração da margem segura (visão) + 1 regeneração | 0 peças com texto/CTA/logo fora da margem num lote de 24 |
| 3 · 3 dias | Composição em camadas para 160×600, 970×250, 728×90, 320×50 | texto legível no 320×50; nenhuma letra cortada; mesmas zonas da máscara |
| 4 · 1 dia | Exportação 1×/2× com orçamento de peso | arquivos nas dimensões exatas e dentro do peso; download no Criar |
| 5 · 1,5 dia | Lote de validação com marcas reais (Cemig, Centralcomm, BDMG) em todos os formatos | aprovação visual do time; métricas de aderência registradas |
| folga · 1 dia | correções do lote | — |

## 9. Decisões (2026-10-02)

1. Peso: sempre o menor possível; IAB até 150 KB. Botão de compressão na Biblioteca fica para depois.
2. Fontes: a auditoria de marca guarda **nomes** de família, não arquivos (Cemig: Roboto, Open Sans;
   BDMG: Gotham; Centralcomm: nenhuma). Resolver de fontes: famílias livres (Google Fonts/OFL) embarcadas
   no servidor; fontes comerciais (Gotham) por upload da marca; sem arquivo, substituta da mesma
   classificação, com aviso.
3. Entrega 2× por padrão, junto do 1×.
4. Texto editável nas peças compostas: sim (camadas), já no lançamento.
