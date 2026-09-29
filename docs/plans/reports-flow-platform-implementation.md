# Reports / Fluxos — planejamento de implementação

Data: 29/09/2026. Revisão 4: revisão TypeSafe, escopo client_id, associações opcionais, edição contínua, públicos e Growth. Estado: planejamento, sem migrações ou implementação de produto nesta entrega.

## 1. Objetivo e decisões de produto

Implementar a direção aprovada em `output/mockups/reports-flows-platform.html` no Reports existente. Desktop é o ambiente principal; tablet deve permitir trabalho real com toque, caneta, mouse e teclado. Celular mostra uma orientação para abrir em tablet ou desktop.

O mockup é referência de linguagem visual, não especificação de capacidades prontas. Métricas demonstrativas, ciclos e botões decorativos precisam dos contratos e estados descritos abaixo.

Decisões:

- TypeSafe atua como assistência semântica opcional, com evidências e sugestões revisáveis; permissões, números, listas de remarketing e execução são determinísticos. Integração e aceite na seção 21.

- Todo recurso Reports pertence ao escopo `(organization_id, client_id)`. Marcas e projetos são contextos opcionais disponibilizados explicitamente ao cliente; não condicionam operação nem alteram atribuição. Mapeamento transversal na seção 20.

- Construtor e Análise são telas distintas do mesmo fluxo e usam o mesmo grafo persistido.
- Construtor não exibe contagens, taxas, tendências ou KPIs. Exibe configuração, integridade, associação de evento e estado de salvamento.
- Análise exibe dados observados por período e fonte, sem permitir arrastar ou editar o grafo. Selecionar etapa abre detalhamento analítico.
- Distinguir blocos de representação de jornada de ações executáveis. Remarketing inclui segmentação persistida e saída por webhook com fila de entrega no escopo funcional. E-mail e integrações de mídia só executam ações com conector habilitado. Recursos Growth futuros aparecem como “Em breve”, conforme seção 17.
- Fluxos podem ser editados continuamente, inclusive após publicação. O banco mantém o draft completo e revisões publicadas imutáveis desde a primeira entrega. Salvar altera o draft; publicar ativa uma revisão nova atomicamente. A versão vigente continua coletando durante a edição. O bloqueio atual de edição deve ser substituído; despublicar não é pré-requisito para editar.
- Reentrada é parte necessária dos exemplos complexos; deve ter semântica validada no frontend e backend, sem depender de uma seta decorativa.
- Usar nomenclatura consistente: Biblioteca, Construtor, Análise, Instalação e Validação. Simular sempre identifica dados fictícios.

## 2. Evidência no repositório e lacunas

Inspeção estática realizada; não foi executado o backend nem confirmada a aplicação das migrações em nenhum ambiente.

| Área | Evidência observada | Trabalho necessário |
| --- | --- | --- |
| Interface | `frontend/reports-v1/main.jsx`, componente `Flow` | Dividir estado e componentes; eliminar manipulação direta de DOM da busca |
| Visual | `frontend/reports-v1/flow-workspace.css`, `styles.css` | Substituir overrides acumulados por estilos escopados e tokens |
| Build | React 18.3, Vite 6, Tailwind 3.4 no `package.json` | Spike isolado antes de adotar componentes Untitled que dependam de outro pipeline |
| Untitled UI | `frontend/cadu-design-system/UNTITLED-UI.md` | A documentação registra ponte inicial e integração real ainda pendente; não anunciar adoção completa |
| Logos | `FlowPlatformLogo` e SVGs em `static/images` | Catálogo único; Google Ads deve ter marca correta de Ads; Google genérico e Facebook não substituem silenciosamente todas as marcas |
| Persistência | `_normalize_flow_config` e PATCH em `reports_flow.py` | Revisão concorrente, schema versionado e campos novos explicitamente permitidos |
| Limites | 100 nós, 300 conexões, configuração até 256.000 bytes | Indicar limites antes da falha; verificar desempenho com essa carga |
| Coordenadas | `x/y` inteiros, intervalo 0–10000 | Adaptador do canvas deve respeitar limites; pan e zoom são estado de apresentação |
| Tipos | source, page, form, event, condition, delay, segment, conversion, webhook, whatsapp, error | Definir propriedades persistidas e capacidades reais de cada tipo |
| Conexões | id, from, to, label normalizados | Acrescentar portas e tipo de conexão; validar IDs únicos, duplicações e ciclos |
| Publicação | Normalização e exigência de pelo menos uma etapa medida | Relatório de validação com entrada, alcance, campos obrigatórios e reentrada |
| Simulação | POST /test grava em `cadu_reports_flow_events_test`; rejeita fluxo publicado | Migrar simulação para a revisão draft, mesmo quando existir versão publicada; separar teste de instalação real |
| Métricas | GET /flow retorna canvas_nodes, canvas_edges, page_transitions, confirmed | Agregação por conexão, comparação, séries e disponibilidade por fonte |
| Ciclos | `connectNode` no frontend bloqueia ciclos; normalizador backend não mostra validação equivalente de ciclos | Resolver divergência antes de habilitar reentradas |
| Autosave | Estados e salvamento já presentes no `Flow` | Serializar gravações, conflito entre abas, recuperação e saída segura |
| Descoberta | Rotas de descoberta, consulta e seleção de páginas | Progresso, parcial, retomada, revisão e tratamento de falha |
| Saúde do site | `reports_flow_monitor.py`, /monitor e /monitor/check | Distinguir verificação HTTP de página, instalação da tag e performance do funil |

Arquivos de apoio: `reports_supertag.py`, `reports_flow_monitor.py`, `reports_v1.py`, `docs/reports-flow-workspace-plan.md`, migrações `add_reports_*flow*` e `add_reports_site_journey_analytics.sql`. Conferir esquema instalado antes de preparar migrações incrementais.

## 3. Direção visual e componentes

Aplicar o skill frontend-design já lido e a direção aprovada. O mapa é o elemento central; controles e navegação ficam discretos. Alinhamento de textos à esquerda nos painéis, conteúdo visual centralizado nos blocos compactos.

Tokens iniciais, a consolidar na camada CADU:

| Papel | Valor inicial |
| --- | --- |
| Superfície | #FFFFFF |
| Canvas | #F8FBFF |
| Texto principal | #17243B |
| Texto secundário | #637591 |
| Ação/conexão selecionada | #087DFF |
| Borda/grade | #E3EAF3 |

Estados usam tokens semânticos de sucesso, aviso e erro do design system. Logos conservam cores de marca. Não colorir cada card por canal. Fonte Inter local com fallback sans-serif; controles 12–14 px, títulos de painel 14 px, cards 12–13 px na escala 100%, métricas 18–22 px. A exportação reduzida não define a legibilidade do produto.

Shell: rail de 56–64 px, header de 56–64 px, paleta de 220–240 px, inspetor de 280–320 px. Painéis recolhíveis. Canvas recebe todo o espaço restante, sem cabeçalho editorial promocional. A seleção do cenário usada no mockup vira navegação real pela Biblioteca.

Famílias de nós:

- Origem: logo correto, plataforma, campanha opcional e associação rastreável.
- Página: miniatura aprovada ou preview estrutural claramente ilustrativo, título e caminho.
- Formulário: página associada e campos configurados, sem valores pessoais coletados.
- Evento: ícone, nome do evento e critério de correspondência.
- Condição/segmento: resumo da regra e portas nomeadas.
- Espera: janela definida, sem prometer execução automática.
- Conversão: evento observado ou confirmação externa identificados como fontes diferentes.
- Reentrada: conexão explícita com motivo e janela, visualmente distinguível por rótulo e traço.

Biblioteca de assets: manifest com platformId, nome, arquivo, variante e texto acessível. Miniaturas com tamanho máximo, cache, estado indisponível e alternativa sem screenshot. Upload/captura de páginas precisa de serviço validado; não usar captura arbitrária de URLs no navegador do usuário.

Untitled UI: wrappers CADU reais para Button, Input, Select, Tabs, Dialog, Dropdown, Tooltip, Checkbox e Toast. Confirmar proveniência/licença dos componentes e construir fronteira de estilos de Reports no spike. Não importar reset global que afete outros produtos.

## 4. Telas e navegação

| Tela | Conteúdo e ações |
| --- | --- |
| Biblioteca | Busca, estado, domínio, saúde da tag, atualização, abrir Construtor ou Análise, criar fluxo |
| Criar fluxo | Nome, URL, verificação de domínio, instalação existente e descoberta opcional |
| Construtor | Nome editável, salvo/pendente/erro, paleta, páginas descobertas, canvas, inspetor, desfazer/refazer, simular, publicar |
| Análise | Período, comparação, filtros suportados, mesmo mapa, indicadores por etapa/conexão, KPIs e detalhe da seleção |
| Instalação | Domínio, snippet, estado da tag, último evento real e validação real |
| Revisão para publicar | Bloqueios/avisos acionáveis, seleção e enquadramento do bloco afetado |
| Simulação | Cenário fictício e percurso; resultado explicitamente separado de eventos reais |

