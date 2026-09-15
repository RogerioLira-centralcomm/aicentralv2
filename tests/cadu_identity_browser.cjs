const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {chromium}=require(path.join(process.env.CADU_NODE_MODULES,'playwright'));
const sharp=require(path.join(process.env.CADU_NODE_MODULES,'sharp'));
(async()=>{
 const root=path.resolve(__dirname,'../output/mockups'),out=path.resolve(__dirname,'../output/cadu-validation');await fs.mkdir(out,{recursive:true});
 const families=['workspace','studio','connect','skills','planner'],sizes=[16,20,24,32,40,48,64,96,128,192,512,1024];
 for(const family of families)for(const size of sizes){const meta=await sharp(path.join(root,'brand-assets/icons-2d',family,`icon-${size}.png`)).metadata();assert.equal(meta.width,size);assert.equal(meta.height,size);assert.equal(meta.hasAlpha,true);}
 const browser=await chromium.launch({headless:true,channel:'chrome'}),page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const width of [1440,1024,768,390]){
  await page.setViewportSize({width,height:1000});
  for(const family of families){await page.goto(pathToFileURL(path.join(root,'cadu-family-design-system.html')).href+'#'+family);await page.locator('.master-stage img').waitFor();await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete));assert.deepEqual(await page.locator('img').evaluateAll(imgs=>imgs.filter(i=>!i.naturalWidth).map(i=>i.src)),[]);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);if(width===1440||width===390)await page.screenshot({path:path.join(out,`identity-${family}-${width}.png`),fullPage:true});}
 }
 await page.setViewportSize({width:1200,height:900});await page.goto(pathToFileURL(path.join(root,'cadu-family-design-system.html')).href);await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete));await page.locator('#all-symbols').screenshot({path:path.join(root,'brand-assets/icons-2d/family-preview.png')});
 await page.goto(pathToFileURL(path.join(root,'cadu-platform.html')).href+'#studio');await page.locator('#product-switch summary').click();await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete));await page.locator('#product-switch .popup').screenshot({path:path.join(out,'product-switch-2d.png')});assert.equal(await page.locator('.product-symbol').count(),5);
 assert.deepEqual(errors,[]);console.log('PASS: 60 PNG sizes/alpha, 20 responsive identity pages, 5 product-menu symbols, no broken images or JS errors.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
