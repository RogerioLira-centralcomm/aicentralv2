# Radar Lab — 20261006202831-9c272c

Prompts v1.0 · cenário **cemig** · tema: conta de luz, bandeira tarifária, calor e consumo consciente no fim do ano · praças: Minas Gerais, Belo Horizonte · janela: 30 dias · 1 token Cadu = US$ 0.00016059

## Comparação dos fluxos

| Fluxo | Oport. | Nota revisor (1–5) | Fontes A/B | URLs abrem | Na janela | Selo alta/média/baixa | Tokens simulados | Tokens debitados | US$ provedor | Tempo |
|---|---|---|---|---|---|---|---|---|---|---|
| F1 Perplexity + imprensa | 5 | 4.56 | 67% | 87% | 80% | 5/0/0 | 432 | 417 | 0.0665 | 74.9 s |
| F2 OpenAI nativo | 4 | 2.6 | 50% | 50% | 100% | 3/0/1 | 5.159 | 6.109 | 0.0699 | 51.3 s |
| F3 Evidência primeiro (Firecrawl + Python) | 3 | 2.67 | 27% | 100% | 100% | 0/3/0 | 145 | 100 | 0.0159 | 48.2 s |

**Revisor (anthropic/claude-haiku-4.5):** vencedor F1. Sistema B é o único com 5 oportunidades verificadas (veredito 'confirmado'), fontes primárias A abertas e recentes, e todas acionáveis em mídia e conteúdo esta semana. Sistemas A e C carecem de veracidade (URLs quebradas, nível C) e clareza de ação, tornando B a base segura para planejamento Cemig.
- F1: Sistema B entrega 5 oportunidades verificadas com fontes primárias A (Cemig, G1, ANEEL, InfoMoney), todas dentro da janela e com veredito 'confirmado'. Combina ação imediata (bandeira verde, calor) com utilidade pública (transparência, economia). Melhor em: Veracidade (fontes A abertas e recentes), Ação (todas acionáveis em 2-6 semanas), Aderência (100% alinhadas com tema e marca).. Pior em: Novidade (B5 é genérico); uma URL Cemig quebrada em B2 reduz levemente a confiança..
- F2: Sistema A oferece 4 oportunidades com veredito 'não verificado' ou 'baixa confiança', com URLs Cemig quebradas e fontes C (Reddit, FIEMG, SAAE). Teses são relevantes (Tarifa Social, Cemig SIM) mas carecem de validação e ação clara. Melhor em: Aderência (Tarifa Social e economia doméstica são pertinentes); Recência (datas recentes).. Pior em: Veracidade (URLs quebradas, veredito não verificado), Ação (A3 e A4 fora de escopo ou sem plano claro), Novidade (genérico)..
- F3: Sistema C entrega 3 oportunidades com todas as fontes nível C (agregadores de notícia, portais regionais), vereditos 'contestado' ou 'parcial', e teses genéricas. Não passa do limite de veracidade 2 por regra de nível C. Melhor em: Recência (datas muito recentes); Aderência (temas corretos).. Pior em: Veracidade (nível C exclusivo = máx 2), Novidade (C3 duplica B3-B4), Ação (sem plano executável)..

## Custo por chamada: simulado x real

