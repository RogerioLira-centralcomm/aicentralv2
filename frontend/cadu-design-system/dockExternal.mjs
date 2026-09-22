const TRELLO_LOGO = new URL('../../aicentralv2/static/images/cadu/technology-logos/trello.svg', import.meta.url).href;
const ASANA_LOGO = new URL('../../aicentralv2/static/images/cadu/technology-logos/asana.svg', import.meta.url).href;
const SLACK_LOGO = new URL('../../aicentralv2/static/images/cadu/technology-logos/slack.svg', import.meta.url).href;

export function dockProviderLogo(rawUrl) {
  let host;
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password || (parsed.port && parsed.port !== '443')) return '';
    host = parsed.hostname.toLowerCase();
  } catch (_) { return ''; }
  const isHost = domain => host === domain || host.endsWith(`.${domain}`);
  if (isHost('trello.com')) return TRELLO_LOGO;
  if (isHost('asana.com')) return ASANA_LOGO;
  if (isHost('slack.com')) return SLACK_LOGO;
  if (host === 'drive.google.com') return 'https://drive.google.com/favicon.ico';
  if (host === 'meet.google.com') return 'https://meet.google.com/favicon.ico';
  if (isHost('miro.com')) return 'https://miro.com/favicon.ico';
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
