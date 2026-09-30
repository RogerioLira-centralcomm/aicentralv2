# ExecPlan — Evolução do módulo de Fluxos no CentralX

Documento vivo. Atualizar **Progress**, **Surprises & Discoveries**, **Decision Log** e **Outcomes & Retrospective** ao concluir cada milestone. Este plano substitui o plano colado inicialmente; o diagnóstico detalhado está em [RECON.md](RECON.md).

## Objetivo de produto

Um Fluxo deve permitir planejar uma jornada por etapas, entender as páginas descobertas no site, acompanhar conexões com dados reais e resolver pendências antes de publicar. O editor deve permanecer estável ao salvar, publicar e abrir painéis. O exemplo Centralcomm serve como cenário de aceite, sem assumir que seus números observados sejam constantes.

## Para quem é a ferramenta e que decisão ela ajuda a tomar

| Pessoa | Tarefa principal | Resposta que a tela deve dar |
|---|---|---|
| Analista que monta o fluxo | Escolher canais, páginas e conversões e explicar a jornada desejada. | “O que falta para este desenho fazer sentido e ser publicado?” |
| Gestor que acompanha o site | Comparar o desenho publicado com o tráfego observado. | “Por onde as pessoas passam, onde deixam de avançar e em qual período?” |
| Cliente ou revisor com acesso de leitura | Entender a jornada sem conhecer o editor. | “O que é planejado, o que foi medido e o que ainda não sabemos?” |

**Percurso principal:** selecionar site e objetivo → examinar páginas descobertas e cobertura → adicionar canais e páginas → conectar e definir conversão → revisar pendências → publicar uma versão → acompanhar eventos dessa versão. Cada passo deve mostrar o próximo passo possível e preservar site, fluxo, período e versão ao navegar entre Editar, Monitorar, Super Tag e inventário. O objetivo informa sugestões iniciais; não deve criar ou publicar nós sem revisão.

**Princípios de leitura:** distinguir desenho planejado, dado observado, simulação e sugestão. Mostrar fonte, período, fuso, versão e estado de coleta ao lado de métricas. “Sem dados”, “coleta parcial” e “zero observado” são estados diferentes. Sessões, eventos e pessoas não são contagens intercambiáveis; uma página em dois idiomas não pode somar a mesma sessão duas vezes. Uma pessoa deve poder descobrir por que um número ou uma pendência aparece sem sair do contexto do fluxo.

## Lacunas de experiência além dos 47 problemas visuais

| Lacuna | Consequência para a pessoa | Milestone |
|---|---|---|
| Primeira abertura sem orientação ou próximo passo | A tela parece completa mesmo quando o desenho não responde a uma pergunta. | M1/M2 |
| Descoberta grande ou parcial sem progresso e cobertura claros | O inventário parece definitivo e contagens diferentes geram desconfiança. | M2 |
| Etapa, tipo de página, evento e conversão misturados | Uma página de contato pode ser confundida com conversão confirmada. | M3/M5 |
| Publicação com impacto pouco explícito | A pessoa não sabe qual versão será medida ou o que muda na tag. | M1/M5 |
| Métricas sem escopo, denominador e estado de coleta | Um 0% pode ser lido como mau desempenho quando não houve dados. | M4 |
| Arrastar como único caminho de edição | Teclado, touch e usuários novos ficam dependentes de tentativa e erro. | M3/M6 |
| Rascunho perdido ou conflito de edição pouco recuperável | Trabalho manual pode ser sobrescrito ou abandonado. | M1/M7 |
| Escala de centenas de páginas e conexões | Busca, canvas e painéis podem ficar lentos ou visualmente inúteis. | M2/M4/M7 |
| Revisor precisa interpretar termos internos | A visão de leitura vira uma versão desabilitada do editor. | M6/M7 |

As lacunas acima passam a ter critérios de aceite próprios; o checklist original continua válido, mas não é a definição completa de sucesso do produto.

## Princípios da infraestrutura existente

