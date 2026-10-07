# Radar Lab — 20261006204639-58f871

Cenário **cemig** · tema: conta de luz, bandeira tarifária, calor e consumo consciente no fim do ano · praças: Minas Gerais, Belo Horizonte · janela: 30 dias · 1 token Cadu = US$ 0.00016039 · tempo total 839.4 s

Melhor versão de prompts: **1.1** · ruído médio do revisor (fluxo sem mudança, de uma passada para outra): 0.21 ponto(s)

## Comparação dos fluxos (melhor versão de cada um)

| Fluxo | Tipo | Oport. | Revisor (1–5) | Notas por volta (por versão) | Evidências | Fontes A/B | URLs abrem | Na janela | Selo a/m/b | Tokens sim. | Tokens debitados | US$ provedor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F3 Evidência primeiro (Firecrawl + Python) | evidence | 2 | **4.6** | v1.0: 3.8 → 3.0 → 3.6 · v1.1: 4.6 → 3.8 → 3.4 | 14 | 38% | 100% | 100% | 1/1/0 | 515 | 265 | 0.0419 |
| F7 Híbrido: Perplexity + RSS, juiz Sonnet | perplexity | 1 | **4.6** | v1.0: 3.73 → 3.53 → 4.8 · v1.1: 3.6 → 3.72 → 4.6 | 14 | 100% | 100% | 100% | 1/0/0 | 2.017 | 3.662 | 0.5865 |
| F1 Perplexity + imprensa | perplexity | 4 | **4.45** | v1.0: 4.45 → 4.3 → 4.3 · v1.1: 4.45 → 4.35 → 4.3 | 14 | 83% | 100% | 100% | 4/0/0 | 623 | 509 | 0.0810 |
| F5 Grok + web e X | web | 1 | **4.4** | v1.0: 3.5 → 4.2 → 4.6 · v1.1: 3.3 → 4.4 → 4.4 | 14 | 50% | 100% | 100% | 1/0/0 | 703 | 1.702 | 0.2720 |
| F2 OpenAI nativo | web | 3 | **4.27** | v1.0: 4.08 → 4.1 → 4.35 · v1.1: 4.05 → 4.27 → 4.27 | 9 | 100% | 100% | 86% | 3/0/0 | 34.797 | 35.938 | 0.2476 |
| F4 Gemini + busca Google | web | 3 | **2.47** | v1.0: 1.45 → 1.8 → 1.8 · v1.1: 2.47 → 1.67 → 1.67 | 13 | 57% | 57% | 0% | 0/3/0 | 1.402 | 3.748 | 0.6002 |
| F6 Claude Sonnet + busca Anthropic | web | 3 | **1.6** | v1.0: 1.67 → 2.0 → 1.47 · v1.1: 1.6 → 1.4 → 1.4 | 10 | 0% | 100% | 0% | 3/0/0 | 2.095 | 2.673 | 0.4278 |

Revisor e médico de prompts (compartilhados): 1.232 tokens debitados, US$ 0.1970. Total da rodada: 49.729 tokens, US$ 2.4541.

## Versões de prompt

| Versão | Média dos fluxos | Vencedor do revisor | Notas por fluxo |
|---|---|---|---|
| 1.0 | 3.686 | F2 | F1 4.45, F2 4.35, F3 3.8, F4 1.8, F5 4.6, F6 2.0, F7 4.8 |
| 1.1 | 3.77 | F7 | F1 4.45, F2 4.27, F3 4.6, F4 2.47, F5 4.4, F6 1.6, F7 4.6 |

**Médico de prompts → v1.1** (a partir da v1.0): 1 mudança(s) aceita(s), 2 recusada(s).
- `revise`: Reduz a reincidência de itens fora da janela, baseados em agregadores/fontes C ou contexto histórico irrelevante, e força substituição por ações realmente acionáveis.
- recusada `judge`: cresceu demais
- recusada `verify`: cresceu demais

