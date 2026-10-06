const {chromium,ensureEditorFixture,FIXTURE,ARTIFACTS}=require('./studio-browser.cjs');
ensureEditorFixture();
const fs=require('fs'),assert=require('node:assert/strict');
const names=['Fachada da loja ao entardecer com luz quente','Família na sala','Roteador em destaque','Logo final','Cena 5','Produto sobre mesa de madeira clara','Detalhe do aplicativo no celular','Promoção de inverno 2026 — banner principal','Equipe sorrindo','Mapa de cobertura'].concat(Array.from({length:14},(_,i)=>'Peça '+(i+11)));
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('http://studio.test/**',async route=>{
const url=new URL(route.request().url()),path=url.pathname;
if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(FIXTURE+'/index.html','utf8')});
if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
if(path==='/clip.mp4')return route.fulfill({path:FIXTURE+'/clip.mp4',contentType:'video/mp4'});
if(path==='/broken.png')return route.fulfill({status:404,body:''});
let data={};
if(path.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[{id:'clip1',name:'Teste horizontal',video_url:'/clip.mp4'}]:names.map((n,i)=>({id:'p'+(i+1),name:n,image_url:i===3?'/broken.png':'/static/images/canais/prime-video.svg',thumb_url:i===3?'/broken.png':'/static/images/canais/prime-video.svg'}))};
if(path.endsWith('/clips'))data={items:[]};
if(path.endsWith('/sounds'))data={items:JSON.parse(fs.readFileSync('aicentralv2/static/audio/studio/catalog.json'))};
if(path.endsWith('/projects'))data=route.request().method()==='POST'?{id:'project',revision:1,document:JSON.parse(route.request().postData()).document}:{items:[]};
if(path.endsWith('/video-project'))data={project:{active_clip_id:'clip1'}};
if(path.endsWith('/inspect')||path.endsWith('/tasks'))data={has_audio:true,waveform:[.3,.8,.2],frames:[]};
if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p',production:'720p'},skills:{}};
return route.fulfill({json:{success:true,data}});
});
page.on('dialog',d=>d.accept());
await page.goto('http://studio.test/?client=1&clip=clip1');
await page.waitForFunction(()=>document.querySelector('#mcSwapVideo').videoWidth===320);
for(const id of ['p1','p2','p3'])await page.click(`#mcVideoLibrary button[data-id="${id}"][data-action="pick"]`);
await page.waitForFunction(()=>document.querySelectorAll('#mcVideoLibrary .mc-lib-item').length>=20);
// imagem quebrada vira marcador, não ícone de imagem quebrada
await page.waitForFunction(()=>document.querySelector('#mcVideoLibrary [data-id="p4"] .mc-lib-missing'));
assert.equal(await page.locator('#mcVideoLibrary [data-id="p4"] img').count(),0);
// ações de cada cartão cabem dentro dele, com texto inteiro
const actions=await page.evaluate(()=>[...document.querySelectorAll('#mcVideoLibrary .mc-lib-item')].slice(0,8).map(li=>{const b=li.getBoundingClientRect();return [...li.querySelectorAll('.mc-lib-actions button')].map(x=>{const r=x.getBoundingClientRect();return {t:x.textContent.trim(),inside:r.left>=b.left-1&&r.right<=b.right+1,h:Math.round(r.height),clipped:x.scrollWidth>x.clientWidth}})}).flat());
assert.ok(actions.some(a=>a.t==='Remover')&&actions.some(a=>a.t==='Excluir'));
assert.ok(actions.every(a=>a.inside&&!a.clipped&&a.h<=24),JSON.stringify(actions));
// abas e busca continuam visíveis depois de rolar a lista
await page.evaluate(()=>{document.querySelector('.mc-cadu-video-lib').scrollTop=1200});
const top=await page.evaluate(()=>{const lib=document.querySelector('.mc-cadu-video-lib').getBoundingClientRect(),s=document.querySelector('#mcVideoSearch').getBoundingClientRect(),t=document.querySelector('#mcVideoLibStillTab').getBoundingClientRect();return {tab:t.top-lib.top,search:s.top-lib.top,libH:lib.height}});
assert.ok(top.tab>=0&&top.tab<60&&top.search>=0&&top.search<110,JSON.stringify(top));
// "Cenas para geração" fica dentro da timeline e mostra a primeira cena sem rolar por dentro da timeline
const strip=await page.evaluate(()=>{const tl=document.querySelector('.mc-cadu-video-timeline').getBoundingClientRect(),box=document.querySelector('.mc-studio-storyboard').getBoundingClientRect(),first=document.querySelector('#mcVideoScenes > *')?.getBoundingClientRect();return {inside:box.top>=tl.top&&box.bottom<=tl.bottom+1,firstVisible:!!first&&first.top>=box.top&&first.top<box.bottom-8}});
assert.deepEqual(strip,{inside:true,firstVisible:true},JSON.stringify(strip));
await page.screenshot({path:ARTIFACTS+'/library-layout.png'});
assert.deepEqual(errors,[]);
console.log('PASS biblioteca: ações visíveis, miniatura indisponível, cabeçalho fixo e cenas sempre visíveis em 1280×720');
await browser.close();
})();