1. **Backend:** Flask/Python com PostgreSQL e rotas em `aicentralv2/cadu_connect/`. Não criar camada PHP. Usar os helpers de escopo por organização/cliente, seleção, transação e erros já usados pelas rotas de Reports.
2. **Frontend:** React 18, `@xyflow/react` 12 e CSS/Untitled UI em `frontend/reports-v1/`. `elkjs` e worker de layout já estão instalados. Não adicionar dependências sem registrar a decisão.
3. **Persistência:** o rascunho vive em `cadu_reports_flow_registry.draft_config`; versões publicadas são imutáveis em `cadu_reports_flow_versions`; passos são materializados em `cadu_reports_flow_steps`. Nós e conexões não precisam de tabelas próprias. Preservar `type`, `title`, `x`, `y`, `from` e `to` para leitores antigos, usando `reports_flow_schema.py` como ponte.
4. **Eventos:** distinguir `cadu_reports_flow_events` (coleta ligada ao fluxo) de `cadu_reports_supertag_events` (instalação independente). Não combinar métricas dos dois sem identidade e janela explícitas. Não inventar volume onde não houver coleta.
5. **Contratos:** manter `/api/v2/reports/flow/...` e a forma antiga dos campos; novos resumos devem ser aditivos. Migrations em `migrations/`, idempotentes e testadas pelo padrão existente.
6. **Linguagem:** texto visível em PT-BR. Usar Fluxo, Etapa, Nó, Canal, Tipo de página, Conexão, Retorno e Pendência; ações “Remover do fluxo”, “Duplicar nó”, “Atualizar captura”. IDs técnicos podem permanecer em APIs e no banco.
7. **Entrega:** um milestone de cada vez, na ordem. Cada um gera commit `fluxos(Mx): <resumo>`. Antes do commit, rodar verificações proporcionais ao código alterado e registrar os comandos e resultados neste arquivo. Uma falha de aceite fica documentada; não marcar concluído como se tivesse passado.

## Progress

- [x] M0 — Reconhecimento estático e plano ajustado à infraestrutura (2026-09-30) — `RECON.md`; commit neste histórico
- [ ] M1 — Estabilidade do editor e publicação coerente
- [ ] M2 — Inventário confiável e agrupamento por idioma
- [ ] M3 — Etapas consistentes e layout do canvas
- [ ] M4 — Conexões planejadas e tráfego observado
- [ ] M5 — Pendências acionáveis com paridade servidor/cliente
- [ ] M6 — Painéis, controles e legibilidade
- [ ] M7 — Vocabulário e QA dos 47 problemas
- [ ] M8 — Proposta de novas visões, somente com aprovação explícita

## M0 — Reconhecimento e ajuste do plano

**Entregas:** `RECON.md` com os 47 itens, arquitetura, tabelas, rotas e comandos; este plano alinhado ao código. Nenhum arquivo de produção é alterado.

**Aceite:** checklist completo; divergências do plano original registradas; `git diff --check` passa. Não exige build, pois só há documentação.

## M1 — Estabilidade do editor e publicação coerente

**Problemas:** 1–5, 9.

- Mover o feedback `versionMessage` de `main.jsx` para um único toast fixo com `aria-live`; não mover o canvas quando a mensagem aparece. Corrigir singular/plural das contagens visíveis. Investigar as faixas amarelas antes de removê-las.
- Exibir status único de salvamento com estado e horário relativo; manter ação de repetição quando houver erro. Colocar o atalho da paleta dentro do respectivo botão e adaptar Mac/Windows.
- Mostrar um estado inicial orientado à tarefa quando não há nós: escolher site, adicionar um Canal, selecionar uma página de entrada e indicar onde definir conversão. Preservar o rascunho em erro de rede; não trocar a tela por estado vazio genérico. Em conflito de revisão, mostrar a revisão local e a remota e exigir escolha explícita antes de sobrescrever.
- Desabilitar Publicar quando há erro bloqueante, com indicação da quantidade e caminho para Pendências. Manter o bloqueio no servidor. Evoluir o endpoint para erro estruturado HTTP 422, documentando a mudança frente ao 409 atual e preservando identificadores de erro consumidos por clientes existentes, se houver.
- A confirmação de publicação deve mostrar nome, site, quantidade de nós/conexões, pendências restantes, revisão e efeito sobre o monitoramento. Impedir duplo envio. Após sucesso, abrir a versão publicada correspondente sem misturar dados de versões anteriores.

