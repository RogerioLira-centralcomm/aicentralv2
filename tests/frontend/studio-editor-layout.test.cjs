// : enviar peça → pedir edição → nova versão, sempre com o token do Studio.
const {chromium,ARTIFACTS}=require('./studio-browser.cjs');
const fs=require('fs'),assert=require('node:assert/strict');
const TOKEN='studio-token';
const bootstrap={apiRoot:'/studio/api',csrf:TOKEN,clientId:'174',projectId:'p1',credits:640,usagePercent:36,
  user:{name:'Ana Planejadora',email:'ana@agencia.test'},links:{home:'/studio',create:'/studio/criar',editor:'/studio/editar',videos:'/studio/video',audio:'/studio/audio',library:'/studio#lib'}};
const html=`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/cadu_studio/editor/react/app.css"></head><body><div id="cadu-studio-editor-root"></div><script id="cadu-studio-editor-bootstrap" type="application/json">${JSON.stringify(bootstrap)}</script><script type="module" src="/static/cadu_studio/editor/react/app.js"></script></body></html>`;
const STILL='/static/images/cadu/brand-icons/studio-192.png';
// Editor: a barra de ferramentas fica sempre logo abaixo do topo e o palco ocupa o resto,
// com a peça vazia, com arquivo ausente e com uma peça válida, mesmo se a altura herdada não for definida.
const bad={id:'v1',name:'Imagem de referência',url:'http://studio.test/missing.png',dataUrl:'http://studio.test/missing.png',status:'draft'};
const good={id:'v2',name:'Peça',url:STILL,dataUrl:STILL,status:'draft'};
(async()=>{
  const browser=await chromium.launch({headless:true});
  const cases=[['vazio',null],['arquivo ausente',bad],['peça válida',good]];
  for(const width of [1704,1280]){
    for(const [label,asset] of cases){
      for(const looseHeight of [false,true]){
        const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];
        page.on('pageerror',e=>errors.push(e.message));
        if(asset)await page.addInitScript(([k,v])=>localStorage.setItem(k,v),['cadu-studio-editor-v1:174',JSON.stringify({asset,versions:[asset],selectedId:asset.id,prompt:'',format:'4:5',outputSize:{width:1080,height:1350,format:'4:5'},quality:'draft',zoom:100})]);
        await page.route('http://studio.test/**',async route=>{const url=new URL(route.request().url()),path=url.pathname;
          if(path==='/')return route.fulfill({contentType:'text/html',body:html});
          if(path==='/missing.png')return route.fulfill({status:404,body:''});
          if(path.startsWith('/static/'))return fs.existsSync('aicentralv2'+path)?route.fulfill({path:'aicentralv2'+path}):route.fulfill({status:404,body:''});
          return route.fulfill({json:{success:true,data:{items:[],runs:[],personal_assets:[],assets:[]}}});});
        await page.goto('http://studio.test/');
        if(looseHeight)await page.addStyleTag({content:'#cadu-studio-editor-root,.se-app{height:auto!important;min-height:100vh}'});
        await page.locator('.se-toolbar').waitFor();await page.waitForTimeout(900);
        const m=await page.evaluate(()=>{const r=e=>{const b=document.querySelector(e).getBoundingClientRect();return {top:Math.round(b.top),height:Math.round(b.height),left:Math.round(b.left),width:Math.round(b.width)}};return {nav:r('.csu-navbar'),toolbar:r('.se-toolbar'),stage:r('.se-stage'),main:r('.se-main')}});
        const where=`${label}, ${width}px${looseHeight?', altura solta':''}`;
        assert.ok(m.toolbar.top-(m.nav.top+m.nav.height)<=4,`barra logo abaixo do topo (${where}): ${JSON.stringify(m)}`);
        assert.ok(Math.abs(m.toolbar.width-m.main.width)<=2,`barra com a largura do palco (${where})`);
        assert.ok(m.stage.height>=m.main.height-m.toolbar.height-4,`palco ocupa o resto (${where}): ${JSON.stringify(m)}`);
        assert.deepEqual(errors,[]);
        await page.close();
      }
    }
  }
  console.log('PASS Editor: barra no topo e palco preenchendo a coluna em 3 estados, 2 larguras e com altura herdada solta');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
