const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../../frontend/reports-v1');
const stages=fs.readFileSync(path.join(root,'flowStages.js'),'utf8');
const labels=fs.readFileSync(path.join(root,'flowUiLabels.js'),'utf8');
(async()=>{
 const stageUrl='data:text/javascript;base64,'+Buffer.from(stages).toString('base64');
 const moduleSource=labels.replace("'./flowStages.js'",`'${stageUrl}'`);
 const {flowStageLabel,flowRoleLabel,flowRoleSourceLabel}=await import('data:text/javascript;base64,'+Buffer.from(moduleSource).toString('base64'));
 assert.equal(flowStageLabel({type:'page',stage:'exploration'}),'Exploração');
 assert.equal(flowRoleLabel('conversion'),'Confirmação');
 assert.equal(flowRoleLabel('unexpected'),'Função não definida');
 assert.equal(flowRoleSourceLabel('typesafe'),'sugestão');
 console.log('Rótulos do fluxo: IDs técnicos traduzidos');
})().catch(error=>{console.error(error);process.exitCode=1;});
