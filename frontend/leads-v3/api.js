// Cliente HTTP da mesa de Leads v3.
// As rotas novas (/leads-v3/api) respondem {success, data | error}; as do Leads v2
// (/api/leads, /api/ia) respondem {success, <chave>} e usam `message` no erro.

async function request(url, {method = 'GET', body} = {}) {
  const response = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: {Accept: 'application/json', ...(body !== undefined ? {'Content-Type': 'application/json'} : {})},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) throw new Error('Sua sessão expirou. Recarregue a página e entre de novo.');
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || payload.message || 'Não foi possível concluir a ação.');
  }
  return payload;
}

const qs = params => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') search.set(key, value); });
  const text = search.toString();
  return text ? `?${text}` : '';
};

export function createApi(boot) {
  const root = boot.apiRoot;
  const legacy = boot.legacyApiRoot;
  return {
    listLeads: filters => request(`${root}/leads${qs(filters)}`).then(p => p.data),
    bulk: (acao, ids, extra = {}) => request(`${root}/leads/lote`, {method: 'POST', body: {acao, ids, ...extra}}).then(p => p.data),

    lead: id => request(`${legacy}/${id}/detalhes`).then(p => p.lead),
    updateStatus: (id, body) => request(`${legacy}/${id}/status`, {method: 'PATCH', body}),
    updateLead: (id, body) => request(`${legacy}/${id}/editar`, {method: 'PATCH', body}),
    createLead: body => request(`${legacy}/novo`, {method: 'POST', body}),

    analyticsLegacy: params => request(`${legacy}/analise${qs(params)}`).then(p => p.data || {}),
    analyticsWeekly: params => request(`${root}/analise/semanal${qs(params)}`).then(p => p.data),
    analyticsV3: params => request(`${root}/analise${qs(params)}`).then(p => p.data),
    importParse: texto => request(`${legacy}/processar-importacao`, {method: 'POST', body: {texto_bruto: texto}}).then(p => p.leads || []),
    importConfirm: body => request(`${legacy}/importar`, {method: 'POST', body}),
    extractSite: (id, url) => request(`${legacy}/${id}/extrair-url`, {method: 'POST', body: {url}}).then(p => ({dados: p.dados || {}, url: p.url || url})),
    saveExtracted: (id, body) => request(`${legacy}/${id}/salvar-dados-extraidos`, {method: 'POST', body}),
    merge: (id, idDuplicado) => request(`${root}/leads/${id}/mesclar`, {method: 'POST', body: {id_duplicado: idDuplicado}}).then(p => p.data),
    suggestActivity: id => request('/api/ia/sugerir-atividade', {method: 'POST', body: {lead_id: id}}).then(p => p.sugestao || null),
    improveText: texto => request('/api/ia/melhorar-texto', {method: 'POST', body: {texto}}).then(p => p.texto || texto),
    updateActivity: (activityId, body) => request(`${legacy}/atividades/${activityId}`, {method: 'PATCH', body}),
    contacts: id => request(`${legacy}/${id}/contatos`).then(p => p.contatos || []),
    addContact: (id, body) => request(`${legacy}/${id}/contatos`, {method: 'POST', body}),
    updateContact: (contactId, body) => request(`${legacy}/contatos/${contactId}`, {method: 'PATCH', body}),
    removeContact: contactId => request(`${legacy}/contatos/${contactId}`, {method: 'DELETE'}),
    makePrimary: (leadId, contactId) => request(`${legacy}/contatos/${contactId}/principal`, {method: 'PATCH', body: {lead_id: leadId}}),

    activities: id => request(`${legacy}/${id}/atividades`).then(p => p.atividades || []),
    addActivity: (id, body) => request(`${legacy}/${id}/atividades`, {method: 'POST', body}),
    toggleActivity: (activityId, concluida) => request(`${legacy}/atividades/${activityId}/concluir`, {method: 'PATCH', body: {concluida}}),

    convert: (id, body) => request(`${legacy}/${id}/converter-cliente`, {method: 'POST', body}),
    lookupCnpj: cnpj => request(`/api/buscar_cnpj/${cnpj}`).then(p => p.data || p),
    updateCompany: (id, body) => request(`${root}/leads/${id}/empresa`, {method: 'PATCH', body}),

    golden: (trimestre, executivo) => request(`${root}/golden${qs({trimestre, executivo})}`).then(p => p.data),
    validateGolden: body => request(`${root}/golden/validar`, {method: 'POST', body}).then(p => p.data),
    createGolden: body => request(`${root}/golden`, {method: 'POST', body}).then(p => p.data),
    updateGolden: (id, body) => request(`${root}/golden/${id}`, {method: 'PATCH', body: typeof body === 'string' ? {status: body} : body}),
    leadGolden: id => request(`${root}/leads/${id}/golden`).then(p => p.data.conta),

    operation: executivo => request(`${root}/operacao${qs({executivo})}`).then(p => p.data),
    cadenceModels: () => request(`${root}/cadencias`).then(p => p.data.modelos),
    leadCadences: id => request(`${root}/leads/${id}/cadencias`).then(p => p.data.inscricoes),
    enrollContact: (contactId, idCadencia) => request(`${root}/contatos/${contactId}/cadencia`, {method: 'POST', body: {id_cadencia: idCadencia || null}}),
    enrollLead: id => request(`${root}/leads/${id}/cadencia`, {method: 'POST', body: {}}).then(p => p.data),
    stepAction: (inscricaoId, acao, nota, idGancho) => request(`${root}/inscricoes/${inscricaoId}/${acao}`, {method: 'POST', body: {nota: nota || '', id_gancho: idGancho || null}}).then(p => p.data),
    writeMessage: body => request(`${root}/mensagens/gerar`, {method: 'POST', body}).then(p => p.data),
    marketContext: id => request(`${root}/leads/${id}/contexto`, {method: 'POST', body: {}}).then(p => p.data),
    hooks: (id, idContato) => request(`${root}/leads/${id}/ganchos${qs({id_contato: idContato})}`).then(p => p.data.ganchos),
    createHook: (id, body) => request(`${root}/leads/${id}/ganchos`, {method: 'POST', body}).then(p => p.data),
    updateHook: (hookId, body) => request(`${root}/ganchos/${hookId}`, {method: 'PATCH', body}),
    suggestFocus: id => request(`${root}/leads/${id}/foco/sugerir`, {method: 'POST', body: {}}).then(p => p.data.foco),
    preferences: () => request(`${root}/preferencias`).then(p => p.data),
    savePreferences: body => request(`${root}/preferencias`, {method: 'PUT', body}).then(p => p.data),
    removeGolden: id => request(`${root}/golden/${id}`, {method: 'DELETE'}),

    candidates: id => request(`${root}/leads/${id}/candidatos`).then(p => p.data.candidatos),
    discover: (id, fonte) => request(`${root}/leads/${id}/descobrir`, {method: 'POST', body: {fonte}}).then(p => p.data),
    approveCandidate: (candidateId, revelar, papel) => request(`${root}/candidatos/${candidateId}/aprovar`, {method: 'POST', body: {revelar, papel}}).then(p => p.data),
    discardCandidate: candidateId => request(`${root}/candidatos/${candidateId}/descartar`, {method: 'POST', body: {}}),
    linkCandidate: (candidateId, revelar) => request(`${root}/candidatos/${candidateId}/vincular`, {method: 'POST', body: {revelar: !!revelar}}).then(p => p.data),
    duplicates: id => request(`${root}/leads/${id}/duplicados`).then(p => p.data.pares),
    mergeContacts: (contactId, idDuplicado) => request(`${root}/contatos/${contactId}/mesclar`, {method: 'POST', body: {id_duplicado: idDuplicado}}).then(p => p.data),
    wrongData: (contactId, campo) => request(`${root}/contatos/${contactId}/dado-errado`, {method: 'POST', body: {campo}}),
    findEmail: contactId => request(`${root}/contatos/${contactId}/achar-email`, {method: 'POST', body: {}}).then(p => p.data),
    requestPhone: contactId => request(`${root}/contatos/${contactId}/celular`, {method: 'POST', body: {}}).then(p => p.data),
    revealContact: contactId => request(`${root}/contatos/${contactId}/revelar`, {method: 'POST', body: {}}).then(p => p.data),
    updateProfile: (contactId, body) => request(`${root}/contatos/${contactId}/perfil`, {method: 'PATCH', body}),

    communications: id => request(`${legacy}/${id}/comunicacoes`).then(p => p.comunicacoes || p.data || []),
    saveCommunication: (id, body) => request(`${legacy}/${id}/comunicacoes`, {method: 'POST', body}),
    generateCommunication: body => request('/api/ia/gerar-comunicacao', {method: 'POST', body}),
  };
}
