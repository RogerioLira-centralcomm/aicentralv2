// Início do Studio (React): barra única, trabalhos recentes do projeto escolhido, filtro e prévia.
const {chromium,ARTIFACTS}=require('./studio-browser.cjs');
const fs=require('fs'),assert=require('node:assert/strict');
const links={home:'/',create:'/criar',editor:'/imagem',videos:'/video',audio:'/audio',analyzer:'/analyzer',library:'/biblioteca',credits:'/workspace/creditos',profile:'/workspace/perfil',workspace:'/workspace',logout:'/logout'};
const bootstrap={apiRoot:'/studio/api',csrf:'t',projectId:'',creditSummaryUrl:'/workspace/api/creditos/resumo',user:{name:'Ana Planejadora',email:'ana@agencia.test'},links};
const svg=color=>`data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="400" height="500"><rect width="100%" height="100%" fill="${color}"/></svg>`)}`;
const page=`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/cadu_studio/home/react/app.css"></head><body><div id="cadu-studio-home-root"></div><script id="cadu-studio-home-bootstrap" type="application/json">${JSON.stringify(bootstrap)}</script><script type="module" src="/static/cadu_studio/home/react/app.js"></script></body></html>`;
(async()=>{
  const browser=await chromium.launch({headless:true});
  const tab=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],libraryCalls=[];
  tab.on('pageerror',e=>errors.push(e.message));
  await tab.route('http://studio.test/**',route=>{
    const url=new URL(route.request().url()),path=url.pathname;
    if(path==='/')return route.fulfill({contentType:'text/html',body:page});
    if(path.startsWith('/static/')&&fs.existsSync('aicentralv2'+path))return route.fulfill({path:'aicentralv2'+path});
    if(path.endsWith('/project-contexts'))return route.fulfill({json:{success:true,data:{items:[{id:'p1',external_project_id:'ci:9',name:'Lançamento Verão',client_id:'174',brand_name:'Centralcomm'}]}}});
    if(path.endsWith('/swap/library')){libraryCalls.push([url.searchParams.get('client_id'),url.searchParams.get('media'),route.request().headers()['x-trocr-csrf-token']]);
      const media=url.searchParams.get('media');
      return route.fulfill({json:{success:true,data:{items:media==='video'
        ?[{id:'v1',headline:'Teaser 15s',poster_url:svg('#2b3a8f'),video_url:'/v.mp4',aspect_ratio:'9:16',updated_at:'2026-10-07T10:00:00Z'}]
        :[{id:'s1',headline:'Post carrossel',thumb_url:svg('#7c5cff'),image_url:svg('#7c5cff'),aspect_ratio:'4:5',updated_at:'2026-10-06T10:00:00Z'},
          {id:'s2',headline:'Banner site',thumb_url:svg('#0e9384'),image_url:svg('#0e9384'),aspect_ratio:'16:9',updated_at:'2026-10-05T10:00:00Z'}]}}});}
    if(path.endsWith('/creditos/resumo'))return route.fulfill({json:{configured:true,monthly:1000,available:640}});
    return route.fulfill({status:404,body:''});
  });
  await tab.goto('http://studio.test/');
  const nav=tab.getByRole('navigation',{name:'Ferramentas do Studio'});
  await nav.waitFor();
  assert.equal(await nav.getByRole('link',{name:'Início'}).getAttribute('aria-current'),'page');
  await tab.getByRole('heading',{name:'Trabalhos recentes'}).waitFor();
  await tab.getByText('Teaser 15s').waitFor();
  const titles=await tab.locator('.sh-card__body strong').allTextContents();
  assert.deepEqual(titles,['Teaser 15s','Post carrossel','Banner site'],'mais recentes primeiro, imagens e vídeos juntos');
  assert.deepEqual(libraryCalls.map(call=>call[0]),['174','174'],'biblioteca do cliente do projeto');
  assert.ok(libraryCalls.every(call=>call[2]==='t'),'envia o token CSRF do Studio');
  await tab.getByText('36% usado').waitFor();
  await tab.screenshot({path:`${ARTIFACTS}/home-desktop.png`});
  await tab.getByRole('button',{name:'Vídeos'}).click();
  assert.deepEqual(await tab.locator('.sh-card__body strong').allTextContents(),['Teaser 15s']);
  await tab.getByRole('button',{name:'Todos'}).click();
  await tab.getByRole('button',{name:'Ver Post carrossel'}).click();
  await tab.getByRole('dialog',{name:'Prévia do trabalho'}).waitFor();
  assert.equal(await tab.getByRole('link',{name:'Continuar editando'}).getAttribute('href'),'/imagem?project_id=ci%3A9');
  await tab.getByRole('button',{name:'Fechar'}).click();
  await tab.setViewportSize({width:390,height:844});
  assert.equal(await tab.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'sem rolagem horizontal em 390px');
  await tab.screenshot({path:`${ARTIFACTS}/home-mobile.png`});
  assert.deepEqual(errors,[]);
  await browser.close();
  console.log('PASS Início do Studio em React: barra única, trabalhos recentes do projeto (imagens e vídeos), filtro, prévia e 390px');
})().catch(error=>{console.error(error);process.exit(1);});
