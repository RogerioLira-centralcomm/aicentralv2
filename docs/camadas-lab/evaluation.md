# Camadas lab — avaliação (Fase 1)

Escopo: o que o código faz hoje. Sem motor novo. Sem score único. Sem vencedor visual.

Legenda: **confirmado** (lido + exercitado ou inspecionado), **hipótese** (código implica, sem prova visual), **proposta** (Fase 2+).

---

## 1. Escada de segmentadores

Arquivo: `aicentralv2/creative_format_lab/split_layers.py` — `resolve_predictor()`, `split_still()`, `_load_rembg()`, `_load_yolo_person()`.

| Pergunta | Achado | Tipo |
|---|---|---|
| Seleciona o primeiro disponível? | Sim: rembg → YOLO person → `field_predictor`. | confirmado (`test_resolve_predictor_escolhe_o_primeiro_disponivel`) |
| Tenta outro se a máscara é rejeitada? | Não. Um único `predict(source)`. Gate `_mask_quality` só descarta a detecção. | confirmado (`test_split_mascara_rejeitada_nao_tenta_segundo_predictor`) |
| Carrega modelos a cada request? | Sim, se o import existir: `new_session("u2net_human_seg")` e `YOLO("yolov8n-seg.pt")` dentro do load, sem cache de módulo. | confirmado no código; **não exercitado** — pacotes ausentes |
| Ambiente local desta auditoria | `rembg` e `ultralytics` = `ModuleNotFoundError`. Engine efetiva: `python`. | confirmado |

`cast_ok=false` cobre rejeição, ausência de detecção e (no decompose) “não pedimos pessoa”. Não distingue `unavailable` / `rejected` / `not_found`. Proposta da Fase 2.

---

## 2. Contrato de `split_still()`

| Tópico | Achado | Tipo |
|---|---|---|
| Canvas da pessoa | PNG RGBA **recortado no bbox** da máscara, não o quadro inteiro com alpha. | confirmado |
| Canvas do fundo | Sempre o tamanho do still. | confirmado |
| `box` | Porcentagem do still original (`x,y,w,h`). | confirmado |
| Transformações | Máscara redimensionada NEAREST; `field_predictor` thumbnail 320 e cola de volta no card após `_trim_paper`. | confirmado no código |
| Erro de entrada | Só PIL / bytes / data URL. HTTP(S) levanta `ValueError("Envie um still em data URL ou bytes.")`. | confirmado |
| Limite de pixels | Nenhum em `_open_image`. Flask `MAX_CONTENT_LENGTH` default 256 MB. | confirmado |
| Ausência de capacidade | Sem rembg/YOLO a mesa não avisa o motor opcional; só `engine: python` e `cast_ok`. | confirmado |

---

## 3. OCR

Cadeia: `FormatLabService.split_layers` → `read_attached_still` (`engineer.py`) → `read_swap_reference(..., strict=True)` (`swap.py`).

Consumidores do mesmo OCR: Camadas (chips), Trocr (campos completos), Conceito (`apply_still_read` trava oferta/CTA).

| Tópico | Achado | Tipo |
|---|---|---|
| Lido pelo Trocr | headline, support, subtitle, price, cta, disclaimer, logo_text, dates, venue, elements, faces, locks, analysis, status | confirmado |
| Projetado na Camadas | headline, support, price, cta, logo_text | confirmado |
| Descartado na slim | dates, venue, elements, status, error | confirmado (`test_read_attached_still_projeta_chips_e_descarta_dates`) |
| Sem credencial / sem callable | `read_swap_reference` devolve `status=unavailable`; slim vira `{}`; split **não** quebra | confirmado no código |
| Erro do provedor | `read_swap_reference` captura `Exception` → `status=provider_error`. Slim descarta o status. Separar continua. | confirmado no código; sem chamada paga |
| Timeout | `chat_completion` timeout 90 s; cai no mesmo `except Exception` | confirmado no código |
| Data URL grande | OCR recusa data URL ≥ `_MAX_DATA_IMAGE` (2_500_000 chars). Split aceita o mesmo still. | confirmado |
| Escape no HTML | `paintCopy` interpola o texto cru em `<span>${value}</span>` | confirmado no JS — **defeito de XSS** |

`logo_text` não é o arquivo oficial do logo. Contrato preservado.

---

## 4. Fundo

| Tópico | Achado | Tipo |
|---|---|---|
| `classify_ground` | Amostra o quadro; ≥ 28% dos pontos a distância &lt; 48 da tinta → `paper`; senão `image`. Inclui pessoa e tipo na amostra. | confirmado no código |
| Wash | `paper` **ou** `not cast_ok` → retângulo sólido da tinta | confirmado |
| Leftover | Só `image` **e** `cast_ok`. Cola o still menos a máscara. **Mantém tipo, logo e grafismo** fora da pessoa. | confirmado (`test_split_leftover_foto_mantem_pixels_fora_da_mascara`) |
| Image 2 | `generate_image()` / `build_image_payload()` **não têm `mask`**. Só prompt + até 2 `input_references`. | confirmado |
| Parâmetros extra | `mask` no callable seria `**_extra` ignorado em `_image_callable` do service | confirmado no código |
| Papel + Image 2 | `CreativeConflictError`: *Este still é papel...* | confirmado por teste existente |
| CAST_PROMPT | Texto morto em `decompose.py`. Não é chamado. | confirmado |

