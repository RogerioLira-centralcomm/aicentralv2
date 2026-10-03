import React, {useEffect, useState} from 'react';
import {AlertTriangle, ArrowUpRight, BarChart01, CheckCircle, ChevronRight, Code01, Copy01, Download01, GitBranch01, Plus, RefreshCw01, SearchLg, Send01, Target04, Trash01} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {CaduTooltip} from '../cadu-design-system/components/CaduTooltip.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsTabs} from './ReportsTabs.jsx';
import {ReportsConfirmDialog} from './ReportsConfirmDialog.jsx';
import {ReportsRelationships} from './ReportsRelationships.jsx';
import {Alert, Callout, Card, DataTable, DrawerActions, EmptyNote, Stats} from './ReportsBlocks.jsx';
import {decimal, integer, json, reportUrl, shortDate} from './reportsCommon.jsx';

const API = '/connect/api/v2/reports/supertag';
const EVENT_LABELS = {page_view: 'Visualização de página', page_leave: 'Saída de página', click: 'Clique', whatsapp_click: 'Clique no WhatsApp', form_submit: 'Envio de formulário',
  visibility: 'Elemento visível', scroll_depth: 'Rolagem', custom_event: 'Evento personalizado', conversion: 'Conversão', heartbeat: 'Tempo ativo'};
const AUDIENCE_DAYS = [[30, '30 dias'], [60, '60 dias'], [90, '90 dias'], [180, '6 meses'], [365, '1 ano'], [395, '13 meses (máximo do navegador)']];
const RETENTION_DAYS = [[30, '30 dias'], [60, '60 dias'], [90, '90 dias'], [180, '6 meses'], [365, '1 ano'], [730, '2 anos'], [1095, '3 anos'], [1825, '5 anos']];
const seconds = value => value == null ? '—' : `${decimal(value)} s`;
const hostKey = value => String(value || '').replace(/^www\./, '');
const longDate = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: 'numeric', month: 'short', year: 'numeric'}) : '—';

export function relativeTime(value) {
  if (!value) return null;
  const elapsed = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (elapsed < 90) return 'agora há pouco';
  const minutes = Math.round(elapsed / 60);
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `há ${hours} h` : `há ${Math.round(hours / 24)} dias`;
}

/** One word for where a site stands, shared by the list, the header and the checks. */
export function siteState(site) {
  if (site.revoked_at) return ['Revogada', 'error'];
  if (!site.enabled) return ['Desativada', 'gray'];
  if (Number(site.events_30d) > 0) return ['Coleta ativa', 'success'];
  if (site.last_event_at) return ['Sem eventos recentes', 'warning'];
  return ['Nunca recebeu eventos', 'gray'];
}

