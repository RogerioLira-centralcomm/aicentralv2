# Reports · Fluxos como mesa infinita madura — análise e plano

**12/10/2026.** Análise feita só pela leitura do código (`frontend/reports-v1/FlowCanvas.jsx`, `FlowsPage.jsx`, `FlowMonitorWorkspace.jsx`, `FlowEdgeActivity.jsx`, `flowStages.js`, `flowOrigins.js`, `flowLayout.js`, `FlowPagePicker.jsx`, `useSitePages.js`, `cadu_connect/reports_flow.py`). Nada foi alterado. Referência visual enviada: um editor de automação em mesa infinita, com etapa numerada, chip de categoria, portas com nome, "+" no fim da cadeia e traço contínuo/tracejado com significado.

---

## 1. Diagnóstico

### 1.1 Erros ao arrastar (confirmados no código)

| # | O que acontece para a pessoa | Causa no código |
|---|---|---|
| A1 | **A conexão some** ao arrastar um nó para a esquerda de quem aponta para ele. Também some uma conexão nova feita "para trás". | `commitDrag` regrava `stage: stageAtX(x)` a cada arraste (`FlowCanvas.jsx:355`). Se o destino passa a ficar numa etapa anterior, `isReturnEdge` vira verdadeiro e `funnelEdges(..., {returns: showReturns})` **oculta a aresta** enquanto "mostrar retornos" está desligado (padrão). O mesmo vale para `onConnect`. |
| A2 | A **etapa do nó muda sozinha** (Entrada → Exploração…) só por mudar de posição; a faixa de etapas, o minimapa e as cores se reorganizam. | Posição e semântica estão acopladas: o arraste altera `stage`, que alimenta relatórios, faixas (`FlowLanes`), cor do minimapa e alças de retorno. |
| A3 | A conexão **troca de lado** de repente (sai pela esquerda e entra pela direita, laranja tracejada). | É consequência da A1: aresta de retorno usa `left-out`/`right-in`. |
| A4 | Arrastar para cima ou para a esquerda da origem faz **toda a seleção pular de volta**. | Coordenadas presas em 0..10.000 (`commitDrag` e `_normalize_flow_config`, `reports_flow.py:566`). Numa mesa infinita, isso parece um bug. |
| A5 | Soltar um bloco da paleta, ou ligar um nó novo pelo "arrastar da alça", faz o nó **aparecer longe do cursor**. | `addNode` usa `x: stageX(stageAtX(point.x))` (`FlowsPage.jsx:302`): o x vai para a coluna da etapa e só o y respeita o ponto solto. |
| A6 | Blocos adicionados por clique **ficam um sobre o outro**. | O y sai de `100 + floor(index/3)*232` e o x da coluna, sem checar colisão. |
| A7 | No trackpad, **rolar com dois dedos dá zoom** e arrastar o fundo faz seleção, não move a mesa. | `panOnDrag=[1,2]` (só botão do meio/direito), sem `panOnScroll` e sem espaço+arrastar. Num Mac, o gesto natural de mover a mesa não funciona no editor. |
| A8 | Duplicar ou colar uma página **inventa um endereço** `/nova-etapa-xxxx`. | `pasteSelection` reescreve `path` (`FlowsPage.jsx:306`). O nó parece medido, mas aponta para uma URL que não existe. |
| A9 | "+" numa conexão sempre cria uma **Condição** chamada "Novo nó". | `insertOnEdge` fixa `type:'condition'`. |
| A10 | No monitoramento, os cards **não se movem**: o arraste vira pan. | `FlowMonitorWorkspace` passa `readOnly`. Só existe "Organizar"; não há como afastar um card que cobre outro. |

> Vale reproduzir A1–A7 num teste de navegador antes de corrigir (fase 0). A1, A4 e A5 são determinísticos pela leitura do código.

### 1.2 Traços no monitoramento

