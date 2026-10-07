# Radar Lab — 20261006204001-0b7ac1

Cenário **cemig** · tema: conta de luz, bandeira tarifária, calor e consumo consciente no fim do ano · praças: Minas Gerais, Belo Horizonte · janela: 30 dias · 1 token Cadu = US$ 0.00016056 · tempo total 334.4 s

Melhor versão de prompts: **1.0** · ruído médio do revisor (fluxo sem mudança, de uma passada para outra): 0.29 ponto(s)

## Comparação dos fluxos (melhor versão de cada um)

| Fluxo | Tipo | Oport. | Revisor (1–5) | Notas por volta (por versão) | Evidências | Fontes A/B | URLs abrem | Na janela | Selo a/m/b | Tokens sim. | Tokens debitados | US$ provedor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 Perplexity + imprensa | perplexity | 3 | **4.73** | v1.0: 4.15 → 4.73 → 4.67 | 13 | 100% | 100% | 100% | 3/0/0 | 554 | 519 | 0.0829 |
| F5 Grok + web e X | web | 2 | **4.7** | v1.0: 4.7 → 4.2 → 3.9 | 14 | 67% | 100% | 100% | 2/0/0 | 242 | 805 | 0.1290 |
| F3 Evidência primeiro (Firecrawl + Python) | evidence | 3 | **3.93** | v1.0: 3.2 → 2.4 → 3.93 | 14 | 80% | 100% | 100% | 1/2/0 | 393 | 293 | 0.0468 |
| F4 Gemini + busca Google | web | 4 | **2.15** | v1.0: 1.75 → 2.15 → 2.1 | 14 | 67% | 33% | 0% | 0/4/0 | 709 | 1.947 | 0.3120 |
| F2 OpenAI nativo | web | 0 | **—** | v1.0: — → — → — | 11 | — | — | — | 0/0/0 | 6.338 | 7.961 | 0.0692 |
| F6 Claude Sonnet + busca Anthropic | web | 0 | **—** | v1.0: — → — → — | 10 | — | — | — | 0/0/0 | 500 | 10.027 | 1.6096 |
| F7 Híbrido: Perplexity + RSS, juiz Sonnet | perplexity | 0 | **—** | v1.0: — → — → — | 14 | — | — | — | 0/0/0 | 499 | 605 | 0.0967 |

Revisor e médico de prompts (compartilhados): 753 tokens debitados, US$ 0.1206. Total da rodada: 22.910 tokens, US$ 2.4668.

## Versões de prompt

| Versão | Média dos fluxos | Vencedor do revisor | Notas por fluxo |
|---|---|---|---|
| 1.0 | 3.878 | F1 | F1 4.73, F2 None, F3 3.93, F4 2.15, F5 4.7, F6 None, F7 None |

**Médico de prompts → v1.1** (a partir da v1.0): 0 mudança(s) aceita(s), 0 recusada(s).

