import React, {useEffect, useMemo, useRef, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';
import {openWorkspaceDetail} from '../workspaceNavigation';
import {WorkspaceCatalog} from './WorkspaceCatalog';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';

function BrandCreateDrop() {
  const input = useRef(null);
  const [active, setActive] = useState(false);
  const [files, setFiles] = useState([]);
  const assign = values => {
    const selected = Array.from(values || []).filter(file => file.type.startsWith('image/')).slice(0, 8);
    if (!selected.length || !input.current) return;
    const transfer = new DataTransfer(); selected.forEach(file => transfer.items.add(file));
    input.current.files = transfer.files; setFiles(selected);
  };
  return <div className={`cadu-ds-brand-file-drop${active ? ' is-active' : ''}`} onDragEnter={event => { event.preventDefault(); setActive(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (event.currentTarget === event.target) setActive(false); }} onDrop={event => { event.preventDefault(); setActive(false); assign(event.dataTransfer.files); }}><input ref={input} name="images" type="file" accept="image/*" multiple hidden aria-hidden="true" tabIndex="-1"/><strong>{files.length ? `${files.length} imagem${files.length === 1 ? '' : 's'} preparada${files.length === 1 ? '' : 's'}` : 'Solte logo e referências aqui'}</strong><small>{files.length ? files.map(file => file.name).join(', ') : 'Arraste arquivos de imagem para criar a identidade'}</small></div>;
}

function catalogHref(base, key, value, query) {
  const params = new URLSearchParams();
  if (value && value !== 'todas') params.set(key, value);
  if (query?.trim()) params.set('q', query.trim());
  const suffix = params.toString();
  return suffix ? `${base}?${suffix}` : base;
}

export function WorkspaceBrands({bootstrap}) {
  const {isMobile} = useWorkspaceViewport();
  const [query, setQuery] = useState(bootstrap.query || '');
  const [creating, setCreating] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const needle = query.trim().toLocaleLowerCase('pt-BR');
  const brands = useMemo(() => (bootstrap.brands || []).filter(brand => !needle || `${brand.name} ${brand.sector} ${brand.summary}`.toLocaleLowerCase('pt-BR').includes(needle)), [bootstrap.brands, needle]);
  const dockItems = bootstrap.dock?.items || [];
  useEffect(() => {
    const key = 'cadu:list:brands';
    const saved = window.sessionStorage.getItem(key);
    if (saved && !bootstrap.query) try { const state = JSON.parse(saved); setQuery(state.query || ''); window.requestAnimationFrame(() => window.scrollTo(0, state.scroll || 0)); } catch (_) {}
    const remember = () => window.sessionStorage.setItem(key, JSON.stringify({query, scroll:window.scrollY}));
    window.addEventListener('pagehide', remember);
    return () => { remember(); window.removeEventListener('pagehide', remember); };
  }, [query, bootstrap.query]);
  return <div className="cadu-ds-home-shell cadu-ds-brands-shell cadu-ds-brands-shell--brands">
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-catalog-workarea">
        {isMobile ? <WorkspaceMobileChrome title="Marcas" links={bootstrap.urls} contextItems={brands.map(item => ({...item, detail:item.sector || 'Marca'}))}/> : <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={dockItems} usagePercent={bootstrap.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>}
        <WorkspaceCatalog title="Marcas" actionLabel="Nova marca" onAction={() => setCreating(true)} error={bootstrap.catalogError} filters={[["todas", "Todas"], ["auditadas", "Analisadas"], ["com-ativos", "Com ativos"]].map(([value, label]) => ({value, label, active: bootstrap.filterName === value, href: catalogHref(bootstrap.urls.brands, 'filtro', value, query)}))} query={query} onQueryChange={setQuery} queryLabel="Buscar marcas" countLabel={`${brands.length} marca${brands.length === 1 ? '' : 's'}`}><div className="untitled-catalog-list is-brands" aria-label="Lista de marcas"><div className="untitled-catalog-list__head" aria-hidden="true"><span>Marca</span><span>Projetos</span><span>Conversas</span><span>Arquivos</span><span/></div>{brands.map(brand => <a className="untitled-catalog-item" href={brand.href} key={brand.id}><span className="untitled-catalog-item__identity"><VisualIdentity src={brand.logoUrl} initials={brand.visualInitials} label={brand.name} color={brand.visualColor}/><span><b>{brand.name}</b><small>{brand.audited ? 'Identidade analisada' : 'Identidade em preparação'}</small></span></span><span className="untitled-catalog-item__metric"><small>Projetos</small><b>{brand.activeProjects || 0}</b></span><span className="untitled-catalog-item__metric"><small>Conversas</small><b>{brand.conversationCount || 0}</b></span><span className="untitled-catalog-item__metric"><small>Arquivos</small><b>{brand.fileCount || 0}</b></span><span className="untitled-catalog-item__chevron" aria-hidden="true">›</span></a>)}{!brands.length && <div className="untitled-catalog-empty"><b>{query.trim() ? 'Nenhuma marca corresponde à busca.' : bootstrap.filterName === 'todas' ? 'Comece registrando a primeira marca.' : 'Nenhuma marca neste filtro.'}</b>{!query.trim() && bootstrap.filterName === 'todas' && <button type="button" onClick={() => setCreating(true)}>Criar marca</button>}</div>}</div></WorkspaceCatalog>
      </div>
    </main>
    {creating && <CaduDialog className="cadu-ds-project-dialog" label="Nova marca" onClose={() => setCreating(false)}><form className="cadu-ds-project-form" method="post" encType="multipart/form-data" action={bootstrap.urls.createBrand}><input type="hidden" name="_csrf" value={bootstrap.csrf}/><header><div><h2>Nova marca</h2><p>Comece com o que já existe; o time revisa a análise antes de usar a identidade.</p></div><button type="button" onClick={() => setCreating(false)}>×</button></header><label>Nome da marca<input name="name" required minLength="2" maxLength="150"/></label><label>Site oficial<input name="website_url" type="url" maxLength="2000"/></label><label>Setor <small>Opcional</small><input name="sector" maxLength="80"/></label><label>Logo e referências<BrandCreateDrop/></label><label><input name="primary_logo" type="checkbox" value="true" defaultChecked/> Usar a primeira imagem como logo principal</label><label><input name="analyze" type="checkbox" value="true" defaultChecked/> Analisar a marca após criar</label><footer><button type="button" onClick={() => setCreating(false)}>Cancelar</button><button className="is-primary">Criar marca</button></footer></form></CaduDialog>}
  </div>;
}