**Revisor (anthropic/claude-haiku-4.5), última passada da melhor versão:** vencedor F7. B1 é a oportunidade mais forte: fato verificável (bandeira verde outubro/2026 confirmada por ANEEL em 25/09), fontes A robustas (gov.br, agenciabrasil, g1, cemig.com.br), tese clara (alívio real + consumo consciente), aderência máxima à marca Cemig, ação imediata (48-72h em owned media). Sistema B prioriza qualidade sobre quantidade, evitando ruído de fontes C e oportunidades fora da janela.
- F1: 4 oportunidades com foco em bandeira verde, calor e consumo consciente. Mistura fontes A (gov.br, cemig.com.br, jc.uol) com C (sampi, rede98), reduzindo veracidade em A2. Quadrantes variados (conteúdo, integrada, ignorar). Melhor em: Estrutura editorial clara (80-81 pontos), janelas bem definidas, alinhamento com tema da marca.. Pior em: A2 e A4 usam fontes C que enfraquecem veracidade; A4 é genérica e fora da janela de 30 dias..
- F7: 1 oportunidade focada e bem documentada: bandeira verde + consumo consciente. Fontes A robustas (gov.br, agenciabrasil, g1, cemig.com.br). Mensagem clara e executável. Melhor em: Veracidade máxima (5), recência máxima (5), aderência máxima (5), ação imediata (5). Tese bem fundamentada.. Pior em: Apenas 1 oportunidade; falta diversidade de ângulos (calor, fim de ano, tarifa social não aparecem)..
- F4: 3 oportunidades com dados de 2024 e fora da janela de 30 dias. Fontes C predominam (ifmg, canalsolar com URL quebrada). Veredito parcial/confirmado mas sem relevância temporal. Melhor em: Editorial alto (81-90 pontos em C3), conceitos educativos válidos (histórico de consumo, eficiência).. Pior em: Veracidade máxima 2, recência máxima 1, todas fora da janela. Nível C sozinho nunca passa de 2 em veracidade (regra aplicada)..
- F5: 1 oportunidade de alerta via Cemig Atende (push/email). Fontes A + C, fato verificável (bandeira verde + calor). Quadrante ignorar, veredito parcial. Melhor em: Aderência alta (5), recência alta (5), ação viável em 1-2 semanas, tese específica.. Pior em: Editorial baixo (57), paid baixo (54), quadrante ignorar, veredito parcial; requer integração técnica..
- F3: 2 oportunidades: campanha educativa genérica (E1) e comunicação sobre Tarifa Social (E2). Fontes mistas (A + C), janelas longas (até janeiro, contínua). Veredito parcial/confirmado. Melhor em: E2 toca em tema social relevante (Tarifa Social), editorial alto (85). E1 integra bandeira verde + calor + fim de ano.. Pior em: E1 é genérica (80 editorial mas novidade 2), E2 tem fontes C fracas (diariodeuberlandia, radiotropical), ambas fora da janela de 30 dias..
- F2: 3 oportunidades: comunicação imediata sobre bandeira verde (F1), dashboard de bandeiras (F2), lembretes de fim de ano (F3). Fontes A robustas. Veredito confirmado/parcial. Melhor em: F1 é crítica e imediata (78 editorial, 5 ação, 48-72h), F2 é inovadora (4 novidade), F3 consolida orientações existentes.. Pior em: F2 requer 2-6 semanas (ação 2), F3 é fora da janela de 30 dias (nov-dez), F1 é similar a B1..
- F6: 3 oportunidades sobre reajuste tarifário de 6,50% em maio/2026. Todas fora da janela de 30 dias (passado). Fontes C (edgar.tools) com datas incoerentes. Editorial e paid zerados em G2 e G3. Melhor em: Nenhum; todas as oportunidades estão fora da janela temporal.. Pior em: Veracidade máxima 2, recência máxima 1, editorial zerado em 2 de 3, fora da janela; não são oportunidades atuais..

## Custo por chamada: simulado x real

