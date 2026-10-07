import React, {useEffect, useMemo, useState} from 'react';
import {Dialog, DialogTrigger, Popover} from 'react-aria-components';
import {AlertTriangle, Check, ChevronDown, ChevronRight, Edit01, FolderPlus, Plus, SearchLg, XClose} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {CaduTooltip} from '../cadu-design-system/components/CaduTooltip.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import {platformName} from './shell/media.jsx';
import {json} from './reportsCommon.jsx';
import {FlowConnectSite} from './FlowConnectSite.jsx';
import {APP_BASE} from './shell/routes.js';
import {readCustomer, writeCustomer} from './shell/customerScope.js';
import {NewClientWizard} from './NewClientWizard.jsx';

const API = '/connect/api/v2/reports';
const ALL = 'all';
const NONE = 'none';
const ACCOUNT_STATUS = {active: ['Ativa', 'success'], paused: ['Pausada', 'warning'], disabled: ['Desativada', 'gray']};
export const CAMPAIGN_STATUS = {ENABLED: ['Ativa', 'success'], PAUSED: ['Pausada', 'warning'], REMOVED: ['Removida', 'gray'], unknown: ['Sem status', 'gray']};
const CHANNELS = {SEARCH: 'Pesquisa', PERFORMANCE_MAX: 'Performance Max', DISPLAY: 'Display', VIDEO: 'Vídeo', SHOPPING: 'Shopping', DEMAND_GEN: 'Demand Gen', DISCOVERY: 'Discovery', APP: 'App', LOCAL: 'Local', SMART: 'Smart', social: 'Social'};
export const channelLabel = value => CHANNELS[value] || CHANNELS[String(value || '').toUpperCase()] || value || '';
const plural = (count, one, many) => `${count.toLocaleString('pt-BR')} ${count === 1 ? one : many}`;
const initials = name => String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();
const matches = (query, ...values) => !query || values.some(value => String(value ?? '').toLowerCase().includes(query));
export const NEW_CLIENT_EVENT = 'reports:new-client';

/** Botão do cabeçalho da página: a tela abre o assistente de novo cliente ao ouvir o evento. */
export function NewClientButton() {
  return <Button size="md" color="primary" iconLeading={Plus} onPress={() => dispatchEvent(new Event(NEW_CLIENT_EVENT))}>Novo cliente</Button>;
}

export function Status({map, value}) {
  const [label, color] = map[value] || [value || 'Sem status', 'gray'];
  return <BadgeWithDot type="pill-color" size="sm" color={color}>{label}</BadgeWithDot>;
}

function Avatar({name, logo, size = 'md'}) {
  const box = size === 'lg' ? 'size-12 text-md' : 'size-8 text-xs';
  if (logo) return <img src={logo} alt="" className={`${box} shrink-0 rounded-full bg-primary object-contain ring-1 ring-secondary`}/>;
  return <span aria-hidden="true" className={`${box} flex shrink-0 items-center justify-center rounded-full bg-brand-secondary font-semibold text-brand-secondary`}>{initials(name)}</span>;
}

/** Workspace links for this client: brands per customer, projects per campaign. Optional everywhere. */
function useWorkspaceMap(clientId) {
  const [map, setMap] = useState(null);
  const load = () => json(`${API}/workspace/map`).then(setMap).catch(() => setMap({available: false}));
  useEffect(() => {load();}, [clientId]);
  return [map, load];
}

function send(data, path, method, payload = {}) {
  return json(`${API}${path}`, {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...payload})});
}

