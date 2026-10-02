# Planner co-construído + Radar de Oportunidades — plano mestre e preparação do ambiente

## Contexto

Hoje existem dois produtos de planejamento que não conversam:

- **Cadu Planner**, o produto para clientes.
  - Onde fica: `/familia/planner`, backend em `aicentralv2/cadu_planner/`, frontend em `frontend/planner/`.
  - O plano é montado à mão a partir dos catálogos. O Cadu não participa.
  - Os itens adicionados a partir dos catálogos caem em `cadu_planner_selections` e não no plano aberto.
  - As páginas de detalhe são genéricas (`CatalogDetail`).
  - O módulo `cadu_planner/channels.py`, que tem métricas, formatos, notícias e exemplos de anúncios por canal, não é usado por nenhuma tela.
  - A revisão de briefing por IA existe (`revisions.review_briefing`), mas nenhum botão a chama.
- **SmartPlanner legado**, o produto interno.
  - Onde fica: `/smart-planner`, código em `aicentralv2/smart_planner/`.
  - É onde está o botão "Novo planejamento".
  - Um pipeline de LLM entrega o plano pronto (`generator._run`): o usuário só assiste.

O objetivo é que **o plano seja co-construído com o Cadu**:
- O Cadu propõe uma seção de cada vez e explica o porquê.
- O usuário aceita, edita ou recusa cada proposta.
- O plano nunca chega pronto de uma vez.

Além disso:
- **Marcas e projetos do workspace** (`cx_clients.brand_profile` e `cadu_ci_projetos`, com o dossiê de "direção") passam a ser a base de contexto. Isso vale para o Planner e também para ferramentas que não são de descoberta: o bloco de Planejamento e o novo Radar.
- Nasce a ferramenta **Radar de Oportunidades®**, que segue a cadeia:
  - Sinal
  - Oportunidade, com nota Editorial e nota Paga
  - Plano orgânico, pago ou integrado
  - Criativos
  - Aprendizado
- A unidade central do sistema passa a ser o **opportunity_id**.

### Decisões tomadas com o usuário

- **Os dois planners em paralelo.** O Cadu Planner (clientes) e o SmartPlanner (interno) usam **o mesmo motor de co-construção**. Cada um mantém sua interface e suas tabelas, e os dois se ligam por um `plan_id` comum.
- **"Vitrines" são os catálogos do grupo Descobrir:** Canais, Audiências, Formatos, Interativos, Portais e Places.
- **Escopo desta entrega:** fundação (Fase 0) e Fase 1. O Radar e a co-construção completa entram nas fases seguintes, mas os contratos e tabelas deles já ficam criados agora.
- **Dados do Radar:**
  - Perplexity via OpenRouter (`insights_research.py`) para descoberta.
  - Firecrawl (`web_search.py`) para extração.
  - Benchmarks reais vindos das tabelas `cadu_reports_gads_*`.
  - Para canais sem histórico, o modelo estima e um revisor corta erros grosseiros. Toda estimativa sai como faixa P25/P50/P75 e marcada com a origem `model_estimate`.

### Atenção ao working tree

Há mudanças não commitadas em `cadu_connect/reports*` e `frontend/reports-v1/*`, vindas de outra frente de trabalho. **Não tocar nesses arquivos** e não incluí-los nos commits desta frente.

---

## Arquitetura alvo

```
Contexto (marca + projeto do workspace)
        │
        ├── Radar ─► Signal ─► Opportunity (Editorial / Paid / Geo) ─┐
        │                                                            ▼
        └── Novo planejamento (Planner cliente | SmartPlanner interno)
                     │
                     ▼
          Plan Workbench (motor de co-construção)
          seções: briefing → objetivo → praças → audiências → canais (papel)
                  → formatos/interativos → verba e cenários → criativos
          Cadu propõe (proposal) ─► usuário aceita/edita/recusa ─► revisão++
                     │
                     ▼
            Benchmark Engine (matemática: CPM → impressões → alcance, em faixas)
                     │
                     ▼
           Studio (matriz criativa) → Campaigns → Reports → aprendizado
```

### Regras do motor de co-construção