**Aceite:** `getBoundingClientRect().top` de header/canvas permanece igual ao mostrar toast; singular/plural corretos; requisição direta de publicação bloqueada retorna 422 com lista; publicação sem bloqueios ainda funciona. Um fluxo vazio tem próximo passo claro; erro de rede e conflito não perdem alterações; publicação informa a revisão e não duplica requisições. Testes de rota e React para bloqueio, falha e recuperação.

## M2 — Inventário confiável e agrupamento por idioma

**Problemas:** 18–22 e 26 nos dados.

- Centralizar a normalização de URL/caminho em Python, considerando host permitido, slash, query e prefixo de idioma. Preservar `canonical_url` e os IDs atuais; adicionar campos novos por migration idempotente em `cadu_reports_flow_discovered_pages` somente onde necessário.
- Coletar `hreflang` se o pipeline de descoberta já expuser HTML; caso não exponha, registrar limite e oferecer vínculo manual de traduções. Mesmo caminho normalizado permite par; caminhos traduzidos como `/contato` e `/en/contact` precisam de evidência ou vínculo explícito.
- Ajustar `build_catalog` para deduplicar antes de contar e agrupar, preservando a exigência atual de assinatura estrutural quando aplicável. Não transformar todo prefixo de URL em grupo automaticamente. Resumo de inventário deve derivar do mesmo conjunto da lista e explicar exclusões sem afirmar que páginas não verificadas são válidas.
- A ação Agrupar mostra prévia dos membros e confirmação. Títulos truncados exibem título e caminho em tooltip acessível.
- Dar ao inventário estados explícitos de “analisando”, “parcial”, “concluído”, “falhou” e “sem páginas verificadas”, com último horário e ação de continuar/tentar novamente. Busca por título, caminho e idioma; filtro “no fluxo / fora do fluxo”; manter seleção e posição ao voltar do inspector. Em sites grandes, renderizar a lista de forma paginada ou virtualizada com os recursos já presentes.

**Aceite:** invariantes de contagem no endpoint e na UI; `/cases/*` une PT/EN quando houver pareamento; grupo `/media-hacks/leituras/*` não repete; nenhuma página se perde entre grupos e avulsas. Uma análise parcial informa cobertura e pode ser retomada; busca encontra uma página pelo caminho; a lista continua utilizável com 539 páginas. Testes Python para normalização, pareamento e contagens; testes JS para a apresentação.

## M3 — Etapas consistentes e layout do canvas

**Problemas:** 6, 23–28, 35–36 parcialmente, 41.

- Fazer `stage` persistido a fonte de verdade; `x` resulta da etapa. Migrar conservadoramente somente nós de página que estejam em Origem. Preservar a sexta etapa legada `support` durante a transição: levantar fluxos existentes e decidir tratamento sem apagar nós ou alterar jornadas publicadas.
- Separar `pageType` de `stage` sem remover `role` até migrar todos os consumidores. Tratar canais (`type: source`) como Origem. Arrasto muda etapa; inspector muda etapa e reposiciona; canal/página fora da etapa permitida recebe explicação.
- Reusar `flowLayout.js`/worker ELK. Centralizar largura e X das faixas e nós; `pinned` conserva apenas ordem vertical. A primeira abertura enquadra os nós sem zoom excessivo. Grupos e nós fixos precisam de casos próprios para evitar sobreposição.
- Consolidar traduções pareadas em um nó de apresentação com opção de separar. Persistir reversivelmente e manter métricas por idioma rastreáveis; registrar log antes de qualquer fusão física. Tornar thumbnail e título legíveis.
- Oferecer alternativa ao arrasto: adicionar por clique, mover para outra Etapa pelo inspector ou teclado e criar Conexão por seleção de origem/destino. Distinguir “página em Conversão” de “evento de conversão confirmado” com texto de ajuda junto ao campo.

**Aceite:** round-trip `stage ↔ coluna` nas etapas suportadas; arrasto e inspector sincronizados; nenhum nó cruza faixa; nós existentes continuam abrindo; grupo e pin não se sobrepõem. O mesmo fluxo pode ser montado sem arrastar. Testes puros de layout/migração e captura visual em `docs/fluxos/screens/`.

## M4 — Conexões planejadas e tráfego observado

**Problemas:** 32–38.

