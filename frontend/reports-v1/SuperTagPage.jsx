import React, {useEffect, useState} from 'react';
import {AlertTriangle, ArrowUpRight, BarChart01, CheckCircle, ChevronRight, Code01, Copy01, Download01, GitBranch01, Plus, RefreshCw01, Send01, Target04, Trash01} from '@untitledui/icons';
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
import {useReportsContext} from './shell/context.js';
import {NewSiteWizard} from './NewSiteWizard.jsx';

const API = '/connect/api/v2/reports/supertag';
const EVENT_LABELS = {page_view: 'Visualização de página', page_leave: 'Saída de página', click: 'Clique', whatsapp_click: 'Clique no WhatsApp', form_submit: 'Envio de formulário',
  visibility: 'Elemento visível', scroll_depth: 'Rolagem', custom_event: 'Evento personalizado', conversion: 'Conversão', heartbeat: 'Tempo ativo',
  outbound_click: 'Link para outro site', file_download: 'Download', contact_click: 'Clique em telefone ou e-mail', video: 'Vídeo'};
/** Enhanced measurement, like a GA4 data stream: detected on their own, one switch each, all on by default. */
const MEASUREMENTS = [
  ['page_changes', 'Troca de página sem recarregar', 'Conta uma nova página quando o endereço muda sem recarregar (sites em React, Vue e similares).'],
  ['scroll', 'Rolagem', 'Até onde cada página foi rolada: 25%, 50%, 75% e 100%.'],
  ['clicks', 'Mapa de cliques', 'Onde as pessoas clicam em links e botões. O texto da página não é lido.'],
  ['outbound', 'Links para outros sites', 'Cliques em links que levam a outro site. Só o domínio de destino é registrado.'],
  ['contacts', 'WhatsApp, telefone e e-mail', 'Cliques em links de contato. O número e o endereço não são enviados.'],
  ['downloads', 'Downloads', 'Cliques em links de PDF, planilhas, documentos, ZIP e outros arquivos.'],
  ['forms', 'Envio de formulário', 'Envios válidos e inválidos. Desligado, formulários deixam de contar como conversão e de mandar contatos para Quem converteu.'],
  ['video', 'Vídeos', 'Início, 25%, 50%, 75% e fim dos vídeos do próprio site (tag <video>). Vídeos incorporados do YouTube ou Vimeo não entram.'],
];
const AUDIENCE_DAYS = [[30, '30 dias'], [60, '60 dias'], [90, '90 dias'], [180, '6 meses'], [365, '1 ano'], [395, '13 meses (máximo do navegador)']];
const RETENTION_DAYS = [[30, '30 dias'], [60, '60 dias'], [90, '90 dias'], [180, '6 meses'], [365, '1 ano'], [730, '2 anos'], [1095, '3 anos'], [1825, '5 anos']];
const TAB_PARAM = 'site_tab';
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

