export const initialExecutionState = Object.freeze({
  id: '', longJobId: '', status: 'idle', connection: 'connected', startedAt: 0, error: null,
});

const ACTIVE = new Set(['queued', 'preparing', 'running', 'waiting_tool', 'streaming', 'reconnecting']);

export function isExecutionActive(state) {
  return ACTIVE.has(state?.status);
}

export function executionReducer(state, action) {
  switch (action.type) {
    case 'submitted':
      return {id: '', status: 'preparing', connection: 'connected', startedAt: Date.now(), error: null};
    case 'upload.failed':
      return {...state, status: 'failed', error: action.error || null};
    case 'event': {
      const event = action.event || {};
      if (event.event === 'run.started') return {...state, id: event.run_id || state.id, status: 'running'};
      if (event.event === 'route.selected') return {...state, status: 'preparing'};
      if (event.event === 'tool.started') return {...state, status: 'waiting_tool'};
      if (event.event === 'tool.completed' || event.event === 'provider.first_token') return {...state, status: 'running'};
      if (event.event === 'answer.delta') return {...state, status: 'streaming'};
      if (event.event === 'answer.completed') return {...state, status: 'running'};
      if (event.event === 'long_job.created') return {...state, longJobId: event.job?.id || '', status: 'running'};
      if (event.event === 'long_job.progress') return {...state, status: 'running'};
      if (event.event === 'long_job.completed') return {...state, status: 'completed'};
      if (event.event === 'long_job.failed') return {...state, status: 'failed', error: event.message || null};
      if (event.event === 'run.completed') return state.longJobId
        ? state : {...state, status: event.status === 'cancelled' ? 'cancelled' : 'completed'};
      if (event.event === 'run.cancelled') return {...state, status: 'cancelled'};
      if (event.event === 'run.failed') return {...state, status: 'failed', error: event.message || null};
      return state;
    }
    case 'connection.lost':
      return {...state, status: state.id ? 'reconnecting' : 'failed', connection: 'disconnected', error: action.error || null};
    case 'connection.restored':
      return {...state, status: state.id ? 'running' : state.status, connection: 'connected', error: null};
    case 'connection.failed':
      return {...state, status: 'failed', connection: 'disconnected', error: action.error || state.error};
    case 'cancel.requested':
      return {...state, status: 'cancelled'};
    case 'reset':
      return {...initialExecutionState};
    default:
      return state;
  }
}