O padrão vem do Flow Blueprint (`frontend/reports-v1/flowBlueprintApply.js` e `cadu_connect/reports_flow_versions.py`).

- **Seções com estado.** Cada seção do plano tem um destes estados: `vazia`, `proposta`, `aceita`, `editada` ou `travada`.
- **O Cadu nunca escreve direto no plano.** Ele grava uma *proposal* com o payload da seção, a justificativa, as evidências e a `base_revision`. A proposta só entra no plano quando o usuário decide.
- **Seção editada ou travada pelo usuário não é sobrescrita.** Uma proposta nova para ela vira sugestão de diferença.
- **Concorrência otimista.** O plano ganha uma coluna `revision`, e toda escrita confere a `expected_revision` (já é o padrão de `reports_flow_versions` e `artifacts.patch_artifact`).
- **Ordem de execução de cada turno do Cadu:**
  1. Reserva créditos com `CaduCreditConnector.authorize`, como em `revisions.py`.
  2. Chama o proposer da seção pelo OpenRouter (`services/openrouter_service.chat_completion`).
  3. Passa o resultado pelo revisor.
  4. Grava a proposta e o evento na linha do tempo.
- **O Cadu pergunta antes de propor quando falta informação.** Exemplo: "qual praça é prioridade?" quando não há geografia no briefing.

---

## Fase 0 — Fundação (nesta entrega)

### 1. Documento do plano no repositório

Criar `docs/planner-cobuild-radar-plan.md` com este plano. Deve incluir os contratos de `Signal`, `Opportunity`, `Proposal` e `Benchmark`, os scores com seus pesos e as releases R1 a R3.

### 2. Migrações

Seguir o padrão do repo: arquivo `.sql` aditivo com `IF NOT EXISTS` mais um runner `run_*.py` que confere as colunas, como em `migrations/run_add_cadu_conversations_v2.py`.

**`migrations/add_cadu_planner_cobuild.sql`**
- Alterações em `cadu_planner_plans`:
  - Novas colunas `revision INT DEFAULT 0` e `workbench JSONB DEFAULT '{}'` (estado por seção).
  - Nova coluna `source TEXT DEFAULT 'manual'`, com os valores `manual`, `radar` e `smart_planner`.
  - Nova coluna `opportunity_id UUID NULL`.
- Tabela nova `cadu_planner_proposals`, com as colunas:
  - id, plan_id, section, payload jsonb, rationale, evidence jsonb, questions jsonb
  - status (`pending`, `accepted`, `partial`, `rejected` ou `superseded`)
  - base_revision, model, cost, created_at, decided_by, decided_at
- Tabela nova `cadu_planner_plan_events`, que guarda a conversa e a linha do tempo do plano. Colunas: plan_id, role (`user` ou `cadu`), kind, body, proposal_id, created_at.
- Alteração em `cadu_smart_planner_sessions`: nova coluna `planner_plan_id UUID NULL`, que é a ponte para o plano comum.

**`migrations/add_cadu_radar.sql`**
- `cadu_radar_runs`: client_id, brand_ref, project_ref, status, custos, created_at.
- `cadu_radar_signals`, com os campos do Signal:
  - headline, description, source, source_type, url
  - published_at, detected_at
  - entities, topics, geography, industry, keywords
  - evidence, confidence, velocity
  - verification jsonb e run_id
- `cadu_radar_opportunities`:
  - client_id, brand_ref, project_ref, title, thesis
  - editorial_score, paid_score, geo_scores jsonb
  - quadrant (`conteudo`, `midia`, `integrada` ou `ignorar`)
  - penalties jsonb
  - status (`nova`, `salva`, `em_plano` ou `descartada`)
  - signal_ids, created_at
- `cadu_media_benchmarks`:
  - channel, objective, geo_level, geo, metric (cpm, cpc, ctr, cpa ou frequency)
  - p25, p50, p75, sample_size
  - source (`history` ou `model_estimate`), reviewed, period, updated_at

### 3. Esqueleto do backend

Criar os módulos com funções e contratos, sem lógica de LLM ainda.