**Revisor (anthropic/claude-haiku-4.5), última passada da melhor versão:** vencedor F1. Sistema B entrega 3 oportunidades com veracidade máxima (fontes gov.br e cemig.com.br abertas), recência confirmada (datas 2026-09-29 a 2026-10-05 dentro da janela), aderência total (serviço direto ao cliente Cemig em MG) e ação imediata (conteúdo planejável esta semana). Todas as fontes abrem, os scores editorial/paid são altos (79-90) e as teses são ancoradas em fatos verificáveis (bandeira verde vigente, páginas de serviço existentes). Sistema C fica em segundo (boa aderência e recência, mas veracidade reduzida por fonte C e scores mais baixos); A e D ficam descartados (A: datas 2024 fora da janela; D: scores muito baixos e teses óbvias).
- F1: Sistema B entrega 3 oportunidades com fontes gov.br e cemig.com.br abertas, datas vigentes na janela de 30 dias, e teses ancoradas em fatos verificáveis (bandeira verde confirmada, páginas de serviço existentes). Todas as URLs abrem e os scores editorial/paid são altos (79-90). Melhor em: Veracidade (fontes A abertas), recência (datas 2026-09-29 a 2026-10-05), ação (conteúdo planejável esta semana), aderência (serviço direto ao cliente Cemig).. Pior em: Novidade (B1 e B3 são educativas mas previsíveis; B2 é evergreen sem urgência semanal)..
- F3: Sistema C oferece 3 oportunidades com mix de fontes A e C, datas recentes (set-out 2026) dentro da janela, e teses contextualizadas (onda de calor, Tarifa Social, consumo consciente). Scores editorial/paid moderados a altos (70-82), mas uma fonte C em C1 reduz confiança geral. Melhor em: Aderência (temas alinhados com marca e público), recência (datas 2026), relevância contextual (calor + fim de ano).. Pior em: Veracidade (C1 tem fonte nível C que reduz para 4; C2 e C3 têm scores editorial/paid mais baixos que B); novidade (temas genéricos de consumo consciente e benefícios)..
- F4: Sistema A apresenta 4 oportunidades com datas e janelas em 2024 (nov-dez 2024, out-jan 2025), fora da janela de 30 dias atual (hoje 2026-10-06). Fontes incluem nível C e URLs quebradas. Vereditos mistos (parcial, contestado, confirmado) indicam inconsistência editorial. Melhor em: Aderência (temas relevantes: negociação débitos, segurança, chuvas); scores editorial/paid moderados (62-85).. Pior em: Recência (todas as datas são 2024, fora da janela); veracidade (fontes quebradas, nível C em A4); ação (impossível planejar mídia para campanhas de 2024 em outubro 2026)..
- F5: Sistema D oferece 2 oportunidades com fontes A abertas e datas na janela (2026-09-28 a 2026-09-29), mas scores editorial/paid muito baixos (31-58) e quadrantes 'ignorar'. Uma fonte é nível C. Teses são óbvias (consumo consciente com bandeira verde; atualizar cadastro). Melhor em: Recência (datas 2026 na janela); veracidade (D1 tem URL Cemig específica que abre).. Pior em: Novidade (teses genéricas e previsíveis); ação (scores baixos sugerem baixa prioridade); aderência (D2 tem score editorial 36, indicando fraca relevância editorial)..

## Custo por chamada: simulado x real

