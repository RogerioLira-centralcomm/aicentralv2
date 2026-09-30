export function applyBlueprint(current,proposal,accepted){
 const allowed=new Set(accepted),protectedIds=new Set(current.nodes.filter(n=>n.origin!=='blueprint'||n.manuallyEdited||n.locked).map(n=>n.id));
 // Manual connections protect their endpoints during a rebuild.
 current.edges.filter(e=>e.origin!=='blueprint').forEach(e=>{protectedIds.add(e.from);protectedIds.add(e.to);});
 const retained=current.nodes.filter(n=>protectedIds.has(n.id));
 const identity=n=>`${(n.host||'').replace(/^www\./,'')}:${n.type}:${n.path||''}:${n.event_name||''}:${n.type==='source'?n.source||n.kind||'':''}`;
 const known=new Map(retained.map(n=>[identity(n),n.id])),remap=new Map();
 const added=[];
 for(const node of proposal.nodes.filter(n=>allowed.has(n.id))){const existing=known.get(identity(node));if(existing)remap.set(node.id,existing);else{added.push(node);known.set(identity(node),node.id);}}
 const nodes=[...retained,...added],ids=new Set(nodes.map(n=>n.id));
 const edges=current.edges.filter(e=>ids.has(e.from)&&ids.has(e.to)&&e.origin!=='blueprint');
 for(const e of proposal.edges){if(!allowed.has(e.from)||!allowed.has(e.to))continue;const edge={...e,from:remap.get(e.from)||e.from,to:remap.get(e.to)||e.to};if(edge.from!==edge.to&&!edges.some(old=>old.from===edge.from&&old.to===edge.to))edges.push(edge);}
 if(nodes.length>200||edges.length>300)throw new Error('A proposta excede os limites do fluxo. Selecione menos etapas.');
 const groups=(current.groups||[]).map(g=>({...g,memberIds:g.memberIds.filter(id=>ids.has(id))})).filter(g=>g.memberIds.length);
 const grouped=new Set(groups.flatMap(g=>g.memberIds));
 for(const g of proposal.groups||[]){const memberIds=g.memberIds.filter(id=>allowed.has(id)).map(id=>remap.get(id)||id).filter(id=>ids.has(id)&&!grouped.has(id));if(memberIds.length){groups.push({...g,memberIds});memberIds.forEach(id=>grouped.add(id));}}
 return {...current,blueprintGoalConfirmed:true,nodes,edges,groups};
}

export function previewBlueprint(proposal,accepted){
 const allowed=new Set(accepted),mapping=new Map(),nodes=[];
 for(const group of proposal.groups||[]){const members=group.memberIds.filter(id=>allowed.has(id));if(!members.length)continue;members.forEach(id=>mapping.set(id,group.id));const first=proposal.nodes.find(n=>n.id===members[0]);nodes.push({...first,id:group.id,title:`${group.name} · ${members.length} páginas`,x:group.bounds.x,y:group.bounds.y});}
 nodes.push(...proposal.nodes.filter(n=>allowed.has(n.id)&&!mapping.has(n.id)));
 const pairs=new Set();const edges=proposal.edges.filter(e=>allowed.has(e.from)&&allowed.has(e.to)).map(e=>({...e,from:mapping.get(e.from)||e.from,to:mapping.get(e.to)||e.to})).filter(e=>{const key=e.from+':'+e.to;if(e.from===e.to||pairs.has(key))return false;pairs.add(key);return true;});
 return {nodes,edges};
}
