import React, {useEffect, useState} from 'react';
import {ArrowLeft, Copy01, Mail01, Stars02} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {KindIcon, LINK_KIND_META} from './linkKinds.jsx';
import {ResultEvidence, ReviewPanel} from './LinkResultEvidence.jsx';
import {LegacyAnalysis, legacyTabs} from './LinkLegacyAnalysis.jsx';
import {LinkEmailDrawer} from './LinkEmailDrawer.jsx';
import {EmptyNote} from './ReportsBlocks.jsx';
import {json, shortDate} from './reportsCommon.jsx';
import {APP_BASE, navigateOnClick} from './shell/routes.js';
import {customerSearch} from './shell/customerScope.js';

const API = '/connect/api/v2/reports/link-tests';
const scoreColor = score => score >= 80 ? 'success' : score >= 50 ? 'warning' : 'error';
export const detailHref = id => `${APP_BASE}/tools/link-tester/${encodeURIComponent(id)}${customerSearch()}`;
const listHref = () => `${APP_BASE}/tools/link-tester${customerSearch()}`;
const shareUrl = token => `${location.origin}/connect/public/link-tests/${encodeURIComponent(token)}`;
const fullDate = value => value ? new Date(value).toLocaleString('pt-BR', {dateStyle: 'medium', timeStyle: 'short'}) : '–';

function Tabs({tabs, value, onChange}) {
  return <div role="tablist" aria-label="Seções do resultado" className="flex gap-1 overflow-x-auto border-b border-secondary">
    {tabs.map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={value === key} onClick={() => onChange(key)}
      className={`-mb-px shrink-0 border-b-2 px-3 py-2.5 text-sm font-medium whitespace-nowrap ${value === key ? 'border-[var(--color-fg-brand-primary)] text-brand-secondary' : 'border-transparent text-tertiary hover:text-secondary'}`}>{label}</button>)}
  </div>;
}

function Screenshots({desktop, mobile, note}) {
  if (!desktop && !mobile) return <EmptyNote title="Sem print">{note || 'Esta análise não tem print guardado.'}</EmptyNote>;
  return <div className="flex flex-col items-start gap-4 md:flex-row">
    {desktop && <figure className="min-w-0 flex-1"><img src={desktop} alt="Print da página no desktop" className="w-full rounded-lg ring-1 ring-secondary" loading="lazy"/><figcaption className="mt-1 text-xs text-tertiary">Desktop</figcaption></figure>}
    {mobile && <figure className="w-full max-w-60 shrink-0"><img src={mobile} alt="Print da página no celular" className="w-full rounded-lg ring-1 ring-secondary" loading="lazy"/><figcaption className="mt-1 text-xs text-tertiary">Celular</figcaption></figure>}
  </div>;
}

function DomainRuns({runs}) {
  if (!runs?.length) return null;
  return <section className="rounded-xl bg-primary p-5 shadow-xs ring-1 ring-secondary">
    <h2 className="text-sm font-semibold text-primary">Outras análises deste domínio</h2>
    <ol className="mt-3 flex flex-col divide-y divide-secondary">{runs.map(item => <li key={item.id}>
      <a href={detailHref(item.id)} onClick={event => navigateOnClick(event, detailHref(item.id))} className="flex items-center gap-3 py-2.5 text-sm no-underline hover:bg-primary_hover">
        <KindIcon kind={item.mode} size={22}/><span className="w-24 shrink-0 text-tertiary">{shortDate(item.created_at)}</span>
        <BadgeWithDot type="pill-color" size="sm" color={scoreColor(item.score)}>{item.score}/100</BadgeWithDot>
        <span className="min-w-0 flex-1 truncate text-secondary">{item.status_label}</span>
        <span className="shrink-0 text-xs text-tertiary">{item.author || ''}{item.source === 'cadu_php' ? ' · Cadu anterior' : ''}</span>
      </a></li>)}</ol>
  </section>;
}