| Fluxo | Etapa | Modelo | Rota | Regime | Simulado (tokens Cadu) | Debitado (tokens Cadu) | US$ provedor | Entrada/saída | Tempo | Nota |
|---|---|---|---|---|---|---|---|---|---|---|
| F3 | google_news | python/rss | python | gratis | 0 | 0 | 0.00000 | 0/0 | 0.2 s | 23 manchetes |
| F3 | search | firecrawl/search | firecrawl | firecrawl | 95 | 32 | 0.00514 | 0/0 | 1.3 s | 0 fontes. 0 lidas |
| F1 | discover_press | perplexity/sonar | openrouter | custo | 49 | 45 | 0.00711 | 1.807/306 | 4.6 s |  |
| F2 | discover_press | openai/gpt-5-mini | openrouter | custo | 82 | 78 | 0.01247 | 10.445/331 | 5.0 s |  |
| F1 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 37 | 0.00589 | 275/611 | 7.1 s |  |
| F1 | discover_open | perplexity/sonar-pro | openrouter | custo | 160 | 142 | 0.02272 | 1.639/787 | 8.6 s |  |
| F2 | discover_open | openai/gpt-5-mini | openrouter | custo | 82 | 163 | 0.02605 | 15.388/1.575 | 13.8 s |  |
| F3 | judge | google/gemini-2.5-flash | openrouter | custo | 39 | 52 | 0.00833 | 6.803/2.516 | 16.2 s |  |
| F2 | judge | gpt-5-mini | openai | tokens | 4.920 | 5.708 | 0.00584 | 3.187/2.521 | 22.2 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| F3 | check | deepseek/deepseek-v3.2 | openrouter | custo | 11 | 16 | 0.00247 | 8.610/580 | 30.3 s |  |
| F1 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 64 | 0.01028 | 0/0 | 40.7 s |  |
| F2 | check | openai/gpt-5-mini | openrouter | custo | 75 | 160 | 0.02559 | 13.257/1.541 | 15.3 s |  |
| F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 79 | 88 | 0.01406 | 5.406/2.224 | 16.4 s |  |
| F1 | check | perplexity/sonar | openrouter | custo | 41 | 41 | 0.00645 | 576/878 | 9.0 s |  |
| REV | review | anthropic/claude-haiku-4.5 | openrouter | custo | 105 | 130 | 0.02076 | 10.409/2.070 | 17.8 s |  |

## Oportunidades

### F1 — Perplexity + imprensa

- **Campanha de consumo consciente na conta de dezembro** · integrada · ed 78 / pago 75 · selo alta · verificação confirmado · revisor 4.8
  Com a bandeira verde e o alerta da própria Cemig de que a conta não fica automaticamente mais barata, a marca pode ativar uma comunicação sazonal de fim de ano para reduzir surpresa na fatura e orientar uso consciente. O contexto é forte em Minas Gerais e Belo Horizonte, com alto encaixe reputacional e de serviço.
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/
  - [A] g1.globo.com · ok · 2026-09-25 · https://g1.globo.com/economia/noticia/2026/09/25/conta-de-luz-aneel-reduz-bandeira-tarifaria-para-verde-em-outubro.ghtml
  - [C] gov.br · ok · 2026-10-02 · https://www.gov.br/aneel/pt-br/assuntos/tarifas/bandeiras-tarifarias/faq-bandeiras-tarifarias
  Revisor: Bandeira verde confirmada por G1 e ANEEL; Cemig pode ativar comunicação sazonal imediata sobre consumo consciente e expectativa de fatura.
- **Conteúdo útil para calor: ar-condicionado sem susto na fatura** · integrada · ed 74 / pago 73 · selo alta · verificação confirmado · revisor 4.6
  A combinação de calor e maior uso de ventiladores/ar-condicionado amplia a chance de uma comunicação prática com dicas de economia. A Cemig pode transformar a bandeira verde em gancho para ensinar como consumir melhor em períodos quentes, sem perder o tom institucional.
  - [A] dadosabertos.aneel.gov.br · ok · 2026-10-05 · https://dadosabertos.aneel.gov.br/dataset/bandeiras-tarifarias
  - [A] cemig.com.br · quebrado · 2023-09-26 · https://www.cemig.com.br/noticia/onda-de-calor-em-setembro/
  - [C] gov.br · ok · 2026-10-02 · https://www.gov.br/aneel/pt-br/assuntos/tarifas/bandeiras-tarifarias/faq-bandeiras-tarifarias
  Revisor: Calor documentado; URL Cemig quebrada reduz veracidade, mas ANEEL e dados abertos sustentam; conteúdo prático de economia em AC é acionável.
- **Página explicativa de bandeira e valor da fatura** · integrada · ed 75 / pago 70 · selo alta · verificação confirmado · revisor 4.6
  Como há alta busca por entender bandeira tarifária, a Cemig pode reforçar uma página simples explicando o que muda na fatura e o que continua dependendo do consumo. Isso reduz dúvidas, melhora transparência e ajuda a conter ruído reputacional.
  - [A] cemig.com.br · ok · 2026-08-05 · https://www.cemig.com.br/valores-e-tarifas/bandeira-tarifaria/
  - [C] gov.br · ok · 2026-10-03 · https://www.gov.br/aneel/pt-br/assuntos/noticias/2026/bandeira-tarifaria-aneel-divulga-calendario-de-acionamento-para-2026
  - [A] infomoney.com.br · ok · 2026-09-25 · https://www.infomoney.com.br/brasil/apos-cinco-meses-conta-de-luz-voltara-a-bandeira-verde-em-outubro/
  Revisor: Página Cemig existe (embora antiga); InfoMoney e G1 recentes confirmam demanda; reforço de transparência é defensivo e necessário.
