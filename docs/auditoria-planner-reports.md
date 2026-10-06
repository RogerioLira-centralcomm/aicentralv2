# Auditoria Planner + Reports (connect): lançamento de 11/10/2026

Auditoria somente leitura, feita em 06/10/2026 sobre `main` (e6655245d). Não alterei código, não rodei migrações e não acessei o banco. As edições não commitadas de outra sessão (chat-kit.css, cadu_identity, config.py, google_workspace) ficaram de fora. Skills aparece só como referência (`cadu_connect/routes.py:10` importa `cadu_skills.repository.customization_targets`; isso precisa continuar funcionando depois que Skills for ocultado).

## Vereditos

| Produto | Veredito | Motivo |
|---|---|---|
| **Planner** | **RISCO (pode virar bloqueador por configuração)** | Todas as gravações do Planner (criar plano, docs, alocações, monitor, Radar) passam pela trava `CADU_FAMILY_WRITES_ENABLED`, que vem desligada por padrão. Sem essa variável em produção, o Planner abre só para leitura. O isolamento por client_id está correto. A co-construção e o Radar ficam desligados e degradam bem sem as migrações. |
| **Reports (connect)** | **OK com riscos menores** | Todas as consultas passam por `reports_access.resolve()`, que valida a membership do usuário. Os escopos `shared` e `viewer` estão bem cercados. A IA passa pelo conector de créditos, com duas exceções parciais. Os scripts do Google Ads usam chave Bearer por cliente, sem Google Ads API. As falhas de teste são desatualização dos testes, não regressão. |

## Mapa

**Planner**
- Rotas: `aicentralv2/cadu_family/routes.py:592-1220`, prefixo `/familia/api/planner/*` e páginas `/familia/planner/*`. Gate de host/CSRF/escrita em `protect()`, `cadu_family/routes.py:143-203`. Comandos CLI de crawl/monitor em `cadu_family/routes.py:33-100`.
- Serviços: `aicentralv2/cadu_planner/*` (plans, docs, revisions, balance, proposals, workbench, site_monitoring, portals, portal_ads, places, link_tester, commercial) e `aicentralv2/cadu_radar/*`.
- Front: `frontend/planner` (com untitled-kit) → `npm run build:planner` → `static/cadu_planner/react/{app.js,app.css,untitled.css,monitor.js}`. O bundle existe em disco. Template: `cadu_planner/react.html`.
- Outros consumidores: `cadu_workspace/mcp/tools/planner.py`, `cadu_workspace/conversations/catalog_tools.py`, `cadu_workspace/routes.py` (docs/revisions) e `cotacoes_routes.py:775+` (pedidos comerciais).

**Reports (connect)**
- Blueprint `cadu_connect` com prefixo `/connect` (`cadu_connect/routes.py:17`). São mais de 20 módulos registrados (`routes.py:49-91`). APIs em `/connect/api/v2/reports/*`, scripts em `/connect/api/gads*`, Super Tag pública em `/connect/public/supertag/v1/*` e relatório público em `/connect/r/<token>`.
- O contrato privado v1 está aposentado (responde 410) em `routes.py:92-95`. Visitante sem sessão é redirecionado ao Workspace em `routes.py:98-108`.
- Acesso: `cadu_connect/reports_access.py` (`resolve`, escopo `shared`, `admin_scope`). Escrita: `reports_v1.py:57 _write_guard` (bloqueia viewer e exige CSRF por `X-CSRF-Token`).
- IA: `cadu_connect/reports_ai.py` é a porta única (`_authorize` → `ensure_priced` + `authorize`, depois `charge_*`).
- Front: `frontend/reports-v1` → `npm run build:reports` (vite.reports.config.mjs). Template: `cadu_connect/app_v1.html` (`reports_v1.py:237`). Scripts estáticos: `static/cadu_connect/google-ads-engine-v2.js` (Leitura) e `google-ads-actions.js` (Ações).

## Achados por severidade

### ALTA (corrigir antes de 11/10)

1. **Planner sem gravação se `CADU_FAMILY_WRITES_ENABLED` não estiver ligado em produção.** `cadu_family/routes.py:197-203` e `config.py:123` (padrão `'0'`). Cenário: o cliente abre o Planner, tenta criar um plano e recebe 403 "Migração em modo de consulta". As exceções cobrem só conversa, contexto e link-test.
   **Correção:** confirmar a variável no ambiente de produção. Se a família inteira não puder ser liberada, criar uma lista de endpoints `cadu_family.planner_*` liberados (ou a flag `CADU_PLANNER_WRITES_ENABLED`).