| Versão | Fluxo | Etapa | Modelo | Rota | Regime | Simulado | Debitado | US$ provedor | Entrada/saída | Tempo | Nota |
|---|---|---|---|---|---|---|---|---|---|---|---|
|  | F3 | google_news | python/rss | python | gratis | 0 | 0 | 0.00000 | 0/0 | 0.2 s | 23 manchetes |
|  | F3 | search | firecrawl/search | firecrawl | firecrawl | 95 | 32 | 0.00514 | 0/0 | 1.3 s | 0 fontes, 0 lidas |
| 1.0 | F1 | discover_press | perplexity/sonar | openrouter | custo | 49 | 43 | 0.00689 | 1.807/83 | 3.5 s |  |
|  | F3 | search-open | firecrawl/search | firecrawl | firecrawl | 95 | 32 | 0.00514 | 0/0 | 3.6 s | 8 fontes, 0 lidas |
| 1.0 | F1 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 37 | 0.00592 | 275/649 | 7.0 s |  |
| 1.0 | F4 | discover_open | google/gemini-3-flash-preview | openrouter | custo | 117 | 34 | 0.00531 | 1.583/1.506 | 9.0 s |  |
| 1.0 | F4 | discover_press | google/gemini-3-flash-preview | openrouter | custo | 117 | 371 | 0.05942 | 1.802/839 | 9.1 s |  |
| 1.0 | F1 | discover_open | perplexity/sonar-pro | openrouter | custo | 160 | 151 | 0.02410 | 1.639/879 | 10.1 s |  |
| 1.0 | F2 | discover_press | openai/gpt-5-mini | openrouter | custo | 82 | 85 | 0.01353 | 10.289/1.110 | 11.5 s |  |
|  | F3 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 32 | 0.00514 | 0/0 | 11.1 s |  |
|  | F3 | extract-python | python/html | python | gratis | 0 | 0 | 0.00000 | 0/0 | 1.5 s | 2/2 lidas |
| 1.0 | F5 | discover_open | x-ai/grok-4.3 | openrouter | custo | 64 | 270 | 0.04325 | 22.134/1.363 | 12.5 s |  |
| 1.0 | F2 | discover_open | openai/gpt-5-mini | openrouter | custo | 82 | 300 | 0.04816 | 23.930/1.720 | 22.8 s |  |
| 1.0 | F7 | discover_press | perplexity/sonar | openrouter | custo | 49 | 43 | 0.00681 | 1.807/6 | 2.9 s |  |
| 1.0 | F5 | discover_press | x-ai/grok-4.3 | openrouter | custo | 65 | 249 | 0.03997 | 17.506/2.419 | 18.8 s |  |
| 1.0 | F7 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 37 | 0.00579 | 275/518 | 6.5 s |  |
| 1.0 | F7 | discover_open | perplexity/sonar-pro | openrouter | custo | 160 | 142 | 0.02269 | 1.639/785 | 9.3 s |  |
|  | F1 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 64 | 0.01028 | 0/0 | 27.8 s |  |
| 1.0 | F6 | discover_open | anthropic/claude-sonnet-5 | openrouter | custo | 164 | 1.954 | 0.31369 | 118.192/2.731 | 33.7 s |  |
|  | F7 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 64 | 0.01028 | 0/0 | 25.0 s |  |
|  | F7 | google_news | python/rss | python | gratis | 0 | 0 | 0.00000 | 0/0 | 0.2 s | 23 manchetes |
| 1.0 | F6 | discover_press | anthropic/claude-sonnet-5 | openrouter | custo | 165 | 7.785 | 1.24984 | 526.805/5.623 | 77.5 s |  |
| 1.0 | F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 80 | 78 | 0.01246 | 5.485/1.854 | 12.9 s |  |
| 1.0 | F4 | judge | google/gemini-3-flash-preview | openrouter | custo | 50 | 62 | 0.00992 | 5.248/2.433 | 14.3 s |  |
| 1.0 | F3 | judge | google/gemini-2.5-flash | openrouter | custo | 39 | 51 | 0.00817 | 6.803/2.451 | 16.9 s |  |
| 1.0 | F4 | check | google/gemini-3-flash-preview | openrouter | custo | 109 | 454 | 0.07282 | 374/879 | 8.3 s |  |
| 1.0 | F2 | judge | gpt-5-mini | openai | tokens | 6.174 | 7.576 | 0.00749 | 4.376/3.200 | 27.9 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F3 | check | deepseek/deepseek-v3.2 | openrouter | custo | 11 | 32 | 0.00510 | 8.522/562 | 14.9 s |  |
| 1.0 | F5 | judge | x-ai/grok-4.3 | openrouter | custo | 63 | 59 | 0.00944 | 4.786/1.436 | 12.3 s |  |
| 1.0 | F1 | check | perplexity/sonar | openrouter | custo | 41 | 38 | 0.00604 | 488/552 | 27.4 s |  |
| 1.0 | F5 | check | x-ai/grok-4.3 | openrouter | custo | 50 | 227 | 0.03629 | 15.586/856 | 7.2 s |  |
| 1.0 | F6 | judge | anthropic/claude-sonnet-5 | openrouter | custo | 171 | 288 | 0.04610 | 7.051/3.200 | 30.1 s |  |
| 1.0 | F7 | judge | anthropic/claude-sonnet-5 | openrouter | custo | 187 | 319 | 0.05110 | 9.551/3.200 | 31.2 s |  |
| 1.0 | REV | review-1.0-r0 | anthropic/claude-haiku-4.5 | openrouter | custo | 170 | 138 | 0.02205 | 10.306/2.348 | 18.6 s |  |
| 1.0 | F1 | revise-r1 | openai/gpt-5.4-mini | openrouter | custo | 80 | 71 | 0.01134 | 5.602/1.587 | 10.0 s |  |
| 1.0 | F4 | revise-r1 | google/gemini-3-flash-preview | openrouter | custo | 49 | 59 | 0.00945 | 4.735/2.361 | 13.1 s |  |
| 1.0 | F3 | revise-r1 | google/gemini-2.5-flash | openrouter | custo | 40 | 52 | 0.00829 | 7.750/2.386 | 13.7 s |  |
| 1.0 | F1 | check-r1 | perplexity/sonar | openrouter | custo | 41 | 37 | 0.00592 | 413/502 | 4.7 s |  |
| 1.0 | F4 | check-r1 | google/gemini-3-flash-preview | openrouter | custo | 109 | 452 | 0.07255 | 406/783 | 8.1 s |  |
| 1.0 | REV | review-1.0-r1 | anthropic/claude-haiku-4.5 | openrouter | custo | 166 | 128 | 0.02054 | 9.505/2.206 | 18.0 s |  |
| 1.0 | F3 | revise-r2 | google/gemini-2.5-flash | openrouter | custo | 40 | 49 | 0.00778 | 7.769/2.178 | 12.9 s |  |
| 1.0 | F4 | revise-r2 | google/gemini-3-flash-preview | openrouter | custo | 49 | 60 | 0.00952 | 4.733/2.386 | 13.8 s |  |
| 1.0 | F4 | check-r2 | google/gemini-3-flash-preview | openrouter | custo | 109 | 455 | 0.07300 | 395/933 | 8.5 s |  |
| 1.0 | F3 | check-r2 | deepseek/deepseek-v3.2 | openrouter | custo | 10 | 13 | 0.00204 | 7.008/548 | 36.6 s |  |
| 1.0 | REV | review-1.0-r2 | anthropic/claude-haiku-4.5 | openrouter | custo | 162 | 125 | 0.01998 | 7.707/2.455 | 19.9 s |  |
| 1.0 | DOC | doctor-1.0 | anthropic/claude-sonnet-5 | openrouter | custo | 217 | 362 | 0.05804 | 4.020/5.000 | 45.5 s |  |

