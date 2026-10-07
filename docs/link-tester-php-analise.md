# Link Tester: o que o PHP tem e o Reports ainda não

Levantamento de 07/10/2026 sobre o código PHP (`centralcomm/www/cadu`) e a base de produção (só leitura). Objetivo: o Link Tester do Reports precisa mostrar **dentro da ferramenta** tudo o que a análise coleta; o link público é um extra, não a única forma de ver o resultado.

## 1. A base de dados

| Tabela | Linhas | O que guarda |
|---|---|---|
| `cadu_link_tests` | 252 | Uma análise por linha. Colunas resumidas (SSL, robots, tempo, redirects, tags, print) e o JSON `analise_completa` (média de 8,5 KB) com até 50 blocos |
| `cadu_site_agentic_checks` | 46 | Catálogo de checagens agênticas com categoria, peso e severidade |
| `cadu_link_tester_monitored` | 3 | Domínios monitorados (vivara, g1, tim); nunca rodaram (`last_score` vazio) |
| `cadu_link_tester_alerts` | 0 | Alertas de queda de score; nenhum gerado |
| `cadu_growth_link_tester_usage` | 67 | Uso da versão pública de growth no site centralcomm.media (limite por IP) |
| `cadu_reports_link_test_runs` | 1 | A tabela nova do Reports |

- 234 análises "campanha" e 18 "completo", de 06/02 a 24/09/2026, em 2 clientes, 8 usuários e 98 domínios.
- 14 análises já estão no formato v2 ("media readiness"), 18 têm o bloco agêntico, 12 têm análise de rede e 3 têm teste de jornada.
- **O Reports nunca leu `cadu_link_tests`.** O histórico do PHP não aparece em lugar nenhum do produto novo.

### O que cada análise guarda (`analise_completa`)

| Bloco | Conteúdo |
|---|---|
| `ssl` | Válido, emissor, organização, validade, dias restantes, EV, wildcard, SAN, algoritmo, tamanho de chave |
| `http_status` | Código, soft 404, página de erro |
| `redirects` | Cadeia completa e código final |
| `performance` | Tempo de resposta, tamanho da página e classificação |
| `meta` | Título e tamanho, descrição, canonical, viewport, favicon, OG completo, contagem de H1, links e imagens, se é mobile friendly |
| `robots` | robots.txt, meta robots e X-Robots-Tag, Googlebot, **AdsBot Google** (teste de acesso real com código HTTP e motivo do bloqueio), facebookbot, `google_ads_ready` |
| `tags` | 22 plataformas (GA4, GTM, Ads, remarketing, Meta Pixel e **Conversions API**, TikTok, LinkedIn, Pinterest, Snapchat, Taboola, Criteo, X, Hotjar, Clarity, HubSpot, RD Station, ActiveCampaign, Mailchimp, VTEX, Shopify, WooCommerce). Cada uma com ID, se carrega via GTM e eventos |
| `tags_analysis` | Erros, duplicadas, tags antes do consentimento, detectadas por rede, sem conversão, **recomendadas ausentes**, agrupadas por plataforma |
| `events` | dataLayer, eventos GA4, GTM e Meta, duplicados, **eventos esperados ausentes** (lead, form_submit, whatsapp_click...) e **lacunas de conversão** (elemento visível sem evento) |
| `conversion` | Formulários (lead, contato, newsletter, campos), WhatsApp (número, links), telefones (click to call), e-mails, **CTAs (acima da dobra)**, **widgets de chat**, popups, nota de conversão |
| `compliance` | LGPD/GDPR, termos, política de privacidade e de cookies, banners de cookie, Consent Mode, links encontrados, detecção em SPA |
| `consent_analysis` | Risco (nível e rótulo), ferramentas de consentimento, estados, tags antes do consentimento |
| `network_analysis` | Requisições de rede reais por plataforma (busca profunda) |
| `page_content` | Idioma, tipo de página (blog, landing, loja), headings, CTAs, ofertas, contagem de palavras |
| `media_platforms` | Prontidão por plataforma (Meta, Google, TikTok, LinkedIn, programática): nota, tags detectadas e faltantes, eventos, problemas, recomendações |
| `media_readiness` | Notas por módulo (técnico, performance, tags, conversão, compliance, IA, ads), **checklist** (passou, atenção, falhou, com explicação e correção), resumo, **comparação com o histórico** |
| `recommendations` / `prioritized_recommendations` | Itens com severidade, esforço, impacto, público (dev ou marketing), **ganho estimado de score** e **ação** (`gtm_instruction`, `configure_event`, `consent_mode`, `consent_fix`, `generate_llms_txt`, `platform_checklist`, `compliance_review`) |
| `screenshot` | **Desktop e mobile** (ScreenshotOne) |
| `site_agentic` | As 46 checagens, cada uma com status, mensagem, evidência, **método da análise** e **como melhorar**. Notas por camada (llms, page, robots, sitemap) e **qualidade da análise** por categoria |
| `session_tests` | **Teste de jornada**: simula o objetivo (WhatsApp, formulário, lead, compra, CTA, scroll, download) com passos, eventos capturados e duração |
| `analysis_scopes` / `scores_by_scope` | Módulos escolhidos pelo usuário (infra, tags, conversão, compliance, ads, agêntico) e nota por módulo |

