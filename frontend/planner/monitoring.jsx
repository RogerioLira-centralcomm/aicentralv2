import React, {useEffect, useRef, useState} from 'react';

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
    <div className="page-intro monitor-intro">
      <div><span className="eyebrow">Medição própria</span><h1>Sites e funis</h1>
        <p>Mapeie jornadas por URL e acompanhe dados recebidos, conversões e disponibilidade.</p></div>
      <button className="button primary" onClick={() => {setShowSetup(!showSetup);setAnalysis(null);setError('');}}>
        {showSetup ? 'Fechar cadastro' : 'Adicionar site'}
      </button>
    </div>

    {error && <div className="feedback" role="alert">{error}<button onClick={() => setError('')} aria-label="Fechar aviso">×</button></div>}
    {notice && <div className="monitor-notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Fechar aviso">×</button></div>}

    {showSetup && <section className="panel monitor-setup">
      <h2>Começar pelo endereço do site</h2>
      <p>Vamos ler apenas a página pública informada para sugerir o tipo de site e um primeiro funil.</p>
      <form className="monitor-url-form" onSubmit={analyze}>
        <label>URL inicial
          <input type="url" required value={entryUrl} onChange={e => setEntryUrl(e.target.value)}
            placeholder="https://www.exemplo.com.br/campanha" autoComplete="url" />
        </label>
        <button className="button primary" disabled={busy}>{busy ? 'Analisando…' : 'Analisar endereço'}</button>
      </form>
      {analysis && <form className="monitor-confirm" onSubmit={createSite}>
        <div className="monitor-evidence">
          <div><small>Página analisada</small><strong>{analysis.evidence?.title || analysis.domain}</strong>
            <span>{analysis.entry_url}</span></div>
          {analysis.suggestion && <span className="badge">Sugestão · {Math.round((analysis.suggestion.site_type_confidence || 0) * 100)}%</span>}
        </div>
        <p>{analysis.message}</p>
        <div className="form-grid">
          <label>Nome deste site<input required maxLength="180" value={siteName} onChange={e => setSiteName(e.target.value)} /></label>
          <label>Tipo de site<select value={siteType} onChange={e => setSiteType(e.target.value)}>
            {SITE_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
          <label className="wide">Nome do primeiro funil<input required maxLength="120" value={funnelName} onChange={e => setFunnelName(e.target.value)} /></label>
        </div>
        <div className="monitor-evidence-list"><strong>Endereços públicos encontrados</strong>
          {analysis.evidence?.public_paths?.length ? <div>{analysis.evidence.public_paths.slice(0, 8).map(path => <code key={path}>{path}</code>)}</div>
            : <span>Não encontramos outros caminhos públicos nesta página.</span>}
        </div>
        <p className="monitor-privacy">A sugestão é revisável. O Planner não recebe senhas, campos de formulário nem dados pessoais do site.</p>
        <button className="button primary" disabled={busy}>{busy ? 'Salvando…' : 'Confirmar e configurar site'}</button>
      </form>}
    </section>}

    {sites.length > 0 ? <>
      <div className="monitor-site-switcher"><label>Site acompanhado
        <select value={siteId} onChange={e => {setSiteId(e.target.value);setNotice('');}}>
          {sites.map(item => <option key={item.id} value={item.id}>{item.name} · {item.domain}</option>)}
        </select>
      </label><span>Atualização dos dados recebidos a cada 15 segundos</span></div>

      {site && <>
        <section className="monitor-site-heading">
          <div><span className="badge">{typeLabel}</span><h2>{site.name}</h2><a href={site.entry_url} target="_blank" rel="noreferrer">{site.entry_url}</a></div>
          <button className="button" onClick={() => window.open(site.test_url, '_blank', 'noopener,noreferrer')}>Abrir teste em nova aba</button>
        </section>

        <section className="monitor-metrics" aria-label="Métricas do site">
          <article className="monitor-metric"><span>Pessoas online</span><strong key={metrics.online_now || 0}>{Number(metrics.online_now || 0).toLocaleString('pt-BR')}</strong><small>últimos 5 minutos</small></article>
          <article className="monitor-metric"><span>Pessoas únicas</span><strong key={metrics.visitors_24h || 0}>{Number(metrics.visitors_24h || 0).toLocaleString('pt-BR')}</strong><small>últimas 24 horas</small></article>
          <article className="monitor-metric"><span>Páginas recebidas</span><strong key={metrics.page_views_24h || 0}>{Number(metrics.page_views_24h || 0).toLocaleString('pt-BR')}</strong><small>últimas 24 horas</small></article>
          <article className="monitor-metric is-conversion"><span>Conversões</span><strong key={metrics.conversions_24h || 0}>{Number(metrics.conversions_24h || 0).toLocaleString('pt-BR')}</strong><small>{Number(metrics.conversion_rate || 0).toLocaleString('pt-BR')}% · últimas 24 horas</small></article>
        </section>

        <div className="monitor-columns">
          <section className="panel monitor-health">
            <div className="monitor-section-head"><div><h2>Disponibilidade</h2><p>Verificação automática da URL configurada.</p></div>
              <span className={'health-state ' + (selectedHealth?.status || 'waiting')}><i />{healthLabel(selectedHealth?.status)}</span></div>
            {selectedHealth ? <div className="health-detail"><strong>{selectedHealth.response_ms ?? '—'} ms</strong>
              <span>{selectedHealth.detail}</span><small>Última verificação · {formatDate(selectedHealth.checked_at)}</small></div>
              : <div className="monitor-empty-inline">A primeira verificação será feita pelo monitor automático.</div>}
            {!!site.health_checks?.length && <div className="health-pages" aria-label="Disponibilidade por URL">
              {site.health_checks.map(check => <div className="health-page-row" key={check.checked_url}>
                <code>{check.checked_url}</code><span>{formatDate(check.checked_at)}</span>
                <b className={check.status}>{healthLabel(check.status)}</b>
              </div>)}
            </div>}
          </section>
          <section className="panel monitor-install">
            <div className="monitor-section-head"><div><h2>Instalar pelo GTM</h2><p>Adicione como tag HTML personalizada e configure o GTM para exigir consentimento de análise antes do disparo.</p></div><span className="monitor-pulse"><i />Tag própria</span></div>
            <pre><code>{site.install_snippet}</code></pre>
            <button className="button small" onClick={() => navigator.clipboard?.writeText(site.install_snippet).then(() => setNotice('Código da tag copiado.')).catch(() => setError('Não foi possível copiar o código.'))}>Copiar tag</button>
            <p className="monitor-privacy">A tag envia páginas e conversões somente ao Planner. Para excluir sessões de teste das tags de anúncios que já existem, crie no GTM uma exceção para a URL com <code>cadu_test=1</code> (ou para o cookie <code>cadu_monitor_test=1</code>).</p>
          </section>
        </div>

        <section className="panel monitor-funnels">
          <div className="monitor-section-head"><div><h2>Funis por URL</h2><p>Crie jornadas diferentes para campanhas, site institucional ou áreas específicas.</p></div>
            <button className="button" onClick={() => {setEditingFunnel('');setFunnelDraft(EMPTY_FUNNEL);setShowFunnelForm(!showFunnelForm);}}>Novo funil</button></div>
          {showFunnelForm && <form className="monitor-funnel-form" onSubmit={saveFunnel}>
            <label>Nome do funil<input required maxLength="120" value={funnelDraft.name} onChange={e => setFunnelDraft({...funnelDraft, name: e.target.value})} placeholder="Ex.: Campanha de lançamento" /></label>
            <label>URL de entrada<input required value={funnelDraft.start_path} onChange={e => setFunnelDraft({...funnelDraft, start_path: e.target.value})} placeholder="/campanha" /></label>
            <label>URL de conversão<input value={funnelDraft.conversion_path} onChange={e => setFunnelDraft({...funnelDraft, conversion_path: e.target.value})} placeholder="/obrigado" /></label>
            <div className="monitor-form-actions"><button className="button" type="button" onClick={() => setShowFunnelForm(false)}>Cancelar</button><button className="button primary" disabled={busy}>{editingFunnel ? 'Salvar alterações' : 'Salvar funil'}</button></div>
            <small>Use caminhos reais do site. A conversão fica sem contagem até você informar uma URL ou configurar o evento do GTM.</small>
          </form>}
          <div className="funnel-list">{(site.funnels || []).map(funnel => <article className="funnel-row" key={funnel.id}>
            <div className="funnel-route"><span className="route-node">{funnel.start_path}</span><span className="route-link" /><span className={funnel.conversion_path ? 'route-node is-goal' : 'route-node is-empty'}>{funnel.conversion_path || 'Conversão a configurar'}</span></div>
            <div className="funnel-row-info"><div><strong>{funnel.name}</strong>{funnel.is_default && <span className="badge">Padrão</span>}</div>
              <small>{Number((site.metrics?.funnel_conversions || {})[funnel.id] || 0).toLocaleString('pt-BR')} conversões nas últimas 24 horas</small></div>
            <button className="button small" onClick={() => editFunnel(funnel)}>Editar</button>
            {!funnel.conversion_path && <code className="funnel-hook">GTM: window.CaduPlannerMonitor?.conversion('{funnel.id}')</code>}
          </article>)}</div>
          <p className="monitor-privacy">Conversões marcadas como teste ficam separadas e não entram nos números acima nem são enviadas a plataformas de anúncios.</p>
        </section>
      </>}
    </> : !showSetup && <section className="panel monitor-empty">
      <div className="monitor-empty-mark">↗</div><h2>Acompanhe o que acontece no site</h2>
      <p>Comece por uma URL. O Planner sugere o tipo de site, prepara um funil inicial e gera a tag para instalar pelo Google Tag Manager.</p>
      <button className="button primary" onClick={() => setShowSetup(true)}>Mapear meu primeiro site</button>
    </section>}
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
