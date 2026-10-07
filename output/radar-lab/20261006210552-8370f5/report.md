# Radar Lab — 20261006210552-8370f5

Cenário **nike** · tema: corrida de rua, provas de fim de ano e São Silvestre · praças: São Paulo, Rio de Janeiro · janela: 30 dias · 1 token Cadu = US$ 0.00016053 · tempo total 165.8 s

Melhor versão de prompts: **1.0** · ruído médio da média do revisor (fluxo sem mudança, de uma passada para outra): 0.07 ponto(s)

## Comparação dos fluxos (melhor versão de cada um)

Critério: **pontos** = soma das notas do revisor das oportunidades **boas** (nota ≥ 4 e selo ≠ baixa). Cortar uma oportunidade boa perde pontos; uma fraca não soma.

| Fluxo | Tipo | Pontos | Boas/total | Média revisor | Pontos por volta: pontos (boas/total) | Evidências | Fontes A/B | URLs abrem | Na janela | Selo a/m/b | Tokens sim. | Tokens debitados | US$ provedor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F2 OpenAI nativo | web | **13.2** | 3/3 | 4.4 | v1.0: 8.0 (2/4) → 13.4 (3/3) → 13.2 (3/3) | 6 | 83% | 100% | 100% | 3/0/0 | 10.728 | 10.092 | 0.0890 |
| F1 Perplexity + imprensa | perplexity | **12.8** | 3/4 | 4.15 | v1.0: 12.8 (3/4) → 0 (0/3) → 0 (0/3) | 14 | 55% | 100% | 29% | 4/0/0 | 720 | 587 | 0.0935 |
| F5 Grok + web e X | web | **4.0** | 1/1 | 4.0 | v1.0: 0 (0/2) → 0 (0/1) → 4.0 (1/1) | 14 | 100% | 100% | 100% | 1/0/0 | 504 | 1.401 | 0.2244 |

Revisor e médico de prompts (compartilhados): 209 tokens debitados, US$ 0.0333. Total da rodada: 12.289 tokens, US$ 0.4402.

## Versões de prompt

| Versão | Pontos médios por fluxo | Vencedor do revisor | Pontos por fluxo |
|---|---|---|---|
| 1.0 | 10.0 | F2 | F1 12.8, F2 13.2, F5 4.0 |

**Médico de prompts → v1.1** (a partir da v1.0): 0 mudança(s) aceita(s), 0 recusada(s).

**Revisor (anthropic/claude-haiku-4.5), última passada da melhor versão:** vencedor F2. Sistema A combina veracidade (fontes oficiais Nível A), recencia (todas na janela), aderência máxima (Nike SP City Marathon é evento próprio) e ação imediata (negociações e logística esta semana). B é defensivo e genérico; C oferece contexto mas sem gatilhos táticos urgentes.
- F2: Sistema A entrega 3 oportunidades com alta confiança e fontes Nível A (Prefeitura + Nike.com.br), focadas em ativações on-site, campanhas táticas de produto e run-to-store. Todas estão na janela e permitem ação imediata. Melhor em: Veracidade (fontes oficiais), Ação (eventos e datas claras), Aderência (alinhamento direto Nike).. Pior em: Novidade (A2 é genérico em produto/treino); A1 e A3 dependem de nike.com.br bloqueado..
- F5: Sistema B oferece 1 oportunidade defensiva (Circuito das Estações) com fonte Nível A recente, mas tática é reativa (capturar em eventos não-patrocinados) e menos diferenciada. Melhor em: Recencia (outubro 2026), Veracidade (Prefeitura oficial).. Pior em: Novidade (OOH em eventos é tática padrão), Ação (menos urgente que A1)..
- F1: Sistema C gera 3 insights contextuais com mix de fontes Nível A (Folha, O Globo, Veja) mas 2 de 3 fora da janela ou com dados defasados (2024). Tendências são reais mas genéricas e não disparam ação tática imediata. Melhor em: Recencia parcial (C3 é de 02-out), Aderência (corredores iniciantes e noturnas são públicos Nike).. Pior em: Veracidade (dados 2024 em C1), Ação (insights sem gatilho operacional), Novidade (tendências óbvias)..

## Custo por chamada: simulado x real

