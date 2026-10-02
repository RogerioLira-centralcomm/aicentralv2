import React from 'react';
import {ReportsActionButton} from '../../ReportsActionButton.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {friendlyAgo, friendlyDateTime} from '../../friendlyDates.js';
import {apiUrl, useApi} from '../../shell/useApi.js';
import {platformName} from '../../shell/media.jsx';
import {Async, DataTable, EmptyState, Section} from '../../shell/primitives.jsx';
import {number} from '../shared.jsx';

const KIND = {google_ads_script: 'Google Ads Script', conversion_webhook: 'Webhook de conversões'};
const FILE_STATUS = {applied: ['Aplicado', 'success'], parsed: ['Em revisão', 'warning'], pending: ['Processando', 'gray'], failed: ['Falhou', 'error'], conflict: ['Com conflitos', 'warning']};
const tone = last => !last ? 'warning' : Date.now() - Date.parse(last) > 48 * 3600e3 ? 'error' : 'success';
const badge = (label, kind) => <span className={`rs-badge is-${kind}`}>{label}</span>;

/** "De onde os dados vêm?" — every source by category with status and freshness. Configuration stays on each source's page. */
export function DataSources({data}) {
  const [keys, retryKeys] = useApi(apiUrl('/ingest-keys'));
  const [sites, retrySites] = useApi(apiUrl('/supertag/sites'));
  const [files, retryFiles] = useApi(apiUrl('/imports'));
  const live = item => !item.revoked_at;
  const media = (keys.body?.keys || []).filter(item => live(item) && item.source_kind === 'google_ads_script');
  const business = (keys.body?.keys || []).filter(item => live(item) && item.source_kind !== 'google_ads_script');
  const accounts = data.accounts.filter(item => item.status !== 'disabled');
  return <div className="rs-stack">
    <Section title="Mídia" description="Plataformas de anúncio conectadas e contas cadastradas" action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('data-sources/connect')}>Conectar fonte</ReportsActionButton>}>
      <Async state={keys} onRetry={retryKeys}>
        {() => <DataTable label="Fontes de mídia" rows={media} rowKey={row => row.id}
          empty={<EmptyState title="Nenhuma integração de mídia" description={accounts.length ? `${accounts.length} ${accounts.length === 1 ? 'conta cadastrada' : 'contas cadastradas'}, ainda sem envio automático. Gere o script do Google Ads ou envie arquivos.` : 'Cadastre as contas de mídia e conecte o Google Ads ou envie arquivos exportados.'}/>}
          columns={[
            {key: 'label', label: 'Fonte', render: row => <><strong>{row.label}</strong><small className="rs-cell-sub">{KIND[row.source_kind] || row.source_kind}</small></>},
            {key: 'accounts', label: 'Contas', numeric: true, sort: row => (row.allowed_account_ids || []).length, render: row => number((row.allowed_account_ids || []).length || (row.bound_account_id ? 1 : 0))},
            {key: 'last_used_at', label: 'Última sincronização', render: row => row.last_used_at ? friendlyAgo(row.last_used_at) : '—'},
            {key: 'status', label: 'Status', sortable: false, render: row => badge(!row.last_used_at ? 'Aguardando envio' : tone(row.last_used_at) === 'error' ? 'Sem envio há 48 h' : 'Ativa', tone(row.last_used_at))},
          ]}/>}
      </Async>
      {accounts.length > 0 && <p className="rs-muted">Contas: {[...new Set(accounts.map(item => platformName(item.platform)))].join(', ')} · <a className="rs-link-inline" href={reportUrl('settings/accounts')}>gerenciar contas e conexões</a></p>}
    </Section>
    <Section title="Site" description="Domínios com a Super Tag" action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('supertag')}>Abrir Super Tag</ReportsActionButton>}>
      <Async state={sites} onRetry={retrySites}>
        {body => <DataTable label="Sites" rows={body.sites.filter(live)} rowKey={row => row.id}
          empty={<EmptyState title="Nenhum site conectado" description="Instale a Super Tag para medir visitas, eventos e conversões do site."/>} columns={[
            {key: 'allowed_host', label: 'Domínio', render: row => <a href={reportUrl('supertag', {}, row.id)}>{row.allowed_host}</a>},
            {key: 'events_30d', label: 'Eventos (30 dias)', numeric: true, render: row => number(row.events_30d)},
            {key: 'last_event_at', label: 'Último evento', render: row => row.last_event_at ? friendlyAgo(row.last_event_at) : '—'},
            {key: 'status', label: 'Status', sortable: false, render: row => !row.enabled ? badge('Pausada', 'gray') : badge(row.last_event_at ? 'Coletando' : 'Aguardando eventos', row.last_event_at ? 'success' : 'warning')},
          ]}/>}
      </Async>
    </Section>
    <Section title="Arquivos" description="Planilhas e relatórios importados" action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('imports')}>Nova importação</ReportsActionButton>}>
      <Async state={files} onRetry={retryFiles}>
        {body => <DataTable label="Arquivos importados" limit={10} rows={body.imports || []} rowKey={row => row.id}
          empty={<EmptyState title="Nenhum arquivo importado" description="Envie CSV, XLSX ou capturas de relatório para incluir mídia sem integração."/>} columns={[
            {key: 'original_name', label: 'Arquivo', render: row => <><strong>{row.original_name}</strong><small className="rs-cell-sub">{(row.file_kind || '').toUpperCase()}</small></>},
            {key: 'created_at', label: 'Enviado', render: row => friendlyDateTime(row.created_at)},
            {key: 'row_count', label: 'Registros', numeric: true, render: row => number(row.applied_count ?? row.row_count)},
            {key: 'status', label: 'Status', sortable: false, render: row => {const [label, kind] = FILE_STATUS[row.status] || [row.status, 'gray']; return badge(label, kind);}},
          ]}/>}
      </Async>
    </Section>
    <Section title="Negócio" description="Conversões confirmadas pelo CRM" action={<ReportsActionButton color="secondary" size="sm" href={reportUrl('data-sources/connect')}>Conectar CRM</ReportsActionButton>}>
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