- **Aviso de serviço: conta verde não é conta barata** · conteudo · ed 73 / pago 68 · selo alta · verificação confirmado · revisor 4.8
  A Cemig pode usar mídia e canais próprios para esclarecer, de forma objetiva, que bandeira verde elimina a cobrança extra, mas não anula o impacto do consumo. A mensagem é defensiva e útil para evitar frustração do cliente no fim do ano.
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/
  - [A] jc.uol.com.br · ok · 2026-09-28 · https://jc.uol.com.br/economia/2026/09/28/conta-de-luz-fica-sem-cobranca-extra-em-outubro-com-a-volta-da-bandeira-verde.html
  - [C] gov.br · ok · 2026-10-02 · https://www.gov.br/aneel/pt-br/assuntos/tarifas/bandeiras-tarifarias/faq-bandeiras-tarifarias
  Revisor: Mensagem clara e verificada em múltiplas fontes A; esclarece mito de bandeira verde = conta barata; acionável em mídia paga e própria.
- **Checklist de fim de ano para reduzir a conta** · conteudo · ed 70 / pago 67 · selo alta · verificação confirmado · revisor 4.0
  A Cemig pode acoplar a sazonalidade de fim de ano a um checklist prático de economia no lar, conectando iluminação, refrigeração e uso consciente. É uma ação menor, mas consistente com a pauta e com o papel de utilidade pública da marca.
  - [A] dadosabertos.aneel.gov.br · ok · 2026-10-05 · https://dadosabertos.aneel.gov.br/dataset/bandeiras-tarifarias
  - [C] gov.br · ok · 2026-10-02 · https://www.gov.br/aneel/pt-br/assuntos/tarifas/bandeiras-tarifarias/faq-bandeiras-tarifarias
  - [A] cemig.com.br · quebrado · 2023-09-26 · https://www.cemig.com.br/noticia/onda-de-calor-em-setembro/
  Revisor: Checklist genérico mas alinhado com sazonalidade; URL Cemig quebrada; ANEEL sustenta; menor impacto que B1-B4.

### F2 — OpenAI nativo

- **Campanha prática de economia doméstica para o verão** · ignorar · ed 51 / pago 55 · selo alta · verificação nao_verificado · revisor 3.0
  Aproveitar a comunicação sobre bandeira verde para reforçar ações simples de redução de consumo durante a onda de calor e evitar surpresas na conta.
  - [A] cemig.com.br · quebrado · 2026-09-28 · https://www.cemig.com.br/noticias/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  - [C] fiemg.com.br · ok · 2026-09-27 · https://www.fiemg.com.br/sesi/noticias/calor-intenso-favorece-setores-de-bebidas-e-sorvetes-mas-eleva-custos-de-energia-climatizacao-logistica-e-ate-do-cafe/
  Revisor: URL Cemig quebrada (crítico); FIEMG é nível C; tese genérica; veredito 'não verificado' reduz confiança.
- **Lembrete proativo da Tarifa Social e orientação para manutenção do benefício** · ignorar · ed 56 / pago 51 · selo alta · verificação nao_verificado · revisor 3.2
  Reforçar e simplificar o acesso/recuperação da Tarifa Social para reduzir contas de famílias elegíveis durante aumento de consumo.
  - [A] cemig.com.br · quebrado · 2026-09-14 · https://www.cemig.com.br/noticias/conta-de-luz-veja-o-que-fazer-para-nao-perder-os-descontos-da-tarifa-social-da-cemig/
  - [A] cemig.com.br · quebrado · 2026-09-28 · https://www.cemig.com.br/noticias/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  Revisor: Ambas URLs Cemig quebradas; veredito 'não verificado'; Tarifa Social é relevante mas sem fontes abertas confiáveis.
