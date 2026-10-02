// Criar → Vídeo: ?scenes= vindo do Criar monta o storyboard na ordem enviada.
const {chromium,ensureEditorFixture,FIXTURE,ARTIFACTS}=require('./studio-browser.cjs');
const fs=require('fs'),assert=require('node:assert/strict');
ensureEditorFixture();
const still=(id,name)=>({id,run_id:'run-1',version_id:id.split(':')[1],name,image_url:'/static/images/canais/prime-video.svg',thumb_url:'/static/images/canais/prime-video.svg',aspect_ratio:'16:9',created_at:'2026-10-02'});
const library=[still('run-1:v1','Abertura'),still('run-1:v2','Produto'),still('run-1:v3','Fecho'),still('run-0:v9','Outra peça')];
async function open(browser,query){
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://studio.test/**',async route=>{
    const url=new URL(route.request().url()),path=url.pathname;
    if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(FIXTURE+'/index.html','utf8')});
    if(path.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+path});
    let data={};
    if(path.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[]:library};
    if(path.endsWith('/clips')||path.endsWith('/projects'))data={items:[]};
    if(path.endsWith('/sounds'))data={items:[]};
    if(path.endsWith('/video-project'))data={project:{}};
    if(path.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p',production:'720p'},skills:{}};
    return route.fulfill({json:{success:true,data}});
  });
  await page.goto(`http://studio.test/?client=1${query}`);
  return {page,errors};
}
(async()=>{
  const browser=await chromium.launch({headless:true});
  const {page,errors}=await open(browser,'&scenes=run-1:v3,run-1:v1,run-1:v2&from=studio-create');
  await page.waitForFunction(()=>document.querySelectorAll('#mcVideoScenes [data-scene]').length===3);
  assert.deepEqual(await page.locator('#mcVideoScenes [data-scene]').evaluateAll(n=>n.map(e=>e.dataset.scene)),['run-1:v3','run-1:v1','run-1:v2']);
  assert.match(await page.locator('#mcAnimateStatus').textContent(),/3 cenas vieram do Criar/);
  assert.equal(new URL(page.url()).searchParams.get('scenes'),null,'o parâmetro scenes sai da URL depois de usado');
  await page.screenshot({path:ARTIFACTS+'/video-handoff.png',fullPage:true});
  const single=await open(browser,'&scenes=run-1:v2');
  await single.page.waitForFunction(()=>document.querySelectorAll('#mcVideoScenes [data-scene]').length===1);
  assert.match(await single.page.locator('#mcAnimateStatus').textContent(),/pronta para animar/);
  const missing=await open(browser,'&scenes=run-9:v1');
  await missing.page.waitForFunction(()=>/ainda não apareceram/.test(document.getElementById('mcAnimateStatus')?.textContent||''));
  assert.equal(await missing.page.locator('#mcVideoScenes [data-scene]').count(),0);
  assert.deepEqual([...errors,...single.errors,...missing.errors],[]);
  console.log('PASS Criar→Vídeo: ordem do storyboard, 1 cena = animar still, cena ausente avisa, URL limpa, sem erros de JS');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
