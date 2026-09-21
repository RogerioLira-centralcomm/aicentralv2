import React, {useEffect, useRef, useState} from 'react';
import {VisualIdentity} from './VisualIdentity';

function useDisclosure() {
  const root = useRef(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return undefined;
    const dismiss = event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setOpen(false);
        root.current?.querySelector('summary')?.focus();
      } else if (event.type === 'pointerdown' && !root.current?.contains(event.target)) setOpen(false);
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

function Selector({label, value, items = [], onChange, emptyLabel, className = ''}) {
  const {root, open, setOpen} = useDisclosure();
  const selected = items.find(item => String(item.id) === String(value));
  const choose = id => { onChange?.(id); setOpen(false); };
  return <details ref={root} open={open} onToggle={event => setOpen(event.currentTarget.open)} className={`cadu-ds-selector ${className}`}>
    <summary aria-label={label}><span>{selected?.name || emptyLabel}</span><i aria-hidden="true">⌄</i></summary>
    <div className="cadu-ds-selector-menu" aria-label={label}>
      <button type="button" aria-pressed={!value} onClick={() => choose('')}>{emptyLabel}</button>
      {items.map(item => <button key={item.id} type="button" aria-pressed={String(item.id) === String(value)} onClick={() => choose(item.id)}>{item.name}</button>)}
    </div>
  </details>;
}

export function CaduSolutionSwitcher({logo, solutions = [], activeId, onSelect}) {
  const {root, open, setOpen} = useDisclosure();
  const choose = solution => { setOpen(false); onSelect?.(solution); };
  return <details ref={root} open={open} onToggle={event => setOpen(event.currentTarget.open)} className="cadu-ds-solution-switcher">
    <summary aria-label="Abrir soluções Cadu">{logo ? <img src={logo} alt="Cadu"/> : <span aria-hidden="true">❮❮</span>}</summary>
    <nav aria-label="Soluções Cadu">{solutions.map(solution => solution.href
      ? <a key={solution.id} href={solution.href} onClick={() => setOpen(false)} aria-current={activeId === solution.id ? 'page' : undefined}>{solution.icon && <img src={solution.icon} alt=""/>}<span><b>{solution.name}</b><small>{solution.description}</small></span></a>
      : <button key={solution.id} type="button" onClick={() => choose(solution)} aria-pressed={activeId === solution.id}>{solution.icon && <img src={solution.icon} alt=""/>}<span><b>{solution.name}</b><small>{solution.description}</small></span></button>)}</nav>
  </details>;
}

export function AgencySwitcher(props) {
  return <Selector label="Agência ativa" emptyLabel="Selecionar agência" {...props} className="cadu-ds-selector--agency"/>;
}

export function ProjectSelector({agencyName, ...props}) {
  return <Selector label={`Projeto${agencyName ? ` da agência ${agencyName}` : ''}`} emptyLabel="Selecionar projeto" {...props} className="cadu-ds-selector--project"/>;
}

export function ChatContextSelector({context = {}, projects = [], brands = [], onProjectChange, onBrandChange, disabled = false, loading = false}) {
  const {root, open, setOpen} = useDisclosure();
  const brandByRef = new Map(brands.map(brand => [brand.ref || brand.brandRef || `studio:${brand.id}`, brand]));
  const selectedProject = projects.find(project => String(project.ref || project.projectRef || project.id || '') === String(context.project_ref || ''));
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
  const chooseProject = ref => { onProjectChange?.(ref); setOpen(false); };
  const chooseBrand = ref => { onBrandChange?.(ref); setOpen(false); };
  const label = selectedProject?.name || selectedBrand?.name || (loading ? 'Carregando contexto…' : 'Sessão livre');
  const orderedGroups = [...groups.entries()].sort(([left], [right]) => (left === context.brand_ref ? -1 : right === context.brand_ref ? 1 : 0));
  return <details ref={root} open={open} onToggle={event => setOpen(event.currentTarget.open)} className="cv-context-selector">
    <summary aria-label="Selecionar contexto da conversa" aria-busy={loading}><span className="cv-context-selector__label">{label}</span><i aria-hidden="true">⌄</i></summary>
    <div className="cv-context-selector__menu" aria-label="Contextos disponíveis">
      <header><span>Onde esta conversa acontece</span><p>Escolha um projeto ou continue em uma sessão livre.</p></header>
      <button type="button" className={!context.project_ref && !context.brand_ref ? 'is-active' : ''} onClick={() => chooseProject('')} disabled={disabled}><span className="cv-context-selector__personal">↗</span><span><b>Sessão livre</b><small>Conversa sem projeto definido</small></span>{!context.project_ref && !context.brand_ref && <em>✓</em>}</button>
      {orderedGroups.map(([brandRef, entries]) => {
        const brand = brandByRef.get(brandRef);
        return <section key={brandRef || 'unlinked'}><div className="cv-context-selector__group">{brand ? <button type="button" onClick={() => chooseBrand(brandRef)} disabled={disabled} className={context.brand_ref === brandRef && !context.project_ref ? 'is-active' : ''}><VisualIdentity src={brand.logoUrl || brand.logo_url} initials={brand.visualInitials || brand.name} label={brand.name} color={brand.visualColor}/><span><b>{brand.name}</b><small>{entries.length} projeto{entries.length === 1 ? '' : 's'}</small></span>{context.brand_ref === brandRef && !context.project_ref && <em>✓</em>}</button> : <span>Projetos sem marca</span>}</div><div className="cv-context-selector__projects">{entries.map(project => <button type="button" key={project.ref} onClick={() => chooseProject(project.ref)} disabled={disabled} className={context.project_ref === project.ref ? 'is-active' : ''}><VisualIdentity src={project.previewUrl} initials={project.visualInitials || project.name} label={project.name} color={project.visualColor}/><span>{project.name}</span>{context.project_ref === project.ref && <em>✓</em>}</button>)}</div></section>;
      })}
      {!projects.length && <p className="cv-context-selector__empty">{loading ? 'Carregando projetos…' : 'Nenhum projeto disponível neste contexto.'}</p>}
    </div>
  </details>;
}
