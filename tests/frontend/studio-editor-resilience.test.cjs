// Editor (React): rascunho local sem estourar a cota, uma só sessão criada sob rede lenta e consulta da edição que sobrevive a uma falha de rede.
const {chromium}=require('./studio-browser.cjs');
const fs=require('fs'),assert=require('node:assert/strict');
const TOKEN='studio-token';
const bootstrap={apiRoot:'/studio/api',csrf:TOKEN,clientId:'174',projectId:'p1',credits:640,usagePercent:36,
  user:{name:'Ana Planejadora',email:'ana@agencia.test'},links:{home:'/studio',create:'/studio/criar',editor:'/studio/editar',videos:'/studio/video',audio:'/studio/audio',library:'/studio#lib'}};
const html=`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/cadu_studio/editor/react/app.css"></head><body><div id="cadu-studio-editor-root"></div><script id="cadu-studio-editor-bootstrap" type="application/json">${JSON.stringify(bootstrap)}</script><script type="module" src="/static/cadu_studio/editor/react/app.js"></script></body></html>`;
const STILL='/static/images/cadu/brand-icons/studio-192.png';
const PICK='input[type=file][accept="image/png,image/jpeg,image/webp"]:not([multiple])';

async function open(browser,{uploadFails=false,slowCreate=0,taskFailsOnce=false}={}){
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],calls=[];
  let taskPolls=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    const original=Storage.prototype.setItem;
    // Simula a cota cheia: qualquer rascunho que carregue uma imagem em data URL é recusado.
    Storage.prototype.setItem=function(key,value){ if(String(key).startsWith('cadu-studio-editor')&&String(value).includes('data:image')) throw new DOMException('quota','QuotaExceededError'); return original.call(this,key,value); };
  });
  await page.route('http://studio.test/**',async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
    if(path==='/')return route.fulfill({contentType:'text/html',body:html});
    if(path.startsWith('/static/'))return fs.existsSync('aicentralv2'+path)?route.fulfill({path:'aicentralv2'+path}):route.fulfill({status:404,body:''});
    if(method!=='GET')calls.push({method,path,body:req.postData()});
    const ok=data=>route.fulfill({json:{success:true,data}});
    if(path.endsWith('/project-contexts'))return ok({items:[{id:'p1',name:'Lançamento Verão',client_id:174,brand_name:'Centralcomm'}]});
    if(path.endsWith('/reference-uploads'))return uploadFails?route.fulfill({status:500,json:{success:false,error:'indisponível'}}):ok({items:[{id:'r1',asset_id:'a1',url:STILL}]});
    if(path.endsWith('/studio/edit-quote'))return ok({estimated_tokens:1200});
    if(path.endsWith('/studio/tasks')&&method==='POST')return ok({id:'task-1',status:'queued'});
    if(path.endsWith('/studio/tasks/task-1')){taskPolls+=1;if(taskFailsOnce&&taskPolls===1)return route.fulfill({status:502,body:'bad gateway'});return ok({id:'task-1',status:'ready',result:{image_url:STILL}});}
    if(path.endsWith('/attach-project'))return ok({id:'s1',revision:1,project_id:'p1',title:'Mesa',status:'active',assets:[]});
    if(/\/sessions(\/[^/]+)?$/.test(path)&&method!=='GET'){if(slowCreate&&method==='POST')await new Promise(resolve=>setTimeout(resolve,slowCreate));return ok({id:'s1',revision:1,title:'Mesa',status:'active',assets:[]});}
    return ok({items:[]});
  });
  await page.goto('http://studio.test/');
  await page.getByRole('navigation',{name:'Ferramentas do Studio'}).waitFor();
  return {page,errors,calls};
}

(async()=>{
  const browser=await chromium.launch({headless:true});

  // 1. Cota do localStorage cheia: nenhum erro solto e o rascunho leve (sem a imagem) é guardado.
  {
    const {page,errors}=await open(browser,{uploadFails:true});
    await page.locator(PICK).setInputFiles('aicentralv2'+STILL);
    await page.locator('.se-artboard img').waitFor();
    await page.getByPlaceholder('Diga ao Cadu o que fazer nesta peça…').fill('Troque o fundo por um céu de fim de tarde.');
    await page.waitForTimeout(1200);
    const saved=await page.evaluate(()=>{const key=Object.keys(localStorage).find(item=>item.startsWith('cadu-studio-editor'));return key?localStorage.getItem(key):null;});
    assert.ok(saved,'o rascunho foi guardado mesmo sem espaço para a imagem');
    assert.ok(!saved.includes('data:image'),'o rascunho leve não carrega imagens em data URL');
    assert.match(saved,/céu de fim de tarde/,'o texto digitado continua no rascunho');
    assert.deepEqual(errors,[],'cota cheia não gera erro não tratado');
    await page.close();
  }

  // 2. Rede lenta ao criar a sessão: edições feitas durante a criação atualizam a mesma sessão.
  {
    const {page,calls,errors}=await open(browser,{slowCreate:1800});
    await page.locator(PICK).setInputFiles('aicentralv2'+STILL);
    await page.locator('.se-artboard img').waitFor();
    await page.waitForTimeout(1100);
    await page.getByPlaceholder('Diga ao Cadu o que fazer nesta peça…').fill('Aumente o contraste do título.');
    await page.waitForTimeout(4500);
    const created=calls.filter(c=>c.method==='POST'&&/\/sessions$/.test(c.path)).length;
    assert.equal(created,1,'apenas uma sessão é criada, as mudanças seguintes atualizam a mesma');
    assert.ok(calls.some(c=>c.method==='PATCH'&&/\/sessions\/s1$/.test(c.path)),'a mudança durante a criação foi gravada na sessão existente');
    assert.deepEqual(errors,[]);
    await page.close();
  }

  // 3. Uma consulta da edição que falha uma vez não perde a edição.
  {
    const {page,errors}=await open(browser,{taskFailsOnce:true});
    await page.locator(PICK).setInputFiles('aicentralv2'+STILL);
    await page.locator('.se-artboard img').waitFor();
    await page.getByPlaceholder('Diga ao Cadu o que fazer nesta peça…').fill('Troque o fundo por um céu de fim de tarde, mantendo o logo.');
    await page.getByRole('button',{name:/Gerar edição/}).click();
    await page.locator('.se-chat-last',{hasText:'Criei uma nova versão'}).waitFor({timeout:15000});
    assert.deepEqual(errors,[]);
    await page.close();
  }
  console.log('PASS Editor resiliente: rascunho leve sem cota, uma única sessão sob rede lenta, edição sobrevive a uma falha de consulta');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
