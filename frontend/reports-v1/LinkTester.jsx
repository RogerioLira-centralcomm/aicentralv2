import React, {useEffect, useState} from 'react';
import {AlertTriangle, Copy01, Link01, Stars02} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {CaduTooltip} from '../cadu-design-system/components/CaduTooltip.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {Callout, Card, DrawerActions, EmptyNote, TD, TH} from './ReportsBlocks.jsx';
import {json, shortDate} from './reportsCommon.jsx';

const MODES = {destination: 'Destino e redirecionamentos', media: 'Medição de mídia', agentic: 'Presença para agentes'};
const PAGE_ROLES = {landing: 'entrada', form: 'formulário', thank_you: 'obrigado', content: 'conteúdo', unknown: 'indefinido'};
const scoreColor = score => score >= 80 ? 'success' : score >= 50 ? 'warning' : 'error';
const shareUrl = token => `${location.origin}/connect/public/link-tests/${encodeURIComponent(token)}`;

/** Check a link (destination, media tagging, agent readiness) and tie it to the right campaign. */
export function LinkTester({data, save, busy}) {
  const [form, setForm] = useState({url: '', mode: 'destination'});
  const [result, setResult] = useState(null);
  const [editing, setEditing] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);
  const [copied, setCopied] = useState('');
  const canEdit = data.client.role !== 'viewer';
  useEffect(() => {json('/connect/api/v2/reports/ai/status').then(setAiStatus).catch(() => setAiStatus(null));}, []);
  useEffect(() => {setEditing(null);}, [data.client.client_id]);
  const submit = async event => {event.preventDefault(); try {const body = await save('/link-tests', form); setResult(body.result);} catch (_) { /* The page banner shows the failure. */ }};
  const copyShare = async token => {try {await navigator.clipboard.writeText(shareUrl(token)); setCopied(token); setTimeout(() => setCopied(''), 1500);} catch (_) { /* Clipboard may be denied. */ }};

  return <div className="untitled-scope flex flex-col gap-6">
    <Card title="Testar link" description="Cole o link do anúncio. A análise segue redirecionamentos e confere o que chega ao site.">
      <form className="grid items-end gap-4 lg:grid-cols-[minmax(0,1fr)_260px_auto]" onSubmit={submit}>
        <ReportsFieldInput label="URL" required type="url" maxLength={2048} value={form.url} onChange={event => setForm({...form, url: event.target.value})} placeholder="https://exemplo.com/pagina?utm_source=…"
          leading={<Link01 size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/>
        <ReportsNativeSelect label="Análise" value={form.mode} onChange={event => setForm({...form, mode: event.target.value})}>
          {Object.entries(MODES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </ReportsNativeSelect>
        <Button type="submit" size="md" color="primary" isDisabled={busy} isLoading={busy}>Analisar link</Button>
      </form>
    </Card>

    {result && <section className="rounded-xl bg-primary px-6 py-5 shadow-xs ring-1 ring-secondary" aria-label="Resultado">
      <div className="flex flex-wrap items-start gap-5">
        <div className={`flex size-16 shrink-0 flex-col items-center justify-center rounded-full ring-4 ring-inset ${({success: 'ring-[var(--color-fg-success-secondary)]', warning: 'ring-[var(--color-fg-warning-secondary)]', error: 'ring-[var(--color-fg-error-secondary)]'})[scoreColor(result.score)]}`}>
          <span className="text-lg font-semibold text-primary tabular-nums">{result.score}</span><span className="text-xs text-tertiary">/100</span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold text-primary">{result.status_label}</h2><Badge type="color" size="sm" color="gray">{MODES[result.kind] || MODES[form.mode]}</Badge></div>
          <p className="mt-1 text-sm text-secondary">{result.summary}</p>
          <p className="mt-2 font-mono text-xs break-all text-tertiary">{result.final_url}</p>
        </div>
        {result.public_token && <Button size="sm" color="secondary" iconLeading={Copy01} onPress={() => copyShare(result.public_token)}>{copied === result.public_token ? 'Copiado' : 'Copiar link do resultado'}</Button>}
      </div>
      {result.alerts?.length > 0 && <ul className="mt-4 flex flex-col gap-2 border-t border-secondary pt-4">
        {result.alerts.map((alert, index) => <li key={index} className="flex items-start gap-2 text-sm text-secondary"><AlertTriangle size={16} className="mt-0.5 shrink-0 text-fg-warning-primary"/>{alert}</li>)}
      </ul>}
    </section>}

    <Card flush title="Histórico" badge={<Badge type="pill-color" size="sm" color="gray">{data.link_tests.length}</Badge>} description="Associe cada link à campanha certa para que os resultados entrem no relatório dela.">
      {aiStatus && !aiStatus.configured && <div className="border-b border-secondary px-6 py-3"><Callout>A sugestão por TypeSafe ainda não está configurada nas Integrações do Cadu. IDs exatos de campanha continuam reconhecidos.</Callout></div>}
      {data.link_tests.length ? <div className="overflow-x-auto"><table className="w-full min-w-[900px]">
        <thead><tr><th className={TH}>Destino</th><th className={TH}>Resultado</th><th className={TH}>Campanha</th><th className={TH}>Data</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
        <tbody>{data.link_tests.map(item => <tr key={item.id} className="hover:bg-primary_hover">
          <td className={`${TD} max-w-72`}><p className="truncate font-mono text-xs text-primary" title={item.final_url}>{item.final_url}</p><p className="text-xs text-tertiary">{MODES[item.mode] || item.mode}</p></td>
          <td className={TD}><BadgeWithDot type="pill-color" size="sm" color={scoreColor(item.score)}>{item.score}/100</BadgeWithDot><p className="mt-1 text-xs text-tertiary">{item.status_label}</p></td>
          <td className={`${TD} min-w-48`}>{item.campaign_name ? <><p className="font-medium text-primary">{item.campaign_name}</p>{item.report_name && <p className="text-xs text-tertiary">{item.report_name}</p>}</> : <span className="text-quaternary">Sem campanha</span>}</td>
          <td className={`${TD} whitespace-nowrap`}>{shortDate(item.created_at)}</td>
          <td className={`${TD} text-right whitespace-nowrap`}>
            {item.public_token && <CaduTooltip label={copied === item.public_token ? 'Copiado' : 'Copiar link do resultado'}><Button size="sm" color="tertiary" iconLeading={Copy01} aria-label="Copiar link do resultado" onPress={() => copyShare(item.public_token)}/></CaduTooltip>}
            <Button className="ml-2" size="sm" color="secondary" onPress={() => setEditing(item)}>{item.campaign_name ? 'Alterar campanha' : 'Associar'}</Button>
          </td>
        </tr>)}</tbody>
      </table></div> : <EmptyNote title="Nenhum teste ainda">Os links testados neste cliente aparecem aqui.</EmptyNote>}
    </Card>
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
    json(`/connect/api/v2/reports/link-tests/${run.id}/association-history?client_id=${data.client.client_id}`).then(body => setHistory(body.history || [])).catch(() => setHistory([]));
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
