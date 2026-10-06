const {chromium,ensureHomeFixture,HOME_FIXTURE,ARTIFACTS}=require('./studio-browser.cjs');
const fs=require('fs');
const { execFileSync } = require('node:child_process');
ensureHomeFixture();
execFileSync(process.env.PYTHON || 'python3', ['tests/frontend/render-studio-fixture.py']); const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {})}); const page=await browser.newPage({viewport:{width:1440,height:1050}}); const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let videoFail=false;let clientFail=false;const counts={};
 await page.route('http://studio.test/**',async route=>{const url=new URL(route.request().url());counts[url.pathname+url.search]=(counts[url.pathname+url.search]||0)+1;
 if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(HOME_FIXTURE+'/rendered.html','utf8')});
 if(url.pathname.startsWith('/static/'))return route.fulfill({path:'aicentralv2'+url.pathname});
 // O contexto do Studio passou a ser projeto + marca (project-contexts), não a lista de marcas.
 if(url.pathname.endsWith('/studio/project-contexts'))return route.fulfill({status:clientFail?500:200,json:{data:{items:[{id:'pA',name:'Projeto A',client_id:'A',brand_name:'TIM CELULAR S.A.'},{id:'pB',name:'Projeto B',client_id:'B',brand_name:'Z Marca B'}]}}});
 if(url.pathname.endsWith('/studio/library-sessions'))return route.fulfill({json:{data:{items:[],personal_assets:[]}}});
 if(url.pathname==='/workspace/api/creditos/resumo')return route.fulfill({json:{configured:true,available:200,monthly:500}});
 if(url.pathname.endsWith('/swap/library')){const video=url.searchParams.get('media')==='video';const client=url.searchParams.get('client_id');return route.fulfill({status:video&&videoFail?500:200,json:{data:{items:video?[]:Array.from({length:26},(_,i)=>({id:`${i}`,run_id:`run ${i}`,name:`${client} · Campanha ${i}`,headline:i===25?'Oferta especial fibra':'',aspect_ratio:'16:9',created_at:'2026-09-14',thumb_url:'/missing.png'}))}}});}
 return route.fulfill({status:404,body:''}); });
 await page.goto('http://studio.test/'); await page.getByText('12 de 26 ativo(s).',{exact:false}).waitFor();
 assert.equal(counts['/parametros/api/format-lab/swap/library?client_id=A&media=still'],1);
 assert.equal(await page.locator('.studio-card').count(),12);
 await page.getByRole('button',{name:'Mostrar mais'}).click();assert.equal(await page.locator('.studio-card').count(),24);
 await page.getByRole('searchbox').fill('oferta especial');assert.equal(await page.locator('.studio-card').count(),1);
 assert.match(await page.locator('.studio-card a.studio-card-action').getAttribute('href'),/client=A/);
 await page.getByRole('searchbox').fill('');await page.getByLabel('Projeto ativo').selectOption('pB');await page.getByText('60% usado',{exact:true}).first().waitFor();await page.locator('.studio-card strong').first().filter({hasText:'B'}).waitFor();
 assert.match(await page.locator('.studio-card a.studio-card-action').first().getAttribute('href'),/client=B/);
 // O saldo agora vem da navbar única do Studio (Saldo + % usado), não do #mcCaduCredits legado.
 await page.waitForTimeout(100);assert.match(await page.locator('body').innerText(),/Saldo 200[\s\S]*60% usado/);
 await page.screenshot({path:ARTIFACTS+'/home-desktop.png',fullPage:true});
 for (const width of [1024,768,390]) { await page.setViewportSize({width,height:844}); assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow em ${width}px`); }assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:ARTIFACTS+'/home-mobile.png',fullPage:true});
 videoFail=true;await page.getByRole('button',{name:'Atualizar',exact:true}).click();await page.locator('.studio-error[role=alert]').waitFor();assert.equal(await page.locator('.studio-card').count(),12);
 videoFail=false;await page.getByRole('button',{name:'Tentar novamente'}).click();await page.locator('.studio-error[role=alert]').waitFor({state:'detached'});
 await page.evaluate(()=>document.dispatchEvent(new CustomEvent('cadu:credits-refresh',{detail:{clientId:'A'}})));assert.equal(await page.getByLabel('Projeto ativo').inputValue(),'pB');
 clientFail=true;await page.evaluate(()=>document.dispatchEvent(new CustomEvent('cadu:context-retry')));await page.getByText('Marcas indisponíveis',{exact:true}).waitFor();assert.equal(await page.locator('.studio-card').count(),0);
 clientFail=false;await page.getByRole('button',{name:'Atualizar',exact:true}).click();await page.locator('.studio-card').first().waitFor();
 assert.deepEqual(errors,[]);console.log('PASS: Jinja render, initial request deduplication, more, search, brand links, credits, 390px overflow, partial error/retry, context retry; no JS errors.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