| Versão | Fluxo | Etapa | Modelo | Rota | Regime | Simulado | Debitado | US$ provedor | Entrada/saída | Tempo | Nota |
|---|---|---|---|---|---|---|---|---|---|---|---|
|  | F3 | google_news | python/rss | python | gratis | 0 | 0 | 0.00000 | 0/0 | 1.6 s | 23 manchetes |
|  | F3 | search | firecrawl/search | firecrawl | firecrawl | 95 | 32 | 0.00513 | 0/0 | 1.3 s | 0 fontes, 0 lidas |
| 1.0 | F1 | discover_press | perplexity/sonar | openrouter | custo | 49 | 43 | 0.00687 | 1.807/65 | 4.7 s |  |
|  | F3 | search-open | firecrawl/search | firecrawl | firecrawl | 95 | 32 | 0.00513 | 0/0 | 2.0 s | 8 fontes, 0 lidas |
| 1.0 | F2 | discover_press | openai/gpt-5-mini | openrouter | custo | 88 | 74 | 0.01186 | 10.115/297 | 5.9 s |  |
| 1.0 | F1 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 38 | 0.00601 | 275/735 | 7.0 s |  |
| 1.0 | F4 | discover_press | google/gemini-3-flash-preview | openrouter | custo | 127 | 279 | 0.04474 | 1.802/612 | 7.9 s |  |
|  | F3 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 16 | 0.00257 | 0/0 | 3.6 s |  |
|  | F3 | extract-python | python/html | python | gratis | 0 | 0 | 0.00000 | 0/0 | 2.0 s | 3/3 lidas |
| 1.0 | F1 | discover_open | perplexity/sonar-pro | openrouter | custo | 161 | 149 | 0.02388 | 1.639/864 | 11.1 s |  |
| 1.0 | F4 | discover_open | google/gemini-3-flash-preview | openrouter | custo | 126 | 556 | 0.08914 | 1.583/1.450 | 15.0 s |  |
| 1.0 | F6 | discover_press | anthropic/claude-sonnet-5 | openrouter | custo | 196 | 137 | 0.02181 | 7.342/13 | 4.1 s |  |
|  | F1 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 64 | 0.01026 | 0/0 | 8.8 s |  |
| 1.0 | F2 | discover_open | openai/gpt-5-mini | openrouter | custo | 88 | 162 | 0.02592 | 14.406/1.794 | 21.3 s |  |
| 1.0 | F7 | discover_press | perplexity/sonar | openrouter | custo | 49 | 43 | 0.00686 | 1.807/51 | 2.7 s |  |
| 1.0 | F5 | discover_open | x-ai/grok-4.3 | openrouter | custo | 71 | 300 | 0.04807 | 25.026/1.846 | 15.2 s |  |
| 1.0 | F7 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 37 | 0.00589 | 275/610 | 6.3 s |  |
| 1.0 | F7 | discover_open | perplexity/sonar-pro | openrouter | custo | 161 | 123 | 0.01971 | 1.639/586 | 7.2 s |  |
| 1.0 | F5 | discover_press | x-ai/grok-4.3 | openrouter | custo | 73 | 245 | 0.03920 | 22.992/2.390 | 20.7 s |  |
|  | F7 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 64 | 0.01026 | 0/0 | 4.7 s |  |
|  | F7 | google_news | python/rss | python | gratis | 0 | 0 | 0.00000 | 0/0 | 0.2 s | 23 manchetes |
| 1.0 | F6 | discover_open | anthropic/claude-sonnet-5 | openrouter | custo | 194 | 322 | 0.05159 | 7.295/3.000 | 32.9 s |  |
| 1.0 | F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 109 | 78 | 0.01244 | 5.404/1.864 | 12.2 s |  |
| 1.0 | F3 | judge | google/gemini-2.5-flash | openrouter | custo | 56 | 30 | 0.00476 | 6.803/1.743 | 12.3 s |  |
| 1.0 | F4 | judge | google/gemini-3-flash-preview | openrouter | custo | 70 | 60 | 0.00954 | 5.038/2.341 | 12.8 s |  |
| 1.0 | F1 | check | perplexity/sonar | openrouter | custo | 46 | 39 | 0.00610 | 477/620 | 5.3 s |  |
| 1.0 | F4 | check | google/gemini-3-flash-preview | openrouter | custo | 123 | 453 | 0.07252 | 337/785 | 7.4 s |  |
| 1.0 | F2 | judge | gpt-5-mini | openai | tokens | 6.517 | 6.919 | 0.00737 | 3.697/3.222 | 26.1 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F5 | judge | x-ai/grok-4.3 | openrouter | custo | 81 | 58 | 0.00915 | 4.909/1.260 | 10.0 s |  |
| 1.0 | F3 | check | deepseek/deepseek-v3.2 | openrouter | custo | 12 | 13 | 0.00206 | 7.210/455 | 24.8 s |  |
| 1.0 | F5 | check | x-ai/grok-4.3 | openrouter | custo | 62 | 229 | 0.03663 | 16.255/1.115 | 9.4 s |  |
| 1.0 | F2 | check | openai/gpt-5-mini | openrouter | custo | 86 | 378 | 0.06049 | 26.315/2.357 | 27.1 s |  |
| 1.0 | F7 | judge | anthropic/claude-sonnet-5 | openrouter | custo | 255 | 311 | 0.04985 | 9.784/3.028 | 28.8 s |  |
| 1.0 | F6 | judge | anthropic/claude-sonnet-5 | openrouter | custo | 221 | 349 | 0.05583 | 4.591/4.665 | 47.8 s |  |
| 1.0 | F7 | check | perplexity/sonar | openrouter | custo | 45 | 38 | 0.00600 | 426/575 | 5.5 s |  |
| 1.0 | F6 | check | anthropic/claude-sonnet-5 | openrouter | custo | 180 | 242 | 0.03876 | 5.335/2.109 | 28.4 s |  |
| 1.0 | REV | review-1.0-r0 | anthropic/claude-haiku-4.5 | openrouter | custo | 147 | 195 | 0.03125 | 13.328/3.585 | 25.7 s |  |
| 1.0 | F4 | revise-r1 | google/gemini-3-flash-preview | openrouter | custo | 68 | 38 | 0.00607 | 4.471/1.278 | 7.8 s |  |
| 1.0 | F5 | revise-r1 | x-ai/grok-4.3 | openrouter | custo | 75 | 49 | 0.00771 | 4.063/1.108 | 9.3 s |  |
| 1.0 | F3 | revise-r1 | google/gemini-2.5-flash | openrouter | custo | 57 | 45 | 0.00708 | 7.491/1.933 | 10.8 s |  |
| 1.0 | F4 | check-r1 | google/gemini-3-flash-preview | openrouter | custo | 122 | 356 | 0.05709 | 279/317 | 5.2 s |  |
| 1.0 | F5 | check-r1 | x-ai/grok-4.3 | openrouter | custo | 61 | 246 | 0.03938 | 18.463/1.111 | 11.0 s |  |
| 1.0 | F2 | revise-r1 | gpt-5-mini | openai | tokens | 7.174 | 7.507 | 0.00730 | 4.405/3.102 | 26.0 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F2 | check-r1 | openai/gpt-5-mini | openrouter | custo | 86 | 237 | 0.03786 | 17.881/2.096 | 18.0 s |  |
| 1.0 | F6 | revise-r1 | anthropic/claude-sonnet-5 | openrouter | custo | 226 | 370 | 0.05929 | 5.274/4.874 | 61.9 s |  |
| 1.0 | F7 | revise-r1 | anthropic/claude-sonnet-5 | openrouter | custo | 250 | 671 | 0.10760 | 8.800/9.000 | 105.4 s |  |
| 1.0 | REV | review-1.0-r1 | anthropic/claude-haiku-4.5 | openrouter | custo | 142 | 175 | 0.02794 | 12.198/3.149 | 23.1 s |  |
| 1.0 | F3 | revise-r2 | google/gemini-2.5-flash | openrouter | custo | 57 | 39 | 0.00616 | 7.470/1.566 | 9.4 s |  |
| 1.0 | F4 | revise-r2 | google/gemini-3-flash-preview | openrouter | custo | 68 | 48 | 0.00759 | 4.111/1.846 | 9.7 s |  |
| 1.0 | F4 | check-r2 | google/gemini-3-flash-preview | openrouter | custo | 123 | 364 | 0.05837 | 343/732 | 7.3 s |  |
| 1.0 | F2 | revise-r2 | gpt-5-mini | openai | tokens | 7.000 | 7.220 | 0.00705 | 4.222/2.998 | 23.5 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F3 | check-r2 | deepseek/deepseek-v3.2 | openrouter | custo | 12 | 12 | 0.00189 | 6.651/401 | 18.3 s |  |
| 1.0 | F2 | check-r2 | openai/gpt-5-mini | openrouter | custo | 86 | 306 | 0.04899 | 22.039/2.146 | 22.0 s |  |
| 1.0 | F6 | revise-r2 | anthropic/claude-sonnet-5 | openrouter | custo | 226 | 299 | 0.04791 | 5.243/3.742 | 49.3 s |  |
| 1.0 | F7 | revise-r2 | anthropic/claude-sonnet-5 | openrouter | custo | 250 | 671 | 0.10750 | 8.751/9.000 | 95.9 s |  |
| 1.0 | F7 | check-r2 | perplexity/sonar | openrouter | custo | 44 | 35 | 0.00550 | 265/230 | 4.1 s |  |
| 1.0 | REV | review-1.0-r2 | anthropic/claude-haiku-4.5 | openrouter | custo | 138 | 165 | 0.02642 | 10.428/3.199 | 26.1 s |  |
| 1.0 | DOC | doctor-1.0 | openai/gpt-5.4 | openrouter | custo | 321 | 123 | 0.01963 | 2.735/853 | 12.2 s |  |
| 1.1 | F4 | judge | google/gemini-3-flash-preview | openrouter | custo | 70 | 50 | 0.00793 | 5.038/1.804 | 10.7 s |  |
| 1.1 | F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 109 | 60 | 0.00949 | 5.404/1.939 | 10.9 s |  |
| 1.1 | F3 | judge | google/gemini-2.5-flash | openrouter | custo | 56 | 32 | 0.00499 | 6.803/1.835 | 12.6 s |  |
| 1.1 | F1 | check | perplexity/sonar | openrouter | custo | 46 | 38 | 0.00595 | 483/469 | 4.7 s |  |
| 1.1 | F4 | check | google/gemini-3-flash-preview | openrouter | custo | 122 | 450 | 0.07215 | 293/669 | 6.8 s |  |
| 1.1 | F2 | judge | gpt-5-mini | openai | tokens | 6.517 | 6.418 | 0.00637 | 3.697/2.721 | 25.4 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.1 | F5 | judge | x-ai/grok-4.3 | openrouter | custo | 81 | 57 | 0.00912 | 4.909/1.248 | 11.4 s |  |
| 1.1 | F3 | check | deepseek/deepseek-v3.2 | openrouter | custo | 12 | 14 | 0.00211 | 7.502/391 | 19.0 s |  |
| 1.1 | F2 | check | openai/gpt-5-mini | openrouter | custo | 86 | 93 | 0.01489 | 9.341/1.678 | 15.5 s |  |
| 1.1 | F5 | check | x-ai/grok-4.3 | openrouter | custo | 62 | 241 | 0.03855 | 16.560/1.273 | 13.2 s |  |
| 1.1 | F6 | judge | anthropic/claude-sonnet-5 | openrouter | custo | 221 | 279 | 0.04467 | 4.591/3.549 | 35.9 s |  |
| 1.1 | F7 | judge | anthropic/claude-sonnet-5 | openrouter | custo | 255 | 391 | 0.06265 | 9.784/4.308 | 40.1 s |  |
| 1.1 | F6 | check | anthropic/claude-sonnet-5 | openrouter | custo | 179 | 227 | 0.03635 | 5.390/1.857 | 21.6 s |  |
| 1.1 | F7 | check | perplexity/sonar | openrouter | custo | 46 | 40 | 0.00629 | 537/753 | 5.7 s |  |
| 1.1 | REV | review-1.1-r0 | anthropic/claude-haiku-4.5 | openrouter | custo | 150 | 204 | 0.03262 | 14.086/3.707 | 27.5 s |  |
| 1.1 | F5 | revise-r1 | x-ai/grok-4.3 | openrouter | custo | 76 | 50 | 0.00792 | 4.137/1.182 | 12.3 s |  |
| 1.1 | F4 | revise-r1 | google/gemini-3-flash-preview | openrouter | custo | 68 | 52 | 0.00823 | 4.378/2.014 | 13.3 s |  |
| 1.1 | F4 | check-r1 | google/gemini-3-flash-preview | openrouter | custo | 123 | 542 | 0.08686 | 365/894 | 8.4 s |  |
| 1.1 | F5 | check-r1 | x-ai/grok-4.3 | openrouter | custo | 61 | 227 | 0.03626 | 16.228/981 | 9.9 s |  |
| 1.1 | F2 | revise-r1 | gpt-5-mini | openai | tokens | 6.983 | 6.536 | 0.00557 | 4.287/2.249 | 25.3 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.1 | F6 | revise-r1 | anthropic/claude-sonnet-5 | openrouter | custo | 226 | 231 | 0.03690 | 5.270/2.636 | 31.2 s |  |
| 1.1 | F2 | check-r1 | openai/gpt-5-mini | openrouter | custo | 86 | 88 | 0.01397 | 9.031/1.258 | 11.8 s |  |
| 1.1 | F7 | revise-r1 | anthropic/claude-sonnet-5 | openrouter | custo | 257 | 682 | 0.10932 | 9.661/9.000 | 102.0 s |  |
| 1.1 | REV | review-1.1-r1 | anthropic/claude-haiku-4.5 | openrouter | custo | 148 | 197 | 0.03151 | 13.590/3.584 | 27.2 s |  |
| 1.1 | F4 | revise-r2 | google/gemini-3-flash-preview | openrouter | custo | 69 | 51 | 0.00812 | 4.516/1.954 | 11.8 s |  |
| 1.1 | F4 | check-r2 | google/gemini-3-flash-preview | openrouter | custo | 123 | 449 | 0.07187 | 356/565 | 6.8 s |  |
| 1.1 | F6 | revise-r2 | anthropic/claude-sonnet-5 | openrouter | custo | 226 | 217 | 0.03466 | 5.276/2.411 | 28.1 s |  |
| 1.1 | F7 | revise-r2 | anthropic/claude-sonnet-5 | openrouter | custo | 257 | 521 | 0.08347 | 9.660/6.415 | 68.7 s |  |
| 1.1 | F7 | check-r2 | perplexity/sonar | openrouter | custo | 45 | 35 | 0.00561 | 290/324 | 3.7 s |  |
| 1.1 | REV | review-1.1-r2 | anthropic/claude-haiku-4.5 | openrouter | custo | 140 | 173 | 0.02763 | 11.383/3.250 | 27.4 s |  |

