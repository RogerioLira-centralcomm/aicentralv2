const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const {chromium}=require('playwright');

const root=path.resolve(__dirname,'../..');
const id='11111111-1111-4111-8111-111111111111';
const config={nodes:[{id:'source',type:'source',title:'Canal',x:40,y:100},{id:'page',type:'page',title:'Entrada',path:'/',x:300,y:100},{id:'goal',type:'conversion',title:'Conclusão',path:'/obrigado',x:560,y:100}],edges:[{id:'sp',from:'source',to:'page'},{id:'pg',from:'page',to:'goal'}]};
let flow={id,name:'Jornada de teste',status:'draft',published_revision:null,draft_revision:1,allowed_host:'example.test',config};
let failNextSave=false;
const html='<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/cadu_connect/react/app.css"><link rel="stylesheet" href="/static/cadu_connect/react/untitled.css"></head><body><div id="cadu-reports-v1-root"></div><script type="module" src="/static/cadu_connect/react/app.js"></script></body></html>';
const server=http.createServer((req,res)=>{const pathname=new URL(req.url,'http://localhost').pathname;if(pathname.startsWith('/static/')){const file=path.join(root,'aicentralv2',pathname);if(fs.existsSync(file)){res.setHeader('Content-Type',file.endsWith('.css')?'text/css':'text/javascript');return res.end(fs.readFileSync(file));}res.statusCode=404;return res.end();}res.setHeader('Content-Type','text/html');res.end(html);});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/connect/api/v2/reports/**',route=>{
      const pathname=new URL(route.request().url()).pathname;let data={};
      if(pathname.endsWith('/bootstrap'))data={ready:true,features:{flows_workspace_v2:true},client:{client_id:1,role:'admin',client_name:'Teste'},clients:[],accounts:[],campaigns:[],reports:[],link_tests:[],workspace_projects:[],csrf:'test'};
      else if(pathname.endsWith('/flow'))data={flows:[flow],activity:[],events:[],tags:[],steps:[],tag_urls:{},supertag_sites:[],canvas_nodes:config.nodes,canvas_edges:config.edges};
      else if(pathname.endsWith('/readiness'))data={tracking_ready:true,issues:[]};
      else if(pathname.endsWith('/discoveries'))data={run:null,pages:[]};
      else if(pathname.endsWith('/publish')){flow={...flow,status:'published',published_revision:2};data={flow};}
      else if(pathname.endsWith(`/flows/${id}`)&&route.request().method()==='PATCH'){
        if(failNextSave){failNextSave=false;return route.fulfill({status:503,json:{error:'Conexão interrompida'}});}
        const payload=route.request().postDataJSON();flow={...flow,name:payload.name,config:payload.config,draft_revision:flow.draft_revision+1};data={flow};
      }
      return route.fulfill({json:data});
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/connect/app/flows/${id}?client_id=1`);
    await page.locator('.react-flow__node').first().waitFor();
    const positions=()=>page.evaluate(()=>({header:document.querySelector('.reports-flow-editor-topbar').getBoundingClientRect().top,canvas:document.querySelector('.reports-flow-canvas').getBoundingClientRect().top}));
    const before=await positions();
    await page.getByRole('button',{name:'Publicar',exact:true}).click();
    await page.getByRole('button',{name:'Publicar versão',exact:true}).click();
    await page.waitForTimeout(1000);
    await page.locator('.flow-toast-root').waitFor({timeout:5000});
    assert.match(await page.locator('.flow-toast-root').innerText(),/Versão 2 publicada/);
    const after=await positions();
    assert.deepEqual(after,before);
    assert.equal(await page.locator('.flow-toast-root').evaluate(element=>getComputedStyle(element).position),'fixed');
    flow={...flow,status:'draft',published_revision:null,draft_revision:1,config:{nodes:[{id:'page',type:'page',title:'Entrada',path:'/',x:300,y:100}],edges:[]}};
    await page.reload();
    await page.locator('.react-flow__node').first().waitFor();
    assert.equal(await page.getByRole('button',{name:'Publicar',exact:true}).isDisabled(),true);
    await page.getByRole('button',{name:/Resolva 1 pendência bloqueante para publicar/}).click();
    const pending=page.getByRole('region',{name:'Pendências do fluxo'});
    assert(await pending.isVisible());
    assert.match(await pending.innerText(),/Sem conversão definida, não será possível medir/);
    await pending.getByRole('button',{name:'Adicionar nó de Conversão'}).click();
    assert.equal(await page.locator('.react-flow__node').count(),2);
    flow={...flow,config:{nodes:[],edges:[]}};
    await page.reload();
    await page.locator('.reports-flow-empty-guide').waitFor();
    assert.match(await page.locator('.reports-flow-empty-guide').innerText(),/Comece sua jornada/);
    failNextSave=true;
    await page.getByRole('textbox',{name:'Nome do fluxo'}).fill('Jornada revisada');
    await page.getByText('Falha ao salvar').waitFor({timeout:10000});
    assert.equal(await page.getByRole('textbox',{name:'Nome do fluxo'}).inputValue(),'Jornada revisada');
    await page.locator('.reports-flow-save-state summary').click();
    await page.getByRole('button',{name:'Tentar salvar novamente'}).click();
    await page.getByText(/Salvo/).first().waitFor({timeout:10000});
    assert.equal(flow.name,'Jornada revisada');
    assert.deepEqual(errors,[]);
    console.log('M1 navegador: publicação, toast fixo, bloqueio, início guiado e recuperação aprovados');
  }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
