import React, {useEffect, useId, useMemo, useRef, useState} from 'react';
import './tokens.css';
import './navbar.css';

// One navigation for every Studio tool. Keys match the `links` bootstrap shared by the pages.
export const STUDIO_SECTIONS = [
  ['home', 'Início'],
  ['create', 'Criar'],
  ['editor', 'Editar'],
  ['videos', 'Vídeo'],
  ['audio', 'Áudio'],
  ['analyzer', 'Analisar'],
  ['library', 'Biblioteca'],
  // Only present in `links` for organizations allowed into the Creative Lab.
  ['lab', 'Lab'],
];

const initials = name => String(name || 'C').trim().split(/\s+/).slice(0, 2).map(part => part[0] || '').join('').toUpperCase() || 'C';

function useDismiss(open, setOpen, ref) {
  useEffect(() => {
    if (!open) return undefined;
    const onPointer = event => { if (!ref.current?.contains(event.target)) setOpen(false); };
    const onKey = event => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('pointerdown', onPointer); document.removeEventListener('keydown', onKey); };
  }, [open, setOpen, ref]);
}

export function ProjectPicker({projects = [], projectId = '', onChange, loading = false, allowQuick = false, quickLabel = 'Criação rápida'}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [cursor, setCursor] = useState(0);
  const root = useRef(null);
  const trigger = useRef(null);
  const listRef = useRef(null);
  const wasOpen = useRef(false);
  const listId = useId();
  useDismiss(open, setOpen, root);
  const options = useMemo(() => {
    const base = allowQuick ? [{id: '', name: quickLabel, brandName: 'sem projeto', quick: true}, ...projects] : projects;
    const needle = query.trim().toLowerCase();
    return needle ? base.filter(item => `${item.name} ${item.brandName}`.toLowerCase().includes(needle)) : base;
  }, [projects, query, allowQuick, quickLabel]);
  const current = (allowQuick && !projectId) ? {name: quickLabel, brandName: 'sem projeto', quick: true}
    : projects.find(item => String(item.id) === String(projectId));
  useEffect(() => { if (open) setCursor(Math.max(0, options.findIndex(item => String(item.id) === String(projectId)))); }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const searchable = projects.length > 6;
  const activeId = open && options[cursor] ? `${listId}-option-${cursor}` : undefined;
  // Real focus moves into the list (or its search box) so assistive technology follows the highlighted option;
  // it returns to the trigger when the list closes.
  useEffect(() => {
    if (open && !searchable) listRef.current?.focus({preventScroll: true});
    if (!open && wasOpen.current && root.current?.contains(document.activeElement)) trigger.current?.focus();
    wasOpen.current = open;
  }, [open, searchable]);
  useEffect(() => { if (activeId) document.getElementById(activeId)?.scrollIntoView?.({block: 'nearest'}); }, [activeId]);
  const choose = item => { setOpen(false); setQuery(''); if (String(item.id) !== String(projectId)) onChange?.(String(item.id)); };
  const onKeyDown = event => {
    if (!open && ['ArrowDown', 'Enter', ' '].includes(event.key)) { event.preventDefault(); setOpen(true); return; }
    if (!open) return;
    if (event.key === 'ArrowDown') { event.preventDefault(); setCursor(index => Math.min(options.length - 1, index + 1)); }
    if (event.key === 'ArrowUp') { event.preventDefault(); setCursor(index => Math.max(0, index - 1)); }
    // In the search box Home/End keep moving the caret.
    if (event.key === 'Home' && event.target.tagName !== 'INPUT') { event.preventDefault(); setCursor(0); }
    if (event.key === 'End' && event.target.tagName !== 'INPUT') { event.preventDefault(); setCursor(Math.max(0, options.length - 1)); }
    if (event.key === 'Enter' && options[cursor]) { event.preventDefault(); choose(options[cursor]); }
  };
  const label = loading ? 'Carregando projetos…' : current ? current.name : projects.length ? 'Escolher projeto' : 'Nenhum projeto com marca';
  return <div className="csu-project" ref={root} onBlur={event => { if (open && event.relatedTarget && !root.current?.contains(event.relatedTarget)) setOpen(false); }}>
    <button type="button" className="csu-project__trigger" ref={trigger} aria-haspopup="listbox" aria-expanded={open} aria-controls={listId}
      aria-label={`Projeto e marca: ${current ? `${current.name} · ${current.brandName}` : label}`}
      disabled={loading || (!projects.length && !allowQuick)} onClick={() => setOpen(value => !value)} onKeyDown={onKeyDown}>
      <span className={`csu-project__chip${current?.quick ? ' is-quick' : ''}`} aria-hidden="true">{current?.quick ? '⚡' : initials(current?.brandName)}</span>
      <span className="csu-project__copy"><small>{current ? current.brandName : 'Projeto e marca'}</small><strong>{label}</strong></span>
      <span className="csu-caret" aria-hidden="true"/>
    </button>
    {open && <div className="csu-popover csu-project__popover">
      {searchable && <input className="csu-project__search" autoFocus role="combobox" aria-expanded="true" aria-autocomplete="list" aria-controls={listId} aria-activedescendant={activeId} value={query} placeholder="Buscar projeto ou marca" aria-label="Buscar projeto ou marca"
        onChange={event => { setQuery(event.target.value); setCursor(0); }} onKeyDown={onKeyDown}/>}
      <ul id={listId} role="listbox" aria-label="Projetos" ref={listRef} tabIndex={-1} aria-activedescendant={activeId} onKeyDown={onKeyDown}>
        {options.map((item, index) => <li key={item.id || 'quick'} id={`${listId}-option-${index}`} role="option" aria-selected={String(item.id) === String(projectId)}
          className={index === cursor ? 'is-cursor' : ''} onMouseEnter={() => setCursor(index)} onClick={() => choose(item)}>
          <span className={`csu-project__chip${item.quick ? ' is-quick' : ''}`} aria-hidden="true">{item.quick ? '⚡' : initials(item.brandName)}</span>
          <span className="csu-project__copy"><strong>{item.name}</strong><small>{item.brandName}{item.extraBrands ? ` +${item.extraBrands}` : ''}</small></span>
        </li>)}
        {!options.length && <li className="csu-empty" role="presentation">Nada encontrado.</li>}
      </ul>
    </div>}
  </div>;
}

const compactTokens = value => {
  const tokens = Math.max(0, Math.round(Number(value) || 0));
  if (tokens >= 1e6) return `${(tokens / 1e6).toLocaleString('pt-BR', {maximumFractionDigits: 1})} mi`;
  if (tokens >= 1e3) return `${(tokens / 1e3).toLocaleString('pt-BR', {maximumFractionDigits: 1})} mil`;
  return tokens.toLocaleString('pt-BR');
};

export function CreditMeter({href, usagePercent, available}) {
  if (usagePercent == null && available == null) return null;
  const usage = Math.max(0, Math.min(100, Math.round(Number(usagePercent || 0))));
  const tone = usage >= 90 ? ' is-critical' : usage >= 70 ? ' is-warning' : '';
  const balance = available != null && available !== '' && Number.isFinite(Number(available)) ? compactTokens(available) : '';
  return <a className={`csu-credits${tone}`} href={href || '#'} aria-label={`${usage}% dos créditos usados${balance ? `, saldo de ${balance} tokens` : ''}. Ver consumo e créditos.`}>
    <small>{balance ? `Saldo ${balance}` : 'Créditos'}</small>
    <strong>{usage}% <span>usado</span></strong>
    <i aria-hidden="true"><b style={{width: `${usage}%`}}/></i>
  </a>;
}

export function AccountMenu({user = {}, links = {}}) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  useDismiss(open, setOpen, root);
  const items = [['Meu perfil', links.profile], ['Créditos e consumo', links.credits], ['Abrir Workspace', links.workspace], ['Sair', links.logout]].filter(([, href]) => href);
  return <div className="csu-account" ref={root}>
    <button type="button" className="csu-avatar" aria-haspopup="menu" aria-expanded={open} aria-label={`Conta de ${user.name || 'usuário'}`} onClick={() => setOpen(value => !value)}>
      {user.avatar ? <img src={user.avatar} alt=""/> : <span>{initials(user.name)}</span>}
    </button>
    {open && <div className="csu-popover csu-account__menu" role="menu">
      <div className="csu-account__who"><strong>{user.name || 'Minha conta'}</strong>{user.email && <small>{user.email}</small>}</div>
      {items.map(([label, href]) => <a key={label} role="menuitem" href={href}>{label}</a>)}
    </div>}
  </div>;
}

