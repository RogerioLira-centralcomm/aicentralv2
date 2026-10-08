# Deploy: Portais do Planner (roteiro de 2026-10-08)

Tudo abaixo está commitado e **sem push**. O banco `.env` (DB_HOST remoto) já recebeu as migrações e os dados desta rodada; confirme se é o banco de produção antes de assumir que o deploy não precisa migrar.

## O que sobe
- **Código:** `frontend/planner` (compilado em `aicentralv2/static/cadu_planner/react/app.js` e `app.css`), `aicentralv2/cadu_planner/` (`portals.py`, `portal_signals.py`, `portal_estimates.py`, `portal_profiles.py`, `portal_ads.py`), `aicentralv2/cadu_family/routes.py`, `plans.py`, `catalog.py`.
- **Migrações novas (já no `migrations/ORDER.txt`, todas aditivas e idempotentes):**
  1. `add_cadu_planner_portal_estimates.sql` (popularidade, porte, demografia)
  2. `add_cadu_planner_portal_signals.sql` (formatos de anúncio e editorias)
  3. `extend_cadu_planner_portal_prints_kinds.sql` (tipo `editoria`)
- **Estáticos:** `static/images/portais/thumbs/` (200 ilustrações, ~21 MB) e `static/images/portais/prints/` (home, matéria e editoria aprovados). Sem eles a vitrine cai no ícone e no print antigo.

## Dados que já estão no banco (não recalcular no deploy)
Estimativas (Tranco) dos portais ativos, Top 10 nacional (`featured_rank` 1 a 10), perfis curados dos 50 principais, formatos de anúncio lidos, 98 portais desativados por DNS inválido, prints aprovados.

## Depois do deploy
1. `flask cadu_family estimate-planner-portals` (só se o banco for outro).
2. Abrir `/portais`, `/portais/1` (G1) e um regional; conferir miniatura, chips, formatos e galeria.
3. Conferir fontes (DejaVu/Liberation) só se voltar a usar compositor de imagem no servidor; hoje não é necessário.

## Rotina contínua (próxima etapa, não incluída)
Saúde semanal (DNS, HTTP), duas falhas seguidas antes de desativar, releitura mensal de formatos e prints, via timer do systemd como o `radar-due`.

## Pendências conhecidas
- 17 portais sem página de matéria ou de editoria nos prints internos; 3 capturas vazias descartadas.
- 359 portais sem `ads.txt` e sem programática seguem no ar como "Venda direta" (decisão: não desativar em massa).
- `tests/test_planner_nav_boot.py` falha desde antes desta rodada (template do plano público).
