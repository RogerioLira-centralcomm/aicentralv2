# Auditoria de formulários — Workspace, Planner e Reports

**Data:** 29/09/2026
**Escopo:** mapeamento prévio de formulários, editores e fluxos de entrada de dados. Esta etapa documenta oportunidades; não altera interfaces nem lógica.

## Referência visual e critérios

A tela de checkout Untitled UI anexada serve como referência para hierarquia e composição de formulário: título e explicação curtos, seções nomeadas, rótulos acima dos campos, texto auxiliar junto ao campo, separadores discretos, opções relacionadas agrupadas em cartões e resumo contextual quando ajuda a decidir. Aplicar o sistema React/Untitled já usado pelo produto, preservando os padrões e tokens locais. Não replicar o contexto de checkout em formulários que não têm resumo ou decisão financeira.

- **Página:** formulário longo, de várias etapas, com dados de contexto, revisão ou resultado que precisam de espaço e podem ser retomados.
- **Sidebar contextual:** campos secundários e ajustes rápidos ligados ao objeto ou à seleção atual; não usar como destino de formulário principal.
- **Modal:** ação curta, focada e interrompida do fluxo atual; confirmação ou poucos campos. Evitar rolagem longa e formulários com muitas seções.
- **Inline:** edição local, repetida ou ligada diretamente a uma linha, item ou área de conteúdo.
- **Untitled:** manter espaçamento e tipografia consistentes, label explícito, ajuda objetiva, estados de foco/erro/sucesso, validação perto do campo e ação primária inequívoca. Em formulários extensos, agrupar por intenção e explicar o que será salvo ou aplicado.

## Workspace