/** Super Tag: the site picked in the header, how it is installed and what it measures. */
export function SuperTagPage({data}) {
  const {scope} = useReportsContext();
  const selectedId = scope.site;
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTabState] = useState(() => new URLSearchParams(location.search).get(TAB_PARAM) || 'overview');
  const [method, setMethod] = useState('html');
  const [flows, setFlows] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [installOpen, setInstallOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [verify, setVerify] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const canEdit = data.client.role !== 'viewer';
  /** Each tab has its own address (?site_tab=), so a link or a reload opens the same area. */
  const setTab = value => {
    setTabState(value);
    const url = new URL(location.href);
    if (value && value !== 'overview') url.searchParams.set(TAB_PARAM, value); else url.searchParams.delete(TAB_PARAM);
    history.replaceState(history.state, '', `${url.pathname}${url.search}${url.hash}`);
  };

  const load = async () => {
    const value = await json(`${API}/sites`);
    setSites(value.sites || []);
  };
  // The site now lives in the header (?scope_site=); old /supertag/sites/<id> addresses become the plain page.
  useEffect(() => {
    if (!/\/supertag\/sites\//.test(location.pathname)) return;
    history.replaceState(history.state, '', `${reportUrl('supertag')}${location.search}${location.hash}`);
  }, []);
  useEffect(() => {
    let active = true;
    setSites([]); setLoading(true);
    json(`${API}/sites`).then(value => {
      if (active) setSites(value.sites || []);
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
  /** Resolves to true when the action worked; the server's message (never a bare HTTP code) goes to the alert. */
  const run = async action => {setBusy(true); setError(''); try {await action(); return true;} catch (failure) {setError(failure.message); return false;} finally {setBusy(false);}};
  const update = changes => run(async () => {
    await json(`${API}/sites/${selectedId}`, {method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify(changes)});
    await load(); setDetail(await json(`${API}/sites/${selectedId}/events`));
  });
  const revoke = () => run(async () => {
    await json(`${API}/sites/${selectedId}/revoke`, {method: 'POST', headers: {'X-CSRF-Token': data.csrf}, body: JSON.stringify({})});
    setRevokeOpen(false); location.assign(reportUrl('supertag'));
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
  const code = site => (method === 'gtm' && site.snippet_gtm) || site.snippet;
  const download = () => {
    const url = URL.createObjectURL(new Blob([code(selected)], {type: 'text/plain;charset=utf-8'}));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `cadu-supertag-${method === 'gtm' ? 'gtm-' : ''}${selected.allowed_host}.txt`; anchor.click(); URL.revokeObjectURL(url);
  };
  const email = () => {
    const subject = encodeURIComponent(`Instalação da Super Tag no site ${selected.allowed_host}`);
    const where = method === 'gtm'
      ? 'No Google Tag Manager, crie uma tag do tipo HTML personalizado com o código abaixo, acionada em All Pages, e publique:'
      : 'Cole o código abaixo dentro de <head>, no modelo usado por todas as páginas do site:';
    const body = encodeURIComponent(`Olá!\n\nPor favor, instale a Super Tag no site ${selected.allowed_host}.\n\n${where}\n\n${code(selected)}\n\nInstale uma única vez (no site ou no GTM, não nos dois). Depois de publicar, avise para conferirmos a chegada dos primeiros eventos.\n`);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };
  const rulesCount = (selected?.config?.conversion_rules || []).length;
  const tabs = [{id: 'overview', label: 'Visão geral'}, ...(hasEvents ? [{id: 'activity', label: 'Atividade'}] : []), {id: 'measurement', label: 'Medição'},
    {id: 'conversions', label: 'Conversões', count: rulesCount || undefined}, {id: 'identity', label: 'Identificação'}, {id: 'install', label: 'Instalação'},
    {id: 'flows', label: 'Fluxos', count: linked.length || undefined}, {id: 'settings', label: 'Configurações'}];
  const current = tabs.some(item => item.id === tab) ? tab : 'overview';
  const disabled = busy || !canEdit;

  return <div className="untitled-scope">
    <div className="flex min-w-0 flex-col gap-6">
      {error && <Alert>{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}
      {!selected && !loading && <Card><EmptyNote title={sites.length ? 'Escolha um site' : canEdit ? 'Conecte seu primeiro site' : 'Nenhum site conectado'}>
        {sites.length ? 'Escolha o site no seletor do cabeçalho para ver instalação, eventos e fluxos.' : canEdit ? 'Instale a Super Tag para acompanhar visitas, eventos e conversões.' : 'Os sites autorizados para este cliente aparecem aqui.'}
        {!sites.length && canEdit && <span className="mt-4 block"><Button size="md" color="primary" iconLeading={Plus} onPress={() => setInstallOpen(true)}>Conectar site</Button>{' '}<Button size="md" color="secondary" onPress={() => setWizardOpen(true)}>Assistente: site, fluxo e Super Tag</Button></span>}
      </EmptyNote></Card>}
      {selected && <>
        <SiteHeader site={selected} hasEvents={hasEvents} flowsCount={detailLoading ? null : linked.length} onAdd={canEdit ? () => setInstallOpen(true) : null} onWizard={canEdit ? () => setWizardOpen(true) : null}/>
        <ReportsTabs label="Áreas do site" value={current} onChange={setTab} items={tabs}/>
        {detailLoading && <p role="status" className="text-sm text-tertiary">Carregando dados do site…</p>}
        {current === 'overview' && <>
          <InstallStatus site={selected} hasEvents={hasEvents} verify={verify} verifying={verifying} onVerify={verifyInstall} onCopy={() => copy(code(selected))} onGuide={() => setTab('install')}/>
          {hasEvents && detail && <Audience detail={detail}/>}
        </>}
        {current === 'activity' && detail && <Activity detail={detail}/>}
        {current === 'measurement' && <Measurement site={selected} disabled={disabled} onUpdate={update} onInstall={() => setTab('install')}/>}
        {current === 'conversions' && <div className="grid items-start gap-6 xl:grid-cols-2">
          <ConversionRules site={selected} disabled={disabled} onUpdate={update}/>
          <LeadCapture site={selected} disabled={disabled} onUpdate={update}/>
        </div>}
        {current === 'identity' && <Identity/>}
        {current === 'install' && <div className="grid items-start gap-6 xl:grid-cols-2">
          <div className="flex flex-col gap-6">
            <InstallCard site={selected} method={method} onMethod={setMethod} code={code(selected)} onCopy={() => copy(code(selected))} onDownload={download} onEmail={email}/>
            <VerifyCard hasEvents={hasEvents} verify={verify} verifying={verifying} onVerify={verifyInstall}/>
          </div>
          <InstallGuide method={method}/>
        </div>}
        {current === 'flows' && <LinkedFlows linked={linked} site={selected}/>}
        {current === 'settings' && <Settings data={data} site={selected} busy={busy} canEdit={canEdit} onUpdate={update} onRevoke={() => setRevokeOpen(true)}/>}
      </>}
    </div>
    {wizardOpen && <NewSiteWizard data={data} onClose={() => setWizardOpen(false)}/>}
    <InstallDrawer open={installOpen} data={data} onClose={() => setInstallOpen(false)} onCreated={site => location.assign(reportUrl('supertag', {scope_site: site.id}))}/>
    <ReportsConfirmDialog open={revokeOpen} title="Revogar Super Tag" description="A coleta neste domínio será interrompida. Os dados já recebidos permanecem no Reports." confirmLabel="Revogar instalação" busy={busy} onCancel={() => setRevokeOpen(false)} onConfirm={revoke}/>
  </div>;
}

function SiteHeader({site, hasEvents, flowsCount, onAdd, onWizard}) {
  const [state, color] = siteState(site);
  const last = site.last_event_at;
  return <section className="overflow-hidden rounded-xl bg-primary shadow-xs ring-1 ring-secondary">
    <div className="flex flex-wrap items-start justify-between gap-4 px-6 py-5">
      <div className="flex min-w-0 items-center gap-4"><Favicon site={site} size="lg"/>
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h2 className="truncate text-xl font-semibold text-primary">{site.allowed_host}</h2><BadgeWithDot type="pill-color" size="sm" color={color}>{state}</BadgeWithDot></div>
          <p className="text-sm text-tertiary">{site.label}</p></div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button size="md" color="secondary" iconTrailing={ArrowUpRight} href={`https://${site.allowed_host}`} target="_blank" rel="noopener noreferrer">Visitar site</Button>
        {onAdd && <Button size="md" color="secondary" iconLeading={Plus} onPress={onAdd}>Conectar site</Button>}
        {onWizard && <Button size="md" color="secondary" onPress={onWizard}>Assistente completo</Button>}
      </div>
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
  else if (verify?.gtm_detected) code = ['Site usa GTM · confira no contêiner', 'warning'];
  else if (verify) code = ['Não encontrado no HTML', 'error'];
  return [
    {id: 'code', icon: Code01, title: 'Código instalado', hint: 'O código precisa estar em todas as páginas do site, direto ou pelo Google Tag Manager.', state: code, done: ['Instalado', 'Código implementado no site']},
    {id: 'receiving', icon: BarChart01, title: 'Recebendo eventos', hint: 'A primeira visita depois da instalação já envia eventos.', state: hasEvents ? [`${integer(site.events_30d)} eventos`, 'success'] : site.last_event_at ? [`Último ${relativeTime(site.last_event_at)}`, 'warning'] : ['Nenhum evento ainda', 'error'], done: ['Recebendo eventos', site.last_event_at ? `Último evento ${relativeTime(site.last_event_at)}` : 'Dados chegando normalmente']},
    {id: 'conversions', icon: Target04, title: 'Conversões', hint: 'Página de obrigado, formulário válido ou evento próprio do site.', state: Number(site.conversions_30d) > 0 ? [`${integer(site.conversions_30d)} em 30 dias`, 'success'] : ['Nenhuma ainda', 'gray'], done: [Number(site.conversions_30d) > 0 ? `${integer(site.conversions_30d)} conversões` : 'Conversões', Number(site.conversions_30d) > 0 ? 'Nos últimos 30 dias' : 'Confira as regras na aba Conversões']},
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
      <div><h3 className="text-md font-semibold text-primary">Coleta precisa de verificação</h3><p className="text-sm text-secondary">Nenhum evento chegou nos últimos 30 dias. Isso, sozinho, não quer dizer que a instalação falhou: o site pode só não ter tido visitas.</p></div>
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
    {verify && !verify.tag_in_html && verify.reachable && <p className="border-t border-secondary px-6 py-3 text-sm text-tertiary">{GTM_VERIFY_NOTE}</p>}
  </section>;
}

const GTM_VERIFY_NOTE = 'Se a instalação foi pelo Google Tag Manager, o código não aparece no HTML da página. Confirme no modo Visualizar do GTM ou aguarde a primeira visita.';

/** The same check as the overview, next to the code: reads the home page HTML and the events already received. */
function VerifyCard({hasEvents, verify, verifying, onVerify}) {
  let result = null;
  if (hasEvents) result = <Callout tone="success">Eventos chegando: a instalação está funcionando.</Callout>;
  else if (verify?.tag_in_html) result = <Callout tone="success">Código encontrado na página inicial. Os eventos aparecem depois da primeira visita.</Callout>;
  else if (verify && !verify.reachable) result = <Callout tone="error">O site não respondeu{verify.status ? ` (HTTP ${verify.status})` : ''}. Confira se ele está no ar e tente de novo.</Callout>;
  else if (verify) result = <Callout tone="warning">{verify.gtm_detected ? GTM_VERIFY_NOTE : 'O código não foi encontrado no HTML da página inicial. Confira se ele foi publicado em todas as páginas.'}</Callout>;
  return <Card title="Verificar instalação" description="Procura o código na página inicial do site e confere se já chegaram eventos.">
    <div className="flex flex-col gap-4">
      {result}
      <span><Button size="md" color="secondary" iconLeading={RefreshCw01} isDisabled={verifying} isLoading={verifying} onPress={onVerify}>Verificar instalação</Button></span>
    </div>
  </Card>;
}

const METHODS = [['html', 'Direto no site'], ['gtm', 'Google Tag Manager']];

function InstallCard({method, onMethod, code, onCopy, onDownload, onEmail}) {
  const gtm = method === 'gtm';
  return <Card title="Código da Super Tag" description={gtm ? 'Para colar numa tag de HTML personalizado do Google Tag Manager. Carrega o mesmo script da instalação direta.'
    : 'Cole dentro de <head>, no modelo usado por todas as páginas. O que medir se ajusta na aba Medição, sem mexer no site.'}>
    <div className="rs-segmented rs-segmented--sm" role="group" aria-label="Método de instalação">{METHODS.map(([id, label]) =>
      <button key={id} type="button" aria-pressed={method === id} onClick={() => onMethod(id)}>{label}</button>)}</div>
    <pre className="mt-4 max-h-64 overflow-auto rounded-lg bg-secondary p-4 font-mono text-xs leading-5 break-all whitespace-pre-wrap text-secondary ring-1 ring-secondary ring-inset">{code}</pre>
    <div className="mt-4 flex flex-wrap gap-3">
      <Button size="md" color="primary" iconLeading={Copy01} onPress={onCopy}>Copiar código</Button>
      <Button size="md" color="secondary" iconLeading={Download01} onPress={onDownload}>Baixar</Button>
      <Button size="md" color="secondary" iconLeading={Send01} onPress={onEmail}>Enviar por e-mail</Button>
    </div>
  </Card>;
}

function InstallGuide({method}) {
  const code = text => <code className="rounded bg-secondary px-1 font-mono text-xs">{text}</code>;
  const steps = method === 'gtm' ? [
    <>No Google Tag Manager, abra <strong>Tags → Nova → Configuração da tag → HTML personalizado</strong>.</>,
    <>Cole o código para GTM inteiro, com os comentários e o {code('<script>')}.</>,
    <>Em <strong>Acionamento</strong>, escolha <strong>All Pages</strong> (todas as páginas). Não precisa de acionador <strong>History Change</strong>: a tag percebe sozinha as trocas de página em sites SPA.</>,
    <>Salve, teste no modo <strong>Visualizar</strong> e publique com <strong>Enviar</strong>.</>,
  ] : [
    <>Abra o modelo (layout) que todas as páginas compartilham, normalmente o cabeçalho.</>,
    <>Cole o código dentro de {code('<head>')}, antes de {code('</head>')}. Evite páginas avulsas: o código precisa estar em todas.</>,
    <>Publique e abra uma página do site. Na aba Rede do navegador aparecem {code('supertag.js')} e, logo depois, o envio para {code('collect')}.</>,
  ];
  return <Card title="Como instalar" description="Uma vez só, em todas as páginas do site.">
    <ol className="flex flex-col gap-3">{steps.map((step, index) => <li key={index} className="flex gap-3 text-sm text-secondary">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-primary text-xs font-semibold text-brand-secondary">{index + 1}</span><span className="pt-0.5">{step}</span></li>)}</ol>
    <div className="mt-4 flex flex-col gap-3">
      {method === 'gtm' ? <Callout>A Super Tag não lê o {code('dataLayer')} e não depende das configurações de consentimento do GTM: começa a medir assim que carrega e só para com uma recusa explícita do site. Depois de publicar, use <strong>Verificar instalação</strong>.</Callout>
        : <Callout><strong>WordPress:</strong> use um plugin de cabeçalho e rodapé (como o WPCode) e cole na área Header. <strong>Wix, Webflow e Shopify:</strong> em Código personalizado, aplique a todas as páginas, na posição Head. Se o site já usa o Google Tag Manager, você pode instalar por ele.</Callout>}
      <Callout tone="warning">Instale uma única vez. Se o código estiver no site e também no GTM, as visitas são contadas em dobro.</Callout>
    </div>
  </Card>;
}

function Audience({detail}) {
  const overall = detail.branding?.overall;
  const engaged = overall && Number(overall.sessions) ? Math.round(100 * Number(overall.engaged_sessions) / Number(overall.sessions)) : 0;
  const coverage = overall && Number(overall.sessions) ? Math.round(100 * Number(overall.measured_sessions) / Number(overall.sessions)) : 0;
  return <>
    {overall && Number(overall.sessions) > 0 && <Stats items={[['Visitantes', integer(overall.visitors), 'Navegadores diferentes neste site'], ['Sessões', integer(overall.sessions), `${integer(overall.closed_sessions)} encerradas · ${integer(detail.known_sessions || 0)} identificadas`],
      ['Engajamento', `${engaged}%`, 'Sessões com 2+ páginas, 10 s ativos ou conversão'], ['Tempo ativo médio', seconds(overall.avg_active_seconds), `${coverage}% das sessões medidas · ${decimal(overall.avg_pages || 0)} páginas/sessão`]]}/>}
    <Card flush title="Campanhas observadas" badge={<Badge type="pill-color" size="sm" color="gray">{detail.branding?.campaigns?.length || 0}</Badge>} description="Campanha (utm_id ou utm_campaign) da primeira página da sessão. O resto da sessão fica atribuído a ela.">
      {detail.branding?.campaigns?.length ? <DataTable dense minWidth={720} rowKey={row => row.campaign_scope || 'sem'} rows={detail.branding.campaigns} columns={[
        ['Campanha', row => row.campaign_scope ? <span className="font-medium text-primary">{row.campaign_scope}</span> : <span className="text-tertiary">Sem campanha</span>],
        ['Visitantes', row => integer(row.visitors), 'right'], ['Sessões', row => integer(row.sessions), 'right'], ['Engajadas', row => integer(row.engaged_sessions), 'right'],
        ['Tempo ativo', row => seconds(row.avg_active_seconds), 'right'], ['Formulários', row => integer(row.forms), 'right'], ['WhatsApp', row => integer(row.whatsapp_clicks), 'right'], ['Conversões', row => integer(row.conversions), 'right']]}/>
        : <EmptyNote title="Nenhuma campanha identificada">Aparecem quando o tráfego chega com utm_id ou utm_campaign.</EmptyNote>}
    </Card>
    <Card flush title="Páginas" badge={<Badge type="pill-color" size="sm" color="gray">{detail.pages?.length || 0}</Badge>} description="Últimos 30 dias. Saída é a última página vista numa sessão encerrada (30 min sem atividade).">
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
    <Card flush title="Sessões recentes" badge={<Badge type="pill-color" size="sm" color="gray">{detail.sessions?.length || 0}</Badge>} description="As 100 sessões mais recentes: campanha, páginas percorridas e saída.">
      {detail.sessions?.length ? <DataTable minWidth={900} rowKey={row => row.session_id} rows={detail.sessions} columns={[
        ['Visitante', row => row.known_name ? <><p className="font-medium text-primary">{row.known_name}</p><p className="text-xs text-tertiary">Identificado</p></> : <span className="text-tertiary">Anônimo</span>],
        ['Campanha', row => row.campaign || <span className="text-tertiary">Sem campanha</span>], ['Início', row => new Date(row.started_at).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'})],
        ['Navegação', row => {const pages = (row.journey || []).filter(event => event.kind === 'page_view' || event.kind === 'conversion'); return pages.length ? <span className="font-mono text-xs">{pages.map(event => event.page).join(' → ')}</span> : '—';}],
        ['Saída', row => <span className="font-mono text-xs">{row.exit_page || '—'}</span>]]}/>
        : <EmptyNote title="Nenhuma sessão ainda"/>}
    </Card>
    <Card flush title="Mapas de interação" badge={<Badge type="pill-color" size="sm" color="gray">{detail.heatmap?.length || 0}</Badge>}
      description="Cliques agrupados em quadrados de 5% da tela. Para medir se um elemento foi visto, marque-o com data-cadu-track e data-cadu-element=&quot;nome&quot;. O texto da página não é lido.">
      {detail.heatmap?.length ? <DataTable minWidth={640} rowKey={(row, index) => `${row.event_kind}:${row.element_id}:${index}`} rows={detail.heatmap.slice(0, 30)} columns={[
        ['Tipo', row => EVENT_LABELS[row.event_kind] || row.event_kind], ['Elemento', row => <span className="font-mono text-xs">{row.element_id || '—'}</span>], ['Posição', cell], ['Ocorrências', row => integer(row.total), 'right']]}/>
        : <EmptyNote title="Sem agregados ainda"/>}
    </Card>
    <Card flush title="Retorno por semana" description="Semana da primeira visita observada e quantos voltaram em até 7 dias.">
      {detail.branding?.cohorts?.length ? <DataTable minWidth={640} rowKey={row => `${row.campaign_scope}:${row.cohort_week}`} rows={detail.branding.cohorts} columns={[
        ['Semana', row => shortDate(row.cohort_week)], ['Campanha', row => row.campaign_scope || <span className="text-tertiary">Sem campanha</span>], ['Visitantes', row => integer(row.visitors), 'right'],
        ['Retornaram', row => integer(row.returned_7d), 'right'], ['Taxa', row => Number(row.visitors) ? `${Math.round(100 * Number(row.returned_7d) / Number(row.visitors))}%` : '—', 'right']]}/>
        : <EmptyNote title="Ainda sem semanas completas">Aparecem depois de sete dias de visitas.</EmptyNote>}
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

/** What the tag measures on its own. Saved here, read by the tag from its config: nothing changes on the site. */
function Measurement({site, disabled, onUpdate, onInstall}) {
  const saved = site.config?.enhanced || {};
  const code = text => <code className="rounded bg-secondary px-1 font-mono text-xs">{text}</code>;
  return <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
    <Card title="Medição aprimorada" description="Cada item é detectado sozinho, sem marcar nada no site. Ao desligar, o Reports para de aceitar esses eventos na hora; os navegadores podem levar alguns minutos para parar de enviá-los."
      actions={<Button size="sm" color="link-color" iconTrailing={ChevronRight} onPress={onInstall}>Ver instalação</Button>}>
      <ul className="flex flex-col divide-y divide-secondary rounded-lg ring-1 ring-secondary ring-inset">{MEASUREMENTS.map(([key, title, hint]) =>
        <li key={key}><label className="flex cursor-pointer items-start gap-3 px-4 py-3">
          <input type="checkbox" role="switch" className="mt-0.5 size-4 accent-brand-600" disabled={disabled} checked={saved[key] !== false}
            onChange={event => onUpdate({enhanced: {[key]: event.target.checked}})}/>
          <span><span className="block text-sm font-semibold text-primary">{title}</span><span className="block text-sm text-tertiary">{hint}</span></span>
        </label></li>)}</ul>
    </Card>
    <div className="flex flex-col gap-6">
      <Card title="Elementos marcados" description="Mede quando uma parte específica da página aparece na tela.">
        <label className="flex cursor-pointer items-start gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
          <input type="checkbox" role="switch" className="mt-0.5 size-4 accent-brand-600" disabled={disabled} checked={site.config?.visibility_enabled !== false} onChange={event => onUpdate({visibility_enabled: event.target.checked})}/>
          <span><span className="block text-sm font-semibold text-primary">Medir visibilidade de elementos marcados</span>
            <span className="block text-sm text-tertiary">Registra quando um elemento com {code('data-cadu-track')} e {code('data-cadu-element="nome"')} fica 25%, 50%, 75% ou 100% visível.</span></span>
        </label>
      </Card>
      <Card title="Eventos próprios" description="Para ações que a tag não detecta sozinha.">
        <pre className="rounded-lg bg-secondary p-4 font-mono text-xs leading-5 break-all whitespace-pre-wrap text-secondary ring-1 ring-secondary ring-inset">{"CaduSuperTag.event('lead_enviado', {value: 100, currency: 'BRL'});"}</pre>
        <p className="mt-3 text-sm text-tertiary">Com {code('conversion: true')} nos parâmetros, o evento já conta como conversão. Sem isso, você pode transformá-lo em conversão na aba Conversões.</p>
      </Card>
    </div>
  </div>;
}

function Identity() {
  const code = text => <code className="rounded bg-secondary px-1 font-mono text-xs">{text}</code>;
  return <div className="grid items-start gap-6 xl:grid-cols-2">
    <Card title="Associar visita a um usuário" description="Use quando a pessoa faz login ou envia um formulário feito em JavaScript, que não passa pelo envio comum do navegador.">
      <pre className="rounded-lg bg-secondary p-4 font-mono text-xs leading-5 break-all whitespace-pre-wrap text-secondary ring-1 ring-secondary ring-inset">{'window.CaduSuperTag?.identify({ name: usuario.nome, email: usuario.email, phone: usuario.telefone });'}</pre>
      <p className="mt-3 text-sm text-tertiary">Precisa de e-mail ou telefone; o nome é opcional. A sessão passa a aparecer com o nome da pessoa em Atividade, e o contato vai para Quem converteu, na aba Conversões.</p>
    </Card>
    <Card title="Privacidade" description="O que acontece com os dados de quem foi identificado.">
      <ul className="flex list-disc flex-col gap-2 pl-5 text-sm text-secondary">
        <li>O contato é guardado cifrado e só aparece por inteiro para quem pode editar o site.</li>
        <li>É apagado junto com os eventos, no prazo de retenção definido em Configurações.</li>
        <li>Formulários comuns já são lidos sozinhos quando a captura de Quem converteu está ligada; {code('identify()')} é só para os casos acima.</li>
      </ul>
    </Card>
  </div>;
}

function SiteName({site, disabled, onUpdate}) {
  const [label, setLabel] = useState(site.label || '');
  useEffect(() => {setLabel(site.label || '');}, [site.id, site.label]);
  const clean = label.trim().replace(/\s+/g, ' ');
  return <Card title="Site" description="Nome usado no Reports e no comentário que delimita o código no site.">
    <div className="flex flex-col gap-4">
      <ReportsFieldInput label="Nome da instalação" maxLength={120} disabled={disabled} value={label} onChange={event => setLabel(event.target.value)}/>
      <div><p className="text-sm font-medium text-secondary">Domínio</p><p className="font-mono text-sm text-primary">{site.allowed_host}</p>
        <p className="text-xs text-tertiary">Vale também para os subdomínios. Para medir outro domínio, conecte um novo site.</p></div>
      {!disabled && <span><Button size="sm" color="secondary" isDisabled={!clean || clean === site.label} onPress={() => onUpdate({label: clean})}>Salvar nome</Button></span>}
    </div>
  </Card>;
}

function Settings({data, site, busy, canEdit, onUpdate, onRevoke}) {
  const config = site.config || {};
  const disabled = busy || !canEdit;
  return <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
    <div className="flex flex-col gap-6">
      <SiteName site={site} disabled={disabled} onUpdate={onUpdate}/>
      <Card title="Coleta" description="Valem para as próximas visitas e eventos. O que já foi recebido mantém o prazo de quando chegou.">
        <div className="flex flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <ReportsNativeSelect label="Duração do identificador" hint="Por quanto tempo o mesmo navegador é reconhecido como o mesmo visitante." disabled={disabled} value={config.audience_days || 365} onChange={event => onUpdate({audience_days: Number(event.target.value)})}>
              {AUDIENCE_DAYS.map(([days, name]) => <option key={days} value={days}>{name}</option>)}</ReportsNativeSelect>
            <ReportsNativeSelect label="Retenção dos eventos" hint="Por quanto tempo eventos e contatos ficam guardados." disabled={disabled} value={config.retention_days || 365} onChange={event => onUpdate({retention_days: Number(event.target.value)})}>
              {RETENTION_DAYS.map(([days, name]) => <option key={days} value={days}>{name}</option>)}</ReportsNativeSelect>
          </div>
          <p className="text-sm text-tertiary">O aviso de cookies e a política de privacidade são do site. A Super Tag mede desde a primeira visita e só para com uma recusa explícita: {"window.CaduSuperTag.setConsent(false)"} ou {"window.dispatchEvent(new CustomEvent('cadu:consent', {detail: {analytics: false}}))"}.</p>
        </div>
      </Card>
    </div>
    <div className="flex flex-col gap-6">
      <Card title="Acesso ao monitoramento" description="Quem pode ver os dados deste site na plataforma." actions={<ReportsRelationships data={data} kind="site" id={site.id} name={site.label}/>}/>
      {canEdit && !site.revoked_at && <Card title="Revogar instalação" description="Interrompe a coleta neste domínio. Os dados já recebidos continuam no Reports até o fim da retenção.">
        <Button size="md" color="secondary-destructive" isDisabled={busy} onPress={onRevoke}>Revogar instalação</Button>
      </Card>}
    </div>
  </div>;
}

const RULE_TYPES = [['path:exact', 'Página exata'], ['path:prefix', 'Página que começa com'], ['path:segment', 'Parte do endereço que começa com'],
  ['valid_form', 'Formulário válido'], ['event_name', 'Evento próprio do site']];
const RULE_FIELDS = {
  'path:exact': ['Endereço da página', '/obrigado', 'Conta a visita a esta página exata. Pode colar o endereço completo: só o caminho é usado.'],
  'path:prefix': ['Começo do endereço', '/checkout/concluido', 'Conta qualquer página cujo caminho começa com este texto.'],
  'path:segment': ['Trecho', 'obrigad', 'Conta páginas em que alguma parte do endereço, entre barras, começa com este trecho. Ex.: obrigad conta /obrigado e /pedido/obrigada.'],
  valid_form: ['Formulário (opcional)', 'contato', 'Vazio, vale qualquer formulário enviado sem erro. Para um formulário só, informe o valor do atributo data-cadu-form dele.'],
  event_name: ['Nome do evento', 'lead_enviado', 'O mesmo nome usado em CaduSuperTag.event() no site.'],
};
const ruleLabel = rule => rule.type === 'path' ? `${rule.match === 'exact' ? 'Página' : rule.match === 'segment' ? 'Parte do endereço começando com' : 'Página que começa com'} ${rule.value}`
  : rule.type === 'valid_form' ? `Formulário válido${rule.form_id ? ` (${rule.form_id})` : ''}` : `Evento ${rule.value}`;
const EVENT_NAME = /^[A-Za-z][A-Za-z0-9_]{0,79}$/;

/** The rule the form describes, normalized like the server does, or the message explaining what to fix. */
export function buildRule(kind, value, name) {
  const [type, match] = kind.split(':');
  const text = String(value || '').trim();
  let rule;
  if (type === 'path' && match === 'segment') {
    const stem = text.replace(/^\/+|\/+$/g, '');
    if (!/^[A-Za-z0-9_.-]{2,60}$/.test(stem)) return {error: 'Trecho: de 2 a 60 letras sem acento, números, ponto, _ ou -, sem barras (ex.: obrigad).'};
    rule = {type, match, value: stem};
  } else if (type === 'path') {
    let path = text;
    if (/^https?:\/\//i.test(path)) {try {path = new URL(path).pathname || '/';} catch (_) {return {error: 'Endereço inválido. Use só o caminho, como /obrigado.'};}}
    path = path.split(/[?#]/)[0].trim();
    if (!path) return {error: 'Informe o endereço da página, como /obrigado.'};
    if (!path.startsWith('/')) path = `/${path}`;
    if (/\s|@/.test(path) || path.length > 200) return {error: 'Endereço inválido: use só o caminho, como /obrigado (sem espaços nem e-mail).'};
    rule = {type, match, value: path};
  } else if (type === 'valid_form') {
    if (text && !/^[A-Za-z0-9_-]{1,80}$/.test(text)) return {error: 'Formulário: o valor de data-cadu-form, com letras sem acento, números, _ ou -.'};
    rule = text ? {type, form_id: text} : {type};
  } else {
    if (!EVENT_NAME.test(text)) return {error: 'Nome do evento: letras sem acento, números e _, começando por letra (ex.: lead_enviado).'};
    rule = {type, value: text};
  }
  const slug = String(name || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').trim().replace(/[^A-Za-z0-9_]+/g, '_').replace(/^_+|_+$/g, '').toLowerCase().slice(0, 80);
  if (slug && !EVENT_NAME.test(slug)) return {error: 'O nome da conversão precisa começar por uma letra (ex.: lead_site).'};
  if (slug) rule.name = slug;
  return {rule};
}

/** What counts as a conversion on this site. Rules are applied when the events arrive, so every screen agrees. */
function ConversionRules({site, disabled, onUpdate}) {
  const [state, setState] = useState(null);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
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
  const add = async () => {
    const built = buildRule(kind, value, name);
    if (built.error) {setFormError(built.error); return;}
    setFormError('');
    if (await save([...rules, built.rule])) {setValue(''); setName('');}
  };
  const [fieldLabel, placeholder, hint] = RULE_FIELDS[kind];
  const needsValue = kind !== 'valid_form';
  return <Card title="O que conta como conversão" description="Vale para os eventos que chegarem a partir de agora; o que já foi recebido não é recontado.">
    {error && <Alert>{error}</Alert>}
    {!state && !error && <p role="status" className="text-sm text-tertiary">Carregando regras…</p>}
    {state && <div className="flex flex-col gap-4">
      {!rules.length && <label className="flex cursor-pointer items-start gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
        <input type="checkbox" className="mt-0.5 size-4 accent-brand-600" disabled={disabled} checked={state.conversion_defaults} onChange={event => onUpdate({conversion_defaults: event.target.checked})}/>
        <span><span className="block text-sm font-semibold text-primary">Página de obrigado automática</span>
          <span className="block text-sm text-tertiary">Enquanto não houver nenhuma regra, conta como conversão a visita a páginas em que alguma parte do endereço começa com obrigad, thank, sucesso ou confirmac (como /obrigado, /thank-you, /sucesso ou /confirmacao). Assim que você criar uma regra, só as suas regras valem.</span></span>
      </label>}
      {rules.length > 0 && <ul className="flex flex-col divide-y divide-secondary rounded-lg ring-1 ring-secondary ring-inset">{rules.map((rule, index) =>
        <li key={`${rule.type}${rule.value || rule.form_id || ''}${index}`} className="flex items-center justify-between gap-3 px-4 py-2.5">
          <span className="min-w-0"><span className="block truncate text-sm font-medium text-primary">{ruleLabel(rule)}</span><span className="block font-mono text-xs text-tertiary">{rule.name || (rule.type === 'event_name' ? rule.value : rule.type === 'valid_form' ? 'formulario_enviado' : 'pagina_obrigado')}</span></span>
          {!disabled && <CaduTooltip label="Remover regra"><Button size="sm" color="tertiary" iconLeading={Trash01} aria-label={`Remover ${ruleLabel(rule)}`} onPress={() => save(rules.filter((_, position) => position !== index))}/></CaduTooltip>}
        </li>)}</ul>}
      {state.suggestions?.length > 0 && <div className="flex flex-col gap-2">
        <p className="text-sm font-semibold text-primary">Sugestões</p>
        <p className="text-xs text-tertiary">Páginas visitadas nos últimos 90 dias com obrigad, thank, sucesso ou confirmac no endereço que nenhuma regra sua cobre. Ao usar, a página vira uma regra de página exata.</p>
        {state.suggestions.map(item => <div key={item.path} className="flex items-center justify-between gap-3 rounded-lg px-4 py-2 ring-1 ring-secondary ring-inset">
          <span className="min-w-0"><span className="block truncate font-mono text-xs text-primary">{item.path}</span><span className="text-xs text-tertiary">{integer(item.views)} visitas · 90 dias</span></span>
          {!disabled && <Button size="sm" color="secondary" iconLeading={Plus} onPress={() => save([...rules, item.rule])}>Usar</Button>}
        </div>)}
      </div>}
      {!disabled && <div className="flex flex-col gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
        <p className="text-sm font-semibold text-primary">Nova regra</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <ReportsNativeSelect label="Tipo de regra" value={kind} onChange={event => {setKind(event.target.value); setFormError('');}}>{RULE_TYPES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</ReportsNativeSelect>
          <ReportsFieldInput label={fieldLabel} value={value} onChange={event => {setValue(event.target.value); setFormError('');}} placeholder={placeholder}/>
        </div>
        <p className="text-xs text-tertiary">{hint}</p>
        <ReportsFieldInput label="Nome da conversão (opcional)" value={name} onChange={event => {setName(event.target.value); setFormError('');}} placeholder="lead_site"/>
        <p className="text-xs text-tertiary">Aparece nos relatórios. Pode escrever normalmente: “Lead do site” vira lead_do_site.</p>
        {formError && <Alert>{formError}</Alert>}
        {!rules.length && state.conversion_defaults && <p className="text-xs text-tertiary">Ao criar a primeira regra, a página de obrigado automática deixa de valer.</p>}
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
  return <Card title="Quem converteu" description="Nome e contato de quem envia um formulário válido. Ficam cifrados e são apagados junto com os eventos.">
    <div className="flex flex-col gap-4">
      <label className="flex cursor-pointer items-start gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
        <input type="checkbox" className="mt-0.5 size-4 accent-brand-600" disabled={disabled} checked={capture.enabled !== false} onChange={event => onUpdate({form_capture: {enabled: event.target.checked}})}/>
        <span><span className="block text-sm font-semibold text-primary">Capturar nome, e-mail e telefone</span>
          <span className="block text-sm text-tertiary">Reconhecidos pelo tipo e pelo nome do campo. Senha, cartão, CPF, CNPJ, RG, tokens, campos ocultos e armadilhas anti-robô nunca são lidos. Para excluir um campo, marque-o com data-cadu-ignore.</span></span>
      </label>
      <ReportsNativeSelect label="Lead confirmado quando" disabled={disabled} value={capture.confirm || 'conversion'} onChange={event => onUpdate({form_capture: {confirm: event.target.value}})}
        hint="Até ser confirmado, o contato aparece como pendente.">
        <option value="conversion">Houver uma conversão na mesma sessão até 30 min depois do envio</option><option value="valid_submit">O formulário for enviado sem erro</option></ReportsNativeSelect>
      <div className="flex flex-col gap-2">
        <ReportsFieldInput label="Campos extras (atributo name)" disabled={disabled} value={fields} onChange={event => setFields(event.target.value)} placeholder="empresa, interesse, cidade"/>
        <p className="text-xs text-tertiary">Até 20 nomes, separados por vírgula. Campos sensíveis (senha, cartão, documentos) são recusados.</p>
        {!disabled && <span><Button size="sm" color="secondary" isDisabled={list.join(',') === (capture.fields || []).join(',')} onPress={() => onUpdate({form_capture: {fields: list}})}>Salvar campos</Button></span>}
      </div>
    </div>
  </Card>;
}

function InstallDrawer({open, data, onClose, onCreated}) {
  const [host, setHost] = useState('');
  const [label, setLabel] = useState('');
  const [labelWasEdited, setLabelWasEdited] = useState(false);
  const [customerId, setCustomerId] = useState('');
  const [check, setCheck] = useState(null);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {if (open) {setHost(''); setLabel(''); setLabelWasEdited(false); setCustomerId(''); setCheck(null); setError('');}}, [open]);
  const verify = async () => {
    if (!host.trim()) return;
    setChecking(true); setCheck(null); setError('');
    try {const result = await json(`${API}/site-check?url=${encodeURIComponent(host.includes('://') ? host : `https://${host}`)}`); setCheck(result); if (result.title && !labelWasEdited) setLabel(result.title.slice(0, 120));}
    catch (failure) {setCheck({error: failure.message});} finally {setChecking(false);}
  };
  const handleHostChange = (value) => {
    setHost(value);
    setCheck(null);
  };
  const handleLabelChange = (value) => {
    setLabel(value);
    setLabelWasEdited(true);
  };
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const checkedHost = new URL(host.includes('://') ? host : `https://${host}`).host;
      const payload = {label: label || checkedHost, allowed_host: checkedHost};
      if (customerId) payload.customer_id = customerId;
      const result = await json(`${API}/sites`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify(payload)});
      if (check?.favicon) faviconCache.set(checkedHost, check.favicon);
      await onCreated(result.site);
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  return <ReportsDrawer open={open} onOpenChange={value => {if (!value) onClose();}} title="Conectar site" context={data.client.client_name} description="Informe o endereço do site. Conferimos se ele responde antes de gerar o código.">
    <form className="untitled-scope flex flex-col gap-5" onSubmit={submit}>
      {error && <Alert>{error}</Alert>}
      <div className="flex items-end gap-3">
        <div className="flex-1"><ReportsFieldInput label="Endereço do site" required type="url" value={host} onChange={event => handleHostChange(event.target.value)} placeholder="www.exemplo.com.br ou exemplo.com.br"/></div>
        <Button type="button" size="md" color="secondary" isDisabled={!host.trim() || checking} isLoading={checking} onPress={verify}>Verificar</Button>
      </div>
      {check && (check.error ? <Callout tone="error" title="Não foi possível acessar o site">{check.error}</Callout>
        : <div className="flex items-center gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
          <span className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg ring-1 ring-secondary">{check.favicon ? <img src={check.favicon} alt="" className="size-6"/> : <span className="text-tertiary">◎</span>}</span>
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-primary">{check.title || check.host || 'Site encontrado'}</p><p className="text-xs text-tertiary">{check.host}{check.status ? ` · HTTP ${check.status}` : ''}</p></div>
          <BadgeWithDot type="pill-color" size="sm" color="success">Respondeu</BadgeWithDot>
        </div>)}
      <ReportsFieldInput label="Nome desta instalação" required maxLength={120} value={label} onChange={event => handleLabelChange(event.target.value)} placeholder={check?.title || 'Será preenchido automaticamente'}/>
      <ReportsNativeSelect label="Cliente / anunciante" value={customerId} onChange={event => setCustomerId(event.target.value)}>
        <option value="">Sem cliente</option>{(data.customers || []).filter(item => item.status !== 'archived').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </ReportsNativeSelect>
      <p className="text-sm text-tertiary">A coleta começa na primeira visita. O aviso de cookies e a política de privacidade continuam sendo do site.</p>
      <DrawerActions onCancel={onClose} busy={busy} label="Criar instalação" disabled={!check || Boolean(check.error)}/>
    </form>
  </ReportsDrawer>;
}
