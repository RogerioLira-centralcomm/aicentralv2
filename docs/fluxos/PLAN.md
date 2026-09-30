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

## Revisão com TypeSafe AI: onde a inteligência ajuda

O Reports já possui `typesafe_service.system_one`, credencial no servidor, `reports_typesafe.suggest_flow_page_role`, sugestão auditada em `reports_flow_suggestions.py` e aceite explícito da pessoa. Reusar esse caminho. O valor mais próximo para o Fluxo é reduzir trabalho de classificação e revisão do inventário, sem tornar uma inferência em fato observado. A documentação atual de [Choice](https://docs.typesafe.ai/primitives/choice), [confiança](https://docs.typesafe.ai/confidence) e [alinhamento de entidades](https://docs.typesafe.ai/cookbooks/entity_alignment) fundamenta os formatos abaixo.

| Necessidade da pessoa | Julgamento TypeSafe possível | Decisão que permanece no código ou com a pessoa |
|---|---|---|
| Entender uma página sem tipo definido | Nova pergunta `Choice` entre os **Tipos de página** do glossário e `sem evidência`, usando título, caminho, H1 e sinais de formulário. A pergunta atual sobre função na jornada permanece separada. | Regras para casos inequívocos; pessoa confirma ou corrige o tipo. `stage` é uma escolha separada; página de contato não vira conversão medida. |
| Encontrar possíveis traduções com caminhos diferentes | Gerar pares candidatos do mesmo domínio em código; `Score` de correspondência semântica e sinais independentes de conflito entre títulos, conteúdo e finalidade. | `hreflang`, caminho normalizado e vínculo manual continuam fontes de identidade. Par sem evidência explícita só aparece para revisão; nunca é unido automaticamente. |
| Localizar uma página entre centenas | Busca textual e filtros atuais geram candidatos; julgamento de relevância pode reordenar uma lista curta quando a consulta expressa intenção, como “onde pedir orçamento”. | Resultados devem mostrar página e caminho reais. Busca exata por título/URL funciona sem IA; nenhuma URL é inventada. |
| Decidir qual pendência resolver primeiro | Escolha entre **ações já permitidas** derivadas das pendências e do objetivo declarado, com opção “reunir evidência”. | Gravidade, bloqueio de publicação, contagens, alcançabilidade e ação continuam determinísticos. IA não cria nem remove pendências e não publica. |

**Sequência de adoção:** (1) no M3, corrigir a confusão atual entre `role` de jornada e **Tipo de página**; qualquer sugestão de Tipo de página precisa de pergunta e resposta próprias, mantendo a sugestão de função existente como recurso opcional; (2) no M5, apresentar ações determinísticas claras antes de considerar ordenação semântica; (3) no M7, avaliar offline pares de tradução e busca semântica com exemplos revisados, decidindo se merecem implementação posterior. Não adicionar chamada TypeSafe ao carregamento do canvas nem transformar a revisão em novo requisito para publicar.

**Contrato para qualquer evolução de IA:** enviar ao servidor apenas os campos necessários, com limites e tratamento de dados pessoais; tratar conteúdo do site como evidência não confiável; preservar ID, revisão, versão da pergunta, hash da evidência, modelo, uso e decisão humana no registro apropriado. Perguntas independentes sobre o mesmo estado podem ser avaliadas juntas. Validar tipos, opções e distribuições de resposta; usar probabilidade e concentração para encaminhar casos incertos à revisão, sem apresentá-las como precisão ou chance de acerto. Definir limiares com amostra rotulada do próprio produto. Erro, ausência de credencial, limite ou latência não podem impedir busca, edição, validação determinística nem publicação válida. Medir custo, tempo e taxa de correção humana antes de ampliar o uso.

## Progress

- [x] M0 — Reconhecimento estático e plano ajustado à infraestrutura (2026-09-30) — `RECON.md`; commit neste histórico
- [x] M1 — Estabilidade do editor e publicação coerente (2026-09-30 18:45) — toast fixo, status, publicação 422 e recuperação — commit neste histórico
- [x] M2 — Inventário confiável e agrupamento por idioma (2026-09-30 18:51) — identidade aditiva, resumo e grupos únicos — commit neste histórico
- [x] M3 — Etapas consistentes e layout do canvas (2026-09-30) — Etapa determina X, Tipo de página separado, traduções reversíveis e edição sem arrasto — commit neste histórico
- [x] M4 — Conexões planejadas e tráfego observado (2026-09-30) — conexões completas, retorno distinto e escopo de coleta — commit neste histórico
- [x] M5 — Pendências acionáveis com paridade servidor/cliente (2026-09-30) — ações, consequências e fixture compartilhado — commit neste histórico
- [x] M6 — Painéis, controles e legibilidade (2026-09-30) — painéis exclusivos, foco e legibilidade em 1280×800 — commit neste histórico
- [x] M7 — Vocabulário e QA dos 47 problemas (2026-09-30) — matriz completa e QA local; Centralcomm real diferido para implantação por decisão do usuário — commit neste histórico
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
- Manter os seis valores de função na jornada usados pela sugestão TypeSafe existente separados de `pageType`. Para sugerir **Tipo de página**, criar pergunta independente com a taxonomia do glossário e opção “sem evidência”; não converter `entry` ou `conversion` em Tipo de página nem gravar uma Etapa com base só na sugestão. Exibir evidência e revisão humana; a edição manual funciona sem TypeSafe.
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
- Ordenar primeiro por bloqueio e consequência definidos em código. Se uma sugestão TypeSafe de próximo passo for experimentada, limitar as opções às ações reais do painel e registrá-la como sugestão, sem alterar a lista de pendências nem a decisão do servidor.

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
- Avaliar a sugestão TypeSafe existente e as hipóteses de pareamento/busca em amostra rotulada do domínio: acertos, falsos vínculos, casos sem resposta, correções humanas, custo e latência. Registrar decisão de produto antes de disponibilizar novas inferências; nenhuma chamada externa é requisito para o QA do fluxo principal.

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
- S6 (M1): o erro 409 também é usado para conflito de revisão; só o bloqueio de publicação passou a 422. A interface mantém resolução explícita do conflito e agora mostra revisões local/remota (`main.jsx`, `reports_flow.py`).
- S7 (M1): as “faixas amarelas” do relato não apareceram na captura de navegador com fluxo de teste em 1440×900. Não há origem inequívoca no CSS do editor; validar novamente no fluxo Centralcomm em M7 antes de remover um indicador possivelmente legítimo.
- S8 (M1): o build de Reports emite avisos preexistentes de sourcemap, diretiva `use client` e tamanho de bundle, mas conclui. Os testes Python emitem um aviso de depreciação de `reportlab`.
- S9 (M2): a descoberta persiste somente respostas HTML 200. Redirecionamentos e erros são descartados antes do inventário (`_fetch_site_page` em `reports_flow.py`), portanto não há evidência para contar seus motivos históricos. O resumo conta páginas registradas, duplicatas canônicas e `noindex` detectado nas novas análises; não inventa totais de URLs descartadas.
- S10 (M2): o mesmo `template_id` era renderizado sob cada papel em `FlowCatalog.jsx`, permitindo que um grupo aparecesse mais de uma vez. A lista agora agrupa globalmente por padrão e assinatura; páginas avulsas continuam por classificação. A triplicação exata de Centralcomm não foi reproduzida sem o inventário real.
- S11 (M2): o banco deste checkout não foi migrado nem contém uma amostra Centralcomm acessível nos testes. Migration e backfill foram adicionados ao `deploy.sh`; a verificação de dados reais fica para a implantação/QA de M7. Páginas antigas marcadas `noindex` só serão reconhecidas após nova descoberta.
- S12 (revisão TypeSafe): já existe serviço TypeSafe no backend, sugestão auditada de papel da página e aceite humano. A sugestão usa `entry/intermediate/form/conversion/error/none`, que descrevem posição/função na jornada e não equivalem ao novo **Tipo de página**; é preciso separar os conceitos antes de ampliar a IA.
- S13 (correção): a UI do catálogo chamava essa função de “Tipo de página” e mostrava valores técnicos em inglês. O plano também sugeria mapear funções para `pageType`, mas esse mapeamento não é confiável: uma página de entrada pode ser Home, Serviço ou Conteúdo. O texto da UI foi corrigido; a modelagem separada permanece no escopo de M3.
- S14 (M3): consulta somente de leitura ao PostgreSQL local encontrou 2 fluxos, 33 nós em rascunhos, 4 com `stage`, 1 página na etapa Origem e nenhum nó `support`; a tabela de versões não contém nós publicados neste banco. Isso confirma a migração conservadora da página em Origem, mas não prova a situação de outros ambientes.
- S15 (M3): grupos existentes podem reunir membros de Etapas distintas. A representação recolhida usa um nó de grupo e preserva IDs/métricas dos membros; a visualização expandida continua com os membros individuais. A captura de referência cobre o fluxo simples; um fluxo denso real deve ser revisto no QA do M7.
- S16 (M4): o endpoint `/journey` já conta sessões distintas para grupos, inclusive páginas em idiomas diferentes, e separa o fluxo de eventos da Super Tag independente. O banco local não contém uma amostra de eventos do cenário Centralcomm; a comparação com dados reais fica no QA de M7.
- S17 (M4): `sessions` e `rate` legados retornavam zero/null em períodos sem qualquer evento. Campos aditivos `observation` por conexão e `collection` no resultado distinguem falta de coleta, ausência de sessões na origem, conexão não medida e zero observado sem mudar os campos antigos.
- S18 (M5): `python3` do sistema é 3.9 e falha na coleta de testes por anotações `str | None` já existentes; `.venv/bin/python3` é 3.13 e executa a suíte. O teste de navegador M1 precisava acompanhar o novo nome acessível do painel de Pendências.
- S19 (M6): o editor v2 usa painéis sobrepostos ao canvas, mesmo em desktop; o CSS de grade antigo não determina a largura útil. A seleção passou a fechar o explorador e enquadrar o nó antes da inspeção. A captura de 1280×800 prova a área útil, mas o cenário denso de 200 nós e a leitura sem permissão seguem no QA M7.
- S20 (M7): o ambiente local não possui o inventário, os eventos e uma amostra TypeSafe rotulada do caso Centralcomm. O usuário escolheu registrar a validação desse cenário como pendente para a implantação. O QA usa fixtures de 539 páginas, 200 nós e leituras observada/sem eventos; não os apresenta como dados reais da Centralcomm.

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
| D9 | Responder 422 estruturado apenas para pendências bloqueantes de publicação; manter 409 para conflito de revisão. | Cada condição tem uma ação de recuperação distinta e o frontend já trata 409 para rascunhos concorrentes. |
| D10 | Renderizar avisos do editor como toast React fixo, sem helper PHP. | O layout do Reports é React e `versionMessage` é estado local. |
| D11 | Contar apenas páginas HTML verificadas no resumo atual e explicitar a cobertura. | A descoberta não armazena redirecionamentos/erros, logo não há base para exibir seus totais. |
| D12 | Manter páginas por idioma no catálogo e unir grupos pelo caminho normalizado; a fusão visual de nós fica no M3. | Preserva seleção e métricas até existir uma apresentação reversível. |
| D13 | Registrar vínculo manual no inventário da varredura atual e reaplicá-lo à próxima varredura da mesma URL. | Crawler já expõe `hreflang` novo; URLs traduzidas sem evidência precisam de escolha humana. |
| D14 | Reusar a integração TypeSafe existente apenas para julgamentos semânticos opcionais e revisáveis. | O produto já dispõe de chamada, cache, limite e auditoria; regras e observações continuam determinísticas. |
| D15 | Não usar sugestão de página como confirmação de conversão, tradução ou Etapa. | `role` atual, `pageType`, `stage` e evento observado respondem a perguntas diferentes. |
| D16 | Solicitar julgamento independente para **Tipo de página** em vez de derivá-lo de `role`. | A função na jornada não determina a classificação de conteúdo. |
| D17 | Persistir `pageType` como campo aditivo e manter `role`/`suggestedRole` para consumidores legados. | A taxonomia de conteúdo e a função na jornada respondem a perguntas diferentes. |
| D18 | Derivar X de `stage` no rascunho ao salvar, manter Y de nós fixos e preservar `support`. | Alinha o canvas sem reescrever versões publicadas nem deslocar a ordem vertical escolhida. |
| D19 | Reunir traduções em grupo reversível com confirmação e opção de separar, preservando cada nó. | Mantém métricas e URLs por idioma identificáveis, sem fusão física. |
| D20 | Renderizar todas as conexões estruturais no Funil e mostrar Retornos por opção explícita. | O corte de 20 escondia caminhos desenhados; retorno precisa de direção e traço próprios. |
| D21 | Acrescentar `observation` e `collection` à resposta `/journey`, preservando `sessions` e `rate`. | Mantém consumidores antigos e permite distinguir ausência de dados de zero medido na UI. |
| D22 | Manter os códigos e severidades de publicação; acrescentar `action`, `consequence` e ID da Conexão quando houver Retorno. | Contrato aditivo, com bloqueios idênticos no cliente e servidor; avisos da Super Tag continuam informativos. |
| D23 | Manter a atribuição React Flow visível. | Não foi confirmada condição de licença para ocultá-la; a marca discreta não cobre ações. |
| D24 | Encerrar o QA local do M7 com matriz dos 47 itens e registrar o cenário Centralcomm como verificação de implantação. | O usuário confirmou esse encaminhamento; não há dados reais no checkout para uma conclusão honesta. Nenhuma inferência TypeSafe nova será liberada sem amostra rotulada, custo e latência medidos. |

## Outcomes & Retrospective

- M0: diagnóstico estático em `RECON.md`; plano ajustado à infraestrutura e aos contratos atuais. Cenário Centralcomm e problemas puramente visuais ainda precisam de verificação no navegador durante os milestones correspondentes.
- M1: mensagens de criação/publicação não ocupam espaço no documento; salvamento mostra estado e tempo relativo; conflito preserva o rascunho e expõe revisões; publicação bloqueada usa 422 com itens; confirmação informa site, revisão, contagens e avisos; fluxo vazio orienta o próximo passo. Teste de navegador com fluxo simulado confirmou posição idêntica de header/canvas antes/depois do toast, bloqueio, guia inicial e recuperação após falha 503. O fluxo Centralcomm real e suas faixas amarelas não foram verificados neste milestone.
- M1 — comandos: `git diff --check`; `npm run build:reports` (passou com avisos descritos em S8); `node tests/frontend/reports-flow-m1-browser.test.cjs`; `node tests/frontend/reports-flow-feedback.test.cjs`; `node tests/frontend/reports-flow-studio.test.cjs`; `node tests/frontend/reports-flow-workspace.test.cjs`; `.venv/bin/python -m pytest -q tests/test_reports_flow_publish_m1.py tests/test_reports_flow_studio.py tests/test_reports_flow_schema_v2.py tests/test_reports_flow_versions.py` (23 passaram). Não há script lint no `package.json`.
- M2: normalização de idioma/caminho, coleta de `hreflang` e `noindex`, vínculo manual, migration idempotente e backfill em lotes, contagens por catálogo único, grupos globais com prévia e lista carregada em partes. O navegador com fixture de 539 páginas confirmou busca pelo caminho, grupo `/cases/*` único PT/EN e prévia. Redirecionamentos/erros não aparecem nos motivos porque o crawler não os persiste (S9). Migration não foi aplicada a banco real neste checkout (S11).
- M2 — comandos: `git diff --check`; `npm run build:reports` (passou com avisos do bundler); `node tests/frontend/reports-flow-catalog-m2.test.cjs`; `node tests/frontend/reports-flow-m2-browser.test.cjs`; `node tests/frontend/reports-flow-workspace.test.cjs`; `.venv/bin/python -m pytest -q tests/test_reports_page_paths.py tests/test_reports_flow_translation_m2.py tests/test_reports_flow_studio.py tests/test_reports_flow_auto.py tests/test_reports_flow_publish_m1.py tests/test_reports_flow_schema_v2.py tests/test_reports_flow_versions.py` (34 passaram); `.venv/bin/python -m py_compile aicentralv2/cadu_connect/reports_flow.py aicentralv2/cadu_connect/reports_flow_catalog.py aicentralv2/cadu_connect/reports_page_paths.py scripts/backfill_reports_flow_page_identity.py`. Não há script lint no `package.json`.
- Correção após revisão TypeSafe, antes do M3 completo: rótulo e explicação da sugestão no catálogo corrigidos; contrato da API preservado. `git diff --check`, `npm run build:reports`, `node tests/frontend/reports-flow-m2-browser.test.cjs`, `node tests/frontend/reports-flow-catalog-m2.test.cjs` e `.venv/bin/python -m pytest -q tests/test_reports_flow_studio.py tests/test_reports_flow_translation_m2.py tests/test_reports_flow_publish_m1.py` passaram (12 testes Python). O M3 continua aberto.
- M3: `stage` conduz X no editor e na normalização do rascunho; arrasto, teclado e inspector mudam a Etapa; Canal permanece em Origem. `pageType` é aditivo e a sugestão TypeSafe responde a duas perguntas independentes. Páginas traduzidas podem virar grupo visual reversível; IDs e URLs permanecem separados. A captura [m3-studio-1440.png](screens/m3-studio-1440.png) mostra as faixas e a jornada de referência. Consulta local de leitura sobre fluxos antigos registrada em S14. O cenário de grupo denso com posição fixa e inventário Centralcomm real continua no roteiro de M7.
- M3 — comandos: `git diff --check`; `npm run build:reports` (passou com os avisos do bundler descritos em S8); `node tests/frontend/reports-flow-studio.test.cjs`; `node tests/frontend/reports-flow-workspace.test.cjs` (mudança de Etapa pelo inspector e quatro larguras); `node tests/frontend/reports-flow-m2-browser.test.cjs` (prévia de traduções); `node tests/frontend/reports-flow-catalog-m2.test.cjs`; `.venv/bin/python -m pytest -q tests/test_reports_flow_stage_m3.py tests/test_reports_flow_studio.py tests/test_reports_flow_workspace_v2.py tests/test_reports_flow_versions.py tests/test_reports_flow_schema_v2.py tests/test_reports_typesafe_assistance.py` (42 testes e 3 subtestes passaram). Não há script lint no `package.json`.
- M4: o Funil mostra todas as conexões planejadas, sem corte por volume; Retornos aparecem sob controle explícito, com direção e traço próprios. Selecionar um nó destaca suas conexões. O servidor fornece estado de coleta, último evento, cobertura e denominador por conexão, preservando os campos antigos. A leitura usa `null` quando falta observação e mantém zero quando houve coleta e nenhuma passagem. A captura [m4-monitor-1440.png](screens/m4-monitor-1440.png) mostra escopo e detalhe de uma conexão medida; o navegador também verificou ausência de eventos sem 0% fictício. O SQL de grupos já usa `COUNT(DISTINCT session_id)` (S16). O roteiro com dados reais e fluxo denso permanece em M7.
- M4 — comandos: `git diff --check`; `npm run build:reports` (passou com avisos do bundler); `node tests/frontend/reports-flow-metrics-m4.test.cjs`; `node tests/frontend/reports-flow-studio.test.cjs`; `node tests/frontend/reports-flow-workspace.test.cjs`; `.venv/bin/python -m pytest -q tests/test_reports_flow_metrics_m4.py tests/test_reports_flow_stage_m3.py tests/test_reports_flow_studio.py tests/test_reports_flow_versions.py` (23 testes Python passaram). Não há script lint no `package.json`.
- M5: painel separa bloqueios e avisos, descreve consequência e oferece ação para cada item; a ação localiza nós e Conexões, abre a revisão do objetivo, verifica Super Tag ou adiciona Conversão. A confirmação lista avisos remanescentes; QR Code usa ícone próprio. Cinco cenários compartilhados validam bloqueios e avisos nos dois lados, inclusive Conversão válida e Canal isolado. A chamada direta de publicação com pendência permanece protegida pelo servidor.
- M5 — comandos: `git diff --check`; `npm run build:reports` (passou com avisos do bundler); `node tests/frontend/reports-flow-validation-parity.test.cjs`; `node tests/frontend/reports-flow-m1-browser.test.cjs` (painel e ação); `node tests/frontend/reports-flow-studio.test.cjs`; `node tests/frontend/reports-flow-workspace.test.cjs`; `.venv/bin/python3 -m pytest -q tests/test_reports_flow_validation_parity.py tests/test_reports_flow_publish_m1.py tests/test_reports_flow_studio.py tests/test_reports_flow_schema_v2.py tests/test_reports_flow_versions.py` (24 passaram). Não há script lint no `package.json`.
- M6: o explorador e o inspector não ficam abertos juntos; a seleção enquadra o nó sem cobri-lo em 1280×800. A contagem de Conexões fora do Funil abre a navegação completa. Ações do nó usam os termos do glossário; controles têm rótulos acessíveis, foco visível e redução de movimento. O minimapa foi deslocado para não disputar o rodapé do rail ou o inspector. A captura [m6-studio-1280.png](screens/m6-studio-1280.png) registra o estado selecionado. A atribuição permanece por D23.
- M6 — comandos: `git diff --check`; `npm run build:reports` (passou com avisos do bundler); `node tests/frontend/reports-flow-workspace.test.cjs` (1280×800 sem scroll/nó coberto, navegação e monitor); `node tests/frontend/reports-flow-studio.test.cjs`; `.venv/bin/python3 -m pytest -q tests/test_reports_flow_studio.py tests/test_reports_flow_workspace_v2.py` (13 passaram). Não há script lint no `package.json`.
- M7: a matriz [QA-M7.md](QA-M7.md) registra situação e evidência ou decisão para cada um dos 47 itens. Rótulos de Etapa, função e origem do nó estão em PT-BR; a busca de nós usa o campo compartilhado; o painel de sugestões deixou de repetir Pendências. O teste com 539 páginas passou; no arrasto de 200 nós, o Chromium local mediu mediana de 16,7 ms/quadro, p95 de 28,6 ms e média de 56 quadros/s. A leitura sem edição abriu a versão publicada, com Publicar desabilitado. Cenário Centralcomm e avaliação TypeSafe em amostra real seguem para implantação conforme D24.
- M7 — comandos: `git diff --check`; `npm run build:reports` (passou com avisos do bundler); `node tests/frontend/reports-flow-ui-labels.test.cjs`; `node tests/frontend/reports-flow-m1-browser.test.cjs`; `node tests/frontend/reports-flow-m2-browser.test.cjs`; `node tests/frontend/reports-flow-workspace.test.cjs`; `VIEWER=1 node tests/frontend/reports-flow-workspace.test.cjs`; `PERF=1 node tests/frontend/reports-flow-workspace.test.cjs`; `node tests/frontend/reports-flow-validation-parity.test.cjs`; `node tests/frontend/reports-flow-studio.test.cjs`; `.venv/bin/python3 -m pytest -q tests/test_reports_flow_studio.py tests/test_reports_flow_schema_v2.py tests/test_reports_flow_versions.py tests/test_reports_flow_publish_m1.py tests/test_reports_flow_validation_parity.py tests/test_reports_flow_stage_m3.py tests/test_reports_flow_metrics_m4.py tests/test_reports_typesafe_assistance.py` (43 testes Python e 3 subtestes passaram). Não há script lint no `package.json`.
