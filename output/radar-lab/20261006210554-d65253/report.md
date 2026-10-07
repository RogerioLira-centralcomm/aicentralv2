# Radar Lab — 20261006210554-d65253

Cenário **cemig** · tema: conta de luz, bandeira tarifária, calor e consumo consciente no fim do ano · praças: Minas Gerais, Belo Horizonte · janela: 30 dias · 1 token Cadu = US$ 0.00016053 · tempo total 198.7 s

Melhor versão de prompts: **1.0** · ruído médio da média do revisor (fluxo sem mudança, de uma passada para outra): 0.35 ponto(s)

## Comparação dos fluxos (melhor versão de cada um)

Critério: **pontos** = soma das notas do revisor das oportunidades **boas** (nota ≥ 4 e selo ≠ baixa). Cortar uma oportunidade boa perde pontos; uma fraca não soma.

| Fluxo | Tipo | Pontos | Boas/total | Média revisor | Pontos por volta: pontos (boas/total) | Evidências | Fontes A/B | URLs abrem | Na janela | Selo a/m/b | Tokens sim. | Tokens debitados | US$ provedor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 Perplexity + imprensa | perplexity | **13.8** | 3/3 | 4.6 | v1.0: 18.0 (4/4) → 12.8 (3/4) → 13.8 (3/3) | 13 | 78% | 100% | 100% | 3/0/0 | 622 | 496 | 0.0789 |
| F2 OpenAI nativo | web | **12.8** | 3/4 | 4.1 | v1.0: 12.8 (3/4) → 9.4 (2/4) → 9.0 (2/3) | 7 | 67% | 100% | 100% | 3/1/0 | 20.369 | 21.138 | 0.1348 |
| F5 Grok + web e X | web | **8.6** | 2/2 | 4.3 | v1.0: 4.2 (1/3) → 8.6 (2/2) → 4.0 (1/2) | 14 | 100% | 100% | 100% | 2/0/0 | 559 | 1.571 | 0.2515 |

Revisor e médico de prompts (compartilhados): 277 tokens debitados, US$ 0.0442. Total da rodada: 23.482 tokens, US$ 0.5093.

## Versões de prompt

| Versão | Pontos médios por fluxo | Vencedor do revisor | Pontos por fluxo |
|---|---|---|---|
| 1.0 | 11.733 | F1 | F1 13.8, F2 12.8, F5 8.6 |

**Médico de prompts → v1.1** (a partir da v1.0): 0 mudança(s) aceita(s), 0 recusada(s).

**Revisor (anthropic/claude-haiku-4.5), última passada da melhor versão:** vencedor F1. Sistema A entrega três oportunidades de alta veracidade (fontes A confirmadas), recência imediata (bandeira verde de outubro 2026 em vigor) e ação esta semana (editorial + paid integrados). Supera B (quadrant 'ignorar' incoerente) e C (veracidade média, janelas longas, C3 especulativa) em clareza estratégica e executabilidade para Cemig.
- F1: Três oportunidades sólidas e imediatas: bandeira verde de outubro (A1), conteúdo calor + consumo (A2) e hub de autosserviço (A3). Todas com fontes A confirmadas, janelas claras e ação viável esta semana. Melhor em: Veracidade (fontes A/ANEEL), recência (dados de 2026-09-29 a 2026-10-05), aderência (alinha 100% com tema Cemig) e ação (editorial + paid integrados).. Pior em: Novidade (A1 e A3 são esperados para uma distribuidora de energia em outubro); A2 depende parcialmente de fontes C..
- F5: Duas oportunidades táticas (Instagram B1, push app B2) com scores editorial/paid baixos (51–54) e quadrant 'ignorar'. Fontes mistas (A + C) e execução clara, mas posicionamento estratégico fraco. Melhor em: Ação (ambas são diretas e executáveis em 48h); recência (dados de 2026-09-25 a 2026-09-29).. Pior em: Veracidade (fontes C reduzem confiança); novidade (carrossel e push são táticas óbvias); quadrant 'ignorar' contradiz scores e tema..
- F2: Três oportunidades com foco em esclarecimento (C1), autoatendimento (C2) e alertas climáticos (C3). Veracidade média (fontes A + C mistas), janelas longas e ação parcial; C3 é especulativa. Melhor em: Aderência (C1 e C2 resolvem dor real de cliente); recência (dados até 2026-10-05).. Pior em: Veracidade (C3 com climatempo.com.br reduz a 3); novidade (C2 é genérico); ação (C3 depende de previsões; C2 requer 7 dias de prep)..

