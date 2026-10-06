# Auditoria de back-end: cadastro, login, planos e créditos

Data: 2026-10-06. Escopo: somente leitura (nenhum arquivo de código alterado, nenhuma migração aplicada, nenhuma escrita no banco). Base: `main` em `dddd524d3` com a árvore de trabalho atual.

## 1. Veredito por fluxo

| Fluxo | Veredito | Motivo principal |
|---|---|---|
| 1. Cadastro / onboarding / convite / Google | **Risco alto** | Cadastro não é atômico (cliente órfão), conta pública nasce sem plano nem crédito de lançamento, sem rate limit/CSRF, convite de cliente aponta para fluxo que o Flask recusa |
| 2. Login / sessão / reset | **Risco alto** | Sem rate limit nem bloqueio por tentativas; sessão assinada de 180 dias sem revalidação (usuário desativado ou com senha trocada continua logado) |
| 3. Alteração de plano / checkout | **Bloqueador** | `/api/subscription/checkout` aceita preço, limites e plano vindos do navegador e ativa o plano na hora, sem pagamento, para qualquer usuário logado |
| 4. Créditos (débito, compra, franquia) | **Bloqueador** (compra) / OK (débito) | Débito é atômico e não negativa saldo; mas qualquer membro de qualquer conta (inclusive recém-cadastrada) libera tokens ilimitados sem pagamento |
| 5. Migrações novas | **OK para o lançamento se NÃO aplicadas**; teste de deploy falha | 3 `.sql` novos fora de `ORDER.txt` e de `NOT_IN_DEPLOY.txt` quebram `tests/test_deploy_order.py` |
| 6. Admin CentralX | **Risco médio** | Admin ainda lê contador morto e grava saldo em tabelas que a Conta não lê |
| 7. Testes | 134 passam, 4 falham (nenhuma falha em débito/plano/compra) | Ver §6 |

## 2. Achados por severidade

### BLOQUEADORES

**B1. Checkout de assinatura confia no cliente e ativa plano sem pagamento**
`aicentralv2/routes.py:15110-15165` (rota `api_subscription_checkout`, decorador `client_accessible_api` em `routes.py:506` só exige `user_id`).
- `plan_id`, `plan_price`, `tokens_monthly_limit`, `image_credits_monthly`, `max_users` vêm do JSON (`routes.py:15127-15155`) e são gravados em `cadu_client_plans` com `plan_status='active'` imediatamente (`db.py:5016-5053`). A fatura é criada com `total = plan_price` do navegador.
- Cenário: qualquer membro (não só admin) de uma conta grátis envia `{"plan_id": <enterprise>, "plan_price": 0, "max_users": 999, ...}` → plano Enterprise ativo, fatura de R$ 0, e o trigger `trg_grant_cadu_launch_credit` (`migrations/add_cadu_launch_credit.sql:59-73`) concede 100k tokens. Com `CADU_PLAN_ALLOWANCE_ENABLED` ligado, ganha também a franquia mensal do plano.
- Não é atômico: atualiza dados de faturamento, cria plano e depois fatura em chamadas separadas com commit próprio; se a fatura falhar, fica plano ativo sem fatura.
- Não existe upgrade/downgrade/cancelamento pelo cliente: com plano ativo, o índice `idx_one_active_plan_per_client` devolve "Você já possui um plano ativo" (`routes.py:15168`). Não há proration, nem auditoria, nem tratamento da franquia em troca de plano.
- Correção mínima para o lançamento: desligar a rota (404/feature flag) ou: exigir admin da conta + CSRF; buscar preço e limites em `cadu_plan_definitions` pelo `plan_id` (validar `is_active`); criar o plano como `pending_payment` (sem disparar o trigger) e ativar só quando o financeiro confirmar; tudo numa transação.

