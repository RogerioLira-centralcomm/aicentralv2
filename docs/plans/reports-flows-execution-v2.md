# Reports — Editor e Monitoramento de Fluxos · Plano de execução revisado

Data: 30/09/2026 · Revisão 2 do plano "adequação do editor e monitoramento de fluxos".
Estado: plano de execução. Nenhuma alteração de produto feita nesta revisão.

Este documento substitui a revisão 1. Mantém todas as decisões aprovadas (React, Untitled UI, React Flow 12.12.0 já instalado, ELK, fluxo horizontal, navegação própria, CRM futuro). Acrescenta o que faltava para executar com segurança: regras de cálculo fechadas, rollout com feature flag, trilhas paralelas, linguagem visual dos nós, modelo de comandos do editor, orçamento de performance, estados vazios, permissões, instrumentação, riscos e rastreabilidade entre seções e fases.

---

## 0. O que mudou em relação à revisão 1

| # | Melhoria | Por quê | Seção |
|---|---|---|---|
| 1 | Glossário e regras de cálculo fechadas: fuso, limites de período, fim de sessão, colapso de repetições | Os P0 corrigem a lógica, mas sem regra de fuso e de sessão os números continuam ambíguos | 3 |
| 2 | Esboço da consulta de passagens e orçamento de latência com índices | O P0 1 descreve o erro, não a forma correta nem o custo | 6, 16 |
| 3 | Feature flag `flows_workspace_v2` por cliente e plano de rollback | O trabalho acontece em `main`; sem flag, UI incompleta vai para produção | 7 |
| 4 | Duas trilhas paralelas (contratos de dados × workspace visual) | Na revisão 1 toda a parte visual esperava a Fase 0; o problema mais sentido pelo usuário é visual | 7, 24 |
| 5 | Linguagem de formas dos nós e edição inline do rótulo | A direção "ícone sobre forma + texto editável" tinha se diluído em "ícone semântico" | 11 |
| 6 | Modelo de comandos do editor, autosave serializado e conflito | "Comandos por gesto" estava declarado sem contrato | 13 |
| 7 | Coordenador de painéis com área livre calculada | As regras de largura existiam; faltava o mecanismo único | 9 |
| 8 | Estados vazios e de primeiro uso do monitor e do editor | Não havia comportamento para "sem publicação" ou "publicado sem eventos" | 15 |
| 9 | Polling com backoff, cursor e sem requisições sobrepostas | Reduz carga e deixa claro o estado de falha | 15 |
| 10 | Especificação do serviço de miniaturas reais (SSRF, fila, TTL, quotas) | A revisão 1 citava o serviço sem parâmetros | 17 |
| 11 | Matriz de permissões | Os testes citavam "viewer", mas o papel não estava definido | 21 |
| 12 | Tabela de copy e estados padrão em português | Evita "Não disponível", "Sem dados" e "—" misturados | 22 |
| 13 | Instrumentação de uso do produto | Não havia como medir se a adequação funcionou | 23 |
| 14 | Fases com tamanho, dependências e rastreabilidade | TypeSafe, CRM e exportação não estavam mapeados em nenhuma fase | 24 |
| 15 | Ferramentas de teste, regressão visual e registro de riscos | Os cenários existiam; faltava onde e como rodá-los | 25, 26 |
| 16 | Lista de decisões pendentes do produto | Evita que o Codex decida regra de negócio sozinho | 27 |

---

## 1. Contexto do projeto

**Stack real (fonte da verdade é o repositório):**
- Frontend: React 18, JavaScript com JSDoc, Untitled UI, `@xyflow/react` 12.12.0, ELK. Bundles versionados gerados pelo build de Reports, com cache busting do projeto.
- Backend: Flask (Python 3) em `aicentralv2/cadu_connect`, PostgreSQL.
- Assistência semântica: TypeSafe, já integrado em `reports_typesafe.py`.
- Fluxo de trabalho: commits em `main`, deploy com migrações aplicadas e validação de ambiente.

**Sem migração de stack.** Nada de TypeScript global, outra biblioteca de canvas, outra API ou outro design system.

**Arquivos centrais:**
- Frontend `frontend/reports-v1/`: `main.jsx`, `FlowCanvas.jsx`, `FlowInspector.jsx`, `FlowJourneyPanel.jsx`, `FlowPlatformLogo.jsx`, `flowLayout.js`, `useFlowHistory.js`, `flowValidation.js`, `flow-canvas.css`, `flow-workspace.css`.
- Backend `aicentralv2/cadu_connect/`: `reports_flow.py`, `reports_flow_live.py`, `reports_flow_monitor.py`, `reports_flow_schema.py`, `reports_flow_versions.py`, `reports_flow_suggestions.py`, `reports_typesafe.py`, `reports_ingest.py`.

**Primeiro passo obrigatório (antes de qualquer fase):** revisar as alterações locais sem commit da entrega anterior (logo no header, catálogo de ícones, alinhamento do monitor). Estabilizar em commits pequenos ou descartar com justificativa. Nenhum trabalho novo começa sobre um working tree ambíguo.

---

## 2. Resultado desejado e decisões centrais

Editar e monitorar são dois modos do mesmo espaço de trabalho. O usuário reconhece o mesmo mapa, abre as páginas reais, entende as origens e vê onde as sessões avançam, permanecem ou deixam de avançar. Painéis servem à seleção e mantêm o mapa utilizável em notebook. Todo número informa período, origem e cobertura.

Decisões:
- **Um canvas React Flow compartilhado** para editar, monitorar, simular e exportar, com permissões e camadas por modo.
- **O editor manipula o rascunho; o monitor lê uma publicação imutável.** Quando divergirem, os dois aparecem identificados.
- **Orientação padrão: esquerda → direita.** Organizar altera só posições. Criar conexão exige ação explícita do usuário ou aceitação de uma sugestão com evidência.
- **Divisão de responsabilidades:** Untitled fornece controles, formulários, menus, abas, badges, tooltips e diálogos. React Flow fornece o comportamento espacial. Nós e arestas são componentes próprios sobre as extensões do React Flow.
- **Linguagem visual por forma:** círculo para origem, miniatura para página, losango para evento e objetivo, quadrado tracejado para etapa visual (seção 11). O rótulo é texto editável no próprio mapa.
- **Uma grade vetorial discreta** que acompanha pan e zoom.
- **Miniaturas honestas:** captura real ou placeholder identificado. Imagem gerada nunca representa uma página existente.
- **CRM:** conectores nativos ficam "Em breve". O webhook atual de confirmação por cliente continua disponível. Não anunciar isolamento por conta nem execução que o backend não oferece.

---

## 3. Glossário e regras de cálculo (novo)

Estas regras valem para backend, frontend, exportação e testes. O copy da UI usa exatamente estes termos.

