# Cadu Reports — plano de refatoração de arquitetura e navegação

Data: 2026-10-02 · Escopo desta rodada: Fase 1 (shell, sidebar, contexto, rotas, tabs) + Visão geral + hubs Mídia e Site & Jornada.

Modelo mental: **Conectar → Coletar → Medir → Entender → Agir**. Quatro camadas: Dados, Mídia, Site & Jornada, Análise.

---

## 1. Estrutura atual encontrada

| Camada | Onde vive |
|---|---|
| SPA | `frontend/reports-v1/` (React 18, Vite) → bundle em `aicentralv2/static/cadu_connect/react/` (`app.js`, `app.css`, `untitled.css`) |
| Shell HTML | `aicentralv2/templates/cadu_connect/app_v1.html` (root `#cadu-reports-v1-root` com data-attributes de URLs e usuário) |
| Rota Flask do SPA | `reports_v1_app` em `aicentralv2/cadu_connect/reports_v1.py:134` — lista fixa de seções, 404 para o resto |
| APIs | `/connect/api/v2/reports/*` em `aicentralv2/cadu_connect/reports_*.py` |
| Design system | `frontend/cadu-design-system/` (wrappers `Cadu*`, `SolutionSidebar`) + kit Untitled em `cadu-design-system/untitled-kit/` (button, input, textarea, native-select, modal, tabs) |

Problemas:

- **Sem roteador**: `App` (`main.jsx`) lê `location.pathname` e escolhe a página num ternário único; toda troca de página é recarga completa.
- **Arquivo gigante**: `main.jsx` tem ~1.600 linhas / ~197 KB com ~20 páginas dentro.
- **Títulos duplicados**: o header do shell (`ReportsPageHeader`, `PageChrome.jsx`) mostra o `h1` da página e quase todas as páginas repetem um hero (`.reports-page-hero`, 28–38px, gradiente) com o mesmo `h1` (Visão geral, Contas, Campanhas, Relatórios, Importações, Dados de mídia, Link Tester, Acessos, Eventos).
- **CSS de header em camadas**: `.reports-page-header` é redefinido em `styles.css:295, 565, 748, 833` e `reports-refinement.css:28, 144`.
- **Troca de cliente**: o seletor recarrega e manda o usuário para a Visão geral, perdendo a página.
- **Período**: estado em memória por página (`filtersByPage`), fora da URL; Páginas e Monitor de fluxo guardam `?days` próprios.
- **Sidebar com 14 itens** no mesmo nível, misturando entidades, ferramentas, fontes e configuração.

## 2. Rotas atuais

`/connect/app/<seção>`: `overview`, `customers`, `accounts` (`?view=management`), `campaigns` (`?campaign_id=&campaign_tab=`), `reports`, `imports`, `data-library` (alias de imports), `monitor`, `supertag` (+ `/supertag/sites/<uuid>`), `flows`/`flow` (+ `/flows/<uuid>`, `/flows/<uuid>/monitor`, `/flows/new`, `?flow_view=monitor|create`), `pages` (`?site_id=&path=`), `alerts`, `events`, `conversions` (alias de events), `links`, `access`. Hashes legados `#secao?…` redirecionam.

## 3. Componentes atuais

| Componente | Arquivo | Avaliação |
|---|---|---|
| `Overview`, `OverviewSetup` | `main.jsx` | Só mídia (3 KPIs, gráfico, tabela). Onboarding "Próxima ação" é bom e fica |
| `ReportsCustomers` | `ReportsCustomers.jsx` | CRUD básico |
| `Accounts`, `AccountsManagementView` | `main.jsx` | Básico; visão 3 colunas de gestão |
| `Campaigns`, `CampaignDetail` | `main.jsx` | Lista básica; detalhe rico (11 abas, "Mapa de calor" placeholder) |
| `Reports` | `main.jsx` | Rico (workspace de relatório com IA e publicação) |
| `Imports` | `main.jsx` | Rico (upload, mapeamento por IA, conflitos) |
| `Monitor` (Dados de mídia) | `main.jsx` | Configuração de fontes (script/webhook, chaves, envios) |
| `SuperTag` + `SuperTagParts.jsx` | `main.jsx` | Rico, 2 estágios |
| `Flow` / `FlowsIndex` / editor / `FlowMonitorWorkspace` / galeria | `FlowsPage.jsx` e afins | Muito rico — **preservar** |
| `PageDetail` / `DomainsOverview` | `PageDetail.jsx`, `DomainsOverview.jsx` | Muito rico |
| `AlertsCenter` | `AlertsCenter.jsx` | Completo |
| `Events` | `main.jsx` | Médio |
| `Links` | `main.jsx` | Médio-completo |
| `Access` | `main.jsx` | Básico e completo |
| Compartilhados | `reportsCommon.jsx` (`json`, `reportUrl`, `Empty`, `Kpi`), `PageChrome.jsx`, `ReportsDateRange.jsx`, `friendlyDates.js`, adapters `Reports*` | Reaproveitar |