/** Clients, their Workspace brands, media accounts and campaigns in one place, as a hierarchy. */
export function ClientsAccounts({data, save, busy, reload}) {
  const [map, reloadMap] = useWorkspaceMap(data.client.client_id);
  // O cliente é o mesmo da barra lateral: a página não tem seletor próprio.
  const selected = readCustomer();
  const setSelected = writeCustomer;
  const [query, setQuery] = useState('');
  const [platform, setPlatform] = useState('');
  const [showInactive, setShowInactive] = useState(true);
  const [collapsed, setCollapsed] = useState(() => new Set());
  const [drawer, setDrawer] = useState(null);
  const [wizard, setWizard] = useState(false);
  const [error, setError] = useState('');
  const canEdit = data.client.role !== 'viewer';
  const canManageClients = Boolean(data.can_manage_clients);
  const workspace = map?.available ? map : null;
  const customers = (data.customers || []).filter(item => item.status !== 'archived');
  const brandsOf = id => workspace?.customer_brands?.[String(id)] || [];
  const logoOf = id => {
    const linked = brandsOf(id).map(brand => workspace.brands.find(item => item.ref === brand.ref)).find(item => item?.logo_url);
    return linked?.logo_url || '';
  };

  useEffect(() => {
    const open = () => setWizard(true);
    addEventListener(NEW_CLIENT_EVENT, open);
    return () => removeEventListener(NEW_CLIENT_EVENT, open);
  }, []);
  useEffect(() => {
    if (selected !== ALL && selected !== NONE && !customers.some(item => String(item.id) === selected)) setSelected(ALL);
  }, [data.customers]);

  const inScope = item => selected === ALL || (selected === NONE ? !item.customer_id : String(item.customer_id || '') === selected);
  const accounts = data.accounts.filter(inScope);
  const campaigns = data.campaigns.filter(inScope);
  const current = customers.find(item => String(item.id) === selected);
  const linkedBrandRefs = new Set(Object.values(workspace?.customer_brands || {}).flat().map(brand => brand.ref));
  const freeBrands = (workspace?.brands || []).filter(brand => !linkedBrandRefs.has(brand.ref));

  const run = async action => {
    setError('');
    try {await action();} catch (failure) {setError(failure.message || 'Não foi possível salvar.');}
  };
  const importBrand = brand => run(async () => {
    const existing = customers.find(item => item.name.trim().toLowerCase() === brand.name.trim().toLowerCase());
    const customerId = existing?.id || (await save('/customers', {name: brand.name}, false)).customer.id;
    await send(data, `/customers/${customerId}/brands`, 'POST', {brand_ref: brand.ref});
    await Promise.all([reload(), reloadMap()]);
    setSelected(String(customerId));
  });

  return <div className="untitled-scope">
    <div className="flex min-w-0 flex-col gap-6">
      {error && <p role="alert" className="rounded-lg bg-error-primary px-4 py-3 text-sm text-error-primary ring-1 ring-error_subtle">{error}</p>}
      <ClientHeader data={data} current={current} selected={selected} brands={current ? brandsOf(current.id) : []} workspace={workspace} accounts={accounts} campaigns={campaigns}
        canManage={canManageClients} onRename={() => setDrawer({kind: 'customer', customer: current})} onBrands={reloadMap} onError={setError}/>
      <section className="overflow-hidden rounded-xl bg-primary shadow-xs ring-1 ring-secondary" aria-label="Contas e campanhas">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-secondary px-6 py-5">
          <div className="min-w-60 flex-1">
            <div className="flex items-center gap-2"><h2 className="text-lg font-semibold text-primary">Contas e campanhas</h2><Badge type="pill-color" size="sm" color="brand">{plural(campaigns.length, 'campanha', 'campanhas')}</Badge></div>
            <p className="mt-0.5 text-sm text-tertiary">{workspace ? 'Cada campanha pode alimentar um projeto do Workspace.' : 'Organizadas por gerente e conta de mídia.'}</p>
          </div>
          {canEdit && <div className="flex max-w-full shrink-0 flex-wrap gap-3">
            <Button size="md" color="secondary" iconLeading={Plus} onPress={() => setDrawer({kind: 'account'})}>Conta de mídia</Button>
            <Button size="md" color="primary" iconLeading={Plus} onPress={() => setDrawer({kind: 'campaign'})}>Campanha</Button>
          </div>}
        </header>
        <div className="flex flex-wrap items-center gap-3 border-b border-secondary px-6 py-3">
          <div className="w-full sm:max-w-80"><ReportsFieldInput size="sm" type="search" aria-label="Buscar conta ou campanha" placeholder="Nome ou ID de conta ou campanha" value={query} onChange={event => setQuery(event.target.value)}
            leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/></div>
          <div className="w-full sm:w-48"><ReportsNativeSelect size="sm" aria-label="Plataforma" value={platform} onChange={event => setPlatform(event.target.value)}>
            <option value="">Todas as plataformas</option>
            {[...new Set(data.accounts.map(item => item.platform))].map(item => <option key={item} value={item}>{platformName(item)}</option>)}
          </ReportsNativeSelect></div>
          <label className="ml-auto flex cursor-pointer items-center gap-2 text-sm text-secondary"><input type="checkbox" className="size-4 accent-brand-600" checked={!showInactive} onChange={event => setShowInactive(!event.target.checked)}/>Somente ativas</label>
        </div>
        <HierarchyTable data={data} accounts={accounts} campaigns={campaigns} query={query.trim().toLowerCase()} platform={platform} showInactive={showInactive}
          collapsed={collapsed} toggle={id => setCollapsed(previous => {const next = new Set(previous); next.has(id) ? next.delete(id) : next.add(id); return next;})}
          workspace={workspace} brandRefs={current ? brandsOf(current.id).map(brand => brand.ref) : []} canEdit={canEdit} onLinksChanged={reloadMap} onError={setError}
          showClient={selected === ALL} customers={customers}
          onEditAccount={account => setDrawer({kind: 'account', account})} onEditCampaign={campaign => setDrawer({kind: 'campaign', campaign})}/>
      </section>
      <SitesSection data={data} current={current} selected={selected} customers={customers} canEdit={canEdit} onError={setError}/>
      {canManageClients && workspace && !current && freeBrands.length > 0 && <section className="overflow-hidden rounded-xl bg-primary shadow-xs ring-1 ring-secondary" aria-label="Marcas do Workspace sem cliente">
        <header className="border-b border-secondary px-6 py-5">
          <div className="flex items-center gap-2"><h2 className="text-lg font-semibold text-primary">Marcas do Workspace sem cliente</h2><Badge type="pill-color" size="sm" color="gray">{freeBrands.length}</Badge></div>
          <p className="mt-0.5 text-sm text-tertiary">Cada marca vira um cliente com um clique, já vinculado a ela.</p>
        </header>
        <ul className="grid gap-3 p-6 sm:grid-cols-2 xl:grid-cols-3">{freeBrands.map(brand => <li key={brand.ref} className="flex items-center gap-3 rounded-lg px-3 py-2.5 ring-1 ring-secondary ring-inset">
          <Avatar name={brand.name} logo={brand.logo_url}/>
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-secondary">{brand.name}</span>
          <Button size="sm" color="secondary" iconLeading={Plus} aria-label={`Criar cliente ${brand.name}`} isDisabled={busy} onPress={() => importBrand(brand)}>Cliente</Button>
        </li>)}</ul>
      </section>}
    </div>

    {wizard && <NewClientWizard freeBrands={freeBrands} save={save} send={(path, method, payload) => send(data, path, method, payload)} reload={reload}
      onDone={async id => {await reloadMap(); if (id) setSelected(String(id)); setWizard(false);}} onClose={() => setWizard(false)}/>}
    <CustomerDrawer open={drawer?.kind === 'customer'} customer={drawer?.customer} data={data} save={save} reload={reload} busy={busy} workspace={workspace} freeBrands={freeBrands}
      onClose={() => setDrawer(null)} onSaved={async id => {await reloadMap(); if (id) setSelected(String(id));}}/>
    <AccountDrawer open={drawer?.kind === 'account'} account={drawer?.account} data={data} save={save} reload={reload} busy={busy} customerId={current?.id || ''} customers={customers} onClose={() => setDrawer(null)}/>
    <CampaignDrawer open={drawer?.kind === 'campaign'} campaign={drawer?.campaign} data={data} save={save} reload={reload} busy={busy} customerId={current?.id || ''} customers={customers}
      workspace={workspace} brandRefs={current ? brandsOf(current.id).map(brand => brand.ref) : []} onClose={() => setDrawer(null)} onLinksChanged={reloadMap}/>
  </div>;
}

