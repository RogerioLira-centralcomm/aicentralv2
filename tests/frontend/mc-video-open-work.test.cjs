// Vídeo: a marca do projeto do link vem da barra do Studio (sem consultar project-contexts de novo), e o projeto em
// andamento é oferecido depois da tela pintada, sem travar a abertura.
const {chromium,ensureEditorFixture,FIXTURE,ARTIFACTS}=require('./studio-browser.cjs');
const fs=require('fs'),assert=require('node:assert/strict');
ensureEditorFixture();
const work={name:'Campanha de outubro',storyboard_draft:{briefing:'Lançamento de outubro',beats:[]},clip_edits:{}};
async function open(browser,{query='',context,projectWork=true,projectContextsCalls}){
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],saves=[];
  page.on('pageerror',e=>errors.push(e.message));
  // The Studio bar publishes this once it has read the project list; the fixture has no bar of its own (a hidden
  // #mcCaduProject stands in for it).
  await page.addInitScript(ctx=>{
    if(ctx==='none')return;
    if(ctx)window.McCaduContext=ctx;
  },context===undefined?'none':context);
  await page.route('http://studio.test/**',async route=>{
    const url=new URL(route.request().url()),path=url.pathname;
    if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(FIXTURE+'/index.html','utf8').replace('<body>','<body><select id="mcCaduProject" hidden></select>')});
    if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
    let data={};
    if(path.endsWith('/project-contexts'))projectContextsCalls.push(url.search);
    if(path.endsWith('/swap/library'))data={items:[]};
    if(path.endsWith('/clips'))data={items:[]};
    if(path.endsWith('/sounds'))data={items:[]};
    if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p',production:'720p'},skills:{}};
    if(path.endsWith('/projects')&&route.request().method()==='GET')data={items:projectWork?[{id:'p1',name:work.name,revision:3}]:[]};
    if(/\/projects\/p1$/.test(path)&&route.request().method()==='GET')data={id:'p1',revision:3,document:work};
    if(route.request().method()==='POST'){saves.push(path);data={id:'p2',name:'Novo projeto',revision:1,document:{},updated_at:'2026-10-12'};}
    if(path.endsWith('/video-project')&&route.request().method()==='GET')data={project:{}};
    return route.fulfill({json:{success:true,data}});
  });
  await page.goto(`http://studio.test/?${query}`);
  return {page,errors,saves};
}
(async()=>{
  const browser=await chromium.launch({headless:true}),calls=[];
  // 1. The bar already published the project's brand: used as is, no second project-contexts request.
  const linked=await open(browser,{query:'project_id=ext-9',context:{clientId:'7',projectId:'p1',brandName:'Marca do projeto'},projectContextsCalls:calls});
  await linked.page.waitForFunction(()=>document.querySelector('dialog.studio-session-prompt[open]'));
  assert.deepEqual(calls,[],'a página de vídeo não consulta project-contexts por conta própria');
  assert.doesNotMatch(await linked.page.locator('#mcAnimateStatus').textContent(),/identificar a marca/);
  // The studio is painted and usable behind the dialog.
  assert(await linked.page.locator('#mcVideoScenes').count(),'a tela já foi pintada atrás do diálogo');
  assert.match(await linked.page.locator('dialog.studio-session-prompt').innerText(),/Campanha de outubro/);
  // Esc keeps the open work: nothing is created.
  await linked.page.keyboard.press('Escape');
  await linked.page.locator('dialog.studio-session-prompt').waitFor({state:'detached'});
  assert.deepEqual(linked.saves.filter(path=>/\/projects/.test(path)),[],'Esc não cria nem descarta projeto');
  // 2. "Novo projeto" starts a blank project and keeps the old one in the list.
  const fresh=await open(browser,{query:'project_id=ext-9',context:{clientId:'7',projectId:'p1',brandName:'Marca do projeto'},projectContextsCalls:calls});
  await fresh.page.waitForFunction(()=>document.querySelector('dialog.studio-session-prompt[open]'));
  await fresh.page.getByRole('button',{name:/Novo projeto de vídeo/}).click();
  await fresh.page.waitForFunction(()=>!document.querySelector('dialog.studio-session-prompt'));
  // The old project is saved first (it stays in the list), then the blank one is created.
  for(let i=0;i<50&&!fresh.saves.some(path=>/\/projects\/p2$/.test(path));i++)await fresh.page.waitForTimeout(100);
  assert(fresh.saves.some(path=>/\/projects\/p1$/.test(path)),'o projeto anterior foi salvo antes');
  assert(fresh.saves.some(path=>/\/projects\/p2$/.test(path)),'um projeto novo foi criado');
  // 3. A link that already says what to open is not interrupted.
  const handoff=await open(browser,{query:'client=7&scenes=x',context:{clientId:'7'},projectContextsCalls:calls});
  await handoff.page.waitForTimeout(800);
  assert.equal(await handoff.page.locator('dialog.studio-session-prompt').count(),0,'cenas vindas do Criar não são interrompidas pelo diálogo');
  // 4. The bar never answers: the page opens anyway, says so, and does not wait on it for long.
  const started=Date.now();
  const silent=await open(browser,{query:'project_id=ext-9&client=',projectContextsCalls:calls});
  await silent.page.waitForFunction(()=>/identificar a marca do projeto/.test(document.getElementById('mcAnimateStatus')?.textContent||''),null,{timeout:8000});
  assert(Date.now()-started<7000,'a abertura não espera indefinidamente pela barra');
  await linked.page.screenshot({path:ARTIFACTS+'/video-open-work.png'});
  assert.deepEqual([...linked.errors,...fresh.errors,...handoff.errors,...silent.errors],[]);
  console.log('PASS Vídeo: marca vem da barra sem chamada extra, diálogo não trava a tela, Esc preserva, Novo cria, links com destino não são interrompidos, falha da barra avisa');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