## Oportunidades (melhor versão de cada fluxo)

### F3 — Evidência primeiro (Firecrawl + Python) · revisor 4.6

- **Campanha de Conscientização: Consumo Inteligente no Verão e Fim de Ano** · integrada · ed 80 / pago 78 · selo alta · verificação parcial · revisor 3.8
  Com a bandeira verde em outubro, mas o alerta de consumo consciente e a previsão de onda de calor, a Cemig deve lançar uma campanha educativa para orientar seus clientes sobre o uso eficiente de energia, evitando surpresas na conta de luz durante o período de festas e altas temperaturas.
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
  - [C] correioregional.net · ok · Tue, 29 Sep 2026 17:13:42 GMT · https://news.google.com/rss/articles/CBMi3gFBVV95cUxNWGkzdEFRRWRiSWd5TE8zcnZtNTlYSENkZTVneXFHSTR5a1dIR2ZyeWVqMmdkNjhpN0s1dWU5bTZhMWVKbWFsQ0x3V2ZRbUFmdUVWd0pQNExRTkhiRFI2c1RUYUpaR0NwVTR0STN6cVpfQi1WUXBfbjFXS0RVWlExR0dqZ1I5ellLbDhrQWJJcGRvUUF5c0c1S1NTbkN6MkVBblhQZEhQUnBHWU1VVU1BUUg2MkVnXzV6dmFMR1l4VXZKS3FOdU9ySEs0RzNUWDFrT2t1OTktS1dNNGtONUE?oc=5
  - [A] g1.globo.com · ok · Sun, 27 Sep 2026 07:00:00 GMT · https://news.google.com/rss/articles/CBMitwFBVV95cUxPaEliQ054Y3FwWjhfSkthMmcxZTJWNElCTUlRR3JPSDZYenNuYjVpMl82Vk5WUXRjX3dZTEZESXAxaDM5WV9jOUNuNC1XRk9lTWw4aDMyYXB3aGlvU3B6cDBGQWNvQ0FiMmlwOW9wdmNVZ3NQYzNxUU5jT3hvcGdoZnFXYWY1dHBpU0NIRTllTGl0dnpVbkdNbU5HanJKcWRxMklLUzBlSDlWbTNhSHpELU1ES2JNb2fSAcYBQVVfeXFMTmo1M01hRlZiZkdPNUViSDY4ajVHcG9sYnRLbE8tcGJEU0V5eU1idVVEb3lCU2V1UDEzeGE3d181SnA1WmpBWWxLd3gtX2lZdlZ5YzhwZ3dpU2Q0eDZycXE4X05Bcktnd1QzTXJ0TVNjTWZ1YU1zdm9JNGVLMk9Nb2gtWF9aMlV0OG1PZ09jQjhKZHViekgzaDFFRU1xUVNaVnF2YUpMMmtBR3ZrWThUU25leF9yMjBoSEozR21lSm5oTC1VTE13?oc=5
  - [C] fiemg.com.br · ok · Tue, 29 Sep 2026 12:26:00 GMT · https://news.google.com/rss/articles/CBMi7wFBVV95cUxOSGF3Nmd4Q1llQjZjSlkzY05ZczA3bnZNeTZ3VlhPLTVsaDBGSWhWaHFZVjdCNmZ4MEdkbnhleEY1Tjl5OWFldmk0ZXE3bXFVNWQ3WHBLNWpDUS1lOTBYeV9qaGtrd0tfYXRTQTJDY1R3cnU3OVVoLWpaQzFVcEM2dVUtSWRNcXpBQzJHOTJ5SkN5N1p5RnhCWTI2Vl9TU290bmRld3V4Q1lKanktdkxrVmg4VnNnUEt0Q2Y5cklGendUU3BsR0dzMU1tdTlabU90UHhMSE9fdVl0NjdxYWctdnExZGhWU2hRM0U1RFY3aw?oc=5
  - [A] agenciabrasil.ebc.com.br · ok · Fri, 25 Sep 2026 07:00:00 GMT · https://news.google.com/rss/articles/CBMizgFBVV95cUxOM1d0OFQ1N1BoWHA0a3pJdVhCX3Z5dklHTzh5V1p6eC1SWlIzN3c5WHFtZDVlUHhhX1dwMGl3UndacUoxaEJJRmkwaEJjVmhYVEs5bWlNVlFDV1FidGlVS201RUlTdUVaWEFXdkxzXzBEVmVJTlNCeVQ1RTN2ODlxa21vRWRJcU1haTFuakU3VGZ3c092Y3VmSGE1TDdfV0RObjZLSk0tRDIyNzk1eW9tYi1OYzJEa05ZV1JrWVZEUEN0QTBwOFRQSm5hRG0tZw?oc=5
  Revisor: Campanha educativa genérica, fontes mistas (A + C), janela até janeiro é longa; conceito válido mas pouco específico.
