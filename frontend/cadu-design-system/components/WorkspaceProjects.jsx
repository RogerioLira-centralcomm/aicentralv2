import React, {useEffect, useMemo, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {ProjectCreateDialog} from './ProjectCreateDialog';
import {openWorkspaceDetail} from '../workspaceNavigation';
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
  const [creating, setCreating] = useState(false);
  const [account, setAccount] = useState(false);
  const needle = normalizeProjectSearch(query.trim());
  const projects = useMemo(() => (bootstrap.projects || []).filter(project => !needle || normalizeProjectSearch(`${project.name} ${project.brandName} ${project.description} ${(project.contextItems || []).map(field => `${field.label} ${field.display_value}`).join(' ')}`).includes(needle)), [bootstrap.projects, needle]);
  const dockItems = bootstrap.dock?.items || [];
  useEffect(() => {
    const key = 'cadu:list:projects';
    const saved = window.sessionStorage.getItem(key);
    if (saved && !bootstrap.query) try { const state = JSON.parse(saved); setQuery(state.query || ''); window.requestAnimationFrame(() => window.scrollTo(0, state.scroll || 0)); } catch (_) {}
    const remember = () => window.sessionStorage.setItem(key, JSON.stringify({query, scroll:window.scrollY}));
    window.addEventListener('pagehide', remember);
    return () => { remember(); window.removeEventListener('pagehide', remember); };
  }, [query, bootstrap.query]);
  return <div className="cadu-ds-home-shell cadu-ds-brands-shell cadu-ds-brands-shell--projects">
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-catalog-workarea">
        {isMobile ? <WorkspaceMobileChrome title="Projetos" links={bootstrap.urls} contextItems={projects.map(item => ({...item, detail:item.brandName || 'Projeto'}))}/> : <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={account} accountMenu={<WorkspaceAccountMenu open={account} onClose={() => setAccount(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccount(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={dockItems} usagePercent={bootstrap.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccount(true)}/>}
        <WorkspaceCatalog title="Projetos" actionLabel="Novo projeto" onAction={() => setCreating(true)} error={bootstrap.catalogError} filters={[["ativos", "Ativos"], ["arquivados", "Arquivados"], ["todos", "Todos"]].map(([value, label]) => ({value, label, active: bootstrap.status === value, href: catalogHref(bootstrap.urls.projects, 'status', value, query)}))} query={query} onQueryChange={setQuery} queryLabel="Buscar projetos" countLabel={`${projects.length} projeto${projects.length === 1 ? '' : 's'}`}><div className="untitled-catalog-list is-projects" aria-label="Lista de projetos"><div className="untitled-catalog-list__head" aria-hidden="true"><span>Projeto</span><span>Marca</span><span>Status</span><span>Fontes</span><span/></div>{projects.map(project => <a className="untitled-catalog-item" href={project.href} key={project.id}><span className="untitled-catalog-item__identity"><VisualIdentity src={project.previewUrl} initials={project.visualInitials} label={project.name} color={project.visualColor}/><span><b>{project.name}</b><small>{project.description || 'Contexto do projeto'}</small></span></span><span className="untitled-catalog-item__value" data-label="Marca">{project.brandName || 'Sem marca'}</span><span className={`untitled-catalog-item__status is-${project.status === 'arquivado' ? 'archived' : 'active'}`}>{project.status === 'arquivado' ? 'Arquivado' : 'Ativo'}</span><span className="untitled-catalog-item__metric"><small>Fontes</small><b>{project.sources || 0}</b></span><span className="untitled-catalog-item__chevron" aria-hidden="true">›</span></a>)}{!projects.length && <div className="untitled-catalog-empty"><b>{query.trim() ? 'Nenhum projeto corresponde à busca.' : bootstrap.status === 'arquivados' ? 'Nenhum projeto arquivado.' : 'Comece criando o primeiro projeto.'}</b>{!query.trim() && bootstrap.status !== 'arquivados' && <button type="button" onClick={() => setCreating(true)}>Criar projeto</button>}</div>}</div></WorkspaceCatalog>
      </div>
    </main>
    {creating && <ProjectCreateDialog action={bootstrap.urls.createProject} csrfToken={bootstrap.csrf} brands={bootstrap.brands || []} onClose={() => setCreating(false)} onCreated={project => window.location.assign(project.href)}/>}
  </div>;
}
