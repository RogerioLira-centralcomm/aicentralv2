# Plano — Conta: Planos, Créditos, Uso e Faturamento

Data: 2026-10-06 · Lançamento: 2026-10-11 (5 dias) · Status: investigação concluída, nada implementado.

Escopo: telas `/plano`, `/uso`, `/creditos`, `/faturas` do Workspace (`frontend/cadu-design-system/components/WorkspaceAccount.jsx`) e todo o backend/banco que as alimenta.

---

## 0. Decisões do dono (2026-10-06)

Estas decisões respondem ao §8 e prevalecem sobre as propostas abaixo quando divergirem.

1. **Franquia mensal automática**: liberada a cada ciclo, sem ação manual.
2. **Modelo telefonia**: ao entrar a franquia do novo ciclo, a sobra da anterior **expira**. Pacotes extras **não expiram** (substitui a validade de 12 meses proposta no §1 e no §4.3).
3. **Ordem de débito**: franquia do plano primeiro, depois extras.
4. **Unidade única "tokens"** em toda a interface (com singular/plural). Venda com margem 4x–7x sobre o custo; custo interno nunca aparece na UI.
5. **Sem créditos de imagem**: imagem consome tokens; "créditos de imagem" sai da UI e do catálogo exibido.
6. **Planos Essencial / Equipe / Agência (R$ 297 / 697 / 1.497)** podem ser criados. Franquias de tokens e GB **não** são inventadas: ficam como dados configuráveis no catálogo (vazio ⇒ a UI mostra "Consulte").
7. **Pessoas ilimitadas em todos os planos.** Armazenamento: GB incluído por plano + GB extra como pacote (Vultr Object Storage); custos/GB vêm do catálogo, nunca do código.
8. **Beta Tester** aparece para todos com nome comercial **"Acesso antecipado"** (chave interna `beta_tester` mantida).
9. **Avisos de compra** para apolo@, financeiro@ e alexandre@centralcomm.media (configurável por `CADU_FINANCE_EMAILS`). Faturas são lançadas **manualmente** pelo financeiro; não há cobrança automática. A tela de Faturamento explica isso e lista pedidos de pacote como **solicitações**, não como faturas.
10. **Interpretação registrada** ("o pacote é renovado todo mês"): renova todo mês a **franquia do plano**; pacotes extras não têm validade. Pendente de confirmação do dono.
11. **Qualquer membro** pode comprar pacote pelo Workspace (o endpoint web já não exige admin; o MCP continua exigindo — alinhar depois).

**Ajustes de fases/riscos decorrentes:**
- Fase 3 (franquia como lote) vai atrás da chave `CADU_PLAN_ALLOWANCE_ENABLED` (default desligada); nada muda em produção até o dono ligar e preencher as franquias.
- Lote de franquia: `expires_at = fim do ciclo`; extras: `expires_at = NULL`. Com a ordenação atual do ledger (`expires_at NULLS LAST`), a franquia é debitada primeiro sem mudar a regra de débito.
- Fatura automática de pacote (fase 5) sai do escopo: só registro do pedido + aviso por e-mail + listagem como solicitação.
- Migrações novas ficam como `.sql` idempotentes **não registradas** em `ORDER.txt` até Q1–Q8 serem rodadas em produção.
- Risco novo: ao ligar a franquia, todos os clientes ativos ganham saldo no mesmo dia — ligar só depois de preencher `tokens_monthly` por plano e combinar com o financeiro.

---

## 1. Modelo conceitual correto

Hoje o sistema só tem **um** saldo efetivo: os lotes de `cadu_credits_extras`. A "franquia mensal do plano" existe apenas como número no catálogo e nunca é concedida, debitada nem zerada. O modelo-alvo:

| Conceito | O que é | Onde vive (alvo) | Expira | Reset |
|---|---|---|---|---|
| **Plano** | Contrato da organização (Free, Pro, Enterprise, Beta Tester) com preço mensal, limites e recursos | `cadu_plan_definitions` (catálogo) + `cadu_client_plans` (assinatura ativa) | Fim da vigência (`valid_until`) | — |
| **Franquia mensal** | Tokens Cadu incluídos no plano a cada ciclo (Free 100 mil, Pro 2 mi, Enterprise 10 mi) | Um lote em `cadu_credits_extras` com `source='plan_allowance'`, `cycle_start/cycle_end`, criado por ciclo | No fim do ciclo (não acumula) | Novo lote no início de cada ciclo |
| **Créditos avulsos** | Pacotes comprados (Extra Essencial / Equipe / Agência) e bônus (lançamento, testes) | Lotes em `cadu_credits_extras` com `source='purchase'` ou `'bonus'` | 12 meses após a compra (bônus: conforme regra) | Não zera |
| **Consumo** | Cada execução cobrada de IA | `cadu_tools_token_usage` (uma linha por cobrança, com `metadata.allocations` indicando de qual lote saiu) | — | — |
| **Cobrança** | O que o financeiro cobra (mensalidade do plano e pacotes) | `cadu_invoices` (fatura) ligada a `cadu_credit_requests` (pedido de pacote) ou à assinatura | — | — |