2. **Pré-requisitos de esquema do Planner.** `plans.get_plan` sempre seleciona `share_enabled, share_token, project_ref, brand_ref` (`cadu_planner/plans.py:110-114`), e `create_plan` grava `project_ref, brand_ref` (`plans.py:83-89`). Se a migração `add_cadu_planner_public_shares.sql` (ORDER.txt:160) não estiver aplicada, ou se a tabela for anterior às colunas `*_ref`, todo detalhe de plano falha com 503.
   **Correção:** rodar as consultas Q-P1/Q-P2 abaixo. Se falhar, aplicar as migrações na ordem de ORDER.txt.

### MÉDIA

3. **IA sem débito: análise de site do Monitor do Planner.** `cadu_planner/site_monitoring.py:106-108` chama TypeSafe `system_one` diretamente, sem `CaduCreditConnector`. A rota `cadu_family/routes.py:688-696` exige apenas `context.resolve()`, então até viewer chega a ela. Também não há limite de taxa, e cada chamada faz crawl externo (com proteção contra SSRF: `portals.py:455`).
   **Correção:** passar a chamada por `authorize`/`charge_provider` (no mesmo padrão de `revisions.py:211-234`) ou usar `writable_context()` com limite de taxa.
4. **Reports: dois pontos de IA fora de `reports_ai`.** São `report_review.py:84-110` (extração de métricas) e `reports_imports.py:1345-1360` (leitura visual de importação). Eles chamam `authorize` e `charge_provider` diretamente, mas pulam `ensure_priced`: um cliente sem preço de tokens recebe 422 depois de uma verificação que não deveria ter passado. Pior: se `charge_provider` falhar, a resposta da IA, já paga ao provedor, é descartada e o usuário vê 502 sem ter sido debitado. `reports_ai._charge` faz o contrário: registra o erro e devolve a resposta.
   **Correção:** trocar as duas chamadas por `reports_ai.chat`.
5. **Briefing de página sem CSRF nem `_write_guard`.** `reports_flow.py:1697-1712` faz uma chamada paga (`reports_flow_briefing.generate` → `reports_ai.chat`). O viewer já é barrado em `actor_for`, e `get_json` exige `application/json` (o que força preflight de CORS), então o risco de CSRF é baixo.
   **Correção:** adicionar `_write_guard(selected)` por consistência.

### BAIXA (pode esperar)

6. **Ids que não são UUID no Planner viram 503, não 404.** `plans.get_plan(..., plan_id)` passa a string direto para o SQL (`plans.py:114`), e o mesmo vale para `docs/<doc_id>` e `radar/runs/<run_id>`. O handler da família faz rollback e devolve "Não foi possível carregar…", o que gera ruído nos logs e nos alertas.
   **Correção:** usar o conversor `<uuid:plan_id>` nas rotas.
7. **Jobs de montagem (blueprint) do Reports ficam em disco e em thread no processo.** O estado fica em `instance/reports-blueprints/<client>` (`reports_flow_blueprint.py:18-30`), e o worker roda em pool dentro do processo (gunicorn com `cpu*2+1` workers). Com um único host funciona. Com mais de um host atrás do balanceador, o polling devolve 404. Se o processo reiniciar, o job fica preso em "running" até 300 s. Isso já é mitigado.
8. **`POST /connect/api/campaigns/<id>/project` sem CSRF.** `cadu_connect/routes.py:190-204` usa `session['cliente_id']` (escopo legado, não a membership do Reports). A propriedade é conferida em `repository.py:168`. O cookie é SameSite=Lax e o corpo é JSON, então o risco é baixo.
   **Correção:** exigir `X-CSRF-Token`, ou aposentar a rota se o front v1 não a usa.
9. **A11y do front Reports.** Há 57 `<div|span onClick>` em `frontend/reports-v1` (4 no Planner) sem papel de botão nem teclado. Não há `console.log` nos dois bundles.
10. **Textos de moeda/tokens.** O Reports mistura "Créditos", "créditos", "Tokens" e "tokens" na UI (mais de 30 ocorrências). Os Planner/Radar mostram "tokens" estimados (`/radar/estimate`, `/briefing-review/estimate`). Alinhar com a decisão da cobrança em tokens reais.
11. **Fila de Ações do Google Ads:** um resultado `simulated` volta para `approved` (`reports_google_ads_actions.py:362-366`) e é oferecido de novo a cada execução até `expires_at`. Isso está correto para o modo de prévia, mas convém mostrar "simulado N vezes" na UI. A arquitetura respeita a regra de não usar a Google Ads API: o script puxa comandos aprovados com chave Bearer escopada (`_script_scope`, `_authorize_scope`).

