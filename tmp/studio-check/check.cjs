const {chromium}=require('/Users/apololira/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'); const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}); const page=await browser.newPage({viewport:{width:1440,height:1050}}); const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let videoFail=false;let clientFail=false;const counts={};
 await page.route('http://studio.test/**',async route=>{const url=new URL(route.request().url());counts[url.pathname+url.search]=(counts[url.pathname+url.search]||0)+1;
 if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('tmp/studio-check/rendered.html','utf8')});
 if(url.pathname.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+url.pathname});
 if(url.pathname.endsWith('/clients'))return route.fulfill({status:clientFail?500:200,json:{data:[{id:'A',name:'TIM CELULAR S.A.',primary_color:'#123'},{id:'B',name:'Z Marca B',primary_color:'#456'}]}});
 if(url.pathname.endsWith('/image-credits'))return route.fulfill({json:{data:{remaining:url.searchParams.get('client_id')==='A'?500:200}}});
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
 await page.screenshot({path:'tmp/studio-check/desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:'tmp/studio-check/mobile.png',fullPage:true});
 videoFail=true;await page.getByRole('button',{name:'Atualizar',exact:true}).click();await page.getByRole('alert').waitFor();assert.equal(await page.locator('.studio-card').count(),12);
 videoFail=false;await page.getByRole('button',{name:'Tentar novamente'}).click();await page.getByRole('alert').waitFor({state:'detached'});
 await page.evaluate(()=>document.dispatchEvent(new CustomEvent('cadu:credits-refresh',{detail:{clientId:'A'}})));assert.equal(await page.getByLabel('Marca desta sessão').inputValue(),'B');
 clientFail=true;await page.evaluate(()=>document.dispatchEvent(new CustomEvent('cadu:context-retry')));await page.getByText('Marcas indisponíveis',{exact:true}).waitFor();assert.equal(await page.locator('.studio-card').count(),0);
 clientFail=false;await page.getByRole('button',{name:'Atualizar',exact:true}).click();await page.locator('.studio-card').first().waitFor();
 assert.deepEqual(errors,[]);console.log('PASS: Jinja render, initial request deduplication, more, search, brand links, credits, 390px overflow, partial error/retry, context retry; no JS errors.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
