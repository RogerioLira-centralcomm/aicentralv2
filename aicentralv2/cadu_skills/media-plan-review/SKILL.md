---
name: cadu-revisar-plano-de-midia
description: Revisa planos de mídia (XLSX, CSV ou PDF de qualquer agência) com a Cadu Análise. Confere verba, conta de entrega, período, concentração e custos e julga canais, público, funil e mensuração. Use quando a pessoa pedir para revisar, auditar, checar ou dar parecer sobre um plano de mídia. Não use para montar um plano novo.
metadata:
  version: 1.0.0
  owner: CentralX
---

# Revisar plano de mídia com a Cadu Análise

A revisão roda no Cadu: o código confere a conta e o TypeSafe julga a estratégia. Você envia o arquivo e mostra o parecer. Você não refaz as contas por conta própria nem altera o plano.

## Antes de enviar

1. Pegue o arquivo do plano que a pessoa anexou ou indicou (XLSX, CSV ou PDF, até 5 MB).
2. Se a conversa trouxer objetivo, público, KPI, período ou verba que não estejam no arquivo, envie esses dados junto. Não invente o que a pessoa não disse.

## Como enviar

**Se o servidor MCP `cadu` estiver conectado**, chame a ferramenta `review.media_plan` com:
- `filename`: o nome do arquivo com extensão;
- `content_base64`: o arquivo em base64 (ou `content_text` com o CSV em texto);
- quando houver: `objetivo`, `publico`, `kpi`, `periodo`, `verba`, `praca`.

**Sem MCP**, use a API com a chave da pessoa na variável `CADU_API_KEY` (criada em Workspace › Integrações › Agentes):

```bash
curl -sS -H "Authorization: Bearer $CADU_API_KEY" \
  -F file=@"plano.xlsx" -F objetivo="awareness" -F verba="R$ 250.000" \
  https://workspace.centralcomm.media/mcp/cadu/v1/reviews/media-plan
```

Nunca escreva a chave na resposta nem em arquivos.

## Como responder

1. Mostre o campo `markdown` da resposta, sem resumir os achados de erro ou atenção.
2. Comece pelo parecer (`summary.verdict_label`) e pela nota. Depois, os erros, as atenções e o ajuste sugerido de cada um.
3. Se `summary.partial` for verdadeiro, avise que a parte estratégica ficou de fora desta vez e que só as checagens de conta valem.
4. Critério "Sem dados" quer dizer que o plano não trouxe a informação. Diga o que faltou; não chame isso de erro.
5. Ofereça revisar de novo depois que a pessoa corrigir o arquivo.

## Limites

- A revisão não altera o plano nem fala com veículos.
- As faixas de custo são referências da v1, ainda em calibração. Custo fora da faixa é um ponto a confirmar, não um erro.
- Se a API responder que a Cadu Análise está em teste interno, diga isso à pessoa e não tente contornar.