- **`aicentralv2/cadu_planner/workbench.py`**
  - `SECTIONS`, `section_state()` e `apply_proposal(plan, proposal, accepted_fields, expected_revision)`.
  - Regras de proteção de seção editada ou travada.
  - `record_event()`.
- **`aicentralv2/cadu_planner/proposals.py`**
  - CRUD de propostas.
  - `propose_section()`: neste momento é só um stub que devolve `NotImplemented` quando a flag está desligada.
- **`aicentralv2/cadu_planner/context.py`**
  - `load_plan_context(client_id, brand_ref, project_ref)`.
  - Reúne `brand_profile` (público, posicionamento, personas, concorrentes e `campaign_opportunities`) e o dossiê de direção do projeto (`project_context_service`).
  - Devolve um dicionário enxuto e com limite de tamanho, que serve de contexto para o Planner e para o Radar.
- **`aicentralv2/cadu_radar/`**, um pacote novo com estes módulos:
  - `contracts.py`, com as dataclasses `Signal`, `Opportunity`, `GeoScore` e `ScoreBreakdown`.
  - `scoring.py`, com pesos e penalizadores determinísticos e já testáveis. Pesos Paid: ICP 20, audiência 15, geo 15, momentum 10, criativo 15, eficiência 15, canais 10. A função `quadrant()` decide o quadrante.
  - `pipeline.py`, que só declara as etapas `discover → extract → verify → cluster → judge`.
  - `repository.py`.
- **`aicentralv2/cadu_planner/benchmarks.py`**
  - `reach_estimate(budget, cpm_range, frequency_range)` devolve faixas (impressões = verba ÷ CPM × 1000; alcance = impressões ÷ frequência).
  - `scenarios(budget_hint)` devolve os cenários Teste, Recomendado e Amplificação.
  - Reaproveitar `smart_planner/estimates.py` (`calculate_estimates` e `_channel_scenarios`), extraindo-o para um núcleo comum em vez de duplicar o código.
- **Feature flags** em `config.py`: `CADU_PLANNER_COBUILD_ENABLED` e `CADU_RADAR_ENABLED`, ambas `False` por padrão.

### 4. Testes de fundação

Seguir o padrão do repo: pytest com monkeypatch e sem banco real.

- `tests/test_cadu_radar_scoring.py`: pesos, penalizadores e quadrante.
- `tests/test_cadu_planner_benchmarks.py`: faixas de alcance e cenários.
- `tests/test_cadu_planner_workbench.py`: aplicar uma proposta respeitando edições, travas e `expected_revision`.

---

## Fase 1 — Planner: interface, detalhes e contexto (nesta entrega)

### 1. Navegação nova

Arquivo: `frontend/planner/main.jsx`, função `sidebarGroups`.

- Início
- **Planejamento:** Novo planejamento, Planos
- **Oportunidades:** Radar. Só aparece com `CADU_RADAR_ENABLED`; até lá a página mostra um estado "em breve" com a explicação do conceito.
- **Descobrir:** Canais, Audiências, Formatos, Interativos, Portais, Places
- **Entregas:** Docs

O item "Novo plano" passa a se chamar **"Novo planejamento"**, alinhado com o SmartPlanner.

### 2. Seletor de contexto (marca e projeto)

- **Componente:** `frontend/planner/ContextBar.jsx`, fixado no topo de Planejamento, Radar e das páginas de detalhe.
- **Dados:** via `/familia/api/entities` e `project-brand-links` do `cadu_family`, porque o Planner roda no host `planner.*` e não deve chamar `/workspace/api` de outro host.
- **Persistência:** a escolha fica na sessão do Planner. O plano já tem `brand_ref` e `project_ref`.
- **Uso:**
  - Pré-preenche o "Novo planejamento" com dados de `context.load_plan_context` (público, praça, objetivo sugerido).
  - Nas vitrines, ordena os resultados por afinidade, com o selo "combina com {marca}". A afinidade é uma regra simples por categoria e público e pode ser refinada depois.

### 3. Páginas de detalhe dedicadas

Hoje existe um único `CatalogDetail` genérico. Ele vira um componente por tipo:

- **`ChannelDetail.jsx`**
  - Usa `cadu_planner/channels.py`, que hoje está sem uso: `detail`, `formats`, `news`, `related_media` e `activation_concepts`.
  - Mostra cabeçalho com logo e cor, métricas de alcance e demografia, formatos disponíveis, exemplos de anúncios aprovados, notícias e "papel típico no plano" (alcance, frequência, intenção, contexto ou presença local).
  - Na Fase 4 a página ganha benchmarks P25/P50/P75.
- **`AudienceDetail.jsx`**
  - Usa os grupos de `AUDIENCE_DATA_GROUPS` (`catalog.py:23`), aplicando antes `client_projection`.
  - Mostra plataformas, tamanho, categorias e canais onde a audiência é comprável.
- **`FormatDetail.jsx`**
  - Mostra especificações, canais compatíveis, objetivo recomendado e exemplos.
- **`InteractiveDetail.jsx`**
  - Igual ao formato, com mecânica de interação, métricas de engajamento e uma prévia.
- **Backend:**
  - Ampliar `catalog.client_detail()` com as relações: formatos do canal, canais do formato e plataformas da audiência.
  - Ajustar a rota `/familia/planner/<kind>/<id>` (`cadu_family/routes.py:961`) para mandar `view` por tipo.
- **Layout comum** (`DetailLayout`), com estes blocos:
  - Herói
  - Abas "Visão geral", "Especificações", "Onde usar" e "Relacionados"
  - Barra lateral fixa com "Adicionar ao plano"

### 4. Corrigir "adicionar ao plano"

- **O problema:** as vitrines não recebem o plano ativo, então o item vai para `cadu_planner_selections` e não para o plano.
- **A correção:**
  1. Os links "Adicionar" do `PlanDetail.jsx:124` passam a levar `?plan=<id>`.
  2. O `_render_planner` coloca `boot.plan` quando recebe `plan`. Também guarda um "plano ativo" na sessão, exibido no `ContextBar`.
  3. Com isso, `usePlanSelection` chama `/plans/<id>/items/toggle`.
- **Migração das seleções soltas:** o usuário pode trazê-las para um plano com um botão.

### 5. Revisão visual do Planner

- **`PlannerHome`:**
  - "Continuar planejamento" com o progresso das seções do workbench.
  - Bloco de oportunidades do Radar, vazio até a Fase 3.
  - Atalhos de marca e projeto.
- **`PlanDetail`** muda para um layout de workbench:
  - Coluna esquerda: as seções do plano com seus estados.
  - Centro: a seção selecionada.
  - Direita: o painel do Cadu. Fica desabilitado com a flag desligada e mostra "o Cadu vai montar isto com você".
  - Nesta fase o painel já mostra o checklist `readiness`.
  - O botão "Revisar briefing com o Cadu" é ligado ao endpoint `/briefing-review`, que já existe e hoje está sem uso.
- **Componentes:** usar os do design system (`frontend/cadu-design-system/`) e manter `planner.css` com tokens. Testar em largura de celular.

### 6. Build e verificação

- Build com `npm run build:planner`. A saída vai para `aicentralv2/static/cadu_planner/react/`.
- Validar no navegador com `preview_start`. Testes de frontend em node seguem o padrão de `tests/frontend/*.test.mjs`.

---

## Fases seguintes (contratos já criados agora; implementação depois)

### Fase 2 — Motor de co-construção + "Novo planejamento" nos dois planners

**Proposers por seção**, chamados pelo OpenRouter e com os modelos configuráveis como em `smart_planner/models.py`:
- Briefing, que reaproveita `revisions.review_briefing`.
- Objetivo
- Praças
- Audiências, buscando em `catalog.query`
- Canais com papel
- Formatos
- Verba, que usa `benchmarks`
- Criativos

**Endpoints novos:**
- `POST /familia/api/planner/plans/<id>/cadu/turn`: a mensagem do usuário ou "proponha a próxima seção". Responde em SSE com perguntas e propostas.
- `POST .../proposals/<pid>/decision`: aceitar, aceitar em parte ou recusar.