/** Super Tag sites of this client. Every site belongs to a client: new ones are created inside the open client, loose ones get assigned. */
function SitesSection({data, current, selected, customers, canEdit, onError}) {
  const [sites, setSites] = useState(null);
  const [version, setVersion] = useState(0);
  const [connecting, setConnecting] = useState(false);
  const [working, setWorking] = useState('');
  useEffect(() => {
    let live = true;
    json(`${API}/supertag/sites`).then(value => {if (live) setSites((value.sites || []).filter(site => !site.revoked_at));})
      .catch(failure => {if (live) {setSites([]); onError(failure.message);}});
    return () => {live = false;};
  }, [version]);
  const nameOf = id => customers.find(item => item.id === id)?.name || '';
  const visible = (sites || []).filter(site => site.customer_id && (selected === ALL || String(site.customer_id) === selected));
  const unassigned = (sites || []).filter(site => !site.customer_id);
  const connect = async host => {
    await send(data, '/supertag/sites', 'POST', {label: host, allowed_host: host, customer_id: current.id});
    setConnecting(false); setVersion(value => value + 1);
  };
  const assign = async (site, customerId) => {
    if (!customerId) return;
    setWorking(site.id);
    try {await send(data, `/supertag/sites/${site.id}`, 'PATCH', {customer_id: Number(customerId)}); setVersion(value => value + 1);}
    catch (failure) {onError(failure.message);} finally {setWorking('');}
  };
  const row = (site, action) => <li key={site.id} className="flex flex-wrap items-center gap-3 px-6 py-3">
    <span className="min-w-0 flex-1">
      <span className="block truncate text-sm font-semibold text-primary">{site.allowed_host}</span>
      <span className="block truncate text-xs text-tertiary">{site.label !== site.allowed_host ? `${site.label} · ` : ''}{site.last_event_at ? `Último evento em ${new Date(site.last_event_at).toLocaleDateString('pt-BR')} · ${plural(Number(site.events_30d) || 0, 'evento', 'eventos')} em 30 dias` : 'Sem eventos recebidos'}{selected === ALL && site.customer_id ? ` · ${nameOf(site.customer_id)}` : ''}</span>
    </span>
    {action || (site.enabled ? <BadgeWithDot type="pill-color" size="sm" color="success">Ativo</BadgeWithDot> : <BadgeWithDot type="pill-color" size="sm" color="gray">Desativado</BadgeWithDot>)}
  </li>;
  const assignControl = site => current
    ? <Button size="sm" color="secondary" isDisabled={working === site.id} onPress={() => assign(site, current.id)}>Ligar a {current.name}</Button>
    : <div className="w-56"><ReportsNativeSelect size="sm" aria-label={`Cliente de ${site.allowed_host}`} value="" disabled={working === site.id} onChange={event => assign(site, event.target.value)}>
      <option value="">Atribuir a um cliente</option>{customers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
    </ReportsNativeSelect></div>;
  return <section className="overflow-hidden rounded-xl bg-primary shadow-xs ring-1 ring-secondary" aria-label="Sites">
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-secondary px-6 py-5">
      <div className="min-w-60 flex-1">
        <div className="flex items-center gap-2"><h2 className="text-lg font-semibold text-primary">Sites</h2>{sites && <Badge type="pill-color" size="sm" color="brand">{plural(visible.length, 'site', 'sites')}</Badge>}</div>
        <p className="mt-0.5 text-sm text-tertiary">{current ? `Domínios com a Super Tag instalada para ${current.name}.` : 'Domínios com a Super Tag instalada. Cada site pertence a um cliente.'}</p>
      </div>
      {canEdit && current && <Button size="md" color="primary" iconLeading={Plus} onPress={() => setConnecting(true)}>Site</Button>}
    </header>
    {sites === null ? <p className="px-6 py-5 text-sm text-tertiary">Carregando sites…</p>
      : visible.length ? <ul className="divide-y divide-secondary">{visible.map(site => row(site))}</ul>
        : <p className="px-6 py-5 text-sm text-tertiary">{current ? 'Nenhum site ligado a este cliente ainda.' : selected === NONE ? 'Sites sempre pertencem a um cliente.' : 'Nenhum site ligado a clientes ainda.'}</p>}
    {canEdit && !current && sites !== null && <p className="border-t border-secondary px-6 py-3 text-sm text-tertiary">Para adicionar um site, escolha o cliente na barra lateral.</p>}
    {canEdit && unassigned.length > 0 && customers.length > 0 && <div className="border-t border-secondary bg-warning-primary">
      <p className="flex items-center gap-2 px-6 pt-4 text-sm font-semibold text-warning-primary"><AlertTriangle size={16} aria-hidden="true"/>{plural(unassigned.length, 'site sem cliente', 'sites sem cliente')}</p>
      <p className="px-6 pt-0.5 text-sm text-tertiary">Atribua cada um a um cliente para que apareça na análise certa.</p>
      <ul className="divide-y divide-secondary">{unassigned.map(site => row(site, assignControl(site)))}</ul>
    </div>}
    {current && <FlowConnectSite open={connecting} clientId={data.client.client_id} data={null} onConnect={connect} onClose={() => setConnecting(false)}/>}
  </section>;
}

function ClientHeader({data, current, selected, brands, workspace, accounts, campaigns, canManage, onRename, onBrands, onError}) {
  const linked = campaigns.filter(item => (workspace?.campaign_projects?.[String(item.id)] || []).length).length;
  const active = campaigns.filter(item => item.status === 'ENABLED').length;
  const title = current?.name || (selected === NONE ? 'Sem cliente' : 'Todos os clientes');
  const description = current ? `${plural(accounts.length, 'conta', 'contas')} · ${plural(campaigns.length, 'campanha', 'campanhas')}` : selected === NONE ? 'Contas e campanhas da operação própria, sem cliente associado.' : `Visão de todos os clientes de ${data.client.client_name || 'sua operação'}.`;
  const stats = [['Contas de mídia', accounts.filter(item => item.account_kind !== 'manager').length], ['Gerentes (MCC)', accounts.filter(item => item.account_kind === 'manager').length], ['Campanhas ativas', active], ...(workspace ? [['Com projeto', `${linked}/${campaigns.length}`]] : [])];
  const toggleBrand = async (brand, isLinked) => {
    try {await send(data, `/customers/${current.id}/brands`, isLinked ? 'DELETE' : 'POST', {brand_ref: brand.ref}); await onBrands();}
    catch (failure) {onError(failure.message);}
  };
  return <section className="rounded-xl bg-primary px-6 py-5 shadow-xs ring-1 ring-secondary">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 items-center gap-4">
        {current ? <Avatar size="lg" name={current.name} logo={brands.length && workspace ? (workspace.brands.find(item => item.ref === brands[0].ref)?.logo_url || '') : ''}/> : null}
        <div className="min-w-0">
          <h2 className="truncate text-xl font-semibold text-primary">{title}</h2>
          <p className="mt-0.5 text-sm text-tertiary">{description}</p>
        </div>
      </div>
      {current && canManage && <Button size="sm" color="secondary" iconLeading={Edit01} onPress={onRename}>Editar cliente</Button>}
    </div>
    {current && workspace && <div className="mt-4 flex flex-wrap items-center gap-2">
      <span className="text-sm font-medium text-secondary">Marcas do Workspace</span>
      {brands.map(brand => <span key={brand.ref} className="inline-flex items-center gap-1 rounded-md bg-primary py-0.5 pr-1 pl-2 text-sm font-medium text-secondary ring-1 ring-primary ring-inset">
        {brand.name}{!brand.accessible && <span className="text-xs text-tertiary">(sem acesso)</span>}
        {canManage && brand.accessible && <CaduTooltip label="Desvincular marca"><Button size="sm" color="tertiary" iconLeading={XClose} aria-label={`Desvincular ${brand.name}`} className="!p-0.5" onPress={() => toggleBrand(brand, true)}/></CaduTooltip>}
      </span>)}
      {canManage && <Picker label="Vincular marca" emptyLabel={brands.length ? 'Marca' : 'Vincular marca'} items={workspace.brands} selected={brands.map(brand => brand.ref)}
        onToggle={(item, isLinked) => toggleBrand(item, isLinked)} placeholder="Buscar marca" empty="Nenhuma marca no Workspace."/>}
      {!brands.length && !canManage && <span className="text-sm text-tertiary">Nenhuma marca vinculada.</span>}
    </div>}
    <dl className={`mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-lg bg-border-secondary ring-1 ring-secondary ${stats.length === 4 ? 'sm:grid-cols-4' : 'sm:grid-cols-3'}`}>
      {stats.map(([label, value]) => <div key={label} className="bg-primary px-4 py-3"><dt className="text-xs font-medium text-tertiary">{label}</dt><dd className="mt-0.5 text-lg font-semibold text-primary tabular-nums">{typeof value === 'number' ? value.toLocaleString('pt-BR') : value}</dd></div>)}
    </dl>
  </section>;
}

/** Searchable list in a popover. Rows toggle; an optional footer action creates a new entry. */
function Picker({label, emptyLabel, items, selected, onToggle, placeholder, empty, groups, create, compact = false}) {
  const [query, setQuery] = useState('');
  const needle = query.trim().toLowerCase();
  const chosen = new Set(selected);
  const sections = (groups || [[null, items]]).map(([title, list]) => [title, list.filter(item => matches(needle, item.name))]).filter(([, list]) => list.length);
  return <DialogTrigger onOpenChange={open => {if (!open) setQuery('');}}>
    <Button size="sm" color={compact ? 'link-gray' : 'secondary'} iconLeading={compact ? undefined : Plus}>{emptyLabel || label}</Button>
    <Popover placement="bottom start" offset={6} className="untitled-scope w-80 overflow-hidden rounded-lg bg-primary shadow-lg ring-1 ring-secondary_alt outline-hidden entering:animate-in entering:fade-in">
      <Dialog aria-label={label} className="outline-hidden">
        {({close}) => <>
          <div className="border-b border-secondary p-2"><ReportsFieldInput size="sm" autoFocus aria-label={placeholder} placeholder={placeholder} value={query} onChange={event => setQuery(event.target.value)}
            leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/></div>
          <div className="max-h-72 overflow-y-auto p-1.5" role="listbox" aria-label={label}>
            {sections.map(([title, list]) => <div key={title || 'all'}>
              {title && <p className="px-2 pt-2 pb-1 text-xs font-semibold text-tertiary">{title}</p>}
              {list.map(item => {
                const isOn = chosen.has(item.ref);
                return <button key={item.ref} type="button" role="option" aria-selected={isOn} onClick={() => onToggle(item, isOn)}
                  className="flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-left text-sm font-medium text-secondary hover:bg-primary_hover focus-visible:bg-primary_hover focus-visible:outline-hidden">
                  <span className="min-w-0 flex-1 truncate">{item.name}</span>
                  {isOn && <Check size={16} aria-hidden="true" className="shrink-0 text-fg-brand-primary"/>}
                </button>;
              })}
            </div>)}
            {!sections.length && <p className="px-2 py-3 text-sm text-tertiary">{needle ? 'Nada encontrado.' : empty}</p>}
          </div>
          {create && <div className="border-t border-secondary p-1.5">
            <button type="button" onClick={async () => {await create(query.trim()); close();}}
              className="flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-left text-sm font-semibold text-brand-secondary hover:bg-primary_hover">
              <FolderPlus size={16} aria-hidden="true" className="shrink-0"/><span className="min-w-0 truncate">{create.label(query.trim())}</span>
            </button>
          </div>}
        </>}
      </Dialog>
    </Popover>
  </DialogTrigger>;
}

/** Projects of one campaign: chips plus a picker that links, unlinks or creates a Workspace project. */
function ProjectCell({data, campaign, workspace, brandRefs, canEdit, onChanged, onError}) {
  const links = workspace.campaign_projects?.[String(campaign.id)] || [];
  const brands = new Set(brandRefs);
  const suggested = workspace.projects.filter(item => item.brand_refs.some(ref => brands.has(ref)));
  const others = workspace.projects.filter(item => !suggested.includes(item));
  const call = async (path, method, payload) => {
    try {await send(data, path, method, payload); await onChanged();} catch (failure) {onError(failure.message);}
  };
  const toggle = (item, isLinked) => call(`/workspace/campaign/${campaign.id}`, isLinked ? 'DELETE' : 'POST', {project_ref: item.ref});
  const create = name => call(`/workspace/campaign/${campaign.id}/create-project`, 'POST', {name: name || campaign.name, idempotency_key: crypto.randomUUID()});
  create.label = name => `Criar projeto “${name || campaign.name}”`;
  return <div className="flex flex-wrap items-center gap-1.5">
    {links.map(item => <Badge key={item.ref} type="color" size="sm" color={item.accessible ? 'brand' : 'gray'}>{item.name}</Badge>)}
    {canEdit ? <Picker compact label="Projetos do Workspace" emptyLabel={links.length ? 'Alterar' : 'Associar projeto'} items={workspace.projects} selected={links.map(item => item.ref)}
      groups={suggested.length ? [['Da marca deste cliente', suggested], ['Outros projetos', others]] : null} onToggle={toggle} create={create}
      placeholder="Buscar projeto" empty="Nenhum projeto no Workspace."/> : !links.length && <span className="text-sm text-quaternary">—</span>}
  </div>;
}

function HierarchyTable({data, accounts, campaigns, query, platform, showInactive, collapsed, toggle, workspace, brandRefs, canEdit, onLinksChanged, onError, showClient, customers, onEditAccount, onEditCampaign}) {
  const customerName = id => customers.find(item => item.id === id)?.name;
  const campaignMatches = item => matches(query, item.name, item.external_id, channelLabel(item.channel_type || item.objective));
  const accountMatches = item => matches(query, item.name, item.external_id, platformName(item.platform));
  const keepAccount = item => (!platform || item.platform === platform) && (showInactive || item.status === 'active');
  const keepCampaign = item => showInactive || item.status === 'ENABLED';
  const campaignsOf = id => campaigns.filter(item => item.account_id === id && keepCampaign(item));
  const managers = accounts.filter(item => item.account_kind === 'manager' && keepAccount(item));
  const managerIds = new Set(managers.map(item => item.id));
  const advertisers = accounts.filter(item => item.account_kind !== 'manager' && keepAccount(item));
  const manual = platform ? [] : campaigns.filter(item => !item.account_id && keepCampaign(item));

  // A row survives the search when it matches or leads to something that matches.
  const advertiserRows = account => {
    const own = accountMatches(account);
    const children = campaignsOf(account.id).filter(item => own || campaignMatches(item));
    return own || children.length ? {account, children} : null;
  };
  const groups = [
    ...managers.map(manager => {
      const children = advertisers.filter(item => item.parent_account_id === manager.id).map(advertiserRows).filter(Boolean);
      return accountMatches(manager) || children.length ? {account: manager, advertisers: accountMatches(manager) && !children.length ? advertisers.filter(item => item.parent_account_id === manager.id).map(account => ({account, children: campaignsOf(account.id)})) : children} : null;
    }).filter(Boolean),
    ...advertisers.filter(item => !managerIds.has(item.parent_account_id)).map(advertiserRows).filter(Boolean),
  ];
  const manualRows = manual.filter(campaignMatches);
  const open = id => query ? true : !collapsed.has(id);
  const columns = workspace ? 'grid-cols-[minmax(220px,3fr)_124px_104px_minmax(160px,2fr)_40px]' : 'grid-cols-[minmax(220px,1fr)_160px_112px_40px]';
  const row = `grid ${columns} items-center gap-4 border-b border-secondary px-6 min-h-14 py-2.5`;

  const accountRow = ({account, depth, childCount, isManager}) => {
    const expanded = open(account.id);
    const [statusLabel] = ACCOUNT_STATUS[account.status] || [];
    return <div key={`a${account.id}`} role="row" className={`${row} bg-secondary_subtle`}>
      <div role="gridcell" className="flex min-w-0 items-center gap-2" style={{paddingLeft: depth * 28}}>
        {childCount ? <button type="button" onClick={() => toggle(account.id)} aria-expanded={expanded} aria-label={`${expanded ? 'Recolher' : 'Expandir'} ${account.name}`}
          className="flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-md text-fg-quaternary hover:bg-primary_hover hover:text-fg-quaternary_hover">{expanded ? <ChevronDown size={16}/> : <ChevronRight size={16}/>}</button> : <span className="size-6 shrink-0"/>}
        <span className="flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-md bg-primary ring-1 ring-secondary [&_img]:size-4 [&_svg]:h-3.5 [&_svg]:w-5"><FlowPlatformLogo platform={account.platform}/></span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-primary">{account.name}</p>
          <p className="truncate text-xs text-tertiary">{isManager ? `Gerente (MCC) · ${plural(childCount, 'conta', 'contas')}` : `${platformName(account.platform)} · ${plural(childCount, 'campanha', 'campanhas')}`}{showClient && customerName(account.customer_id) ? ` · ${customerName(account.customer_id)}` : ''}</p>
        </div>
      </div>
      <span role="gridcell" className="truncate font-mono text-xs text-tertiary">{account.external_id}</span>
      <span role="gridcell">{statusLabel ? <Status map={ACCOUNT_STATUS} value={account.status}/> : null}</span>
      {workspace && <span role="gridcell"/>}
      <span role="gridcell" className="flex justify-end">{canEdit && <CaduTooltip label="Editar conta"><Button size="sm" color="tertiary" iconLeading={Edit01} aria-label={`Editar ${account.name}`} onPress={() => onEditAccount(account)}/></CaduTooltip>}</span>
    </div>;
  };

  const campaignRow = ({campaign, depth}) => <div key={`c${campaign.id}`} role="row" className={`${row} hover:bg-primary_hover`}>
    <div role="gridcell" className="flex min-w-0 items-center gap-2" style={{paddingLeft: depth * 28 + 32}}>
      <div className="min-w-0">
        <a href={`${APP_BASE}/media/campaigns/${campaign.id}`} className="block truncate text-sm font-medium text-primary hover:text-brand-secondary hover:underline">{campaign.name}</a>
        <p className="truncate text-xs text-tertiary">{[channelLabel(campaign.channel_type || campaign.objective), !campaign.account_id && 'Campanha manual', showClient && customerName(campaign.customer_id)].filter(Boolean).join(' · ') || 'Campanha'}</p>
      </div>
    </div>
    <span role="gridcell" className="truncate font-mono text-xs text-tertiary">{campaign.external_id || '—'}</span>
    <span role="gridcell"><Status map={CAMPAIGN_STATUS} value={campaign.status}/></span>
    {workspace && <div role="gridcell" className="min-w-0"><ProjectCell data={data} campaign={campaign} workspace={workspace} brandRefs={brandRefs} canEdit={canEdit} onChanged={onLinksChanged} onError={onError}/></div>}
    <span role="gridcell" className="flex justify-end">{canEdit && <CaduTooltip label="Editar campanha"><Button size="sm" color="tertiary" iconLeading={Edit01} aria-label={`Editar ${campaign.name}`} onPress={() => onEditCampaign(campaign)}/></CaduTooltip>}</span>
  </div>;

  const rows = [];
  for (const group of groups) {
    if (group.advertisers) {
      rows.push(accountRow({account: group.account, depth: 0, isManager: true, childCount: group.advertisers.length}));
      if (!open(group.account.id)) continue;
      for (const child of group.advertisers) {
        rows.push(accountRow({account: child.account, depth: 1, childCount: child.children.length}));
        if (open(child.account.id)) child.children.forEach(item => rows.push(campaignRow({campaign: item, depth: 1})));
      }
    } else {
      rows.push(accountRow({account: group.account, depth: 0, childCount: group.children.length}));
      if (open(group.account.id)) group.children.forEach(item => rows.push(campaignRow({campaign: item, depth: 0})));
    }
  }
  if (manualRows.length) {
    rows.push(<div key="manual" role="row" className={`${row} bg-secondary_subtle`}><div role="gridcell" className="col-span-full flex items-center gap-2 pl-8">
      <p className="text-sm font-semibold text-primary">Campanhas manuais</p><span className="text-xs text-tertiary">sem conta de mídia conectada</span></div></div>);
    manualRows.forEach(item => rows.push(campaignRow({campaign: item, depth: 0})));
  }

  if (!rows.length) return <div className="px-6 py-10 text-center">
    <p className="text-md font-semibold text-primary">{query || platform || !showInactive ? 'Nada corresponde aos filtros' : 'Nenhuma conta ou campanha ainda'}</p>
    <p className="mt-1 text-sm text-tertiary">{query || platform || !showInactive ? 'Ajuste a busca ou os filtros.' : 'Adicione uma conta de mídia ou conecte uma fonte em Fontes de dados.'}</p>
  </div>;
  return <div role="grid" aria-label="Contas e campanhas" className="overflow-x-auto">
    <div className="min-w-[720px]">
      <div role="row" className={`grid ${columns} items-center gap-4 border-b border-secondary bg-secondary px-6 py-3 text-xs font-semibold text-tertiary`}>
        <span role="columnheader">Conta / campanha</span><span role="columnheader">ID</span><span role="columnheader">Status</span>{workspace && <span role="columnheader">Projeto do Workspace</span>}<span role="columnheader" className="sr-only">Ações</span>
      </div>
      {rows}
    </div>
  </div>;
}

function DrawerActions({onCancel, busy, label}) {
  return <div className="mt-2 flex justify-end gap-3 border-t border-secondary pt-4">
    <Button type="button" size="md" color="secondary" onPress={onCancel}>Cancelar</Button>
    <Button type="submit" size="md" color="primary" isDisabled={busy} isLoading={busy}>{label}</Button>
  </div>;
}

function CustomerDrawer({open, customer, data, save, reload, busy, workspace, freeBrands, onClose, onSaved}) {
  const [name, setName] = useState('');
  const [brand, setBrand] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {if (open) {setName(customer?.name || ''); setBrand(''); setError('');}}, [open, customer]);
  const chosen = freeBrands.find(item => item.ref === brand);
  const submit = async event => {
    event.preventDefault();
    try {
      const result = await save(customer ? `/customers/${customer.id}` : '/customers', {name: name || chosen?.name, status: 'active'}, !chosen, customer ? 'PATCH' : 'POST');
      const id = customer?.id || result.customer?.id;
      if (chosen && id) {await send(data, `/customers/${id}/brands`, 'POST', {brand_ref: chosen.ref}); await reload();}
      await onSaved(id); onClose();
    } catch (failure) {setError(failure.message);}
  };
  const archive = async () => {
    try {await save(`/customers/${customer.id}`, {name: customer.name, status: 'archived'}, true, 'PATCH'); await onSaved(null); onClose();}
    catch (failure) {setError(failure.message);}
  };
  return <ReportsDrawer open={open} onOpenChange={value => {if (!value) onClose();}} title={customer ? 'Editar cliente' : 'Novo cliente'} context={data.client.client_name}
    description={customer ? 'O nome aparece nos relatórios e nos filtros.' : 'Um cliente reúne marcas, contas de mídia e campanhas de um anunciante.'}>
    <form className="flex flex-col gap-5" onSubmit={submit}>
      {!customer && workspace && freeBrands.length > 0 && <ReportsNativeSelect label="A partir de uma marca do Workspace" value={brand} onChange={event => {setBrand(event.target.value); const item = freeBrands.find(entry => entry.ref === event.target.value); if (item && !name) setName(item.name);}}
        hint="O cliente já nasce vinculado à marca. Projetos dela aparecem como sugestão nas campanhas.">
        <option value="">Nenhuma, criar só no Reports</option>
        {freeBrands.map(item => <option key={item.ref} value={item.ref}>{item.name}</option>)}
      </ReportsNativeSelect>}
      <ReportsFieldInput label="Nome do cliente ou anunciante" required maxLength={200} value={name} onChange={event => setName(event.target.value)} placeholder="Ex.: Loja Verão"/>
      {error && <p role="alert" className="text-sm text-error-primary">{error}</p>}
      <DrawerActions onCancel={onClose} busy={busy} label={customer ? 'Salvar' : 'Criar cliente'}/>
      {customer && <div className="rounded-lg bg-secondary_subtle p-4 ring-1 ring-secondary">
        <p className="text-sm font-semibold text-primary">Arquivar cliente</p>
        <p className="mt-1 text-sm text-tertiary">Some da lista e dos filtros. Contas, campanhas e histórico continuam guardados.</p>
        <Button className="mt-3" type="button" size="sm" color="secondary-destructive" isDisabled={busy} onPress={archive}>Arquivar</Button>
      </div>}
    </form>
  </ReportsDrawer>;
}

