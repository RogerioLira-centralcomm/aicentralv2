import React, {useEffect, useRef, useState} from 'react';
import {ArrowLeft, ArrowUpRight, Plus, SearchLg, Stars02, Trash01, UploadCloud02} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';
import {Alert, Callout, Card, DateField, DrawerActions, EmptyNote} from './ReportsBlocks.jsx';
import {json, shortDate} from './reportsCommon.jsx';
import {createFromGoogle, loadUnlinkedGoogleCampaigns} from './GoogleCampaignLinks.jsx';

const API = '/connect/api/v2/reports';
const EMPTY_METRIC = {name: '', raw: '', unit: 'count', definition: '', scope: '', evidence: ''};
const UNITS = [['count', 'Quantidade'], ['BRL', 'R$'], ['USD', 'US$'], ['percent', '%'], ['seconds', 'Segundos']];
const KINDS = [['all', 'Todos'], ['published', 'Publicados'], ['draft', 'Em edição']];

/** Saved reports: a library of cards, then one report with document, sources, assistant and publication. */
export function ReportsLibrary({data, save, busy}) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  useEffect(() => {setDetail(null); setError('');}, [data.client.client_id]);
  const open = async reportId => {
    setError('');
    try {setDetail(await json(`${API}/workspaces/${reportId}`));} catch (failure) {setError(failure.message);}
  };
  const refresh = async () => setDetail(await json(`${API}/workspaces/${detail.report.id}`));
  return <div className="untitled-scope flex flex-col gap-6">
    {error && <Alert>{error}</Alert>}
    {detail ? <ReportDetail key={detail.report.id} data={data} save={save} busy={busy} detail={detail} refresh={refresh} onBack={() => setDetail(null)} setError={setError}/>
      : <Library data={data} onOpen={open} onCreate={() => setCreateOpen(true)}/>}
    <CreateDrawer open={createOpen} data={data} save={save} busy={busy} onClose={() => setCreateOpen(false)}/>
  </div>;
}

