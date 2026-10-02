// Editor: a edição envia a peça base e no máximo duas referências. Referências globais escolhidas
// antes (guardadas no navegador) aparecem como chips removíveis e nunca passam do limite do gerador
// ("Use no máximo 2 imagens de referência").
const {chromium}=require('./studio-browser.cjs');
const {execFileSync}=require('child_process');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
execFileSync(fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3',['tests/frontend/render-studio-editor-fixture.py'],{stdio:'inherit'});
const HTML=fs.readFileSync('tests/frontend/.fixtures/studio-editor/index.html','utf8').replace(/"clientId":\s*"[^"]*"/,'"clientId":"174"');
const STILL='/static/images/cadu/brand-icons/studio-192.png';
const refs=[0,1,2].map(i=>`http://studio.test/static/images/cadu/brand-icons/studio-192.png?ref=${i}`);
const asset={id:'v1',name:'Peça',url:'http://studio.test'+STILL,dataUrl:'http://studio.test'+STILL,status:'draft'};
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1500,height:950}}),calls=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(([k,v])=>localStorage.setItem(k,v),['cadu-studio-editor-v1:174',JSON.stringify({asset,versions:[asset],selectedId:'v1',prompt:'',format:'4:5',outputSize:{width:1080,height:1350,format:'4:5'},quality:'draft',zoom:100,selectedGlobalReferences:['brand-reference-0','brand-reference-1','brand-reference-2']})]);
  await page.route('https://**',route=>route.fulfill({status:200,contentType:'text/css',body:''}));
  await page.route('http://studio.test/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;
    if(p==='/')return route.fulfill({contentType:'text/html',body:HTML});
    if(p.startsWith('/static/'))return fs.existsSync('aicentralv2'+p)?route.fulfill({path:path.resolve('aicentralv2'+p)}):route.fulfill({status:404,body:''});
    if(req.method()!=='GET')calls.push({p,body:req.postData()});
    const ok=data=>route.fulfill({json:{success:true,data}});
    if(p.endsWith('/project-contexts'))return ok({items:[{id:'p1',name:'Marketing',client_id:174,brand_name:'Centralcomm',brand_context:{name:'Centralcomm',assets:{references:refs,logo:[]},palette:[]}}]});
    if(p.endsWith('/studio/edit-quote'))return ok({estimated_tokens:22000});
    if(p.endsWith('/studio/tasks')&&req.method()==='POST')return ok({id:'t1',status:'queued'});
    if(p.endsWith('/studio/tasks/t1'))return ok({id:'t1',status:'ready',result:{image_url:STILL}});
    if(/\/sessions(\/[^/]+)?$/.test(p)&&req.method()!=='GET')return ok({id:'s1',revision:1,title:'Mesa',status:'active',assets:[]});
    return ok({items:[],runs:[],personal_assets:[],assets:[]});});
  await page.goto('http://studio.test/?project_id=p1');
  await page.locator('.se-composer').waitFor();await page.waitForTimeout(1200);
  const chips=await page.locator('.se-reference-chip.is-global').count();
  assert.ok(chips>=1&&chips<=2,`no máximo 2 referências globais visíveis (${chips})`);
  await page.getByPlaceholder('Diga ao Cadu o que fazer nesta peça…').fill('Troque a frase para Conheça as principais mídias digitais.');
  await page.getByRole('button',{name:/Gerar edição/}).click();
  await page.getByText('Criei uma nova versão. Você pode revisar no palco ou pedir outro ajuste.').waitFor({timeout:15000});
  const task=calls.find(c=>c.p.endsWith('/studio/tasks'));
  const payload=JSON.parse(task.body).payload;
  assert.ok(payload.reference_images.length<=2,`referências enviadas: ${payload.reference_images.length}`);
  assert.ok(payload.reference_inputs.length<=2);
  // remover um chip global tira a referência do próximo envio
  await page.locator('.se-reference-chip.is-global button').first().click();
  await page.waitForTimeout(700);
  const stored=JSON.parse(await page.evaluate(()=>localStorage.getItem('cadu-studio-editor-v1:174'))).selectedGlobalReferences;
  assert.equal(stored.length,2,`remover o chip tira a referência da seleção guardada: ${JSON.stringify(stored)}`);
  assert.deepEqual(errors,[]);
  console.log('PASS Editor: peça base + no máximo 2 referências, chips globais visíveis e removíveis');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