**Regra de débito (proposta):** primeiro a franquia do ciclo (vence primeiro), depois bônus, depois avulsos pelo vencimento mais próximo. O conector já ordena por `expires_at NULLS LAST, purchased_at, id` (`aicentralv2/cadu_credit_connector.py:250-258`); se o lote de franquia tiver `expires_at = cycle_end`, a ordem sai certa **sem mudar o conector**.

**Ciclo:** mensal, ancorado em `valid_from` do plano (ou dia 1 — decisão do usuário, ver §8). Tokens de franquia não usados não acumulam.

**Unidade:** uma só, "tokens Cadu". A UI hoje mistura "créditos" e "tokens" para a mesma coisa (pacote de "100.000 créditos" debita 100.000 tokens). Decidir um nome (§8) e usar em todas as telas.

---

## 2. Diagnóstico com evidências

### 2.1 Fluxo de dados real de cada tela

Entrada única: `account_page` em `aicentralv2/cadu_workspace/routes.py:9697`. Lê `_php_account_data(client_id, _ACCOUNT_SECTION_NEEDS[section])` (`routes.py:237-245`, `249-415`) e serializa via `_account_public_view` (`routes.py:~9770`) para `account_react.html`.

| Tela | Número exibido | Origem real |
|---|---|---|
| Planos | lista de planos | `db.obter_plan_definitions(apenas_ativos=True)` → `SELECT * FROM cadu_plan_definitions WHERE is_active` (`db.py:4649`; chamada em `routes.py:9738-9743`) |
| Planos | plano atual | `db.obter_planos_clientes` (`db.py:4664`) → `cadu_client_plans` + `cadu_plan_definitions` |
| Planos | preço/CTA | `price_monthly` do catálogo; CTA "Ver contratação" só se `plan_type in ('pro','enterprise')` (`WorkspaceAccount.jsx:130`), senão "Consulte a equipe" (`:145`) |
| Créditos | Saldo | `credit_position` (`cadu_skills/repository.py:330`) → soma de `cadu_credits_extras` ativos |
| Créditos | Lotes ativos | `purchases` = `cadu_credits_extras` ativos, todos rotulados "Lote de créditos" (`routes.py:306-325`) |
| Créditos | Último consumo | `movements[0]` = última linha **bruta** de `cadu_tools_token_usage` (`routes.py:288-303`; `WorkspaceAccount.jsx:64,165`) |
| Créditos | Pacotes e preços | **hardcoded no JSX** (`WorkspaceAccount.jsx:163`), e de novo em `routes.py:46-61` e em `credit_purchase_service.py:16-20` (3 cópias) |
| Uso | Tokens neste ciclo | `insights.tokens` ← `cadu_client_plans.tokens_used_current_month` (`routes.py:388`) |
| Uso | Interações recentes | `groupCommercialActivity(movements)` — agrupamento das 20 últimas linhas de `cadu_tools_token_usage` (`WorkspaceAccount.jsx:35,154`) |
| Uso | Créditos adicionados | todos os lotes de `cadu_credits_extras` (`routes.py:327-341`) |
| Uso | Espaço | `cadu_ci_projetos` + `cadu_ci_projeto_arquivos` (`routes.py:343-355`) |
| Faturamento | faturas | `_workspace_billing_data` (`routes.py:456`) → `db.obter_invoices` → `cadu_invoices` (`db.py:5440`) |
| Compra | botão "Confirmar compra" | `POST /workspace/api/creditos/solicitar` (`routes.py:1243`) → insere `cadu_credit_requests` (status `approved`) + lote em `cadu_credits_extras` + e-mail ao financeiro |

### 2.2 "Tokens neste ciclo: 0 de 2.000.000" — causa raiz

- O número usado vem de `cadu_client_plans.tokens_used_current_month` (`routes.py:388`).
- **Nenhum fluxo de IA escreve essa coluna.** O único escritor é `db.atualizar_consumo_tokens` (`db.py:5098`), chamado em um só lugar, com `tokens=0, imagens=1` (`aicentralv2/routes.py:4950`, contador de imagens de audiência; e esse trecho lê `plano['id_plan']` de `SELECT id_plan FROM cadu_client_plans`, coluna que o repo cria como `id` — provável erro silencioso engolido pelo `except`).
- Todo consumo real passa pelo `CaduCreditConnector` / `ToolTokenLedger`, que grava `cadu_tools_token_usage` e debita `cadu_credits_extras.tokens_used` (`cadu_credit_connector.py:213-284`, `cadu_tool_billing.py:180+`). Nunca toca `cadu_client_plans`.
- O limite 2.000.000 vem de `pd_tokens_monthly_limit` (catálogo Pro), mas essa franquia **nunca vira saldo**: `credit_position` soma só lotes (`repository.py:340-350`); `"monthly"` é na verdade o total dos lotes (comentário em `repository.py:362-364`).
- Reproduzido localmente (função pura): `_workspace_account_insights({'pd_tokens_monthly_limit':2000000,'tokens_used_current_month':0}, {'used':180000,...}, ...)` → `tokens.used = 0`, independentemente do consumo.
- Também `resetar_contadores_mensais` (`db.py:5127`) não tem chamador/cron.

