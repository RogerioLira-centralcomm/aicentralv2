const {chromium,ensureEditorFixture,FIXTURE,ARTIFACTS}=require('./studio-browser.cjs');
ensureEditorFixture();
const fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const posted=[];const images=[];let failOn=0;
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('http://studio.test/**',async route=>{
const url=new URL(route.request().url()),path=url.pathname;
if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(FIXTURE+'/index.html','utf8')});
if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
if(path==='/clip.mp4')return route.fulfill({path:FIXTURE+'/clip.mp4',contentType:'video/mp4'});
let data={};
if(path.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[{id:'clip1',name:'Teste horizontal',video_url:'/clip.mp4'}]:[1,2,3,4,5].map(n=>({id:'p'+n,name:'Peça '+n,image_url:'/static/images/canais/prime-video.svg',thumb_url:'/static/images/canais/prime-video.svg'}))};
if(path.endsWith('/agent/storyboard/image')){const body=JSON.parse(route.request().postData());if(body.dry_run)data={credits_per_image:120};else{images.push(body);if(failOn&&images.length===failOn)return route.fulfill({status:400,json:{success:false,error:'Saldo insuficiente.'}});const n=images.length;data={image_url:'/static/images/canais/prime-video.svg?n='+n,scene_id:'p'+n,run_id:'run-1',charged_credits:120};}}
if(path.endsWith('/agent/storyboard')){posted.push(JSON.parse(route.request().postData()));data={beats:[{id:'beat-1',purpose:'hook',visual:'Família na sala',motion:'push-in',hold:'logo',transition:'cut',spoken:'Olá'},{id:'beat-2',purpose:'offer',visual:'Roteador em destaque',motion:'zoom',hold:'oferta',transition:'cross dissolve',spoken:'500 mega'},{id:'beat-3',purpose:'end',visual:'Logo final',motion:'pull-back',hold:'logo',transition:'cut',spoken:'Fale com a gente'}],warnings:[]};}
if(path.endsWith('/clips'))data={items:[]};
if(path.endsWith('/sounds'))data={items:JSON.parse(fs.readFileSync('aicentralv2/static/audio/studio/catalog.json'))};
if(path.endsWith('/projects'))data=route.request().method()==='POST'?{id:'project',revision:1,document:JSON.parse(route.request().postData()).document}:{items:[]};
if(path.endsWith('/video-project'))data={project:{active_clip_id:'clip1'}};
if(path.endsWith('/inspect')||path.endsWith('/tasks'))data={has_audio:true,waveform:[.3,.8,.2],frames:Array.from({length:8},(_,i)=>({time:i*.3,url:'/static/images/canais/prime-video.svg'}))};
if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p',production:'720p'},skills:{}};
return route.fulfill({json:{success:true,data}});
});
page.on('dialog',d=>d.accept());
await page.goto('http://studio.test/?client=1&clip=clip1');
await page.waitForFunction(()=>document.querySelector('#mcSwapVideo').videoWidth===320);
await page.fill('#mcVideoBriefing','Anúncio de internet fibra para famílias, 500 mega, fale com a gente.');
await page.click('#mcVideoDraftBtn');
await page.waitForFunction(()=>document.querySelectorAll('#mcVideoDraft .mc-draft-card').length===3);
// 2ª imagem falha: para, mantém a 1ª e mostra o erro
failOn=2;
await page.click('#mcVideoDraftGenerate');
await page.waitForFunction(()=>document.querySelector('#mcVideoDraft .mc-draft-error'));
let state1=await page.evaluate(async()=>{const {state}=await import('/static/js/cadu-video/state.js');return {scenes:state.scenes.map(s=>s.id),draft:state.draft.beats.map(b=>b.id),req:state.draft.beats[0].request_id,err:state.draft.beats[0].error,gen:state.draft.generating};});
console.log(JSON.stringify(state1));
assert.deepEqual(state1.scenes,['p1']); assert.deepEqual(state1.draft,['beat-2','beat-3']); assert.match(state1.err,/Saldo/); assert.equal(state1.gen,false);
// tentar de novo: reaproveita o mesmo request_id e termina as duas
const retriedId=state1.req; failOn=0;
await page.click('#mcVideoDraftGenerate');
await page.waitForFunction(()=>document.querySelectorAll('#mcVideoDraft .mc-draft-card').length===0);
const final=await page.evaluate(async()=>{const {state,beatFor}=await import('/static/js/cadu-video/state.js');return {scenes:state.scenes.map(s=>s.id),spoken:state.scenes.map(s=>beatFor(s.id)?.spoken),anchor:state.draft.anchorUrl};});
console.log(JSON.stringify(final)); console.log(JSON.stringify(images.map(i=>({req:i.request_id.length,anchor:i.anchor_url,index:i.index,total:i.total,aspect:i.aspect_ratio,run:i.run_id}))));
assert.deepEqual(final.scenes,['p1','p3','p4']); assert.deepEqual(final.spoken,['Olá','500 mega','Fale com a gente']);
assert.equal(images[0].anchor_url,'');
assert.ok(images.slice(1).every(i=>i.anchor_url.includes('prime-video.svg?n=1')));
assert.equal(images.length,4); // 1 ok + 1 falha + 2 ao tentar de novo
assert.equal(images[1].request_id,images[2].request_id); // a repetição reaproveita o pedido
assert.ok(images.every(i=>i.aspect_ratio==='16:9')); // o formato escolhido não muda com a 1ª imagem
await page.screenshot({path:ARTIFACTS+'/draft-images.png',fullPage:true});
assert.deepEqual(errors,[]);
console.log('PASS imagens por cena: ordem, referência de estilo, parada no erro e retomada sem repetir pedido');
await browser.close();
})();