- **Série de conteúdo esclarecendo o impacto do Cemig SIM na fatura** · ignorar · ed 27 / pago 23 · selo alta · verificação nao_verificado · revisor 2.2
  Responder dúvidas públicas sobre a plataforma Cemig SIM com casos reais e simuladores para recuperar confiança e orientar expectativas.
  - [C] reddit.com · ok · 2026-09-21 · https://www.reddit.com/r/PergunteReddit/comments/1wmb1sb/algu%C3%A9m_usa_cemig_sim_teve_alguma_redu%C3%A7%C3%A3o_real_na/
  - [A] cemig.com.br · quebrado · 2026-09-28 · https://www.cemig.com.br/noticias/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  Revisor: Reddit nível C; URL Cemig quebrada; Cemig SIM é produto interno mas sem validação externa; editorial 27 indica baixa confiança interna.
- **Campanha integrada água+energia para municípios afetados pela onda de calor** · ignorar · ed 40 / pago 37 · selo baixa · verificação nao_verificado · revisor 2.0
  Coordenar mensagem com SAAE e órgãos locais sobre economia de água e energia para reduzir pressão sobre abastecimento e contas.
  - [C] saaeitabira.com.br · ok · 2026-09-28 · https://www.saaeitabira.com.br/onda-de-calor-exige-atencao-saae-reforca-necessidade-de-economia-de-agua-em-itabira
  - [C] fiemg.com.br · ok · 2026-09-27 · https://www.fiemg.com.br/sesi/noticias/calor-intenso-favorece-setores-de-bebidas-e-sorvetes-mas-eleva-custos-de-energia-climatizacao-logistica-e-ate-do-cafe/
  Revisor: Ambas fontes nível C; selo 'baixa confiança' explícito; coordenação com SAAE não é competência Cemig; fora do escopo.

### F3 — Evidência primeiro (Firecrawl + Python)

- **Campanha de Conscientização: Consumo Inteligente no Calor e Fim de Ano** · ignorar · ed 66 / pago 63 · selo media · verificação contestado · revisor 2.6
  A Cemig deve lançar uma campanha educativa focada no consumo consciente de energia, aproveitando a bandeira verde para reforçar a importância da economia, especialmente com a chegada do calor e das festas de fim de ano, que tendem a aumentar o consumo.
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
  - [C] correioregional.net · ok · Tue, 29 Sep 2026 17:13:42 GMT · https://news.google.com/rss/articles/CBMi3gFBVV95cUxNWGkzdEFRRWRiSWd5TE8zcnZtNTlYSENkZTVneXFHSTR5a1dIR2ZyeWVqMmdkNjhpN0s1dWU5bTZhMWVKbWFsQ0x3V2ZRbUFmdUVWd0pQNExRTkhiRFI2c1RUYUpaR0NwVTR0STN6cVpfQi1WUXBfbjFXS0RVWlExR0dqZ1I5ellLbDhrQWJJcGRvUUF5c0c1S1NTbkN6MkVBblhQZEhQUnBHWU1VVU1BUUg2MkVnXzV6dmFMR1l4VXZKS3FOdU9ySEs0RzNUWDFrT2t1OTktS1dNNGtONUE?oc=5
  - [A] g1.globo.com · ok · Sun, 27 Sep 2026 07:00:00 GMT · https://news.google.com/rss/articles/CBMitwFBVV95cUxPaEliQ054Y3FwWjhfSkthMmcxZTJWNElCTUlRR3JPSDZYenNuYjVpMl82Vk5WUXRjX3dZTEZESXAxaDM5WV9jOUNuNC1XRk9lTWw4aDMyYXB3aGlvU3B6cDBGQWNvQ0FiMmlwOW9wdmNVZ3NQYzNxUU5jT3hvcGdoZnFXYWY1dHBpU0NIRTllTGl0dnpVbkdNbU5HanJKcWRxMklLUzBlSDlWbTNhSHpELU1ES2JNb2fSAcYBQVVfeXFMTmo1M01hRlZiZkdPNUViSDY4ajVHcG9sYnRLbE8tcGJEU0V5eU1idVVEb3lCU2V1UDEzeGE3d181SnA1WmpBWWxLd3gtX2lZdlZ5YzhwZ3dpU2Q0eDZycXE4X05Bcktnd1QzTXJ0TVNjTWZ1YU1zdm9JNGVLMk9Nb2gtWF9aMlV0OG1PZ09jQjhKZHViekgzaDFFRU1xUVNaVnF2YUpMMmtBR3ZrWThUU25leF9yMjBoSEozR21lSm5oTC1VTE13?oc=5
  - [C] fiemg.com.br · ok · Tue, 29 Sep 2026 12:26:00 GMT · https://news.google.com/rss/articles/CBMi7wFBVV95cUxOSGF3Nmd4Q1llQjZjSlkzY05ZczA3bnZNeTZ3VlhPLTVsaDBGSWhWaHFZVjdCNmZ4MEdkbnhleEY1Tjl5OWFldmk0ZXE3bXFVNWQ3WHBLNWpDUS1lOTBYeV9qaGtrd0tfYXRTQTJDY1R3cnU3OVVoLWpaQzFVcEM2dVUtSWRNcXpBQzJHOTJ5SkN5N1p5RnhCWTI2Vl9TU290bmRld3V4Q1lKanktdkxrVmg4VnNnUEt0Q2Y5cklGendUU3BsR0dzMU1tdTlabU90UHhMSE9fdVl0NjdxYWctdnExZGhWU2hRM0U1RFY3aw?oc=5
  Revisor: Todas fontes nível C; URLs genéricas de agregadores; tese genérica; veredito 'contestado'; não passa de 2 em veracidade (regra C).