- Todas as arestas são bezier `getBezierPath`, saindo sempre de `right-out`. Com várias saídas do mesmo nó, as curvas **se sobrepõem na porta** e cruzam cards. O ELK calcula `SPLINES`, mas as rotas dele são descartadas: só as posições são usadas.
- A espessura segue o volume (`1.5 + 7·√(sessões/máx)`), mas **nada explica isso** na tela.
- A legenda é uma frase solta no rodapé ("Azul: Conexão do fluxo · cinza tracejado: planejada · laranja tracejado: Retorno"). Ela não cobre: saída (laranja pontilhado até "Saiu sem converter"), caminho sugerido (cinza 3/6), simulação (verde animado), pontos de tráfego, ponto verde "operacional" e pulso azul de "nova passagem".
- O rótulo da aresta só aparece com métrica ou hover, e vários rótulos disputam o mesmo ponto médio.
- Com uma seleção, as demais arestas ficam com opacidade 0,25, mas os nós não esmaecem. O foco fica ambíguo.
- Não existe camada de **taxa de passagem** (% do nó anterior) separada de volume. A camada "Presença agora" apenas apaga as arestas.

### 1.3 Criação de nós

- Um nó novo **não se conecta**. Só existem: (a) a alça arrastada até o vazio (quick-add), (b) `wireNewNodes`, que liga **apenas origens** à página de entrada, e (c) "Ligar sequência" pela ordem visual.
- Uma página nova nasce como `status:'planned'` e sem endereço. A pessoa precisa abrir o inspetor e procurar no seletor (`FlowPagePicker`), mesmo quando o site já foi importado (`useSitePages` / descobertas) e o servidor já sabe **qual página vem depois de qual** (`page_transitions`, `reports_flow.py:1197`).
- O quick-add só oferece Página, Formulário e Conversão.

### 1.4 Mesa infinita: o que falta para parecer madura

Comparado à referência e a ferramentas como n8n, Figma ou Miro:

- Não há "+" fantasma no fim de cada cadeia, nem número de etapa.
- O chip de categoria/etapa não fica acima do card.
- As portas não têm nome. Hoje são seis alças sem rótulo, quatro delas "aux" e invisíveis.
- Faltam espaço+arrastar, zoom em %, "ir para seleção", busca na mesa (⌘K) e alinhar/distribuir seleção.
- Falta guia de alinhamento magnético ao arrastar (só existe grade).
- Desfazer existe (`useFlowHistory`), mas sem atalhos visíveis nem toast "Desfazer" depois de ações automáticas, como ligações criadas pelo sistema.

---

## 2. Princípios do redesenho

1. **Posição não é semântica.** Arrastar move, nunca muda etapa, função ou visibilidade de conexão. A etapa só muda por ação explícita (inspetor, menu ou "Organizar por etapas").
2. **Toda ação automática é visível e reversível**: toast com "Desfazer" e marca `origin:'auto'` no nó ou na aresta.
3. **Todo traço tem legenda.** Cada estilo de traço tem uma entrada na legenda, e a legenda só lista o que está na tela.
4. **Uma mesa, dois modos**: editar e monitorar usam o mesmo canvas, os mesmos gestos e a mesma legenda. Muda só a camada de dados e o que salva.

---

## 3. Plano por fases

Cada fase fecha com testes e captura de tela em 1280/1440/1920. Sem migração de banco, exceto a decisão da fase 1 sobre coordenadas.

### Fase 0 · Reproduzir e travar (½ dia)
- Teste de navegador `tests/frontend/reports-flow-drag.test.cjs`, no padrão dos `reports-flow-m*-browser`, com fixture local e **sem tocar no banco de produção**:
  - arrastar o nó B para a esquerda de A → a aresta A→B continua visível;
  - arrastar abaixo de 0 → a posição é mantida;
  - soltar da paleta em (x, y) → o nó nasce no ponto solto;
  - quick-add → o nó nasce no cursor e já ligado;
  - colar uma página → `path` preservado ou vazio, nunca inventado.