/** Full result of one Link Tester run inside the tool. The public link and the e-mail are actions, not the only view. */
export function LinkTestDetail({id, data, save, busy, onAssociate}) {
  const [run, setRun] = useState(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('resumo');
  const [emailing, setEmailing] = useState(null);
  const [reviewing, setReviewing] = useState(false);
  const [copied, setCopied] = useState(false);
  const canEdit = data.client.role !== 'viewer';
  useEffect(() => {
    setRun(null); setError(''); setTab('resumo');
    json(`${API}/${encodeURIComponent(id)}?client_id=${encodeURIComponent(data.client.client_id)}`).then(body => setRun(body.run)).catch(failure => setError(failure.message || 'Não foi possível abrir esta análise.'));
  }, [id, data.client.client_id]);

  const back = <a href={listHref()} onClick={event => navigateOnClick(event, listHref())} className="inline-flex items-center gap-1.5 text-sm font-medium text-tertiary no-underline hover:text-secondary"><ArrowLeft size={16}/>Todas as análises</a>;
  if (error) return <div className="untitled-scope flex flex-col gap-4">{back}<EmptyNote title="Análise indisponível">{error}</EmptyNote></div>;
  if (!run) return <div className="untitled-scope flex flex-col gap-4">{back}<p className="text-sm text-tertiary">Carregando a análise…</p></div>;

  const legacy = run.source === 'cadu_php';
  const result = run.result || {};
  const evidence = result.evidence || {};
  const kind = run.kind || run.mode;
  const tabs = legacy ? [...legacyTabs(run.analysis || {}), ['print', 'Print']]
    : [['resumo', 'Resumo'], ['analise', 'Análise completa'], ['print', 'Print'], ...(result.review ? [['revisao', 'Revisão do Cadu']] : [])];
  const runReview = async () => {
    setReviewing(true);
    try {const body = await save(`/link-tests/${run.id}/review`, {}, false); setRun(value => ({...value, result: {...value.result, review: body.review}})); setTab('revisao');}
    catch (_) { /* The page banner shows the failure. */ } finally {setReviewing(false);}
  };
  const copyShare = async () => {try {await navigator.clipboard.writeText(shareUrl(run.public_token)); setCopied(true); setTimeout(() => setCopied(false), 1500);} catch (_) { /* Clipboard may be denied. */ }};

  return <div className="untitled-scope flex flex-col gap-4">
    {back}
    <section className="rounded-xl bg-primary px-6 py-5 shadow-xs ring-1 ring-secondary" aria-label="Resultado">
      <div className="flex flex-wrap items-start gap-5">
        <div className={`flex size-16 shrink-0 flex-col items-center justify-center rounded-full ring-4 ring-inset ${({success: 'ring-[var(--color-fg-success-secondary)]', warning: 'ring-[var(--color-fg-warning-secondary)]', error: 'ring-[var(--color-fg-error-secondary)]'})[scoreColor(run.score)]}`}>
          <span className="text-lg font-semibold text-primary tabular-nums">{run.score ?? '–'}</span><span className="text-xs text-tertiary">/100</span>
        </div>
        <div className="min-w-[16rem] flex-1">
          <div className="flex flex-wrap items-center gap-2"><KindIcon kind={kind} size={28}/><h1 className="text-lg font-semibold text-primary">{run.status_label}</h1>
            <Badge type="color" size="sm" color="gray">{legacy ? run.type_label : LINK_KIND_META[kind]?.label}</Badge>
            {legacy && <Badge type="color" size="sm" color="warning">Cadu anterior</Badge>}</div>
          {result.summary && <p className="mt-1 text-sm text-secondary">{result.summary}</p>}
          <p className="mt-2 font-mono text-xs break-all text-tertiary">{run.final_url}</p>
          <p className="mt-2 text-xs text-tertiary">Testado por <strong className="font-medium text-secondary">{run.author || 'usuário removido'}</strong> em {fullDate(run.created_at)}
            {run.campaign_name ? <> · campanha <strong className="font-medium text-secondary">{run.campaign_name}</strong></> : null}</p>
        </div>
        {!legacy && <div className="flex flex-wrap gap-2">
          {canEdit && <Button size="sm" color="secondary" iconLeading={Stars02} isDisabled={reviewing} isLoading={reviewing} onPress={runReview}>{result.review ? 'Revisar de novo' : 'Revisar com o Cadu'}</Button>}
          {canEdit && <Button size="sm" color="secondary" iconLeading={Mail01} onPress={() => setEmailing({id: run.id, url: run.final_url})}>Enviar por e-mail</Button>}
          {run.public_token && <Button size="sm" color="secondary" iconLeading={Copy01} onPress={copyShare}>{copied ? 'Copiado' : 'Link público'}</Button>}
          {canEdit && onAssociate && <Button size="sm" color="secondary" onPress={() => onAssociate({...run, campaign_name: run.campaign_name})}>{run.campaign_name ? 'Alterar campanha' : 'Associar campanha'}</Button>}
        </div>}
      </div>
    </section>

    <Tabs tabs={tabs} value={tabs.some(([key]) => key === tab) ? tab : tabs[0][0]} onChange={setTab}/>
    <div role="tabpanel">
      {legacy && tab !== 'print' && <LegacyAnalysis analysis={run.analysis} tab={tabs.some(([key]) => key === tab) ? tab : 'resumo'}/>}
      {legacy && tab === 'print' && <Screenshots desktop={run.screenshots?.desktop} mobile={run.screenshots?.mobile} note="O Cadu anterior não guardou print desta análise."/>}
      {!legacy && tab === 'resumo' && <section className="rounded-xl bg-primary p-5 ring-1 ring-secondary">
        <h2 className="text-sm font-semibold text-primary">Resultado preliminar</h2>
        <ul className="mt-3 flex flex-col divide-y divide-secondary">{(result.highlights || []).map((item, index) => <li key={index} className="flex items-start gap-3 py-2 text-sm">
          <span className={`mt-1.5 size-2.5 shrink-0 rounded-full ${item.tone === 'ok' ? 'bg-[var(--color-fg-success-secondary)]' : item.tone === 'bad' ? 'bg-[var(--color-fg-error-secondary)]' : 'bg-[var(--color-fg-warning-secondary)]'}`}/>
          <span className="text-secondary">{item.text}</span></li>)}</ul>
        {(result.alerts || []).length > 0 && <><h3 className="mt-4 text-sm font-semibold text-primary">Pontos de atenção</h3><ul className="mt-2 list-disc pl-5 text-sm text-secondary">{result.alerts.map(alert => <li key={alert}>{alert}</li>)}</ul></>}
      </section>}
      {!legacy && tab === 'analise' && <section className="rounded-xl bg-primary p-5 ring-1 ring-secondary"><ResultEvidence result={result}/></section>}
      {!legacy && tab === 'print' && <Screenshots desktop={evidence.screenshot} mobile={evidence.screenshot_mobile} note={evidence.capture_note}/>}
      {!legacy && tab === 'revisao' && <ReviewPanel review={result.review}/>}
    </div>
    <DomainRuns runs={run.domain_runs}/>
    <LinkEmailDrawer run={emailing} data={data} save={save} busy={busy} onClose={() => setEmailing(null)}/>
  </div>;
}