### As 46 checagens agênticas do catálogo

- **infra (6):** HTTPS, HTTP 200, sem soft 404, redirects, tempo de resposta, SSL.
- **llms (8):** existe, H1, resumo, seções de links, llms-full, links acessíveis, seção Optional, quantidade de links.
- **page (12):** canonical, H1 único, JSON-LD, Organization/WebSite, landmarks, volume de texto, idioma, OG, não é SPA vazia, indexável, sem overlay bloqueante, conversão visível no HTML.
- **robots (10):** existe, sitemap declarado, GPTBot, OAI-SearchBot, ClaudeBot, Claude-SearchBot, PerplexityBot, Google-Extended, wildcard, paths sensíveis, meta robots e X-Robots-Tag.
- **sitemap (8):** encontrado, XML válido, quantidade de URLs, lastmod, homepage presente, **amostra de URLs saudável**, **sem 404 em massa**, sitemap index.

## 2. O back-end PHP

| Peça | Papel |
|---|---|
| `api/link-tester.php` (3,9 mil linhas) | Processador: coleta, módulos, notas, gravação |
| `includes/LinkAnalyzer.php` (3,1 mil) | Coleta e detecção da análise "campanha" |
| `includes/link-tester/*` | v2: normalização de URL, tags, eventos, rede, consentimento, plataformas, notas, recomendações, montagem do resultado, monitoramento, jornada |
| `LinkTesterPageSignals`, `LinkTesterScopes` | Sinais de página e módulos escolhidos |
| `ferramentas-link-tester*.php` + `views/link-tester/*` + `assets/js/link-tester/*` | Teste, resultado completo **dentro da ferramenta** (abas por módulo, acordeões, subnav com "Testar jornada", "Monitorar", "E-mail", "Compartilhar"), histórico por domínio com evolução, exportação do agêntico (llms.txt gerado, download) |
| `link-tester-public.php` | Página pública (o extra) |
| `api/link-tester-growth.php` | Versão aberta no site da Centralcomm, com limite por IP (aquisição) |
| `email-templates/link-tester-resultado.html` | E-mail do resultado |

## 3. Comparação com o Reports (Link Tester v2)

