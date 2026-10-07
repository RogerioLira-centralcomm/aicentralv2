# Radar Lab — 20261006210551-3a73bd

Cenário **bomfim** · tema: pico logístico de Black Friday e Natal, frete e estradas · praças: Minas Gerais, São Paulo · janela: 30 dias · 1 token Cadu = US$ 0.00016053 · tempo total 195.2 s

Melhor versão de prompts: **1.0** · ruído médio da média do revisor (fluxo sem mudança, de uma passada para outra): 1.07 ponto(s)

## Comparação dos fluxos (melhor versão de cada um)

Critério: **pontos** = soma das notas do revisor das oportunidades **boas** (nota ≥ 4 e selo ≠ baixa). Cortar uma oportunidade boa perde pontos; uma fraca não soma.

| Fluxo | Tipo | Pontos | Boas/total | Média revisor | Pontos por volta: pontos (boas/total) | Evidências | Fontes A/B | URLs abrem | Na janela | Selo a/m/b | Tokens sim. | Tokens debitados | US$ provedor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 Perplexity + imprensa | perplexity | **9.6** | 2/3 | 4.4 | v1.0: 9.0 (2/4) → 4.0 (1/4) → 9.6 (2/3) | 14 | 67% | 100% | 100% | 3/0/0 | 733 | 571 | 0.0910 |
| F5 Grok + web e X | web | **9.0** | 2/3 | 4.0 | v1.0: 0 (0/3) → 9.0 (2/3) → 8.0 (2/3) | 14 | 50% | 100% | 100% | 0/2/1 | 508 | 1.576 | 0.2522 |
| F2 OpenAI nativo | web | **4.4** | 1/3 | 3.4 | v1.0: 9.0 (2/4) → 13.4 (3/3) → 4.4 (1/3) | 10 | 100% | 100% | 100% | 0/3/0 | 12.252 | 12.790 | 0.1031 |

Revisor e médico de prompts (compartilhados): 267 tokens debitados, US$ 0.0426. Total da rodada: 15.204 tokens, US$ 0.4890.

## Versões de prompt

| Versão | Pontos médios por fluxo | Vencedor do revisor | Pontos por fluxo |
|---|---|---|---|
| 1.0 | 7.667 | F1 | F1 9.6, F2 4.4, F5 9.0 |

**Médico de prompts → v1.1** (a partir da v1.0): 0 mudança(s) aceita(s), 0 recusada(s).

**Revisor (anthropic/claude-haiku-4.5), última passada da melhor versão:** vencedor F1. Sistema B combina veracidade máxima (fontes gov.br A + portais B recentes: 01/10 a 06/10), aderência total (3 ações específicas para transportadora em MG/SP), ação imediata (2-3 semanas, realista) e novidade moderada (conteúdo educativo + geolocalização). A1 e C carecem de fontes C ou datas incompletas; B entrega 3 oportunidades prontas para planejamento de mídia/conteúdo esta semana.
- F1: Sistema B entrega 3 oportunidades de alta veracidade (fontes A+gov.br) com recência 5 e aderência máxima. Foco em conteúdo educativo (guia ANTT, rotas críticas, kit embarcador) com janelas realistas e ação imediata. Melhor em: Veracidade (fontes gov.br A + portais B confiáveis), recência (datas 01/10 a 06/10), ação (janelas 2-3 semanas, executáveis).. Pior em: Novidade (conteúdo educativo padrão, sem diferencial tático); B3 carece de data em fontes gov.br..
- F5: Sistema A oferece 3 oportunidades com mix de veracidade (1 fonte A, 2 fontes C). Teses operacionais claras (relatório customizado, comunicado ANTT, alerta segurança) mas com prazos curtos (até 20/10) e dependência de fonte C em A3. Melhor em: Aderência (todas as 3 ações são específicas para Bomfim); ação (prazos definidos e factíveis); recência (datas 09/09 a 30/09).. Pior em: Veracidade (A3 com fonte C única reduz confiança); novidade (teses são reativas, não proativas); A2 é genérico (comunicado ANTT padrão)..
- F2: Sistema C propõe 3 oportunidades ambiciosas (compliance+apoio, alertas rotas, SLA+API) com fontes A mas datas incompletas ou ausentes. Janelas longas (até 31/12) e viabilidade técnica questionável. Melhor em: Aderência (C2 e C1 endereçam dor real do pico); recência parcial (C2 com O Tempo 24/09); novidade (C3 com integração API é diferencial).. Pior em: Veracidade (C1 e C3 com datas faltando ou genéricas; C3 com fonte B sem data); ação (C3 requer POC técnico não viável em 2 semanas); recência (C1 e C3 com lacunas de data)..

