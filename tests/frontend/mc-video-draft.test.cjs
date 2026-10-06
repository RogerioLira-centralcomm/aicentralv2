const {chromium,ensureEditorFixture,FIXTURE,ARTIFACTS}=require('./studio-browser.cjs');
ensureEditorFixture();
const fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const posted=[];
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('http://studio.test/**',async route=>{
const url=new URL(route.request().url()),path=url.pathname;
if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(FIXTURE+'/index.html','utf8')});
if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
if(path==='/clip.mp4')return route.fulfill({path:FIXTURE+'/clip.mp4',contentType:'video/mp4'});
let data={};
if(path.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[{id:'clip1',name:'Teste horizontal',video_url:'/clip.mp4'}]:[1,2,3].map(n=>({id:'p'+n,name:'Peça '+n,image_url:'/static/images/canais/prime-video.svg',thumb_url:'/static/images/canais/prime-video.svg'}))};
if(path.endsWith('/agent/storyboard')){posted.push(JSON.parse(route.request().postData()));data={beats:[{id:'beat-1',purpose:'hook',visual:'Família na sala',motion:'push-in',hold:'logo',transition:'cut',spoken:'Olá'},{id:'beat-2',purpose:'offer',visual:'Roteador em destaque',motion:'zoom',hold:'oferta',transition:'cross dissolve',spoken:'500 mega'},{id:'beat-3',purpose:'end',visual:'Logo final',motion:'pull-back',hold:'logo',transition:'cut',spoken:'Fale com a gente'}],warnings:[]};}
if(path.endsWith('/clips'))data={items:[]};
if(path.endsWith('/sounds'))data={items:JSON.parse(fs.readFileSync('aicentralv2/static/audio/studio/catalog.json'))};
if(path.endsWith('/projects'))data=route.request().method()==='POST'?{id:'project',revision:1,document:JSON.parse(route.request().postData()).document}:{items:[]};
if(path.endsWith('/video-project'))data={project:{active_clip_id:'clip1'}};
if(path.endsWith('/inspect')||path.endsWith('/tasks'))data={has_audio:true,waveform:[.3,.8,.2],frames:Array.from({length:8},(_,i)=>({time:i*.3,url:'/static/images/canais/prime-video.svg'}))};
if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p',production:'720p'},skills:{}};
return route.fulfill({json:{success:true,data}});
});
await page.goto('http://studio.test/?client=1&clip=clip1');
await page.waitForFunction(()=>document.querySelector('#mcSwapVideo')?.videoWidth===320);
await page.fill('#mcVideoBriefing','Anúncio de internet fibra para famílias, 500 mega, fale com a gente.');
await page.click('#mcVideoDraftBtn');
await page.waitForFunction(()=>document.querySelectorAll('#mcVideoDraft .mc-draft-card').length===3);
assert.equal(posted.length,1); assert.match(posted[0].briefing,/internet fibra/); assert.ok(posted[0].request_id);
// editar um campo não recria a lista nem perde o foco
await page.fill('[data-draft="beat-2"] [data-draft-field="spoken"]','500 mega por setenta e nove');
// reordenar
await page.click('[data-draft="beat-3"] [data-draft-action="up"]');
let order=await page.$$eval('#mcVideoDraft .mc-draft-card',n=>n.map(x=>x.dataset.draft));
assert.deepEqual(order,['beat-1','beat-3','beat-2']);
// escolher peça: o beat vira cena e leva o roteiro
await page.click('[data-draft="beat-2"] [data-draft-action="pick"]');
await page.waitForSelector('#mcVideoLibrary [data-action]');
await page.click('#mcVideoLibrary [data-id="p1"]');
const out=await page.evaluate(async()=>{
  const {state,beatFor}=await import('/static/js/cadu-video/state.js');
  return {scenes:state.scenes.map(s=>s.id),draft:state.draft.beats.map(b=>b.id),beat:beatFor('p1'),pick:state.pickDraftId,saved:null};
});
console.log(JSON.stringify(out));
assert.deepEqual(out.scenes,['p1']); assert.deepEqual(out.draft,['beat-1','beat-3']);
assert.equal(out.beat.spoken,'500 mega por setenta e nove'); assert.equal(out.beat.visual,'Roteador em destaque'); assert.equal(out.beat.transition,'cross dissolve');
assert.equal(out.pick,'');
await page.screenshot({path:ARTIFACTS+'/draft.png',fullPage:true});
assert.deepEqual(errors,[]);
console.log('PASS rascunho: briefing monta cartões; editar, reordenar e ligar peça preservam o roteiro');
await browser.close();
})();
