import React, {useEffect, useMemo, useRef, useState} from 'react';
import {CaduDock} from './CaduDock';
import {WorkspaceAccountMenu} from './WorkspaceFeedback';
import {VisualIdentity} from './VisualIdentity';
import {CaduDialog} from './CaduDialog';
import {openWorkspaceDetail} from '../workspaceNavigation';
import {WorkspaceCatalog} from './WorkspaceCatalog';
import {WorkspaceMobileChrome} from './WorkspaceMobileChrome';
import {useWorkspaceViewport} from '../hooks/useWorkspaceViewport';
import {csrf} from '../../conversations-v2/lib/api';
import {Icon} from './Icon';

function BrandCreateDrop({websiteLogoSelected = false, onChooseUploadLogo}) {
  const input = useRef(null);
  const [active, setActive] = useState(false);
  const [files, setFiles] = useState([]);
  const [primaryIndex, setPrimaryIndex] = useState(0);
  useEffect(() => () => files.forEach(file => URL.revokeObjectURL(file.preview)), [files]);
  const setSelection = (items, primary = 0) => {
    const selected = Array.from(items || []).filter(file => ['image/png', 'image/jpeg', 'image/webp'].includes(file.type)
      || /\.(png|jpe?g|webp)$/i.test(file.name || '')).slice(0, 8);
    if (!selected.length || !input.current) return;
    const transfer = new DataTransfer();
    selected.forEach(file => transfer.items.add(file));
    input.current.files = transfer.files;
    setPrimaryIndex(Math.min(primary, selected.length - 1));
    setFiles(selected.map(file => ({file, preview:URL.createObjectURL(file)})));
  };
  const choosePrimary = index => setPrimaryIndex(index);
  const clearFiles = () => { if (input.current) input.current.value = ''; setFiles([]); setPrimaryIndex(0); };
  return <div className={`cadu-ds-brand-file-drop${active ? ' is-active' : ''}`} onDragEnter={event => { event.preventDefault(); setActive(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (event.currentTarget === event.target) setActive(false); }} onDrop={event => { event.preventDefault(); setActive(false); setSelection(event.dataTransfer.files); }}>
    <input ref={input} name="images" type="file" accept="image/png,image/jpeg,image/webp" multiple hidden aria-hidden="true" tabIndex="-1" onChange={event => { const selected = Array.from(event.target.files || []); event.target.value = ''; setSelection(selected); }}/>
    <button type="button" onClick={() => input.current?.click()}><strong>{files.length ? 'Adicionar imagens' : 'Selecionar logo e referências'}</strong><small>PNG, JPG ou WebP</small></button>
    {files.length > 0 && <fieldset className="cadu-ds-brand-uploaded-logos"><legend>{websiteLogoSelected ? 'Imagens enviadas como referências' : 'Escolha a logo principal'}</legend><div>{files.map(({file, preview}, index) => <label key={`${file.name}-${file.lastModified}`} className={!websiteLogoSelected && primaryIndex === index ? 'is-selected' : ''}><input type="radio" name="uploaded_primary_logo" checked={!websiteLogoSelected && primaryIndex === index} onChange={() => { choosePrimary(index); onChooseUploadLogo?.(); }}/><span><img src={preview} alt=""/></span><small title={file.name}>{file.name}</small></label>)}</div><input type="hidden" name="primary_logo" value={websiteLogoSelected ? 'false' : 'true'}/><input type="hidden" name="primary_logo_index" value={primaryIndex}/><button type="button" className="cadu-ds-brand-uploaded-logos__clear" onClick={clearFiles}>Remover imagens</button></fieldset>}
  </div>;
}

function normalizeBrandUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const withProtocol = /^[a-z][a-z\d+.-]*:\/\//i.test(raw) ? raw : `https://${raw}`;
  try {
    const url = new URL(withProtocol);
    return url.toString().replace(/\/$/, '');
  } catch (_) {
    return withProtocol;
  }
}

