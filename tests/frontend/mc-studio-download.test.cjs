const {chromium}=require('/Users/apololira/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true}),errors=[],jobs=new Map();page.on('pageerror',e=>errors.push(e.message));
 await page.route('http://studio.test/**',async route=>{
  const url=new URL(route.request().url()),p=url.pathname;
  if(p==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('tmp/studio-editor-check/index.html','utf8')});
  if(p.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+p});
  if(p==='/clip.mp4'||(p.includes('/exports/')&&p.endsWith('/content')&&url.searchParams.get('inline')==='1'))return route.fulfill({path:'tmp/studio-editor-check/clip.mp4',contentType:'video/mp4'});
  if(p.includes('/exports/')&&p.endsWith('/content')){const job=jobs.get(p.split('/').at(-2));return route.fulfill({status:200,contentType:'application/octet-stream',headers:{'Content-Disposition':`attachment; filename="${job.filename}"`},body:Buffer.from('exported test file')});}
  let data={};
  if(p.endsWith('/swap/library'))data={items:url.searchParams.get('media')==='video'?[{id:'clip1',name:'Oferta',duration:3,video_url:'/clip.mp4'}]:[]};
  if(p.endsWith('/clips')||p.endsWith('/sounds')||p.endsWith('/jobs'))data={items:[],exports:[]};
  if(p.endsWith('/projects'))data=route.request().method()==='POST'?{id:'project',revision:1,document:JSON.parse(route.request().postData()).document}:{items:[]};
  if(p.endsWith('/video-project'))data={project:{active_clip_id:'clip1'}};
  if(p.endsWith('/tasks'))data={has_audio:true,waveform:[],frames:[]};
  if(p.endsWith('/capabilities'))data={model:'seedance',durations:[4,8],qualities:{draft:'720p'},skills:{}};
  if(p.endsWith('/exports')){const body=JSON.parse(route.request().postData()),format=body.delivery.format;assert.equal(body.delivery.creative,'Oferta especial');data={id:body.request_id,status:'queued'};jobs.set(body.request_id,{id:body.request_id,status:'ready',created:Date.now(),format,filename:`marca_v001_oferta_especial_9x16.${format}`,download_url:`/parametros/api/format-lab/studio/exports/${body.request_id}/content?client_id=1&format=${format}`});}
  else if(p.includes('/exports/')){data=jobs.get(p.split('/').at(-1));if(Date.now()-data.created<1800)data={...data,status:'rendering'};}
  return route.fulfill({json:{success:true,data}});
 });
 await page.goto('http://studio.test/?client=1&clip=clip1');await page.waitForFunction(()=>document.querySelector('#mcSwapVideo').videoWidth===320);
 await page.locator('#mcVideoName').fill('Oferta especial');await page.locator('#mcVideoName').dispatchEvent('change');
 for(const format of ['mp4','gif','html']){
  const download=page.waitForEvent('download');await page.locator('#mcStudioExportFormat').selectOption(format);
  await page.waitForFunction(()=>document.querySelector('#mcStudioExportFormat').selectedOptions[0].textContent.includes('00:01'));
  assert.equal(await page.locator('#mcStudioExportFormat').getAttribute('aria-busy'),'true');
  if(format==='mp4')await page.screenshot({path:'tmp/studio-editor-check/download-progress.png',fullPage:true});
  const file=await download;
  assert.equal(file.suggestedFilename(),`marca_v001_oferta_especial_9x16.${format}`);
  assert.equal(await page.locator('#caduProcessing a').filter({hasText:'Baixar'}).count(),0);
  assert.equal(await page.locator('#mcStudioExportStatus a').count(),0);
  assert.equal(await page.locator('#mcStudioExportFormat').getAttribute('aria-busy'),'false');
 }
 assert.equal(jobs.size,3);assert.deepEqual(errors,[]);console.log('PASS automatic MP4/GIF/HTML downloads, creative metadata, correct filenames, loading spinner and elapsed timer, no footer download links');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