Preservar inicialmente URLs existentes: `flow_view=create|edit|monitor`, `flow_id` e contexto `client_id`. Sincronizar back/forward via popstate, não apenas replaceState. Filtros de análise persistem na URL; zoom, pan e painéis são preferências locais por usuário/cliente/fluxo. Alterar modo não perde edição: aguardar save ou permitir recuperação quando falhar.

Botões decorativos do mockup só entram no produto com comportamento e estado definidos. Permissões de leitura e escrita precisam ser verificadas no servidor em toda mutação.

## 5. Viewports, tablet e teclado

Desktop preferencial não significa exigir mouse. Regras por largura CSS útil e capacidade de entrada; não usar user-agent ou orientação isoladamente para classificar dispositivo.

| Área útil | Composição proposta |
| --- | --- |
| ≥1440 px | Paleta e inspetor podem coexistir; manter ao menos 720 px de área útil de canvas |
| 1180–1439 px | Um painel lateral expandido por vez quando necessário; outro como drawer |
| 768–1179 px | Tablet compacto: rail reduzido, um drawer sobreposto de cada vez; toolbar simplificada e canvas preservado |
| <768 px de largura de layout | Tela de orientação, sem inicializar editor pesado; ação copiar link e voltar ao Reports |

Texto do celular: **“Abra este fluxo em um tablet ou computador.”** Complemento: “A mesa de fluxos precisa de uma tela maior para organizar etapas e conexões.” Oferecer “Copiar link” e “Voltar ao Reports”. Um desktop em janela estreita recebe a mesma orientação de ampliar a janela. Tablets compactos abaixo do limite podem receber sugestão de orientação horizontal; a edição nunca aparece espremida.

Cuidado com teclado virtual: elegibilidade usa largura de layout estável, nunca apenas altura de `visualViewport`. Ao abrir o teclado, manter seleção, zoom, estado e drawer; tornar o formulário interno rolável e trazer o campo focado à vista. Não chamar fit-to-view em cada resize de teclado. Usar `100dvh` com fallback e safe-area; observar VisualViewport apenas para posicionar controles e evitar oclusão.

Tablet com teclado físico não tem detecção confiável universal. Aceitar eventos de teclado quando chegarem; todos os comandos continuam disponíveis por botão. Considerar `any-pointer` e `any-hover` como sinais de capacidade, não como identificação de dispositivo. Trocar de toque para trackpad durante a sessão deve funcionar sem remount.

Alvos: botões de toque ≥44×44 px; handles podem ser visualmente pequenos, mas com área de captura de 44 px. Tooltips por foco e alternativa por toque; nenhuma função exclusiva de hover, duplo clique ou clique direito. Drawer com foco contido, retorno de foco e fechar visível. Stylus usa Pointer Events e rejeição de gesto cancelado, sem tratar caneta como mouse obrigatoriamente.

## 6. Interações do canvas

| Intenção | Desktop / teclado | Tablet / toque | Persistência |
| --- | --- | --- | --- |
| Adicionar bloco | Clique ou drag da paleta | Toque em bloco, depois local no canvas; drag opcional | Nó + posição |
| Selecionar | Clique; navegação pela lista acessível | Toque | Local |
| Mover | Arrastar card; setas quando canvas focado | Arrastar card após limiar de movimento | Commit único ao soltar |
| Pan | Espaço + arrastar, botão do meio, modo mão | Um dedo no fundo | Local |
| Zoom | Controles; pinch de trackpad; Cmd/Ctrl+roda no canvas | Dois dedos + controles | Local |
| Conectar | Arrastar handle ou “Conectar a…” | Tocar saída e depois destino | Edge com IDs e portas |
| Cancelar | Escape | Botão cancelar e pointercancel | Não grava |
| Editar conexão | Clique no traço ou lista de conexões | Toque em área ampliada | Label/tipo/portas |
| Multisseleção | Shift + clique ou retângulo em modo seleção | Modo seleção + toques | Local; movimento conjunto grava |
| Desfazer/refazer | Cmd/Ctrl+Z, Shift+Cmd/Ctrl+Z | Botões | Histórico de alterações do grafo |
| Excluir | Delete/Backspace fora de inputs | Menu de seleção | Undo; operação composta para nó e edges |
| Ajustar mapa | Botão; atalho indicado no menu | Botão | Local |

Não capturar atalhos quando foco está em input, textarea, select ou contenteditable. Não bloquear zoom de acessibilidade da página globalmente. Aplicar touch-action apenas ao canvas necessário; painéis continuam com rolagem nativa. Pointer capture para drag; tratar pointercancel, perda de foco, segundo dedo e rotação.

Motor de interação com estados explícitos: idle, panning, dragging, connecting, selecting. Histórico registra comandos completos; arrastar não cria uma entrada por frame. Snap em coordenadas do mundo, não coordenadas da tela. Conversão entre viewport e mundo usa a mesma matriz para drop, hit testing e conexões.

Conexões: calcular âncoras por tamanho medido e porta selecionada; manter nós e edges no mesmo sistema de coordenadas. Roteamento evita retângulos dos nós, prevê corredores de retorno, rótulos e setas. Não depender de percentuais independentes ou de DOM redesenhado inteiro a cada gesto. Hit area do edge maior que o traço visível. Autosize, fontes, resize e recolhimento de painéis não podem desalinhar conexões.

Estudar motor de canvas mantido versus implementação própria em spike: compatibilidade React 18, licença, touch, acessibilidade, tamanho do bundle, roteamento, minimapa, undo e serialização. A decisão final de biblioteca e versão depende desse resultado; não instalar nova stack na fase de planejamento.

## 7. Arquitetura React/JavaScript

```text
frontend/reports-v1/flow/
  FlowWorkspace.jsx          contexto, modo e navegação
  FlowLibrary.jsx            busca e lista
  FlowHeader.jsx             nome, publicação e salvamento
  FlowEditor.jsx             composição sem métricas
  FlowAnalysis.jsx           composição somente leitura
  canvas/                    viewport, nodes, edges, minimapa, tools
  panels/                    palette, discoveries, inspector, filters
  dialogs/                   create, validation, simulation, install
  state/                     reducer, commands, history, selectors
  api/                       client, adapters, error mapping
  assets/                    manifest de logos e ícones
  flow-tokens.css             aliases da skin Reports
  flow-workspace.css          escopo exclusivo
```

Usar JavaScript com JSDoc e validação do payload no limite da API; não introduzir migração global para TypeScript. Estruturas estáveis com IDs; adaptadores convertem x/y e from/to do backend para a API do motor escolhido.

Separar estado persistido (nodes, edges, nome, revisão), estado da UI (seleção, viewport, painéis, histórico) e estado remoto (discovery, métricas, permissões, requests). Metrics nunca são anexadas ao draft para salvar. Abortar requisições obsoletas ao trocar cliente/fluxo/filtros e rejeitar respostas atrasadas por request key.

Autosave: debounce inicial 800 ms após comando concluído; uma gravação por vez, fila com snapshot mais recente. Estados salvo/pendente/salvando/falha/conflito. Idempotência ou revisão esperada impede sobrescrita silenciosa. Salvar antes de publicar; não publicar revisão diferente da revisada. Cache local de recuperação por identidade e fluxo, com expiração, limpeza em logout e política para dispositivos compartilhados; servidor continua sendo autoridade.

## 8. Mapeamento de API atual

Prefixo observado: `/connect/api/v1/reports` após registro do blueprint. Preservar contexto de seleção/autorização existente.

| Ação UI | Rota existente | Observação |
| --- | --- | --- |
| Carregar biblioteca/grafo/análise | GET /flow | view, flow_id, client_id, days, datas, plataforma, conta, campanha |
| Verificar domínio | GET /supertag/site-check | Usada pelo frontend atual; validar tratamento de falhas |
| Criar fluxo | POST /flow/flows | name, allowed_host, tag opcional, config; retorna flow/tag/site |
| Salvar draft | PATCH /flow/flows/:id | name/config; retorna 409 se publicado |
| Publicar | POST /flow/flows/:id/publish | Hoje exige etapa medida; ampliar validação |
| Despublicar | POST /flow/flows/:id/unpublish | Retorna draft; investigar impacto na coleta e comunicar |
| Simular eventos | POST /flow/flows/:id/test | Até 30 eventos fictícios; somente draft |
| Descobrir páginas | POST /flow/flows/:id/discover | Suporta descoberta parcial e retomada conforme estado atual |
| Consultar descoberta | GET /flow/flows/:id/discoveries | Run e páginas |
| Adicionar página descoberta | POST /flow/flows/:id/discoveries/:page_id/select | Sincroniza página, etapa e nó; evitar duplicação de autoridade com save do grafo |
| Configurar verificação de páginas | PATCH /flow/flows/:id/monitor | Frequência/ativação; não equivale a analytics |
| Verificar páginas agora | POST /flow/flows/:id/monitor/check | Apenas publicado |
| Mapear etapas | POST /flow/steps; PATCH /flow/steps/:id; POST /flow/steps/:id/archive | Preservar vínculo de campanha, tag e URL |
| Coletar | POST /flow/collect e POST /flow/collect/:code | Endpoints de tracking; não usados como gravação do editor |

