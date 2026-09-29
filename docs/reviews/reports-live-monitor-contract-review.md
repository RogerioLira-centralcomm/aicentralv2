# Revisão dos contratos de Fluxos e monitoramento

29/09/2026. Revisão estática do backend, coletor Super Tag e React; sem consulta ao banco de produção ou teste de carga. Nenhum contrato abaixo foi implementado nesta revisão.

## Achados prioritários

### P1 — Eventos não estão isolados por fluxo quando a tag é compartilhada

`reports_flow.py` cria fluxos adicionais com o mesmo tag_id. `_fanout_flow_events` em `reports_supertag.py` replica cada evento por fluxo publicado, mas a inserção em flow_events identifica tag_id e flow_revision, sem flow_id. As consultas do monitor filtram tag_id + revisão. Dois fluxos da mesma tag na mesma revisão podem ler eventos um do outro e duplicar contagens de acessos. COUNT DISTINCT pode esconder parte do problema, mas não resolve o escopo.

Correção: chave de evento por organização, cliente, flow_id, revisão e source_event_id; deduplicação no banco; escopo por flow_id também em etapas, snapshots de sessão, checks e publicação. Migração deve tratar registros antigos ambíguos sem atribuir arbitrariamente a um fluxo.

### P1 — Online depende do período histórico e não representa ocupação atual

`totals.online` e `activity.online` usam selected_events, já restrito por data/período e revisão. Selecionar um período antigo zera online. A mesma sessão pode ser contada em várias páginas nos 90 segundos; page_leave também conta como presença.

Correção: consulta live própria; sessão ativa = último sinal válido dentro da janela; posição atual = última página conhecida por sessão. Processar page_leave/visibilidade de forma explícita, admitindo expiração por TTL quando o encerramento não chegar. Mostrar “sessões ativas”, nunca “pessoas” sem identidade deduplicável.

### P1 — Conversões e etapas não têm a mesma unidade/semântica

O total conversions é COUNT(DISTINCT visitor_id), enquanto o texto da UI diz eventos. O fanout usa session_id como fallback de visitor_id; portanto isso não garante pessoas únicas. Não existe contrato específico de pessoas atualmente em conversão.

O match de nós de conversão no monitor considera event_kind=conversion, mas não compara event_name como o matcher de ingestão faz. Dois eventos de conversão na mesma URL podem aparecer atribuídos às mesmas etapas.

Correção: separar conversion_events, converting_sessions e converted_visitors (este último apenas se a identidade estiver disponível e sua cobertura for conhecida). Aplicar um matcher único de tipo, domínio, caminho e nome de evento em ingestão e consultas.

### P1 — Animação não representa novas transições

CSS anima todas as arestas infinitamente, inclusive warning. recent_transition é um EXISTS de uma passagem na janela de 15 minutos e não um delta. Uma passagem antiga continua animando; ausência de passagem também anima em amarelo.

Correção: linhas estáticas por padrão; pulsos finitos somente para novas transições identificadas por cursor/ID. Primeira carga é baseline. Falha de rede pausa animações; saúde HTTP não move partículas. Respeitar reduced-motion.

### P2 — Passagem por aresta não significa próxima etapa

As consultas unem quaisquer eventos source e target posteriores na mesma sessão. Isso mede “alcançou destino depois”, inclusive com etapas intermediárias, não transição direta. Uma pessoa pode alimentar várias arestas de saída.

Correção: definir contratos separados para transição direta (LEAD após normalização/deduplicação da jornada) e alcance posterior. Não trocar a semântica retroativamente sem versionar a métrica.

### P2 — Atualização funciona por polling, sem cursor de eventos

Frontend consulta a cada 15 s, evita polls sobrepostos e pausa ao ocultar a aba. Coletor envia batches a cada 5 s e heartbeat a cada 30 s em página visível. Portanto não é streaming instantâneo; a presença pode permanecer por até a janela de 90 s após o último sinal. O backend não retorna cursor, generated_at, watermark de ingestão ou validade do snapshot.

Correção: primeiro endpoint live pequeno com envelope versionado; separar consultas históricas pesadas. Depois avaliar SSE autenticado com fallback de polling. Cursor deve usar ordem de ingestão, pois occurred_at pode chegar atrasado ou fora de ordem.

