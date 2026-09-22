export const ARTIFACT_SIDE_COOKIE = 'cadu-artifact-side';
export const CONVERSATION_MOBILE_QUERY = '(max-width: 1199px)';

export function isConversationMobile(matchMedia) {
  if (typeof matchMedia === 'function') return Boolean(matchMedia(CONVERSATION_MOBILE_QUERY)?.matches);
  if (typeof globalThis.matchMedia !== 'function') return false;
  return Boolean(globalThis.matchMedia(CONVERSATION_MOBILE_QUERY)?.matches);
}

export function artifactKey(item) {
  return String(item?.tabKey || item?.id || '');
}

export function readCookie(key) {
  const escaped = String(key).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]+)`))?.[1] || '';
}

export function writeCookie(key, value) {
  document.cookie = `${key}=${value}; Max-Age=31536000; Path=/; SameSite=Lax`;
}

export async function copyText(value) {
  if (!value) return false;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return true;
  }

  const field = document.createElement('textarea');
  field.value = value;
  field.setAttribute('readonly', '');
  field.style.position = 'fixed';
  field.style.opacity = '0';
  document.body.appendChild(field);
  field.select();

  let copied = false;
  try { copied = document.execCommand('copy'); } catch (_) { copied = false; }
  field.remove();
  return copied;
}
