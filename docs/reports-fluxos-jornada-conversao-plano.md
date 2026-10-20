# Fluxos: jornada da conversão e páginas fora do fluxo

Plano de 2026-10-20. Ponto de partida: o fluxo "Centralcomm - Serviços de mídia de alta complexidade" (v67), que mostra 5 conversões e só 1 seta chegando ao nó de conversão. As outras 4 passaram por páginas que não estão no desenho, e hoje o produto não diz quais.

Ordem: fase 0 (base) → fase 1 (jornada da conversão) → fase 2 (influência das páginas fora do fluxo). O que vem depois (setas "na mesma sessão", fluxo global, mesa com vários fluxos, fim da cópia de eventos) fica na seção 6, só registrado.

## 0. Estado em 2026-10-20 (implementado, sem commit)

| Item | O que ficou | Onde |
|---|---|---|
| Métricas não zeram ao publicar | O período soma todas as publicações, lidas com o desenho atual; `?revision=N` lê só uma publicação, com o próprio desenho. Presença ao vivo e saúde da coleta seguem só na publicação atual. | `reports_flow_history.py`, `reports_flow.py` (jornada e `/flow`) |
| 3.2 Um número só | `outcome` na resposta da jornada: sessões que passaram por algum nó medido e sessões que chegaram a um nó de conversão. O resumo do canvas, o painel e o Monitor usam esse número; o do funil aparece como "a partir da entrada". | `reports_flow.py`, `FlowCanvas.jsx`, `FlowJourneyPanel.jsx`, `FlowMonitorWorkspace.jsx` |
| 3.3 Click id | Clique pago sem UTM vira origem `click:google` ou `click:meta` (a regra "Iw" do hub de Jornada), nos Fluxos e na Página 360. A tag já mandava `gclid`/`gbraid`/`wbraid`/`fbclid` em `click_id`. | `reports_flow_metrics.py` (`click_origin_sql`), `reports_pages.py` |
| 4 Jornada da conversão | `GET …/flow/flows/<id>/conversions`: cada conversão com os passos (inclusive páginas fora do desenho), as visitas anteriores do visitante (30 dias) e as três origens; os caminhos mais comuns. Aba "Conversões" no painel Jornada observada. | `reports_flow_conversions.py`, `FlowJourneyPanel.jsx` |
| 5 Influência | `GET …/flow/flows/<id>/influence`: páginas fora do fluxo que aparecem em 2+ conversões, com posição típica, taxas só com amostra; páginas do fluxo que nenhuma conversão usou. Aba "Páginas fora", com "Adicionar ao rascunho" depois do nó que mais a antecede. | idem |

Mudanças em relação ao plano abaixo:

- **3.1 Metas do site já existiam.** São as regras de conversão da Super Tag (`config.conversion_rules`, com o padrão `obrigad`/`thank`/`sucesso`/`confirmac`), que viram eventos `conversion` na chegada. Não foi criada uma lista nova. Dentro de um fluxo, conversão é a sessão que chegou a um nó de conversão do fluxo, para a lista de jornadas bater com o número do nó. As conversões derivadas pelas regras não são copiadas para os fluxos (`_fanout_flow_events` recebe só os eventos originais); alinhar as duas definições fica para a fase da leitura direta dos eventos do site (seção 6.4).
- **Fonte das fases 1 e 2:** os eventos do próprio fluxo (todas as publicações), não os do site. Assim os números conferem com o mapa; o custo é não haver dados de antes da primeira publicação.
- **Jornada não foi materializada:** a consulta é sob demanda, com teto de 200 conversões na lista e 2000 na influência.
- Testes: `tests/test_reports_flow_history.py` e `tests/test_reports_flow_conversions.py` (as partes SQL rodam com `CX_TEST_DATABASE_URL`).

Pendente: aba "Conversões" na Página 360 (visão do site, sem fluxo); setas "na mesma sessão"; seção 6 inteira.

## 1. Diagnóstico (o que o código faz hoje)

