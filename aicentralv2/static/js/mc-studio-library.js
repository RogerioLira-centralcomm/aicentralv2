/* Shared, DOM-free library state. Each media request owns its cancellation token. */
(function (root) {
  function createStore(request, onChange) {
    const state = { clientId: '', media: 'all', query: '', limit: 12, context: 'loading',
      still: { status: 'idle', items: [] }, video: { status: 'idle', items: [] } };
    const pending = {};
    function emit() { onChange(state); }
    async function load(media) {
      pending[media]?.abort();
      const controller = new AbortController();
      pending[media] = controller;
      const clientId = state.clientId;
      state[media] = { status: 'loading', items: [] };
      emit();
      try {
        const data = await request(`/parametros/api/format-lab/swap/library?client_id=${encodeURIComponent(clientId)}&media=${media}`, { signal: controller.signal });
        if (controller.signal.aborted || state.clientId !== clientId || pending[media] !== controller) return;
        if (!Array.isArray(data?.items)) throw new Error('Resposta de biblioteca inválida');
        state[media] = { status: 'ready', items: data.items.filter(item => item && typeof item === 'object').map(item => ({ ...item, media })) };
      } catch (error) {
        if (controller.signal.aborted || state.clientId !== clientId || pending[media] !== controller) return;
        state[media] = { status: 'error', items: [] };
      }
      emit();
    }
    function context(clientId, status = 'ready') {
      clientId = String(clientId || '');
      if (clientId === state.clientId && status === state.context) return;
      Object.values(pending).forEach(controller => controller.abort());
      state.clientId = clientId;
      state.context = status;
      state.limit = 12;
      state.query = '';
      state.still = { status: 'idle', items: [] };
      state.video = { status: 'idle', items: [] };
      // Set both states together so a partial initial render never says "empty".
      if (clientId && status === 'ready') {
        state.still.status = state.video.status = 'loading';
        emit();
        return Promise.all([load('still'), load('video')]);
      }
      emit();
    }
    function view() {
      const media = state.media === 'all' ? ['still', 'video'] : [state.media];
      const query = state.query.toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      const items = media.flatMap(key => state[key].items).filter(item =>
        [item.name, item.title, item.headline, item.aspect_ratio].filter(Boolean).join(' ').toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g, '').includes(query)
      ).sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
      return { items: items.slice(0, state.limit), total: items.length,
        loading: media.some(key => state[key].status === 'loading'), errors: media.filter(key => state[key].status === 'error') };
    }
    return { state, context, view,
      filter(media) { if (!['all', 'still', 'video'].includes(media)) return; state.media = media; state.limit = 12; emit(); },
      search(query) { state.query = String(query); state.limit = 12; emit(); },
      more() { state.limit += 12; emit(); },
      retry(media) { if (!state.clientId || state.context !== 'ready') return; return media ? load(media) : Promise.all([load('still'), load('video')]); },
    };
  }
  const api = { createStore };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.McStudioLibrary = api;
})(typeof window !== 'undefined' ? window : globalThis);