Conclusão: duas fontes de verdade para "uso" (contador legado no plano, morto; ledger de lotes, vivo). A tela lê a morta.

### 2.3 "Último consumo: 1 créditos"

- Mostra `tokens_cobrados` da linha mais recente de `cadu_tools_token_usage`, sem agrupar por execução. Cobranças mínimas existem: RAG usa `max(1, ceil(raw*margem))` (`repository.py:388`); mídia arredonda para cima (`cadu_tool_billing.py:57`); uma execução vira várias linhas por etapa.
- Erros: (a) unidade "créditos" para tokens; (b) etapa isolada em vez da interação; (c) plural não tratado ("1 créditos").
- Confirmar em produção com a query Q6 (§3.5).

### 2.4 "Até 1 pessoas" e "não informado"

- `WorkspaceAccount.jsx:144`: `` `Até ${number(plan.max_users)} pessoas` `` sem singular; Free/Beta têm `max_users = 1`.
- "Créditos de imagem não informados" quando `limit_image_generation`/`image_credits_monthly` é nulo/0; "Limite de equipe não informado" quando `max_users` nulo (ex.: Enterprise ilimitado). O catálogo não tem campos para "ilimitado", descrição comercial, lista de recursos, destaque ou CTA — a UI cai no texto de ausência.
- "Consulte a equipe" para todos: a regra depende de `plan_type` ser exatamente `pro`/`enterprise` (`WorkspaceAccount.jsx:130`); verificar valores reais (Q1).
- Créditos de imagem são legado: o Studio cobra imagem em tokens reais (memória "Cobrança do Studio em tokens reais"). Exibir "50 créditos de imagem" no Pro promete algo que não é aplicado. Decisão §8.
- Preços divergentes: `CADU_COMMERCIAL_PRICES` tem planos `essencial 297 / equipe 697 / agência 1497` (`routes.py:51-54`) que não existem no catálogo exibido (Pro 1.599 / Enterprise 3.599). Terceira fonte de verdade de preço.

### 2.5 Faturamento vazio

- Lê tabela real (`cadu_invoices`), mas o único escritor no fluxo do cliente é `/api/subscription/checkout` → `db.criar_invoice_assinatura` (`aicentralv2/routes.py:15110`, `15187`). `db.criar_invoice` (`db.py:5487`) não tem chamador no Workspace.
- **Compra de pacote não gera fatura**: `request_credit_package` grava só `cadu_credit_requests` + lote (`routes.py:1293-1303`). Logo, toda compra feita na tela de Créditos fica invisível em Faturamento.
- `obter_invoices` ordena por `reference_month`, `obter_invoices_cliente` por `billing_month` (`db.py:5458` vs `5619`) — dois esquemas históricos; `_workspace_billing_data` normaliza os dois (`routes.py:456+`). Confirmar colunas em produção (Q3).

### 2.6 Contraste dos botões (texto escuro sobre verde escuro)

- `styles.css:1021`: `.cadu-ds-credit-package-grid button { background: var(--cadu-accent-strong); color: var(--cadu-on-accent,#fff) }` — seletor genérico de `button` que **sobrescreve o CaduButton/Untitled**.
- `tokens.css:168`: `[data-cadu-theme="dark"] { --cadu-on-accent: #04201c }` (texto escuro, pensado para acento claro), mas `[data-cadu-skin="workspace"]` mantém `--cadu-accent-strong: #055c50` (verde escuro) (`tokens.css:99-103`). Resultado no tema escuro: `#04201c` sobre `#055c50` ≈ 1,9:1.
- Mesmo defeito em `.cadu-ds-pricing-action` (`styles.css:2970`) — botões da página de Planos.
- Cartão dentro de cartão: `.cadu-ds-account-section` (cartão) contém `.cadu-ds-credit-package-grid article` (cartões com borda, `styles.css:1015`), e a mesma informação aparece duas vezes (tabela + grade, `WorkspaceAccount.jsx:165`).

### 2.7 Outras incoerências

- Compra pelo Workspace grava `status='approved'` e libera na hora; pelo MCP grava `pending` e exige confirmação (`credit_purchase_service.py:41`). Aceitável, mas sem idempotência: duplo clique = dois lotes e dois e-mails (não há chave única no pedido).
- O endpoint aceita `tokens`/`price` do cliente e só valida contra o dicionário; o preço salvo vem do servidor (ok), mas a validação de plano usa `tokens_monthly_limit` como "créditos" de plano (`routes.py:1262-1270`) — comprar um *plano* por esse endpoint cria um lote de 12 meses com a franquia mensal. Errado conceitualmente.
- Destinatário do financeiro fixo em código: `recipients = ['apolo@centralcomm.media']` (`routes.py:1309`).
- Uso do "admin" legado: `/cadu/creditos` (`aicentralv2/routes.py:~600-710`) grava `cadu_credit_purchases` e `cadu_credit_movements` via `db.registrar_compra_creditos`/`criar_movimento_creditos` (`db.py:4894`, `4937`) e mexe em `image_credits_used_current_month` — **não** cria lote em `cadu_credits_extras`. Créditos adicionados pelo admin legado não aparecem no saldo do Workspace.

