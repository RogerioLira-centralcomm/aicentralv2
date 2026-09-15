const {chromium}=require('/Users/apololira/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('http://studio.test/**',async route=>{
const url=new URL(route.request().url()),path=url.pathname;
if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('tmp/studio-editor-check/index.html','utf8')});
if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
if(path==='/clip.mp4')return route.fulfill({path:'tmp/studio-editor-check/clip.mp4',contentType:'video/mp4'});
let data={};
if(path.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[{id:'clip1',name:'Teste horizontal',video_url:'/clip.mp4'}]:[]};
if(path.endsWith('/clips'))data={items:[]};
if(path.endsWith('/sounds'))data={items:JSON.parse(fs.readFileSync('aicentralv2/static/audio/studio/catalog.json'))};
if(path.endsWith('/projects'))data=route.request().method()==='POST'?{id:'project',revision:1,document:JSON.parse(route.request().postData()).document}:{items:[]};
if(path.endsWith('/video-project'))data={project:{active_clip_id:'clip1'}};
if(path.endsWith('/inspect')||path.endsWith('/tasks'))data={has_audio:true,waveform:[.3,.8,.2],frames:Array.from({length:8},(_,i)=>({time:i*.3,url:'/static/images/canais/prime-video.svg'}))};
if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p',production:'720p'},skills:{}};
return route.fulfill({json:{success:true,data}});
});
await page.goto('http://studio.test/?client=1&clip=clip1');
await page.waitForFunction(()=>document.querySelector('#mcSwapVideo').videoWidth===320);
await page.waitForFunction(()=>document.querySelectorAll('#mcStudioFilmstrip img').length===8);
for(const width of [1440,1024,900,390]){
await page.setViewportSize({width,height:1000});
for(const name of ['scene','audio','video','seedance','agent']){
await page.locator(`[data-panel-tab="${name}"]`).click();
assert.equal(await page.locator('[data-panel-pane]:visible').count(),1);
const ys=await page.locator('[data-panel-tab]').evaluateAll(nodes=>nodes.map(n=>Math.round(n.getBoundingClientRect().y)));
assert.equal(new Set(ys).size,1,`tabs wrap at ${width}`);
}
}
await page.setViewportSize({width:1440,height:1000});await page.locator('[data-panel-tab="video"]').click();
await page.locator('#mcStudioAddText').click();await page.getByRole('textbox',{name:'Texto 1',exact:true}).fill('Oferta especial');
await page.locator('#mcStudioMuteOriginal').click();assert.equal(await page.locator('#mcSwapVideo').evaluate(v=>v.volume),0);
await page.locator('[data-lib-tab="sound"]').click();assert.equal(await page.locator('#mcStudioSoundList article').count(),100);
assert.equal(await page.locator('#mcSwapVideo').evaluate(v=>getComputedStyle(v).objectFit),'contain');
await page.evaluate(()=>document.dispatchEvent(new CustomEvent('cadu:clip-imported',{detail:{id:'clip2',name:'Segundo vídeo',video_url:'/clip.mp4'}})));
await page.locator('[data-lib-tab="video"]').click();await page.locator('[data-action="play"][data-clip="clip1"]').click();
assert.equal(await page.locator('#mcSwapVideo').evaluate(v=>v.volume),0);
assert.equal(await page.getByRole('textbox',{name:'Texto 1',exact:true}).inputValue(),'Oferta especial');
await page.screenshot({path:'tmp/studio-editor-check/editor.png',fullPage:true});
assert.deepEqual(errors,[]);console.log('PASS tabs 390–1440px, filmstrip, text, mute, 100 sounds, contain, no JS errors');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