Hipótese (Arraial, sessão anterior, não reexecutada agora): cartela 1:1 com foto + bandeirola foi `image` mesmo com campo lilás estável, porque a amostragem vê variação.

---

## 5. Frontend

Arquivo: `aicentralv2/static/js/mc-camadas.js`.

| Tópico | Achado | Tipo |
|---|---|---|
| Limpar poço substitui o pacote? | Sim. `showPack` faz `grid.innerHTML = ...` e `paintCopy(data.read)`. Decompose não manda `read` nem `cast`. Pessoa e chips somem. | confirmado |
| Estados anteriores | `showStill` limpa grid/copy; `showPack` não faz merge | confirmado |
| Resposta antiga vs still novo | Sem `operationId`. `split()` chama `showPack` sem checar se `imageUrl` ainda é o daquele POST. | confirmado no código; **não reproduzido** com dois stills nesta fase |
| Overlay vs `object-fit` | Caixas em % no overlay `inset:0`; img tem `width:100%`, `max-height:26rem`, `object-fit:contain`. Letterbox desalinha caixa e pixel. | confirmado no CSS; sem prova visual nesta fase |
| Copy “16:9” | Label do drop e docstring de `hypothetical_still`. Preview **não** força `aspect-ratio: 16/9`. | confirmado |

---

## 6. Geometria do example

| Fonte | Valor |
|---|---|
| `hypothetical_still()` | 480 × 180 |
| Razão | 2,667 (8:3) |
| 16:9 | 1,778 |
| Image 2 no lifestyle 320×180 | mapeia para `16:9` (`width/height >= 1.45`) |

Aspecto nativo do still é preservado no split Python (`width`/`height` = `source.size`). Image 2 **não** preserva razões fora de 16:9 / 9:16 / 1:1.

---

## 7. Infraestrutura

| Recurso | Existe para Camadas? |
|---|---|
| Fila / worker | Não |
| Cache Redis | `CACHE_TYPE` no app; Camadas não usa |
| Storage de acetatos | Não; data URL na resposta |
| Métricas | Não específicas |
| Feature flag | Nenhuma. Padrão do repo: env em `config.py` |
| Dependências opcionais | rembg, ultralytics **fora** de `requirements.txt` |
| Testes | `python3 -m unittest` (pytest ausente neste Mac) |

---

## 8. Problemas priorizados

Não são “comportamento desejado”. Teste de regressão da correção = Fase 2, salvo P0 de segurança se autorizado à parte.

| ID | Problema | Prioridade | Correção planejada |
|---|---|---|---|
| P1 | Limpar poço apaga pessoa e chips | P0 produto | `replace:ground` + merge no JS | **feito Fase 2** (unittest de fonte; sem browser) |
| P2 | Sem ID de operação; resposta atrasada pinta still novo | P0 produto | `operation_id` | **feito Fase 2** (lógica no JS; race não reproduzida no browser) |
| P3 | OCR interpolado sem escape | P0 segurança | `escapeHtml` | **feito Fase 2** |
| P4 | `cast_ok` único para vários estados | P1 contrato | `cast_status` aditivo | **feito Fase 2** (`cast_ok` permanece) |
| P5 | OCR slim descarta dates/venue/status | P1 copy | `read_full` | **feito Fase 2** |
| P6 | Leftover não é fundo limpo | P1 asset | Natureza vs estratégia | Fase 5 |
| P7 | Image 2 sem máscara; prompt só promete poço vazio | P1 fundo | Declarar limitação; composição determinística | Fase 5 |
| P8 | Escada não faz fallback após rejeição | P2 qualidade | Policy Fase 6; cache de sessão Fase 3 |
| P9 | Example 480×180 documentado como 16:9 | P2 docs/fixture | Fixture 16:9 verdadeira **ou** copy honesta | Fase 2 |
| P10 | Overlay % vs letterbox | P2 UI | Overlay no box da imagem | Fase 5 |
| P11 | Sem aviso de motor opcional ausente | P2 honestidade | `capabilities` no payload | Fase 2 |
| P12 | `_open_image` sem teto de pixels | P2 segurança | Limite de decode | Fase 2 |
| P13 | HTTP callable keys no service | P2 segurança | Strip no route | Fase 2 |

---

## 9. O que esta fase **não** validou

- Qualidade visual de rembg / YOLO / Image 2 em criativos reais.
- Se o leftover do Arraial ou TIM “parece” papel (sessões anteriores são memória, não reteste desta fase).
- Race de duas requisições no browser.
- Custo ou latência de OpenRouter.
