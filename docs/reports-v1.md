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

Crie uma chave em **Monitoramentos**, copie o script gerado e instale em **Ferramentas → Scripts** no Google Ads. Para MCC, informe os IDs das contas pertencentes ao `client_id` antes de gerar a chave. O script recebe essa lista e falha se for instalado em MCC sem contas autorizadas; a API também rejeita qualquer conta fora da lista. Em instalação direta, uma chave sem lista fica vinculada à primeira conta que enviar dados. O script envia métricas de ontem em lotes com chave de repetição; o servidor cria ou atualiza contas e campanhas pelo ID externo. Agende a execução diária. A chave pode ser revogada no Reports. O script não é por campanha: a campanha é identificada em cada linha enviada.

## Instalação da tag do Funnel Flow

Crie uma instalação para o domínio das páginas. Copie a tag para o código do site ou para uma tag de HTML personalizado no GTM. A mesma instalação atende todas as páginas desse domínio. Configure o disparo conforme a escolha de medição do visitante no site. Em páginas SPA, dispare `window.CaduFlow && window.CaduFlow.trackPage()` no gatilho de mudança de rota do GTM, após a URL ser atualizada; a chamada ignora repetições imediatas da mesma página. Depois, cadastre caminhos de URL em **Funnel Flow** e marque o caminho da página de obrigado como **Conversão**. Uma etapa pode ser vinculada a uma campanha; sem esse vínculo, a leitura permanece por domínio e URL. Uma regra de etapa incorreta pode ser arquivada e criada novamente; os eventos históricos permanecem registrados.

A tag carrega de forma assíncrona, não lê formulários, não cria cookies e não captura mapa de calor. Ela envia um identificador aleatório limitado à sessão da aba, caminho sem parâmetros, domínio de referência e parâmetros de atribuição selecionados. O servidor aceita eventos somente do domínio autorizado, descarta parâmetros gerais da URL e troca segmentos de caminho que parecem IDs ou emails por marcadores. Os números de visitantes são estimativas por identificador de sessão, não pessoas identificadas. Presença online significa uma visita ou sinal enviado nos últimos 90 segundos. As passagens entre etapas são contadas apenas quando a mesma sessão chegou à etapa anterior antes da seguinte. A tag preserva `utm_source`, `utm_medium`, `utm_campaign`, `utm_id` e o identificador de clique durante a sessão, para que uma página de obrigado possa manter os sinais da entrada. O coletor limita cada instalação a 1.200 eventos por minuto; o histórico dessas janelas é removido pelo mesmo comando de retenção.

Uma campanha é atribuída ao evento somente quando `utm_id` identifica uma campanha única, `utm_campaign` corresponde exatamente a um nome único, ou a etapa foi vinculada explicitamente a uma campanha. Páginas compartilhadas sem esses sinais continuam sem campanha atribuída. Uma visita à página de obrigado é uma **conversão observada no site**; ela não confirma sozinha que houve uma venda.

## Conversões confirmadas pelo CRM

Em **Monitoramentos**, escolha **CRM / conversões** e crie uma chave distinta da usada no Google Ads. O CRM envia um `POST` para `/connect/api/v1/reports/ingest/conversions` com `Authorization: Bearer <chave>` e um objeto `events` de até 100 itens. Cada item aceita somente `external_event_id`, `kind` (`lead`, `qualified_lead` ou `sale`), `occurred_at` em ISO 8601 com fuso, `visitor_id` ou `campaign_id`, e opcionalmente `value_micros` com `currency`. O ID externo impede duplicação. Não envie nomes, emails, telefones nem o conteúdo de formulários.

Depois que a tag carregar, o site pode obter `window.CaduFlow.getVisitorId()` ou ouvir o evento `cadu:flow-ready`. Esse UUID pode acompanhar o lead até o CRM e voltar no webhook. Se um único vínculo de campanha for encontrado para o visitante nos 90 dias anteriores, Reports atribui a confirmação a essa campanha. Se houver ambiguidade, o evento permanece sem campanha. Um `campaign_id` informado explicitamente pelo CRM tem prioridade e é validado no mesmo `client_id`.

## TypeSafe

O Link Tester oferece uma sugestão de campanha a partir do destino e de sinais UTM da URL original e final. IDs externos exatos e únicos são resolvidos por regra. Nos demais casos, ele procura campanhas compatíveis por nome em todo o cliente. Se houver mais de 25 candidatas, não sugere uma campanha até o UTM ser refinado. Uma chamada TypeSafe envia apenas domínio, caminho, título e descrição limitados, dicas de campanha e os candidatos encontrados. A pergunta `Choice` de campanha só é enviada quando há candidatos; a pergunta independente sobre o papel da página sempre pode ser enviada. A resposta e a confiança são mostradas para revisão humana; nada é associado automaticamente. O operador pode escolher outra campanha, vincular um relatório compatível, confirmar ou limpar a associação. Cada mudança fica registrada com autor e data. A tela informa se a integração TypeSafe está configurada. A chave é lida de **Parâmetros → Integrações** no CentralX; `TYPESAFE_API_KEY` no servidor é a alternativa.

## Acesso próprio do Reports

Um administrador da organização pode abrir **Acesso** e conceder a uma conta existente papel de visualização, operação ou administração para um `client_id`. A opção de acesso exclusivo impede que essa conta entre nos outros módulos do Cadu; as requisições de Reports usam apenas os clientes com concessão ativa. Alterações e revogações são lidas do banco nas requisições seguintes, inclusive quando uma sessão já estava aberta. Contas exclusivas não recebem acesso automático ao cliente da organização.

## Relatórios na interface React

A biblioteca do Reports agora abre o detalhe no React. O operador pode editar objetivo, metas, notas, datas e cor, com nota obrigatória, controle de versão e histórico. Publicação e revogação do link público também ficam no detalhe. A revisão de prints, o envio de fontes e a edição de identidade ainda abrem as telas anteriores enquanto essas etapas são migradas; os dados e permissões são os mesmos.

## Implantação e próxima etapa

`deploy.sh` aplica `migrations/add_reports_operations_v1.sql`, `migrations/add_reports_review_fixes_v1.sql` e `migrations/add_reports_link_associations_v1.sql`, inclusive em ambientes que já tenham as primeiras migrações. O bundle React é construído por `npm run build:reports`. As migrações são aditivas e preservam os dados anteriores. A V1 ainda não inclui conectores nativos para outras plataformas, importação completa de métricas antigas, automações de audiência, análise de cliques ou mapa de calor. Esses recursos dependem de contratos de ingestão e controles de privacidade próprios antes de ativação.

Após aplicar as migrações em homologação, `python scripts/audit_reports_v1.py` verifica em modo somente leitura as tabelas exigidas e referências entre clientes. Ele termina com código 2 se faltar tabela e 1 se encontrar vínculo cruzado; não altera registros.

O procedimento de backup, pilotos, critérios de liberação e retorno está em [reports-v1-rollout.md](reports-v1-rollout.md).

Para retenção, `scripts/prune_reports_events.py` mostra por padrão quantos eventos brutos superaram 180 dias e quantas confirmações do CRM superaram 400 dias. `--apply` executa a exclusão em lotes. O operador pode agendar esse comando no ambiente de produção após revisar os períodos; ele não roda na abertura de páginas nem durante o deploy.

## Plano de continuação

O plano com prioridades, dependências e critérios de conclusão está em [reports-v1-next-steps.md](reports-v1-next-steps.md). A próxima execução começa pela consolidação das mudanças do Reports, aplicação controlada das migrações e pilotos de Google Ads, tag e CRM.
