export async function layoutFlow(config) {
  const {default: ELK} = await import('elkjs/lib/elk.bundled.js');
  const elk = new ELK();
  const graph = await elk.layout({
    id:'flow',
    layoutOptions:{'elk.algorithm':'layered','elk.direction':'RIGHT','elk.spacing.nodeNode':'52','elk.layered.spacing.nodeNodeBetweenLayers':'100'},
    children:(config.nodes||[]).map(node=>({id:node.id,width:160,height:160})),
    edges:(config.edges||[]).map(edge=>({id:edge.id,sources:[edge.from],targets:[edge.to]})),
  });
  const positions=new Map((graph.children||[]).map(node=>[node.id,{x:Math.round((node.x||0)+80),y:Math.round((node.y||0)+80)}]));
  return (config.nodes||[]).map(node=>({...node,...positions.get(node.id)}));
}
