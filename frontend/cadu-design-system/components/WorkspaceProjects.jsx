import React, {useEffect, useMemo, useRef, useState} from 'react';
import {WorkspaceContextSidebar} from './WorkspaceContextSidebar';
import {Icon} from './Icon';
import {VisualIdentity} from './VisualIdentity';
import {ProjectCreateDialog} from './ProjectCreateDialog';
import {CaduButton} from './CaduButton';
import {WorkspaceCatalog} from './WorkspaceCatalog';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';

function catalogHref(base, key, value, query) {
  const params = new URLSearchParams();
  if (value) params.set(key, value);
  if (query?.trim()) params.set('q', query.trim());
  const suffix = params.toString();
  return suffix ? `${base}?${suffix}` : base;
}

const normalizeProjectSearch = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');

export function WorkspaceProjects({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const [query, setQuery] = useState(bootstrap.query || '');
  const searchRef = useRef(null);
  const [creating, setCreating] = useState(false);
  const [overrides, setOverrides] = useState({});
  const [saving, setSaving] = useState(() => new Set());
  const [notice, setNotice] = useState('');
  const shownInSidebar = project => overrides[project.id] ?? project.showInSidebar !== false;
  const needle = normalizeProjectSearch(query.trim());
  const projects = useMemo(() => (bootstrap.projects || []).filter(project => !needle || normalizeProjectSearch(`${project.name} ${project.brandName} ${project.description} ${(project.contextItems || []).map(field => `${field.label} ${field.display_value}`).join(' ')}`).includes(needle)), [bootstrap.projects, needle]);
  useEffect(() => {
    const key = 'cadu:list:projects';
    const saved = window.sessionStorage.getItem(key);
    if (saved && !bootstrap.query) try { const state = JSON.parse(saved); setQuery(state.query || ''); window.requestAnimationFrame(() => window.scrollTo(0, state.scroll || 0)); } catch (_) {}
    const remember = () => window.sessionStorage.setItem(key, JSON.stringify({query, scroll:window.scrollY}));
    window.addEventListener('pagehide', remember);
    return () => { remember(); window.removeEventListener('pagehide', remember); };
  }, [query, bootstrap.query]);
  // One section per brand (A→Z, "Sem marca" last); projects keep the catalog's recency order inside each.
  const groups = useMemo(() => {
    const byKey = new Map();
    projects.forEach(project => {
      const label = (project.brandName || '').trim() || 'Sem marca';
      if (!byKey.has(label)) {
        // The header wears the brand's own identity (never a project thumbnail); initials when the brand has no logo.
        const brand = (bootstrap.brands || []).find(item => normalizeProjectSearch(item.name) === normalizeProjectSearch(label));
        byKey.set(label, {key: label, label, projects: [], previewUrl: brand?.logoUrl || '', initials: (brand?.visualInitials || label.slice(0, 2)).toUpperCase(), color: brand?.visualColor || ''});
      }
      byKey.get(label).projects.push(project);
    });
    return [...byKey.values()].sort((left, right) => (left.label === 'Sem marca') - (right.label === 'Sem marca') || left.label.localeCompare(right.label, 'pt-BR', {sensitivity: 'base'}));
  }, [projects, bootstrap.brands]);
  const toggleSidebar = async project => {
    const next = !shownInSidebar(project);
    setNotice('');
    setOverrides(current => ({...current, [project.id]: next}));
    setSaving(current => new Set(current).add(project.id));
    try {
      const response = await fetch(`/workspace/api/projetos/${encodeURIComponent(String(project.id).replace(/^ci:/, ''))}/sidebar`, {
        method: 'PATCH', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': bootstrap.csrf},
        body: JSON.stringify({show: next}),
      });
      if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || 'Não foi possível salvar agora.');
    } catch (error) {
      setOverrides(current => ({...current, [project.id]: !next}));
      setNotice(error.message || 'Não foi possível salvar agora.');
    } finally {
      setSaving(current => { const copy = new Set(current); copy.delete(project.id); return copy; });
    }
  };
  const catalogFilters = [["ativos", "Ativos"], ["arquivados", "Arquivados"], ["todos", "Todos"]].map(([value, label]) => ({value, label, active: bootstrap.status === value, href: catalogHref(bootstrap.urls.projects, 'status', value, query)}));
  return <div className="cadu-ds-home-shell cadu-ds-brands-shell cadu-ds-brands-shell--projects">
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-catalog-workarea">
        {isMobile ? <WorkspaceMobileChrome title="Projetos" links={bootstrap.urls} logo={bootstrap.caduMark} solutionIcons={bootstrap.solutionIcons} contextItems={projects.map(item => ({...item, detail:item.brandName || 'Projeto'}))}/> : <WorkspaceContextSidebar mode="home" rail bootstrap={bootstrap} links={bootstrap.urls} active="projetos"/>}
        <WorkspaceCatalog actionLabel="Novo projeto" actionSize="sm" onAction={() => setCreating(true)} title="Projetos" error={bootstrap.catalogError} filters={catalogFilters} query={query} onQueryChange={setQuery} searchRef={searchRef} queryLabel="Buscar projetos" countLabel={`${projects.length} projeto${projects.length === 1 ? '' : 's'}`} resultCount={projects.length} totalCount={(bootstrap.projects || []).length}>
          <div className="cadu-projects-groups" aria-label="Lista de projetos">
            {notice && <p className="cadu-projects-notice" role="alert">{notice}</p>}
            {groups.map(group => <section className="cadu-projects-group" key={group.key}>
              <header className="cadu-projects-group__head">
                <VisualIdentity src={group.previewUrl} initials={group.initials} label={group.label} color={group.color}/>
                <h2>{group.label}</h2><span>{group.projects.length} projeto{group.projects.length === 1 ? '' : 's'}</span>
              </header>
              <div className="untitled-catalog-list is-projects">
                <div className="untitled-catalog-list__head" aria-hidden="true"><span>Projeto</span><span>Fontes</span><span>Na sidebar</span><span/></div>
                {group.projects.map(project => {
                  const shown = shownInSidebar(project);
                  return <div className="untitled-catalog-item" key={project.id}>
                    <a className="untitled-catalog-item__hit" href={project.href} aria-label={`Abrir ${project.name}`}/>
                    <span className="untitled-catalog-item__identity"><VisualIdentity src={project.previewUrl} initials={project.visualInitials} label={project.name} color={project.visualColor}/><span><b>{project.name}</b><small>{project.description || 'Contexto do projeto'}</small></span></span>
                    <span className="untitled-catalog-item__metric"><small>Fontes</small><b>{project.sources || 0}</b></span>
                    <span className="untitled-catalog-item__pin">
                      <button type="button" role="switch" aria-checked={shown} className={`cadu-switch${shown ? ' is-on' : ''}`} disabled={saving.has(project.id)} onClick={() => toggleSidebar(project)} aria-label={`Mostrar ${project.name} na sidebar`}><i/></button>
                      <small>{shown ? 'Visível' : 'Oculto'}</small>
                    </span>
                    <span className="untitled-catalog-item__chevron" aria-hidden="true">›</span>
                  </div>;
                })}
              </div>
            </section>)}
            {!projects.length && <div className="untitled-catalog-empty"><img className="cadu-ds-project-state__illustration" src="/static/images/cadu/project-states/overview.webp" alt="" loading="lazy"/><b>{query.trim() ? 'Nenhum projeto corresponde à busca.' : bootstrap.status === 'arquivados' ? 'Nenhum projeto arquivado.' : 'Comece criando o primeiro projeto.'}</b>{!query.trim() && bootstrap.status !== 'arquivados' && <CaduButton type="button" onClick={() => setCreating(true)}>Criar projeto</CaduButton>}</div>}
          </div>
        </WorkspaceCatalog>
      </div>
    </main>
    {creating && <ProjectCreateDialog action={bootstrap.urls.createProject} csrfToken={bootstrap.csrf} brands={bootstrap.brands || []} onClose={() => setCreating(false)} onCreated={project => window.location.assign(project.href)}/>}
  </div>;
}