| Termo | Definição |
|---|---|
| **Sessão** | A sessão definida por `reports_ingest`. Se a ingestão não fechar sessão explicitamente, a sessão termina após **30 min sem atividade**; o valor fica numa constante única no backend e aparece na legenda. |
| **Etapa** | Um nó do fluxo com regra de correspondência medível (página ou evento). Origens e etapas visuais não são etapas medidas. |
| **Visita relevante** | Toda `page_view` do site do fluxo, mais os eventos mapeados na revisão. Uma `page_view` não mapeada é visita relevante com `node_id = NULL` e interrompe passagens diretas. |
| **Repetição** | Visitas consecutivas ao mesmo nó na mesma sessão colapsam em uma (A → A → B conta uma passagem A → B). |
| **Passagem direta A → B** | Após o colapso, B é a próxima visita relevante depois de A na mesma sessão. |
| **Período** | Intervalo meio-aberto `[início, fim)` no **fuso do cliente** (padrão `America/Sao_Paulo` se o cliente não tiver fuso configurado), convertido para UTC na consulta. "Últimos 30 dias" = de 00:00 de D-29 até agora. |
| **Ordem** | `occurred_at`, com desempate pelo ID de ingestão. Nunca pela ordem de chegada da requisição. |
| **Agora** | Sessões com última atividade nos últimos 90 s, excluindo as que registraram saída. Rótulo "sessões", nunca "pessoas". |
| **Não avançaram** | Sessões que passaram por A e não tiveram passagem para nenhuma etapa configurada depois de A dentro do período. Não é sinônimo de abandono. |
| **Saída observada** | Sessão encerrada (regra de sessão acima) cuja última visita relevante pertence à etapa. Só é calculada para sessões encerradas antes do fim do período. |
| **Cobertura** | Fração do escopo efetivamente medida (ex.: 38 de 40 URLs checadas). Toda métrica parcial exibe cobertura. |

Regras gerais:
- **Zero** só aparece quando uma consulta válida mediu a grandeza e o resultado é zero. Qualquer outro caso é "Não disponível", "Sem vínculo" ou erro.
- **Divisão por zero** resulta em "Não disponível", nunca 0% nem 100%.
- **Sessões únicas nunca são somadas entre nós**; agregados usam união (`COUNT DISTINCT`).
- **Moedas diferentes** não são somadas.

---

## 4. Leitura das referências

| Referência | O que funciona | Aplicação |
|---|---|---|
| Mapa compacto Meta/Google → landing → checkout → saída | Poucos elementos, métrica no caminho, saída explícita | Monitor com contagem e taxa por conexão; seleção explica o que não avançou |
| Editor amplo com barra superior e Forecast | Canvas dominante, ferramentas curtas | Header 56 px, rail, resumo recolhível; nada de projeção misturada com resultado |
| Jornada complexa com origens, páginas, segmentos e CRM | Famílias visuais distintas, ramificações legíveis | Linguagem de formas da seção 11, grupos nomeados |
| Recorte do header | Identidade, período e salvamento acessíveis | Logo, voltar, nome, modo, estado, filtros, uma ação principal |
| Contagens e taxas nas conexões | Volume versus avanço | Sessões por etapa e por passagem, denominador explícito |
| Rail lateral estreito | Ferramentas sem menu aberto | Explorar, adicionar, selecionar/mover, organizar, revisão, configurações |
| Biblioteca de modelos | Reconhecer antes de escolher | Preview do grafo real, objetivo, etapas, pré-requisitos |
| Muitas páginas convergindo | Comparar contribuição | Portas distribuídas, rótulos sem sobreposição, filtro por origem |
| Apresentação com insights | Comunicação com contexto | Exportação do mapa filtrado; apresentação completa fica para depois |
| Explorador Sources/Pages/Actions | Lista pesquisável ligada ao mapa | Abas Origens/Páginas/Eventos com Localizar/Adicionar |

Números, previsões e alertas das imagens são ilustrativos. Não provam capacidade nem dados do Reports.

---

## 5. Estado atual e desvio

Inspeção do working tree, incluindo mudanças locais sem commit. O build da entrega anterior passou. Não houve execução do backend, consulta à produção nem validação visual ao vivo. As falhas HTTP 400 continuam sem causa confirmada.

| Área | Hoje | Ajuste |
|---|---|---|
| Editor | `FlowCanvas` usa ReactFlow, Background, Handle, MiniMap, BaseEdge, EdgeLabelRenderer | Adotar Controls, Panel, NodeToolbar, seleção e conexão nativas; composição centralizada |
| Monitor | `main.jsx` desenha SVG e cards absolutos | Mesmo canvas do editor, com zoom, pan, seleção, foco e minimapa |
| Jornada no editor | Terceiro modo com painel próprio e consulta 7/30/90 isolada | Absorvida pelo modo Monitorar com o mesmo contrato de filtros |
| Header | Ações e modos competem por espaço | Hierarquia fixa, overflow previsível, sem banner empurrando o mapa |
| Navegação | Editor em `/flows/:id`; monitor por `flow_view` | Rota própria para monitor, redirecionamento dos links antigos |
| Painéis | CSS absoluto com overrides; 280 + 320 px cobrem o canvas | Coordenador de painéis com área livre calculada |
| Miniaturas | Desenho esquemático para todos os tipos | Captura real com data e estados, ou placeholder identificado |
| Ícones | Catálogo local; Google Ads com "G" genérico; Meta pode virar Facebook | Identidade canônica por plataforma, assets corretos, fallback explícito |
| Organização | ELK com dimensões fixas; resultado assíncrono pode sobrescrever edição | Dimensões medidas, guarda de revisão, merge por ID, grupos |
| Monitor alinhado | Fallback de três colunas com erro silencioso | Layout compartilhado, falha visível, viewport persistido |
| Histórico | Snapshots com debounce de 200 ms | Comandos por gesto (seção 13) |
| Eventos | Paleta mostra até 5 eventos; inspetor decide "recebendo" pela URL | Catálogo paginado, identidade de evento, estado do evento |
| Grupos | `pageGroup` é string | Contêiner com membros, colapso e movimento conjunto |
| Tempo real | Polling 15 s, janela 90 s, pulso por transição nova | Preservar semântica, adicionar backoff e cursor |
| Disponibilidade | Checagem HTTP até 101 URLs | Cobertura explícita, lotes até o limite de nós |
| TypeSafe | Papel de página, cache, guarda por revisão e evidência | Reaproveitar, melhorar explicação e escolha entre candidatos |
| CRM | Webhook por `organization_id`/`client_id` | Expor escopo real, reservar associação por conta |

---

## 6. P0 — confiança e integridade dos dados

Precedem qualquer camada visual de analytics. O editor visual pode avançar em paralelo (seção 7).

