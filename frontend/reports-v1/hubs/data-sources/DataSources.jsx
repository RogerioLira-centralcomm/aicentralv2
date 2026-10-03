import React, {useState} from 'react';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {json, reportUrl} from '../../reportsCommon.jsx';
import {ReportsNativeSelect} from '../../ReportsNativeSelect.jsx';
import {ALL_CUSTOMERS, NO_CUSTOMER, readCustomer} from '../../shell/customerScope.js';
import {friendlyAgo, friendlyDateTime} from '../../friendlyDates.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {platformName} from '../../shell/media.jsx';
import {Async, DataTable, EmptyState, Section} from '../../shell/primitives.jsx';
import {number} from '../shared.jsx';

const KIND = {google_ads_script: 'Google Ads Script', conversion_webhook: 'Webhook de conversões'};
const FILE_STATUS = {applied: ['Aplicado', 'success'], parsed: ['Em revisão', 'warning'], pending: ['Processando', 'gray'], failed: ['Falhou', 'error'], conflict: ['Com conflitos', 'warning']};
const tone = last => !last ? 'warning' : Date.now() - Date.parse(last) > 48 * 3600e3 ? 'error' : 'success';
const badge = (label, kind) => <span className={`rs-badge is-${kind}`}>{label}</span>;

/** "De onde os dados vêm?" — every source by category, by client, with status and freshness. Configuration stays on each source's page. */
export function DataSources({data}) {
  const [keys, retryKeys] = useApi(apiUrl('/ingest-keys'));
  const [sites, retrySites] = useApi(apiUrl('/supertag/sites'));
  const [files, retryFiles] = useApi(apiUrl('/imports'));
  const [working, setWorking] = useState('');
  const [error, setError] = useState('');
  const customer = readCustomer();
  const customers = (data.customers || []).filter(item => item.status !== 'archived');
  const canEdit = data.client.role !== 'viewer';
  const current = customers.find(item => String(item.id) === customer);
  const nameOf = id => customers.find(item => item.id === id)?.name;
  const inScope = id => customer === ALL_CUSTOMERS || (customer === NO_CUSTOMER ? !id : String(id || '') === customer);
  const live = item => !item.revoked_at;
  const accounts = data.accounts.filter(item => item.status !== 'disabled');
  // A media key reaches the clients of the accounts it may send for; one with no account yet belongs to nobody.
  const customersOfKey = key => {
    const ids = new Set([...(key.allowed_account_ids || []), key.bound_account_id].filter(Boolean).map(String));
    return [...new Set(data.accounts.filter(item => ids.has(String(item.external_id))).map(item => item.customer_id || null))];
  };
  const keyInScope = key => {const owners = customersOfKey(key); return customer === ALL_CUSTOMERS || (customer === NO_CUSTOMER ? !owners.length || owners.includes(null) : owners.some(id => inScope(id)));};
  const media = (keys.body?.keys || []).filter(item => live(item) && item.source_kind === 'google_ads_script' && keyInScope(item));
  const business = (keys.body?.keys || []).filter(item => live(item) && item.source_kind !== 'google_ads_script');
  const scopedAccounts = accounts.filter(item => inScope(item.customer_id));
  const accountName = (data.clients || []).find(item => String(item.id) === String(data.client.client_id))?.name || '';
  const scopeLabel = current ? current.name : customer === NO_CUSTOMER ? 'sem cliente' : '';
  const relink = async (site, value) => {
    setWorking(site.id); setError('');
    try {
      await json(`/connect/api/v2/reports/supertag/sites/${site.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({customer_id: value || null})});
      retrySites();
    } catch (failure) {setError(failure.message);} finally {setWorking('');}
  };
  const accountNote = scopeLabel && <p className="rs-muted rs-sources__note">Arquivos e CRM ainda são da conta {accountName}, sem separação por cliente; por isso aparecem iguais em todos os filtros.</p>;
  return <div className="rs-stack">
    {error && <div className="rs-error" role="alert"><div><strong>Não foi possível concluir</strong><p>{error}</p></div></div>}
    <Section title="Mídia" description={`Plataformas de anúncio conectadas e contas cadastradas${scopeLabel ? ` · ${scopeLabel}` : ''}`} action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('data-sources/connect')}>Conectar fonte</ReportsActionButton>}>
      <Async state={keys} onRetry={retryKeys}>
        {() => <DataTable label="Fontes de mídia" rows={media} rowKey={row => row.id}
          empty={<EmptyState title={scopeLabel ? `Nenhuma integração de mídia para ${scopeLabel}` : 'Nenhuma integração de mídia'} description={scopedAccounts.length ? `${scopedAccounts.length} ${scopedAccounts.length === 1 ? 'conta cadastrada' : 'contas cadastradas'}, ainda sem envio automático. Gere o script do Google Ads ou envie arquivos.` : 'Cadastre as contas de mídia e conecte o Google Ads ou envie arquivos exportados.'}/>}
          columns={[
            {key: 'label', label: 'Fonte', render: row => <><strong>{row.label}</strong><small className="rs-cell-sub">{KIND[row.source_kind] || row.source_kind}</small></>},
            {key: 'customer', label: 'Cliente', sort: row => customersOfKey(row).map(nameOf).join(), render: row => {
              const names = customersOfKey(row).map(id => id ? nameOf(id) : null);
              return names.length ? names.map(name => name || 'Sem cliente').join(', ') : <span className="rs-muted">—</span>;
            }},
            {key: 'accounts', label: 'Contas', numeric: true, sort: row => (row.allowed_account_ids || []).length, render: row => number((row.allowed_account_ids || []).length || (row.bound_account_id ? 1 : 0))},
            {key: 'last_used_at', label: 'Última sincronização', render: row => row.last_used_at ? friendlyAgo(row.last_used_at) : '—'},
            {key: 'status', label: 'Status', sortable: false, render: row => badge(!row.last_used_at ? 'Aguardando envio' : tone(row.last_used_at) === 'error' ? 'Sem envio há 48 h' : 'Ativa', tone(row.last_used_at))},
          ]}/>}
      </Async>
      {scopedAccounts.length > 0 && <p className="rs-muted">Contas: {[...new Set(scopedAccounts.map(item => platformName(item.platform)))].join(', ')} · <a className="rs-link-inline" href={reportUrl('settings/accounts', current ? {customer: current.id} : {})}>gerenciar contas e conexões</a></p>}
    </Section>
    <Section title="Site" description={`Domínios com a Super Tag${scopeLabel ? ` · ${scopeLabel}` : ''}`} action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('supertag')}>Abrir Super Tag</ReportsActionButton>}>
      <Async state={sites} onRetry={retrySites}>
        {body => <DataTable label="Sites" rows={body.sites.filter(live).filter(site => inScope(site.customer_id))} rowKey={row => row.id}
          empty={<EmptyState title={scopeLabel ? `Nenhum site de ${scopeLabel}` : 'Nenhum site conectado'} description={scopeLabel ? 'Ligue um site a este cliente na coluna Cliente, escolhendo outro filtro, ou instale a Super Tag.' : 'Instale a Super Tag para medir visitas, eventos e conversões do site.'}/>} columns={[
            {key: 'allowed_host', label: 'Domínio', render: row => <a href={reportUrl('supertag', {}, row.id)}>{row.allowed_host}</a>},
            {key: 'customer', label: 'Cliente', sort: row => nameOf(row.customer_id) || '', render: row => canEdit
              ? <ReportsNativeSelect size="sm" value={row.customer_id || ''} disabled={working === row.id} aria-label={`Cliente de ${row.allowed_host}`} onChange={event => relink(row, event.target.value)}>
                <option value="">Sem cliente</option>
                {customers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
              </ReportsNativeSelect>
              : nameOf(row.customer_id) || <span className="rs-muted">Sem cliente</span>},
            {key: 'events_30d', label: 'Eventos (30 dias)', numeric: true, render: row => number(row.events_30d)},
            {key: 'last_event_at', label: 'Último evento', render: row => row.last_event_at ? friendlyAgo(row.last_event_at) : '—'},
            {key: 'status', label: 'Status', sortable: false, render: row => !row.enabled ? badge('Pausada', 'gray') : badge(row.last_event_at ? 'Coletando' : 'Aguardando eventos', row.last_event_at ? 'success' : 'warning')},
          ]}/>}
      </Async>
    </Section>
    <Section title="Arquivos" description="Planilhas e relatórios importados pela conta" action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('imports')}>Nova importação</ReportsActionButton>}>
      <Async state={files} onRetry={retryFiles}>
        {body => <DataTable label="Arquivos importados" limit={10} rows={body.imports || []} rowKey={row => row.id}
          empty={<EmptyState title="Nenhum arquivo importado" description="Envie CSV, XLSX ou capturas de relatório para incluir mídia sem integração."/>} columns={[
            {key: 'original_name', label: 'Arquivo', render: row => <><strong>{row.original_name}</strong><small className="rs-cell-sub">{(row.file_kind || '').toUpperCase()}</small></>},
            {key: 'created_at', label: 'Enviado', render: row => friendlyDateTime(row.created_at)},
            {key: 'row_count', label: 'Registros', numeric: true, render: row => number(row.applied_count ?? row.row_count)},
            {key: 'status', label: 'Status', sortable: false, render: row => {const [label, kind] = FILE_STATUS[row.status] || [row.status, 'gray']; return badge(label, kind);}},
          ]}/>}
      </Async>
      {accountNote}
    </Section>
    <Section title="Negócio" description="Conversões confirmadas pelo CRM, da conta" action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('data-sources/connect')}>Conectar CRM</ReportsActionButton>}>
      <Async state={keys} onRetry={retryKeys}>
        {() => <DataTable label="Fontes de negócio" rows={business} rowKey={row => row.id}
          empty={<p className="rs-muted">Nenhum webhook de conversões. Conecte o CRM para confirmar leads e vendas.</p>} columns={[
            {key: 'label', label: 'Fonte', render: row => <><strong>{row.label}</strong><small className="rs-cell-sub">{KIND[row.source_kind] || row.source_kind}</small></>},
            {key: 'last_used_at', label: 'Último envio', render: row => row.last_used_at ? friendlyAgo(row.last_used_at) : '—'},
            {key: 'status', label: 'Status', sortable: false, render: row => badge(row.last_used_at ? 'Ativa' : 'Aguardando envio', row.last_used_at ? 'success' : 'warning')},
          ]}/>}
      </Async>
    </Section>
  </div>;
}
