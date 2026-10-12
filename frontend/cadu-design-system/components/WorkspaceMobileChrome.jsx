import React, {useEffect, useRef, useState} from 'react';
import {Icon} from './Icon';
import {useWorkspaceNotifications} from './WorkspaceNotifications';
import {workspaceChatHref, workspaceMobileDestinationItems, workspaceSolutionItems} from '../workspaceSolutions';

export function WorkspaceMobileChrome({title = 'Workspace', eyebrow = 'Workspace', workspaceName = '', links = {}, contextItems = [], accountItems = [], logo = '', solutionIcons = {}}) {
  const notifications = useWorkspaceNotifications();
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
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
      const focusable = [...(panel.current?.querySelectorAll('a[href],button:not([disabled]),summary') || [])];
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
  useEffect(() => {
    if (!switching) return undefined;
    const onKey = event => { if (event.key === 'Escape') setSwitching(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [switching]);
  const go = () => setOpen(false);
  const availableContextItems = (() => {
    // Alternate kinds so a long run of conversations never hides every project.
    const usable = contextItems.filter(item => item?.href || item?.url);
    const projects = usable.filter(item => item.detail === 'Projeto');
    const others = usable.filter(item => item.detail !== 'Projeto');
    return [others[0], projects[0], others[1], projects[1], ...others.slice(2), ...projects.slice(2)].filter(Boolean).slice(0, 4);
  })();
  const destinations = workspaceMobileDestinationItems(links);
  const brandMark = logo || solutionIcons.workspace || '';
  const sheetSolutions = workspaceSolutionItems({urls: links, solutionIcons}).filter(item => item.href || item.id === 'workspace');
  const chatSearchHref = links.search || workspaceChatHref(links, {history: true});
  return <>
    <header className="cadu-ds-mobile-chrome">
      <button ref={trigger} type="button" onClick={() => setOpen(true)} aria-label="Abrir menu" aria-haspopup="dialog" aria-expanded={open} aria-controls="workspace-mobile-navigation"><Icon name="menu" size={20}/></button>
      <div className="cadu-ds-mobile-chrome__context"><button type="button" className="cadu-ds-mobile-chrome__brand" onClick={() => setSwitching(true)} aria-label={`Trocar de solução Cadu. Atual: ${title}`} aria-haspopup="dialog" aria-expanded={switching}>{brandMark ? <img src={brandMark} alt="" width="26" height="26"/> : <strong>Cadu</strong>}<Icon name="chevron" size={14}/></button></div>
      <div className="cadu-ds-mobile-chrome__actions">{notifications.open && notifications.pending.length > 0 && <button type="button" className="cadu-ds-mobile-chrome__notifications" onClick={notifications.open} aria-label="Abrir notificações"><Icon name="pulse" size={18}/><i>{notifications.pending.length > 9 ? '9+' : notifications.pending.length}</i></button>}</div>
    </header>
    {switching && <div className="cadu-ds-mobile-sheet" role="presentation" onPointerDown={event => { if (event.target === event.currentTarget) setSwitching(false); }}>
      <section role="dialog" aria-modal="true" aria-label="Soluções Cadu">
        <span className="cadu-ds-mobile-sheet__grip" aria-hidden="true"/>
        <h2>Para onde você quer ir?</h2>
        <div className="cadu-ds-mobile-sheet__list">{sheetSolutions.map(item => {
          const desktopOnly = item.id === 'studio';
          return <a key={item.id} href={item.href || links.home || '/'} onClick={() => setSwitching(false)} aria-current={item.id === 'workspace' ? 'page' : undefined}>{item.icon && <img src={item.icon} alt="" width="36" height="36"/>}<span><b>{item.name}</b><small>{desktopOnly ? 'Melhor no computador' : item.description}</small></span></a>;
        })}</div>
        <button type="button" onClick={() => setSwitching(false)}>Fechar</button>
      </section>
    </div>}
    {open && <div className="cadu-ds-mobile-navigation" role="presentation" onPointerDown={event => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section ref={panel} id="workspace-mobile-navigation" role="dialog" aria-modal="true" aria-label="Navegação do Workspace">
        <header><div className="cadu-ds-mobile-navigation__brand">{brandMark && <img src={brandMark} alt="" width="28" height="28"/>}<span><strong>Cadu</strong>{workspaceName && <small>{workspaceName}</small>}</span></div><button type="button" onClick={() => setOpen(false)} aria-label="Fechar navegação"><Icon name="close" size={18}/></button></header>
        <div className="cadu-ds-mobile-navigation__body">
          <div className="cadu-ds-mobile-navigation__primary">{links.newConversation && <a href={links.newConversation} onClick={go}><Icon name="compose" size={18}/>Novo chat</a>}{chatSearchHref && <a href={chatSearchHref} onClick={go} aria-label="Buscar chats"><Icon name="search" size={18}/></a>}</div>
          <nav aria-label="Áreas principais">{destinations.map(item => <a key={item.id} href={item.href} onClick={go}><Icon name={item.icon} size={18}/><span>{item.name}</span></a>)}</nav>
          {availableContextItems.length > 0 && <div className="cadu-ds-mobile-navigation__context"><span>Recentes</span>{availableContextItems.map((item, index) => <a key={item.id || item.href || index} href={item.href || item.url} onClick={go}><b>{item.title || item.name || 'Item do Workspace'}</b>{item.detail && <small>{item.detail}</small>}</a>)}</div>}
          {accountItems.length > 0 && <details className="cadu-ds-mobile-navigation__account"><summary>Conta e configurações<Icon name="chevron" size={14}/></summary><nav aria-label="Seções da conta">{accountItems.map(item => <a key={item.id} href={item.href} onClick={go} aria-current={item.active ? 'page' : undefined}><Icon name={item.icon} size={18}/><span>{item.name}</span></a>)}</nav></details>}
        </div>
        <footer className="cadu-ds-mobile-navigation__footer">
          {links.agency && <a className="cadu-ds-mobile-navigation__account-link" href={links.agency} onClick={go}><Icon name="home" size={18}/>Conta e workspace</a>}
        </footer>
      </section>
    </div>}
  </>;
}
