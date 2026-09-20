import React, {useMemo, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountControl, WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {CaduSolutionSwitcher} from './WorkspaceSelectors';
import {CaduDialog} from './CaduDialog';

export function WorkspaceProjects({bootstrap}) {
  const [query, setQuery] = useState(bootstrap.query || '');
  const [creating, setCreating] = useState(false);
  const [account, setAccount] = useState(false);
  const needle = query.trim().toLocaleLowerCase('pt-BR');
  const projects = useMemo(() => (bootstrap.projects || []).filter(project => !needle || `${project.name} ${project.brandName} ${project.description}`.toLocaleLowerCase('pt-BR').includes(needle)), [bootstrap.projects, needle]);
  const solutions = [['workspace', 'Workspace', 'Projetos e contexto'], ['planner', 'Planner', 'Planos e cenários'], ['studio', 'Studio', 'Criação e análise'], ['connect', 'Reports', 'Relatórios e resultados'], ['skills', 'Skills', 'Recursos e automações']].map(([id, name, description]) => ({id, name, description, href: bootstrap.urls.solutions?.[id], icon: bootstrap.solutionIcons?.[id]}));

  return <div className="cadu-ds-home-shell cadu-ds-brands-shell">
    <CaduDock brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={bootstrap.dock?.items || []} usagePercent={bootstrap.usagePercent} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onManageShortcuts={() => window.location.assign(bootstrap.urls.home)} onOpenBrand={item => item.href && window.location.assign(item.href)} onOpenResource={item => item.href && window.location.assign(item.href)} onOpenUsage={() => setAccount(true)}/>
    <main className="cadu-ds-home-main">
      <header className="cadu-ds-home-navbar"><CaduSolutionSwitcher logo={bootstrap.caduMark} solutions={solutions} activeId="workspace"/><strong>Projetos</strong><a className="cadu-ds-brands-nav" href={bootstrap.urls.brands}>Marcas</a><div className="cadu-ds-project-navbar__spacer"/><WorkspaceAccountControl user={bootstrap.user} onOpen={() => setAccount(true)}/></header>
      <section className="cadu-ds-brands-content">
        <header><div><p>Trabalho em contexto</p><h1>Projetos que continuam com a equipe</h1><span>Direção, fontes e entregas organizadas para a próxima decisão.</span></div><button className="is-primary" onClick={() => setCreating(true)}>Novo projeto</button></header>
        <div className="cadu-ds-brands-tools"><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar projeto, marca ou contexto"/><span>{projects.length} projeto{projects.length === 1 ? '' : 's'}</span></div>
        <div className="cadu-ds-brands-grid">{projects.map(project => <a href={project.href} key={project.id}><VisualIdentity src={project.previewUrl} initials={project.visualInitials} label={project.name} color={project.visualColor}/><div><small>{project.status === 'arquivado' ? 'Arquivado' : project.brandName || 'Projeto'}</small><b>{project.name}</b><p>{project.description || 'Reúna o briefing, as fontes e as decisões que orientam este trabalho.'}</p><em>{project.sources} fonte{project.sources === 1 ? '' : 's'} pronta{project.sources === 1 ? '' : 's'}</em></div></a>)}{!projects.length && <p className="cadu-ds-brands-empty">Nenhum projeto corresponde à busca.</p>}</div>
      </section>
    </main>
    <WorkspaceAccountMenu open={account} onClose={() => setAccount(false)} user={bootstrap.user} links={bootstrap.urls} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>
    {creating && <CaduDialog className="cadu-ds-project-dialog" label="Novo projeto" onClose={() => setCreating(false)}><form className="cadu-ds-project-form" method="post" action={bootstrap.urls.createProject}><input type="hidden" name="_csrf" value={bootstrap.csrf}/><header><div><h2>Novo projeto</h2><p>Crie o contexto que vai acompanhar conversas, fontes e entregas.</p></div><button type="button" onClick={() => setCreating(false)}>×</button></header><label>Nome<input name="name" required minLength="2" maxLength="150"/></label><label>Contexto inicial<textarea name="description" rows="3" maxLength="4000"/></label><label>Orientações para o Cadu<textarea name="instructions" rows="4" maxLength="12000"/></label><footer><button type="button" onClick={() => setCreating(false)}>Cancelar</button><button className="is-primary">Criar projeto</button></footer></form></CaduDialog>}
  </div>;
}
