/* SSE transport for the Python adapter: no provider key or PHP endpoints. */
(() => {
  'use strict';
  async function* events(body) {
    if (!body) throw new Error('A resposta não contém um fluxo de mensagens.');
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let pending = '', parts = [], size = 0, finished = false;
    const limit = 1024 * 1024;
    function line(value) {
      if (value.endsWith('\r')) value = value.slice(0, -1);
      if (!value) {
        if (!parts.length) return null;
        const raw = parts.join('\n'); parts = []; size = 0;
        if (raw === '[DONE]') return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Evento de resposta inválido.');
        return parsed;
      }
      if (value.startsWith('data:')) {
        const data = value.slice(5).replace(/^ /, '');
        size += data.length;
        if (size > limit) throw new Error('Evento de resposta muito grande.');
        parts.push(data);
      }
      return null;
    }
    try {
      while (true) {
        const {value, done} = await reader.read();
        pending += decoder.decode(value || new Uint8Array(), {stream: !done});
        let boundary;
        while ((boundary = pending.indexOf('\n')) >= 0) {
          const event = line(pending.slice(0, boundary));
          pending = pending.slice(boundary + 1);
          if (event) yield event;
        }
        if (pending.length > limit) throw new Error('Evento de resposta muito grande.');
        if (done) {
          if (pending) line(pending);
          const event = line('');
          if (event) yield event;
          finished = true;
          break;
        }
      }
    } finally {
      if (!finished) { try { await reader.cancel(); } catch (_) { /* Already closed. */ } }
      reader.releaseLock();
    }
  }
  function pause(ms, signal) {
    return new Promise((resolve, reject) => {
      if (signal.aborted) { reject(new DOMException('Acompanhamento interrompido', 'AbortError')); return; }
      const abort = () => { clearTimeout(timer); reject(new DOMException('Acompanhamento interrompido', 'AbortError')); };
      const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
      signal.addEventListener('abort', abort, {once:true});
    });
  }
  async function* queued(run, {signal, fetchPage, onRetry = () => {}, sleep = pause, now = Date.now}) {
    yield {event:'start', run_id:run.run_id, conversation_id:run.conversation_id};
    let cursor = 0, failures = 0;
    const deadline = now() + 300000;
    while (!signal.aborted && now() < deadline) {
      let page;
      try {
        page = await fetchPage(cursor, signal);
        failures = 0;
      } catch (error) {
        if (signal.aborted || (error.status >= 400 && error.status < 500 && ![408, 429].includes(error.status))) throw error;
        if (++failures > 3) throw error;
        onRetry(failures);
        await sleep(1000 * 2 ** (failures - 1), signal);
        continue; // Retry the GET at the same cursor, never the original send.
      }
      if (signal.aborted) throw new DOMException('Acompanhamento interrompido', 'AbortError');
      if (!Array.isArray(page.events) || !['running', 'completed', 'failed', 'stopped'].includes(page.status)) {
        throw new Error('Estado de acompanhamento inválido. Consulte o histórico.');
      }
      for (const item of page.events) {
        if (!Number.isSafeInteger(item.id) || !item.event || typeof item.event.event !== 'string') {
          throw new Error('Evento de acompanhamento inválido. Consulte o histórico.');
        }
        if (item.id <= cursor) continue;
        cursor = item.id;
        if (item.event.event !== 'start') yield item.event;
        if (item.event.event === 'done') return;
      }
      if (page.events.length < 100 && page.status !== 'running') {
        yield {event:'done', status:page.status};
        return;
      }
      if (page.events.length < 100) await sleep(1000, signal);
    }
    if (signal.aborted) throw new DOMException('Acompanhamento interrompido', 'AbortError');
    throw new Error('O acompanhamento foi pausado. O processamento continua no servidor; consulte o histórico.');
  }
  globalThis.CaduConversationStream = Object.freeze({events, queued});
})();