- **Comunicação Proativa sobre Tarifa Social e Descontos** · integrada · ed 85 / pago 82 · selo media · verificação confirmado · revisor 3.0
  Diante da possibilidade de famílias perderem descontos da Tarifa Social, a Cemig deve intensificar a comunicação sobre os critérios e a importância da atualização cadastral, garantindo que os clientes elegíveis mantenham o benefício e reforçando seu compromisso social.
  - [C] diariodeuberlandia.com.br · ok · Sun, 27 Sep 2026 14:00:00 GMT · https://news.google.com/rss/articles/CBMixAFBVV95cUxOWnJSVHRibVRuWlhqZktDcmpFOUFndHpXa1VDcy1OSWl2RkpPUTdHblBXd19URXVCTk1Wci15YWpUZkNReUYxQTBJcHpsZEthcERTWjFESGpVUXZuSXFtbVhyYXh4X19FQUFQRHpCVlhSRm5JaExZdURIX3JFcS1wMl9CWG9mTGY1MkZCNmJfLWJlSG10LUI2YUxyVHN6MUVSOTdxQVJMREc0c2JNWGVHV1RrQ3M0aU9wMUVBeWsta0lRcnR4?oc=5
  - [A] itatiaia.com.br · ok · Thu, 17 Sep 2026 07:00:00 GMT · https://news.google.com/rss/articles/CBMiogFBVV95cUxQVllsbXo2N1VKRjh1bmxvRkM3REtSOHAwbjA1NGpxOEw2NTF5eUZFalN6M3VfakJkT1piT2Y0MjY4VTc2WG1qSUhKLXM3R2p1LUpBeUJfYzZxaUJKWWV6R21fWHBoa1kxeVR3WkZwcDEwalp0dGdHeDl5VXQ5MlhGMGp0YmtIRmJPWXMzTE1zZmo0QzNtdHRUeWRfVGdaU1RKMWc?oc=5
  - [C] radiotropical.net · ok · Tue, 22 Sep 2026 17:53:04 GMT · https://news.google.com/rss/articles/CBMipAFBVV95cUxNdmRkaTF6R2tRdWl3X0UtM3ZUdVh2Q3dHUGtvazBLMVlfX3ZSMGZHV0dMMHZiZHdfOGNpME1YY2R4dUs1QzJDOWZGczFZX3lGQWtGdDkxSUpVMXVDY3lUTFlTbmNpaU53cnZ3N0VuMWZPWFBvT1BXWWozYXJheC1ETVB6LTBrcnJfTEc3ak0wcGdSTFJzcDNPY2xnRERGbEZ3NGFTMA?oc=5
  Revisor: Tarifa Social é relevante mas fontes C (diariodeuberlandia, radiotropical) reduzem veracidade; ação contínua, não semanal.