- Primeiro tornar as conexões planejadas visíveis no modo Funil, sem limite arbitrário de 20 que esconda trajetos essenciais. Retorno é conexão cujo destino está em etapa anterior; visual distinto e toggle explícito. Handles nas laterais e seta visível.
- Reusar `/journey` e os cálculos existentes antes de criar endpoint. Se faltar agregação para a visão, acrescentar campos ao contrato atual. Para cada conexão, exibir volume e taxa somente quando a origem e o período tiverem denominador medido; `null` significa sem dados.
- Reduzir sobreposição por ordem ELK e roteamento; seleção realça conexões relevantes. Legenda explica estrutura planejada e estados sem coleta, com acesso ao estado da Super Tag.
- No modo Monitorar, fixar período, fuso, versão publicada e origem dos eventos em local visível; indicar última coleta e cobertura. Explicar denominador no detalhe da conexão e quando uma taxa é indisponível. Evitar soma dupla de sessões ao agregar idiomas e grupos. Deixar simulação marcada como fictícia em toda superfície onde aparecer.

**Aceite:** conexões estruturais aparecem no Funil; retornos têm cor/traço próprios; sem dados não se mostra 0% fictício; com dados volume e taxa conferem com a resposta da API. O detalhe informa fonte, janela e denominador; sessão que percorre PT e EN não duplica no agregado. Captura visual sem conexão atravessando nó no cenário de referência.

## M5 — Pendências acionáveis

**Problemas:** 29, 43–47, e contador ligado ao 5.

- Evoluir `flowValidation.js` e `reports_flow_validation.py` a partir das regras existentes, mantendo paridade em fixture JSON compartilhado. A regra de conversão considera a definição persistida correta, não confunde `role`, `type` e `stage`; não descarta regras atuais de URL, evento, objetivo ou alcançabilidade sem decisão registrada.
- Cada pendência tem `code`, severidade estável, `nodeId`/`edgeId` quando aplicável e ação. O painel separa bloqueantes/avisos, mostra texto completo, remove itens resolvidos e foca o nó ou a conexão. O header usa a mesma lista. QR Code usa ícone e tipo de Canal coerentes.
- Separar pendências que bloqueiam publicação das que apenas afetam leitura de dados. Para cada item, explicar consequência e ação concreta, por exemplo “Sem conversão definida: não será possível medir a conclusão desta jornada”. Revisar antes da publicação deve mostrar o que mudou desde a versão anterior e quais avisos permanecem.

**Aceite:** conversão válida não gera falso bloqueio; canal isolado gera pendência com ação; clicar centraliza e seleciona; frontend/servidor concordam nos bloqueios do fixture; publicação é impedida por chamada direta.

## M6 — Painéis, controles e legibilidade

**Problemas:** 7–8, 10–17, 30–31, 39.

- Consolidar painéis no `ReportsPanelShell` existente. Rail com funções distintas, rótulo acessível e tooltip; abrir um painel de ferramenta por vez, Escape fecha, viewport compensa painel sobre nó selecionado.
- Ajustar busca, filtros, abas, ícones de canais e toolbar do nó. Trocar “+N ocultas” por explicação e lista acionável. Evitar `title` nativo em componentes com tooltip customizado.
- Nomear controles, enquadrar layout, reposicionar minimapa e dar legenda. Ocultar atribuição React Flow somente depois de confirmar condição de licença aplicável e registrar decisão.
- Ajustar a visão de leitura para reduzir controles de edição e priorizar objetivo, versão, jornada, métricas e pendências de coleta. Respeitar foco visível, ordem de tabulação, leitor de tela, `prefers-reduced-motion` e largura estreita; não depender de cor para distinguir retorno ou severidade.

**Aceite:** em 1280×800 não há scroll horizontal nem nó selecionado coberto; rail e controles operáveis por teclado; ações do nó explicadas; tooltip único. Capturas antes/depois.

## M7 — Linguagem e QA final

**Problemas:** 2, 40, 42 e revisão de todos os 47.

- Centralizar rótulos visíveis do módulo sem reescrever IDs de API. Aplicar o glossário e revisar pluralização, aria-labels, tooltips, vazios e erros. Nenhum ID como `exploration` aparece na UI.
- Percorrer os 47 itens do `RECON.md`, marcando resolvido com teste/captura ou justificativa e risco residual. Validar fluxos antigos, rascunho, publicação, monitoramento e Centralcomm em desktop responsivo.
- Executar um roteiro de tarefa com pelo menos três perspectivas: criar fluxo do zero, corrigir uma pendência e publicar; interpretar um período sem eventos e outro com dados; revisar uma versão publicada sem permissão de edição. Medir passos, ambiguidades e falhas, corrigindo as que impedem a tarefa antes de encerrar M7. Medir tempo de abertura, busca e enquadramento com inventário de 539 páginas e fluxo denso; registrar limite observado.

