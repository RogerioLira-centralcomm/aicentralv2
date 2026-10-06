const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
// flowValidation.js passou a importar flowGoals.js; carrega pelo arquivo para resolver imports relativos.
const modulePath=path.resolve(__dirname,'../../frontend/reports-v1/flowValidation.js');
const cases=require('../fixtures/reports_flow_validation.json');
(async()=>{
  const {flowValidation}=await import(pathToFileURL(modulePath).href);
  for(const item of cases){
    const issues=flowValidation(item.config);
    const keys=severity=>issues.filter(issue=>issue.severity===severity).map(issue=>issue.code+(issue.nodeId?':'+issue.nodeId:''));
    assert.deepEqual(keys('error'),item.expected_errors,item.name+' bloqueios');
    assert.deepEqual(keys('warning'),item.expected_warnings,item.name+' avisos');
    assert.ok(issues.every(issue=>issue.action&&issue.consequence),item.name+' ações');
    assert.ok(issues.filter(issue=>issue.code==='cycle_without_condition').every(issue=>issue.edgeId==='volta'),item.name+' conexão');
  }
  console.log('Paridade de pendências JS: '+cases.length+' cenários');
})().catch(error=>{console.error(error);process.exitCode=1;});