- **Guia Prático: Maximizando Descontos da Tarifa Social** · ignorar · ed 67 / pago 62 · selo media · verificação contestado · revisor 2.8
  A Cemig deve criar um guia prático e campanhas informativas sobre a Tarifa Social de Energia Elétrica, detalhando quem tem direito, como se cadastrar e como evitar a perda do benefício, dado o grande número de famílias elegíveis e o risco de perda de descontos.
  - [C] diariodeuberlandia.com.br · ok · Sun, 27 Sep 2026 14:00:00 GMT · https://news.google.com/rss/articles/CBMixAFBVV95cUxOWnJSVHRibVRuWlhqZktDcmpFOUFndHpXa1VDcy1OSWl2RkpPUTdHblBXd19URXVCTk1Wci15YWpUZkNReUYxQTBJcHpsZEthcERTWjFESGpVUXZuSXFtbVhyYXh4X19FQUFQRHpCVlhSRm5JaExZdURIX3JFcS1wMl9CWG9mTGY1MkZCNmJfLWJlSG10LUI2YUxyVHN6MUVSOTdxQVJMREc0c2JNWGVHV1RrQ3M0aU9wMUVBeWsta0lRcnR4?oc=5
  - [A] itatiaia.com.br · ok · Thu, 17 Sep 2026 07:00:00 GMT · https://news.google.com/rss/articles/CBMiogFBVV95cUxQVllsbXo2N1VKRjh1bmxvRkM3REtSOHAwbjA1NGpxOEw2NTF5eUZFalN6M3VfakJkT1piT2Y0MjY4VTc2WG1qSUhKLXM3R2p1LUpBeUJfYzZxaUJKWWV6R21fWHBoa1kxeVR3WkZwcDEwalp0dGdHeDl5VXQ5MlhGMGp0YmtIRmJPWXMzTE1zZmo0QzNtdHRUeWRfVGdaU1RKMWc?oc=5
  - [C] radiotropical.net · ok · Tue, 22 Sep 2026 17:53:04 GMT · https://news.google.com/rss/articles/CBMipAFBVV95cUxNdmRkaTF6R2tRdWl3X0UtM3ZUdVh2Q3dHUGtvazBLMVlfX3ZSMGZHV0dMMHZiZHdfOGNpME1YY2R4dUs1QzJDOWZGczFZX3lGQWtGdDkxSUpVMXVDY3lUTFlTbmNpaU53cnZ3N0VuMWZPWFBvT1BXWWozYXJheC1ETVB6LTBrcnJfTEc3ak0wcGdSTFJzcDNPY2xnRERGbEZ3NGFTMA?oc=5
  Revisor: Maioria nível C; G1 nível A mas genérico; veredito 'contestado'; Tarifa Social relevante mas sem fontes primárias Cemig.
