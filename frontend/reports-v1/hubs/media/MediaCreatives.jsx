import React, {useEffect, useRef, useState} from 'react';
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
import {currency, number} from '../shared.jsx';

const STATUS = {draft: ['Rascunho', 'gray'], active: ['Em criação', 'warning'], ready: ['Pronto', 'success'], finalized: ['Finalizado', 'success'], finalizing: ['Finalizando', 'warning'], failed: ['Falhou', 'error'], cancelled: ['Cancelado', 'gray'], archived: ['Arquivado', 'gray']};
const ACTIVE = ['ENABLED', 'active'];

const dash = value => (value === null || value === undefined ? '—' : number(value));

/** One row per Google Ads account of the client, most work first: where to spend the next hour of the day. */
function AccountsPortfolio({portfolio: [state, retry]}) {
  const {scope, setScope} = useReportsContext();
  if (state.error) return <ErrorState message={state.error} onRetry={retry}/>;
  if (state.loading && !state.body) return <LoadingState rows={4}/>;
  const body = state.body;
  if (!body?.ready || !body.accounts.length) return null;
  const money = value => currency(value, body.currency);
  return <Section title="Contas por prioridade" description={`Quem precisa de trabalho primeiro. Índice = ${body.formula}.`}>
    <DataTable label="Contas do Google Ads" rows={body.accounts} rowKey={row => row.id} initialSort={{key: 'gap', dir: 'desc'}} columns={[
      {key: 'name', label: 'Conta', render: row => <><strong>{row.name}</strong>{String(row.id) === scope.account && <span className="rs-badge is-low"> Em foco</span>}
        <small className="rs-cell-sub">{row.collection_problems.length ? `Coleta com problema: ${row.collection_problems.join(', ')}` : row.last_run_at ? `Lida ${friendlyDateTime(row.last_run_at)}` : 'Sem leitura'}</small></>},
      {key: 'cost', label: 'Investimento', numeric: true, render: row => money(row.cost)},
      {key: 'waste_cost', label: 'Desperdício em termos', numeric: true, render: row => <>{money(row.waste_cost)}<small className="rs-cell-sub">{row.waste_terms} termos</small></>},
      {key: 'opportunities', label: 'Termos para virar palavra', numeric: true, render: row => number(row.opportunities)},
      {key: 'low_quality_keywords', label: 'Índice de Qualidade ≤ 4', numeric: true, render: row => number(row.low_quality_keywords)},
      {key: 'weak_ads', label: 'Anúncios fracos', numeric: true, sort: row => row.weak_ads ?? -1, render: row => row.weak_ads === null ? <span className="rs-muted" title="Atualize o script de Leitura para a versão 2.2.0 para coletar os anúncios.">sem coleta</span> : number(row.weak_ads)},
      {key: 'gap', label: 'Prioridade', numeric: true, render: row => <>{number(row.gap)}<small className="rs-cell-sub">{row.high} alta · {row.medium} média · {row.low} baixa</small></>},
      {key: 'open', label: '', sortable: false, render: row => <ReportsActionButton color="link-color" size="sm" className="rs-link-button" onClick={() => setScope({...scope, account: String(row.id), campaign: ''})}>Focar</ReportsActionButton>},
    ]}/>
  </Section>;
}

/** What can be worked on in the scope in focus, by kind of asset: Google Ads is texts, keywords and terms as much as images. */
function AssetTypes({portfolio: [state], onPick}) {
  const {scope} = useReportsContext();
  const rows = (state.body?.accounts || []).filter(row => !scope.account || String(row.id) === scope.account);
  const total = key => rows.reduce((sum, row) => sum + (row[key] || 0), 0);
  const adsKnown = rows.length > 0 && rows.every(row => row.weak_ads !== null);
  const money = value => currency(value, state.body?.currency);
  const link = view => reportUrl('media/google-ads', {view});
  const cards = [
    {key: 'ads', title: 'Anúncios de pesquisa', detail: adsKnown ? `${number(rows.reduce((sum, row) => sum + row.weak_ads, 0))} anúncios com força fraca` : 'A coleta de anúncios chega com o script de Leitura 2.2.0.', tone: adsKnown ? '' : 'is-pending'},
    {key: 'keywords', title: 'Palavras-chave', detail: `${number(total('low_quality_keywords'))} com Índice de Qualidade ≤ 4 · ${number(total('opportunities'))} termos para virar palavra`, href: link('keywords')},
    {key: 'terms', title: 'Termos e negativas', detail: `${money(total('waste_cost'))} em ${number(total('waste_terms'))} termos sem conversão`, href: link('search_terms')},
    {key: 'media', title: 'Imagem e vídeo', detail: 'Crie ou envie peças pelo Studio, com marca e projeto.', onClick: onPick},
  ];
  return <Section title="O que trabalhar" description={scope.account ? 'Na conta em foco.' : 'Em todas as contas do cliente.'}>
    <div className="rs-asset-types">{cards.map(card => card.href
      ? <a key={card.key} className="rs-asset-type" href={card.href}><strong>{card.title}</strong><span>{card.detail}</span></a>
      : card.onClick ? <button type="button" key={card.key} className="rs-asset-type" onClick={card.onClick}><strong>{card.title}</strong><span>{card.detail}</span></button>
        : <div key={card.key} className={`rs-asset-type ${card.tone || ''}`}><strong>{card.title}</strong><span>{card.detail}</span></div>)}</div>
  </Section>;
}