## Custo por chamada: simulado x real

| Versão | Fluxo | Etapa | Modelo | Rota | Regime | Simulado | Debitado | US$ provedor | Entrada/saída | Tempo | Nota |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | F1 | discover_press | perplexity/sonar | openrouter | custo | 41 | 34 | 0.00544 | 433/5 | 4.2 s |  |
| 1.0 | F1 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 38 | 0.00604 | 239/800 | 5.5 s |  |
| 1.0 | F1 | discover_open | perplexity/sonar-pro | openrouter | custo | 137 | 105 | 0.01676 | 268/664 | 9.5 s |  |
| 1.0 | F2 | discover_open | openai/gpt-5-mini | openrouter | custo | 86 | 159 | 0.02543 | 13.318/1.456 | 15.7 s |  |
| 1.0 | F5 | discover_press | x-ai/grok-4.3 | openrouter | custo | 63 | 170 | 0.02724 | 12.186/1.477 | 15.8 s |  |
| 1.0 | F2 | discover_press | openai/gpt-5-mini | openrouter | custo | 86 | 224 | 0.03584 | 16.255/1.392 | 16.5 s |  |
| 1.0 | F5 | discover_open | x-ai/grok-4.3 | openrouter | custo | 62 | 376 | 0.06021 | 27.648/2.420 | 26.3 s |  |
|  | F1 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 64 | 0.01027 | 0/0 | 21.6 s |  |
| 1.0 | F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 105 | 76 | 0.01206 | 4.453/1.939 | 11.2 s |  |
| 1.0 | F5 | judge | x-ai/grok-4.3 | openrouter | custo | 67 | 52 | 0.00821 | 3.005/1.835 | 18.6 s |  |
| 1.0 | F1 | check | perplexity/sonar | openrouter | custo | 46 | 41 | 0.00654 | 507/1.037 | 8.4 s |  |
| 1.0 | F2 | judge | gpt-5-mini | openai | tokens | 5.931 | 6.148 | 0.00693 | 3.067/3.081 | 27.5 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F5 | check | x-ai/grok-4.3 | openrouter | custo | 62 | 279 | 0.04471 | 19.065/1.375 | 14.3 s |  |
| 1.0 | F2 | check | openai/gpt-5-mini | openrouter | custo | 86 | 91 | 0.01451 | 9.342/1.490 | 14.6 s |  |
| 1.0 | REV | review-1.0-r0 | anthropic/claude-haiku-4.5 | openrouter | custo | 117 | 90 | 0.01442 | 5.230/1.838 | 16.3 s |  |
| 1.0 | F1 | revise-r1 | openai/gpt-5.4-mini | openrouter | custo | 105 | 80 | 0.01280 | 4.492/2.096 | 12.3 s |  |
| 1.0 | F5 | revise-r1 | x-ai/grok-4.3 | openrouter | custo | 65 | 51 | 0.00819 | 2.744/1.983 | 17.5 s |  |
| 1.0 | F1 | check-r1 | perplexity/sonar | openrouter | custo | 46 | 42 | 0.00671 | 551/1.161 | 8.6 s |  |
| 1.0 | F2 | revise-r1 | gpt-5-mini | openai | tokens | 5.977 | 6.081 | 0.00651 | 3.230/2.851 | 24.8 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F5 | check-r1 | x-ai/grok-4.3 | openrouter | custo | 62 | 281 | 0.04501 | 17.005/1.638 | 15.2 s |  |
| 1.0 | F2 | check-r1 | openai/gpt-5-mini | openrouter | custo | 86 | 87 | 0.01388 | 9.137/1.203 | 11.8 s |  |
| 1.0 | REV | review-1.0-r1 | anthropic/claude-haiku-4.5 | openrouter | custo | 116 | 89 | 0.01413 | 5.190/1.788 | 16.3 s |  |
| 1.0 | F1 | revise-r2 | openai/gpt-5.4-mini | openrouter | custo | 105 | 52 | 0.00828 | 4.492/1.744 | 10.6 s |  |
| 1.0 | F5 | revise-r2 | x-ai/grok-4.3 | openrouter | custo | 65 | 53 | 0.00840 | 2.844/2.018 | 17.5 s |  |
| 1.0 | F1 | check-r2 | perplexity/sonar | openrouter | custo | 45 | 39 | 0.00614 | 467/670 | 8.1 s |  |
| 1.0 | F5 | check-r2 | x-ai/grok-4.3 | openrouter | custo | 62 | 314 | 0.05027 | 22.585/1.461 | 13.5 s |  |
| 1.0 | REV | review-1.0-r2 | anthropic/claude-haiku-4.5 | openrouter | custo | 114 | 88 | 0.01402 | 4.510/1.903 | 16.9 s |  |
| 1.0 | DOC | doctor-1.0 | openai/gpt-5.4 | openrouter | custo | 312 | 0 | 0.00000 | 0/0 | 0.6674201659625396 s | FALHOU OpenRouterError: O saldo da conta OpenRouter é insuficiente. |