function BrandCreateForm({bootstrap, onClose}) {
  const nameInput = useRef(null);
  const autoName = useRef('');
  const autoSector = useRef('');
  const inspectionController = useRef(null);
  const [website, setWebsite] = useState('');
  const [sector, setSector] = useState('');
  const [selectedLogo, setSelectedLogo] = useState('');
  const [health, setHealth] = useState(null);
  const [checking, setChecking] = useState(false);
  useEffect(() => () => inspectionController.current?.abort('unmounted'), []);
  const checkHealth = async () => {
    setChecking(true);
    const normalized = normalizeBrandUrl(website);
    setWebsite(normalized);
    if (!normalized) {
      setHealth({ok:false, message:'Informe o site oficial para localizar a marca e suas logos.'});
      setChecking(false);
      return {ok:false};
    }
    const controller = new AbortController();
    inspectionController.current?.abort('replaced');
    inspectionController.current = controller;
    const timeout = window.setTimeout(() => controller.abort('timeout'), 30000);
    try {
      const response = await fetch(bootstrap.urls.inspectBrandSite, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':bootstrap.csrf, Accept:'application/json'}, body:JSON.stringify({website_url:normalized, logo_url:selectedLogo}), signal:controller.signal});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) throw new Error(payload.error || 'Não foi possível inspecionar o endereço.');
      const inspection = payload.inspection || {};
      const explicitLogoValid = !selectedLogo || Boolean(inspection.explicit_logo?.valid_image);
      const ok = Boolean(inspection.ready_for_analysis && explicitLogoValid);
      const candidateCount = inspection.logo_candidates?.length || 0;
      const websiteUrl = inspection.final_url || inspection.website_url || normalized;
      setWebsite(websiteUrl);
      const currentName = nameInput.current?.value.trim() || '';
      if (inspection.suggested_name && (!currentName || currentName === autoName.current)) {
        nameInput.current.value = inspection.suggested_name;
        autoName.current = inspection.suggested_name;
      }
      if (inspection.suggested_sector && (!sector.trim() || sector.trim() === autoSector.current)) {
        setSector(inspection.suggested_sector);
        autoSector.current = inspection.suggested_sector;
      }
      const suggestedLogo = inspection.explicit_logo?.valid_image ? inspection.explicit_logo.url : inspection.suggested_logo_url;
      if (!selectedLogo && suggestedLogo) setSelectedLogo(suggestedLogo);
      setHealth({ok, inspection, inspectionToken:payload.inspection_token || '', message:ok ? `Site validado${candidateCount ? ` e ${candidateCount} candidato${candidateCount === 1 ? '' : 's'} de logo encontrado${candidateCount === 1 ? '' : 's'}` : ''}.` : inspection.warnings?.[0] || 'O site ou a logo não pôde ser validado.'});
      return {ok, websiteUrl, inspectionToken:payload.inspection_token || ''};
    } catch (error) {
      if (controller.signal.reason !== 'unmounted' && controller.signal.reason !== 'replaced') setHealth({ok:false, message:controller.signal.reason === 'timeout' ? 'A inspeção demorou demais. Tente novamente.' : error?.message || 'Não foi possível inspecionar o endereço.'});
      return {ok:false};
    } finally {
      window.clearTimeout(timeout);
      if (inspectionController.current === controller) { inspectionController.current = null; setChecking(false); }
    }
  };
  return <form className="cadu-ds-brand-create-form" method="post" encType="multipart/form-data" action={bootstrap.urls.createBrand} onSubmit={async event => { const form = event.currentTarget; const hasName = Boolean(nameInput.current?.value.trim()); const hasWebsite = Boolean(website.trim()); if (!hasName && !hasWebsite) { event.preventDefault(); setHealth({ok:false, message:'Informe um site ou o nome da marca.'}); nameInput.current?.focus(); return; } if (!hasWebsite) { form.elements.official_logo_url.value = ''; form.elements.suggested_logo_url.value = ''; return; } if (!health?.ok || !health.inspectionToken) { event.preventDefault(); const result = await checkHealth(); if (result.ok) { form.elements.website_url.value = result.websiteUrl; form.elements.inspection_token.value = result.inspectionToken; form.elements.official_logo_url.value = selectedLogo || ''; form.elements.suggested_logo_url.value = selectedLogo || ''; form.submit(); } } else { form.elements.official_logo_url.value = selectedLogo || ''; form.elements.suggested_logo_url.value = selectedLogo || ''; } }}>
    <input type="hidden" name="_csrf" value={bootstrap.csrf}/>
    <input type="hidden" name="inspection_token" value={health?.inspectionToken || ''}/>
    <input type="hidden" name="official_logo_url" value={selectedLogo}/><input type="hidden" name="suggested_logo_url" value={selectedLogo}/>
    <header><div><h2>Nova marca</h2><p>Informe o site e selecione a logo.</p></div><button type="button" onClick={onClose} aria-label="Fechar">×</button></header>
    <div className="cadu-ds-brand-create-fields">
      <div className="cadu-ds-brand-create-field"><label htmlFor="new-brand-website">Site oficial</label><div className="cadu-ds-brand-create-site"><input id="new-brand-website" name="website_url" type="text" inputMode="url" maxLength="2000" placeholder="www.exemplo.com.br" value={website} onChange={event => { const next = event.target.value; setWebsite(next); setHealth(null); setSelectedLogo(''); if (nameInput.current?.value === autoName.current) nameInput.current.value = ''; if (sector === autoSector.current) setSector(''); autoName.current = ''; autoSector.current = ''; }} onBlur={() => setWebsite(normalizeBrandUrl(website))}/><button type="button" onClick={checkHealth} disabled={checking || !website.trim()}>{checking ? 'Buscando…' : 'Buscar'}</button></div></div>
      <label>Nome da marca<input ref={nameInput} name="name" maxLength="150" autoFocus placeholder="Preenchido pelo site ou informe o nome" onChange={() => { autoName.current = ''; setHealth(null); }}/></label>
      <label>Setor<input name="sector" maxLength="80" placeholder="Ex.: Varejo" value={sector} onChange={event => setSector(event.target.value)}/></label>
    </div>
    {health?.inspection && <fieldset className="cadu-ds-brand-create-logos"><legend>Logo do site</legend>{health.inspection.logo_candidates?.length > 0 ? <div>{health.inspection.logo_candidates.map((candidate, index) => <label key={`${candidate.url}-${index}`} className={selectedLogo === candidate.url ? 'is-selected' : ''}><input type="radio" name="logo_choice" checked={selectedLogo === candidate.url} onChange={() => setSelectedLogo(candidate.url)}/><span className={`cadu-ds-brand-logo-preview is-${index % 3}`}><img src={candidate.url} alt=""/></span></label>)}</div> : <p>Não encontramos uma logo compatível. Você pode enviar uma imagem abaixo.</p>}</fieldset>}
    <div className="cadu-ds-brand-create-upload-field"><span>Logo ou referências enviadas</span><BrandCreateDrop websiteLogoSelected={Boolean(selectedLogo)} onChooseUploadLogo={() => setSelectedLogo('')}/></div>
    <div className="cadu-ds-brand-create-options"><label><input name="analyze" type="checkbox" value="true" defaultChecked/> Analisar a marca depois de criar</label></div>
    <section className={`cadu-ds-brand-health${health ? (health.ok ? ' is-ready' : ' is-incomplete') : ''}`} aria-live="polite">
      {checking ? <span className="cadu-ds-brand-spinner" aria-label="Inspecionando site e logo"/> : health && <span role={health.ok ? 'status' : 'alert'}>{health.message}</span>}
    </section>
    <footer><button type="button" onClick={onClose}>Cancelar</button><button className="is-primary" disabled={checking}>Criar marca</button></footer>
  </form>;
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
  const [busyBrand, setBusyBrand] = useState('');
  const [actionError, setActionError] = useState('');
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
  const setBrandStatus = async brand => {
    setBusyBrand(String(brand.id)); setActionError('');
    try {
      const response = await fetch(`${bootstrap.urls.brands}/${encodeURIComponent(brand.id)}/status`, {method:'POST', credentials:'same-origin', headers:{'X-CSRF-Token':bootstrap.csrf || csrf(), Accept:'application/json'}});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || 'Não foi possível atualizar o status da marca.');
      window.location.reload();
    } catch (error) { setActionError(error.message || 'Não foi possível atualizar o status da marca.'); setBusyBrand(''); }
  };
  return <div className="cadu-ds-home-shell cadu-ds-brands-shell cadu-ds-brands-shell--brands">
    <main className="cadu-ds-home-main">
      <div className="cadu-ds-home-workarea cadu-ds-catalog-workarea">
        {isMobile ? <WorkspaceMobileChrome title="Marcas" links={bootstrap.urls} contextItems={brands.map(item => ({...item, detail:item.sector || 'Marca'}))}/> : <CaduDock bootstrap={bootstrap} logo={bootstrap.caduMark} homeUrl={bootstrap.urls.home} userName={bootstrap.user?.name} userAvatar={bootstrap.user?.avatar} userInitials={bootstrap.user?.name?.slice(0, 2).toUpperCase()} accountOpen={accountOpen} accountMenu={<WorkspaceAccountMenu open={accountOpen} onClose={() => setAccountOpen(false)} user={bootstrap.user} links={bootstrap.urls} projects={bootstrap.projects || []} brands={bootstrap.brands || []} usagePercent={bootstrap.usagePercent} onManageShortcuts={() => window.location.assign(`${bootstrap.urls.home}#atalhos`)}/>} onOpenAccount={() => setAccountOpen(current => !current)} brands={bootstrap.brands || []} resources={bootstrap.projects || []} shortcutItems={dockItems} usagePercent={bootstrap.usagePercent} onNewConversation={() => window.location.assign(bootstrap.urls.newConversation)} onOpenBrand={openWorkspaceDetail} onOpenResource={openWorkspaceDetail} onOpenUsage={() => setAccountOpen(true)}/>}
      <WorkspaceCatalog title="Marcas" actionLabel="Nova marca" onAction={() => setCreating(true)} error={bootstrap.catalogError} filters={[["ativas", "Ativas"], ["arquivadas", "Arquivadas"], ["todas", "Todas"], ["auditadas", "Analisadas"], ["com-ativos", "Com ativos"]].map(([value, label]) => ({value, label, active: bootstrap.filterName === value, href: catalogHref(bootstrap.urls.brands, 'filtro', value, query)}))} query={query} onQueryChange={setQuery} queryLabel="Buscar marcas" countLabel={`${brands.length} marca${brands.length === 1 ? '' : 's'}`}><div className="untitled-catalog-list is-brands" aria-label="Lista de marcas"><div className="untitled-catalog-list__head" aria-hidden="true"><span>Marca</span><span>Projetos</span><span>Conversas</span><span>Arquivos</span><span/></div>{actionError && <p role="alert">{actionError}</p>}{brands.map(brand => <div className="untitled-catalog-brand-row" key={brand.id}><a className="untitled-catalog-item" href={brand.href}><span className="untitled-catalog-item__identity"><VisualIdentity src={brand.logoUrl} initials={brand.visualInitials} label={brand.name} color={brand.visualColor}/><span><b>{brand.name}</b><small>{brand.audited ? 'Identidade analisada' : 'Identidade em preparação'}{brand.archived ? ' · Arquivada' : ''}</small></span></span><span className="untitled-catalog-item__metric"><small>Projetos</small><b>{brand.activeProjects || 0}</b></span><span className="untitled-catalog-item__metric"><small>Conversas</small><b>{brand.conversationCount || 0}</b></span><span className="untitled-catalog-item__metric"><small>Arquivos</small><b>{brand.fileCount || 0}</b></span><span className="untitled-catalog-item__chevron" aria-hidden="true">›</span></a>{bootstrap.canManageBrands && <button type="button" className="untitled-catalog-brand-row__archive" disabled={busyBrand === String(brand.id)} onClick={() => setBrandStatus(brand)} aria-label={`${brand.archived ? 'Restaurar' : 'Arquivar'} ${brand.name}`} title={`${brand.archived ? 'Restaurar' : 'Arquivar'} marca`}><Icon name={brand.archived ? 'undo' : 'archive'} size={16}/></button>}</div>)}{!brands.length && <div className="untitled-catalog-empty"><b>{query.trim() ? 'Nenhuma marca corresponde à busca.' : bootstrap.filterName === 'ativas' ? 'Nenhuma marca ativa.' : bootstrap.filterName === 'arquivadas' ? 'Nenhuma marca arquivada.' : 'Nenhuma marca neste filtro.'}</b>{!query.trim() && bootstrap.filterName === 'ativas' && <button type="button" onClick={() => setCreating(true)}>Criar marca</button>}</div>}</div></WorkspaceCatalog>
      </div>
    </main>
    {creating && <CaduDialog className="cadu-ds-brand-create-dialog" label="Nova marca" onClose={() => setCreating(false)}><BrandCreateForm bootstrap={bootstrap} onClose={() => setCreating(false)}/></CaduDialog>}
  </div>;
}
