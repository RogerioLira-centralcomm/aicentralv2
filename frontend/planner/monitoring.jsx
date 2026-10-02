import React, {useEffect, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {PlannerHeader} from './PlannerHeader.jsx';
import {CaduSelectField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {PlannerNotice, PlannerPanel} from './PlannerUi.jsx';
import {MetricTiles} from './details/DetailLayout.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';

const SITE_TYPES = [
  ['campaign', 'Landing page de campanha'],
  ['institutional', 'Site institucional'],
  ['ecommerce', 'E-commerce'],
  ['publisher', 'Portal ou publisher'],
  ['app', 'Aplicação web'],
  ['other', 'Outro tipo de site'],
];

const EMPTY_FUNNEL = {name: '', start_path: '/', conversion_path: ''};

export function MonitorPage({request}) {
  const requestRef = useRef(request);
  requestRef.current = request;
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState('');
  const [site, setSite] = useState(null);
  const [entryUrl, setEntryUrl] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [siteName, setSiteName] = useState('');
  const [siteType, setSiteType] = useState('institutional');
  const [funnelName, setFunnelName] = useState('');
  const [funnelDraft, setFunnelDraft] = useState(EMPTY_FUNNEL);
  const [editingFunnel, setEditingFunnel] = useState('');
  const [showSetup, setShowSetup] = useState(false);
  const [showFunnelForm, setShowFunnelForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function loadSites(keepSelected = true) {
    const data = await requestRef.current('/monitor/sites');
    const next = data.sites || [];
    setSites(next);
    if (!keepSelected || !next.some(item => item.id === siteId)) setSiteId(next[0]?.id || '');
    return next;
  }

  useEffect(() => {
    requestRef.current('/monitor/sites').then(data => {
      const next = data.sites || [];
      setSites(next);
      setSiteId(next[0]?.id || '');
    }).catch(err => setError(err.message));
  }, []);

  useEffect(() => {
    if (!siteId) {
      setSite(null);
      return undefined;
    }
    let active = true;
    const refresh = () => requestRef.current('/monitor/sites/' + encodeURIComponent(siteId))
      .then(data => { if (active) setSite(data.site || null); })
      .catch(err => { if (active) setError(err.message); });
    refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, [siteId]);

  async function analyze(event) {
    event.preventDefault();
    setBusy(true); setError(''); setNotice(''); setAnalysis(null);
    try {
      const data = await request('/monitor/analyze', {method: 'POST', body: JSON.stringify({entry_url: entryUrl})});
      const result = data.analysis;
      setAnalysis(result);
      setSiteName(result.evidence?.site_name || result.evidence?.title || result.domain || '');
      setSiteType(result.suggestion?.site_type || 'institutional');
      setFunnelName(result.suggestion?.funnel_name || 'Contato');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function createSite(event) {
    event.preventDefault();
    if (!analysis) return;
    setBusy(true); setError('');
    try {
      const data = await request('/monitor/sites', {method: 'POST', body: JSON.stringify({
        entry_url: analysis.entry_url, name: siteName, site_type: siteType,
        funnel_name: funnelName, analysis,
      })});
      setSite(data.site);
      setSiteId(data.site.id);
      await loadSites();
      setShowSetup(false); setAnalysis(null); setEntryUrl('');
      setNotice('Site e primeiro funil configurados. Instale a tag para começar a receber eventos.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function editFunnel(funnel) {
    setEditingFunnel(funnel.id);
    setFunnelDraft({name: funnel.name, start_path: funnel.start_path, conversion_path: funnel.conversion_path || ''});
    setShowFunnelForm(true);
  }

  async function saveFunnel(event) {
    event.preventDefault();
    if (!site) return;
    setBusy(true); setError('');
    const payload = {...funnelDraft, steps: [
      {name: 'Entrada', path: funnelDraft.start_path},
      {name: 'Conversão', path: funnelDraft.conversion_path},
    ]};
    try {
      const path = '/monitor/sites/' + site.id + '/funnels' + (editingFunnel ? '/' + editingFunnel : '');
      const data = await request(path, {method: editingFunnel ? 'PUT' : 'POST', body: JSON.stringify(payload)});
      setSite(data.site); setShowFunnelForm(false); setEditingFunnel(''); setFunnelDraft(EMPTY_FUNNEL);
      setNotice('Funil salvo. A conversão será contabilizada somente no Planner.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const metrics = site?.metrics || {};
  const typeLabel = SITE_TYPES.find(([value]) => value === site?.site_type)?.[1] || 'Site';
  const selectedHealth = site?.health_checks?.[0];

  return <>
    <PlannerHeader title={site ? site.name : 'Sites e funis'}
      crumbs={site ? [['Sites e funis', null]] : null}
      meta={site ? <CaduBadge tone="neutral">{typeLabel}</CaduBadge> : null}
      description={site ? <a href={site.entry_url} target="_blank" rel="noreferrer">{site.entry_url}</a> : 'Mapeie jornadas por URL e acompanhe visitas, conversões e disponibilidade.'}
      actions={<>
        {sites.length > 1 && <CaduSelectField size="sm" className="ph-context__select" aria-label="Site acompanhado" value={siteId}
          onChange={e => {setSiteId(e.target.value);setNotice('');}} options={sites.map(item => ({value: item.id, label: `${item.name} · ${item.domain}`}))}/>}
        {site && <CaduButton variant="secondary" onClick={() => window.open(site.test_url, '_blank', 'noopener,noreferrer')}><Icon name="external" size={16}/>Abrir teste</CaduButton>}
        <CaduButton variant={showSetup ? 'secondary' : 'primary'} onClick={() => {setShowSetup(!showSetup);setAnalysis(null);setError('');}}>{showSetup ? 'Fechar cadastro' : <><Icon name="plus" size={16}/>Adicionar site</>}</CaduButton>
      </>}/>

    <PlannerNotice notice={error ? {tone: 'error', message: error} : notice ? {message: notice} : null} onDismiss={() => { setError(''); setNotice(''); }}/>

    {showSetup && <PlannerPanel className="monitor-setup" title="Começar pelo endereço do site" description="Lemos apenas a página pública informada para sugerir o tipo de site e um primeiro funil.">
      <form className="monitor-url-form" onSubmit={analyze}>
        <CaduInput label="URL inicial" type="url" required value={entryUrl} onChange={e => setEntryUrl(e.target.value)} placeholder="https://www.exemplo.com.br/campanha" autoComplete="url"/>
        <CaduButton type="submit" loading={busy}>Analisar endereço</CaduButton>
      </form>
      {analysis && <form className="monitor-confirm" onSubmit={createSite}>
        <div className="monitor-evidence">
          <div><small>Página analisada</small><strong>{analysis.evidence?.title || analysis.domain}</strong><span>{analysis.entry_url}</span></div>
          {analysis.suggestion && <CaduBadge tone="brand">Sugestão · {Math.round((analysis.suggestion.site_type_confidence || 0) * 100)}%</CaduBadge>}
        </div>
        {analysis.message && <p>{analysis.message}</p>}
        <div className="planner-fields">
          <CaduInput label="Nome deste site" required maxLength="180" value={siteName} onChange={e => setSiteName(e.target.value)}/>
          <CaduSelectField label="Tipo de site" value={siteType} onChange={e => setSiteType(e.target.value)} options={SITE_TYPES.map(([value, label]) => ({value, label}))}/>
          <CaduInput className="is-wide" label="Nome do primeiro funil" required maxLength="120" value={funnelName} onChange={e => setFunnelName(e.target.value)}/>
        </div>
        <div className="monitor-evidence-list"><strong>Endereços públicos encontrados</strong>
          {analysis.evidence?.public_paths?.length ? <div>{analysis.evidence.public_paths.slice(0, 8).map(path => <code key={path}>{path}</code>)}</div>
            : <span>Não encontramos outros caminhos públicos nesta página.</span>}
        </div>
        <p className="monitor-privacy">A sugestão é revisável. O Planner não recebe senhas, campos de formulário nem dados pessoais do site.</p>
        <div><CaduButton type="submit" loading={busy}>Confirmar e configurar site</CaduButton></div>
      </form>}
    </PlannerPanel>}

    {sites.length > 0 ? <>
      {site && <>
        <MetricTiles items={[
          {label: 'Pessoas online', value: Number(metrics.online_now || 0).toLocaleString('pt-BR'), hint: 'Últimos 5 minutos'},
          {label: 'Pessoas únicas', value: Number(metrics.visitors_24h || 0).toLocaleString('pt-BR'), hint: 'Últimas 24 horas'},
          {label: 'Páginas recebidas', value: Number(metrics.page_views_24h || 0).toLocaleString('pt-BR'), hint: 'Últimas 24 horas'},
          {label: 'Conversões', value: Number(metrics.conversions_24h || 0).toLocaleString('pt-BR'), hint: `Taxa de ${Number(metrics.conversion_rate || 0).toLocaleString('pt-BR')}% · atualiza a cada 15 s`},
        ]}/>

        <div className="monitor-columns">
          <PlannerPanel title="Disponibilidade" description="Verificação automática da URL configurada." actions={<span className={'health-state ' + (selectedHealth?.status || 'waiting')}><i />{healthLabel(selectedHealth?.status)}</span>}>
            {selectedHealth ? <div className="health-detail"><strong>{selectedHealth.response_ms ?? '—'} ms</strong>
              <span>{selectedHealth.detail}</span><small>Última verificação · {formatDate(selectedHealth.checked_at)}</small></div>
              : <p className="planner-muted">A primeira verificação será feita pelo monitor automático.</p>}
            {!!site.health_checks?.length && <div className="health-pages" aria-label="Disponibilidade por URL">
              {site.health_checks.map(check => <div className="health-page-row" key={check.checked_url}>
                <code>{check.checked_url}</code><span>{formatDate(check.checked_at)}</span>
                <b className={check.status}>{healthLabel(check.status)}</b>
              </div>)}
            </div>}
          </PlannerPanel>
          <PlannerPanel className="monitor-install" title="Instalar pelo GTM" description="Adicione como tag HTML personalizada e exija consentimento de análise antes do disparo." actions={<span className="monitor-pulse"><i />Tag própria</span>}>
            <pre><code>{site.install_snippet}</code></pre>
            <CaduButton variant="secondary" onClick={() => navigator.clipboard?.writeText(site.install_snippet).then(() => setNotice('Código da tag copiado.')).catch(() => setError('Não foi possível copiar o código.'))}>Copiar tag</CaduButton>
            <p className="monitor-privacy">A tag envia páginas e conversões somente ao Planner. Para excluir sessões de teste das tags de anúncios, crie no GTM uma exceção para a URL com <code>cadu_test=1</code> (ou para o cookie <code>cadu_monitor_test=1</code>).</p>
          </PlannerPanel>
        </div>

        <PlannerPanel className="monitor-funnels" title="Funis por URL" description="Jornadas diferentes para campanhas, site institucional ou áreas específicas."
          actions={<CaduButton variant="secondary" onClick={() => {setEditingFunnel('');setFunnelDraft(EMPTY_FUNNEL);setShowFunnelForm(!showFunnelForm);}}>Novo funil</CaduButton>}>
          {showFunnelForm && <form className="monitor-funnel-form" onSubmit={saveFunnel}>
            <CaduInput label="Nome do funil" required maxLength="120" value={funnelDraft.name} onChange={e => setFunnelDraft({...funnelDraft, name: e.target.value})} placeholder="Ex.: Campanha de lançamento"/>
            <CaduInput label="URL de entrada" required value={funnelDraft.start_path} onChange={e => setFunnelDraft({...funnelDraft, start_path: e.target.value})} placeholder="/campanha"/>
            <CaduInput label="URL de conversão" value={funnelDraft.conversion_path} onChange={e => setFunnelDraft({...funnelDraft, conversion_path: e.target.value})} placeholder="/obrigado"/>
            <small>Use caminhos reais do site. A conversão fica sem contagem até você informar uma URL ou configurar o evento do GTM.</small>
            <div className="monitor-form-actions"><CaduButton variant="secondary" onClick={() => setShowFunnelForm(false)}>Cancelar</CaduButton><CaduButton type="submit" loading={busy}>{editingFunnel ? 'Salvar alterações' : 'Salvar funil'}</CaduButton></div>
          </form>}
          <div className="funnel-list">{(site.funnels || []).map(funnel => <article className="funnel-row" key={funnel.id}>
            <div className="funnel-route"><span className="route-node">{funnel.start_path}</span><span className="route-link" /><span className={funnel.conversion_path ? 'route-node is-goal' : 'route-node is-empty'}>{funnel.conversion_path || 'Conversão a configurar'}</span></div>
            <div className="funnel-row-info"><div><strong>{funnel.name}</strong>{funnel.is_default && <CaduBadge tone="neutral">Padrão</CaduBadge>}</div>
              <small>{Number((site.metrics?.funnel_conversions || {})[funnel.id] || 0).toLocaleString('pt-BR')} conversões nas últimas 24 horas</small></div>
            <CaduButton variant="secondary" size="sm" onClick={() => editFunnel(funnel)}>Editar</CaduButton>
            {!funnel.conversion_path && <code className="funnel-hook">GTM: window.CaduPlannerMonitor?.conversion('{funnel.id}')</code>}
          </article>)}</div>
          <p className="monitor-privacy">Conversões marcadas como teste ficam separadas e não entram nos números acima nem são enviadas a plataformas de anúncios.</p>
        </PlannerPanel>
      </>}
    </> : !showSetup && <PlannerPanel className="planner-panel--flush"><CaduEmptyState title="Acompanhe o que acontece no site"
      description="Comece por uma URL. O Planner sugere o tipo de site, prepara um funil inicial e gera a tag para instalar pelo Google Tag Manager."
      action={<CaduButton onClick={() => setShowSetup(true)}>Mapear meu primeiro site</CaduButton>}/></PlannerPanel>}
  </>;
}

function healthLabel(status) {
  return ({up: 'No ar', degraded: 'Instável', down: 'Fora do ar', blocked: 'Acesso bloqueado'})[status] || 'Aguardando';
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'});
}