## Oportunidades (melhor versão de cada fluxo)

### F1 — Perplexity + imprensa · revisor 4.4

- **Frete ANTT: guia rápido para embarcadores** · ignorar · ed 67 / pago 63 · selo alta · verificação parcial · revisor 4.8
  A Bomfim Cargas pode publicar um guia curto explicando o que mudou no piso mínimo do frete e o que o embarcador precisa checar em CIOT e Vale-Pedágio. O tema está quente agora porque a ANTT atualizou o piso e reforçou a fiscalização sobre o transporte rodoviário de cargas.
  - [C] diariodocomercio.com.br · ok · 2026-10-01 · https://diariodocomercio.com.br/economia/frete-minimo-antt-transportes-rodoviarios/
  - [A] gov.br · ok · 2026-10-01 · https://www.gov.br/antt/pt-br/assuntos/noticias-defeso-eleitoral/antt-aprova-novos-projetos-de-concessao-atualiza-o-piso-do-frete-e-amplia-fiscalizacao-e-seguranca-viaria-em-setembro
  - [A] gov.br · ok · 2026-09-16 · https://www.gov.br/antt/pt-br/assuntos/noticias-defeso-eleitoral/antt-inicia-procedimentos-para-suspensao-de-empresas-que-descumprem-o-piso-minimo-do-frete/
  - [C] gazetadoparana.com.br · ok · 2026-09-29 · https://gazetadoparana.com.br/publico/antt-aprova-transicao-para-novas-regras-do-ciot-no-frete-rodoviario
  Revisor: Guia ANTT com fontes gov.br A recentes (01/10) e tema quente de fiscalização; executável em 2 semanas como conteúdo educativo para embarcadores.
- **Rotas críticas MG-SP no pico: reduzir atraso e custo** · ignorar · ed 60 / pago 62 · selo alta · verificação parcial · revisor 4.8
  A Bomfim Cargas deve ativar um conteúdo e uma campanha geolocalizada sobre rotas críticas no Sudeste, mostrando como planejar coleta, janela de entrega e custo em trechos com trânsito pesado em MG e SP. Isso é relevante agora porque há trânsito crítico em rodovias do Sudeste e mudanças de pedágio/fluxo em corredores importantes.
  - [C] noticias.portaldaindustria.com.br · ok · 2026-10-06 · https://noticias.portaldaindustria.com.br/noticias/competitividade/16-trechos-de-rodovias-do-sudeste-tem-transito-critico-em-horarios-de-pico/
  - [A] gov.br · ok · 2026-10-01 · https://www.gov.br/antt/pt-br/assuntos/noticias-defeso-eleitoral/antt-aprova-novos-projetos-de-concessao-atualiza-o-piso-do-frete-e-amplia-fiscalizacao-e-seguranca-viaria-em-setembro
  - [A] gov.br · ok · 2026-09-16 · https://www.gov.br/antt/pt-br/assuntos/noticias-defeso-eleitoral/dia-nacional-do-caminhoneiro-como-a-regulacao-da-antt-acompanha-quem-vive-do-transporte-de-cargas/
  Revisor: Rotas críticas MG-SP com dados gov.br A e Portal da Indústria C (06/10); campanha geolocalizada viável até dezembro com sustentação no pico.