---

## 3. Base de dados

### 3.1 Inventário

| Tabela | Criada em (repo) | Escreve | Lê | Situação |
|---|---|---|---|---|
| `cadu_plan_definitions` | sem migração no repo (só `ALTER` em `add_cadu_plan_storage.sql`) | admin legado | Planos, conector (preço/token, `cadu_credit_connector.py:44`) | Em uso; faltam campos comerciais |
| `cadu_client_plans` | `migrations/create_cadu_client_plans.py` | checkout de assinatura, admin, `restore_centralcomm_test_credits.sql` | Planos, Uso, `credit_position`, skills | Em uso; colunas `tokens_used_current_month`/`image_credits_*` **mortas** para tokens |
| `cadu_credits_extras` | `add_cadu_tool_token_ledger.sql` (ORDER:74) | compra Workspace/MCP, `grant_cadu_launch_credit`, conector (débito) | saldo em todo o Cadu | **Fonte de verdade do saldo** |
| `cadu_tools_token_usage` | idem | `ToolTokenLedger`, conector | Uso, Créditos, alertas, custos Studio | **Fonte de verdade do consumo** |
| `cadu_credit_requests` | `add_cadu_credit_requests.sql` + `_lot.sql` (ORDER:75-76) | compra Workspace/MCP | MCP (`pending_extra`) | Em uso como pedido; não aparece em nenhuma tela |
| `cadu_credit_entitlements` | `add_cadu_launch_credit.sql` (**fora de ORDER e de NOT_IN_DEPLOY**) | função `grant_cadu_launch_credit`, `restore_centralcomm…` | `email_service.py:221` | Em uso (bônus); migração não registrada |
| `cadu_credit_alerts` | `add_cadu_credit_alerts.sql` (**não registrada**) | `cadu_credit_alerts.py`, `cadu_tool_billing.py` | idem | Em uso; migração não registrada |
| `cadu_invoices` | `migrations/create_cadu_invoices.py` | checkout de assinatura (`routes.py:15187`), admin | Faturamento | Em uso, mas não recebe pacotes |
| `cadu_credit_movements` | `create_cadu_credit_movements.sql` (**não registrada**) | admin legado `/cadu/creditos` | admin legado (`db.py:4746`, `4953`) | **Fonte paralela/órfã** em relação ao Workspace |
| `cadu_credit_purchases` | idem | admin legado (`db.py:4914`) | admin legado | **Órfã** para o Workspace (duplica `cadu_credit_requests`) |
| `cadu_credit_packages` | idem | ninguém no código | admin legado, `creative_media/studio_sessions.py:113` | **Catálogo órfão** — pacotes reais estão hardcoded em 3 lugares |
| assinaturas (`cadu_subscriptions`) | não existe | — | — | A assinatura é a própria linha de `cadu_client_plans` |

### 3.2 Alterações propostas

**M1 — `add_cadu_billing_catalog_v1.sql`** (idempotente, `IF NOT EXISTS`):
```sql
ALTER TABLE cadu_plan_definitions
  ADD COLUMN IF NOT EXISTS slug VARCHAR(40),
  ADD COLUMN IF NOT EXISTS tagline VARCHAR(200),
  ADD COLUMN IF NOT EXISTS features_list JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS users_unlimited BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS cta_kind VARCHAR(20) NOT NULL DEFAULT 'contact', -- checkout|contact|current|none
  ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT TRUE,        -- Beta Tester = false
  ADD COLUMN IF NOT EXISTS highlight BOOLEAN NOT NULL DEFAULT FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cadu_plan_definitions_slug ON cadu_plan_definitions (slug) WHERE slug IS NOT NULL;

ALTER TABLE cadu_credit_packages
  ADD COLUMN IF NOT EXISTS slug VARCHAR(40),
  ADD COLUMN IF NOT EXISTS validity_months INTEGER NOT NULL DEFAULT 12;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cadu_credit_packages_slug ON cadu_credit_packages (slug) WHERE slug IS NOT NULL;
-- seed com ON CONFLICT (slug) DO UPDATE: extra-essencial 100000/49, extra-equipe 500000/179, extra-agencia 1000000/299
```
`cadu_credit_packages` passa a ser o catálogo único de pacotes (adota a tabela órfã em vez de criar outra). `CREATE TABLE IF NOT EXISTS` incluído antes, pois a migração de origem não está registrada.

**M2 — `add_cadu_credit_lot_source_v1.sql`**:
```sql
ALTER TABLE cadu_credits_extras
  ADD COLUMN IF NOT EXISTS source VARCHAR(24) NOT NULL DEFAULT 'purchase', -- plan_allowance|purchase|bonus|adjustment
  ADD COLUMN IF NOT EXISTS label VARCHAR(160),
  ADD COLUMN IF NOT EXISTS client_plan_id BIGINT,
  ADD COLUMN IF NOT EXISTS cycle_start DATE,
  ADD COLUMN IF NOT EXISTS credit_request_id BIGINT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cadu_credits_extras_allowance_cycle
  ON cadu_credits_extras (id_cliente, cycle_start) WHERE source = 'plan_allowance';
```
O índice único garante que a franquia do ciclo seja concedida uma vez só (idempotência do job).

