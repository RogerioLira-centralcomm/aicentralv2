export function groupNodes(config,ids,name='Novo grupo',id=crypto.randomUUID()) {
  const selected=config.nodes.filter(n=>ids.includes(n.id));
  if(selected.length<1)return config;
  const memberIds=selected.map(n=>n.id),members=new Set(memberIds);
  const x=Math.max(0,Math.min(...selected.map(n=>Number(n.x)))-32);
  const y=Math.max(0,Math.min(...selected.map(n=>Number(n.y)))-48);
  const bounds={x,y,width:Math.max(...selected.map(n=>Number(n.x)+180))-x+32,height:Math.max(...selected.map(n=>Number(n.y)+210))-y+32};
  const groups=(config.groups||[]).map(g=>({...g,memberIds:g.memberIds.filter(id=>!members.has(id))})).filter(g=>g.memberIds.length);
  return {...config,schema_version:2,groups:[...groups,{id,name,bounds,memberIds}],nodes:config.nodes.map(n=>members.has(n.id)?{...n,groupId:id,pageGroup:name,manuallyEdited:true}:n)};
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
    const x=Math.max(0,Math.min(...members.map(node=>node.x))-32);
    const y=Math.max(0,Math.min(...members.map(node=>node.y))-48);
    return {...group,bounds:{x,y,width:Math.max(...members.map(node=>node.x+(node.width||180)))-x+32,height:Math.max(...members.map(node=>node.y+(node.height||210)))-y+32}};
  })};
}
