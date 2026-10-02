// Editor: referências do projeto só entram se a pessoa escolher, e trocar de sessão traz a conversa e as
// escolhas daquela sessão, sem arrastar o chat da sessão anterior.
const {chromium}=require('./studio-browser.cjs');
const {execFileSync}=require('child_process');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
execFileSync(fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3',['tests/frontend/render-studio-editor-fixture.py'],{stdio:'inherit'});
const HTML=fs.readFileSync('tests/frontend/.fixtures/studio-editor/index.html','utf8').replace(/"clientId":\s*"[^"]*"/,'"clientId":"174"');
const STILL='http://studio.test/static/images/cadu/brand-icons/studio-192.png';
const refs=[0,1].map(i=>`${STILL}?ref=${i}`);
const asset={id:'v1',name:'Peça',url:STILL,dataUrl:STILL,status:'draft'};
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1500,height:950}}),tasks=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(([k,v])=>localStorage.setItem(k,v),['cadu-studio-editor-v1:174',JSON.stringify({asset,versions:[asset],selectedId:'v1',prompt:'',format:'4:5',outputSize:{width:1080,height:1350,format:'4:5'},quality:'draft',zoom:100,agentMessages:[{id:'old',role:'assistant',text:'Mensagem da sessão antiga'}]})]);
  await page.route('https://**',route=>route.fulfill({status:200,contentType:'text/css',body:''}));
  await page.route('http://studio.test/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;
    if(p==='/')return route.fulfill({contentType:'text/html',body:HTML});
    if(p.startsWith('/static/'))return fs.existsSync('aicentralv2'+p)?route.fulfill({path:path.resolve('aicentralv2'+p)}):route.fulfill({status:404,body:''});
    const ok=data=>route.fulfill({json:{success:true,data}});
    if(p.endsWith('/project-contexts'))return ok({items:[{id:'p1',name:'Marketing',client_id:174,brand_name:'Centralcomm',brand_context:{name:'Centralcomm',assets:{references:refs,logo:[]},palette:[]}}]});
    if(p.endsWith('/studio/edit-quote'))return ok({estimated_tokens:22000});
    if(p.endsWith('/studio/tasks')&&req.method()==='POST'){tasks.push(JSON.parse(req.postData()).payload);return ok({id:'t1',status:'queued'});}
    if(p.endsWith('/studio/tasks/t1'))return ok({id:'t1',status:'ready',result:{image_url:STILL}});
    if(p.endsWith('/sessions/s2')&&req.method()==='GET')return ok({id:'s2',revision:3,title:'Outra sessão',status:'active',assets:[],metadata:{editor:{versions:[{id:'x2',name:'Peça da outra sessão',url:STILL,status:'draft'}],selected_id:'x2',format:'4:5',agent_messages:[{id:'m2',role:'assistant',text:'Mensagem da outra sessão'}],selected_global_references:[]}}});
    if(/\/sessions$/.test(p)&&req.method()==='GET')return ok({items:[{id:'s2',title:'Outra sessão',status:'active'}]});
    if(/\/sessions(\/[^/]+)?$/.test(p)&&req.method()!=='GET')return ok({id:'s1',revision:1,title:'Mesa',status:'active',assets:[]});
    return ok({items:[],runs:[],personal_assets:[],assets:[]});});
  await page.goto('http://studio.test/?project_id=p1');
  await page.locator('.se-composer').waitFor();await page.waitForTimeout(1200);

  // 1. Nenhuma referência do projeto é escolhida sozinha
  assert.equal(await page.locator('.se-reference-chip.is-global').count(),0,'sem referências do projeto pré-selecionadas');
  await page.getByPlaceholder('Diga ao Cadu o que fazer nesta peça…').fill('Troque o fundo por um céu de fim de tarde.');
  await page.getByRole('button',{name:/Gerar edição/}).click();
  await page.locator('.se-chat-last',{hasText:'Criei uma nova versão'}).waitFor({timeout:15000});
  assert.deepEqual(tasks[0].reference_images,[],'nenhuma referência enviada sem escolha da pessoa');

  // 2. Trocar de sessão traz a conversa daquela sessão
  await page.locator('.se-rail-top select').selectOption('s2');
  await page.locator('.se-chat-last',{hasText:'Mensagem da outra sessão'}).waitFor({timeout:8000});
  await page.locator('.se-chat-content > summary').click();
  const thread=await page.locator('.se-chat-thread').innerText();
  assert.doesNotMatch(thread,/Criei uma nova versão|Mensagem da sessão antiga/,'a conversa anterior não aparece na outra sessão');
  assert.deepEqual(errors,[]);
  console.log('PASS Editor: referências do projeto só por escolha e conversa de cada sessão');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
