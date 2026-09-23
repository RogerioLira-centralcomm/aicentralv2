import assert from 'node:assert/strict';
import test from 'node:test';
import {COMPOSER_STATES, composerReducer, composerState} from '../../frontend/cadu-design-system/lib/composerState.mjs';

test('composer follows explicit focus, submit, streaming and completion states', () => {
  let state = composerState({value: '', running: false});
  assert.equal(state.status, COMPOSER_STATES.IDLE);
  state = composerReducer(state, {type: 'focus', hasValue: false});
  assert.equal(state.status, COMPOSER_STATES.FOCUSED);
  state = composerReducer(state, {type: 'change', hasValue: true, focused: true});
  assert.equal(state.status, COMPOSER_STATES.TYPING);
  state = composerReducer(state, {type: 'submit'});
  assert.equal(state.status, COMPOSER_STATES.SUBMITTING);
  state = composerReducer(state, {type: 'stream'});
  assert.equal(state.status, COMPOSER_STATES.STREAMING);
  state = composerReducer(state, {type: 'complete', focused: false});
  assert.equal(state.status, COMPOSER_STATES.IDLE);
});

test('composer exposes disabled and recoverable error states', () => {
  assert.equal(composerState({disabled: true}).status, COMPOSER_STATES.DISABLED);
  const failed = composerReducer(composerState(), {type: 'error', error: 'offline'});
  assert.equal(failed.status, COMPOSER_STATES.ERROR);
  assert.equal(failed.error, 'offline');
});
