import React, {useEffect, useState} from 'react';
import {ArrowUpRight, Image01} from '@untitledui/icons';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {ReportsNativeSelect} from '../../ReportsNativeSelect.jsx';
import {ReportsTextArea} from '../../ReportsTextArea.jsx';
import {json, reportUrl} from '../../reportsCommon.jsx';
import {friendlyDateTime} from '../../friendlyDates.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {platformName} from '../../shell/media.jsx';
import {useReportsContext} from '../../shell/context.js';
import {DataTable, EmptyState, ErrorState, LoadingState, Section} from '../../shell/primitives.jsx';

const STATUS = {draft: ['Rascunho', 'gray'], active: ['Em criação', 'warning'], ready: ['Pronto', 'success'], finalized: ['Finalizado', 'success'], finalizing: ['Finalizando', 'warning'], failed: ['Falhou', 'error'], cancelled: ['Cancelado', 'gray'], archived: ['Arquivado', 'gray']};
const ACTIVE = ['ENABLED', 'active'];

/**
 * "Que peça criar para cada campanha?" — the brief comes from what the campaign shows (intent that converts,
 * landing page, performance) and opens in the Studio with the brand and project, where direction, generation
 * and credits are handled.
 */
export function MediaCreatives({data}) {
  const {scope} = useReportsContext();
  // The header's source/campaign narrows which campaigns can be picked here.
  const campaigns = data.campaigns.filter(item => (!scope.account || String(item.account_id) === scope.account) && (!scope.campaign || String(item.id) === scope.campaign)).sort((a, b) => Number(ACTIVE.includes(b.status)) - Number(ACTIVE.includes(a.status)));
  const [campaignId, setCampaignId] = useState(() => new URLSearchParams(location.search).get('campaign') || scope.campaign || String(campaigns[0]?.id || ''));
  useEffect(() => {if (scope.campaign) setCampaignId(scope.campaign); else if (!campaigns.some(item => String(item.id) === campaignId)) setCampaignId(String(campaigns[0]?.id || ''));}, [scope.account, scope.campaign]);
  const [format, setFormat] = useState('feed');
  const [angle, setAngle] = useState('benefit');
  const [context, retryContext] = useApi(campaignId ? apiUrl(`/creatives/campaigns/${campaignId}`, {format, angle}) : '');
  const [sessions, retrySessions] = useApi(apiUrl('/creatives/sessions'));
  const [prompt, setPrompt] = useState('');
  const [edited, setEdited] = useState(false);
  const [brandRef, setBrandRef] = useState('');
  const [projectRef, setProjectRef] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const body = context.body;
  // A new suggestion replaces the text only while the person has not edited it.
  useEffect(() => {if (body && !edited) setPrompt(body.prompt);}, [body?.prompt]);
  useEffect(() => {if (body) {setBrandRef(body.brand_ref || ''); setProjectRef(body.project_ref || '');}}, [body?.campaign?.id]);
  useEffect(() => {setEdited(false);}, [campaignId]);
  const viewer = data.client.role === 'viewer';
  const open = async () => {
    setSending(true); setError('');
    // Open the tab inside the click so the browser does not block it, then point it at the Studio session.
    const tab = window.open('', '_blank');
    try {
      const result = await json('/connect/api/v2/reports/creatives/studio', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf},
        body: JSON.stringify({campaign_id: Number(campaignId), prompt, brand_ref: brandRef, project_ref: projectRef, format, request_id: crypto.randomUUID?.()})});
      if (tab) tab.location.href = result.studio_url; else window.location.assign(result.studio_url);
      retrySessions();
    } catch (failure) {tab?.close(); setError(failure.message);} finally {setSending(false);}
  };
  if (!campaigns.length) return <EmptyState title="Nenhuma campanha cadastrada" description="Os briefings de criativo partem dos dados de uma campanha. Cadastre ou importe campanhas primeiro."
    action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('media/campaigns')}>Ver campanhas</ReportsActionButton>}/>;
  const brand = body?.brands.find(item => item.ref === brandRef);
  const signals = body?.signals;
  return <div className="rs-stack">
    <Section title="Criar com o Studio" description="O briefing nasce dos dados da campanha. A direção, a geração e os créditos ficam no Studio.">
      <div className="rs-creative">
        <div className="rs-creative__form">
          <label className="rs-field"><span>Campanha</span>
            <ReportsNativeSelect value={campaignId} onChange={event => setCampaignId(event.target.value)}>
              {campaigns.map(item => <option key={item.id} value={item.id}>{item.name} · {platformName(item.platform)}{ACTIVE.includes(item.status) ? '' : ' (pausada)'}</option>)}
            </ReportsNativeSelect></label>
          {context.error ? <ErrorState message={context.error} onRetry={retryContext}/> : !body ? <LoadingState rows={4}/> : <>
            <div className="rs-field-row">
              <label className="rs-field"><span>Marca</span>
                <ReportsNativeSelect value={brandRef} onChange={event => setBrandRef(event.target.value)}>
                  <option value="">Sem marca (sem identidade visual)</option>
                  {body.brands.map(item => <option key={item.ref} value={item.ref}>{item.name}</option>)}
                </ReportsNativeSelect></label>
              <label className="rs-field"><span>Projeto</span>
                <ReportsNativeSelect value={projectRef} onChange={event => setProjectRef(event.target.value)}>
                  <option value="">Sem projeto (criação pessoal)</option>
                  {body.projects.map(item => <option key={item.ref} value={item.ref}>{item.name}</option>)}
                </ReportsNativeSelect></label>
            </div>
            <div className="rs-field"><span>Formato</span><div className="rs-segmented" role="group" aria-label="Formato">{body.formats.map(item => <button type="button" key={item.key} aria-pressed={format === item.key} onClick={() => setFormat(item.key)}>{item.label}</button>)}</div></div>
            <div className="rs-field"><span>Ângulo</span><div className="rs-segmented" role="group" aria-label="Ângulo">{body.angles.map(item => <button type="button" key={item.key} aria-pressed={angle === item.key} onClick={() => setAngle(item.key)}>{item.label}</button>)}</div></div>
            <label className="rs-field"><span>Briefing {edited && <ReportsActionButton color="link-color" size="sm" className="rs-link-button" onClick={() => {setEdited(false); setPrompt(body.prompt);}}>Restaurar sugestão</ReportsActionButton>}</span>
              <ReportsTextArea rows={9} maxLength={4000} value={prompt} onChange={event => {setPrompt(event.target.value); setEdited(true);}} aria-label="Briefing do criativo"/></label>
            {error && <p className="rs-error-inline" role="alert">{error}</p>}
            <div className="rs-actions">
              <ReportsActionButton color="primary" onClick={open} disabled={viewer || sending || prompt.trim().length < 3} iconTrailing={ArrowUpRight}>{sending ? 'Abrindo o Studio…' : 'Abrir no Studio'}</ReportsActionButton>
              <span className="rs-muted">{viewer ? 'Seu acesso permite consultar, sem criar peças.' : brand ? `A marca ${brand.name}${projectRef ? ' e o projeto' : ''} seguem com o pedido.` : 'Sem marca, a peça sai sem logo e cores oficiais.'}</span>
            </div>
          </>}
        </div>
        <aside className="rs-creative__signals" aria-label="O que os dados mostram">
          <h3>O que os dados mostram</h3>
          {!signals ? <LoadingState rows={3}/> : <dl>
            <div><dt>Página de destino</dt><dd>{signals.landing_page || 'Sem dado de página de destino'}</dd></div>
            <div><dt>Buscas que converteram</dt><dd>{signals.terms.length ? <ul className="rs-chips">{signals.terms.map(term => <li key={term}>{term}</li>)}</ul> : 'Sem termos com conversão no período'}</dd></div>
            {!signals.terms.length && signals.keywords.length > 0 && <div><dt>Palavras-chave com mais cliques</dt><dd><ul className="rs-chips">{signals.keywords.map(term => <li key={term}>{term}</li>)}</ul></dd></div>}
            <div><dt>Últimos 30 dias</dt><dd>{signals.metrics ? `${Number(signals.metrics.clicks).toLocaleString('pt-BR')} cliques · CTR ${(signals.metrics.clicks * 100 / signals.metrics.impressions).toLocaleString('pt-BR', {maximumFractionDigits: 1})}% · ${Number(signals.metrics.conversions).toLocaleString('pt-BR', {maximumFractionDigits: 0})} conversões` : 'Sem métricas no período'}</dd></div>
          </dl>}
        </aside>
      </div>
    </Section>
    <Section title="Criações enviadas ao Studio" description="Sessões abertas a partir do Reports, com a imagem mais recente quando já foi gerada">
      {sessions.error ? <ErrorState message={sessions.error} onRetry={retrySessions}/> : !sessions.body ? <LoadingState rows={3}/> :
        <DataTable label="Criações enviadas ao Studio" rows={sessions.body.sessions} rowKey={row => row.id}
          empty={<p className="rs-muted">Nenhuma criação ainda. Escolha uma campanha acima e abra o briefing no Studio.</p>} columns={[
            {key: 'title', label: 'Criação', render: row => <span className="rs-thumb-cell">{row.image_url ? <img src={row.image_url} alt="" loading="lazy"/> : <span className="rs-thumb-empty"><Image01 size={16} aria-hidden="true"/></span>}<span><strong>{row.title}</strong><small className="rs-cell-sub">{row.campaign_name}</small></span></span>},
            {key: 'status', label: 'Status', sortable: false, render: row => {const [label, tone] = STATUS[row.status] || [row.status, 'gray']; return <span className={`rs-badge is-${tone}`}>{label}</span>;}},
            {key: 'created_at', label: 'Criada', render: row => friendlyDateTime(row.created_at)},
            {key: 'open', label: '', sortable: false, render: row => <a className="rs-link" href={row.studio_url} target="_blank" rel="noopener">Abrir no Studio<ArrowUpRight size={14} aria-hidden="true"/></a>},
          ]}/>}
    </Section>
  </div>;
}