1. **Passagens diretas.** `/journey` calcula `LEAD` depois de um JOIN apenas com etapas mapeadas, então visitas intermediárias somem e criam A → B falso. Corrigir com a sequência completa de visitas relevantes (esboço abaixo). A mesma função serve `/journey` e o snapshot live.
2. **Conversão do funil.** Exigir conversão posterior à entrada na mesma sessão, pela regra de ordem da seção 3, dentro da revisão e do período.
3. **Presença.** `node_presence` atribui presença por URL a todos os nós da URL. Presença vale só para páginas; eventos mostram ocorrências e sessões que executaram a ação.
4. **Evento recebido.** Trocar a busca por caminho no `FlowInspector` pela identidade `host + path + event_kind + event_name`. Visitar a página não ativa um evento personalizado.
5. **Zero × indisponível.** Aplicar as regras da seção 3 em todas as respostas e componentes.
6. **HTTP 400.** Reproduzir o payload que falha antes de atribuir causa. Hipóteses a testar: evento duplicado na mesma URL, path inválido, porta inválida, posição fora do limite. O erro de duplicata deve apontar os `node_ids`. Deduplicar o inventário de eventos pela identidade medida antes de oferecer "Adicionar".
7. **Erro único.** Cada operação tem um único dono da mensagem: campo → inspetor; salvamento → estado no header com detalhe acionável. Nunca dois banners.
8. **Layout assíncrono.** Aplicar o resultado do ELK só se o fluxo e a revisão local forem os mesmos do início do cálculo. Merge por ID. Cancelar ou recalcular se houver edição no meio.
9. **Campos duplicados no schema.** `title/path/x/y` são a origem canônica de gravação. Adaptadores convertem para `data/position` do React Flow e de volta. Nenhum modo lê uma cópia antiga.
10. **Validação coerente.** Placeholders têm estado explícito. Evento real começando com `evento_` não é inválido pelo prefixo. Frontend e publicação importam as mesmas regras (identidade, portas, limites, configuração incompleta), exportadas do backend como fonte de verdade quando possível.

### 6.1 Esboço da consulta de passagens

Nomes de tabelas e colunas são ilustrativos; usar os reais de `reports_ingest`. A regra de correspondência da revisão é materializada como um `VALUES` ou tabela temporária `(node_id, host, path, match_kind, event_kind, event_name)`. Na primeira entrega, `match_kind` aceita apenas `exact` e `prefix`.

```sql
WITH visitas AS (
  SELECT e.session_id, e.id AS ingest_id, e.occurred_at,
         m.node_id                                   -- NULL = visita relevante não mapeada
  FROM   ingest_events e
  LEFT JOIN revision_match m ON <regra de correspondência>
  WHERE  e.client_id = :client_id AND e.site_host = ANY(:hosts)
    AND  e.occurred_at >= :inicio_utc AND e.occurred_at < :fim_utc
    AND (e.event_kind = 'page_view' OR m.node_id IS NOT NULL)
),
ordenadas AS (
  SELECT *, LAG(node_id) OVER w AS anterior
  FROM visitas
  WINDOW w AS (PARTITION BY session_id ORDER BY occurred_at, ingest_id)
),
colapsadas AS (                                      -- A → A vira A
  SELECT * FROM ordenadas
  WHERE anterior IS DISTINCT FROM node_id
),
sequencia AS (
  SELECT session_id, node_id,
         LEAD(node_id) OVER w AS proximo
  FROM colapsadas
  WINDOW w AS (PARTITION BY session_id ORDER BY occurred_at, ingest_id)
)
SELECT node_id AS origem, proximo AS destino, COUNT(DISTINCT session_id) AS sessoes
FROM   sequencia
WHERE  node_id IS NOT NULL AND proximo IS NOT NULL
GROUP  BY 1, 2;
```

- `proximo` NULL depois de um nó mapeado significa próxima visita não mapeada ou fim da sessão; isso alimenta "Não avançaram".
- A conversão do funil usa a mesma CTE `colapsadas` com `MIN(occurred_at)` de entrada e existência de objetivo posterior.
- Fixtures de teste cobrem todos os casos da seção 25 ("Dados").

---

## 7. Rollout, trilhas e rollback (novo)

### 7.1 Feature flag
- Flag `flows_workspace_v2`, por cliente, no mecanismo de configuração que o repo já usa (se não houver, uma coluna ou chave de configuração por cliente lida no Flask e exposta no bootstrap do frontend).
- **Desligada:** rotas e telas atuais inalteradas.
- **Ligada:** novas rotas, workspace e monitor no canvas compartilhado.
- Ordem de ativação: cliente interno CENTRALCOMM → 2 ou 3 clientes piloto → todos.
- Correções de dados do P0 **não** ficam atrás da flag; valem para todos, porque corrigem números errados.
- A flag e o código antigo (SVG do monitor, CSS absoluto, modo Jornada separado) são removidos na Fase 5.

### 7.2 Trilhas paralelas
| Trilha | Conteúdo | Depende de |
|---|---|---|
| **A — Dados** | P0 1–6, contratos `/journey` e `/live`, disponibilidade com cobertura, erros JSON | — |
| **B — Workspace** | Rotas, header, rail, coordenador de painéis, linguagem de nós, comandos, ELK, grupos | P0 7–10 (frontend) |
| **Junção** | Monitor no canvas compartilhado com métricas | A e B concluídas |

Assim, o usuário vê o editor novo cedo (trilha B) sem depender das correções de consulta (trilha A).

### 7.3 Rollback
- Desligar a flag devolve a experiência antiga sem deploy.
- Mudanças de schema são aditivas (`groups`, `groupId`, metadados de asset). Publicações antigas continuam legíveis e o editor antigo ignora campos novos sem apagá-los. Testar esse round-trip.
- Cada commit em `main` compila e mantém a flag desligada funcionando.

---

## 8. Navegação e header

| Rota | Conteúdo |
|---|---|
| `/connect/app/flows` | Biblioteca de fluxos |
| `/connect/app/flows/new` | Criar com domínio e modelo |
| `/connect/app/flows/:id` | Editor do rascunho |
| `/connect/app/flows/:id/monitor` | Monitor da publicação selecionada |

- `client_id` continua explícito na URL e é autorizado no servidor.
- A query do monitor conserva `revision`, período, conta e campanha.
- Links antigos com `flow_view` são redirecionados preservando contexto (redirect no Flask e no parser do frontend, no mesmo commit).
- Back, forward, refresh e acesso direto carregam o mesmo estado.
- A biblioteca mantém a sidebar do Reports. Editor e monitor usam o workspace em tela cheia.
- Trocar de cliente volta à biblioteca desse cliente.
- Sair do editor com alteração pendente mostra o estado do salvamento e aguarda a conclusão (`beforeunload` só se houver falha pendente).

