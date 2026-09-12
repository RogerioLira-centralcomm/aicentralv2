# Camadas lab — plano ajustado ao repositório

O briefing original (Fases 1–7) permanece a direção. Este arquivo ajusta **como** executar no CentralX de hoje, sem inventar infra.

Documento de produto: [`docs/camadas.md`](../camadas.md).

## Condições reais

- Mesa síncrona no request Flask. Sem worker de Camadas.
- Flags = variáveis de ambiente em `config.py`, não um serviço de feature flags.
- Testes = `unittest`. Sem pytest neste ambiente.
- rembg / YOLO opcionais e **ausentes** no Python da auditoria.
- OCR e Image 2 passam por OpenRouter já existente (`chat_completion`, `generate_image`).
- Trocr já evoluiu o OCR (`status`, `dates`, `venue`, `normalize_read`). A Camadas ainda projeta o slim de `read_attached_still`.

## Fase 1 (esta)

Aceite: explicar o que funciona, o que é ambíguo e o que muda, sem motor novo.

Entregue. Ver `state.md` e `evaluation.md`.

## Fase 2 — contratos (feita)

Aceite do briefing: candidato fake conecta, compara e some sem mudar o default. `cast_ok` e chips preservados.

P12 (teto de pixels em `_open_image`) ficou para um ciclo futuro — não bloqueia o aceite.

## Fase 3 — shadow (próxima, só com comando)

Default OFF. Sem thread no request.

1. Comando offline (`python -m ...`) se não houver fila aprovada.
2. Env `CAMADAS_LAB_MODE=off|shadow` só quando o comando existir.
3. Allowlist + timeout + um candidato fake local.
4. Não enviar stills reais a provedor novo.

## Fase 4 — benchmark

Manifesto de dataset **sem** imagens no Git. Validação visual = `blocked` até acervo autorizado. Fixtures sintéticas medem contrato, não vencedor.

## Fase 5 — correção assistida

Depois dos contratos. Priorizar P6/P7/P10. Sem editor gráfico completo.

## Fase 6 — roteamento

Policy versionada, dry-run, fallback ≤ 1. Ativação ROUTED exige aprovação explícita.

## Fase 7 — outras mesas

Reusar persistência do Trocr/modelagem. Manifesto de pacote. Sem histórico editorial duplicado.

## Gates que exigem autorização sua

- Instalar rembg, ultralytics, PaddleOCR, SAM, BiRefNet ou baixar pesos.
- Chamada paga (OpenRouter ou outro).
- Enviar criativo real a provedor novo.
- Ativar shadow/assisted/routed fora de OFF.
- Coletar acervo persistente de stills/rostos.
- Promover candidato a motor principal.