Erros padronizados propostos: code, message, field_errors, node_ids, edge_ids, request_id. Tratar 400/403/404/409/413/429/5xx, offline, timeout e sessão expirada. Nunca converter falha em “zero eventos”.

## 9. Backend pendente e contratos propostos

As rotas/campos desta seção são propostas, não APIs existentes verificadas.

### P0 — segurança de gravação e schema

- `schema_version` explícito em config; migração de configurações antigas sem perda.
- `revision` e comparação atômica no UPDATE. PATCH leva `expected_revision`; resposta retorna nova revisão; conflito responde 409 com metadados atuais. Sem último escritor silencioso.
- Propriedades novas allowlisted: thumbnail_asset_id, description, platform_id, condition, duration, segment_ref; normalizador atual descarta campos desconhecidos dentro dos nós.
- Edge: from_port, to_port, kind (normal/reentry), condition_ref. IDs únicos, duplicatas e portas válidas.
- Preservar normalização de caminhos/domínios e isolamento organization/client; verificar autorização também para assets e referências externas.

### P0 — validação e ciclos

Propor `POST /flow/flows/:id/validate` retornando revision, errors e warnings. Reutilizar o mesmo serviço dentro de publish, transacionalmente.

Bloquear campos obrigatórios ausentes, referência inválida, edge sem nó/porta, etapa medida sem correspondência, loop não declarado e ausência de entrada alcançável para etapas medidas. Avisar sobre nós desconectados, saídas sem conversão e fonte sem associação. Entrada e regra de alcance precisam atender fluxos importados, sem presumir que todo nó source é evento medido.

Reentrada permitida somente por edge declarada, com janela e critério claros. Não executar recursão livre. Medição conta sessão/lead segundo contrato temporal; simulação limita passos e visitas. Enquanto não implementado, sinalizar reentrada indisponível e bloquear publicação desse caminho. Resolver divergência entre frontend que proíbe ciclos e backend que hoje aceita pares válidos sem análise do ciclo.

### P1 — analytics por grafo e fonte

GET atual já retorna alcance/progresso por nó e transições de página. Isso não prova métricas por cada conexão configurada. Não somar `progressed` como se fosse um total exclusivo de funil.

Propor endpoint dedicado `GET /flow/flows/:id/analytics` ou extensão versionada do GET atual, escolhendo após medir custo. Contrato: período/timezone, filtros aplicados, versão do grafo, collected_at, disponibilidade, KPIs, série temporal, nodes e edges indexados por ID, comparação anterior e proveniência.

- Alcance: sessões distintas com evento que corresponde ao nó.
- Passagem A→B: sessões que visitaram A e depois B dentro da janela definida; definir se transição direta ou eventual por edge.
- Taxa por edge: sessões de passagem / sessões elegíveis na origem. Denominador explícito.
- Branches não são necessariamente exclusivas; não exigir soma 100% em percursos não exclusivos.
- Zero = medição disponível sem ocorrência; null = sem integração/dado; erro = consulta falhou; pendente = processamento.
- Período anterior com mesma duração e timezone; base zero mostra “sem base de comparação”.
- Campanhas e mídia paga não podem atribuir sessões apenas pela presença de logo no mapa.
- E-mail aberto/enviado exige conector do provedor; visita à página não substitui esse dado.
- Venda/receita CRM exige evento externo reconciliado, moeda, deduplicação e vínculo ao fluxo. `confirmed` atual é agregado e não comprova atribuição por nó/receita.
- Dispositivo, país e filtros ausentes permanecem indisponíveis até contrato e dados existirem. Não mostrar controles que aparentam filtrar sem efeito.
- Reentrada exige ordem temporal, política de repetição e janela de atribuição. Mesmo timestamp, sessões sem ID e eventos tardios precisam de regra.

### P1 — visual e observabilidade

Serviço de miniaturas com allowlist de domínio, proteção SSRF/rede privada, limite de bytes, timeout e cache; armazenar referência de asset em vez de imagem base64 no grafo. Preferir preview estrutural enquanto não houver serviço.

Instrumentar falhas de autosave, conflitos, latência, publicação e agregação sem conteúdo pessoal. Saúde da tag deve usar último evento real, sem confundir HTTP 200 do site com instalação funcionando.

### P0 — versionamento; P2 — integrações avançadas

Revisões publicadas imutáveis, draft paralelo, rollback explícito e analytics associado à versão são obrigatórios na primeira entrega, conforme seção 15. Comparar versões sem remapear silenciosamente dados históricos. Conectores de CRM/e-mail com webhooks idempotentes e reconciliação; a entrega inicial de públicos e webhooks já exige fila, retries, limites, credenciais e auditoria; automações Growth entram posteriormente.

## 10. Cenários completos de entrega

Aquisição: Meta, Google Ads, Instagram e influenciadores convergem para captura; formulário validado leva a boas-vindas, página de vendas, checkout e confirmação. Ramo alternativo: webinar, presença, oferta. Abandono abre remarketing e reentrada com janela. Os ramos configurados ficam visíveis sem contadores no editor; análise conserva IDs e associa somente métricas disponíveis.

B2B: LinkedIn, busca e parceiros → página de solução → formulário → qualificação → SDR → reunião → proposta → ganho/perda. Lead não qualificado segue nutrição; ausência na reunião segue reagendamento com retorno declarado. Score e CRM são referências externas até existir execução/integrador; não prometer cálculo ou mensagens automáticas só pelo desenho.

Criar fixtures com a complexidade de 18–25 nós e 25–40 conexões, incluindo ramificação, convergência, reentrada, nó sem dado, erro de associação e resultados distintos. Os exemplos menores do mockup continuam como referência visual, não como teste de complexidade.

## 11. Sequência de implementação e entregáveis

| Fase | Escopo | Entrega verificável / dependência |
| --- | --- | --- |
| 0. Contratos e baseline | Inventário runtime/migrações, schema, capacidades, mapa de APIs, spike Untitled e motor canvas | ADRs de build/canvas, matriz de capacidades; precede código estrutural |
| 1. Shell e biblioteca | Tokens, logos corretos, header/rail, criar/abrir, rotas e bloqueio mobile | Desktop + tablet navegáveis, componentes reais e sem controles inertes |
| 2. Editor | Modelo/reducer, paleta, inspetor, páginas, canvas/portas, pan/zoom, histórico, seleção | Cenários complexos editáveis e viewport estável; depende do contrato do grafo |
| 3. Persistência/publicação | Draft contínuo, snapshots publicados, ativação atômica, autosave concorrente, recuperação, validação e simulação do draft | Editar publicado sem interromper coleta; round trip completo e rollback auditado |
| 4. Monitoramento e públicos | Contadores por nó/edge, recálculo versionado, filtros, duas listas de remarketing, outbox e entregas webhook | Eventos reais, deduplicação, transição de público e reprocessamento sem repetir ações |
| 5. Tablet e robustez | Teclado virtual/físico, toque, caneta, resize, acessibilidade, performance | Matriz de dispositivos e cenários atendida; iniciado desde fase 1 |
| 6. Rollout | Flag de experiência, piloto por cliente, observação e retorno ao editor anterior | Ativação gradual e rollback de UI sem perda de configuração |

Cada fase gera checklist de aceite e diff revisável. Não estimar prazo fechado antes do spike de canvas e auditoria do esquema instalado. Caminho crítico: schema/revisão → editor persistente → validação/reentrada → analytics do mesmo grafo. Contratos podem ser definidos antes da construção visual de todas as telas.

## 12. Verificação planejada e critérios de aceite

Plano de testes para implementação futura; não executado nesta entrega documental.

