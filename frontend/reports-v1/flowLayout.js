export async function layoutFlow(config, {width=160,height=160,nodeSpacing=64,layerSpacing=112} = {}) {
  const {default: ELK} = await import('elkjs/lib/elk.bundled.js');
  const elk = new ELK();
  const graph = await elk.layout({
    id:'flow',
    layoutOptions:{'elk.algorithm':'layered','elk.direction':'RIGHT','elk.spacing.nodeNode':String(nodeSpacing),'elk.layered.spacing.nodeNodeBetweenLayers':String(layerSpacing)},
    children:(config.nodes||[]).map(node=>({id:node.id,width:node.width||width,height:node.height||height})),
    edges:(config.edges||[]).map(edge=>({id:edge.id,sources:[edge.from],targets:[edge.to]})),
  });
  if((graph.children||[]).some(node=>(node.x||0)+80>10000||(node.y||0)+80>10000))throw new Error('O fluxo excede a área disponível. Organize grupos menores.');
  const positions=new Map((graph.children||[]).map(node=>[node.id,{x:Math.round((node.x||0)+80),y:Math.round((node.y||0)+80)}]));
  return (config.nodes||[]).map(node=>({...node,...positions.get(node.id)}));
}
