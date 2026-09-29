import React, {useEffect, useLayoutEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {Icon} from './Icon';
import {markProjectUsed, recentProjectOptions} from '../projectOptions.mjs';

function useDisclosure(menuRef) {
  const root = useRef(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return undefined;
    const dismiss = event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setOpen(false);
        root.current?.querySelector('summary')?.focus();
      } else if (event.type === 'pointerdown' && !root.current?.contains(event.target) && !menuRef?.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('keydown', dismiss);
    document.addEventListener('pointerdown', dismiss);
    return () => {
      document.removeEventListener('keydown', dismiss);
      document.removeEventListener('pointerdown', dismiss);
    };
  }, [open]);
  return {root, open, setOpen};
}

const selectorItemId = item => item?.ref || item?.projectRef || item?.brandRef || item?.id || '';
const selectorItemIds = item => [item?.ref, item?.projectRef, item?.brandRef, item?.id]
  .map(id => String(id || '')).filter(Boolean);

function Selector({label, value, items = [], onChange, emptyLabel, className = '', icon, menuLabel = ''}) {
  const {root, open, setOpen} = useDisclosure();
  const selected = items.find(item => selectorItemIds(item).includes(String(value || '')));
  const choose = id => { onChange?.(id); setOpen(false); };
  return <details ref={root} open={open} onToggle={event => setOpen(event.currentTarget.open)} className={`cadu-ds-selector ${className}`}>
    <summary aria-label={label}>{icon}<span>{selected?.name || emptyLabel}</span><Icon name="chevron" size={13}/></summary>
    <div className="cadu-ds-selector-menu" aria-label={label}>
      {menuLabel && <span className="cadu-ds-selector-menu__label">{menuLabel}</span>}
      <button type="button" aria-pressed={!value} onClick={() => choose('')}>{emptyLabel}</button>
      {items.map(item => { const id = selectorItemId(item); return <button key={id} type="button" aria-pressed={String(id) === String(value)} onClick={() => choose(id)}>{item.name}</button>; })}
    </div>
  </details>;
}

export function CaduSolutionSwitcher({logo, solutions = [], activeId, onSelect, showActiveLabel = false, overlay = false, overlayAccent}) {
  const menuRef = useRef(null);
  const {root, open, setOpen} = useDisclosure(menuRef);
  const [menuPosition, setMenuPosition] = useState(null);
  useLayoutEffect(() => {
    if (!overlay || !open) return undefined;
    const positionMenu = () => {
      const anchor = root.current?.querySelector('summary');
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const width = Math.min(280, window.innerWidth - 24);
      const menuHeight = Math.min(solutions.length * 48 + 16, window.innerHeight - 24);
      const top = rect.bottom + menuHeight + 8 <= window.innerHeight ? rect.bottom + 8 : Math.max(12, rect.top - menuHeight - 8);
      setMenuPosition({top, left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)), width});
    };
    positionMenu();
    window.addEventListener('resize', positionMenu);
    window.addEventListener('scroll', positionMenu, true);
    return () => {
      window.removeEventListener('resize', positionMenu);
      window.removeEventListener('scroll', positionMenu, true);
    };
  }, [overlay, open, solutions.length]);
  const choose = solution => { setOpen(false); onSelect?.(solution); };
  const activeSolution = solutions.find(solution => solution.id === activeId);
  const menu = <nav ref={menuRef} className={overlay ? 'cadu-ds-solution-switcher__overlay' : undefined} style={overlay ? menuPosition || {visibility: 'hidden'} : undefined} aria-label="Soluções Cadu">{solutions.map(solution => solution.href
    ? <a key={solution.id} href={solution.href} onClick={() => setOpen(false)} aria-current={activeId === solution.id ? 'page' : undefined}>{solution.icon && <img src={solution.icon} alt=""/>}<span><b>{solution.name}</b><small>{solution.description}</small></span></a>
    : <button key={solution.id} type="button" onClick={() => choose(solution)} aria-pressed={activeId === solution.id}>{solution.icon && <img src={solution.icon} alt=""/>}<span><b>{solution.name}</b><small>{solution.description}</small></span></button>)}</nav>;
  return <details ref={root} open={open} onToggle={event => setOpen(event.currentTarget.open)} className="cadu-ds-solution-switcher">
    <summary aria-label={showActiveLabel ? `Selecionar solução: ${activeSolution?.name || 'Workspace'}` : 'Abrir soluções Cadu'}>{logo ? <img src={logo} alt="Cadu"/> : <span aria-hidden="true">❮❮</span>}{showActiveLabel && <span className="cadu-ds-solution-switcher__active-label">{activeSolution?.name || 'Workspace'}</span>}</summary>
    {overlay ? open && createPortal(<div className="cadu-ds-solution-switcher cadu-ds-solution-switcher__portal" style={overlayAccent ? {'--solution-accent': overlayAccent} : undefined}>{menu}</div>, document.body) : menu}
  </details>;
}