**Header de 56 px:**
- **Esquerda:** voltar, logo/seletor Reports, nome do fluxo (editável inline, truncado com tooltip), domínio no detalhe.
- **Centro:** `Editar | Monitorar` (ButtonGroup do Untitled). "Simular" é uma ação do editor que abre painel com faixa "Simulação".
- **Direita no editor:** estado de salvamento (texto terciário + ícone), desfazer/refazer, **Publicar** (único primário), menu Mais (snippet, histórico, exportar, duplicar).
- **Direita no monitor:** revisão, período, atualização ativa/pausada com horário, filtros, menu.
- Erros aparecem num popover de estado ou numa faixa interna de altura fixa. O header nunca muda de altura.

---

## 9. Canvas, rail e painéis

Composição: header 56 px, rail 48 px à esquerda, canvas no restante. Painéis ancorados com `Panel`, em slots fixos, sem arraste livre.

| Rail | Editor | Monitor |
|---|---|---|
| Explorar | Origens, Páginas, Eventos, Grupos; Localizar/Adicionar | Mesmas abas com métricas; Localizar/Inspecionar |
| Adicionar | Paleta, modelos, página descoberta | Oculto; "Editar fluxo" no contexto |
| Selecionar/Mover | `V` / `H` | Mover como padrão; seleção permitida |
| Organizar | Tudo, seleção, grupo | Layout publicado × organizado (não grava rascunho) |
| Revisão | Pendências de publicação, uso dos limites | Saúde da coleta, URLs com falha, cobertura |
| Configurações | Grade, snap, nomes, miniaturas, portas | Camadas e legendas |

**Painéis:** explorador 288 px, inspetor 320 px, padding 16 px. Título e abas fixos, só o corpo rola. Todo painel tem fechar e devolve o foco ao elemento de origem.

### 9.1 Coordenador de painéis (novo)
Um único hook/contexto (`usePanelLayout`) é dono de:
- estado `{ explorer, inspector, simulation, summary }` (aberto/fechado + aba ativa);
- `freeArea`: retângulo do canvas menos rail e painéis abertos, recalculado por `ResizeObserver`;
- regras de largura:
  - **≥ 1440 px:** até dois painéis, se sobrarem ≥ 720 px de canvas; senão, abrir o inspetor fecha o explorador.
  - **1024–1439 px:** um painel expandido por vez; aba e busca preservadas ao alternar.
  - **768–1023 px:** um drawer de até 320 px, rail compacto, ações secundárias no menu.
  - **< 768 px:** monitor vira lista de etapas com indicadores; editor mostra orientação para tela maior e link para o monitor. O editor não é montado.

Todo enquadramento (`fitBounds`, localizar, centralizar seleção) usa `freeArea` como padding. Controls ficam no canto inferior esquerdo de `freeArea`, MiniMap no inferior direito, avisos acima dos Controls. Nenhum painel cobre esses alvos. Fechar painel não dispara `fitView`.

---

## 10. Componentes do React Flow

| Recurso | Uso |
|---|---|
| `ReactFlowProvider` + `useReactFlow` | Um contexto por workspace; viewport, foco, `fitBounds`, conversão de coordenadas |
| `Controls` + `ControlButton` | Zoom ±, ajustar, 100%, organizar, mão/seleção |
| `Panel` | Explorar, inspetor, resumo, avisos |
| `Background` | Uma camada de pontos ou linhas; alternância visual independente do snap |
| `MiniMap` | Visão geral, arrastar viewport, localizar grupos |
| `NodeToolbar` | Renomear, duplicar, agrupar, conectar, excluir; tamanho fixo em qualquer zoom |
| `EdgeToolbar` / `EdgeLabelRenderer` | Ações da conexão e rótulos de métrica com área de clique ampliada |
| `Handle` + `useUpdateNodeInternals` | Portas por direção e condição; recálculo após expandir grupo ou mudar dimensão |
| `BaseEdge` + caminhos calculados | Desenho e hit area consistentes; corredor de retorno |
| `applyNodeChanges` / `applyEdgeChanges` | Estado controlado; dimensão e seleção separadas de mutação de negócio |
| `onReconnect` + `reconnectEdge` | Mover ponta de conexão com validação e undo |
| `NodeResizer` | Só grupos e notas |
| `parentId` / `extent` | Agrupamento; filhos depois do pai no adaptador |
| `useNodesInitialized` / `getNodesBounds` | Medir antes de layout e enquadramento; remover timeouts fixos de 80 ms |

O ELK continua como algoritmo de layout. Nenhum template do React Flow UI que traga outro design system. Nada depende de exemplos Pro.

