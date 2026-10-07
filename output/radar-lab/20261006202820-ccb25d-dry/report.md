# Radar Lab — 20261006202820-ccb25d

Prompts v1.0 · cenário **cemig** · tema: conta de luz, bandeira tarifária, calor e consumo consciente no fim do ano · praças: Minas Gerais, Belo Horizonte · janela: 30 dias · 1 token Cadu = US$ 0.00016059

## Comparação dos fluxos

| Fluxo | Oport. | Nota revisor (1–5) | Fontes A/B | URLs abrem | Na janela | Selo alta/média/baixa | Tokens simulados | Tokens debitados | US$ provedor | Tempo |
|---|---|---|---|---|---|---|---|---|---|---|
| F1 Perplexity + imprensa | 5 | — | 0% | 0% | 100% | 0/0/5 | 435 | 0 | 0.0000 | 0.1 s |
| F2 OpenAI nativo | 5 | — | 0% | 0% | 100% | 0/0/5 | 8.253 | 0 | 0.0000 | 0.0 s |
| F3 Evidência primeiro (Firecrawl + Python) | 5 | — | 0% | 100% | 100% | 0/0/5 | 144 | 0 | 0.0000 | 1.7 s |

## Custo por chamada: simulado x real

| Fluxo | Etapa | Modelo | Rota | Regime | Simulado (tokens Cadu) | Debitado (tokens Cadu) | US$ provedor | Entrada/saída | Tempo | Nota |
|---|---|---|---|---|---|---|---|---|---|---|
| F2 | discover_open | openai/gpt-5-mini | openrouter | custo | 82 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | discover_open | perplexity/sonar-pro | openrouter | custo | 160 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F2 | discover_press | openai/gpt-5-mini | openrouter | custo | 82 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | discover_press | perplexity/sonar | openrouter | custo | 49 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F2 | judge | gpt-5-mini | openai | tokens | 8.014 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F2 | check | openai/gpt-5-mini | openrouter | custo | 75 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 83 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | check | perplexity/sonar | openrouter | custo | 40 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F3 | google_news | python/rss | python | gratis | 0 | 0 | 0.00000 | 0/0 | 1.5 s | 23 manchetes |
| F3 | search | firecrawl/search | firecrawl | firecrawl | 95 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F3 | judge | google/gemini-2.5-flash | openrouter | custo | 39 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F3 | check | deepseek/deepseek-v3.2 | openrouter | custo | 10 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| REV | review | anthropic/claude-haiku-4.5 | openrouter | custo | 91 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |

## Oportunidades

### F1 — Perplexity + imprensa

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

### F2 — OpenAI nativo

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

### F3 — Evidência primeiro (Firecrawl + Python)

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