const emptyAccount = customerId => ({platform: 'google_ads', account_kind: 'advertiser', name: '', external_id: '', parent_account_id: '', status: 'active', customer_id: String(customerId || '')});

function AccountDrawer({open, account, data, save, reload, busy, customerId, customers, onClose}) {
  const [form, setForm] = useState(emptyAccount(customerId));
  const [error, setError] = useState('');
  useEffect(() => {
    if (!open) return;
    setError('');
    setForm(account ? {platform: account.platform, account_kind: account.account_kind, name: account.name, external_id: account.external_id, parent_account_id: String(account.parent_account_id || ''), status: account.status || 'active', customer_id: String(account.customer_id || '')} : emptyAccount(customerId));
  }, [open, account, customerId]);
  const set = patch => setForm(previous => ({...previous, ...patch}));
  const managers = data.accounts.filter(item => item.account_kind === 'manager' && item.platform === form.platform && item.status !== 'disabled' && item.id !== account?.id);
  const google = form.platform === 'google_ads';
  const submit = async event => {
    event.preventDefault();
    try {
      if (account) {
        await save(`/accounts/${account.id}`, {name: form.name, external_id: form.external_id, status: form.status, parent_account_id: form.parent_account_id || null}, false, 'PATCH');
        if (String(account.customer_id || '') !== form.customer_id) await save(`/account/${account.id}/customer`, {customer_id: form.customer_id || null}, false, 'PATCH');
        await reload();
      } else {
        await save('/accounts', {...form, parent_account_id: form.parent_account_id || null, customer_id: form.customer_id || null});
      }
      onClose();
    } catch (failure) {setError(failure.message);}
  };
  return <ReportsDrawer open={open} onOpenChange={value => {if (!value) onClose();}} title={account ? 'Editar conta de mídia' : 'Adicionar conta de mídia'} context={data.client.client_name}
    description="Identifique a conta como ela aparece na plataforma e, se houver, a conta gerente.">
    <form className="flex flex-col gap-5" onSubmit={submit}>
      <div className="grid grid-cols-2 gap-4">
        <ReportsNativeSelect label="Plataforma" disabled={Boolean(account)} value={form.platform} onChange={event => set({platform: event.target.value, parent_account_id: ''})}>
          <option value="google_ads">Google Ads</option><option value="meta_ads">Meta Ads</option><option value="microsoft_ads">Microsoft Ads</option><option value="linkedin_ads">LinkedIn Ads</option><option value="tiktok_ads">TikTok Ads</option><option value="other">Outra</option>
        </ReportsNativeSelect>
        <ReportsNativeSelect label="Tipo" disabled={Boolean(account)} value={form.account_kind} onChange={event => set({account_kind: event.target.value, parent_account_id: ''})}>
          <option value="advertiser">Conta de anúncios</option><option value="manager">Gerente (MCC)</option>
        </ReportsNativeSelect>
      </div>
      <ReportsFieldInput label="Nome da conta" required maxLength={240} value={form.name} onChange={event => set({name: event.target.value})} placeholder="Nome exibido na plataforma"/>
      <ReportsFieldInput label="ID da conta" required maxLength={160} value={form.external_id} onChange={event => set({external_id: event.target.value})} className="font-mono"
        placeholder={google ? '123-456-7890' : 'ID fornecido pela plataforma'} hint={google ? '10 dígitos, com ou sem hífens.' : 'Copie o identificador exibido na plataforma.'}/>
      <div className="grid grid-cols-2 gap-4">
        {form.account_kind === 'advertiser' ? <ReportsNativeSelect label="Conta gerente" value={form.parent_account_id} onChange={event => set({parent_account_id: event.target.value})}>
          <option value="">Sem gerente</option>{managers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </ReportsNativeSelect> : <span/>}
        {account ? <ReportsNativeSelect label="Status" value={form.status} onChange={event => set({status: event.target.value})}>
          <option value="active">Ativa</option><option value="paused">Pausada</option><option value="disabled">Desativada</option>
        </ReportsNativeSelect> : <span/>}
      </div>
      <ReportsNativeSelect label="Cliente" value={form.customer_id} onChange={event => set({customer_id: event.target.value})} hint={account ? 'Contas com campanhas mantêm o cliente para preservar o histórico.' : undefined}>
        <option value="">Sem cliente (operação própria)</option>{customers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </ReportsNativeSelect>
      {error && <p role="alert" className="text-sm text-error-primary">{error}</p>}
      <DrawerActions onCancel={onClose} busy={busy} label={account ? 'Salvar' : 'Adicionar conta'}/>
    </form>
  </ReportsDrawer>;
}

const emptyCampaign = customerId => ({customer_id: String(customerId || ''), account_id: '', name: '', external_id: '', objective: '', channel_type: '', tags: '', project: ''});

function CampaignDrawer({open, campaign, data, save, reload, busy, customerId, customers, workspace, brandRefs, onClose, onLinksChanged}) {
  const [form, setForm] = useState(emptyCampaign(customerId));
  const [error, setError] = useState('');
  useEffect(() => {
    if (!open) return;
    setError('');
    const tags = campaign?.metadata?.tags || [];
    setForm(campaign ? {customer_id: String(campaign.customer_id || ''), account_id: String(campaign.account_id || ''), name: campaign.name, external_id: campaign.external_id || '', objective: campaign.objective || '', channel_type: campaign.channel_type || '', tags: tags.join(', '), project: ''} : emptyCampaign(customerId));
  }, [open, campaign, customerId]);
  const set = patch => setForm(previous => ({...previous, ...patch}));
  const advertisers = data.accounts.filter(item => item.account_kind === 'advertiser' && item.status !== 'disabled' && String(item.customer_id || '') === form.customer_id);
  const locked = Boolean(campaign?.account_id);
  const brands = new Set(brandRefs);
  const projects = useMemo(() => {
    const list = workspace?.projects || [];
    return [...list.filter(item => item.brand_refs.some(ref => brands.has(ref))), ...list.filter(item => !item.brand_refs.some(ref => brands.has(ref)))];
  }, [workspace, brandRefs.join()]);
  const submit = async event => {
    event.preventDefault();
    try {
      const tags = form.tags.split(',').map(tag => tag.trim()).filter(Boolean);
      const payload = {name: form.name, objective: form.objective, channel_type: form.channel_type, account_id: form.account_id || null, external_id: form.external_id, tags};
      const result = campaign ? await save(`/campaigns/${campaign.id}`, payload, false, 'PATCH') : await save('/campaigns', {...payload, customer_id: form.customer_id || null}, false);
      const id = campaign?.id || result.campaign?.id;
      if (id && form.project === 'new') await send(data, `/workspace/campaign/${id}/create-project`, 'POST', {name: form.name, idempotency_key: crypto.randomUUID()});
      else if (id && form.project) await send(data, `/workspace/campaign/${id}`, 'POST', {project_ref: form.project});
      await reload();
      if (form.project) await onLinksChanged();
      onClose();
    } catch (failure) {setError(failure.message);}
  };
  return <ReportsDrawer open={open} onOpenChange={value => {if (!value) onClose();}} title={campaign ? 'Editar campanha' : 'Adicionar campanha'} context={data.client.client_name}
    description={campaign ? 'Campanhas conectadas mantêm a conta; nome e classificação podem mudar.' : 'Crie uma campanha manual ou ligue-a a uma conta de mídia do cliente.'}>
    <form className="flex flex-col gap-5" onSubmit={submit}>
      <div className="grid grid-cols-2 gap-4">
        <ReportsNativeSelect label="Cliente" disabled={Boolean(campaign)} value={form.customer_id} onChange={event => set({customer_id: event.target.value, account_id: ''})}>
          <option value="">Sem cliente</option>{customers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </ReportsNativeSelect>
        <ReportsNativeSelect label="Conta de mídia" disabled={locked} value={form.account_id} onChange={event => set({account_id: event.target.value})}>
          <option value="">Campanha manual</option>{(locked ? data.accounts.filter(item => item.id === campaign.account_id) : advertisers).map(item => <option key={item.id} value={item.id}>{item.name} · {platformName(item.platform)}</option>)}
        </ReportsNativeSelect>
      </div>
      <ReportsFieldInput label="Nome da campanha" required maxLength={240} value={form.name} onChange={event => set({name: event.target.value})} placeholder="Como aparece na plataforma"/>
      {form.account_id && <ReportsFieldInput label="ID da campanha" required disabled={locked} maxLength={160} value={form.external_id} onChange={event => set({external_id: event.target.value})} className="font-mono"
        placeholder="Identificador na plataforma" hint="Liga os dados importados a esta campanha."/>}
      <div className="grid grid-cols-2 gap-4">
        <ReportsFieldInput label="Objetivo" maxLength={160} value={form.objective} onChange={event => set({objective: event.target.value})} placeholder="Ex.: leads"/>
        <ReportsFieldInput label="Tipo de canal" maxLength={64} value={form.channel_type} onChange={event => set({channel_type: event.target.value})} placeholder="Ex.: pesquisa, social"/>
      </div>
      <ReportsFieldInput label="Tags" value={form.tags} onChange={event => set({tags: event.target.value})} placeholder="Separe por vírgula: marca-a, outono, urgente" hint="Organize campanhas em grupos personalizados."/>
      {workspace && !campaign && <ReportsNativeSelect label="Projeto do Workspace" value={form.project} onChange={event => set({project: event.target.value})} hint="Opcional. Você também pode associar depois, direto na lista.">
        <option value="">Não associar agora</option>
        <option value="new">Criar projeto com o nome da campanha</option>
        {projects.map(item => <option key={item.ref} value={item.ref}>{item.name}</option>)}
      </ReportsNativeSelect>}
      {error && <p role="alert" className="text-sm text-error-primary">{error}</p>}
      <DrawerActions onCancel={onClose} busy={busy} label={campaign ? 'Salvar' : 'Adicionar campanha'}/>
    </form>
  </ReportsDrawer>;
}