## Oportunidades (melhor versão de cada fluxo)

### F1 — Perplexity + imprensa · revisor 4.73

- **Bandeira verde em MG: explique na conta e no app** · integrada · ed 90 / pago 87 · selo alta · verificação confirmado · revisor 4.8
  A ANEEL confirmou bandeira verde para outubro e a Cemig atualizou sua página com o mesmo status. A marca pode transformar isso em uma peça de serviço direto para clientes mineiros: informar que não há custo extra no mês e orientar o que continua pesando na fatura.
  - [A] gov.br · ok · 2026-09-29 · https://www.gov.br/aneel/pt-br
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/
  - [A] cemig.com.br · ok · s/ data · https://www.cemig.com.br/valores-e-tarifas/bandeira-tarifaria/
  Revisor: Bandeira verde confirmada em gov.br e Cemig.com.br com URLs abertas e datas na janela; ação imediata de serviço ao cliente.
- **Leia a conta Cemig: bandeiras, kWh e valor final** · integrada · ed 82 / pago 79 · selo alta · verificação confirmado · revisor 4.4
  A Cemig tem uma página própria para explicar a conta de luz e outra sobre bandeiras tarifárias. Isso permite uma ação educativa mais útil que um post genérico: mostrar, em formato curto, onde aparece a bandeira, como ler o consumo em kWh e como isso afeta o valor final.
  - [A] cemig.com.br · ok · s/ data · https://www.cemig.com.br/faturas/entenda-sua-conta/
  - [A] cemig.com.br · ok · s/ data · https://www.cemig.com.br/valores-e-tarifas/bandeira-tarifaria/
  - [A] dadosabertos.aneel.gov.br · ok · s/ data · https://dadosabertos.aneel.gov.br/dataset/bandeiras-tarifarias
  Revisor: Páginas próprias Cemig sobre fatura e bandeiras existem e abrem; conteúdo evergreen mas com baixa urgência semanal.
- **Conteúdo de serviço: como a bandeira verde muda a fatura** · integrada · ed 85 / pago 81 · selo alta · verificação confirmado · revisor 4.8
  Com a bandeira verde vigente e a explicação oficial disponível na ANEEL, a Cemig pode publicar uma nota curta e objetiva sobre o que muda e o que não muda na conta. A ação é mais forte se for ancorada em transparência e serviço, não em campanha genérica de economia.
  - [A] gov.br · ok · 2026-09-29 · https://www.gov.br/aneel/pt-br
  - [A] dadosabertos.aneel.gov.br · ok · 2026-10-05 · https://dadosabertos.aneel.gov.br/dataset/bandeiras-tarifarias/resource/0591b8f6-fe54-437b-b72b-1aa2efd46e42
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/
  Revisor: Conteúdo educativo ancorado em transparência com fontes oficiais abertas e vigentes; execução viável esta semana.

