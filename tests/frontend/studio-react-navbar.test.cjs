// Editor e Áudio (apps React) usam a mesma navbar do Studio.
const {chromium,ARTIFACTS}=require('./studio-browser.cjs');
const fs=require('fs'),assert=require('node:assert/strict');
const links={home:'/studio',create:'/studio/criar',editor:'/studio/editar',videos:'/studio/video',audio:'/studio/audio',analyzer:'/studio/analyzer',library:'/studio#studioLibrary',credits:'/workspace/creditos',profile:'/workspace/perfil',workspace:'/workspace',logout:'/logout'};
const bootstrap={apiRoot:'/studio/api',csrf:'t',projectId:'',credits:640,usagePercent:36,user:{name:'Ana Planejadora',email:'ana@agencia.test'},links};
const apps={
  editor:{root:'cadu-studio-editor-root',data:'cadu-studio-editor-bootstrap',dir:'editor'},
  audio:{root:'cadu-studio-audio-root',data:'cadu-studio-audio-bootstrap',dir:'audio'},
};
const page=(app)=>`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/cadu_studio/${app.dir}/react/app.css"></head><body><div id="${app.root}"></div><script id="${app.data}" type="application/json">${JSON.stringify(bootstrap)}</script><script type="module" src="/static/cadu_studio/${app.dir}/react/app.js"></script></body></html>`;
(async()=>{
  const browser=await chromium.launch({headless:true});
  for(const [name,app] of Object.entries(apps)){
    const tab=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
    tab.on('pageerror',e=>errors.push(e.message));
    await tab.route('http://studio.test/**',route=>{
      const path=new URL(route.request().url()).pathname;
      if(path==='/')return route.fulfill({contentType:'text/html',body:page(app)});
      if(path.startsWith('/static/')&&fs.existsSync('aicentralv2'+path))return route.fulfill({path:'aicentralv2'+path});
      if(path.includes('/api/'))return route.fulfill({json:{success:true,data:{items:[{id:'p1',name:'Lançamento Verão',client_id:174,brand_name:'Centralcomm'}]}}});
      return route.fulfill({status:404,body:''});
    });
    await tab.goto('http://studio.test/');
    const nav=tab.getByRole('navigation',{name:'Ferramentas do Studio'});
    await nav.waitFor();
    assert.deepEqual(await nav.getByRole('link').allTextContents(),['Início','Criar','Editar','Vídeo','Áudio','Analisar','Biblioteca']);
    assert.equal(await nav.getByRole('link',{name:name==='editor'?'Editar':'Áudio'}).getAttribute('aria-current'),'page');
    await tab.getByText('36% usado').waitFor();
    await tab.getByRole('button',{name:/Projeto e marca/}).waitFor();
    await tab.screenshot({path:`${ARTIFACTS}/navbar-${name}.png`});
    if(name==='editor'){
      await tab.locator('.se-session-nav').getByRole('button',{name:'Histórico'}).click();
      const dialog=tab.getByRole('dialog',{name:'Sessões e versões'});
      await dialog.waitFor();
      await tab.keyboard.press('Escape');
      await dialog.waitFor({state:'detached'});
    }
    await tab.setViewportSize({width:390,height:844});
    assert.equal(await tab.evaluate(()=>document.querySelector('.csu-navbar').scrollWidth<=innerWidth),true,`${name}: navbar sem overflow em 390px`);
    assert.deepEqual(errors,[],`${name}: erros de JS`);
  }
  console.log('PASS Editor e Áudio usam a navbar única: mesmas 7 ferramentas, item ativo correto, créditos, seletor de projeto, 390px');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
