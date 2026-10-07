import React, {useEffect, useState} from 'react';
import {AlertTriangle, Copy01, Link01, Mail01, Stars02} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {CaduTooltip} from '../cadu-design-system/components/CaduTooltip.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {Callout, Card, DrawerActions, EmptyNote, TD, TH} from './ReportsBlocks.jsx';
import {ResultEvidence, ReviewPanel} from './LinkResultEvidence.jsx';
import {LinkTestWizard} from './LinkTestWizard.jsx';
import {json, shortDate} from './reportsCommon.jsx';

import {KindIcon, LINK_KIND_META} from './linkKinds.jsx';
import {LinkEmailDrawer} from './LinkEmailDrawer.jsx';
const MODES = Object.fromEntries(Object.entries(LINK_KIND_META).map(([key, meta]) => [key, meta.label]));
const PAGE_ROLES = {landing: 'entrada', form: 'formulário', thank_you: 'obrigado', content: 'conteúdo', unknown: 'indefinido'};
const scoreColor = score => score >= 80 ? 'success' : score >= 50 ? 'warning' : 'error';
const shareUrl = token => `${location.origin}/connect/public/link-tests/${encodeURIComponent(token)}`;

/** Check a link (destination, media tagging, agent readiness) and tie it to the right campaign. */
export function LinkTester({data, save, busy}) {
  const [form, setForm] = useState({url: '', mode: 'destination'});
  const [result, setResult] = useState(null);
  const [editing, setEditing] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);
  const [guided, setGuided] = useState(false);
  const [emailing, setEmailing] = useState(null);
  const [reviewing, setReviewing] = useState(false);
  const runReview = async () => {
    setReviewing(true);
    try {const body = await save(`/link-tests/${result.run_id}/review`, {}, false); setResult(value => ({...value, review: body.review}));}
    catch (_) { /* The page banner shows the failure. */ } finally {setReviewing(false);}
  };
  const [copied, setCopied] = useState('');
  const sites = data.client_sites || [];
  const canEdit = data.client.role !== 'viewer';
  useEffect(() => {json('/connect/api/v2/reports/ai/status').then(setAiStatus).catch(() => setAiStatus(null));}, []);
  useEffect(() => {setEditing(null);}, [data.client.client_id]);
  const submit = async event => {event.preventDefault(); try {const body = await save('/link-tests', form); setResult(body.result);} catch (_) { /* The page banner shows the failure. */ }};
  const copyShare = async token => {try {await navigator.clipboard.writeText(shareUrl(token)); setCopied(token); setTimeout(() => setCopied(''), 1500);} catch (_) { /* Clipboard may be denied. */ }};

  return <div className="untitled-scope flex flex-col gap-4">
    {guided && <LinkTestWizard sites={sites} initial={form} onClose={() => setGuided(false)}
      onRun={async values => {const body = await save('/link-tests', values); setForm(values); setResult(body.result);}}/>}
    {/* One compact row: link, kind, run. Client sites come as suggestions of the link field. */}
    <form onSubmit={submit} aria-label="Testar link" className="flex flex-wrap items-center gap-2 rounded-xl bg-primary p-2.5 shadow-xs ring-1 ring-secondary">
      <label className="relative flex-1" style={{minWidth: 280}}>
        <span className="sr-only">URL do link</span>
        <Link01 size={16} aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-fg-quaternary"/>
        <input type="url" required maxLength={2048} list="link-tester-sites" value={form.url} onChange={event => setForm({...form, url: event.target.value})}
          placeholder={sites.length ? `Cole o link do anúncio ou escolha ${sites[0].host}` : 'Cole o link do anúncio (https://…?utm_source=…)'}
          style={{paddingLeft: 36, paddingRight: 12}} className="h-10 w-full rounded-lg bg-primary text-sm text-primary shadow-xs ring-1 ring-primary outline-none ring-inset placeholder:text-placeholder focus:ring-2 focus:ring-brand"/>
        <datalist id="link-tester-sites">{sites.map(site => <option key={site.host} value={site.url}>{site.label}</option>)}</datalist>
      </label>
      <div role="radiogroup" aria-label="Análise" className="flex h-10 w-full shrink-0 items-center gap-0.5 sm:w-auto rounded-lg bg-secondary_subtle p-0.5 ring-1 ring-secondary ring-inset">
        {Object.entries(LINK_KIND_META).map(([value, meta]) => <CaduTooltip key={value} label={meta.label}><button type="button" role="radio" aria-checked={form.mode === value} aria-label={meta.label} onClick={() => setForm({...form, mode: value})}
          className={`flex h-full flex-1 items-center justify-center gap-1.5 rounded-md px-2.5 text-sm font-medium ${form.mode === value ? 'bg-primary text-primary shadow-xs' : 'text-tertiary hover:text-secondary'}`}>
          <KindIcon kind={value} size={20}/><span className="whitespace-nowrap">{meta.short}</span></button></CaduTooltip>)}
      </div>
      <Button type="submit" size="md" color="primary" isDisabled={busy} isLoading={busy}>Analisar</Button>
      <CaduTooltip label="Teste guiado: explica cada análise passo a passo"><Button size="md" color="tertiary" iconLeading={Stars02} onPress={() => setGuided(true)}>Guiado</Button></CaduTooltip>
    </form>

    {result && <section className="rounded-xl bg-primary px-6 py-5 shadow-xs ring-1 ring-secondary" aria-label="Resultado">
      <div className="flex flex-wrap items-start gap-5">
        <div className={`flex size-16 shrink-0 flex-col items-center justify-center rounded-full ring-4 ring-inset ${({success: 'ring-[var(--color-fg-success-secondary)]', warning: 'ring-[var(--color-fg-warning-secondary)]', error: 'ring-[var(--color-fg-error-secondary)]'})[scoreColor(result.score)]}`}>
          <span className="text-lg font-semibold text-primary tabular-nums">{result.score}</span><span className="text-xs text-tertiary">/100</span>
        </div>
        <div className="min-w-[16rem] flex-1">
          <div className="flex flex-wrap items-center gap-2"><KindIcon kind={result.kind} size={28}/><h2 className="text-lg font-semibold text-primary">{result.status_label}</h2><Badge type="color" size="sm" color="gray">{MODES[result.kind] || MODES[form.mode]}</Badge></div>
          <p className="mt-1 text-sm text-secondary">{result.summary}</p>
          <p className="mt-2 font-mono text-xs break-all text-tertiary">{result.final_url}</p>
        </div>
        {result.public_token && <div className="flex flex-wrap gap-2">
          {result.run_id && canEdit && <Button size="sm" color="secondary" iconLeading={Stars02} isDisabled={reviewing} isLoading={reviewing} onPress={runReview}>{result.review ? 'Revisar de novo' : 'Revisar com o Cadu'}</Button>}
          {result.run_id && <Button size="sm" color="secondary" iconLeading={Mail01} onPress={() => setEmailing({id: result.run_id, url: result.final_url})}>Enviar por e-mail</Button>}
          <Button size="sm" color="secondary" iconLeading={Copy01} onPress={() => copyShare(result.public_token)}>{copied === result.public_token ? 'Copiado' : 'Copiar link do resultado'}</Button>
        </div>}
      </div>
      {(result.evidence?.screenshot || result.evidence?.screenshot_mobile) && <div className="mt-4 flex items-start gap-3">
        {result.evidence.screenshot && <img src={result.evidence.screenshot} alt="Print da página no desktop" className="min-w-0 flex-1 rounded-lg ring-1 ring-secondary"/>}
        {result.evidence.screenshot_mobile && <img src={result.evidence.screenshot_mobile} alt="Print da página no celular" className="w-[22%] max-w-44 shrink-0 rounded-lg ring-1 ring-secondary"/>}
      </div>}
      <ReviewPanel review={result.review}/>
      <ResultEvidence result={result}/>
      {result.alerts?.length > 0 && <ul className="mt-4 flex flex-col gap-2 border-t border-secondary pt-4">
        {result.alerts.map((alert, index) => <li key={index} className="flex items-start gap-2 text-sm text-secondary"><AlertTriangle size={16} className="mt-0.5 shrink-0 text-fg-warning-primary"/>{alert}</li>)}
      </ul>}
    </section>}

    <Card flush title="Histórico" badge={<Badge type="pill-color" size="sm" color="gray">{data.link_tests.length}</Badge>} description="Associe cada link à campanha certa para que os resultados entrem no relatório dela.">
      {aiStatus && !aiStatus.configured && <div className="border-b border-secondary px-6 py-3"><Callout>A sugestão por TypeSafe ainda não está configurada nas Integrações do Cadu. IDs exatos de campanha continuam reconhecidos.</Callout></div>}
      {data.link_tests.length ? <><ul className="divide-y divide-secondary md:hidden">{data.link_tests.map(item => <li key={item.id} className="flex items-start gap-3 px-4 py-3">
        <KindIcon kind={item.mode} size={28}/>
        <div className="min-w-0 flex-1"><p className="truncate font-mono text-xs text-primary">{item.final_url}</p>
          <p className="mt-0.5 text-xs text-tertiary">{item.score}/100 · {item.status_label} · {shortDate(item.created_at)}</p>
          <p className="mt-0.5 text-xs text-tertiary">{item.campaign_name || 'Sem campanha'}</p></div>
        <div className="flex shrink-0 gap-1">{item.public_token && <Button size="sm" color="tertiary" iconLeading={Copy01} aria-label="Copiar link do resultado" onPress={() => copyShare(item.public_token)}/>}
          <Button size="sm" color="secondary" onPress={() => setEditing(item)}>{item.campaign_name ? 'Alterar' : 'Associar'}</Button></div>
      </li>)}</ul>
      <div className="relative hidden overflow-x-auto md:block"><table className="w-full min-w-[900px]">
        <thead><tr><th className={TH}>Destino</th><th className={TH}>Resultado</th><th className={TH}>Campanha</th><th className={TH}>Data</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
        <tbody>{data.link_tests.map(item => <tr key={item.id} className="hover:bg-primary_hover">
          <td className={`${TD} max-w-72`}><div className="flex items-center gap-2"><KindIcon kind={item.mode} size={24}/><div className="min-w-0"><p className="truncate font-mono text-xs text-primary" title={item.final_url}>{item.final_url}</p><p className="text-xs text-tertiary">{MODES[item.mode] || item.mode}</p></div></div></td>
          <td className={TD}><BadgeWithDot type="pill-color" size="sm" color={scoreColor(item.score)}>{item.score}/100</BadgeWithDot><p className="mt-1 text-xs text-tertiary">{item.status_label}</p></td>
          <td className={`${TD} min-w-48`}>{item.campaign_name ? <><p className="font-medium text-primary">{item.campaign_name}</p>{item.report_name && <p className="text-xs text-tertiary">{item.report_name}</p>}</> : <span className="text-quaternary">Sem campanha</span>}</td>
          <td className={`${TD} whitespace-nowrap`}>{shortDate(item.created_at)}</td>
          <td className={`${TD} text-right whitespace-nowrap`}>
            {item.public_token && <CaduTooltip label={copied === item.public_token ? 'Copiado' : 'Copiar link do resultado'}><Button size="sm" color="tertiary" iconLeading={Copy01} aria-label="Copiar link do resultado" onPress={() => copyShare(item.public_token)}/></CaduTooltip>}
            {canEdit && item.public_token && <CaduTooltip label="Enviar por e-mail"><Button className="ml-2" size="sm" color="tertiary" iconLeading={Mail01} aria-label="Enviar por e-mail" onPress={() => setEmailing({id: item.id, url: item.final_url})}/></CaduTooltip>}
            <Button className="ml-2" size="sm" color="secondary" onPress={() => setEditing(item)}>{item.campaign_name ? 'Alterar campanha' : 'Associar'}</Button>
          </td>
        </tr>)}</tbody>
      </table></div></> : <EmptyNote title="Nenhum teste ainda">Os links testados neste cliente aparecem aqui.</EmptyNote>}
    </Card>
    <LinkEmailDrawer run={emailing} data={data} save={save} busy={busy} onClose={() => setEmailing(null)}/>
    <AssociationDrawer run={editing} data={data} save={save} busy={busy} canEdit={canEdit} onClose={() => setEditing(null)}/>
  </div>;
}

