# Execução do workspace de Fluxos — 30/09/2026

## Implementado nesta entrega

- Biblioteca e monitoramento novos atrás de `flows_workspace_v2`.
- Rotas próprias para edição e monitoramento; canvas React Flow compartilhado.
- Fontes compactas com logo, páginas com prévia ilustrativa, eventos/conversões distintos e etapas visuais.
- Movimento verde nas conexões diretas quando há sinal de coleta operacional; não representa usuários. Pulsos azuis apenas após novo identificador de passagem. Movimento reduzido respeitado.
- Painéis flutuantes coordenados, controles nativos, minimapa, organização horizontal e grupos persistidos.
- Presença restrita a páginas; sessões históricas separadas de presença atual; métricas indisponíveis não fabricam zeros.
- Consulta leve de presença, pausa, cancelamento, aba oculta e backoff.
- Correções de sequência, entrada/conversão, eventos distintos na mesma URL, fuso e denominadores no relatório histórico.
- Rascunhos aceitam eventos sem nome; publicação continua validada. Erros estruturados permitem localizar etapas duplicadas.
- Histórico por gesto, proteção contra resultado atrasado de organização e dimensões preservadas em leitura.

## Verificação

29 testes Python de workspace, live, schema, versões e descoberta passaram. Build Reports aprovado. Teste Playwright com APIs simuladas: monitor, seleção, explorador, pausa, ausência de erro JavaScript e overflow horizontal em 1920×1080, 1440×900, 1366×768 e 1024×768.

Essas verificações não substituem execução das consultas em Postgres real, teste de carga, revisão visual completa de todos os estados ou aceite em produção. Prévias atuais são ilustrativas, identificadas como tal.

## Ainda necessário para concluir o plano integral

- Exercitar SQL histórico em Postgres com fixtures temporais e EXPLAIN; avaliar índices e sessões entre dias.
- Completar máquina de estados de salvamento/conflito entre abas e comandos com patches; testar publicação concorrente.
- Expandir testes de grupos, reconexão, histórico, teclado, toque, leitor de tela e 200 nós/300 conexões.
- Finalizar navegação de aliases, retorno com filtros e histórico back/forward; coordenar viewport ao redimensionar sem perder o foco.
- Capturas reais com fila, proteção SSRF, armazenamento/retencão e fallback; exploração completa de páginas/origens/eventos.
- Camadas HTTP/coleta separadas, saúde por URL, integrações futuras claramente identificadas e templates por objetivo.
- Exportação pelo mesmo renderer, revisão de acessibilidade e divisão dos bundles grandes.
- Ativar CENTRALCOMM, executar pilotos e só então retirar legado/flag, conforme plano.

## Ativação

A flag permanece desligada por padrão. `REPORTS_FLOWS_WORKSPACE_V2_CLIENTS` recebe IDs de clientes separados por vírgula; `*` habilita globalmente e não é recomendado antes do aceite. Nenhuma configuração de produção foi modificada nesta entrega.

Padrões usados: America/Sao_Paulo; permissões existentes de publicação; sessão conforme identificador da ingestão. Infraestrutura de captura e outros pilotos ainda não validados.
