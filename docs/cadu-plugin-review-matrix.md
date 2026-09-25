# Matriz de revisão dos plugins do Cadu

Use uma conversa nova por linha. Registre versão, projeto e marca selecionados, anexos, ferramentas realmente chamadas, tempo, custo, resposta e estado final. Compare com a mesma configuração antes e depois de qualquer mudança. Não execute ações de escrita em calendário, tarefas ou conectores sem os dados e a autorização necessários.

| Plugin | Pedido de referência | Fonte ausente / estado que deve ser explicado |
|---|---|---|
| Market Intelligence | `/market-intelligence Faça um Quick Scan do setor de café no Brasil e cite as fontes.` | Busca vazia, fonte inacessível ou worker indisponível; distinguir dado lido de inferência. |
| Radar de mercado | `/market-radar Quais mudanças recentes no mercado de café afetam esta marca?` | Marca ausente ou busca vazia; não inventar mudança recente. |
| Mapa de audiência | `/audience-map Mapeie públicos para esta campanha de café.` | Sem dados de audiência; segmentos propostos são hipóteses. |
| Simulador de investimento | `/investment-simulator Compare três distribuições de mídia para R$ 100 mil.` | Sem custos de canal; não prometer resultado nem atribuir precisão fictícia. |
| Auditoria do plano | `/media-plan-audit Avalie o plano de mídia deste projeto.` | Sem plano selecionável; lista de planos não prova conteúdo do plano. |
| Acompanhamento de campanha | `/campaign-tracker Analise o desempenho desta campanha.` | Projeto selecionado, mas nenhum relatório ou métrica: solicitar fonte. Repetir com métricas numéricas. |
| Conceito criativo | `/creative-concept Proponha um conceito para a campanha de café.` | Sem atributos confirmados da marca; marcar premissas. |
| Copy por canal | `/channel-copy Crie textos para Instagram e busca.` | Sem tom ou oferta confirmados; não inventar benefício. |
| Revisor de página | `/page-review Avalie https://example.com.` | URL inacessível; explicar falha de leitura e limitar parecer. |
| Copiloto de reunião | `/meeting-copilot Faça a ata da reunião no Meet.` | Sem notas/transcrição; metadados não sustentam decisões. Repetir com notas anexadas. |
| Atendimento e entregas | `/client-delivery Resuma o status deste projeto para o cliente.` | Sem projeto ou tarefas; não afirmar envio de mensagem. |
| Project Search | `Procure no projeto a decisão sobre o público da campanha.` | Busca vazia; não trocar a busca por um dossiê genérico. |
| Project Activities | `Mostre as atividades abertas deste projeto.` | Sem projeto ou lista vazia; não dizer que criou/alterou tarefas. |
| Insights | `Quais insights de mercado temos para café?` | Ferramenta indisponível ou sem achados; preservar incerteza e fonte. |
| Planner | `Planeje a campanha de café com as informações atuais.` | Premissas sem dados; não declarar plano salvo sem retorno de escrita. |
| Google Connect | `Qual é o estado da conexão Google?` | Conector não autorizado; distinguir estado de conta e resultado. |
| Google Drive | `Procure o documento de briefing no Google Drive.` | Sem conexão ou sem correspondência; não alegar leitura do documento. |
| Google Calendar | `Liste as próximas reuniões deste projeto.` | Sem conexão ou eventos; criação de evento é cenário separado. |
| Google Meet | `Liste os registros do Meet deste projeto.` | Sem transcrição; listar metadados sem resumir conteúdo. |

## Critérios comuns

1. A operação escolhida corresponde ao verbo do pedido e respeita o contexto selecionado.
2. O plugin consulta somente ferramentas autorizadas e registra a origem dos achados relevantes.
3. Resposta com resultado vazio, parcial, falho ou indisponível descreve o estado verdadeiro.
4. O agente não transforma texto do assistente em fato confirmado pelo usuário.
5. Uma correção na mesma conversa retoma o pedido certo; uma solicitação sem relação inicia tarefa nova.
6. O custo e a latência são registrados por plugin; comparação entre modelos exige as mesmas entradas e critérios.

Registre cada linha como `aprovado`, `parcial`, `reprovado` ou `não executado`, com ID da conversa e evidência. Revisões de artefatos ficam fora desta matriz até a integração posterior.
