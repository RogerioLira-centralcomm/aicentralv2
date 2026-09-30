const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const source=fs.readFileSync(path.resolve(__dirname,'../../frontend/reports-v1/flowFeedback.js'),'utf8');
const load=async()=>import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

(async()=>{
  const {plural,savedAgo,publishBlocked}=await load();
  assert.equal(plural(1,'fluxo criado','fluxos criados'),'1 fluxo criado');
  assert.equal(plural(2,'fluxo criado','fluxos criados'),'2 fluxos criados');
  assert.equal(savedAgo(1_000_000,1_000_000),'Salvo agora');
  assert.equal(savedAgo(1_000_000,1_120_000),'Salvo há 2 minutos');
  assert.equal(publishBlocked([{severity:'warning'}]),false);
  assert.equal(publishBlocked([{severity:'error'}]),true);
  console.log('Feedback do fluxo: pluralização, tempo e bloqueio aprovados');
})().catch(error=>{console.error(error);process.exitCode=1;});
