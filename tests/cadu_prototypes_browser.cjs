/* Run with CADU_NODE_MODULES pointing to an installation containing playwright. */
const {chromium}=require(require('node:path').join(process.env.CADU_NODE_MODULES||'../node_modules','playwright'));
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.CADU_BROWSER_CHANNEL||'chrome'});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const root=path.resolve(__dirname,'../output/mockups');const out=path.resolve(__dirname,'../output/cadu-validation');fs.mkdirSync(out,{recursive:true});
 const url=name=>pathToFileURL(path.join(root,name)).href;
 const routes=['workspace','studio','connect','skills','planner','plans','credits','skills-private','integrations','ecosystem','studio-library','studio-edit','connect-reports','planner-objectives'];
 const checks=[];
 for(const width of [1440,1024,768,390]){
  await page.setViewportSize({width,height:1000});
  for(const route of routes){
   await page.goto(url('cadu-platform.html')+'#'+route);await page.locator('#main h1').waitFor();
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false,route+' overflow at '+width);
   const broken=await page.locator('img').evaluateAll(images=>images.filter(i=>i.complete&&i.naturalWidth===0).map(i=>i.src));assert.deepEqual(broken,[]);
   if(['workspace','studio','connect','skills','planner','plans'].includes(route))await page.screenshot({path:path.join(out,route+'-'+width+'.png'),fullPage:true});
   checks.push({route,width,overflow,broken});
  }
  await page.goto(url('cadu-commercial-model.html'));await page.locator('#title-0').waitFor();
  for(let i=0;i<12;i++){
   await page.locator('[data-slide="'+i+'"]').click();
   assert.equal(await page.locator('.slide:not([hidden])').count(),1);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'slide '+i+' overflow at '+width);
  }
  await page.locator('[data-slide="9"]').click();await page.screenshot({path:path.join(out,'dre-'+width+'.png'),fullPage:true});
 }
 await page.setViewportSize({width:390,height:844});
 await page.goto(url('cadu-platform.html')+'#workspace');
 await page.locator('#product-switch summary').focus();await page.keyboard.press('Enter');assert.equal(await page.locator('#product-switch').getAttribute('open'),'');await page.keyboard.press('Escape');assert.equal(await page.locator('#product-switch').getAttribute('open'),null);assert.equal(await page.locator('#product-switch summary').evaluate(el=>el===document.activeElement),true);
 await page.locator('[data-action="step"][data-step="2"]').click();assert.match(await page.locator('.onboard').innerText(),/3 de 3/);await page.locator('[data-action="dismiss"]').click();assert.equal(await page.locator('.onboard').count(),0);await page.locator('[data-action="onboard-reset"]').click();assert.equal(await page.locator('.onboard').count(),1);
 await page.locator('#context-switch summary').click();await page.locator('#organization').selectOption('Agência exemplo');await page.locator('#brand').selectOption('Marca demonstração');
 await page.locator('#product-switch summary').click();await page.locator('.product-link[href="#studio"]').click();
 assert.equal(await page.locator('#organization').inputValue(),'Agência exemplo');assert.equal(await page.locator('#brand').inputValue(),'Marca demonstração');
 await page.locator('[data-action="menu"]').click();assert.equal(await page.locator('[data-action="menu"]').getAttribute('aria-expanded'),'true');
 await page.locator('#local-nav a[href="#studio-edit"]').click();await page.getByRole('heading',{name:'Editar uma peça',exact:true}).waitFor();await page.locator('[data-action="edit"]').click();assert.match(await page.locator('#modal').innerText(),/Continue no desktop/);await page.locator('.close').click();
 await page.goto(url('cadu-platform.html')+'#credits');await page.locator('[data-action="quote-image"]').click();await page.locator('[data-action="reserve"]').click();await page.locator('[data-action="settle-fail"]').click();assert.match(await page.locator('#main').innerText(),/Estornado/);assert.match(await page.locator('#main').innerText(),/1\.500|1500/);
 await page.goto(url('cadu-platform.html')+'#skills');await page.locator('#skill-search').fill('relatório');assert.match(await page.locator('#skill-results').innerText(),/Leitura de relatório/);assert.doesNotMatch(await page.locator('#skill-results').innerText(),/Direção de criativo/);
 await page.goto(url('cadu-platform.html')+'#skills-private');await page.locator('[name="name"]').fill('Skill local de teste');await page.getByRole('button',{name:'Salvar versão local'}).click();assert.match(await page.locator('#main').innerText(),/Versão 2/);await page.locator('[data-action="skill-preview"]').click();assert.match(await page.locator('#modal').innerText(),/Skill local de teste/);await page.locator('.close').click();
 await page.goto(url('cadu-platform.html')+'#plans');await page.locator('#billing').selectOption('annual');await page.locator('#annual-discount').fill('20');assert.match(await page.locator('#plan-options').innerText(),/6.00×/);
 await page.goto(url('cadu-commercial-model.html')+'#10');await page.locator('[data-field="fx"]').fill('0');assert.equal(await page.locator('#calc-error').isVisible(),true);await page.locator('[data-field="fx"]').fill('6.25');assert.equal(await page.locator('#calc-error').isVisible(),false);
 await page.goto(url('cadu-components-v2.html'));for(const theme of ['hub','studio','connect','skills','planner'])await page.locator('#theme').selectOption(theme);await page.locator('#confirm').click();assert.equal(await page.locator('dialog').isVisible(),true);
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({checks,errors,interactions:'passed'},null,2));console.log('PASS: '+checks.length+' responsive route checks, 48 slide checks, keyboard, onboarding, product/context, mobile editor, credits, Skills, plans, validation, components.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
