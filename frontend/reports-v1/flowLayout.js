export async function layoutFlow(config, {width=160,height=160,nodeSpacing=52,layerSpacing=100} = {}) {
  const {default: ELK} = await import('elkjs/lib/elk.bundled.js');
  const elk = new ELK();
  const graph = await elk.layout({
    id:'flow',
    layoutOptions:{'elk.algorithm':'layered','elk.direction':'RIGHT','elk.spacing.nodeNode':String(nodeSpacing),'elk.layered.spacing.nodeNodeBetweenLayers':String(layerSpacing)},
    children:(config.nodes||[]).map(node=>({id:node.id,width,height})),
    edges:(config.edges||[]).map(edge=>({id:edge.id,sources:[edge.from],targets:[edge.to]})),
  });
  const positions=new Map((graph.children||[]).map(node=>[node.id,{x:Math.round((node.x||0)+80),y:Math.round((node.y||0)+80)}]));
  return (config.nodes||[]).map(node=>({...node,...positions.get(node.id)}));
}