**M3 — `add_cadu_credit_request_idempotency_v1.sql`**:
```sql
ALTER TABLE cadu_credit_requests
  ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(80),
  ADD COLUMN IF NOT EXISTS package_slug VARCHAR(40),
  ADD COLUMN IF NOT EXISTS invoice_id BIGINT,
  ADD COLUMN IF NOT EXISTS finance_notified_at TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cadu_credit_requests_idem
  ON cadu_credit_requests (id_cliente, idempotency_key) WHERE idempotency_key IS NOT NULL;
ALTER TABLE cadu_invoices ADD COLUMN IF NOT EXISTS credit_request_id BIGINT;
```

**Backfill (script separado, `NOT_IN_DEPLOY` como `manual-pontual`):**
- `UPDATE cadu_credits_extras e SET source='bonus', label='Crédito de lançamento' FROM cadu_credit_entitlements t WHERE t.credit_lot_id=e.id;`
- `UPDATE cadu_credits_extras e SET label=r.package_name, credit_request_id=r.id FROM cadu_credit_requests r WHERE r.credit_lot_id=e.id;`
- Faturas retroativas para `cadu_credit_requests` aprovados sem fatura: **só após decisão do financeiro** (§8).
- Seed dos campos comerciais dos planos (valores do §5.1) após aprovação.

**Ordem em `migrations/ORDER.txt`:** registrar primeiro, como já-aplicadas-ou-idempotentes, as órfãs que o código usa: `add_cadu_credit_alerts.sql`, `add_cadu_launch_credit.sql`, `create_cadu_credit_movements.sql` (todas `IF NOT EXISTS`); depois M1, M2, M3. Antes, rodar Q2 em produção para confirmar quais já existem. Testar tudo em Postgres local (memória "Deploy: ORDER.txt e migrações"), nunca no `.env` remoto.

**Rollback:** só colunas/índices novos e nulos/com default — rollback = `DROP INDEX IF EXISTS …; ALTER TABLE … DROP COLUMN IF EXISTS …` em `rollback_cadu_billing_v1.sql` (listado em `NOT_IN_DEPLOY.txt` como reversão).

### 3.3 Órfãs — o que fazer
- `cadu_credit_packages`: **adotar** como catálogo (M1).
- `cadu_credit_purchases`, `cadu_credit_movements`: congelar. Mudar o admin `/cadu/creditos` para criar lotes `source='adjustment'` em `cadu_credits_extras` (fase pós-lançamento); manter as tabelas só leitura para histórico. Não dropar antes de Q5.
- `cadu_client_plans.tokens_used_current_month` / `image_credits_*`: deixar de ler. Não remover (PHP legado pode ler).

### 3.4 Duplicidades de fonte de verdade
1. Uso: `cadu_client_plans.tokens_used_current_month` × `cadu_tools_token_usage` → fica o ledger.
2. Saldo: `cadu_credit_movements` (admin) × `cadu_credits_extras` → fica `cadu_credits_extras`.
3. Pedido: `cadu_credit_purchases` × `cadu_credit_requests` → fica `cadu_credit_requests`.
4. Preço: catálogo × `CADU_COMMERCIAL_PRICES` × JSX × `EXTRA_PACKAGES` → fica o banco.

