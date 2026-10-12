// Infinite board: dragging is spatial only, "+" continues the path with a page found on the site, strokes have a legend
// and the monitor keeps a personal arrangement. Runs against the built bundle with mocked APIs (no database).
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const http=require('node:http');const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'),id='22222222-2222-4222-8222-222222222222',out=path.join(root,'output/reports-workspace-qa');
const n=(nodeId,type,title,x,y,extra={})=>({id:nodeId,type,title,x,y,...extra});
const config={nodes:[
  n('meta','source','Meta Ads',80,100,{kind:'traffic.meta',source:'meta',stage:'source'}),
  n('google','source','Google Ads',80,340,{kind:'traffic.google',source:'google',stage:'source'}),
  n('home','page','Página inicial',420,220,{path:'/',stage:'entry',pageType:'home'}),
  n('servicos','page','Serviços',760,100,{path:'/servicos',stage:'exploration',pageType:'service'}),
  n('blog','page','Blog',760,400,{path:'/blog',stage:'exploration',pageType:'content'}),
  n('contato','form','Contato',1100,220,{path:'/contato',stage:'intent',pageType:'contact'}),
  n('obrigado','conversion','Lead enviado',1440,220,{path:'/obrigado',stage:'conversion',pageType:'other'}),
],edges:[
  {id:'mh',from:'meta',to:'home',variant:'planned'},{id:'gh',from:'google',to:'home',variant:'planned'},
  {id:'hs',from:'home',to:'servicos'},{id:'hb',from:'home',to:'blog'},
  {id:'sc',from:'servicos',to:'contato'},{id:'co',from:'contato',to:'obrigado'},
  {id:'back',from:'contato',to:'servicos',origin:'manual'},
]};
const flow={id,name:'Jornada completa',status:'published',published_revision:1,draft_revision:1,allowed_host:'example.test',config:JSON.parse(JSON.stringify(config)),active_config:config};
const metric=(edgeId,from,to,sessions,base)=>({id:edgeId,from,to,sessions,rate:Math.round(sessions/base*100),observation:{status:'measured',sessions,rate:Math.round(sessions/base*100),denominator:base}});
const journey={status:'ready',revision:1,config,timezone:'America/Sao_Paulo',scope:{from:'2026-09-01T00:00:00-03:00',to:'2026-10-01T00:00:00-03:00'},collection:{status:'observed',source:'Super Tag deste fluxo',event_count:900,last_event_at:'2026-09-30T14:00:00-03:00'},
  nodes:[{id:'meta',sessions:600},{id:'google',sessions:300},{id:'home',sessions:900},{id:'servicos',sessions:420},{id:'blog',sessions:90},{id:'contato',sessions:140},{id:'obrigado',sessions:62}],
  edges:[metric('mh','meta','home',600,600),metric('gh','google','home',300,300),metric('hs','home','servicos',420,900),metric('hb','home','blog',90,900),metric('sc','servicos','contato',110,420),metric('co','contato','obrigado',62,140)],
  funnel:{entries:900,conversions:62,rate:6.9}};
const row=(nodeId,title,type,pathName,extra)=>({node_id:nodeId,title,type,path:pathName,host:'example.test',status:'measured',...extra});
const pagesData={status:'ready',window:{days:30},site_id:'33333333-3333-4333-8333-333333333333',host:'example.test',min_sessions:20,weights:{time:25,scroll:25,advance:30,exit:20},
  pages:[row('home','Página inicial','page','/',{sessions:900,views:1100,median_active_seconds:38,scroll_50:62,scroll_75:40,advance_rate:56,next_steps:['Serviços','Blog'],exit_rate:35,score:78,grade:'good',components:{time:84,scroll:53,advance:100,exit:65}}),
    row('servicos','Serviços','page','/servicos',{sessions:420,views:480,median_active_seconds:21,scroll_50:41,scroll_75:18,advance_rate:26,next_steps:['Contato'],exit_rate:64,score:45,grade:'attention',components:{time:47,scroll:32,advance:52,exit:36}}),
    row('blog','Blog','page','/blog',{status:'idle',sessions:0,score:null}),
    row('contato','Contato','form','/contato',{sessions:140,views:150,median_active_seconds:9,scroll_50:20,scroll_75:8,advance_rate:44,next_steps:['Lead enviado'],exit_rate:52,score:31,grade:'critical',components:{time:20,scroll:15,advance:88,exit:48}}),
    row('obrigado','Lead enviado','conversion','/obrigado',{sessions:62,views:62,median_active_seconds:6,score:null,small_sample:false})],
  idle:{flow:[row('blog','Blog','page','/blog',{status:'idle',sessions:0})],site:[{path:'/trabalhe-conosco',name:'Trabalhe Conosco',title:null},{path:'/blog/post-antigo',name:'Blog · Post Antigo',title:'Um post antigo'}],site_total:2,catalog:true}};