**Ligação com o SmartPlanner:**
- O "Novo planejamento" interno cria um `cadu_planner_plans` com `source='smart_planner'` e grava o `planner_plan_id` na sessão.
- O pipeline do `generator.py` é quebrado em proposers chamáveis um a um: snapshot/evidências viram contexto, `strategy_core` vira a proposta de objetivo e praças, `one_page` vira o consolidado final.
- O modo "gerar tudo" continua existindo, mas passa a gerar *propostas* para revisão, não o plano final.

**MCP:** criar `planner.propose_section` em `cadu_workspace/mcp/tools/planner.py`, para que o chat do workspace possa co-construir também.

### Fase 3 — Radar de Oportunidades R1

**Pipeline**, rodando em uma thread daemon com lease no banco, como em `long_jobs`:
1. `discover`: Perplexity via `insights_research`.
2. `extract`: Firecrawl via `web.read`.
3. `verify`: um segundo modelo pelo OpenRouter, com a missão de tentar refutar a oportunidade.
4. `signals`
5. `cluster`
6. `judge`: calcula as notas Editorial, Paid e Geo.

**Telas:**
- Lista de oportunidades com a matriz Orgânico × Pago.
- Detalhe com as evidências e o resultado da verificação.
- Botão **"Criar planejamento a partir desta oportunidade"**, que cria o plano com `source='radar'` e `opportunity_id`.

**Custos:** créditos via `cadu_cost_catalog` (já tem entradas de perplexity e firecrawl).

### Fase 4 — Media Opportunity Planner (R2)

**Benchmark Engine:**
- Um job agrega CPM, CPC, CTR e CPA a partir de `cadu_reports_gads_*` e das métricas de campanha (`campanha_pi_metrics.py`), em P25/P50/P75 por canal, objetivo e praça.
- Canais sem histórico (DOOH, Spotify, streaming) recebem estimativa do modelo, passam por um revisor com limites de sanidade e ficam marcados `model_estimate`.

**Matemática:**
- Três cenários: Teste, Recomendado e Amplificação.
- Distribuição da verba com o papel de cada canal.
- Alcance, impressões e frequência sempre em faixa.

**Telas:** Geo Opportunity Score por praça.

### Fase 5 — Ciclo fechado (R3)

- Matriz criativa: a combinação hooks × visuais × CTAs é enviada ao Studio.
- Os resultados de Reports voltam e são comparados com a previsão, ligados pelo `opportunity_id`.
- A partir disso o sistema aprende quais tipos de oportunidade dão resultado.

---

## Arquivos críticos

**Backend:**
- `aicentralv2/cadu_planner/plans.py`, `catalog.py`, `channels.py`, `pages.py`, `revisions.py`
- `aicentralv2/cadu_family/routes.py`: `_render_planner` (:1313), rota de detalhe (:961), API do planner (:561–:935)
- `aicentralv2/smart_planner/generator.py` e `estimates.py`
- Novos: `cadu_planner/workbench.py`, `proposals.py`, `context.py`, `benchmarks.py` e o pacote `cadu_radar/`

**Frontend:**
- `frontend/planner/main.jsx`, `PlanDetail.jsx`, `PlansPages.jsx`, `Catalog.jsx`, `PlannerUi.jsx`, `api.js`, `planner.css`
- Novos: `ContextBar.jsx`, `details/*Detail.jsx`, `Radar.jsx` (placeholder)

**Template:** `aicentralv2/templates/cadu_planner/react.html`, que recebe bootstrap com plano ativo, contexto e flags.

**Migrações:** `migrations/add_cadu_planner_cobuild.sql`, `migrations/add_cadu_radar.sql` e seus runners.

## Verificação

1. **Migrações:** rodar com `.venv/bin/python migrations/run_add_cadu_planner_cobuild.py` e `run_add_cadu_radar.py` no banco local e conferir as colunas.
2. **Testes:** `.venv/bin/python -m pytest tests/test_cadu_radar_scoring.py tests/test_cadu_planner_benchmarks.py tests/test_cadu_planner_workbench.py tests/test_cadu_planner*.py`. Já existem cerca de 125 falhas antes desta frente; comparar só os testes tocados.
3. **Frontend:** `npm run build:planner`, depois os testes node do planner.
4. **Navegador:** subir o dev server com `preview_start` e percorrer:
   - A sidebar nova.
   - O detalhe de canal, de audiência, de formato e de interativo.
   - Adicionar um item a partir da vitrine com `?plan=` e confirmar que ele aparece no plano.
   - O seletor de marca e projeto pré-preenchendo o "Novo planejamento".
   - O botão "Revisar briefing com o Cadu".
   - A tela em largura mobile.
   - Uma captura de tela como prova.
