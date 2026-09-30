# Reconhecimento do módulo de Fluxos — M0

Reconhecimento estático do checkout em 2026-09-30. As observações do checklist descrevem pontos de implementação, não confirmam a reprodução visual do exemplo Centralcomm. Nenhum código de produção foi alterado.

## Arquitetura e dados

- O aplicativo é Flask/Python com PostgreSQL (`aicentralv2/cadu_connect/reports_flow.py:1711`, `migrations/add_reports_funnel_management_v1.sql:8`), e não PHP. O editor é React/JS/CSS, montado em `frontend/reports-v1/FlowCanvas.jsx:168`, com `@xyflow/react` 12.12.0 (`package-lock.json:1038`). O layout ELK já existe em `frontend/reports-v1/flowLayout.js:2` e `elkjs` já consta no `package.json:23`.
- A mensagem de criação é estado React (`versionMessage`) em `frontend/reports-v1/main.jsx:1047`, renderizado no fluxo da página em `main.jsx:1180`; não é flash PHP.
- O endpoint de inventário existente é `GET /api/v2/reports/flow/flows/<flow_id>/discovery` em `aicentralv2/cadu_connect/reports_flow.py:1427-1495`; a UI calcula `discovery.pages.length` e `mappedSitePages` em `frontend/reports-v1/main.jsx:1217`, enquanto `FlowCatalog.jsx:9` calcula suas próprias contagens sobre `items`.
- O catálogo deduplica por URL canônica e agrupa por padrão e assinatura de estrutura em `aicentralv2/cadu_connect/reports_flow_catalog.py:38-65`. Há outra função de grupos para a montagem automática em `reports_flow.py:351`. Classificadores em `reports_flow_catalog.py:24` e `reports_flow.py:245`.
- Pendências: `frontend/reports-v1/flowValidation.js` e `aicentralv2/cadu_connect/reports_flow_validation.py:6`. A publicação é `POST /api/v2/reports/flow/flows/<flow_id>/publish` em `reports_flow.py:1711`; bloqueios hoje retornam HTTP 409 (`:1721-1723`).
- Tabelas principais: `cadu_reports_flow_registry` (id, client_id, tag_id, status, config; depois `draft_config` e revisões) em `migrations/add_reports_funnel_management_v1.sql:8` e `add_reports_flow_versions_v1.sql:4`; nós e conexões do rascunho ficam no JSONB, não em tabelas individuais. Publicação tem `cadu_reports_flow_versions` (`add_reports_flow_versions_v1.sql:11`) e passos materializados `cadu_reports_flow_steps` (`add_reports_operations_v1.sql:200`). Inventário: `cadu_reports_flow_discovery_runs` e `cadu_reports_flow_discovered_pages` (`add_reports_flow_site_mapping_v1.sql:16,31`). Eventos: `cadu_reports_flow_events` (`add_reports_operations_v1.sql:227`) e `cadu_reports_supertag_events` (`add_reports_supertag_v1.sql:21`), ambos com sessão, caminho e horário. A instalação da tag é `cadu_reports_supertag_sites` (`add_reports_supertag_v1.sql:2`).
- Estilos de painéis e rail: `frontend/reports-v1/flow-workspace.css:281-315`, `flow-monitor-workspace.css:58-60`, `flow-canvas.css:56-68,130-140`.

## Checklist dos 47 problemas

