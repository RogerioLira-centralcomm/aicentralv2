import {Flow} from './FlowsPage.jsx';
import {ReportsCustomers} from './ReportsCustomers.jsx';
import {ReportsRelationships} from './ReportsRelationships.jsx';
import {SharedReports} from './SharedReports.jsx';
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {SolutionSidebar} from '../cadu-design-system/components/SolutionSidebar.jsx';
import {Button as UntitledButton} from '../cadu-design-system/untitled-kit/button.tsx';
import {ReportsActionButton} from './ReportsActionButton.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';
import {ReportsConfirmDialog} from './ReportsConfirmDialog.jsx';
import {ReportsTabs} from './ReportsTabs.jsx';
import {AccessCard, InstallCard, InstallGuide, InstallStatus, LinkedFlows, RecentEvents, SiteSidebar, SiteSummary, StatusBadge} from './SuperTagParts.jsx';
import './supertag-workspace.css';
import {PageDetail} from './PageDetail.jsx';
import {AlertsCenter} from './AlertsCenter.jsx';
import {REPORT_FILTER_DEFAULTS, ReportsFilterBar} from './PageChrome.jsx';
import {APP_BASE, HUBS, applyLegacyRedirect, navigate, navigateOnClick, resolveRoute, useLocationKey} from './shell/routes.js';
import {ReportsContext, periodFilters, readPeriod, writePeriod} from './shell/context.js';
import {ContextSelector, PageHeader} from './shell/PageHeader.jsx';
import {LoadingState} from './shell/primitives.jsx';
import {setActiveClient} from './shell/useApi.js';
import {Chart, amount, money, platformName} from './shell/media.jsx';
import {Overview} from './hubs/overview/Overview.jsx';
import {MediaOverview} from './hubs/media/MediaOverview.jsx';
import {JourneyOverview} from './hubs/journey/JourneyOverview.jsx';
import {Navigation} from './hubs/journey/Navigation.jsx';
import {Conversions} from './hubs/journey/Conversions.jsx';
import {DataSources} from './hubs/data-sources/DataSources.jsx';
import './shell/shell.css';
import {CheckCircle, FilterLines, Plus, RefreshCw01, SearchLg} from '@untitledui/icons';
import {dropClientFromUrl, flowEditorId, reportUrl, shortDate, integer, decimal, json, Empty, Kpi} from './reportsCommon.jsx';
import '../cadu-design-system/tokens.css';
import './styles.css';
import './flow-workspace.css';
import './reports-refinement.css';
import '../cadu-design-system/primitives.css';

const ACCESS_ROLE_LABELS = {viewer: 'Visualização', member: 'Operação', admin: 'Administração de dados'};
const validGoogleAdsAccountId = value => /^(?:\d{10}|\d{3}-\d{3}-\d{4})$/.test(String(value || '').trim());
const sourceHealth = item => item.revoked_at ? 'Revogada' : !item.last_used_at ? 'Aguardando primeiro envio' : item.source_kind === 'google_ads_script' && Date.now() - new Date(item.last_used_at).getTime() > 48 * 3600 * 1000 ? 'Sem envio há 48 h' : 'Ativa';
const rootElement = document.getElementById('cadu-reports-v1-root');
document.documentElement.dataset.caduSkin = 'reports';






const FLOW_ROLE_LABELS = {
  entry:'Entrada', intermediate:'Página', form:'Formulário',
  conversion:'Conversão', error:'Erro', none:'Sem correspondência',
};
const FLOW_NODE_LABELS = {page:'Página', form:'Formulário', event:'Evento', whatsapp:'WhatsApp', conversion:'Conversão', erro:'Erro'};

function AccountsManagementView({data, selectedCustomer, setSelectedCustomer, selectedAccount, setSelectedAccount, selectedCampaign, setSelectedCampaign, save, busy, onExit}) {
  const accountsOfCustomer = selectedCustomer ? data.accounts.filter(a => a.customer_id === selectedCustomer.id) : data.accounts;
  const campaignsOfAccount = selectedAccount ? data.campaigns.filter(c => c.account_id === selectedAccount.id) : [];
  const accountCount = a => (data.accounts.filter(x => x.customer_id === a.id) || []).length;
  const campaignCount = a => (data.campaigns.filter(c => c.account_id === a.id) || []).length;

  return <div className="reports-accounts-view">
    <div className="reports-breadcrumb">
      <button onClick={onExit} className="reports-text-button" title="Voltar para visualização padrão">
        <span>←</span> Voltar
      </button>
    </div>

    <div className="reports-3col-layout">
      <div className="reports-col reports-col--customers">
        <div className="reports-col-header"><h3>Clientes</h3></div>
        <div className="reports-col-list">
          {(data.customers || []).map(c => {
            const count = accountCount(c);
            return (
              <div
                key={c.id}
                className={`reports-col-item ${selectedCustomer?.id === c.id ? 'active' : ''}`}
                onClick={() => {setSelectedCustomer(c); setSelectedAccount(null); setSelectedCampaign(null);}}
                role="button"
                tabIndex={0}
                title={c.name}
              >
                <div className="reports-col-item-label">{c.name}</div>
                <div className="reports-col-item-meta">{count} {count === 1 ? 'conta' : 'contas'}</div>
              </div>
            );
          })}
          {!data.customers?.length && <div className="reports-col-empty">Nenhum cliente cadastrado</div>}
        </div>
      </div>

      <div className="reports-col reports-col--accounts">
        <div className="reports-col-header"><h3>Contas</h3></div>
        <div className="reports-col-list">
          {accountsOfCustomer.map(a => {
            const count = campaignCount(a);
            return (
              <div
                key={a.id}
                className={`reports-col-item ${selectedAccount?.id === a.id ? 'active' : ''}`}
                onClick={() => {setSelectedAccount(a); setSelectedCampaign(null);}}
                role="button"
                tabIndex={0}
                title={`${a.name} • ${a.platform || 'Manual'}`}
              >
                <div className="reports-col-item-label">{a.name}</div>
                <div className="reports-col-item-meta">{a.platform || 'Manual'} · {count} campanhas</div>
              </div>
            );
          })}
          {!accountsOfCustomer.length && (
            <div className="reports-col-empty">
              {selectedCustomer ? 'Nenhuma conta neste cliente' : 'Selecione um cliente'}
            </div>
          )}
        </div>
      </div>

      <div className="reports-col reports-col--campaigns">
        <div className="reports-col-header"><h3>Campanhas</h3></div>
        <div className="reports-col-list">
          {campaignsOfAccount.map(c => (
            <div
              key={c.id}
              className={`reports-col-item ${selectedCampaign?.id === c.id ? 'active' : ''}`}
              onClick={() => setSelectedCampaign(c)}
              role="button"
              tabIndex={0}
              title={c.name}
            >
              <div className="reports-col-item-label">{c.name}</div>
              <div className="reports-col-item-meta">{c.id}</div>
            </div>
          ))}
          {!campaignsOfAccount.length && (
            <div className="reports-col-empty">
              {selectedAccount ? 'Nenhuma campanha' : 'Selecione uma conta'}
            </div>
          )}
        </div>
      </div>
    </div>

    {selectedCampaign && selectedAccount && (
      <div className="reports-campaign-detail">
        <h2>{selectedCampaign.name}</h2>
        <div className="reports-campaign-info">
          <div><strong>ID da campanha:</strong> <span>{selectedCampaign.id}</span></div>
          <div><strong>Conta:</strong> <span>{selectedAccount.name}</span></div>
          <div><strong>Plataforma:</strong> <span>{selectedAccount.platform || 'Manual'}</span></div>
          {selectedAccount.id && <div><strong>ID da conta:</strong> <span>{selectedAccount.id}</span></div>}
        </div>
      </div>
    )}
  </div>;
}

function FlowSuggestionConfidence({suggestion}) {
  const alternatives = Object.entries(suggestion?.probabilities || {})
    .filter(([role, probability]) => FLOW_ROLE_LABELS[role] && Number.isFinite(Number(probability)))
    .sort((left, right) => Number(right[1]) - Number(left[1]));
  const confidence = Number(suggestion?.confidence);
  if (!alternatives.length) return null;
  return <span className="reports-flow-ai-confidence" title="A concentração resume a distribuição das alternativas; não é garantia de acerto.">
    {Number.isFinite(confidence) ? `Concentração ${Math.round(confidence * 100)}% · ` : ''}
    Alternativas: {alternatives.map(([role, probability]) => `${FLOW_ROLE_LABELS[role]} ${Math.round(Number(probability) * 100)}%`).join(' / ')}
  </span>;
}


function CustomerSelect({data,value,onChange}) {return <label>Cliente / anunciante<ReportsNativeSelect value={value} onChange={e=>onChange(e.target.value)}><option value="">Operação própria</option>{(data.customers||[]).filter(c=>c.status==='active').map(c=><option value={c.id} key={c.id}>{c.name}</option>)}</ReportsNativeSelect></label>;}

