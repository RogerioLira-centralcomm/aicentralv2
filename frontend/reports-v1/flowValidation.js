const measured=new Set(['page','form','event','conversion','whatsapp','error']);
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
};

export function flowValidation(config,allowedHost='') {
  const nodes=config.nodes||[],edges=config.edges||[];
  const issues=[];
  const connected=new Set(edges.flatMap(edge=>[edge.from,edge.to]));
  const pagePaths=new Map();
  // Institutional sites are read by engagement (time, depth, exits); a conversion is optional there.
  const engagement=config.site_kind==='institucional';
  if(!engagement&&!nodes.some(node=>node.type==='conversion'))issues.push({severity:'error',code:'no_conversion',message:'Defina um nó de Conversão antes de publicar.'});
  for(const node of nodes){
    if(measured.has(node.type)&&(!node.path||node.path.startsWith('/configurar-')))issues.push({severity:'error',code:'unmapped_page',nodeId:node.id,message:`Configure a URL real de ${node.title||'um nó'}.`});
    if(node.type==='event'&&(!node.event_name||node.placeholder===true))issues.push({severity:'error',code:'unmapped_event',nodeId:node.id,message:`Configure o nome do evento de ${node.title||'um nó'}.`});
    if(node.type==='page'&&node.path&&!node.path.startsWith('/configurar-')){
      const key=`${node.host||allowedHost}:${node.path}`;
      if(pagePaths.has(key))issues.push({severity:'error',code:'duplicate_page',nodeId:node.id,message:`A URL ${node.path} já está em outra página do fluxo.`});
      else pagePaths.set(key,node.id);
    }
    if(nodes.length>1&&!connected.has(node.id))issues.push({severity:'warning',code:'orphan',nodeId:node.id,message:`${node.title||'Um nó'} está sem conexões.`});
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
