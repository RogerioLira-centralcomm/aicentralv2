// O provedor de vídeo barra o áudio gerado por possível direito autoral: mensagem clara e "Tentar sem áudio".
const {chromium,ensureEditorFixture,FIXTURE}=require('./studio-browser.cjs');
ensureEditorFixture();
const fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],quotes=[];
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>sessionStorage.setItem('cx-cadu-video-job','job-1'));
const message='O provedor bloqueou o áudio gerado por possível direito autoral (música ou som parecido com obra protegida). Gere de novo sem áudio ou mude a direção do som. [audio_bloqueado]';
await page.route('http://studio.test/**',async route=>{
const url=new URL(route.request().url()),path=url.pathname;
if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(FIXTURE+'/index.html','utf8')});
if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
if(path==='/clip.mp4')return route.fulfill({path:FIXTURE+'/clip.mp4',contentType:'video/mp4'});
let data={};
if(path.endsWith('/swap/animate/job-1'))data={status:'failed',job_id:'job-1',error:message,message,plan:{duration:8}};
if(path.endsWith('/swap/animate/quote')){quotes.push(JSON.parse(route.request().postData()||'{}'));data={estimated_tokens:1000,voiceover_fits:true};}
if(path.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[{id:'clip1',name:'Teste horizontal',video_url:'/clip.mp4'}]:[1,2].map(n=>({id:'p'+n,name:'Peça '+n,image_url:'/static/images/canais/prime-video.svg',thumb_url:'/static/images/canais/prime-video.svg'}))};
if(path.endsWith('/clips'))data={items:[]};
if(path.endsWith('/sounds'))data={items:JSON.parse(fs.readFileSync('aicentralv2/static/audio/studio/catalog.json'))};
if(path.endsWith('/projects'))data=route.request().method()==='POST'?{id:'project',revision:1,document:JSON.parse(route.request().postData()).document}:{items:[]};
if(path.endsWith('/video-project'))data={project:{active_clip_id:'clip1'}};
if(path.endsWith('/inspect')||path.endsWith('/tasks'))data={has_audio:true,waveform:[.3],frames:[]};
if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p',production:'720p'},skills:{}};
return route.fulfill({json:{success:true,data}});
});
await page.goto('http://studio.test/?client=1&clip=clip1');
await page.waitForSelector('#mcAnimateStatus .mc-status-action');
const text=await page.locator('#mcAnimateStatus').innerText();
assert.match(text,/bloqueou o áudio gerado por possível direito autoral/);
assert.doesNotMatch(text,/audio_bloqueado/,'o marcador técnico não aparece para a pessoa');
assert.equal(await page.evaluate(async()=>(await import('/static/js/cadu-video/state.js')).state.audio.enabled!==false),true);
await page.click('#mcAnimateStatus .mc-status-action');
assert.equal(await page.evaluate(async()=>(await import('/static/js/cadu-video/state.js')).state.audio.enabled),false,'o áudio foi desligado');
assert.match(await page.locator('#mcAnimateStatus').innerText(),/Áudio desligado\. Confira o custo/);
assert.equal(await page.locator('#mcAnimateStatus .mc-status-action').count(),0);
assert.equal(await page.locator('input[name="mcVideoAudioEnabled"][value="off"]').isChecked(),true);
assert.deepEqual(errors,[]);
console.log('PASS áudio bloqueado: mensagem clara, marcador escondido e "Tentar sem áudio" desliga o áudio sem gerar sozinho');
await browser.close();
})();