- **Conteúdo Explicativo: Bandeira Verde e Consumo Consciente** · ignorar · ed 67 / pago 62 · selo media · verificação parcial · revisor 2.6
  A Cemig deve produzir conteúdo explicativo detalhado sobre o significado da bandeira tarifária verde, desmistificando a ideia de que não há necessidade de economia e reforçando a importância do consumo consciente para a manutenção da bandeira e a sustentabilidade energética.
  - [C] pocoscom.com · ok · Tue, 06 Oct 2026 09:31:03 GMT · https://news.google.com/rss/articles/CBMi1wFBVV95cUxNM1hQZjBFdWdxMVNtTTdfZ2J2UFZJc2NLaUlkTjVGUUVHRXhNSnctbWVRa2RjTllYRWhKcWxNaDY0UlNUUFZWMHBfUEhoS2JuNFQ0M1ZlOW5VZWpJOW1mbG56R3VHUk5vODJ5aVBqOXg1dDZyMUZIVklnVFBoMC1WcE8zb0pKRXZwTTNLUnVyVTRPUWZPZ1ptWmc3dzhNdzZQcTVGTXRoME9aQXlYb1JZUEthMVJ4SG4yb0tzYTUwYll5cWFEZW1IZW83WDRiOHlaQW1xQ01rTQ?oc=5
  - [C] correioregional.net · ok · Tue, 29 Sep 2026 17:13:42 GMT · https://news.google.com/rss/articles/CBMi3gFBVV95cUxNWGkzdEFRRWRiSWd5TE8zcnZtNTlYSENkZTVneXFHSTR5a1dIR2ZyeWVqMmdkNjhpN0s1dWU5bTZhMWVKbWFsQ0x3V2ZRbUFmdUVWd0pQNExRTkhiRFI2c1RUYUpaR0NwVTR0STN6cVpfQi1WUXBfbjFXS0RVWlExR0dqZ1I5ellLbDhrQWJJcGRvUUF5c0c1S1NTbkN6MkVBblhQZEhQUnBHWU1VVU1BUUg2MkVnXzV6dmFMR1l4VXZKS3FOdU9ySEs0RzNUWDFrT2t1OTktS1dNNGtONUE?oc=5
  - [C] drd.com.br · ok · Mon, 28 Sep 2026 20:21:49 GMT · https://news.google.com/rss/articles/CBMimwFBVV95cUxQc2d4aWk0SWpDdmNDOVl6SGJyRkc5bXhiN0lVcWVfbmR5UWRmbk83Rjg5dU05ZmxITGNiY0tNLVZ1NjVvN1ByZS1LckVuRURmN0RRSDdYanc0a28xNlU5enhXeXYxWGthaDlsNXZjRjRxMWxkdjFlV2dfTU9ZbnJjQmZGY0Z1R3NpcEZ6YzVJU01SM1dCY3oyQVpNWQ?oc=5
  - [A] g1.globo.com · ok · Fri, 02 Oct 2026 23:42:03 GMT · https://news.google.com/rss/articles/CBMi5gFBVV95cUxNMDEwQ0FOeGxmUk1UMXZNekxMc3BsUFNYYU9VM3B3cWItYldJSS1PLXdUN0VpUmVXdWZRMUNxaUpVYUpLQXVCN0FHUEpHQ29KTGRYSllUSXFPVDdGOFRKRnctWGxLR2JwN2RuR2xLcXl0VFdDcU4wM1hwbzNIcE1keG1iM3RGcTJ5UUh2YjlPbEhISG84S0NGU1ZELUtRVlJWeG1oN2RIaWpoY05Kb2ozOURyaDFuQjZETElCUC1nNTFzX3V2UUxZc2VPc2pzOW5xdkVnRmNma3hfQjd4b0JnODdvNi1aZ9IB9AFBVV95cUxPWkdiUTRTR24wVW1JajJ0REhRSDkxQkdxZldUNXM1VDBFWEdBUEV4UHJSTEpkZGVoY3c3TURSNks4ZzNBT0ZqOXdpZVJYSWNtcUtzeXNiUWJfU0Q5UENBa1VMMTV3Sk9mNVM2NEd5dHRjZjd4Z0s2eElOc1dQYVFiNEltM2lmY0xqSmFHc2Ita1p5SnE4bmpieXU5ZktJRHJLNXZoVXJJaEdaS3lQc2pRVlllSmh0ZnFWd3g2T1k5d1JJNnlFeWVmbERwclo0amxlMTdMeVNxMjlYaFlOVndtMmhJSUlHY1dsOFNucmt2dWhYVEcy?oc=5
  Revisor: Maioria nível C; G1 nível A mas genérico; veredito 'parcial'; conteúdo sobre bandeira é óbvio e já coberto por B3-B4.
