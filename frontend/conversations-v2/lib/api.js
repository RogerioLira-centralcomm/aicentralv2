export const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

function responseError(data, status) {
  const error = new Error(data.error || `Não foi possível concluir (${status}).`);
  error.status = status;
  error.code = String(data.code || '');
  error.details = data.details && typeof data.details === 'object' ? data.details : {};
  error.retryable = Boolean(data.retryable);
  return error;
}

export async function renewCsrfToken(url) {
  const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw responseError(data, response.status);
  const token = String(data.csrf || '');
  if (!token) throw new Error('Não foi possível renovar a sessão de trabalho.');
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) meta.content = token;
  return token;
}

export async function request(url, options = {}) {
  const send = requestOptions => fetch(url, {credentials: 'same-origin', ...requestOptions});
  let response = await send(options);
  let data = await response.clone().json().catch(() => ({}));
  if (!response.ok && response.status === 403 && data.code === 'csrf_invalid'
      && (options.method || 'GET').toUpperCase() !== 'GET') {
    const token = await renewCsrfToken('/workspace/api/v2/csrf');
    response = await send({
      ...options,
      headers: {...(options.headers || {}), 'X-CSRF-Token': token},
    });
    data = await response.clone().json().catch(() => ({}));
  }
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
