const EVENT_ALIASES = Object.freeze({
  start: 'run.started',
  progress: 'execution.step',
  replace: 'answer.delta',
  'v2.answer': 'answer.completed',
  'v2.artifact': 'artifact.created',
  done: 'run.completed',
});

const KNOWN_EVENTS = new Set([
  'run.started', 'route.selected', 'execution.step',
  'tool.started', 'tool.completed', 'tool.unavailable',
  'action.proposed', 'artifact.created', 'artifact.updated',
  'long_job.created', 'long_job.progress', 'long_job.completed', 'long_job.failed',
  'provider.first_token', 'answer.delta', 'answer.completed',
  'run.completed', 'run.failed', 'run.cancelled',
]);

function stableEventId(event) {
  const explicit = event.event_id || event.eventId;
  if (explicit) return String(explicit);
  const type = event.event;
  const identity = event.step_id || event.tool_call_id || event.toolCallId || event.action?.step_id
    || event.artifact?.id || event.message_id || event.messageId;
  // Deltas without a server event id are intentionally not deduplicated: two
  // equal chunks can be legitimate consecutive output.
  return identity && type !== 'answer.delta' ? `${type}:${identity}` : '';
}

export function normalizeAgentEvent(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return null;
  const rawType = String(input.event || input.type || '').trim();
  const event = EVENT_ALIASES[rawType] || rawType;
  if (!KNOWN_EVENTS.has(event)) return null;
  const normalized = {...input, event};
  normalized.eventId = stableEventId(normalized);
  if (event === 'answer.delta') normalized.answer = String(input.answer ?? input.text ?? '');
  if (event === 'run.started') {
    normalized.run_id = String(input.run_id || input.executionId || '');
    normalized.conversation_id = String(input.conversation_id || input.conversationId || '');
  }
  return normalized;
}

export function acceptAgentEvent(input, seen) {
  const event = normalizeAgentEvent(input);
  if (!event) return null;
  if (event.eventId && seen?.has(event.eventId)) return null;
  if (event.eventId) seen?.add(event.eventId);
  return event;
}
