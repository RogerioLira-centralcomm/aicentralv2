import React, {useEffect, useState} from 'react';
import {ArrowLeft, Copy01, Mail01, Stars02} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {KindIcon} from './linkKinds.jsx';
import {LinkReportView} from './LinkReportView.jsx';
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
  const [emailing, setEmailing] = useState(null);
  const [reviewing, setReviewing] = useState(false);
  const [copied, setCopied] = useState(false);
  const canEdit = data.client.role !== 'viewer';
  useEffect(() => {
    setRun(null); setError('');
    json(`${API}/${encodeURIComponent(id)}?client_id=${encodeURIComponent(data.client.client_id)}`).then(body => setRun(body.run)).catch(failure => setError(failure.message || 'Não foi possível abrir esta análise.'));
  }, [id, data.client.client_id]);

  const back = <a href={listHref()} onClick={event => navigateOnClick(event, listHref())} className="inline-flex items-center gap-1.5 text-sm font-medium text-tertiary no-underline hover:text-secondary"><ArrowLeft size={16}/>Todas as análises</a>;
  if (error) return <div className="untitled-scope flex flex-col gap-4">{back}<EmptyNote title="Análise indisponível">{error}</EmptyNote></div>;
  if (!run) return <div className="untitled-scope flex flex-col gap-4">{back}<p className="text-sm text-tertiary">Carregando a análise…</p></div>;

  const legacy = run.source === 'cadu_php';
  const result = run.result || {};
  const runReview = async () => {
    setReviewing(true);
    try {
      await save(`/link-tests/${run.id}/review`, {}, false);
      const body = await json(`${API}/${encodeURIComponent(id)}?client_id=${encodeURIComponent(data.client.client_id)}`);
      setRun(body.run);
    } catch (_) { /* The page banner shows the failure. */ } finally {setReviewing(false);}
  };
  const copyShare = async () => {try {await navigator.clipboard.writeText(shareUrl(run.public_token)); setCopied(true); setTimeout(() => setCopied(false), 1500);} catch (_) { /* Clipboard may be denied. */ }};
  const actions = <>
    {!legacy && canEdit && <Button size="sm" color="secondary" iconLeading={Stars02} isDisabled={reviewing} isLoading={reviewing} onPress={runReview}>{result.review ? 'Revisar de novo' : 'Revisar com o Cadu'}</Button>}
    {!legacy && canEdit && <Button size="sm" color="secondary" iconLeading={Mail01} onPress={() => setEmailing({id: run.id, url: run.final_url})}>Enviar por e-mail</Button>}
    {run.public_token && <Button size="sm" color="secondary" iconLeading={Copy01} onPress={copyShare}>{copied ? 'Copiado' : 'Copiar link público'}</Button>}
    {run.public_token && <a href={shareUrl(run.public_token)} target="_blank" rel="noreferrer noopener" className="inline-flex h-9 items-center rounded-lg px-3 text-sm font-semibold text-tertiary no-underline ring-1 ring-secondary ring-inset hover:text-secondary">Abrir link público</a>}
    {!legacy && canEdit && onAssociate && <Button size="sm" color="secondary" onPress={() => onAssociate({...run, campaign_name: run.campaign_name})}>{run.campaign_name ? 'Alterar campanha' : 'Associar campanha'}</Button>}
  </>;

  return <div className="untitled-scope flex flex-col gap-4">
    {back}
    <LinkReportView report={run.report} actions={actions}/>
    <DomainRuns runs={run.domain_runs}/>
    <LinkEmailDrawer run={emailing} data={data} save={save} busy={busy} onClose={() => setEmailing(null)}/>
  </div>;
}
