const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const load=async name=>import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(path.join(root,'frontend/reports-v1',name),'utf8')).toString('base64'));
(async()=>{
  const {edgeMetricLabel}=await load('flowMetricLabels.js');
  assert.equal(edgeMetricLabel({observation:{status:'no_data',sessions:null}}),'Sem dados no período');
  assert.equal(edgeMetricLabel({observation:{status:'measured',sessions:0,rate:0}}),'0 · 0%');
  assert.equal(edgeMetricLabel({observation:{status:'unmeasured',sessions:null}}),'Conexão sem medição');
  const {funnelEdges,isReturnEdge}=await load('flowStages.js');
  const nodes=[{id:'a',stage:'entry'},{id:'b',stage:'intent'}],edges=[];
  for(let index=0;index<25;index++)edges.push({id:String(index),from:'a',to:'b',kind:index?'manual':'site_link'});
  edges.push({id:'back',from:'b',to:'a'});
  const config={nodes,edges};
  assert.equal(funnelEdges(config).length,25);
  assert.equal(funnelEdges(config,{returns:true}).length,26);
  assert.equal(isReturnEdge(edges.at(-1),new Map(nodes.map(node=>[node.id,node]))),true);
  console.log('M4: conexões planejadas, retornos e estados de métrica aprovados');
})().catch(error=>{console.error(error);process.exitCode=1;});