| Capacidade | PHP | Reports hoje |
|---|---|---|
| Resultado completo dentro da ferramenta | Sim, página própria com abas | Parcial: só logo após testar; o histórico não reabre o resultado |
| Quem testou | Sim (`user_id`) | Gravado (`created_by`), mas não exibido |
| Histórico do PHP (252) | Sim | **Não aparece** |
| Plataformas de tag | 22, com ID, via GTM e CAPI | 13 no inventário, com ID e origem |
| Prontidão por plataforma com recomendações | Sim | Só percentual simples |
| Eventos esperados ausentes e lacunas de conversão | Sim | Não |
| Elementos de conversão (CTA, chat, popup, click to call) | Sim | Só formulário, WhatsApp e telefone |
| Compliance e risco de consentimento | Sim, com nível de risco | Ferramenta e Consent Mode |
| AdsBot / Google Ads pronto | Sim | **Não** |
| SSL detalhado (dias restantes, emissor) | Sim | Só válido ou inválido |
| Meta e OG completos, conteúdo da página | Sim | Parcial (no agêntico) |
| Print | Desktop e mobile | Só desktop |
| Recomendações com ganho estimado e ação (GTM, llms.txt) | Sim | Achados com "como corrigir"; sem ganho nem ação |
| Checagens agênticas | 46, com método e evidência por item | Cerca de 25 achados; mais rígido em WAF, JS e HTML falso |
| Sitemap: amostra de URLs e 404 em massa | Sim | Não |
| Teste de jornada | Sim | Não |
| Monitoramento e alertas | Estrutura existe, sem uso | Não |
| Evolução por domínio | Sim | Não |
| Gerar llms.txt sugerido | Sim | Não |
| Revisor por IA | Não | **Sim** |
| Super Tag | Não | **Sim** |
| Bloqueio por WAF, conteúdo só JS, HTML falso em llms/robots | Parcial | **Sim** |

## 4. Problemas encontrados

1. **Chave da ScreenshotOne exposta.** As 252 `screenshot_url` guardam a URL da API com `access_key` em texto, e a página pública e o e-mail do PHP mostram essa URL. **Recomendação:** trocar a chave na ScreenshotOne e, ao migrar, baixar a imagem e servir pelo nosso endereço (como o Reports já faz).
2. Monitoramento criado e nunca executado (3 domínios, 0 alertas).
3. A análise completa de 8,5 KB é guardada, mas a página pública do PHP mostra só parte dela, e o Reports não mostra nada do histórico.

## 5. Proposta

**Fase 1: resultado completo dentro da ferramenta**
- Página do resultado no app (`/connect/app/tools/link-tester/<id>`), aberta pelo histórico, com abas por módulo: Resumo, Destino, Tags e plataformas, Conversão, Compliance, Agentes de IA, Recomendações, Print.
- Mostrar quem testou e quando. Compartilhar e enviar e-mail viram ações da página.
- Ler também `cadu_link_tests` (somente leitura, por um adaptador) para o histórico do PHP aparecer com tudo o que ele guardou.

**Fase 2: portar o que falta na coleta**
- AdsBot e Google Ads pronto, SSL detalhado, meta/OG/conteúdo.
- Elementos de conversão (CTA, chat, popup, click to call).
- Eventos esperados ausentes e lacunas de conversão, prontidão por plataforma, mais tags (CAPI, remarketing, Criteo, Taboola, RD, HubSpot, plataformas de e-commerce).
- Print mobile. Sitemap com amostra e 404.
- Usar o catálogo das 46 checagens como referência, preservando o rigor novo (WAF, JS, HTML falso).

**Fase 3: recomendações acionáveis e acompanhamento**
- Ganho estimado de score e ações: instrução para GTM, llms.txt gerado, evento a configurar.
- Evolução por domínio, monitoramento e alertas (no Central de alertas do Reports), teste de jornada.

A versão aberta de growth (`api/link-tester-growth.php`) fica fora deste plano até haver decisão comercial.

---

# Parte 2: análise completa dos dados, dividida pelas 3 análises

Números da base de produção em 07/10/2026 (252 análises, consultas só de leitura). "Cobertura" é quantas análises têm o dado preenchido. "Reports" é o Link Tester v2.

## 6. Visão geral da base

| Indicador | Valor |
|---|---|
| Análises | 252 (234 "campanha", 18 "completo") |
| Período | 06/02/2026 a 24/09/2026 |
| Clientes / usuários / domínios | 2 / 8 / 98 |
| Formato v2 (media readiness) | 14 |
| Com bloco agêntico | 18 |
| Com rede real (busca profunda) | 12 |
| Com teste de jornada | 3 (6 jornadas, todas "atenção") |
| Tamanho | 4 MB, 8,5 KB por análise |

| Nota | Campanha (234) | Completo (18) |
|---|---|---|
| Média | 81 | 64 |
| Mínima / máxima | 3 / 100 | 18 / 99 |
| 80 ou mais | 166 (71%) | 3 (17%) |
| Abaixo de 50 | 35 (15%) | 3 (17%) |

