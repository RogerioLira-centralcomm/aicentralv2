# Radar Lab — 20261006202313-1a3052

Prompts v1.0 · cenário **cemig** · tema: conta de luz, bandeira tarifária, calor e consumo consciente no fim do ano · praças: Minas Gerais, Belo Horizonte · janela: 30 dias · 1 token Cadu = US$ 0.00001000

## Comparação dos fluxos

| Fluxo | Oport. | Nota revisor (1–5) | Fontes A/B | URLs abrem | Na janela | Selo alta/média/baixa | Tokens simulados | Tokens debitados | US$ provedor | Tempo |
|---|---|---|---|---|---|---|---|---|---|---|
| F1 Perplexity + imprensa | 5 | — | 0% | 0% | 100% | 0/0/5 | 6.334 | 0 | 0.0000 | 0.1 s |
| F2 OpenAI nativo | 5 | — | 0% | 0% | 100% | 0/0/5 | 10.488 | 0 | 0.0000 | 0.0 s |
| F3 Evidência primeiro (Firecrawl + Python) | 5 | — | 0% | 0% | 100% | 0/0/5 | 2.303 | 0 | 0.0000 | 0.6 s |

## Custo por chamada: simulado x real

| Fluxo | Etapa | Modelo | Rota | Regime | Simulado (tokens Cadu) | Debitado (tokens Cadu) | US$ provedor | Entrada/saída | Tempo | Nota |
|---|---|---|---|---|---|---|---|---|---|---|
| F2 | discover_open | openai/gpt-5-mini | openrouter | custo | 1.271 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | discover_open | perplexity/sonar-pro | openrouter | custo | 2.196 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F2 | discover_press | openai/gpt-5-mini | openrouter | custo | 1.274 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | discover_press | perplexity/sonar | openrouter | custo | 648 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | discover_trends | perplexity/sonar | openrouter | custo | 630 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F2 | judge | gpt-5-mini | openai | tokens | 6.741 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F2 | check | openai/gpt-5-mini | openrouter | custo | 1.202 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | extract | firecrawl/scrape | firecrawl | firecrawl | 1.000 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 1.226 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F1 | check | perplexity/sonar | openrouter | custo | 634 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F3 | google_news | python/rss | python | gratis | 0 | 0 | 0.00000 | 0/0 | 0.4 s | 0 manchetes |
| F3 | search | firecrawl/search | firecrawl | firecrawl | 1.500 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F3 | judge | google/gemini-2.5-flash | openrouter | custo | 625 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| F3 | check | deepseek/deepseek-v3.2 | openrouter | custo | 178 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |
| REV | review | anthropic/claude-haiku-4.5 | openrouter | custo | 1.288 | 0 | 0.00000 | 0/0 | 0.0 s | simulado (dry-run) |

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
