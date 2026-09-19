/* Conversations V2 transport adapter. It translates server contracts into
   customer-facing UI events and never exposes tool names or provider details. */
(() => {
  'use strict';
  const progressFor = event => {
    const action = event.route?.action || '';
    return ({
      search_project:'Consultando as fontes do projeto…', create_brief:'Preparando o briefing…',
      compare_report_to_plan:'Comparando plano e relatório…', decision:'Organizando as opções…',
      direct:'Preparando a resposta…'
    })[action] || 'Organizando a resposta…';
  };
  const normalize = event => {
    if (event.event === 'run.started') return {event:'start', conversation_id:event.conversation_id, run_id:event.run_id};
    if (event.event === 'route.selected') return {event:'progress', message:progressFor(event)};
    if (event.event === 'tool.completed') return {event:'progress', message:'Contexto consultado. Preparando a resposta…'};
    if (event.event === 'tool.unavailable') return {event:'progress', message:'Continuando com as informações disponíveis…'};
    if (event.event === 'artifact.created') return {event:'v2.artifact', artifact:event.artifact};
    if (event.event === 'answer.completed') return {event:'v2.answer', response:event.response || {}};
    if (event.event === 'run.failed') return {event:'error', message:event.message || 'A execução foi interrompida.'};
    if (event.event === 'run.completed') return {event:'done', status:event.status || 'failed', conversation_id:event.conversation_id};
    return null;
  };
  async function* events(response) {
    if (!response.ok) {
      const value = await response.json().catch(() => ({}));
      throw new Error(value.error || 'Não foi possível iniciar a conversa.');
    }
    const reader = response.body.getReader(), decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), {stream:!done});
      const frames = buffer.split('\n\n'); buffer = frames.pop() || '';
      for (const frame of frames) {
        const raw = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (!raw) continue;
        const translated = normalize(JSON.parse(raw));
        if (translated) yield translated;
      }
      if (done) break;
    }
  }
  window.CaduConversationV2 = {events, normalize};
})();