- Unitários úteis: transforms screen/world, validação, normalização, comandos/undo, regra temporal e denominadores.
- Integração: create/save/load, schema round trip, revisão concorrente em duas abas, isolamento entre clientes, permissão viewer, publish após save, eventos fictícios fora de métricas reais.
- Browser: abrir URL direta, back/forward, busca/paleta, drag/conectar por click, escolha de página descoberta, erros/offline e recuperação.
- Geometria: 100 nós/300 edges, resize, zoom, labels longos, painéis alternados, fontes carregadas; sem extremidades soltas ou linhas cruzando cards em cenários aprovados.
- Viewports: 1920×1080, 1440×900, 1280×800; tablet 1366×1024, 1194×834, 1024×768, 834×1194, 768×1024; celular 390×844 e janela desktop estreita.
- Tablet real: Safari/iPadOS e Chromium/Android, teclado aberto/fechado, rotação no meio da edição, caneta, trackpad e teclado Bluetooth. Emulação não comprova comportamento do teclado do sistema.
- Acessibilidade: fluxo completo por teclado, foco em drawers, nomes de botões/portas, alternativa textual do grafo, contraste e zoom 200%. Compatibilidade assistiva real antes de declarar acessibilidade completa.
- Performance: medir pan/drag com carga limite; meta inicial de fluidez próxima de 60 fps em desktop e sem travamentos >100 ms em tablet de referência, ajustada após baseline. Sem refetch integral por pointermove.
- Visual: screenshots separadas de Construtor e Análise; sem métricas no primeiro, logos corretos, miniaturas disponíveis/fallback honesto, texto legível a 100%, controles não sobrepostos.
- Aceite final: nenhum filtro sem efeito, nenhum KPI inventado, nenhum estado de erro representado como zero, nenhum controle decorativo apresentado como funcional e nenhuma promessa de automação sem executor.

## 13. Riscos e decisões abertas com encaminhamento

1. Biblioteca de canvas: selecionar em spike com protótipo de 100 nós, touch e grafo serializado atual.
2. Untitled/Tailwind: confirmar fronteira de build antes de importar componentes; manter documentação de proveniência.
3. Reentradas: fechar contrato temporal com tracking e validação, depois habilitar no editor.
4. Publicação: remover o bloqueio de edição; implementar draft e revisão publicada desde a primeira fase funcional. Auditar coleta e migração para preservar a versão vigente.
5. Analytics: confirmar dados por evento e por fonte antes de habilitar cada card do mockup.
6. Dispositivos: definir tablet físico de referência; teclado e altura útil entram no aceite, não em uma correção pós-lançamento.
7. Migração: preservar JSON antigo e rollout por flag; migração de banco deve ser compatível com a UI anterior durante transição.

## 14. Próximo pacote executável

Começar pela fase 0: mapa de schema instalado, contratos de draft/publicação/contadores/públicos, spike de componentes Untitled e canvas, fixtures dos dois fluxos complexos e ADR de entrada por toque/teclado. Em seguida implementar shell, Biblioteca e a política de viewport. A entrega visual aprovada é a referência; o documento existente `docs/reports-flow-workspace-plan.md` permanece como histórico de diagnóstico e este plano detalha sua execução.


## 15. Persistência completa e edição contínua — requisito obrigatório

Esta revisão substitui a proposta anterior de exigir despublicação para editar. Um fluxo é um documento vivo; a coleta usa uma revisão publicada estável enquanto o usuário continua trabalhando.

### Modelo de dados proposto

Nomes abaixo são propostas a ajustar após inspeção das tabelas instaladas; reutilizar `cadu_reports_flow_registry` como identidade do fluxo, evitando catálogo paralelo.

| Entidade | Dados e finalidade |
| --- | --- |
| Flow registry | Identidade, cliente/organização, nome, domínio, draft_revision, active_version_id, estado de publicação |
| Draft do fluxo | Grafo completo, schema_version, revisão de concorrência, autor e updated_at; persistência transacional |
| Versões do fluxo | Snapshot imutável do grafo/configuração, número, hash, autor, data, versão do matcher e regras de públicos |
| Histórico/auditoria | Operação, autor, revisão anterior/nova, publicação, restauração, mudanças de regras e destinos |
| Preferências da mesa | Por usuário/cliente/fluxo: viewport, zoom, painéis, filtros; não altera a lógica publicada |
| Assets | Referências de miniaturas e logos, integridade e variante; sem base64 no grafo |

O documento completo inclui nós, IDs estáveis, posições, dimensões, portas, conexões, rótulos, descrições, domínio/caminhos, regras de correspondência, campanhas, condições, tempo, metas, públicos, referências de ações, variantes visuais, marca, posicionamento de recursos Growth e referências a templates. Campos futuros precisam de schema e round trip, não de descarte silencioso pelo normalizador. Credenciais permanecem em armazenamento de segredos; o grafo guarda apenas referências autorizadas.

Fluxo operacional:

1. Abrir recupera o draft salvo no banco e informa qual versão está ativa.
2. Editar grava continuamente o documento completo com controle de revisão. Alterações não mudam a versão ativa.
3. Publicar apresenta resumo do diff: nós adicionados/removidos, regras alteradas, públicos e destinos afetados.
4. Após confirmação, validar a revisão exata, criar snapshot e trocar active_version_id numa transação. Falha mantém a versão anterior ativa.
5. Coleta recebe versão válida e identifica os eventos com a revisão efetivamente usada; não confiar em IDs arbitrários enviados pelo navegador sem validar tenant/fluxo/versão.
6. Continuar editando usa draft derivado da última versão. Comparar/restaurar uma versão cria novo draft; nunca reescreve o histórico.

Estados independentes: publicação (nunca publicado/ativo/pausado) e draft (salvo/alterado/salvando/falha/conflito). Header pode exibir “Publicado v4 · alterações não publicadas”. Permissões para editar e publicar podem divergir; concorrência usa expected_revision e resolve conflito explicitamente.

Migração: para cada fluxo publicado existente, criar snapshot inicial e draft equivalente; para draft, criar somente draft. Backfill de eventos sem versão recebe marcador legado explícito, sem inventar versão de coleta. Compatibilidade com APIs antigas é transitória e documentada. Não zerar contadores ao migrar ou publicar.

Mudança de regra de um nó mantém identidade visual e histórico, mas produz série versionada; não somar métricas de semânticas incompatíveis sem aviso. Remover nó no draft não remove seus eventos históricos. Sessões em curso ficam vinculadas à versão recebida no início; novas sessões usam a versão ativa. Configuração cacheada precisa de versionamento e invalidação. Eventos atrasados são associados à versão da sessão quando conhecida.

## 16. Contadores, publicação, recálculo e confirmações

Contadores pertencem exclusivamente à Análise. Cada nó medível publicado precisa de: estado de instrumentação, fonte, última atualização, volume deduplicado e detalhamento de eventos que sustentam o número. Nó ilustrativo ou integração ausente exibe “Sem medição configurada”; não inventar um contador de execução.

Pipeline obrigatório: evento recebido → validar consentimento/escopo/versão → deduplicar → armazenar evento → corresponder a nós/regras daquela versão → atualizar agregados por nó/edge → atualizar público → registrar ações elegíveis em outbox → entregar destinos → expor estado na UI. Manter registro bruto dentro da retenção definida e versão do cálculo.

Eventos carregam event_id, flow_id, version_id quando disponível, session_id/visitor_id pseudônimo permitido, occurred_at, received_at, tipo, página e dados mínimos. Conversão externa inclui identificador estável do provedor; retries e dupla coleta cliente/servidor não podem duplicar vendas. Timestamp do cliente deve ser validado; tratar eventos fora de ordem.

Contadores por tipo:

- Origem/página: sessões distintas e eventos, com unidade explícita.
- Formulário: submissões válidas e sessões que enviaram, deduplicadas.
- Condição: elegíveis e correspondências, somente quando avaliador existir.
- Público: membros atuais, entradas/saídas no período e entregas pendentes; não confundir membros com sessões.
- Webhook: enfileirados, entregues, falhos e tentativas; HTTP aceito pelo destino não comprova inclusão em mídia.
- Conversão: observada pelo site e confirmada externamente como métricas distintas; receita somente com dado financeiro válido.
- Growth futuro: visualização, clique, fechamento e conversão atribuída quando houver coletor implementado.

“Recalcular métricas” cria job assíncrono com flow/version, período, filtros, versão do cálculo, requested_by e cursor. O servidor recomputa a partir de eventos disponíveis, não de totais já agregados. UI exibe aguardando/processando/concluído/falhou, progresso quando mensurável e período efetivamente disponível. Usar staging e troca atômica dos agregados para evitar gráficos parcialmente recalculados. Repetir o job com mesma chave não duplica números.

Recálculo não dispara novamente webhooks ou ações Growth. Reconstrução histórica de públicos é uma operação separada; prévia mostra diferença e a aplicação exige decisão explícita. Reenviar eventos a destinos também é uma ação separada e auditada. Informar retenção e lacunas; não prometer reconstrução de eventos já eliminados. Publicação nova não redefine o histórico anterior nem recalcula retroativamente usando regras novas por padrão.

Mensagens e confirmações:

