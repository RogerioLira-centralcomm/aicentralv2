import React, {useMemo, useState} from 'react';
import {Icon} from '../lib/icons';

const primary = [
  ['home', 'Início', 'home'],
  ['compose', 'Novo chat', 'newChat'],
  ['folder', 'Projetos', 'projects'],
  ['file', 'Docs', 'docs'],
  ['brand', 'Marcas', 'brands'],
];

export function Sidebar({bootstrap, conversations, activeId, onOpen, onNew, mobileOpen, onMobileClose, loading, openingId}) {
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => conversations.filter(item =>
    String(item.title || '').toLocaleLowerCase().includes(query.toLocaleLowerCase())
  ), [conversations, query]);
  const initials = String(bootstrap.user?.name || 'Cadu').split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();

  return <>
    {mobileOpen && <button type="button" onClick={onMobileClose} aria-label="Fechar navegação" className="cv-fixed cv-inset-0 cv-z-50 cv-border-0 cv-bg-black/50 md:cv-hidden"/>}
    <aside className={`cv-workspace-sidebar ${mobileOpen ? 'cv-mobile-sidebar' : 'max-md:cv-hidden'} cv-relative cv-z-10 cv-flex cv-h-full cv-flex-none cv-flex-col cv-transition-[width] cv-duration-200 ${collapsed ? 'cv-w-[76px]' : 'cv-w-[276px]'}`} aria-label="Navegação do Workspace">
      <header className="cv-flex cv-h-[68px] cv-items-center cv-gap-3 cv-px-5">
        <a href={bootstrap.urls.home} className="cv-flex cv-min-w-0 cv-flex-1 cv-items-center cv-gap-3 cv-text-inherit cv-no-underline">
          <img src={bootstrap.logo} alt="" className="cv-h-8 cv-w-8 cv-object-contain"/>
          {!collapsed && <div className="cv-min-w-0"><strong className="cv-block cv-text-[15px] cv-font-bold">Cadu</strong><span className="cv-block cv-text-xs cv-text-[#6f8581]">Workspace</span></div>}
        </a>
        <button type="button" onClick={() => mobileOpen ? onMobileClose() : setCollapsed(value => !value)} className="cv-grid cv-h-8 cv-w-8 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-[#68807c] hover:cv-bg-black/5" aria-label={collapsed ? 'Expandir navegação' : 'Recolher navegação'}>
          <Icon name={mobileOpen ? 'close' : 'chevron'} size={16} className={collapsed ? '' : 'cv-rotate-180'}/>
        </button>
      </header>

      <nav className="cv-grid cv-gap-1 cv-px-3" aria-label="Áreas principais">
        {primary.map(([icon, label, key]) => key === 'newChat' ?
          <button key={key} type="button" onClick={onNew} className={`cv-flex cv-h-10 cv-items-center cv-gap-3 cv-rounded-xl cv-border-0 cv-bg-transparent cv-px-3 cv-text-left cv-text-[13px] cv-font-medium hover:cv-bg-[#e8efed] ${collapsed ? 'cv-justify-center' : ''}`}><Icon name={icon}/>{!collapsed && label}</button>
          : <a key={key} href={bootstrap.urls[key]} className={`cv-flex cv-h-10 cv-items-center cv-gap-3 cv-rounded-xl cv-px-3 cv-text-[13px] cv-font-medium cv-text-inherit cv-no-underline hover:cv-bg-[#e8efed] ${collapsed ? 'cv-justify-center' : ''}`}><Icon name={icon}/>{!collapsed && label}</a>)}
      </nav>

      {!collapsed && <section className="cv-mt-6 cv-flex cv-min-h-0 cv-flex-1 cv-flex-col cv-px-3" aria-label="Chats recentes">
        <div className="cv-mb-2 cv-flex cv-items-center cv-justify-between cv-px-2">
          <span className="cv-text-xs cv-font-semibold cv-text-[#6f8581]">Chats recentes</span>
          <button type="button" onClick={onNew} className="cv-grid cv-h-7 cv-w-7 cv-place-items-center cv-rounded-lg cv-border-0 cv-bg-transparent cv-text-[#238f83] hover:cv-bg-[#dcebe8]" aria-label="Novo chat"><Icon name="compose" size={15}/></button>
        </div>
        {conversations.length > 6 && <label className="cv-relative cv-mb-2 cv-block">
          <Icon name="search" size={14} className="cv-pointer-events-none cv-absolute cv-left-3 cv-top-1/2 cv--translate-y-1/2 cv-text-[#80928f]"/>
          <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar chat" aria-label="Buscar chat" className="cv-h-9 cv-w-full cv-rounded-lg cv-border-0 cv-bg-[#e9efed] cv-pl-9 cv-pr-3 cv-text-xs cv-text-[#17302d] placeholder:cv-text-[#7e918d]"/>
        </label>}
        <div className="cv-scroll cv-min-h-0 cv-overflow-y-auto">
          {filtered.slice(0, 20).map(item => <button key={item.id} type="button" disabled={Boolean(openingId)} onClick={() => onOpen(String(item.id), item.title)} aria-current={String(item.id) === String(activeId) ? 'page' : undefined} className={`cv-mb-1 cv-flex cv-w-full cv-items-center cv-gap-2 cv-rounded-lg cv-border-0 cv-px-3 cv-py-2.5 cv-text-left cv-text-[12px] disabled:cv-cursor-wait ${String(item.id) === String(activeId) ? 'cv-bg-[#173b36] cv-font-semibold cv-text-white' : 'cv-bg-transparent cv-text-[#607a76] hover:cv-bg-[#e8efed] hover:cv-text-[#17302d]'}`}><span className="cv-min-w-0 cv-flex-1 cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap">{item.title || 'Chat sem título'}</span>{String(item.id) === String(openingId) && <i className="cv-h-1.5 cv-w-1.5 cv-flex-none cv-animate-pulse cv-rounded-full cv-bg-[#20a797]"/>}</button>)}
          {loading && !conversations.length && <div className="cv-grid cv-gap-2 cv-px-2 cv-py-1" aria-label="Carregando chats"><i className="cv-h-8 cv-animate-pulse cv-rounded-lg cv-bg-[#e7eceb]"/><i className="cv-h-8 cv-animate-pulse cv-rounded-lg cv-bg-[#e7eceb]"/><i className="cv-h-8 cv-animate-pulse cv-rounded-lg cv-bg-[#e7eceb]"/></div>}
          {!loading && !filtered.length && <p className="cv-px-3 cv-text-xs cv-leading-5 cv-text-[#829590]">Seus chats aparecerão aqui.</p>}
        </div>
      </section>}

      <footer className="cv-mt-auto cv-p-3">
        {!collapsed && <details className="cv-group cv-mb-2">
          <summary className="cv-cursor-pointer cv-list-none cv-rounded-lg cv-px-3 cv-py-2 cv-text-xs cv-text-[#728783] hover:cv-bg-[#e8efed]">Workspace e conta</summary>
          <nav className="cv-mt-1 cv-grid cv-gap-1 cv-pl-3">
            {bootstrap.secondaryNav.map(item => <a key={item.label} href={item.href} className="cv-rounded-lg cv-px-3 cv-py-2 cv-text-xs cv-text-[#607a76] cv-no-underline hover:cv-bg-[#e8efed]">{item.label}</a>)}
          </nav>
        </details>}
        <a href={bootstrap.urls.profile} className={`cv-flex cv-items-center cv-gap-3 cv-rounded-xl cv-p-2 cv-text-inherit cv-no-underline hover:cv-bg-[#e8efed] ${collapsed ? 'cv-justify-center' : ''}`}>
          <span className="cv-grid cv-h-9 cv-w-9 cv-flex-none cv-place-items-center cv-rounded-full cv-bg-[#173b36] cv-text-[11px] cv-font-bold cv-text-white">{initials}</span>
          {!collapsed && <span className="cv-min-w-0"><strong className="cv-block cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-xs">{bootstrap.user?.name || 'Minha conta'}</strong><small className="cv-block cv-overflow-hidden cv-text-ellipsis cv-whitespace-nowrap cv-text-[10px] cv-text-[#7d918d]">{bootstrap.user?.email || ''}</small></span>}
        </a>
      </footer>
    </aside>
  </>;
}
