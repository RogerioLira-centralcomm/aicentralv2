// Editor (React): rascunho aberto é oferecido (continuar ou nova sessão); imagem só escolhida da prateleira não volta sozinha.
const {chromium}=require('./studio-browser.cjs');
const fs=require('fs'),assert=require('node:assert/strict');
const KEY='cadu-studio-editor-v1:174:p1';
const bootstrap={apiRoot:'/studio/api',csrf:'t',clientId:'174',projectId:'p1',credits:640,usagePercent:36,
  user:{name:'Ana Planejadora',email:'ana@agencia.test'},links:{home:'/studio',create:'/studio/criar',editor:'/studio/editar',videos:'/studio/video',audio:'/studio/audio',library:'/studio#lib'}};
const html=fs.readFileSync('tests/frontend/studio-editor-resilience.test.cjs','utf8').match(/const html=`([\s\S]*?)`;/)[1].replace('${JSON.stringify(bootstrap)}',JSON.stringify(bootstrap)).replace(/\$\{[^}]*\}/g,'');
const STILL='/static/images/cadu/brand-icons/studio-192.png';
const logo={id:'shelf:logo',name:'Cadu Reports · logo',url:STILL,dataUrl:STILL,status:'draft'};
async function open(browser,draft){
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  if(draft)await page.addInitScript(([key,value])=>localStorage.setItem(key,value),[KEY,JSON.stringify(draft)]);
  await page.route('http://studio.test/**',route=>{
    const path=new URL(route.request().url()).pathname;
    if(path==='/')return route.fulfill({contentType:'text/html',body:html});
    if(path.startsWith('/static/'))return fs.existsSync('aicentralv2'+path)?route.fulfill({path:'aicentralv2'+path}):route.fulfill({status:404,body:''});
    if(path.endsWith('/project-contexts'))return route.fulfill({json:{success:true,data:{items:[{id:'p1',name:'Lançamento Verão',client_id:174,brand_name:'Centralcomm'}]}}});
    return route.fulfill({json:{success:true,data:{items:[]}}});
  });
  await page.goto('http://studio.test/');
  await page.getByRole('navigation',{name:'Ferramentas do Studio'}).waitFor();
  return {page,errors};
}
(async()=>{
  const browser=await chromium.launch({headless:true});
  // 1. só a logo da prateleira: abre em branco, sem perguntar
  let {page,errors}=await open(browser,{asset:logo,versions:[logo],selectedId:'shelf:logo'});
  await page.waitForTimeout(600);
  assert.equal(await page.getByText('Sessão em aberto',{exact:true}).count(),0,'imagem só da prateleira não gera pergunta');
  assert.equal(await page.getByText('Cadu Reports · logo').count(),0,'a logo não volta como base');
  assert.deepEqual(errors,[]);
  await page.close();
  // 2. rascunho com trabalho: oferece; "Nova sessão" começa em branco e descarta o rascunho
  const work={asset:{id:'u1',name:'Peça da campanha',url:STILL,dataUrl:STILL,status:'draft'},versions:[{id:'u1',name:'Peça da campanha',url:STILL,dataUrl:STILL,status:'draft'}],selectedId:'u1',prompt:'Trocar o fundo'};
  ({page,errors}=await open(browser,work));
  await page.getByText('Sessão em aberto',{exact:true}).waitFor();
  await page.getByRole('button',{name:/Nova sessão em Lançamento Verão/}).click();
  await page.waitForTimeout(700);
  assert.equal(await page.getByText('Peça da campanha').count(),0,'nova sessão começa sem a peça anterior');
  assert.equal(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)||'{}').asset||null,KEY),null,'o rascunho anterior é descartado');
  assert.deepEqual(errors,[]);
  await page.close();
  // 3. continuar retoma a peça e o texto
  ({page,errors}=await open(browser,work));
  await page.getByText('Sessão em aberto',{exact:true}).waitFor();
  await page.getByRole('button',{name:/Continuar sessão em aberto/}).click();
  await page.getByText('Peça da campanha').first().waitFor();
  assert.equal(await page.locator('textarea').first().inputValue(),'Trocar o fundo');
  assert.deepEqual(errors,[]);
  await browser.close();
  console.log('PASS Editor: rascunho oferecido (continuar ou nova sessão) e logo da prateleira não volta sozinha');
})().catch(error=>{console.error(error);process.exit(1);});
