import test from 'node:test';
import assert from 'node:assert/strict';
import {flowNextAction} from '../../frontend/reports-v1/flowNextAction.js';

test('next action follows the flow lifecycle', () => {
  assert.equal(flowNextAction({config:{nodes:[]}}).label, 'Testar conversão');
  assert.equal(flowNextAction({config:{nodes:[{type:'page'}]}}).label, 'Adicionar a origem do tráfego');
  assert.equal(flowNextAction({config:{nodes:[{type:'source'},{type:'page'}]}}).label, 'Definir a conversão');
  assert.equal(flowNextAction({status:'draft',config:{site_kind:'institucional',nodes:[{type:'source'},{type:'page'}]}}).label, 'Revisar e publicar');
  assert.equal(flowNextAction({status:'draft',config:{nodes:[{type:'source'},{type:'conversion'}]}}).label, 'Revisar e publicar');
  assert.deepEqual(flowNextAction({status:'published',monitor_enabled:true,monitor_status:'offline',config:{nodes:[{type:'source'},{type:'conversion'}]}}).view, 'monitor');
  assert.equal(flowNextAction({status:'published',config:{nodes:[{type:'source'},{type:'conversion'}]}}).label, 'Acompanhar jornada');
  assert.equal(flowNextAction({revoked_at:'2026-01-01',config:{nodes:[]}}).label, 'Reativar a tag do site');
  assert.equal(flowNextAction({allowed_host:'',status:'draft',config:{nodes:[{type:'source'},{type:'page',status:'planned'}]}}).label, 'Revisar o plano');
  assert.equal(flowNextAction({allowed_host:'',config:{nodes:[]}}).label, 'Montar o plano');
});