**Leitura:** a nota "campanha" é generosa (71% acima de 80) e não conversa com a "completo". O Reports deve ter uma escala só, com travas (como já faz no agêntico).

Domínios mais testados: g1.com.br (19), vivara.com.br (18 + 16 com www), www.centralcomm.media (17, nota de 26 a 100), stripe.com (12), byd.com.br (7), copasa.com.br (6). A coluna `root_domain` está vazia na maioria, então a evolução por domínio do PHP separa "vivara.com.br" de "www.vivara.com.br".

## 7. Análise 1: Destino ("O clique chega ao site?")

| Dado | PHP guarda | Cobertura e resultado na base | Reports hoje | Fazer |
|---|---|---|---|---|
| HTTP final, soft 404, página de erro | Sim | 39 com erro (15%), 6 soft 404 | Status final | Soft 404 e página de erro |
| Cadeia de redirects | Sim | 168 com redirect (67%), no máximo 1 salto | Sim | — |
| UTMs | Não guarda em separado | — | **Sim (só no Reports)** | — |
| Tempo de resposta | Sim | média 2,1 s; p90 1,3 s (há valores extremos) | Sim | Mostrar p90 do histórico do domínio |
| Tamanho da página | Sim | média 390 KB | Não | Portar |
| SSL detalhado | Sim (emissor, validade, dias restantes, EV, SAN, chave) | 245 válidos; **16 vencem em menos de 30 dias** | Só válido/inválido | Portar, com alerta de vencimento |
| AdsBot / Google Ads pronto | Sim, com teste de acesso real | 109 prontos; **15 com AdsBot bloqueado** | Não | Portar (crítico para mídia paga) |
| Mobile friendly, viewport | Sim | 193 ok (77%) | Não | Portar |
| Título, descrição, OG, H1 | Sim | OG image em 120 (48%); H1 único em 106 (42%) | Título e descrição | Portar OG e H1 |
| Print desktop e mobile | Sim (ScreenshotOne, chave exposta) | 252 | **Desktop e mobile assinados (feito agora)** | Migrar os antigos para o nosso disco |

## 8. Análise 2: Medição de mídia ("A conversão será medida?")

### Tags por plataforma (das 251 análises)

| Tag | Detectada | % | Reports |
|---|---|---|---|
| GA4 | 161 | 64% | Sim |
| GTM | 154 | 61% | Sim |
| Google Ads | 73 | 29% | Sim |
| VTEX | 43 | 17% | Não |
| WooCommerce | 25 | 10% | Não |
| Microsoft Clarity | 16 | 6% | Sim |
| Hotjar | 15 | 6% | Sim |
| Meta Pixel | 12 | 5% | Sim |
| RD Station | 8 | 3% | Não |
| HubSpot | 2 | 1% | Não |
| Shopify, remarketing Google, LinkedIn, Meta CAPI | 1 cada | <1% | LinkedIn sim; os outros não |
| TikTok, Pinterest, Snapchat, Taboola, Criteo, X, Mailchimp, ActiveCampaign | 0 | 0% | TikTok, Pinterest e X sim |
| Cadu Super Tag | — | — | **Sim (só no Reports)** |

**Leitura crítica:**
- `loaded_via_gtm` é **zero em todas** as 251, e o Meta Pixel aparece em só 5%. O PHP lia o HTML estático; tag disparada pelo GTM era invisível.
- O Reports corrige isso porque compara o HTML entregue com o renderizado e marca "injetada (GTM/JS)".
- Os números acima subestimam a realidade.

### Conversão

| Elemento | Análises | % | Reports |
|---|---|---|---|
| CTA | 200 | 80% | Não |
| Popup | 191 | **76% (provável falso positivo)** | Não |
| Formulário | 75 | 30% | Sim |
| WhatsApp | 70 | 28% | Sim |
| Telefone | 61 | 24% | Sim |
| Widget de chat | 31 | 12% | Não |
| Nota média de conversão | 27 | — | — |

### Eventos e lacunas (12 análises v2)

| Indicador | Valor |
|---|---|
| Com dataLayer | 6 de 12 |
| Com lacuna de conversão (elemento visível sem evento) | 8 de 12, média 1,3 por página |

