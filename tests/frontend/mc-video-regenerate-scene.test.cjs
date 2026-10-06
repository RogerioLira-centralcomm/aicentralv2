// Fase 3 (regerar uma cena sem refazer o resto) e fase 4 (checagem antes de gerar).
const {chromium,ensureEditorFixture,FIXTURE,ARTIFACTS}=require('./studio-browser.cjs');
ensureEditorFixture();
const fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],beatCalls=[],imageCalls=[],requests=[];
page.on('pageerror',e=>errors.push(e.message));
let imageSeq=0,failImage=false,dialogs=[],promptAnswer='mais direto';
page.on('dialog',async d=>{dialogs.push({type:d.type(),message:d.message()});if(d.type()==='prompt')await d.accept(promptAnswer);else await d.accept();});
const lib=n=>({id:'p'+n,name:'Peça '+n,image_url:'/static/images/canais/prime-video.svg?n='+n,thumb_url:'/static/images/canais/prime-video.svg?n='+n});
await page.route('http://studio.test/**',async route=>{
const url=new URL(route.request().url()),path=url.pathname;
if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(FIXTURE+'/index.html','utf8')});
if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
if(path==='/clip.mp4')return route.fulfill({path:FIXTURE+'/clip.mp4',contentType:'video/mp4'});
if(route.request().method()==='POST')requests.push(path);
let data={};
if(path.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[{id:'clip1',name:'Teste horizontal',video_url:'/clip.mp4'}]:[1,2,3,4,5,6,7,8,9].map(lib)};
if(path.endsWith('/agent/storyboard/beat')){const body=JSON.parse(route.request().postData());beatCalls.push(body);data={beat:{id:body.beats[body.index].id,purpose:'beat',visual:'Roteador novo sobre a mesa',motion:'dolly',hold:'oferta',transition:'cut',spoken:'500 mega'},warnings:[]};}
if(path.endsWith('/agent/storyboard/image')){const body=JSON.parse(route.request().postData());if(body.dry_run)data={credits_per_image:120};else{imageCalls.push(body);if(failImage)return route.fulfill({status:400,json:{success:false,error:'Falha de rede simulada.'}});imageSeq++;data={image_url:'/static/images/canais/prime-video.svg?n='+imageSeq,scene_id:'p'+imageSeq,run_id:'run-1',charged_credits:120};}}
if(path.endsWith('/agent/storyboard')){data={beats:[{id:'beat-1',purpose:'hook',visual:'Família na sala',motion:'push-in',hold:'logo',transition:'cut',spoken:'Olá'},{id:'beat-2',purpose:'offer',visual:'Roteador em destaque',motion:'zoom',hold:'oferta',transition:'cut',spoken:'500 mega'},{id:'beat-3',purpose:'end',visual:'Logo final',motion:'pull-back',hold:'logo',transition:'cut',spoken:'Fale com a gente'}],warnings:[]};}
if(path.endsWith('/swap/animate/quote'))data={estimated_tokens:1000,voiceover_fits:true};
if(path.endsWith('/clips'))data={items:[]};
if(path.endsWith('/sounds'))data={items:JSON.parse(fs.readFileSync('aicentralv2/static/audio/studio/catalog.json'))};
if(path.endsWith('/projects'))data=route.request().method()==='POST'?{id:'project',revision:1,document:JSON.parse(route.request().postData()).document}:{items:[]};
if(path.endsWith('/video-project'))data={project:{active_clip_id:'clip1'}};
if(path.endsWith('/inspect')||path.endsWith('/tasks'))data={has_audio:true,waveform:[.3,.8,.2],frames:[]};
if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8,12],qualities:{draft:'720p',production:'720p'},skills:{}};
return route.fulfill({json:{success:true,data}});
});
await page.goto('http://studio.test/?client=1&clip=clip1');
await page.waitForFunction(()=>document.querySelector('#mcSwapVideo')?.videoWidth===320);
await page.evaluate(async()=>{window.__S=(await import('/static/js/cadu-video/state.js')).state;});
// monta 3 cenas: rascunho + peças da biblioteca
await page.fill('#mcVideoBriefing','Anúncio de internet fibra para famílias, 500 mega, fale com a gente.');
await page.click('#mcVideoDraftBtn');
await page.waitForFunction(()=>document.querySelectorAll('#mcVideoDraft .mc-draft-card').length===3);
await page.click('#mcVideoDraftGenerate');
await page.waitForFunction(()=>document.querySelectorAll('#mcVideoDraft .mc-draft-card').length===0&&document.querySelectorAll('#mcVideoSceneCards .mc-scene-card').length===3);
imageCalls.length=0;
const scenes=()=>page.evaluate(async()=>{const {state,beatFor}=await import('/static/js/cadu-video/state.js');return state.scenes.map(s=>({id:s.id,visual:beatFor(s.id)?.visual,spoken:beatFor(s.id)?.spoken}))});
const before=await scenes();
// ---- Fase 3: reescrever só o texto da cena 2 ----
await page.locator('#mcVideoSceneCards [data-card-action="rewrite"]').nth(1).click();
await page.waitForFunction(()=>document.querySelector('#mcVideoSceneCards [data-card-action="undo-text"]'));
assert.equal(beatCalls.length,1);assert.equal(beatCalls[0].index,1);assert.equal(beatCalls[0].beats.length,3);assert.equal(beatCalls[0].instruction,'mais direto');assert.match(beatCalls[0].briefing,/internet fibra/);
let now=await scenes();
assert.equal(now[1].visual,'Roteador novo sobre a mesa');assert.equal(now[0].visual,before[0].visual);assert.equal(now[2].visual,before[2].visual);assert.deepEqual(now.map(s=>s.id),before.map(s=>s.id),'a imagem não muda ao reescrever o texto');
await page.locator('#mcVideoSceneCards [data-card-action="undo-text"]').click();
now=await scenes();assert.equal(now[1].visual,before[1].visual);assert.equal(await page.locator('#mcVideoSceneCards [data-card-action="undo-text"]').count(),0);
// ---- Fase 3: gerar nova imagem só da cena 2 (queda de rede reaproveita o mesmo request_id) ----
failImage=true;
await page.locator('#mcVideoSceneCards [data-card-action="regen-image"]').nth(1).click();
await page.waitForFunction(()=>/Falha de rede simulada/.test(document.body.innerText));
failImage=false;
await page.locator('#mcVideoSceneCards [data-card-action="regen-image"]').nth(1).click();
await page.waitForFunction(()=>window.__S.scenes[1].id==='p4');
assert.equal(imageCalls.length,2);assert.equal(imageCalls[0].request_id,imageCalls[1].request_id,'repetir o mesmo pedido reaproveita o id');
assert.equal(imageCalls[1].index,1);assert.equal(imageCalls[1].total,3);assert.match(imageCalls[1].anchor_url,/prime-video\.svg\?n=1$/,'o estilo vem da 1ª cena');
assert.equal(imageCalls[1].beat.visual,before[1].visual);
now=await scenes();assert.equal(now[1].id,'p4');assert.equal(now[1].spoken,before[1].spoken,'o roteiro da cena é mantido');assert.equal(now[0].id,before[0].id);assert.equal(now[2].id,before[2].id);
assert.ok(dialogs.some(d=>d.type==='confirm'&&/nova imagem para a cena 2/.test(d.message)));
// próximo clique = id novo (variação diferente)
await page.locator('#mcVideoSceneCards [data-card-action="regen-image"]').nth(1).click();
await page.waitForFunction(()=>window.__S.scenes[1].id==='p5');
assert.equal(imageCalls.length,3);assert.notEqual(imageCalls[2].request_id,imageCalls[1].request_id);
// ---- Fase 4: checagem ----
await page.click('[data-panel-tab="seedance"]');
await page.waitForFunction(()=>document.querySelector('#mcVideoChecks')&&!document.querySelector('#mcVideoChecks').hidden);
const generate=page.locator('#mcVideoGenerate');
await page.waitForFunction(()=>!document.querySelector('#mcVideoGenerate').disabled);
// aviso: fala longa na cena 3 -> confirma antes de gerar; cancelar não envia nada
await page.evaluate(async()=>{const {state,beatFor}=await import('/static/js/cadu-video/state.js');const {updateGenerateEnabled}=await import('/static/js/cadu-video/render.js');beatFor(state.scenes[2].id).spoken=Array.from({length:60},()=>'palavra').join(' ');updateGenerateEnabled();});
assert.match(await page.locator('#mcVideoChecks').innerText(),/aviso/);
assert.match(await page.locator('#mcVideoChecks').innerText(),/Cena 3: 60 palavras/);
dialogs=[];requests.length=0;
await page.evaluate(()=>{window.confirm=message=>{window.__confirm=message;return false;};});
await generate.click();await new Promise(r=>setTimeout(r,300));
assert.match(await page.evaluate(()=>window.__confirm),/Antes de gerar, há \d+ avisos?/);
assert.ok(!requests.some(p=>p.endsWith('/swap/animate')),'nada foi enviado depois de cancelar');
// erro: imagem indisponível bloqueia o botão e o clique no problema seleciona a cena
await page.evaluate(async()=>{const {state}=await import('/static/js/cadu-video/state.js');const {updateGenerateEnabled}=await import('/static/js/cadu-video/render.js');state.scenes[0].broken=true;updateGenerateEnabled();});
assert.equal(await generate.isDisabled(),true);
assert.match(await generate.getAttribute('title'),/Cena 1 sem imagem disponível/);
assert.match(await page.locator('#mcVideoChecks').innerText(),/bloqueia/);
await page.locator('#mcVideoChecks [data-check-scene]').first().click();
assert.equal(await page.evaluate(async()=>{const {state}=await import('/static/js/cadu-video/state.js');return state.selectedSceneId===state.scenes[0].id;}),true);
await page.screenshot({path:ARTIFACTS+'/regenerate-and-checks.png',fullPage:true});
assert.deepEqual(errors,[]);
console.log('PASS fase 3 e 4: reescrever/desfazer texto, nova imagem só da cena (id reaproveitado na retomada) e checagem que bloqueia ou avisa');
await browser.close();
})();
