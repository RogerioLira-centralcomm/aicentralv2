# Auditoria: admin de conta cliente x admin interno do CentralX

Data: 2026-10-06.

## Problema

`user_type` em `tbl_contato_cliente` tem dois significados:

- **admin de conta cliente**: no Workspace, `admin` administra a própria conta (edita Agência, convida e promove pessoas, gerencia marcas, pede mudança de plano).
- **admin interno**: `admin_required`/`admin_required_api`/`is_admin()` em `aicentralv2/auth.py` protegiam ferramentas internas do CentralX só pelo `user_type`.

Resultado: qualquer admin de conta cliente passava pelos guards internos. Se o cadastro público criasse o primeiro contato como `admin`, toda conta pública passaria.

Havia mais um vetor: `session['is_centralcomm']` é calculado no login pelo `nome_fantasia` do cliente (`== 'CENTRALCOMM'`). O cadastro público grava o nome da pessoa como `nome_fantasia`; a tela Agência do Workspace e a solicitação de plano (`cadu_plan_checkout`) deixam o admin de conta editar `nome_fantasia`. Com isso, uma conta cliente podia virar "CentralComm" no login seguinte e passar por todas as rotas internas, inclusive as que já checavam `is_centralcomm`. O próprio teste `test_workspace_settings` gravava `trade_name='CentralComm'`.

## Como `is_centralcomm` é calculado (e por que agora é confiável)

- Login por formulário (`routes.py`, rota `/login`), SSO (`cadu_identity._start_flask_session`) e o context processor (`__init__.py`): cliente ativo com `nome_fantasia.upper() == 'CENTRALCOMM'`.
- Cadastro público: `is_centralcomm=False` fixo.
- Aceite de convite (`routes.py`, `aceitar_convite_submit`): `True`, mas a rota antes recusa convite de cliente que não seja CENTRALCOMM.
- O `login_required` de `routes.py` (ERP) revalida no banco a cada requisição.
- A sessão é um cookie Flask assinado: o cliente não consegue alterar `is_centralcomm` sem a `SECRET_KEY`.
- Não depende do domínio do e-mail. O login Google do realm `centralx` exige `@centralcomm.media`, mas a flag continua vindo do cliente.
- **Novo:** `auth.is_reserved_org_name()` reserva "CENTRALCOMM" sem diferenciar caixa, espaços, pontuação ou acento. Ele é aplicado em:
  - `services/onboarding_comercial.provisionar_conta_publica` (formulário e Google);
  - `cadu_workspace/routes.update_organization` (Agência, exceto sessão CentralComm);
  - `cadu_plan_checkout.request_plan_change` (dados de faturamento).

  Fica de fora o cadastro interno de clientes do ERP/CRM, que já é restrito à equipe CentralComm.

## Nova API de papéis (`aicentralv2/auth.py`)

| Função | Aceita |
|---|---|
| `is_account_admin()`, `account_admin_required`, `account_admin_required_api` | admin/superadmin de **qualquer** conta (categoria b) |
| `is_internal_admin()`, `is_admin()`, `admin_required`, `admin_required_api` | admin/superadmin **com** `session['is_centralcomm']` (categoria a) |
| `is_superadmin()`, `superadmin_required(_api)` | superadmin com `is_centralcomm` |
| `is_finance_admin()` (e `financeiro.permissions.is_finance_admin`) | `is_centralcomm` **e** (flag `is_finance_admin` ou admin) |

## Classificação

### (a) Internas do CentralX: passam a exigir CentralComm

Todas as rotas com `@admin_required`/`@admin_required_api` (152 ocorrências) são internas. Nenhuma rota de categoria (b) usava esses decoradores.