**B2. Compra de pacote libera tokens ilimitados, sem pagamento, para qualquer membro**
`aicentralv2/cadu_workspace/routes.py:1316-1408` (`request_credit_package`).
- Só exige login + CSRF. Não verifica papel (o caminho MCP exige admin: `cadu_workspace/credit_purchase_service.py:72-73`; a regra está inconsistente entre as duas portas).
- O lote é criado `active`, sem expiração, no ato (`routes.py:1368-1372`), inclusive com `billing_mode='postpaid'` escolhido pelo próprio cliente. A deduplicação cobre só o mesmo usuário + mesmo pacote em 30 s (`routes.py:1343-1347`).
- Cenário: alguém se cadastra em `/signup` (sem verificação de e-mail, sem CNPJ), clica "comprar Extra Agência" pós-pago 10 vezes com intervalo de 31 s → 10 M tokens de IA reais consumíveis antes de qualquer cobrança. O e-mail ao financeiro é a única barreira e é posterior.
- Correção mínima: (a) exigir `user_type in {admin, superadmin}` (alinhar com o MCP); (b) para contas sem plano pago/sem CNPJ, gravar o pedido `pending` e liberar o lote só na aprovação do financeiro; ou (c) teto de crédito pós-pago por cliente (ex.: soma de pedidos `approved` não faturados ≤ limite). Se o dono decidir manter liberação imediata, pelo menos (a) + teto.

### ALTOS

**A1. Cadastro público não é atômico e deixa cliente órfão**
`aicentralv2/services/onboarding_comercial.py:46-63`: `db.criar_cliente` faz commit; se `db.criar_contato` falhar (e-mail duplicado em corrida, constraint, queda), o `tbl_cliente` fica sem contato (só um log). Também a checagem de duplicidade é ler-depois-inserir (`:34`), sujeita a corrida entre duas abas/Google + formulário.
Correção: criar cliente e contato na mesma transação (cursor único, um commit) e garantir índice único `lower(email)` em `tbl_contato_cliente` (validar com Q-S2).

**A2. Conta pública nasce sem plano e sem crédito de lançamento**
`provisionar_conta_publica` não cria `cadu_client_plans`; o bônus de 100k só é concedido pelo trigger em INSERT de `cadu_client_plans` (`migrations/add_cadu_launch_credit.sql:59-73`). Resultado: saldo 0, `send_launch_bonus_email` é pulado (`email_service.py:231`), `cadu_family/repository.py:344-347` devolve `plan_type='free'` sintético, e a franquia (quando ligada) não se aplica (`cadu_plan_allowance.py:181-183`, sem plano ativo → no-op). O usuário só usa IA "comprando" (o que leva a B2).
Correção: decidir com o dono o plano inicial (ex.: `free`/trial de `cadu_plan_definitions`) e criá-lo na mesma transação do A1; o trigger concede o bônus. Validar com Q-S1.

**A3. Sem rate limit / bloqueio no login, cadastro, esqueci-senha e convite**
Nenhum `Flask-Limiter` ou contador em `routes.py:1270` (signup), `:1407` (login), `:1563` (forgot-password), nem em `/aceitar-convite`. `verificar_credenciais` (`db.py:1196-1210`) não registra falhas.
Cenário: brute force de senha de 8 caracteres; criação massiva de contas (combinada com B2); disparo de e-mails de reset/boas-vindas em massa (custo e reputação Brevo).
Correção: limitador por IP+e-mail (ex.: 5/min e 20/h no login; 3/h por IP no signup; 3/h por e-mail no forgot). Pode ser em memória/Redis ou tabela simples.

**A4. Sessão de 180 dias sem revalidação: desativar membro ou trocar senha não derruba a sessão**
`aicentralv2/config.py:97-100` (180 dias, refresh a cada request, cookie assinado no cliente, domínio `.centralcomm.media` em produção `config.py:351`). `aicentralv2/auth.py:74-82` (`login_required` do Workspace) só verifica `'user_id' in session`; `_workspace_team_admin` (`cadu_workspace/routes.py:1435`) confia em `session['user_type']`.
Cenário: admin desativa um ex-funcionário em `/workspace/app/equipe/<id>/status` → ele continua usando IA e gastando o saldo por até 180 dias; um admin rebaixado continua admin (convida, compra). Reset de senha (`routes.py:1592+`) não invalida sessões roubadas.
Correção: em `before_request` do Workspace (ou no `login_required`), recarregar contato a cada N minutos (cache curto) e limpar a sessão se `status=false`, cliente inativo ou `user_type` mudou; gravar `password_changed_at`/`session_version` no contato e comparar com a sessão.