### F7 — Híbrido: Perplexity + RSS, juiz Sonnet · revisor 4.6

- **Bandeira verde em outubro: comunicar alívio real e manter hábito consciente** · conteudo · ed 70 / pago 64 · selo alta · verificação confirmado · revisor 4.6
  ANEEL e a própria Cemig confirmaram que outubro/2026 opera em bandeira verde, encerrando a cobrança extra de R$1,85 por 100 kWh que vigorava desde maio sob bandeira amarela; é um fato recente e verificável que gera alívio financeiro concreto ao cliente mineiro, e a marca deve comunicá-lo de forma clara antes que a bandeira mude novamente, aproveitando a atenção já existente nos veículos regionais.
  - [A] gov.br · ok · 2026-09-29 · https://www.gov.br/aneel/pt-br
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/
  - [A] agenciabrasil.ebc.com.br · ok · 2026-09-26 · https://agenciabrasil.ebc.com.br/radioagencia-nacional/geral/audio/2026-09/conta-de-luz-sem-taxa-extra-em-outubro-bandeira-tarifaria-sera-verde
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/noticias/
  - [A] g1.globo.com · ok · 2026-09-25 · https://g1.globo.com/economia/noticia/2026/09/25/conta-de-luz-aneel-reduz-bandeira-tarifaria-para-verde-em-outubro.ghtml
  Revisor: Fato verificável (bandeira verde outubro), fontes A robustas, mensagem clara; execução imediata em owned media.

### F1 — Perplexity + imprensa · revisor 4.45

- **Atualizar canal sobre bandeira verde e consumo consciente** · conteudo · ed 81 / pago 60 · selo alta · verificação confirmado · revisor 4.8
  A Cemig deve usar o momento da bandeira verde em outubro para reforçar, em seus canais próprios, que a ausência de cobrança extra não elimina a necessidade de consumo consciente. Isso ajuda a alinhar expectativa do cliente e reduz risco de percepção de conta alta por uso elevado.
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/noticias/
  - [A] gov.br · ok · 2026-09-25 · https://www.gov.br/aneel/pt-br/assuntos/noticias/2026/bandeira-tarifaria-aneel-divulga-calendario-de-acionamento-para-2026
  Revisor: Bandeira verde confirmada por ANEEL (gov.br A, 25/09) e Cemig já publicou alerta; executável esta semana em canais próprios.
- **Campanha de calor: ar-condicionado e geladeira sem susto na conta** · conteudo · ed 75 / pago 61 · selo alta · verificação confirmado · revisor 4.4
  Com a cobertura ligando bandeira verde, onda de calor e aumento do uso de ar-condicionado, a Cemig pode publicar dicas práticas de economia para equipamentos de maior consumo. A ação responde a uma necessidade concreta do consumidor e reforça utilidade pública.
  - [C] sampi.net.br · ok · 2026-10-06 · https://sampi.net.br/jundiai/noticias/3009565/jundiai/2026/10/bandeira-verde-conta-de-luz-nao-tera-cobranca-extra-em-outubro
  - [C] rede98.com.br · ok · 2026-09-29 · https://rede98.com.br/98-news/conta-de-luz-tera-bandeira-verde-em-outubro-mas-consumo-exige-atencao/
  - [A] jc.uol.com.br · ok · 2026-09-28 · https://jc.uol.com.br/economia/2026/09/28/conta-de-luz-fica-sem-cobranca-extra-em-outubro-com-a-volta-da-bandeira-verde.html
  Revisor: Onda de calor real (pauta em evidência) mas fontes C (sampi, rede98) reduzem veracidade; conteúdo prático é aderente.