/**
 * "Que peça criar para cada campanha?" — the brief comes from what the campaign shows (intent that converts,
 * landing page, performance) and opens in the Studio with the brand and project, where direction, generation
 * and credits are handled.
 */
export function MediaCreatives({data}) {
  const {scope, period} = useReportsContext();
  // One portfolio request feeds both the account table and the asset cards.
  const portfolio = useApi(apiUrl('/assets/portfolio', {start_date: period.start, end_date: period.end}));
  const [mode, setMode] = useState(() => (new URLSearchParams(location.search).get('campaign') ? 'generate' : ''));
  // The header's source/campaign narrows which campaigns can be picked here.
  const campaigns = data.campaigns.filter(item => (!scope.account || String(item.account_id) === scope.account) && (!scope.campaign || String(item.id) === scope.campaign)).sort((a, b) => Number(ACTIVE.includes(b.status)) - Number(ACTIVE.includes(a.status)));
  const [campaignId, setCampaignId] = useState(() => new URLSearchParams(location.search).get('campaign') || (/^\d+$/.test(scope.campaign) ? scope.campaign : '') || String(campaigns[0]?.id || ''));
  // A deep link (?campaign=) wins on open; afterwards the header selection drives the pick.
  const deepLink = useRef(Boolean(new URLSearchParams(location.search).get('campaign')));
  useEffect(() => {
    if (deepLink.current) {deepLink.current = false; return;}
    if (/^\d+$/.test(scope.campaign)) setCampaignId(scope.campaign); else if (!campaigns.some(item => String(item.id) === campaignId)) setCampaignId(String(campaigns[0]?.id || ''));}, [scope.account, scope.campaign]);
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
  const brand = body?.brands.find(item => item.ref === brandRef);
  const signals = body?.signals;
  const studio = !campaigns.length
    ? <EmptyState title="Nenhuma campanha cadastrada" description="Os briefings de criativo partem dos dados de uma campanha. Cadastre ou importe campanhas primeiro."
      action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('media/campaigns')}>Ver campanhas</ReportsActionButton>}/>
    : !mode ? <Section title="Imagem e vídeo" description="Você já tem as peças ou quer gerar novas?">
      <div className="rs-asset-types">
        <button type="button" className="rs-asset-type" onClick={() => setMode('have')}><strong>Já tenho os criativos</strong><span>Veja o que já foi enviado ao Studio e abra para continuar.</span></button>
        <button type="button" className="rs-asset-type" onClick={() => setMode('generate')}><strong>Quero gerar</strong><span>O briefing nasce dos dados da campanha e abre no Studio.</span></button>
      </div></Section>
    : <div className="rs-stack">
    <div className="rs-actions"><div className="rs-segmented" role="group" aria-label="Imagem e vídeo">
      <button type="button" aria-pressed={mode === 'have'} onClick={() => setMode('have')}>Já tenho os criativos</button>
      <button type="button" aria-pressed={mode === 'generate'} onClick={() => setMode('generate')}>Quero gerar</button></div></div>
    {mode === 'generate' && <Section title="Criar com o Studio" description="O briefing nasce dos dados da campanha. A direção, a geração e os créditos ficam no Studio.">
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
    </Section>}
    {mode === 'have' && <Section title="Criações enviadas ao Studio" description="Sessões abertas a partir do Reports, com a imagem mais recente quando já foi gerada">
      {sessions.error ? <ErrorState message={sessions.error} onRetry={retrySessions}/> : !sessions.body ? <LoadingState rows={3}/> :
        <DataTable label="Criações enviadas ao Studio" rows={sessions.body.sessions} rowKey={row => row.id}
          empty={<p className="rs-muted">Nenhuma criação ainda. Escolha uma campanha acima e abra o briefing no Studio.</p>} columns={[
            {key: 'title', label: 'Criação', render: row => <span className="rs-thumb-cell">{row.image_url ? <img src={row.image_url} alt="" loading="lazy"/> : <span className="rs-thumb-empty"><Image01 size={16} aria-hidden="true"/></span>}<span><strong>{row.title}</strong><small className="rs-cell-sub">{row.campaign_name}</small></span></span>},
            {key: 'status', label: 'Status', sortable: false, render: row => {const [label, tone] = STATUS[row.status] || [row.status, 'gray']; return <span className={`rs-badge is-${tone}`}>{label}</span>;}},
            {key: 'created_at', label: 'Criada', render: row => friendlyDateTime(row.created_at)},
            {key: 'open', label: '', sortable: false, render: row => <a className="rs-link" href={row.studio_url} target="_blank" rel="noopener">Abrir no Studio<ArrowUpRight size={14} aria-hidden="true"/></a>},
          ]}/>}
    </Section>}
  </div>;
  return <div className="rs-stack">
    <AccountsPortfolio portfolio={portfolio}/>
    <AssetTypes portfolio={portfolio} onPick={() => {setMode(''); document.getElementById('creative-studio')?.scrollIntoView({behavior: 'smooth'});}}/>
    <div id="creative-studio">{studio}</div>
  </div>;
}