- **Kit do embarcador: documentos e regras do frete** · ignorar · ed 61 / pago 56 · selo alta · verificação parcial · revisor 3.6
  A Bomfim Cargas pode oferecer um kit curto com checklist de documentos, cadastro e obrigações do transporte rodoviário de cargas para embarcadores e novos contratantes. A ação é útil porque a ANTT fiscaliza RNTRC, notas, manifesto e outras exigências que impactam a contratação e a execução do frete.
  - [A] gov.br · ok · s/ data · https://www.gov.br/antt/pt-br/a-antt/o-transporte-de-cargas
  - [A] gov.br · ok · s/ data · https://www.gov.br/antt/pt-br/assuntos/noticias-defeso-eleitoral/dia-nacional-do-caminhoneiro-como-a-regulacao-da-antt-acompanha-quem-vive-do-transporte-de-cargas
  Revisor: Kit embarcador com fontes gov.br A mas sem data; conteúdo evergreen útil mas não urgente; publicação em 3 semanas.

### F5 — Grok + web e X · revisor 4.0

- **Relatório frete+IA Black Friday para clientes MG/SP** · ignorar · ed 50 / pago 47 · selo media · verificação parcial · revisor 4.6
  S1 mostra que frete, dados e IA decidem conversão na Black Friday 2026; Bomfim Cargas deve enviar relatório customizado com rotas MG-SP otimizadas para 15 clientes de e-commerce até 20/10/2026.
  - [B] ecommercebrasil.com.br · ok · 2026-09-09 · https://www.ecommercebrasil.com.br/noticias/frete-dados-e-ia-devem-pautar-logistica-na-black-friday-2026-mostra-relatorio
  Revisor: Relatório customizado com dados de IA sobre frete em Black Friday é acionável esta semana e alinha perfeitamente com posicionamento B2B da marca.
- **Comunicado piso mínimo frete ANTT para base MG/SP** · ignorar · ed 54 / pago 50 · selo media · verificação parcial · revisor 4.4
  S4 e S5 confirmam reajuste ANTT com diesel a R$7,33; Bomfim Cargas deve enviar comunicado com tabela atualizada e impacto em rotas MG-SP até 15/10/2026.
  - [A] cnnbrasil.com.br · ok · 2026-09-30 · https://www.cnnbrasil.com.br/infra/tensoes-globais-multiplicam-periodos-de-alta-demanda-no-frete-diz-dhl-global-forwarding/
  - [C] minaspetro.com.br · ok · 2026-10-02 · https://minaspetro.com.br/setor-de-transportes-rodoviarios-de-cargas-diz-que-reajuste-da-tabela-do-frete-minimo-ajuda-mas-nao-resolve-problemas/
  Revisor: Comunicado sobre piso ANTT é urgente e obrigatório, mas tema genérico; fontes A+C sustentam, prazo até 15/10 é crítico.
- **Planejamento rotas Fernão Dias Black Friday** · ignorar · ed 50 / pago 47 · selo baixa · verificação parcial · revisor 3.0
  S8 informa interdições na Fernão Dias 6-8/10; Bomfim Cargas deve publicar plano de rotas alternativas MG-SP para clientes até 05/10/2026.
  - [C] mobilidadesampa.com.br · ok · 2026-10-02 · https://mobilidadesampa.com.br/2026/10/passarela-na-fernao-dias-icamento-vigas-outubro/
  Revisor: Fonte C única sobre interdições Fernão Dias; prazo já vencido (05/10) e informação pode estar desatualizada.

### F2 — OpenAI nativo · revisor 3.4

