const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs');
const { execFileSync } = require('node:child_process');
fs.mkdirSync('tmp/studio-check', { recursive: true });
execFileSync(process.env.PYTHON || 'python3', ['tests/frontend/render-studio-fixture.py']); const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {})}); const page=await browser.newPage({viewport:{width:1440,height:1050}}); const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let videoFail=false;let clientFail=false;let delayedCredit;const counts={};
 await page.route('http://studio.test/**',async route=>{const url=new URL(route.request().url());counts[url.pathname+url.search]=(counts[url.pathname+url.search]||0)+1;
 if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('tmp/studio-check/rendered.html','utf8')});
 if(url.pathname.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+url.pathname});
 if(url.pathname.endsWith('/clients'))return route.fulfill({status:clientFail?500:200,json:{data:[{id:'A',name:'TIM CELULAR S.A.',primary_color:'#123'},{id:'B',name:'Z Marca B',primary_color:'#456'}]}});
 if(url.pathname.endsWith('/image-credits')) { if (url.searchParams.get('client_id')==='A') { delayedCredit=route; return; } return route.fulfill({json:{data:{remaining:200}}}); }
 if(url.pathname.endsWith('/swap/library')){const video=url.searchParams.get('media')==='video';const client=url.searchParams.get('client_id');return route.fulfill({status:video&&videoFail?500:200,json:{data:{items:video?[]:Array.from({length:26},(_,i)=>({id:`${i}`,run_id:`run ${i}`,name:`${client} · Campanha ${i}`,headline:i===25?'Oferta especial fibra':'',aspect_ratio:'16:9',created_at:'2026-09-14',thumb_url:'/missing.png'}))}}});}
 return route.fulfill({status:404,body:''}); });
 await page.goto('http://studio.test/'); await page.getByText('12 de 26 resultado(s).',{exact:false}).waitFor();
 assert.equal(counts['/parametros/api/format-lab/swap/library?client_id=A&media=still'],1);
 assert.equal(await page.locator('.studio-card').count(),12);
 await page.getByRole('button',{name:'Mostrar mais'}).click();assert.equal(await page.locator('.studio-card').count(),24);
 await page.getByRole('searchbox').fill('oferta especial');assert.equal(await page.locator('.studio-card').count(),1);
 assert.match(await page.locator('.studio-card a').getAttribute('href'),/client=A/);
 await page.getByRole('searchbox').fill('');await page.getByLabel('Marca desta sessão').selectOption('B');await page.getByText('200 créditos',{exact:true}).waitFor();await page.locator('.studio-card strong').first().filter({hasText:'B'}).waitFor();
 assert.match(await page.locator('.studio-card a').first().getAttribute('href'),/client=B/);
 await delayedCredit.fulfill({json:{data:{remaining:500}}});await page.waitForTimeout(100);assert.equal(await page.locator('#mcCaduCredits').textContent(),'200 créditos');
 await page.screenshot({path:'tmp/studio-check/desktop.png',fullPage:true});
 for (const width of [1024,768,390]) { await page.setViewportSize({width,height:844}); assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow em ${width}px`); }assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:'tmp/studio-check/mobile.png',fullPage:true});
 videoFail=true;await page.getByRole('button',{name:'Atualizar',exact:true}).click();await page.getByRole('alert').waitFor();assert.equal(await page.locator('.studio-card').count(),12);
 videoFail=false;await page.getByRole('button',{name:'Tentar novamente'}).click();await page.getByRole('alert').waitFor({state:'detached'});
 await page.evaluate(()=>document.dispatchEvent(new CustomEvent('cadu:credits-refresh',{detail:{clientId:'A'}})));assert.equal(await page.getByLabel('Marca desta sessão').inputValue(),'B');
 clientFail=true;await page.evaluate(()=>document.dispatchEvent(new CustomEvent('cadu:context-retry')));await page.getByText('Marcas indisponíveis',{exact:true}).waitFor();assert.equal(await page.locator('.studio-card').count(),0);
 clientFail=false;await page.getByRole('button',{name:'Atualizar',exact:true}).click();await page.locator('.studio-card').first().waitFor();
 assert.deepEqual(errors,[]);console.log('PASS: Jinja render, initial request deduplication, more, search, brand links, credits, 390px overflow, partial error/retry, context retry; no JS errors.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