### P2 — Saúde operacional se mistura com tráfego

O estado dos nós combina sinais dos últimos 15 min com último check HTTP; amarelo pode significar ausência normal de visitas. Worker cobre no máximo 20 páginas e erros internos podem marcar offline.

Correção: availability, collection e traffic como estados separados; informar cobertura e idade do check. Falha do verificador não equivale a indisponibilidade do site.

## Contrato proposto

Manter endpoint histórico para relatórios; criar GET /api/v1/reports/flow/flows/{flow_id}/live com client_id, after_cursor e filtros de atribuição explicitamente suportados. A versão live é sempre a publicada atual; uma visualização histórica recebe aviso e não se apresenta como ocupação ao vivo.

Envelope:
- schema_version: versão do contrato.
- scope: organization_id, client_id, site_id, flow_id, published_revision e filtros aplicados.
- generated_at, received_through, cursor, reset_required, suggested_poll_ms.
- collection: estado, last_received_at, freshness_seconds e active_window_seconds.
- availability: estado, checked_at, monitored_pages, total_pages, checker_error.
- totals: active_sessions, page_view_events, conversion_events, converting_sessions; cada campo com janela explícita.
- nodes: node_id, active_sessions_here, reached_sessions, conversion_events, last_activity_at.
- edges: edge_id, direct_transition_sessions, new_transition_count, last_transition_at.
- updates: registros agregados com ID estável, tipo, node_id/edge_id, count e received_at; nunca incluir dados pessoais no canvas.

Invariantes:
1. Um cliente não acessa dados de outro; validar fluxo e revisão no servidor.
2. active_sessions_here usa uma única posição por sessão. Grupos calculam união de sessões, não soma de visitantes das etapas.
3. Duplicação/retry do mesmo source_event_id não altera o resultado.
4. cursor não avança sobre registros não entregues; paginação e limites têm sinal de continuação.
5. Mudança de revisão ou filtros exige reset explícito e novo baseline; não animar diferenças entre escopos.
6. Ausência de resultado/erro retorna indisponível; zero significa medição válida igual a zero.
7. Conversão concluída é evento; “em conversão” é um estado de interação com início, conclusão/abandono e TTL.

## “Em conversão”: entrega honesta

Com dados atuais, exibir “Sessões ativas na página de conversão”, se a última posição e a janela estiverem disponíveis. Isso não comprova preenchimento de formulário.

Para medir interação em andamento: acrescentar form_start/form_progress sem conteúdo de campos, identificador do formulário, encerramento, conclusão confirmada e expiração. submit observado não comprova aceitação pelo backend do site. Uma pessoa pode ter várias sessões/dispositivos; usar “sessões” como unidade padrão.

## Interface e animação

- Cabeçalho: disponibilidade do site, estado da coleta e horário do snapshot separados.
- KPI: sessões ativas agora; acessos no período; conversões no período; sessões interagindo (somente com instrumentação).
- Card: badge de ocupação atual, total histórico secundário e pulso curto quando chega um novo evento daquele nó.
- Aresta: largura por volume da janela selecionada; pulso por novas transições, com limite de partículas e agregação em tráfego alto.
- Grupo recolhido: união de sessões e contagem agregada de transições; não duplicar pulsos nas arestas internas/externas.
- Estado de reconexão: manter último snapshot com idade visível, interromper movimento e carregar baseline ao recuperar cursor expirado.

## Testes necessários antes de ativar

- Dois fluxos publicados da mesma tag, ambos revisão 1: eventos e taxas isolados.
- Retry de batch, múltiplas abas, eventos atrasados e ordem de chegada invertida.
- Dois eventos de conversão distintos na mesma URL.
- Período histórico selecionado enquanto live continua na publicação atual.
- Sessão A→B→C: não afirmar transição direta A→C.
- page_leave, aba oculta, heartbeat interrompido e TTL.
- Republicação no meio da sessão e vínculo à versão correta.
- Primeiro snapshot sem animação; cursor repetido sem pulso; novo evento produz um pulso finito.
- Falha HTTP do endpoint, worker parado, check antigo e recuperação.
- reduced-motion e limitação de atualizações para tráfego alto.

Ordem: isolamento/deduplicação → semântica das métricas → endpoint live e cursor → interface/pulsos → instrumentação de conversão em andamento → SSE se necessário.

