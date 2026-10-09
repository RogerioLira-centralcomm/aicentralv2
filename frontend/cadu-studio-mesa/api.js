// Cliente das rotas do Studio já existentes (mesmo contrato do Criar v2 e do Editar/Trocr).

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const absolute = value => { const raw = String(value || ''); if (!raw || raw.startsWith('data:')) return ''; try { return new URL(raw, location.origin).href; } catch { return ''; } };
const RATIOS = {'4:5': 0.8, '1:1': 1, '9:16': 9 / 16, '16:9': 16 / 9};
/** O Editar só conhece quatro proporções: a mais próxima do formato (o tamanho exato vai em output_width/height). */
export const nearestRatio = format => { const r = (Number(format?.width) || 1) / (Number(format?.height) || 1); return Object.entries(RATIOS).reduce((best, [key, value]) => Math.abs(Math.log(value / r)) < Math.abs(Math.log(RATIOS[best] / r)) ? key : best, '1:1'); };

export function createApi(boot) {
  const root = boot.apiRoot;
  let csrf = boot.csrf || '';
  const renew = async () => {
    const response = await fetch(`${root}/format-lab/studio/csrf`, {credentials: 'same-origin', headers: {Accept: 'application/json'}});
    const payload = await response.json().catch(() => ({}));
    if (!payload?.data?.token) throw new Error('Não foi possível renovar a sessão segura do Studio.');
    csrf = payload.data.token;
  };
  const request = async (path, options = {}, retried = false) => {
    const response = await fetch(`${root}${path}`, {...options, credentials: 'same-origin',
      headers: {Accept: 'application/json', ...(options.body ? {'Content-Type': 'application/json'} : {}), ...(csrf ? {'X-Trocr-CSRF-Token': csrf} : {}), ...(options.headers || {})}});
    const payload = await response.json().catch(() => ({}));
    if (response.status === 403 && !retried && /token|seguran|csrf/i.test(String(payload.error || ''))) { await renew(); return request(path, options, true); }
    if (!response.ok || payload.success === false) {
      const error = new Error(payload.error || 'Não foi possível concluir a solicitação.');
      error.status = response.status; error.code = payload.code;
      throw error;
    }
    return payload.data !== undefined ? payload.data : payload;
  };
  const post = (path, body) => request(path, {method: 'POST', body: JSON.stringify(body)});
  const rid = prefix => `${prefix}-${crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`}`;

  return {
    projects: () => request('/format-lab/studio/project-contexts').then(data => data.items || []),
    session: (id, clientId) => request(`/format-lab/studio/sessions/${encodeURIComponent(id)}?client_id=${encodeURIComponent(clientId || '')}`),
    sessions: clientId => request(`/format-lab/studio/sessions?client_id=${encodeURIComponent(clientId || '')}&limit=40`).then(data => data.items || []),
    createSession: ({ctx, title, board}) => post('/format-lab/studio/sessions', {
      client_id: ctx.quick ? '' : ctx.clientId, project_id: ctx.quick ? '' : ctx.projectId, studio_type: 'create',
      title, metadata: {surface: 'quadro', board},
    }),
    saveSession: ({id, ctx, revision, title, board}) => request(`/format-lab/studio/sessions/${encodeURIComponent(id)}`, {method: 'PATCH', body: JSON.stringify({
      client_id: ctx.quick ? '' : ctx.clientId, expected_revision: revision, title, metadata: {surface: 'quadro', board},
    })}),

    /** Peça nova ou variação: direção (diretor) e imagem, aprovando a direção automaticamente. */
    async create({ctx, prompt, format, quality = 'Padrão', variationBase = '', references = [], recipe = '', intent = 'branded_creative', creationType = ''}) {
      const common = {client_id: ctx.quick ? '' : ctx.clientId, project_id: ctx.quick ? '' : ctx.projectId, quick_mode: ctx.quick};
      const fullPrompt = recipe ? `${prompt}\n\n${recipe}` : prompt;
      const directions = await post('/format-lab/studio/create/directions', {...common, count: 1, prompt: fullPrompt, references,
        context: {purpose: 'criacao', creation_intent: intent, channels: [format.channel || 'social'], format: format.ratio, format_key: format.key,
          width: format.width, height: format.height, requested_directions: 1, references, creation_type: creationType || undefined, project_name: ctx.projectName || 'Rascunho pessoal'}});
      const direction = directions.directions?.[0];
      if (!direction) throw new Error('O diretor não devolveu uma direção.');
      const approved = String(direction.prompt || direction.summary || fullPrompt);
      const image = await post('/format-lab/studio/create/image', {...common, studio_v2: true, direction_approved: true, original_prompt: prompt, prompt: approved,
        title: direction.title || 'Peça', channel: format.channel || 'social', format_key: format.key, width: format.width, height: format.height,
        aspect_ratio: format.ratio, quality, creation_intent: intent, references, reference_plan: direction.reference_plan || [],
        copy: direction.copy || null, variation_base: variationBase, creation_type: creationType || undefined, register_library: false, request_id: rid('quadro')});
      return {url: image.image_url, url2x: image.image_url_2x || '', base: image.variation_base || image.image_url, asset_id: image.asset_id || '', title: direction.title || '', prompt: approved, review: image.review || null};
    },

    /** Ajuste de uma peça pronta pela fila do servidor (mesmo caminho do Editar): sobrevive a recarregar a página. */
    async adjust({ctx, base, instruction, format, sourceFormat = null, references = [], sessionId = '', brandName = '', onTask}) {
      const source = absolute(base.url);
      if (!source) throw new Error('A peça-base ainda não tem endereço público.');
      const refs = references.map(item => ({...item, url: absolute(item.url)})).filter(item => item.url).slice(0, 2);
      const payload = {reference: source, note: instruction, instruction, original_instruction: instruction, client_id: ctx.clientId || undefined,
        aspect_ratio: nearestRatio(format), aspect_hint: sourceFormat ? nearestRatio(sourceFormat) : undefined, output_width: format?.width, output_height: format?.height, quality: 'production', brand_name: brandName,
        reference_images: refs.map(item => item.url), reference_inputs: refs.map((item, index) => ({image: item.url, role: item.role || 'reference', source: item.source, label: item.label, order: index + 2})),
        director_context: {references: refs, reference_policy: 'similarity_only_preserve_source_identity'},
        use_brand_context: true, confirm_conflicts: true, variation_count: 1};
      const task = await post('/format-lab/studio/tasks', {kind: 'image_edit', client_id: ctx.clientId, session_id: sessionId || undefined, payload});
      onTask?.(task.id);
      return this.waitTask({ctx, taskId: task.id, prompt: instruction});
    },

    /** Espera uma tarefa da fila (também usada para retomar ajustes depois de recarregar). */
    async waitTask({ctx, taskId, prompt = ''}) {
      const deadline = Date.now() + 8 * 60 * 1000;
      let failures = 0;
      while (Date.now() < deadline) {
        let current;
        try { current = await request(`/format-lab/studio/tasks/${encodeURIComponent(taskId)}?client_id=${encodeURIComponent(ctx.clientId || '')}`); failures = 0; }
        catch (error) { failures += 1; if (failures >= 4) throw error; await sleep(2000); continue; }
        if (current.status === 'ready') {
          const result = current.result || {};
          const url = result.image_url || result.png_data_url;
          if (!url) throw new Error(result.preview || 'A edição não devolveu imagem.');
          return {url, asset_id: result.asset_id || '', prompt};
        }
        if (current.status === 'failed') throw new Error(current.error || 'Não foi possível concluir esta edição.');
        await sleep(1500);
      }
      throw new Error('A edição continua no servidor. Abra o quadro de novo daqui a pouco.');
    },

    /** Referências do contexto: máscaras de composição, imagens da marca/projeto e as enviadas. */
    async shelf(ctx) {
      if (ctx.quick) {
        const data = await request('/format-lab/studio/library-sessions');
        return {masks: data.reference_masks || [], items: (data.personal_assets || []).map(item => ({...item, source: 'user'}))};
      }
      const data = await request(`/format-lab/studio/projects/${encodeURIComponent(ctx.projectId)}/creation-history?client_id=${encodeURIComponent(ctx.clientId)}&limit=30`);
      return {masks: data.reference_masks || [], items: data.items || []};
    },

    async upload(ctx, files) {
      const form = new FormData();
      form.append('client_id', ctx.quick ? '' : ctx.clientId);
      if (!ctx.quick) form.append('project_id', ctx.projectId);
      [...files].forEach(file => form.append('files', file, file.name));
      const response = await fetch(`${root}/format-lab/studio/reference-uploads`, {method: 'POST', credentials: 'same-origin', body: form, headers: {Accept: 'application/json', ...(csrf ? {'X-Trocr-CSRF-Token': csrf} : {})}});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.success === false) throw new Error(payload.error || 'Não foi possível enviar a imagem.');
      return ((payload.data || payload).items || []).map(item => ({id: item.id, url: item.url, label: item.original_name || 'Enviada', source: 'user', role: 'reference'}));
    },

    /** Peças aprovadas viram ativos oficiais da marca do projeto. */
    publish: ({ctx, items}) => post('/format-lab/studio/quadro/publish', {client_id: ctx.clientId, items}),

    /** Quebra um pedido com várias peças em lista revisável. */
    decompose: ({ctx, text, type}) => post('/format-lab/studio/quadro/decompose', {client_id: ctx.quick ? '' : ctx.clientId, project_id: ctx.quick ? '' : ctx.projectId, text, type}),
  };
}
