# Reports V1 · implantação controlada

## Antes de executar

1. Confirmar por configuração e responsável se a conexão alvo é **homologação ou produção**. A conexão disponível na sessão de desenvolvimento é remota e não está identificada como homologação; não executar migrations nela até o alvo ser formalmente identificado. A inspeção somente de leitura mostrou que as tabelas `cadu_reports_*` ainda não existem nela.
2. Registrar commit e versão da aplicação em execução; manter a versão anterior disponível para retorno. Confirmar espaço e política de retenção do backup.
3. Fazer backup do alvo com a rotina operacional do ambiente, incluindo esquema e dados das tabelas `cadu_connect_report_*`, `cadu_reports_link_test_runs`, `tbl_cliente` e `tbl_contato_cliente`. Validar restore isolado. Um dump criado pela estação de desenvolvimento e restore apenas de tabelas selecionadas são evidência útil, mas não substituem o backup operacional do alvo. Não colocar senha ou dump no repositório.
4. Rotacionar nas Integrações do CentralX a credencial TypeSafe que foi compartilhada na conversa e conferir que a integração continua ativa.

## Homologação

1. Depois de confirmar homologação e backup restaurável, confira as pré-migrations e runners do Reports/Link Tester no `deploy.sh`: `add_cadu_planner_link_test_runs.sql`, `run_add_connect_report_workspace.py`, `run_add_connect_report_sources.py`, `run_add_connect_report_imports.py`, `run_add_connect_report_reviews.py`, `run_add_connect_report_ai_runs.py` e `run_add_connect_report_public_links.py`. Execute apenas as que faltarem; não rode o `deploy.sh` completo.
2. Aplicar, exatamente nesta ordem, usando `migrations/run_sql_migration.py` (uma transação por arquivo): `add_reports_operations_v1.sql`, `add_reports_review_fixes_v1.sql`, `add_reports_funnel_management_v1.sql`, `add_reports_supertag_v1.sql`, `add_reports_link_associations_v1.sql`, `move_link_tester_to_reports_v1.sql`, `add_reports_universal_imports_v1.sql`, `add_reports_import_decisions_v1.sql`, `add_reports_import_visual_runs_v1.sql`, `add_reports_import_projection_v1.sql`, `add_reports_import_projection_decisions_v1.sql`, `add_reports_import_range_snapshots_v1.sql`, `add_reports_import_custom_values_v1.sql`, `add_reports_import_custom_dimensions_v1.sql`, `add_reports_import_observation_dimensions_v1.sql`, `add_reports_import_column_maps_v1.sql` e `add_reports_import_column_suggestions_v1.sql`. Registrar o resultado de cada migration e interromper no primeiro erro. Esta lista precisa permanecer sincronizada com o bloco Reports de `deploy.sh`.
3. Executar `python scripts/audit_reports_v1.py` após a cadeia completa. Código 0 confirma que as tabelas/views requeridas existem e que as verificações conhecidas de referências entre clientes retornaram zero; código 1 indica vínculo cruzado; código 2 indica schema/coluna pendente. A auditoria não valida as telas nem substitui a reconciliação das contagens legadas pré/pós.

O Funnel Flow usa `add_reports_funnel_management_v1.sql`: ela cria o registro de fluxos, amplia os tipos de etapas, cria uma tabela separada para execuções fictícias e adiciona `event_name` para eventos personalizados. A tag de fluxo é servida por `/static/cadu_connect/cadu-flow-tag.js?client=<client_id>` e cada snippet associa a chave do cliente ao código `CF_…`. A coleta publicada grava eventos sem valores de formulários na tabela normal de tráfego. O endpoint de simulação usa somente a tabela de testes. A página Eventos lista essa coleta e o método público `window.CaduFlow.trackEvent('nome_do_evento')`. A URL de Supertag não é emitida enquanto seu script próprio não existir no produto; conexão/sincronização Google Ads continua separada das tags e do fluxo.
4. Abrir o Reports com um administrador, usuário operador e viewer. Conferir que cada um vê apenas os clientes concedidos e que viewer não grava. Abrir um relatório antigo e criar outro sem projeto.
5. Cadastrar MCC/anunciantes em **Contas**, gerar integração limitada à MCC e aos anunciantes permitidos, e instalar em conta Google Ads piloto. Comparar por dia/campanha, reenviar lote, revogar chave e testar rejeição de conta não autorizada.
6. Instalar tag em domínio piloto no código e via GTM. Validar page view, rota SPA, formulário sem valor coletado, clique, página de obrigado, usuário online, consentimento e UTM. Enviar conversão CRM com ID opaco e separar observada de confirmada.
7. Confirmar manualmente campanha no Link Tester, associar relatório, desfazer e revisar histórico/isolamento por cliente.

## Modelo de importação multicanal

- O arquivo, suas linhas originais e a leitura normalizada ficam preservados por cliente; exports diários entram como observações imutáveis em campanha/data/métrica/dimensão.
- A projeção de campanha usa a observação mais recente para cada anúncio ou dimensão e soma somente depois. Métricas proporcionais ou específicas do canal ficam em pares chave/valor, com unidade, moeda, canal e dimensões do export.
- Valores distintos para a mesma métrica e dimensão não se somam nem são escolhidos silenciosamente: a projeção sinaliza conflito e a revisão fica registrada por dimensão. Totais de período vindos de prints são snapshots separados, nunca distribuídos entre dias.
- A identidade procura primeiro IDs do provedor e valida conta anunciante, cliente e moeda. Quando o provedor não fornece IDs, tenta uma associação única pelo nome. Campanha ausente fica em revisão; a tela pede confirmação antes de criar campanha/conta de importação e gravar os fatos.
- TypeSafe pode sugerir um mapeamento para cabeçalhos desconhecidos, mas a pessoa confirma o mapeamento. Os campos determinísticos seguem no parser e no código do Reports.

## Liberação restrita e retorno

Liberar inicialmente para um `client_id` piloto e acompanhar erros HTTP de ingestão/coleta, última execução das fontes, quota da tag e divergência de totais por dia. Conservar a versão anterior da aplicação e o backup até o aceite dos números.

Se houver falha de aplicação, voltar ao commit anterior e revogar chaves ou tags afetadas. As migrações são aditivas: deixar as novas colunas e tabelas no banco durante o retorno evita apagar dados recebidos no piloto. Restaurar dados do backup somente depois de avaliar os registros criados após a implantação e decidir como preservá-los. A liberação ampla exige passar pelos critérios do piloto, não apenas pelo build do React.