function Library({data, onOpen, onCreate}) {
  const [query, setQuery] = useState('');
  const [campaign, setCampaign] = useState('');
  const [kind, setKind] = useState('all');
  const term = query.trim().toLocaleLowerCase();
  const visible = data.reports.filter(item => (!term || `${item.campaign_name} ${item.project_ref || ''}`.toLocaleLowerCase().includes(term))
    && (!campaign || (campaign === 'none' ? !item.media_campaign_id && !item.flow_id : campaign.startsWith('flow:') ? item.flow_id === campaign.slice(5) : String(item.media_campaign_id) === campaign))
    && (kind === 'all' || (kind === 'published') === Boolean(item.published)));
  const counts = {all: data.reports.length, published: data.reports.filter(item => item.published).length, draft: data.reports.filter(item => !item.published).length};
  const campaignName = id => data.campaigns.find(item => String(item.id) === String(id))?.name;
  const flows = [...new Map(data.reports.filter(item => item.flow_id).map(item => [item.flow_id, item.flow_name])).entries()];
  const scopeLabel = item => item.flow_id ? `Fluxo · ${item.flow_name || 'sem nome'}` : campaignName(item.media_campaign_id) || 'Sem campanha';
  return <Card flush title="Relatórios" badge={<Badge type="pill-color" size="sm" color="gray">{data.reports.length}</Badge>} description="Documentos de resultado por campanha ou por fluxo, com evidências revisadas e link público opcional."
    actions={data.client.role !== 'viewer' && <Button size="md" color="primary" iconLeading={Plus} onPress={onCreate}>Criar relatório</Button>}>
    <div className="flex flex-wrap items-center gap-3 border-b border-secondary px-6 py-3">
      <div className="rs-segmented rs-segmented--sm" role="group" aria-label="Situação">{KINDS.map(([key, label]) => <button type="button" key={key} aria-pressed={kind === key} onClick={() => setKind(key)}>{label} <small>{counts[key]}</small></button>)}</div>
      <div className="ml-auto flex flex-wrap gap-3">
        <div className="w-64"><ReportsFieldInput size="sm" type="search" aria-label="Buscar relatório" placeholder="Buscar relatório" value={query} onChange={event => setQuery(event.target.value)}
          leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/></div>
        <div className="w-56"><ReportsNativeSelect size="sm" aria-label="Campanha ou fluxo" value={campaign} onChange={event => setCampaign(event.target.value)}>
          <option value="">Todas as campanhas e fluxos</option><option value="none">Sem campanha nem fluxo</option>
          {flows.map(([id, name]) => <option key={id} value={`flow:${id}`}>Fluxo · {name}</option>)}
          {data.campaigns.filter(item => data.reports.some(report => String(report.media_campaign_id) === String(item.id))).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </ReportsNativeSelect></div>
      </div>
    </div>
    {visible.length ? <div className="grid gap-4 p-6 sm:grid-cols-2 xl:grid-cols-3">{visible.map(item => <button type="button" key={item.id} onClick={() => onOpen(item.id)}
      className="flex flex-col gap-2 rounded-xl bg-primary p-5 text-left shadow-xs ring-1 ring-secondary transition duration-100 ring-inset hover:bg-primary_hover hover:ring-primary">
      <div className="flex items-center justify-between gap-2">
        <BadgeWithDot type="pill-color" size="sm" color={item.published ? 'success' : 'gray'}>{item.published ? 'Publicado' : 'Em edição'}</BadgeWithDot>
        <span className="text-xs text-tertiary">v{item.revision}</span>
      </div>
      <h3 className="text-md font-semibold text-primary">{item.campaign_name}</h3>
      <p className="text-sm text-tertiary">{scopeLabel(item)}{item.project_ref ? ' · com projeto' : ''}</p>
      <p className="mt-auto pt-2 text-xs text-quaternary">Atualizado em {shortDate(item.updated_at)}</p>
    </button>)}</div>
      : <EmptyNote title={data.reports.length ? 'Nada corresponde aos filtros' : 'Nenhum relatório ainda'}>{data.reports.length ? 'Ajuste a busca, a situação ou a campanha.' : 'Crie um relatório por campanha, por fluxo ou independente.'}</EmptyNote>}
  </Card>;
}

function CreateDrawer({open, data, save, busy, onClose}) {
  const [form, setForm] = useState({campaign_name: '', media_campaign_id: '', flow_id: ''});
  const [scope, setScope] = useState('campaign');
  const [flows, setFlows] = useState(null);
  const [flowError, setFlowError] = useState('');
  const [google, setGoogle] = useState([]);
  useEffect(() => {if (open) loadUnlinkedGoogleCampaigns().then(setGoogle).catch(() => setGoogle([]));}, [open]);
  const pickedGoogle = form.media_campaign_id.startsWith('gads:') ? google[Number(form.media_campaign_id.slice(5))] : null;
  useEffect(() => {if (open) {setForm({campaign_name: '', media_campaign_id: '', flow_id: ''}); setScope('campaign');}}, [open]);
  // Flows load only when the flow scope is picked: the list comes from the Fluxos area.
  useEffect(() => {
    if (!open || scope !== 'flow' || flows) return;
    json(`${API}/flow`).then(value => setFlows((value.flows || []).filter(item => !item.archived_at))).catch(failure => {setFlows([]); setFlowError(failure.message);});
  }, [open, scope]);
  const submit = async event => {
    event.preventDefault();
    try {
      // A Google Ads campaign without a Reports record is created first, with all the context the script sent.
      const campaignId = pickedGoogle ? (await createFromGoogle(save, pickedGoogle, false)).campaign.id : form.media_campaign_id;
      const payload = scope === 'flow' ? {campaign_name: form.campaign_name, flow_id: form.flow_id} : scope === 'campaign' ? {campaign_name: form.campaign_name, media_campaign_id: campaignId} : {campaign_name: form.campaign_name};
      await save('/workspaces', payload); onClose();
    } catch (_) { /* The page banner shows the failure. */ }
  };
  const SCOPES = [['campaign', 'Por campanha', 'Resultado de mídia de uma campanha.'], ['flow', 'Por fluxo', 'Jornada do fluxo com a mídia das campanhas que levam tráfego a ele.'], ['none', 'Independente', 'Sem vínculo; você monta as evidências.']];
  return <ReportsDrawer open={open} onOpenChange={value => {if (!value) onClose();}} title="Criar relatório" description="Escolha o foco do relatório: uma campanha ou um fluxo." context={data.client.client_name}>
    <form className="untitled-scope flex flex-col gap-5" onSubmit={submit}>
      <ReportsFieldInput label="Nome" required maxLength={200} value={form.campaign_name} onChange={event => setForm({...form, campaign_name: event.target.value})} placeholder="Ex.: Resultado de setembro"/>
      <fieldset className="flex flex-col gap-2"><legend className="mb-2 text-sm font-medium text-secondary">Foco</legend>
        {SCOPES.map(([key, label, hint]) => <label key={key} className={`flex cursor-pointer items-start gap-3 rounded-lg p-3 ring-inset ${scope === key ? 'bg-brand-primary ring-2 ring-brand' : 'ring-1 ring-secondary hover:bg-primary_hover'}`}>
          <input type="radio" name="report-scope" className="mt-1 size-4 accent-brand-600" checked={scope === key} onChange={() => setScope(key)}/>
          <span><span className="block text-sm font-semibold text-primary">{label}</span><span className="block text-sm text-tertiary">{hint}</span></span>
        </label>)}
      </fieldset>
      {scope === 'campaign' && <ReportsNativeSelect label="Campanha" required value={form.media_campaign_id} onChange={event => setForm({...form, media_campaign_id: event.target.value})}
        hint={pickedGoogle ? `Será criada agora com a conta ${pickedGoogle.account_name}, o ID ${pickedGoogle.campaign_external_id}, o tipo e o objetivo do Google Ads.` : google.length ? `${google.length} campanha(s) do Google Ads ainda sem cadastro aparecem no fim da lista: escolha uma para criar na hora.` : undefined}>
        <option value="">{data.campaigns.length || google.length ? 'Escolha a campanha' : 'Nenhuma campanha cadastrada'}</option>{data.campaigns.map(item => <option key={item.id} value={item.id}>{item.name} · {item.account_name || 'manual'}</option>)}
        {google.map((item, index) => <option key={`gads-${index}`} value={`gads:${index}`}>＋ Criar do Google Ads: {item.campaign_name || item.campaign_external_id} · {item.account_name}</option>)}
      </ReportsNativeSelect>}
      {scope === 'campaign' && !data.campaigns.length && google.length > 0 && !pickedGoogle && <Button size="sm" color="secondary" iconLeading={Plus} onPress={() => setForm({...form, media_campaign_id: 'gads:0', campaign_name: form.campaign_name || `Resultado · ${google[0].campaign_name}`})}>Criar rápido com a campanha do Google Ads</Button>}
      {scope === 'flow' && <ReportsNativeSelect label="Fluxo" required hint={flowError || (flows && !flows.length ? 'Nenhum fluxo neste cliente. Crie em Site & Jornada › Fluxos.' : 'As campanhas ligadas ao fluxo e às etapas entram no relatório.')} value={form.flow_id} onChange={event => setForm({...form, flow_id: event.target.value})}>
        <option value="">{flows ? 'Escolha o fluxo' : 'Carregando fluxos…'}</option>{(flows || []).map(item => <option key={item.id} value={item.id}>{item.name}{item.status === 'published' ? '' : item.status === 'paused' ? ' (pausado)' : ' (rascunho)'}</option>)}
      </ReportsNativeSelect>}
      <DrawerActions onCancel={onClose} busy={busy} label="Criar relatório"/>
    </form>
  </ReportsDrawer>;
}

/** Flow-scoped report: the journey of the flow in the report period, plus the media feeding it. */
function FlowJourneyCard({document}) {
  const [state, setState] = useState({loading: true});
  const params = new URLSearchParams(document.start_date && document.end_date ? {start_date: document.start_date, end_date: document.end_date} : {days: '30'});
  useEffect(() => {
    let live = true;
    json(`${API}/flow/flows/${document.flow_id}/journey?${params}`).then(body => live && setState({body})).catch(failure => live && setState({error: failure.message}));
    return () => {live = false;};
  }, [document.flow_id, document.start_date, document.end_date]);
  const body = state.body;
  const labels = Object.fromEntries((body?.config?.nodes || []).map(node => [node.id, node.title || node.label || node.name || node.id]));
  const steps = (body?.nodes || []).filter(node => node.sessions != null);
  const pct = value => value == null ? '—' : `${value.toLocaleString('pt-BR')}%`;
  return <Card title={`Jornada · ${document.flow_name}`} description={`${body?.scope ? `${shortDate(body.scope.from)} – ${shortDate(body.scope.to)}` : 'Últimos 30 dias'} · Super Tag do fluxo. Mídia: ${(document.flow_campaigns || []).map(item => item.name).join(', ') || 'nenhuma campanha ligada ao fluxo'}.`}>
    {state.loading ? <p className="text-sm text-tertiary">Carregando a jornada…</p>
      : state.error ? <Alert>{state.error}</Alert>
      : body.status !== 'ready' ? <EmptyNote title="Jornada indisponível">Publique o fluxo para medir a jornada.</EmptyNote>
      : <div className="flex flex-col gap-4">
        <dl className="grid gap-px overflow-hidden rounded-lg bg-border-secondary ring-1 ring-secondary sm:grid-cols-3">
          {[['Entradas', body.funnel?.entries], ['Conversões', body.funnel?.conversions], ['Taxa', pct(body.funnel?.rate)]].map(([term, value]) =>
            <div key={term} className="bg-primary px-4 py-3"><dt className="text-sm text-tertiary">{term}</dt><dd className="text-xl font-semibold text-primary tabular-nums">{typeof value === 'number' ? value.toLocaleString('pt-BR') : value ?? '—'}</dd></div>)}
        </dl>
        {steps.length ? <table className="w-full text-sm"><thead><tr><th className="py-2 text-left font-medium text-tertiary">Etapa</th><th className="py-2 text-right font-medium text-tertiary">Sessões</th></tr></thead>
          <tbody>{steps.map(node => <tr key={node.id} className="border-t border-secondary"><td className="py-2 text-primary">{labels[node.id]}</td><td className="py-2 text-right tabular-nums">{node.sessions.toLocaleString('pt-BR')}</td></tr>)}</tbody></table>
          : <p className="text-sm text-tertiary">{body.collection?.status === 'no_data' ? 'Nenhum evento da Super Tag no período.' : 'Nenhuma etapa medida.'}</p>}
      </div>}
  </Card>;
}

function ReportDetail({data, save, busy, detail, refresh, onBack, setError}) {
  const viewer = data.client.role === 'viewer';
  const [draft, setDraft] = useState(detail.report.document || {});
  const [note, setNote] = useState('');
  const [expiresDays, setExpiresDays] = useState('30');
  const [plan, setPlan] = useState(null);
  const [planning, setPlanning] = useState(false);
  const [reviewSource, setReviewSource] = useState(null);
  useEffect(() => {setDraft(detail.report.document || {});}, [detail.report.revision]);
  const edit = (field, value) => {setDraft(current => ({...current, [field]: value})); if (field === 'objective' || field === 'goals') setPlan(null);};
  const run = async action => {try {await action(); setError('');} catch (failure) {setError(failure.message);}};
  const update = event => {
    event.preventDefault();
    run(async () => {
      await save(`/workspaces/${detail.report.id}/document`, {revision: detail.report.revision, update_note: note, document: Object.fromEntries(['objective', 'goals', 'management_notes', 'start_date', 'end_date', 'accent'].map(field => [field, draft[field] || '']))});
      await refresh(); setNote('');
    });
  };
  const planNext = async () => {
    setPlanning(true);
    await run(async () => setPlan((await json(`${API}/workspaces/${detail.report.id}/plan`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({})})).plan));
    setPlanning(false);
  };
  const incorporate = () => {
    const addition = `${plan.title}\n${plan.steps.map(step => `• ${step}`).join('\n')}`;
    setDraft(current => ({...current, management_notes: [current.management_notes, addition].filter(Boolean).join('\n\n')}));
    setPlan(null);
  };
  const publish = () => run(async () => {await save(`/workspaces/${detail.report.id}/publish`, {expires_days: Number(expiresDays)}, false); await refresh();});
  const unpublish = () => run(async () => {await save(`/workspaces/${detail.report.id}/unpublish`, {}, false); await refresh();});
  const link = detail.public_link;

  return <>
    <div><Button size="sm" color="link-gray" iconLeading={ArrowLeft} onPress={onBack}>Relatórios</Button></div>
    <section className="flex flex-wrap items-start justify-between gap-4 rounded-xl bg-primary px-6 py-5 shadow-xs ring-1 ring-secondary">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-semibold text-primary">{detail.report.campaign_name}</h2>
          <BadgeWithDot type="pill-color" size="sm" color={link ? 'success' : 'gray'}>{link ? 'Publicado' : 'Privado'}</BadgeWithDot></div>
        <p className="mt-0.5 text-sm text-tertiary">Versão {detail.report.revision} · atualizado em {shortDate(detail.report.updated_at)} · {detail.sources.length} {detail.sources.length === 1 ? 'fonte' : 'fontes'}</p>
      </div>
      {link && <Button size="md" color="secondary" href={`/connect/r/${link.token}`} target="_blank" rel="noopener noreferrer" iconTrailing={ArrowUpRight}>Abrir link público</Button>}
    </section>
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="flex min-w-0 flex-col gap-6">
        {detail.report.document?.scope === 'flow' && <FlowJourneyCard document={detail.report.document}/>}
        <Card title="Documento" description="O que o relatório comunica. Cada atualização vira uma versão.">
          <form className="flex flex-col gap-5" onSubmit={update}>
            <ReportsTextArea label="Objetivo" disabled={viewer} maxLength={2000} rows={3} value={draft.objective || ''} onChange={event => edit('objective', event.target.value)}/>
            <ReportsTextArea label="Metas" disabled={viewer} maxLength={4000} rows={3} value={draft.goals || ''} onChange={event => edit('goals', event.target.value)}/>
            <ReportsTextArea label="Notas de gestão" disabled={viewer} maxLength={8000} rows={5} value={draft.management_notes || ''} onChange={event => edit('management_notes', event.target.value)}/>
            <div className="grid gap-4 sm:grid-cols-[1fr_1fr_120px]">
              <DateField label="Início" disabled={viewer} value={draft.start_date || ''} onChange={event => edit('start_date', event.target.value)}/>
              <DateField label="Fim" disabled={viewer} value={draft.end_date || ''} onChange={event => edit('end_date', event.target.value)}/>
              <label className="flex flex-col gap-1.5 text-sm font-medium text-secondary">Cor
                <input type="color" disabled={viewer} value={draft.accent || '#1767c5'} onChange={event => edit('accent', event.target.value)} className="h-10 w-full cursor-pointer rounded-lg bg-primary p-1 shadow-xs ring-1 ring-primary ring-inset"/></label>
            </div>
            {!viewer && <div className="flex flex-wrap items-end gap-3 border-t border-secondary pt-5">
              <div className="min-w-64 flex-1"><ReportsFieldInput label="Nota desta versão" required maxLength={2000} value={note} onChange={event => setNote(event.target.value)} placeholder="O que mudou neste relatório?"/></div>
              <Button type="submit" size="md" color="primary" isDisabled={busy} isLoading={busy}>Salvar versão</Button>
            </div>}
          </form>
        </Card>
        <SourcesCard data={data} detail={detail} viewer={viewer} busy={busy} refresh={refresh} setError={setError} onReview={setReviewSource}/>
      </div>
      <aside className="flex flex-col gap-6 lg:sticky lg:top-4">
        <Card title="Assistente" description="Sugere próximos passos a partir do objetivo e das métricas revisadas. Só entra no documento se você incorporar e salvar.">
          {!viewer && <Button size="md" color="secondary" iconLeading={Stars02} isDisabled={planning} isLoading={planning} onPress={planNext}>Planejar próximo passo</Button>}
          {plan && <div className="mt-4"><Callout tone="brand" title={plan.title}>
            <ul className="mt-1 flex list-disc flex-col gap-1 pl-5">{plan.steps.map((step, index) => <li key={index}>{step}</li>)}</ul>
            <Button className="mt-3" size="sm" color="link-color" onPress={incorporate}>Incorporar às notas</Button>
          </Callout></div>}
        </Card>
        <Card title="Publicação" badge={<Badge type="pill-color" size="sm" color={link ? 'success' : 'gray'}>{link ? 'Link ativo' : 'Privado'}</Badge>}>
          {link ? <div className="flex flex-col gap-3">
            <p className="text-sm text-secondary">{link.expires_at ? `Disponível até ${shortDate(link.expires_at)}.` : 'Disponível sem data de expiração.'}</p>
            {!viewer && <Button size="sm" color="secondary-destructive" isDisabled={busy} onPress={unpublish}>Revogar link</Button>}
          </div> : viewer ? <p className="text-sm text-tertiary">Ainda não publicado.</p> : <div className="flex items-end gap-3">
            <div className="flex-1"><ReportsNativeSelect label="Validade do link" value={expiresDays} onChange={event => setExpiresDays(event.target.value)}>
              <option value="7">7 dias</option><option value="30">30 dias</option><option value="90">90 dias</option><option value="0">Sem expiração</option>
            </ReportsNativeSelect></div>
            <Button size="md" color="primary" isDisabled={busy} onPress={publish}>Publicar</Button>
          </div>}
          <h3 className="mt-5 border-t border-secondary pt-4 text-sm font-semibold text-primary">Versões</h3>
          <ol className="mt-2 flex max-h-64 flex-col gap-2 overflow-y-auto">{detail.versions.map(item => <li key={item.revision} className="text-sm text-secondary">
            <span className="font-medium text-primary">v{item.revision}</span> · {item.note} <span className="text-xs text-tertiary">· {shortDate(item.created_at)}</span>
          </li>)}{!detail.versions.length && <li className="text-sm text-tertiary">Nenhuma versão anterior.</li>}</ol>
        </Card>
      </aside>
    </div>
    <ReviewDrawer source={reviewSource} data={data} detail={detail} busy={busy} viewer={viewer} refresh={refresh} setError={setError} onClose={() => setReviewSource(null)}/>
  </>;
}