- Teste unitário de `commitDrag`, extraído para função pura em `flowDrag.js`.

### Fase 1 · Correções de arraste (1–2 dias)
- **A1/A2/A3:** tirar `stage` de `commitDrag` e de `onNodesChange`. A etapa vem de `node.stage` explícito ou de `stageFor` (tipo/rota), nunca do x. "Retorno" passa a ser **orientação explícita** da aresta (`edge.kind==='return'`, marcada pela pessoa ou pelo "Organizar"), e não uma inferência por coluna. Aresta desenhada pela pessoa **nunca é ocultada**: o filtro de retornos vale só para arestas `origin:'observed'|'auto'`.
- **A4:** o servidor passa a aceitar coordenadas em −50.000..50.000. O cliente deixa de prender coordenadas e, ao salvar, normaliza transladando o mapa inteiro se precisar. Confirmar que `sync_published_steps` e a coleta não leem x/y.
- **A5/A6:** o nó nasce no ponto solto. Sem ponto, nasce à direita do nó selecionado ou do último nó da cadeia, com busca de vaga livre: o mesmo laço de colisão do `flowLayout.js`, extraído para `findFreeSlot`.
- **A7:** `panOnScroll` + `zoomOnPinch` + ⌘/Ctrl+roda para zoom + **espaço+arrastar** para mover; arrastar o fundo continua fazendo seleção. Exibir zoom em % no controle.
- **A8:** colar mantém o `path` original e marca o nó como `planned` com aviso "endereço repetido".
- **A9:** "+" na aresta abre o mesmo menu de tipos do quick-add.
- Guias de alinhamento magnético (bordas e centros dos vizinhos) durante o arraste; Alt desliga, como já acontece com a grade.

### Fase 2 · Nó novo que se conecta e se resolve sozinho (2–3 dias)
**Conectar:**
- Clique na paleta com um nó selecionado → cria à direita e liga `selecionado → novo`.
- Sem seleção → liga a partir do **nó terminal da cadeia principal** (o mais à direita, sem saída e que não seja conversão ou nota). Origem nova continua no `wireNewNodes`.
- "+" fantasma à direita de todo nó sem saída, como na referência. Ele abre o menu de tipos e cria já ligado.
- Toda ligação automática gera aresta `origin:'auto'` e toast "Conectado a ‹A› · Desfazer".

**Resolver a página (site importado):**
- Ao criar um nó Página/Formulário/Conversão, se o domínio do fluxo tem catálogo (`/flow/site-pages`) **ou** descobertas:
  1. **Próxima página observada:** novo endpoint leve `GET /flow/flows/<id>/next-pages?from=<host,path>` reaproveitando a consulta `page_transitions`. Ordena as páginas que mais vêm depois do nó de origem.
  2. **Heurística por tipo:** Formulário → caminhos com `contato|orcamento|agendar`; Conversão → `obrigado|sucesso|confirmacao`; Página após a home → as mais visitadas.
  3. **Sitemap:** busca normal.
- Com uma sugestão de confiança alta (ex.: ≥ 40% das passagens), o nó já nasce com `host/path/title`, `status` real e `origin:'auto'`, além de pedir a captura automaticamente. Senão, nasce com um **seletor inline no próprio card** (combobox curto com as 5 melhores) aberto e focado, sem precisar do inspetor.
- Nó com endereço resolvido automaticamente mostra o selo "sugerido pelo site · trocar".
- Sem site importado: nada muda (fica planejado), com um link "Importar páginas do site".

