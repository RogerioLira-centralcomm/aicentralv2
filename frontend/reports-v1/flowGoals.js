// What counts as success for a flow. Conversion is one answer; many sites are read by time, reach or navigation.
export const FLOW_GOALS=Object.freeze([
  {id:'conversion',label:'Conversão',summary:'O visitante conclui uma ação: formulário, WhatsApp, compra.',
    setup:['Marque um nó de Conversão no fim do caminho.','Se houver formulário, use “Testar conversão” para confirmar que ele leva a uma página de obrigado.','A taxa de conversão vem de quem chegou e converteu.'],
    page:'Esta página conta como sucesso quando leva o visitante à Conversão. Ligue-a até lá.'},
  {id:'time',label:'Tempo na página',summary:'O visitante fica e lê o conteúdo: artigos, páginas institucionais.',
    setup:['Escolha as páginas-chave: o sucesso é o tempo ativo nelas.','A rolagem além de 50% conta como leitura.','Não é preciso criar um nó de Conversão.'],
    page:'Sucesso aqui é permanência: tempo ativo e rolagem além de 50%.'},
  {id:'reach',label:'Acesso',summary:'O objetivo é gerar visitas e saber de onde vêm.',
    setup:['Ligue cada origem de tráfego à página de entrada.','O sucesso é o volume de sessões por origem.','Não é preciso criar um nó de Conversão.'],
    page:'Sucesso aqui é o número de visitas que chegam a esta página e de onde vêm.'},
  {id:'navigation',label:'Navegação interna',summary:'O visitante explora o site: páginas por visita e profundidade.',
    setup:['Ligue as páginas na ordem em que se espera a navegação.','O sucesso é páginas por visita e quem segue para o próximo passo.','As saídas mostram onde a navegação para.'],
    page:'Sucesso aqui é o visitante seguir para a próxima página do caminho, em vez de sair.'},
]);
export const GOAL_IDS=FLOW_GOALS.map(goal=>goal.id);

/** A saved goal wins; older institutional sites read as navigation, everything else as conversion. */
export const flowGoal=config=>GOAL_IDS.includes(config?.goal)?config.goal:config?.site_kind==='institucional'?'navigation':'conversion';
export const goalById=id=>FLOW_GOALS.find(goal=>goal.id===id)||FLOW_GOALS[0];
/** Flows read by engagement do not need a Conversion node to publish. */
export const isEngagementFlow=config=>flowGoal(config)!=='conversion';
