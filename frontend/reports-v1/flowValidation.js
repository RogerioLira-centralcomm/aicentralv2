import {isEngagementFlow} from './flowGoals.js';
// Kept free of imports: the parity test loads this file on its own.
const measured=new Set(['page','form','event','conversion','whatsapp','error']);
export const MEASURED_TYPES=measured;
export const NODE_STATUSES=['planned','in_production','ready','live'];
export const hasRealPath=node=>typeof node?.path==='string'&&node.path.startsWith('/')&&!node.path.startsWith('//');
// A step can exist in the plan before its page does; only ready/live steps are measured.
// Planning is an explicit choice: without a status, a step missing its URL is "ready" and publication asks for it.
export function nodeStatus(node){
  if(NODE_STATUSES.includes(node?.status))return node.status;
  return !measured.has(node?.type)||hasRealPath(node)?'live':'ready';
}
export const isPlanned=node=>measured.has(node?.type)&&['planned','in_production'].includes(nodeStatus(node));
export const isMeasured=node=>measured.has(node?.type)&&['ready','live'].includes(nodeStatus(node))&&hasRealPath(node);
const pageTypes=new Set(['page','form','conversion','error']);
// A flow follows a few pages that matter; the explorer is where the rest of the site lives.
export const MAX_FLOW_PAGES=6;
const details={
  no_conversion:['Sem conversão definida, não será possível medir a conclusão desta jornada.','add_conversion'],
  unmapped_page:['O nó não poderá ser associado a uma página ou evento recebido.','configure_url'],
  unmapped_event:['A Super Tag não conseguirá associar este evento ao nó.','configure_event'],
  duplicate_page:['A mesma visita pode ser atribuída ao nó errado.','review_duplicate'],
  orphan:['Este nó não participa de um caminho planejado.','connect_node'],
  intent_without_goal:['Não há caminho deste nó até uma conversão definida.','connect_to_conversion'],
  unconfirmed_goal:['O objetivo sugerido ainda não foi revisado.','confirm_goal'],
  cycle_without_condition:['A jornada pode ficar ambígua neste Retorno.','review_return'],
  too_many_pages:['Com muitas páginas o fluxo deixa de mostrar o caminho principal.','reduce_pages'],
  planned_step:['Este passo fica fora da medição até ter uma página no ar.','link_page'],
  planned_conversion:['A medição não registrará conclusões enquanto a conversão estiver planejada.','link_page'],
  duplicate_source_utm:['As visitas das duas origens chegam iguais e não poderão ser separadas nos relatórios.','set_utm_campaign'],
  duplicate_search_engine:['O mesmo buscador em duas origens divide as visitas de forma arbitrária.','choose_search_engines'],
};
export const isSearchSource=node=>node?.type==='source'&&(node.kind==='traffic.organic_search'||node.source==='organic');
// What the Super Tag can tell apart: UTM source, UTM campaign and the linked client campaign.
export function sourceTrafficKey(node){
  const utm=node?.media?.utm||{};
  const source=utm.source||node?.source||String(node?.kind||'').split('.').slice(1).join('.');
  return [String(source).toLowerCase(),String(utm.campaign||'').toLowerCase(),String(node?.campaign_id||'')].join('|');
}
// Engines a search origin covers; an origin without a choice covers every engine.
export const searchEnginesOf=node=>Array.isArray(node?.search_engines)&&node.search_engines.length?node.search_engines:['*'];