### Pontos verificados e corretos

- O isolamento por cliente no Planner funciona assim: todas as rotas usam `context.resolve()` e as consultas filtram `client_id` (por exemplo, `plans.py:58-64` e `plans.py:110-114`). `_planner_refs` valida marca e projeto contra o inventário do cliente (`cadu_family/routes.py:784-792`). As mutações usam `writable_context()` (admin ou member) mais CSRF.
- O isolamento no Reports funciona assim: `resolve()` só aceita um client_id presente em `cadu_reports_client_memberships` ativo. O escopo `shared` só alcança journey/live/previews dos fluxos com grant. A revogação apaga os grants. Todas as rotas mutáveis examinadas chamam `_write_guard` ou `admin_scope`. As exceções são as rotas públicas por token, os scripts com chave e as rotas 410.
- Proteção contra SSRF: tester de links (`reports_link_tester.py:42-45`), capturas de página (`reports_page_captures.py:170-173`, sem redirect e com limite de bytes), probe (`reports_flow_probe.py:486`) e portais do Planner.
- Débito de créditos já correto em: revisão de briefing/doc do Planner (`revisions.py`), Radar (`cadu_radar/pipeline.py:86-102`), todo o `reports_ai` (chat, typesafe, firecrawl), negativas do Google Ads, agentes de relatório e classificação de páginas no blueprint (`reports_flow_suggestions.suggest` herda `actor_id`).
- Co-construção e Radar sem migração: `proposals.available()` e `radar.available()` retornam vazio, sem 500. A flag `CADU_PLANNER_COBUILD_ENABLED` e `CADU_RADAR_ENABLED` vêm desligadas (`config.py:126-127`).
- As consultas de listagem têm LIMIT (planos 100, alertas 200, eventos 100).

## Migrações

| Migração | Lançamento exige? |
|---|---|
| `add_cadu_planner_plans`, `channel_allocations`, `client_flow`, `review_history`, `docs_compat` (ORDER 103-107) | **Sim** (base do Planner) |
| `add_cadu_planner_public_shares.sql` (ORDER 160) | **Sim**: `get_plan` lê `share_enabled`/`share_token` |
| `add_cadu_planner_cobuild.sql`, `add_cadu_radar.sql` (ORDER 161-162) | **Não**: o recurso fica desligado e degrada bem. Só aplicar se o lançamento incluir co-construção ou Radar (e, nesse caso, ligar as flags) |
| `add_cadu_planner_site_monitoring.sql` (ORDER 167) | Sim, se o Monitor fizer parte do lançamento |
| Reports v2: `add_reports_flow_page_identity_m2` + backfill, `flow_ownership`, `plan_versions`, `plan_only`, `templates`, `probe_runs`, `site_pages`, `published_versions`, `custom_metrics`, `google_ads_engine_v2/v22`, `supertag_leads`, `enhanced_events`, `google_ads_actions`, `alerts_v1`, `supertag_site_customer`, `add_cadu_connect_accounts` | **Sim** (sem `cadu_reports_client_memberships` o Reports inteiro responde 503: `reports_access.py:24-26`) |
| `add_reports_google_ads_history_goals.sql` | Aplicada pelo próprio app (NOT_IN_DEPLOY) |
| `reset_reports_client_scope_v2.sql` | **NÃO rodar** (destrutiva) |

## SELECTs somente leitura para validar produção

