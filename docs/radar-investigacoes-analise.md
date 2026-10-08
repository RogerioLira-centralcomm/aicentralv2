# Radar como investigação: o que existe e o que falta

Análise de 2026-10-08, a partir do mockup "Meus radares" (vitrine sem sidebar e sem banner) e da direção "radar = investigação com várias execuções". Substitui a fase 0 de `docs/radar-ui-refatoracao.md` (sidebar + detalhe), que já está em `main`.

## 1. Modelo de dados hoje

| Conceito | Tabela | Observação |
|---|---|---|
| Execução | `cadu_radar_runs` | Uma por busca. `focus`, `brand_ref`, `project_ref`, `params` (praça, janela), `status`, `steps`, `cost.tokens`, `trigger` (manual/agendado), `watch_id`, `created_by` |
| Radar recorrente | `cadu_radar_watches` | `name`, `focus`, `params`, `frequency` (1–3x/dia, horários fixos 08h / 08h+17h / 08h+13h+18h), `status` (ativo/pausado/sem_credito), `next_run_at`, `last_run_at` |
| Sinal | `cadu_radar_signals` | Por execução. `headline`, `description`, `source`, `url`, `published_at`, `verification` (tier, url_status). `saved_at` (v3, não aplicada) |
| Ângulo | `cadu_radar_opportunities` | Por execução. `title`, `thesis`, `score_breakdown` (rank, why_now, formats, channels, window, buzz), `status` (nova/salva/em_plano/descartada), `signal_ids` |
| Plano vindo do Radar | `cadu_planner_plans` | `source='radar'`, `opportunity_id`; `signal_id` (v3, não aplicada) |

**Conclusão:** a "investigação" já existe para os radares recorrentes (`watch` + suas execuções). O que não existe é tratar a **busca avulsa** como o mesmo tipo de objeto, nem nada sobre **leitura** (o que a pessoa já viu) ou **comparação entre execuções**.

### Falhas do modelo atual que afetam a nova tela

1. **Criar radar recorrente gera dois objetos.** O wizard dispara uma busca manual e depois cria o `watch`; a busca fica sem `watch_id`. Na vitrine apareceriam dois cards para o mesmo radar. *Correção: o watch "adota" a busca que nasceu com ele.*
2. **Sinais não têm impressão digital.** Cada execução repete as mesmas notícias. Para "3 novos sinais" é preciso comparar por URL normalizada (já previsto no `radar-v2-plano.md`, item 4). Sem isso, toda execução parece cheia de novidades.
3. **Ângulos são regerados a cada execução.** Não há "ângulo atualizado", só ângulo novo com outro título. Comparar por título é frágil (o modelo reescreve). Primeira versão: título normalizado; depois, fingerprint semântico.
4. **Watch recém-criado sem execução não aparece** (a vitrine se monta pelas execuções). Raro com a correção do item 1, mas precisa de um card "Aguardando primeira execução".
5. **Execução agendada roda em thread do gunicorn / CLI**; `lease_until` não é usado. Execução morta fica "em andamento" até 20 min. Afeta o estado "Em execução" na vitrine.
6. **Sem nome editável.** O título do watch é o tema truncado; busca avulsa nem tem nome. O mockup mostra títulos curtos ("Consumo consciente no fim do ano") e uma descrição separada.
7. **Sem categoria/segmento** (Varejo, Energia, Tecnologia no mockup). Hoje só existe a marca. Derivar da marca (segmento do cadastro do Workspace) ou pedir no wizard.
8. **Sem imagem por radar.** O mockup tem miniatura. Não há fonte de imagem.

## 2. Tela a tela

### Vitrine "Meus radares"

| Elemento do mockup | Hoje | Falta |
|---|---|---|
| Cabeçalho compacto, sem sidebar, sem banner | Sidebar + cards (fase 0) | Refazer layout |
| Abas Todos / Agendados / Em andamento / Concluídos / Favoritos com contagem | Filtros na sidebar | Abas; Favoritos precisa de estado por pessoa |
| Filtro "Não visualizados" com contador | — | Estado de leitura por pessoa |
| Busca, filtro de marca, ordenar (Mais recentes / Novidades desde minha última visita) | Só no feed antigo | Implementar sobre a lista de radares |
| Card: estado da investigação (Concluído, Programado, Em execução, Falha) | Status da execução | Derivar do watch + última execução |
| Card: estado de leitura (Novo, Novos resultados, Sem novidades, Atenção) | — | Estado por pessoa + comparação entre execuções |
| Card: "3 novos sinais · 1 novo ângulo" | — | Comparação por URL/título |
| Card: "Diário · 08h", última e próxima execução | Dados existem no watch | Só exibir |
| Card: métricas sinais / fontes / ângulos / no plano | Sinais, ângulos, em plano | Fontes verificadas por execução (consulta) |
| Card: favoritar (estrela), menu ⋯ (pausar, retomar, apagar, editar) | Pausar/apagar em outra tela | Menu no card; editar frequência e nome |
| Card: miniatura | — | Decisão de imagem (ver §4) |
| Faixa "Radares automáticos e agendados" | — | Texto + ação (abre o wizard com "me avise" ligado) |

