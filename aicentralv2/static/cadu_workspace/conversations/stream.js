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
  globalThis.CaduConversationStream = Object.freeze({events});
})();
