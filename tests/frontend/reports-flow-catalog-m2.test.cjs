const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,'../../frontend/reports-v1/flowCatalogModel.js'),'utf8');
(async()=>{
  const {catalogSections}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const rows=[
    {id:'a',role:'entry',template_id:'cases',template_pattern:'/cases/*',locale:'pt'},
    {id:'b',role:'content',template_id:'cases',template_pattern:'/cases/*',locale:'en'},
    {id:'c',role:'none',template_id:null},
  ];
  const result=catalogSections(rows);
  assert.equal(result.groups.length,1);
  assert.deepEqual(result.groups[0].pages.map(page=>page.id),['a','b']);
  assert.deepEqual([...result.groups[0].locales].sort(),['en','pt']);
  assert.equal(result.loose[0][1][0].id,'c');
  assert.equal(result.groups.reduce((sum,group)=>sum+group.pages.length,0)+result.loose.reduce((sum,[,pages])=>sum+pages.length,0),rows.length);
  console.log('M2 catálogo: grupos únicos e contagem conservada');
})().catch(error=>{console.error(error);process.exitCode=1;});
