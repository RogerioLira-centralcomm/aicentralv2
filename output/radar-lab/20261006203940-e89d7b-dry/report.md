# Radar Lab — 20261006203940-e89d7b

Cenário **cemig** · tema: conta de luz, bandeira tarifária, calor e consumo consciente no fim do ano · praças: Minas Gerais, Belo Horizonte · janela: 30 dias · 1 token Cadu = US$ 0.00016056 · tempo total 3.4 s

Melhor versão de prompts: **1.0** · ruído médio do revisor (fluxo sem mudança, de uma passada para outra): — ponto(s)

## Comparação dos fluxos (melhor versão de cada um)

| Fluxo | Tipo | Oport. | Revisor (1–5) | Notas por volta (por versão) | Evidências | Fontes A/B | URLs abrem | Na janela | Selo a/m/b | Tokens sim. | Tokens debitados | US$ provedor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 Perplexity + imprensa | perplexity | 5 | **—** | v1.0: — → — → — | 10 | 0% | 0% | 100% | 0/0/5 | 690 | 0 | 0.0000 |
| F2 OpenAI nativo | web | 5 | **—** | v1.0: — → — → — | 10 | 0% | 0% | 100% | 0/0/5 | 25.709 | 0 | 0.0000 |
| F3 Evidência primeiro (Firecrawl + Python) | evidence | 5 | **—** | v1.0: — → — → — | 14 | 0% | 100% | 100% | 0/0/5 | 339 | 0 | 0.0000 |
| F4 Gemini + busca Google | web | 5 | **—** | v1.0: — → — → — | 10 | 0% | 0% | 100% | 0/0/5 | 730 | 0 | 0.0000 |
| F5 Grok + web e X | web | 5 | **—** | v1.0: — → — → — | 10 | 0% | 0% | 100% | 0/0/5 | 526 | 0 | 0.0000 |
| F6 Claude Sonnet + busca Anthropic | web | 5 | **—** | v1.0: — → — → — | 10 | 0% | 0% | 100% | 0/0/5 | 1.338 | 0 | 0.0000 |
| F7 Híbrido: Perplexity + RSS, juiz Sonnet | perplexity | 5 | **—** | v1.0: — → — → — | 14 | 0% | 100% | 100% | 0/0/5 | 976 | 0 | 0.0000 |

Revisor e médico de prompts (compartilhados): 0 tokens debitados, US$ 0.0000. Total da rodada: 0 tokens, US$ 0.0000.

## Versões de prompt

| Versão | Média dos fluxos | Vencedor do revisor | Notas por fluxo |
|---|---|---|---|
| 1.0 | 0 | — | F1 None, F2 None, F3 None, F4 None, F5 None, F6 None, F7 None |

**Médico de prompts → v1.1** (a partir da v1.0): 0 mudança(s) aceita(s), 0 recusada(s).

## Custo por chamada: simulado x real