- **Comunicação de compliance ANTT e apoio direto ao caminhoneiro** · ignorar · ed 46 / pago 43 · selo media · verificação parcial · revisor 3.2
  Comunicar que Bomfim Cargas já cumpre regras ANTT (CIOT, vale‑pedágio, frete mínimo) e lançar pacote operacional de apoio ao motorista (checklist, canal dedicado, vale‑pedágio operacional) para reduzir risco regulatório e atrair clientes B2B preocupados com conformidade no pico.
  - [A] gov.br · ok · 2026-09-16 · https://www.gov.br/antt/pt-br/assuntos/noticias-defeso-eleitoral/dia-nacional-do-caminhoneiro-como-a-regulacao-da-antt-acompanha-quem-vive-do-transporte-de-cargas/
  - [A] gov.br · ok · 2026-03- (resoluções recentes com ampla implementação em 2026; ações divulgadas em notícias recentes) · https://www.gov.br/antt/pt-br/assuntos/ultimas-noticias/antt-publica-duas-resolucoes-transforma-medida-provisoria-em-operacao-real-bloqueia-distorcoes-na-origem-e-eleva-o-padrao-de-fiscalizacao-no-pais
  Revisor: Compliance ANTT + apoio motorista com fonte A (16/09) mas tese genérica; ação até 31/12 é longa; falta diferencial claro.
- **Serviço e comunicação de alertas de rotas e rotas alternativas (MG e SP)** · ignorar · ed 49 / pago 39 · selo media · verificação parcial · revisor 4.4
  Implementar e oferecer como serviço premium alertas em tempo real e sugestões de rotas alternativas para reduzir atrasos por obras/interdições em rodovias-chave de Minas Gerais e São Paulo durante o pico.
  - [A] gov.br · ok · 2026-09- (documento publicado em setembro de 2026) · https://www.gov.br/dnit/pt-br/assuntos/infraestrutura-rodoviaria/aet/restricoes/restricao-temporaria/09-2026/sp.pdf/view
  - [A] otempo.com.br · ok · 2026-09-24 · https://www.otempo.com.br/cidades/2026/9/24/apos-um-mes-interditada-mgc-383-tem-trafego-parcialmente-liberado-entenda-as-restricoes
  - [A] otempo.com.br · ok · 2026-09-24 · https://www.otempo.com.br/cidades/2026/9/24/atencao-motoristas-trecho-da-br-040-entre-bh-e-juiz-de-fora-tera-obras-ate-outubro-saiba-onde
  - [A] otempo.com.br · ok · 2026-09-24 · https://www.otempo.com.br/cidades/2026/9/24/br-381-tera-interdicao-de-ate-15-minutos-para-detonacao-de-rocha-em-minas.amp
  Revisor: Alertas de rotas com fontes A (O Tempo 24/09 sobre BR-040, BR-381, MG-383); serviço premium viável mas requer integração técnica imediata.
- **Oferta de SLA com integração técnica (API) para e‑commerces em MG/SP** · ignorar · ed 39 / pago 40 · selo media · verificação parcial · revisor 2.6
  Posicionar Bomfim Cargas para varejistas e marketplaces oferecendo SLAs claros para entregas do pico e integração técnica (API/WMS) para garantir prazos e comunicação automática — fechar propostas comerciais até outubro.
  - [B] ecommercebrasil.com.br · ok · 2026-09-?? · https://www.ecommercebrasil.com.br/noticias/frete-dados-e-ia-devem-pautar-logistica-na-black-friday-2026-mostra-relatorio
  - [A] gov.br · ok · 2026-03- (resoluções recentes com ampla implementação em 2026; ações divulgadas em notícias recentes) · https://www.gov.br/antt/pt-br/assuntos/ultimas-noticias/antt-publica-duas-resolucoes-transforma-medida-provisoria-em-operacao-real-bloqueia-distorcoes-na-origem-e-eleva-o-padrao-de-fiscalizacao-no-pais
  Revisor: SLA+API para e-commerces com fonte B sem data (ecommercebrasil) e gov.br sem data; tese ambiciosa mas falta urgência e viabilidade técnica clara.