### 3.5 Queries somente leitura para o usuário rodar em produção
```sql
-- Q1 catálogo de planos real
SELECT id, plan_name, plan_type, price_monthly, tokens_monthly_limit, max_users,
       limit_image_generation, storage_bytes_limit, is_active, display_order, features
  FROM cadu_plan_definitions ORDER BY display_order;
-- Q2 quais tabelas existem
SELECT table_name FROM information_schema.tables WHERE table_schema='public'
   AND table_name IN ('cadu_plan_definitions','cadu_client_plans','cadu_credits_extras','cadu_tools_token_usage',
   'cadu_credit_requests','cadu_credit_entitlements','cadu_credit_alerts','cadu_invoices',
   'cadu_credit_movements','cadu_credit_purchases','cadu_credit_packages');
-- Q3 colunas de faturas e lotes
SELECT table_name, column_name, data_type FROM information_schema.columns
 WHERE table_name IN ('cadu_invoices','cadu_credits_extras','cadu_client_plans','cadu_credit_requests')
 ORDER BY table_name, ordinal_position;
-- Q4 contador morto x ledger, por cliente com plano ativo
SELECT p.id_cliente, p.tokens_used_current_month,
       (SELECT COALESCE(SUM(tokens_cobrados),0) FROM cadu_tools_token_usage u
         WHERE u.id_cliente=p.id_cliente AND u.status='charged'
           AND u.charged_at >= date_trunc('month', now())) AS ledger_mes
  FROM cadu_client_plans p WHERE p.plan_status='active' ORDER BY ledger_mes DESC LIMIT 30;
-- Q5 uso das tabelas legadas
SELECT 'movements' t, COUNT(*), MAX(created_at) FROM cadu_credit_movements
UNION ALL SELECT 'purchases', COUNT(*), MAX(created_at) FROM cadu_credit_purchases
UNION ALL SELECT 'packages', COUNT(*), MAX(updated_at) FROM cadu_credit_packages
UNION ALL SELECT 'requests', COUNT(*), MAX(created_at) FROM cadu_credit_requests
UNION ALL SELECT 'invoices', COUNT(*), MAX(created_at) FROM cadu_invoices;
-- Q6 cobranças pequenas (origem do "1 créditos")
SELECT ferramenta, etapa, COUNT(*), MIN(tokens_cobrados), MAX(tokens_cobrados)
  FROM cadu_tools_token_usage WHERE status='charged' AND tokens_cobrados <= 10
 GROUP BY 1,2 ORDER BY 3 DESC;
-- Q7 pedidos sem fatura
SELECT r.id, r.id_cliente, r.package_name, r.price_brl, r.billing_mode, r.status, r.created_at
  FROM cadu_credit_requests r ORDER BY r.created_at DESC LIMIT 50;
-- Q8 lotes por cliente com origem
SELECT e.id_cliente, e.id, e.tokens_amount, e.tokens_used, e.expires_at, e.status,
       t.entitlement_key, r.package_name
  FROM cadu_credits_extras e
  LEFT JOIN cadu_credit_entitlements t ON t.credit_lot_id=e.id
  LEFT JOIN cadu_credit_requests r ON r.credit_lot_id=e.id
 ORDER BY e.id_cliente, e.id;
```

---

## 4. Backend

### 4.1 Serviço novo `aicentralv2/cadu_billing/account.py` (funções puras + leitura)
- `catalog_plans()` / `catalog_packages()` — do banco; substitui `CADU_COMMERCIAL_PRICES`, `CADU_EXTRA_CREDIT_AMOUNTS`, `EXTRA_PACKAGES` e o array do JSX.
- `current_cycle(plan, today)` → `(start, end)` pura, testável.
- `ensure_plan_allowance(cursor, client_id)` — cria o lote `plan_allowance` do ciclo se faltar (`INSERT … ON CONFLICT DO NOTHING` sobre o índice M2). Chamado: (a) de forma preguiçosa em `credit_position` antes de somar e antes de cobrar no conector; (b) por um job diário. Sem job externo, o modo preguiçoso basta no lançamento.
- `usage_summary(client_id, cycle)` — `SUM(tokens_cobrados)` de `cadu_tools_token_usage` no ciclo, separado por origem via `metadata.allocations` → lote → `source` (franquia vs avulso); interações = `COUNT(DISTINCT COALESCE(metadata->>'studio_root_session_id', idempotency_key prefixo))`, por ferramenta.
- `credit_position` passa a devolver `{allowance:{granted,used,available,cycle_end}, extras:{granted,used,available,lots}, total_available}`; manter as chaves antigas (`available`, `monthly`, `monthly_usage_percentage`) para os shells que as usam (`routes.py:3942`, `5601`, `5861`, `6261`, `6570`, `8679`).

### 4.2 Contratos JSON (bootstrap da Conta)
```json
// planos
{"current_plan":{"slug":"pro","name":"Pro","cycle":{"start":"2026-10-01","end":"2026-10-31"}},
 "plans":[{"slug":"pro","name":"Pro","tagline":"…","price_monthly":1599,"tokens_monthly":2000000,
           "users":{"limit":5,"unlimited":false},"storage_bytes":null,"features":["…"],
           "cta":"checkout|contact|current","highlight":true}]}
// creditos
{"balance":{"total":2180000,"allowance":{"available":1900000,"granted":2000000,"cycle_end":"…"},
            "extras":{"available":280000,"lots":2}},
 "packages":[{"slug":"extra-equipe","name":"Extra Equipe","tokens":500000,"price":179,"validity_months":12}],
 "lots":[{"id":1,"label":"Extra Equipe","source":"purchase","available":280000,"total":500000,"expires_at":"…"}],
 "last_interaction":{"tool":"Studio","tokens":12400,"at":"…"},
 "requests":[{"id":9,"package":"Extra Equipe","price":179,"billing_mode":"postpaid","status":"approved","invoice_number":null}]}
// uso
{"cycle":{"start":"…","end":"…"},"allowance":{"used":100000,"limit":2000000},
 "extras_used":0,"by_tool":[{"tool":"Studio","tokens":80000,"interactions":3}],
 "interactions":5,"daily":[{"date":"…","tokens":…}],"space":{…},"projection":{"tokens_end_of_cycle":…}}
// faturamento
{"summary":{"open_total":…,"open_count":…,"paid_count":…,"overdue_count":…},
 "invoices":[…], "pending_requests":[…]}
```

