# Reports V1 · implantação controlada

## Antes de executar

1. Confirmar por configuração e responsável que a conexão de banco é **homologação**. A conexão disponível na sessão de desenvolvimento é remota e não está identificada como homologação; a inspeção somente de leitura mostrou que as tabelas `cadu_reports_*` ainda não existem nela.
2. Registrar commit e versão da aplicação em execução; manter a versão anterior disponível para retorno. Confirmar espaço e política de retenção do backup.
3. Fazer backup do banco com a rotina do ambiente, incluindo esquema e dados das tabelas `cadu_connect_report_*`, `cadu_planner_link_test_runs`, `tbl_cliente` e `tbl_contato_cliente`. Validar que o arquivo é restaurável em ambiente isolado. Não colocar senha ou dump no repositório.
4. Rotacionar nas Integrações do CentralX a credencial TypeSafe que foi compartilhada na conversa e conferir que a integração continua ativa.

## Homologação

1. Aplicar as migrações prévias de relatório e Link Tester do `deploy.sh`, caso ainda faltem. Depois aplicar, nesta ordem, `add_reports_operations_v1.sql`, `add_reports_review_fixes_v1.sql` e `add_reports_link_associations_v1.sql` usando `migrations/run_sql_migration.py`. O runner executa cada arquivo em transação.
2. Executar `python scripts/audit_reports_v1.py`. Código de saída 0 significa que todas as tabelas exigidas existem e as verificações conhecidas de referência entre clientes retornaram zero. Código 1 indica vínculo cruzado; 2 indica migração pendente.
3. Abrir o Reports com um administrador, um usuário operador e um usuário exclusivo. Conferir que cada um vê apenas os clientes concedidos, e que o papel de visualização não grava. Abrir um relatório antigo e criar outro sem projeto.
4. Instalar o script em uma conta Google Ads piloto com chave vinculada ao cliente. Comparar o dia recebido por conta/campanha com a plataforma; repetir o mesmo lote; revogar a chave. Repetir em MCC com duas contas permitidas e verificar a rejeição de conta fora da lista.
5. Instalar a tag em domínio piloto no código e via GTM. Confirmar página inicial, mudança de rota SPA, página de obrigado, contador online e preservação do UTM. Enviar conversão confirmada pelo CRM com ID opaco e conferir a diferença entre observada e confirmada.
6. Confirmar manualmente a campanha de um Link Tester e vincular um relatório. Verificar histórico, remoção e isolamento por cliente.

## Liberação restrita e retorno

Liberar inicialmente para um `client_id` piloto e acompanhar erros HTTP de ingestão/coleta, última execução das fontes, quota da tag e divergência de totais por dia. Conservar a versão anterior da aplicação e o backup até o aceite dos números.

Se houver falha de aplicação, voltar ao commit anterior e revogar chaves ou tags afetadas. As migrações são aditivas: deixar as novas colunas e tabelas no banco durante o retorno evita apagar dados recebidos no piloto. Restaurar dados do backup somente depois de avaliar os registros criados após a implantação e decidir como preservá-los. A liberação ampla exige passar pelos critérios do piloto, não apenas pelo build do React.