function Accounts({data, save, busy}) {
  const [form, setForm] = useState({customer_id:'',platform: 'google_ads', account_kind: 'advertiser', external_id: '', name: '', parent_account_id: ''});
  const [query, setQuery] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const managers = data.accounts.filter(account => account.account_kind === 'manager' && account.platform === form.platform);
  const advertisers = data.accounts.filter(account => account.account_kind === 'advertiser');
  const visibleAccounts = data.accounts.filter(item => `${item.name} ${item.external_id} ${item.platform} ${item.account_kind}`.toLowerCase().includes(query.trim().toLowerCase()));
  const submit = async event => {
    event.preventDefault();
    try {await save('/accounts', form); setForm({...form, external_id: '', name: '', parent_account_id: ''}); setCreateOpen(false);}
    catch (_) { /* Global error banner shows the failure. */ }
  };
  return <>
    <section className="reports-accounts-page">
    <header className="reports-accounts-heading"><div><p>{data.client.client_name || `Cliente ${data.client.client_id}`} <span>·</span> {integer(data.accounts.length)} {data.accounts.length === 1 ? 'conta' : 'contas'}</p></div><div className="reports-accounts-heading__actions"><UntitledButton className="reports-account-connect" color="tertiary" href={reportUrl('monitor')}>Conectar fonte</UntitledButton>{data.client.role!=='viewer'&&<UntitledButton className="reports-account-add" onPress={()=>setCreateOpen(true)}>Adicionar conta</UntitledButton>}</div></header>
    <div className="reports-accounts-layout">
    <article className="reports-panel reports-accounts-list"><div className="reports-accounts-toolbar"><div className="reports-accounts-search"><ReportsFieldInput type="search" aria-label="Buscar contas" placeholder="Nome, ID ou plataforma" value={query} onChange={event => setQuery(event.target.value)}/></div></div>
      {visibleAccounts.length ? <div className="reports-table-wrap"><table><thead><tr><th>Nome</th><th>Plataforma</th><th>ID externo</th><th>Tipo</th><th>MCC</th><th>Status</th><th></th></tr></thead><tbody>{visibleAccounts.map(item => <AccountRow key={item.id} item={item} data={data} save={save} busy={busy} />)}</tbody></table></div> : <Empty message={data.accounts.length?'Nenhuma conta encontrada.':'Nenhuma conta ainda. Conecte uma fonte ou adicione uma conta.'} />}
    </article>
    <ReportsDrawer open={createOpen} onOpenChange={setCreateOpen} title="Adicionar conta de mídia" description="Identifique a conta e seu vínculo com uma gerenciadora, se houver." context={data.client.client_name}>
      <form className="reports-account-create-form" onSubmit={submit}>
      <label>Plataforma<ReportsNativeSelect value={form.platform} onChange={event => setForm({...form, platform: event.target.value, parent_account_id: ''})}><option value="google_ads">Google Ads</option><option value="meta_ads">Meta Ads</option><option value="microsoft_ads">Microsoft Ads</option><option value="other">Outra</option></ReportsNativeSelect></label>
      <label>Tipo<ReportsNativeSelect value={form.account_kind} onChange={event => setForm({...form, account_kind: event.target.value, parent_account_id: ''})}><option value="advertiser">Conta de mídia</option><option value="manager">MCC / gerente</option></ReportsNativeSelect></label>
      <ReportsFieldInput label="Nome da conta" required maxLength={240} value={form.name} onChange={event => setForm({...form,name:event.target.value})} placeholder="Nome exibido na plataforma" hint="Use um nome que ajude a identificar a conta na lista." />
      <ReportsFieldInput label="ID da conta" required maxLength={160} value={form.external_id} onChange={event => setForm({...form,external_id:event.target.value})} placeholder={form.platform === 'google_ads' ? '123-456-7890' : 'ID fornecido pela plataforma'} hint={form.platform === 'google_ads' ? 'ID Google Ads com 10 dígitos, com ou sem hífens.' : 'Copie o identificador exibido pela plataforma escolhida.'}/>
      {form.account_kind === 'advertiser' && managers.length > 0 && <label>Conta gerente<ReportsNativeSelect value={form.parent_account_id} onChange={event => setForm({...form, parent_account_id: event.target.value})}><option value="">Sem gerente</option>{managers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</ReportsNativeSelect></label>}
      <div className="reports-untitled-drawer__actions"><UntitledButton type="submit" isDisabled={busy} isLoading={busy}>Salvar conta</UntitledButton></div>
    </form></ReportsDrawer>
    </div>
  </section>
  </>;
}

function AccountRow({item, data, save, busy}) {
  const formId = `reports-account-${item.id}`;
  const [draft, setDraft] = useState({name: item.name, external_id: item.external_id, status: item.status || 'active', parent_account_id: item.parent_account_id || ''});
  const [saved, setSaved] = useState(false);
  const [editing, setEditing] = useState(false);
  useEffect(() => setDraft({name: item.name, external_id: item.external_id, status: item.status || 'active', parent_account_id: item.parent_account_id || ''}), [item]);
  const managers = data.accounts.filter(account => account.platform === item.platform && account.account_kind === 'manager' && account.status !== 'disabled' && account.id !== item.id);
  const update = async event => {event.preventDefault(); setSaved(false); try {await save(`/accounts/${item.id}`, draft, true, 'PATCH'); setSaved(true);setEditing(false);} catch (_) { /* Global error banner shows the failure. */ }};
  const cancel = () => {setDraft({name:item.name,external_id:item.external_id,status:item.status||'active',parent_account_id:item.parent_account_id||''});setEditing(false);};
  return <tr className={editing?'reports-account-row is-editing':'reports-account-row'} onKeyDown={event => {if (editing && event.key === 'Escape') {event.preventDefault();cancel();}}}><td>{editing?<ReportsFieldInput form={formId} className="reports-account-field" aria-label={`Nome da conta ${item.external_id}`} value={draft.name} onChange={event => setDraft({...draft, name: event.target.value})} required maxLength="240" />:<><strong>{item.name}</strong><ReportsRelationships data={data} kind="account" id={item.id} name={item.name}/></>}</td><td>{platformName(item.platform)}</td><td>{editing?<ReportsFieldInput form={formId} className="reports-account-field" aria-label={`ID externo ${item.external_id}`} value={draft.external_id} onChange={event => setDraft({...draft, external_id: event.target.value})} required maxLength="160" />:item.external_id}</td><td>{item.account_kind === 'manager' ? 'Gerente' : 'Anunciante'}</td><td>{editing&&item.account_kind==='advertiser'?<ReportsNativeSelect form={formId} className="reports-account-field" aria-label={`Gerente da conta ${item.external_id}`} value={draft.parent_account_id} onChange={event => setDraft({...draft, parent_account_id: event.target.value})}><option value="">Sem gerente</option>{managers.map(manager => <option key={manager.id} value={manager.id}>{manager.name}</option>)}</ReportsNativeSelect>:data.accounts.find(parent => parent.id === item.parent_account_id)?.name || '—'}</td><td>{editing?<ReportsNativeSelect form={formId} className="reports-account-field" aria-label={`Estado da conta ${item.external_id}`} value={draft.status} onChange={event => setDraft({...draft, status: event.target.value})}><option value="active">Ativa</option><option value="paused">Pausada</option><option value="disabled">Desativada</option></ReportsNativeSelect>:({active:'Ativa',paused:'Pausada',disabled:'Desativada'})[item.status]||item.status}</td><td>{data.client.role!=='viewer'&&(editing?<form id={formId} className="reports-account-row__actions" onSubmit={update}><UntitledButton size="xs" type="submit" isDisabled={busy} isLoading={busy}>Salvar</UntitledButton></form>:<UntitledButton className="reports-account-edit" size="xs" color="link-color" onPress={()=>{setSaved(false);setEditing(true);}}>Editar</UntitledButton>)}{saved&&<span className="reports-account-saved" role="status">Salva</span>}</td></tr>;
}

/** Campaign detail lives at /media/campaigns/<id>; ?campaign_id= from older links is still understood. */
const campaignIdFromUrl = () => resolveRoute().entity || new URLSearchParams(location.search).get('campaign_id') || '';

function Campaigns({data, save, busy, filters, refreshRevision}) {
  const [form, setForm] = useState({customer_id:'',account_id: '', external_id: '', name: '', objective: '', channel_type: ''});
  const [createOpen, setCreateOpen] = useState(false);
  const [campaignId, setCampaignId] = useState(campaignIdFromUrl);
  const [campaignDetail, setCampaignDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [tab, setTab] = useState(() => {
    const current = new URLSearchParams(location.search).get('campaign_tab') || 'overview';
    return current === 'metrics' ? 'performance' : current;
  });
  const accounts = data.accounts.filter(item => item.account_kind === 'advertiser');
  const visibleCampaigns = data.campaigns.filter(item =>
    (!filters.platform || item.platform === filters.platform) &&
    (!filters.account || String(item.account_id) === filters.account) &&
    (!filters.campaign || String(item.id) === filters.campaign));
  useEffect(() => {
    let live = true;
    if (!campaignId) {setCampaignDetail(null); return () => {live=false;};}
    json(`/connect/api/v2/reports/campaigns/${campaignId}?client_id=${data.client.client_id}`)
      .then(value => {if(live){setCampaignDetail(value);setDetailError('');}})
      .catch(error => {if(live)setDetailError(error.message);});
    return () => {live=false;};
  }, [campaignId, data.client.client_id]);
  useEffect(()=>{const sync=()=>{const params=new URLSearchParams(location.search);setCampaignId(campaignIdFromUrl());const current=params.get('campaign_tab')||'overview';setTab(current==='metrics'?'performance':current);};addEventListener('popstate',sync);return()=>removeEventListener('popstate',sync);},[]);
  const campaignUrl = ({id = campaignId, view = ''} = {}) => {
    const url = new URL(location.href);
    url.searchParams.delete('client_id');
    url.searchParams.delete('campaign_id');
    if (view) url.searchParams.set('campaign_tab', view); else url.searchParams.delete('campaign_tab');
    url.pathname = `${APP_BASE}/media/campaigns${id ? `/${encodeURIComponent(id)}` : ''}`;
    url.hash = '';
    return url;
  };
  const openCampaign = item => {setCampaignId(String(item.id));setTab('overview');history.pushState(null,'',campaignUrl({id:item.id}));};
  const changeCampaignTab = value => {setTab(value);history.replaceState(history.state,'',campaignUrl({view:value}));};
  const closeCampaign = () => {setCampaignId('');setCampaignDetail(null);setDetailError('');history.replaceState(history.state,'',campaignUrl({id:'',view:''}));};
  const submit = async event => {event.preventDefault(); try {await save('/campaigns', form); setForm({...form, external_id: '', name: '', objective: '', channel_type: ''}); setCreateOpen(false);} catch (_) { /* Global error banner shows the failure. */ }};
  if (campaignId) return <CampaignDetail data={data} detail={campaignDetail} error={detailError} tab={tab} setTab={changeCampaignTab} close={closeCampaign} filters={filters} refreshRevision={refreshRevision} save={save} busy={busy} updateDetail={setCampaignDetail} />;
  return <>
    <section className="reports-campaigns-page reports-campaigns-list-page"><article className="reports-panel"><div className="reports-panel-head reports-panel-head--actions"><div className="reports-list-head-actions"><span>{visibleCampaigns.length} de {data.campaigns.length}</span>{data.client.role !== 'viewer' && <ReportsActionButton className="reports-campaign-add" onClick={() => setCreateOpen(true)} color="primary">Adicionar campanha</ReportsActionButton>}</div></div>
    {visibleCampaigns.length ? <div className="reports-table-wrap"><table><thead><tr><th>Campanha</th><th>Conta</th><th>Plataforma</th><th>Tipo</th><th>ID externo</th><th>Projeto Workspace (opcional)</th><th>Status</th></tr></thead><tbody>{visibleCampaigns.map(item => <tr key={item.id}><td><ReportsActionButton type="button" className="reports-campaign-open" onClick={()=>openCampaign(item)}><strong>{item.name}</strong><small>Abrir detalhes ↗</small></ReportsActionButton></td><td>{item.account_name||'Sem conta de mídia'}</td><td>{platformName(item.platform)}</td><td>{item.channel_type || item.objective || '—'}</td><td>{item.external_id}</td><td><ReportsRelationships data={data} kind="campaign" id={item.id} name={item.name}/></td><td>{({ENABLED:'Ativa',PAUSED:'Pausada',REMOVED:'Removida',unknown:'Não informado'})[item.status] || item.status}</td></tr>)}</tbody></table></div> : <Empty message={data.campaigns.length ? 'Nenhuma campanha corresponde aos filtros desta página.' : 'Nenhuma campanha ainda. Adicione uma ou sincronize uma conta de mídia.'} />}</article>
    <ReportsDrawer open={createOpen} onOpenChange={setCreateOpen} onDiscard={()=>setForm({customer_id:'',account_id:'',external_id:'',name:'',objective:'',channel_type:''})} title="Adicionar campanha" description="Crie uma campanha manual ou associe uma conta de mídia." context={data.client.client_name}>{data.client.role==='viewer'?<Empty message="Seu acesso permite consultar as campanhas, sem cadastrar ou editar."/>:<form className="reports-form" onSubmit={submit}>
      <CustomerSelect data={data} value={form.customer_id} onChange={value=>setForm({...form,customer_id:value,account_id:''})}/>
      <label>Conta de mídia (opcional)<ReportsNativeSelect value={form.account_id} onChange={event=>setForm({...form,account_id:event.target.value})}><option value="">Campanha manual</option>{accounts.filter(a=>String(a.customer_id||'')===form.customer_id).map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</ReportsNativeSelect></label>
      <label>Nome<ReportsFieldInput required maxLength="240" value={form.name} onChange={event => setForm({...form, name: event.target.value})} /></label>
      <label>{accounts.find(item => String(item.id) === String(form.account_id))?.platform === 'microsoft_ads' ? 'ID da campanha' : 'ID da campanha ou PI'}<ReportsFieldInput required={Boolean(form.account_id)} disabled={!form.account_id} maxLength="160" value={form.external_id} onChange={event => setForm({...form, external_id: event.target.value})} placeholder="Identificador informado pela plataforma" /><small>Use o identificador correspondente à conta selecionada. Ele será usado para relacionar os dados importados.</small></label>
      <label>Objetivo (opcional)<ReportsFieldInput maxLength="160" value={form.objective} onChange={event => setForm({...form, objective: event.target.value})} placeholder="Ex.: geração de leads" /></label>
      <label>Tipo de canal (opcional)<ReportsFieldInput maxLength="64" value={form.channel_type} onChange={event => setForm({...form, channel_type: event.target.value})} placeholder="Ex.: pesquisa, social, vídeo" /></label>
      <ReportsActionButton type="submit" disabled={busy}>Salvar campanha</ReportsActionButton>
    </form>}</ReportsDrawer></section>
  </>;
}

function CampaignDetail({data, detail, error, tab, setTab, close, filters, refreshRevision, save, busy, updateDetail}) {
  const [channelData, setChannelData] = useState(null);
  const [flowData, setFlowData] = useState(null);
  const [analysisError, setAnalysisError] = useState('');
  const [settings, setSettings] = useState({name: '', objective: '', channel_type: ''});
  const [settingsNotice, setSettingsNotice] = useState('');
  const [collectionQuery, setCollectionQuery] = useState('');
  const [collectionSource, setCollectionSource] = useState('all');
  const [metricFilter, setMetricFilter] = useState('all');
  const campaignId = detail?.campaign?.id;
  useEffect(() => {
    if (!campaignId) return undefined;
    let active = true;
    const params = new URLSearchParams({
      client_id: String(data.client.client_id),
      campaign_id: String(campaignId),
      days: filters.period,
      start_date: filters.startDate,
      end_date: filters.endDate,
    });
    Promise.all([
      json(`/connect/api/v2/reports/metrics?${params}`),
      json(`/connect/api/v2/reports/flow?${params}`),
    ]).then(([metrics, flow]) => {
      if (active) {setChannelData(metrics);setFlowData(flow);setAnalysisError('');}
    }).catch(failure => {if(active)setAnalysisError(failure.message);});
    return () => {active = false;};
  }, [campaignId, data.client.client_id, filters.period, filters.startDate, filters.endDate, refreshRevision]);
  useEffect(() => {
    if (!detail?.campaign) return;
    setSettings({account_id:detail.campaign.account_id||'',external_id:detail.campaign.external_id||'',name: detail.campaign.name || '', objective: detail.campaign.objective || '', channel_type: detail.campaign.channel_type || ''});
    setSettingsNotice('');
  }, [detail?.campaign?.id, detail?.campaign?.name, detail?.campaign?.objective, detail?.campaign?.channel_type]);
  if(error)return <section className="reports-grid"><article className="reports-panel"><ReportsActionButton type="button" className="reports-text-button" onClick={close}>← Voltar às campanhas</ReportsActionButton><p className="reports-error">{error}</p></article></section>;
  if(!detail)return <section className="reports-grid"><article className="reports-panel"><Empty message="Carregando detalhes da campanha…"/></article></section>;
  const campaign=detail.campaign;
  const saveSettings = async event => {
    event.preventDefault();
    try {
      await save(`/campaigns/${campaign.id}`, settings, true, 'PATCH');
      const updated = await json(`/connect/api/v2/reports/campaigns/${campaign.id}?client_id=${data.client.client_id}`);
      updateDetail(updated);
      setSettingsNotice('Campanha atualizada.');
    } catch (failure) {setAnalysisError(failure.message); setSettingsNotice('');}
  };
  const totals=detail.metric_totals||[];
  const latest=totals.reduce((value,item)=>!value||item.latest_date>value?item.latest_date:value,'');
  const periodMetricValue=key=>detail.metrics.filter(item=>item.metric_key===key&&item.metric_date>=filters.startDate&&item.metric_date<=filters.endDate&&item.value_numeric!=null).reduce((sum,item)=>sum+Number(item.value_numeric||0),0);
  const metricLabels={impressions:'Impressões',clicks:'Cliques',cost:'Investimento',conversions:'Conversões',conversion_value:'Valor de conversão'};
  const stateLabel=({ENABLED:'Ativa',PAUSED:'Pausada',REMOVED:'Removida',unknown:'Não informado'})[campaign.status]||campaign.status||'Ativa';
  const channelEvents = Object.values((flowData?.events || []).reduce((map, item) => {
    const key = item.source_label || 'Origem direta';
    map[key] = map[key] || {source_label: key, total: 0, mapped: 0};
    map[key].total += Number(item.total || 0);
    map[key].mapped += Number(item.mapped || 0);
    return map;
  }, {}));
  const forms = (flowData?.events || []).filter(item => item.event_kind === 'form_submit');
  const confirmed = flowData?.confirmed || [];
  const ingestedDaily = (channelData?.days || []).flatMap(item => [
    {metric_date:item.date,metric_key:'impressions',value_numeric:item.impressions,source:'google_ads_script'},
    {metric_date:item.date,metric_key:'clicks',value_numeric:item.clicks,source:'google_ads_script'},
    {metric_date:item.date,metric_key:'cost',value_numeric:item.cost_micros == null ? null : Number(item.cost_micros) / 1_000_000,currency:channelData.currency,source:'google_ads_script'},
    {metric_date:item.date,metric_key:'conversions',value_numeric:item.conversions,source:'google_ads_script'},
  ]).filter(item=>item.value_numeric!=null);
  const importedDaily=detail.metrics.filter(item=>item.value_numeric!=null&&item.metric_date>=filters.startDate&&item.metric_date<=filters.endDate);
  const dimensionalDaily=(detail.metric_observations||[]).filter(item=>item.metric_date>=filters.startDate&&item.metric_date<=filters.endDate);
  const queryText=collectionQuery.trim().toLocaleLowerCase('pt-BR');
  const matchesQuery=value=>!queryText||String(value||'').toLocaleLowerCase('pt-BR').includes(queryText);
  const collectionToolbar=(placeholder, options=[], metricOptions=false)=><div className="reports-collection-toolbar"><label className="reports-collection-search"><SearchLg size={16} aria-hidden="true"/><ReportsFieldInput type="search" value={collectionQuery} onChange={event=>setCollectionQuery(event.target.value)} placeholder={placeholder}/></label>{options.length>0&&<label className="reports-collection-filter"><span>Origem</span><ReportsNativeSelect value={collectionSource} onChange={event=>setCollectionSource(event.target.value)}><option value="all">Todas</option>{options.map(option=><option key={option} value={option}>{option}</option>)}</ReportsNativeSelect></label>}{metricOptions&&<label className="reports-collection-filter"><span>Métrica</span><ReportsNativeSelect value={metricFilter} onChange={event=>setMetricFilter(event.target.value)}><option value="all">Todas</option>{Object.entries(metricLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</ReportsNativeSelect></label>}</div>;
  const visibleChannelEvents=channelEvents.filter(item=>(collectionSource==='all'||item.source_label===collectionSource)&&matchesQuery(item.source_label));
  const pageRows=(flowData?.activity||[]).filter(item=>matchesQuery(item.page_path));
  const formRows=forms.filter(item=>(collectionSource==='all'||item.source_label===collectionSource)&&matchesQuery(`${item.event_name} ${item.page_path} ${item.source_label}`));
  const conversionRows=(flowData?.events||[]).filter(item=>item.event_kind==='conversion'&&(collectionSource==='all'||item.source_label===collectionSource)&&matchesQuery(`${item.event_name} ${item.page_path} ${item.source_label}`));
  const conversionAssistRows=(flowData?.events||[]).filter(item=>['form_submit','whatsapp_click'].includes(item.event_kind));
  const performanceRows=[...ingestedDaily,...importedDaily].filter(item=>(collectionSource==='all'||(item.source==='google_ads_script'?'Google Ads':'Importação')===collectionSource)&&(metricFilter==='all'||item.metric_key===metricFilter)&&matchesQuery(`${metricLabels[item.metric_key]||item.metric_key} ${item.metric_date} ${item.currency||''} ${item.source||''}`));
  const dimensionRows=dimensionalDaily.filter(item=>(metricFilter==='all'||item.metric_key===metricFilter)&&matchesQuery(`${metricLabels[item.metric_key]||item.metric_key} ${item.metric_date} ${Object.values(item.dimensions||{}).map(value=>`${value.label} ${value.value}`).join(' ')}`));
  const campaignTabs = [
    ['overview','Visão geral'],['performance','Performance'],['channels','Canais'],
    ['pages','Páginas'],['forms','Formulários'],['leads','Leads'],
    ['conversions','Conversões'],['heatmap','Mapa de calor'],['reports','Relatórios'],
    ['imports','Dados de origem'],['settings','Configurações'],
  ];
  const periodLabel = `${shortDate(filters.startDate)} – ${shortDate(filters.endDate)}`;
  return <section className="reports-grid reports-grid--four reports-campaign-detail">
    <div className="reports-campaign-crumb reports-span-four"><ReportsActionButton type="button" className="reports-text-button" onClick={close}>Campanhas</ReportsActionButton><span>›</span><b>{campaign.name}</b></div>
    <header className="reports-panel reports-span-four reports-campaign-hero"><div><small>{campaign.platform} · {campaign.account_name} · ID {campaign.external_id}</small><h2>{campaign.name}<span className={`reports-campaign-status ${campaign.status==='PAUSED'?'is-paused':''}`}>{stateLabel}</span></h2><p>Campanha de mídia do cliente {data.client.client_name}. Criada em {shortDate(campaign.created_at)} · Atualizada em {shortDate(campaign.updated_at)}.</p></div><div className="reports-campaign-hero-actions"><span className="reports-period-chip">{periodLabel}</span><a className="reports-primary-link" href={reportUrl('imports')}>Importar dados</a></div></header>
    <ReportsTabs className="reports-panel reports-span-four reports-campaign-tabs" label="Seções da campanha" items={campaignTabs.map(([id,label]) => ({id,label}))} value={tab} onChange={setTab} />
    {analysisError&&<div className="reports-error reports-span-four" role="alert">Não foi possível carregar os dados desta campanha: {analysisError}</div>}
    {tab==='overview'&&<><Kpi label="Impressões" value={integer(channelData?.totals?.impressions ?? periodMetricValue('impressions'))} detail={`${periodLabel} · mídia`}/><Kpi label="Cliques" value={integer(channelData?.totals?.clicks ?? periodMetricValue('clicks'))} detail={`${periodLabel} · mídia`}/><Kpi label="Conversões" value={decimal(channelData?.totals?.conversions ?? periodMetricValue('conversions'))} detail="Métricas recebidas da plataforma"/><Kpi label="Último dado" value={shortDate(latest)} detail="data mais recente entre as métricas importadas"/><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Performance no período</h3><span>{periodLabel}</span></div><Chart type="area" labels={(channelData?.days||[]).map(item=>shortDate(item.date))} values={(channelData?.days||[]).map(item=>item.impressions)}/></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Dados personalizados</h3><span>{detail.custom_values.length} pares chave/valor</span></div>{detail.custom_values.length?detail.custom_values.slice(0,8).map((item,index)=><div className="reports-row" key={`${item.metric_key}:${item.metric_date}:${index}`}><span>{item.metric_label} · {item.channel}<small>{item.metric_key} · {shortDate(item.metric_date)}</small></span><b>{item.value_numeric} {item.currency||item.unit}</b></div>):<Empty message="Dados extras importados aparecerão associados a esta campanha."/>}</article></>}
    {tab==='performance'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Performance da campanha</h3><span>{periodLabel} · origem: Google Ads Script</span></div><div className="reports-grid reports-grid--four"><Kpi label="Impressões" value={integer(channelData?.totals?.impressions)} detail="No período selecionado"/><Kpi label="Cliques" value={integer(channelData?.totals?.clicks)} detail="No período selecionado"/><Kpi label="Investimento" value={money(channelData?.totals?.cost_micros,channelData?.currency)} detail="Moeda da conta"/><Kpi label="Conversões da plataforma" value={decimal(channelData?.totals?.conversions)} detail="Métrica enviada pela plataforma"/></div><Chart type="area" labels={(channelData?.days||[]).map(item=>shortDate(item.date))} values={(channelData?.days||[]).map(item=>item.impressions)}/></article>}
    {tab==='channels'&&<><Kpi label="Plataforma" value={campaign.platform} detail={campaign.channel_type||campaign.objective||'Canal não informado'}/><Kpi label="Origens atribuídas" value={integer(channelEvents.length)} detail="UTM ou domínio de referência"/><Kpi label="Eventos atribuídos" value={integer(channelEvents.reduce((sum,item)=>sum+item.total,0))} detail="No período selecionado"/><Kpi label="Campanha" value={campaign.name} detail={campaign.external_id}/><article className="reports-panel reports-span-four"><div className="reports-panel-head"><div><h3>Origem do tráfego</h3><p>Eventos da tag de fluxo · {periodLabel}</p></div><span>{visibleChannelEvents.length} de {channelEvents.length} origens</span></div>{collectionToolbar('Buscar origem, UTM ou domínio',Array.from(new Set(channelEvents.map(item=>item.source_label))))}{channelEvents.length?(visibleChannelEvents.length?<div className="reports-table-wrap"><table><thead><tr><th>Origem / canal</th><th>Eventos</th><th>Mapeados em etapas</th><th>Participação</th></tr></thead><tbody>{visibleChannelEvents.map(item=><tr key={item.source_label}><td>{item.source_label}</td><td>{integer(item.total)}</td><td>{integer(item.mapped)}</td><td>{channelEvents.reduce((sum,row)=>sum+row.total,0)?`${Math.round(item.total/channelEvents.reduce((sum,row)=>sum+row.total,0)*100)}%`:'—'}</td></tr>)}</tbody></table></div>:<Empty message="Nenhuma origem corresponde à busca e aos filtros."/>):<Empty message="Não há eventos atribuídos a esta campanha no período."/>}</article></>}
    {tab==='pages'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><div><h3>Páginas do fluxo</h3><p>Atividade agregada por URL · {periodLabel}</p></div><span>{pageRows.length} de {(flowData?.activity||[]).length} páginas</span></div>{collectionToolbar('Buscar caminho ou URL')}{flowData?.activity?.length?(pageRows.length?<div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Visitas</th><th>Visitantes</th><th>Formulários</th><th>Conversões</th></tr></thead><tbody>{pageRows.map(item=><tr key={`${item.tag_id}:${item.page_path}`}><td>{item.page_path}</td><td>{integer(item.views)}</td><td>{integer(item.visitors)}</td><td>{integer(item.form_submissions)}</td><td>{integer(item.conversions)}</td></tr>)}</tbody></table></div>:<Empty message="Nenhuma página corresponde à busca."/>):<Empty message="As páginas aparecem quando a Super Tag recebe visitas atribuídas à campanha."/>}</article>}
    {tab==='forms'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><div><h3>Eventos de formulário</h3><p>Somente contagens; valores digitados não são armazenados.</p></div><span>{formRows.length} de {forms.length} eventos</span></div>{collectionToolbar('Buscar evento, página ou origem',Array.from(new Set(forms.map(item=>item.source_label))))}{forms.length?(formRows.length?<div className="reports-table-wrap"><table><thead><tr><th>Evento</th><th>Página</th><th>Origem</th><th>Envios</th><th>Mapeados</th></tr></thead><tbody>{formRows.map((item,index)=><tr key={`${item.event_name}:${item.page_path}:${index}`}><td>{item.event_name}</td><td>{item.page_path}</td><td>{item.source_label}</td><td>{integer(item.total)}</td><td>{integer(item.mapped)}</td></tr>)}</tbody></table></div>:<Empty message="Nenhum evento corresponde à busca e aos filtros."/>):<Empty message="Nenhum envio de formulário foi recebido para esta campanha no período."/>}</article>}
    {tab==='leads'&&<><Kpi label="Leads" value={integer(confirmed.find(item=>item.conversion_kind==='lead')?.total)} detail="Confirmações do CRM"/><Kpi label="Qualificados" value={integer(confirmed.find(item=>item.conversion_kind==='qualified_lead')?.total)} detail="Confirmações do CRM"/><Kpi label="Vendas" value={integer(confirmed.find(item=>item.conversion_kind==='sale')?.total)} detail="Confirmações do CRM"/><article className="reports-panel"><h3>Dados protegidos</h3><p>Esta tela mostra totais agregados. Dados pessoais ficam no CRM de origem.</p></article><article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Confirmações recebidas</h3><span>CRM · {periodLabel}</span></div>{confirmed.length?<div className="reports-table-wrap"><table><thead><tr><th>Etapa</th><th>Total confirmado</th></tr></thead><tbody>{confirmed.map(item=><tr key={item.conversion_kind}><td>{({lead:'Lead',qualified_lead:'Lead qualificado',sale:'Venda'})[item.conversion_kind]||item.conversion_kind}</td><td>{integer(item.total)}</td></tr>)}</tbody></table></div>:<Empty message="Conecte o CRM em Monitoramentos para receber confirmações de leads e vendas."/>}</article></>}
    {tab==='conversions'&&<><Kpi label="Conversões da plataforma" value={decimal(channelData?.totals?.conversions)} detail="Importadas da conta de mídia"/><Kpi label="Conversões no site" value={integer(channelData?.observed_conversions)} detail="Eventos de conversão atribuídos"/><Kpi label="Confirmadas pelo CRM" value={integer(channelData?.confirmed_conversions)} detail="Leads, qualificados e vendas"/><article className="reports-panel"><h3>Leitura dos dados</h3><p>Plataforma, site e CRM usam critérios diferentes; os totais ficam separados para comparação.</p></article><article className="reports-panel reports-span-four"><div className="reports-panel-head"><div><h3>Conversões observadas no site</h3><p>Eventos próprios da tag · {periodLabel}</p></div><span>{conversionRows.length} de {(flowData?.events||[]).filter(item=>item.event_kind==='conversion').length} eventos</span></div>{collectionToolbar('Buscar conversão, página ou origem',Array.from(new Set((flowData?.events||[]).filter(item=>item.event_kind==='conversion').map(item=>item.source_label))))}{conversionRows.length?<div className="reports-table-wrap"><table><thead><tr><th>Evento</th><th>Página</th><th>Origem</th><th>Ocorrências</th><th>Mapeados</th></tr></thead><tbody>{conversionRows.map((item,index)=><tr key={`${item.event_name}:${item.page_path}:${index}`}><td>{item.event_name}</td><td>{item.page_path}</td><td>{item.source_label}</td><td>{integer(item.total)}</td><td>{integer(item.mapped)}</td></tr>)}</tbody></table></div>:<Empty message="Nenhuma conversão própria corresponde aos filtros ou foi registrada neste período."/>}</article><article className="reports-panel reports-span-four"><div className="reports-panel-head"><div><h3>Ações de interesse antes da conversão</h3><p>Formulários e cliques WhatsApp atribuídos à campanha, sem somar aos eventos de conversão.</p></div><span>{conversionAssistRows.length} eventos</span></div><div className="reports-supertag-kpis"><Kpi label="Formulários" value={integer(conversionAssistRows.filter(item=>item.event_kind==='form_submit').reduce((sum,item)=>sum+Number(item.total||0),0))} detail="Envios observados"/><Kpi label="WhatsApp" value={integer(conversionAssistRows.filter(item=>item.event_kind==='whatsapp_click').reduce((sum,item)=>sum+Number(item.total||0),0))} detail="Cliques observados"/></div><p className="reports-info">Para registrar outra conversão, configure um bloco com nome de evento em Fluxos e chame trackConversion no site após a ação confirmada.</p></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><div><h3>Etapas confirmadas pelo CRM</h3><p>Fonte independente · agregados protegidos</p></div><span>{confirmed.length} etapas</span></div>{confirmed.length?<div className="reports-table-wrap"><table><thead><tr><th>Etapa</th><th>Confirmações</th></tr></thead><tbody>{confirmed.map(item=><tr key={item.conversion_kind}><td>{({lead:'Lead',qualified_lead:'Lead qualificado',sale:'Venda'})[item.conversion_kind]||item.conversion_kind}</td><td>{integer(item.total)}</td></tr>)}</tbody></table></div>:<Empty message="Nenhuma confirmação recebida do CRM."/>}</article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><div><h3>Conversões reportadas pela mídia</h3><p>Totais da plataforma, sem somar ao site ou CRM</p></div></div>{channelData?.totals?.conversions!=null?<div className="reports-source-total"><strong>{decimal(channelData.totals.conversions)}</strong><span>{campaign.platform} · {periodLabel}</span></div>:<Empty message="Não há conversões da plataforma neste período."/>}</article></>}
    {tab==='heatmap'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Mapa de calor</h3><span>Super Tag</span></div><p>O mapa visual fica nas instalações da Super Tag. Ainda não há vínculo entre uma instalação e esta campanha para filtrar os cliques com segurança.</p><a className="reports-primary-link" href={reportUrl('supertag')}>Abrir Super Tag</a></article>}
    {tab==='performance'&&<><article className="reports-panel reports-span-four"><div className="reports-panel-head"><div><h3>Métricas por data</h3><p>{periodLabel} · valores mantidos por origem e unidade</p></div><span>{performanceRows.length} de {ingestedDaily.length+importedDaily.length} linhas</span></div>{collectionToolbar('Buscar data, origem ou métrica',['Google Ads','Importação'],true)}{ingestedDaily.length+importedDaily.length?(performanceRows.length?<div className="reports-table-wrap"><table><thead><tr><th>Data</th><th>Métrica</th><th>Valor</th><th>Moeda</th><th>Fonte / estado</th></tr></thead><tbody>{performanceRows.map((item,index)=><tr key={`${item.metric_date}:${item.metric_key}:${index}`}><td>{shortDate(item.metric_date)}</td><td>{metricLabels[item.metric_key]||item.metric_key}</td><td>{item.metric_key==='cost'||item.metric_key==='conversion_value'?amount(item.value_numeric,item.currency):integer(item.value_numeric)}</td><td>{item.currency||'—'}</td><td>{item.source==='google_ads_script'?'Google Ads':item.version_count>1?'Revisar divergência':'Importação'}</td></tr>)}</tbody></table></div>:<Empty message="Nenhuma métrica corresponde à busca e aos filtros."/>):<Empty message="Ainda não há dados de performance no período."/>}</article><article className="reports-panel reports-span-four"><div className="reports-panel-head"><div><h3>Detalhe por anúncio e dimensão</h3><p>Valores de origem apresentados sem soma entre dimensões</p></div><span>{dimensionRows.length} de {dimensionalDaily.length} observações</span></div>{collectionToolbar('Buscar anúncio, dimensão ou métrica',[],true)}{dimensionalDaily.length?(dimensionRows.length?<div className="reports-table-wrap"><table><thead><tr><th>Data</th><th>Métrica</th><th>Valor</th><th>Dimensões do export</th></tr></thead><tbody>{dimensionRows.slice(0,500).map((item,index)=><tr key={`${item.metric_date}:${item.metric_key}:${index}`}><td>{shortDate(item.metric_date)}</td><td>{metricLabels[item.metric_key]||item.metric_key}</td><td>{item.metric_key==='cost'||item.metric_key==='conversion_value'?amount(item.value_numeric,item.currency):integer(item.value_numeric)}</td><td>{Object.values(item.dimensions||{}).map(value=>`${value.label}: ${value.value}`).join(' · ')||'Campanha'}</td></tr>)}</tbody></table></div>:<Empty message="Nenhuma observação corresponde à busca e à métrica escolhida."/>):<Empty message="O detalhamento por anúncio aparece quando o export traz essa dimensão."/>}</article></>}
    {tab==='reports'&&<article className="reports-panel reports-span-four"><div className="reports-panel-head"><h3>Relatórios associados</h3><span>{detail.reports.length}</span></div>{detail.reports.length?detail.reports.map(item=><div className="reports-row" key={item.id}><span>{item.campaign_name}<small>Versão {item.revision} · {shortDate(item.updated_at)}</small></span><a className="reports-inline-link" href={reportUrl('reports')}>Abrir relatório ↗</a></div>):<Empty message="Nenhum relatório está associado a esta campanha."/>}</article>}
    {tab==='imports'&&<><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Arquivos de origem</h3><span>{detail.imports.length}</span></div>{detail.imports.length?detail.imports.map(item=><div className="reports-row" key={item.id}><span>{item.original_name}<small>{item.file_kind} · {item.observations} métricas · {shortDate(item.created_at)}</small></span><a className="reports-inline-link" href={reportUrl('imports')}>Abrir Importações ↗</a></div>):<Empty message="Nenhum arquivo importado para esta campanha."/>}</article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Totais por intervalo</h3><span>{detail.range_snapshots.length}</span></div>{detail.range_snapshots.length?detail.range_snapshots.map(item=><div className="reports-row" key={item.id}><span>{shortDate(item.period_start)} – {shortDate(item.period_end)}<small>{item.original_name}</small></span><b>{item.metrics.map(metric=>`${metric.metric_label}: ${metric.value_numeric} ${metric.currency||metric.unit}`).join(' · ')}</b></div>):<Empty message="Snapshots de período aparecem separados dos dados diários."/>}</article></>}
    {tab==='settings'&&<><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Identificação da campanha</h3><span>Dados da conta de mídia</span></div><div className="reports-campaign-settings"><p><small>Plataforma</small><b>{campaign.platform}</b></p><p><small>Conta anunciante</small><b>{campaign.account_name}</b></p><p><small>ID externo da conta</small><b>{campaign.account_external_id}</b></p><p><small>ID externo da campanha</small><b>{campaign.external_id}</b></p><p><small>Status na plataforma</small><b>{stateLabel}</b></p><p><small>Última atualização</small><b>{shortDate(campaign.updated_at)}</b></p></div></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h3>Editar classificação</h3><span>Nome e contexto Reports</span></div>{data.client.role==='viewer'?<Empty message="Seu acesso permite consultar a campanha, sem editar seus dados."/>:<form className="reports-form" onSubmit={saveSettings}>{!campaign.account_id&&<><label>Conectar conta de mídia (opcional)<ReportsNativeSelect value={settings.account_id||''} onChange={e=>setSettings({...settings,account_id:e.target.value})}><option value="">Manter campanha manual</option>{data.accounts.filter(a=>a.account_kind==='advertiser'&&a.customer_id===campaign.customer_id).map(a=><option value={a.id} key={a.id}>{a.name}</option>)}</ReportsNativeSelect></label>{settings.account_id&&<label>ID da campanha na plataforma<ReportsFieldInput required value={settings.external_id||''} onChange={e=>setSettings({...settings,external_id:e.target.value})}/></label>}</>}<label>Nome<ReportsFieldInput required maxLength="240" value={settings.name} onChange={event=>setSettings({...settings,name:event.target.value})}/></label><label>Objetivo<ReportsFieldInput maxLength="160" value={settings.objective} onChange={event=>setSettings({...settings,objective:event.target.value})} placeholder="Ex.: geração de leads"/></label><label>Tipo de canal<ReportsFieldInput maxLength="64" value={settings.channel_type} onChange={event=>setSettings({...settings,channel_type:event.target.value})} placeholder="Ex.: pesquisa, social, vídeo"/></label><ReportsActionButton type="submit" disabled={busy}>Salvar alterações</ReportsActionButton>{settingsNotice&&<small role="status">{settingsNotice}</small>}</form>}</article></>}
  </section>;
}

function Reports({data, save, busy}) {
  const [form, setForm] = useState({campaign_name: '', media_campaign_id: ''});
  const [createOpen, setCreateOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [draft, setDraft] = useState({});
  const [note, setNote] = useState('');
  const [expiresDays, setExpiresDays] = useState('30');
  const [detailError, setDetailError] = useState('');
  const [reviewSource, setReviewSource] = useState(null);
  const [reviewMetrics, setReviewMetrics] = useState([]);
  const [reviewNote, setReviewNote] = useState('');
  const [reviewHistory, setReviewHistory] = useState([]);
  const [suggesting, setSuggesting] = useState(false);
  const [typeSafeReview, setTypeSafeReview] = useState(null);
  const [reviewingTypeSafe, setReviewingTypeSafe] = useState(false);
  const reviewRequestRef = useRef(0);
  const reviewContextRef = useRef('');
  reviewContextRef.current = JSON.stringify({clientId:data.client.client_id,
    reportId:detail?.report?.id, sourceId:reviewSource?.id, metrics:reviewMetrics});
  const invalidateTypeSafeReview = () => {
    reviewRequestRef.current += 1;
    setTypeSafeReview(null);
    setReviewingTypeSafe(false);
  };
  const [planSuggestion, setPlanSuggestion] = useState(null);
  const [planning, setPlanning] = useState(false);
  useEffect(() => {setDetail(null); setDraft({}); setPlanSuggestion(null); invalidateTypeSafeReview(); setDetailError('');}, [data.client.client_id]);
  const submit = async event => {event.preventDefault(); try {await save('/workspaces', form); setForm({campaign_name: '', media_campaign_id: ''}); setCreateOpen(false);} catch (_) { /* Global error banner shows the failure. */ }};
  const open = async (event, reportId) => {event.preventDefault(); setDetailError(''); setPlanSuggestion(null); setReviewSource(null); invalidateTypeSafeReview(); try {const value = await json(`/connect/api/v2/reports/workspaces/${reportId}?client_id=${data.client.client_id}`); setDetail(value); setDraft(value.report.document || {}); setNote('');} catch (failure) {setDetailError(failure.message);}};
  const refresh = async reportId => {const value = await json(`/connect/api/v2/reports/workspaces/${reportId}?client_id=${data.client.client_id}`); setDetail(value); setDraft(value.report.document || {});};
  const update = async event => {event.preventDefault(); if (!detail) return; try {await save(`/workspaces/${detail.report.id}/document`, {revision: detail.report.revision, update_note: note, document: Object.fromEntries(['objective', 'goals', 'management_notes', 'start_date', 'end_date', 'accent'].map(field => [field, draft[field] || '']))}); await refresh(detail.report.id); setNote(''); setDetailError('');} catch (failure) {setDetailError(failure.message);}};
  const planNextAction = async () => {
    if (!detail) return;
    setPlanning(true); setDetailError('');
    try {
      const body = await json(`/connect/api/v2/reports/workspaces/${detail.report.id}/plan`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf},
        body: JSON.stringify({client_id: data.client.client_id}),
      });
      setPlanSuggestion(body.plan);
    } catch (failure) {setDetailError(failure.message);} finally {setPlanning(false);}
  };
  const incorporatePlan = () => {
    if (!planSuggestion) return;
    const addition = `${planSuggestion.title}\n${planSuggestion.steps.map(step => `• ${step}`).join('\n')}`;
    setDraft(current => ({...current, management_notes: [current.management_notes, addition].filter(Boolean).join('\n\n')}));
    setPlanSuggestion(null);
  };
  const publish = async () => {if (!detail) return; try {await save(`/workspaces/${detail.report.id}/publish`, {expires_days: Number(expiresDays)}, false); await refresh(detail.report.id); setDetailError('');} catch (failure) {setDetailError(failure.message);}};
  const unpublish = async () => {if (!detail) return; try {await save(`/workspaces/${detail.report.id}/unpublish`, {}, false); await refresh(detail.report.id); setDetailError('');} catch (failure) {setDetailError(failure.message);}};
  const edit = (field, value) => {setDraft(current => ({...current, [field]: value})); if (field === 'objective' || field === 'goals') setPlanSuggestion(null);};
  const openReview = async source => {
    invalidateTypeSafeReview();
    const requestId = reviewRequestRef.current;
    try {const body = await json(`/connect/relatorios/${detail.report.id}/fontes/${source.id}/revisar`); if (requestId !== reviewRequestRef.current) return; setReviewSource(source); setReviewMetrics(body.metrics?.length ? body.metrics : [{name: '', raw: '', unit: 'count', definition: '', scope: '', evidence: ''}]); setReviewHistory(body.history || []); setReviewNote(''); setDetailError('');}
    catch (failure) {setDetailError(failure.message);}
  };
  const suggestReview = async () => {
    if (!reviewSource) return;
    const requestId = reviewRequestRef.current;
    const context = reviewContextRef.current;
    setSuggesting(true); setDetailError('');
    try {
      const payload = new FormData(); payload.append('_csrf', data.csrf);
      const response = await fetch(`/connect/relatorios/${detail.report.id}/fontes/${reviewSource.id}/sugerir`, {method: 'POST', credentials: 'same-origin', body: payload});
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `Falha HTTP ${response.status}`);
      if (requestId !== reviewRequestRef.current || context !== reviewContextRef.current) return;
      invalidateTypeSafeReview();
      setReviewMetrics(body.suggestion.metrics.length ? body.suggestion.metrics : [{name: '', raw: '', unit: 'count', definition: '', scope: '', evidence: ''}]);
    } catch (failure) {setDetailError(failure.message);} finally {setSuggesting(false);}
  };
  const reviewWithTypeSafe = async () => {
    if (!reviewSource) return;
    const requestId = ++reviewRequestRef.current;
    const context = reviewContextRef.current;
    setReviewingTypeSafe(true); setDetailError('');
    setTypeSafeReview(null);
    try {
      const body = await json(`/connect/relatorios/${detail.report.id}/fontes/${reviewSource.id}/revisar-typesafe`, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf},
        body: JSON.stringify({metrics: reviewMetrics}),
      });
      if (requestId === reviewRequestRef.current && context === reviewContextRef.current)
        setTypeSafeReview(body.review);
    } catch (failure) {
      if (requestId === reviewRequestRef.current && context === reviewContextRef.current)
        setDetailError(failure.message);
    } finally {
      if (requestId === reviewRequestRef.current) setReviewingTypeSafe(false);
    }
  };
  const updateReviewMetric = (index, key, value) => {
    invalidateTypeSafeReview();
    setReviewMetrics(current => current.map((item, itemIndex) => itemIndex === index ? {...item, [key]: value} : item));
  };
  const saveReview = async event => {
    event.preventDefault(); if (!reviewSource) return;
    try {
      const payload = {revision: detail.report.revision, note: reviewNote, metrics: reviewMetrics.map(item => ({name: item.name, value: item.raw, unit: item.unit, definition: item.definition, scope: item.scope, evidence: item.evidence}))};
      await json(`/connect/relatorios/${detail.report.id}/fontes/${reviewSource.id}/revisar?client_id=${data.client.client_id}`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify(payload)});
      await refresh(detail.report.id); setReviewSource(null); setReviewNote(''); setTypeSafeReview(null);
    } catch (failure) {setDetailError(failure.message);}
  };
  return <><section className="reports-report-library"><article className="reports-panel"><div className="reports-panel-head reports-panel-head--actions"><div className="reports-list-head-actions"><span>{data.reports.length} relatórios</span>{data.client.role !== 'viewer' && <ReportsActionButton className="reports-report-create" color="primary" onClick={() => setCreateOpen(true)}>Criar relatório</ReportsActionButton>}</div></div><div className="reports-grid reports-grid--three">{data.reports.length ? data.reports.map(item => <a className="reports-panel reports-report-card" key={item.id} href={reportUrl('reports')} onClick={event => open(event, item.id)}><span>Relatório · v{item.revision}</span><h2>{item.campaign_name}</h2><p>{item.project_ref || 'Sem projeto associado'}</p><small>Atualizado em {shortDate(item.updated_at)}</small></a>) : <Empty message="Nenhum relatório ainda. Crie um independente ou associado a uma campanha." />}</div></article><ReportsDrawer open={createOpen} onOpenChange={setCreateOpen} onDiscard={()=>setForm({campaign_name:'',media_campaign_id:''})} title="Criar relatório" description="O relatório pertence a este cliente; a campanha é opcional." context={data.client.client_name}>{data.client.role !== 'viewer' && <form className="reports-form" onSubmit={submit}><label>Nome<ReportsFieldInput required maxLength="200" value={form.campaign_name} onChange={event => setForm({...form, campaign_name: event.target.value})} placeholder="Ex.: Resultado de setembro" /></label><label>Campanha (opcional)<ReportsNativeSelect value={form.media_campaign_id} onChange={event => setForm({...form, media_campaign_id: event.target.value})}><option value="">Sem campanha vinculada</option>{data.campaigns.map(item => <option key={item.id} value={item.id}>{item.account_name} · {item.name}</option>)}</ReportsNativeSelect></label><ReportsActionButton type="submit" disabled={busy}>Criar relatório</ReportsActionButton></form>}</ReportsDrawer></section>
    {detailError && <p className="reports-error" role="alert">{detailError}</p>}
    {detail && <section className="reports-detail-layout" aria-label="Detalhe do relatório"><div className="reports-detail-main"><article className="reports-panel"><div className="reports-panel-head"><h2>{detail.report.campaign_name}</h2><span>Versão {detail.report.revision} · {shortDate(detail.report.updated_at)}</span></div><form className="reports-form" onSubmit={update}><label>Objetivo<ReportsTextArea disabled={data.client.role === 'viewer'} maxLength="2000" rows="3" value={draft.objective || ''} onChange={event => edit('objective', event.target.value)} /></label><label>Metas<ReportsTextArea disabled={data.client.role === 'viewer'} maxLength="4000" rows="3" value={draft.goals || ''} onChange={event => edit('goals', event.target.value)} /></label><label>Notas de gestão<ReportsTextArea disabled={data.client.role === 'viewer'} maxLength="8000" rows="4" value={draft.management_notes || ''} onChange={event => edit('management_notes', event.target.value)} /></label><div className="reports-form-pair"><label>Início<ReportsFieldInput disabled={data.client.role === 'viewer'} type="date" value={draft.start_date || ''} onChange={event => edit('start_date', event.target.value)} /></label><label>Fim<ReportsFieldInput disabled={data.client.role === 'viewer'} type="date" value={draft.end_date || ''} onChange={event => edit('end_date', event.target.value)} /></label><label>Cor<ReportsFieldInput disabled={data.client.role === 'viewer'} type="color" value={draft.accent || '#1767c5'} onChange={event => edit('accent', event.target.value)} /></label></div>{data.client.role !== 'viewer' && <><label>Nota desta versão<ReportsFieldInput required maxLength="2000" value={note} onChange={event => setNote(event.target.value)} placeholder="O que mudou neste relatório?" /></label><ReportsActionButton type="submit" disabled={busy}>Salvar atualização</ReportsActionButton></>}</form></article>
      <article className="reports-panel"><div className="reports-panel-head"><h2>Fontes e evidências</h2><span>{detail.sources.length} fontes</span></div>{detail.sources.length ? detail.sources.map(item => <div className="reports-row" key={item.id}><span>{item.original_name} · {item.supplier || 'Fornecedor não informado'} · {item.status === 'reviewed' ? 'Revisada' : 'Aguardando revisão'}</span><ReportsActionButton className="reports-inline-link" type="button" onClick={() => openReview(item)}>Revisar ↗</ReportsActionButton><a className="reports-inline-link" href={`/connect/relatorios/${detail.report.id}/fontes/${item.id}`} target="_blank" rel="noopener noreferrer">Abrir print ↗</a></div>) : <Empty message="As fontes recebidas aparecerão aqui." />}<div className="reports-form-pair"><label>Prints<ReportsFieldInput type="file" multiple accept="image/png,image/jpeg,image/webp" id="report-source-files" /></label><label>Origem<ReportsFieldInput maxLength="200" id="report-source-supplier" placeholder="Ex.: Meta Ads" /></label><label>Início<ReportsFieldInput type="date" id="report-source-start" /></label><label>Fim<ReportsFieldInput type="date" id="report-source-end" /></label></div>{data.client.role !== 'viewer' && <ReportsActionButton type="button" disabled={busy} onClick={async () => {const files=document.getElementById('report-source-files')?.files;if(!files?.length)return;const payload=new FormData();Array.from(files).forEach(file=>payload.append('prints',file));payload.append('supplier',document.getElementById('report-source-supplier')?.value||'');payload.append('period_start',document.getElementById('report-source-start')?.value||'');payload.append('period_end',document.getElementById('report-source-end')?.value||'');payload.append('_csrf',data.csrf);try{const response=await fetch(`/connect/relatorios/${detail.report.id}/fontes`,{method:'POST',body:payload,credentials:'same-origin'});if(!response.ok)throw new Error(`Falha HTTP ${response.status}`);await refresh(detail.report.id);}catch(failure){setDetailError(failure.message);}}}>Receber fontes</ReportsActionButton>}</article>
      {reviewSource && <article className="reports-panel"><div className="reports-panel-head"><h2>Revisar fonte · {reviewSource.original_name}</h2><div><ReportsActionButton type="button" className="reports-text-button" disabled={suggesting || data.client.role==='viewer'} onClick={suggestReview}>{suggesting ? 'Lendo print…' : 'Sugerir com IA'}</ReportsActionButton><ReportsActionButton type="button" className="reports-text-button" disabled={reviewingTypeSafe || data.client.role==='viewer' || !reviewMetrics.some(metric=>metric.name&&metric.raw&&metric.evidence)} onClick={reviewWithTypeSafe}>{reviewingTypeSafe ? 'Revisando evidências…' : 'Comparar trechos com TypeSafe'}</ReportsActionButton><ReportsActionButton type="button" className="reports-text-button" onClick={() => {invalidateTypeSafeReview(); setReviewSource(null);}}>Fechar</ReportsActionButton></div></div><img className="reports-source-preview" src={`/connect/relatorios/${detail.report.id}/fontes/${reviewSource.id}`} alt={`Print ${reviewSource.original_name}`} /><p>Confira cada valor e evidência no print antes de confirmar. A sugestão de extração não altera os dados até a revisão.</p>{typeSafeReview && <div className="reports-suggestion"><strong>Leitura do trecho informado · confira no print</strong><p>O TypeSafe compara os valores com o texto informado. Ele não verifica se esse texto aparece no print. Confira a fonte original; concentração não é chance de acerto.</p>{typeSafeReview.judgments.map(item=><p key={item.index}>{item.name}: {item.judgment==='supported'?'trecho informado compatível':item.judgment==='contradicted'?'possível divergência':'evidência insuficiente'} · concentração {Math.round(item.confidence*100)}%</p>)}<p>Esta leitura não alterou os valores nem verificou a imagem. Compare cada trecho com o print antes de confirmar.</p>{typeSafeReview.omitted_count>0&&<p>{typeSafeReview.omitted_count} indicadores ficaram fora desta revisão.</p>}</div>}{reviewHistory.map(item => <p key={item.report_revision}>Revisão v{item.report_revision} · {item.note} · {shortDate(item.created_at)}</p>)}<form className="reports-form" onSubmit={saveReview}><div className="reports-form-pair">{reviewMetrics.map((metric,index) => <fieldset className="reports-metric-review" key={index}><label>Indicador<ReportsFieldInput required maxLength="120" value={metric.name} onChange={event => updateReviewMetric(index,'name',event.target.value)} /></label><label>Valor (use vírgula decimal)<ReportsFieldInput inputMode="decimal" value={metric.raw || ''} onChange={event => updateReviewMetric(index,'raw',event.target.value)} /></label><label>Unidade<ReportsNativeSelect value={metric.unit} onChange={event => updateReviewMetric(index,'unit',event.target.value)}>{['count','BRL','USD','percent','seconds'].map(unit => <option key={unit}>{unit}</option>)}</ReportsNativeSelect></label>{[['definition','Definição'],['scope','Escopo'],['evidence','Evidência']].map(([key,label]) => <label key={key}>{label}<ReportsFieldInput required maxLength="1000" value={metric[key] || ''} onChange={event => updateReviewMetric(index,key,event.target.value)} /></label>)}{reviewMetrics.length>1 && <ReportsActionButton type="button" className="reports-text-button" onClick={() => {setReviewMetrics(reviewMetrics.filter((_,i)=>i!==index)); invalidateTypeSafeReview();}}>Remover</ReportsActionButton>}</fieldset>)}</div>{reviewMetrics.length<60 && <ReportsActionButton type="button" className="reports-text-button" onClick={() => {setReviewMetrics([...reviewMetrics,{name:'',raw:'',unit:'count',definition:'',scope:'',evidence:''}]); invalidateTypeSafeReview();}}>+ Indicador</ReportsActionButton>}<label>Nota da revisão<ReportsTextArea required maxLength="2000" value={reviewNote} onChange={event => setReviewNote(event.target.value)} /></label><ReportsActionButton disabled={busy || data.client.role==='viewer'} type="submit">Confirmar e registrar versão</ReportsActionButton></form></article>}
      </div><aside className="reports-detail-assistant" aria-label="Assistente do relatório"><article className="reports-panel reports-assistant-card"><div className="reports-assistant-heading"><span className="reports-assistant-avatar" aria-hidden="true">C</span><div><h2>Assistente</h2><small>Contexto do relatório</small></div></div><p>Use o TypeSafe para sugerir próximos passos com base no objetivo e nas métricas revisadas. A sugestão só entra no documento quando você escolher incorporar e salvar.</p>{data.client.role !== 'viewer' && <ReportsActionButton type="button" className="reports-assistant-primary" disabled={planning} onClick={planNextAction}>{planning ? 'Preparando sugestão…' : 'Planejar próximo passo'}</ReportsActionButton>}{planSuggestion && <div className="reports-suggestion"><strong>{planSuggestion.title}</strong><ul>{planSuggestion.steps.map((step,index)=><li key={index}>{step}</li>)}</ul><ReportsActionButton type="button" className="reports-text-button" onClick={incorporatePlan}>Incorporar às notas</ReportsActionButton></div>}<div className="reports-assistant-hint"><strong>Revisão de evidências</strong><span>{reviewSource ? `Revisando ${reviewSource.original_name}` : `${detail.sources.length} fontes disponíveis`}</span><small>{reviewSource ? 'A leitura compara o texto informado; confira cada trecho no print antes de confirmar.' : 'Abra Revisar em uma fonte para conferir os valores e a evidência original.'}</small></div></article><article className="reports-panel reports-assistant-publication"><div className="reports-panel-head"><h2>Publicação</h2><span>{detail.public_link ? 'Link ativo' : 'Privado'}</span></div>{detail.public_link ? <><p>{detail.public_link.expires_at ? `Disponível até ${shortDate(detail.public_link.expires_at)}.` : 'Disponível sem data de expiração.'}</p><a className="reports-inline-link" href={`/connect/r/${detail.public_link.token}`} target="_blank" rel="noopener noreferrer">Abrir link público ↗</a>{data.client.role !== 'viewer' && <ReportsActionButton className="reports-text-button" type="button" disabled={busy} onClick={unpublish}>Revogar link</ReportsActionButton>}</> : data.client.role !== 'viewer' ? <div className="reports-form"><label>Validade<ReportsNativeSelect value={expiresDays} onChange={event => setExpiresDays(event.target.value)}><option value="7">7 dias</option><option value="30">30 dias</option><option value="90">90 dias</option><option value="0">Sem expiração</option></ReportsNativeSelect></label><ReportsActionButton type="button" disabled={busy} onClick={publish}>Publicar relatório</ReportsActionButton></div> : <p>Este relatório ainda não foi publicado.</p>}<div className="reports-association-history"><h3>Versões</h3>{detail.versions.map(item => <p key={item.revision}>v{item.revision} · {item.note} · {shortDate(item.created_at)}</p>)}</div></article></aside></section>}
  </>;
}