### F5 — Grok + web e X · revisor 4.7

- **Campanha de consumo consciente com bandeira verde** · ignorar · ed 58 / pago 53 · selo alta · verificação confirmado · revisor 4.2
  Cemig deve reforçar hábitos de economia mesmo com bandeira verde em outubro, pois a tarifa não cai e o calor de fim de ano pode elevar consumo.
  - [A] cemig.com.br · ok · 2026-09-28 · https://www.cemig.com.br/noticia/dicas-e-orientacoes/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  - [C] diariodocomercio.com.br · ok · 2026-09-29 · https://diariodocomercio.com.br/geral/bandeira-verde/
  Revisor: Fonte Cemig.com.br com URL específica abre; mas tese é óbvia (consumo consciente mesmo com bandeira verde).
- **Alerta sobre regularização da Tarifa Social até dezembro** · ignorar · ed 36 / pago 31 · selo alta · verificação confirmado · revisor 3.6
  Cemig precisa comunicar famílias de baixa renda sobre risco de perda de descontos caso não atualizem cadastro até 31/12/2026.
  - [A] itatiaia.com.br · ok · 2026-09-17 · https://www.itatiaia.com.br/ouropreto/cemig-alerta-para-risco-de-perda-de-descontos-na-conta-de-luz/
  Revisor: Fonte Itatiaia abre e data na janela; mas score editorial/paid baixos (36/31) indicam baixa prioridade interna.

### F3 — Evidência primeiro (Firecrawl + Python) · revisor 3.93

- **Alerta Cemig: Onda de calor e consumo consciente no fim de ano** · integrada · ed 82 / pago 79 · selo alta · verificação confirmado · revisor 4.2
  Com a previsão de onda de calor em Minas Gerais e o período de festas de fim de ano, a Cemig deve alertar seus clientes sobre o aumento do consumo de energia e a importância de práticas conscientes para evitar surpresas na conta de luz.
  - [A] g1.globo.com · ok · Sun, 27 Sep 2026 07:00:00 GMT · https://news.google.com/rss/articles/CBMitwFBVV95cUxPaEliQ054Y3FwWjhfSkthMmcxZTJWNElCTUlRR3JPSDZYenNuYjVpMl82Vk5WUXRjX3dZTEZESXAxaDM5WV9jOUNuNC1XRk9lTWw4aDMyYXB3aGlvU3B6cDBGQWNvQ0FiMmlwOW9wdmNVZ3NQYzNxUU5jT3hvcGdoZnFXYWY1dHBpU0NIRTllTGl0dnpVbkdNbU5HanJKcWRxMklLUzBlSDlWbTNhSHpELU1ES2JNb2fSAcYBQVVfeXFMTmo1M01hRlZiZkdPNUViSDY4ajVHcG9sYnRLbE8tcGJEU0V5eU1idVVEb3lCU2V1UDEzeGE3d181SnA1WmpBWWxLd3gtX2lZdlZ5YzhwZ3dpU2Q0eDZycXE4X05Bcktnd1QzTXJ0TVNjTWZ1YU1zdm9JNGVLMk9Nb2gtWF9aMlV0OG1PZ09jQjhKZHViekgzaDFFRU1xUVNaVnF2YUpMMmtBR3ZrWThUU25leF9yMjBoSEozR21lSm5oTC1VTE13?oc=5
  - [C] fiemg.com.br · ok · Tue, 29 Sep 2026 12:26:00 GMT · https://news.google.com/rss/articles/CBMi7wFBVV95cUxOSGF3Nmd4Q1llQjZjSlkzY05ZczA3bnZNeTZ3VlhPLTVsaDBGSWhWaHFZVjdCNmZ4MEdkbnhleEY1Tjl5OWFldmk0ZXE3bXFVNWQ3WHBLNWpDUS1lOTBYeV9qaGtrd0tfYXRTQTJDY1R3cnU3OVVoLWpaQzFVcEM2dVUtSWRNcXpBQzJHOTJ5SkN5N1p5RnhCWTI2Vl9TU290bmRld3V4Q1lKanktdkxrVmg4VnNnUEt0Q2Y5cklGendUU3BsR0dzMU1tdTlabU90UHhMSE9fdVl0NjdxYWctdnExZGhWU2hRM0U1RFY3aw?oc=5
  - [A] agenciabrasil.ebc.com.br · ok · Fri, 25 Sep 2026 07:00:00 GMT · https://news.google.com/rss/articles/CBMizgFBVV95cUxOM1d0OFQ1N1BoWHA0a3pJdVhCX3Z5dklHTzh5V1p6eC1SWlIzN3c5WHFtZDVlUHhhX1dwMGl3UndacUoxaEJJRmkwaEJjVmhYVEs5bWlNVlFDV1FidGlVS201RUlTdUVaWEFXdkxzXzBEVmVJTlNCeVQ1RTN2ODlxa21vRWRJcU1haTFuakU3VGZ3c092Y3VmSGE1TDdfV0RObjZLSk0tRDIyNzk1eW9tYi1OYzJEa05ZV1JrWVZEUEN0QTBwOFRQSm5hRG0tZw?oc=5
  Revisor: Onda de calor e fim de ano confirmados em fontes A; uma fonte C reduz veracidade; planejável mas genérico.