| Sintoma no fluxo | Causa | Onde |
|---|---|---|
| 5 conversões, 1 seta em Conversão | A seta conta só passagem direta. Uma página fora do fluxo entra como `node_id` nulo e quebra a sequência: Home → /blog → /contato não conta Home → Contato. | `reports_flow.py` (consulta de `transitions`, `LEAD(node_id)` sobre `collapsed`) |
| "5 converteram · 6%" no topo e "2,6% · 2 de 77" no painel | São duas definições: sessões no nó de conversão ÷ sessões que chegaram, contra sessões que entraram por um nó de entrada e converteram depois. | resumo do canvas × `funnel` em `reports_flow.py` |
| "Caminhos fora do desenho" nunca sugere uma página nova | A sugestão só pega pares de nós já desenhados (`suggestions` sai de `transitions`, que só tem `node_id`). | `reports_flow.py` |
| 67 de 86 em "Acesso direto"; campanha [Search] [AON] com 0 | Suspeita: clique pago com só `gclid`, sem UTM e sem referrer, cai em direto. `origin_platform` lê UTM e referrer; `click_id` é gravado mas não é usado na origem. **Verificar nos dados antes de corrigir.** | `reports_flow_metrics.py` (`origin_platform`, `parse_origin`) |
| A conversão é creditada à origem da sessão em que aconteceu | Não há leitura entre sessões, embora `cadu_reports_supertag_sessions` ligue `session_id` a `visitor_id`. | — |
| Página 360 e fluxo discordam sobre o que é conversão | Página 360 só conta `event_kind='conversion'`. No fluxo, uma visita a `/obrigado` vira conversão porque o nó diz isso. O site não tem uma lista própria de metas. | `reports_pages.py` (`_CONVERSION_MAP_SQL`) × `match_flow_node` |

O que já existe e será reaproveitado:

- `cadu_reports_supertag_events`: todos os eventos do site, inclusive páginas fora de qualquer fluxo, por 90 dias, com índice `(site_id, session_id, occurred_at)`.
- `cadu_reports_supertag_sessions`: `session_id` → `visitor_id`, para enxergar visitas anteriores.
- Mapa de conversão da Página 360: mesma ideia, mas para uma página por vez e sem caminho completo.
- CRM (`cadu_reports_external_conversions`): lead, qualificado e venda ligados pelo visitante, quando houver.
- A ação "Adicionar ao rascunho" do painel Jornada observada.

## 2. Princípios

1. **Ler o site, não o desenho.** A jornada e a influência saem dos eventos do site. O fluxo vira uma camada por cima: diz o que está desenhado e o que não está.
2. **Associação, não causa.** É o mesmo aviso que a Página 360 já mostra. Nenhum rótulo diz "causou".
3. **Contagem antes de taxa.** Com poucas conversões (5 em 30 dias aqui), mostrar números absolutos. Comparação com a média do site só acima de um mínimo de amostra (seção 5.3).
4. **Faltar dado não é zero.** Sem `visitor_id` não há jornada entre visitas: o produto diz isso e mostra a cobertura, sem esconder.
5. **Uma definição de conversão por site**, usada pelo fluxo, pela Página 360 e pela jornada.

## 3. Fase 0: base comum

### 3.1 Metas do site

Uma lista de metas por instalação da Super Tag, guardada em `cadu_reports_supertag_sites.config`, chave `goals`, sem tabela nova:

```json
{"goals": [
  {"id": "obrigado", "label": "Contato enviado", "kind": "page", "path": "/obrigado"},
  {"id": "whatsapp", "label": "WhatsApp", "kind": "whatsapp_click"},
  {"id": "form", "label": "Formulário", "kind": "form_submit"},
  {"id": "evento", "label": "Conversão (tag)", "kind": "conversion", "event_name": null}
]}
```

- Valores iniciais: os nós de conversão dos fluxos publicados do site, mais `event_kind='conversion'`. O usuário confirma ou ajusta na aba Páginas do fluxo ou na Página 360.
- Uma função, `site_goal_match(goals, event)` → `goal_id | None`, num módulo novo e autossuficiente (`reports_site_goals.py`), sem importar de arquivos com mudanças não commitadas.
- A partir desta fase, a Página 360 também passa a usar as metas, para não haver duas verdades.

### 3.2 Um número de conversão só

- **Conversões**: sessões que atingiram uma meta no período.
- **Taxa**: conversões ÷ sessões que chegaram ao fluxo (ou ao site, nas telas de site).
- O número atual do painel continua, renomeado para "a partir da entrada", com uma frase dizendo o que conta.

### 3.3 Origem pelo click id (só se a verificação confirmar)

Antes de mexer: medir, nos últimos 30 dias deste site, quantas sessões "diretas" têm `click_id` na atribuição e de que tipo. Se for relevante:

- `gclid`/`gbraid`/`wbraid` → `google`, `fbclid` → `meta`, `ttclid` → `tiktok`, `msclkid` → `bing`, `li_fat_id` → `linkedin`.
- Conferir como `click_id` é gravado (só o valor ou o par nome/valor). Se só o valor, a tag precisa mandar o nome do parâmetro. Alterou `cadu-supertag-v1.js` → regenerar o `.min.js` com esbuild.
- Testes em `tests/` para `origin_platform` com cada click id e com UTM + click id (a UTM explícita vence).

## 4. Fase 1: jornada da conversão

Pergunta que responde: **para cada conversão, que caminho a pessoa fez e de onde veio.**

### 4.1 Como uma jornada é montada

Para cada conversão (primeiro evento de meta da sessão):