## 4. Endpoints utilizados (principais)

- `GET /bootstrap` — cliente, clientes, contas, campanhas, relatórios, link tests, clientes/anunciantes.
- Mídia: `/metrics` (inclui `by_platform`, nunca exibido), `/import-metrics`, `/campaigns/<id>`, `/ingest-keys`.
- Site: `/supertag/sites`, `/supertag/sites/<id>/events`, `/pages/domains`, `/pages/overview|interactions|conversion-map|suggestions`.
- Jornada: `/flow?view=create|edit|monitor` (monitor traz `site_pages` e `page_transitions`), `/flow/flows/<id>/journey|live`, `/flow/events`.
- Análise: `/alerts`, `/workspaces/*`.
- Dados: `/imports/*`, `/import-ranges`, `/import-conflicts`.

Dados existentes e sem tela: `metrics.by_platform`, `site_pages`/`page_transitions` (escondidos quando o monitor v2 está ligado), catálogo `/flow/sites/<host>/catalog`, tabelas `cadu_reports_gads_*` (ad group, device, keyword, search term) e `cadu_reports_external_conversions` sem listagem.

## 5. Páginas preservadas (comportamento intacto, só ganham header único)

Fluxos (lista, editor, monitor, galeria), Páginas (domínios e detalhe), Super Tag, Alertas, Relatórios, Importações, Link Tester, Acessos, Clientes, Contas, detalhe de Campanha.

## 6. Páginas movidas

| De | Para |
|---|---|
| Campanhas | Mídia → Campanhas |
| Dados de mídia | Mídia → Dados |
| Fluxos | Site & Jornada → Fluxos |
| Páginas | Site & Jornada → Páginas |
| Conversões (alias de Eventos) | Site & Jornada → Conversões |
| Clientes e anunciantes | Configurações → Clientes |
| Contas | Configurações → Contas e conexões |
| Acessos | Configurações → Acessos |
| Link Tester | Ferramentas → Link Tester |
| Biblioteca de dados | Importações (`?view=library`) |

Páginas novas: Mídia (visão geral), Site & Jornada (visão geral), Navegação, Conversões, Fontes de dados (índice das fontes existentes).

## 7. Redirects necessários (client-side, `replaceState`, preservando query)

| Antiga | Nova |
|---|---|
| `/connect/app/campaigns[?campaign_id=X]` | `/connect/app/media/campaigns[/X]` |
| `/connect/app/monitor` | `/connect/app/media/data` |
| `/connect/app/pages` | `/connect/app/journey/pages` |
| `/connect/app/flows`, `/connect/app/flow` | `/connect/app/journey/flows` |
| `/connect/app/conversions` | `/connect/app/journey/conversions` |
| `/connect/app/customers` | `/connect/app/settings/clients` |
| `/connect/app/accounts` | `/connect/app/settings/accounts` |
| `/connect/app/access` | `/connect/app/settings/access` |
| `/connect/app/links` | `/connect/app/tools/link-tester` |
| `/connect/app/data-library` | `/connect/app/imports?view=library` |
| `#secao?…` | regra atual mantida, agora para a rota nova |

Mantidos sem mudança: `/connect/app/flows/<uuid>`, `/flows/<uuid>/monitor`, `/flows/new` (editor tem layout próprio, links já compartilhados), `/connect/app/supertag/sites/<uuid>`. `reportUrl()` passa a gerar sempre o caminho novo, então todos os links internos e e-mails (`reports_alerts.py` usa `/connect/app/alerts`, que não muda) continuam válidos.

## 8. Componentes novos (`frontend/reports-v1/shell/`)

- `routes.js` — tabela de rotas (path, hub, tab, título, pergunta), `resolveRoute()`, `legacyRedirect()`, `navigate()`, `useRoute()`, `ReportsLink`.
- `ReportsContext.jsx` — cliente + período globais; período na URL (`?period=30d` ou `?start=&end=`).
- `ReportsShell` (no `main.jsx`) — sidebar + header + conteúdo.
- `PageHeader` — **único h1** da página (20px, descrição de 1 linha, ações à direita, breadcrumb só no nível 3).
- `ContextSelector` — cliente e período no header.
- `SectionTabs` — tabs de nível 2 com links reais.
- `primitives.jsx` — `MetricGroup`, `Section`, `DataTable`, `LoadingState`, `EmptyState`, `ErrorState`.
- Hubs: `hubs/overview`, `hubs/media`, `hubs/journey`, `hubs/data-sources`.

Untitled UI: botões, tabs, modal e campos vêm do kit via wrappers existentes; sem shadcn, sem nova lib.