## Custo por chamada: simulado x real

| Versão | Fluxo | Etapa | Modelo | Rota | Regime | Simulado | Debitado | US$ provedor | Entrada/saída | Tempo | Nota |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | F1 | discover_press | perplexity/sonar | openrouter | custo | 49 | 46 | 0.00726 | 1.807/449 | 6.2 s |  |
| 1.0 | F2 | discover_press | openai/gpt-5-mini | openrouter | custo | 88 | 76 | 0.01219 | 10.271/444 | 7.2 s |  |
| 1.0 | F1 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 37 | 0.00583 | 275/558 | 7.7 s |  |
| 1.0 | F1 | discover_open | perplexity/sonar-pro | openrouter | custo | 160 | 126 | 0.02014 | 1.639/615 | 9.5 s |  |
|  | F1 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 64 | 0.01027 | 0/0 | 5.2 s |  |
| 1.0 | F2 | discover_open | openai/gpt-5-mini | openrouter | custo | 88 | 86 | 0.01374 | 10.275/1.220 | 17.4 s |  |
| 1.0 | F5 | discover_open | x-ai/grok-4.3 | openrouter | custo | 71 | 381 | 0.06103 | 29.637/1.753 | 17.8 s |  |
| 1.0 | F5 | discover_press | x-ai/grok-4.3 | openrouter | custo | 72 | 239 | 0.03831 | 23.060/2.025 | 21.5 s |  |
| 1.0 | F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 110 | 79 | 0.01266 | 5.501/1.897 | 13.1 s |  |
| 1.0 | F5 | judge | x-ai/grok-4.3 | openrouter | custo | 80 | 64 | 0.01021 | 4.809/1.734 | 15.7 s |  |
| 1.0 | F1 | check | perplexity/sonar | openrouter | custo | 46 | 39 | 0.00612 | 450/674 | 6.1 s |  |
| 1.0 | F2 | judge | gpt-5-mini | openai | tokens | 6.375 | 6.436 | 0.00668 | 3.537/2.899 | 21.6 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F5 | check | x-ai/grok-4.3 | openrouter | custo | 62 | 266 | 0.04264 | 16.196/1.524 | 16.1 s |  |
| 1.0 | F2 | check | openai/gpt-5-mini | openrouter | custo | 86 | 366 | 0.05860 | 21.841/1.973 | 23.7 s |  |
| 1.0 | REV | review-1.0-r0 | anthropic/claude-haiku-4.5 | openrouter | custo | 124 | 99 | 0.01578 | 6.588/1.839 | 16.7 s |  |
| 1.0 | F5 | revise-r1 | x-ai/grok-4.3 | openrouter | custo | 76 | 56 | 0.00895 | 4.237/1.544 | 13.3 s |  |
| 1.0 | F2 | revise-r1 | gpt-5-mini | openai | tokens | 6.780 | 7.433 | 0.00781 | 4.035/3.398 | 27.2 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F5 | check-r1 | x-ai/grok-4.3 | openrouter | custo | 62 | 212 | 0.03390 | 13.451/1.397 | 14.0 s |  |
| 1.0 | F2 | check-r1 | openai/gpt-5-mini | openrouter | custo | 86 | 95 | 0.01525 | 9.291/1.866 | 18.2 s |  |
| 1.0 | REV | review-1.0-r1 | anthropic/claude-haiku-4.5 | openrouter | custo | 121 | 93 | 0.01481 | 5.908/1.781 | 15.5 s |  |
| 1.0 | F1 | revise-r2 | openai/gpt-5.4-mini | openrouter | custo | 109 | 68 | 0.01080 | 5.451/1.491 | 9.5 s |  |
| 1.0 | F5 | revise-r2 | x-ai/grok-4.3 | openrouter | custo | 74 | 53 | 0.00839 | 3.964/1.454 | 11.8 s |  |
| 1.0 | F1 | check-r2 | perplexity/sonar | openrouter | custo | 45 | 37 | 0.00580 | 387/408 | 4.2 s |  |
| 1.0 | F2 | revise-r2 | gpt-5-mini | openai | tokens | 6.780 | 6.555 | 0.00605 | 4.035/2.520 | 21.7 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F5 | check-r2 | x-ai/grok-4.3 | openrouter | custo | 62 | 300 | 0.04804 | 21.090/1.261 | 11.7 s |  |
| 1.0 | F2 | check-r2 | openai/gpt-5-mini | openrouter | custo | 86 | 91 | 0.01451 | 8.935/1.539 | 13.5 s |  |
| 1.0 | REV | review-1.0-r2 | anthropic/claude-haiku-4.5 | openrouter | custo | 119 | 85 | 0.01356 | 5.383/1.636 | 14.6 s |  |
| 1.0 | DOC | doctor-1.0 | openai/gpt-5.4 | openrouter | custo | 311 | 0 | 0.00000 | 0/0 | 0.3665331659722142 s | FALHOU OpenRouterError: O saldo da conta OpenRouter é insuficiente. |

