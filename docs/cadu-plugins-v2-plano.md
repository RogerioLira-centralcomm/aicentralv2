# Plugins do Cadu: menos entradas, fluxos mais completos

Status: implementação faseada, 2026-09-25. Esta etapa cobre conversa, pesquisa, análise e operações. Persistência e visualização de artefatos entram depois da revisão paralela. Prioridade agora: utilidade e correção do fluxo; custo por tarefa será medido depois que cada fluxo tiver critérios de qualidade estáveis.

### Progresso verificado

- O catálogo e a tela agrupam os modos atuais em cinco fluxos. Modos planejados aparecem como futuros, sem simular disponibilidade; comandos antigos seguem funcionando.
- A busca web informa `read_status` e a origem da data. Market Intelligence aceita claims extraídos somente quando a citação aparece no corpo lido; Insights tenta ler URLs citadas antes de usá-las como fonte elegível.
- O Quick Scan também passa por revisão antes da entrega. Performance só aceita métricas textuais quando um valor está associado a um indicador; mencionar “CTR” e o ano da campanha não satisfaz a pré-condição.
- Estratégia de mídia dispõe de um cálculo determinístico para três distribuições ilustrativas: cada cenário soma 100%, mantém o total monetário exato quando há orçamento e retorna somente percentuais quando não há. O modo Simulador usa o resultado como ponto de partida, sem apresentar projeções de desempenho.
- Três casos automatizados cobrem citação literal, fonte apenas descoberta e duplicata lida sem tomar a data do metadado como confirmação. A verificação estática de Python e o empacotamento isolado do componente React concluíram sem erro.
- Permanecem para execução: motor compartilhado completo de pesquisa, expansão por lacunas entre modos, revisores específicos de Estratégia/Criação/Performance/Operações, contratos de escrita e migração completa das rotas. A revisão do Quick cobre apenas Market Intelligence. Esta lista descreve trabalho aberto, não promessa de que os cinco fluxos já estão prontos.

## Diagnóstico do funcionamento atual

O catálogo mistura três conceitos: plugin de fluxo, capacidade interna do agente e conector. Onze workflows aparecem em `daily_workflows.py`; outros plugins são selecionados em `plugins.py`. Vários workflows diferem principalmente pelo prompt e por uma ou duas ferramentas. A experiência pede que o usuário escolha uma função cedo demais e não aproveita bem a passagem de pesquisa para planejamento, criação e análise.

Há uma base promissora: `web_search.py` já faz busca Firecrawl e leitura selecionada; `insights_research.py` combina busca, Perplexity, síntese e revisão; Market Intelligence tem trabalho retomável, consultas iterativas, extração com IDs de fonte e papéis de modelo configuráveis. O problema é que esses mecanismos não formam uma camada compartilhada: Radar usa uma busca; Insights tem pipeline próprio; Market Intelligence tem outro; Planner e Audience Map recebem apenas parte das evidências. O usuário pode obter respostas de qualidade muito diferente para perguntas próximas.

