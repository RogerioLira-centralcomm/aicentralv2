# Plugins do Cadu e Artefatos 2.0

Este contrato liga os cinco fluxos de plugins aos 12 tipos de artefato. O chat é a entrega padrão. Um artefato é criado quando a pessoa pede material editável, exportável, compartilhável ou persistido. A exceção existente é a pesquisa longa do Market Intelligence, que já produz artefato; essa exceção deve ser sinalizada na interface antes da execução. A escolha do plugin nunca pode apagar uma entrega explícita.

O artefato **apresenta o conteúdo**. Avaliações, sugestões, recomendações e próximos passos do plugin ficam na resposta da conversa, salvo pedido explícito para incluí-los no material. A resposta deve apontar para o artefato criado e dizer se a fonte foi lida, apenas descoberta ou indisponível.

| Tipo | Plugin que pode produzir ou atualizar | Composição principal | Condição de evidência |
| --- | --- | --- | --- |
| `brief` | Planner, Mapa de audiência, Conceito criativo | Resumo, marca, objetivo, público, mensagem, canais, entregáveis, prazo e verba; imagens úteis | Diferenciar informações confirmadas de hipóteses; não transformar lacunas em formulário. |
| `document` | Pesquisa, Criação, Performance, Operações | Títulos, prosa, listas, tabelas, citações, links e imagens conforme o conteúdo | Preservar material e fontes originais na mudança de formato. |
| `note` | Radar, Insights, Criação, Operações | Ideia ou registro curto, tópicos e links | Não inflar uma nota em dossiê. |
| `executive_summary` | Intelligence, Radar, Insights, Auditoria, Performance, Operações | Síntese e métricas primeiro; detalhe e fontes depois | Métricas com período, unidade e origem; sem generalizar dado parcial. |
| `media_plan` | Planner, Simulador, Auditoria | Canais, logos oficiais quando disponíveis, tabela de alocação, período, formatos, criativos e cronograma | Preservar totais do plano; catálogo não comprova preço ou resultado; auditoria não altera plano sem pedido. |
| `scenario` | Simulador, Planner | Cenários lado a lado, premissas, variáveis e métricas | Identificar projeções como hipóteses; conferir somas e unidades. |
| `research` | Intelligence, Radar, Insights, Busca de campanhas, Mapa de audiência, Performance | Pergunta, achados, dados, tabelas, citações e links | Somente fonte efetivamente lida sustenta achado factual; separar metadado de conteúdo. |
| `project_map` | Busca e Atividades do projeto; Drive como fonte | Grupos, recursos, relações, status e links para abrir | Derivar de inventário autorizado; listagem de recurso não comprova seu conteúdo. |
| `html` | Qualquer fluxo quando a pessoa pedir página; Criação é o encaixe mais natural | Página responsiva com identidade, seções, imagens, links e interações solicitadas | Prévia completa e segura; identidade e dados só com origem conhecida; publicação é operação separada. |
| `meeting_summary` | Copiloto de reunião; Meet como fonte | Discussão, decisões e ações com responsável e prazo quando disponíveis | Exige notas ou transcrição lidas; metadados Meet não são conteúdo da reunião. |
| `meeting_agenda` | Copiloto de reunião; Calendar como fonte | Objetivo, tópicos ordenados, tempo e decisão esperada | Útil antes da reunião; não inventar participantes ou decisões. |
| `link_reader` | Drive, Revisor de página, Busca do projeto como fontes | URL, origem, conteúdo capturado, prévia e ação de guardar referência | Diferenciar URL/metadados de página lida e do resumo do agente. |

## Encaixe dos modos de plugin

- **Intelligence:** `market-intelligence` pesquisa estruturada; `market-radar` fatos recentes; `insights` síntese; `campaign-search` casos. Produzem `research`, `executive_summary` ou `note` conforme profundidade. Descoberta sem leitura não vira citação. Pesquisa longa do Market Intelligence é uma exceção operacional de materialização automática já existente; Quick Scan deve permanecer no chat.
- **Estratégia de mídia:** `planner` apresenta plano existente em `media_plan`; `audience-map` organiza pesquisa ou briefing; `investment-simulator` compara `scenario`; `media-plan-audit` apresenta a versão lida e envia críticas no chat. A revisão não regrava o plano.
- **Criação e experiência:** `creative-concept` usa `brief` ou `document`; `channel-copy` usa `document` ou `note`; `page-review` registra conteúdo efetivamente lido e análise no chat; `studio` anexa imagens geradas com proveniência quando essa capacidade estiver disponível. `html` é uma entrega explícita, com prévia e estado de publicação próprios.
- **Performance:** `campaign-tracker` e `reports` podem apresentar `executive_summary` ou `document` a partir de arquivo/métricas fornecidos ou relatório lido. Interpretações e ações recomendadas ficam no chat. Métricas calculadas condicionalmente não são dados vivos da plataforma.
- **Operações:** `project-search` monta `project_map` de recursos existentes; `project-activities` executa tarefas com recibos, separadamente de qualquer mapa; `meeting-copilot` escolhe pauta ou resumo segundo a fonte; `client-delivery` apresenta status para compartilhar sem alegar envio.
- **Conectores:** Drive, Calendar e Meet são fontes ou executores de ações autorizadas. A conexão por si só não cria artefato. Google Connect informa estado de acesso. `link_reader` é referência de fonte, não texto inventado pelo agente.

## Contrato de apresentação para o agente de frontend

Cabeçalho compacto; área principal para o conteúdo. Tipografia legível em painel estreito e notebook. Componentes por informação: texto para explicar, tabela para comparar, número para métrica, imagem para referência ou peça. Preservar Markdown fonte em visualização/edição/exportação; manter links, fontes, logos oficiais e imagens fornecidas. Um campo ausente é omitido ou marcado “não informado”; jamais preenchido por suposição. Mostrar origem e estado da leitura próximos ao conteúdo. Distinguir rascunho, salvo, incompleto e publicado. Em reunião, agrupar ação com responsável e prazo. Em mapa, cada recurso deve abrir sua origem. Em HTML, a prévia precisa indicar geração incompleta e permitir acesso ao código-fonte.

## Limites do runtime atual

O catálogo declara os 12 tipos, mas o materializador de respostas textuais cobre nove tipos mais HTML. `project_map` é montado a partir dos recursos reais do projeto no serviço da conversa; `link_reader` é uma referência de leitura aberta no frontend e pode ser guardada como referência pessoal. Nenhum dos dois deve ser anunciado como geração textual genérica. O catálogo de plugins expõe sugestões de apresentação, sem conceder ferramentas ou criar artefatos por si. A rota de workflow preserva `artifact_type` explícito e suas ferramentas de contexto. Quick Scan sem pedido de arquivo conclui no chat; pesquisa longa e pedido explícito de arquivo geram artefato. O trabalho longo persiste `source_markdown` junto do HTML, e a indexação `.md` usa essa fonte. A exportação e edição Markdown no painel estão sob integração do agente de artefatos; até essa etapa terminar, não declarar fidelidade completa de `.md` no frontend.