## Oportunidades (melhor versão de cada fluxo)

### F1 — Perplexity + imprensa · revisor 4.6

- **Cemig: alerta de conta sem taxa extra em outubro** · integrada · ed 87 / pago 85 · selo alta · verificação confirmado · revisor 4.8
  A Cemig já informou que a bandeira de outubro de 2026 é verde e que o consumo consciente segue importante para evitar surpresas na conta. A marca pode ativar uma peça curta e utilitária agora, conectando a mudança tarifária ao uso responsável de energia.
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/
  - [A] cemig.com.br · ok · s/ data · https://www.cemig.com.br/noticias/
  - [A] gov.br · ok · 2026-09-29 · https://www.gov.br/aneel/pt-br
  Revisor: Bandeira verde confirmada (ANEEL + Cemig), janela imediata, alinha perfeitamente com tema e permite ativação editorial/paid esta semana.
- **Conteúdo Cemig para calor e consumo nos lares mineiros** · integrada · ed 75 / pago 72 · selo alta · verificação parcial · revisor 4.4
  O material da ANEEL lembra que, em períodos mais quentes, ar-condicionado e ventiladores pesam mais no consumo. A Cemig pode publicar orientação prática, curta e regional, ligando calor em Minas a hábitos de uso mais conscientes.
  - [A] dadosabertos.aneel.gov.br · ok · s/ data · https://dadosabertos.aneel.gov.br/dataset/bandeiras-tarifarias
  - [C] sampi.net.br · ok · 2026-10-06 · https://sampi.net.br/jundiai/noticias/3009565/jundiai/2026/10/bandeira-verde-conta-de-luz-nao-tera-cobranca-extra-em-outubro
  - [C] rede98.com.br · ok · 2026-09-29 · https://rede98.com.br/98-news/conta-de-luz-tera-bandeira-verde-em-outubro-mas-consumo-exige-atencao/
  Revisor: Conexão calor + consumo é válida (ANEEL + FIEMG), mas fontes C reduzem veracidade; conteúdo prático e regional é acionável.
- **Página Cemig de bandeira tarifária como hub de autosserviço** · integrada · ed 88 / pago 86 · selo alta · verificação confirmado · revisor 4.6
  A Cemig já mantém página atualizada sobre bandeira tarifária e serviços de atendimento ligados à conta. Vale transformar essa página em destino central da comunicação de outubro, com chamada clara para consulta da fatura e entendimento da tarifa.
  - [A] cemig.com.br · ok · s/ data · https://www.cemig.com.br/valores-e-tarifas/bandeira-tarifaria/
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/
  - [A] cemig.com.br · ok · s/ data · https://www.cemig.com.br/noticias/
  Revisor: Hub de autosserviço já existe e está atualizado; oportunidade de amplificar tráfego com call-to-action clara sobre bandeira e fatura.

### F2 — OpenAI nativo · revisor 4.1

- **Campanha educativa: 'Bandeira verde não é desconto — consumo consciente importa'** · ignorar · ed 62 / pago 64 · selo alta · verificação confirmado · revisor 4.6
  A Cemig deve aproveitar o alerta institucional sobre bandeira verde para esclarecer clientes que a bandeira não reduz a tarifa e incentivar práticas de consumo consciente, reduzindo surpresas na conta no fim do ano.
  - [A] cemig.com.br · ok · 2026-09-28 · https://www.cemig.com.br/noticia/dicas-e-orientacoes/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/duvida-frequente/como-saber-sobre-o-acionamento-das-bandeiras-tarifarias/
  - [A] dadosabertos.aneel.gov.br · ok · 2026-09-10 · https://dadosabertos.aneel.gov.br/pt_BR/dataset/bandeiras-tarifarias
  Revisor: Fontes A sólidas (Cemig + ANEEL); mensagem clara mas não diferencia do que A e B já cobrem.
