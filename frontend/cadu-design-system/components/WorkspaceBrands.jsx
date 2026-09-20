import React, {useMemo, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';
import {workspaceSolutionItems} from '../workspaceSolutions';
import {openWorkspaceDetail} from '../workspaceNavigation';
import {WorkspaceNavbar} from './WorkspaceNavbar';
import {WorkspaceCatalog} from './WorkspaceCatalog';

function catalogHref(base, key, value, query) {
  const params = new URLSearchParams();
  if (value && value !== 'todas') params.set(key, value);
  if (query?.trim()) params.set('q', query.trim());
  const suffix = params.toString();
  return suffix ? `${base}?${suffix}` : base;
}

export function WorkspaceBrands({bootstrap}) {
  const [query, setQuery] = useState(bootstrap.query || '');
  const [creating, setCreating] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const needle = query.trim().toLocaleLowerCase('pt-BR');
  const brands = useMemo(() => (bootstrap.brands || []).filter(brand => !needle || `${brand.name} ${brand.sector} ${brand.summary}`.toLocaleLowerCase('pt-BR').includes(needle)), [bootstrap.brands, needle]);
  const solutions = workspaceSolutionItems(bootstrap);

  return <div className="cadu-ds-home-shell cadu-ds-brands-shell">
    <main className="cadu-ds-home-main">
      <WorkspaceNavbar logo={bootstrap.caduMark} solutions={solutions} user={bootstrap.user} onOpenAccount={() => setAccountOpen(true)}><a className="cadu-ds-brands-nav" href={bootstrap.urls.projects}>Projetos</a><strong>Marcas</strong></WorkspaceNavbar>
      <div className="cadu-ds-home-workarea cadu-ds-catalog-workarea">
        <CaduDock brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={bootstrap.dock?.items || []} usagePercent={bootstrap.usagePercent} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>
        <WorkspaceCatalog eyebrow="Gestão de marca" title="Identidades que orientam o trabalho" description="Reúna marca, referências e direção antes de levar o contexto para um projeto." actionLabel="Nova marca" onAction={() => setCreating(true)} error={bootstrap.catalogError} filters={[["todas", "Todas"], ["auditadas", "Analisadas"], ["com-ativos", "Com ativos"]].map(([value, label]) => ({value, label, active: bootstrap.filterName === value, href: catalogHref(bootstrap.urls.brands, 'filtro', value, query)}))} query={query} onQueryChange={setQuery} queryLabel="Buscar marcas" countLabel={`${brands.length} marca${brands.length === 1 ? '' : 's'}`}><div className="cadu-ds-brands-grid">{brands.map(brand => <a href={brand.href} key={brand.id}><VisualIdentity src={brand.logoUrl} initials={brand.visualInitials} label={brand.name} color={brand.visualColor}/><div><small>{brand.sector || 'Marca'}</small><b>{brand.name}</b><p>{brand.summary || (brand.audited ? 'Identidade analisada e disponível.' : 'Adicione referências para construir a identidade.')}</p><em>{brand.audited ? 'Analisada' : 'Em construção'} · {brand.assetCount} ativo{brand.assetCount === 1 ? '' : 's'}</em></div></a>)}{!brands.length && <div className="cadu-ds-brands-empty"><b>{query.trim() ? 'Nenhuma marca corresponde à busca.' : bootstrap.filterName === 'todas' ? 'Comece registrando a primeira marca.' : 'Nenhuma marca neste filtro.'}</b>{!query.trim() && bootstrap.filterName === 'todas' && <button type="button" onClick={() => setCreating(true)}>Criar marca</button>}</div>}</div></WorkspaceCatalog>
      </div>
    </main>
    <WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>
    {creating && <CaduDialog className="cadu-ds-project-dialog" label="Nova marca" onClose={() => setCreating(false)}><form className="cadu-ds-project-form" method="post" encType="multipart/form-data" action={bootstrap.urls.createBrand}><input type="hidden" name="_csrf" value={bootstrap.csrf}/><header><div><h2>Nova marca</h2><p>Comece com o que já existe; o time revisa a análise antes de usar a identidade.</p></div><button type="button" onClick={() => setCreating(false)}>×</button></header><label>Nome da marca<input name="name" required minLength="2" maxLength="150"/></label><label>Site oficial<input name="website_url" type="url" maxLength="2000"/></label><label>Setor <small>Opcional</small><input name="sector" maxLength="80"/></label><label>Logo e referências<input name="images" type="file" accept="image/*" multiple/></label><label><input name="primary_logo" type="checkbox" value="true" defaultChecked/> Usar a primeira imagem como logo principal</label><label><input name="analyze" type="checkbox" value="true" defaultChecked/> Analisar a marca após criar</label><footer><button type="button" onClick={() => setCreating(false)}>Cancelar</button><button className="is-primary">Criar marca</button></footer></form></CaduDialog>}
  </div>;
}