function SourcesCard({data, detail, viewer, busy, refresh, setError, onReview}) {
  const [files, setFiles] = useState([]);
  const [supplier, setSupplier] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [sending, setSending] = useState(false);
  const input = useRef(null);
  const send = async () => {
    if (!files.length) return;
    const payload = new FormData();
    files.forEach(file => payload.append('prints', file));
    payload.append('supplier', supplier); payload.append('period_start', start); payload.append('period_end', end); payload.append('_csrf', data.csrf);
    setSending(true);
    try {
      const response = await fetch(`/connect/relatorios/${detail.report.id}/fontes`, {method: 'POST', body: payload, credentials: 'same-origin'});
      if (!response.ok) throw new Error(`Falha HTTP ${response.status}`);
      await refresh(); setFiles([]); setSupplier(''); setStart(''); setEnd(''); if (input.current) input.current.value = ''; setError('');
    } catch (failure) {setError(failure.message);} finally {setSending(false);}
  };
  return <Card flush title="Fontes e evidências" badge={<Badge type="pill-color" size="sm" color="gray">{detail.sources.length}</Badge>} description="Prints das plataformas. Cada valor usado no relatório é conferido contra o print.">
    {detail.sources.length ? <ul>{detail.sources.map(item => <li key={item.id} className="flex flex-wrap items-center gap-3 border-b border-secondary px-6 py-3">
      <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-primary">{item.original_name}</p><p className="text-xs text-tertiary">{item.supplier || 'Origem não informada'}</p></div>
      <BadgeWithDot type="pill-color" size="sm" color={item.status === 'reviewed' ? 'success' : 'warning'}>{item.status === 'reviewed' ? 'Revisada' : 'Aguardando revisão'}</BadgeWithDot>
      <Button size="sm" color="link-gray" href={`/connect/relatorios/${detail.report.id}/fontes/${item.id}`} target="_blank" rel="noopener noreferrer">Abrir print</Button>
      <Button size="sm" color="secondary" onPress={() => onReview(item)}>Revisar</Button>
    </li>)}</ul> : <EmptyNote title="Nenhuma fonte ainda">Envie os prints das plataformas para revisar os valores.</EmptyNote>}
    {!viewer && <div className="grid gap-4 bg-secondary_subtle px-6 py-5 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_150px_150px_auto] lg:items-end">
      <label className="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm shadow-xs ring-1 ring-primary ring-inset hover:bg-primary_hover">
        <input ref={input} type="file" multiple accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={event => setFiles(Array.from(event.target.files || []))}/>
        <UploadCloud02 size={16} className="shrink-0 text-fg-quaternary"/>
        <span className="truncate text-secondary">{files.length ? `${files.length} print(s) escolhido(s)` : 'Escolher prints'}</span>
      </label>
      <ReportsFieldInput aria-label="Origem" maxLength={200} value={supplier} onChange={event => setSupplier(event.target.value)} placeholder="Origem, ex.: Meta Ads"/>
      <DateField label="Início do período" hideLabel value={start} onChange={event => setStart(event.target.value)}/>
      <DateField label="Fim do período" hideLabel value={end} onChange={event => setEnd(event.target.value)}/>
      <Button size="md" color="primary" isDisabled={busy || sending || !files.length} isLoading={sending} onPress={send}>Enviar</Button>
    </div>}
  </Card>;
}

