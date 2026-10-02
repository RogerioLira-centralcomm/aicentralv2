// Kept free of imports: the studio test loads this file on its own. FLOW_GRID lives in flowStages.js.
const GRID=20,alignToGrid=value=>Math.round(Number(value||0)/GRID)*GRID;

// Frames hug the real card size (248×184) and keep every edge on the 20px board grid,
// so a dragged frame and its members stay aligned with the rest of the map.
const CARD_WIDTH=260,CARD_HEIGHT=200,PAD_X=40,PAD_TOP=60,PAD_END=40;
export function groupNodes(config,ids,name='Novo grupo',id=crypto.randomUUID()) {
  const selected=config.nodes.filter(n=>ids.includes(n.id));
  if(selected.length<1)return config;
  const memberIds=selected.map(n=>n.id),members=new Set(memberIds);
  const x=alignToGrid(Math.max(0,Math.min(...selected.map(n=>Number(n.x)))-PAD_X));
  const y=alignToGrid(Math.max(0,Math.min(...selected.map(n=>Number(n.y)))-PAD_TOP));
  const bounds={x,y,width:alignToGrid(Math.max(...selected.map(n=>Number(n.x)+CARD_WIDTH))-x+PAD_END),height:alignToGrid(Math.max(...selected.map(n=>Number(n.y)+CARD_HEIGHT))-y+PAD_END)};
  const groups=(config.groups||[]).map(g=>({...g,memberIds:g.memberIds.filter(id=>!members.has(id))})).filter(g=>g.memberIds.length);
  return {...config,schema_version:3,groups:[...groups,{id,name,bounds,memberIds}],nodes:config.nodes.map(n=>members.has(n.id)?{...n,groupId:id,pageGroup:name,manuallyEdited:true}:n)};
}
export function ungroupNodes(config,id) {
  return {...config,groups:(config.groups||[]).filter(g=>g.id!==id),nodes:config.nodes.map(n=>{if(n.groupId!==id)return n;const copy={...n};delete copy.groupId;delete copy.pageGroup;return copy;})};
}
export function syncGroups(config) {
  const ids=new Set(config.nodes.map(n=>n.id));
  const groups=(config.groups||[]).map(g=>({...g,memberIds:g.memberIds.filter(id=>ids.has(id))})).filter(g=>g.memberIds.length);
  const membership=new Map(groups.flatMap(g=>g.memberIds.map(id=>[id,g.id])));
  return {...config,groups,nodes:config.nodes.map(n=>{const groupId=membership.get(n.id);if(n.groupId===groupId)return n;const copy={...n};if(groupId)copy.groupId=groupId;else delete copy.groupId;delete copy.pageGroup;return copy;})};
}

/** Recompute frames after layout so parent-relative positions stay inside them. */
export function fitGroups(config) {
  return {...config,groups:(config.groups||[]).map(group=>{
    const members=config.nodes.filter(node=>group.memberIds.includes(node.id));
    if(!members.length)return group;
    const x=alignToGrid(Math.max(0,Math.min(...members.map(node=>node.x))-PAD_X));
    const y=alignToGrid(Math.max(0,Math.min(...members.map(node=>node.y))-PAD_TOP));
    return {...group,bounds:{x,y,width:alignToGrid(Math.max(...members.map(node=>node.x+(node.width||CARD_WIDTH)))-x+PAD_END),height:alignToGrid(Math.max(...members.map(node=>node.y+(node.height||CARD_HEIGHT)))-y+PAD_END)}};
  })};
}