- **Alertas em tempo real e dicas para reduzir picos por onda de calor** · ignorar · ed 52 / pago 54 · selo media · verificação parcial · revisor 4.0
  Ativar campanha tática com dicas práticas (como ajustar ar-condicionado, ventiladores, horários para uso de eletrodomésticos) e alertas em dias de calor recorde para reduzir picos de consumo em BH e MG.
  - [C] em.com.br · ok · 2026-09-27 · https://www.em.com.br/gerais/2026/09/7509603-pico-de-calor-recorde-em-bh-altera-rotina-e-dispara-consumo-de-energia.html
  - [C] climatempo.com.br · ok · 2026-10-01 · https://www.climatempo.com.br/noticia/calor/setembro-termina-com-muito-calor-no-brasil
  - [C] fiemg.com.br · ok · 2026-09-29 · https://www.fiemg.com.br/sesi/noticias/calor-intenso-favorece-setores-de-bebidas-e-sorvetes-mas-eleva-custos-de-energia-climatizacao-logistica-e-ate-do-cafe/
  - [A] epe.gov.br · ok · 2026-09-18 · https://www.epe.gov.br/pt/imprensa/noticias/epe-divulga-boletim-trimestral-de-consumo-de-eletricidade-n-26
  Revisor: Alertas em tempo real é tático e novo; mas 3 fontes C (EM, Climatempo, FIEMG) enfraquecem veracidade.
- **Promover ferramentas de autoatendimento para checar bandeiras e fatura** · ignorar · ed 63 / pago 59 · selo alta · verificação confirmado · revisor 4.2
  Empurrar os canais digitais e FAQs que explicam o acionamento de bandeiras e mostram fatura detalhada, reduzindo dúvidas e chamadas ao atendimento.
  - [A] cemig.com.br · ok · 2026-10-05 · https://www.cemig.com.br/duvida-frequente/como-saber-sobre-o-acionamento-das-bandeiras-tarifarias/
  - [A] cemig.com.br · ok · 2026-09-28 · https://www.cemig.com.br/noticia/dicas-e-orientacoes/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  - [A] dadosabertos.aneel.gov.br · ok · 2026-09-10 · https://dadosabertos.aneel.gov.br/pt_BR/dataset/bandeiras-tarifarias
  Revisor: Promover FAQ e autoatendimento é essencial mas completamente óbvio para utilidade pública.
- **Programa de parceria B2B: gestão de demanda para setores afetados pelo calor** · ignorar · ed 27 / pago 19 · selo alta · verificação confirmado · revisor 3.6
  Oferecer consultoria e soluções (demand response, horários alternados, eficiência energética) para indústrias e comércios mais afetados pelo aumento da climatização em MG.
  - [C] fiemg.com.br · ok · 2026-09-29 · https://www.fiemg.com.br/sesi/noticias/calor-intenso-favorece-setores-de-bebidas-e-sorvetes-mas-eleva-custos-de-energia-climatizacao-logistica-e-ate-do-cafe/
  - [A] epe.gov.br · ok · 2026-09-18 · https://www.epe.gov.br/pt/imprensa/noticias/epe-divulga-boletim-trimestral-de-consumo-de-eletricidade-n-26
  Revisor: Demand response B2B é inovador; mas fora do escopo de mídia de consumidor; fonte C (FIEMG) limita veracidade.

### F5 — Grok + web e X · revisor 4.3

- **Posts no Instagram e app Cemig Atende sobre bandeira verde** · ignorar · ed 43 / pago 40 · selo alta · verificação confirmado · revisor 4.4
  Cemig deve alertar clientes que bandeira verde em outubro não elimina necessidade de consumo consciente, pois calor aumenta demanda por ar-condicionado.
  - [A] cemig.com.br · ok · 2026-09-25 · https://www.cemig.com.br/noticia/dicas-e-orientacoes/bandeira-verde-em-outubro-cemig-alerta-que-consumo-consciente-continua-essencial-para-evitar-surpresas-na-conta-de-luz/
  Revisor: Uma fonte Nível A recente; posts em Instagram/app são acionáveis mas genéricos e duplicam A1.
- **Reaproveitamento de vídeo do engenheiro Cemig no YouTube e G1** · ignorar · ed 40 / pago 36 · selo alta · verificação confirmado · revisor 4.2
  Cemig deve compartilhar explicação de engenheiro sobre definição da bandeira verde para educar clientes e reforçar imagem de autoridade.
  - [A] g1.globo.com · ok · 2026-10-02 · https://g1.globo.com/mg/centro-oeste/videos-mgtv-2-edicao/video/conta-de-luz-nao-tera-cobranca-extra-em-outubro-com-bandeira-tarifaria-verde-15017999.ghtml
  Revisor: Fonte Nível A (G1) com vídeo de engenheiro; reutilização é prática mas requer produção/edição adicional.
