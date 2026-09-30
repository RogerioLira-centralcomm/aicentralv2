const measured=new Set(['page','form','event','conversion','whatsapp','error']);

export function flowValidation(config,allowedHost='') {
  const nodes=config.nodes||[],edges=config.edges||[];
  const issues=[];
  const connected=new Set(edges.flatMap(edge=>[edge.from,edge.to]));
  const pagePaths=new Map();
  if(!nodes.some(node=>node.type==='conversion'))issues.push({severity:'error',code:'no_conversion',message:'Adicione uma etapa de conversão antes de publicar.'});
  for(const node of nodes){
    if(measured.has(node.type)&&(!node.path||node.path.startsWith('/configurar-')))issues.push({severity:'error',code:'unmapped_page',nodeId:node.id,message:`Configure a URL real de ${node.title||'uma etapa'}.`});
    if(node.type==='event'&&(!node.event_name||node.placeholder===true))issues.push({severity:'error',code:'unmapped_event',nodeId:node.id,message:`Configure o nome do evento de ${node.title||'uma etapa'}.`});
    if(node.type==='page'&&node.path&&!node.path.startsWith('/configurar-')){
      const key=`${node.host||allowedHost}:${node.path}`;
      if(pagePaths.has(key))issues.push({severity:'error',code:'duplicate_page',nodeId:node.id,message:`A URL ${node.path} já está em outra página do fluxo.`});
      else pagePaths.set(key,node.id);
    }
    if(nodes.length>1&&!connected.has(node.id))issues.push({severity:'warning',code:'orphan',nodeId:node.id,message:`${node.title||'Uma etapa'} está sem conexões.`});
  }
  const byId=new Map(nodes.map(node=>[node.id,node]));
  const next=new Map(nodes.map(node=>[node.id,edges.filter(edge=>edge.from===node.id).map(edge=>edge.to)]));
  const stack=[],visited=new Set();let unsafeCycle=false;
  const walk=id=>{if(stack.includes(id)){unsafeCycle ||= !stack.slice(stack.indexOf(id)).some(item=>byId.get(item)?.type==='condition');return;}if(visited.has(id))return;stack.push(id);(next.get(id)||[]).forEach(walk);stack.pop();visited.add(id);};
  nodes.forEach(node=>walk(node.id));
  if(unsafeCycle)issues.push({severity:'error',code:'cycle_without_condition',message:'Há um ciclo sem bloco de condição. Revise as conexões.'});
  return issues;
}
