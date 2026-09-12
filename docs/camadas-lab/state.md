# Camadas lab — estado

Atualizado: 2026-09-12.

## Fase atual

**Fase 2 — Contratos, capacidades e adapters**  
Status: `validated` para contrato, fake candidate e regressão unittest. Validação visual: `blocked`.

## Fases concluídas

| Fase | Status |
|---|---|
| 1. Auditoria e baseline | `validated` no contrato/código |
| 2. Contratos e adapters | `validated` no contrato; visual `blocked` |
| 3. Shadow | `planned` |
| 4. Avaliação | `planned` |
| 5. Correção assistida | `planned` |
| 6. Roteamento | `planned` |
| 7. Integração e rollout | `planned` |

Modo do lab: **OFF**. Nenhum candidato entra no request default. `compare_segmenters` só é chamado por teste/comando.

## Escopo implementado (Fase 2)

- Baseline encapsulado com `engine_id`, `cast_status`, `cast_reason`, `cast_score_raw`, `cast_confidence=None`, `geometry`, `provenance`, `duration_ms`.
- Registry `list_capabilities()` via `importlib.util.find_spec` — sem baixar pesos.
- OCR: uma chamada; `read` (chips) + `read_full` (bloco completo).
- Image 2 devolve `replace: "ground"`; a mesa faz merge e conserva pessoa/copy.
- `operation_id` ecoado; cliente descarta resposta atrasada.
- Escape de OCR no HTML.
- HTTP remove `predictor` / `text_callable` / `image_callable`.
- Candidato fake comparável e removível sem mudar o default.

## Arquivos alterados

- `aicentralv2/creative_format_lab/camadas_lab.py` (novo)
- `aicentralv2/creative_format_lab/split_layers.py`
- `aicentralv2/creative_format_lab/engineer.py`
- `aicentralv2/creative_format_lab/service.py`
- `aicentralv2/creative_modeling_routes.py`
- `aicentralv2/static/js/mc-camadas.js`
- `aicentralv2/templates/parametros/_mc_camadas.html`
- `aicentralv2/templates/parametros/modelagem_desk.html` (`mc_page_js?v=53`)
- `tests/test_creative_format_lab.py`
- `tests/test_modelagem_criativos.py` (cache JS)
- `docs/camadas-lab/*`

## Testes realmente executados

`PYTHONPATH=. python3 -m unittest` — **27 testes, OK, 4,69 s** (Python 3.9).

Inclui regressão da Fase 1 + capabilities, compare fake/erro/ausente, geometria, `cast_status=rejected`, `read_full`, rota que descarta injections, desk `v=53`.

`pytest` ausente neste ambiente.

## Bloqueios

- rembg / ultralytics ausentes. Qualidade visual não validada.
- Sem dataset autorizado.
- Sem fila. Shadow continua proibido in-request.

## Autorizações concedidas

| Autorização | Escopo |
|---|---|
| Fase 1 | Auditoria |
| Fase 2 (escolha do engenheiro, 2026-09-12) | Contratos e P0 de mesa. Sem motores novos, sem chamadas pagas, sem promoção. |

## Limitações conhecidas

- `cast_confidence` é sempre `None` (score cru ≠ confiança calibrada).
- Image 2 ainda sem máscara (`limitation: no_mask`).
- Leftover ainda guarda tipo (Fase 5).
- Overlay % vs letterbox (Fase 5).
- Example ainda é 480×180; copy do drop deixou de afirmar 16:9.

## Próxima ação recomendada

**Fase 3**: comando offline de shadow + env `CAMADAS_LAB_MODE=off` (default). Sem thread no Flask. Sem provedor novo.