- **Cemig Explica: Bandeira Verde e o Consumo Consciente** · conteudo · ed 70 / pago 65 · selo media · verificação confirmado · revisor 3.6
  Mesmo com a bandeira verde, a Cemig deve educar seus clientes sobre o significado da bandeira tarifária e a importância contínua do consumo consciente, desmistificando a ideia de que a conta será 'barata' e prevenindo surpresas.
  - [A] g1.globo.com · ok · Fri, 02 Oct 2026 23:42:03 GMT · https://news.google.com/rss/articles/CBMi5gFBVV95cUxNMDEwQ0FOeGxmUk1UMXZNekxMc3BsUFNYYU9VM3B3cWItYldJSS1PLXdUN0VpUmVXdWZRMUNxaUpVYUpLQXVCN0FHUEpHQ29KTGRYSllUSXFPVDdGOFRKRnctWGxLR2JwN2RuR2xLcXl0VFdDcU4wM1hwbzNIcE1keG1iM3RGcTJ5UUh2YjlPbEhISG84S0NGU1ZELUtRVlJWeG1oN2RIaWpoY05Kb2ozOURyaDFuQjZETElCUC1nNTFzX3V2UUxZc2VPc2pzOW5xdkVnRmNma3hfQjd4b0JnODdvNi1aZ9IB9AFBVV95cUxPWkdiUTRTR24wVW1JajJ0REhRSDkxQkdxZldUNXM1VDBFWEdBUEV4UHJSTEpkZGVoY3c3TURSNks4ZzNBT0ZqOXdpZVJYSWNtcUtzeXNiUWJfU0Q5UENBa1VMMTV3Sk9mNVM2NEd5dHRjZjd4Z0s2eElOc1dQYVFiNEltM2lmY0xqSmFHc2Ita1p5SnE4bmpieXU5ZktJRHJLNXZoVXJJaEdaS3lQc2pRVlllSmh0ZnFWd3g2T1k5d1JJNnlFeWVmbERwclo0amxlMTdMeVNxMjlYaFlOVndtMmhJSUlHY1dsOFNucmt2dWhYVEcy?oc=5
  Revisor: Fonte G1 abre e está na janela; tema educativo mas genérico; execução menos urgente que B1/B3.
- **Cemig Alerta: Não perca o desconto da Tarifa Social** · integrada · ed 81 / pago 80 · selo media · verificação confirmado · revisor 4.0
  A Cemig deve alertar e orientar proativamente as famílias elegíveis sobre a importância da atualização cadastral para manter o benefício da Tarifa Social, evitando a perda de descontos essenciais na conta de luz.
  - [A] itatiaia.com.br · ok · Thu, 17 Sep 2026 07:00:00 GMT · https://news.google.com/rss/articles/CBMiogFBVV95cUxQVllsbXo2N1VKRjh1bmxvRkM3REtSOHAwbjA1NGpxOEw2NTF5eUZFalN6M3VfakJkT1piT2Y0MjY4VTc2WG1qSUhKLXM3R2p1LUpBeUJfYzZxaUJKWWV6R21fWHBoa1kxeVR3WkZwcDEwalp0dGdHeDl5VXQ5MlhGMGp0YmtIRmJPWXMzTE1zZmo0QzNtdHRUeWRfVGdaU1RKMWc?oc=5
  Revisor: Tarifa Social é relevante para público Cemig; fonte A abre; mas ação requer coordenação com área de benefícios.