1. **Sessão da conversão**: todos os `page_view`, `form_submit` e `whatsapp_click` da sessão até a meta, em ordem. Visitas repetidas em sequência viram uma só (A, A, B → A, B). Endereços normalizados com `normalize_path`/`normalize_host` (`reports_flow_matching.py`). Limite de 30 passos; acima disso, os 10 primeiros, "+N páginas" e os 19 últimos.
2. **Visitas anteriores**: as sessões do mesmo `visitor_id` nos 30 dias anteriores (`cadu_reports_supertag_sessions`, índice `cohort_idx`), cada uma com origem, data e até 5 páginas.
3. **Origens**:
   - *primeiro contato*: origem da sessão mais antiga dentro dos 30 dias;
   - *último contato não direto*: a última origem que não foi direta;
   - *sessão da conversão*: a origem que existe hoje.
4. **Em relação ao fluxo** (quando aberta de dentro de um fluxo), cada passo leva:
   - `node_id` e título, quando a página está desenhada;
   - `off_flow: true`, quando não está.

Sem `visitor_id` (sem consentimento de audiência), a jornada fica só na sessão, com o selo "sem visitas anteriores identificáveis". A tela mostra a cobertura: "X de Y conversões com histórico".

### 4.2 Onde calcular

Primeiro, sob demanda, sem tabela nova:

- 90 dias de retenção e volumes baixos tornam viável uma consulta por site e período, usando o índice `(site_id, session_id, occurred_at)`.
- Teto de 200 conversões por resposta (as mais recentes), com paginação por cursor `(occurred_at, event_id)`.
- Medir o tempo num site com mais tráfego. Se passar de ~1,5 s, materializar em `cadu_reports_conversion_journeys` (site, evento da meta, sessão, visitante, `goal_id`, passos em JSONB, origens, `expires_at` igual ao do evento), preenchida pelo mesmo caminho de ingestão ou por um job a cada 5 minutos. A decisão sai da medição.

### 4.3 API

`GET /api/v2/reports/site/conversion-journeys?site_id=&days=30&flow_id=&goal=&origin=&cursor=`

```json
{
  "window": {"days": 30, "since": "...", "until": "..."},
  "coverage": {"conversions": 5, "with_visitor_history": 3},
  "journeys": [{
    "conversion_at": "...", "goal": {"id": "obrigado", "label": "Contato enviado"},
    "origin": {"first": "meta", "last_non_direct": "meta", "session": "direct"},
    "prior_sessions": [{"started_at": "...", "origin": "meta", "pages": ["/", "/solucoes"]}],
    "steps": [{"path": "/", "title": "Home", "node_id": "n2", "off_flow": false, "seconds": 42},
              {"path": "/blog/ctv", "title": "Blog · Ctv", "off_flow": true, "seconds": 95},
              {"path": "/contato", "node_id": "n10", "off_flow": false},
              {"path": "/obrigado", "node_id": "n11", "goal": true}]
  }],
  "top_paths": [{"steps": ["/", "/blog/*", "/contato", "/obrigado"], "conversions": 2}],
  "next_cursor": null,
  "notes": ["É associação observada, não prova de que o caminho causou a conversão."]
}
```

- `top_paths`: os caminhos somados, com páginas fora do fluxo agrupadas pelo começo do endereço (`/blog/*`). Até 10, só com 2 ou mais conversões.
- Mesmo escopo e as mesmas permissões das rotas `/api/v2/reports/pages/*` (`_selection`, `_site`).

### 4.4 Tela

Dentro do fluxo, no modo Monitorar:

- **Botão no nó de conversão**: "Ver as 5 jornadas". Abre um painel lateral, no mesmo formato de "Jornada observada".
- **Painel**: no topo, os caminhos mais comuns. Abaixo, uma linha por conversão. Cada linha mostra as pílulas da origem e a sequência de páginas; as páginas fora do fluxo ficam tracejadas, com o botão "Adicionar ao rascunho" (a ação que já existe).
- **Sobre o canvas**: cada nó medido ganha "N conversões passaram aqui". Entre dois nós, quando a passagem foi por fora do desenho, uma pílula fantasma "via 3 páginas fora do fluxo", que abre a lista.

Fora do fluxo: uma aba "Conversões" na Página 360 do domínio, com a mesma lista, sem a camada do fluxo.

### 4.5 Testes

- Unidade para a montagem da jornada (função pura sobre linhas de evento): repetição seguida, limite de 30 passos, meta no meio da sessão, sessão sem `visitor_id`, visita anterior fora da janela.
- Unidade para as origens: primeiro contato, último não direto, tudo direto.
- Rota com Postgres local (nunca contra o banco do `.env`, que é o de produção).
- Teste de navegador do painel depois de `npx vite build --config vite.reports.config.mjs`.