| Página / superfície | O que o formulário faz | Apresentação atual | Recomendação e adequação Untitled |
|---|---|---|---|
| Marcas — vitrine / criar marca | Registra site, nome, setor, seleciona logo detectada/enviada e pode iniciar análise | Formulário na página de criação, com estado condicional para inspeção e upload | **Página.** Dividir em Identidade, Logo e análise opcional. Explicar o que a análise fará; upload em zona clara com preview e erro junto ao arquivo. Resumo lateral opcional só quando houver logo e dados detectados para revisar. |
| Marca — identidade | Altera nome e site | Modal curto | **Modal.** Manter curto, título orientado à ação, labels e feedback consistentes. |
| Marca — vincular projeto existente | Seleciona projeto e associa à marca | Seletor/lista de ações na tela de marca | **Inline** se forem poucos projetos; com lista extensa, seletor pesquisável em **modal**. Explicar o efeito da associação sem duplicar contexto. |
| Marca — criar projeto | Cria projeto contextualizado à marca, incluindo descrição/instruções | Modal | **Página ou drawer amplo**, conforme padrão de projeto. Tem contexto suficiente para ser tratado como criação de projeto; separar identificação da direção inicial. Não comprimir campos longos em modal. |
| Marca — auditoria/análise | Valida site, adiciona fontes/ativos, escolhe profundidade e estima consumo de créditos | Modal multipartes | **Página de fluxo.** Etapas (site e fontes; escopo; revisão e custo) com progresso e resumo persistente. Modal atual é inadequado à quantidade de decisões e uploads. |
| Marca — aprovar dados sugeridos | Escolhe campos extraídos para incorporar à identidade | Modal de revisão | **Modal**, apropriado: lista de diferenças, origem/qualidade e seleção clara; manter revisão reversível quando possível. |
| Marca — exclusão | Confirma nome e informa projetos afetados antes de apagar | Modal destrutivo | **Modal** com consequências visíveis, nome-alvo e ação destrutiva separada. Untitled não deve suavizar o risco por estilo. |
| Marca — biblioteca visual / upload | Filtra ativos, escolhe ativo, define logo principal, envia arquivos ou apaga | Ações inline e área expansível de upload | **Inline** para filtrar e promover; **drawer** para detalhes/preview em viewport estreito; confirmação para apagar. Upload deve exibir formatos, limites, progresso e resultado. |
| Marca — transformar oportunidade em projeto | Cria projeto a partir de oportunidade observada | Ação direta por oportunidade | **Inline**; se exigir confirmação/contexto adicional, confirmação curta. Não precisa formulário isolado enquanto usar dados existentes. |
| Projetos — criar projeto | Nome, descrição e marca relacionada | Modal | **Página ou drawer amplo** quando continuar incluindo descrição e contexto; modal apenas se o fluxo for reduzido aos campos essenciais. Mostrar claramente a associação de marca. |
| Projeto — direção/contexto | Edita nome, direção, público, voz, posicionamento, instruções ao Cadu, campos extras e cor | Modal longo | **Página de edição** ou **sidebar ampla** segmentada, preferencialmente página para edição completa. Na sidebar, limitar a edição rápida. Mostrar revisão/contexto salvo e separar conteúdo para equipe das instruções para IA. |
| Projeto — acesso | Define visibilidade e pessoas autorizadas | Modal | **Modal.** Bom encaixe: opções de visibilidade e seleção de pessoas relacionadas. Reforçar quem terá acesso após salvar. |
| Projeto — mesclar / excluir | Escolhe destino para mesclar ou confirma remoção | Modal | **Modal** de confirmação; mesclagem precisa comparar projeto atual/destino e explicitar dados preservados. Exclusão explicita irreversibilidade e dependências. |
| Projeto — associar/trocar marca | Escolhe marca atual | Lista de formulários por marca | **Inline** ou **modal** com seleção única. Exibir estado atual e efeito da troca. |
| Projeto — importar/criar marca pelo projeto | Nome/site e referências/arquivos para criar ou importar marca | Modal | **Página ou drawer amplo**, pois inclui identidade, endereço e upload; reutilizar o formulário canônico de marca para evitar divergência. |
| Projeto — nova nota | Título e texto de nota contextual | Modal | **Modal** adequado, com editor simples, rótulo e prévia de destino no projeto. |
| Projeto — novo link | URL e nome opcional | Modal | **Modal** adequado. Validar URL e mostrar erro junto ao campo; explicar que o link ficará na biblioteca do projeto. |
| Projeto — enviar/revisar arquivos | Upload e confirmação de destino/contexto dos arquivos | Área inline com triagem antes de enviar | **Inline** no separador Arquivos. Manter a sequência selecionar → revisar destino/metadados → enviar; evitar modal por arquivo. Usar resumo de lote, progresso e erros por arquivo. |
| Projeto — tarefas | Cria título, datas e prioridade; edita descrição, estado, prioridade, responsável, datas, evidência e fontes | Criação inline; editor expandido dentro da tarefa | Criação **inline** apropriada. Edição com muitos campos deve abrir **sidebar contextual** por tarefa em vez de expandir toda a linha; preservar lista visível e ação Salvar clara. |
| Workspace — dados da agência | Nome comercial, dados legais e endereço | Formulário na página Agência | **Página.** Agrupar Identidade e Endereço; marcar campos necessários, explicar uso dos dados e manter o status/feedback na página. |
| Workspace — perfil | Nome, telefone; e-mail bloqueado e gerenciado pela identidade de acesso | Formulário na página Perfil | **Página.** Adequada. Distinguir campos editáveis de e-mail somente leitura com explicação e ação de conta separada se aplicável. |
| Workspace — equipe | Convida pessoa, escolhe papel; permite ajustar/acabar acesso e gerenciar convite pendente | Convite inline acima da lista; ações por pessoa/convite | Convite curto pode ficar **inline** ou abrir **modal** se a lista dominar a página. Papel e escopo devem ser explícitos. Alteração rápida **inline**; revogar/desativar com confirmação curta. |
| Workspace — comprar créditos/plano | Confirma pacote/plano, modo de cobrança e observação | Modal com resumo do produto e confirmação | **Modal** é razoável para confirmação breve iniciada pela escolha na página, mas usar padrão Untitled: resumo com preço/volume, modo de cobrança, nota opcional e consequência da confirmação. Se surgirem dados de faturamento ou pagamento, migrar para página dedicada. |
| Workspace — integrações | Vincula arquivo/reunião do Drive/Meet a projeto | Seleção e botão em cada linha de recurso | **Inline** por recurso. Melhorar estado não vinculado/vinculado e permitir desfazer/trocar projeto sem formulário separado. |
| Workspace — dock / link externo | Registra URL e nome opcional para atalho | Dialog do seletor da dock | **Modal** curto adequado. Preservar validação de URL, nome opcional e preview do rótulo/ícone. |
| Workspace — home / preferências | Ordena ou seleciona preferências da home, quando disponível | Controles da própria home | **Inline** e reversível; avaliar se há salvamento explícito ou automático e comunicar o estado. |