### Página interna de um radar (pendente no mockup)

| Elemento | Hoje | Falta |
|---|---|---|
| Abas Visão geral, Sinais, Ângulos, Evidências, Aplicações | Existem (fase 0), sobre **uma** execução | Passar a abrir pelo radar, mostrando a última execução |
| Aba Histórico de execuções | — | Lista com data, sinais, novos, ângulos, novos, tokens, falhas; abrir uma execução antiga; comparar duas |
| "O que mudou desde sua última visita" no topo | — | Diff entre a execução atual e o que a pessoa já tinha visto; atalhos para os novos sinais e ângulos |
| Marcar como visto ao abrir | — | Endpoint de leitura |
| Programação no cabeçalho (frequência, próxima execução, pausar) | Só na tela antiga | Controles no cabeçalho |
| Planos relacionados, sinal → plano | Feito (`a91577221`) | Nada; passa a agregar todas as execuções |
| Metodologia | Aba própria | Vira detalhe de cada execução no Histórico |

### O que sai

- Barra lateral e feed global (Em alta, Recentes, Salvos) da fase 0. "Salvar notícia" não aparece no mockup novo. Decidir: remover, ou manter salvar dentro da aba Sinais.
- Tela antiga `/radares` (já redireciona para a vitrine).
- `feed.py` e `PUT /radar/signals/<id>/saved` ficam sem uso se o feed global sair.

## 3. O que precisa ser construído

**Backend**
1. Migração `add_cadu_radar_v4.sql`: `cadu_radar_user_state (client_id, user_id, subject_id, last_seen_at, favorite)`. *(rascunho escrito, não commitado)*
2. `cadu_radar/radars.py`: agrupar execuções por radar, estados, novidades por URL/título, histórico com novidades por execução. *(rascunho escrito, sem testes)*
3. Endpoints: `GET /radar/radars`, `GET /radar/radars/<id>`, `POST …/seen`, `PUT …/favorite`. *(rascunho escrito)*
4. Watch adota a busca de criação (`run_id` no `POST /radar/watches`). *(rascunho escrito; falta o front enviar)*
5. Nome e descrição editáveis do radar (`PATCH` do watch; busca avulsa ganha `name` no run).
6. Fingerprint de sinal gravado na execução (URL normalizada) para a comparação não depender de recalcular.
7. Execuções presas: usar `lease_until` e expirar.

**Frontend**
1. Vitrine: cabeçalho, abas, busca, marca, ordenação, cards em 3 colunas, estados, favoritos, menu ⋯.
2. Página do radar: cabeçalho com programação, "O que mudou", abas incluindo Histórico, marcar visto.
3. Wizard: enviar `run_id` ao criar o radar recorrente; ao fim, abrir o radar (não a execução).
4. Remover sidebar, feed global e telas mortas.

**Testes**
- Estados de leitura e investigação (tabela de casos), novidades por URL/título, adoção da busca, permissões por cliente/pessoa.
- Harness visual com dados de exemplo (como nas rodadas anteriores), já que a rota local dá 404.

## 4. Decisões pendentes

1. **Miniatura do card.** (a) imagem da notícia principal da última execução (og:image, precisa capturar no pipeline); (b) capa gerada pelo Studio uma vez por radar; (c) ícone/cor por segmento. Recomendo (c) agora e (a) quando o pipeline capturar imagem.
2. **Categoria (Varejo, Energia…).** Recomendo usar o segmento da marca no Workspace; se não houver, não mostrar.
3. **"Novo sinal".** Recomendo URL normalizada nesta etapa. Mesma notícia em outro veículo conta como novo até existir fingerprint de fato.
4. **Salvar notícia.** Recomendo manter dentro da aba Sinais e remover o feed global.
5. **Estado por pessoa ou por cliente?** O mockup fala em "minha última visita": recomendo por pessoa (favorito também).
6. **Busca avulsa vira radar recorrente depois?** Recomendo ação "Programar" no menu ⋯ (cria o watch e adota a execução).

## 4b. O que os 6 mockups de 2026-10-08 acrescentam

Telas: vitrine, Novo radar, radar (visão geral), lista de Sinais, página de um sinal, página de um ângulo.

### Confirmam a análise (sem trabalho a mais)

- Vitrine sem sidebar, cards em 3 colunas, estados separados ("Novo resultado", "Em execução", "Concluído", "Atualizado", "Programado", "Atenção") e "+3 novos sinais · +1 novo ângulo".
- Cabeçalho do radar com segmento, "Atualizado hoje, 08:15" e "Programado diariamente às 07h".
- Faixa "Novos resultados desde sua última visita · 3 novos sinais · 1 novo ângulo · 2 evidências atualizadas" com "Ver novidades".
- Abas Visão geral, Sinais, Ângulos, Evidências, Aplicações, Histórico.

### Mudam decisões anteriores