```sql
-- Q-P1 tabelas do Planner/Radar
SELECT t, to_regclass('public.'||t) IS NOT NULL AS existe FROM unnest(ARRAY[
 'cadu_planner_plans','cadu_planner_plan_items','cadu_planner_channel_allocations','cadu_planner_quote_requests',
 'cadu_planner_user_notifications','cadu_planner_proposals','cadu_radar_opportunities','cadu_radar_runs',
 'cadu_planner_link_test_runs']) t;
-- Q-P2 colunas exigidas por get_plan/create_plan e da co-construção
SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='cadu_planner_plans'
 AND column_name IN ('share_enabled','share_token','project_ref','brand_ref','archived_at','revision','workbench','source','opportunity_id');
-- Q-P3 isolamento: itens órfãos ou de plano arquivado
SELECT COUNT(*) FROM cadu_planner_plan_items i LEFT JOIN cadu_planner_plans p ON p.id=i.plan_id WHERE p.id IS NULL;
-- Q-R1 base do Reports
SELECT t, to_regclass('public.'||t) IS NOT NULL FROM unnest(ARRAY['cadu_reports_client_memberships','cadu_reports_flow_registry',
 'cadu_reports_flow_grants','cadu_reports_site_grants','cadu_reports_alerts','cadu_reports_gads_actions','cadu_reports_gads_action_agents',
 'cadu_reports_ingest_keys','cadu_reports_import_visual_runs','cadu_connect_report_public_links','cadu_reports_customers']) t;
SELECT * FROM cadu_reports_schema_version;
-- Q-R2 clientes sem admin ativo (ninguém consegue gerir acessos)
SELECT client_id FROM cadu_reports_client_memberships GROUP BY client_id
 HAVING COUNT(*) FILTER (WHERE role='admin' AND revoked_at IS NULL AND access_scope='all')=0;
-- Q-R3 grants de recurso de usuários revogados (deveriam ser 0)
SELECT g.client_id,g.user_id FROM cadu_reports_flow_grants g JOIN cadu_reports_client_memberships m
 ON m.client_id=g.client_id AND m.user_id=g.user_id WHERE m.revoked_at IS NOT NULL;
-- Q-R4 fila de Ações presa
SELECT status,COUNT(*),MIN(created_at) FROM cadu_reports_gads_actions WHERE expires_at>NOW() GROUP BY status;
-- Q-C1 clientes com Reports/Planner sem preço de token (IA ficaria 409)
SELECT m.client_id FROM (SELECT DISTINCT client_id FROM cadu_reports_client_memberships WHERE revoked_at IS NULL) m;
--   cruzar com a fonte de preço usada por CaduCreditConnector.ensure_priced (cadu_credit_connector.py)
```

## Testes (com DB_HOST=127.0.0.1 DB_PORT=1)

- pytest (planner, report, connect, radar, google_ads): **962 passaram e 28 falharam**. Todas as falhas são desatualização dos testes, não regressão de produto:
  - `test_connect_report_workspace.py` (10): o teste faz patch de `report_workspace.context`, que não existe mais (o módulo virou redirecionador legado).
  - `test_planner_hero_backgrounds.py` (12): espera 200 para visitante, mas o produto agora redireciona (302) ao Workspace, de propósito.
  - `test_reports_alerts.py` (3): o mock não cobre `reports_access.resolve` e o teste tenta abrir o banco, daí o 500. Em produção, `_alert_for` (`reports_alerts.py:211-215`) devolve 404 para um id que não é UUID.
  - `test_smart_planner_history.py` (2) e `test_smart_planner_mix.py` (1): dependem da data (mês "2026-09" fixo) e pertencem ao smart_planner interno, não a este produto.
- node --test (report*/reports-*): **65 passaram e 8 falharam**:
  - `reports-flow-validation-parity` não carrega porque `flowValidation.js` passou a importar `./flowGoals.js` (o teste carrega o arquivo isolado como data URL).
  - `reports-ui-workflows` (4) e `reports-flow-strategies` (2) verificam o texto do código-fonte, que mudou.
  - Não há testes de front do Planner.

## Telas

Não abri as telas ao vivo: elas exigem sessão e banco, e o `.env` aponta para produção. Usei as capturas que já estão no repositório: `output/reports-workspace-qa/page-*.png` e `page-*-mobile.png` (overview, campanhas, imports, monitor, supertag, acessos, clientes, contas, eventos, links, relatórios) e `monitor-{1024..1920}.png`. Elas mostram as versões desktop e mobile das páginas principais do Reports. A conferência de console e a11y foi feita por análise estática (achados 9 e 10). Planner: só o código e o bundle buildado `static/cadu_planner/react/`.

## Corrigir antes de 11/10 vs pode esperar

**Antes de 11/10:** item 1 (variável de escrita do Planner em produção), item 2 (rodar Q-P1/Q-P2/Q-R1 e aplicar as migrações base que faltarem), item 3 (débito ou trava no analyze do Monitor, se o Monitor for lançado) e item 4 (unificar a IA do Reports em `reports_ai`).

**Pode esperar:** itens 5 a 11, a atualização dos testes desatualizados e a decisão sobre co-construção e Radar (seguem desligados).
