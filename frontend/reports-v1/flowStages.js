export const FLOW_STAGES = Object.freeze([
  {id:'source',label:'Origem'}, {id:'entry',label:'Entrada'},
  {id:'exploration',label:'Exploração'}, {id:'intent',label:'Intenção'},
  {id:'conversion',label:'Conversão'}, {id:'support',label:'Suporte e erros'},
]);
export function stageFor(node) {
  if(FLOW_STAGES.some(stage=>stage.id===node.stage))return node.stage;
  if(node.type==='source')return 'source';
  if(node.type==='conversion'||node.suggestedRole==='conversion')return 'conversion';
  if(node.type==='error'||['legal','error'].includes(node.role))return 'support';
  if(['form','whatsapp'].includes(node.type)||['intent','form','checkout'].includes(node.role)||/\/(contato|orcamento|agendar)(\/|$)/i.test(node.path||''))return 'intent';
  if(node.isEntry||node.path==='/')return 'entry';
  return 'exploration';
}
export function funnelEdges(config,{full=false,returns=false,metrics=null}={}) {
  const byId=new Map(config.nodes.map(node=>[node.id,node]));
  const valid=config.edges.filter(edge=>byId.has(edge.from)&&byId.has(edge.to));
  if(full)return valid;
  const candidates=valid.filter(edge=>{
    if(edge.kind==='site_link'||edge.origin==='navigation')return false;
    const from=byId.get(edge.from),to=byId.get(edge.to);
    if(from.groupId&&from.groupId===to.groupId)return false;
    return returns||FLOW_STAGES.findIndex(s=>s.id===stageFor(to))>=FLOW_STAGES.findIndex(s=>s.id===stageFor(from));
  });
  if(!metrics)return mergeDirections(candidates).slice(0,20);
  const counts=new Map(metrics.map(edge=>[edge.id,Number(edge.sessions)||0]));
  const accepted=new Set();
  for(const node of config.nodes){
    const outgoing=candidates.filter(edge=>edge.from===node.id).sort((a,b)=>(counts.get(b.id)||0)-(counts.get(a.id)||0)||a.id.localeCompare(b.id));
    const total=outgoing.reduce((sum,edge)=>sum+(counts.get(edge.id)||0),0);
    let covered=0;
    outgoing.forEach((edge,index)=>{if(index<3&&(covered<total*.8||index===0)){accepted.add(edge.id);covered+=counts.get(edge.id)||0;}});
  }
  return mergeDirections(candidates.filter(edge=>accepted.has(edge.id))).slice(0,20);
}

function mergeDirections(edges){
  const result=[],pairs=new Map();
  for(const edge of edges){const reverse=pairs.get(`${edge.to}:${edge.from}`);if(reverse){reverse.reverseId=edge.id;continue;}const item={...edge};result.push(item);pairs.set(`${edge.from}:${edge.to}`,item);}
  return result;
}