| Versão | Fluxo | Etapa | Modelo | Rota | Regime | Simulado | Debitado | US$ provedor | Entrada/saída | Tempo | Nota |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | F1 | discover_press | perplexity/sonar | openrouter | custo | 41 | 34 | 0.00544 | 429/6 | 4.9 s |  |
| 1.0 | F2 | discover_press | openai/gpt-5-mini | openrouter | custo | 86 | 76 | 0.01206 | 9.138/290 | 5.0 s |  |
| 1.0 | F1 | discover_trends | perplexity/sonar | openrouter | custo | 40 | 37 | 0.00580 | 224/579 | 5.5 s |  |
| 1.0 | F1 | discover_open | perplexity/sonar-pro | openrouter | custo | 137 | 148 | 0.02374 | 264/1.130 | 7.1 s |  |
| 1.0 | F5 | discover_press | x-ai/grok-4.3 | openrouter | custo | 63 | 236 | 0.03778 | 21.226/1.171 | 13.3 s |  |
| 1.0 | F2 | discover_open | openai/gpt-5-mini | openrouter | custo | 86 | 156 | 0.02501 | 9.527/1.818 | 16.4 s |  |
| 1.0 | F5 | discover_open | x-ai/grok-4.3 | openrouter | custo | 62 | 320 | 0.05135 | 21.277/2.061 | 18.5 s |  |
|  | F1 | extract | firecrawl/scrape | firecrawl | firecrawl | 63 | 64 | 0.01027 | 0/0 | 11.3 s |  |
| 1.0 | F1 | judge | openai/gpt-5.4-mini | openrouter | custo | 101 | 68 | 0.01091 | 3.686/1.810 | 11.5 s |  |
| 1.0 | F5 | judge | x-ai/grok-4.3 | openrouter | custo | 67 | 46 | 0.00736 | 3.046/1.476 | 13.5 s |  |
| 1.0 | F1 | check | perplexity/sonar | openrouter | custo | 46 | 39 | 0.00615 | 455/692 | 4.7 s |  |
| 1.0 | F2 | judge | gpt-5-mini | openai | tokens | 4.993 | 4.687 | 0.00579 | 2.049/2.638 | 20.3 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F5 | check | x-ai/grok-4.3 | openrouter | custo | 62 | 300 | 0.04813 | 19.585/1.621 | 17.4 s |  |
| 1.0 | F2 | check | openai/gpt-5-mini | openrouter | custo | 86 | 94 | 0.01497 | 9.346/1.719 | 20.8 s |  |
| 1.0 | REV | review-1.0-r0 | anthropic/claude-haiku-4.5 | openrouter | custo | 112 | 85 | 0.01357 | 4.107/1.893 | 15.9 s |  |
| 1.0 | F5 | revise-r1 | x-ai/grok-4.3 | openrouter | custo | 64 | 39 | 0.00610 | 2.702/1.170 | 11.3 s |  |
| 1.0 | F1 | revise-r1 | openai/gpt-5.4-mini | openrouter | custo | 101 | 78 | 0.01236 | 3.617/2.145 | 12.9 s |  |
| 1.0 | F2 | revise-r1 | gpt-5-mini | openai | tokens | 5.391 | 4.918 | 0.00541 | 2.529/2.389 | 19.2 s | custo do provedor calculado pela tabela (a OpenAI direta não informa USD) |
| 1.0 | F1 | check-r1 | perplexity/sonar | openrouter | custo | 45 | 39 | 0.00625 | 380/869 | 8.0 s |  |
| 1.0 | F5 | check-r1 | x-ai/grok-4.3 | openrouter | custo | 61 | 214 | 0.03432 | 14.338/1.151 | 12.6 s |  |
| 1.0 | F2 | check-r1 | openai/gpt-5-mini | openrouter | custo | 86 | 161 | 0.02578 | 13.323/1.630 | 14.8 s |  |
| 1.0 | REV | review-1.0-r1 | anthropic/claude-haiku-4.5 | openrouter | custo | 106 | 63 | 0.00998 | 2.653/1.465 | 14.6 s |  |
| 1.0 | F1 | revise-r2 | openai/gpt-5.4-mini | openrouter | custo | 101 | 41 | 0.00644 | 3.617/1.328 | 8.8 s |  |
| 1.0 | F5 | revise-r2 | x-ai/grok-4.3 | openrouter | custo | 64 | 25 | 0.00395 | 2.702/1.359 | 12.0 s |  |
| 1.0 | F1 | check-r2 | perplexity/sonar | openrouter | custo | 45 | 39 | 0.00617 | 407/762 | 6.9 s |  |
| 1.0 | F5 | check-r2 | x-ai/grok-4.3 | openrouter | custo | 61 | 221 | 0.03542 | 15.015/1.226 | 12.7 s |  |
| 1.0 | REV | review-1.0-r2 | anthropic/claude-haiku-4.5 | openrouter | custo | 106 | 61 | 0.00972 | 2.688/1.406 | 13.3 s |  |
| 1.0 | DOC | doctor-1.0 | openai/gpt-5.4 | openrouter | custo | 310 | 0 | 0.00000 | 0/0 | 0.35207320895278826 s | FALHOU OpenRouterError: O saldo da conta OpenRouter é insuficiente. |

