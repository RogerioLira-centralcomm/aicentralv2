import * as elkApi from 'elkjs/lib/elk-api.js';
import {FLOW_STAGES,stageFor} from './flowStages.js';
// elk-api is CommonJS; the constructor arrives as default, default.default or the namespace depending on the bundler.
const ELK=[elkApi.default?.default,elkApi.default,elkApi].find(candidate=>typeof candidate==='function');
export async function layoutFlow(config,{width=240,height=150,nodeSpacing=48,layerSpacing=120,mode='stages'}={}) {
  // Layout collapsed groups as one unit; preserve their internal coordinates.
  if(config.groups?.length){
    const membership=new Map(config.groups.flatMap(g=>g.memberIds.map(id=>[id,g])));
    const proxies=config.groups.map(g=>{const members=config.nodes.filter(n=>g.memberIds.includes(n.id));return {id:g.id,type:'page',stage:stageFor(members[0]||{}),x:g.bounds.x,y:g.bounds.y,width:180,height:150,locked:members.some(n=>n.locked)};});
    const pairs=new Set();
    const edges=config.edges.map(e=>({...e,from:membership.get(e.from)?.id||e.from,to:membership.get(e.to)?.id||e.to})).filter(e=>{const key=e.from+':'+e.to;if(e.from===e.to||pairs.has(key))return false;pairs.add(key);return true;});
    const arranged=await layoutFlow({nodes:[...config.nodes.filter(n=>!membership.has(n.id)),...proxies],edges},{width,height,nodeSpacing,layerSpacing,mode});
    const placed=new Map(arranged.map(n=>[n.id,n]));
    return config.nodes.map(n=>{const group=membership.get(n.id);if(!group)return placed.get(n.id)||n;const target=placed.get(group.id);return {...n,stage:stageFor(n),x:n.x+target.x-group.bounds.x,y:n.y+target.y-group.bounds.y};});
  }
  const ids=new Set(config.nodes.map(n=>n.id));
  const graph={id:'flow',layoutOptions:{'elk.algorithm':'layered','elk.direction':'RIGHT','elk.edgeRouting':'SPLINES','elk.layered.nodePlacement.strategy':'BRANDES_KOEPF','elk.partitioning.activate':String(mode==='stages'),'elk.spacing.nodeNode':String(nodeSpacing),'elk.layered.spacing.nodeNodeBetweenLayers':String(layerSpacing)},children:config.nodes.map(node=>({id:node.id,width:node.width||width,height:node.height||height,layoutOptions:{'elk.partitioning.partition':String(FLOW_STAGES.findIndex(s=>s.id===stageFor(node)))}})),edges:config.edges.filter(e=>ids.has(e.from)&&ids.has(e.to)&&e.kind!=='site_link').map(e=>({id:e.id,sources:[e.from],targets:[e.to]}))};
  const elk=new ELK({workerFactory:()=>new Worker(new URL('./flowLayout.worker.js',import.meta.url),{type:'module'})});
  let timer;
  const result=await Promise.race([elk.layout(graph),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('A organização excedeu o tempo disponível.')),20000);})])
    .catch(error=>{throw new Error(error?.message?.includes('tempo')?error.message:'Não foi possível organizar o fluxo.');})
    .finally(()=>{clearTimeout(timer);elk.terminateWorker();});
  const positions=new Map(result.children.map(node=>[node.id,{x:Math.round(node.x+80),y:Math.round(node.y+80)}]));
  // Stages order the layers (ELK partitions); rows come from the graph itself, so busy paths stay together.
  // Notes are free annotations: arranging the journey never moves them.
  const occupied=config.nodes.filter(n=>n.locked||n.type==='note').map(n=>({...n,x:n.x,width:n.width||width,height:n.height||height}));
  const nodes=config.nodes.map(node=>{
    if(node.locked||node.type==='note')return node;
    const next={...node,stage:stageFor(node),...positions.get(node.id)};
    while(occupied.some(other=>next.x<other.x+other.width+24&&next.x+(node.width||width)+24>other.x&&next.y<other.y+other.height+24&&next.y+(node.height||height)+24>other.y)){next.y+=height+32;if(next.y>10000)break;}
    occupied.push({...next,width:node.width||width,height:node.height||height});return next;
  });
  if(nodes.some(node=>node.x>10000||node.y>10000))throw new Error('Organize grupos menores para caber na área disponível.');
  return nodes;
}
