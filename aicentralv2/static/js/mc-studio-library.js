/* Shared, DOM-free library state. Each media request owns its cancellation token. */
(function (root) {
  function createStore(request, onChange) {
    const state = { clientId: '', media: 'all', project: 'all', query: '', sort: 'recent', limit: 12, context: 'loading',
      still: { status: 'idle', items: [] }, video: { status: 'idle', items: [] }, projects: { status: 'idle', items: [] } };
    const pending = {};
    function emit() { onChange(state); }
    function assetKey(value) {
      if (!value) return '';
      try {
        const url = new URL(String(value), 'https://studio.local');
        return `${url.pathname.replace(/\/$/, '')}${url.search}`;
      } catch (_) { return String(value).split('#')[0].replace(/\/$/, ''); }
    }
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
    async function loadProjects() {
      pending.projects?.abort();
      const controller = new AbortController();
      pending.projects = controller;
      const clientId = state.clientId;
      state.projects = { status: 'loading', items: [] };
      emit();
      try {
        const listing = await request(`/parametros/api/format-lab/studio/library-sessions?client_id=${encodeURIComponent(clientId)}`, { signal: controller.signal });
        const projects = (Array.isArray(listing?.items) ? listing.items : []).map(project => ({ id: String(project.id), name: String(project.name || 'Projeto sem nome'), updatedAt: project.updated_at || '', assets: Array.isArray(project.assets) ? project.assets.map(String).filter(Boolean) : [] }));
        if (controller.signal.aborted || state.clientId !== clientId || pending.projects !== controller) return;
        state.projects = { status: 'ready', items: projects,
          personalAssets: (Array.isArray(listing?.personal_assets) ? listing.personal_assets : []).map(item => ({...item, media:'still', personal:true})) };
      } catch (error) {
        if (controller.signal.aborted || state.clientId !== clientId || pending.projects !== controller) return;
        state.projects = { status: 'error', items: [] };
      }
      emit();
    }
    function context(clientId, status = 'ready') {
      clientId = String(clientId || '');
      if (clientId === state.clientId && status === state.context) return;
      Object.values(pending).forEach(controller => controller.abort());
      state.clientId = clientId;
      state.context = status;
      state.project = 'all';
      state.limit = 12;
      state.query = '';
      state.still = { status: 'idle', items: [] };
      state.video = { status: 'idle', items: [] };
      state.projects = { status: 'idle', items: [] };
      // Set both states together so a partial initial render never says "empty".
      if (clientId && status === 'ready') {
        state.still.status = state.video.status = 'loading';
        emit();
        return Promise.all([load('still'), load('video'), loadProjects()]);
      }
      emit();
    }
    function view() {
      const media = state.media === 'all' ? ['still', 'video'] : [state.media];
      const query = state.query.toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      const projectFor = (item) => {
        const urls = new Set([item.image_url, item.video_url, item.thumb_url, item.poster_url].map(assetKey).filter(Boolean));
        return state.projects.items.filter(project => project.assets.some(asset => urls.has(assetKey(asset))));
      };
      const personal = state.media === 'video' ? [] : (state.projects.personalAssets || []);
      const items = [...media.flatMap(key => state[key].items), ...personal].map(item => ({ ...item, media:item.media||'still', projects: projectFor(item) })).filter(item =>
        [item.name, item.title, item.headline, item.aspect_ratio].filter(Boolean).join(' ').toLocaleLowerCase('pt-BR').normalize('NFD').replace(/[\u0300-\u036f]/g, '').includes(query)
      ).filter(item => state.project === 'all' || (state.project === 'unassigned' ? !item.projects.length : item.projects.some(project => project.id === state.project))).sort((a, b) => {
        if(state.sort==='name')return String(a.name||a.title||'').localeCompare(String(b.name||b.title||''),'pt-BR');
        if(state.sort==='oldest')return String(a.created_at||'').localeCompare(String(b.created_at||''));
        return String(b.created_at || '').localeCompare(String(a.created_at || ''));
      });
      return { items: items.slice(0, state.limit), total: items.length,
        loading: media.some(key => state[key].status === 'loading') || state.projects.status === 'loading', errors: media.filter(key => state[key].status === 'error'), projectError: state.projects.status === 'error', projects: state.projects.items };
    }
    return { state, context, view,
      filter(media) { if (!['all', 'still', 'video'].includes(media)) return; state.media = media; state.limit = 12; emit(); },
      project(project) { state.project = String(project || 'all'); state.limit = 12; emit(); },
      search(query) { state.query = String(query); state.limit = 12; emit(); },
      sort(value) { state.sort = ['recent','oldest','name'].includes(value) ? value : 'recent'; emit(); },
      more() { state.limit += 12; emit(); },
      retry(media) { if (!state.clientId || state.context !== 'ready') return; return media ? load(media) : Promise.all([load('still'), load('video'), loadProjects()]); },
    };
  }
  const api = { createStore };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.McStudioLibrary = api;
})(typeof window !== 'undefined' ? window : globalThis);