| Situação | Conteúdo esperado |
| --- | --- |
| Autosave concluído | “Alterações salvas no rascunho.” Sem modal a cada alteração |
| Publicar mudanças | “Publicar v5? A versão v4 continuará no histórico.” + resumo de regras/ações afetadas |
| Publicação concluída | “Versão v5 publicada. A coleta está ativa.” Somente após ativação confirmada pelo servidor |
| Nenhum evento real ainda | “Aguardando o primeiro evento desta versão.” Não afirmar que os contadores estão funcionando sem evidência |
| Recalcular | Mostrar período, revisão do cálculo e fontes; indicar que não reenviará ações |
| Job concluído | “Métricas recalculadas para [período].” + horário e eventual cobertura parcial |
| Falha de save/publicação | Preservar draft, explicar erro e oferecer tentar novamente |
| Pausar publicação | Mostrar efeito sobre coleta, públicos e ações antes de confirmar |
| Restaurar versão | Explicar que a restauração cria draft e precisa de publicação |

Meta inicial de frescor: processar contadores em até 60 s sob carga de referência, medir fila/atraso e exibir last_updated. Poll apenas em tela visível, com backoff; avaliar SSE posteriormente. Não vincular frescor analítico ao verificador HTTP de páginas.

## 17. Área Growth — funções “Em breve”

Criar área reconhecível no produto com catálogo, prévias e selo “Em breve”. Não ativar scripts, coletar leads ou apresentar botão “Publicar ação” funcional antes de existir executor. Salvar configuração de planejamento no draft é permitido, com status indisponível explícito; a publicação de tracking pode continuar desde que o recurso futuro fique excluído das ações ativas e isso seja explicado na revisão.

| Recurso futuro | Configuração prevista |
| --- | --- |
| Pop-up de entrada | Páginas, atraso, visitante novo/recorrente, frequência e exclusões |
| Pop-up de saída | Intento de saída suportado, público, frequência e supressão para convertidos |
| Vídeo antes de sair | Player, poster, legenda, CTA, fechar, som controlado pelo usuário e fallback sem autoplay |
| Oferta com outro link | Texto, imagem, CTA, destino validado e parâmetros de atribuição |
| Templates | Galeria por objetivo, prévia desktop/tablet/mobile, duplicar e versionar; atualização de template não muda instâncias publicadas |
| Marca e posicionamento | Cores, tipografia, logo, contraste, posição, margens seguras, tamanho e regras por viewport |
| Conversão | Meta, janela de atribuição, exposição/clique/conversão, exclusões e deduplicação |

Editor administrativo mobile permanece bloqueado conforme a regra aprovada. Os recursos Growth exibidos no site do cliente devem ser responsivos também para visitantes em celular. São superfícies diferentes.

Intento de saída não significa poder impedir fechar uma aba. Desktop pode usar sinais de ponteiro conforme suporte; toque precisa de gatilhos próprios (tempo, scroll ou inatividade), identificados como tais. Não prometer interceptar o fechamento do navegador. Fechar a oferta deve ser acessível, com limite de frequência e supressão após conversão. Remover a oferta não pode impedir navegação normal.

Escopo funcional futuro: renderer versionado, entrega por tag, isolamento de CSS, consentimento, frequência por usuário/sessão, regras de prioridade para evitar overlays concorrentes, preview seguro, publicação, pausa, eventos e atribuição. Não considerar o selo “Em breve” como implementação desses serviços.

## 18. Remarketing — duas listas e ações concretas

Remarketing é um público dinâmico persistido. Webhook é uma saída possível desse público, não a própria lista. No escopo inicial funcional, entregar as duas listas, seu avaliador e saídas webhook com histórico, retries e reconciliação. Integrações nativas de mídia só aparecem habilitadas depois de implementadas e autorizadas.

### Lista A — engajados que não converteram

Regra configurável: entrou no escopo de páginas do fluxo, acumulou pelo menos X segundos de tempo ativo e não possui a conversão-meta dentro da janela relevante. Expor X, meta, janela de observação e retenção do membro como campos independentes. Nenhum limite fixo escondido.

Tempo ativo: medir com visibility/focus e heartbeats enquanto a página estiver visível; definir sessão e somar intervalos validados pelo servidor com teto por heartbeat. Página em background não acumula tempo. Saída súbita não garante último heartbeat; indicar cobertura parcial em vez de deduzir abandono com certeza.

Ao alcançar X segundos, agendar avaliação após uma tolerância configurada para conversões em trânsito. O não convertido é um estado provisório, reavaliado quando houver conversão, expiração ou correção. Antes de despachar webhook pendente, verificar se o membro ainda é elegível. Para mídia, atrasos de sincronização podem existir e precisam aparecer no status.

### Lista B — convertidos

Regra: ocorreu a conversão-meta configurada, com fonte e janela explícitas. Pode usar evento observado ou confirmação CRM, conforme a opção do fluxo; não misturar automaticamente. Conversão prevalece sobre a Lista A: remover da A e incluir na B atomicamente. Ambas usam o mesmo escopo e a mesma identidade de público.

As listas são mutuamente exclusivas para a mesma meta/escopo enquanto a conversão estiver válida. Expiração, estorno ou correção seguem regra declarada e auditada, sem reinscrever silenciosamente para prospecção. Pessoa anônima não deve ser fundida com outra identidade sem vínculo permitido e determinístico. Multi-dispositivo depende de identificação existente; não prometer cobertura universal.

### Ações possíveis

| Público | Ação | Disponibilidade planejada |
| --- | --- | --- |
| Engajado sem conversão | Enviar entrada/saída a webhook de CRM/CDP/automação | Inicial, com endpoint configurado e autorizado |
| Engajado sem conversão | Sincronizar audiência para campanha de recuperação | Conector nativo futuro; depende de credenciais, identificadores elegíveis e regras da plataforma |
| Engajado sem conversão | Exibir oferta de retorno/popup/vídeo | Growth “Em breve” |
| Convertido | Remover/suprimir da recuperação no destino | Inicial via evento de saída/supressão webhook; efetivação depende do consumidor |
| Convertido | Enviar evento a CRM para pós-venda ou lista de clientes | Inicial via webhook |
| Convertido | Campanha de recompra, upsell ou exclusão em mídia | Conector nativo futuro |

Pertencer a uma lista não compra mídia, cria anúncio ou envia e-mail sozinho. Interfaces devem mostrar público, ação, destino e resultado de entrega separadamente.

### Persistência e entrega

Entidades propostas: audience_definitions (meta, regras, X, janelas, versão), audience_memberships (identidade, público, elegibilidade, entrada, expiração, motivo), audience_events (entered/exited/converted/suppressed), action_destinations, delivery_outbox e delivery_attempts.

Outbox criada na mesma transação da mudança de público. Worker com entrega pelo menos uma vez, chave idempotente estável, assinatura HMAC, timestamp, retry exponencial, dead-letter e reenviar manualmente. Destino pode receber duplicata: contrato exige deduplicação. Garantir ordenação por identidade/versão ou número de sequência para não aplicar entrada atrasada após exclusão. Credenciais criptografadas e URLs de saída com validação contra acesso a rede privada.

Payload mínimo proposto: event_id, schema_version, flow_id, flow_version, audience_id, action (enter/exit/suppress), subject_ref pseudônimo autorizado, occurred_at, sequence, reason e conversion_ref quando aplicável. Evitar PII bruta por padrão. Segmentar e ativar destinos somente com consentimento/base e identificadores adequados ao canal; exclusão/expiração precisa se propagar ao destino.

Tela de públicos: quantidade atual, motivo de inclusão, X configurado, meta, última avaliação, membros pendentes, estado de sincronização, falhas e ação testar destino com payload fictício identificado. Sem expor identificadores pessoais indiscriminadamente.

## 19. API adicional proposta e aceite da revisão

Rotas ilustrativas a consolidar com o desenho do backend; não são capacidades existentes.

- PATCH /flow/flows/:id/draft: salva grafo completo com expected_revision, mesmo com versão ativa.
- POST /flow/flows/:id/publish: valida draft_revision e ativa snapshot transacionalmente.
- GET /flow/flows/:id/versions e POST /flow/flows/:id/versions/:version/restore: histórico e novo draft.
- POST /flow/flows/:id/metrics/recalculations; GET /flow/jobs/:job_id: reprocessamento e progresso.
- GET/POST/PATCH /flow/flows/:id/audiences: regras e estado das duas listas, com autorização e revisão.
- GET /flow/flows/:id/audiences/:audience_id/members: paginação e filtros, conforme permissão.
- POST /flow/flows/:id/destinations; POST /flow/destinations/:id/test: configurar/testar webhook.
- GET /flow/flows/:id/deliveries; POST /flow/deliveries/:id/retry: auditoria e reenvio explícito.

Aceite adicional obrigatório:

