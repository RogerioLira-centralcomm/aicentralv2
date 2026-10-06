// Parte de baixo do editor: timeline vazia explicada, arrastar da biblioteca, cenas visíveis e altura ajustável.
const {chromium,ensureEditorFixture,FIXTURE,ARTIFACTS}=require('./studio-browser.cjs');
ensureEditorFixture();
const fs=require('fs'),assert=require('node:assert/strict');
async function open(browser,width,height){
const page=await browser.newPage({viewport:{width,height}}),errors=[];page.errors=errors;page.on('pageerror',e=>errors.push(e.message));
await page.route('http://studio.test/**',async route=>{
const url=new URL(route.request().url()),path=url.pathname;
if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(FIXTURE+'/index.html','utf8')});
if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
if(path==='/clip.mp4')return route.fulfill({path:FIXTURE+'/clip.mp4',contentType:'video/mp4'});
let data={};
if(path.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[{id:'clip1',name:'Teste horizontal',video_url:'/clip.mp4',duration:3}]:[1,2,3,4,5,6].map(n=>({id:'p'+n,name:'Peça '+n,image_url:'/static/images/canais/prime-video.svg',thumb_url:'/static/images/canais/prime-video.svg'}))};
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
return page;}
const comp=page=>page.evaluate(async()=>{const {state}=await import('/static/js/cadu-video/state.js');const c=state.composition||{};return {enabled:!!c.enabled,items:(c.items||[]).map(i=>i.asset_id),kinds:(c.items||[]).map(i=>i.kind),audio:(c.audio||[]).map(a=>({id:a.sound_id,start:a.start}))}});
(async()=>{
const browser=await chromium.launch({headless:true});
let page=await open(browser,1280,720);
// A) rótulo claro, estado vazio com ação e faixa de cenas visível
for(const id of ['p1','p2','p3'])await page.click(`#mcVideoLibrary button[data-id="${id}"][data-action="pick"]`);
assert.equal((await page.locator('#mcCompositionMode').textContent()).trim(),'Editar em trilhas');
await page.click('#mcCompositionMode');
assert.equal((await page.locator('#mcCompositionMode').textContent()).trim(),'Voltar à visão simples');
assert.equal(await page.locator('#mcCompositionEmpty').isVisible(),true);
assert.match(await page.locator('[data-comp-empty="scenes"]').textContent(),/Usar as 3 cenas da sequência/);
assert.equal(await page.locator('.mc-studio-storyboard > summary').isVisible(),true,'a faixa de cenas continua acessível no modo trilhas');
await page.click('[data-comp-empty="scenes"]');
assert.deepEqual((await comp(page)).items,['p1','p2','p3']);
assert.equal(await page.locator('#mcCompositionEmpty').isVisible(),false);
assert.equal(await page.locator('[data-composition-item]').count(),3);
// B) arrastar peça para o meio da timeline: entra antes do 2º item
const lane=page.locator('#mcCompositionTracks [data-track-kind="video"] .mc-pro-lane');
const laneBox=await lane.boundingBox(),pps=Number(await page.locator('.mc-pro-timeline').getAttribute('data-pps'));
await page.locator('#mcVideoLibrary [data-media-id="p5"]').dragTo(lane,{targetPosition:{x:Math.round(pps*4.7),y:laneBox.height/2}});
assert.deepEqual((await comp(page)).items,['p1','p5','p2','p3'],'posição pelo ponto solto');
// B) clipe da biblioteca vai para o fim quando solto depois do último item
await page.click('#mcVideoLibClipTab');
await page.locator('#mcVideoClips [data-media-id="clip1"]').dragTo(lane,{targetPosition:{x:Math.round(pps*14),y:laneBox.height/2}});
let state=await comp(page);assert.deepEqual(state.items.slice(-1),['clip1']);assert.equal(state.kinds.at(-1),'video');
// B) som solto em 5s começa em ~5s
await page.click('#mcStudioSoundsTab');
await page.waitForSelector('#mcStudioSoundList .mc-studio-sound');
const soundId=await page.locator('#mcStudioSoundList .mc-studio-sound').first().getAttribute('data-media-id');
await page.locator('#mcStudioSoundList .mc-studio-sound').first().dragTo(lane,{targetPosition:{x:Math.round(pps*5),y:laneBox.height/2}});
state=await comp(page);assert.equal(state.audio.length,1);assert.equal(state.audio[0].id,soundId);assert.ok(Math.abs(state.audio[0].start-5)<.3,'início do áudio '+state.audio[0].start);
await page.screenshot({path:ARTIFACTS+'/timeline-bottom.png'});
assert.deepEqual(page.errors,[]);
await page.close();
// B) soltar na visão simples liga a montagem sozinho
page=await open(browser,1280,720);
assert.equal((await comp(page)).enabled,false);
await page.locator('#mcVideoLibrary [data-media-id="p6"]').dragTo(page.locator('.mc-cadu-video-timeline'),{targetPosition:{x:300,y:120}});
state=await comp(page);assert.equal(state.enabled,true);assert.deepEqual(state.items,['p6']);
assert.deepEqual(page.errors,[]);
await page.close();
// C) altura proporcional à tela e ajustável acima de 360px
page=await open(browser,1920,1080);
const height=async()=>Math.round((await page.locator('.mc-cadu-video-timeline').boundingBox()).height);
const base=await height();assert.ok(base>=340,'altura padrão em 1080p: '+base);
const handle=await page.locator('#mcStudioTimelineResize').boundingBox();
await page.mouse.move(handle.x+handle.width/2,handle.y+2);await page.mouse.down();await page.mouse.move(handle.x+handle.width/2,handle.y-8,{steps:2});await page.mouse.up();
const nudged=await height();assert.ok(Math.abs(nudged-(base+10))<=4,'salto ao começar o arraste: '+base+' -> '+nudged);
const handle2=await page.locator('#mcStudioTimelineResize').boundingBox();
await page.mouse.move(handle2.x+handle2.width/2,handle2.y+2);await page.mouse.down();await page.mouse.move(handle2.x+handle2.width/2,handle2.y-260,{steps:6});await page.mouse.up();
const grown=await height();assert.ok(grown>=500,'altura depois de arrastar: '+grown);
await page.close();
page=await open(browser,1280,720);
assert.ok(await page.locator('.mc-cadu-video-timeline').boundingBox().then(b=>b.height)<=290);
assert.deepEqual(page.errors,[]);
console.log('PASS parte de baixo: vazio explicado, cenas do roteiro, arrastar peça/clipe/som, ligar montagem ao soltar e altura ajustável');
await browser.close();
})();
