# Camadas lab — decisões

## D1 — Fase 1 não altera o runtime

- Data: 2026-09-12
- Decisão: nenhum arquivo de produção da Camadas muda na Fase 1.
- Motivo: preservar o funcionamento atual; o briefing pede diagnóstico e baseline, não adapters.
- Status: aceita

## D2 — Lab começa em OFF, sem flag nova

- Data: 2026-09-12
- Decisão: não criar `CAMADAS_LAB_MODE` ainda.
- Motivo: o projeto configura features por env em `aicentralv2/config.py` (`PI_HANDOFF_GATE`, `CACHE_TYPE`, etc.). Criar flag sem consumidor viola “não criar sistema paralelo”. A Fase 3 introduz a env quando houver código que a leia.
- Status: aceita

## D3 — Shadow não roda dentro do request Flask

- Data: 2026-09-12
- Decisão: Fase 3 começa por comando offline. Não há Celery/RQ no pacote da modelagem.
- Evidência: busca por `celery`, `rq.Queue`, `huey` em `aicentralv2/` sem matches. Há status `queued` em jobs de outra feature (`creative_modeling_repository.py`), não reutilizável sem desenho.
- Status: aceita; infraestrutura de fila permanece pendente de autorização

## D4 — Testes de caracterização não cristalizam defeito como desejo

- Data: 2026-09-12
- Decisão: testes da Fase 1 descrevem o contrato atual (geometria, slim OCR, first-available). Defeitos (race, XSS, merge do poço) ficam documentados em `evaluation.md`; o teste de JS só caracteriza o fonte (`showPack` substitui o grid, sem `operationId` / `escapeHtml`) e será atualizado quando a Fase 2 corrigir.
- Status: aceita

## D5 — Callables de teste continuam injeção Python

- Data: 2026-09-12
- Decisão: `payload.predictor` e `payload.text_callable` só funcionam se forem callables Python. JSON da mesa não entrega executável.
- Evidência: `split_still` / `_text_callable` exigem `callable(...)`. String no JSON é ignorada.
- Risco residual: um caller interno Python pode injetar callable via o mesmo dict. Fase 2 deve recusar chaves de callable quando o payload veio de HTTP.
- Status: aceita; endurecimento HTTP feito na Fase 2 (`strip_client_injections` na rota)

## D6 — Fase 2 escolhida em vez de refinar a Fase 1

- Data: 2026-09-12
- Decisão: avançar para contratos/P0. Refinar Fase 1 não destrava rembg, YOLO nem dataset.
- Status: aceita

## D7 — Candidato fake fica fora do request

- Data: 2026-09-12
- Decisão: `compare_segmenters` não é chamado por `split_layers`. Default = baseline.
- Status: aceita

## D8 — Image 2 não apaga pessoa/OCR no cliente

- Data: 2026-09-12
- Decisão: payload `replace: "ground"`; JS faz merge com `lastNonGround` e `lastRead`.
- Status: aceita

## D9 — Confiança calibrada não existe ainda

- Data: 2026-09-12
- Decisão: `cast_score_raw` pode ser cobertura; `cast_confidence` fica `None`.
- Status: aceita
