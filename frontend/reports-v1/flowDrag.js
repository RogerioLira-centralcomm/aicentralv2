// Kept free of imports: tests load this file on its own. FLOW_GRID lives in flowStages.js.
const GRID=20;
/** The board is effectively infinite; this bound only keeps documents sane (mirrors reports_flow.FLOW_COORD_LIMIT). */
export const FLOW_COORD_LIMIT=20000;
const clampCoord=value=>Math.max(-FLOW_COORD_LIMIT,Math.min(FLOW_COORD_LIMIT,Math.round(value)));

/**
 * Applies a finished drag to the document. Moving is purely spatial: stage, role, ports and connections never
 * change because of where a card lands. The selection moves as one block, so one grid snap applies to every
 * dragged item and relative spacing never changes. `raw` maps ids to React Flow positions (parent-relative for
 * members of a frame).
 */
export function applyDrag(current,raw,{grid=GRID,snap=true}={}){
  if(!raw?.size)return current;
  const groupsById=new Map((current.groups||[]).map(g=>[g.id,g]));
  const nodesById=new Map(current.nodes.map(n=>[n.id,n]));
  const absolute=[...raw].map(([id,pos])=>{const parent=groupsById.has(id)?null:groupsById.get(nodesById.get(id)?.groupId);const inherited=parent&&!raw.has(parent.id);return {x:pos.x+(inherited?parent.bounds.x:0),y:pos.y+(inherited?parent.bounds.y:0)};});
  const first=absolute[0];
  const align=value=>snap?Math.round(value/grid)*grid:value;
  let dx=align(first.x)-first.x,dy=align(first.y)-first.y;
  const shift=(min,max)=>min<-FLOW_COORD_LIMIT?Math.ceil((-FLOW_COORD_LIMIT-min)/grid)*grid:max>FLOW_COORD_LIMIT?-Math.ceil((max-FLOW_COORD_LIMIT)/grid)*grid:0;
  dx+=shift(Math.min(...absolute.map(p=>p.x))+dx,Math.max(...absolute.map(p=>p.x))+dx);
  dy+=shift(Math.min(...absolute.map(p=>p.y))+dy,Math.max(...absolute.map(p=>p.y))+dy);
  const moved=new Map([...raw].map(([id,pos])=>[id,{x:pos.x+dx,y:pos.y+dy}]));
  const groups=(current.groups||[]).map(g=>moved.has(g.id)?{...g,bounds:{...g.bounds,x:clampCoord(moved.get(g.id).x),y:clampCoord(moved.get(g.id).y)}}:g);
  const nextGroups=new Map(groups.map(g=>[g.id,g]));
  return {...current,groups:current.groups?groups:current.groups,nodes:current.nodes.map(node=>{
    const oldParent=groupsById.get(node.groupId),parent=nextGroups.get(node.groupId),move=moved.get(node.id);
    const groupMoved=Boolean(parent&&moved.has(parent.id));
    if(!move&&!groupMoved)return node;
    const x=move?move.x+(parent?.bounds.x||0):Number(node.x)+(parent.bounds.x-oldParent.bounds.x);
    const y=move?move.y+(parent?.bounds.y||0):Number(node.y)+(parent.bounds.y-oldParent.bounds.y);
    return {...node,manuallyEdited:true,x:clampCoord(x),y:clampCoord(y)};
  })};
}

/** Where a new card can sit near (x, y) without covering another one: scans down, then to the right. */
export function findFreeSlot(nodes,{x,y},{width=260,height=200,gap=24,grid=GRID}={}){
  const align=value=>Math.round(value/grid)*grid;
  const boxes=(nodes||[]).filter(n=>!n.groupId).map(n=>({x:Number(n.x)||0,y:Number(n.y)||0,w:Number(n.width)||width,h:Number(n.height)||height}));
  const free=(px,py)=>!boxes.some(b=>px<b.x+b.w+gap&&px+width+gap>b.x&&py<b.y+b.h+gap&&py+height+gap>b.y);
  const startX=align(x),startY=align(y);
  for(let column=0;column<6;column++)for(let row=0;row<12;row++){
    const px=startX+column*(width+gap*2),py=startY+row*align(height/2);
    if(free(px,py))return {x:clampCoord(px),y:clampCoord(py)};
  }
  return {x:clampCoord(startX),y:clampCoord(startY)};
}

/** Picks connection sides from where the cards actually are, unless the person chose a port explicitly. */
export function edgePorts(edge,source,target,{returning=false,width=248,height=184}={}){
  const custom=(edge.from_port&&edge.from_port!=='right-out')||(edge.to_port&&edge.to_port!=='left-in');
  if(custom)return {sourceHandle:edge.from_port||'right-out',targetHandle:edge.to_port||'left-in'};
  if(!source||!target)return {sourceHandle:'right-out',targetHandle:'left-in'};
  const sx=Number(source.x)||0,sy=Number(source.y)||0,tx=Number(target.x)||0,ty=Number(target.y)||0;
  const sw=Number(source.width)||width,sh=Number(source.height)||height;
  if(tx>=sx+sw*.6)return {sourceHandle:'right-out',targetHandle:'left-in'};
  if(ty>=sy+sh*.9&&Math.abs(tx-sx)<sw*1.2)return {sourceHandle:'bottom-out',targetHandle:'top-in'};
  // Going back loops under both cards, so it never shares the corridor of the forward connection.
  if(returning||tx<sx)return {sourceHandle:'bottom-out',targetHandle:'bottom-in'};
  return {sourceHandle:'right-out',targetHandle:'left-in'};
}