## 9. Plano de migração e estado

| Fase | Entrega | Estado |
|---|---|---|
| 1 | Shell, sidebar por áreas, rotas + redirects, contexto (cliente/período), cabeçalho único, tabs | Feito |
| 2 | Visão geral (resumo, mídia, site, alertas, saúde dos dados); Mídia: Visão geral, Campanhas, Dados | Feito |
| 3 | Site & Jornada: Visão geral, Fluxos (sem mudança de motor), Páginas (lista + detalhe), Navegação, Conversões | Feito |
| 4 | Conteúdos (seções do site com alcance, influência na conversão e campanhas pagas que levam até lá); Mídia → Desempenho (grupos, palavras-chave, termos, páginas de destino, dispositivos, configuração das campanhas) | Feito |
| 5 | Fontes de dados (Mídia, Site, Arquivos, Negócio com status e atualização); Eventos com detalhe em painel lateral; Super Tag e Importações na camada Dados | Feito |
| 6 | Relatórios com busca e filtro por campanha; Alertas ligados aos objetos (página, navegação, coleta do site); Link Tester em Ferramentas; Clientes, Contas e conexões e Acessos em Configurações | Feito |

Endpoints novos: `GET /journey/navigation`, `GET /journey/conversions`, `GET /journey/content`, `GET /media/performance` (todos sobre tabelas já existentes; nenhuma migração).

Correções de organização feitas no caminho: detalhe de campanha usava `.reports-span-four` sem definição (cabeçalho e abas presos numa célula da grade) e um card envolvendo os cards; aba "Mapa de calor" (placeholder) escondida; CSS dos heroes removido.

### Criativos e pendências resolvidas

- **Mídia → Criativos** (`GET /creatives/campaigns/<id>`, `POST /creatives/studio`, `GET /creatives/sessions` em `reports_creatives.py`): o briefing nasce dos dados da campanha (buscas que converteram, página de destino, CTR e conversões dos últimos 30 dias, objetivo), com formato e ângulo escolhidos. "Abrir no Studio" cria uma sessão retomável pelo mesmo `start_studio_session` do agente do Workspace, com a marca Studio (`studio:<id>`) e o projeto do Workspace (`ci:<uuid>`). Marca e projeto vêm por padrão do projeto da campanha → marca vinculada ao projeto → marca do cliente/anunciante. O Reports não gera imagem nem consome créditos; direção, geração e cobrança ficam no Studio. As sessões ganham `metadata.origin='cadu_reports'` e o histórico aparece na própria aba, com a imagem mais recente.
- **Studio respeita o projeto e a marca do link** (`static/js/mc-cadu-nav.js`): `/criar?project_id=` (UUID do Workspace ou id do projeto Studio) seleciona o projeto; só com `creative_client_id`, seleciona o projeto da marca quando ele é único. Antes o parâmetro era ignorado e a criação caía em "Criação rápida", sem as referências da marca — isso também corrige os links que o Workspace já enviava.
- **Navegação em Sankey**: os 10 caminhos mais comuns aparecem como fluxo entre páginas, acima da tabela.
- **Relatórios**: situação Publicado (link público ativo) ou Em edição, com contagem, além de busca e campanha.

### Mídia → Google Ads (antes "Desempenho")

Área própria para o Google Ads, porque os dados do motor v2 são específicos da plataforma. `/connect/app/media/performance` redireciona para `/media/google-ads`.

- **Resumo e ações**: investimento, conversões, CPA, valor/ROAS e cliques contra o período anterior; **ações recomendadas em ordem de execução** (o que trava a conta primeiro, depois maior impacto em R$), cada uma com objeto, números, ação concreta e link para a visão certa; investimento e conversões por dia; saúde da coleta por conta (última execução, conjuntos cortados ou com erro).
- **Termos de pesquisa**: cada termo com a ação (Negativar, Virar palavra-chave, Revisar, Já negativado, Excluído, Manter) decidida em `term_action`; seleção e **exportação CSV para o Google Ads Editor** (negativas de campanha exata ou de frase; palavras-chave exatas por grupo) e cópia em notação `[exata]`/`"frase"`.
- **Palavras-chave**: Índice de Qualidade colorido, custo, conversões, CPA, CTR, CPC.
- **Palavras negativas**: inventário por nível (campanha, grupo, lista compartilhada com campanhas vinculadas), conflitos com palavras-chave ativas, removidas nos últimos 30 dias.
- **Campanhas**: estratégia de lance, orçamento diário, uso do orçamento, resultado do período.
- **Grupos, páginas e dispositivos**: detalhe que já existia.
- **Regras** (`reports_google_ads_rules.py`, limites visíveis em "Como decidimos"): script parado (>48 h), negativa bloqueando palavra-chave ativa, coleta incompleta, termo para negativar (≥10 cliques, 0 conversão, não coberto), palavra-chave com gasto sem conversão (≥30 cliques), campanha sem conversão, campanha que converte limitada pelo orçamento (≥95% do orçamento com CPA ≤ conta), termo que converte para virar palavra-chave (≥2 conversões), Índice de Qualidade ≤4, dispositivo com CPA ≥2× a conta, negativas desatualizadas (>7 dias — termos para negativar não são sugeridos sem elas).
- **Alertas**: as ações de prioridade alta e média aparecem no topo da central de Alertas, com link para o objeto no Google Ads.
- Endpoints: `GET /google-ads/summary`, `/google-ads/search-terms`, `/google-ads/keywords`, `/google-ads/negatives`.