### 4.3 Compra de pacote (`POST /workspace/api/creditos/solicitar`)
- Receber só `package_slug`, `billing_mode`, `note`, `idempotency_key` (UUID gerado ao abrir o modal). Ignorar `tokens`/`price` do cliente.
- Recusar planos neste endpoint (troca de plano vai para `/assinatura/checkout` ou "falar com a equipe").
- Transação única: `cadu_credit_requests` (com `idempotency_key`, `ON CONFLICT` → devolve o pedido existente) + lote `source='purchase'`, `label`, `credit_request_id` + `cadu_invoices` pendente (`credit_request_id`, valor, vencimento conforme `billing_mode`) — se o financeiro aprovar (§8).
- Exigir papel admin (como o MCP já faz em `credit_purchase_service.py:29`).
- E-mail ao financeiro depois do commit; gravar `finance_notified_at` em sucesso; destinatários por variável `CADU_FINANCE_EMAILS` em vez do e-mail fixo (`routes.py:1309`).
- Unificar com `credit_purchase_service.purchase_extra` (MCP) numa só função.

### 4.4 Medição de tokens
Nenhuma mudança no conector além de chamar `ensure_plan_allowance` antes de selecionar lotes. Parar de exibir `tokens_used_current_month`.

---

## 5. Frontend por tela

Regras gerais: só `CaduButton` (remover o seletor `.cadu-ds-credit-package-grid button` e o estilo de `.cadu-ds-pricing-action` como botão; usar `CaduButton`/link com `variant`); tabela do kit (`DataTable` atual sobre a tabela Untitled); **um** nível de superfície por seção — linhas e divisores dentro da seção, nunca cartões com borda dentro de cartões; plural via helper `plural(n, 'pessoa', 'pessoas')`; nenhum texto "não informado" — campo ausente some, ou mostra "Ilimitado"/"Sob consulta" conforme flag.