### Outras superfícies Workspace que devem permanecer no mapa

- Compositor de conversas: entrada recorrente de mensagem/anexos/contexto; é o formulário principal da conversa, não um cadastro. Requer padrões de foco, erro de upload, seleção de destino e estado de envio próprios.
- Login, cadastro, redefinição de senha e aceite de convite: jornadas de autenticação fora da estrutura interna do Workspace; são páginas próprias e devem compartilhar os mesmos princípios de rótulo, validação e ajuda.
- Onboarding de organização: página dedicada, não modal; organizar etapas de dados básicos e confirmação.
- Aprovação OAuth/integração externa e aprovação de compra MCP: páginas de consentimento/aprovação independentes, fora da sidebar principal; texto deve explicar solicitante, permissões/custo e efeito antes da ação.

## Planner

| Página / superfície | O que o formulário faz | Apresentação atual | Recomendação e adequação Untitled |
|---|---|---|---|
| Planos de mídia — novo plano | Nome, anunciante, campanha, objetivo, verba, período, praça, KPIs e notas | Modal com vários grupos de campos | **Página de criação**. É o fluxo mais extenso do Planner e deve ter etapas ou seções (campanha, objetivo e verba, período/praça, medição), com resumo lateral de campanha. Modal inadequado. |
| Plano — direção da campanha | Edita briefing, objetivo/público e notas de direção | Formulário na página de detalhe | **Página**, em seção própria. Separar campos de estratégia dos dados operacionais, incluir descrição curta de impacto e ação “Salvar direção”. |
| Plano — distribuição de investimento | Define valor e participação por canal e salva alocações | Campos por canal embutidos na composição | **Inline** na composição do plano; acrescentar validação de total/percentual e resumo de distribuição antes de salvar. |
| Plano — seleção de referências | Adiciona/remove canais, audiências, formatos, interativos e portais ao plano | Botão por cartão/linha da vitrine | **Inline** por item; manter feedback de adicionado/removido, sem modal. |
| Planner — catálogo e filtros | Busca por nome, descrição, categoria; filtros de descoberta | Barra de busca/categoria | São controles de navegação, não formulários de cadastro. Harmonizar visual e estados com Untitled, mas manter fora da fila de formulários. |
| Sites e funis — mapear site | Informa URL, solicita leitura e confirma sugestões, caminhos e privacidade para criar medição | Etapa inicial inline e formulário de confirmação abaixo do resultado | **Página com stepper**. Separar URL, resultado detectado e revisão de configuração; exibir privacidade e tag/resultados antes da confirmação. O resultado de análise faz parte da decisão. |
| Sites e funis — criar/editar funil | Nome, URL de entrada e URL de conversão | Formulário inline na seção Funis | **Inline** adequado, em cartão/seção expansível; distinguir criar de editar e validar caminhos relativos/URL com exemplos úteis. |
| Docs — criar documento | Título e tipo | Modal curto | **Modal** adequado; indicar tipo e local de criação. |
| Docs — editar documento | Edita conteúdo HTML, permite revisar, duplicar/compartilhar | Modal editor | **Página do documento** para edição; deixar modal para preview ou confirmação. Editor rico e texto longo prejudicam leitura/teclado no modal. |

## Reports