**A5. Convite de membro do cliente leva a um fluxo que o Flask recusa**
`email_service.py:272` gera link `cadu/aceitar-convite?token=...`; as rotas Flask `routes.py:3041-3075` e `:3076-3100` recusam qualquer convite cujo cliente não seja CENTRALCOMM ("REGRA INQUEBRÁVEL"). Se o host `cadu` ainda for o PHP e ele aceitar, ok; se o host `cadu` já estiver no Flask, todo convite criado em `create_team_invite` (`cadu_workspace/routes.py:10241`) falha. **Validar em tela antes do lançamento.** Também: `max_users` do plano não é checado ao convidar (`routes.py:10241-10280`), e aceitar convite para um e-mail que já existe em outro cliente sobrescreve nome e senha desse contato sem mudar de cliente (`routes.py:3136-3140`).

### MÉDIOS

**M1. Débito pós-execução perde o registro quando o saldo acaba no meio**
`cadu_tool_billing.py:180-320`: o débito é atômico e seguro contra corrida (lotes com `FOR UPDATE`, mesma ordem determinística, `UPDATE ... tokens_used + x`, reavaliação do `WHERE tokens_used < tokens_amount` após o lock no READ COMMITTED; o caminho em transação `cadu_credit_connector.py:213-288` idem). Dois débitos simultâneos **não** negativam saldo. Porém, como a cobrança acontece depois da chamada ao provedor, `InsufficientToolCredits` faz `rollback` inclusive da linha do ledger: o custo real do provedor ocorreu e não fica registro. Correção: em saldo insuficiente, debitar o que houver e gravar a linha como `charged_partial`/`overdraft` (ou reservar antes via `claim_generation` com o valor estimado).

**M2. Login CSRF e logout por GET**
`/login`, `/signup`, `/forgot-password` não têm token CSRF (não há `CSRFProtect`; só `family_csrf` nas APIs do Workspace). `SameSite=Lax` não impede login CSRF (o atacante loga a vítima na conta dele). `/logout` é GET (`routes.py:1528`). Correção: token CSRF de sessão nos três formulários; logout por POST.

**M3. Expiração do token de reset em UTC comparada com `NOW()` do banco**
`routes.py:1573` grava `datetime.utcnow() + 1h`; `db.py:2291-2292` compara com `NOW()`. Se a coluna for `timestamp without time zone` e o banco estiver em `America/Sao_Paulo`, o link vale 4 h em vez de 1 h. Validar com Q-S6; correção: gravar `NOW() + INTERVAL '1 hour'` no SQL.

**M4. Enumeração de usuários no cadastro**
`onboarding_comercial.py:34-35` responde "Este e-mail já possui uma conta". O esqueci-senha é uniforme (bom, `routes.py:1597`). Aceitável se houver rate limit (A3).

**M5. Franquia (quando ligada) — pontos a decidir**
`cadu_plan_allowance.py`: idempotência por índice único `(id_cliente, cycle_start) WHERE source='plan_allowance'` + `ON CONFLICT DO NOTHING` está correta; ordem franquia→extras (`debit_order_sql`, `:136-143`) e expiração só da franquia (`:189-193`) corretas. Riscos ao ligar: (a) concede no primeiro débito a todo cliente com plano ativo, inclusive planos criados por B1 e planos legados com `tokens_monthly_limit` default 100000 (`db.py:5041`); (b) troca de plano no meio do ciclo não ajusta a franquia; (c) `_SOURCE_COLUMN` é cache por processo (`:121-129`): se a migração for aplicada com o app rodando e o cache já tiver gravado `False`, só reinício resolve; (d) `get_balance` faz `conn.commit()` na conexão compartilhada (`:256`), podendo comitar trabalho pendente do chamador.

