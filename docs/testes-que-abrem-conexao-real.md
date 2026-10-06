# Testes que tentavam abrir conexão real com o banco

Medido em 2026-10-06 com `psycopg.connect` bloqueado durante a execução de cada teste. O guard autouse em
`tests/conftest.py` agora recusa essas conexões. Cada teste abaixo precisa simular `get_db`/`psycopg.connect`:
sem isso, ele dependia do banco apontado pelo `.env` (em produção, o remoto).

Total:      102 testes;       58 deles falham hoje.

| Arquivo | Testes |
|---|---|
| `tests/test_crm_v3.py` | 39 |
| `tests/test_workspace_project_sources.py` | 5 |
| `tests/test_workspace_account_usage.py` | 5 |
| `tests/test_planner_hero_backgrounds.py` | 4 |
| `tests/test_cadu_skills.py` | 4 |
| `tests/test_cadu_chat_history.py` | 4 |
| `tests/test_cadu_attachments.py` | 4 |
| `tests/test_workspace_project_lifecycle.py` | 3 |
| `tests/test_workspace_billing_integrations.py` | 3 |
| `tests/test_reports_alerts.py` | 3 |
| `tests/test_workspace_project_notes.py` | 2 |
| `tests/test_workspace_documents.py` | 2 |
| `tests/test_studio_maintenance.py` | 2 |
| `tests/test_reports_typesafe_assistance.py` | 2 |
| `tests/test_product_portals.py` | 2 |
| `tests/test_cadu_copy_ads.py` | 2 |
| `tests/test_cadu_agent_v2.py` | 2 |
| `tests/test_workspace_project_knowledge.py` | 1 |
| `tests/test_workspace_dock.py` | 1 |
| `tests/test_workspace_brands.py` | 1 |
| `tests/test_workspace_brand_system.py` | 1 |
| `tests/test_workspace_account_routes.py` | 1 |
| `tests/test_google_calendar_meet.py` | 1 |
| `tests/test_design_system_ads_postgres.py` | 1 |
| `tests/test_cadu_public_mcp.py` | 1 |
| `tests/test_cadu_mcp_studio_handoff.py` | 1 |
| `tests/test_cadu_foundation.py` | 1 |
| `tests/test_cadu_family.py` | 1 |
| `tests/test_cadu_chat_recovery.py` | 1 |
| `tests/test_auth_public.py` | 1 |
| `tests/test_agent.py` | 1 |