const html='<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/cadu_connect/react/app.css"><link rel="stylesheet" href="/static/cadu_connect/react/untitled.css"></head><body><div id="cadu-reports-v1-root"></div><script type="module" src="/static/cadu_connect/react/app.js"></script></body></html>';
const server=http.createServer((req,res)=>{const pathname=new URL(req.url,'http://localhost').pathname;if(pathname.startsWith('/static/')){const file=path.join(root,'aicentralv2',pathname);if(fs.existsSync(file)){res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'image/png');return res.end(fs.readFileSync(file));}res.statusCode=404;return res.end();}res.setHeader('Content-Type','text/html');res.end(html);});
let pagesRequests=0;
const waitFor=async(check,label)=>{for(let i=0;i<100;i++){if(check())return;await new Promise(r=>setTimeout(r,100));}assert.fail(label);};

(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const base=`http://127.0.0.1:${server.address().port}`;
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],nextQueries=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/connect/api/v2/reports/**',route=>{
      const url=new URL(route.request().url()),p=url.pathname,method=route.request().method();let data={};
      if(p.endsWith('/bootstrap'))data={ready:true,features:{flows_workspace_v2:true},client:{client_id:1,role:'admin',client_name:'Teste'},clients:[{id:1,name:'Teste'}],accounts:[],campaigns:[],reports:[],link_tests:[],workspace_projects:[],csrf:'test'};
      else if(p.endsWith('/flow'))data={flows:[flow],activity:[],events:[],tags:[],steps:[],tag_urls:{},supertag_sites:[],canvas_nodes:flow.config.nodes,canvas_edges:flow.config.edges};
      else if(p.endsWith(`/flows/${id}`)&&method==='PATCH'){const payload=route.request().postDataJSON();Object.assign(flow,{config:payload.config,draft_revision:flow.draft_revision+1});data={flow};}
      else if(p.endsWith(`/flows/${id}/pages`)){pagesRequests+=1;data=pagesData;}
      else if(p.endsWith('/site-pages/next')){nextQueries.push(Object.fromEntries(url.searchParams));data={host:'example.test',catalog:true,observed_total:50,pages:[{host:'example.test',path:'/blog/guia-completo',name:'Blog · Guia Completo',title:'Guia completo',reason:'observed',passes:40,confidence:.8}]};}
      else if(p.endsWith('/site-pages'))data={hosts:['example.test'],host:'example.test',pages:[],page_count:0};
      else if(p.endsWith('/versions'))data={versions:[{revision:1,name:'Teste'}]};
      else if(p.endsWith('/readiness'))data={tracking_ready:true,issues:[]};
      else if(p.endsWith('/discoveries'))data={run:{status:'complete'},pages:[]};
      else if(p.endsWith('/journey'))data=journey;
      else if(p.endsWith('/live'))data={status:'ready',revision:1,edge_activity:{hs:new Date().toISOString()},active_sessions:4,node_presence:{servicos:3,contato:1},transitions:{hs:'1'},next_cursor:'1',tracking_health:{status:'healthy'}};
      return route.fulfill({json:data});
    });

    // Editor: the whole journey, numbered, with the legend of the strokes on screen.
    await page.goto(`${base}/connect/app/flows/${id}?client_id=1&modo=editar`);
    await page.locator('.react-flow__node[data-id="obrigado"]').waitFor();
    await page.locator('.react-flow__controls-fitview').click();await page.waitForTimeout(300);
    assert(await page.locator('.react-flow__edge[data-id="back"]').count(),'a return drawn by hand is visible without "Mostrar retornos"');
    assert.match(await page.getByRole('region',{name:'Legenda dos traços'}).innerText(),/Retorno a uma etapa anterior/);
    assert.equal(await page.locator('.react-flow__node[data-id="home"] .fnode__badge b').innerText(),'3');
    await page.screenshot({path:path.join(out,'board-editor-1440.png')});

    // Dragging the goal behind the step that feeds it keeps its stage and its connection.
    const goal=await page.locator('.react-flow__node[data-id="obrigado"] .fnode__head').boundingBox();
    const entry=await page.locator('.react-flow__node[data-id="home"]').boundingBox();
    await page.mouse.move(goal.x+20,goal.y+8);await page.mouse.down();
    await page.mouse.move(goal.x-200,goal.y+120,{steps:8});await page.mouse.move(entry.x-120,entry.y+260,{steps:12});await page.mouse.up();
    // The goal now sits behind the form that leads to it: before, this flipped its stage and hid the connection.
    await waitFor(()=>flow.config.nodes.find(node=>node.id==='obrigado').x<1100,'the drag is saved');
    const dropped=flow.config.nodes.find(node=>node.id==='obrigado');
    assert.equal(dropped.stage,'conversion','dragging never changes the stage');
    assert(await page.locator('.react-flow__edge[data-id="co"]').count(),'the connection survives the drag');
    await page.keyboard.press('Meta+z');
    await waitFor(()=>flow.config.nodes.find(node=>node.id==='obrigado').x===1440,'undo restores the position');

    // "+" after the open end of the path (the flow follows up to 6 pages, this is the 6th): a page step, connected and filled with the page people open next.
    await page.locator('.react-flow__node[data-id="blog"]').hover();
    await page.locator('.react-flow__node[data-id="blog"] .fnode__append').click();
    const quick=page.getByRole('dialog',{name:'Adicionar etapa conectada'});await quick.waitFor();
    await quick.getByRole('button',{name:'Página',exact:true}).click();
    await waitFor(()=>flow.config.nodes.some(node=>node.path==='/blog/guia-completo'),'the suggested page is filled');
    const added=flow.config.nodes.find(node=>node.path==='/blog/guia-completo');
    assert.equal(added.pathSource,'suggested');assert.equal(added.status,undefined);
    assert(flow.config.edges.some(edge=>edge.from==='blog'&&edge.to===added.id),'the new step arrives connected');
    assert.equal(nextQueries.at(-1).after,'/blog');assert.equal(nextQueries.at(-1).type,'page');
    assert(added.x>760&&Math.abs(added.y-400)<400,'it lands beside the card it continues');
    await page.screenshot({path:path.join(out,'board-editor-append-1440.png')});

    // Pages tab: usage score per page for managers, and the pages nobody visits (flow and sitemap).
    assert.equal(pagesRequests,0,'the site scan only runs when the Pages tab is opened');
    await page.getByRole('group',{name:'Modo do fluxo'}).getByRole('button',{name:/^Páginas/}).click();
    const tab=page.getByRole('region',{name:'Páginas do fluxo'});await tab.waitFor();
    const usageRows=tab.getByRole('table',{name:'Uso das páginas do fluxo'}).getByRole('row');
    assert.match(await usageRows.nth(1).innerText(),/Contato[\s\S]*31/,'worst score first');
    await page.screenshot({path:path.join(out,'board-pages-usage-1440.png')});
    await tab.getByRole('tab',{name:/Sem tráfego/}).click();
    assert.match(await tab.getByRole('region',{name:'Páginas do fluxo sem tráfego'}).innerText(),/Blog/);
    assert.match(await tab.getByRole('region',{name:'Páginas do site sem tráfego'}).innerText(),/trabalhe-conosco/);
    await page.screenshot({path:path.join(out,'board-pages-idle-1440.png')});
    await tab.getByRole('region',{name:'Páginas do fluxo sem tráfego'}).getByRole('button',{name:'Ver no mapa'}).click();
    await page.locator('.react-flow__node[data-id="blog"].selected').waitFor();
    assert.match(await page.locator('.react-flow__node[data-id="home"] .fnode__usage').innerText(),/78/,'scores read in the tab stay on the cards');
    assert.equal(pagesRequests,1);

    // Monitor: measured strokes with a scale, cards that can be arranged for this screen only.
    await page.goto(`${base}/connect/app/flows/${id}/monitor?client_id=1`);
    await page.locator('.flow-monitor-workspace .react-flow__node[data-id="servicos"]').waitFor();
    await page.waitForTimeout(600);
    const legend=await page.getByRole('region',{name:'Legenda dos traços'}).innerText();
    assert.match(legend,/Caminho medido/);assert.match(legend,/600 sessões/);assert.doesNotMatch(legend,/Planejada/,'origins with measured traffic read as measured paths');
    await page.screenshot({path:path.join(out,'board-monitor-1440.png')});
    await page.getByRole('region',{name:'Legenda dos traços'}).getByRole('button',{name:/Retorno a uma etapa anterior/}).click();
    assert.equal(await page.locator('.react-flow__edge[data-id="back"] .react-flow__edge-path').evaluate(element=>Number(getComputedStyle(element).opacity)),1);
    assert(await page.locator('.react-flow__edge[data-id="hs"] .react-flow__edge-path').evaluate(element=>Number(getComputedStyle(element).opacity)<.5),'other strokes step back while one kind is highlighted');
    await page.screenshot({path:path.join(out,'board-monitor-focus-1440.png')});
    const card=await page.locator('.flow-monitor-workspace .react-flow__node[data-id="blog"] .fnode__head').boundingBox();
    await page.mouse.move(card.x+20,card.y+6);await page.mouse.down();await page.mouse.move(card.x+60,card.y+180,{steps:10});await page.mouse.up();
    await page.getByRole('button',{name:'Voltar ao arranjo publicado'}).waitFor();
    assert(await page.evaluate(()=>Object.keys(localStorage).some(key=>key.startsWith('reports-flow-arrange:'))),'the arrangement is kept in this browser');
    assert.equal(flow.published_revision,1);
    assert.deepEqual(errors,[]);
    console.log('Mesa infinita: arraste espacial, desfazer, continuação com página do site, legenda com escala e arranjo do monitor aprovados');
  }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