### Fase 3 · Traços e legenda (2 dias)
- **Roteamento:** usar as rotas do ELK (`edge.sections`) quando o mapa foi organizado. Com posições manuais, usar `getSmoothStepPath` com raio, alternável por "Traços: curvos / ortogonais". Distribuir várias saídas da mesma porta (deslocamento vertical por índice) para não sobrepor.
- **Vocabulário único de traço** (tokens em `flow-canvas.css`):

  | Traço | Significado |
  |---|---|
  | contínuo azul, espessura ∝ volume | caminho medido |
  | contínuo cinza fino | conexão desenhada, ainda sem dados |
  | tracejado cinza 6/6 | planejada (origem ou link de site) |
  | tracejado laranja 3/5 com seta de volta | retorno |
  | pontilhado laranja até "Fim da visita" | saída sem converter |
  | tracejado cinza 3/6 | caminho sugerido pela navegação real |
  | verde animado | simulação |
  | pontos em movimento / ponto verde / pulso azul | tráfego, coleta saudável, nova passagem |
- **Legenda flutuante** (canto inferior, recolhível, mesma no editor e no monitor). Ela é gerada a partir dos estilos **presentes na tela**, com amostra SVG real de cada traço e uma escala de espessura ("fino ≈ 10 sessões · grosso ≈ 1.200"). Clicar numa entrada destaca só esse tipo de traço.
- **Rótulos:** pílula com `sessões · % do passo anterior`. Rótulos colidindo são afastados ao longo da curva. Com zoom < 0,55 mostram só o número.
- **Foco:** ao selecionar, esmaecer também os nós não relacionados e destacar o caminho a montante e a jusante (duplo clique = caminho completo).
- **Camadas no monitor:** Volume · Taxa de passagem · Presença agora · Saídas. Cada uma reescreve espessura, rótulo e legenda, em vez de apagar as arestas.

### Fase 4 · Aparência de mesa infinita madura (2–3 dias)
- **Card:** chip de etapa acima (Origem/Entrada/…), número da etapa em ordem topológica, ícone/favicon, título, endereço e métricas. Alças visíveis só no hover, com **portas nomeadas** quando fizer sentido: Formulário → "enviou" / "abandonou"; Condição → "sim" / "não". Nas demais, porta única de entrada e de saída.
- **Barra superior compacta:** nome · salvo há x · Desfazer/Refazer · Editar|Monitorar · Publicar.
- **Controles da mesa:** zoom %, ajustar, ir para a seleção, minimapa, alinhar/distribuir quando houver mais de um nó selecionado.
- **⌘K:** buscar nó ou página e ir até ela.
- **Atalhos:** `N` novo nó ligado, `C` conectar selecionados em sequência, `⌘D` duplicar, `⌘G` agrupar, `?` lista de atalhos.
- **Monitor permite mover cards** em modo "arranjo da tela": salvo por fluxo/revisão em `localStorage`, nunca na publicação. Botão "Voltar ao arranjo publicado".

### Fase 5 · Verificação e entrega (1 dia)
- Testes das fases 0–4, `npm run build` e passada no navegador do editor e do monitor com um fluxo publicado real. O ambiente local usa o **banco de produção**: só leitura, ou com fluxo de teste criado para isso.
- Atualizar `docs/reports-flow-workspace-plan.md` com o vocabulário de traços e os gestos.

**Estimativa total:** 9–12 dias de trabalho, entregáveis por fase. Fase 1 sozinha já resolve os erros de arrastar relatados.

---

## 4. Decisões pendentes

1. **Coordenadas fora de 0..10.000:** ampliar o limite no servidor (recomendado) ou manter o limite e só normalizar no cliente?
2. **Etapa do nó:** concorda que arrastar nunca mais muda a etapa, e que o "Organizar por etapas" é quem alinha colunas?
3. **Página automática:** preencher sozinho quando a confiança for alta, ou sempre abrir o seletor com a sugestão marcada?
4. **Monitor com cards móveis:** arranjo pessoal (localStorage) ou arranjo compartilhado salvo no fluxo?
5. **Feature flag:** as mudanças entram direto, ou atrás de `flows_workspace_v2` (hoje liberado por cliente via `REPORTS_FLOWS_WORKSPACE_V2_CLIENTS`)?

