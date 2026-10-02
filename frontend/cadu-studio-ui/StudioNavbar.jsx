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
  const choose = item => { setOpen(false); setQuery(''); if (String(item.id) !== String(projectId)) onChange?.(String(item.id)); };
  const onKeyDown = event => {
    if (!open && ['ArrowDown', 'Enter', ' '].includes(event.key)) { event.preventDefault(); setOpen(true); return; }
    if (!open) return;
    if (event.key === 'ArrowDown') { event.preventDefault(); setCursor(index => Math.min(options.length - 1, index + 1)); }
    if (event.key === 'ArrowUp') { event.preventDefault(); setCursor(index => Math.max(0, index - 1)); }
    if (event.key === 'Enter' && options[cursor]) { event.preventDefault(); choose(options[cursor]); }
  };
  const label = loading ? 'Carregando projetos…' : current ? current.name : projects.length ? 'Escolher projeto' : 'Nenhum projeto com marca';
  return <div className="csu-project" ref={root}>
    <button type="button" className="csu-project__trigger" aria-haspopup="listbox" aria-expanded={open} aria-controls={listId}
      aria-label={`Projeto e marca: ${current ? `${current.name} · ${current.brandName}` : label}`}
      disabled={loading || (!projects.length && !allowQuick)} onClick={() => setOpen(value => !value)} onKeyDown={onKeyDown}>
      <span className={`csu-project__chip${current?.quick ? ' is-quick' : ''}`} aria-hidden="true">{current?.quick ? '⚡' : initials(current?.brandName)}</span>
      <span className="csu-project__copy"><small>{current ? current.brandName : 'Projeto e marca'}</small><strong>{label}</strong></span>
      <span className="csu-caret" aria-hidden="true"/>
    </button>
    {open && <div className="csu-popover csu-project__popover">
      {(projects.length > 6) && <input className="csu-project__search" autoFocus value={query} placeholder="Buscar projeto ou marca" aria-label="Buscar projeto ou marca"
        onChange={event => { setQuery(event.target.value); setCursor(0); }} onKeyDown={onKeyDown}/>}
      <ul id={listId} role="listbox" aria-label="Projetos">
        {options.map((item, index) => <li key={item.id || 'quick'} role="option" aria-selected={String(item.id) === String(projectId)}
          className={index === cursor ? 'is-cursor' : ''} onMouseEnter={() => setCursor(index)} onClick={() => choose(item)}>
          <span className={`csu-project__chip${item.quick ? ' is-quick' : ''}`} aria-hidden="true">{item.quick ? '⚡' : initials(item.brandName)}</span>
          <span className="csu-project__copy"><strong>{item.name}</strong><small>{item.brandName}{item.extraBrands ? ` +${item.extraBrands}` : ''}</small></span>
        </li>)}
        {!options.length && <li className="csu-empty" role="presentation">Nada encontrado.</li>}
      </ul>
    </div>}
  </div>;
}

export function CreditMeter({href, usagePercent, available}) {
  if (usagePercent == null && available == null) return null;
  const usage = Math.max(0, Math.min(100, Math.round(Number(usagePercent || 0))));
  const tone = usage >= 90 ? ' is-critical' : usage >= 70 ? ' is-warning' : '';
  return <a className={`csu-credits${tone}`} href={href || '#'} aria-label={`${usage}% dos créditos usados. Ver consumo e créditos.`}>
    <small>Créditos</small>
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
