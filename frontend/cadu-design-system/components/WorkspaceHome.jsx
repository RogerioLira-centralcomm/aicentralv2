import React, {useMemo, useState} from 'react';
import {AgencySwitcher, CaduSolutionSwitcher, ProjectSelector} from './WorkspaceSelectors';
import {CaduDock} from './CaduDock';
import {WorkspaceComposer} from './WorkspaceComposer';
import {ResumeCardCollection} from './ResumeCards';
import {ActivityDrawer, ShortcutManagerDialog, UndoToast} from './WorkspaceFeedback';

function withQuery(url, values) {
  const target = new URL(url, window.location.origin);
  Object.entries(values).forEach(([key, value]) => { if (value) target.searchParams.set(key, value); });
  return target.pathname + target.search;
}

export function WorkspaceHome({bootstrap}) {
  const home = bootstrap.home || {};
  const [value, setValue] = useState(() => new URLSearchParams(window.location.search).get('prompt') || '');
  const [projectRef, setProjectRef] = useState('');
  const [activityOpen, setActivityOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [toast, setToast] = useState('');
  const projects = home.projects || [];
  const selectedProject = useMemo(() => projects.find(item => item.id === projectRef), [projects, projectRef]);
  const selectProject = projectId => setProjectRef(projectId);
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
  const solutions = [
    {id: 'workspace', name: 'Workspace', description: 'Projetos e contexto'},
    {id: 'planner', name: 'Planner', description: 'Planos e cenários'},
    {id: 'studio', name: 'Studio', description: 'Criação e análise'},
    {id: 'reports', name: 'Reports', description: 'Relatórios e resultados'},
  ];
  return <div className="cadu-ds-home-shell">
    <CaduDock logo={bootstrap.caduMark} brands={home.brands || []} resources={home.resources || []} usagePercent={home.usagePercent} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} onHome={() => window.location.assign(bootstrap.urls.home)} onNewConversation={() => { setValue(''); setProjectRef(''); window.scrollTo({top: 0, behavior: 'smooth'}); }} onOpenBrand={() => setToast('A Home da marca será aberta quando o contexto for selecionado.')} onOpenResource={item => openProject(projects.find(project => project.id === item.projectRef))} onDropItem={item => { setToast('Atalho adicionado à dock.'); dropContext(item); }} onOpenUsage={() => window.location.assign(bootstrap.urls.profile)}/>
    <main className="cadu-ds-home-main">
      <header className="cadu-ds-home-navbar">
        <CaduSolutionSwitcher logo={bootstrap.caduMark} solutions={solutions} activeId="workspace" onSelect={solution => { if (solution.id === 'workspace') return; setToast(`${solution.name} será aberto em uma nova superfície.`); }}/>
        <AgencySwitcher value={home.agency?.id} items={[home.agency].filter(Boolean)} onChange={() => {}} emptyLabel={home.agency?.name || 'Selecionar agência'}/>
        <ProjectSelector agencyName={home.agency?.name} value={projectRef} items={projects} onChange={selectProject}/>
        <label className="cadu-ds-home-search"><span className="cadu-ds-sr-only">Buscar no workspace</span><input placeholder="Buscar no workspace"/></label>
        <button type="button" className="cadu-ds-home-account" onClick={() => setShortcutsOpen(true)} aria-label="Abrir conta">{bootstrap.user?.name?.slice(0, 1) || 'C'}</button>
      </header>
      <section className="cadu-ds-home-content">
        <div className="cadu-ds-home-intro"><h1>{selectedProject ? selectedProject.name : 'O que vamos resolver hoje?'}</h1><p>{selectedProject ? `Trabalhe no contexto de ${selectedProject.brandName || 'seu projeto'}.` : 'Comece uma conversa ou escolha um contexto para trabalhar.'}</p></div>
        <WorkspaceComposer value={value} onChange={setValue} onSubmit={submit} context={selectedProject ? {label: selectedProject.name} : null} onClearContext={() => setProjectRef('')} onAttach={() => setToast('Arraste um arquivo para anexar ao chat.')} onContextDrop={dropContext}/>
        {!value.trim() && <ResumeCardCollection items={home.resumeCards || []} onOpen={openProject} onOpenActivity={() => setActivityOpen(true)}/>}
      </section>
    </main>
    <ActivityDrawer open={activityOpen} onClose={() => setActivityOpen(false)} items={(home.resumeCards || []).map(item => ({...item, detail: item.context, time: item.status}))} onOpenItem={openProject}/>
    <ShortcutManagerDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} items={[...(home.brands || []), ...projects].map(item => ({...item, pinned: true}))} onToggle={item => setToast(`${item.name} removido dos atalhos.`)} onMove={() => setToast('Ordem dos atalhos atualizada.')}/>
    <UndoToast message={toast} onDismiss={() => setToast('')}/>
  </div>;
}