**Aceite:** todos os itens têm evidência ou decisão registrada; build Reports, testes Python/JS e revisão visual passam; nenhum texto visível fora do glossário. As três tarefas podem ser concluídas sem depender de conhecimento do código; versão/período/fonte aparecem corretamente na leitura; desempenho com inventário grande é registrado e não impede a tarefa.

## M8 — Somente mediante aprovação explícita

Separação conceitual em “Mapa do site”, “Fluxo planejado” e “Jornada real”. Se aprovada, entregar **apenas proposta** em `M8-proposta.md`: wireframes, contratos aditivos, custo de dados e estimativa. Não implementar código neste milestone.

## Verificações por milestone

- Base: `git diff --check`; `npm run build:reports` para alterações no frontend; `node tests/frontend/reports-flow-studio.test.cjs` e `node tests/frontend/reports-flow-workspace.test.cjs`.
- Backend: `python -m pytest tests/test_reports_flow_studio.py tests/test_reports_flow_schema_v2.py tests/test_reports_flow_versions.py` e testes novos dos arquivos alterados. Usar o ambiente Python configurado no projeto se `python` não tiver dependências.
- Não existe script `npm run lint` ou `npm test` na raiz. Se um lint específico surgir, adicioná-lo ao registro. Evitar rodar o build geral sem necessidade, pois abrange outros produtos.
- Verificação manual dos cenários visualmente relevantes com captura em `docs/fluxos/screens/`; inspecionar console e requisições do editor. Registrar comandos, resultado e limites na conclusão de cada milestone.

## Surprises & Discoveries

- S1 (2026-09-30): a stack real é Flask/Python + PostgreSQL, não PHP (`reports_flow.py:1711`, migration do registry). A orientação PHP do texto inicial não se aplica a este checkout.
- S2 (2026-09-30): o banner nasce no estado React (`main.jsx:1047,1180`), não em flash de sessão.
- S3 (2026-09-30): `elkjs` e layout em worker já existem (`package.json:23`, `flowLayout.js:19-26`).
- S4 (2026-09-30): o backend já valida publicação, mas usa HTTP 409 e mensagem textual (`reports_flow.py:1719-1723`); o frontend mantém duas superfícies de revisão.
- S5 (2026-09-30): há uma sexta etapa `support` e tipos de nó além de página/canal (`flowStages.js:1-5`, `flowBlockRegistry.js`). Reduzir diretamente a cinco etapas quebraria fluxos existentes.

## Decision Log

| ID | Decisão | Motivo |
|---|---|---|
| D1 | Priorizar a arquitetura Python/Flask e os contratos v2 existentes. | É a infraestrutura real do Reports. |
| D2 | Evoluir `draft_config` com campos aditivos e manter projeção legada. | Coleta e versões publicadas consomem campos anteriores. |
| D3 | Reusar ELK, painel e endpoint `/journey` antes de criar infraestrutura nova. | Reduz duplicação e risco. |
| D4 | Preservar a etapa `support` até auditoria dos fluxos salvos. | O plano anterior assumia cinco etapas, mas o produto suporta seis. |
| D5 | Traduções só se unem com evidência de hreflang, caminho normalizado ou vínculo manual. | Parear apenas por semelhança de título cria falsos positivos. |
| D6 | M8 depende de aprovação e gera somente proposta. | Nova separação de visões é decisão de produto. |
| D7 | Priorizar o percurso criar → revisar → publicar → acompanhar, além da correção dos 47 itens. | O checklist visual não cobre orientação, confiança dos dados e recuperação de trabalho. |
| D8 | Manter planejado, observado, simulado e sugerido identificados em todos os modos. | Evita decisões baseadas em números ou caminhos de natureza diferente. |

## Outcomes & Retrospective

- M0: diagnóstico estático em `RECON.md`; plano ajustado à infraestrutura e aos contratos atuais. Cenário Centralcomm e problemas puramente visuais ainda precisam de verificação no navegador durante os milestones correspondentes.
