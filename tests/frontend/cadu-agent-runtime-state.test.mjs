import test from 'node:test';
import assert from 'node:assert/strict';

import {acceptAgentEvent, normalizeAgentEvent} from '../../frontend/conversations-v2/lib/agentEvents.mjs';
import {executionReducer, initialExecutionState, isExecutionActive} from '../../frontend/conversations-v2/lib/executionState.mjs';

test('agent event normalization rejects raw unknown payloads and normalizes aliases', () => {
  assert.equal(normalizeAgentEvent({payload: '{"text":"raw"}'}), null);
  assert.equal(normalizeAgentEvent({event: 'private.provider.debug', secret: true}), null);
  assert.deepEqual(normalizeAgentEvent({event: 'replace', text: 'Olá'}), {
    event: 'answer.delta', text: 'Olá', eventId: '', answer: 'Olá',
  });
});

test('stable tool and artifact events are idempotent while equal deltas remain valid', () => {
  const seen = new Set();
  const tool = {event: 'tool.completed', tool_call_id: 'tool-1', name: 'web.search'};
  assert.ok(acceptAgentEvent(tool, seen));
  assert.equal(acceptAgentEvent(tool, seen), null);
  assert.ok(acceptAgentEvent({event: 'answer.delta', answer: 'mesmo'}, seen));
  assert.ok(acceptAgentEvent({event: 'answer.delta', answer: 'mesmo'}, seen));
});

test('execution reducer has explicit valid states from submission through completion', () => {
  let state = executionReducer(initialExecutionState, {type: 'submitted'});
  assert.equal(state.status, 'preparing');
  assert.equal(isExecutionActive(state), true);
  state = executionReducer(state, {type: 'event', event: {event: 'run.started', run_id: 'run-1'}});
  assert.equal(state.status, 'running');
  assert.equal(state.id, 'run-1');
  state = executionReducer(state, {type: 'event', event: {event: 'tool.started'}});
  assert.equal(state.status, 'waiting_tool');
  state = executionReducer(state, {type: 'event', event: {event: 'answer.delta'}});
  assert.equal(state.status, 'streaming');
  state = executionReducer(state, {type: 'event', event: {event: 'run.completed', status: 'completed'}});
  assert.equal(state.status, 'completed');
  assert.equal(isExecutionActive(state), false);
});

test('cancelled and failed connections cannot remain accidentally active', () => {
  let state = executionReducer({...initialExecutionState, id: 'run-1', status: 'streaming'}, {type: 'cancel.requested'});
  assert.equal(state.status, 'cancelled');
  assert.equal(isExecutionActive(state), false);
  state = executionReducer({...initialExecutionState, id: 'run-2', status: 'running'}, {type: 'connection.lost'});
  assert.equal(state.status, 'reconnecting');
  state = executionReducer(state, {type: 'connection.failed', error: 'offline'});
  assert.equal(state.status, 'failed');
  assert.equal(isExecutionActive(state), false);
});

test('a long job keeps execution active after the admission stream completes', () => {
  let state = executionReducer(initialExecutionState, {type: 'submitted'});
  state = executionReducer(state, {type: 'event', event: {event: 'long_job.created', job: {id: 'job-1'}}});
  state = executionReducer(state, {type: 'event', event: {event: 'run.completed', status: 'completed'}});
  assert.equal(state.status, 'running');
  assert.equal(state.longJobId, 'job-1');
  state = executionReducer(state, {type: 'event', event: {event: 'long_job.completed'}});
  assert.equal(state.status, 'completed');
});