1. Editar/publicar repetidamente não interrompe a versão ativa nem zera seus contadores.
2. Reabrir em outra máquina recupera grafo, propriedades, visual e regras completos do banco.
3. Conflito entre duas abas não sobrescreve edição silenciosamente.
4. Eventos durante troca de versão e eventos atrasados preservam atribuição; históricos incompatíveis não são fundidos.
5. Contadores por nó e edge deduplicam retries; recálculo reproduz resultados sem reenviar webhooks.
6. Visitante com tempo ativo abaixo de X não entra na A; background não soma tempo; conversão durante tolerância impede entrada indevida.
7. Conversão após entrada remove da A e inclui na B; repetir o evento não duplica inclusão/ação.
8. Webhook indisponível acumula retry auditável; ação antiga não desfaz supressão mais recente; dead-letter é visível.
9. Falta de integração ou identidade elegível aparece como indisponível, não como sincronização concluída.
10. Growth futuro aparece “Em breve” e não executa ações; o tracking publicado continua com capacidades efetivamente implementadas.

Sequência atualizada: persistência completa e publicação versionada → coleta e métricas por nó → recálculo → avaliação de públicos → outbox/webhooks → monitoramento operacional. Catálogo Growth pode ser desenhado em paralelo; seu executor é uma etapa futura independente.

## 20. Propriedade por client_id e associações opcionais com Workspace

Revisão 3. Esta seção é transversal: aplica-se ao editor, biblioteca, sites, campanhas, Growth, públicos, métricas, jobs e integrações. Reports tem gestão própria dentro de um cliente. Marca e projeto são associações opcionais; sua ausência não impede criar, editar, publicar, medir ou operar itens.

### Hierarquia e identidade

```text
Organização (limite de acesso)
└── Cliente Reports (client_id; contexto obrigatório)
    ├── Campanhas e contas de mídia
    ├── Sites, tags e páginas
    ├── Fluxos, drafts e versões
    ├── Eventos, conversões e relatórios
    ├── Públicos e destinos de remarketing
    ├── Imports, links, templates e ações Growth
    └── Contextos opcionais disponíveis neste cliente
        ├── Projetos Workspace
        └── Marcas Workspace
```

Todo recurso Reports tem proprietário definido por `(organization_id, client_id)`. Não usar project_id ou brand_id como substituto de client_id. IDs de cliente Reports nativo, cliente legado, marca e projeto pertencem a domínios diferentes: coincidência numérica não é relacionamento.

Uma associação serve para organizar, filtrar, contextualizar e abrir o item a partir de outras áreas autorizadas. Ela não transfere propriedade, não duplica campanha/site/fluxo, não concede acesso automaticamente e não cria dependência de um projeto ou marca para o funcionamento de Reports.

### O que já existe e o que falta

Evidência estática adicional:

- `_selection()` em `reports_v1.py` resolve client_id via `reports_access.resolve`; acesso é resolvido no contexto autorizado.
- `add_reports_native_clients_v1.sql` cria `cadu_reports_clients`, independentes de `tbl_cliente`, e documenta coexistência de clientes legados e nativos.
- `add_reports_workspace_project_links_v1.sql` cria `cadu_reports_campaigns.workspace_project_id`, FK para `cadu_ci_projetos`, com ON DELETE SET NULL e índice organization/client/project.
- PATCH `/api/v1/reports/campaigns/:id/workspace-project` já associa/desassocia projeto de uma campanha, exige admin Reports, valida organização e permissão de ver o projeto, e restringe a campanha ao client_id.
- `_visible_workspace_projects()` busca projetos por `organization_id` e permissão do usuário. No trecho inspecionado não há cadastro de disponibilidade do projeto por cliente Reports. Essa é uma lacuna para o modelo requerido.
- `project_ref` também existe como campo opcional em migração de campanhas. Definir migração/adaptador; não presumir equivalência com workspace_project_id nem operar duas fontes de verdade.
- Marcas do Workspace usam referências próprias, incluindo `studio:<id>`, e projetos usam referências como `ci:<id>`. Resolver por catálogo/repositório canônico, sem inventar FK numérica cruzada.
- Não foi identificado vínculo de marca nos arquivos Reports inspecionados nem associação equivalente de projeto em flow registry e sites. Tratar como pendente até auditoria completa das tabelas e serviços.

### Catálogo de contextos disponíveis no cliente

Introduzir relação explícita de disponibilidade: cliente Reports ↔ projeto Workspace e cliente Reports ↔ marca Workspace. Criar vínculo exige administração do cliente e permissão sobre o destino. O mesmo projeto/marca pode ser disponibilizado a mais de um cliente apenas por decisão explícita; isso não mistura recursos ou métricas entre clientes.

Seletores de item mostram a interseção entre contextos disponibilizados ao client_id e contextos acessíveis ao usuário. Apenas pertencer à organização não torna projeto/marca elegível. Itens já associados, mas inacessíveis ao usuário atual, exibem “Associação restrita” sem revelar nome ou permitir troca silenciosa.

### Matriz de associação

| Item Reports | Propriedade | Marca/projeto opcional | Relação operacional preservada |
| --- | --- | --- | --- |
| Campanha | Cliente Reports | Sim; vínculo de projeto existente a migrar | Conta/plataforma e ID externo da campanha |
| Fluxo | Cliente Reports | Sim | Site/tag, nós, regras, versões e eventos |
| Site / Super Tag | Cliente Reports | Sim | Domínio autorizado e coleta do site |
| Página descoberta | Cliente Reports, vinculada ao site | Contexto efetivo do site; override explícito se necessário | URL, descoberta e associação a nós |
| Conta de mídia | Cliente Reports | Sim, como organização; não restringe autenticação por inferência | Credenciais e conta externa autorizadas |
| Relatório | Cliente Reports | Sim | Filtros, campanhas e recortes salvos |
| Importação | Cliente Reports | Sim | Origem, campanha alvo, lote e decisões de revisão |
| Link Tester / link | Cliente Reports | Sim | Associação operacional a campanha/conta/relatório já existente |
| Público de remarketing | Cliente Reports | Contexto do fluxo por padrão, override explícito | Regras, conversão-meta e associação dos membros |
| Destino webhook | Cliente Reports | Sim, apenas contexto | Credencial, endpoint e autorização; associação não habilita disparo |
| Ação Growth | Cliente Reports | Sim; marca pode fornecer tokens | Fluxo/site, regra e versão publicada da ação |
| Template privado | Cliente Reports | Sim | Versão de template e instância copiada |
| Eventos/conversões | Cliente Reports | Derivado para consulta; sem seleção manual por evento | Site/fluxo/versão/campanha comprovados |
| Job, entrega e recálculo | Cliente Reports | Derivado da operação | Escopo original e referências versionadas |

Templates de sistema são catálogo separado, sem dados de cliente; copiar para uso cria instância pertencente ao client_id. Qualquer compartilhamento futuro entre clientes precisa de ação e permissão próprias.

### Cardinalidade e persistência propostas

Modelo suporta zero ou mais associações de projeto e marca por item, para atender campanhas multimarcas e recursos compartilhados dentro do mesmo cliente. Interface pode começar com um projeto principal e uma marca principal, com associações adicionais em “Mais vínculos”. Um único vínculo por tipo pode ser principal. Marca principal define sugestão visual; nunca misturar automaticamente paletas de várias marcas.

Entidades propostas:

1. `reports_client_contexts`: organization_id, client_id, context_type (brand/project), context_ref canônica, ativo, autor/data e revoked_at. Unicidade por escopo/tipo/ref.
2. `reports_resource_contexts`: organization_id, client_id, resource_type, resource_id, client_context_id, is_primary, autor/data. Unicidade por recurso/contexto e uma associação principal por tipo.
3. Histórico de associação: contexto anterior/novo, recurso, ator, instante, motivo e operação em lote.

Referência polimórfica exige registro de tipos de recurso e validação server-side transacional; não confiar em resource_type livre do cliente. Usar FK composta para o catálogo de contextos e, onde possível, tabelas de vínculo por recurso com FKs concretas. Definir a escolha física no desenho de schema; a integridade entre clientes é obrigatória em qualquer opção.

Revogar disponibilidade de marca/projeto no cliente não apaga recursos Reports: desativa vínculo com histórico. Excluir/arquivar destino não faz cascade para campanha, site ou fluxo. Mudança do client_id proprietário é uma operação de migração separada, fora do seletor de associações.

### Associação, herança e atribuição são conceitos diferentes

- Associação direta: vínculo escolhido no item, editável sem publicar nova lógica de tracking.
- Contexto herdado: por exemplo, página via site ou público via fluxo. UI informa a origem; override explícito prevalece. Alteração do pai não grava cópias silenciosas em todos os filhos.
- Atribuição: campanha, origem e conversão identificadas por evidência de coleta/importação. Vincular um fluxo à mesma marca de uma campanha não atribui conversões àquela campanha.

Projetos podem sugerir suas marcas, mas selecionar projeto não adiciona marca silenciosamente. Em conflito com marca explícita do item, apresentar opção de manter a marca ou trocar. Fluxo e site podem ter vínculos distintos; nenhum deles altera o domínio de coleta ou conta externa por inferência.