| Ponto | Antes | Mockup |
|---|---|---|
| Filtros da vitrine | Abas Todos/Agendados/… | Busca + selects (marcas, status, ordenação). Mais simples: usar selects |
| "Atenção" | Só falha da execução | Também falha parcial: "Falha em 2 fontes" (links quebrados na verificação, `url_status = quebrado`). Já temos o dado |
| KPIs do radar | Números absolutos | Com delta: "24 sinais (+3 novos)", "8 fontes (2 novas)", "4 ângulos (1 novo)", "5 aplicações em planos (2 em andamento)" |
| Ângulo novo | Só contagem | Etiqueta "Novo" no card do ângulo |
| Sinais | Aba com cartões | Tabela com seleção, fonte, data, **relevância (Alta/Média)**, filtros de tema e fonte, ordenação |

### Telas e dados novos (não estavam na análise)

1. **Página de um sinal** (`Radar / <radar> / Sinais / <sinal>`): resumo, **principais pontos** (lista), **citação** da fonte, abas Contexto / Evidências / Ângulos relacionados; lateral com temas relacionados, ângulos que ele sustenta e outros sinais do tema; ação **"Adicionar aos ângulos"**.
   - Hoje o sinal guarda só título, 1 frase (`description`), fonte, link e data. **Principais pontos e citação não existem**: exigem guardar o texto lido (o Firecrawl já lê a página) e uma extração curta por sinal (custo de modelo por sinal; medir no Lab).
   - "Temas relacionados" exige palavras-chave por sinal (mesma extração).
   - "Adicionar aos ângulos" = editar `signal_ids` do ângulo à mão (novo endpoint).
2. **Página de um ângulo** (`Radar / <radar> / Ângulos / <ângulo>`): tese, por que agora, **janela de oportunidade com prioridade**, formatos recomendados; lateral com sinais que sustentam e **aplicações no planejamento** (planos ligados, com tipo: plano de mídia, estratégia, conteúdo); abas Sinais (8), Evidências (5), Aplicações, **Discussão**; ação **"Adicionar ao plano"**.
   - Tese, por que agora, janela, formatos e sinais: **já existem** (`score_breakdown`, `signal_ids`).
   - **"Adicionar ao plano" existente** (hoje só cria plano novo): falta escolher um plano e anexar o ângulo ao briefing dele.
   - **Discussão** (comentários por ângulo): não existe nada no Planner; deixar para depois.
3. **Resumo executivo** com "Gerar resumo em apresentação": resumo já estava previsto (fase 1); **gerar apresentação** é exportar para o Studio/slides. Depois.
4. **Relevância do sinal (Alta/Média)**: sem nota hoje. Proposta sem custo: Alta quando o sinal sustenta algum ângulo **ou** vem de fonte nível A; Média no resto. Nota de verdade só com o scoring do Radar v2.
5. **Novo radar em 4 passos** (Tema e contexto, Objetivo, Fontes e filtros, Revisão): o wizard atual tem Marca, Conceito, Onde e quando, Revisão.
   - **Contexto (texto livre)**, **Objetivo** e **Territórios de busca** (Mercado, Concorrentes, Comportamento, Sazonalidade, Regulação, Mídia e tecnologia) **não existem** em `clean_params` (só praça e janela). Os territórios mudariam o prompt da busca: medir no Lab antes de ir ao produto.
   - O título curto do radar (separado do tema longo) também nasce aqui.
6. **Evidências atualizadas / fontes novas**: comparar fontes por domínio entre execuções (mesmo método dos sinais).

### Padrões fixados (decisão de 2026-10-08)

- **Vitrine:** sem abas; busca e filtros controlam a lista.
- **Cadastro:** um formulário em seções na mesma página (não um passo a passo). A programação diária é opcional e fica no próprio cadastro (cria o radar recorrente e adota a primeira execução).
- **Radar aberto:** abas horizontais pelos conteúdos reais da investigação, com a última execução sempre visível no cabeçalho.
- **Sinais:** tabela, não cards.
- **Ângulos:** página editorial para a tese, ligada às evidências.

### Ordem revista

1. Backend de radares + leitura + favoritos + adoção da busca (rascunho atual, com testes).
2. Vitrine nova (selects, estados, novidades, "Falha em N fontes").
3. Página do radar: faixa de novidades, KPIs com delta, etiqueta "Novo", Histórico.
4. Sinais em tabela com relevância derivada; páginas de sinal e de ângulo com o que já existe (sem principais pontos/citação); "Adicionar ao plano" existente; "Adicionar aos ângulos".
5. Pipeline (medido no Lab): resumo executivo, principais pontos e citação por sinal, temas, territórios e objetivo no wizard.
6. Depois: Discussão, apresentação, miniaturas.

## 5. Ordem sugerida (versão anterior, substituída pela "Ordem revista" acima)

1. Backend de radares + migração v4 + testes (fecha o rascunho atual).
2. Vitrine nova.
3. Página do radar com Histórico e "O que mudou".
4. Nome/descrição editáveis, "Programar" busca avulsa, execuções presas.
5. Miniatura e categoria, conforme as decisões.