- **Guia Cemig da bandeira tarifária para clientes MG** · conteudo · ed 80 / pago 69 · selo alta · verificação confirmado · revisor 4.4
  A Cemig pode transformar a página de bandeira tarifária em um hub simples com explicação da cor vigente, impactos na conta e perguntas frequentes. Isso captura a intenção de busca e reduz fricção de atendimento em um tema regulatório recorrente.
  - [A] cemig.com.br · ok · s/ data · https://www.cemig.com.br/valores-e-tarifas/bandeira-tarifaria/
  - [A] dadosabertos.aneel.gov.br · ok · 2026-10-05 · https://dadosabertos.aneel.gov.br/dataset/bandeiras-tarifarias/resource/0591b8f6-fe54-437b-b72b-1aa2efd46e42
  - [A] gov.br · ok · 2026-09-25 · https://www.gov.br/aneel/pt-br/assuntos/noticias/2026/bandeira-tarifaria-aneel-divulga-calendario-de-acionamento-para-2026
  Revisor: Hub de bandeira tarifária é estrutural e útil, mas requer investimento técnico; não é ação imediata.
- **Ação regional de fim de ano: consumo consciente na conta** · ignorar · ed 63 / pago 48 · selo alta · verificação parcial · revisor 3.6
  No fim do ano, a Cemig pode amarrar a sazonalidade de calor e consumo consciente a uma campanha regional de prevenção de surpresa na conta. A oportunidade é reputacional e educativa, com tom de serviço público e proximidade local.
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/noticias/
  - [A] oglobo.globo.com · ok · 2026-09-25 · https://oglobo.globo.com/economia/noticia/2026/09/25/conta-de-luz-bandeira-tarifaria-sera-verde-em-outubro-e-contas-de-luz-devem-ter-alivio-decide-aneel.ghtml
  - [A] jc.uol.com.br · ok · 2026-09-28 · https://jc.uol.com.br/economia/2026/09/28/conta-de-luz-fica-sem-cobranca-extra-em-outubro-com-a-volta-da-bandeira-verde.html
  Revisor: Campanha de fim de ano é genérica e fora da janela (nov-dez); veredito parcial reflete isso.

### F5 — Grok + web e X · revisor 4.4

- **Alerta Cemig Atende: bandeira verde + calor exige consumo consciente** · ignorar · ed 57 / pago 54 · selo alta · verificação parcial · revisor 4.4
  Cemig deve enviar push e e-mail em outubro via Cemig Atende para clientes de MG alertando que bandeira verde (S1,S2) não reduz tarifa e que calor eleva consumo em até 40% (S3,S4), direcionando para dicas no site e app.
  - [A] agenciabrasil.ebc.com.br · ok · 2026-09-25 · https://agenciabrasil.ebc.com.br/economia/noticia/2026-09/apos-cinco-meses-conta-de-luz-voltara-bandeira-verde-em-outubro
  - [A] cemig.com.br · ok · 2026-09-28 · https://www.cemig.com.br/noticia/dicas-e-orientacoes/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  - [C] fiemg.com.br · ok · 2026-09-29 · https://www.fiemg.com.br/noticias/calor-intenso-favorece-setores-de-bebidas-e-sorvetes-mas-eleva-custos-de-energia-climatizacao-logistica-e-ate-do-cafe/
  - [C] em.com.br · ok · 2026-09-28 · https://www.em.com.br/gerais/2026/09/7509603-pico-de-calor-recorde-em-bh-altera-rotina-e-dispara-consumo-de-energia.html
  Revisor: Fato verificável (bandeira verde + calor), fontes A + C, mas push/email requer integração técnica; executável em 1-2 semanas.

### F2 — OpenAI nativo · revisor 4.27

- **Comunicação imediata: 'Bandeira verde não é desconto'** · conteudo · ed 78 / pago 59 · selo alta · verificação confirmado · revisor 4.8
  ANEEL confirmou bandeira verde para outubro/2026 (S1,S2) e a Cemig já publicou alerta explicando que isso não reduz a tarifa (S3); agir agora evita expectativas equivocadas e reclamações.
  - [A] gov.br · ok · 2026-09-25 · https://www.gov.br/aneel/pt-br/assuntos/noticias/2026-defeso-eleitoral/outubro-tera-bandeira-verde-contas-de-luz-sem-custo-extra
  - [A] agenciabrasil.ebc.com.br · ok · 2026-09-25 · https://agenciabrasil.ebc.com.br/economia/noticia/2026-09/apos-cinco-meses-conta-de-luz-voltara-bandeira-verde-em-outubro
  - [A] cemig.com.br · ok · 2026-09-28 · https://www.cemig.com.br/noticia/dicas-e-orientacoes/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  Revisor: Fato crítico (bandeira verde ≠ desconto), Cemig já publicou, fontes gov.br + agenciabrasil; executável em 48-72h.
- **Dashboard público: painel local com dados das bandeiras ANEEL** · ignorar · ed 61 / pago 36 · selo alta · verificação confirmado · revisor 4.0
  Portal de Dados Abertos da ANEEL atualizou base de bandeiras (S4) e clientes querem entender impacto na fatura; a Cemig pode publicar um painel local que traduza os dados federais para o cliente mineiro.
  - [A] dadosabertos.aneel.gov.br · ok · 2026-09-28 · https://dadosabertos.aneel.gov.br/pt_BR/dataset/bandeiras-tarifarias
  - [A] cemig.com.br · ok · 2026-09-28 · https://www.cemig.com.br/noticia/dicas-e-orientacoes/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  Revisor: Dashboard com dados ANEEL é inovador, mas requer 2-6 semanas de desenvolvimento; não é ação imediata.
