# Revisão de Fluxos e TypeSafe — 29/09/2026

Escopo: alterações desta conversa em Reports, versões de fluxos, descoberta, TypeSafe e monitoramento. Alterações de outros módulos no working tree não fazem parte desta revisão. Revisão de código; nenhuma alteração funcional ou migração aplicada.

## Achados

### P1 — Respostas de descoberta/restauração podem apagar edição local

`frontend/reports-v1/main.jsx:766–780`: após salvar, o comando de descoberta fica em andamento enquanto os campos e o arraste continuam disponíveis. `adoptDraft` substitui todo o grafo e o nome quando a resposta chega. Uma edição feita nesse intervalo pode desaparecer, inclusive antes de o debounce do autosave disparar. A restauração usa o mesmo caminho. Serializar comandos com edições ou reconciliar alterações posteriores à revisão enviada; não marcar como salvo conteúdo que foi perdido. Cenário necessário: arrastar/renomear durante uma resposta lenta de seleção de página.

### P1 — Histórico de métricas usa o grafo atual

`aicentralv2/cadu_connect/reports_flow.py:805–855`: a consulta cruza eventos do período com `active_config` atual e seus caminhos/conexões. Não há revisão do fluxo fixada no evento/sessão. Alterar uma URL ou ligação e publicar muda a interpretação de eventos antigos. Os snapshots de configuração não resolvem esse problema. Persistir revisão na coleta, manter a sessão vinculada e agregar pela revisão correspondente, deixando explícita a comparação entre versões.

### P1 — Identidades de etapas distintas são colapsadas na publicação

`aicentralv2/cadu_connect/reports_flow_versions.py:53–55`: a chave de deduplicação usa host/caminho/tipo, sem node_id ou event_name. Dois eventos distintos na mesma página, ou dois nós com campanhas diferentes, resultam em uma única etapa; o segundo é ignorado. Usar identidade estável por nó e definir explicitamente o compartilhamento de mapeamentos antes de sincronizar publicação e coletor.

### P2 — Aplicação TypeSafe não valida a evidência que originou a sugestão

`reports_flow.py:1125–1137` e `main.jsx:776–785`: a sugestão só retorna base_revision; não há suggestion_id persistido, hash da evidência ou validação do resultado no comando de aplicação. O browser verifica uma revisão momentânea, mas `chooseDiscoveredPage` salva alterações e usa a revisão nova para aplicar o papel antigo. Assim a verificação de validade pode ser contornada pelo próprio fluxo normal de edição. Vincular sugestão ao cliente, fluxo, página, revisão, evidência e pergunta; validar tudo no servidor ao aplicar. Resultado tardio também precisa ser descartado ao trocar de fluxo.

### P2 — Verde nas ligações não comprova passagem entre os nós

`main.jsx:882`: a aresta fica verde quando origem e destino têm sinais, mesmo que provenientes de sessões diferentes e sem nenhuma transição observada. Nós sem caminho herdam a saúde geral. Separar saúde da coleta de trânsito observado na aresta; calcular a segunda condição por sequência na mesma sessão. A legenda atual diz sinais recentes, mas o pedido de detecção de ligação quebrada ainda não está atendido por esse critério.

### P2 — Falha antiga mantém página amarela indefinidamente

`reports_flow.py:911–916`: a última verificação HTTP é usada sem prazo de validade e sem vínculo à revisão publicada. Se o monitor for desativado ou a publicação mudar depois de uma falha, sinais novos continuam sobrepostos por esse resultado antigo. Exibir idade da verificação, expirar evidência e usar estado desconhecido/aguardando nova verificação quando necessário.

### P2 — Retornos de remarketing bloqueados no editor

`main.jsx:702`: o conector rejeita todo ciclo, apesar das curvas de retorno adicionadas e dos casos previstos de reentrada/remarketing. O desenho de uma curva não habilita o comportamento. Modelar portas, condições e regras de reentrada e validar o mesmo contrato no servidor.

### P2 — Custo e avaliação TypeSafe incompletos

`reports_flow.py:1103–1126`: cada chamada autorizada pode gerar nova inferência; não há orçamento por cliente, cache por evidência, deduplicação ou trilha persistida de consumo/aceitação. O wrapper tem timeout por tentativa e até três tentativas, mas não um prazo total para a operação. A função nova de classificação não está coberta pelos testes existentes nem por um conjunto rotulado. Implementar política de uso e avaliação antes de habilitar amplamente. Não converter confidence em prova de correção; não impor um limiar universal sem avaliação.

## Cobertura e lacunas de entrega