A skill [Firecrawl Research Index](https://www.skills.sh/firecrawl/skills/firecrawl-research-index) mostra o padrão a adaptar: classificar a pergunta, buscar candidatos, mudar o enquadramento quando os resultados forem fracos, expandir por relações e ler o corpo para verificar afirmações decisivas. Ela é especializada em papers; `search_papers`, `related_papers` e `read_paper` não devem ser presumidos como fontes de mercado. Para mercado, a expansão deve usar entidades, concorrentes, fontes primárias, notícias e páginas relacionadas, com verificação em conteúdo lido. Não há receita fixa nem necessidade de pesquisa profunda para todo pedido.

## Proposta de superfície: cinco plugins

| Plugin v2 | Resultado exclusivo para o usuário | Reúne fluxos atuais |
|---|---|---|
| **Inteligência** | Entender mercado, concorrentes, audiência e sinais; responder com evidência e implicação. Modos pergunta rápida, radar, investigação e estudo profundo. | Market Intelligence, Radar, Insights, Campaign Search, Audience Map na parte de pesquisa. |
| **Estratégia de mídia** | Converter objetivo e evidências em públicos, canais, cenários, plano e auditoria com contas e premissas coerentes. | Planner, Simulador de investimento, Auditoria de plano, Audience Map na parte de decisão. |
| **Criação e experiência** | Traduzir estratégia em conceito, copy e revisão de página, com consistência de marca e avaliação editorial. | Conceito criativo, Copy por canal, Revisor de página; Studio quando estiver funcional. |
| **Performance** | Ler resultados reais, comparar períodos/metas e recomendar mudanças priorizadas. | Acompanhamento de campanha, Reports. |
| **Operações do projeto** | Recuperar decisões, organizar tarefas, preparar reuniões e comunicar status com ações rastreáveis. | Project Search, Project Activities, Copiloto de reunião, Atendimento e entregas. |

Google Connect, Drive, Calendar e Meet passam a ser **conectores e fontes**, apresentados na área de integrações. Busca no projeto também é uma **capacidade comum**, acessível a qualquer plugin com autorização, não uma experiência concorrente no catálogo. Os comandos antigos permanecem como aliases durante a migração e encaminham para o fluxo v2 equivalente. Isso reduz a escolha visível sem remover capacidade.

## Revisão de cada plugin atual

| Atual | Hoje no código | Melhoria necessária e destino |
|---|---|---|
| Market Intelligence | Worker Quick/Deep/Custom com busca, extração e papéis de modelo; Quick lê no máximo seis fontes. | Tornar o núcleo de Inteligência. Planejar perguntas conforme intenção, expandir entidades/fontes relevantes, verificar claims decisivos no corpo, parar quando houver cobertura suficiente e explicar lacunas. Revisor independente checa citações e alternativas. |
| Radar de mercado | `web.search` com contexto da marca e prompt especializado. | Virar modo temporal da Inteligência: entidades monitoradas, janela explícita, linha do tempo, sinal novo vs. repetido, implicação para a marca; evitar notícia genérica. Monitoramento recorrente só com agenda própria autorizada. |
| Insights | Firecrawl + Perplexity + síntese + revisor, com janela de atualidade. | Compartilhar corpus e revisão da Inteligência. Produzir 1 a 3 insights úteis a partir de claims lidos, com contraevidência e próxima decisão; manter frescor como filtro adequado ao pedido, não regra universal para dados históricos. |
| Campaign Search | Planejado, não selecionável; rota ainda pode buscar marca/projeto. | Virar busca facetada da Inteligência: campanhas internas e públicas separadas, período, marca, canal, objetivo e fonte. Sem índice/corpus confiável, indicar cobertura em vez de sugerir que pesquisou tudo. |
| Audience Map | Busca web + referências do Planner + hipóteses. | Inteligência reúne evidências; Estratégia transforma em segmentos priorizados, jobs/necessidades, canais, sinais de validação e grau de confiança. Tamanho de público só com base identificada. |
| Planner | Catálogo de canais/audiências/formatos e pesquisa de insumos. | Núcleo de Estratégia: brief de entrada curto, objetivos, restrições, alternativas, distribuição, indicadores, dependências e decisão recomendada. Catálogo é inventário, não prova de preço ou desempenho. |
| Simulador de investimento | Referências do Planner e cenários em texto. | Módulo determinístico de Estratégia: cálculo fora do LLM, 100% por cenário, intervalos e sensibilidade; separar orçamento, CPM/CPC observado, suposição e resultado estimado. |
| Auditoria do plano | Lê plano ativo ou lista de planos; prompt compara campos. | Revisor independente de Estratégia: validar contas, vínculo objetivo–público–canal–KPI, restrições e risco. Emitir correções ordenadas por impacto e evidência, sem declarar edição do plano. |
| Conceito criativo | Contexto autorizado e prompt de conceito. | Modo de Criação: plataforma de mensagem com promessa, prova, tensão, tom e rotas criativas alternativas; crítico de marca e de alegações rejeita ideias sem sustentação. |
| Copy por canal | Prompt com voz da marca, CTA e canais. | Derivar da plataforma aprovada; variantes por intenção/estágio e formato, limites verificáveis por canal, revisão de clareza, claims e consistência. Regras de plataforma precisam de fonte atual ou configuração versionada. |
| Revisor de página | `web.read` de URL ou texto colado e parecer. | Modo de Experiência: inspecionar página real, estrutura e elementos observáveis; separar problema visto, hipótese de conversão e proposta. Usar captura/interação somente quando houver ferramenta autorizada. Não alegar acessibilidade testada só com Markdown. |
| Studio | Planejado e não selecionável. | Integrar a Criação quando geração/edição tiver prévia, parâmetros, proveniência e estado verificáveis. Até lá, não anunciar geração funcional. |
| Acompanhamento de campanha | Analisa anexo/métricas, sem Reports; pré-requisito agora exige fonte. | Núcleo de Performance: normalizar período, canal, objetivo e unidade; comparar apenas séries compatíveis; diagnosticar anomalias e recomendar teste com impacto/risco. Revisor numérico determinístico. |
| Reports | Inicial e não selecionável no catálogo. | Tornar fonte da Performance após leitura canônica de relatórios revisados, com status de atualização, permissão e métrica. Não confundir relatório importado com dado ao vivo da plataforma. |
| Project Search | Ferramentas de busca e recursos do projeto. | Capacidade transversal: recuperação por pergunta, tipo e data, trechos com IDs, cobertura e conflito entre versões. Operações a usa para localizar decisões; os outros plugins a usam quando o pedido precisa de contexto interno. |
| Project Activities | Lista e escreve tarefas. | Operações: separar consultar, propor e executar; preview de mudanças, idempotência, confirmação quando exigida e recibo por tarefa. Conferir dependências e responsáveis antes da escrita. |
| Copiloto de reunião | Metadados Meet; resumo depende de notas/transcrição. | Operações: pauta antes, preparação com contexto, resumo após transcrição lida, decisões com responsável/prazo/estado e tarefas propostas. Metadado de Meet não vira conteúdo da reunião. |
| Atendimento e entregas | Lista tarefas/recursos e redige status. | Operações: status por evidência, bloqueios, próximas decisões e mensagem revisável; separar redação de envio. Incluir mudanças desde o último status quando houver histórico. |
| Google Connect | Estado do conector. | Integrações: estado, escopos e erro de autorização legíveis; não ser plugin de trabalho. |
| Google Drive | Busca e vinculação de recursos. | Fonte de projeto/Operações com escopo, versão, permissão e leitura efetiva; listagem não prova conteúdo. |
| Google Calendar | Lista e cria reuniões. | Ação de Operações com disponibilidade e recibo; leitura e escrita com estados distintos. |
| Google Meet | Lista registros e artefatos do Meet. | Fonte de Operações; resumo apenas após recuperar transcrição/notas legíveis. |

## Motor compartilhado de evidência

1. **Classificar a pergunta** em consulta factual, monitoramento temporal, comparação, planejamento, auditoria ou ação. Determinar fontes obrigatórias antes de escolher modelo.
2. **Descobrir fontes** no projeto, anexos, conectores e web conforme autorização. Pesquisa pública usa apenas termos públicos; dados privados não entram em consultas externas.
3. **Expandir quando necessário**: reformular consulta, procurar concorrentes/entidades relacionadas, fontes primárias, estudos citados e contrapontos. Essa etapa tem critério de parada por cobertura da pergunta, não por número fixo de URLs.
4. **Ler e normalizar** páginas/trechos relevantes. Guardar URL/ID, título, data verificada ou desconhecida, origem, acesso, trecho, status e vínculo com projeto. Resultado de busca sem leitura não sustenta claim detalhado.
5. **Extrair claims e relações** com IDs de fonte. Deduplicar republicações; detectar conflito de data, geografia, unidade e versão. Fontes internas e externas podem se complementar, mas têm proveniência separada.
6. **Sintetizar para a decisão** pedida, em vez de retornar dossiê genérico. Cada afirmação importante aponta para evidência lida ou é marcada como hipótese.
7. **Revisar independentemente** números, citações, datas, alegações de marca e adequação ao objetivo. Código valida aritmética, IDs, estados e formato; modelo revisor examina interpretação e lacunas. Falha bloqueante volta à pesquisa ou produz resposta parcial honesta.

Fontes externas candidatas: sites oficiais de marcas e concorrentes, órgãos estatísticos, bibliotecas de anúncios quando acessíveis, relatórios públicos, publicações setoriais, notícias e papers quando a pergunta realmente os exigir. Conectores privados entram somente com escopo e permissão definidos. Cada adaptador declara o que consegue **descobrir**, **ler** e **atualizar**. Antes de adicionar bases pagas, medir cobertura e confiabilidade das fontes atuais.

## Política de modelos e revisores

| Papel | Tarefa | Regra de uso |
|---|---|---|
| Classificador/planejador | Escolher fluxo, fontes e profundidade | Modelo leve ou regra determinística; não decidir sozinho que uma fonte foi lida. |
| Gerador de consultas | Criar buscas públicas e expansões | Apenas contexto público aprovado; checagem de vazamento antes de chamar fornecedor. |
| Extrator estruturado | Converter trecho lido em claim com fonte, data e unidade | Modelo configurável; saída validada contra IDs e esquema. |
| Analista | Comparar evidências e formular implicações | Modelo com capacidade de raciocínio proporcional à complexidade. |
| Especialista | Planejamento, criação, performance ou operações | Recebe corpus filtrado e contrato da tarefa, não todo o histórico bruto. |
| Revisor independente | Criticar prova, conta, conclusão e adequação | Preferir família/modelo diferente do autor quando disponível; receber evidências e rascunho, emitir falhas estruturadas. |

GLM5 pode ser candidato a analista ou revisor se estiver aprovado na configuração e demonstrar qualidade nesse papel. O usuário/configuração do cliente controla modelos permitidos; não trocar provedor silenciosamente. Cada papel registra modelo, versão, tokens, latência e resultado para avaliação posterior.

## Revisão do plano com a skill TypeSafe

A [documentação de System One](https://docs.typesafe.ai/llms.txt) descreve `Choice` para uma opção entre alternativas, `Noul` para uma proposição sim/não e `Score` para graus ordenados. Uso essas ideias **nesta atividade de planejamento**, como uma disciplina para formular perguntas objetivas, comparar alternativas e deixar a incerteza explícita. Elas não são requisito arquitetural para o produto.

O escopo solicitado é o TypeSafe disponível **aqui para o agente que revisa o plano**. Não estou propondo usar o cliente servidor do CentralX, consumir a API interna, configurar credenciais do cliente ou adicionar chamadas TypeSafe aos plugins. O funcionamento existente do produto permanece uma questão separada.

| Decisão de planejamento | Material que eu comparo | Pergunta de revisão inspirada na skill | Resultado esperado no plano |
|---|---|---|---|
| Rota e continuidade | Mensagem atual, pedido anterior, correção, respostas do usuário, capacidades disponíveis | Qual dos cinco fluxos atende o objetivo? Há uma tarefa anterior claramente retomada? | Especificar precedência e exemplos de ambiguidade sem criar roteamento novo agora. |
| Fonte a consultar | Pergunta, escopo autorizado, opções de fonte disponíveis e status de conexão | Qual fonte é necessária, disponível e realmente legível? | Documentar pré-requisitos e fallback por fluxo. |
| Candidatos de busca | Pergunta, título, trecho, data, origem e ID de cada candidato | O candidato é pertinente à entidade e à pergunta, ou não há correspondência? | Exigir leitura e identificação da fonte antes de sustentar claim. |
| Cobertura e expansão | Subperguntas, claims existentes, fontes lidas e lacunas | Que subpergunta segue sem evidência? Qual busca adicional pode resolvê-la? | Planejar expansão apenas onde há lacuna relevante. |
| Extração de evidência | Trecho lido e candidatos exatos de data, valor, entidade e unidade | O valor consta da fonte? A unidade e o período correspondem? | Definir verificação de valores e normalização em código. |
| Citação/claim | Claim, trecho de origem e ID da fonte lida | O trecho sustenta, contradiz ou não aborda a afirmação? | Exigir verificação de claims decisivos no produto, sem pressupor TypeSafe como verificador. |
| Escalação de modelo | Resultado do extrator, campo e texto de origem | Qual erro concreto justifica uma revisão mais forte? | Definir critérios de escalonamento independentes de fornecedor. |

Na revisão, cada pergunta deve ter um conjunto claro de alternativas e a possibilidade de “nenhuma se aplica”. Eu registro a evidência usada, a incerteza e o motivo da decisão. Isso ajuda a detectar lacunas do plano sem transformar a técnica em dependência do produto.

### Aplicação por fluxo

| Fluxo | Perguntas que a revisão deve responder | Garantia proposta para o produto |
|---|---|---|
| Inteligência | A pesquisa cobre a pergunta, a entidade e os contrapontos? | Revisor factual compara claim e trecho; código verifica leitura, IDs, data e domínio. |
| Estratégia de mídia | A recomendação decorre do objetivo, público, verba e restrições? | Código calcula verba e totais; revisor estratégico avalia coerência com brief e evidência. |
| Criação e experiência | A proposta tem voz de marca, prova e diferença entre fato e hipótese? | Revisor editorial avalia clareza e originalidade; alegação sem prova é removida ou marcada como hipótese. |
| Performance | As comparações usam períodos, métricas e unidades compatíveis? | Código valida unidades, períodos, deltas e metas; revisor analisa causas alternativas. |
| Operações do projeto | A decisão/tarefa localizada corresponde ao pedido? A ação foi executada? | Código exige permissão, confirmação aplicável e recibo de escrita. |

Os exemplos oficiais de [reordenação de candidatos](https://docs.typesafe.ai/cookbooks/rerank_typesafe), [checagem de citação](https://docs.typesafe.ai/cookbooks/citation_check) e [cascata de extração](https://docs.typesafe.ai/cookbooks/sde_cascade) inspiram a decomposição da revisão. Eles não definem o modelo, o serviço nem os limiares que o CentralX usará.

### Revisões prioritárias do plano

1. **Relevância das fontes da Inteligência:** avaliar se a proposta recupera fonte primária, concorrentes corretos e contrapontos; registrar quando a cobertura é insuficiente.
2. **Citação factual:** confrontar claims do Market Intelligence/Insights com trechos efetivamente lidos e definir bloqueio para suporte ausente ou contraditório.
3. **Continuidade:** revisar exemplos de retomada real e de nova tarefa sem relação; documentar quando perguntar ao usuário.
4. **Demais fluxos:** revisar extração numérica, adequação de canal, alegações criativas e recibos de operações com casos representativos.

Para cada revisão, registrar pedido, alternativas consideradas, evidência, decisão, incerteza e efeito esperado no fluxo. Os casos em português brasileiro e com erros de digitação são essenciais. A comparação de tokens/latência entra **depois** da qualidade e do valor entregues.

## Sequência de implementação

1. **Definir contratos de fluxo e fonte:** `question_type`, `source_plan`, `evidence_status`, `claim`, `review_issue`, `decision_output`. Incluir estados `found`, `read`, `unavailable`, `conflicting` e `not_searched`. Preservar autorização por ferramenta.
2. **Extrair o motor compartilhado de pesquisa:** aproveitar Firecrawl atual, busca do projeto e conectores; implementar expansão orientada a lacunas e verificação de claims. Migrar Inteligência primeiro, sem quebrar comandos antigos. Usar a revisão estruturada acima para examinar as escolhas de desenho.
3. **Consolidar os cinco fluxos:** Estratégia usa evidências da Inteligência e cálculos determinísticos; Criação usa estratégia e revisão editorial; Performance usa métricas normalizadas; Operações usa fontes internas e recibos de ação.
4. **Habilitar revisores por risco:** factual para Inteligência, aritmético para Estratégia/Performance, claims e voz para Criação, autorização/estado para Operações. Um revisor que falha devolve problema concreto, não reescrita genérica.
5. **Migrar catálogo e interface:** mostrar cinco entradas e modos internos; aliases antigos preservados; integrações em área própria. Explicar fonte necessária, progresso e estado sem expor detalhes de implementação ao usuário final.
6. **Validar valor antes de custo:** executar casos de pergunta simples, pesquisa complexa, fonte vazia, contradição, falha de leitura, dados privados, correção e ação. Medir resposta útil, cobertura, verificabilidade e decisão tomada. Só então comparar tokens, tempo e crédito por qualidade equivalente.
7. **Integrar artefatos por último:** aplicar contrato de entrega/versão do trabalho paralelo sem redesenhar novamente os cinco fluxos.

## Critérios de aceite por fluxo

- Inteligência: responde à pergunta específica com evidência lida, datas e pelo menos um contraponto quando houver; declara cobertura e lacunas.
- Estratégia: plano e cenários consistentes, somas corretas, premissas explícitas e auditoria que encontra erros sem inventar dados.
- Criação: peças coerentes com a marca, canal e objetivo; alegações sustentadas; revisão aponta alterações acionáveis.
- Performance: métricas rastreáveis, comparações válidas e recomendações vinculadas a um sinal observado.
- Operações: decisões e status recuperáveis; nenhuma ação anunciada sem recibo; meeting summary depende de conteúdo lido.

Nenhum fluxo passa apenas porque gerou texto longo, muitas fontes ou um artefato. A evidência deve sustentar a decisão que o usuário pediu.