Relatórios por associação usam joins/EXISTS e agregação por identidade de evento; nunca duplicar métricas porque um item tem duas marcas ou dois projetos. Definir filtros “qualquer vínculo” versus “principal” e não somar subtotais sobrepostos como total geral. Apresentar contexto atual por padrão; exportação histórica precisa declarar se usa associações da época ou atuais, com histórico para suportar a opção.

### Marca e aparência publicada

Identidade visual sugerida por marca principal: logo, cores, tipografia e assets permitidos. Usuário pode personalizar a instância no Reports. Guardar origem dos tokens, versão da marca e overrides. Publicar Growth congela snapshot visual; mudar a marca no Workspace não altera automaticamente pop-up/oferta já publicada. UI informa “Atualização da marca disponível” e permite aplicar ao draft, revisar e publicar.

Associar marca a fluxo muda organização/contexto imediatamente; qualquer mudança que altere regras, consentimento, destino executável ou aparência publicada exige nova revisão. Não usar associações como atalho para alterar ações ativas.

### Experiência no frontend

- Seletor de cliente no shell é o contexto principal. Marca e projeto aparecem como filtros opcionais ou chips “Associar marca” / “Associar projeto”.
- Biblioteca de campanhas, fluxos, sites e demais itens funciona com “Sem associação”. Não pedir projeto/marca para concluir criação.
- Painel “Associações” no detalhe: vínculo principal, adicionais, origem herdada, remover, abrir destino autorizado e histórico.
- Mudança de cliente limpa seleção, caches, filtros incompatíveis e requisições pendentes; salvar draft pendente antes de trocar. URLs preservam client_id e filtros opcionais.
- Acesso por projeto/marca do Workspace abre Reports com client_id explícito e filtros; mantém o cabeçalho do cliente. Se houver mais de um cliente elegível, selecionar antes de abrir, nunca adivinhar por marca.
- Ações em lote mostram client_id de origem, itens afetados e resultado por item. Falha parcial é explícita e não deve deixar mensagens de sucesso globais falsas.

### Contratos de API propostos

- GET `/reports/contexts?client_id=...&type=brand|project`: destinos já disponibilizados ao cliente e acessíveis ao ator.
- POST/DELETE `/reports/clients/:client_id/contexts/:context_id`: disponibilizar/revogar contexto com permissão administrativa e auditoria.
- GET/PATCH `/reports/:resource_type/:resource_id/associations`: leitura/gravação com client_id obrigatório, expected_revision e validação do recurso.
- Filtros opcionais em listagens: project_ref, brand_ref, association_mode e unassociated. Aplicados somente depois do escopo organization/client.
- Manter rota existente de campanha/workspace-project como adaptador temporário para vínculo principal, sem duas autoridades divergentes.

Todos os caminhos são contratos propostos relativos ao prefixo da API de Reports; padronizar antes da implementação. Contexto no payload ou URL nunca substitui `reports_access.resolve` nem `_write_guard`.

Workers de coleta, recálculo, públicos, entrega e miniaturas recebem scope completo do job e revalidam relações. Chaves de cache, deduplicação, storage e auditoria incluem escopo; não compartilhar por brand_id ou project_id sozinho.

### Migração e aceite

1. Auditar vínculos atuais, client_id nativos/legados, project_ref e workspace_project_id; resolver conflitos por revisão, sem transformar projeto textual em ID arbitrário.
2. Criar catálogo de disponibilidade por cliente. Para campanha com vínculo válido existente, backfill de disponibilidade e associação nesse mesmo client_id, registrando origem da migração. Vínculos inválidos ficam sinalizados, não transferidos a outro cliente.
3. Acrescentar associação de marcas e demais recursos; adaptar seletor atual para não listar toda a organização.
4. Confirmar create/edit/publish/analytics integralmente sem marca/projeto.
5. Testar dois clientes da mesma organização com nomes e IDs externos semelhantes; vínculo de um não aparece nem opera no outro.
6. Testar a mesma marca disponibilizada a dois clientes: nenhum compartilhamento automático de campanhas, fluxo, eventos, segredos ou membros de público.
7. Remover vínculo ou arquivar projeto mantém fluxo publicado, coleta, campanhas e contadores intactos.
8. Alterar associação não reenfileira webhook, recalcula atribuição nem duplica conversão.
9. Usuário sem acesso ao projeto/marca não ganha acesso ao recurso Reports por vínculo, e o inverso também não ocorre.
10. Filtros multimarcas/multiprojetos não duplicam totais; snapshot visual publicado não muda com edição da marca.

Este mapeamento deve entrar na fase 0 de contratos e schema, na fase 1 de shell/bibliotecas e em todos os serviços de persistência/analytics seguintes. Associação é capacidade transversal de Reports, não requisito exclusivo da mesa de fluxos.

## 21. Revisão TypeSafe AI — assistência semântica com contratos tipados

Revisão 4, utilizando o skill `.agents/skills/typesafe-ai/SKILL.md`. Documentação oficial consultada em 29/09/2026: índice, Choice, Noul, Score, Confidence, API e cookbook de entity alignment. As páginas .md falharam nesta consulta; as versões HTML foram acessadas. Esta entrega revisa o planejamento, sem chamadas de inferência, alteração de credenciais ou integração nova em produção.

### Conclusão arquitetural

TypeSafe ajuda onde existe interpretação de conteúdo: função de uma página, pertinência de associação, seleção de template e revisão de evidência. Persistência, autorização, cálculo, publicação, estados de audiência e entrega continuam determinísticos. O produto completo funciona sem inferência disponível. Tipagem da resposta não comprova sua verdade.

Prioridade inicial: sugerir classificação de páginas descobertas e associações opcionais com projetos/marcas já elegíveis no cliente. Implantar primeiro como sugestão revisável, com comparação à escolha humana. Growth permanece “Em breve”; sugestões de template não habilitam o executor.

### Integração existente e lacunas

- `aicentralv2/services/typesafe_service.py`: wrapper HTTP server-side para System One, resolução de credencial existente, estado/perguntas JSON, modelo configurável, timeout e retries limitados para 429/529. Reutilizar o serviço em vez de criar cliente no browser.
- `aicentralv2/cadu_connect/reports_typesafe.py`: sugestões de próxima ação e revisão de evidência de métricas; `validate_choice` verifica opção, distribuição e concentração. Isso é assistência de relatórios, não motor de fluxo/associações já pronto.
- `record_run` registra telemetria por report_id/source_id e pode não registrar quando tabela estiver ausente. Para fluxos/associações, criar auditoria de sugestão com scope explícito e recurso próprio; não inventar report_id só para reaproveitar a tabela.
- O wrapper não garante sozinho shape semântico de Noul e Score. Implementar validadores próprios conforme contrato vigente se esses tipos forem usados.
- Redação de e-mails/telefones no helper atual é parcial. Projetar minimização de dados estruturada e limites por campo antes de enviar conteúdo ao serviço.
- Alias de modelo pode mudar. Registrar modelo efetivamente retornado, versão de pergunta e dados de avaliação; fixar versão suportada quando for necessário reproduzir uma decisão.

### Matriz de responsabilidade

| Recurso | Código / banco | Julgamento TypeSafe opcional |
| --- | --- | --- |
| client_id e acesso | Resolve cliente, permissions e catálogo elegível | Nenhum |
| Associação marca/projeto | Valida IDs, disponibilidade, revisão e gravação explícita | Sugere candidatos pelo conteúdo do item |
| Descoberta | Coleta URL/DOM autorizado, extrai título/formulário/links | Sugere papel semântico da página |
| Construção do fluxo | Cria IDs, conexões, portas, valida e persiste | Sugere próxima etapa entre blocos disponíveis |
| Contagem/conversão | Deduplica eventos e aplica regra publicada | Não determina se uma conversão realmente ocorreu |
| Remarketing A/B | Tempo ativo ≥ X, conversão-meta, janela e transições | Pode sugerir nomenclatura/descrever objetivo; não decide membros |
| Publicação | Diff, validação, revisão e ativação transacional | Aviso semântico consultivo, nunca autorização |
| Recálculo | Replay versionado sem reenviar ações | Nenhum cálculo por modelo |
| Webhook | Outbox, autorização, idempotência e retries | Não escolhe destino arbitrário nem dispara entrega |
| Templates/Growth | Catálogo permitido, disponibilidade e snapshots | Ranking por objetivo e compatibilidade de conteúdo |
| Análise | Números, unidade, período e evidências | Seleciona uma recomendação limitada e sustentada pela evidência |

### Julgamentos propostos

