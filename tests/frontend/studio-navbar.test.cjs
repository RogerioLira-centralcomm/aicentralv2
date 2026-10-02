// Navbar única do Studio: ilha React sobre o contrato legado (#mcCaduProject + eventos cadu:*).
const {chromium,ARTIFACTS}=require('./studio-browser.cjs');
const {execFileSync}=require('child_process');
const fs=require('fs'),assert=require('node:assert/strict');
execFileSync(fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3',['tests/frontend/render-studio-navbar-fixture.py'],{stdio:'inherit'});
const projects=[
  {id:'p1',name:'Lançamento Verão',client_id:174,brand_name:'Centralcomm',brand_context:{}},
  {id:'p2',name:'Black Friday',client_id:25,brand_name:'Aurora Cosméticos',brand_count:2,brand_context:{}},
];
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:800}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://studio.test/**',route=>{
    const url=new URL(route.request().url()),path=url.pathname;
    if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('tests/frontend/.fixtures/studio-navbar/index.html','utf8')});
    if(path.startsWith('/static/'))return fs.existsSync('aicentralv2'+path)?route.fulfill({path:'aicentralv2'+path}):route.fulfill({status:404,body:''});
    if(path.endsWith('/project-contexts'))return route.fulfill({json:{success:true,data:{items:projects}}});
    if(path==='/workspace/api/creditos/resumo')return route.fulfill({json:{configured:true,monthly:1000,available:250}});
    return route.fulfill({status:404,body:''});
  });
  const events=[];
  await page.exposeFunction('recordEvent',detail=>events.push(detail));
  await page.addInitScript(()=>document.addEventListener('cadu:project-change',e=>window.recordEvent(e.detail)));
  await page.goto('http://studio.test/');
  const nav=page.getByRole('navigation',{name:'Ferramentas do Studio'});
  await nav.waitFor();
  assert.equal(await nav.getByRole('link',{name:'Criar'}).getAttribute('aria-current'),'page');
  assert.deepEqual(await nav.getByRole('link').allTextContents(),['Início','Criar','Editar','Vídeo','Áudio','Analisar','Biblioteca']);
  assert.ok((await page.locator('.mc-cadu-nav').boundingBox()).width<=1,'a navegação antiga fica só como contrato');
  const trigger=page.getByRole('button',{name:/Projeto e marca: Criação rápida · sem projeto/});
  await trigger.waitFor();
  await page.getByText('75% usado').waitFor();
  await trigger.click();
  const list=page.getByRole('listbox',{name:'Projetos'});
  assert.deepEqual(await list.getByRole('option').allTextContents(),['⚡Criação rápidasem projeto','CLançamento VerãoCentralcomm','ACBlack FridayAurora Cosméticos +1']);
  await list.getByRole('option',{name:/Black Friday/}).click();
  assert.equal(await page.locator('#mcCaduProject').inputValue(),'p2');
  await page.waitForFunction(()=>window.McCaduContext?.projectId==='p2');
  assert.equal(events.at(-1).clientId,'25');
  await page.getByRole('button',{name:/Projeto e marca: Black Friday · Aurora Cosméticos/}).waitFor();
  await page.keyboard.press('Tab');
  await page.getByRole('button',{name:/Conta de Ana Planejadora/}).click();
  await page.getByRole('menuitem',{name:'Sair'}).waitFor();
  await page.screenshot({path:ARTIFACTS+'/navbar-desktop.png'});
  await page.keyboard.press('Escape');
  await page.setViewportSize({width:390,height:800});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'sem rolagem horizontal em 390px');
  await page.screenshot({path:ARTIFACTS+'/navbar-mobile.png'});
  assert.deepEqual(errors,[]);
  console.log('PASS navbar única: 7 ferramentas, item ativo, projeto troca o contrato legado e dispara cadu:project-change, créditos, menu de conta, 390px sem overflow');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