Referências: [componentes](https://reactflow.dev/api-reference/components), [Panel](https://reactflow.dev/api-reference/components/panel), [Controls](https://reactflow.dev/api-reference/components/controls), [NodeToolbar](https://reactflow.dev/api-reference/components/node-toolbar), [subflows](https://reactflow.dev/learn/layouting/sub-flows), [layout](https://reactflow.dev/learn/layouting/layouting).

---

## 11. Linguagem visual dos nós (reforçada)

Um **catálogo único** (`flowCatalog.js`) define para cada `kind`: `type`, `family`, `shape`, `platformId`, ícone, rótulo padrão, campos do inspetor e capacidade (`measured` | `visual` | `future`). Canvas, paleta, explorador, inspetor, modelos, monitor e exportação leem só dele. Nenhum `switch` por tipo fora do catálogo.

### 11.1 Anatomia comum
```
      Rótulo editável              13 px semibold, até 2 linhas, acima da forma
        ┌───────┐
        │ forma │                   ícone sobre forma de fundo
        └───────┘
      /obrigado                    11 px, terciário: URL curta, plataforma ou evento
      [ 1.240 sessões ]            chip de métrica (só no monitor)
```

### 11.2 Formas por família
| Família | Forma (a 100%) | Conteúdo | Capacidade |
|---|---|---|---|
| **Origem** | Círculo 56 px, superfície branca, borda `border-secondary` | Logo oficial 28 px; badge 16 px "pago" quando for mídia paga | Medida se houver vínculo; senão "Sem vínculo" |
| **Página** | Moldura de navegador 96×112 | Captura real (`object-fit: contain`) ou placeholder identificado | Medida |
| **Evento** | Losango 48 px, cor por tipo de evento | Ícone branco 20 px (formulário, clique, download, vídeo, WhatsApp) | Medida |
| **Objetivo / conversão** | Losango 48 px `success`, com anel duplo | Ícone de objetivo; sublabel "Evento do site" ou "Confirmação CRM" | Medida |
| **Etapa visual** (CRM, segmento, webhook) | Quadrado arredondado 48 px, borda tracejada | Ícone + badge "Etapa visual" ou "Em breve" | Visual/futura |
| **Grupo** | Frame com contorno leve e título | Nome + quantidade de etapas | Agregado por união |
| **Nota** | Retângulo redimensionável | Texto livre | — |

- Forma e ícone diferenciam famílias **sem depender de cor**.
- A borda tracejada comunica "não medido".
- Logos de plataforma usam assets locais versionados: Google Ads, Google orgânico, Meta, Facebook, Instagram, YouTube, TikTok, LinkedIn e DV360 são identidades distintas. Aliases antigos migram por `kind`, não por substituição global. Fallback é nome + ícone genérico, nunca imagem quebrada.

### 11.3 Edição inline do rótulo
- Duplo clique no rótulo, `Enter` ou `F2` com o nó selecionado abre um input sobreposto do mesmo tamanho.
- `Enter` e blur confirmam, `Esc` cancela. Máximo de 60 caracteres. Vazio volta ao rótulo anterior.
- Grava em `title` (campo canônico) como **um** comando de histórico.
- Desabilitado no monitor.
- Atalhos globais não disparam enquanto o input tem foco.

### 11.4 Níveis de detalhe por zoom
- **≥ 65%:** tudo.
- **40–65%:** esconde sublabel e badges secundários.
- **< 40%:** forma, nome curto e métrica principal.
- Seleção mostra detalhes pela toolbar e pelo inspetor, fora da escala.
- Nada é reduzido até ficar ilegível.

### 11.5 Estados do nó
Padrão, hover (handles visíveis), selecionado (anel `brand` na forma), com pendência (badge de aviso), bloqueado, placeholder (tracejado + "Configurar"). No monitor: com atividade, sem atividade no período (neutro, não é erro), coleta com falha.

---

## 12. Conexões, grupos e organização

**Organização:** horizontal. Origens à esquerda, páginas e eventos no sentido das conexões, objetivos à direita. Ramificações em linhas, retornos em corredores externos. ELK usa dimensões medidas, 64 px entre nós e 112 px entre camadas, ampliando quando os rótulos exigirem.

- Organizar oferece **Tudo, Seleção e Grupo**, com preview e Desfazer.
- "Organizando…" bloqueia nova solicitação.
- O resultado vira um comando único, aplicado só se a revisão local não mudou (P0 8).
- Nunca cria conexões.
- O monitor oferece "Layout publicado" e "Organizado"; a preferência é local por usuário, fluxo e revisão. Primeira abertura de layout legado irregular usa "Organizado". Consultas de métrica não reexecutam layout nem reenquadram.

**Conexões:**
- Planejada: cinza tracejado. Selecionada: azul.
- Observada: rótulo neutro com volume e taxa. Cor de sucesso ou alerta só quando uma regra explícita justificar. Inatividade não é erro.
- Espessura proporcional ao volume dentro do filtro, com legenda e teto de 5 px.
- Cor de canal nunca representa desempenho.
- Múltiplas entradas e saídas distribuem portas.
- Uma conexão por par de nós. Condições distintas exigem nó de decisão com portas nomeadas, que não executa automação.
- Loops representam navegação observada e usam corredor externo.

**Grupos:**
- Documento v2 ganha `groups[]` (`id`, `name`, `bounds`, `memberIds`) e `groupId` no nó, com validação de referência.
- `x/y` absolutos continuam gravados; o adaptador converte para coordenadas relativas ao `parentId`.
- Colapsar é preferência visual. Conexões internas ficam ocultas, não excluídas. Externas podem ser agregadas visualmente com contagem deduplicada e detalhe das originais.
- Mover o grupo é um comando. Desagrupar preserva posições mundiais.

**Limites:** 200 nós, 300 conexões, config de 256 KB, `x/y` até 10000. O layout detecta falta de espaço e devolve mensagem acionável, sem gerar posições que o backend rejeitaria e sem reduzir escala silenciosamente. O painel Revisão mostra o uso dos limites (ex.: "142 de 200 etapas").

---

## 13. Edição: comandos, histórico, autosave e conflito (novo)

### 13.1 Modelo de comandos
```js
/**
 * @typedef {Object} FlowCommand
 * @property {string} type      // 'move' | 'add' | 'remove' | 'rename' | 'connect' | 'reconnect' | 'layout' | 'group' | 'update-field' ...
 * @property {string} label     // texto para tooltip de desfazer: "Desfazer mover 3 etapas"
 * @property {FlowPatch} forward
 * @property {FlowPatch} inverse
 */
```
- Todo gesto produz **um** comando: arrastar (do início ao fim), organizar, excluir com conexões, colar, agrupar, renomear.
- Digitação no inspetor coalesce por campo enquanto ele tem foco.
- Seleção, viewport e métricas **não** são comandos.
- Histórico de até 100 comandos, em memória. É limpo ao recarregar por conflito ou trocar de fluxo.
- Substitui os snapshots com debounce de 200 ms do `useFlowHistory.js`.

### 13.2 Autosave
- Disparo 1 s após o último comando.
- Uma requisição por vez; mudanças durante o envio entram na próxima.
- Envia a revisão esperada e mantém o mecanismo de concorrência atual.
- Estados no header: "Salvando…", "Salvo às 14:32", "Falha ao salvar · Tentar novamente".
- Falha de validação com `node_ids` seleciona e enquadra os nós envolvidos.

### 13.3 Conflito
Diálogo "Este fluxo foi alterado em outra aba ou por outra pessoa":
- **Recarregar:** descarta o local.
- **Manter minha versão:** só para quem tem permissão de edição; sobrescreve com a revisão nova como base.

A versão local fica em memória até a decisão. Nada é descartado sem escolha explícita.

### 13.4 Atalhos
| Ação | Atalho |
|---|---|
| Selecionar / mover | `V` / `H` |
| Desfazer / refazer | `⌘Z` / `⌘⇧Z` |
| Copiar / colar / duplicar | `⌘C` / `⌘V` / `⌘D` |
| Excluir | `Delete` / `Backspace` |
| Renomear | `Enter` / `F2` |
| Ajustar à tela / zoom na seleção | `⇧1` / `⇧2` |
| Buscar e adicionar bloco | `/` |
| Fechar contexto | `Esc` (fecha popover, depois painel, depois seleção; nunca navega) |
| Lista de atalhos | `?` |

Nenhum atalho dispara com foco em campo de texto.

---

## 14. Explorador e inspetor

**Explorador:**
- Abas Origens / Páginas / Eventos, com busca por nome, URL ou evento.
- Filtros: No fluxo, Disponíveis no site, Com atividade, Com falha.
- Cabeçalho mostra "filtrados de total".
- Paginação real, sem corte silencioso em cinco itens.
- Cada linha tem miniatura/ícone, nome, detalhe, estado e ação: **Localizar** (já no grafo; seleciona e enquadra em `freeArea`) ou **Adicionar**.
- Adicionar insere no centro de `freeArea` ou ligado à conexão selecionada, com o novo nó selecionado e o inspetor aberto.
- Eventos são deduplicados pela identidade medida. Ocorrências somam só quando a divisão por origem é disjunta; sessões nunca somam.
- Evento já mapeado oferece Localizar e "Conectar a este bloco".

**Inspetor — editor:**
- Cabeçalho: ícone, tipo, nome, fechar.
- **Essencial:** nome, página/domínio, evento ou plataforma.
- **Medição:** o que dispara a etapa, último evento correspondente, instrução de instalação.
- **Organização** (recolhida): grupo, entrada, descrição.
- **Conexões:** entradas e saídas com Localizar.
- Rodapé: Remover (terciária destrutiva) com undo imediato via toast.

**Inspetor — monitor:**
- Resumo, URL, publicação, sessões, eventos, avanço, origem dos dados, série temporal no período.
- Duas saúdes independentes: HTTP e coleta.
- Conexão selecionada mostra origem, destino, sessões, denominador, taxa e período.
- Nenhum campo editável.

---

## 15. Monitoramento

**Primeiro conteúdo é o mapa.** Resumo recolhível no topo do canvas: sessões de entrada, sessões com conversão e taxa do funil. O bloco "Agora" é separado. Tabelas e histórico ficam em Explorar/Detalhes.

**Camadas:** Volume, Taxa de passagem, Agora, Disponibilidade HTTP, Saúde da coleta. Padrão: Volume + Taxa. Cada camada tem legenda curta com a regra de atualização.

### 15.1 Contrato de leitura
| Indicador | Definição |
|---|---|
| Sessões da etapa | `COUNT DISTINCT session_id` que correspondem à etapa na revisão e no período |
| Eventos | Ocorrências; podem superar sessões |
| Passagem A → B | Seção 3 e 6.1 |
| Taxa A → B | Passagens / sessões de A no mesmo escopo; denominador 0 → "Não disponível" |
| Conversão do funil | Sessões com objetivo posterior à entrada / sessões que entraram; união entre objetivos |
| Agora | Seção 3 |
| Saída observada | Seção 3 |
| Não avançaram | Seção 3 |
| Receita e investimento | Só com integração de moeda e atribuição compatíveis; site, mídia e CRM identificados |
| Disponibilidade | Status e horário da última checagem HTTP, com cobertura |

- Taxas de ramificações podem somar mais de 100%; o detalhe explica o motivo, sem normalizar.
- Sem ROI ou Forecast estimado nesta adequação.
- Alertas descritivos usam "Não avançaram" com numerador e denominador. "Queda em relação ao período anterior" exige período equivalente e cobertura suficiente. Nenhum diagnóstico causal.

### 15.2 Estados vazios e primeiro uso (novo)
| Situação | O que aparece |
|---|---|
| Fluxo sem publicação | Mapa do rascunho esmaecido + "Publique este fluxo para começar a medir" + ação Editar |
| Publicado, Super Tag sem eventos do site | Checklist: tag instalada? domínio correto? último evento recebido do site; ação Copiar Super Tag |
| Publicado, eventos do site mas nenhum da etapa | Etapa neutra, "Sem atividade no período", sugestão de revisar a regra no editor |
| Filtros sem resultado | "Nenhuma sessão com esses filtros" + Limpar filtros |
| Falha de consulta | Estado de erro com mensagem, `request_id` e Tentar novamente; mapa mantido com métricas "Não disponível" |
| Revisão antiga selecionada | Faixa "Visualizando a publicação de 12/09"; "Agora" indisponível |

### 15.3 Tempo real
- Polling de 15 s só com a aba visível, **uma requisição por vez**.
- Envia `since` (último cursor de transição) para receber só o novo.
- Backoff em falha: 15 → 30 → 60 s, com estado "Atualização com falha · tentando novamente às 14:33". Volta a 15 s no primeiro sucesso.
- Mostra "Atualiza a cada 15 s · última às 14:32:10".
- Pausa manual disponível. SSE fica fora do escopo e a UI não promete streaming.

### 15.4 Animação
- O marcador de última transição do `FlowLiveEdge` é portado para o edge do React Flow.
- O primeiro snapshot é referência. Só IDs novos pulsam.
- Trocar filtro ou revisão, reconectar ou abrir a página não reproduz lote antigo.
- Pulso de até 1,8 s, respeita `prefers-reduced-motion`, não representa uma pessoa por partícula.
- Contadores atualizam sem mudar o tamanho dos nós (largura mínima e `tabular-nums`).

---

## 16. Contratos de backend

Preservar gravação, publicação, versionamento e concorrência. Acrescentar sem remover consumidores durante a migração.

- **`GET /flow/flows/:id/journey`** aceita `revision`, `from`/`to` ou `days`, `account_id`, `campaign_id`, `platform`.
  - Retorna config da revisão, métricas por `node_id` e `edge_id`, `scope`, `timezone`, `generated_at`, `coverage` e estado de disponibilidade por métrica.
  - Sem parâmetros novos, mantém o comportamento atual.
- **`GET /flow/flows/:id/live?since=`** devolve snapshot leve da publicação atual: `active_window_seconds`, `generated_at`, `node_presence`, transições após o cursor, `next_cursor`, `status`.
  - Escopo: todas as origens, indicado na UI. Revisão antiga → `unavailable`.
- **`GET /flow`** fica para biblioteca e contexto. O tick live deixa de recarregar histórico, descoberta e agregados caros.
- **Disponibilidade** devolve `checked_pages`, `total_pages`, `coverage`, `revision`. URLs únicas processadas em lotes até o limite de nós.
- **Erros JSON padronizados:** `{ code, message, field_errors, node_ids, edge_ids, request_id }`. Nenhum HTML em rota de API. O cliente nunca converte falha em lista vazia.
- **Frontend separa** documento persistido, seleção/viewport, métricas e requisições. Métricas nunca entram no PATCH. Respostas antigas são canceladas (`AbortController`) ao trocar fluxo, cliente, revisão ou filtro.
- **Preferências** (viewport, painéis, camadas) em cache local por usuário + cliente + fluxo + modo (+ revisão no monitor). Sem tokens nem dados pessoais. Não incrementam revisão.
- **Schema:** `groups`, `groupId` e metadados de asset com allowlist, validação de referência, limites e testes de round-trip. Publicações antigas continuam legíveis.

### 16.1 Orçamento de performance (novo)
| Operação | Meta (p95) |
|---|---|
| `/live` | ≤ 300 ms |
| `/journey` 30 dias, cliente de maior volume | ≤ 1,5 s |
| Abrir editor com 200 nós e 300 conexões | Interativo em ≤ 1,5 s; pan/zoom a 60 fps |
| ELK com 200 nós | ≤ 1 s, fora da thread principal se passar disso |

- Rodar `EXPLAIN ANALYZE` das consultas novas no maior cliente e anexar ao commit.
- Índices candidatos: `(client_id, occurred_at)` e `(session_id, occurred_at, id)` na tabela de eventos, se ainda não existirem.
- Se `/journey` ultrapassar a meta: agregado diário por revisão para dias fechados + consulta direta só para hoje.
- Se o ELK ultrapassar a meta: rodar em Web Worker (o bundle `elkjs` já oferece).

---

## 17. Miniaturas reais de páginas (detalhado)

O campo `thumbnail_asset_id` já existe, mas serviço e autorização não. Não tratar o campo como funcionalidade pronta.

- **Captura:** navegador headless (Playwright/Chromium) em worker. Usar a fila ou job runner do repo; se não houver, tabela de jobs no Postgres com worker simples.
- **Segurança (SSRF):**
  - Só domínios do cliente já validados.
  - Resolver DNS e bloquear IPs privados, loopback, link-local e metadata em **cada** salto de redirecionamento e em **cada** requisição do navegador (interceptação de rede).
  - Só portas 80/443. Sem cookies, credenciais, downloads nem permissões de browser.
- **Parâmetros:** viewport 1280×800, timeout 15 s, captura acima da dobra, saída WebP de até 200 KB e 640 px de largura.
- **Cache:** por URL normalizada e cliente. Recaptura automática após 7 dias; manual pelo inspetor.
- **Quota:** 200 capturas por cliente por dia.
- **Estados:** sem captura, na fila, capturando, disponível (com data), falhou (motivo), desatualizada.
- **Acesso ao asset:** endpoint autenticado que valida o cliente. Nunca URL pública previsível.
- Falha de captura nunca impede medir a página.

---

## 18. Integrações e CRM

**Futuro:** o cliente é o limite de isolamento. Cada integração pode ser associada a uma conta autorizada; o bloco referencia `integration_id` e `account_id` validados no servidor. Credenciais ficam no backend. Remover integração não apaga histórico confirmado.

**Nesta adequação:**
- O inspetor mostra "Representação de CRM".
- Dá acesso ao webhook de conversões do cliente, com escopo real ("Recebe confirmações de todo o cliente, atribuídas por visitante e campanha").
- Mostra "API para seu CRM · Em breve".
- Conectar uma seta a um bloco de CRM não dispara nada.

**Fase futura separada:** conexão por conta, teste de credencial, escopos, último envio, logs, revogação, deduplicação, fila e retries. Só então há blocos executáveis. `client_id` informado pelo emissor nunca altera o escopo da credencial.

---

## 19. TypeSafe: assistência com evidência

Reaproveitar a classificação de papel de página com `Choice` + `none`, o cache de 15 min, a guarda por revisão, o hash de evidência e o limite de 50 análises por cliente a cada 24 h.

**Usos:**
- **Papel da página:** a partir de título, heading, formulário e caminho reais. Mostra a evidência e "Aplicar ao rascunho".
- **Etapa desejada → candidatos:** escolher entre páginas e eventos já encontrados no catálogo, com `none` quando nenhum serve.
- **Agrupamento semântico:** só como proposta revisável, depois do agrupamento determinístico por domínio e seção.

**Limites:**
- Nunca usar IA para coordenadas, taxas ou identidade de visitante.
- Sugestões obsoletas ou sem evidência ficam bloqueadas.
- Falha do provedor mantém tudo manual disponível.
- Confiança significa concentração da distribuição, não "vai funcionar". Mostrar alternativas e nunca tratar alta confiança como aprovação.
- Nunca inferir abandono, receita, conversão, entrega de webhook ou causa de queda a partir do texto de uma página.

**Avaliação antes de qualquer inferência nova:** conjunto com formulário, botão de compra sem confirmação, obrigado, conteúdo ambíguo, erro, subdomínio e página com instrução maliciosa. Medir acerto de papel, escolha de `none`, latência e falhas.

Fontes: [índice](https://docs.typesafe.ai/llms.txt), [confiança](https://docs.typesafe.ai/confidence), [seleção entre candidatos](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook).

---

## 20. Biblioteca, modelos e exportação

**Biblioteca:**
- Grid ou lista com miniatura do grafo (renderer compartilhado em modo estático), nome, domínio, estado de rascunho/publicação, saúde da coleta e atualização.
- Busca e filtros: Rascunho, Publicado, Com atenção.
- CTA "Criar fluxo". O card abre o último modo usado, com Editar e Monitorar explícitos.

**Modelos** (vazio, leads, compra, webinar, WhatsApp):
- Preview pelo renderer compartilhado.
- Lista de URLs e eventos a conectar.
- Páginas descobertas são candidatas e só preenchem após escolha. Placeholders não viram páginas medidas.
- Nenhum número demonstrativo.

**Exportação PNG/SVG:**
- Mesmo renderer. Inclui título, cliente, período, revisão, legenda e horário dos dados.
- "Rascunho" no editor; filtros ativos no monitor.
- Sem painéis, menus, tokens ou snippet.
- Forecast, slides e recomendações ficam para depois.

---

## 21. Permissões (novo)

Mapear para os papéis que já existem em Acessos; se os nomes diferirem, usar os existentes.

| Ação | Leitura | Edição | Administração |
|---|---|---|---|
| Biblioteca, monitor, exportar | ✓ | ✓ | ✓ |
| Editar rascunho, organizar, simular | — | ✓ | ✓ |
| Publicar, restaurar versão | — | ✓ | ✓ |
| Copiar Super Tag, ver webhook | — | ✓ | ✓ |
| Excluir fluxo | — | — | ✓ |

- O servidor valida tudo. O frontend só esconde.
- O editor aberto por usuário de leitura redireciona para o monitor.

---

## 22. Copy e estados padrão (novo)

| Situação | Texto |
|---|---|
| Consulta válida com resultado zero | `0` |
| Sem dados para medir | Não disponível |
| Origem sem vínculo a conta ou campanha | Sem vínculo |
| Recurso não entregue | Em breve |
| Etapa sem atividade no período | Sem atividade no período |
| Métrica parcial | `38 de 40 páginas verificadas` |
| Presença | `12 sessões agora` |
| Salvamento | Salvando… · Salvo às 14:32 · Falha ao salvar |
| Placeholder | Configurar etapa |
| Etapa visual | Etapa visual · não medida |

- Português em toda a UI; nomes técnicos (`event_name`) só no inspetor.
- Nunca usar "—" como valor.
- Sentence case. Verbo nos botões.

---

## 23. Instrumentação do produto (novo)

Eventos internos no mecanismo de analytics do próprio Reports, sem dados pessoais:
- `flow_editor_opened`, `flow_monitor_opened` (com `flag`, largura da viewport)
- `flow_node_added` (`kind`, origem: paleta, explorador, busca, modelo)
- `flow_layout_applied` (escopo, duração, sucesso)
- `flow_publish_attempted` / `flow_publish_blocked` (motivos)
- `flow_conflict_shown`, `flow_save_failed` (`code`)
- `flow_layer_toggled`, `flow_export`

**Métricas de sucesso da adequação**, comparando flag ligada × desligada:
- tempo até a primeira publicação;
- % de fluxos publicados com ao menos uma etapa com atividade em 7 dias;
- sessões de monitor por fluxo publicado;
- taxa de falha de salvamento.

---

## 24. Fases, tamanhos e rastreabilidade

Tamanhos: **P** ≤ 1 dia · **M** 2–4 dias · **G** 1–2 semanas. Commits pequenos por item, cada um compilando e com a flag desligada funcionando.

| Fase | Trilha | Entregas | Seções | Tam. | Critério para seguir |
|---|---|---|---|---|---|
| **0.0** | — | Estabilizar working tree local | 1 | P | Tree limpo, build passa |
| **0A** | Dados | P0 1–6, consulta de passagens, regras da seção 3, erros JSON | 3, 6, 16 | G | Fixtures da seção 25 passam; nenhuma falha exibida como zero |
| **0B** | Workspace | P0 7–10, flag, adaptadores canônicos, validação compartilhada | 6, 7 | M | Round-trip do schema; um erro por operação |
| **1** | Workspace | Rotas, header, rail, coordenador de painéis, React Flow nos dois modos (monitor ainda com métricas atuais) | 8, 9, 10 | G | Mesma navegação, zoom e seleção nos dois modos; nenhum painel cobre controles |
| **2** | Workspace | Catálogo, linguagem de formas, rótulo inline, comandos, autosave, conflito, reconexão, ELK com guarda, grupos | 11, 12, 13 | G | Undo restaura estado completo; sem perda no autosave; mapa de referência reproduzível |
| **3** | Junção | Métricas no mapa, camadas, Agora, saúde, filtros, estados vazios, polling com backoff | 15, 16 | G | Cada número tem definição e escopo; polling não move o mapa; pulso só por ID novo |
| **4** | Ambas | Explorador completo, catálogo de eventos, miniaturas reais, modelos, TypeSafe, CRM no inspetor | 14, 17, 18, 19, 20 | G | Localizar/Adicionar corretos; captura com fallback; sugestões com evidência |
| **5** | — | Exportação, acessibilidade, remoção do SVG/CSS antigo e da flag, documentação | 20, 22, 25 | M | Só o renderer compartilhado atende editor, monitor e exportação |

**Ativação da flag:**
- Fim da Fase 2: CENTRALCOMM.
- Fim da Fase 3: pilotos.
- Fase 5: todos, com a flag removida.

---

## 25. Testes e aceite

**Ferramentas** (usar as do repo; se faltar, adicionar só estas):
- **pytest:** consultas com fixtures de sequência, schema, versões, live, permissões.
- **Vitest + Testing Library:** adaptadores, catálogo, comandos e histórico, coordenador de painéis, formatação.
- **Playwright:** fluxos E2E e screenshots de regressão nas viewports listadas, com flag ligada.

**Cenários:**
- **Navegação:** link direto, refresh, back/forward, aliases `flow_view`, troca de cliente, retorno com filtros.
- **Dados:** A→B; A→não mapeada→B; A→A→B; A→B→A; conversão antes e depois da entrada; várias entradas e objetivos; dois eventos na mesma URL; subdomínios; virada do período no fuso do cliente; sessão cruzando meia-noite.
- **Métricas:** zero real, fonte indisponível, falha de API, amostra vazia, divisão por zero, revisão antiga; nunca somar sessões nem moedas.
- **Live:** primeiro snapshot sem pulso, repetido sem pulso, ID novo com pulso, reentrada, saída, aba oculta, offline, backoff e retomada, movimento reduzido. Filtro histórico não altera "Agora".
- **Persistência:** arrastar, agrupar, organizar, renomear inline, copiar/colar, excluir com conexões, undo/redo; conflito entre abas; salvar e publicar concorrentes; ELK atrasado; sair com pendência.
- **Geometria:** cadeias, 10→1, 1→10, ciclos, isolados, grupos abertos e fechados, 200/300, falta de espaço com erro compreensível.
- **Visual:** 1920×1080, 1440×900, 1366×768, 1024×768, tablet; zoom do navegador 200%; nomes longos; sem logo; captura com proporção diferente; light e dark se o tema suportar.
- **Interação:** mouse, trackpad, toque, teclado; arrastar e clicar para adicionar; reconectar; Shift; `Esc` em camadas; atalhos não capturam digitação.
- **Acessibilidade:** tabulação, rótulos em português, foco ao abrir e fechar painéis, contraste, estados por texto e ícone, lista equivalente para quem não usa o canvas.
- **Isolamento:** conta, campanha, asset e integração de outro cliente recusados; leitura não muta; captura não alcança destino privado nem por redirecionamento.
- **Rollout:** flag desligada idêntica à produção atual; ligar e desligar sem perda; documento v2 aberto pelo editor antigo sem apagar campos.
- **Build:** testes existentes de flow, schema, versions e live; build de Reports; diff de bundles; cache busting.

**Condição final:** o usuário abre o fluxo, reconhece as URLs, organiza ou inspeciona o caminho, entende cada número e volta ao mesmo ponto. Falhas de coleta, edição e integração têm mensagens próprias, sem banners sobrepostos, métricas falsas ou ações decorativas.

---

## 26. Riscos

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Extração de `main.jsx` quebra telas fora de Fluxos | Média | Alto | Extrair por módulo atrás da flag; Playwright nas telas vizinhas |
| `/journey` lento em clientes grandes | Média | Alto | `EXPLAIN` na Fase 0A, índices, agregado diário |
| Números mudam após o P0 e geram desconfiança | Alta | Médio | Nota de mudança na UI ("Cálculo de passagens atualizado em …") e comunicação aos clientes piloto |
| Escopo cresce com as referências (Forecast, slides) | Alta | Médio | Itens fora de escopo listados nas seções 15 e 20 |
| SSRF no serviço de captura | Baixa | Crítico | Regras da seção 17 com testes de redirecionamento e rede privada |
| Conflito de edição simultânea perde trabalho | Baixa | Alto | Seção 13.3; versão local mantida até decisão |
| Assets de marca incorretos ou fora da diretriz | Média | Baixo | Assets oficiais versionados, sem recolorir logos |

---

## 27. Decisões pendentes do produto

O Codex não decide estes pontos. Até haver resposta, usa o padrão indicado e deixa uma nota no commit.

1. **Fim de sessão:** a ingestão já define? Se não, confirmar 30 min.
2. **Fuso do cliente:** existe configuração por cliente? Padrão: `America/Sao_Paulo`.
3. **Clientes piloto** da flag além de CENTRALCOMM.
4. **Infraestrutura de captura:** há worker ou fila no servidor para Playwright? Padrão: tabela de jobs no Postgres.
5. **Publicar:** qualquer editor ou só administração? Padrão: editor.
6. **Retenção das capturas:** padrão de 90 dias sem uso → remover.
7. **Comunicação da mudança de números** do P0 aos clientes atuais.