---

## 5. Execução · 12/10/2026

Decisões tomadas com as recomendações acima: limite de posição ampliado para ±20.000 no servidor; arrastar nunca muda a etapa; página preenchida sozinha quando a evidência é clara; arranjo do monitor guardado só no navegador de cada pessoa; sem feature flag.

**Feito**
- A1–A9: arraste só espacial (`flowDrag.js · applyDrag`); conexão desenhada à mão nunca é ocultada (`origin:'manual'`); mesa sem parede em 0; nó solto nasce no cursor; vaga livre (`findFreeSlot`); trackpad move a mesa (`panOnScroll`, pinça para zoom, espaço+arrastar); setas movem por grade (Shift = 5×); colar mantém o endereço e marca como planejado; "+" na conexão escolhe o tipo.
- A10: cards do monitor podem ser arrastados; arranjo salvo por publicação no navegador, com "Voltar ao arranjo publicado".
- Fase 2: nó novo continua o card selecionado ou a única ponta aberta do caminho; "+" fantasma em todo card sem saída; `GET /api/v2/reports/flow/site-pages/next` ranqueia páginas (navegação observada → padrão do tipo → catálogo). Preenche sozinho com ≥ 40% das passagens e ≥ 5 visitas, ou um único padrão claro; senão, o seletor mostra as sugeridas primeiro. `pathSource:'suggested'` persiste.
- Fase 3: lados da conexão pela posição real (`edgePorts`), retornos em arco por baixo, conexões que dividem um lado se abrem em leque, rótulos sobrepostos são afastados, traço curvo/ortogonal, legenda gerada do que está na tela com escala de espessura e filtro por tipo; ligação com tráfego medido deixa de parecer "planejada".
- Fase 4 (parte): número da etapa em ordem de leitura e chip de etapa sobre o card (substitui os rótulos de coluna que se sobrepunham), foco esmaece cards não relacionados, zoom em % com volta a 100%, "Adicionar etapa depois" no menu do card.

**Testes:** `tests/frontend/reports-flow-drag.test.mjs`, `tests/frontend/reports-flow-board-browser.test.cjs` (capturas `output/reports-workspace-qa/board-*.png`), `tests/test_reports_flow_infinite_board.py`; suíte de fluxos verde.

**Ficou para depois:** guias de alinhamento magnético, alinhar/distribuir seleção, portas nomeadas (enviou/abandonou), rotas do ELK (`edge.sections`) e as camadas Taxa/Saídas no monitor.

## 6. Páginas do fluxo · 12/10/2026

- **Limite:** o fluxo segue até **20 páginas** (um grupo conta como 1). Montagens automáticas (descoberta e blueprint) continuam começando com 6 (`SUGGESTED_FLOW_PAGES`).
- **Aba "Páginas"** (Editar · Revisão · **Páginas** · Monitorar; o monitor tem atalho): `GET /api/v2/reports/flow/flows/<id>/pages?days=7|30|90`, eventos da Super Tag do site (mesma fonte da Página 360).
  - **Nota de uso 0–100** por página: tempo ativo mediano (cheio em 45 s) 25 · rolagem 50%/75% 25 · avanço para a próxima etapa desenhada (cheio com 50%) 30 · permanência no site (100 − saída) 20. Sinais que não se aplicam saem e os pesos são renormalizados. Sem nota abaixo de 20 sessões e nas etapas de conversão. Faixas: ≥ 70 bom uso, 40–69 atenção, < 40 crítico. A nota aparece também no card do mapa.
  - **Sem tráfego:** etapas do fluxo sem sessão no período (com orientação ao gestor e "Ver no mapa") e páginas do sitemap sem visita (busca, até 300 listadas, total sempre informado).
- Testes: `tests/test_reports_flow_pages.py`, `tests/frontend/reports-flow-board-browser.test.cjs` (capturas `board-pages-*.png`).