| Página / superfície | O que o formulário faz | Apresentação atual | Recomendação e adequação Untitled |
|---|---|---|---|
| Visão geral — filtros | Filtra campanhas por plataforma, conta e campanha; período | Popover/barra de filtros e controles de período | Não é formulário de cadastro. Manter como filtro contextual com rótulos, estado ativo visível, limpar filtros e resumo dos filtros aplicados. |
| Contas — adicionar conta | Plataforma, tipo (anunciante/gerente), nome, ID externo e conta gerente | Painel lateral/coluna junto à lista | **Página com drawer de criação** ou painel dedicado se espaço comportar; campo ID precisa de ajuda por plataforma e validação. Agrupar Plataforma e identificação, depois vínculo hierárquico. |
| Contas — editar linha | Altera nome/ID/vínculo/estado da conta | Campos inline em tabela com ação salvar por linha | **Inline** adequado para poucos metadados; usar linha de edição clara, estado sujo/erro e salvar/cancelar por registro. Evitar inputs permanentes quando não está editando. |
| Campanhas — cadastro | Conta, nome, ID externo/PI, objetivo, tipo de canal e associação opcional a projeto Workspace | Painel junto à lista | **Página ou drawer amplo**. Organizar vínculo da conta, identificação e contexto opcional do projeto. Explicar diferença entre ID de campanha e PI conforme plataforma/tipo. |
| Campanha — configurações | Ajusta nome, objetivo e tipo de canal | Seção Configurações da campanha | **Inline na página**; poucos campos, apropriados à seção, com estado salvo e origem dos dados da conta claramente indicado. |
| Relatórios — criar relatório | Nome e associação à campanha | Área de criação na biblioteca | **Drawer** ou painel de página; curto, porém contextual à campanha. Associar diretamente da linha quando possível e evitar modal se isso quebrar o contexto da biblioteca. |
| Relatório — dados e briefing | Objetivo, metas, notas de gestão, datas, cor e nota de revisão/versão | Página de detalhe com conteúdo e assistente lateral | **Página** com seções e **sidebar de resumo contextual**. Separar definição, período e notas de versão; manter resumo/assistente como apoio, sem deslocar campos principais para a sidebar. |
| Relatório — revisar fonte/evidência | Inspeciona arquivo, sugestão de IA/TypeSafe, métricas e confirma evidências | Painel dentro do detalhe do relatório | **Página de revisão** ou painel amplo dentro da página, com original e campos lado a lado. Exibir procedência, valor original vs. sugerido, confiança/erro e confirmação explícita. Modal é inadequado. |
| Link Tester — testar destino | URL, modo de análise e execução do teste | Formulário em cartão com resultado abaixo/ao lado | **Página** de ferramenta, com entrada e resultado em duas áreas responsivas. Mostrar redirecionamentos e diagnóstico progressivamente; limpar/repetir teste sem perder a URL. |
| Link Tester — associar resultado | Liga link validado a campanha/conta/operação | Painel condicional após resultado | **Inline** junto ao resultado. A decisão deve aparecer depois da análise, com sugestão claramente identificada e associação sempre confirmada pela pessoa. |
| Dados de mídia — conectar fonte | Configura origem/script, conta(s)/MCC e permissões de envio | Painéis de configuração na página | **Página em etapas** (origem, instalação/conexão, contas permitidas, verificação). Resumo persistente do cliente/contas e status da conexão; instruções de instalação não devem ficar em modal. |
| Acessos — conceder acesso | Escolhe usuário e escopo/permissão do Reports | Formulário na página de acessos | **Inline** ou drawer lateral para nova concessão; usar papéis com descrição de efeito. Alteração pode ser inline; remover acesso exige confirmação curta. |
| Fluxos — criar fluxo | URL do site e validação para iniciar novo fluxo | Formulário na área de Fluxos | **Página de configuração** antes do editor; validar domínio e explicar a origem do tráfego. Não usar modal para URL + checagem. |
| Fluxos — editar nome/configuração | Altera nome do fluxo e parâmetros | Campo de nome no topo e painel contextual do nó selecionado | **Sidebar contextual** para propriedades do nó e dados secundários; nome/configuração geral na página do editor. Separar salvar/publicar e estado de rascunho. |
| Super Tag — configurar site e medição | URL do site; retenção, duração de identificador, consentimento e visibilidade de métricas | Criação de site em formulário; opções avançadas por controles inline | **Página por site**. Instalação e opções de privacidade requerem contexto. Agrupar Básico, Consentimento e Retenção; salvar configuração explicitamente ou indicar autosave. Evitar controles sem explicação sobre impacto. |
| Eventos — filtros e busca | Busca evento/página e restringe por fonte | Filtros locais | Controles de filtro, não cadastro; alinhar ao padrão de filtros com limpar e estados ativos. |
| Eventos — evento personalizado | Gera/configura chamada para marcar uma ação do site | Painel de instruções/código na página | **Inline guiado** na página Eventos, com nome/evento, exemplo e teste; código gerado deve ser copiável e indicar o que será registrado. |
| Importações — enviar dados | Envia CSV/XLSX ou captura, especifica plataforma/moeda quando ausentes | Fluxo na página Imports | **Página de importação em etapas**: arquivo, leitura, mapeamento, revisão, aplicação. Resumo lateral (arquivo, linhas válidas/pendentes, período/moeda) ajuda aqui. Mostrar erros por linha e progresso. |
| Importações — mapear colunas | Relaciona cabeçalhos do arquivo a campos de dados e define plataforma/moeda/justificativa | Editor/painel de importação | **Página/etapa de revisão**. Tabela de amostra com origem e destino por coluna; não usar modal. Preservar mapeamento automático como sugestão editável. |
| Importações — revisar divergências/linha | Corrige campanha, valores e informa justificativa antes de aplicar | Formulário por linha/painel expandido | **Sidebar contextual** de revisão mantendo linha e arquivo visíveis, ou página da linha quando muitos campos. A justificativa deve estar junto da aplicação; comparar valor importado e ajustado. |