export function AgencySwitcher(props) {
  return <Selector label="Agência ativa" emptyLabel="Selecionar agência" {...props} className="cadu-ds-selector--agency"/>;
}

export function ProjectSelector({agencyName, ...props}) {
  const [, setRecencyVersion] = useState(0);
  const items = recentProjectOptions(props.items, props.value);
  const chooseProject = id => {
    if (id) markProjectUsed(id);
    setRecencyVersion(version => version + 1);
    props.onChange?.(id);
  };
  return <Selector label={`Projeto${agencyName ? ` da agência ${agencyName}` : ''}`} emptyLabel="Selecionar projeto" {...props} onChange={chooseProject} items={items} menuLabel="Projetos recentes" icon={<Icon name="folder" size={14}/>} className="cadu-ds-selector--project"/>;
}

export function ChatContextSelector({context = {}, projects = [], brands = [], onProjectChange, onBrandChange, disabled = false, loading = false, projectsOnly = false}) {
  const {root, open, setOpen} = useDisclosure();
  const brandByRef = new Map(brands.map(brand => [brand.ref || brand.brandRef || `studio:${brand.id}`, brand]));
  const selectedProject = projects.find(project => String(project.ref || project.projectRef || project.id || '') === String(context.project_ref || ''));
  const projectOptions = recentProjectOptions(projects, context.project_ref);
  const selectedBrand = brandByRef.get(context.brand_ref);
  const groups = new Map();
  projects.forEach(project => {
    const relatedRefs = Array.isArray(project.related_refs)
      ? project.related_refs
      : Array.isArray(project.relatedRefs) ? project.relatedRefs : project.brandRef ? [project.brandRef] : [];
    const related = relatedRefs.filter(ref => brandByRef.has(ref));
    const ref = related[0] || '';
    if (!groups.has(ref)) groups.set(ref, []);
    groups.get(ref).push(project);
  });
  const chooseProject = ref => { if (ref) markProjectUsed(ref); onProjectChange?.(ref); setOpen(false); };
  const chooseBrand = ref => { onBrandChange?.(ref); setOpen(false); };
  const label = selectedProject?.name || selectedBrand?.name || (loading ? 'Carregando contexto…' : 'Sessão livre');
  const orderedGroups = [...groups.entries()].sort(([left], [right]) => (left === context.brand_ref ? -1 : right === context.brand_ref ? 1 : 0));
  return <details ref={root} open={open} onToggle={event => setOpen(event.currentTarget.open)} className="cv-context-selector">
    <summary aria-label="Selecionar contexto da conversa" aria-busy={loading}><span className="cv-context-selector__label">{label}</span><i aria-hidden="true">⌄</i></summary>
    <div className="cv-context-selector__menu" aria-label={projectsOnly ? 'Projetos disponíveis' : 'Contextos disponíveis'}>
      <button type="button" className={!context.project_ref && !context.brand_ref ? 'is-active' : ''} onClick={() => chooseProject('')} disabled={disabled}><span><b>Sessão livre</b></span>{!context.project_ref && !context.brand_ref && <em>✓</em>}</button>
      {projectsOnly ? <section className="cv-context-selector__project-list"><span className="cv-context-selector__menu-label">Projetos</span><div className="cv-context-selector__projects">{projectOptions.map(project => <button type="button" key={project.ref || project.projectRef || project.id} onClick={() => chooseProject(project.ref || project.projectRef || project.id)} disabled={disabled} className={String(context.project_ref || '') === String(project.ref || project.projectRef || project.id) ? 'is-active' : ''}><span title={project.name}>{project.name}</span>{String(context.project_ref || '') === String(project.ref || project.projectRef || project.id) && <em>✓</em>}</button>)}</div></section> : orderedGroups.map(([brandRef, entries]) => {
        const brand = brandByRef.get(brandRef);
        return <section key={brandRef || 'unlinked'}><div className="cv-context-selector__group">{brand ? <button type="button" onClick={() => chooseBrand(brandRef)} disabled={disabled} className={context.brand_ref === brandRef && !context.project_ref ? 'is-active' : ''}><span><b>{brand.name}</b><small>{entries.length} projeto{entries.length === 1 ? '' : 's'}</small></span>{context.brand_ref === brandRef && !context.project_ref && <em>✓</em>}</button> : <span>Projetos sem marca</span>}</div><div className="cv-context-selector__projects">{entries.map(project => <button type="button" key={project.ref} onClick={() => chooseProject(project.ref)} disabled={disabled} className={context.project_ref === project.ref ? 'is-active' : ''}><span>{project.name}</span>{context.project_ref === project.ref && <em>✓</em>}</button>)}</div></section>;
      })}
      {!projects.length && loading && <p className="cv-context-selector__empty">Carregando projetos…</p>}
    </div>
  </details>;
}
