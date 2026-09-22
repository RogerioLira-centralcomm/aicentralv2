const HOME_ATTACHMENTS_KEY = 'cadu:home-pending-attachments';
const CHAT_CONTEXT_KEY = 'cadu:workspace-chat-context';

export function takePendingHomeAttachments(storage) {
  try {
    const target = storage === undefined ? globalThis.sessionStorage : storage;
    if (!target) return [];
    const raw = target.getItem(HOME_ATTACHMENTS_KEY);
    target.removeItem(HOME_ATTACHMENTS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(item => item?.id) : [];
  } catch (_) {
    return [];
  }
}

export function persistConversationContext(context, storage) {
  try {
    const target = storage === undefined ? globalThis.localStorage : storage;
    if (!target) return false;
    if (context?.project_ref || context?.brand_ref) {
      target.setItem(CHAT_CONTEXT_KEY, JSON.stringify(context));
    } else {
      target.removeItem(CHAT_CONTEXT_KEY);
    }
    return true;
  } catch (_) {
    return false;
  }
}