**M6. Admin CentralX diverge da tela da Conta** (fluxo 6)
- Contador morto: `routes.py:2732-2735`, `static/js/clientes.js:1235-1241`, `templates/cadu_planos.html:104,111`, `db.py:4689-4694` (percentuais de uso), `db.py:5405-5420` (alertas por limiar), `db.py:5112-5150` (incremento/reset). Nenhum fluxo de IA atualiza `tokens_used_current_month`; a Conta lê `cadu_tools_token_usage`.
- Saldo legado: `/cadu/creditos/<plan_id>` (`routes.py:645-705`) grava em `cadu_credit_purchases`/`cadu_credit_movements` (`db.py:4894-4985`) e mexe em `image_credits_used_current_month`; não cria lote em `cadu_credits_extras`, então crédito dado pelo admin **não aparece** no saldo da Conta nem é consumível.
- `cadu_family/repository.py:344-353`: plano lê `plan_type` direto de `cadu_client_plans` e consumo de `cadu_token_usage` (tabela antiga), não do ledger.
- Depois do seed do catálogo, os pacotes de tokens (100k/500k/1M) passam a aparecer no admin legado como pacotes de "créditos de imagem" (`db.py:4885`, `:4907`) e mudam o preço unitário usado pelo Studio (`creative_media/studio_sessions.py:111-117` pega o menor preço/crédito entre todos os pacotes ativos).
Correção pós-lançamento: admin passa a criar lotes `source='adjustment'` em `cadu_credits_extras` e a mostrar uso pelo ledger; no curto prazo, rotular o admin legado como "não reflete o saldo do Workspace".

### BAIXOS / OK
- `next` / open redirect: `product_domains.safe_product_target` (`product_domains.py:157-178`) só aceita relativo ou HTTPS em host configurado, rejeita `//`, `\`, controles, credenciais e portas. OK.
- Google OIDC: state + nonce + PKCE + `email_verified is True` (`cadu_identity/google_oidc.py:69-113`); login Google só resolve contas existentes e ativas (`cadu_identity/routes.py:55-69`). OK. Cadastro Google reutiliza `provisionar_conta_publica` (herda A1/A2).
- SSO ticket: hash SHA-256, uso único com `FOR UPDATE`, expiração, `no-store` (`cadu_identity/routes.py:308-345`). OK.
- Senha: bcrypt com migração automática de MD5 legado (`db.py:1205-1210`); mínimo 8 caracteres. Aceitável.
- Reset: token `secrets.token_urlsafe(32)`, uso único, resposta uniforme. OK (salvo M3).
- Compra: preço/volume só do catálogo do servidor (`routes.py:1323-1327`); lock consultivo por cliente; e-mails só depois do commit, falha de e-mail não desfaz a compra; destinatários `apolo@`, `financeiro@`, `alexandre@` (`cadu_billing_catalog.py:49`, sobrescrevível por `CADU_FINANCE_EMAILS`) + executivo. OK.
- Débito: idempotência por `idempotency_key` com `ON CONFLICT DO NOTHING` e checagem de dono da chave (`cadu_tool_billing.py:203-243`). OK.

## 3. Migrações novas (fluxo 5)

| Arquivo | Idempotente | Em ORDER/NOT_IN_DEPLOY | Observação |
|---|---|---|---|
| `migrations/add_cadu_credit_packages_catalog_v1.sql` | Sim (`IF NOT EXISTS`, `ON CONFLICT (slug) WHERE slug IS NOT NULL`) | **Nenhum** | Seed muda preço do Studio e lista do admin legado (M6). `CREATE TABLE IF NOT EXISTS` não corrige uma tabela de produção com colunas diferentes; os `CHECK` só valem se a tabela for criada agora |
| `migrations/add_cadu_credit_lot_source_v1.sql` | Sim | **Nenhum** | `ADD COLUMN ... NOT NULL DEFAULT 'purchase'` reescreve/valida a tabela; todos os lotes existentes (inclusive bônus de lançamento) ficam `source='purchase'` — rótulo errado no extrato |
| `migrations/rename_cadu_orphan_tables_old_v1.sql` | Sim (renomes comentados; só `COMMENT ON COLUMN`) | **Nenhum** | Os `RENAME` `_old_` estão corretamente comentados: `cadu_credit_purchases/movements` ainda são usadas pelo admin (`db.py:4914`, `:4923`, `:4746`, `:4953`, `:4978`). Não descomentar antes de Q1–Q8 e da migração do admin |

- O deploy só roda o que está em `ORDER.txt` (`tests/test_deploy_order.py:51`), portanto os 3 arquivos **não serão aplicados** no próximo deploy — correto para o lançamento.
- Porém `test_every_sql_migration_is_in_the_order_file_or_called_by_a_runner_or_documented` **falha** ("Fora do deploy e sem motivo"). Correção: registrar os três em `migrations/NOT_IN_DEPLOY.txt` como `manual-pontual | aplicar só após Q1–Q8`.
- O código funciona sem as migrações: `load_packages` verifica a coluna `slug` e cai no catálogo do código (`cadu_billing_catalog.py:97-118`); a franquia verifica `source`/`cycle_start` (`cadu_plan_allowance.py:121-129`).
- Produção diverge do repo (não há migração de criação de `cadu_plan_definitions`, `cadu_invoices` tem dois esquemas — ver `docs/plano-conta-planos-creditos-uso-faturamento.md`). Testar qualquer aplicação em Postgres local com esquema copiado de produção, nunca no `.env` remoto.

## 4. Consultas SOMENTE LEITURA para o dono rodar em produção

Rodar também Q1–Q8 de `docs/plano-conta-planos-creditos-uso-faturamento.md` §3.5.

```sql
-- Q-S1 contas criadas pelo cadastro público sem plano ativo e sem lote (A2)
SELECT c.id_cliente, c.nome_fantasia, c.data_cadastro,
       EXISTS (SELECT 1 FROM cadu_client_plans p WHERE p.id_cliente=c.id_cliente AND p.plan_status='active') AS tem_plano,
       (SELECT COALESCE(SUM(tokens_amount-tokens_used),0) FROM cadu_credits_extras e
         WHERE e.id_cliente=c.id_cliente AND e.status='active' AND (e.expires_at IS NULL OR e.expires_at>NOW())) AS saldo
  FROM tbl_cliente c
 WHERE c.classificacao_cliente='Prospecção'
 ORDER BY c.id_cliente DESC LIMIT 50;

