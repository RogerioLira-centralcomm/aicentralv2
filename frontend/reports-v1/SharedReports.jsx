import React, {useEffect, useState} from 'react';
import {FlowMonitorWorkspace} from './FlowMonitorWorkspace.jsx';
import {ReportsClientSelect, ReportsPageHeader} from './PageChrome.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';

export function SharedReports({data}) {
  const [flows, setFlows] = useState([]);
  const [sites, setSites] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let timedOut = false;
    setSelected(null);
    setFlows([]);
    setSites([]);
    setError('');
    setLoading(true);
    const timeout = setTimeout(() => {timedOut = true; controller.abort();}, 15000);
    async function load() {
      try {
        const response = await fetch(`/connect/api/v2/reports/shared/resources`, {signal: controller.signal});
        if (!response.ok) throw new Error('Não foi possível consultar seus acessos.');
        const result = await response.json();
        if (!Array.isArray(result.flows) || !Array.isArray(result.sites)) throw new Error('Não foi possível carregar os recursos compartilhados.');
        if (active) {setFlows(result.flows); setSites(result.sites);}
      } catch (failure) {
        if (active) setError(timedOut ? 'A consulta demorou mais que o esperado. Tente novamente.' : failure.message);
      } finally {
        clearTimeout(timeout);
        if (active) setLoading(false);
      }
    }
    load();
    return () => {active = false; clearTimeout(timeout); controller.abort();};
  }, [data.client.client_id, attempt]);

  if (selected) return <div data-cadu-skin="reports"><FlowMonitorWorkspace
    key={`${data.client.client_id}:${selected.id}`} flow={selected} client={data.client}
    csrf={data.csrf} filters={{period: '30'}} baseConfig={selected.config}
    headerActions={<ReportsClientSelect clients={data.clients} client={data.client}/>}
    onBack={() => setSelected(null)}/></div>;

  return <div data-cadu-skin="reports" className="reports-shared-page">
    <ReportsPageHeader clients={data.clients} client={data.client} titleOverride="Compartilhados com você" descriptionOverride={data.client.client_name}/>
    <main className="reports-content" aria-busy={loading}>
      {loading && <p role="status">Carregando recursos compartilhados…</p>}
      {error && <div role="alert"><p>{error}</p><Button onClick={() => setAttempt(value => value + 1)}>Tentar novamente</Button></div>}
      {!loading && !error && <>
        {sites.length > 0 && <section aria-label="Sites compartilhados"><h2>Sites</h2>{sites.map(site => <p key={site.id}><strong>{site.label}</strong> · {site.allowed_host} · {site.events_30d} eventos nos últimos 30 dias</p>)}</section>}
        {flows.length > 0 && <section aria-label="Fluxos compartilhados"><h2>Fluxos</h2>{flows.map(flow => <p key={flow.id}>{flow.name} <Button onClick={() => setSelected(flow)}>Monitorar</Button></p>)}</section>}
        {!flows.length && <p>{sites.length ? 'Os sites compartilhados ainda não têm fluxos disponíveis para monitoramento.' : 'Nenhum recurso compartilhado disponível nesta conta.'}</p>}
      </>}
    </main>
  </div>;
}