export function flowValidation(config,allowedHost='') {
  const nodes=config.nodes||[],edges=config.edges||[];
  const issues=[];
  const connected=new Set(edges.flatMap(edge=>[edge.from,edge.to]));
  const pagePaths=new Map();
  const sourceKeys=new Set(),searchEngines=new Set();
  // Institutional sites are read by engagement (time, depth, exits); a conversion is optional there.
  const engagement=isEngagementFlow(config);
  const conversions=nodes.filter(node=>node.type==='conversion');
  if(!engagement&&!conversions.length)issues.push({severity:'error',code:'no_conversion',message:'Defina um nó de Conversão antes de publicar.'});
  else if(!engagement&&nodes.some(isMeasured)&&conversions.every(node=>['planned','in_production'].includes(nodeStatus(node))))issues.push({severity:'warning',code:'planned_conversion',message:'Todas as conversões estão planejadas; a medição não registrará conclusões.'});
  for(const node of nodes){
    const planned=isPlanned(node);
    if(planned)issues.push({severity:'info',code:'planned_step',nodeId:node.id,message:`${node.title||'Um passo'} está planejado e ainda não é medido.`});
    else if(measured.has(node.type)&&!hasRealPath(node))issues.push({severity:'error',code:'unmapped_page',nodeId:node.id,message:`Configure a URL real de ${node.title||'um nó'} ou marque o passo como Planejado.`});
    if(!planned&&node.type==='event'&&(!node.event_name||node.placeholder===true))issues.push({severity:'error',code:'unmapped_event',nodeId:node.id,message:`Configure o nome do evento de ${node.title||'um nó'}.`});
    if(node.type==='page'&&isMeasured(node)){
      const key=`${node.host||allowedHost}:${node.path}`;
      if(pagePaths.has(key))issues.push({severity:'error',code:'duplicate_page',nodeId:node.id,message:`A URL ${node.path} já está em outra página do fluxo.`});
      else pagePaths.set(key,node.id);
    }
    if(isSearchSource(node)){
      const engines=searchEnginesOf(node);
      if(engines.some(engine=>searchEngines.has(engine))||(searchEngines.size&&engines.includes('*'))||searchEngines.has('*'))issues.push({severity:'error',code:'duplicate_search_engine',nodeId:node.id,message:`${node.title||'Esta busca'} repete um buscador de outra origem de busca.`});
      engines.forEach(engine=>searchEngines.add(engine));
    }else if(node.type==='source'){
      const key=sourceTrafficKey(node);
      if(sourceKeys.has(key))issues.push({severity:'error',code:'duplicate_source_utm',nodeId:node.id,message:`${node.title||'Esta origem'} repete a origem e a campanha UTM de outra origem; defina uma utm_campaign própria.`});
      sourceKeys.add(key);
    }
    if(node.type!=='note'&&nodes.length>1&&!connected.has(node.id))issues.push({severity:'warning',code:'orphan',nodeId:node.id,message:`${node.title||'Um nó'} está sem conexões.`});
  }
  const byId=new Map(nodes.map(node=>[node.id,node]));
  const reachable=new Set(nodes.filter(n=>n.type==='conversion').map(n=>n.id));
  let changed=true;while(changed){const size=reachable.size;edges.forEach(e=>{if(reachable.has(e.to))reachable.add(e.from);});changed=size!==reachable.size;}
  if(!engagement)nodes.filter(n=>(n.stage==='intent'||['form','whatsapp'].includes(n.type))&&!reachable.has(n.id)).forEach(n=>issues.push({severity:'error',code:'intent_without_goal',nodeId:n.id,message:`Conecte ${n.title||'o nó de Intenção'} a um nó de Conversão.`}));
  // A group of similar pages reads as one step.
  const pages=new Set(nodes.filter(node=>pageTypes.has(node.type)).map(node=>node.groupId||node.id)).size;
  if(pages>MAX_FLOW_PAGES)issues.push({severity:'warning',code:'too_many_pages',message:`O fluxo tem ${pages} páginas; mantenha até ${MAX_FLOW_PAGES} no caminho principal.`});
  if(nodes.some(n=>n.origin==='blueprint')&&config.blueprintGoalConfirmed!==true)issues.push({severity:'error',code:'unconfirmed_goal',message:'Confirme o objetivo da montagem antes de publicar.'});
  const stack=[],visited=new Set();let unsafeCycle=false,unsafeEdgeId;
  const walk=(id,edgeId)=>{if(stack.includes(id)){if(!stack.slice(stack.indexOf(id)).some(item=>byId.get(item)?.type==='condition')){unsafeCycle=true;unsafeEdgeId||=edgeId;}return;}if(visited.has(id))return;stack.push(id);edges.filter(edge=>edge.from===id).forEach(edge=>walk(edge.to,edge.id));stack.pop();visited.add(id);};
  nodes.forEach(node=>walk(node.id));
  if(unsafeCycle)issues.push({severity:'error',code:'cycle_without_condition',edgeId:unsafeEdgeId,message:'Há um Retorno sem nó de condição. Revise as conexões.'});
  return issues.map(issue=>({...issue,consequence:details[issue.code][0],action:details[issue.code][1]}));
}