export default function StudioNavbar({active, links = {}, projects = [], projectId = '', onProjectChange, projectsLoading = false, allowQuick = false, quickLabel,
  credits, user, identity, actions, embedded = false}) {
  const Root = embedded ? 'div' : 'header';
  return <Root className={`csu-navbar${embedded ? ' csu-navbar--embedded' : ''}`}>
    {identity !== false && <div className="csu-navbar__identity">{identity || <a className="csu-brand" href={links.home || '#'}>
      <img src="/static/images/cadu/products/studio-icon.png" alt=""/><strong>Cadu</strong><span>Studio</span></a>}</div>}
    <nav className="csu-navbar__nav" aria-label="Ferramentas do Studio">
      {STUDIO_SECTIONS.filter(([key]) => links[key]).map(([key, label]) =>
        <a key={key} href={links[key]} aria-current={key === active ? 'page' : undefined}>{label}</a>)}
    </nav>
    <div className="csu-navbar__meta">
      {onProjectChange && <ProjectPicker projects={projects} projectId={projectId} onChange={onProjectChange} loading={projectsLoading} allowQuick={allowQuick} quickLabel={quickLabel}/>}
      {credits && <CreditMeter href={links.credits} usagePercent={credits.usagePercent} available={credits.available}/>}
      {actions}
      <AccountMenu user={user} links={links}/>
    </div>
  </Root>;
}
