import React, {useEffect, useRef, useState} from 'react';
import {Icon} from './Icon';
import {useWorkspaceNotifications} from './WorkspaceNotifications';

const destinations = [
  ['home', 'Home', 'home'],
  ['projects', 'Projetos', 'folder'],
  ['brands', 'Marcas', 'brand'],
  ['library', 'Biblioteca', 'file'],
  ['automations', 'Automações', 'pulse'],
];

export function WorkspaceMobileChrome({title = 'Workspace', eyebrow = 'Workspace', workspaceName = '', links = {}, contextItems = []}) {
  const notifications = useWorkspaceNotifications();
  const [open, setOpen] = useState(false);
  const trigger = useRef(null);
  const panel = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = event => {
      if (event.key === 'Escape') {
        setOpen(false);
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = [...(panel.current?.querySelectorAll('a[href],button:not([disabled])') || [])];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    window.requestAnimationFrame(() => panel.current?.querySelector('a,button')?.focus());
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener('keydown', onKey);
      window.requestAnimationFrame(() => trigger.current?.focus());
    };
  }, [open]);
  const go = () => setOpen(false);
  const availableContextItems = contextItems.filter(item => item?.href || item?.url).slice(0, 8);
  return <>
    <header className="cadu-ds-mobile-chrome">
      <button ref={trigger} type="button" onClick={() => setOpen(true)} aria-label="Abrir menu" aria-haspopup="dialog" aria-expanded={open} aria-controls="workspace-mobile-navigation"><Icon name="menu" size={20}/></button>
      <div className="cadu-ds-mobile-chrome__context"><strong>{title}</strong></div>
      <div className="cadu-ds-mobile-chrome__actions">{notifications.open && notifications.pending.length > 0 && <button type="button" className="cadu-ds-mobile-chrome__notifications" onClick={notifications.open} aria-label="Abrir notificações"><Icon name="pulse" size={18}/><i>{notifications.pending.length > 9 ? '9+' : notifications.pending.length}</i></button>}<button type="button" onClick={() => setOpen(true)} aria-label="Mais opções"><span aria-hidden="true">•••</span></button></div>
    </header>
    {open && <div className="cadu-ds-mobile-navigation" role="presentation" onPointerDown={event => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section ref={panel} id="workspace-mobile-navigation" role="dialog" aria-modal="true" aria-label="Navegação do Workspace">
        <header><div><strong>Cadu</strong></div><button type="button" onClick={() => setOpen(false)} aria-label="Fechar navegação"><Icon name="close" size={18}/></button></header>
        <div className="cadu-ds-mobile-navigation__quick">{links.newConversation && <a href={links.newConversation} onClick={go}><Icon name="compose" size={18}/>Nova conversa</a>}<a href={links.search || links.conversations || '#'} onClick={go}><Icon name="search" size={18}/>Buscar</a></div>
        <div className="cadu-ds-mobile-navigation__workspace"><strong>{workspaceName || 'Workspace atual'}</strong><small>Workspace</small>{links.agency && <a href={links.agency} onClick={go}>Trocar workspace</a>}</div>
        <nav aria-label="Áreas principais">{destinations.map(([key, label, icon]) => links[key] ? <a key={key} href={links[key]} onClick={go}><Icon name={icon} size={18}/><span>{label}</span></a> : null)}</nav>
        {availableContextItems.length > 0 && <div className="cadu-ds-mobile-navigation__context"><span>Fixadas e recentes</span>{availableContextItems.map((item, index) => <a key={item.id || item.href || index} href={item.href || item.url} onClick={go}><b>{item.title || item.name || 'Item do Workspace'}</b>{item.detail && <small>{item.detail}</small>}</a>)}</div>}
        {links.agency && <div className="cadu-ds-mobile-navigation__account"><a href={links.agency} onClick={go}><Icon name="home" size={18}/>Conta</a></div>}
      </section>
    </div>}
  </>;
}