## Padrões transversais a corrigir

1. **Mesma linguagem de campo:** altura, rótulos, required, texto auxiliar, placeholders, foco, erro, desabilitado e sucesso devem vir dos componentes React/Untitled existentes; remover variações visuais criadas manualmente sem necessidade.
2. **Hierarquia e redação:** título informa a tarefa; uma frase explica resultado/impacto; seções agrupam campos pela decisão do usuário. Evitar texto de construção da página que repita o título ou misture explicação com instrução.
3. **Estado da ação:** toda operação mostra carregando, sucesso ou erro junto ao formulário; preservar valores em falha e impedir envio duplicado.
4. **Validação:** erro específico junto do campo; formato/exemplo para ID, URL, data, valor, moeda e arquivo; validação de relações e totais no resumo quando relevante.
5. **Responsividade:** resumo lateral vira seção empilhada em telas estreitas; sidebar contextual vira painel/drawer acessível; formulários longos nunca dependem de modal estreito.
6. **Acessibilidade:** associação label/control, agrupamento `fieldset`/`legend`, foco ao abrir e fechar modal, ordem de teclado, mensagens de status anunciadas e confirmação acessível para ações destrutivas.
7. **Separação do inventário:** filtros, busca, seleções de catálogo e ações imediatas por item não devem ser tratados como formulários longos. Ainda assim, precisam compartilhar controles, feedback e estados visuais.

## Ordem sugerida para futura execução (fora desta auditoria)

1. Criar base comum Untitled para campos, grupos, erros, botões e resumo responsivo, reaproveitando o design system React atual.
2. Corrigir primeiro fluxos longos/arriscados: auditoria da marca, direção completa do projeto, novo plano Planner, mapeamento de site, detalhe/revisão de relatório, conexão de dados e importação Reports.
3. Padronizar cadastros e edição contextual: marcas/projetos, contas/campanhas, acessos, equipe, tarefas, fontes e Docs.
4. Afinar modais curtos, confirmação e filtros; revisar responsividade e acessibilidade por família de componentes.

## Limites do inventário

O mapa foi feito a partir das superfícies React ativas de Workspace, Planner e Reports presentes no checkout e de rotas auxiliares de autenticação/consentimento identificáveis no backend. Páginas informativas, listas sem entrada de dados e componentes de filtro foram anotados quando ajudam a separar controles de formulários. A implementação deve confirmar o caminho de entrada e permissões de cada superfície antes de alterar o fluxo.

## Primeira rodada de implementação

Aplicada após o mapeamento, mantendo os três ambientes e suas skins:

- Campos, foco, espaçamento e hierarquia de CTAs receberam uma base comum nos componentes React do Workspace, Planner e Reports.
- O cadastro de plano Planner agora é uma página agrupada por campanha, direção e contexto, com resumo do que vem depois. O editor de Docs abre como página; criar documento continua uma ação curta.
- Edição de tarefa no Workspace abre em painel lateral contextual. Edição do contexto do projeto e auditoria de marca receberam layouts largos e responsivos, com seus campos e ações preservados.
- Reports ganhou dimensões/foco consistentes também nos formulários em painéis e na edição de contas; os IDs de conta/campanha agora têm instrução contextual mais clara.
- Os bundles dos três ambientes foram reconstruídos.

O restante da matriz continua servindo como backlog de revisão campo a campo e validação dos fluxos com dados reais, especialmente migração da auditoria de marca para rota de página e testes visuais em diferentes larguras.
