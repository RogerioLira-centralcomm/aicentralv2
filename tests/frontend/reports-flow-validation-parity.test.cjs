const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.resolve(__dirname,'../../frontend/reports-v1/flowValidation.js'),'utf8');
const cases=require('../fixtures/reports_flow_validation.json');
(async()=>{
  const {flowValidation}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
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