**Correção de contraste (tokens):** em `tokens.css`, no tema escuro do Workspace, ou definir `--cadu-on-accent:#fff` quando `--cadu-accent-strong` for escuro, ou criar `--cadu-on-accent-strong` (#fff) e usá-lo em todo fundo `accent-strong`. Validar 4,5:1 nos dois temas.

### 5.1 Planos
- Cabeçalho com plano atual, ciclo e uso da franquia (barra).
- Comparativo em **tabela** (colunas = planos públicos; Beta Tester só aparece se for o atual): preço/mês, tokens/mês, pessoas, armazenamento, recursos (Workspace, Studio, Planner, Connect, Skills), suporte.
- Bloco "O que está incluído" (franquia mensal renova a cada ciclo; créditos avulsos complementam).
- CTA por `cta_kind`: "Plano atual" (desabilitado), "Contratar" (checkout), "Falar com a equipe" (mailto/form) — sem cinza-sobre-cinza.
- FAQ curto: o que é um token; o que acontece se a franquia acabar (usa créditos avulsos, depois bloqueia); franquia acumula? (não); como trocar de plano; como é cobrado.
- Layout responsivo sem 3+1: `grid-template-columns: repeat(n, 1fr)` com n = nº de planos públicos, ou tabela.

### 5.2 Créditos
- Resumo em uma faixa: saldo total = franquia disponível (vence em X) + avulsos.
- Pacotes: uma tabela (ou lista de linhas) com nome, volume, validade, preço e `CaduButton` "Comprar" — remover a grade duplicada.
- Lotes: tabela com origem (Franquia de outubro / Extra Equipe / Bônus de lançamento), disponível, total, vencimento.
- Pedidos recentes com status de cobrança.
- Último consumo = última interação agrupada, em tokens, com ferramenta.
- Estado vazio: "Você está usando a franquia do plano. Compre um pacote quando precisar de mais."

### 5.3 Uso
- Franquia do ciclo: `usado de limite` com barra e projeção até o fim do ciclo.
- Créditos avulsos consumidos no ciclo (separado).
- Consumo por ferramenta (tabela) e por dia (gráfico simples).
- Interações (contagem agrupada), espaço e arquivos.
- Remover "Créditos adicionados" daqui (pertence a Créditos).

### 5.4 Faturamento
- Tabela de faturas (mensalidade + pacotes).
- Pedidos de pacote ainda sem fatura, com "Em faturamento pelo financeiro".
- Estado vazio útil: explica quando a fatura aparece, condição de pagamento e contato do financeiro.

---

## 6. Testes e verificação

Existentes (20 passam): `tests/test_workspace_account_usage.py`, `test_workspace_billing_integrations.py`, `test_workspace_account_sections.py`, `test_credit_position_queries.py`, `test_cadu_credit_connector.py`, `test_cadu_tool_billing.py`, `test_cadu_creditos.py`, `test_workspace_rag_credits.py`, `test_cadu_mcp_credit_artifact_flow.py`. Nenhum cobre: uso do ciclo pelo ledger, franquia mensal, idempotência da compra, fatura de pacote, contraste.

A criar:
1. `tests/test_cadu_billing_cycle.py` — `current_cycle` (dia 31, fevereiro, troca de plano no meio do ciclo).
2. `tests/test_cadu_plan_allowance.py` — `ensure_plan_allowance` idempotente; ordem de débito franquia → bônus → avulso (cursor falso).
3. `tests/test_workspace_usage_summary.py` — soma do ciclo e separação por `source` via `allocations`; regressão do "0 de 2.000.000".
4. `tests/test_workspace_credit_purchase.py` — mesma `idempotency_key` = 1 pedido/1 lote/1 fatura; slug inválido; plano recusado; não-admin recusado; preço do servidor.
5. Migrações M1–M3 aplicadas duas vezes num Postgres local (idempotência) + rollback.
6. Frontend: `tests/frontend/` com snapshot de rótulos (sem "não informado", plural correto).
7. Fixtures de tela em `tests/visual/workspace/fixtures.mjs`: adicionar `planos`, `creditos`, `uso`, `faturamento` com dados realistas (Pro com consumo, lotes de franquia+avulso, 2 faturas, 1 pedido sem fatura) e estados vazios; verificar em claro/escuro, 1280 e 375px, contraste dos botões com a ferramenta de inspeção.

---

## 7. Fases (até 2026-10-11)

| Dia | Fase | Entrega | Bloqueador? |
|---|---|---|---|
| 06/10 (seg) | 0 | Usuário roda Q1–Q8 e responde §8 | **Sim** |
| 07/10 | 1 | Contraste (tokens + remover seletores de `button`), plural, sem "não informado", remover grade duplicada/cartão em cartão, Uso lendo o ledger do mês (`SUM tokens_cobrados` — sem migração) | **Sim** |
| 07–08/10 | 2 | M1–M3 em Postgres local; catálogo único (planos+pacotes do banco); compra idempotente e só por slug, admin-only | **Sim** (idempotência e preço) |
| 08–09/10 | 3 | Franquia mensal como lote (`ensure_plan_allowance` preguiçoso) + `credit_position` com franquia/avulso; telas Créditos e Uso separando os dois | **Sim** se a decisão for vender a franquia no lançamento; senão, rótulo honesto "franquia em breve" |
| 09/10 | 4 | Página de Planos comercial (comparativo, CTA, FAQ) + seed dos campos | **Sim** |
| 10/10 | 5 | Fatura para pedido de pacote + "pedidos em faturamento" na tela; destinatários do financeiro por env | Sim (mínimo: mostrar pedidos); fatura automática pode ser pós |
| 10/10 | 6 | Testes §6, fixtures visuais, revisão em tela; deploy com ORDER.txt | **Sim** |
| pós | 7 | Admin legado `/cadu/creditos` gravando em `cadu_credits_extras`; congelar `cadu_credit_movements/purchases`; job diário de franquia; corrigir `routes.py:4950` (`id_plan`); créditos de imagem legados removidos | Não |

Estimativa realista: fases 1–2 e 4 cabem; fase 3 é a de maior risco (toca o caminho de cobrança de todo o Cadu) — fazer com feature flag `CADU_PLAN_ALLOWANCE_LOTS`.

---

## 8. Riscos e perguntas em aberto

**Decisões do usuário (bloqueiam):**
1. A franquia mensal (Free 100 mil, Pro 2 mi, Enterprise 10 mi) passa a ser concedida automaticamente a cada ciclo? Hoje **não é** — clientes só têm o que foi lançado em lote manual.
2. Ciclo: dia 1 do mês ou aniversário do contrato? Franquia não usada expira (proposta: sim)?
3. Ordem de débito: franquia antes dos avulsos (proposta: sim)?
4. Nome da unidade na UI: "tokens" ou "créditos"?
5. Créditos de imagem (Pro: 50) continuam sendo vendidos? O Studio já cobra imagem em tokens; proposta: remover do catálogo.
6. Planos "Essencial 297 / Equipe 697 / Agência 1.497" em `CADU_COMMERCIAL_PRICES` ainda existem? O catálogo exibido é Free/Pro/Enterprise.
7. Enterprise: pessoas ilimitadas? Armazenamento por plano?
8. Beta Tester: aparece para quem não é beta? Tem franquia?
9. Quem emite a fatura do pacote: o sistema gera `cadu_invoices` automaticamente ou o financeiro lança? Pré-pago libera antes do pagamento (hoje libera)?
10. E-mails do financeiro (substituir o fixo `apolo@centralcomm.media`).
11. Validade de 12 meses dos pacotes confirmada?
12. Membros não-admin podem comprar pelo Workspace (hoje podem; o MCP não deixa)?

**Riscos:**
- Produção diverge do repo: `cadu_plan_definitions` não tem migração de criação aqui; três migrações de crédito não estão em ORDER.txt. Sem Q2/Q3 não aplicar nada.
- Conceder franquia automaticamente aumenta o saldo de todos os clientes ativos de uma vez — combinar com o financeiro e usar flag.
- `credit_position` é lido em ~7 telas; mudar o contrato quebra shells — manter chaves antigas.
- Admin legado continua gravando em tabelas paralelas até a fase 7: créditos lançados por lá não aparecem no Workspace.
- Branch `main` compartilhada: commits pequenos por fase, sem misturar com as mudanças do Studio no working tree.