-- Q-S2 clientes órfãos (sem contato) e e-mails duplicados por caixa (A1)
SELECT c.id_cliente, c.nome_fantasia FROM tbl_cliente c
 WHERE NOT EXISTS (SELECT 1 FROM tbl_contato_cliente t WHERE t.pk_id_tbl_cliente=c.id_cliente)
 ORDER BY c.id_cliente DESC LIMIT 50;
SELECT lower(email) AS email, COUNT(*) FROM tbl_contato_cliente GROUP BY 1 HAVING COUNT(*)>1;
SELECT indexname, indexdef FROM pg_indexes WHERE tablename='tbl_contato_cliente';

-- Q-S3 planos criados pelo checkout de autoatendimento e faturas (B1)
SELECT p.id, p.id_cliente, p.id_plan_definition, pd.plan_name, pd.price_monthly,
       p.tokens_monthly_limit, pd.tokens_monthly_limit AS pd_tokens, p.max_users, pd.max_users AS pd_users,
       p.plan_status, p.created_at
  FROM cadu_client_plans p LEFT JOIN cadu_plan_definitions pd ON pd.id=p.id_plan_definition
 WHERE p.tokens_monthly_limit IS DISTINCT FROM pd.tokens_monthly_limit
    OR p.max_users IS DISTINCT FROM pd.max_users
 ORDER BY p.created_at DESC LIMIT 50;
SELECT column_name, data_type FROM information_schema.columns WHERE table_name='cadu_invoices' ORDER BY ordinal_position;

-- Q-S4 compras liberadas por não-admin e volume pós-pago não faturado (B2)
SELECT r.id_cliente, t.user_type, r.billing_mode, COUNT(*) AS pedidos, SUM(r.tokens_amount) AS tokens, SUM(r.price_brl) AS valor
  FROM cadu_credit_requests r JOIN tbl_contato_cliente t ON t.id_contato_cliente=r.requested_by
 WHERE r.status='approved'
 GROUP BY 1,2,3 ORDER BY tokens DESC LIMIT 50;

