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

### Pendências conscientes

- **Mídia → Criativos**: não há tabela nem endpoint de criativos; a aba só entra quando o motor coletar anúncios. Canais está na Visão geral de Mídia (tabela por plataforma) para não duplicar.
- **Conteúdo como entidade própria** (relacionar manualmente com campanhas, criativos e URLs) exige tabela nova; hoje o conteúdo é a seção do site.
- **Super Tag com tabs** (Instalação, Domínios, Diagnóstico): a tela já é mestre-detalhe por site com os dois estágios; reorganizar em tabs fica para quando houver mais de uma visão por site.
- **Relatórios por categoria** (dashboards, recorrentes, exportados): o modelo de relatório não guarda tipo; os filtros atuais cobrem busca e campanha.
- **Navegação em Sankey** cliente-wide: as tabelas de caminhos cobrem a leitura; o Sankey da página continua no detalhe de cada página.

## 10. Riscos identificados

- **`main.jsx` monolítico**: mover páginas com cuidado; páginas sem mudança de comportamento ficam onde estão nesta rodada.
- **Tailwind `@source`**: classes Untitled em arquivos novos precisam de `@source` em `untitled-kit/styles/reports-kit.css`, senão não são geradas.
- **Navegação SPA x recarga**: várias páginas usam `location.assign(reportUrl(...))`; continuam funcionando (recarga), e links internos novos usam `navigate()`.
- **Sessão do cliente é única** por navegador: trocar cliente numa aba afeta as outras após recarga.
- **Monitor v2 esconde `site_pages`/`page_transitions`**: Navegação usa endpoint próprio para não depender do flag.
- **Teste `tests/frontend/reports-ui-workflows.test.cjs` já quebrado** (mocka APIs v1 antigas).
- **Artefatos gerados versionados** (`untitled.css`, bundles) — nunca commitar regenerados; o deploy roda `build:reports`.
- **Bookmarks/links externos**: cobertos pelos redirects; o Flask aceita as rotas antigas e novas.
