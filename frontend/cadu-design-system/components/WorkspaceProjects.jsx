import React, {useMemo, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';
import {openWorkspaceDetail} from '../workspaceNavigation';
import {WorkspaceCatalog} from './WorkspaceCatalog';

function catalogHref(base, key, value, query) {
  const params = new URLSearchParams();
  if (value) params.set(key, value);
  if (query?.trim()) params.set('q', query.trim());
  const suffix = params.toString();
  return suffix ? `${base}?${suffix}` : base;
}

export function WorkspaceProjects({bootstrap}) {
  const [query, setQuery] = useState(bootstrap.query || '');
  const [creating, setCreating] = useState(false);
  const [account, setAccount] = useState(false);
  const needle = query.trim().toLocaleLowerCase('pt-BR');
  const projects = useMemo(() => (bootstrap.projects || []).filter(project => !needle || `${project.name} ${project.brandName} ${project.description}`.toLocaleLowerCase('pt-BR').includes(needle)), [bootstrap.projects, needle]);
  return <div className="cadu-ds-home-shell cadu-ds-brands-shell">
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-catalog-workarea">
        <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={account} accountMenu={<WorkspaceAccountMenu open={account} onClose={() => setAccount(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccount(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={bootstrap.dock?.items || []} usagePercent={bootstrap.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccount(true)}/>
        <WorkspaceCatalog eyebrow="Trabalho em contexto" title="Projetos que continuam com a equipe" description="Direção, fontes e entregas organizadas para a próxima decisão." actionLabel="Novo projeto" onAction={() => setCreating(true)} error={bootstrap.catalogError} filters={[["ativos", "Ativos"], ["arquivados", "Arquivados"], ["todos", "Todos"]].map(([value, label]) => ({value, label, active: bootstrap.status === value, href: catalogHref(bootstrap.urls.projects, 'status', value, query)}))} query={query} onQueryChange={setQuery} queryLabel="Buscar projeto, marca ou contexto" countLabel={`${projects.length} projeto${projects.length === 1 ? '' : 's'}`}><div className="cadu-ds-catalog-list" aria-label="Lista de projetos"><div className="cadu-ds-catalog-list__head" aria-hidden="true"><span>Projeto</span><span>Marca</span><span>Status</span><span>Fontes</span></div>{projects.map(project => <a className="cadu-ds-catalog-row" href={project.href} key={project.id}><VisualIdentity src={project.previewUrl} initials={project.visualInitials} label={project.name} color={project.visualColor}/><span className="cadu-ds-catalog-row__main"><b>{project.name}</b><small>{project.description || 'Reúna o briefing, as fontes e as decisões que orientam este trabalho.'}</small></span><span className="cadu-ds-catalog-row__meta">{project.brandName || 'Sem marca'}</span><span className="cadu-ds-catalog-row__meta">{project.status === 'arquivado' ? 'Arquivado' : 'Ativo'}</span><span className="cadu-ds-catalog-row__meta cadu-ds-catalog-row__number">{project.sources}</span></a>)}{!projects.length && <div className="cadu-ds-brands-empty"><b>{query.trim() ? 'Nenhum projeto corresponde à busca.' : bootstrap.status === 'arquivados' ? 'Nenhum projeto arquivado.' : 'Comece criando o primeiro projeto.'}</b>{!query.trim() && bootstrap.status !== 'arquivados' && <button type="button" onClick={() => setCreating(true)}>Criar projeto</button>}</div>}</div></WorkspaceCatalog>
      </div>
    </main>
    {creating && <CaduDialog className="cadu-ds-project-dialog" label="Novo projeto" onClose={() => setCreating(false)}><form className="cadu-ds-project-form" method="post" action={bootstrap.urls.createProject}><input type="hidden" name="_csrf" value={bootstrap.csrf}/><header><div><h2>Novo projeto</h2><p>Crie o contexto que vai acompanhar conversas, fontes e entregas.</p></div><button type="button" onClick={() => setCreating(false)}>×</button></header><label>Nome<input name="name" required minLength="2" maxLength="150"/></label><label>Contexto inicial<textarea name="description" rows="3" maxLength="4000"/></label><label>Orientações para o Cadu<textarea name="instructions" rows="4" maxLength="12000"/></label><footer><button type="button" onClick={() => setCreating(false)}>Cancelar</button><button className="is-primary">Criar projeto</button></footer></form></CaduDialog>}
  </div>;
}