-- Q-S5 saldo negativo ou lote estourado (deve voltar vazio)
SELECT id, id_cliente, tokens_amount, tokens_used FROM cadu_credits_extras WHERE tokens_used > tokens_amount OR tokens_used < 0;

-- Q-S6 fuso e tipo da coluna de expiração do reset (M3)
SHOW timezone;
SELECT data_type FROM information_schema.columns
 WHERE table_name='tbl_contato_cliente' AND column_name='reset_token_expires';

-- Q-S7 usuários desativados com atividade recente no ledger (A4)
SELECT t.id_contato_cliente, t.email, MAX(u.created_at) AS ultimo_uso
  FROM tbl_contato_cliente t JOIN cadu_tools_token_usage u ON u.id_contato_cliente=t.id_contato_cliente
 WHERE t.status = false GROUP BY 1,2 HAVING MAX(u.created_at) > NOW() - INTERVAL '30 days';

-- Q-S8 trigger do bônus e índice de plano único existem?
SELECT tgname FROM pg_trigger WHERE tgname='trg_grant_cadu_launch_credit';
SELECT indexname FROM pg_indexes WHERE indexname='idx_one_active_plan_per_client';
```

## 5. NÃO ligar / NÃO aplicar antes do lançamento

1. `CADU_PLAN_ALLOWANCE_ENABLED` — manter desligado (M5; e B1 permitiria franquias sem pagamento).
2. `migrations/add_cadu_credit_lot_source_v1.sql`, `add_cadu_credit_packages_catalog_v1.sql`, `rename_cadu_orphan_tables_old_v1.sql` — não aplicar sem Q1–Q8 + Q-S8 e teste em Postgres local; apenas registrar em `NOT_IN_DEPLOY.txt`.
3. Descomentar os `RENAME ... _old_` — nunca, enquanto o admin `/cadu/creditos` usar essas tabelas.
4. Não divulgar/linkar `/assinatura/checkout` até corrigir B1.
5. Não abrir o cadastro público em campanha (tráfego pago) antes de B2 + A3.
6. `CADU_GOOGLE_NATIVE_ENABLED` só depois de confirmar que A1/A2 estão corrigidos (o cadastro Google usa o mesmo provisionamento).

## 6. Testes executados

Comando (com `DB_HOST=127.0.0.254 DB_PORT=1` para impedir conexão com o banco remoto):
`.venv/bin/python -m pytest -q -p no:cacheprovider` em `test_workspace_account_usage`, `test_cadu_tool_billing`, `test_workspace_rag_credits`, `test_deploy_order`, `test_cadu_billing_catalog`, `test_cadu_plan_allowance`, `test_cadu_credit_connector`, `test_cadu_creditos`, `test_auth_login`, `test_auth_public`, `test_cadu_password_flows`, `test_google_identity`, `test_cadu_native_identity`, `test_workspace_onboarding`, `test_credit_position_queries`, `test_cadu_mcp_credit_artifact_flow`, `test_workspace_billing_integrations`.

Resultado: **134 passaram, 4 falharam.**

| Teste | Causa | Classificação |
|---|---|---|
| `test_deploy_order.py::test_every_sql_migration_is_in_the_order_file_or_called_by_a_runner_or_documented` | 3 `.sql` novos sem registro | **Nova** (commits e708e9f6e / d68c90395) — corrigir em `NOT_IN_DEPLOY.txt` |
| `test_workspace_rag_credits.py::test_project_ux_keeps_rag_processing_out_of_the_project_overview` | Texto "Fontes e arquivos" saiu do JSX | Front (texto de UI, provavelmente `dddd524d3`); não é back-end |
| `test_workspace_rag_credits.py::test_project_detail_has_brand_import_and_quality_workflows` | Texto "Índice do projeto" saiu do JSX | Idem |
| `test_cadu_native_identity.py::test_callback_rotates_session_and_shares_cookie_between_products` | Callback Google agora redireciona para `/acesso-confirmado` (ponte de conversão) em vez do destino direto | Teste desatualizado em relação a `cadu_identity/routes.py:203-207`; comportamento atual é intencional |

Não há teste cobrindo: checkout de assinatura, papel exigido na compra de pacote, concorrência real de débito (só mocks), atomicidade do cadastro, rate limit.
