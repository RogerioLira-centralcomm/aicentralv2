export const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

function responseError(data, status) {
  const error = new Error(data.error || `Não foi possível concluir (${status}).`);
  error.status = status;
  error.code = String(data.code || '');
  error.details = data.details && typeof data.details === 'object' ? data.details : {};
  return error;
}

export async function request(url, options = {}) {
  const response = await fetch(url, {credentials: 'same-origin', ...options});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw responseError(data, response.status);
  }
  return data;
}

export async function streamEvents(response, onEvent) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw responseError(data, response.status);
  }
  if (!response.body) throw new Error('A resposta não pôde ser transmitida.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let terminal = false;
  const consume = frame => {
    const raw = frame.split('\n').filter(line => line.startsWith('data:'))
      .map(line => line.slice(5).trimStart()).join('\n');
    if (!raw) return;
    const event = JSON.parse(raw);
    if (['run.completed', 'run.failed', 'run.cancelled'].includes(event.event)) terminal = true;
    onEvent(event);
  };
  while (true) {
    const {value, done} = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
    const frames = buffer.split('\n\n');
    buffer = frames.pop() || '';
    frames.forEach(consume);
    if (done) {
      if (buffer.trim()) consume(buffer);
      break;
    }
  }
  if (!terminal) throw new Error('A conexão terminou antes da conclusão. Tente novamente.');
}

export const safeUrl = value => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  try {
    const url = new URL(raw, window.location.origin);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch (_) {
    return '';
  }
};

export const uid = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