| Versão | Fluxo | Etapa | Modelo | Rota | Regime | Simulado | Debitado | US$ provedor | Entrada/saída | Tempo | Nota |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | F1 | discover_open | perplexity/sonar-pro | openrouter | custo | 160 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F1 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F1 | discover_press | perplexity/sonar | openrouter | custo | 49 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F4 | discover_open | google/gemini-3-flash-preview | openrouter | custo | 117 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F2 | discover_open | openai/gpt-5-mini | openrouter | custo | 82 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F2 | discover_press | openai/gpt-5-mini | openrouter | custo | 82 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F4 | discover_press | google/gemini-3-flash-preview | openrouter | custo | 117 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F5 | discover_open | x-ai/grok-4.3 | openrouter | custo | 64 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F5 | discover_press | x-ai/grok-4.3 | openrouter | custo | 65 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F6 | discover_open | anthropic/claude-sonnet-5 | openrouter | custo | 164 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F6 | discover_press | anthropic/claude-sonnet-5 | openrouter | custo | 165 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F7 | discover_open | perplexity/sonar-pro | openrouter | custo | 160 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F7 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F7 | discover_press | perplexity/sonar | openrouter | custo | 49 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
|  | F7 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
|  | F1 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
|  | F3 | google_news | python/rss | python | gratis | 0 | 0 | 0.00000 | 0/0 | 1.6 s | 23 manchetes |
|  | F7 | google_news | python/rss | python | gratis | 0 | 0 | 0.00000 | 0/0 | 1.5 s | 23 manchetes |
|  | F3 | search | firecrawl/search | firecrawl | firecrawl | 95 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
|  | F3 | search-open | firecrawl/search | firecrawl | firecrawl | 95 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 83 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F1 | check | perplexity/sonar | openrouter | custo | 41 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F2 | judge | gpt-5-mini | openai | tokens | 8.014 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F2 | check | openai/gpt-5-mini | openrouter | custo | 77 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F3 | judge | google/gemini-2.5-flash | openrouter | custo | 39 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F3 | check | deepseek/deepseek-v3.2 | openrouter | custo | 10 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F4 | judge | google/gemini-3-flash-preview | openrouter | custo | 55 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F4 | check | google/gemini-3-flash-preview | openrouter | custo | 109 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F5 | judge | x-ai/grok-4.3 | openrouter | custo | 78 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F5 | check | x-ai/grok-4.3 | openrouter | custo | 51 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F6 | judge | anthropic/claude-sonnet-5 | openrouter | custo | 196 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F6 | check | anthropic/claude-sonnet-5 | openrouter | custo | 135 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F7 | judge | anthropic/claude-sonnet-5 | openrouter | custo | 175 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F7 | check | perplexity/sonar | openrouter | custo | 41 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | REV | review-1.0-r0 | anthropic/claude-haiku-4.5 | openrouter | custo | 176 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F1 | revise-r1 | openai/gpt-5.4-mini | openrouter | custo | 86 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F1 | check-r1 | perplexity/sonar | openrouter | custo | 41 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F2 | revise-r1 | gpt-5-mini | openai | tokens | 8.650 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F2 | check-r1 | openai/gpt-5-mini | openrouter | custo | 77 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F3 | revise-r1 | google/gemini-2.5-flash | openrouter | custo | 40 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F3 | check-r1 | deepseek/deepseek-v3.2 | openrouter | custo | 10 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F4 | revise-r1 | google/gemini-3-flash-preview | openrouter | custo | 57 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F4 | check-r1 | google/gemini-3-flash-preview | openrouter | custo | 109 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F5 | revise-r1 | x-ai/grok-4.3 | openrouter | custo | 83 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F5 | check-r1 | x-ai/grok-4.3 | openrouter | custo | 51 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F6 | revise-r1 | anthropic/claude-sonnet-5 | openrouter | custo | 204 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F6 | check-r1 | anthropic/claude-sonnet-5 | openrouter | custo | 135 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F7 | revise-r1 | anthropic/claude-sonnet-5 | openrouter | custo | 183 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F7 | check-r1 | perplexity/sonar | openrouter | custo | 41 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | REV | review-1.0-r1 | anthropic/claude-haiku-4.5 | openrouter | custo | 176 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F1 | revise-r2 | openai/gpt-5.4-mini | openrouter | custo | 86 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F1 | check-r2 | perplexity/sonar | openrouter | custo | 41 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F2 | revise-r2 | gpt-5-mini | openai | tokens | 8.650 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F2 | check-r2 | openai/gpt-5-mini | openrouter | custo | 77 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F3 | revise-r2 | google/gemini-2.5-flash | openrouter | custo | 40 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F3 | check-r2 | deepseek/deepseek-v3.2 | openrouter | custo | 10 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F4 | revise-r2 | google/gemini-3-flash-preview | openrouter | custo | 57 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F4 | check-r2 | google/gemini-3-flash-preview | openrouter | custo | 109 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F5 | revise-r2 | x-ai/grok-4.3 | openrouter | custo | 83 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F5 | check-r2 | x-ai/grok-4.3 | openrouter | custo | 51 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F6 | revise-r2 | anthropic/claude-sonnet-5 | openrouter | custo | 204 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F6 | check-r2 | anthropic/claude-sonnet-5 | openrouter | custo | 135 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F7 | revise-r2 | anthropic/claude-sonnet-5 | openrouter | custo | 183 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | F7 | check-r2 | perplexity/sonar | openrouter | custo | 41 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | REV | review-1.0-r2 | anthropic/claude-haiku-4.5 | openrouter | custo | 176 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| 1.0 | DOC | doctor-1.0 | anthropic/claude-sonnet-5 | openrouter | custo | 203 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |

## Oportunidades (melhor versão de cada fluxo)

### F1 — Perplexity + imprensa · revisor —

- **Oportunidade simulada 1** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 2** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 3** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 4** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 5** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0

### F2 — OpenAI nativo · revisor —

- **Oportunidade simulada 1** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 2** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 3** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 4** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 5** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0

### F3 — Evidência primeiro (Firecrawl + Python) · revisor —

- **Oportunidade simulada 1** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
- **Oportunidade simulada 2** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
- **Oportunidade simulada 3** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
- **Oportunidade simulada 4** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
- **Oportunidade simulada 5** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5

### F4 — Gemini + busca Google · revisor —

- **Oportunidade simulada 1** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 2** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 3** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 4** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 5** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0

### F5 — Grok + web e X · revisor —

- **Oportunidade simulada 1** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 2** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 3** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 4** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 5** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0

### F6 — Claude Sonnet + busca Anthropic · revisor —

- **Oportunidade simulada 1** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 2** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 3** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 4** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0
- **Oportunidade simulada 5** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] exemplo.com.br · quebrado · 2026-10-01 · https://exemplo.com.br/0

### F7 — Híbrido: Perplexity + RSS, juiz Sonnet · revisor —

- **Oportunidade simulada 1** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
- **Oportunidade simulada 2** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
- **Oportunidade simulada 3** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
- **Oportunidade simulada 4** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
- **Oportunidade simulada 5** · ignorar · ed 0 / pago 0 · selo baixa · verificação nao_verificado · revisor —
  tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese tese 
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