## Oportunidades (melhor versão de cada fluxo)

### F2 — OpenAI nativo · revisor 4.4

- **Ativação on-site: Nike SP City Marathon 2026** · ignorar · ed 55 / pago 57 · selo alta · verificação confirmado · revisor 4.6
  A Nike já comunica presença oficial no 'Nike SP City Marathon' (S2) e a Prefeitura de SP listou corridas autorizadas (S1) — agir agora garante exposição on-site, teste de produtos e conteúdo urbano relevante antes da temporada de fim de ano.
  - [A] nike.com.br · bloqueado · 2026-09-16 · https://www.nike.com.br/sc/nike-sp-city-marathon
  - [A] prefeitura.sp.gov.br · ok · 2026-09-15 · https://prefeitura.sp.gov.br/w/servico/corridas-de-rua
  Revisor: Evento próprio Nike com confirmação oficial (Prefeitura + nike.com.br); janela curta exige ação imediata em negociações e logística.
- **Campanha tática: linha de produto e treinos para 5–10 km e meias** · ignorar · ed 47 / pago 52 · selo alta · verificação confirmado · revisor 4.2
  Calendários especializados indicam crescimento de provas de 5–10 km e meia maratonas (S5) e a Nike tem presença em provas urbanas (S2) — oportunidade para promover produtos específicos e programas de 4–8 semanas para corredores urbanos em SP e RJ.
  - [C] corrida360.com.br · ok · 2026-09-22 · https://corrida360.com.br/blog/corridas-de-rua-no-rio-de-janeiro-2026
  - [A] nike.com.br · bloqueado · 2026-09-16 · https://www.nike.com.br/sc/nike-sp-city-marathon
  Revisor: Campanha tática sólida mas fonte C (corrida360.com.br) reduz confiança; produto e treino são genéricos para Nike.
- **Run-to-store/local engagement: test-run e ofertas regionais em SP** · ignorar · ed 53 / pago 57 · selo alta · verificação parcial · revisor 4.4
  Com eventos e autorizações listadas pela Prefeitura (S1) e prova própria da Nike em SP (S2), ativar experiências em lojas e parques cria fluxo direto de participantes para compras locais e test-drives de produto.
  - [A] prefeitura.sp.gov.br · ok · 2026-09-15 · https://prefeitura.sp.gov.br/w/servico/corridas-de-rua
  - [A] nike.com.br · bloqueado · 2026-09-16 · https://www.nike.com.br/sc/nike-sp-city-marathon
  Revisor: Run-to-store com base em eventos reais; exige coordenação com lojas e parques, viável mas operacionalmente complexo.

### F1 — Perplexity + imprensa · revisor 4.15

- **Ative São Silvestre com conversão de fim de ano** · ignorar · ed 64 / pago 62 · selo alta · verificação parcial · revisor 4.0
  A São Silvestre segue como ativo cultural e comercial de alto alcance em São Paulo no pico de dezembro, com forte adesão e associação à tradição. Nike pode usar esse momento para capturar intenção de compra de performance e presenteável com campanha, landing e oferta de corrida.
  - [B] terra.com.br · ok · 2025-12-31 · https://www.terra.com.br/noticias/mercado-de-wellness-cresce-junto-a-sao-silvestre-2025,215cecc1fdb9ac0bcf07cbb066045245umgfx5fq.html
  - [C] maquinadoesporte.com.br · ok · s/ data · https://maquinadoesporte.com.br/running/sao-silvestre-inicia-novo-seculo-unindo-tradicao-com-experiencia-conexao-e-visibilidade/
  - [C] corrida360.com.br · ok · s/ data · https://corrida360.com.br/blog/corridas-de-rua-em-sao-paulo-2026
  Revisor: São Silvestre é ativo cultural comprovado (Nível A + B), mas fonte principal está fora da janela; oportunidade de conversão de fim de ano é clara e acionável já.