function ReviewDrawer({source, data, detail, busy, viewer, refresh, setError, onClose}) {
  const [metrics, setMetrics] = useState([EMPTY_METRIC]);
  const [history, setHistory] = useState([]);
  const [note, setNote] = useState('');
  const [suggesting, setSuggesting] = useState(false);
  const [typeSafe, setTypeSafe] = useState(null);
  const [checking, setChecking] = useState(false);
  const requestRef = useRef(0);
  const contextRef = useRef('');
  contextRef.current = JSON.stringify({clientId: data.client.client_id, reportId: detail.report.id, sourceId: source?.id, metrics});
  const invalidate = () => {requestRef.current += 1; setTypeSafe(null); setChecking(false);};
  useEffect(() => {
    if (!source) return;
    invalidate();
    const requestId = requestRef.current;
    json(`/connect/relatorios/${detail.report.id}/fontes/${source.id}/revisar`).then(body => {
      if (requestId !== requestRef.current) return;
      setMetrics(body.metrics?.length ? body.metrics : [EMPTY_METRIC]); setHistory(body.history || []); setNote('');
    }).catch(failure => setError(failure.message));
  }, [source?.id]);
  const set = (index, key, value) => {invalidate(); setMetrics(current => current.map((item, itemIndex) => itemIndex === index ? {...item, [key]: value} : item));};
  const suggest = async () => {
    const requestId = requestRef.current, context = contextRef.current;
    setSuggesting(true);
    try {
      const payload = new FormData(); payload.append('_csrf', data.csrf);
      const response = await fetch(`/connect/relatorios/${detail.report.id}/fontes/${source.id}/sugerir`, {method: 'POST', credentials: 'same-origin', body: payload});
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `Falha HTTP ${response.status}`);
      if (requestId !== requestRef.current || context !== contextRef.current) return;
      invalidate(); setMetrics(body.suggestion.metrics.length ? body.suggestion.metrics : [EMPTY_METRIC]);
    } catch (failure) {setError(failure.message);} finally {setSuggesting(false);}
  };
  const compare = async () => {
    const requestId = ++requestRef.current, context = contextRef.current;
    setChecking(true); setTypeSafe(null);
    try {
      const body = await json(`/connect/relatorios/${detail.report.id}/fontes/${source.id}/revisar-typesafe`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({metrics})});
      if (requestId === requestRef.current && context === contextRef.current) setTypeSafe(body.review);
    } catch (failure) {if (requestId === requestRef.current) setError(failure.message);} finally {if (requestId === requestRef.current) setChecking(false);}
  };
  const submit = async event => {
    event.preventDefault();
    try {
      const payload = {revision: detail.report.revision, note, metrics: metrics.map(item => ({name: item.name, value: item.raw, unit: item.unit, definition: item.definition, scope: item.scope, evidence: item.evidence}))};
      await json(`/connect/relatorios/${detail.report.id}/fontes/${source.id}/revisar`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify(payload)});
      await refresh(); onClose(); setError('');
    } catch (failure) {setError(failure.message);}
  };
  const judgment = Object.fromEntries((typeSafe?.judgments || []).map(item => [item.index, item]));
  return <ReportsDrawer size="lg" open={Boolean(source)} onOpenChange={value => {if (!value) {invalidate(); onClose();}}} title="Revisar fonte" context={source?.original_name || ''}
    description="Confira cada valor e evidência no print. Sugestões não alteram nada até você confirmar.">
    {source && <form className="untitled-scope flex flex-col gap-6" onSubmit={submit}>
      <img className="max-h-80 w-full rounded-lg object-contain ring-1 ring-secondary" src={`/connect/relatorios/${detail.report.id}/fontes/${source.id}`} alt={`Print ${source.original_name}`}/>
      {!viewer && <div className="flex flex-wrap gap-3">
        <Button size="sm" color="secondary" iconLeading={Stars02} isDisabled={suggesting} isLoading={suggesting} onPress={suggest}>Sugerir valores com IA</Button>
        <Button size="sm" color="secondary" isDisabled={checking || !metrics.some(metric => metric.name && metric.raw && metric.evidence)} isLoading={checking} onPress={compare}>Comparar trechos com TypeSafe</Button>
      </div>}
      {typeSafe && <Callout tone="brand" title="Leitura dos trechos informados">O TypeSafe compara o valor com o texto da evidência; ele não lê a imagem. Confira no print.{typeSafe.omitted_count > 0 && ` ${typeSafe.omitted_count} indicadores ficaram de fora.`}</Callout>}
      <div className="flex flex-col gap-4">{metrics.map((metric, index) => {
        const verdict = judgment[index];
        return <fieldset key={index} className="flex flex-col gap-4 rounded-xl p-4 ring-1 ring-secondary ring-inset">
          <div className="flex items-center justify-between gap-3">
            <legend className="text-sm font-semibold text-primary">Indicador {index + 1}</legend>
            <div className="flex items-center gap-2">
              {verdict && <Badge type="pill-color" size="sm" color={verdict.judgment === 'supported' ? 'success' : verdict.judgment === 'contradicted' ? 'error' : 'warning'}>{verdict.judgment === 'supported' ? 'Trecho compatível' : verdict.judgment === 'contradicted' ? 'Possível divergência' : 'Evidência insuficiente'} · {Math.round(verdict.confidence * 100)}%</Badge>}
              {metrics.length > 1 && !viewer && <Button size="sm" color="tertiary" iconLeading={Trash01} aria-label={`Remover indicador ${index + 1}`} onPress={() => {invalidate(); setMetrics(metrics.filter((_, i) => i !== index));}}/>}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_140px]">
            <ReportsFieldInput label="Nome" required maxLength={120} value={metric.name} onChange={event => set(index, 'name', event.target.value)}/>
            <ReportsFieldInput label="Valor" inputMode="decimal" value={metric.raw || ''} onChange={event => set(index, 'raw', event.target.value)} hint="Vírgula decimal." className="tabular-nums"/>
            <ReportsNativeSelect label="Unidade" value={metric.unit} onChange={event => set(index, 'unit', event.target.value)}>{UNITS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</ReportsNativeSelect>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <ReportsFieldInput label="Definição" required maxLength={1000} value={metric.definition || ''} onChange={event => set(index, 'definition', event.target.value)}/>
            <ReportsFieldInput label="Escopo" required maxLength={1000} value={metric.scope || ''} onChange={event => set(index, 'scope', event.target.value)} placeholder="Ex.: Meta Ads · setembro"/>
          </div>
          <ReportsFieldInput label="Evidência" required maxLength={1000} value={metric.evidence || ''} onChange={event => set(index, 'evidence', event.target.value)} placeholder="Texto exatamente como aparece no print"/>
        </fieldset>;
      })}</div>
      {!viewer && metrics.length < 60 && <div><Button size="sm" color="link-color" iconLeading={Plus} onPress={() => {invalidate(); setMetrics([...metrics, EMPTY_METRIC]);}}>Adicionar indicador</Button></div>}
      {history.length > 0 && <section><h3 className="text-sm font-semibold text-primary">Revisões anteriores</h3>
        <ol className="mt-2 flex flex-col gap-1">{history.map(item => <li key={item.report_revision} className="text-sm text-secondary">v{item.report_revision} · {item.note} <span className="text-xs text-tertiary">· {shortDate(item.created_at)}</span></li>)}</ol></section>}
      {!viewer && <>
        <ReportsTextArea label="Nota da revisão" required maxLength={2000} rows={2} value={note} onChange={event => setNote(event.target.value)}/>
        <DrawerActions onCancel={() => {invalidate(); onClose();}} busy={busy} label="Confirmar e registrar versão"/>
      </>}
    </form>}
  </ReportsDrawer>;
}