const faviconCache = new Map();
/** The initial stays until an image really loads, so a failing favicon never shows a broken image. */
function Favicon({site, size = 'md'}) {
  const host = site.allowed_host;
  const [src, setSrc] = useState(() => faviconCache.get(host) ?? `https://${host}/favicon.ico`);
  const [loaded, setLoaded] = useState(false);
  const [checked, setChecked] = useState(false);
  useEffect(() => {setSrc(faviconCache.get(host) ?? `https://${host}/favicon.ico`); setLoaded(false); setChecked(false);}, [host]);
  const recover = async () => {
    setLoaded(false);
    if (checked) {faviconCache.set(host, ''); setSrc(''); return;}
    setChecked(true);
    try {const preview = await json(`${API}/site-check?url=${encodeURIComponent(`https://${host}`)}`); faviconCache.set(host, preview.favicon || ''); setSrc(preview.favicon || '');}
    catch (_) {faviconCache.set(host, ''); setSrc('');}
  };
  const box = size === 'lg' ? 'size-12 rounded-xl text-md' : 'size-8 rounded-lg text-xs';
  return <span aria-hidden="true" className={`relative flex shrink-0 items-center justify-center overflow-hidden bg-primary font-semibold text-tertiary ring-1 ring-secondary ${box}`}>
    {(site.label || host).trim().charAt(0).toUpperCase()}
    {src && <img src={src} alt="" referrerPolicy="no-referrer" onLoad={() => setLoaded(true)} onError={recover} className={`absolute inset-0 m-auto size-1/2 object-contain ${loaded ? '' : 'invisible'}`}/>}
  </span>;
}

/** Super Tag: the sites that send activity, how each one is installed and what it measures. */
export function SuperTagPage({data}) {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(() => location.pathname.match(/^\/connect\/app\/supertag\/sites\/([0-9a-f-]{36})(?:\/monitor)?\/?$/i)?.[1] || '');
  const [tab, setTab] = useState('overview');
  const [flows, setFlows] = useState([]);
  const [query, setQuery] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [installOpen, setInstallOpen] = useState(false);
  const [verify, setVerify] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const canEdit = data.client.role !== 'viewer';

  const load = async () => {
    const value = await json(`${API}/sites`);
    setSites(value.sites || []);
    if (!selectedId || !(value.sites || []).some(item => item.id === selectedId)) setSelectedId('');
  };
  useEffect(() => {
    let active = true;
    setSites([]); setLoading(true);
    json(`${API}/sites`).then(value => {
      if (!active) return;
      const next = value.sites || [];
      setSites(next);
      setSelectedId(current => current && !next.some(item => item.id === current) ? '' : current);
    }).catch(failure => {if (active) setError(failure.message);}).finally(() => {if (active) setLoading(false);});
    return () => {active = false;};
  }, [data.client.client_id]);
  useEffect(() => {
    setDetail(null); setFlows([]); setError(''); setVerify(null);
    if (!selectedId) {setDetailLoading(false); return undefined;}
    let cancelled = false; setDetailLoading(true);
    Promise.allSettled([json(`${API}/sites/${selectedId}/events`), json('/connect/api/v2/reports/flow?view=create')]).then(([events, flowList]) => {
      if (cancelled) return;
      if (events.status === 'fulfilled') setDetail(events.value);
      if (flowList.status === 'fulfilled') setFlows(flowList.value.flows || []);
      setError([events.status === 'rejected' && `Não foi possível carregar a atividade: ${events.reason.message}`, flowList.status === 'rejected' && `Não foi possível carregar os fluxos: ${flowList.reason.message}`].filter(Boolean).join(' '));
    }).finally(() => {if (!cancelled) setDetailLoading(false);});
    return () => {cancelled = true;};
  }, [selectedId, data.client.client_id]);

  const selected = sites.find(item => item.id === selectedId);
  const hasEvents = Number(selected?.events_30d || detail?.site?.events_30d || 0) > 0;
  const linked = selected ? flows.filter(item => hostKey(item.allowed_host) === hostKey(selected.allowed_host)) : [];
  const run = async action => {setBusy(true); setError(''); try {await action();} catch (failure) {setError(failure.message);} finally {setBusy(false);}};
  const update = changes => run(async () => {
    await json(`${API}/sites/${selectedId}`, {method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify(changes)});
    await load(); setDetail(await json(`${API}/sites/${selectedId}/events`));
  });
  const revoke = () => run(async () => {
    await json(`${API}/sites/${selectedId}/revoke`, {method: 'POST', headers: {'X-CSRF-Token': data.csrf}, body: JSON.stringify({})});
    setRevokeOpen(false); setSelectedId(''); await load(); location.assign(reportUrl('supertag'));
  });
  const copy = async value => {
    try {await navigator.clipboard.writeText(value); setNotice('Código copiado.');} catch (_) {setNotice('Não foi possível copiar. Selecione o código e copie.');}
    setTimeout(() => setNotice(''), 2500);
  };
  const verifyInstall = async () => {
    setVerifying(true); setError('');
    try {
      const [result, latest] = await Promise.all([json(`${API}/sites/${selectedId}/verify-install`), json(`${API}/sites/${selectedId}/events`)]);
      setVerify(result); setDetail(latest); await load();
    } catch (failure) {setError(failure.message);} finally {setVerifying(false);}
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([selected.snippet], {type: 'text/plain;charset=utf-8'}));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `cadu-supertag-${selected.allowed_host}.txt`; anchor.click(); URL.revokeObjectURL(url);
  };
  const email = () => {
    const subject = encodeURIComponent(`Instalação da Super Tag no site ${selected.allowed_host}`);
    const body = encodeURIComponent(`Olá!\n\nPor favor, instale a Super Tag no site ${selected.allowed_host}.\n\nCole este código antes de </head> ou pelo gerenciador de tags:\n\n${selected.snippet}\n\nDepois de publicar, avise para validarmos o primeiro envio.\n`);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };
  const tabs = [{id: 'overview', label: 'Visão geral'}, ...(hasEvents ? [{id: 'activity', label: 'Atividade'}] : []), {id: 'install', label: 'Instalação'},
    {id: 'flows', label: 'Fluxos', count: linked.length || undefined}, {id: 'settings', label: 'Configurações'}];
  const active = sites.filter(site => Number(site.events_30d) > 0).length;
  const install = selected && <InstallCard site={selected} onCopy={() => copy(selected.snippet)} onDownload={download} onEmail={email}/>;

  return <div className="untitled-scope grid items-start gap-6 lg:grid-cols-[288px_minmax(0,1fr)]">
    <SiteList sites={sites} loading={loading} query={query} onQuery={setQuery} selectedId={selectedId} canAdd={canEdit} onAdd={() => setInstallOpen(true)} active={active}/>
    <div className="flex min-w-0 flex-col gap-6">
      {error && <Alert>{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}
      {!selected && !loading && <Card><EmptyNote title={sites.length ? 'Escolha um site' : canEdit ? 'Conecte seu primeiro site' : 'Nenhum site conectado'}>
        {sites.length ? 'Selecione um site na lista para ver instalação, eventos e fluxos.' : canEdit ? 'Instale a Super Tag para acompanhar visitas, eventos e conversões.' : 'Os sites autorizados para este cliente aparecem aqui.'}
        {!sites.length && canEdit && <span className="mt-4 block"><Button size="md" color="primary" iconLeading={Plus} onPress={() => setInstallOpen(true)}>Conectar site</Button></span>}
      </EmptyNote></Card>}
      {selected && <>
        <SiteHeader site={selected} hasEvents={hasEvents} flowsCount={detailLoading ? null : linked.length}/>
        <ReportsTabs label="Áreas do site" value={tabs.some(item => item.id === tab) ? tab : 'overview'} onChange={setTab} items={tabs}/>
        {detailLoading && <p role="status" className="text-sm text-tertiary">Carregando dados do site…</p>}
        {(tab === 'overview' || (tab === 'activity' && !hasEvents)) && <>
          <InstallStatus site={selected} hasEvents={hasEvents} verify={verify} verifying={verifying} onVerify={verifyInstall} onCopy={() => copy(selected.snippet)} onGuide={() => setTab('install')}/>
          {hasEvents && detail ? <Audience detail={detail}/> : <div className="grid items-start gap-6 xl:grid-cols-2">{install}<InstallGuide/></div>}
        </>}
        {tab === 'activity' && hasEvents && detail && <Activity detail={detail}/>}
        {tab === 'install' && <div className="grid items-start gap-6 xl:grid-cols-2">{install}<InstallGuide/></div>}
        {tab === 'flows' && <LinkedFlows linked={linked} site={selected}/>}
        {tab === 'settings' && <Settings data={data} site={selected} busy={busy} canEdit={canEdit} onUpdate={update} onRevoke={() => setRevokeOpen(true)}/>}
      </>}
    </div>
    <InstallDrawer open={installOpen} data={data} onClose={() => setInstallOpen(false)} onCreated={async site => {await load(); location.assign(reportUrl('supertag', {}, site.id));}}/>
    <ReportsConfirmDialog open={revokeOpen} title="Revogar Super Tag" description="A coleta neste domínio será interrompida. Os dados já recebidos permanecem no Reports." confirmLabel="Revogar instalação" busy={busy} onCancel={() => setRevokeOpen(false)} onConfirm={revoke}/>
  </div>;
}

function SiteList({sites, loading, query, onQuery, selectedId, canAdd, onAdd, active}) {
  const visible = sites.filter(site => `${site.label} ${site.allowed_host}`.toLowerCase().includes(query.toLowerCase()));
  const groups = [['Coleta ativa', visible.filter(site => siteState(site)[1] === 'success')], ['Precisam de atenção', visible.filter(site => siteState(site)[1] !== 'success')]].filter(([, items]) => items.length);
  return <aside className="flex flex-col overflow-hidden rounded-xl bg-primary shadow-xs ring-1 ring-secondary lg:sticky lg:top-4" aria-label="Sites de medição">
    <header className="flex items-center justify-between gap-3 border-b border-secondary px-4 py-3">
      <div><div className="flex items-center gap-2"><h2 className="text-md font-semibold text-primary">Sites</h2><Badge type="pill-color" size="sm" color="gray">{sites.length}</Badge></div>
        {sites.length > 0 && <p className="text-xs text-tertiary">{active ? `${active} com coleta ativa` : 'Nenhum com coleta ativa'}</p>}</div>
      {canAdd && <CaduTooltip label="Conectar site"><Button size="sm" color="secondary" iconLeading={Plus} aria-label="Conectar site" onPress={onAdd}/></CaduTooltip>}
    </header>
    {sites.length > 5 && <div className="px-3 pt-3"><ReportsFieldInput size="sm" aria-label="Buscar site" placeholder="Buscar site" value={query} onChange={event => onQuery(event.target.value)}
      leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/></div>}
    <nav className="flex max-h-[calc(100vh-220px)] flex-col gap-3 overflow-y-auto p-2" aria-label="Lista de sites">
      {loading && <p role="status" className="px-2 py-3 text-sm text-tertiary">Carregando sites…</p>}
      {!loading && groups.map(([label, items]) => <div key={label} className="flex flex-col gap-0.5">
        {groups.length > 1 && <p className="px-2.5 pt-1 pb-1 text-xs font-semibold text-tertiary">{label}</p>}
        {items.map(site => {
          const [state, color] = siteState(site);
          const on = site.id === selectedId;
          return <a key={site.id} href={reportUrl('supertag', {}, site.id)} aria-current={on ? 'page' : undefined}
            className={`flex items-center gap-3 rounded-md px-2.5 py-2 outline-focus-ring focus-visible:outline-2 ${on ? 'bg-secondary ring-1 ring-secondary ring-inset' : 'hover:bg-primary_hover'}`}>
            <Favicon site={site}/>
            <span className="min-w-0 flex-1"><span className={`block truncate text-sm font-semibold ${on ? 'text-primary' : 'text-secondary'}`}>{site.allowed_host}</span>
              <span className="flex items-center gap-1 text-xs text-tertiary"><span className={`size-1.5 rounded-full ${({success: 'bg-fg-success-secondary', warning: 'bg-fg-warning-secondary', error: 'bg-fg-error-secondary', gray: 'bg-fg-quaternary'})[color]}`}/>{state}</span></span>
            <CaduTooltip label="Eventos nos últimos 30 dias"><span className="text-xs font-medium text-tertiary tabular-nums">{integer(site.events_30d || 0)}</span></CaduTooltip>
          </a>;
        })}
      </div>)}
      {!loading && sites.length > 0 && !visible.length && <p className="px-2 py-3 text-sm text-tertiary">Nenhum site corresponde à busca.</p>}
    </nav>
  </aside>;
}

function SiteHeader({site, hasEvents, flowsCount}) {
  const [state, color] = siteState(site);
  const last = site.last_event_at;
  return <section className="overflow-hidden rounded-xl bg-primary shadow-xs ring-1 ring-secondary">
    <div className="flex flex-wrap items-start justify-between gap-4 px-6 py-5">
      <div className="flex min-w-0 items-center gap-4"><Favicon site={site} size="lg"/>
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h2 className="truncate text-xl font-semibold text-primary">{site.allowed_host}</h2><BadgeWithDot type="pill-color" size="sm" color={color}>{state}</BadgeWithDot></div>
          <p className="text-sm text-tertiary">{site.label}</p></div>
      </div>
      <Button size="md" color="secondary" iconTrailing={ArrowUpRight} href={`https://${site.allowed_host}`} target="_blank" rel="noopener noreferrer">Visitar site</Button>
    </div>
    <dl className="grid gap-px border-t border-secondary bg-border-secondary sm:grid-cols-2 lg:grid-cols-4">
      {[['Eventos · 30 dias', integer(site.events_30d || 0), hasEvents ? 'Aceitos pelo coletor' : 'Nenhum evento recebido'], ['Último evento', last ? relativeTime(last) : 'Nenhum ainda', last ? longDate(last) : 'Aguardando a primeira visita'],
        ['Fluxos vinculados', flowsCount == null ? '—' : integer(flowsCount), 'Usam os dados deste site'], ['Instalação', hasEvents ? 'Verificada' : 'Pendente', hasEvents ? 'Confirmada pelos eventos' : 'Verifique o código no site']].map(([label, value, hint]) =>
        <div key={label} className="bg-primary px-6 py-4"><dt className="text-sm font-medium text-tertiary">{label}</dt><dd className="mt-1 text-lg font-semibold text-primary tabular-nums">{value}</dd><p className="text-xs text-tertiary">{hint}</p></div>)}
    </dl>
  </section>;
}

function checks({site, verify, hasEvents}) {
  let code = ['Verificação pendente', 'warning'];
  if (hasEvents) code = ['Confirmado pelos eventos', 'success'];
  else if (verify?.tag_in_html) code = ['Encontrado no site', 'success'];
  else if (verify && !verify.reachable) code = ['O site não respondeu', 'error'];
  else if (verify?.gtm_detected) code = ['GTM detectado · confirme no contêiner', 'warning'];
  else if (verify) code = ['Não encontrado no HTML', 'error'];
  return [
    {id: 'code', icon: Code01, title: 'Código instalado', hint: 'O código da Super Tag precisa estar em todas as páginas.', state: code, done: ['Instalado', 'Código implementado no site']},
    {id: 'receiving', icon: BarChart01, title: 'Recebendo eventos', hint: 'A primeira visita com o código instalado já envia eventos.', state: hasEvents ? [`${integer(site.events_30d)} eventos`, 'success'] : site.last_event_at ? [`Último ${relativeTime(site.last_event_at)}`, 'warning'] : ['Nenhum evento ainda', 'error'], done: ['Recebendo eventos', site.last_event_at ? `Último evento ${relativeTime(site.last_event_at)}` : 'Dados chegando normalmente']},
    {id: 'conversions', icon: Target04, title: 'Conversões', hint: 'Página de obrigado, formulário válido ou evento personalizado.', state: Number(site.conversions_30d) > 0 ? [`${integer(site.conversions_30d)} em 30 dias`, 'success'] : ['Nenhuma ainda', 'gray'], done: [Number(site.conversions_30d) > 0 ? `${integer(site.conversions_30d)} conversões` : 'Conversões', Number(site.conversions_30d) > 0 ? 'Nos últimos 30 dias' : 'Confira as regras em Configurações']},
  ];
}

function InstallStatus({site, hasEvents, verify, verifying, onVerify, onCopy, onGuide}) {
  const rows = checks({site, verify, hasEvents});
  if (hasEvents) return <section aria-label="Status da instalação" className="grid gap-px overflow-hidden rounded-xl bg-border-secondary shadow-xs ring-1 ring-secondary sm:grid-cols-3">
    {rows.map(row => <div key={row.id} className="flex items-center gap-3 bg-primary px-5 py-4">
      <CheckCircle size={20} aria-hidden="true" className="shrink-0 text-fg-success-primary"/>
      <div><p className="text-sm font-semibold text-primary">{row.done[0]}</p><p className="text-xs text-tertiary">{row.done[1]}</p></div>
    </div>)}
  </section>;
  return <section aria-label="Verificação da instalação" className="overflow-hidden rounded-xl bg-primary shadow-xs ring-1 ring-secondary">
    <header className="flex items-start gap-3 border-b border-secondary bg-warning-primary px-6 py-4">
      <AlertTriangle size={20} aria-hidden="true" className="mt-0.5 shrink-0 text-fg-warning-primary"/>
      <div><h3 className="text-md font-semibold text-primary">Coleta precisa de verificação</h3><p className="text-sm text-secondary">Nenhum evento chegou neste período. Isso não confirma falha na instalação.</p></div>
    </header>
    <ul>{rows.map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 border-b border-secondary px-6 py-3">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg ring-1 ring-secondary"><row.icon size={18} aria-hidden="true" className="text-fg-quaternary"/></span>
      <div className="min-w-48 flex-1"><p className="text-sm font-semibold text-primary">{row.title}</p><p className="text-xs text-tertiary">{row.hint}</p></div>
      <BadgeWithDot type="pill-color" size="sm" color={row.state[1]}>{row.state[0]}</BadgeWithDot>
    </li>)}</ul>
    <footer className="flex flex-wrap items-center gap-3 px-6 py-4">
      <Button size="md" color="primary" iconLeading={RefreshCw01} isDisabled={verifying} isLoading={verifying} onPress={onVerify}>Verificar instalação</Button>
      <Button size="md" color="secondary" iconLeading={Copy01} onPress={onCopy}>Copiar código</Button>
      <Button size="md" color="link-color" iconTrailing={ChevronRight} onPress={onGuide}>Ver como instalar</Button>
    </footer>
    {verify && !verify.tag_in_html && verify.reachable && <p className="border-t border-secondary px-6 py-3 text-sm text-tertiary">Instalada pelo Google Tag Manager, a tag não aparece no HTML. Abra o site no modo Visualizar do GTM para confirmar.</p>}
  </section>;
}

function InstallCard({site, onCopy, onDownload, onEmail}) {
  return <Card title="Código da Super Tag" description="Cole dentro de <head>, em todas as páginas. O código não contém credenciais.">
    <pre className="max-h-48 overflow-auto rounded-lg bg-secondary p-4 font-mono text-xs leading-5 break-all whitespace-pre-wrap text-secondary ring-1 ring-secondary ring-inset">{site.snippet}</pre>
    <div className="mt-4 flex flex-wrap gap-3">
      <Button size="md" color="primary" iconLeading={Copy01} onPress={onCopy}>Copiar código</Button>
      <Button size="md" color="secondary" iconLeading={Download01} onPress={onDownload}>Baixar</Button>
      <Button size="md" color="secondary" iconLeading={Send01} onPress={onEmail}>Enviar por e-mail</Button>
    </div>
  </Card>;
}

function InstallGuide() {
  const [method, setMethod] = useState('html');
  const code = text => <code className="rounded bg-secondary px-1 font-mono text-xs">{text}</code>;
  const steps = {
    html: [<>Abra o modelo (layout) que todas as páginas compartilham, normalmente o cabeçalho.</>, <>Cole o código dentro de {code('<head>')}, antes de {code('</head>')}. Não use o rodapé nem páginas avulsas.</>, <>Publique e abra uma página. A tag aparece na aba Rede do navegador como {code('supertag.js')}.</>],
    gtm: [<>Crie uma tag <strong>HTML personalizado</strong> e cole o código inteiro, com {code('<script>')}.</>, <>Acionamento: <strong>Initialization – All Pages</strong>, para não perder a primeira visita.</>, <>Consentimento: <strong>Nenhum consentimento adicional necessário</strong>. O aviso de cookies e a política são do site; para respeitar uma recusa, dispare {code("cadu:consent")} com {code('analytics: false')}.</>, <>Teste em <strong>Visualizar</strong> e publique com <strong>Enviar</strong>.</>],
    cms: [<><strong>WordPress:</strong> use um plugin de cabeçalho e rodapé (como o WPCode) e cole na área <strong>Header</strong>.</>, <><strong>Wix, Webflow, Shopify:</strong> em <strong>Código personalizado</strong>, aplique a todas as páginas, posição <strong>Head</strong>.</>, <>Se o site já usa GTM, prefira instalar pelo GTM.</>],
  };
  return <Card title="Onde instalar" description="Uma vez só, em todas as páginas do site.">
    <div className="rs-segmented rs-segmented--sm" role="group" aria-label="Forma de instalação">{[['html', 'No site'], ['gtm', 'Google Tag Manager'], ['cms', 'WordPress e outros']].map(([id, label]) =>
      <button key={id} type="button" aria-pressed={method === id} onClick={() => setMethod(id)}>{label}</button>)}</div>
    <ol className="mt-4 flex flex-col gap-3">{steps[method].map((step, index) => <li key={index} className="flex gap-3 text-sm text-secondary">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-primary text-xs font-semibold text-brand-secondary">{index + 1}</span><span className="pt-0.5">{step}</span></li>)}</ol>
    <div className="mt-4"><Callout tone="warning">Instale uma única vez. No site e também no GTM, as visitas são contadas em dobro.</Callout></div>
  </Card>;
}

function Audience({detail}) {
  const overall = detail.branding?.overall;
  const engaged = overall && Number(overall.sessions) ? Math.round(100 * Number(overall.engaged_sessions) / Number(overall.sessions)) : 0;
  const coverage = overall && Number(overall.sessions) ? Math.round(100 * Number(overall.measured_sessions) / Number(overall.sessions)) : 0;
  return <>
    {overall && Number(overall.sessions) > 0 && <Stats items={[['Visitantes', integer(overall.visitors), 'Identificadores desta instalação'], ['Sessões', integer(overall.sessions), `${integer(overall.closed_sessions)} encerradas · ${integer(detail.known_sessions || 0)} conhecidas`],
      ['Engajamento', `${engaged}%`, '2+ páginas, 10 s ativos ou conversão'], ['Tempo ativo médio', seconds(overall.avg_active_seconds), `${coverage}% das sessões medidas · ${decimal(overall.avg_pages || 0)} páginas/sessão`]]}/>}
    <Card flush title="Campanhas observadas" badge={<Badge type="pill-color" size="sm" color="gray">{detail.branding?.campaigns?.length || 0}</Badge>} description="Primeira UTM da sessão; os eventos seguintes ficam atribuídos a ela.">
      {detail.branding?.campaigns?.length ? <DataTable dense minWidth={720} rowKey={row => row.campaign_scope || 'sem'} rows={detail.branding.campaigns} columns={[
        ['Campanha', row => row.campaign_scope ? <span className="font-medium text-primary">{row.campaign_scope}</span> : <span className="text-tertiary">Sem campanha</span>],
        ['Visitantes', row => integer(row.visitors), 'right'], ['Sessões', row => integer(row.sessions), 'right'], ['Engajadas', row => integer(row.engaged_sessions), 'right'],
        ['Tempo ativo', row => seconds(row.avg_active_seconds), 'right'], ['Formulários', row => integer(row.forms), 'right'], ['WhatsApp', row => integer(row.whatsapp_clicks), 'right'], ['Conversões', row => integer(row.conversions), 'right']]}/>
        : <EmptyNote title="Nenhuma campanha identificada">Aparecem quando o tráfego chega com utm_id ou utm_campaign.</EmptyNote>}
    </Card>
    <Card flush title="Páginas" badge={<Badge type="pill-color" size="sm" color="gray">{detail.pages?.length || 0}</Badge>} description="Últimos 30 dias. Saída é a última página de uma sessão encerrada.">
      {detail.pages?.length ? <DataTable dense minWidth={780} rowKey={row => row.page_path} rows={detail.pages} columns={[
        ['Página', row => <span className="font-mono text-xs text-primary">{row.page_path}</span>], ['Visitas', row => integer(row.views), 'right'], ['Saídas', row => integer(row.exits), 'right'],
        ['Tempo ativo', row => <span title={`${integer(row.measured_visits)} visitas medidas`}>{seconds(row.avg_active_seconds)}</span>, 'right'], ['Formulários', row => integer(row.form_submissions), 'right'],
        ['Cliques', row => integer(row.clicks), 'right'], ['Conversões', row => integer(row.conversions), 'right'], ['Visibilidade', row => integer(row.visibility_events), 'right'], ['Rolagem', row => integer(row.scroll_events), 'right']]}/>
        : <EmptyNote title="Nenhuma página ainda"/>}
    </Card>
  </>;
}

function Activity({detail}) {
  const events = [...(detail.summary || [])].sort((a, b) => Number(b.total) - Number(a.total));
  const cell = item => item.x != null ? `${(Number(item.x) / 10).toFixed(1)}–${Math.min(100, (Number(item.x) + 49) / 10).toFixed(1)}% × ${(Number(item.y) / 10).toFixed(1)}–${Math.min(100, (Number(item.y) + 49) / 10).toFixed(1)}%`
    : item.ratio != null ? `${item.ratio}% visível` : item.depth != null ? `${item.depth}% rolagem` : '—';
  return <>
    <Card flush title="Eventos · 30 dias" description="Tipos de evento recebidos pela Super Tag.">
      {events.length ? <ul>{events.map(row => <li key={row.event_kind} className="flex items-center justify-between gap-3 border-b border-secondary px-6 py-2.5 last:border-b-0">
        <div className="min-w-0"><p className="truncate text-sm font-medium text-primary">{EVENT_LABELS[row.event_kind] || row.event_kind}</p><p className="font-mono text-xs text-tertiary">{row.event_kind}</p></div>
        <span className="text-sm font-semibold text-primary tabular-nums">{integer(row.total)}</span>
      </li>)}</ul> : <EmptyNote title="Sem eventos"/>}
    </Card>
    <Card flush title="Sessões recentes" badge={<Badge type="pill-color" size="sm" color="gray">{detail.sessions?.length || 0}</Badge>} description="Até 100 sessões: campanha, páginas percorridas e saída.">
      {detail.sessions?.length ? <DataTable minWidth={900} rowKey={row => row.session_id} rows={detail.sessions} columns={[
        ['Visitante', row => row.known_name ? <><p className="font-medium text-primary">{row.known_name}</p><p className="text-xs text-tertiary">Conhecido</p></> : <span className="text-tertiary">Anônimo</span>],
        ['Campanha', row => row.campaign || <span className="text-tertiary">Sem campanha</span>], ['Início', row => new Date(row.started_at).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'})],
        ['Navegação', row => {const pages = (row.journey || []).filter(event => event.kind === 'page_view' || event.kind === 'conversion'); return pages.length ? <span className="font-mono text-xs">{pages.map(event => event.page).join(' → ')}</span> : '—';}],
        ['Saída', row => <span className="font-mono text-xs">{row.exit_page || '—'}</span>]]}/>
        : <EmptyNote title="Nenhuma sessão ainda"/>}
    </Card>
    <Card flush title="Mapas de interação" badge={<Badge type="pill-color" size="sm" color="gray">{detail.heatmap?.length || 0}</Badge>}
      description="Cliques agrupados em grade de 5% da tela. Para visibilidade, marque elementos com data-cadu-track e data-cadu-element. Textos da página não são lidos.">
      {detail.heatmap?.length ? <DataTable minWidth={640} rowKey={(row, index) => `${row.event_kind}:${row.element_id}:${index}`} rows={detail.heatmap.slice(0, 30)} columns={[
        ['Tipo', row => EVENT_LABELS[row.event_kind] || row.event_kind], ['Elemento', row => <span className="font-mono text-xs">{row.element_id || '—'}</span>], ['Posição', cell], ['Ocorrências', row => integer(row.total), 'right']]}/>
        : <EmptyNote title="Sem agregados ainda"/>}
    </Card>
    <Card flush title="Retorno por semana" description="Semana da primeira visita observada e quantos voltaram em até 7 dias.">
      {detail.branding?.cohorts?.length ? <DataTable minWidth={640} rowKey={row => `${row.campaign_scope}:${row.cohort_week}`} rows={detail.branding.cohorts} columns={[
        ['Semana', row => shortDate(row.cohort_week)], ['Campanha', row => row.campaign_scope || <span className="text-tertiary">Sem campanha</span>], ['Visitantes', row => integer(row.visitors), 'right'],
        ['Retornaram', row => integer(row.returned_7d), 'right'], ['Taxa', row => Number(row.visitors) ? `${Math.round(100 * Number(row.returned_7d) / Number(row.visitors))}%` : '—', 'right']]}/>
        : <EmptyNote title="Ainda sem semanas completas">Aparecem após sete dias de visitas.</EmptyNote>}
    </Card>
  </>;
}

function LinkedFlows({linked, site}) {
  return <Card flush title="Fluxos vinculados" badge={<Badge type="pill-color" size="sm" color="gray">{linked.length}</Badge>} description="Fluxos que usam os dados deste site."
    actions={<Button size="md" color="secondary" iconLeading={Plus} href={reportUrl('flow', {site_host: site.allowed_host, flow_view: 'create'})}>Criar fluxo</Button>}>
    {linked.length ? <DataTable minWidth={560} rowKey={row => row.id} rows={linked} columns={[
      ['Fluxo', row => <span className="flex items-center gap-2 font-medium text-primary"><GitBranch01 size={16} aria-hidden="true" className="text-fg-quaternary"/>{row.name}</span>],
      ['Status', row => <BadgeWithDot type="pill-color" size="sm" color={row.status === 'published' ? 'success' : 'gray'}>{row.status === 'published' ? 'Publicado' : 'Rascunho'}</BadgeWithDot>],
      ['Atualizado', row => longDate(row.updated_at)],
      ['', row => <div className="text-right"><Button size="sm" color="secondary" iconTrailing={ArrowUpRight} href={reportUrl('flow', {flow_id: row.id, flow_view: row.status === 'published' ? 'monitor' : 'edit'})}>Abrir</Button></div>]]}/>
      : <EmptyNote title="Nenhum fluxo usa este site">Crie um fluxo para medir a jornada das campanhas neste site.</EmptyNote>}
  </Card>;
}

function Settings({data, site, busy, canEdit, onUpdate, onRevoke}) {
  const config = site.config || {};
  const disabled = busy || !canEdit;
  return <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
    <div className="flex flex-col gap-6">
    <Card title="Coleta" description="Valem para todas as páginas deste site. Mudanças entram na próxima visita.">
      <div className="flex flex-col gap-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <ReportsNativeSelect label="Duração do identificador" hint="Tempo que o mesmo visitante é reconhecido." disabled={disabled} value={config.audience_days || 365} onChange={event => onUpdate({audience_days: Number(event.target.value)})}>
            {AUDIENCE_DAYS.map(([days, name]) => <option key={days} value={days}>{name}</option>)}</ReportsNativeSelect>
          <ReportsNativeSelect label="Retenção dos eventos" hint="Por quanto tempo os eventos ficam guardados." disabled={disabled} value={config.retention_days || 365} onChange={event => onUpdate({retention_days: Number(event.target.value)})}>
            {RETENTION_DAYS.map(([days, name]) => <option key={days} value={days}>{name}</option>)}</ReportsNativeSelect>
        </div>
        <label className="flex cursor-pointer items-start gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
          <input type="checkbox" className="mt-0.5 size-4 accent-brand-600" disabled={disabled} checked={config.visibility_enabled !== false} onChange={event => onUpdate({visibility_enabled: event.target.checked})}/>
          <span><span className="block text-sm font-semibold text-primary">Medir visibilidade de elementos marcados</span><span className="block text-sm text-tertiary">Registra quando um elemento com data-cadu-track aparece na tela.</span></span>
        </label>
        <p className="text-sm text-tertiary">O aviso de cookies e a política de privacidade são do site. A Super Tag coleta desde a primeira visita e para só com uma recusa explícita: {'window.CaduSuperTag.setConsent(false)'} ou o evento cadu:consent com analytics: false.</p>
      </div>
    </Card>
    <ConversionRules site={site} disabled={disabled} onUpdate={onUpdate}/>
    </div>
    <div className="flex flex-col gap-6">
      <LeadCapture site={site} disabled={disabled} onUpdate={onUpdate}/>
      <Card title="Associar visita a um usuário" description="Para login ou formulários feitos em JavaScript, que não disparam o envio comum.">
        <pre className="rounded-lg bg-secondary p-4 font-mono text-xs leading-5 break-all whitespace-pre-wrap text-secondary ring-1 ring-secondary ring-inset">{'window.CaduSuperTag?.identify({ name: usuario.nome, email: usuario.email });'}</pre>
        <p className="mt-3 text-sm text-tertiary">Aceita também telefone. O contato fica cifrado, aparece em Quem converteu e expira com a retenção.</p>
      </Card>
      <Card title="Acesso ao monitoramento" description="Quem pode ver os dados deste site na plataforma." actions={<ReportsRelationships data={data} kind="site" id={site.id} name={site.label}/>}/>
      {canEdit && !site.revoked_at && <Card title="Revogar instalação" description="Interrompe a coleta neste domínio. Os dados recebidos ficam no Reports.">
        <Button size="md" color="secondary-destructive" isDisabled={busy} onPress={onRevoke}>Revogar instalação</Button>
      </Card>}
    </div>
  </div>;
}

const RULE_TYPES = [['path:exact', 'Página exata'], ['path:prefix', 'Página que começa com'], ['valid_form', 'Formulário válido'], ['event_name', 'Evento personalizado']];
const ruleLabel = rule => rule.type === 'path' ? `${rule.match === 'exact' ? 'Página' : rule.match === 'segment' ? 'Caminho com o trecho' : 'Página que começa com'} ${rule.value}`
  : rule.type === 'valid_form' ? `Formulário válido${rule.form_id ? ` (${rule.form_id})` : ''}` : `Evento ${rule.value}`;

/** What counts as a conversion on this site. Rules are applied when the events arrive, so every screen agrees. */
function ConversionRules({site, disabled, onUpdate}) {
  const [state, setState] = useState(null);
  const [error, setError] = useState('');
  const [kind, setKind] = useState('path:exact');
  const [value, setValue] = useState('');
  const [name, setName] = useState('');
  useEffect(() => {
    let active = true; setError('');
    json(`${API}/sites/${site.id}/conversion-rules`).then(body => {if (active) setState(body);}).catch(failure => {if (active) setError(failure.message);});
    return () => {active = false;};
  }, [site.id, site.config_version]);
  const rules = state?.rules || [];
  const save = next => onUpdate({conversion_rules: next});
  const add = () => {
    const [type, match] = kind.split(':');
    const rule = type === 'path' ? {type, match, value: value.trim()} : type === 'valid_form' ? {type, ...(value.trim() ? {form_id: value.trim()} : {})} : {type, value: value.trim()};
    if (name.trim()) rule.name = name.trim();
    save([...rules, rule]); setValue(''); setName('');
  };
  const needsValue = kind !== 'valid_form';
  return <Card title="Conversões" description="O que conta como conversão neste site. Vale para os eventos que chegarem a partir de agora.">
    {error && <Alert>{error}</Alert>}
    {!state && !error && <p role="status" className="text-sm text-tertiary">Carregando regras…</p>}
    {state && <div className="flex flex-col gap-4">
      {!rules.length && <label className="flex cursor-pointer items-start gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
        <input type="checkbox" className="mt-0.5 size-4 accent-brand-600" disabled={disabled} checked={state.conversion_defaults} onChange={event => onUpdate({conversion_defaults: event.target.checked})}/>
        <span><span className="block text-sm font-semibold text-primary">Página de obrigado automática</span>
          <span className="block text-sm text-tertiary">Sem regras salvas, páginas cujo caminho tem um trecho começando por obrigad, thank, sucesso ou confirmac contam como conversão. Ao salvar uma regra, só as regras salvas valem.</span></span>
      </label>}
      {rules.length > 0 && <ul className="flex flex-col divide-y divide-secondary rounded-lg ring-1 ring-secondary ring-inset">{rules.map((rule, index) =>
        <li key={`${rule.type}${rule.value || rule.form_id || ''}${index}`} className="flex items-center justify-between gap-3 px-4 py-2.5">
          <span className="min-w-0"><span className="block truncate text-sm font-medium text-primary">{ruleLabel(rule)}</span><span className="block font-mono text-xs text-tertiary">{rule.name || (rule.type === 'event_name' ? rule.value : rule.type === 'valid_form' ? 'formulario_enviado' : 'pagina_obrigado')}</span></span>
          {!disabled && <CaduTooltip label="Remover regra"><Button size="sm" color="tertiary" iconLeading={Trash01} aria-label={`Remover ${ruleLabel(rule)}`} onPress={() => save(rules.filter((_, position) => position !== index))}/></CaduTooltip>}
        </li>)}</ul>}
      {state.suggestions?.length > 0 && <div className="flex flex-col gap-2">
        <p className="text-sm font-semibold text-primary">Sugestões</p>
        <p className="text-xs text-tertiary">Páginas visitadas que parecem de obrigado. Aceite para contar só elas.</p>
        {state.suggestions.map(item => <div key={item.path} className="flex items-center justify-between gap-3 rounded-lg px-4 py-2 ring-1 ring-secondary ring-inset">
          <span className="min-w-0"><span className="block truncate font-mono text-xs text-primary">{item.path}</span><span className="text-xs text-tertiary">{integer(item.views)} visitas · 90 dias</span></span>
          {!disabled && <Button size="sm" color="secondary" iconLeading={Plus} onPress={() => save([...rules, item.rule])}>Usar</Button>}
        </div>)}
      </div>}
      {!disabled && <div className="flex flex-col gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
        <div className="grid gap-3 sm:grid-cols-2">
          <ReportsNativeSelect label="Tipo de regra" value={kind} onChange={event => setKind(event.target.value)}>{RULE_TYPES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</ReportsNativeSelect>
          <ReportsFieldInput label={kind.startsWith('path') ? 'Caminho' : kind === 'valid_form' ? 'data-cadu-form (opcional)' : 'Nome do evento'} value={value} onChange={event => setValue(event.target.value)}
            placeholder={kind.startsWith('path') ? '/obrigado' : kind === 'valid_form' ? 'contato' : 'lead_enviado'}/>
        </div>
        <ReportsFieldInput label="Nome da conversão (opcional)" value={name} onChange={event => setName(event.target.value)} placeholder="pagina_obrigado"/>
        <span><Button size="sm" color="secondary" iconLeading={Plus} isDisabled={needsValue && !value.trim()} onPress={add}>Adicionar regra</Button></span>
      </div>}
    </div>}
  </Card>;
}

/** Who converted: which contact data a valid form sends, and when the lead counts as confirmed. */
function LeadCapture({site, disabled, onUpdate}) {
  const capture = site.config?.form_capture || {};
  const [fields, setFields] = useState((capture.fields || []).join(', '));
  useEffect(() => {setFields((site.config?.form_capture?.fields || []).join(', '));}, [site.id, site.config_version]);
  const list = fields.split(',').map(item => item.trim()).filter(Boolean);
  return <Card title="Quem converteu" description="Contatos de formulários válidos, cifrados e com a mesma retenção dos eventos.">
    <div className="flex flex-col gap-4">
      <label className="flex cursor-pointer items-start gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
        <input type="checkbox" className="mt-0.5 size-4 accent-brand-600" disabled={disabled} checked={capture.enabled !== false} onChange={event => onUpdate({form_capture: {enabled: event.target.checked}})}/>
        <span><span className="block text-sm font-semibold text-primary">Capturar nome, e-mail e telefone</span>
          <span className="block text-sm text-tertiary">Detectados pelo tipo e pelo nome do campo. Senha, cartão, CPF/CNPJ/RG, tokens, campos ocultos e armadilhas anti-robô nunca são lidos; use data-cadu-ignore para excluir um campo.</span></span>
      </label>
      <ReportsNativeSelect label="Lead confirmado quando" disabled={disabled} value={capture.confirm || 'conversion'} onChange={event => onUpdate({form_capture: {confirm: event.target.value}})}
        hint="Sem confirmação, o lead aparece como pendente.">
        <option value="conversion">Chega a conversão da mesma sessão (até 30 min)</option><option value="valid_submit">O formulário é enviado válido</option></ReportsNativeSelect>
      <div className="flex flex-col gap-2">
        <ReportsFieldInput label="Campos extras (atributo name)" disabled={disabled} value={fields} onChange={event => setFields(event.target.value)} placeholder="empresa, interesse, cidade"/>
        <p className="text-xs text-tertiary">Até 20 campos, separados por vírgula. Campos sensíveis são recusados.</p>
        {!disabled && <span><Button size="sm" color="secondary" isDisabled={list.join(',') === (capture.fields || []).join(',')} onPress={() => onUpdate({form_capture: {fields: list}})}>Salvar campos</Button></span>}
      </div>
    </div>
  </Card>;
}

function InstallDrawer({open, data, onClose, onCreated}) {
  const [host, setHost] = useState('');
  const [label, setLabel] = useState('Site principal');
  const [check, setCheck] = useState(null);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {if (open) {setHost(''); setLabel('Site principal'); setCheck(null); setError('');}}, [open]);
  const verify = async () => {
    if (!host.trim()) return;
    setChecking(true); setCheck(null); setError('');
    try {const result = await json(`${API}/site-check?url=${encodeURIComponent(host.trim())}`); setCheck(result); if (result.title && label === 'Site principal') setLabel(result.title.slice(0, 120));}
    catch (failure) {setCheck({error: failure.message});} finally {setChecking(false);}
  };
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const checkedHost = new URL(host.includes('://') ? host : `https://${host}`).host;
      const result = await json(`${API}/sites`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({label, allowed_host: checkedHost})});
      if (check?.favicon) faviconCache.set(checkedHost, check.favicon);
      await onCreated(result.site);
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  return <ReportsDrawer open={open} onOpenChange={value => {if (!value) onClose();}} title="Conectar site" context={data.client.client_name} description="Informe o endereço do site. Conferimos se ele responde antes de gerar o código.">
    <form className="untitled-scope flex flex-col gap-5" onSubmit={submit}>
      {error && <Alert>{error}</Alert>}
      <div className="flex items-end gap-3">
        <div className="flex-1"><ReportsFieldInput label="Endereço do site" required type="url" value={host} onChange={event => {setHost(event.target.value); setCheck(null);}} placeholder="https://www.exemplo.com.br"/></div>
        <Button type="button" size="md" color="secondary" isDisabled={!host.trim() || checking} isLoading={checking} onPress={verify}>Verificar</Button>
      </div>
      {check && (check.error ? <Callout tone="error" title="Não foi possível acessar o site">{check.error}</Callout>
        : <div className="flex items-center gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
          <span className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg ring-1 ring-secondary">{check.favicon ? <img src={check.favicon} alt="" className="size-6"/> : <span className="text-tertiary">◎</span>}</span>
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-primary">{check.title || check.host || 'Site encontrado'}</p><p className="text-xs text-tertiary">{check.host}{check.status ? ` · HTTP ${check.status}` : ''}</p></div>
          <BadgeWithDot type="pill-color" size="sm" color="success">Respondeu</BadgeWithDot>
        </div>)}
      <ReportsFieldInput label="Nome desta instalação" required maxLength={120} value={label} onChange={event => setLabel(event.target.value)} placeholder={check?.title || 'Site principal'}/>
      <p className="text-sm text-tertiary">A coleta começa na primeira visita. O aviso de cookies e a política de privacidade continuam sendo do site.</p>
      <DrawerActions onCancel={onClose} busy={busy} label="Criar instalação" disabled={!check || Boolean(check.error)}/>
    </form>
  </ReportsDrawer>;
}
