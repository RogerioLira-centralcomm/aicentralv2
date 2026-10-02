// Editor (React): enviar peça → pedir edição → nova versão, sempre com o token do Studio.
const {chromium,ARTIFACTS}=require('./studio-browser.cjs');
const fs=require('fs'),assert=require('node:assert/strict');
const TOKEN='studio-token';
const bootstrap={apiRoot:'/studio/api',csrf:TOKEN,clientId:'174',projectId:'p1',credits:640,usagePercent:36,
  user:{name:'Ana Planejadora',email:'ana@agencia.test'},links:{home:'/studio',create:'/studio/criar',editor:'/studio/editar',videos:'/studio/video',audio:'/studio/audio',library:'/studio#lib'}};
const html=`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/cadu_studio/editor/react/app.css"></head><body><div id="cadu-studio-editor-root"></div><script id="cadu-studio-editor-bootstrap" type="application/json">${JSON.stringify(bootstrap)}</script><script type="module" src="/static/cadu_studio/editor/react/app.js"></script></body></html>`;
const STILL='/static/images/cadu/brand-icons/studio-192.png';
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],rejected=[],calls=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://studio.test/**',async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
    if(path==='/')return route.fulfill({contentType:'text/html',body:html});
    if(path.startsWith('/static/'))return fs.existsSync('aicentralv2'+path)?route.fulfill({path:'aicentralv2'+path}):route.fulfill({status:404,body:''});
    if(method!=='GET'){
      calls.push({method,path,body:req.postData()});
      if(req.headers()['x-trocr-csrf-token']!==TOKEN){rejected.push(path);return route.fulfill({status:403,json:{success:false,error:'Token de segurança inválido.'}});}
    }
    const ok=data=>route.fulfill({json:{success:true,data}});
    if(path.endsWith('/project-contexts'))return ok({items:[{id:'p1',name:'Lançamento Verão',client_id:174,brand_name:'Centralcomm'}]});
    if(path.endsWith('/reference-uploads'))return ok({items:[{id:'r1',asset_id:'a1',url:STILL}]});
    if(path.endsWith('/studio/edit-quote'))return ok({estimated_tokens:1200,estimate_label:'~1,2 mil tokens'});
    if(path.endsWith('/studio/tasks')&&method==='POST')return ok({id:'task-1',status:'queued'});
    if(path.endsWith('/studio/tasks/task-1'))return ok({id:'task-1',status:'ready',result:{image_url:STILL}});
    if(/\/sessions(\/[^/]+)?$/.test(path)&&method!=='GET')return ok({id:'s1',revision:1,title:'Mesa',status:'active',assets:[]});
    return ok({items:[]});
  });
  await page.goto('http://studio.test/');
  await page.getByRole('navigation',{name:'Ferramentas do Studio'}).waitFor();
  await page.locator('input[type=file][accept="image/png,image/jpeg,image/webp"]:not([multiple])').setInputFiles('aicentralv2'+STILL);
  await page.locator('.se-artboard img').waitFor();
  // Marcar a região e ir direto para o texto conclui a máscara sem o botão "Concluir máscara".
  await page.getByRole('button',{name:'Marcar região'}).click();
  const box=await page.locator('.se-mask-canvas').boundingBox();
  await page.mouse.move(box.x+box.width*.3,box.y+box.height*.3);await page.mouse.down();await page.mouse.move(box.x+box.width*.6,box.y+box.height*.35,{steps:6});await page.mouse.up();
  await page.getByPlaceholder('Diga ao Cadu o que fazer nesta peça…').click();
  await page.getByText('Região marcada',{exact:true}).first().waitFor();
  assert.equal(await page.locator('.se-mask-tools').count(),0,'ao focar o texto a máscara é concluída e a barra do pincel fecha');
  await page.getByPlaceholder('Diga ao Cadu o que fazer nesta peça…').fill('Troque o fundo por um céu de fim de tarde, mantendo o logo.');
  await page.getByRole('button',{name:/Gerar edição/}).click();
  await page.locator('.se-chat-last',{hasText:'Criei uma nova versão'}).waitFor();
  assert.equal(await page.locator('.se-notice').count(),0,'resultado já aparece no palco e na conversa: sem aviso extra');
  const task=calls.find(c=>c.path.endsWith('/studio/tasks'));
  assert.ok(task,'a edição foi enviada como tarefa do Studio');
  const body=JSON.parse(task.body);
  assert.equal(body.kind,'image_edit');
  assert.equal(body.payload.selection_context?.role,'marked_region','a região marcada vai com a edição');
  assert.equal(String(body.client_id),'174');
  assert.match(body.payload.note,/céu de fim de tarde/);
  assert.match(body.payload.reference,/studio-192\.png$/);
  assert.deepEqual(rejected,[],'nenhuma chamada recusada por token de segurança');
  await page.screenshot({path:ARTIFACTS+'/editor-flow.png'});
  // Remover fundo pede recorte de verdade ao servidor (fundo chapado + alpha), não um xadrez desenhado.
  const before=calls.filter(c=>c.path.endsWith('/studio/tasks')).length;
  await page.getByRole('button',{name:'Remover fundo'}).click();
  await page.locator('.se-vrow__copy b',{hasText:'sem fundo'}).first().waitFor({timeout:15000});
  const removal=JSON.parse(calls.filter(c=>c.path.endsWith('/studio/tasks'))[before].body).payload;
  assert.equal(removal.background_removal,true);
  assert.deepEqual(errors,[]);
  console.log('PASS Editor: upload salvo na biblioteca, edição enviada como tarefa com marca e referência, nova versão no palco, token do Studio aceito em todas as chamadas');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
