export const COMPOSER_STATES = Object.freeze({
  IDLE: 'idle', FOCUSED: 'focused', TYPING: 'typing', SUBMITTING: 'submitting',
  STREAMING: 'streaming', DISABLED: 'disabled', ERROR: 'error',
});

export function composerState(initial = {}) {
  if (initial.disabled) return {status: COMPOSER_STATES.DISABLED, error: ''};
  if (initial.running) return {status: COMPOSER_STATES.STREAMING, error: ''};
  return {status: initial.value ? COMPOSER_STATES.TYPING : COMPOSER_STATES.IDLE, error: ''};
}

export function composerReducer(state, action) {
  switch (action.type) {
    case 'focus': return {status: action.hasValue ? COMPOSER_STATES.TYPING : COMPOSER_STATES.FOCUSED, error: ''};
    case 'change': return {status: action.hasValue ? COMPOSER_STATES.TYPING : action.focused ? COMPOSER_STATES.FOCUSED : COMPOSER_STATES.IDLE, error: ''};
    case 'submit': return {status: COMPOSER_STATES.SUBMITTING, error: ''};
    case 'stream': return {status: COMPOSER_STATES.STREAMING, error: ''};
    case 'complete': return {status: action.focused ? COMPOSER_STATES.FOCUSED : COMPOSER_STATES.IDLE, error: ''};
    case 'disable': return {status: COMPOSER_STATES.DISABLED, error: ''};
    case 'error': return {status: COMPOSER_STATES.ERROR, error: String(action.error || '')};
    case 'blur': return state.status === COMPOSER_STATES.ERROR ? state : {status: COMPOSER_STATES.IDLE, error: ''};
    default: return state;
  }
}
