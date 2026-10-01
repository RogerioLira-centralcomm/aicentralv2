export const FLOW_STAGES = Object.freeze([
  {id:'source',label:'Origem'}, {id:'entry',label:'Entrada'},
  {id:'exploration',label:'Exploração'}, {id:'intent',label:'Intenção'},
  {id:'conversion',label:'Conversão'}, {id:'support',label:'Suporte e erros'},
]);
export const FLOW_STAGE_WIDTH=320;
export const FLOW_STAGE_NODE_X=80;
export const PAGE_TYPES=Object.freeze(['home','service','institutional','contact','case','content','other']);
export function stageX(stage){const index=FLOW_STAGES.findIndex(item=>item.id===stage);return FLOW_STAGE_NODE_X+Math.max(0,index)*FLOW_STAGE_WIDTH;}
export function stageAtX(x){
  const index=Math.floor((Number(x)-48)/FLOW_STAGE_WIDTH);
  return FLOW_STAGES[Math.max(0,Math.min(FLOW_STAGES.length-1,index))].id;
}
export function editableStage(node){
  if(node.type==='source')return 'source';
  if(node.stage==='source'&&['page','form','conversion','error'].includes(node.type))return node.isEntry||node.path==='/'?'entry':'exploration';
  return stageFor(node);
}
export function placeNodeInStage(node,stage){const target=node.type==='source'?'source':stage==='source'?'entry':stage;return {...node,stage:target,x:stageX(target)};}
export function stageFor(node) {
  if(node.type==='source')return 'source';
  if(node.stage==='source'&&['page','form','conversion','error'].includes(node.type))return node.isEntry||node.path==='/'?'entry':'exploration';
  if(FLOW_STAGES.some(stage=>stage.id===node.stage))return node.stage;
  if(node.type==='conversion'||node.suggestedRole==='conversion')return 'conversion';
  if(node.type==='error'||['legal','error'].includes(node.role))return 'support';
  if(['form','whatsapp'].includes(node.type)||['intent','form','checkout'].includes(node.role)||/\/(contato|orcamento|agendar)(\/|$)/i.test(node.path||''))return 'intent';
  if(node.isEntry||node.path==='/')return 'entry';
  return 'exploration';
}
export function isReturnEdge(edge,byId){
  const source=byId.get(edge.from),target=byId.get(edge.to);
  return Boolean(source&&target&&FLOW_STAGES.findIndex(stage=>stage.id===stageFor(target))<FLOW_STAGES.findIndex(stage=>stage.id===stageFor(source)));
}
export function funnelEdges(config,{full=false,returns=false}={}) {
  const byId=new Map(config.nodes.map(node=>[node.id,node]));
  const valid=config.edges.filter(edge=>byId.has(edge.from)&&byId.has(edge.to));
  if(full)return valid;
  return valid.filter(edge=>{
    const from=byId.get(edge.from),to=byId.get(edge.to);
    if(from.groupId&&from.groupId===to.groupId)return false;
    return returns||!isReturnEdge(edge,byId);
  });
}

// One grid for everything on the board: the canvas snaps to it and every placement is a multiple of it,
// so a group of selected steps keeps its spacing when it is dragged.
export const FLOW_GRID=20;
export const alignToGrid=value=>Math.round(Number(value||0)/FLOW_GRID)*FLOW_GRID;
export function alignConfigToGrid(config){
  if(!config)return config;
  const align=item=>({...item,x:alignToGrid(item.x),y:alignToGrid(item.y)});
  let changed=false;
  const nodes=(config.nodes||[]).map(node=>{const next=align(node);if(next.x!==node.x||next.y!==node.y)changed=true;return next;});
  const groups=(config.groups||[]).map(group=>{const bounds={x:alignToGrid(group.bounds.x),y:alignToGrid(group.bounds.y),width:Math.max(FLOW_GRID*5,alignToGrid(group.bounds.width)),height:Math.max(FLOW_GRID*5,alignToGrid(group.bounds.height))};
    if(Object.keys(bounds).some(key=>bounds[key]!==group.bounds[key]))changed=true;return {...group,bounds};});
  return changed?{...config,nodes,...(groups.length?{groups}:{})}:config;
}