| Julgamento | Primitiva | Opções / critério | Resultado de produto |
| --- | --- | --- | --- |
| Papel principal da página | Choice | captura, produto, checkout, confirmação, conteúdo, outro, evidência insuficiente | Sugestão na lista de páginas antes de adicionar |
| Selecionar associação principal | Choice | IDs locais de candidatos elegíveis + nenhum + evidência insuficiente | Preview de marca/projeto, nunca gravação automática |
| Pertinência de vínculos adicionais | Noul por candidato | Se a evidência relaciona explicitamente item e candidato | Lista de sugestões não exclusivas; relações múltiplas não são forçadas a uma Choice única |
| Relevância de template | Score por candidato | Níveis descritos de incompatível até adequação clara ao objetivo | Ordenação entre templates disponíveis |
| Evidência de regra contraditória | Choice | consistente, contraditória, insuficiente | Aviso com referências, complementando validador estrutural |
| Próxima ação de investigação | Choice | Catálogo de ações disponíveis + reunir evidência | Sugestão como verificar instalação ou revisar mapeamento |

Definições: Choice seleciona uma opção; Noul retorna probabilidade de sim, sem confidence separado; Score representa posição ponderada em níveis ordenados. Para várias marcas válidas, usar perguntas independentes por candidato ou revisão humana, não exigir escolha exclusiva. Thresholds só após avaliação no domínio.

### Estado e evidência

Servidor prepara estado mínimo e nomeado: item (tipo, título, descrição, domínio), páginas/evidence_refs, candidatos autorizados (ref, nome, descrição necessária), regras do produto e capacidades disponíveis. client_id/organization_id ficam obrigatórios no envelope de aplicação e auditoria; não é necessário enviar identificadores internos ao modelo quando aliases locais bastarem.

Cada avaliação guarda base_revision, evidence_hash e candidate_set_hash. IDs das perguntas servem para correlacionar respostas; todo significado deve estar nas instruções. Conteúdo de páginas, relatórios e nomes de candidatos é dado não confiável, nunca instrução para operar o sistema.

Antes da inferência, buscar candidatos somente no cliente autorizado e acessível ao usuário. Após a inferência, revalidar acesso e existência antes de exibir detalhes/aplicar sugestão. Mesmo marca/projeto compartilhado explicitamente entre clientes não permite misturar seus recursos no state.

Recuperação de candidatos deve medir cobertura: truncar arbitrariamente candidatos pode remover a resposta correta. Expor ausência de candidato e permitir busca manual. Não deixar a IA inventar IDs, caminhos, fontes, marcas ou conexões indisponíveis.

### Composição e aplicação

1. Resolver escopo e carregar snapshot de evidência/candidatos autorizados.
2. Validar fatos e obter correspondências exatas em código; inferência apenas se há questão semântica útil.
3. Agrupar perguntas independentes do mesmo estado numa chamada com orçamento limitado. Respostas não veem umas às outras.
4. Quando a resposta exigir buscar nova evidência/candidatos, executar segunda etapa; não assumir dependência entre perguntas paralelas.
5. Validar tipos, opções, probabilidades, números finitos e resultado compatível com o catálogo.
6. Aplicar política da aplicação: mostrar sugestão, pedir revisão ou abster-se. Não confundir confidence alta com autorização.
7. Mostrar “Sugerido” separado do valor salvo, com candidato/evidência de origem e ações Aplicar/Dispensar. Explicação vem de texto de interface e evidência disponível; não atribuir ao Jev uma justificativa textual que ele não produziu.
8. Ao aplicar, conferir revisão e hashes; se o item mudou, invalidar sugestão e reavaliar quando necessário. Gravar via comando normal do draft/associações, com undo e auditoria; publicar continua ação separada.

Contrato interno proposto (não é o payload literal da API TypeSafe):

```text
SuggestionRequest:
  organization_id, client_id, resource_type, resource_id,
  base_revision, operation, evidence_refs, candidate_refs
SuggestionResult:
  suggestion_id, base_revision, evidence_hash, candidate_set_hash,
  answers, model, question_version, policy_version, usage,
  status (ready | abstained | stale | unavailable), created_at
ApplySuggestion:
  suggestion_id, expected_revision, selected_candidate_refs
```

Rotas propostas: POST `/reports/:resource_type/:resource_id/suggestions`, GET `/reports/suggestions/:id`, POST `/reports/suggestions/:id/apply|dismiss`. Todos resolvem client_id e autorização; cliente não envia livremente prompts, credenciais ou candidatos fora do catálogo. Aplicar tem idempotência e revisão, não usa a resposta do browser como autoridade.

### Incerteza, disponibilidade e custo

Confidence de Choice/Score expressa concentração da distribuição, não precisão comprovada. Noul próximo de 0,5 representa incerteza sim/não; não intensidade intermediária. Calibrar limites por operação com dados representativos: um ranking reversível e uma sugestão de associação têm custos de erro diferentes. Não adotar 0,8/0,9 como regra universal.

Não chamar IA por pointermove, autosave, heartbeat ou evento individual de visitante. Avaliar páginas/conteúdo quando mudarem ou sob ação explícita. Cache isolado por scope, hash de evidência/candidatos, versão da pergunta/modelo; revogação de acesso invalida reutilização. Alterar pesos de ranking não exige nova inferência se os julgamentos e evidências forem os mesmos.

Definir orçamento por cliente/operação, timeout total, limite de batch, fila e backoff. Falha/429/timeout deixa edição, publicação, contadores e webhook funcionando; UI oferece revisão manual. Não tratar falha de serviço como ausência de associação nem como probabilidade zero. Registrar tokens, latência, status e aceitação sem logar segredos ou conteúdo pessoal completo.

### Avaliação antes de ativar sugestões

Conjunto rotulado por especialistas com: páginas ambíguas, vários CTAs, confirmação sem evidência de evento, campanhas com nomes parecidos, múltiplas marcas válidas, nenhum candidato, evidência ausente, candidatos omitidos, português abreviado, conteúdo malicioso, resposta atrasada e permissão revogada.

Medir cobertura de candidatos, precisão por classe, taxa de abstenção, aceitação/correção humana, custo e latência p50/p95. Zero tolerância para vazamento entre clientes ou gravação não autorizada é uma exigência do código, não uma meta estatística do modelo. Separar falhas de evidência, inferência, composição e serviço. Comparar com baseline determinístico e revisão manual; só ativar funcionalidades com benefício observado.

Fase 0 inclui contratos e dataset; classificação de páginas entra após a descoberta estar estável; associação sugerida só entra depois do catálogo por client_id da seção 20. IA não é dependência do caminho crítico de persistência/publicação/analytics. Nenhuma chamada de avaliação foi executada nesta revisão; testes e calibração ficam para a implementação.

Fontes oficiais consultadas:

- [Choice](https://docs.typesafe.ai/primitives/choice)
- [Noul](https://docs.typesafe.ai/primitives/noul)
- [Score](https://docs.typesafe.ai/primitives/score)
- [Confidence](https://docs.typesafe.ai/confidence)
- [Entity alignment cookbook](https://docs.typesafe.ai/cookbooks/entity_alignment)
- [API](https://docs.typesafe.ai/api)


## 22. Execução — 29/09/2026

### Implementado no código nesta etapa

- Rascunho separado de `config` ativo; revisão otimista para gravações concorrentes.
- Publicação transacional com snapshot imutável, histórico e restauração como novo rascunho.
- Descoberta de páginas altera o rascunho; os mapeamentos de rastreamento são sincronizados na publicação.
- Validação de referências de campanha/etapa no escopo organization_id/client_id.
- Autosave, confirmação de publicação, indicação de falha e proteção de saída com alterações pendentes.
- Sugestão explícita de papel de página com TypeSafe e fallback manual. Não representa ainda o contrato completo de sugestões auditadas da seção 21.
- Orientação para celular; estado do editor preservado quando a janela fica estreita; cancelamento de gesto de ponteiro.
- Curvas compartilhadas de conexão entre editor/monitoramento, incluindo retornos; catálogo Growth desabilitado como Em breve.

### Integração pendente antes de disponibilizar

- Aplicar `migrations/add_reports_flow_versions_v1.sql` antes de iniciar a API nova. A configuração local aponta para banco remoto; nenhuma migração foi executada nesta etapa.
- Validar publicação, coleta e restauração com PostgreSQL e navegador reais. Build do Reports concluído. A rodada anterior de testes unitários registrou 23 testes e 3 subtestes aprovados; alterações posteriores de sincronização de etapas ainda precisam de nova execução.
- Persistir/auditar sugestões, vincular hash de evidência e aplicar políticas de orçamento/calibração.

### Partes do plano ainda não implementadas nesta etapa

- Catálogo e vínculos autorizados de projetos/marcas por cliente para todos os recursos.
- Versão fixa por sessão, contadores de todos os tipos de nó/aresta, recálculo versionado.
- Segmentos de remarketing por tempo ativo/conversão, reconciliação e outbox/webhook com tentativas/idempotência.
- Canvas completo com undo/redo, zoom/pan, portas e roteamento com desvio de obstáculos; testes de tablet/teclado.
- Galeria de templates, identidade visual aplicada e duas jornadas complexas integradas como exemplos.

Este registro descreve uma entrega parcial da implementação; não significa conclusão de todas as fases anteriores.