- **Programa de lembretes práticos para o fim de ano (checklist e mensagens)** · conteudo · ed 70 / pago 52 · selo alta · verificação confirmado · revisor 4.0
  Cemig já mantém orientações práticas (S8) e publicou alerta sobre consumo consciente (S3); consolidar essas orientações em lembretes segmentados evita picos de consumo no período pré-festas.
  - [A] cemig.com.br · ok · 2026-09-03 · https://www.cemig.com.br/noticia/categoria/dicas-e-orientacoes/
  - [A] cemig.com.br · ok · 2026-09-28 · https://www.cemig.com.br/noticia/dicas-e-orientacoes/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  Revisor: Lembretes práticos consolidam orientações existentes; executável em nov-dez, mas fora da janela de 30 dias.

### F4 — Gemini + busca Google · revisor 2.47

- **Campanha de Consumo Consciente para Verão e Bandeira Amarela** · ignorar · ed 54 / pago 52 · selo media · verificação contestado · revisor 2.2
  Aproveitar a transição para a bandeira amarela e a previsão de calor extremo para educar o consumidor sobre economia, mitigando o impacto financeiro das altas temperaturas.
  - [A] gov.br · ok · 2024-10-25 · https://www.gov.br/aneel/pt-br/assuntos/noticias/2024/aneel-anuncia-bandeira-amarela-para-o-mes-de-novembro
  - [C] ifmg.edu.br · ok · 2024-11-01 · https://www.ifmg.edu.br/teofilootoni/noticias/boletim-meteorologico-novembro-2024
  - [A] ri.cemig.com.br · ok · 2024-10-15 · https://ri.cemig.com.br/sustentabilidade/eficiencia-energetica/
  Revisor: Campanha bandeira amarela/calor; fontes fora janela (2024), veredito contestado, não viável esta semana.
- **Alerta de Segurança contra Golpes de Faturas Falsas** · conteudo · ed 73 / pago 69 · selo media · verificação confirmado · revisor 2.8
  Comunicar proativamente sobre o novo layout das faturas para proteger clientes contra fraudes, aproveitando o pico de buscas sobre contas de luz.
  - [A] g1.globo.com · quebrado · 2024-10-20 · https://g1.globo.com/mg/minas-gerais/noticia/2024/05/21/conta-de-luz-fica-mais-cara-em-minas-gerais-saiba-de-quanto-sera-este-aumento.ghtml
  - [C] canalsolar.com.br · quebrado · 2024-11-01 · https://canalsolar.com.br/buscas-por-aumento-na-conta-de-luz-disparam-238-no-google-no-ultimo-trimestre/
  Revisor: Alerta sobre golpes em faturas; fontes A quebradas (fora janela 2024), veredito contestado, não sustenta ação esta semana.
- **Promoção do Planejamento Financeiro via App Cemig Atende** · ignorar · ed 58 / pago 55 · selo media · verificação parcial · revisor 2.4
  Estimular o uso do histórico de consumo de 12 meses para que famílias planejem os gastos de fim de ano diante da instabilidade das bandeiras.
  - [A] mg.gov.br · ok · 2024-11-01 · https://www.mg.gov.br/servico/visualizar-historico-de-contas
  - [C] canalsolar.com.br · quebrado · 2024-11-01 · https://canalsolar.com.br/buscas-por-aumento-na-conta-de-luz-disparam-238-no-google-no-ultimo-trimestre/
  Revisor: Planejamento financeiro via app; fontes fora janela (2024), veredito parcial, requer coordenação produto.

### F6 — Claude Sonnet + busca Anthropic · revisor 1.6

- **Explicar o reajuste tarifário de 6,50% antes da entrada em vigor** · ignorar · ed 26 / pago 21 · selo alta · verificação confirmado · revisor 1.4
  A ANEEL já aprovou reajuste médio de 6,50% para a Cemig D com início em 28/05/2026; comunicar com antecedência o motivo e o impacto na conta reduz ruído e reclamações no período de maior consumo.
  - [C] app.edgar.tools · ok · 2026-05-26 · https://app.edgar.tools/filing/1157557/0001292814-26-004500/cig20260908_6k.htm
  Revisor: Reajuste de 6,50% é de maio/2026 (passado), fora janela; fonte C (edgar.tools) com data incoerente.
- **Orientar sobre consumo consciente diante do novo valor da conta** · ignorar · ed 0 / pago 0 · selo alta · verificação confirmado · revisor 1.4
  Com o reajuste de 6,50% confirmado, há oportunidade de posicionar a Cemig como parceira do cliente, oferecendo dicas de uso consciente de energia para mitigar o impacto financeiro do aumento.
  - [C] app.edgar.tools · ok · 2026-05-26 · https://app.edgar.tools/filing/1157557/0001292814-26-004500/cig20260908_6k.htm
  Revisor: Reajuste passado (maio/2026), editorial e paid zerados; não é oportunidade atual.
- **Reforçar transparência institucional sobre critérios do reajuste** · ignorar · ed 0 / pago 0 · selo alta · verificação parcial · revisor 1.4
  Divulgar de forma clara os critérios técnicos usados pela ANEEL para aprovar o reajuste pode reduzir desconfiança do consumidor e fortalecer a reputação regulatória da Cemig.
  - [C] app.edgar.tools · ok · 2026-05-26 · https://app.edgar.tools/filing/1157557/0001292814-26-004500/cig20260908_6k.htm
  Revisor: Reajuste passado, editorial e paid zerados, veredito parcial; fora da janela.