## Segunda revisão com a skill typesafe-ai

A documentação oficial de confidence foi consultada em https://docs.typesafe.ai/confidence. O guia de construção permaneceu indisponível. Não foi executada inferência remota Jev: a revisão aplicou a skill ao código e aos contratos.

### P1 adicional — Publicação de fluxo adicional arquiva etapas do principal

O endpoint discovery-flows reutiliza flow.tag_id (reports_flow.py:1286–1290). sync_published_steps arquiva todas as etapas ativas dessa tag que não pertencem à publicação atual (reports_flow_versions.py:63–66). Assim, publicar um fluxo adicional pode desativar etapas do principal. Isso confirma uma quebra do contrato documentado no próprio serviço: cada Flow deve possuir sua tag interna, e a Super Tag distribui eventos entre essas tags.

Correção inicial mais compatível com o código existente: gerar tag interna exclusiva para cada fluxo adicional e impedir reutilização entre registros; manter o vínculo ao mesmo site Super Tag. Migrar compartilhamentos existentes com cuidado: registros históricos ambíguos não podem ser atribuídos automaticamente. A alternativa de flow_id explícito em todas as tabelas exige uma migração mais ampla. O plano anterior não deve tratar essa migração ampla como única solução.

### Separação entre evidência e julgamento

- Contagem, online, ocupação de nós, deduplicação, revisão e cursor são regras determinísticas. Não dependem de modelo nem de confidence.
- TypeSafe serve para sugerir o papel semântico da página. O código existente usa Choice, alternativa none, probabilidades, versão de pergunta e evidência limitada; não declara que alguém converteu.
- A montagem corrigida preserva suggestedRole e cria nós page até revisão. Essa fronteira deve continuar na publicação e nas legendas da interface.
- Confidence expressa concentração da distribuição do julgamento; não valida identidade, contrato SQL, coleta atual ou conversão real. Limiares devem ser avaliados no domínio, não copiados de exemplos.

Validação: 13 testes existentes de montagem/revisão passaram. Eles não cobrem isolamento entre dois fluxos com a mesma tag, publicação cruzada, cursor ou animação. O sucesso deles não aprova a operação live. Nenhuma alteração de aplicação realizada nesta revisão.

## Correções implementadas após a revisão

Correção da própria revisão: add_reports_funnel_management_v1.sql já define tag_id UNIQUE. Em bancos com o schema oficial, compartilhar a tag falhava na criação; contaminação/publicação cruzada eram riscos condicionados a um schema legado sem essa restrição, não falhas comprovadas em produção.

- Novos fluxos sempre recebem tag interna exclusiva; criação em lote corrigida.
- Migração defensiva add_reports_flow_private_tags_v1.sql isola tags compartilhadas apenas se existirem. Mantém eventos antigos na tag original e registra auditoria; não inventa a atribuição histórica. Não aplicada a banco nesta tarefa.
- Publicação e leitura de fluxo recusam compartilhamento legado ainda não reparado.
- Presença usa última atividade por sessão em 90 s, independente dos filtros históricos, com exclusão de page_leave. Consulta live pertence à publicação atual e todas as origens, explicitado na UI; snapshots históricos não mostram presença atual.
- Conversões contam eventos; consultas de etapas respeitam nome de conversão.
- Transições live diretas derivam da sequência de nós, interrompida por página não mapeada. UI usa ID da passagem como sinal de novidade e baseline na primeira carga/reconexão. Pulsos finitos e reduced-motion.
- Contrato live inclui versão, escopo, generated_at, intervalo, estado, posições e presença em páginas de conversão. Não afirma interação de formulário em andamento.
- Janela live limitada a 5.000 eventos/15 min. Acima disso retorna indisponibilidade explícita; não apresenta totais parciais como completos. Ainda é polling de 15 s; não há SSE ou replay de todo evento intermediário.
- Monitor HTTP usa somente o grafo publicado, até 101 URLs (100 nós + raiz); erro interno do worker marca unknown, não offline.

Publicação depende do processo normal de deploy. Bancos oficiais com a restrição UNIQUE não precisam reparar compartilhamentos. Banco legado sem restrição deve aplicar a migração defensiva primeiro. A precisão visual e a integração com PostgreSQL de produção ainda precisam ser verificadas no ambiente de destino.
