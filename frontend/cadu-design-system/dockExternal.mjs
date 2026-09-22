// Raster app icons published by the products or on their official app listings.
// A failed remote image falls back to the shortcut initials in VisualIdentity.
const PROVIDER_ICONS = {
  trello: 'https://play-lh.googleusercontent.com/n61MGuPfTK5t8ETbAAmc2nwy6CQnw5BFCqPSTRdsPbUc2e9MJhKu4GGB6qYgi2-B8-Cx6LVPPGqUKNkgPnO-xg=w240-h480-rw',
  asana: 'https://brand.asana.biz/image/upload/f_auto:image,fl_preserve_transparency/v1696462483/asana_favicon_180x180.png',
  drive: 'https://play-lh.googleusercontent.com/chc-Fx3Qi3BisTZw1aOteYK_XkMHUiXKRbX2Hc8shyFI8pYt7DcyUPzVwLGJKIeKCKDD6nFVhEtUrIaEyzcnmA=s0-br30',
  meet: 'https://play-lh.googleusercontent.com/G7KKIhzS9ZKa5iCVAkt1P8vXvVWPbaV9JjkMsgb4BcEjqov0TysngtuJ4jE17DYhi4wblu4UXJDWjr7SYgnZ6A=w240-h480-rw',
  slack: 'https://play-lh.googleusercontent.com/C9w-zv2PzpS-Rr9L8PUveRfv36lfYiB2kPKiEy45ucveIYMCoUW1nKQls5VxXSJyUsNxC_s7nFqpIAbqlLbSKA',
  miro: 'https://framerusercontent.com/images/6FBG66PBxjV2QFaDfIdUi5mi9A.png',
  chatgpt: 'https://chatgpt.com/unauth-mweb/apple-touch-icon.png',
  claude: 'https://assets-proxy.anthropic.com/claude-ai/v2/assets/v1/c129d018a-0ZbJsTbu.png',
  gemini: 'https://www.gstatic.com/lamda/images/gemini_sparkle_4g_512_lt_f94943af3be039176192d.png',
  notebooklm: 'https://play-lh.googleusercontent.com/gQAp2_D_utKEdDI4Nr6_We5DAl2y7kPzoBKo8IE36rSDZyM_R5emL_t9zG4wHop8iMbFHzDVMlYKNTNSnzPCVw',
  meta: 'https://www.google.com/s2/favicons?domain=facebook.com&sz=128',
  tiktok: 'https://www.google.com/s2/favicons?domain=tiktok.com&sz=128',
  linkedin: 'https://www.google.com/s2/favicons?domain=linkedin.com&sz=128',
  instagram: 'https://www.google.com/s2/favicons?domain=instagram.com&sz=128',
  pinterest: 'https://www.google.com/s2/favicons?domain=pinterest.com&sz=128',
  googleAds: 'https://www.google.com/s2/favicons?domain=ads.google.com&sz=128',
  analytics: 'https://www.google.com/s2/favicons?domain=analytics.google.com&sz=128',
  gmail: 'https://www.google.com/s2/favicons?domain=mail.google.com&sz=128',
  canva: 'https://www.google.com/s2/favicons?domain=canva.com&sz=128',
  clickup: 'https://www.google.com/s2/favicons?domain=clickup.com&sz=128',
  whatsapp: 'https://www.google.com/s2/favicons?domain=whatsapp.com&sz=128',
};

export function dockProviderLogo(rawUrl) {
  let host;
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password || (parsed.port && parsed.port !== '443')) return '';
    host = parsed.hostname.toLowerCase();
  } catch (_) { return ''; }
  const isHost = domain => host === domain || host.endsWith(`.${domain}`);
  if (isHost('trello.com')) return PROVIDER_ICONS.trello;
  if (isHost('asana.com')) return PROVIDER_ICONS.asana;
  if (isHost('slack.com')) return PROVIDER_ICONS.slack;
  if (host === 'drive.google.com') return PROVIDER_ICONS.drive;
  if (host === 'meet.google.com') return PROVIDER_ICONS.meet;
  if (isHost('miro.com')) return PROVIDER_ICONS.miro;
  if (isHost('chatgpt.com') || host === 'chat.openai.com') return PROVIDER_ICONS.chatgpt;
  if (isHost('claude.ai')) return PROVIDER_ICONS.claude;
  if (host === 'gemini.google.com') return PROVIDER_ICONS.gemini;
  if (host === 'notebooklm.google.com' || host === 'notebook.google.com') return PROVIDER_ICONS.notebooklm;
  if (isHost('facebook.com') || isHost('business.facebook.com') || isHost('meta.com')) return PROVIDER_ICONS.meta;
  if (isHost('tiktok.com') || isHost('ads.tiktok.com')) return PROVIDER_ICONS.tiktok;
  if (isHost('linkedin.com')) return PROVIDER_ICONS.linkedin;
  if (isHost('instagram.com')) return PROVIDER_ICONS.instagram;
  if (isHost('pinterest.com') || isHost('ads.pinterest.com')) return PROVIDER_ICONS.pinterest;
  if (host === 'ads.google.com') return PROVIDER_ICONS.googleAds;
  if (host === 'analytics.google.com') return PROVIDER_ICONS.analytics;
  if (host === 'mail.google.com') return PROVIDER_ICONS.gmail;
  if (isHost('canva.com')) return PROVIDER_ICONS.canva;
  if (isHost('clickup.com')) return PROVIDER_ICONS.clickup;
  if (isHost('whatsapp.com') || host === 'web.whatsapp.com') return PROVIDER_ICONS.whatsapp;
  return '';
}

export function dockExternalPresentation(rawUrl) {
  let url;
  try { url = new URL(rawUrl); } catch (_) { return null; }
  if (url.protocol !== 'https:' || url.username || url.password || (url.port && url.port !== '443')) return null;
  const host = url.hostname.toLowerCase();
  if (/\.(?:avif|gif|jpe?g|png|svg|webp)$/i.test(url.pathname)) {
    return {kind: 'image', url: url.href, host};
  }
  if (host === 'meet.google.com' || host === 'teams.microsoft.com' || host === 'zoom.us' || host.endsWith('.zoom.us')) {
    return {kind: 'external', url: url.href, host};
  }
  if (host === 'drive.google.com') {
    const file = url.pathname.match(/^\/file\/d\/([^/]+)/i);
    if (file) return {kind: 'iframe', url: url.href, embedUrl: `https://drive.google.com/file/d/${encodeURIComponent(file[1])}/preview`, host};
  }
  if (host === 'docs.google.com' && /^\/(?:document|spreadsheets|presentation)\/d\//.test(url.pathname)) {
    const preview = new URL(url.href);
    preview.pathname = preview.pathname.replace(/\/(?:edit|view|preview)\/?$/, '/preview');
    preview.search = '';
    return {kind: 'iframe', url: url.href, embedUrl: preview.href, host};
  }
  return {kind: 'iframe', url: url.href, embedUrl: url.href, host};
}