function AssociationDrawer({run, data, save, busy, canEdit, onClose}) {
  const [campaignId, setCampaignId] = useState('');
  const [reportId, setReportId] = useState('');
  const [suggestion, setSuggestion] = useState(null);
  const [history, setHistory] = useState(null);
  useEffect(() => {
    if (!run) return;
    setCampaignId(run.media_campaign_id ? String(run.media_campaign_id) : ''); setReportId(run.report_workspace_id ? String(run.report_workspace_id) : '');
    setSuggestion(null); setHistory(null);
    json(`/connect/api/v2/reports/link-tests/${run.id}/association-history`).then(body => setHistory(body.history || [])).catch(() => setHistory([]));
  }, [run]);
  const selected = data.campaigns.find(item => String(item.id) === campaignId);
  const reports = data.reports.filter(item => !item.media_campaign_id || String(item.media_campaign_id) === campaignId).filter(item => !item.account_id || item.account_id === selected?.account_id);
  const suggest = async () => {
    try {const body = await save(`/link-tests/${run.id}/suggest-campaign`, {}, false); setSuggestion(body); if (body.suggestion) {setCampaignId(String(body.suggestion.id)); setReportId('');}}
    catch (_) { /* The page banner shows the failure. */ }
  };
  const submit = async event => {
    event.preventDefault();
    try {await save(`/link-tests/${run.id}/association`, {campaign_id: campaignId || null, report_id: reportId || null}); onClose();} catch (_) { /* The page banner shows the failure. */ }
  };
  const how = suggestion?.model === 'exact_id' ? 'ID externo exato' : suggestion?.model === 'exact_name' ? 'nome exato' : `concentração ${Math.round((suggestion?.confidence || 0) * 100)}%`;
  return <ReportsDrawer open={Boolean(run)} onOpenChange={value => {if (!value) onClose();}} title="Associar link à campanha" context={run?.final_url || ''} description="A decisão fica registrada com data e autor.">
    <form className="untitled-scope flex flex-col gap-6" onSubmit={submit}>
      {canEdit && (suggestion ? <Callout tone={suggestion.suggestion ? 'brand' : 'gray'} title={suggestion.suggestion ? `Sugestão: ${suggestion.suggestion.name}` : 'Nenhuma campanha sugerida'}>
        {suggestion.suggestion ? `Por ${how}. Confira antes de salvar.` : suggestion.reason}
        {suggestion.page_role && <p className="mt-1">Tipo provável de página: {PAGE_ROLES[suggestion.page_role] || suggestion.page_role}.</p>}
      </Callout> : <div className="flex items-center justify-between gap-3 rounded-lg bg-secondary_subtle p-4 ring-1 ring-secondary ring-inset">
        <p className="text-sm text-secondary">Deixe o Cadu sugerir a campanha a partir do link.</p>
        <Button size="sm" color="secondary" iconLeading={Stars02} isDisabled={busy} onPress={suggest}>Sugerir</Button>
      </div>)}
      <ReportsNativeSelect label="Campanha" disabled={!canEdit} value={campaignId} onChange={event => {setCampaignId(event.target.value); setReportId('');}}>
        <option value="">Sem campanha</option>{data.campaigns.map(item => <option key={item.id} value={item.id}>{item.name} · {item.account_name || 'manual'}</option>)}
      </ReportsNativeSelect>
      <ReportsNativeSelect label="Relatório" hint="Opcional. Só relatórios da mesma campanha e conta." value={reportId} disabled={!canEdit || !campaignId} onChange={event => setReportId(event.target.value)}>
        <option value="">Sem relatório</option>{reports.map(item => <option key={item.id} value={item.id}>{item.campaign_name}</option>)}
      </ReportsNativeSelect>
      <section>
        <h3 className="text-sm font-semibold text-primary">Decisões anteriores</h3>
        {history === null ? <p className="mt-2 text-sm text-tertiary">Carregando…</p> : history.length ? <ol className="mt-2 flex flex-col gap-1.5">{history.map((item, index) => <li key={`${item.decided_at}-${index}`} className="text-sm text-secondary">
          <span className="text-tertiary">{shortDate(item.decided_at)}</span> · {item.action === 'clear' ? 'Associação removida' : `${data.campaigns.find(entry => entry.id === item.campaign_id)?.name || `Campanha #${item.campaign_id}`}${item.report_id ? ` · relatório #${item.report_id}` : ''}`}
        </li>)}</ol> : <p className="mt-2 text-sm text-tertiary">Nenhuma decisão anterior.</p>}
      </section>
      {canEdit && <DrawerActions onCancel={onClose} busy={busy} label={campaignId ? 'Confirmar associação' : 'Remover associação'}/>}
    </form>
  </ReportsDrawer>;
}