| Módulo | Rotas | Observação |
|---|---|---|
| `creative_modeling_routes.py` | 89 APIs `admin_required_api` (format lab, protótipos, registry de formatos, campanhas/produção, cenas, variações, desdobramentos, publicação, histórico, coleções públicas, `api_campaign_clients`) + 5 páginas `admin_required` (UX states, templates, specimen) | São montadas em `/parametros`, `/studio` e `workspace_brand_api`. Antes, um admin de conta cliente alcançava essas rotas também pelo Studio e pelo Workspace (ex.: `api_campaign_clients` lista clientes). As rotas usadas pelo cliente no Studio usam `studio_or_admin_required(_api)`, que no host Studio/Workspace aplica `login_required` e não muda |
| `camadas/routes.py` | 18 (APIs `/api/camadas/v2/*` + `html_stage_page`) | Ferramenta interna (templates em `parametros/`) |
| `training_studio/routes.py` | 14 (`/parametros/treinamentos*`) | Interno |
| `cadu_skills/routes.py` | 12 (`/skills/gestao*`, `/skills/api/gestao/*`) | Gestão interna (já redireciona para o host CentralX) |
| `integration_settings_routes.py` | 7 (`/parametros/integracoes`, `/parametros/api/integrations*`, `/parametros/prototipos-cadu*`) | Credenciais globais |
| `server_monitor_routes.py` | 2 (`/parametros/monitoramento`, `/parametros/api/server-monitor`) | Interno |
| `brevo_test_routes.py` | 2 (`/teste-brevo/*`) | Interno |
| `crm_v3_routes.py` | `/crm-v3/api/_debug/store` + detalhe de erro 500 (`is_admin` inline) | Interno |
| `creative_media/studio*.py`, `creative_format_lab/*`, `creative_analyzer/routes.py` | `studio_or_admin_required(_api)` | No host CentralX usa `admin_required(_api)`, agora só CentralComm. No host Studio/Workspace usa `login_required` (cliente) e não muda |
| `financeiro/*` | `finance_admin_required(_api)`, `is_finance_admin()` | Agora exige CentralComm |
| `dv360_routes._is_dv_session_admin` | escopo "todos os clientes" do DV360 | Agora `is_internal_admin()`. Admin de conta cliente fica no próprio cliente |
| `agent/permissions.has_global_commercial_access` | escopo comercial global do agente | Agora `is_internal_admin()` |
| `admin_migrations_routes.py` | `superadmin_required(_api)` | Agora exige superadmin CentralComm |
| `routes.py` (ERP: `/clientes`, `/planos`, `/contratos/*`, `/cadu/creditos*`, `/api/cliente/<id>/criar-plano-beta`, wasender etc.) | `login_required` local do `routes.py` | Já era só CentralComm (revalida no banco). Os testes inline `user_type in admin/superadmin` ficam atrás desse guard. Corrigido só o vetor do nome |
| `smart_planner/routes.py`, `cotacoes_routes.py` (`solicitacoes-planner`), `agent_v2` (melhorias de observabilidade) | `centralcomm_required` / checagem explícita de `is_centralcomm` | Já corretos |

### (b) Administrador de conta cliente: continua aceitando admin de conta

| Local | Uso |
|---|---|
| `cadu_workspace/routes._workspace_team_admin` (agora usa `is_account_admin()`) | Equipe, convites, promoção e remoção, Agência (`update_organization`) e demais telas de conta |
| `cadu_workspace/routes.py` ~7171, ~8595 | Gestão de marca (`can_manage_brand`) |
| `cadu_workspace/routes.py` ~10402-10458 | Proteção do último admin da conta |
| `cadu_family/repository.account_role` | Papel `admin` na organização (Planner, Reports, Studio e plano) |
| `cadu_plan_checkout.request_plan_change` | Só admin da organização pede mudança de plano |
| `cadu_workspace/agent_v2/routes.py` observabilidade (página e `runs/<id>`) | Escopo `current.client_id` (a própria conta) |
| `cadu_credit_alerts.py` | Admins da conta recebem alertas de saldo |
| `creative_format_lab/swap_routes.py:154` | Sessão sem tenant: na prática, só sessões internas. Cliente sempre tem `cliente_id` |

`account_admin_required(_api)` fica disponível para rotas novas de conta cliente. Hoje nenhuma rota precisava do decorador, porque o Workspace usa `_workspace_team_admin`.

## Riscos residuais

- Sessões antigas sem a chave `is_centralcomm` perdem acesso interno até um novo login. Login e SSO sempre gravam a chave.
- `nome_fantasia` continua sendo o critério de CentralComm. O ideal é um id fixo de cliente em configuração ou uma coluna `is_internal`, mas isso exige migração e ficou fora deste passo.
- Templates que mostram links internos por `session.user_type` ainda podem exibir um link para admin de conta. A rota responde 403/redirect.
