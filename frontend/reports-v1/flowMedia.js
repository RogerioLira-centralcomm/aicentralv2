// Media planning for each traffic origin: who is reached (segment), with what (creatives) and how it is set up.
export const SEGMENT_KINDS = Object.freeze([
  ['prospeccao', 'Prospecção (público frio)'], ['interesses', 'Interesses e comportamento'], ['palavras_chave', 'Palavras-chave'],
  ['semelhante', 'Semelhante (lookalike)'], ['remarketing', 'Remarketing'], ['base', 'Base de clientes'], ['outro', 'Outro'],
]);
export const OBJECTIVES = Object.freeze([
  ['leads', 'Geração de leads'], ['vendas', 'Vendas'], ['trafego', 'Tráfego'], ['alcance', 'Alcance e reconhecimento'],
  ['engajamento', 'Engajamento'], ['video', 'Visualizações de vídeo'], ['mensagens', 'Mensagens'], ['relacionamento', 'Relacionamento'],
]);
export const CREATIVE_FORMATS = Object.freeze([
  ['imagem', 'Imagem'], ['video', 'Vídeo'], ['carrossel', 'Carrossel'], ['stories', 'Stories / Reels'], ['texto', 'Anúncio de texto'], ['mensagem', 'Mensagem'],
]);
export const CREATIVE_STATUSES = Object.freeze([['rascunho', 'Rascunho'], ['em_aprovacao', 'Em aprovação'], ['aprovado', 'Aprovado']]);
export const LIMITS = Object.freeze({creatives: 20, setup: 20});

const PAID = new Set(['google', 'youtube', 'meta', 'instagram', 'tiktok', 'linkedin', 'dv360', 'retargeting']);
const MESSAGING = new Set(['email', 'sms', 'whatsapp', 'push', 'phone']);
const UTM_SOURCE = {google: 'google', youtube: 'youtube', meta: 'facebook', instagram: 'instagram', tiktok: 'tiktok', linkedin: 'linkedin',
  dv360: 'dv360', retargeting: 'retargeting', email: 'email', sms: 'sms', whatsapp: 'whatsapp', push: 'push', organic: 'google', social: 'social', affiliate: 'afiliado', qr: 'qrcode'};
const UTM_MEDIUM = {google: 'cpc', youtube: 'video', meta: 'paid_social', instagram: 'paid_social', tiktok: 'paid_social', linkedin: 'paid_social',
  dv360: 'display', retargeting: 'remarketing', email: 'email', sms: 'sms', whatsapp: 'whatsapp', push: 'push', organic: 'organic', social: 'social', affiliate: 'affiliate', qr: 'offline'};
const FORMATS_BY_PLATFORM = {google: ['texto'], youtube: ['video'], meta: ['imagem', 'video'], instagram: ['stories', 'imagem'], tiktok: ['video'],
  linkedin: ['imagem'], dv360: ['imagem', 'video'], retargeting: ['imagem'], email: ['mensagem'], sms: ['mensagem'], whatsapp: ['mensagem'], push: ['mensagem']};
const label = (list, value) => list.find(([id]) => id === value)?.[1] || '';
export const segmentKindLabel = value => label(SEGMENT_KINDS, value);
export const objectiveLabel = value => label(OBJECTIVES, value);
export const creativeFormatLabel = value => label(CREATIVE_FORMATS, value);
export const creativeStatusLabel = value => label(CREATIVE_STATUSES, value);

export const isPaidPlatform = platform => PAID.has(platform);

export function defaultSetup(platform) {
  if (PAID.has(platform)) return ['Conta e acessos confirmados', 'Pixel ou tag da plataforma instalado', 'Evento de conversão configurado',
    'Públicos criados', 'Orçamento e período definidos', 'Links com UTM aplicados nos anúncios'];
  if (MESSAGING.has(platform)) return ['Lista ou segmento definido', 'Remetente configurado', 'Mensagens revisadas', 'Links com UTM aplicados', 'Envio agendado'];
  return ['Links com UTM aplicados nas publicações'];
}

const id = () => crypto.randomUUID().slice(0, 8);
export function defaultMedia(platform, objective = '') {
  const formats = FORMATS_BY_PLATFORM[platform] || [];
  return {
    ...(objective ? {objective} : {}),
    creatives: formats.map((format, index) => ({id: id(), name: `Criativo ${index + 1}`, format, status: 'rascunho'})),
    setup: defaultSetup(platform).map(text => ({id: id(), text, done: false})),
  };
}

const slug = value => String(value || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);

/** Tagged landing URL for one origin; empty until the flow has a site and the entry page has its address. */
export function utmLink(node, {platform, host, entryPath, flowName}) {
  const utm = node.media?.utm || {};
  const params = {
    utm_source: utm.source || UTM_SOURCE[platform] || slug(node.title),
    utm_medium: utm.medium || UTM_MEDIUM[platform] || 'referral',
    utm_campaign: utm.campaign || slug(flowName) || 'campanha',
    ...((utm.content || node.segment?.name) ? {utm_content: utm.content || slug(node.segment.name)} : {}),
  };
  const query = new URLSearchParams(params).toString();
  return {params, url: host && entryPath ? `https://${host}${entryPath}?${query}` : '', query};
}

/** Approval and setup progress for one origin, as shown in the review page and the production sheet. */
export function mediaProgress(node) {
  const creatives = node.media?.creatives || [];
  const setup = node.media?.setup || [];
  return {
    creatives: {done: creatives.filter(item => item.status === 'aprovado').length, total: creatives.length},
    setup: {done: setup.filter(item => item.done).length, total: setup.length},
    missing: [...setup.filter(item => !item.done).map(item => item.text),
      ...(creatives.some(item => item.status !== 'aprovado') ? [`${creatives.filter(item => item.status !== 'aprovado').length} criativo(s) sem aprovação`] : [])],
  };
}

/** First page each origin leads to, used to build its tagged link. */
export function entryPageFor(config, nodeId) {
  const byId = new Map((config.nodes || []).map(node => [node.id, node]));
  const seen = new Set([nodeId]);
  let frontier = [nodeId];
  while (frontier.length) {
    const next = [];
    for (const id of frontier) for (const edge of config.edges || []) {
      if (edge.from !== id || seen.has(edge.to)) continue;
      const target = byId.get(edge.to);
      if (!target) continue;
      if (['page', 'form', 'conversion'].includes(target.type)) return target;
      seen.add(edge.to); next.push(edge.to);
    }
    frontier = next;
  }
  return null;
}
