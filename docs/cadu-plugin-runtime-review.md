# Revisão dos plugins do chat — execução e evidências

Status em 2026-09-25. Escopo desta rodada: seleção, pré-requisitos, fontes, ferramentas e resposta na conversa. A política de artefatos será integrada depois da revisão paralela dos visualizadores.

O redesenho de produto e a análise detalhada de cada fluxo estão em [cadu-plugins-v2-plano.md](cadu-plugins-v2-plano.md). A medição de custo vem após a validação da utilidade e da fidelidade das respostas.

## Regras comuns

- O catálogo mostra disponibilidade; somente o código permite executar ferramentas. `declared_internal_tools` registra o manifesto, `runtime_tools` mostra a allowlist e `execution_path` distingue `worker`, `workflow` e `agent`. Nenhum desses campos amplia permissões.
- Projeto e marca selecionados delimitam o escopo. Uma fonte só está disponível após retorno efetivo da ferramenta ou anexo legível.
- `empty`, `partial`, `unavailable` e `failed` não são sucesso. A resposta deve explicar o limite sem inventar consulta, dados, decisões ou gravação.
- Não repetir pergunta já respondida pelo usuário; resposta do assistente não confirma um dado do projeto.
- Toda revisão de plugin verifica escolha explícita, escolha automática, pré-requisitos, ferramenta real, resposta com/sem evidência e custo. Escrita em tarefas, calendário ou conectores exige política própria.

## Workflows de uso diário

| Plugin | Estado | Fonte executada hoje | Resultado desta revisão / próximo ajuste |
|---|---|---|---|
| Market Intelligence | Ativo | Worker próprio, Firecrawl e modelos por função; `_execution_tools` vazio | Caminho próprio intencional; manifesto lista quatro ferramentas que o seletor não aciona. Quick teve execução real; Deep/Custom ainda precisam de validação ponta a ponta e controle de custo. |
| Radar de mercado | Ativo | `web.search`, com contexto de marca resolvido na orquestração | Preservar marca/concorrentes e exigir fonte específica; conferir busca vazia e resultados genéricos. |
| Mapa de audiência | Ativo | `web.search`, `planner.research_plan_inputs` e contexto autorizado | Tratar tamanhos de público como desconhecidos sem fonte; conferir separação entre evidência e hipótese. |
| Simulador de investimento | Ativo | `planner.research_plan_inputs` e contexto autorizado | Conferir somas de 100% e cenários sem verba informada; não transformar catálogo em cotação. |
| Auditoria do plano | Ativo | `planner.list_plans` ou `planner.get_media_plan` | Lista de planos não basta para auditoria; escolher plano antes de avaliar. Distinguir parecer de alteração persistida. |
| Acompanhamento de campanha | Ativo | Anexo/métricas da mensagem; nenhuma ferramenta Reports | Corrigido pré-requisito: projeto selecionado sozinho não supre relatório ou métricas. Manifesto ainda declara `reports.get_recent_project_metrics`, que não participa desta execução. |
| Conceito criativo | Ativo | Pedido e contexto autorizado | Conferir se promessa/prova decorrem da marca; dados de consumidor sem fonte são hipóteses. |
| Copy por canal | Ativo | Pedido e contexto autorizado | Conferir canal, formato e voz; limites de plataformas só quando comprovados. |
| Revisor de página | Ativo | `web.read` quando há URL; conteúdo colado nos demais casos | Não alegar leitura de URL que falhou. Revisar separadamente acessibilidade e oferta com evidência. |
| Copiloto de reunião | Ativo | Notas/anexo e, se pedido, metadados do Meet | Corrigido pré-requisito: pedido de resumo curto sem notas/transcrição pede conteúdo; metadados do Meet não sustentam decisões. Pauta continua possível sem transcrição. |
| Atendimento e entregas | Ativo | `projects.list_tasks`, `projects.list_resources` quando há projeto | Status deve diferenciar feito, andamento e proposta; nunca dizer que uma mensagem foi enviada sem ação executada. |

## Plugins de plataforma e catálogo

| Plugin | Estado | Observação |
|---|---|---|
| Campaign Search | Planejado, não selecionável | Não anunciar execução como plugin; rota direta pode continuar conforme ferramentas autorizadas. |
| Project Search | Em desenvolvimento, selecionável | Allowlist tem sete ferramentas; manifesto não lista `workspace.get_project_context`. Alinhar metadados antes de usar o manifesto como diagnóstico. |
| Project Activities | Em desenvolvimento, selecionável | Nove ferramentas permitidas, incluindo escrita de tarefas. Verificar confirmação/resultado por ação; não tratar criação de tarefa como documento. |
| Insights | Ativo | Três ferramentas no runtime; manifesto não declara as duas leituras de contexto adicionadas pela orquestração. Conferir qualidade de dados atuais e ausência de resultado. |
| Planner | Em desenvolvimento, selecionável | Pesquisa e leitura disponíveis; edição canônica do plano pelo chat ainda não está concluída. Resposta não pode alegar gravação sem retorno. |
| Reports | Inicial, não selecionável | Rotas de relatório continuam próprias; não oferecer fluxo de plugin ativo. |
| Studio | Planejado, não selecionável | Ferramentas de geração têm custo/efeito; confirmação e recibo são necessários antes de declarar criação. |
| Google Connect | Ativo | Conferir estado de conexão e distinguir autorização de execução. |
| Google Drive | Ativo | Conferir escopo de acesso e resultado de pesquisa/vinculação. |
| Google Calendar | Ativo | Leitura e criação são operações diferentes; criação de evento precisa de resultado da ferramenta. |
| Google Meet | Ativo | Listagem de artefatos é metadado; transcrição precisa ser lida antes de resumir. |

## Próximos bloqueios de qualidade

1. Rever cada resposta com casos de fonte vazia, falha da ferramenta e indisponibilidade do conector. Registrar status e fonte citada.
2. Medir custo/latência por plugin e por papel de modelo. O Market Intelligence já separa papéis; GLM5 pode ser avaliado como modelo configurável onde o perfil permite, após medir custo e qualidade, sem trocar provedores silenciosamente.
3. Executar a matriz de prompts por plugin com as mesmas condições de projeto/marca/anexos e registrar resultado no guia de testes.
4. Integrar condições de materialização somente quando o contrato de artefatos do outro trabalho estiver estável.