### F4 — Gemini + busca Google · revisor 2.15

- **Alívio Financeiro Cemig: Negociação de Débitos com 90% de Desconto** · midia · ed 68 / pago 71 · selo media · verificação parcial · revisor 3.0
  Aproveitar a janela de lançamento da campanha de negociação da Cemig para converter inadimplentes em clientes regulares, utilizando o gatilho de descontos agressivos antes das festas de fim de ano.
  - [A] agenciaminas.mg.gov.br · ok · 2024-10-07 · https://www.agenciaminas.mg.gov.br/noticia/cemig-oferece-condicoes-especiais-para-clientes-quitarem-debitos-com-ate-90-de-desconto
  Revisor: Fonte A (agenciaminas) mas data 2024-10-07 fora da janela 2026; desconto de 90% não verificado em fontes atuais.
- **Estratégia de Sobrevivência à Bandeira Vermelha Patamar 2** · ignorar · ed 59 / pago 56 · selo media · verificação confirmado · revisor 2.0
  Mitigar o impacto da tarifa mais cara do sistema (Bandeira Vermelha 2) educando o consumidor sobre o custo extra de R$ 7,87 a cada 100 kWh, posicionando a Cemig como aliada na economia.
  - [A] g1.globo.com · quebrado · 2024-09-28 · https://g1.globo.com/economia/noticia/2024/09/27/aneel-anuncia-bandeira-tarifaria-vermelha-patamar-2-para-outubro.ghtml
  - [A] cnnbrasil.com.br · quebrado · 2024-09-27 · https://www.cnnbrasil.com.br/economia/macroeconomia/aneel-define-bandeira-vermelha-patamar-2-para-outubro-a-mais-cara-do-sistema/
  Revisor: URLs quebradas em G1 e CNN; data 2024-09-27 fora da janela; bandeira vermelha não é contexto atual (verde em outubro 2026).
- **Operação Segurança: Proteção contra Golpes de PIX no Fim de Ano** · integrada · ed 80 / pago 74 · selo media · verificação confirmado · revisor 2.2
  Combater o aumento de fraudes em contas de luz falsas via PIX, utilizando o canal oficial da Cemig para validar pagamentos e proteger o cliente.
  - [A] otempo.com.br · quebrado · 2024-10-22 · https://www.otempo.com.br/cidades/2024/10/22/cemig-alerta-para-golpes-na-conta-de-luz-saiba-como-se-proteger
  Revisor: O Tempo URL quebrada; data 2024-10-22 fora da janela; tema relevante mas sem fonte verificável atual.
- **Campanha Varejo Consciente: Climatização e Black Friday em BH** · ignorar · ed 47 / pago 46 · selo media · verificação contestado · revisor 1.4
  Conectar a alta demanda por aparelhos de ventilação no comércio de BH com a redução tarifária de 1,92% aprovada pela Aneel, incentivando a troca por aparelhos eficientes.
  - [C] canalenergia.com.br · quebrado · 2024-10-15 · https://www.canalenergia.com.br/noticias/53292415/aneel-aprova-reducao-media-de-192-nas-tarifas-da-cemig-d
  - [C] diariodocomercio.com.br · ok · 2024-10-28 · https://diariodocomercio.com.br/economia/comercio-de-bh-espera-crescimento-nas-vendas-de-fim-de-ano/
  Revisor: Duas fontes C com URLs quebradas; redução de 1,92% não confirmada em fontes A; Black Friday genérica e forçada.

### F2 — OpenAI nativo · revisor —


### F6 — Claude Sonnet + busca Anthropic · revisor —


### F7 — Híbrido: Perplexity + RSS, juiz Sonnet · revisor —