function Links({data, save, busy}) {
  const [form, setForm] = useState({url: '', mode: 'destination'});
  const [result, setResult] = useState(null);
  const [suggestion, setSuggestion] = useState(null);
  const [editing, setEditing] = useState(null);
  const [campaignId, setCampaignId] = useState('');
  const [reportId, setReportId] = useState('');
  const [history, setHistory] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);
  const shareUrl = token => `${location.origin}/connect/public/link-tests/${encodeURIComponent(token)}`;
  const copyShare = async token => {try {await navigator.clipboard.writeText(shareUrl(token));} catch (_) { /* Browser may deny clipboard access. */ }};
  useEffect(() => {json('/connect/api/v2/reports/ai/status').then(setAiStatus).catch(() => setAiStatus(null));}, []);
  useEffect(() => {setEditing(null); setSuggestion(null); setHistory(null);}, [data.client.client_id]);
  const submit = async event => {event.preventDefault(); try {const body = await save('/link-tests', form); setResult(body.result);} catch (_) { /* Global error banner shows the failure. */ }};
  const choose = run => {setEditing(run); setSuggestion(null); setCampaignId(run.media_campaign_id ? String(run.media_campaign_id) : ''); setReportId(run.report_workspace_id ? String(run.report_workspace_id) : ''); setHistory(null);};
  const suggest = async run => {choose(run); try {const body = await save(`/link-tests/${run.id}/suggest-campaign`, {}, false); setSuggestion(body); if (body.suggestion) {setCampaignId(String(body.suggestion.id)); setReportId('');}} catch (_) { /* Global error banner shows the failure. */ }};
  const confirm = async event => {event.preventDefault(); if (!editing) return; try {await save(`/link-tests/${editing.id}/association`, {campaign_id: campaignId || null, report_id: reportId || null}); setEditing(null); setSuggestion(null); setHistory(null);} catch (_) { /* Global error banner shows the failure. */ }};
  const showHistory = async run => {choose(run); try {const body = await json(`/connect/api/v2/reports/link-tests/${run.id}/association-history?client_id=${data.client.client_id}`); setHistory(body.history);} catch (_) { /* Global error banner shows the failure. */ }};
  const selectedCampaign = data.campaigns.find(item => String(item.id) === campaignId);
  const availableReports = data.reports.filter(item => !item.media_campaign_id || String(item.media_campaign_id) === campaignId).filter(item => !item.account_id || item.account_id === selectedCampaign?.account_id);
  return <><section className="reports-grid reports-grid--three"><article className="reports-panel"><div className="reports-panel-head"><h2>Testar destino</h2><span>Link Tester</span></div><form className="reports-form" onSubmit={submit}>
    <label>URL<ReportsFieldInput required type="url" maxLength="2048" value={form.url} onChange={event => setForm({...form, url: event.target.value})} placeholder="https://exemplo.com/pagina?utm_source=..." /></label>
    <label>Análise<ReportsNativeSelect value={form.mode} onChange={event => setForm({...form, mode: event.target.value})}><option value="destination">Destino e redirecionamentos</option><option value="media">Medição de mídia</option><option value="agentic">Presença para agentes</option></ReportsNativeSelect></label>
    <ReportsActionButton type="submit" disabled={busy}>Analisar link</ReportsActionButton>
  </form></article><article className="reports-panel reports-span-two"><div className="reports-panel-head"><h2>Resultado</h2>{result && <span>{result.score}/100</span>}</div>{result ? <><strong className="reports-result-title">{result.status_label}</strong><p>{result.summary}</p><p className="reports-url">{result.final_url}</p>{result.public_token && <ReportsActionButton type="button" className="reports-text-button" onClick={() => copyShare(result.public_token)}>Copiar link de compartilhamento</ReportsActionButton>}{result.alerts?.length > 0 && <ul className="reports-alerts">{result.alerts.map((alert, index) => <li key={index}>{alert}</li>)}</ul>}</> : <Empty message="Execute uma análise para ver o resultado e as evidências." />}</article>
    <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Histórico</h2><span>{data.link_tests.length} recentes</span></div>{aiStatus && !aiStatus.configured && <p className="reports-suggestion">TypeSafe ainda não está configurada nas Integrações do Cadu. IDs exatos de campanha continuam reconhecidos por regra; a revisão semântica fica disponível após configurar a chave.</p>}{data.link_tests.length ? <div className="reports-table-wrap"><table><thead><tr><th>Destino</th><th>Tipo</th><th>Resultado</th><th>Data</th><th>Associação confirmada</th><th>Ações</th></tr></thead><tbody>{data.link_tests.map(item => <tr key={item.id}><td>{item.final_url}</td><td>{item.mode}</td><td>{item.score}/100 · {item.status_label}</td><td>{shortDate(item.created_at)}</td><td>{item.campaign_name || 'Sem campanha'}{item.report_name ? ` · ${item.report_name}` : ''}</td><td><ReportsActionButton type="button" className="reports-text-button" disabled={busy} onClick={() => choose(item)}>Associar</ReportsActionButton> · <ReportsActionButton type="button" className="reports-text-button" disabled={busy} onClick={() => suggest(item)}>Sugerir</ReportsActionButton> · <ReportsActionButton type="button" className="reports-text-button" onClick={() => showHistory(item)}>Decisões</ReportsActionButton>{item.public_token && <> · <ReportsActionButton type="button" className="reports-text-button" onClick={() => copyShare(item.public_token)}>Copiar link</ReportsActionButton></>}</td></tr>)}</tbody></table></div> : <Empty message="Os testes realizados neste cliente aparecerão aqui." />}</article>
    {editing && <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Associar link à operação</h2><span>Decisão do usuário · {editing.final_url}</span></div>{suggestion && <p className="reports-suggestion">{suggestion.suggestion ? <>Sugestão: <strong>{suggestion.suggestion.name}</strong> · {suggestion.model === 'exact_id' ? 'ID externo exato' : suggestion.model === 'exact_name' ? 'nome exato' : `concentração ${Math.round((suggestion.confidence || 0) * 100)}%`}. Confirme antes de salvar.</> : (suggestion.reason || 'Nenhuma campanha sugerida.')}{suggestion.page_role && <span className="reports-suggestion-role">Tipo provável de página: {({landing: 'entrada', form: 'formulário', thank_you: 'obrigado', content: 'conteúdo', unknown: 'indefinido'})[suggestion.page_role] || suggestion.page_role}.</span>}</p>}<form className="reports-form" onSubmit={confirm}><label>Campanha<ReportsNativeSelect value={campaignId} onChange={event => {setCampaignId(event.target.value); setReportId('');}}><option value="">Sem campanha · limpar associação</option>{data.campaigns.map(item => <option key={item.id} value={item.id}>{item.account_name} · {item.name}</option>)}</ReportsNativeSelect></label><label>Relatório (opcional)<ReportsNativeSelect value={reportId} disabled={!campaignId} onChange={event => setReportId(event.target.value)}><option value="">Sem relatório</option>{availableReports.map(item => <option key={item.id} value={item.id}>{item.campaign_name}</option>)}</ReportsNativeSelect></label>{data.client.role !== 'viewer' && <ReportsActionButton type="submit" disabled={busy}>Confirmar associação</ReportsActionButton>}</form>{history && <div className="reports-association-history"><h3>Decisões anteriores</h3>{history.length ? history.map((item, index) => <p key={`${item.decided_at}-${index}`}>{shortDate(item.decided_at)} · {item.action === 'clear' ? 'Associação removida' : `Campanha #${item.campaign_id}${item.report_id ? ` · relatório #${item.report_id}` : ''}`} · usuário #{item.decided_by}</p>) : <p>Nenhuma decisão anterior.</p>}</div>}</article>}
  </section>
  </>;
}

function Monitor({data, save, busy}) {
  const [keys, setKeys] = useState([]);
  const [runs, setRuns] = useState([]);
  const [label, setLabel] = useState('Google Ads · monitoramento');
  const [sourceKind, setSourceKind] = useState('google_ads_script');
  const [managerAccountId, setManagerAccountId] = useState('');
  const [accountIds, setAccountIds] = useState([]);
  const [script, setScript] = useState('');
  const [generatedKind, setGeneratedKind] = useState('google_ads_script');
  const [localError, setLocalError] = useState('');
  const [revokeId, setRevokeId] = useState('');
  const managers = data.accounts.filter(account => account.platform === 'google_ads' && account.account_kind === 'manager' && account.status !== 'disabled' && validGoogleAdsAccountId(account.external_id));
  const advertisers = data.accounts.filter(account => account.platform === 'google_ads' && account.account_kind === 'advertiser' && account.status !== 'disabled' && validGoogleAdsAccountId(account.external_id));
  const invalidGoogleAdsAccounts = data.accounts.filter(account => account.platform === 'google_ads' && account.status !== 'disabled' && !validGoogleAdsAccountId(account.external_id));
  const children = advertisers.filter(account => String(account.parent_account_id || '') === managerAccountId);
  const directAdvertisers = advertisers.filter(account => !account.parent_account_id);
  const hasUsableManagerSetup = managers.some(manager => advertisers.some(account => String(account.parent_account_id || '') === String(manager.id)));
  const invalidIntegrationAccounts = managerAccountId
    ? invalidGoogleAdsAccounts.filter(account => account.account_kind === 'advertiser' && String(account.parent_account_id || '') === managerAccountId)
    : directAdvertisers.length || hasUsableManagerSetup ? [] : invalidGoogleAdsAccounts.filter(account =>
      (account.account_kind === 'advertiser' && !account.parent_account_id) ||
      (account.account_kind === 'manager' && data.accounts.some(child => child.account_kind === 'advertiser' && child.status !== 'disabled' && String(child.parent_account_id || '') === String(account.id))));
  const formatGoogleId = value => String(value).replace(/^(\d{3})(\d{3})(\d{4})$/, '$1-$2-$3');
  const reload = () => json(`/connect/api/v2/reports/ingest-keys?client_id=${data.client.client_id}`).then(value => {setKeys(value.keys); setRuns(value.runs || []);});
  useEffect(() => {reload().catch(failure => setLocalError(failure.message));}, [data.client.client_id]);
  const create = async event => {
    event.preventDefault();
    try {
      let template = '';
      if (sourceKind === 'google_ads_script') {
        const response = await fetch('/static/cadu_connect/google-ads-engine-v2.js', {credentials: 'same-origin'});
        if (!response.ok) throw new Error('Não foi possível carregar o script do Google Ads.');
        template = await response.text();
      }
      const selectedIds = accountIds;
      const created = await save('/ingest-keys', {label, source_kind: sourceKind, manager_account_id: managerAccountId ? managers.find(item => String(item.id) === managerAccountId)?.external_id : '', account_ids: sourceKind === 'google_ads_script' ? selectedIds : []}, false);
      if (sourceKind === 'google_ads_script') {
        const scriptIds = created.allowed_account_ids.map(formatGoogleId);
        setScript(template.replace('__CADU_INGEST_URL__', `${location.origin}/connect/api/v1/reports/ingest/google-ads/v2`).replace('__CADU_API_KEY__', created.token).replace('__CADU_ACCOUNT_IDS__', JSON.stringify(scriptIds)));
      } else {
        setScript(`POST ${location.origin}/connect/api/v1/reports/ingest/conversions\nAuthorization: Bearer ${created.token}\nContent-Type: application/json\n\n${JSON.stringify({events: [{external_event_id: 'pedido-123', visitor_id: 'UUID recebido de window.CaduSuperTag.getVisitorId()', kind: 'sale', occurred_at: new Date().toISOString(), value_micros: 129000000, currency: 'BRL'}]}, null, 2)}`);
      }
      setGeneratedKind(sourceKind);
      await reload();
    } catch (failure) {setLocalError(failure.message);}
  };
  const revoke = async id => {
    try {await save(`/ingest-keys/${id}/revoke`, {}, false); await reload(); setRevokeId('');} catch (failure) {setLocalError(failure.message);}
  };
  return <section className="reports-media-data-page">
    <div className="reports-media-container">
      <div className="reports-media-layout">
        <aside className="reports-media-sidebar">
          <div className="reports-panel reports-media-status">
            <div className="reports-panel-head"><h2>Status</h2></div>
            <div className="reports-media-kpis">
              <div className="reports-media-kpi">
                <span className="reports-media-kpi__label">Fontes conectadas</span>
                <strong className="reports-media-kpi__value">{keys.length}</strong>
              </div>
              <div className="reports-media-kpi">
                <span className="reports-media-kpi__label">Últimos envios</span>
                <strong className="reports-media-kpi__value">{runs.length}</strong>
              </div>
            </div>
          </div>
        </aside>
        <main className="reports-media-main">
          <article className="reports-panel reports-media-connect">
            <div className="reports-panel-head"><h2>Conectar fonte</h2><span>Instalação</span></div>
            <p>Google Ads envia campanhas e métricas. O webhook recebe conversões confirmadas pelo CRM sem dados pessoais.</p>
            {data.client.role !== 'viewer' && <form className="reports-form" onSubmit={create}>
              <label>Fonte
                <ReportsNativeSelect value={sourceKind} onChange={event => {setSourceKind(event.target.value); setLabel(event.target.value === 'conversion_webhook' ? 'CRM · conversões' : 'Google Ads · monitoramento');}}>
                  <option value="google_ads_script">Google Ads Script</option>
                  <option value="conversion_webhook">CRM / conversões</option>
                </ReportsNativeSelect>
              </label>
              <label>Nome da instalação
                <ReportsFieldInput required maxLength="120" value={label} onChange={event => setLabel(event.target.value)} />
              </label>
              {sourceKind === 'google_ads_script' && <>
                <label>MCC / conta gerente
                  <ReportsNativeSelect value={managerAccountId} onChange={event => {setManagerAccountId(event.target.value); setAccountIds([]);}}>
                    <option value="">Instalação direta em uma conta anunciante</option>
                    {managers.map(item => <option key={item.id} value={item.id}>{item.name} · {formatGoogleId(item.external_id)}</option>)}
                  </ReportsNativeSelect>
                </label>
                {managerAccountId ? <fieldset className="reports-account-picker"><legend>Contas anunciantes autorizadas</legend>{children.length ? children.map(item => <label key={item.id} className="reports-checkbox"><ReportsFieldInput type="checkbox" checked={accountIds.includes(item.external_id)} onChange={event => setAccountIds(event.target.checked ? [...accountIds, item.external_id] : accountIds.filter(id => id !== item.external_id))} />{item.name} · {formatGoogleId(item.external_id)}</label>) : <small>Cadastre anunciantes válidos e associe-os a esta MCC na área Contas.</small>}</fieldset> : <label>Conta anunciante
                  <ReportsNativeSelect value={accountIds[0] || ''} onChange={event => setAccountIds(event.target.value ? [event.target.value] : [])}>
                    <option value="">Selecione a conta que receberá os dados</option>
                    {directAdvertisers.map(item => <option key={item.id} value={item.external_id}>{item.name} · {formatGoogleId(item.external_id)}</option>)}
                  </ReportsNativeSelect>
                  <small>Use o ID de cliente Google Ads com 10 dígitos. Para várias contas, cadastre uma MCC e associe os anunciantes em Contas.</small>
                </label>}
              </>}
              <ReportsActionButton disabled={busy || (sourceKind === 'google_ads_script' && (!accountIds.length || (managerAccountId && !children.length)))} type="submit">Gerar integração</ReportsActionButton>
              {sourceKind === 'google_ads_script' && invalidIntegrationAccounts.length > 0 && <p className="reports-integration-hint" role="status">{invalidIntegrationAccounts.length} conta(s) vinculada(s) sem ID de 10 dígitos. Corrija a conta na página Contas para gerar a integração.</p>}
            </form>}
            {localError && <p className="reports-error">{localError}</p>}
          </article>
          {script && <article className="reports-panel reports-media-script">
            <div className="reports-panel-head">
              <h2>{generatedKind === 'conversion_webhook' ? 'Contrato do webhook' : 'Script gerado'}</h2>
              <span>Copie agora: a chave não será mostrada novamente</span>
            </div>
            <ReportsTextArea className="reports-code" readOnly value={script} aria-label="Código da integração" />
            <ReportsActionButton className="reports-copy" onClick={() => navigator.clipboard.writeText(script)}>Copiar</ReportsActionButton>
          </article>}
          <article className="reports-panel reports-media-keys">
            <div className="reports-panel-head"><h2>Chaves de ingestão</h2><span>{keys.length} criadas</span></div>
            {keys.length ? <div className="reports-table-wrap"><table><thead><tr><th>Nome</th><th>Fonte</th><th>MCC / contas permitidas</th><th>Último envio</th><th>Estado</th><th></th></tr></thead><tbody>{keys.map(item => <tr key={item.id}><td>{item.label}</td><td>{item.source_kind === 'conversion_webhook' ? 'CRM' : 'Google Ads'}</td><td>{item.source_kind === 'google_ads_script' ? <>{item.manager_external_id ? `MCC ${formatGoogleId(item.manager_external_id)} · ` : ''}{item.allowed_account_ids?.length ? item.allowed_account_ids.map(formatGoogleId).join(', ') : item.bound_account_id || 'Vincula no primeiro envio'}</> : '—'}</td><td>{shortDate(item.last_used_at)}</td><td>{sourceHealth(item)}</td><td>{!item.revoked_at && data.client.role !== 'viewer' && <ReportsActionButton className="reports-text-button" disabled={busy} onClick={() => setRevokeId(item.id)}>Revogar</ReportsActionButton>}</td></tr>)}</tbody></table></div> : <Empty message="Gere uma chave para conectar uma fonte." />}
          </article>
          <article className="reports-panel reports-media-runs">
            <div className="reports-panel-head"><h2>Últimos envios</h2><span>{runs.length} lotes</span></div>
            {runs.length ? <div className="reports-table-wrap"><table><thead><tr><th>Recebido</th><th>Período</th><th>Linhas</th><th>Estado</th></tr></thead><tbody>{runs.map(item => <tr key={item.id}><td>{shortDate(item.created_at)}</td><td>{shortDate(item.period_start)} – {shortDate(item.period_end)}</td><td>{integer(item.record_count)}</td><td>{item.status === 'completed' ? 'Concluído' : item.status}</td></tr>)}</tbody></table></div> : <Empty message="Os lotes recebidos aparecerão aqui." />}
          </article>
        </main>
      </div>
    </div>
    <ReportsConfirmDialog open={Boolean(revokeId)} title="Revogar chave de ingestão" description="O script que usa esta chave deixará de enviar dados. Os envios anteriores permanecem no histórico." confirmLabel="Revogar chave" busy={busy} onCancel={() => setRevokeId('')} onConfirm={() => revoke(revokeId)} />
  </section>;
}

function Access({data, save, busy}) {
  const [users, setUsers] = useState([]);
  const [grantOpen, setGrantOpen] = useState(false);
  const [revokeUser, setRevokeUser] = useState(null);
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState('viewer');
  const [exclusive, setExclusive] = useState(false);
  const [localError, setLocalError] = useState('');
  const [accessQuery, setAccessQuery] = useState('');
  const reload = () => json(`/connect/api/v2/reports/access?client_id=${data.client.client_id}`).then(value => setUsers(value.users));
  useEffect(() => {reload().catch(error => setLocalError(error.message));}, [data.client.client_id]);
  const choose = value => {
    setUserId(value);
    const selected = users.find(item => String(item.id) === value);
    setRole(selected?.role && !selected.revoked_at ? selected.role : 'viewer');
    setExclusive(Boolean(selected?.reports_only));
  };
  const grant = async event => {
    event.preventDefault();
    try {await save('/access', {user_id: Number(userId), role, exclusive}, false); await reload(); setLocalError(''); setGrantOpen(false);}
    catch (error) {setLocalError(error.message);}
  };
  const revoke = async user => {
    try {await save(`/access/${user.id}/revoke`, {}, false); await reload(); setLocalError(''); setRevokeUser(null);}
    catch (error) {setLocalError(error.message);}
  };
  const activeUsers = users.filter(user => user.role && !user.revoked_at);
  const visibleUsers = activeUsers.filter(user => `${user.name} ${user.email || ''}`.toLocaleLowerCase('pt-BR').includes(accessQuery.trim().toLocaleLowerCase('pt-BR')));
  return <><section className="reports-access-page">
    <ReportsDrawer open={grantOpen} onOpenChange={setGrantOpen} onDiscard={()=>{setUserId('');setRole('viewer');setExclusive(false);setLocalError('');}} title="Conceder acesso" description="Defina quem pode consultar ou operar os dados deste cliente." context={data.client.client_name}>
      <p>Defina o acesso à conta principal do Reports. Compartilhamentos restritos são feitos no site ou fluxo.</p>
      {localError && <p className="reports-error" role="alert">{localError}</p>}
      <form className="reports-form" onSubmit={grant}><label>Usuário<ReportsNativeSelect required value={userId} onChange={event => choose(event.target.value)}><option value="">Selecione</option>{users.map(user => <option key={user.id} value={user.id}>{user.name} · {user.email}</option>)}</ReportsNativeSelect></label><label>Papel<ReportsNativeSelect value={role} onChange={event => setRole(event.target.value)}>{Object.entries(ACCESS_ROLE_LABELS).map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label><ReportsActionButton disabled={busy || !userId} type="submit">Salvar acesso</ReportsActionButton></form>
    </ReportsDrawer>
    <article className="reports-panel"><div className="reports-panel-head"><h2>Usuários deste cliente</h2><div className="reports-list-head-actions"><span>{activeUsers.length} ativos</span><ReportsActionButton color="primary" onClick={() => setGrantOpen(true)}>Conceder acesso</ReportsActionButton></div></div>
      {activeUsers.length > 8 && <div className="reports-access-search"><ReportsFieldInput type="search" aria-label="Buscar pessoa" placeholder="Buscar por nome ou e-mail" value={accessQuery} onChange={event => setAccessQuery(event.target.value)}/></div>}
      {visibleUsers.length ? <div className="reports-table-wrap"><table><thead><tr><th>Usuário</th><th>Papel</th><th>Tipo</th><th><span className="reports-sr-only">Ações</span></th></tr></thead><tbody>{visibleUsers.map(user => <tr key={user.id}><td>{user.name}</td><td>{ACCESS_ROLE_LABELS[user.role] || user.role}</td><td>{user.access_scope==='shared'?'Recursos compartilhados':'Conta principal'}</td><td className="reports-flow-table__actions"><ReportsActionButton className="reports-danger-button" disabled={busy} onClick={() => setRevokeUser(user)}>Revogar</ReportsActionButton></td></tr>)}</tbody></table></div> : <Empty message={activeUsers.length ? 'Ninguém corresponde à busca.' : 'Nenhum acesso próprio do Reports concedido para este cliente.'} />}
    </article>
    <ReportsConfirmDialog open={Boolean(revokeUser)} title="Revogar acesso" description={revokeUser ? `Remover o acesso de ${revokeUser.name} a este cliente no Reports?` : ''} confirmLabel="Revogar acesso" busy={busy} onCancel={() => setRevokeUser(null)} onConfirm={() => revoke(revokeUser)} />
  </section>
  </>;
}

// Flows page lives in FlowsPage.jsx.
function BrandingInsights({branding}) {
  const overall = branding?.overall;
  if (!overall || !Number(overall.sessions)) return null;
  const engagedRate = Number(overall.sessions) ? Math.round(100 * Number(overall.engaged_sessions) / Number(overall.sessions)) : 0;
  const coverage = Number(overall.sessions) ? Math.round(100 * Number(overall.measured_sessions) / Number(overall.sessions)) : 0;
  return <div className="reports-supertag-branding">
    <article className="reports-panel"><div className="reports-panel-head"><div><h2>Visão de marca e público</h2><p>Últimos 30 dias · sessões com consentimento e página vista</p></div><span>Site conectado</span></div>
      <div className="reports-supertag-kpis"><Kpi label="Visitantes observados" value={integer(overall.visitors)} detail="Identificadores desta instalação"/><Kpi label="Sessões" value={integer(overall.sessions)} detail={`${integer(overall.closed_sessions)} encerradas por inatividade`}/><Kpi label="Engajamento" value={`${engagedRate}%`} detail="2+ páginas, 10 s ativos ou conversão"/><Kpi label="Tempo ativo médio" value={overall.avg_active_seconds == null?'—':`${decimal(overall.avg_active_seconds)} s`} detail={`${coverage}% das sessões com duração medida`}/></div>
      <p className="reports-info">Média de {decimal(overall.avg_pages || 0)} páginas por sessão · {integer(overall.deep_scroll_sessions)} sessões chegaram a 75% de rolagem. O tempo exclui períodos em que a aba estava oculta.</p>
    </article>
    <article className="reports-panel"><div className="reports-panel-head"><div><h2>Campanhas observadas no site</h2><p>Primeira UTM da sessão; eventos permanecem atribuídos durante a navegação</p></div><span>{branding.campaigns?.length || 0} origens</span></div>
      {branding.campaigns?.length?<div className="reports-table-wrap"><table><thead><tr><th>Campanha</th><th>Visitantes</th><th>Sessões</th><th>Engajadas</th><th>Tempo ativo</th><th>Formulários</th><th>WhatsApp</th><th>Conversões</th></tr></thead><tbody>{branding.campaigns.map(row=><tr key={row.campaign_scope||'sem-campanha'}><td>{row.campaign_scope||'Sem campanha identificada'}</td><td>{integer(row.visitors)}</td><td>{integer(row.sessions)}</td><td>{integer(row.engaged_sessions)}</td><td>{row.avg_active_seconds==null?'—':`${decimal(row.avg_active_seconds)} s`}</td><td>{integer(row.forms)}</td><td>{integer(row.whatsapp_clicks)}</td><td>{integer(row.conversions)}</td></tr>)}</tbody></table></div>:<Empty message="As campanhas aparecem quando o tráfego chega com utm_id ou utm_campaign."/>}
    </article>
    <article className="reports-panel"><div className="reports-panel-head"><div><h2>Coortes de retorno</h2><p>Semana da primeira visita observada · retorno entre 1 e 7 dias</p></div><span>Até 8 semanas</span></div>
      {branding.cohorts?.length?<div className="reports-table-wrap"><table><thead><tr><th>Semana</th><th>Campanha</th><th>Visitantes</th><th>Retornaram</th><th>Taxa</th></tr></thead><tbody>{branding.cohorts.map(row=><tr key={`${row.campaign_scope}:${row.cohort_week}`}><td>{shortDate(row.cohort_week)}</td><td>{row.campaign_scope||'Sem campanha identificada'}</td><td>{integer(row.visitors)}</td><td>{integer(row.returned_7d)}</td><td>{Number(row.visitors)?`${Math.round(100*Number(row.returned_7d)/Number(row.visitors))}%`:'—'}</td></tr>)}</tbody></table></div>:<Empty message="Coortes aparecem após sete dias de visitas consentidas."/>}
    </article>
  </div>;
}

const siteFaviconCache = new Map();

function SiteFavicon({site}) {
  const host = site.allowed_host;
  const [favicon, setFavicon] = useState(() => siteFaviconCache.get(host) ?? `https://${host}/favicon.ico`);
  const [loaded, setLoaded] = useState(false);
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    setFavicon(siteFaviconCache.get(host) ?? `https://${host}/favicon.ico`);
    setLoaded(false);
    setChecked(false);
  }, [host]);
  // The initial stays on screen until an image really loads, so a failing favicon never shows a broken-image icon.
  const recover = async () => {
    setLoaded(false);
    if (checked) {
      siteFaviconCache.set(host, '');
      setFavicon('');
      return;
    }
    setChecked(true);
    try {
      const preview = await json(`/connect/api/v2/reports/supertag/site-check?url=${encodeURIComponent(`https://${host}`)}`);
      const next = preview.favicon || '';
      siteFaviconCache.set(host, next);
      setFavicon(next);
    } catch (_) {
      siteFaviconCache.set(host, '');
      setFavicon('');
    }
  };
  return <span className="reports-site-list-favicon" aria-hidden="true">
    <span className="reports-site-list-favicon__initial">{(site.label || host).trim().charAt(0).toUpperCase()}</span>
    {favicon && <img src={favicon} alt="" referrerPolicy="no-referrer" onLoad={() => setLoaded(true)} onError={recover} style={loaded ? undefined : {visibility: 'hidden'}}/>}
  </span>;
}

function SuperTag({data}) {
  const [sites, setSites] = useState([]);
  const [sitesLoading, setSitesLoading] = useState(true);
  const [sitesLoadFailed, setSitesLoadFailed] = useState(false);
  const [selectedId, setSelectedId] = useState(() => location.pathname.match(/^\/connect\/app\/supertag\/sites\/([0-9a-f-]{36})(?:\/monitor)?\/?$/i)?.[1] || '');
  const [siteTab, setSiteTab] = useState('overview');
  const [siteFlows, setSiteFlows] = useState([]);
  const [siteQuery, setSiteQuery] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [label, setLabel] = useState('Site principal');
  const [host, setHost] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [installOpen, setInstallOpen] = useState(false);
  const [verify, setVerify] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [revokeConfirmOpen, setRevokeConfirmOpen] = useState(false);
  const [siteCheck, setSiteCheck] = useState(null);
  const [checkingSite, setCheckingSite] = useState(false);
  const load = async () => {
    const value = await json(`/connect/api/v2/reports/supertag/sites?client_id=${data.client.client_id}`);
    setSites(value.sites || []);
    if (selectedId && value.sites.some(item => item.id === selectedId)) return;
    setSelectedId('');
  };
  useEffect(() => {
    let active = true;
    setSites([]);
    setSitesLoading(true);
    setSitesLoadFailed(false);
    json(`/connect/api/v2/reports/supertag/sites?client_id=${data.client.client_id}`)
      .then(value => {
        if (!active) return;
        const nextSites = value.sites || [];
        setSites(nextSites);
        setSelectedId(current => current && !nextSites.some(item => item.id === current) ? '' : current);
      })
      .catch(failure => {if (active) {setSitesLoadFailed(true);setError(failure.message);}})
      .finally(() => {if (active) setSitesLoading(false);});
    return () => {active = false;};
  }, [data.client.client_id]);
  useEffect(() => {
    setDetail(null);setSiteFlows([]);setError('');setVerify(null);
    if (!selectedId) {setDetailLoading(false);return;}
    let cancelled=false;setDetailLoading(true);
    Promise.allSettled([
      json(`/connect/api/v2/reports/supertag/sites/${selectedId}/events?client_id=${data.client.client_id}`),
      json(`/connect/api/v2/reports/flow?client_id=${data.client.client_id}&view=create`)
    ]).then(([events,flows])=>{
      if(cancelled)return;
      if(events.status==='fulfilled')setDetail(events.value);
      if(flows.status==='fulfilled')setSiteFlows(flows.value.flows||[]);
      const failures=[];
      if(events.status==='rejected')failures.push(`Não foi possível carregar a atividade: ${events.reason.message}`);
      if(flows.status==='rejected')failures.push(`Não foi possível carregar os fluxos: ${flows.reason.message}`);
      setError(failures.join(' '));
    })
      .finally(()=>{if(!cancelled)setDetailLoading(false);});
    return()=>{cancelled=true;};
  }, [selectedId, data.client.client_id]);
  const create = async event => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const checkedHost = new URL(host.includes('://') ? host : `https://${host}`).host;
      const result = await json(`/connect/api/v2/reports/supertag/sites?client_id=${data.client.client_id}`, {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':data.csrf},
        body:JSON.stringify({label,allowed_host:checkedHost})});
      if (siteCheck?.favicon) siteFaviconCache.set(checkedHost, siteCheck.favicon);
      await load(); location.assign(reportUrl('supertag', {client_id:data.client.client_id}, result.site.id));
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const update = async changes => {
    if (!selectedId) return;
    setBusy(true); setError('');
    try {
      await json(`/connect/api/v2/reports/supertag/sites/${selectedId}?client_id=${data.client.client_id}`, {
        method:'PATCH', headers:{'Content-Type':'application/json','X-CSRF-Token':data.csrf}, body:JSON.stringify(changes)});
      await load();
      const latest = await json(`/connect/api/v2/reports/supertag/sites/${selectedId}/events?client_id=${data.client.client_id}`);
      setDetail(latest);
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const revoke = async () => {
    if (!selectedId) return;
    setBusy(true); setError('');
    try {
      await json(`/connect/api/v2/reports/supertag/sites/${selectedId}/revoke?client_id=${data.client.client_id}`, {
        method:'POST', headers:{'X-CSRF-Token':data.csrf}, body:JSON.stringify({})});
      setSelectedId(''); setDetail(null); setRevokeConfirmOpen(false); await load(); location.assign(reportUrl('supertag'));
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const selected = sites.find(item => item.id === selectedId);
  const copy = async value => {
    try {await navigator.clipboard.writeText(value); setNotice('Copiado.');}
    catch (_) {setNotice('Não foi possível copiar automaticamente. Selecione o código e copie.');}
  };
  const verifyInstall = async () => {
    if (!selectedId) return;
    setVerifying(true); setError('');
    try {
      const [result, latest] = await Promise.all([
        json(`/connect/api/v2/reports/supertag/sites/${selectedId}/verify-install?client_id=${data.client.client_id}`),
        json(`/connect/api/v2/reports/supertag/sites/${selectedId}/events?client_id=${data.client.client_id}`)]);
      setVerify(result); setDetail(latest); await load();
    } catch (failure) {setError(failure.message);} finally {setVerifying(false);}
  };
  const kindTotal = kind => Number((detail?.summary || []).find(item => item.event_kind === kind)?.total || 0);
  const checkSite = async () => {
    if (!host.trim()) return;
    setCheckingSite(true); setSiteCheck(null); setError('');
    try {setSiteCheck(await json(`/connect/api/v2/reports/supertag/site-check?url=${encodeURIComponent(host.trim())}`));}
    catch (failure) {setSiteCheck({error:failure.message});}
    finally {setCheckingSite(false);}
  };
  const downloadSnippet = () => {
    if (!selected) return;
    const blob = new Blob([selected.snippet], {type:'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
    anchor.href=url; anchor.download=`cadu-supertag-${selected.allowed_host}.txt`; anchor.click(); URL.revokeObjectURL(url);
  };
  const emailSnippet = () => {
    if (!selected) return;
    const subject = encodeURIComponent(`Instalação da Super Tag no site ${selected.allowed_host}`);
    const body = encodeURIComponent(`Olá!\n\nPor favor, instale a Super Tag no site ${selected.allowed_host}.\n\nCole este código antes de </head> ou pelo gerenciador de tags:\n\n${selected.snippet}\n\nDepois de publicar, avise para validarmos o primeiro envio. A coleta respeita o consentimento configurado.\n`);
    window.location.href=`mailto:?subject=${subject}&body=${body}`;
  };
  // The site list carries the 30-day total; the detail call only refines it, so either source proves collection.
  const hasEvents = Number(selected?.events_30d || detail?.site?.events_30d || 0)>0;
  const tagInstalled = Boolean(selected && hasEvents);
  const collectionKnown = Boolean(detail?.site);
  const visibleSites = sites.filter(site => `${site.label} ${site.allowed_host}`.toLowerCase().includes(siteQuery.toLowerCase()));
  const installationState = selected?.revoked_at ? 'Revogada' : !selected?.enabled ? 'Desativada' : !collectionKnown ? 'Coleta não consultada' : tagInstalled ? 'Eventos recebidos · 30 dias' : 'Sem eventos · 30 dias';
  const sitesTotal = sites.length;
  const renderFavicon = site => <SiteFavicon site={site}/>;
  const canEdit = data.client.role !== 'viewer';
  const activeSites = sites.filter(site => Number(site.events_30d) > 0).length;
  const openInstall = () => {setInstallOpen(true);setSiteCheck(null);};
  const hostKey = value => String(value || '').replace(/^www\./, '');
  const linkedFlowsCount = selected ? siteFlows.filter(item => hostKey(item.allowed_host) === hostKey(selected.allowed_host)).length : 0;
  const tabs = [{id:'overview',label:'Visão geral'},{id:'install',label:'Instalação'},{id:'flows',label:'Fluxos'},{id:'settings',label:'Configurações'}];
  return <section className="st-page">
    <header className="st-topbar"><p>Instale uma única tag e acompanhe a coleta consentida de cada site.</p>
      <div className="st-topbar__side">{sitesTotal>0&&<><StatusBadge tone="gray">{sitesTotal} {sitesTotal===1?'site conectado':'sites conectados'}</StatusBadge><StatusBadge tone={activeSites?'success':'warning'}>{activeSites?`${activeSites} com coleta ativa`:'Sem coleta ativa'}</StatusBadge></>}{canEdit&&<ReportsActionButton color={selected?'secondary':'primary'} iconLeading={Plus} onClick={openInstall}>Conectar site</ReportsActionButton>}</div></header>
    {error&&<p className="reports-error" role="alert">{error}</p>}{notice&&<p className="reports-success" role="status">{notice}</p>}
    <div className="st-layout">
      <SiteSidebar sites={sites} loading={sitesLoading} query={siteQuery} onQuery={setSiteQuery} selectedId={selectedId} clientId={data.client.client_id} canAdd={canEdit} onAdd={openInstall} renderFavicon={renderFavicon}/>
      <main className="st-main">
        {!selected&&!sitesLoading&&<div className="st-empty"><h2>{sitesTotal?'Selecione um site':canEdit?'Conecte seu primeiro site':'Nenhum site conectado'}</h2><p>{sitesTotal?'Escolha um site na lista para ver a instalação, os eventos e os fluxos vinculados.':canEdit?'Instale a Super Tag para acompanhar visitas e eventos consentidos.':'Os sites autorizados para este cliente aparecerão aqui.'}</p>{!sitesTotal&&canEdit&&<ReportsActionButton color="primary" onClick={openInstall}>Conectar site</ReportsActionButton>}</div>}
        {selected&&<>
          <SiteSummary site={selected} flowsCount={detailLoading?null:linkedFlowsCount} hasEvents={hasEvents} renderFavicon={renderFavicon}/>
          <ReportsTabs className="reports-site-tabs" label="Áreas do site" value={siteTab} onChange={setSiteTab} items={tabs}/>
          {detailLoading&&<p className="st-muted" role="status">Carregando dados do site…</p>}
          {siteTab==='overview'&&<>
            <InstallStatus site={selected} hasEvents={hasEvents} verify={verify} verifying={verifying} onVerify={verifyInstall} onCopy={()=>copy(selected.snippet)} onGuide={()=>setSiteTab('install')}/>
            <div className="st-grid"><InstallCard site={selected} onCopy={()=>copy(selected.snippet)} onDownload={downloadSnippet} onEmail={emailSnippet}/>{hasEvents?<RecentEvents summary={detail?.summary}/>:<InstallGuide/>}</div>
            <div className="st-grid st-grid--wide"><LinkedFlows flows={siteFlows} site={selected} clientId={data.client.client_id}/><AccessCard data={data} site={selected}/></div>
          </>}
          {siteTab==='install'&&<>
            <InstallCard site={selected} onCopy={()=>copy(selected.snippet)} onDownload={downloadSnippet} onEmail={emailSnippet}/>
            <InstallGuide/>
          </>}
          {siteTab==='flows'&&<LinkedFlows flows={siteFlows} site={selected} clientId={data.client.client_id}/>}
          {siteTab==='settings'&&<article className="st-card st-settings"><header><div><h3>Configurações da tag</h3><p>Identificação, retenção e consentimento deste site.</p></div></header>
        <div className="reports-supertag-settings">
          <label>Duração do identificador<ReportsNativeSelect disabled={busy || data.client.role==='viewer'} value={selected.config?.audience_days || 365} onChange={event=>update({audience_days:Number(event.target.value)})}>{[[30,'30 dias'],[60,'60 dias'],[90,'90 dias'],[180,'6 meses'],[365,'1 ano'],[395,'13 meses (máximo do navegador)']].map(([days,name])=><option key={days} value={days}>{name}</option>)}</ReportsNativeSelect><small>Tempo que o mesmo visitante é reconhecido. Navegadores limitam este valor a cerca de 13 meses.</small></label>
          <label>Retenção dos eventos<ReportsNativeSelect disabled={busy || data.client.role==='viewer'} value={selected.config?.retention_days || 365} onChange={event=>update({retention_days:Number(event.target.value)})}>{[[30,'30 dias'],[60,'60 dias'],[90,'90 dias'],[180,'6 meses'],[365,'1 ano'],[730,'2 anos'],[1095,'3 anos'],[1825,'5 anos']].map(([days,name])=><option key={days} value={days}>{name}</option>)}</ReportsNativeSelect><small>Por quanto tempo os eventos ficam guardados para comparar períodos.</small></label>
          <label>Consentimento<ReportsNativeSelect disabled={busy || data.client.role==='viewer'} value={selected.config?.consent_mode || 'auto'} onChange={event=>update({consent_mode:event.target.value})}><option value="auto">Automático</option><option value="manual">Integrado ao meu aviso</option></ReportsNativeSelect><small>{(selected.config?.consent_mode||'auto')==='manual'?'A Super Tag nunca mostra aviso. Informe a decisão com o evento cadu:consent.':'Lê o aviso de cookies do site (OneTrust, Cookiebot, Google Consent Mode e similares). Só mostra o aviso próprio se não encontrar nenhum.'}</small></label>
          <label className="reports-checkbox"><ReportsFieldInput type="checkbox" disabled={busy || data.client.role==='viewer'} checked={selected.config?.visibility_enabled !== false} onChange={event=>update({visibility_enabled:event.target.checked})} /><span>Medir visibilidade em elementos marcados<small>Registra quando um elemento marcado aparece na tela.</small></span></label></div>
        <div className="reports-tag-card"><div className="reports-tag-card-head"><div><strong>Associar visita a um usuário conhecido</strong><small>Chame após login ou confirmação do formulário, com consentimento concedido</small></div></div><code>{"window.CaduSuperTag?.identify({ name: usuario.nome, email: usuario.email });"}</code><small>Também aceita telefone. E-mail e telefone são protegidos por HMAC; valores de formulário nunca são lidos automaticamente. A associação expira conforme a retenção configurada.</small></div>
        {data.client.role!=='viewer' && !selected.revoked_at && <ReportsActionButton type="button" className="reports-danger-button" disabled={busy} onClick={() => setRevokeConfirmOpen(true)}>Revogar instalação</ReportsActionButton>}
          </article>}
          {selected&&siteTab==='overview'&&detail&&hasEvents && <div className="st-analytics">
      {hasEvents ? <div className="reports-supertag-analytics"><div className="reports-supertag-kpis"><Kpi label="Eventos · 30 dias" value={integer(detail.site.events_30d)} detail="Eventos aceitos pelo coletor" /><Kpi label="Páginas vistas" value={integer(kindTotal('page_view'))} detail="Após consentimento" /><Kpi label="Sessões conhecidas" value={integer(detail.known_sessions||0)} detail="Identificadas pelo site" /><Kpi label="Sessões encerradas" value={integer(detail.branding?.overall?.closed_sessions||0)} detail="Após 30 min sem eventos" /></div><BrandingInsights branding={detail.branding}/><article className="reports-panel reports-supertag-activity"><div className="reports-panel-head"><div><h2>Atividade por página</h2><p>Saída = última página de uma sessão encerrada</p></div><span>Últimos 30 dias</span></div>
        {detail.pages?.length ? <div className="reports-table-wrap"><table><thead><tr><th>Página</th><th>Visitas</th><th>Saídas</th><th>Tempo ativo médio</th><th>Formulários</th><th>Cliques</th><th>Conversões</th><th>Visibilidade</th><th>Rolagem</th></tr></thead><tbody>{detail.pages.map(item=><tr key={item.page_path}><td>{item.page_path}</td><td>{integer(item.views)}</td><td>{integer(item.exits)}</td><td>{item.avg_active_seconds==null?'—':`${decimal(item.avg_active_seconds)} s`}<small>{integer(item.measured_visits)} visitas medidas</small></td><td>{integer(item.form_submissions)}</td><td>{integer(item.clicks)}</td><td>{integer(item.conversions)}</td><td>{integer(item.visibility_events)}</td><td>{integer(item.scroll_events)}</td></tr>)}</tbody></table></div> : <Empty message="Os eventos aparecem depois de consentimento e da primeira visita." />}
      </article>
      <article className="reports-panel reports-supertag-journeys"><div className="reports-panel-head"><div><h2>Sessões e navegação</h2><p>Até 100 sessões recentes · páginas percorridas e saída</p></div><span>{integer(detail.sessions?.length||0)} sessões</span></div>
        {detail.sessions?.length ? <div className="reports-table-wrap"><table><thead><tr><th>Visitante</th><th>Campanha</th><th>Início</th><th>Navegação</th><th>Página de saída</th></tr></thead><tbody>{detail.sessions.map(item=>{const pages=(item.journey||[]).filter(event=>event.kind==='page_view'||event.kind==='conversion');return <tr key={item.session_id}><td>{item.known_name||'Anônimo'}{item.known_name&&<small>Conhecido</small>}</td><td>{item.campaign||'Sem campanha'}</td><td>{new Date(item.started_at).toLocaleString('pt-BR')}</td><td>{pages.length?pages.map((event,index)=><React.Fragment key={`${event.page}:${index}`}>{index>0?' → ':''}{event.page}</React.Fragment>):'—'}</td><td>{item.exit_page||'—'}</td></tr>;})}</tbody></table></div> : <Empty message="As sessões aparecem depois de consentimento e da primeira visita." />}
      </article>
      <article className="reports-panel reports-supertag-heatmap"><div className="reports-panel-head"><h2>Dados para mapas de interação</h2><span>{detail.heatmap?.length || 0} células agregadas</span></div><p>Cliques são agrupados em uma grade normalizada de 5% do viewport. Para mapas de visibilidade, marque os elementos com <code>data-cadu-track data-cadu-element="hero_cta"</code>. O código não lê texto nem valores de formulário.</p>
        {detail.heatmap?.length ? <div className="reports-table-wrap"><table><thead><tr><th>Tipo</th><th>Elemento</th><th>Grade normalizada</th><th>Ocorrências</th></tr></thead><tbody>{detail.heatmap.slice(0,30).map((item,index)=><tr key={`${item.event_kind}:${item.element_id}:${index}`}><td>{item.event_kind}</td><td>{item.element_id || '—'}</td><td>{item.x != null ? `${(Number(item.x)/10).toFixed(1)}–${Math.min(100,(Number(item.x)+49)/10).toFixed(1)}% × ${(Number(item.y)/10).toFixed(1)}–${Math.min(100,(Number(item.y)+49)/10).toFixed(1)}%` : item.ratio != null ? `${item.ratio}% visível` : item.depth != null ? `${item.depth}% rolagem` : '—'}</td><td>{integer(item.total)}</td></tr>)}</tbody></table></div> : <Empty message="Os agregados de cliques e visibilidade aparecerão com o tráfego consentido." />}
      </article></div> : null}
    </div>}
        </>}
      </main>
    </div>
    <ReportsDrawer open={installOpen} onOpenChange={setInstallOpen} onDiscard={()=>{setHost('');setLabel('Site principal');setSiteCheck(null);setError('');}} title="Nova instalação da Super Tag" description="Informe a página inicial para personalizar e testar a conexão." context={data.client.client_name}>
      <form className="reports-form" onSubmit={create}><label>URL do site<ReportsFieldInput required type="url" value={host} onChange={event=>{setHost(event.target.value);setSiteCheck(null);}} placeholder="https://www.exemplo.com.br" /></label><ReportsActionButton type="button" className="reports-secondary-button" disabled={!host.trim()||checkingSite} onClick={checkSite}>{checkingSite?'Verificando site…':'Verificar site'}</ReportsActionButton>{siteCheck && <div className={`reports-site-preview${siteCheck.error?' has-error':''}`}><span className="reports-site-favicon">{siteCheck.favicon?<img src={siteCheck.favicon} alt=""/>:'◎'}</span><div><strong>{siteCheck.title||siteCheck.host||'Site encontrado'}</strong><small>{siteCheck.host}{siteCheck.status?` · Respondeu com HTTP ${siteCheck.status}`:''}</small></div>{!siteCheck.error&&<b>Ping concluído</b>}{siteCheck.error&&<p role="alert">{siteCheck.error}</p>}</div>}{error && <p className="reports-error" role="alert">{error}</p>}<label>Nome desta instalação<ReportsFieldInput required maxLength="120" value={label} onChange={event=>setLabel(event.target.value)} placeholder={siteCheck?.title||'Site principal'} /></label><p className="reports-info">A Super Tag verifica o domínio usando o servidor Python, identifica o título e favicon e confirma que o site responde. Eventos só serão coletados após consentimento.</p><div className="reports-modal-actions"><ReportsActionButton type="submit" className="reports-primary-button" disabled={busy||!siteCheck||Boolean(siteCheck.error)}>{busy?'Criando…':'Criar instalação'}</ReportsActionButton></div></form>
    </ReportsDrawer>
    <ReportsConfirmDialog open={revokeConfirmOpen} title="Revogar Super Tag" description="A coleta neste domínio será interrompida. Os dados já recebidos permanecem no Reports." confirmLabel="Revogar instalação" busy={busy} onCancel={() => setRevokeConfirmOpen(false)} onConfirm={revoke} />
  </section>;
}

function Events({data, filters, initialKind = 'all', refreshRevision}) {
  const [result, setResult] = useState({events: [], event_summary: {}});
  const [query, setQuery] = useState('');
  const [kindFilter, setKindFilter] = useState(initialKind);
  useEffect(() => setKindFilter(initialKind), [initialKind]);
  const [sourceFilter, setSourceFilter] = useState('all');
  const [newEventName, setNewEventName] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const requestVersion = useRef(0);
  const loadEvents = () => {
    const currentRequest = ++requestVersion.current;
    const params = new URLSearchParams({client_id: String(data.client.client_id), days: filters.period, start_date: filters.startDate, end_date: filters.endDate});
    if (filters.platform) params.set('platform', filters.platform);
    if (filters.account) params.set('account_id', filters.account);
    if (filters.campaign) params.set('campaign_id', filters.campaign);
    json(`/connect/api/v2/reports/flow/events?${params}`).then(value => {
      if (currentRequest === requestVersion.current) {setResult(value); setError('');}
    }).catch(failure => {if (currentRequest === requestVersion.current) setError(failure.message);});
  };
  useEffect(() => {
    loadEvents();
    return () => {requestVersion.current += 1;};
  }, [data.client.client_id, filters.period, filters.startDate, filters.endDate, filters.platform, filters.account, filters.campaign, refreshRevision]);
  const allEvents = result.events || [];
  const sources = [...new Set(allEvents.map(item => item.source_label))];
  const visible = allEvents.filter(item => {
    const term = query.trim().toLowerCase();
    const searchMatch = !term || `${item.event_name} ${item.page_path} ${item.source_label}`.toLowerCase().includes(term);
    const typeMatch = kindFilter === 'all' || (kindFilter === 'custom' ? item.event_kind === 'custom_event' : kindFilter === 'conversion' ? item.event_kind === 'conversion' : item.event_kind !== 'custom_event' && item.event_kind !== 'conversion');
    return searchMatch && typeMatch && (sourceFilter === 'all' || item.source_label === sourceFilter);
  });
  const summary = result.event_summary || {};
  const health = summary.total ? Math.round(Number(summary.attributed || 0) / Number(summary.total) * 100) : 0;
  const normalizedEventName = newEventName.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim().replace(/[\s-]+/g, '_').replace(/[^a-z0-9_]/g, '').replace(/^[^a-z]+/, '').slice(0, 80) || 'lead_qualified';
  const customSnippet = `window.CaduSuperTag && window.CaduSuperTag.trackEvent('${normalizedEventName}');`;
  const copyEvent = async () => {try {await navigator.clipboard.writeText(customSnippet);setCopied(true);window.setTimeout(()=>setCopied(false),1800);} catch (_) {setError('Não foi possível copiar o código.');}};
  const timeAgo = value => {const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000)); return minutes < 60 ? `há ${minutes} min` : minutes < 1440 ? `há ${Math.floor(minutes / 60)} h` : `há ${Math.floor(minutes / 1440)} d`;};
  return <>
    <section className="reports-events-layout"><article className="reports-panel reports-events-main"><div className="reports-panel-head"><div><h2>Atividade recebida</h2><p>Veja as interações recebidas pela Super Tag e prepare eventos personalizados.</p></div><a className="reports-inline-link" href={reportUrl('flow')}>Abrir Fluxos ↗</a></div>
      <ReportsTabs className="reports-event-tabs" label="Tipos de evento" items={[{id:'all',label:'Todos os eventos'},{id:'standard',label:'Padrão'},{id:'custom',label:'Personalizados'},{id:'conversion',label:'Conversões'}]} value={kindFilter} onChange={setKindFilter} />
      <div className="reports-event-filters"><ReportsFieldInput type="search" aria-label="Buscar eventos" placeholder="Buscar evento ou página…" value={query} onChange={event=>setQuery(event.target.value)}/><ReportsNativeSelect aria-label="Filtrar fonte" value={sourceFilter} onChange={event=>setSourceFilter(event.target.value)}><option value="all">Todas as fontes</option>{sources.map(source=><option key={source}>{source}</option>)}</ReportsNativeSelect><ReportsActionButton type="button" onClick={loadEvents}><RefreshCw01 size={16} aria-hidden="true"/>Atualizar</ReportsActionButton></div>
      {error&&<div className="reports-error" role="alert">{error}</div>}
      <div className="reports-table-wrap"><table className="reports-events-table"><thead><tr><th>Evento</th><th>Tipo</th><th>Fonte / Página</th><th>Última ocorrência</th><th>Mapeamento</th></tr></thead><tbody>{visible.map((item,index)=><tr key={`${item.event_kind}:${item.event_name}:${item.page_path}:${item.source_label}:${index}`}><td><span className="reports-event-icon">{item.event_kind==='conversion'?'✓':item.event_kind==='form_submit'?'▤':item.event_kind==='whatsapp_click'?'◉':item.event_kind==='custom_event'?'✳':'⌖'}</span><span><strong>{item.event_name}</strong><small>{item.page_path}</small></span></td><td><span className={`reports-event-type ${item.event_kind==='custom_event'?'is-custom':item.event_kind==='conversion'?'is-conversion':''}`}>{item.event_kind==='custom_event'?'Personalizado':item.event_kind==='conversion'?'Conversão':'Automático'}</span></td><td>{item.source_label}<small>{item.total} ocorrências · {item.page_path}</small></td><td>{timeAgo(item.last_occurred_at)}<small>{shortDate(item.last_occurred_at)}</small></td><td><span className={`reports-event-status ${Number(item.mapped)>0?'is-mapped':''}`}><i/>{Number(item.mapped)>0?'URL mapeada':'Sem etapa'}</span></td></tr>)}</tbody></table>{!visible.length&&<Empty message="Nenhum evento corresponde aos filtros. A atividade aparecerá quando a tag enviar eventos." />}</div>
      <div className="reports-events-foot">Mostrando {visible.length} de {integer(result.event_group_count ?? allEvents.length)} combinações de evento, página e origem · {shortDate(filters.startDate)} – {shortDate(filters.endDate)}{Number(result.event_group_count)>allEvents.length?' · exibindo as 300 mais recentes':''}</div>
    </article><aside className="reports-events-side"><article className="reports-panel"><div className="reports-panel-head"><h2>Resumo de eventos</h2><span>{shortDate(filters.startDate)} – {shortDate(filters.endDate)}</span></div><div className="reports-event-kpis"><Kpi label="Ocorrências" value={integer(summary.total)} detail="No intervalo selecionado"/><Kpi label="Envios de formulário" value={integer(summary.form_submissions)} detail="Sem registrar valores enviados"/><Kpi label="Conversões" value={integer(summary.conversions)} detail="Páginas de conversão mapeadas"/><Kpi label="Origem identificada" value={`${health}%`} detail="UTM ou domínio de referência"/></div><p className="reports-event-health">{health>=80?'Boa atribuição das origens':health?'Algumas visitas não têm UTM ou referência':'Aguardando os primeiros eventos'}</p></article>
      <article className="reports-panel"><div className="reports-panel-head"><h2>Adicionar evento personalizado</h2><span>Usa a Super Tag compartilhada</span></div><p>Gere uma chamada para marcar ações específicas do site, como lead qualificado ou início de checkout.</p><label className="reports-event-name">Nome do evento<ReportsFieldInput value={newEventName} onChange={event=>setNewEventName(event.target.value)} maxLength={120} placeholder="lead_qualified"/></label><code className="reports-event-snippet">{customSnippet}</code><ReportsActionButton className="reports-event-copy" type="button" onClick={copyEvent}>{copied?'Copiado':'Copiar código'}</ReportsActionButton><small>Instale a Super Tag e chame este código no momento da ação; use um identificador genérico, sem nome, e-mail, telefone ou outros dados pessoais.</small></article>
      <article className="reports-panel reports-event-help"><h2>Melhores resultados</h2><p>Use nomes consistentes e marque a URL de obrigado como conversão em Fluxos. Cliques de WhatsApp são detectados automaticamente por links wa.me e api.whatsapp.com.</p><a className="reports-inline-link" href={reportUrl('flow')}>Configurar páginas e conversões ↗</a></article></aside></section>
  </>;
}

function VisualConfirm({detail, data, busy, setBusy, setError, onRefresh}) {
  const [active, setActive] = useState(null);
  const [draft, setDraft] = useState({});
  const [createCampaign, setCreateCampaign] = useState(false);
  const [campaignMatch, setCampaignMatch] = useState(null);
  const scopes = detail.visual?.result?.scopes || [];
  const begin = (scope, index) => {
    const metricValues = {};
    const aliases = {impressions:'impressions', impressoes:'impressions', clicks:'clicks', cliques:'clicks',
      cost:'cost', spend:'cost', gasto:'cost', custo:'cost', conversions:'conversions', conversoes:'conversions',
      'conversion value':'conversion_value', 'valor de conversao':'conversion_value'};
    for (const metric of scope.metrics || []) {
      const label = metric.label.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();
      const key = aliases[label];
      if (key) metricValues[key] = metric.raw_value;
    }
    setDraft({platform:scope.platform || '', external_account_id:scope.account_id || '',
      account_name:scope.account_name || '', external_campaign_id:scope.campaign_id || '',
      campaign_name:scope.campaign_name || '', metric_date:scope.period_start || '',
      period_start:scope.period_start || '', period_end:scope.period_end || '',
      currency:scope.currency || '', impressions:'', clicks:'', cost:'', conversions:'',
      conversion_value:'', ...metricValues, note:''});
    setCreateCampaign(false);
    setActive(index);
    setCampaignMatch(null);
  };
  useEffect(() => {
    let live = true;
    if (active === null || !draft.platform || !draft.external_account_id || !draft.external_campaign_id) {
      setCampaignMatch(null);
      return () => {live = false;};
    }
    const params = new URLSearchParams({client_id: String(data.client.client_id), platform: draft.platform,
      account_id: draft.external_account_id, campaign_id: draft.external_campaign_id});
    fetch(`/connect/api/v2/reports/imports/${detail.import_file.id}/campaign-match?${params}`, {credentials:'same-origin'})
      .then(response => response.ok ? response.json() : Promise.reject(new Error('Falha ao verificar campanha')))
      .then(value => {if (live) {setCampaignMatch(value.match); setCreateCampaign(value.match?.state === 'missing');}})
      .catch(() => {if (live) setCampaignMatch({state:'unmatched'});});
    return () => {live = false;};
  }, [active, draft.platform, draft.external_account_id, draft.external_campaign_id, data.client.client_id]);
  const confirm = async (event, daily) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const {metric_date, period_start, period_end, ...shared} = draft;
      const payload = daily ? {...shared, metric_date, create_campaign:createCampaign} : {...shared, period_start, period_end, create_campaign:createCampaign};
      const action = daily ? 'confirm' : 'range';
      await json(`/connect/api/v2/reports/imports/${detail.import_file.id}/visual/${active}/${action}?client_id=${data.client.client_id}`,
        {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token':data.csrf}, body:JSON.stringify(payload)});
      setActive(null); await onRefresh();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const baseFields = [['platform','Plataforma'], ['external_account_id','ID da conta'],
    ['account_name','Nome da conta'], ['external_campaign_id','ID da campanha'],
    ['campaign_name','Nome da campanha']];
  const metricFields = [['currency','Moeda'], ['impressions','Impressões'], ['clicks','Cliques'],
    ['cost','Custo'], ['conversions','Conversões'], ['conversion_value','Valor das conversões']];
  return <article className="reports-panel reports-span-three">
    <div className="reports-panel-head"><h2>Conferir print</h2><span>Imagem original normalizada</span></div>
    <img className="reports-import-image" src={`/connect/api/v2/reports/imports/${detail.import_file.id}/image?client_id=${data.client.client_id}`} alt={`Print enviado: ${detail.import_file.original_name}`} />
    {scopes.map((scope, index) => {
      const daily = scope.granularity === 'day' && scope.period_start && scope.period_start === scope.period_end;
      const range = scope.granularity === 'range' || Boolean(scope.period_start && scope.period_end && scope.period_start !== scope.period_end);
      const dailyConfirmed = detail.rows.some(row => row.sheet_name === 'Print' && row.source_row === index + 1);
      const snapshot = (detail.range_snapshots || []).find(item => item.scope_index === index);
      const fields = [...baseFields, ...(daily ? [['metric_date','Data ISO']] : [['period_start','Início ISO'],['period_end','Fim ISO']]), ...metricFields];
      return <div key={index} className="reports-suggestion">
        <strong>Bloco {index + 1} · {scope.campaign_name || scope.campaign_id || 'Campanha sem identificação'}</strong>
        <p>A associação será conferida por plataforma, conta e ID da campanha antes de gravar.</p>
        {dailyConfirmed ? <p>Dia confirmado e incluído nas observações.</p> : snapshot ? <p>Intervalo confirmado: {shortDate(snapshot.period_start)} a {shortDate(snapshot.period_end)}. {snapshot.note}</p> : daily || range ? data.client.role !== 'viewer' && <ReportsActionButton type="button" className="reports-text-button" onClick={() => begin(scope,index)}>{daily ? 'Conferir e confirmar dia' : 'Conferir total do intervalo'}</ReportsActionButton> : <p>Período indefinido: mantenha como evidência até identificar as datas no print.</p>}
        {active === index && <form className="reports-form" onSubmit={event => confirm(event, daily)}>
          <div className="reports-form-pair">{fields.map(([key,label]) => <label key={key}>{label}<ReportsFieldInput value={draft[key] || ''} onChange={event => setDraft({...draft,[key]:event.target.value})} /></label>)}</div>
          {campaignMatch?.state === 'missing' && <div className="reports-suggestion"><strong>Campanha não encontrada</strong><p>Não localizamos {draft.campaign_name} na conta selecionada.</p><label className="reports-checkbox"><ReportsFieldInput type="checkbox" checked={createCampaign} onChange={event => setCreateCampaign(event.target.checked)} />Criar esta campanha e armazenar os dados do print</label></div>}
          {campaignMatch?.state === 'matched' && <p>Campanha encontrada: {campaignMatch.campaign_name} · {campaignMatch.account_name}</p>}
          {campaignMatch?.state === 'unmatched' && <p className="reports-error">{campaignMatch.reason || 'Complete plataforma, ID da conta e ID da campanha para validar a associação.'}</p>}
          <label>Justificativa<ReportsFieldInput required maxLength="1000" value={draft.note || ''} onChange={event => setDraft({...draft,note:event.target.value})} placeholder="Conferi os números, IDs e período no print" /></label>
          <ReportsActionButton type="submit" disabled={busy || !campaignMatch || campaignMatch?.state === 'unmatched' || (campaignMatch?.state === 'missing' && !createCampaign)}>Confirmar {daily ? 'dados do dia' : 'total do intervalo'}</ReportsActionButton>
        </form>}
      </div>;
    })}
  </article>;
}

function ColumnMapping({detail, data, busy, setBusy, setError, onRefresh}) {
  const [mapping, setMapping] = useState({});
  const [localSuggestion, setLocalSuggestion] = useState(null);
  const evidenceKey = `${detail.import_file.id}:${detail.column_evidence_fingerprint || ''}`;
  const evidenceKeyRef = useRef(evidenceKey);
  evidenceKeyRef.current = evidenceKey;
  const suggestions = localSuggestion?.key === evidenceKey
    ? localSuggestion.value : detail.column_suggestions || null;
  const [platformHint, setPlatformHint] = useState(detail.import_file.platform_hint || '');
  const [currencyHint, setCurrencyHint] = useState('');
  const [dateOrder, setDateOrder] = useState('auto');
  const [note, setNote] = useState('');
  const fields = [['platform','Plataforma'],['account_id','ID da conta'],['account_name','Nome da conta'],
    ['campaign_id','ID da campanha'],['campaign_name','Nome da campanha'],['date','Data'],
    ['currency','Moeda'],['impressions','Impressões'],['clicks','Cliques'],['cost','Custo'],
    ['conversions','Conversões'],['conversion_value','Valor das conversões']];
  const suggest = async () => {
    const requestedKey = evidenceKey;
    setBusy(true); setError('');
    try {
      const value = await json(`/connect/api/v2/reports/imports/${detail.import_file.id}/suggest-columns?client_id=${data.client.client_id}`,
        {method:'POST', headers:{'X-CSRF-Token':data.csrf}});
      if (requestedKey === evidenceKeyRef.current &&
          value.suggestion?.result?.evidence_fingerprint === detail.column_evidence_fingerprint)
        setLocalSuggestion({key:requestedKey, value:value.suggestion});
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const chosen = Object.fromEntries(Object.entries(mapping).filter(([,header]) => header));
      await json(`/connect/api/v2/reports/imports/${detail.import_file.id}/map-columns?client_id=${data.client.client_id}`,
        {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':data.csrf},
          body:JSON.stringify({mapping:chosen, platform_hint:platformHint, currency_hint:currencyHint,
            date_order:dateOrder, note})});
      await onRefresh();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  return <article className="reports-panel reports-span-three"><div className="reports-panel-head"><h2>Mapear colunas do arquivo</h2><span>{detail.headers.length} cabeçalhos detectados</span></div>
    <p>Use quando o export tiver nomes de colunas que o Reports não reconheceu. O mapa será aplicado às linhas pendentes deste arquivo; o original fica preservado.</p>
    {data.client.role !== 'viewer' && detail.import_file.applied_count < detail.import_file.row_count && !suggestions && <ReportsActionButton type="button" className="reports-text-button" disabled={busy} onClick={suggest}>Corrigir mapeamento com TypeSafe</ReportsActionButton>}
    {suggestions && <div className="reports-suggestion"><strong>Correções TypeSafe sugeridas · confira antes de aplicar</strong><p>Concentração das alternativas, não uma garantia de acerto. O mapa só é aplicado após sua revisão e confirmação.</p>{suggestions.result.suggestions.length ? suggestions.result.suggestions.map((item,index) => <p key={`${item.header}:${index}`}>{item.header} → {fields.find(([key]) => key === item.field)?.[1] || 'Sem correspondência'} · concentração {Math.round(item.confidence * 100)}% {item.field !== 'none' && data.client.role !== 'viewer' && <ReportsActionButton type="button" className="reports-text-button" onClick={() => setMapping({...mapping,[item.field]:item.header})}>Usar no formulário</ReportsActionButton>}</p>) : <p>Nenhum cabeçalho desconhecido encontrado.</p>}{suggestions.result.omitted_count > 0 && <p>{suggestions.result.omitted_count} cabeçalhos ficaram fora da sugestão; mapeie manualmente.</p>}</div>}
    {data.client.role !== 'viewer' && detail.import_file.applied_count < detail.import_file.row_count && <form className="reports-form" onSubmit={submit}>
      <div className="reports-form-pair">{fields.map(([key,label]) => <label key={key}>{label}<ReportsNativeSelect value={mapping[key] || ''} onChange={event => setMapping({...mapping,[key]:event.target.value})}><option value="">Usar leitura automática</option>{detail.headers.map(header => <option key={header} value={header}>{header}</option>)}</ReportsNativeSelect></label>)}</div>
      <div className="reports-form-pair"><label>Plataforma do arquivo, se ausente<ReportsFieldInput value={platformHint} onChange={event => setPlatformHint(event.target.value)} placeholder="Ex.: Meta Ads" /></label><label>Moeda, se ausente<ReportsFieldInput maxLength="3" value={currencyHint} onChange={event => setCurrencyHint(event.target.value)} placeholder="BRL" /></label><label>Formato de data<ReportsNativeSelect value={dateOrder} onChange={event => setDateOrder(event.target.value)}><option value="auto">Detectar</option><option value="dmy">Dia/mês/ano</option><option value="mdy">Mês/dia/ano</option></ReportsNativeSelect></label></div>
      <label>Justificativa<ReportsFieldInput required maxLength="1000" value={note} onChange={event => setNote(event.target.value)} placeholder="Ex.: cabeçalhos do export conferidos" /></label><ReportsActionButton type="submit" disabled={busy}>Aplicar às linhas pendentes</ReportsActionButton>
    </form>}
    {(detail.column_maps || []).map((item,index) => <p key={index}>{shortDate(item.created_at)} · {item.applied_rows} linhas reconhecidas · {item.note}</p>)}
  </article>;
}

function Imports({data, reloadBootstrap, focusLibrary = false}) {
  const [importsView, setImportsView] = useState(focusLibrary ? 'metrics' : 'upload');
  const [items, setItems] = useState([]);
  const [customMetrics, setCustomMetrics] = useState([]);
  const [rangeSnapshots, setRangeSnapshots] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [choices, setChoices] = useState({});
  const [reasons, setReasons] = useState({});
  const [ready, setReady] = useState(true);
  const [detail, setDetail] = useState(null);
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState({});
  const [file, setFile] = useState(null);
  const [platform, setPlatform] = useState('');
  const [currency, setCurrency] = useState('');
  const [dateOrder, setDateOrder] = useState('auto');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);
  const activeClientRef = useRef(String(data.client.client_id));
  activeClientRef.current = String(data.client.client_id);
  const base = `/connect/api/v2/reports/imports?client_id=${data.client.client_id}`;
  const refresh = async () => {
    const clientId = String(data.client.client_id);
    const [body, pending, ranges] = await Promise.all([
      json(`/connect/api/v2/reports/imports?client_id=${clientId}`),
      json(`/connect/api/v2/reports/import-conflicts?client_id=${clientId}`),
      json(`/connect/api/v2/reports/import-ranges?client_id=${clientId}`),
    ]);
    if (activeClientRef.current !== clientId) return;
    setReady(body.ready); setItems(body.imports || []);
    setCustomMetrics(body.custom_metrics || ranges.custom_metrics || []);
    setConflicts(pending.conflicts || []); setRangeSnapshots(ranges.snapshots || []);
  };
  useEffect(() => {
    setItems([]); setCustomMetrics([]); setRangeSnapshots([]); setConflicts([]);
    setChoices({}); setReasons({}); setDetail(null); setEditing(null); setDraft({});
    setFile(null); setPlatform(''); setCurrency(''); setDateOrder('auto');
    setBusy(false); setError(''); setNote(''); setDragActive(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setImportsView(focusLibrary ? 'metrics' : 'upload');
    refresh().catch(failure => {
      if (activeClientRef.current === String(data.client.client_id)) setError(failure.message);
    });
  }, [data.client.client_id]);
  useEffect(() => {if (focusLibrary) setImportsView('metrics');}, [focusLibrary]);
  const open = async id => {
    const clientId = String(data.client.client_id);
    try {
      const result = await json(`/connect/api/v2/reports/imports/${id}?client_id=${clientId}`);
      if (activeClientRef.current !== clientId) return;
      setDetail(result); setImportsView('review'); setError('');
    } catch (failure) {
      if (activeClientRef.current === clientId) setError(failure.message);
    }
  };
  const acceptFile = selected => {
    if (!selected) return;
    if (!/\.(csv|xlsx|png|jpe?g|webp)$/i.test(selected.name || '')) {
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setError('Escolha um arquivo CSV, XLSX, PNG, JPG ou WEBP.');
      return;
    }
    setError(''); setFile(selected); setImportsView('upload'); setNote('');
  };
  const edit = row => {setEditing(row.id); setDraft({...row.parsed, metric_date: row.parsed.metric_date || '', ...row.parsed.metrics, create_campaign:row.parsed.campaign_match?.state === 'missing', note: ''}); setImportsView('review');};
  const resolve = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const payload = Object.fromEntries(['platform','external_account_id','account_name','external_campaign_id','campaign_name','metric_date','currency','impressions','clicks','cost','conversions','conversion_value','note'].map(key => [key, String(draft[key] || '')]));
      payload.create_campaign = Boolean(draft.create_campaign);
      await json(`/connect/api/v2/reports/imports/${detail.import_file.id}/rows/${editing}/resolve?client_id=${data.client.client_id}`, {method: 'POST', headers: {'Content-Type': 'application/json','X-CSRF-Token': data.csrf}, body: JSON.stringify(payload)});
      setEditing(null); await open(detail.import_file.id); await refresh(); await reloadBootstrap();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const extract = async () => {
    setBusy(true); setError('');
    try {
      await json(`/connect/api/v2/reports/imports/${detail.import_file.id}/extract?client_id=${data.client.client_id}`, {method: 'POST', headers: {'X-CSRF-Token': data.csrf}});
      await open(detail.import_file.id); await refresh();
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const resolveConflict = async (event, conflict) => {
    event.preventDefault(); setBusy(true); setError('');
    const key = `${conflict.campaign_id}:${conflict.metric_date}:${conflict.metric_key}`;
    try {
      await json(`/connect/api/v2/reports/import-conflicts/${conflict.campaign_id}/${conflict.metric_date}/${conflict.metric_key}/resolve?client_id=${data.client.client_id}`, {method: 'POST', headers: {'Content-Type': 'application/json','X-CSRF-Token': data.csrf}, body: JSON.stringify({observation_id: choices[key] || conflict.candidates[0]?.id, note: reasons[key] || ''})});
      await refresh(); await reloadBootstrap();
      setChoices(current => {const next = {...current}; delete next[key]; return next;});
      setReasons(current => {const next = {...current}; delete next[key]; return next;});
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const submit = async event => {
    event.preventDefault(); if (!file) return;
    setBusy(true); setError(''); setNote('');
    try {
      const payload = new FormData(); payload.append('file', file);
      if (platform) payload.append('platform_hint', platform);
      if (currency) payload.append('currency_hint', currency.toUpperCase());
      payload.append('date_order', dateOrder);
      const result = await json(base, {method: 'POST', headers: {'X-CSRF-Token': data.csrf}, body: payload});
      setNote(result.duplicate ? 'Este arquivo já foi importado para o cliente.' : `${result.applied_count || 0} de ${result.row_count || 0} linhas prontas para reconciliação.`);
      await refresh(); await open(result.import_id); await reloadBootstrap();
      event.target.reset(); setFile(null);
    } catch (failure) {setError(failure.message);} finally {setBusy(false);}
  };
  const tabItems = [
    {id:'upload',label:'Importar arquivos',count:items.length || undefined},
    {id:'review',label:'Revisar importação',count:detail ? 'Aberta' : undefined,disabled:!detail},
    {id:'metrics',label:'Métricas personalizadas',count:customMetrics.length || undefined},
    {id:'conflicts',label:'Divergências',count:conflicts.length || undefined},
    {id:'ranges',label:'Períodos importados',count:rangeSnapshots.length || undefined},
  ];
  return <><section className={`reports-imports-page is-${importsView}`}>
    <ReportsTabs className="reports-imports-tabs" label="Etapas de importação" items={tabItems} value={importsView} onChange={setImportsView} />
    {error && <p className="reports-error reports-imports-alert" role="alert">{error}</p>}
    {note && <p className="reports-success reports-imports-alert" role="status">{note}</p>}
    {importsView==='upload'&&<div className="reports-imports-overview">
    <article className="reports-panel reports-import-upload"><div className="reports-panel-head"><div><h2>Importar dados de mídia</h2><p>Envie exportações CSV/XLSX ou prints. Campanhas e métricas passam por revisão antes de entrar nos relatórios.</p></div><span>CSV · XLSX · PNG · JPG · WEBP</span></div>{!ready && <p className="reports-error">A migração de importações precisa ser aplicada neste ambiente.</p>}{ready && data.client.role !== 'viewer' && <form className="reports-form" onSubmit={submit}>
      <label className={`reports-import-dropzone${dragActive?' is-drag-active':''}${file?' has-file':''}`} onDragEnter={event=>{event.preventDefault();setDragActive(true);}} onDragOver={event=>{event.preventDefault();setDragActive(true);}} onDragLeave={event=>{if(!event.currentTarget.contains(event.relatedTarget))setDragActive(false);}} onDrop={event=>{event.preventDefault();setDragActive(false);acceptFile(event.dataTransfer.files?.[0]);}}><ReportsFieldInput ref={fileInputRef} className="reports-import-file-input" type="file" accept=".csv,.xlsx,.png,.jpg,.jpeg,.webp" required onChange={event=>acceptFile(event.target.files?.[0])}/><strong>{file?'Arquivo pronto para enviar':'Escolher arquivo ou arrastar até aqui'}</strong>{file&&<span>{file.name}</span>}<small>CSV, XLSX, PNG, JPG ou WEBP · um arquivo</small></label>
      <div className="reports-import-options"><label>Plataforma, se não estiver no arquivo<ReportsFieldInput value={platform} onChange={event => setPlatform(event.target.value)} placeholder="Ex.: Google Ads, Meta Ads" /></label><label>Moeda, se houver valores<ReportsFieldInput maxLength="3" value={currency} onChange={event => setCurrency(event.target.value)} placeholder="BRL" /></label><label>Datas com barras<ReportsNativeSelect value={dateOrder} onChange={event => setDateOrder(event.target.value)}><option value="auto">Detectar; revisar datas ambíguas</option><option value="dmy">Dia/mês/ano</option><option value="mdy">Mês/dia/ano</option></ReportsNativeSelect></label></div><ReportsActionButton type="submit" disabled={busy || !file}>{busy?'Enviando…':'Enviar e analisar arquivo'}</ReportsActionButton>
    </form>}</article>
    <article className="reports-panel reports-import-history"><div className="reports-panel-head"><div><h2>Arquivos recebidos</h2><p>Abra um arquivo para mapear colunas, revisar campanhas e confirmar dados.</p></div><span>{items.length} arquivos</span></div>{items.length ? <div className="reports-table-wrap"><table><thead><tr><th>Arquivo</th><th>Estado</th><th>Linhas</th><th>Recebido</th><th></th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td>{item.original_name}</td><td>{({parsed:'Lido',needs_review:'Revisão necessária',awaiting_extraction:'Aguardando leitura visual'})[item.status] || item.status}</td><td>{item.applied_count}/{item.row_count}</td><td>{shortDate(item.created_at)}</td><td><ReportsActionButton className="reports-text-button" onClick={() => open(item.id)}>Revisar</ReportsActionButton></td></tr>)}</tbody></table></div> : <Empty message="Nenhum arquivo enviado para este cliente." />}</article>
    </div>}
    {importsView==='metrics'&&<article id="reports-data-library" className="reports-panel reports-import-full"><div className="reports-panel-head"><div><h2>Coleção de métricas personalizadas</h2><p>Campos adicionais preservados com dimensão, unidade e evidência de origem.</p></div><span>{customMetrics.length} pares canal/chave</span></div>{customMetrics.length ? <div className="reports-table-wrap"><table><thead><tr><th>Canal</th><th>Chave</th><th>Campo de origem</th><th>Dimensão</th><th>Data</th><th>Último valor</th><th>Observações</th></tr></thead><tbody>{customMetrics.map((metric,index)=><tr key={`${metric.campaign_id}:${metric.channel}:${metric.metric_key}:${metric.metric_date}:${index}`}><td>{metric.channel}</td><td>{metric.metric_key}</td><td>{metric.metric_label}</td><td>{Object.values(metric.dimensions || {}).map(dimension => `${dimension.label}: ${dimension.value}`).join(' · ') || '—'}</td><td>{shortDate(metric.metric_date)}</td><td>{metric.latest_value} {metric.currency || metric.unit}</td><td>{metric.observations}</td></tr>)}</tbody></table></div>:<Empty message="Campos numéricos adicionais dos canais aparecerão aqui como chave/valor."/>}</article>}
    <article className="reports-panel reports-span-three reports-import-conflicts"><div className="reports-panel-head"><h2>Valores divergentes</h2><span>{conflicts.length} pendências recentes</span></div>{conflicts.length ? conflicts.map(conflict => {const key = `${conflict.campaign_id}:${conflict.metric_date}:${conflict.metric_key}`; return <details className="reports-suggestion" key={key}><summary><strong>{conflict.platform} · {conflict.account_name} · {conflict.campaign_name}</strong> · {shortDate(conflict.metric_date)} · {conflict.metric_key} · {conflict.version_count} valores distintos</summary><p>Confira os arquivos de origem e escolha um valor. O histórico será preservado.</p>{data.client.role !== 'viewer' ? <form className="reports-form" onSubmit={event => resolveConflict(event, conflict)}><label>Observação<ReportsNativeSelect value={choices[key] || conflict.candidates[0]?.id || ''} onChange={event => setChoices({...choices,[key]:event.target.value})}>{conflict.candidates.map(candidate => <option key={candidate.id} value={candidate.id}>{candidate.value_numeric} {candidate.currency || ''}{Object.values(candidate.dimensions || {}).map(dimension => ` · ${dimension.label}: ${dimension.value}`).join('')} · {candidate.original_name} · {shortDate(candidate.created_at)}</option>)}</ReportsNativeSelect></label><label>Justificativa<ReportsFieldInput required maxLength="1000" value={reasons[key] || ''} onChange={event => setReasons({...reasons,[key]:event.target.value})} placeholder="Ex.: export mais recente conferido na plataforma" /></label><ReportsActionButton type="submit" disabled={busy || !conflict.candidates.length}>Confirmar valor</ReportsActionButton></form> : conflict.candidates.map(candidate => <p key={candidate.id}>{candidate.value_numeric} {candidate.currency || ''} · {candidate.original_name}</p>)}</details>;}) : <Empty message="Nenhuma divergência entre arquivos importados." />}</article>
    <article className="reports-panel reports-span-three reports-import-ranges"><div className="reports-panel-head"><h2>Snapshots de intervalo</h2><span>{rangeSnapshots.length} recentes · sem soma diária</span></div>{rangeSnapshots.length ? <div className="reports-table-wrap"><table><thead><tr><th>Conta e campanha</th><th>Período</th><th>Métricas do intervalo</th><th>Origem</th><th></th></tr></thead><tbody>{rangeSnapshots.map(snapshot => <tr key={snapshot.id}><td>{snapshot.platform} · {snapshot.account_name} · {snapshot.campaign_name}</td><td>{shortDate(snapshot.period_start)} a {shortDate(snapshot.period_end)}</td><td>{snapshot.metrics.map(metric => `${metric.metric_key}: ${metric.value_numeric} ${metric.currency || metric.unit}`).join(' · ')}</td><td>{snapshot.original_name}</td><td><ReportsActionButton type="button" className="reports-text-button" onClick={() => open(snapshot.import_id)}>Abrir print</ReportsActionButton></td></tr>)}</tbody></table></div> : <Empty message="Totais de período confirmados em prints aparecerão aqui, separados das métricas diárias." />}</article>
    {detail && <article className="reports-panel reports-span-three reports-import-detail"><div className="reports-panel-head"><h2>{detail.import_file.original_name}</h2><span>{detail.import_file.row_count} linhas</span></div>{detail.import_file.file_kind === 'image' ? <>{detail.visual ? <><p>Leitura visual sugerida por {detail.visual.model}. Confira o print antes de usar qualquer número.</p>{detail.visual.result.scopes.length ? detail.visual.result.scopes.map((scope,index) => <div className="reports-suggestion" key={index}><strong>Bloco {index + 1}: {scope.platform || 'Plataforma não identificada'} · {scope.account_name || scope.account_id || 'Conta não identificada'} · {scope.campaign_name || scope.campaign_id || 'Campanha não identificada'}</strong><p>{scope.period_start || 'Período não identificado'}{scope.period_end && scope.period_end !== scope.period_start ? ` a ${scope.period_end}` : ''} · {scope.granularity || 'Granularidade indefinida'} · {scope.currency || 'Moeda não identificada'}</p><small>Evidência: {scope.evidence}</small>{scope.metrics.length ? <ul>{scope.metrics.map((metric,metricIndex) => <li key={metricIndex}>{metric.label}: {metric.raw_value} {metric.unit} · {metric.evidence}</li>)}</ul> : <p>Sem métricas legíveis neste bloco.</p>}</div>) : <Empty message="Não identificamos dados legíveis neste print. Envie uma imagem mais nítida ou um export CSV/XLSX para continuar." />}{detail.visual.result.questions.map((question,index) => <p key={index}>{question}</p>)}</> : <><p>Print recebido. A leitura visual consome créditos Cadu e gera sugestões com evidências; nenhuma campanha ou métrica é confirmada automaticamente.</p>{data.client.role !== 'viewer' && <ReportsActionButton type="button" className="reports-text-button" disabled={busy} onClick={extract}>Ler print com IA</ReportsActionButton>}</>}</> : <><div className="reports-table-wrap"><table><thead><tr><th>Linha</th><th>Plataforma</th><th>Conta</th><th>Campanha</th><th>Atualização</th><th>Data</th><th>Estado</th><th></th></tr></thead><tbody>{detail.rows.map(row => <tr key={row.id}><td>{row.sheet_name} · {row.source_row}</td><td>{row.parsed.platform || '—'}</td><td>{row.parsed.account_name || row.parsed.external_account_id || '—'}</td><td>{row.parsed.campaign_name || row.parsed.external_campaign_id || '—'}{row.parsed.campaign_match?.state === 'missing' && <small>Campanha associada automaticamente quando a identidade é única</small>}</td><td>{{first:'Primeiros dados',incremental:'Novos dias',revision:'Revisão de valores',duplicate:'Reenvio idêntico',campaign_missing:'Campanha ausente'}[row.parsed.update_kind] || 'Análise pendente'}</td><td>{row.metric_date || '—'}</td><td>{row.reason || (row.decision_note ? `Confirmada: ${row.decision_note}` : 'Incluída na projeção quando não há conflito')}</td><td>{row.status === 'needs_review' && data.client.role !== 'viewer' && <ReportsActionButton type="button" className="reports-text-button" onClick={() => edit(row)}>Revisar</ReportsActionButton>}</td></tr>)}</tbody></table></div><small>Mostrando até 100 linhas, com pendências primeiro. Valores divergentes entre arquivos aparecem acima para revisão.</small>{(detail.custom_values || []).length > 0 && <div className="reports-suggestion"><strong>Métricas personalizadas · chave/valor</strong>{detail.custom_values.map((metric,index) => <p key={`${metric.import_row_id}:${metric.metric_key}:${index}`}>{metric.campaign_name} · {metric.metric_label} ({metric.metric_key}): {metric.value_numeric} {metric.currency || metric.unit}{Object.values(metric.dimensions || {}).map(dimension => ` · ${dimension.label}: ${dimension.value}`).join('')}</p>)}</div>}</>}</article>}
    {detail?.import_file?.file_kind === 'image' && <div className="reports-import-visual"><VisualConfirm key={detail.import_file.id} detail={detail} data={data} busy={busy} setBusy={setBusy} setError={setError} onRefresh={async () => {await open(detail.import_file.id); await refresh(); await reloadBootstrap();}} /></div>}
    {detail && detail.import_file.file_kind !== 'image' && <div className="reports-import-columnmap"><ColumnMapping key={detail.import_file.id} detail={detail} data={data} busy={busy} setBusy={setBusy} setError={setError} onRefresh={async () => {await open(detail.import_file.id); await refresh(); await reloadBootstrap();}} /></div>}
    {editing && <article className="reports-panel reports-span-three reports-import-editing"><div className="reports-panel-head"><h2>Revisar linha</h2><ReportsActionButton type="button" className="reports-text-button" onClick={() => setEditing(null)}>Fechar</ReportsActionButton></div>{draft.campaign_match?.state === 'missing' && <div className="reports-suggestion"><strong>Campanha não encontrada</strong><p>Não localizamos {draft.campaign_name} ({draft.platform} · conta {draft.external_account_id} · campanha {draft.external_campaign_id}). Escolha criar essa campanha para armazenar os dados importados.</p>{!draft.campaign_match?.account_id && <p>Se a conta ainda não estiver cadastrada, os campos acima serão usados para criar o vínculo; sem ID externo, ela ficará identificada como conta de importação do Reports.</p>}<label className="reports-checkbox"><ReportsFieldInput type="checkbox" checked={Boolean(draft.create_campaign)} onChange={event => setDraft({...draft,create_campaign:event.target.checked})} />Criar campanha e associar os dados desta linha</label></div>}{draft.update_kind && <p>Tipo identificado: {{first:'primeiros dados da campanha',incremental:'novos dias de dados',revision:'valores diferentes para uma data já recebida',duplicate:'reenvio com os mesmos valores',campaign_missing:'campanha ainda sem associação'}[draft.update_kind]}.</p>}<form className="reports-form" onSubmit={resolve}><div className="reports-form-pair">{[['platform','Plataforma'],['external_account_id','ID da conta'],['account_name','Nome da conta'],['external_campaign_id','ID da campanha'],['campaign_name','Nome da campanha'],['metric_date','Data ISO (AAAA-MM-DD)'],['currency','Moeda'],['impressions','Impressões'],['clicks','Cliques'],['cost','Custo'],['conversions','Conversões'],['conversion_value','Valor das conversões']].map(([key,label]) => <label key={key}>{label}<ReportsFieldInput value={draft[key] || ''} onChange={event => setDraft({...draft,[key]:event.target.value})} /></label>)}</div><label>Justificativa<ReportsFieldInput required maxLength="1000" value={draft.note || ''} onChange={event => setDraft({...draft,note:event.target.value})} placeholder="Ex.: data e conta conferidas no export original" /></label><ReportsActionButton type="submit" disabled={busy || (draft.campaign_match?.state === 'missing' && !draft.create_campaign)}>Confirmar linha</ReportsActionButton></form></article>}
  </section>
  </>;
}

const reportIcons = {overview:'home', media:'analysis', journey:'branch', reports:'file', alerts:'alert', 'data-sources':'plugin', supertag:'pulse', events:'calendar', imports:'download', links:'link', customers:'users', accounts:'table', access:'folder'};
const NAV_GROUPS = [
  ['', [['overview', 'Visão geral', 'overview']]],
  ['Análise', [['media', 'Mídia', 'media'], ['journey', 'Site & Jornada', 'journey'], ['reports', 'Relatórios', 'reports'], ['alerts', 'Alertas', 'alerts']]],
  ['Dados', [['data-sources', 'Fontes de dados', 'data-sources'], ['supertag', 'Super Tag', 'supertag'], ['events', 'Eventos', 'events'], ['imports', 'Importações', 'imports']]],
  ['Ferramentas', [['links', 'Link Tester', 'tools/link-tester']]],
  ['Configurações', [['customers', 'Clientes', 'settings/clients'], ['accounts', 'Contas e conexões', 'settings/accounts'], ['access', 'Acessos', 'settings/access']]],
];

// Sections that older links addressed as #section?params.
const LEGACY_HASHES = new Set(['overview', 'customers', 'accounts', 'campaigns', 'reports', 'imports', 'monitor', 'supertag', 'flow', 'flows', 'pages', 'alerts', 'events', 'conversions', 'links', 'access', 'data-library']);

function App() {
  const locationKey = useLocationKey();
  const route = useMemo(() => resolveRoute(), [locationKey]);
  const pageSection = route.page;
  const [data, setData] = useState(null);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const accountsView = pageSection === 'accounts' && new URLSearchParams(location.search).get('view') === 'management';
  const isFlowEditor = Boolean(flowEditorId())&&(!/\/monitor\/?$/.test(location.pathname)||Boolean(data?.features?.flows_workspace_v2));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [period, setPeriodState] = useState(readPeriod);
  const setPeriod = range => {setPeriodState(range); writePeriod(range);};
  // Platform/account/campaign filters stay per page; the period is one for the whole app.
  const [filtersByPage, setFiltersByPage] = useState({});
  const filters = {...REPORT_FILTER_DEFAULTS, ...(filtersByPage[pageSection] || {}), ...periodFilters(period)};
  const updateFilters = ({period: preset, startDate, endDate, ...changes}) => {
    if (startDate && endDate) setPeriod({start: startDate, end: endDate});
    if (Object.keys(changes).length) setFiltersByPage(current => ({...current, [pageSection]: {...(current[pageSection] || {}), ...changes}}));
  };
  const [refreshRevision, setRefreshRevision] = useState(0);
  const load = async (clientId = new URLSearchParams(location.search).get('client_id')) => {
    try {
      const body = await json(`/connect/api/v2/reports/bootstrap${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ''}`);
      setActiveClient(body.client?.client_id);
      setData(body); setError(''); dropClientFromUrl();
    } catch (failure) {setError(failure.message);}
  };
  /** Changes the analysed client in place: same page, same period, data reloaded. */
  const switchClient = async clientId => {
    if (String(clientId) === String(data?.client?.client_id)) return;
    setFiltersByPage({});
    await load(clientId);
  };
  useEffect(() => {
    const legacySection = location.hash.slice(1).split('?')[0];
    if (LEGACY_HASHES.has(legacySection)) {
      const legacyParams = Object.fromEntries(new URLSearchParams(location.hash.split('?')[1] || ''));
      location.replace(reportUrl(legacySection, legacyParams));
      return undefined;
    }
    const syncRoute = () => {
      applyLegacyRedirect();
      const query = new URLSearchParams(location.search);
      // Links between pages don't carry the period; keep the current one in the new URL.
      if (['period', 'days', 'start_date', 'end_date'].some(key => query.has(key))) setPeriodState(readPeriod());
      else setPeriodState(current => {writePeriod(current); return current;});
      window.scrollTo(0, 0);
    };
    load();
    syncRoute();
    addEventListener('popstate', syncRoute);
    return () => {removeEventListener('popstate', syncRoute);};
  }, []);
  const save = async (path, payload, reload = true, method = 'POST') => {
    setBusy(true); setError('');
    try {
      const result = await json(`/connect/api/v2/reports${path}`, {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...payload, client_id: data.client.client_id})});
      if (reload) await load(data.client.client_id);
      return result;
    } catch (failure) {if(!path.startsWith('/flow/'))setError(failure.message); throw failure;} finally {setBusy(false);}
  };
  const groups = NAV_GROUPS.map(([label, items]) => ({label, items: items
    .filter(([id]) => id !== 'access' || data?.can_manage_access)
    .map(([id, title, path]) => ({id, label: title, icon: reportIcons[id], href: `${APP_BASE}/${path}`}))}));
  const solutionUrls={workspace:rootElement.dataset.workspaceUrl,planner:rootElement.dataset.plannerUrl,studio:rootElement.dataset.studioUrl,connect:location.pathname+location.search,skills:rootElement.dataset.skillsUrl};
  const solutionIcons={workspace:'/static/images/cadu/products/cadu-icon.png',planner:'/static/images/cadu/products/planner-icon.png',studio:'/static/images/cadu/products/studio-icon.png',connect:'/static/images/cadu/products/connect-icon.png',skills:'/static/images/cadu/products/skills-icon.png'};
  const onRefresh = () => {setRefreshRevision(value => value + 1); load(data?.client?.client_id);};
  const context = useMemo(() => ({period, setPeriod, switchClient}), [period, data?.client?.client_id]);
  if(data?.shared)return <SharedReports key={data.client.client_id} data={data}/>;
  const showAccountsView = accountsView && data?.ready;
  const hub = route.hub ? HUBS[route.hub] : null;
  const library = pageSection === 'imports' && new URLSearchParams(location.search).get('view') === 'library';
  const header = hub ? {title: hub.title, description: hub.description, tabs: hub.tabs}
    : {title: library ? 'Biblioteca de dados' : route.title, description: library ? 'Campos personalizados e dados preservados dos arquivos importados.' : route.description};
  const showFilterBar = data?.ready && !isFlowEditor && (pageSection === 'campaigns' && !route.entity && !new URLSearchParams(location.search).get('campaign_id')
    || pageSection === 'events' || (pageSection === 'flow' && new URLSearchParams(location.search).get('flow_view') === 'monitor'));
  const clientKey = data?.client?.client_id;
  const page = !data ? <LoadingState rows={4} label="Carregando Reports…"/>
    : !data.ready ? <Empty message="A base de Reports V1 ainda precisa da migração de dados." />
    : {
      overview: () => <Overview data={data}/>,
      media: () => <MediaOverview data={data}/>,
      campaigns: () => <Campaigns data={data} save={save} busy={busy} filters={filters} refreshRevision={refreshRevision} />,
      monitor: () => <Monitor data={data} save={save} busy={busy} />,
      journey: () => <JourneyOverview data={data}/>,
      flow: () => <Flow data={data} save={save} busy={busy} filters={filters} refreshRevision={refreshRevision} />,
      pages: () => <PageDetail data={data} />,
      navigation: () => <Navigation/>,
      conversions: () => <Conversions/>,
      reports: () => <Reports data={data} save={save} busy={busy} />,
      alerts: () => <AlertsCenter data={data} />,
      'data-sources': () => <DataSources data={data}/>,
      supertag: () => <SuperTag data={data} />,
      events: () => <Events data={data} filters={filters} refreshRevision={refreshRevision} />,
      imports: () => <Imports data={data} reloadBootstrap={() => load(data.client.client_id)} focusLibrary={library} />,
      links: () => <Links data={data} save={save} busy={busy} />,
      customers: () => <ReportsCustomers data={data} save={save} busy={busy}/>,
      accounts: () => <Accounts data={data} save={save} busy={busy} />,
      access: () => data.can_manage_access ? <Access data={data} save={save} busy={busy} /> : <Empty message="Seu acesso não permite administrar usuários do Reports neste cliente." />,
    }[pageSection]();
  return <ReportsContext.Provider value={context}><div data-cadu-skin="reports" className={`reports-shell reports-shell--${pageSection}${isFlowEditor?' reports-shell--flow-editor':''}${showAccountsView ? ' reports-shell--accounts-view' : ''}`}>
    {!isFlowEditor && !showAccountsView && <SolutionSidebar solution="Reports" userName={rootElement.dataset.userName||'Minha conta'} accountLabel={rootElement.dataset.agencyName||'Agência'} userAvatar={rootElement.dataset.userAvatar||''} creditsUrl={rootElement.dataset.creditsUrl} profileUrl={rootElement.dataset.profileUrl} accent="#175cd3" storageKey="reports-sidebar" active={route.nav} activeSolutionId="connect" solutionLogo={solutionIcons.connect} solutionUrls={solutionUrls} solutionIcons={solutionIcons} groups={groups} onNavigate={navigateOnClick} />}
    <main className="reports-main">
      {showAccountsView ? (
        <AccountsManagementView data={data} selectedCustomer={selectedCustomer} setSelectedCustomer={setSelectedCustomer} selectedAccount={selectedAccount} setSelectedAccount={setSelectedAccount} selectedCampaign={selectedCampaign} setSelectedCampaign={setSelectedCampaign} save={save} busy={busy} onExit={() => navigate(`${APP_BASE}/settings/accounts`)} />
      ) : (
        <>
          {data && !isFlowEditor && <PageHeader {...header} activeTab={route.path}
            context={<ContextSelector clients={data.clients} client={data.client} showPeriod={Boolean(route.period) && !(pageSection === 'pages' && new URLSearchParams(location.search).get('site_id'))}/>}/>}
          {showFilterBar && <ReportsFilterBar data={data} filters={filters} onChange={updateFilters} onRefresh={onRefresh} />}
          <div className="reports-content">{error && <div className="reports-error" role="alert">{error}</div>}<React.Fragment key={`${clientKey}:${route.path}`}>{page}</React.Fragment></div>
        </>
      )}
    </main>
  </div></ReportsContext.Provider>;
}

class ReportsErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {failed: false};
  }

  static getDerivedStateFromError() {
    return {failed: true};
  }

  componentDidCatch(error) {
    console.error('Reports render failed:', error);
  }

  render() {
    if (this.state.failed) return <main className="reports-content" role="alert">
      <div className="reports-error">Não foi possível exibir o Reports. Atualize a página para tentar novamente.</div>
    </main>;
    return this.props.children;
  }
}

createRoot(rootElement).render(<ReportsErrorBoundary><App /></ReportsErrorBoundary>);