**Histórico, comparação e metas (script 2.1)**

- **Histórico permanente**: as linhas diárias nunca são apagadas. O script 2.1 pede ao Reports um plano de datas (`GET /api/v1/reports/ingest/google-ads/v2/plan`): relê os últimos 14 dias (conversões atrasadas) e busca mais 45 dias do passado por execução, até 13 meses. O plano avança mesmo quando uma fatia antiga vem vazia (usa a janela registrada no resumo da execução). Os lotes de faixas diferentes seguem numerados para não colidir na idempotência.
- **Configuração com histórico**: CPA e ROAS desejados lidos do Google Ads (com queda para a consulta antiga se a API recusar os campos) e `cadu_reports_gads_campaign_settings_history` com cada mudança de status, lance, orçamento e metas.
- **Comparação**: período anterior ou mesmo período do ano anterior, nos KPIs (CPA com sentido invertido), nos gráficos (série comparada alinhada por dia) e por campanha.
- **Metas da equipe** (`cadu_reports_campaign_goals`, `PUT /google-ads/goals/<campaign_id>`): objetivo, teto mensal e total, período, CPA, ROAS e conversões por mês. Ritmo do mês: gasto até hoje + média dos últimos 7 dias × dias restantes.
- **Próximos passos de meta**: teto atingido, campanha gastando após o fim, ritmo que estoura o teto (com o orçamento diário que fecha no teto), CPA/ROAS fora da meta, meta de conversões em risco, orçamento sobrando com CPA dentro da meta, CPA desejado no Google diferente da meta da equipe.
- **"Como funciona"** em Mídia → Dados: modal para operadores de Google Ads com as etapas, todas as extrações, as regras, segurança e limites.
- **Aplicar**: `python migrations/run_sql_migration.py add_reports_google_ads_history_goals.sql` e gerar/reinstalar o script (versão 2.1.0) nas contas.

**Meta e demais plataformas** terão áreas separadas, alimentadas por prints e, no futuro, por extensão do Chrome; não entram na área Google Ads.

**Limites do script hoje** (registrados para a próxima versão do motor): não coleta ações de conversão separadas, parcela de impressões, anúncios/RSA, recursos, geografia, horário, públicos nem negativas de conta e de Performance Max; envia os últimos 8 dias a cada execução.

### Pendências que dependem de modelo novo

- **Criativos com desempenho por anúncio**: o motor Google Ads não coleta anúncios; quando coletar, a aba ganha a tabela de peças e o botão passa a partir da peça vencedora.
- **Conteúdo como entidade própria** (ligar manualmente a campanhas, criativos e URLs) exige tabela nova; hoje o conteúdo é a seção do site.
- **Relatórios por tipo** (dashboard, recorrente, exportado) exige guardar o tipo no relatório.
- **Super Tag com tabs** (Instalação, Domínios, Diagnóstico): a tela já é mestre-detalhe por site com os dois estágios.

## 10. Riscos identificados

- **`main.jsx` monolítico**: mover páginas com cuidado; páginas sem mudança de comportamento ficam onde estão nesta rodada.
- **Tailwind `@source`**: classes Untitled em arquivos novos precisam de `@source` em `untitled-kit/styles/reports-kit.css`, senão não são geradas.
- **Navegação SPA x recarga**: várias páginas usam `location.assign(reportUrl(...))`; continuam funcionando (recarga), e links internos novos usam `navigate()`.
- **Sessão do cliente é única** por navegador: trocar cliente numa aba afeta as outras após recarga.
- **Monitor v2 esconde `site_pages`/`page_transitions`**: Navegação usa endpoint próprio para não depender do flag.
- **Teste `tests/frontend/reports-ui-workflows.test.cjs` já quebrado** (mocka APIs v1 antigas).
- **Artefatos gerados versionados** (`untitled.css`, bundles) — nunca commitar regenerados; o deploy roda `build:reports`.
- **Bookmarks/links externos**: cobertos pelos redirects; o Flask aceita as rotas antigas e novas.
