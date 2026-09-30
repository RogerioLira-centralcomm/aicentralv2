# Revisão do editor, monitoramento e navbar — 30/09/2026

Escopo: implementação 1a873569 e mudanças locais da navbar. Revisão de código, contratos e testes locais; sem consulta ou alteração em produção. Skill TypeSafe AI aplicada: estado observado separado de inferência e regras determinísticas verificadas em código. Índice oficial consultado; páginas detalhadas retornaram erro de acesso. Não houve chamada de inferência Jev.

## Achados

### P1 — Coleta e live discordam sobre conversão por visita à página

`reports_flow_versions.py:108` reconhece `page_view` em nó conversion sem event_name; `reports_flow_live.py:17` só reconhece esse nó com kind conversion. Reprodução local: sequência `/` → `/obrigado`, ambos page_view; ingestão retorna conversion, live retorna transitions vazio. Páginas de erro têm divergência semelhante. Reutilizar a mesma regra de correspondência, preferencialmente a identidade persistida da etapa/revisão. Incluir testes para conversão por página e por evento nomeado.

### P1 — Publicação nova pode misturar revisões no monitoramento

`FlowMonitorWorkspace.jsx:36–45`: journey atualiza em 60s e live em 15s; não compara suas revisões. Após publicação em outra aba, métricas/desenho da revisão N podem receber presença e pulsos da N+1. `liveScope` também não inclui a revisão efetivamente retornada. O modo histórico usa published_revision recebido inicialmente. Vincular snapshot à revisão exibida e renovar baseline quando mudar; nunca combinar respostas incompatíveis.

### P2 — Sinal global apresentado como operação de todas as conexões

`reports_flow.py:1721` considera healthy qualquer evento nos últimos 15 minutos. `FlowCanvas.jsx:82` propaga esse estado para todas as conexões diretas. Um heartbeat em uma página pode animar caminhos sem sinal observado. A legenda explica que não são pessoas, mas o sinal tampouco confirma cada ligação. Reservar sinal global ao cabeçalho, e habilitar movimento por ligação apenas com evidência/frescor próprios, ou explicitar visualmente que é uma animação global da coleta.

### P2 — Presença congelada continua rotulada como agora

`FlowMonitorWorkspace.jsx:45` continua passando node_presence quando paused. `FlowCanvas.jsx:37` escreve sessões agora. O total superior muda para Última consulta, porém os nós não. Além disso, ocultar a aba pausa consultas sem invalidar o sinal operacional; ao retornar, dados antigos continuam ativos até a resposta. Propagar paused/stale e timestamp aos nós, parar animações vencidas e usar último registro ou indisponível.

### P2 — Trocar camada apaga os números do detalhe da conexão

`FlowMonitorWorkspace.jsx:45–48` usa edges=[] para ocultar volume, mas consulta a mesma coleção para o inspector. Na camada Presença agora, uma conexão com volume conhecido passa a mostrar Não disponível. Manter dados completos separados da camada de apresentação.

## Navbar

Seletor compartilhado, foto com fallback, primeiro nome e consulta real de créditos presentes. Não encontrei exposição de credenciais no novo componente. O consumo indisponível aparece como traço. O layout permite quebra de linha; falta aceite visual do editor com todas as ações, nome longo e conta real em 1024/1366 px. O teste atual cobre monitoramento com sessão simulada sem atributos de foto/créditos; não valida integralmente a nova navbar.

## Evidência

- 29 testes Python passaram.
- Playwright passou: monitor, seleção, explorador, pausa e quatro tamanhos desktop.
- Reprodução adicional confirmou divergência de conversão por page_view.
- Nenhuma correção de produto aplicada nesta revisão.

## Limites e pendências

SQL histórico não exercitado contra PostgreSQL nesta revisão. Não há evidência suficiente para afirmar desempenho em produção, isolamento em todas as rotas ou conclusão integral do plano. Capturas reais, exportação unificada, conflitos de edição e rollout continuam pendentes no documento de progresso. Manter flag desligada até corrigir os P1 e ampliar os testes.

## Correções aplicadas após a revisão

- P1 correspondência: ingestão e live compartilham `match_flow_node`; visitas às páginas de conversão/erro agora geram a mesma etapa.
- P1 revisão: presença e pulsos só entram quando as revisões de journey/live coincidem; mudança solicita atualização histórica e reinicia a identidade dos pulsos pela revisão.
- P2 operação: animação verde exige timestamp recente de passagem na própria conexão. Um heartbeat isolado não ativa conexões.
- P2 frescor: hook invalida snapshots para animação/presença ao pausar, ocultar aba, falhar ou ultrapassar o prazo de atualização. Os nós deixam de mostrar presença congelada como agora.
- P2 camada: detalhe mantém as métricas completas; ocultar os rótulos no canvas não apaga os números do inspector.
- Fluidez: índices por URL e par de nós evitam percorrer todo o grafo por evento; métricas visuais memorizadas; nenhuma animação de bolinha usa atualização React por quadro.

Verificação após correção: 32 testes Python aprovados; Playwright aprovado com pausa removendo presença/animação e troca de camada preservando o detalhe da conexão, além das quatro resoluções desktop. Build aprovado. Desempenho com tráfego de produção permanece sem medição; não houve deploy.