O Reports lista eventos, mas não cruza "elemento visível × evento esperado". Isso deve ser portado: é o achado mais acionável para mídia.

### Compliance (247 análises)

| Sinal | Análises | % | Reports |
|---|---|---|---|
| Política de privacidade | 125 | 51% | Sim |
| Termos | 79 | 32% | Não |
| Banner de consentimento | 64 | 26% | Sim (ferramenta de consentimento) |
| Menção à LGPD | 58 | 23% | Não |
| Política de cookies | 13 | 5% | Não |
| **Consent Mode** | **0** | **0%** | Sim |

Consent Mode zerado em 247 análises indica **detector quebrado no PHP**, não ausência real. No Reports, o inventário procura `gtag('consent', ...)` no HTML renderizado.

### Prontidão por plataforma (14 análises v2)

| Plataforma | Prontidão média | Prontas |
|---|---|---|
| Programática | 52 | 2 |
| Google | 20 | 0 |
| Meta | 4 | 0 |
| TikTok | 0 | 0 |
| LinkedIn | 0 | 0 |

### Recomendações geradas (v2)

| Módulo | Ação | Severidade | Qtde | Ganho estimado |
|---|---|---|---|---|
| Plataformas | checklist da plataforma | alta | 51 | +7 |
| Tags | instrução para GTM | alta | 26 | +8 |
| Eventos | instrução para GTM | alta | 16 | +8 |
| Consentimento | ativar Consent Mode | média | 14 | +6 |
| Plataformas | checklist da plataforma | média | 11 | +7 |
| Tags | configurar evento | média | 5 | +5 |
| Segurança, acesso, status, performance | legado | crítica | 8 | +15 |

O Reports tem "como corrigir" por achado e o revisor de IA, mas não o **ganho estimado** nem a **ação pronta** (instrução de GTM). Portar.

## 9. Análise 3: Presença para agentes de IA ("Agentes conseguem ler o site?")

### Notas por camada (18 análises)

| Camada | Média |
|---|---|
| llms | **7** |
| page | 71 |
| robots | 82 |
| sitemap | 52 |
| Total agêntico | 71 |

### As 46 checagens: o que de fato rodou

"Não avaliada" é quando o PHP gravou a checagem sem resultado (pulada ou não implementada).

| Categoria | Checagem | Passou | Falhou | Não avaliada | Reports |
|---|---|---|---|---|---|
| llms | llms.txt existe | 1 | **17** | 0 | Sim (e detecta HTML falso) |
| llms | H1, seções de links | 1 | 1 | 16 | Sim |
| llms | resumo, contagem de links, llms-full, Optional | 0 | 0 | **18** | Sim (exceto Optional) |
| llms | links acessíveis | 1 | 0 | 17 | Sim (amostra de 5) |
| page | landmarks semânticos | 4 | **14** | 0 | Sim (main/article) |
| page | volume de texto | 5 | **13** | 0 | Sim (e compara com o renderizado) |
| page | JSON-LD | 10 | 8 | 0 | Sim (e valida o JSON) |
| page | conversão visível no HTML | 13 | 5 | 0 | Não |
| page | Organization/WebSite | 9 | 0 | 9 | Sim |
| page | OG completo | 10 | 0 | 8 | Não (no agêntico) |
| page | H1 único | 7 | 0 | 11 | Sim |
| page | sem overlay bloqueante | 8 | 0 | 10 | Não |
| page | indexável | 18 | 0 | 0 | Sim |
| page | **não é SPA vazia, canonical, idioma** | 0 | 0 | **18** | **Sim (rodam de verdade)** |
| robots | robots.txt existe | 11 | 7 | 0 | Sim |
| robots | sitemap declarado | 8 | 5 | 5 | Sim |
| robots | GPTBot, OAI-SearchBot, ClaudeBot, Claude-SearchBot, PerplexityBot, Google-Extended, wildcard | 12 | 1 | 5 | Sim (11 robôs, separando busca de treinamento) |
| robots | meta robots, X-Robots-Tag | 18 | 0 | 0 | Sim |
| robots | paths sensíveis | 2 | 0 | 16 | Não |
| sitemap | encontrado | 10 | 8 | 0 | Sim |
| sitemap | XML válido, quantidade de URLs | 10 | 1 | 7 | Sim |
| sitemap | amostra saudável, sem 404 em massa | 10 | 0 | 8 | **Não** |
| sitemap | index processado | 7 | 0 | 11 | Sim (detecta o index) |
| sitemap | **homepage no sitemap, lastmod** | 0 | 0 | **18** | Sim (página no sitemap, lastmod) |
| infra | HTTPS, HTTP 200, SSL | 15 a 17 | 1 a 3 | 0 | Sim |
| infra | sem soft 404, redirects | 18 | 0 | 0 | Parcial |
| infra | **resposta rápida** | 0 | 0 | **18** | Não (no agêntico) |
| — | **bloqueio por CDN/WAF com user-agent de robô** | — | — | **não existe** | **Sim (só no Reports)** |

