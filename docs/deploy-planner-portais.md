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

## Canais atualizados só no banco (sem migração, sem código)
Em 2026-10-08 os canais abaixo foram completados direto na tabela `cadu_canais` do banco do `.env`, a partir de fontes públicas (links em `fontes_metricas.formatos` de cada um):
- **Uber, iFood, 99:** formatos, produtos, mensuração e diferenciais novos (Journey Ads, Ride Offers e Destination Offers; Instant Sampling e closed loop; 99Ads no app e OOH na frota). iFood passou a ter 60M usuários/mês em 1.500 cidades.
- **Amazon Ads / Marketplace:** Sponsored Products, Sponsored Brands e Amazon Stores (fonte de mercado, não oficial).
- **Logan:** reescrito com a página oficial logan.ai/pt-br/logan-ads (plataforma multicanal: OOH, rich media, CTV, vídeo in-app, áudio, WhatsApp, in-game, push); categoria passou a Programática; logo oficial em `static/images/canais/logan.svg` (esse vai no commit, o resto é banco).
- **Serasa Data (DMP):** produtos confirmados (Programa de Parcerias, audiências digitais, Serasa Ads). O nome "DMP", a base de 200M de perfis e as integrações com DSPs seguem do cadastro anterior, **sem fonte pública**.
- **Interativos:** descrição passou a refletir os 29 formatos do catálogo.

Se o banco do `.env` **não** for o de produção, esses UPDATEs precisam ser reaplicados lá (os textos estão neste roteiro e nas fontes de cada canal); se for, nada a fazer no deploy.

## Reaplicar em outro banco (snapshot por domínio e slug)
Se o banco de produção não for o do `.env` deste desenvolvimento, use o snapshot (`docs/planner-catalog-snapshot.json`, gerado por `scripts/export_planner_catalog_snapshot.py`):
1. Rodar as migrações do `ORDER.txt` (estimates, signals, prints kinds) no banco de produção.
2. Simular: `python scripts/apply_planner_catalog_snapshot.py docs/planner-catalog-snapshot.json` (não grava nada). Ele diz quantos portais têm o mesmo id nos dois bancos, quantos faltam e o que mudaria.
3. Aplicar: `... --apply`. Regras: portal nunca é reativado; descrição só dos portais com perfil curado; leituras só se o snapshot for mais novo; canais por slug; prints aprovados registrados a partir dos arquivos do repositório.
4. Se a simulação mostrar `ids_diferentes` maior que zero, as miniaturas e os prints (nomeados por id) precisam ser renomeados: aplicar com `--remap-files`.
5. Os arquivos (ilustrações e prints) continuam indo pelo deploy do repositório.
Para refazer o snapshot depois de novas mudanças: `python scripts/export_planner_catalog_snapshot.py docs/planner-catalog-snapshot.json`.

## Depois do deploy
1. `flask cadu_family estimate-planner-portals` (só se o banco for outro).
2. Abrir `/portais`, `/portais/1` (G1) e um regional; conferir miniatura, chips, formatos e galeria. Nos canais, abrir Logan, Uber e iFood (produtos em lista, fontes dos formatos, logos com cantos arredondados).
3. Conferir fontes (DejaVu/Liberation) só se voltar a usar compositor de imagem no servidor; hoje não é necessário.

## Rotina noturna (já no código, ativa no deploy)
`deploy/install_planner_portal_ads_timer.sh` (rodado pelo `deploy.sh`) instala o timer das 3h30: saúde e ads.txt em ciclo semanal (até 400 portais por noite; DNS inválido desativa só após duas noites seguidas), formatos de anúncio mensais (8 por noite, Firecrawl) e estimativas de popularidade mensais. Prints e ilustrações não são renovados automaticamente.

## Pendências conhecidas
- 17 portais sem página de matéria ou de editoria nos prints internos; 3 capturas vazias descartadas.
- Logo da Logan: wordmark oficial; confira o resultado no card.
- 359 portais sem `ads.txt` e sem programática seguem no ar como "Venda direta" (decisão: não desativar em massa).
- `tests/test_planner_nav_boot.py` falha desde antes desta rodada (template do plano público).
