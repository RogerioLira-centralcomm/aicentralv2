// Áudio do Studio (protótipo): largura total, modal de lançamento após 3 s e "quero ser avisado".
const {chromium,ARTIFACTS}=require('./studio-browser.cjs');
const fs=require('fs'),assert=require('node:assert/strict');
const links={home:'/',create:'/criar',editor:'/imagem',videos:'/video',audio:'/audio',analyzer:'/analyzer',library:'/biblioteca',credits:'/c',profile:'/p'};
const bootstrap={apiRoot:'/studio/api',csrf:'tok',projectId:'',credits:120800,usagePercent:98,user:{name:'Apolo'},links};
// O tema dos portais limita todo <main>; a fixture repete a regra para pegar a regressão.
const page=`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>.portal main{width:min(1180px,calc(100% - 40px));margin:auto}</style><link rel="stylesheet" href="/static/cadu_studio/audio/react/app.css"></head><body class="portal"><div id="content"><div id="cadu-studio-audio-root"></div></div><script id="cadu-studio-audio-bootstrap" type="application/json">${JSON.stringify(bootstrap)}</script><script type="module" src="/static/cadu_studio/audio/react/app.js"></script></body></html>`;
async function open(browser,{registered=false,failPost=false}={}){
  const tab=await browser.newPage({viewport:{width:1593,height:930}}),errors=[],posts=[];
  tab.on('pageerror',e=>errors.push(e.message));
  await tab.route('http://studio.test/**',route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(path==='/')return route.fulfill({contentType:'text/html',body:page});
    if(path.startsWith('/static/')&&fs.existsSync('aicentralv2'+path))return route.fulfill({path:'aicentralv2'+path});
    if(path.endsWith('/project-contexts'))return route.fulfill({json:{success:true,data:{items:[]}}});
    if(path.endsWith('/api/interesse/audio')){
      if(req.method()==='POST'){posts.push(req.headers());return failPost?route.fulfill({status:503,json:{success:false,error:'x'}}):route.fulfill({json:{success:true,data:{registered:true}}});}
      return route.fulfill({json:{success:true,data:{registered}}});}
    return route.fulfill({status:404,body:''});
  });
  await tab.goto('http://studio.test/');
  await tab.locator('.au-main').waitFor();
  return {tab,errors,posts};
}
(async()=>{
  const browser=await chromium.launch({headless:true});
  let {tab,errors,posts}=await open(browser);
  const width=await tab.evaluate(()=>Math.round(document.querySelector('.au-main').getBoundingClientRect().width));
  assert.ok(width>=1560,`a ferramenta usa a largura toda (${width}px)`);
  await tab.waitForTimeout(1200);
  assert.equal(await tab.getByRole('dialog').count(),0,'o mock aparece antes; o modal só depois de 3 s');
  await tab.getByRole('dialog').waitFor({timeout:3500});
  await tab.waitForTimeout(900);await tab.screenshot({path:`${ARTIFACTS}/audio-launch-modal.png`});
  assert.equal(await tab.evaluate(()=>document.activeElement?.textContent),'Quero ser avisado','o foco vai ao botão principal');
  await tab.getByRole('button',{name:'Quero ser avisado'}).click();
  await tab.getByText('Combinado. Avisamos você.').waitFor();
  assert.equal(posts.length,1);assert.equal(posts[0]['x-trocr-csrf-token'],'tok','envia o token de segurança');
  await tab.getByRole('button',{name:'Ver o protótipo'}).click();
  assert.equal(await tab.getByRole('dialog').count(),0);
  await tab.getByRole('button',{name:/Em breve · dez\/26 · você será avisado/}).waitFor();
  assert.deepEqual(errors,[]);
  await tab.close();
  // quem já se registrou não vê o modal
  ({tab,errors}=await open(browser,{registered:true}));
  await tab.waitForTimeout(3600);
  assert.equal(await tab.getByRole('dialog').count(),0,'já registrado: sem modal');
  await tab.close();
  // falha do servidor: mensagem e nova tentativa; Esc fecha e não volta na mesma aba
  ({tab,errors}=await open(browser,{failPost:true}));
  await tab.getByRole('dialog').waitFor({timeout:3500});
  await tab.getByRole('button',{name:'Quero ser avisado'}).click();
  await tab.getByRole('alert').waitFor();
  assert.equal(await tab.getByRole('button',{name:'Quero ser avisado'}).isEnabled(),true,'pode tentar de novo');
  await tab.keyboard.press('Escape');
  assert.equal(await tab.getByRole('dialog').count(),0);
  await tab.reload();await tab.locator('.au-main').waitFor();await tab.waitForTimeout(3600);
  assert.equal(await tab.getByRole('dialog').count(),0,'fechado nesta aba: não reabre sozinho');
  await tab.getByRole('button',{name:/Em breve · dez\/26/}).click();
  await tab.getByRole('dialog').waitFor();
  await browser.close();
  console.log('PASS Áudio: largura total, modal em 3 s, aviso registrado, já registrado sem modal e falha tratada');
})().catch(error=>{console.error(error);process.exit(1);});