5. **SmartPlanner:** `/smart-planner/` continua funcionando sem mudanças nesta fase; a ponte só entra na Fase 2.

---

## Estado da preparação (2026-10-02)

Feito nesta entrega (Fase 0 + Fase 1):

| Peça | Onde |
|---|---|
| Migrações (não aplicadas ainda) | `migrations/add_cadu_planner_cobuild.sql`, `migrations/add_cadu_radar.sql`, registradas no `deploy.sh` |
| Flags | `CADU_PLANNER_COBUILD_ENABLED`, `CADU_RADAR_ENABLED` em `aicentralv2/config.py` (desligadas) |
| Motor de co-construção (puro, testado) | `aicentralv2/cadu_planner/workbench.py` |
| Propostas e linha do tempo | `aicentralv2/cadu_planner/proposals.py` (`propose_section` ainda sem proposers) |
| Contexto marca/projeto | `aicentralv2/cadu_planner/context.py` |
| Benchmark Engine (faixas) | `aicentralv2/cadu_planner/benchmarks.py` (SmartPlanner reaproveita `impressions`/`reach`) |
| Radar: contratos, notas, pipeline (stub), leitura | `aicentralv2/cadu_radar/` |
| Fichas de catálogo | `catalog.channel_profile`, `audience_profile`, `format_profile`, `channel_roles` |
| API | `/familia/api/planner/context`, `/plans/<id>/workbench`, `/plans/<id>/proposals/<pid>/decision`, `/plans/<id>/sections/<s>/propose` (501 até a Fase 2), `/radar/opportunities` |
| Páginas | `/radar`; detalhe de canal, audiência e formato/interativo com views próprias; plano ativo via `?plan=` ou sessão |
| Frontend | `frontend/planner/ContextBar.jsx`, `PlanWorkbench.jsx`, `Radar.jsx`, `details/*` |
| Testes | `tests/test_cadu_radar_scoring.py`, `test_cadu_planner_benchmarks.py`, `test_cadu_planner_workbench.py` |

### Contratos

**Proposal** (`cadu_planner_proposals`): `section` ∈ briefing, objetivo, pracas, audiencias, canais, formatos, verba, criativos. O `payload` usa as chaves do briefing (`budget`, `period`, `geography`, `kpis`, `notes`) e `objective`. Seções de catálogo usam `add: [{kind, resource_id}]`. Os demais campos (`roles`, `scenarios`, `big_idea`, `messages`, `matrix`) vão para `workbench.sections[section].value`. Decisões: `accepted`, `partial` (com `fields`) e `rejected`, sempre com `expected_revision`.

**Signal / Opportunity / GeoScore / ScoreBreakdown**: `aicentralv2/cadu_radar/contracts.py`.

**Pesos**:
- Editorial: ICP 20, marca 15, território 15, autoridade 15, cultura 10, timing 15, conversa 10.
- Paga: ICP 20, audiência 15, geo 15, momentum 10, criativo 15, eficiência 15, canais 10.
- Geo: interesse 20, audiência 15, base própria 15, histórico de mídia 10, concorrência 10, cobertura 10, contexto 10, objetivo de negócio 10.
- Quadrante alto ≥ 70.
- Penalidades com teto: saturação 15, custo 15, baixa confiança 20, restrição de marca 30, risco reputacional 30, pouca evidência 20.

**Benchmark**: P25/P50/P75 por canal, objetivo, praça e métrica, com `source` = `history` | `model_estimate` e `reviewed`.

### Próximo passo (Fase 2)

1. Aplicar as migrações em homologação.
2. Implementar os proposers por seção em `proposals.propose_section`.
3. Ligar a flag `CADU_PLANNER_COBUILD_ENABLED`.
4. Criar a ponte com o SmartPlanner (`planner_plan_id`).
