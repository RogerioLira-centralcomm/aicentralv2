import React, {useMemo, useState} from 'react';
import {AgencySwitcher, CaduSolutionSwitcher, ProjectSelector} from './WorkspaceSelectors';
import {CaduDock} from './CaduDock';
import {WorkspaceComposer} from './WorkspaceComposer';
import {ResumeCardCollection} from './ResumeCards';
import {ActivityDrawer, ShortcutManagerDialog, UndoToast, WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {csrf, request} from '../../conversations-v2/lib/api';

function withQuery(url, values) {
  const target = new URL(url, window.location.origin);
  Object.entries(values).forEach(([key, value]) => { if (value) target.searchParams.set(key, value); });
  return target.pathname + target.search;
}

export function WorkspaceHome({bootstrap}) {
  const home = bootstrap.home || {};
  const [value, setValue] = useState(() => new URLSearchParams(window.location.search).get('prompt') || '');
  const [searchValue, setSearchValue] = useState('');
  const [projectRef, setProjectRef] = useState('');
  const [activityOpen, setActivityOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [toast, setToast] = useState('');
  const projects = home.projects || [];
  const [dockItems, setDockItems] = useState(home.dock?.items || []);
  const selectedProject = useMemo(() => projects.find(item => item.id === projectRef), [projects, projectRef]);
  const normalizedSearch = searchValue.trim().toLocaleLowerCase('pt-BR');
  const matchedProjects = useMemo(() => !normalizedSearch ? [] : projects.filter(project => `${project.name || ''} ${project.brandName || ''}`.toLocaleLowerCase('pt-BR').includes(normalizedSearch)), [projects, normalizedSearch]);
  const selectProject = projectId => { setProjectRef(projectId); setSearchValue(''); };
  const openProject = project => { if (project?.href) window.location.assign(project.href); };
  const submit = () => {
    const prompt = value.trim();
    if (!prompt) return;
    window.location.assign(withQuery(bootstrap.urls.newConversation, {prompt, project_ref: projectRef}));
  };
  const dropContext = payload => {
    if (payload.projectRef || payload.type === 'project') setProjectRef(payload.projectRef || payload.id);
    if (payload.type === 'brand') setToast('Marca adicionada ao contexto da conversa.');
  };
  const shortcutCandidates = [...(home.brands || []), ...projects].map(item => ({...item, title: item.title || item.name}));
  const explicitDockItems = dockItems.filter(item => item.shortcutId);
  const managerItems = [
    ...explicitDockItems,
    ...shortcutCandidates.filter(item => !explicitDockItems.some(dockItem => dockItem.id === item.id)),
  ].map(item => ({...item, pinned: Boolean(item.shortcutId)}));
  const persistShortcut = async item => {
    const kind = item.kind === 'brand' ? 'brand' : 'project';
    const targetRef = kind === 'brand' ? item.id : item.projectRef || item.id;
    const response = await request(bootstrap.endpoints.dockShortcuts, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({shortcut_type: kind, target_ref: targetRef, project_ref: item.projectRef || null, brand_ref: item.brandRef || null})});
    const next = {...item, shortcutId: response.shortcut.id, pinned: true};
    setDockItems(current => [...current.filter(currentItem => currentItem.shortcutId && currentItem.id !== item.id), next]);
  };
  const addDroppedShortcut = async payload => {
    const candidate = payload.type === 'brand'
      ? (home.brands || []).find(item => item.id === payload.id)
      : projects.find(item => item.id === (payload.projectRef || payload.id));
    if (!candidate || !['brand', 'project'].includes(candidate.kind)) {
      setToast('Apenas marcas e projetos podem ser fixados na dock.');
      return;
    }
    if (dockItems.some(item => item.id === candidate.id && item.shortcutId)) {
      setToast(`${candidate.title || candidate.name} já está nos seus atalhos.`);
      return;
    }
    try {
      await persistShortcut(candidate);
      setToast(`${candidate.title || candidate.name} fixado nos seus atalhos.`);
    } catch (error) { setToast(error.message || 'Não foi possível fixar este atalho.'); }
  };
  const toggleShortcut = async item => {
    try {
      const current = dockItems.find(dockItem => dockItem.id === item.id || dockItem.shortcutId === item.shortcutId);
      if (current?.shortcutId) {
        await request(`${bootstrap.endpoints.dockShortcuts}/${current.shortcutId}`, {method: 'DELETE', headers: {'X-CSRF-Token': csrf()}});
        setDockItems(values => values.filter(value => value.shortcutId !== current.shortcutId));
        setToast(`${item.title} removido dos seus atalhos.`);
      } else {
        await persistShortcut(item);
        setToast(`${item.title} fixado nos seus atalhos.`);
      }
    } catch (error) { setToast(error.message || 'Não foi possível atualizar os atalhos.'); }
  };
  const moveShortcut = async (item, direction) => {
    if (!item.shortcutId) { setToast('Fixe este item antes de mudar sua posição.'); return; }
    const before = dockItems;
    const index = before.findIndex(candidate => candidate.shortcutId === item.shortcutId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= before.length) return;
    const next = [...before];
    [next[index], next[target]] = [next[target], next[index]];
    setDockItems(next);
    try {
      await request(`${bootstrap.endpoints.dockShortcuts}/order`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf()}, body: JSON.stringify({ids: next.map(candidate => candidate.shortcutId).filter(Boolean)})});
    } catch (error) { setDockItems(before); setToast(error.message || 'Não foi possível salvar a ordem dos atalhos.'); }
  };
  const solutions = [
    {id: 'workspace', name: 'Workspace', description: 'Projetos e contexto'},
    {id: 'planner', name: 'Planner', description: 'Planos e cenários'},
    {id: 'studio', name: 'Studio', description: 'Criação e análise'},
    {id: 'connect', name: 'Reports', description: 'Relatórios e resultados'},
    {id: 'skills', name: 'Skills', description: 'Recursos e automações'},
  ].map(solution => ({...solution, href: bootstrap.urls.solutions?.[solution.id], icon: bootstrap.solutionIcons?.[solution.id]}));
  const contextVisuals = projects.slice(0, 4);
  return <div className="cadu-ds-home-shell">
    <CaduDock brands={home.brands || []} resources={home.resources || []} shortcutItems={dockItems} usagePercent={home.usagePercent} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onManageShortcuts={() => setShortcutsOpen(true)} onOpenBrand={brand => { if (brand.href) window.location.assign(brand.href); }} onOpenResource={item => openProject(projects.find(project => project.id === item.projectRef))} onDropItem={addDroppedShortcut} onOpenUsage={() => setAccountOpen(true)}/>
    <main className="cadu-ds-home-main">
      <header className="cadu-ds-home-navbar">
        <CaduSolutionSwitcher logo={bootstrap.caduMark} solutions={solutions} activeId="workspace"/>
        <AgencySwitcher value={home.agency?.id} items={[home.agency].filter(Boolean)} onChange={() => {}} emptyLabel={home.agency?.name || 'Selecionar agência'}/>
        <ProjectSelector agencyName={home.agency?.name} value={projectRef} items={projects} onChange={selectProject}/>
        <label className="cadu-ds-home-search"><span className="cadu-ds-sr-only">Buscar projetos no workspace</span><input value={searchValue} onChange={event => setSearchValue(event.target.value)} placeholder="Buscar projetos"/></label>
        <button type="button" className="cadu-ds-home-account" onClick={() => setAccountOpen(true)} aria-label="Abrir conta"><VisualIdentity src={bootstrap.user?.avatar} initials={bootstrap.user?.name} label={bootstrap.user?.name} color="#1b6d64"/></button>
      </header>
      <section className="cadu-ds-home-content">
        <div className="cadu-ds-home-intro"><p className="cadu-ds-home-kicker">Workspace {home.agency?.name ? `da ${home.agency.name}` : ''}</p><h1>{normalizedSearch ? 'Contextos encontrados' : selectedProject ? selectedProject.name : 'O que vamos resolver hoje?'}</h1><p>{normalizedSearch ? `${matchedProjects.length} projeto${matchedProjects.length === 1 ? '' : 's'} encontrado${matchedProjects.length === 1 ? '' : 's'} para “${searchValue.trim()}”.` : selectedProject ? `Trabalhe no contexto de ${selectedProject.brandName || 'seu projeto'}.` : 'Comece uma conversa ou escolha um contexto para trabalhar.'}</p></div>
        {normalizedSearch ? <section className="cadu-ds-home-search-results" aria-live="polite">{matchedProjects.map(project => <button key={project.id} type="button" onClick={() => selectProject(project.id)}><VisualIdentity src={project.previewUrl} initials={project.visualInitials} label={project.name} color={project.visualColor}/><span><b>{project.name}</b><small>{project.brandName || 'Projeto sem marca vinculada'}</small></span><em>Usar contexto</em></button>)}{!matchedProjects.length && <p>Nenhum projeto corresponde a esta busca.</p>}</section> : <><WorkspaceComposer value={value} onChange={setValue} onSubmit={submit} context={selectedProject ? {label: selectedProject.name} : null} onClearContext={() => setProjectRef('')} onAttach={() => setToast('Arraste um arquivo para anexar ao chat.')} onContextDrop={dropContext}/>
        {!value.trim() && contextVisuals.length > 0 && <section className="cadu-ds-home-context-strip" aria-label="Contextos do Workspace"><div><span>Contextos em movimento</span><b>{projects.length} projeto{projects.length === 1 ? '' : 's'}</b><small>Escolha um projeto para levar sua base para a conversa.</small></div><div className="cadu-ds-home-context-strip__visuals">{contextVisuals.map(project => <button key={project.id} type="button" onClick={() => selectProject(project.id)} aria-label={`Usar ${project.name} como contexto`}><VisualIdentity src={project.previewUrl} initials={project.visualInitials} label={project.name} color={project.visualColor}/></button>)}</div><a href={bootstrap.urls.projects}>Ver projetos</a></section>}
        {!value.trim() && <ResumeCardCollection items={home.resumeCards || []} onOpen={openProject} onOpenActivity={() => setActivityOpen(true)}/>}</>}
      </section>
    </main>
    <ActivityDrawer open={activityOpen} onClose={() => setActivityOpen(false)} items={(home.resumeCards || []).map(item => ({...item, detail: item.context, time: item.status}))} onOpenItem={openProject}/>
    <WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} onManageShortcuts={() => { setAccountOpen(false); setShortcutsOpen(true); }}/>
    <ShortcutManagerDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} items={managerItems} onToggle={toggleShortcut} onMove={moveShortcut}/>
    <UndoToast message={toast} onDismiss={() => setToast('')}/>
  </div>;
}
