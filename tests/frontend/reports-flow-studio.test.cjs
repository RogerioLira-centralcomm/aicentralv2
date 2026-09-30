const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const moduleAt=async name=>import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(path.join(root,'frontend/reports-v1',name),'utf8')).toString('base64'));
(async()=>{
 const {applyBlueprint}=await moduleAt('flowBlueprintApply.js');
 const nodes=[{id:'manual',origin:'manual',path:'/a'},{id:'edited',origin:'blueprint',manuallyEdited:true,path:'/b'},{id:'locked',origin:'blueprint',locked:true,path:'/c'},{id:'old',origin:'blueprint',path:'/old'},{id:'endpoint',origin:'blueprint',path:'/d'}];
 const current={nodes,edges:[{id:'e',from:'manual',to:'endpoint'}],groups:[]};
 const next=applyBlueprint(current,{nodes:[{id:'new',origin:'blueprint',path:'/new'}],edges:[]},['new']);
 assert.deepEqual(next.nodes.map(n=>n.id),['manual','edited','locked','endpoint','new']);assert.deepEqual(next.edges,current.edges);assert.equal(current.nodes.length,5);
 const canvas=fs.readFileSync(path.join(root,'frontend/reports-v1/FlowCanvas.jsx'),'utf8');
 assert(canvas.includes("origin:'manual',from:connection.source,to:connection.target"));
 const editedGraph={nodes:[{id:'a',origin:'blueprint'},{id:'b',origin:'blueprint'}],edges:[{id:'ab',origin:'manual',from:'a',to:'b'}],groups:[]};
 const rebuilt=applyBlueprint(editedGraph,{nodes:[],edges:[],groups:[]},[]);
 assert.deepEqual(rebuilt.nodes,editedGraph.nodes);assert.deepEqual(rebuilt.edges,editedGraph.edges);
 const {FLOW_STAGES}=await moduleAt('flowStages.js');
 const stageExpressions=[...canvas.matchAll(/stage:(FLOW_STAGES\[Math\.max.*?\]\.id)/g)];
 assert.equal(stageExpressions.length,2);
 for(const [,expression] of stageExpressions){const stageAt=new Function('FLOW_STAGES','x',`return ${expression}`);FLOW_STAGES.forEach((stage,index)=>assert.equal(stageAt(FLOW_STAGES,48+index*320+100),stage.id));}
 const {funnelEdges}=await moduleAt('flowStages.js');
 const graph={nodes:[{id:'a',stage:'entry'},{id:'b',stage:'intent'},{id:'c',stage:'conversion'}],edges:[{id:'ab',from:'a',to:'b'},{id:'ba',from:'b',to:'a'},{id:'bc',from:'b',to:'c',kind:'site_link'}]};
 assert.deepEqual(funnelEdges(graph).map(e=>e.id),['ab']);assert.equal(funnelEdges(graph,{full:true}).length,3);assert.equal(graph.edges.length,3);
 for(const name of ['FlowCanvas.jsx','FlowInspector.jsx','FlowBlueprint.jsx','FlowCatalog.jsx','FlowStudioAssist.jsx'])assert(!/\bborder-2\b/.test(fs.readFileSync(path.join(root,'frontend/reports-v1',name),'utf8')),name);
 console.log('Studio: rebuild preservation, edge policy, immutable view and border guard passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
