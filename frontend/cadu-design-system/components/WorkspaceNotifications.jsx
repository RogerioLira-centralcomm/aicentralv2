import React, {createContext, useContext, useEffect, useMemo, useState} from 'react';
import {csrf} from '../../conversations-v2/lib/api';
import {WorkspaceNotificationCenter} from './WorkspaceNotificationCenter';

const WorkspaceNotificationsContext = createContext(null);

export function WorkspaceNotificationsProvider({bootstrap, children}) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const endpoint = bootstrap?.endpoints?.notifications || bootstrap?.urls?.notifications || '/workspace/api/notificacoes';
  useEffect(() => {
    let active = true;
    const refresh = () => fetch(endpoint, {credentials:'same-origin', headers:{Accept:'application/json'}})
      .then(response => response.ok ? response.json() : Promise.reject(new Error('notifications unavailable')))
      .then(value => { if (active) setItems(value.items || []); })
      .catch(() => {});
    refresh();
    const timer = window.setInterval(refresh, 60000);
    return () => { active = false; window.clearInterval(timer); };
  }, [endpoint]);
  const pending = useMemo(() => items.filter(item => ['approval','attention','failure'].includes(item.kind) && !['read','resolved','archived'].includes(item.status)), [items]);
  const openItem = item => {
    setOpen(false);
    if (item.id && /^[0-9a-f-]{36}$/i.test(String(item.id))) {
      fetch(`${endpoint}/${item.id}/read`, {method:'POST', credentials:'same-origin', headers:{Accept:'application/json','X-CSRF-Token':bootstrap?.csrf || csrf()}}).catch(() => {});
      setItems(current => current.map(entry => entry.id === item.id ? {...entry, status:entry.status === 'unread' ? 'read' : entry.status} : entry));
    }
    if (item.conversationId) {
      const destination = new URL(bootstrap?.urls?.conversations || bootstrap?.urls?.newConversation || '/chat', window.location.origin);
      destination.searchParams.set('conversation_id', item.conversationId);
      window.location.assign(`${destination.pathname}${destination.search}`);
    } else if (item.projectRef?.startsWith('ci:')) {
      window.location.assign(`/projetos/${encodeURIComponent(item.projectRef.slice(3))}`);
    }
  };
  const value = {items, pending, open:() => setOpen(true)};
  return <WorkspaceNotificationsContext.Provider value={value}>{children}{open && <WorkspaceNotificationCenter items={items} onClose={() => setOpen(false)} onOpenItem={openItem}/>}</WorkspaceNotificationsContext.Provider>;
}

export function useWorkspaceNotifications() {
  return useContext(WorkspaceNotificationsContext) || {items:[], pending:[], open:undefined};
}