- Testes executados: `tests/test_reports_flow_versions.py`, `tests/test_reports_typesafe_assistance.py`, `tests/test_typesafe_service.py`.
- Resultado: 23 testes e 3 subtestes aprovados; um aviso de depreciação ReportLab.
- A sincronização de etapas está mockada no teste de publicação; esse resultado não valida seu SQL real.
- Não houve avaliação real do modelo, teste de navegador/tablet, tráfego de Super Tag/snippet ou integração PostgreSQL nesta revisão.
- Migração de versões permanece pré-requisito para a API nova; não foi aplicada nesta revisão. Sem as colunas, consultas de listagem/edição falham.
- Associações de projetos/marcas por cliente, públicos de remarketing, outbox/webhooks, recálculo por versão, templates completos e canvas avançado continuam pendentes conforme seção 22 do plano.

## Aspectos adequados

A classificação usa Choice com opções fechadas e alternativa `none`; credenciais ficam no servidor; conteúdo da página é tratado como evidência não confiável; resposta passa por validador tipado; aplicação exige ação explícita. Regras de saúde, métricas e autorização permanecem determinísticas. Gravações de rascunho usam revisão esperada e escopo organization_id/client_id. São fundamentos adequados, mas não eliminam os achados acima.

## Ordem recomendada

1. Preservação de edições e identidade estável de nós/etapas.
2. Eventos e métricas por revisão.
3. Validade de sugestões e de verificações de saúde.
4. Semântica de ligações/reentrada e avaliação integrada.
5. Completar associações, remarketing e demais entregas do plano.

## Referências TypeSafe consultadas

- https://docs.typesafe.ai/llms.txt
- https://docs.typesafe.ai/api
- https://docs.typesafe.ai/primitives/choice
- https://docs.typesafe.ai/confidence
- https://docs.typesafe.ai/cookbooks/classification_using_confidence

As páginas `.md` de API/Choice falharam na ferramenta; suas versões HTML foram consultadas. Choice/confidence fornecem julgamentos tipados; a aplicação continua responsável por autorização, validade da evidência e consequências da decisão.

## Correções implementadas após a revisão

- Descoberta/restauração usam exclusão mútua no editor, impedindo novas edições enquanto substituem o rascunho. Respostas de sugestões/descoberta são conferidas contra o fluxo aberto.
- Etapas publicadas possuem identidade `(tag_id, flow_revision, node_id)`. Publicações anteriores mantêm seus registros. Blocos que representariam o mesmo evento com atribuições ambíguas são rejeitados; eventos com nomes diferentes continuam separados.
- Super Tag e snippet por flow_code fixam a sessão em um snapshot. Eventos novos carregam `flow_revision`. O monitoramento permite selecionar uma publicação e filtra eventos e etapas pela versão. Métricas de CRM permanecem explicitamente por período, sem atribuição fictícia de versão.
- Não foi inventada uma versão para dados antigos: os eventos legados ficam NULL e não entram nos contadores de uma publicação. A rota antiga de coleta por chave de tag continua legada e sem versão; a coleta versionada usa Super Tag ou snippet por flow_code.
- Sugestões são persistidas com cliente, fluxo, página, revisão, hash da evidência, autor, resultado/consumo e estado. Aplicação verifica validade no servidor dentro da transação do rascunho. Cache de 15 minutos, limite de 50 análises por cliente/24h e uma análise pendente por cliente. Falhas consomem a reserva para evitar repetição ilimitada.
- A classificação de páginas usa uma tentativa com timeout de rede de 15 segundos. Esse timeout é o do cliente requests, não uma garantia de prazo total de parede para respostas que entreguem bytes lentamente.
- Ligações verdes exigem eventos em ordem na mesma sessão e versão, nos últimos 15 minutos. Etapas sem medição direta não recebem transições fictícias.
- Verificações HTTP expiram após 30 minutos e não são reaproveitadas para uma publicação diferente ou anterior à sua ativação. Ausência de sinais segue distinguida de falha comprovada.
- Ciclos podem ser adicionados como retorno observado. Isso habilita a medição de reentrada, não a execução automática de ações de remarketing.
- Consultas do período foram alinhadas para que os indicadores e a progressão também respeitem início/fim personalizados.

### Entrega e limites

Compilação Python dos módulos alterados e build Vite do Reports concluídos. Nenhum teste adicional ou avaliação real de IA executado nesta etapa; a rodada de 23 testes acima é anterior às correções. Validação integrada de banco, concorrência, navegador e coleta permanece pendente. A calibração da classificação com páginas rotuladas também permanece pendente; não foi inventado um limiar de confiança.

Aplicar, nesta ordem, antes de ativar os novos coletores/API:

1. `migrations/add_reports_flow_versions_v1.sql`
2. `migrations/add_reports_flow_integrity_v1.sql`

Nenhuma migração ou implantação remota foi realizada. Funções completas de remarketing, associações projeto/marca e demais fases do plano não foram incluídas nesta correção dos achados.