| # | Problema | Arquivo:linha | Observação |
|---|---|---|---|
| 1 | Banner desloca layout | `frontend/reports-v1/main.jsx:1180` | `versionMessage` entra antes do editor. |
| 2 | Plural incorreto | `frontend/reports-v1/main.jsx:1047` | Interpolação fixa de “fluxos criados”. |
| 3 | Faixas amarelas | não localizado | Requer inspeção visual; nenhuma origem inequívoca no código. |
| 4 | Status ambíguo | `frontend/reports-v1/main.jsx:1201` | Estado do fluxo e salvamento em elementos separados. |
| 5 | Publicar com pendências | `frontend/reports-v1/main.jsx:1203`; `aicentralv2/cadu_connect/reports_flow.py:1719-1723` | Botão não desabilita por erro; servidor responde 409. |
| 6 | Área vazia | `frontend/reports-v1/FlowCanvas.jsx:168`; `flowLayout.js:2` | Viewport padrão e layout existente; validar visualmente. |
| 7 | Marca React Flow | `frontend/reports-v1/FlowCanvas.jsx:168` | Atribuição padrão; sem `proOptions`. |
| 8 | Minimapa | `frontend/reports-v1/FlowCanvas.jsx:168` | Tamanho fixo 150×95 e sem legenda. |
| 9 | Hint ⌘K | `frontend/reports-v1/FlowStudioAssist.jsx:11` | Botão separado. |
| 10 | Controles zoom | `frontend/reports-v1/FlowCanvas.jsx:168` | `Controls` padrão e botões adicionais. |
| 11 | Rail duplicada | `frontend/reports-v1/main.jsx:1213-1215` | Dois botões “+” e ícones repetidos. |
| 12 | Fechar painéis | `frontend/reports-v1/ReportsPanelShell.jsx`; `main.jsx:1217` | Shell compartilhado já existe; uso e layout variam. |
| 13 | Painéis cobrem nós | `frontend/reports-v1/flow-workspace.css:281-285` | Painéis absolutos sobre canvas. |
| 14 | Scroll horizontal | `frontend/reports-v1/flow-workspace.css:285`; `flow-canvas.css:60` | Overflow em painéis; validar em 1280×800. |
| 15 | Busca nativa | `frontend/reports-v1/main.jsx:1217` | `<input>` direto para “Buscar blocos”. |
| 16 | Ícones canais | `frontend/reports-v1/flowBlockRegistry.js:43`; `FlowPlatformLogo.jsx:23` | Mapa de ícones e logos espalhado. |
| 17 | Abas inspector | `frontend/reports-v1/FlowInspector.jsx:21` | `aria-selected` existe; estado visual depende de CSS. |
| 18 | Contagens incoerentes | `frontend/reports-v1/main.jsx:1217`; `FlowCatalog.jsx:9` | Fontes e filtros de contagem distintos. |
| 19 | Grupo triplicado | `frontend/reports-v1/FlowCatalog.jsx:9`; `aicentralv2/cadu_connect/reports_flow_catalog.py:56-65` | UI agrupa por papel e template; duplicação real não reproduzida sem dados. |
| 20 | Grupos PT/EN separados | `aicentralv2/cadu_connect/reports_flow_catalog.py:56-65` | Chave de grupo usa caminho com prefixo de idioma. |
| 21 | Agrupar sem contexto | `frontend/reports-v1/FlowCatalog.jsx:9` | Ação direta após seleção. |
| 22 | Títulos truncados | `frontend/reports-v1/FlowCatalog.jsx:9` | Tooltip nativo `title`; verificar truncamento no CSS. |
| 23 | Nós nas divisórias | `frontend/reports-v1/FlowCanvas.jsx:27-29`; `flowLayout.js:27-34` | Faixas em overlay separado; layout usa X calculado. |
| 24 | Etapa ≠ posição | `frontend/reports-v1/FlowCanvas.jsx:145`; `FlowInspector.jsx:29` | Arrasto recalcula stage por X; inspector altera stage. |
| 25 | Páginas em Origem | `frontend/reports-v1/flowStages.js:7-14` | Stage explícito pode prevalecer sem restrição de tipo. |
| 26 | PT/EN duplicados | `aicentralv2/cadu_connect/reports_flow_catalog.py:38-49` | Deduplicação por URL, sem tradução. |
| 27 | Thumbnails/títulos | `frontend/reports-v1/FlowCanvas.jsx:53-63` | Imagem e rótulo no nó; validar legibilidade. |
| 28 | QR Code tipografia | `frontend/reports-v1/FlowCanvas.jsx:53-63`; `flowBlockRegistry.js` | Não localizado tratamento exclusivo do texto; validar visualmente. |
| 29 | QR Code ícone/conexão | `frontend/reports-v1/flowBlockRegistry.js:43`; `flowValidation.js` | Ícone no registro; conexão depende de configuração. |
| 30 | Toolbar nó | `frontend/reports-v1/FlowCanvas.jsx:58-60` | `NodeToolbar` existe; ações usam termos “etapa”. |
| 31 | Ocultas opaco | `frontend/reports-v1/FlowCanvas.jsx:168` | Contador pequeno sem lista de motivos. |
| 32 | Handles thumbnail | `frontend/reports-v1/FlowCanvas.jsx:45,60` | Quatro handles dentro do corpo do nó. |
| 33 | Funil sem conexões | `frontend/reports-v1/flowStages.js:15-37` | Filtro remove `site_link`/`navigation` e limita a 20. |
| 34 | Conexões iguais | `frontend/reports-v1/FlowCanvas.jsx:123`; `:82` | Métricas alteram largura quando presentes. |
| 35 | Conexões atravessam nós | `frontend/reports-v1/FlowCanvas.jsx:82`; `flowLayout.js:19-34` | Curva smooth step; roteamento visual a verificar. |
| 36 | Retorno longo | `frontend/reports-v1/flowStages.js:15-37`; `FlowCanvas.jsx:82` | Filtro e edge customizada; geometria a verificar. |
| 37 | Sem volume/taxa | `frontend/reports-v1/FlowCanvas.jsx:123`; `FlowJourneyPanel.jsx:10` | Dados existem no modo jornada; sem eventos, labels somem. |
| 38 | Setas escondidas | `frontend/reports-v1/FlowCanvas.jsx:123` | Marker configurado; visibilidade a verificar. |
| 39 | Tooltip duplicado | `frontend/reports-v1/FlowCanvas.jsx:57-58`; `FlowCatalog.jsx:9` | `title` nativo junto com hover customizado. |
| 40 | Inglês na UI | `frontend/reports-v1/FlowCanvas.jsx:58`; `flowStages.js:2-4` | Renderiza `node.role` e `stageFor(node)` como IDs técnicos. |
| 41 | Papel × Etapa | `frontend/reports-v1/FlowInspector.jsx:28-29`; `flowStages.js:7-14` | Campos separados; inferência pode contradizer seleção. |
| 42 | Vocabulário | `frontend/reports-v1/main.jsx:1217`; `FlowInspector.jsx:20,28`; `FlowStudioAssist.jsx:11` | “Blocos”, “Papel”, “Prontidão”, “Excluir etapa”. |
| 43 | Conversão contradiz canvas | `aicentralv2/cadu_connect/reports_flow_validation.py:16`; `frontend/reports-v1/flowValidation.js` | Regra olha `type === conversion`, não etapa. |
| 44 | Pendências cinzas | `frontend/reports-v1/FlowStudioAssist.jsx:11`; `main.jsx:1182` | Dois painéis de revisão; estado cinza a validar visualmente. |
| 45 | Texto truncado | `frontend/reports-v1/FlowStudioAssist.jsx:11`; `flow-canvas.css` | Texto do painel a validar visualmente. |
| 46 | Pendências sem ação | `frontend/reports-v1/main.jsx:1182`; `FlowStudioAssist.jsx:11` | Apenas itens com `nodeId` podem localizar nó. |
| 47 | Jargão de ciclo | `aicentralv2/cadu_connect/reports_flow_validation.py:70-73` | Mensagem “ciclo sem bloco de condição”. |

## Comandos encontrados

- Build do módulo: `npm run build:reports` (`package.json:10`). Build geral: `npm run build` (`package.json:9`).
- Testes direcionados: `node tests/frontend/reports-flow-studio.test.cjs`, `node tests/frontend/reports-flow-workspace.test.cjs`, `python -m pytest tests/test_reports_flow_studio.py tests/test_reports_flow_schema_v2.py tests/test_reports_flow_versions.py`.
- Não há script `lint` nem `test` no `package.json`; usar verificações direcionadas e registrar comandos nos milestones seguintes.
