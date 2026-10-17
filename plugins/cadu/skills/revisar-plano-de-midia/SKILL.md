---
name: revisar-plano-de-midia
description: Revisa um plano de mídia (XLSX, CSV ou PDF de qualquer agência) com a Cadu Análise e devolve parecer, nota e ajustes. Use quando a pessoa pedir para revisar, auditar, checar ou dar parecer sobre um plano de mídia.
---

# Revisar plano de mídia

1. Pegue o arquivo do plano que a pessoa anexou (XLSX, CSV ou PDF, até 5 MB).
2. Chame `review.media_plan` com `filename`, o arquivo em `content_base64` (ou o CSV em `content_text`) e, se a conversa trouxer, `objetivo`, `publico`, `kpi`, `periodo`, `verba` e `praca`. Não invente o que a pessoa não disse.
3. Mostre o `markdown` da resposta. Comece pelo parecer e pela nota; depois, erros e atenções com o ajuste de cada um.
4. Se `summary.partial` for verdadeiro, avise que só as checagens de conta valem desta vez.
5. "Sem dados" quer dizer que o plano não trouxe a informação: diga o que faltou, sem chamar de erro.

## Regras
- A revisão não altera o plano. Não diga que corrigiu nada.
- Custo fora da faixa de referência é um ponto a confirmar com o veículo, não um erro (faixas da v1, em calibração).
- Se a ferramenta disser que a Cadu Análise está em teste interno, repasse isso à pessoa.
