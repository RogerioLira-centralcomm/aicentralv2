// Origins panel of the flow monitor: the origins the flow draws, plus the ones that really sent visits.
// Classification mirrors origin_platform in reports_flow_metrics.py (a source label is a utm_source or a referrer host).

const AI_AGENTS = {
  chatgpt: {names: ['chatgpt', 'openai'], domains: ['chatgpt.com', 'chat.openai.com', 'openai.com']},
  gemini: {names: ['gemini', 'bard'], domains: ['gemini.google.com', 'bard.google.com']},
  claude: {names: ['claude', 'anthropic'], domains: ['claude.ai']},
};
const ALIASES = {
  google: ['google', 'googleads', 'google_ads', 'adwords', 'gads', 'google-ads'],
  meta: ['facebook', 'fb', 'meta', 'instagram', 'ig', 'facebook_ads', 'meta_ads'],
  tiktok: ['tiktok', 'tiktok_ads'], linkedin: ['linkedin', 'linkedin_ads', 'lnkd'], youtube: ['youtube', 'yt'],
  email: ['email', 'e-mail', 'newsletter', 'mailchimp', 'rdstation', 'hubspot'], whatsapp: ['whatsapp', 'wa'], sms: ['sms'],
};
const SEARCH_DOMAINS = ['google.com', 'google.com.br', 'google.pt', 'google.co.uk', 'google.es', 'google.de', 'google.fr', 'google.it', 'google.ca', 'google.com.ar', 'google.com.mx', 'google.cl', 'google.co', 'bing.com', 'search.yahoo.com', 'yahoo.com', 'duckduckgo.com', 'ecosia.org', 'yandex.com', 'yandex.ru', 'baidu.com', 'search.brave.com'];
const NOT_SEARCH = ['mail.', 'accounts.', 'docs.', 'drive.', 'maps.', 'play.', 'support.', 'news.', 'calendar.'];
const SOCIAL_DOMAINS = ['facebook.com', 'fb.com', 'fb.me', 'messenger.com', 'instagram.com', 'linkedin.com', 'lnkd.in', 't.co', 'twitter.com', 'x.com', 'tiktok.com', 'youtube.com', 'youtu.be', 'pinterest.com', 'threads.net', 'reddit.com'];
const NODE_PLATFORMS = {facebook: 'meta', instagram: 'meta', dv360: 'google', organic_search: 'organic', organic_social: 'social', communication: 'email'};

export const ORIGIN_LABELS = {direct: 'Acesso direto', organic: 'Busca orgânica', social: 'Redes sociais', referral: 'Outros sites',
  google: 'Google Ads', meta: 'Meta Ads', tiktok: 'TikTok Ads', linkedin: 'LinkedIn Ads', youtube: 'YouTube', email: 'E-mail',
  whatsapp: 'WhatsApp', sms: 'SMS', campaign: 'Outras campanhas', chatgpt: 'ChatGPT', gemini: 'Gemini', claude: 'Claude'};
export const AI_PLATFORMS = Object.keys(AI_AGENTS);

const bare = value => String(value || '').toLowerCase().trim().replace(/^\.+|\.+$/g, '').replace(/^www\./, '');
const inDomain = (host, domains) => domains.some(domain => host === domain || host.endsWith(`.${domain}`));

export function aiAgentFor(value) {
  const host = bare(value);
  return AI_PLATFORMS.find(id => AI_AGENTS[id].names.includes(host) || inDomain(host, AI_AGENTS[id].domains)) || null;
}

/** Platform id of a source label, in the server's vocabulary. */
export function classifyOrigin(label) {
  const value = bare(label);
  if (!value || value === 'website') return 'direct';
  const agent = aiAgentFor(value);
  if (agent) return agent;
  const named = Object.keys(ALIASES).find(id => ALIASES[id].includes(value));
  if (named) return named;
  if (!value.includes('.')) return 'campaign';
  if (!NOT_SEARCH.some(prefix => value.startsWith(prefix)) && inDomain(value, SEARCH_DOMAINS)) return 'organic';
  if (inDomain(value, SOCIAL_DOMAINS)) return 'social';
  return 'referral';
}

export function nodePlatform(node) {
  const platform = node.source || String(node.kind || '').split('.').slice(1).join('.');
  return NODE_PLATFORMS[platform] || platform;
}

/**
 * Rows for the panel: every origin the flow draws (in the flow's order), organic search and direct always,
 * then any other origin that sent page views. Each row keeps the labels seen and its page views.
 */
export function flowOriginRows(config, events = []) {
  const totals = new Map();
  for (const item of events) {
    if (item.event_kind !== 'page_view') continue;
    const platform = classifyOrigin(item.source_label);
    const row = totals.get(platform) || {total: 0, sources: new Set()};
    row.total += Number(item.total || 0);
    if (item.source_label && item.source_label !== 'Website') row.sources.add(item.source_label);
    totals.set(platform, row);
  }
  const drawn = [];
  for (const node of (config?.nodes || [])) {
    if (node.type !== 'source') continue;
    const platform = nodePlatform(node);
    if (platform && !drawn.some(item => item.platform === platform)) drawn.push({platform, title: node.title});
  }
  const order = [...drawn];
  for (const platform of ['organic', 'direct']) if (!order.some(item => item.platform === platform)) order.push({platform});
  for (const platform of totals.keys()) if (!order.some(item => item.platform === platform)) order.push({platform});
  return order.map(({platform, title}) => ({platform, label: ORIGIN_LABELS[platform] || title || platform,
    drawn: drawn.some(item => item.platform === platform), total: totals.get(platform)?.total || 0, sources: [...(totals.get(platform)?.sources || [])]}));
}