**Leitura crítica:**
- Das 46 checagens do catálogo, **12 nunca produziram resultado** nas 18 análises (canonical, idioma, SPA vazia, resposta rápida, homepage e lastmod no sitemap, resumo do llms.txt, entre outras).
- O falso "llms.txt existe" também não é tratado: uma rota coringa que devolve HTML conta como existente.
- O catálogo vale como **lista de verificação e texto de "como melhorar"**. A execução do Reports é mais confiável e deve continuar sendo a base.

## 10. Divisão final: o que cada análise do Reports deve mostrar

| Bloco na tela | Destino | Mídia | Agentes | De onde vem |
|---|---|---|---|---|
| Nota com travas e status | ✓ | ✓ | ✓ | Reports |
| Print desktop + mobile | ✓ | ✓ | ✓ | Reports (ScreenshotOne assinado) |
| Caminho do clique, HTTP, soft 404, tempo, tamanho | ✓ | — | resumo | Reports + portar soft 404 e tamanho |
| UTMs | ✓ | — | — | Reports |
| SSL detalhado com vencimento | ✓ | — | resumo | Portar |
| AdsBot / Google Ads pronto | ✓ | ✓ | — | Portar |
| Mobile friendly, OG, H1 | ✓ | — | ✓ | Portar OG e mobile friendly |
| Plataformas com IDs (código × GTM) | — | ✓ | — | Reports (inventário) + tags de e-commerce e CRM do PHP |
| Prontidão por plataforma com checklist | — | ✓ | — | Portar |
| Elementos de conversão (form, WhatsApp, telefone, CTA, chat) | — | ✓ | conversão visível | Reports + portar CTA e chat |
| Eventos e **lacunas de conversão** | — | ✓ | — | Portar |
| Consentimento, LGPD, termos, políticas | — | ✓ | — | Reports + portar termos e LGPD |
| Super Tag | — | ✓ | — | Reports |
| JavaScript por origem | — | ✓ | ✓ (bloqueantes) | Reports |
| Acesso de robôs (robots + WAF) | — | — | ✓ | Reports |
| llms.txt, llms-full, links | — | — | ✓ | Reports |
| Sitemap com amostra e 404 em massa | — | — | ✓ | Portar a amostra |
| Dados estruturados, semântica, texto sem JS | — | — | ✓ | Reports |
| Recomendações com ganho estimado e ação | ✓ | ✓ | ✓ | Portar (somar ao revisor de IA) |
| Revisor de IA | ✓ | ✓ | ✓ | Reports |
| Quem testou, quando, histórico e evolução do domínio | ✓ | ✓ | ✓ | Portar (com `root_domain` preenchido) |
| Teste de jornada | — | ✓ | — | Portar (fase 3) |

## 11. Prints e chave da ScreenshotOne

- O cofre de integrações passa a ter **ScreenshotOne** (access key pública; secret key criptografada). O Link Tester assina cada captura com HMAC-SHA256 e guarda desktop e mobile no nosso disco.
- Antes de cadastrar, gere uma chave nova na ScreenshotOne: a atual está nas 252 URLs do PHP. Ative "Require signed requests".
- Ao migrar o histórico, baixar as imagens antigas para o nosso disco e não exibir mais as URLs com a chave.