- **Explorar o boom de corridas em São Paulo** · ignorar · ed 67 / pago 66 · selo alta · verificação confirmado · revisor 4.2
  São Paulo vive expansão consistente do calendário de corrida de rua, com alta de provas e calendário aquecido. Nike pode se posicionar com uma jornada sempre-on de corrida, ativando produto, comunidade e aquisição durante a temporada.
  - [A] prefeitura.sp.gov.br · ok · 2025-08-31 · https://prefeitura.sp.gov.br/web/prefeitura-de-sao-paulo/w/corridas-de-rua-conquistam-cada-vez-mais-paulistanos
  - [C] eventia-br.meublog.net · ok · 2026-03-30 · https://eventia-br.meublog.net/post/calendario-corridas-de-rua-sao-paulo-2026
  - [A] prefeitura.sp.gov.br · ok · s/ data · https://prefeitura.sp.gov.br/web/esportes/w/noticias/36750
  Revisor: Prefeitura (Nível A) confirma boom de corridas em SP; dados sólidos mas não recentes; estratégia sempre-on é viável e alinhada com Nike.
- **Lançar campanha para 5K/10K e estreia na corrida** · ignorar · ed 66 / pago 68 · selo alta · verificação confirmado · revisor 4.6
  O calendário de São Paulo mostra muitas provas curtas e conteúdo de preparação, sinalizando entrada de novos corredores. Nike pode capturar iniciantes com produto de porta de entrada, conteúdo de treino e incentivo para primeira prova.
  - [C] eventia-br.meublog.net · ok · 2026-03-30 · https://eventia-br.meublog.net/post/calendario-corridas-de-rua-sao-paulo-2026
  - [A] www1.folha.uol.com.br · ok · 2026-09-01 · https://www1.folha.uol.com.br/equilibrio/2026/09/o-que-e-preciso-saber-antes-de-participar-de-uma-corrida-de-rua.shtml
  - [A] oglobo.globo.com · ok · 2026-09-28 · https://oglobo.globo.com/patrocinado/pulse-brand/noticia/2026/09/28/a-corrida-explodiu-no-brasil-agora-o-corredor-quer-aprender-a-descansar-1.ghtml
  Revisor: Folha e O Globo (Nível A, recente) validam entrada de iniciantes; campanha de porta de entrada é acionável esta semana com conteúdo e produto.
- **Apostar em corrida noturna com clima festivo** · ignorar · ed 52 / pago 54 · selo alta · verificação parcial · revisor 3.8
  As corridas noturnas e experiências com música/ambiente social estão em alta no Brasil, especialmente para públicos jovens. Nike pode testar eventos, ativações e criativos com estética noturna para ampliar relevância cultural e diferenciar a marca.
  - [C] vogue.globo.com · ok · 2026-09 · https://vogue.globo.com/wellness/noticia/2026/09/das-running-raves-aos-festivais-a-pista-de-corrida-da-vez-esta-diferente-e-muito-mais-animada.ghtml
  - [A] veja.abril.com.br · ok · 2026-10-02 · https://veja.abril.com.br/saude/por-que-as-corridas-de-rua-noturnas-estao-com-tudo-no-brasil/
  Revisor: Veja (Nível A, recente) confirma corridas noturnas em alta, mas Vogue é Nível C; diferenciação cultural é forte mas requer testes e parcerias.

### F5 — Grok + web e X · revisor 4.0

- **Ativar em Circuito das Estações SP com OOH e eventos Nike Run Club** · ignorar · ed 50 / pago 48 · selo alta · verificação parcial · revisor 4.0
  Calendário oficial da Prefeitura (S5) lista dezenas de provas em SP out-dez 2026; Nike pode capturar corredores de rua em eventos não patrocinados pela Netshoes via ativações presenciais e OOH perto de largadas.
  - [A] prefeitura.sp.gov.br · ok · 2026-10-01 · https://prefeitura.sp.gov.br/web/esportes/w/corridas_de_rua/8722
  Revisor: Circuito das Estações é real e recente; OOH em eventos não-patrocinados é tática defensiva, menos diferenciada.
