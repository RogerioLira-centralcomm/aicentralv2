# Reports V1 · operação de mídia

## Organização

`client_id` é a unidade de isolamento e a única seleção necessária na entrada. Cada cliente pode ter contas de diversas plataformas, contas gerentes (MCC), campanhas, relatórios, testes de link e instalações do Funnel Flow. O projeto do Workspace é opcional para um relatório. As chaves de ingestão e as tags são emitidas para um único cliente.

| Área | Fonte atual | Ação principal |
| --- | --- | --- |
| Visão geral | Métricas diárias recebidas do Google Ads Script | Filtrar período, plataforma, conta e campanha |
| Contas | `cadu_reports_accounts` | Organizar MCC e anunciantes |
| Campanhas | `cadu_reports_campaigns` | Conferir e cadastrar campanhas |
| Funnel Flow | Tag em páginas do domínio autorizado e webhook do CRM | Mapear etapas, passagem entre páginas e conversões confirmadas |
| Relatórios | Biblioteca existente, agora com `project_ref` opcional | Criar relatório independente ou associado a campanha |
| Link Tester | Histórico existente do Planner | Analisar URL e sugerir campanha via TypeSafe |
| Monitoramentos | Chaves e lotes do Google Ads Script | Gerar um script por cliente e instalá-lo na conta ou MCC |

## Instalação do Google Ads Script

Crie uma chave em **Monitoramentos**, copie o script gerado e instale em **Ferramentas → Scripts** no Google Ads. Uma instalação em uma MCC percorre as contas acessíveis. O script envia métricas de ontem, em lotes com chave de repetição; o servidor cria ou atualiza contas e campanhas pelo ID externo. Agende a execução diária. A chave pode ser revogada no Reports. O script não é por campanha: a campanha é identificada em cada linha enviada. Para clientes distintos, gere chaves distintas e separe as contas acessíveis ou preencha `CADU.accountIds`.

## Instalação da tag do Funnel Flow

Crie uma instalação para o domínio das páginas. Copie a tag para o código do site ou para uma tag de HTML personalizado no GTM. A mesma instalação atende todas as páginas desse domínio. Configure o disparo conforme a escolha de medição do visitante no site. Depois, cadastre caminhos de URL em **Funnel Flow** e marque o caminho da página de obrigado como **Conversão**. Uma etapa pode ser vinculada a uma campanha; sem esse vínculo, a leitura permanece por domínio e URL. Uma regra de etapa incorreta pode ser arquivada e criada novamente; os eventos históricos permanecem registrados.

A tag carrega de forma assíncrona, não lê formulários, não cria cookies e não captura mapa de calor. Ela envia um identificador aleatório limitado à sessão da aba, caminho sem parâmetros, domínio de referência e parâmetros de atribuição selecionados. O servidor aceita eventos somente do domínio autorizado, descarta parâmetros gerais da URL e troca segmentos de caminho que parecem IDs ou emails por marcadores. Os números de visitantes são estimativas por identificador de sessão, não pessoas identificadas. Presença online significa um sinal enviado nos últimos 90 segundos. As passagens entre etapas são contadas apenas quando a mesma sessão chegou à etapa anterior antes da seguinte. A tag preserva `utm_source`, `utm_medium`, `utm_campaign`, `utm_id` e o identificador de clique durante a sessão, para que uma página de obrigado possa manter os sinais da entrada.

Uma campanha é atribuída ao evento somente quando `utm_id` identifica uma campanha única, `utm_campaign` corresponde exatamente a um nome único, ou a etapa foi vinculada explicitamente a uma campanha. Páginas compartilhadas sem esses sinais continuam sem campanha atribuída. Uma visita à página de obrigado é uma **conversão observada no site**; ela não confirma sozinha que houve uma venda.

## Conversões confirmadas pelo CRM

Em **Monitoramentos**, escolha **CRM / conversões** e crie uma chave distinta da usada no Google Ads. O CRM envia um `POST` para `/connect/api/v1/reports/ingest/conversions` com `Authorization: Bearer <chave>` e um objeto `events` de até 100 itens. Cada item aceita somente `external_event_id`, `kind` (`lead`, `qualified_lead` ou `sale`), `occurred_at` em ISO 8601 com fuso, `visitor_id` ou `campaign_id`, e opcionalmente `value_micros` com `currency`. O ID externo impede duplicação. Não envie nomes, emails, telefones nem o conteúdo de formulários.

Depois que a tag carregar, o site pode obter `window.CaduFlow.getVisitorId()` ou ouvir o evento `cadu:flow-ready`. Esse UUID pode acompanhar o lead até o CRM e voltar no webhook. Se um único vínculo de campanha for encontrado para o visitante nos 90 dias anteriores, Reports atribui a confirmação a essa campanha. Se houver ambiguidade, o evento permanece sem campanha. Um `campaign_id` informado explicitamente pelo CRM tem prioridade e é validado no mesmo `client_id`.

## TypeSafe

O Link Tester oferece uma sugestão de campanha a partir do destino e de sinais UTM. IDs externos exatos e únicos são resolvidos por regra. Nos demais casos, uma chamada TypeSafe envia apenas domínio, caminho, título e descrição limitados, dicas de campanha e candidatos do cliente atual. Duas perguntas `Choice` independentes voltam na mesma chamada: campanha provável (incluindo `none`) e papel provável da página no funil (incluindo `unknown`). A resposta e a confiança são mostradas para revisão humana; nada é associado automaticamente. A tela informa se a integração TypeSafe está configurada. A chave é lida de **Parâmetros → Integrações** no CentralX; `TYPESAFE_API_KEY` no servidor é a alternativa.

## Implantação e próxima etapa

`deploy.sh` aplica `migrations/add_reports_operations_v1.sql` após a cadeia de relatórios e o histórico do Link Tester. O bundle React é construído por `npm run build:reports`. A migração é aditiva e preserva os dados anteriores. A V1 ainda não inclui conectores nativos para outras plataformas, importação completa de métricas antigas, usuários exclusivos de Reports, automações de audiência, análise de cliques ou mapa de calor. Esses recursos dependem de contratos de ingestão e controles de privacidade próprios antes de ativação.

Para retenção, `scripts/prune_reports_events.py` mostra por padrão quantos eventos brutos superaram 180 dias e quantas confirmações do CRM superaram 400 dias. `--apply` executa a exclusão em lotes. O operador pode agendar esse comando no ambiente de produção após revisar os períodos; ele não roda na abertura de páginas nem durante o deploy.

## Plano de continuação

1. Fechar o isolamento de acesso para usuários exclusivos de Reports e revisar o escopo de `client_id` em todos os relatórios e testes legados.
2. Preparar a implantação da migração aditiva, conferir o estado do banco de destino e preservar um caminho de reversão antes de publicar a nova interface.
3. Completar o ciclo do Link Tester: confirmação da sugestão e persistência da associação com conta, campanha e relatório.
4. Preparar a coleta pública para tráfego real: limite de volume, rejeição de eventos suspeitos, observabilidade, retenção e política de consentimento por instalação. O domínio autorizado ajuda a validar o navegador, mas uma chave pública pode ser copiada e cabeçalhos de origem podem ser forjados por clientes fora do navegador.
5. Validar Google Ads Script em uma conta piloto e depois em uma MCC, incluindo execução diária, lotes grandes, falhas parciais e identificação correta de contas de clientes distintos.
6. Completar os conectores de outras plataformas e a modelagem administrativa de marcas, projetos e conjuntos de dados isolados, mantendo a seleção inicial apenas por cliente.