## 5. Fase 2: influência das páginas fora do fluxo

Pergunta que responde: **que páginas aparecem nas conversões e não estão no fluxo.**

### 5.1 Medidas por página (site, período)

Para cada página P com pelo menos uma visita no período:

| Medida | Definição |
|---|---|
| `sessions` | sessões que viram P |
| `assisted` | conversões em que P apareceu antes da meta, na mesma sessão, sem ser a página da meta |
| `assisted_prior` | conversões em que P apareceu numa visita anterior do mesmo visitante (30 dias) |
| `share` | `assisted` ÷ total de conversões do período |
| `rate_with` | sessões com P que converteram ÷ `sessions` |
| `rate_without` | sessões sem P que converteram ÷ sessões sem P |
| `position` | onde P costuma estar nas conversões: início, meio ou véspera (o passo antes da meta) |
| `in_flow` | se P é nó do fluxo aberto, e qual |

### 5.2 Ranking "Influenciam e não estão no fluxo"

- Ordenar por `assisted + assisted_prior`; desempate por `share`.
- Mostrar só páginas com `in_flow = false` e pelo menos 2 conversões assistidas.
- Cada linha: título (do catálogo `reports_site_pages`, ou `slug_name`), contagens, posição típica, e "Adicionar ao fluxo" depois do nó que mais a antecede nas jornadas.
- No mesmo lugar, a lista inversa: **páginas do fluxo que nenhuma conversão usou** no período. Ajuda a enxugar o desenho.

### 5.3 Quando mostrar taxa

- `rate_with` contra `rate_without` só aparece com P em pelo menos 20 sessões (a mesma regra da aba Páginas) **e** pelo menos 10 conversões no site no período.
- Abaixo disso, só contagens, com a frase "Poucas conversões para comparar taxas".
- Nada de lift em porcentagem com amostra pequena: 1 conversão em 3 sessões não vira "33% de conversão".

### 5.4 Onde aparece

- Aba **Páginas** do fluxo: uma seção nova "Fora do fluxo", abaixo das linhas atuais (que vêm de `flow_page_rows`).
- Painel **Jornada observada**: "Caminhos observados fora do desenho" passa a incluir páginas não desenhadas, não só pares de nós.
- **Página 360**: as mesmas medidas da página, num cartão "Participação nas conversões".

### 5.5 API

`GET /api/v2/reports/site/page-influence?site_id=&days=30&flow_id=`

Devolve `pages[]` com as medidas da 5.1, `thresholds` com os mínimos aplicados e `notes`. Reaproveita a montagem da fase 1: as duas rotas usam a mesma função de jornada; a influência é uma agregação sobre ela.

### 5.6 Testes

- Agregação pura: página vista duas vezes conta uma, página da meta não conta como assistida, visita anterior conta só em `assisted_prior`, mínimos de amostra.
- O ranking ignora páginas do fluxo e respeita o mínimo de 2 assistidas.

## 6. Depois destas fases (registrado, sem detalhe)

1. **Setas "na mesma sessão"**: além da passagem direta, A e depois B na mesma sessão, com "+N via outras páginas". Sai quase de graça da fase 1.
2. **Fluxo global automático**: visão gerada do site. Entradas são as páginas onde mais se chega, por origem. Destinos são as metas mais as páginas com mais conversões assistidas. O meio fica agrupado por prefixo. Nada é desenhado à mão.
3. **Mesa com vários fluxos**: cada fluxo como um quadro numa mesa do site (institucional, campanha, CTV).
4. **Fim da cópia de eventos**: hoje cada fluxo publicado copia todos os eventos do site para `cadu_reports_flow_events`, linha a linha, dentro da requisição da Super Tag (`_fanout_flow_events`), dividindo um limite de 1.200 eventos por minuto por tag. Os itens 2 e 3 só ficam baratos quando o fluxo passar a ler os eventos do site em vez de recebê-los copiados. É a mudança mais pesada; precisa de plano próprio.

## 7. Entrega

- Migrações, se a fase 1 precisar materializar: seguir `migrations/ORDER.txt` e testar em Postgres local, porque a produção diverge do esquema do repositório.
- Nenhum script contra o banco do `.env` para "testar local": é o de produção.
- O bundle do Reports (`static/cadu_connect/react/app.js`) não é versionado; rebuild antes dos testes de navegador.

## 8. Decisões em aberto

1. **Janela de visitas anteriores**: 30 dias (proposta), ou a `audience_days` do site?
2. **Metas iniciais**: aceitar automaticamente os nós de conversão dos fluxos publicados, ou exigir confirmação na primeira vez?
3. **Correção do click id**: decidir depois da medição da 3.3.
4. **Materializar a jornada já na fase 1**, ou só se a medição de tempo pedir (proposta: só se pedir).
