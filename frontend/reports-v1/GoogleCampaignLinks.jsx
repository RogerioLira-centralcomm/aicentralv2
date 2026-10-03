import React, {useEffect, useState} from 'react';
import {Button as UntitledButton} from '../cadu-design-system/untitled-kit/button.tsx';
import {CAMPAIGN_STATUS, Status as CampaignStatus, channelLabel} from './ClientsAccounts.jsx';
import {json, Empty} from './reportsCommon.jsx';

const BIDDING_OBJECTIVE = {
  MAXIMIZE_CONVERSIONS: 'Conversões', TARGET_CPA: 'Conversões com CPA alvo', MAXIMIZE_CONVERSION_VALUE: 'Valor de conversão',
  TARGET_ROAS: 'Valor de conversão com ROAS alvo', MAXIMIZE_CLICKS: 'Tráfego (cliques)', TARGET_SPEND: 'Tráfego (cliques)', MANUAL_CPC: 'Tráfego (CPC manual)',
  TARGET_IMPRESSION_SHARE: 'Parcela de impressões', MANUAL_CPM: 'Alcance (CPM)', TARGET_CPM: 'Alcance (CPM)', MANUAL_CPV: 'Visualizações de vídeo',
};

/** Unlinked Google Ads campaigns of this client (sent by the script, not in Reports yet). */
export const loadUnlinkedGoogleCampaigns = () => json('/connect/api/v2/reports/google-ads/unlinked-campaigns').then(value => value.campaigns || []);

/** Creates the Reports campaign from everything the script already knows: account, real id, name, channel and objective. */
export const createFromGoogle = (save, row, reload = true) => save('/campaigns', {
  account_id: row.account_id, external_id: row.campaign_external_id, name: row.campaign_name || `Campanha ${row.campaign_external_id}`,
  channel_type: row.channel_type || undefined, objective: BIDDING_OBJECTIVE[row.bidding_strategy_type] || undefined,
}, reload);

/** Google Ads campaigns the script already sends but that have no Reports campaign yet: create them with the real ids. */
export function UnlinkedGoogleCampaigns({save, busy, clientId, revision, emptyMessage = '', onCountChange}) {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState('');
  const load = () => loadUnlinkedGoogleCampaigns().then(value => {setRows(value); setError(''); onCountChange?.(value.length);}).catch(failure => {setError(failure.message); onCountChange?.(0);});
  useEffect(() => {load();}, [clientId, revision]);
  const create = async list => {
    // Only the last one reloads the page data, so the new campaigns show up in the list below at once.
    try {
      for (const [index, row] of list.entries()) await createFromGoogle(save, row, index === list.length - 1);
    } catch {/* save already shows the error */} finally {load();}
  };
  if (!rows.length && !error) return emptyMessage ? <article className="reports-panel"><Empty message={emptyMessage}/></article> : null;
  return <article className="reports-panel">
    <div className="reports-panel-head"><div><h2>Campanhas do Google Ads sem cadastro <small>{rows.length}</small></h2><p>Recebidas pelo script, mas ainda sem campanha no Reports. Crie para ver desempenho, metas e criativos com os IDs corretos.</p></div>
      {rows.length > 1 && <UntitledButton size="sm" color="primary" isDisabled={busy} onPress={() => create(rows)}>Criar todas ({rows.length})</UntitledButton>}</div>
    {error ? <Empty message={error}/> : <div className="reports-table-wrap"><table className="cadu-table"><thead><tr><th>Campanha</th><th>Conta</th><th>Tipo</th><th>Status</th><th></th></tr></thead><tbody>{rows.map(row => <tr key={`${row.account_id}:${row.campaign_external_id}`}>
      <td><span className="reports-cell-stack"><strong>{row.campaign_name || `Campanha ${row.campaign_external_id}`}</strong><small>ID {row.campaign_external_id}</small></span></td>
      <td><span className="reports-cell-stack"><span>{row.account_name}</span><small>Google Ads</small></span></td>
      <td>{channelLabel(row.channel_type) || '—'}</td>
      <td>{row.status ? <CampaignStatus map={CAMPAIGN_STATUS} value={row.status}/> : '—'}</td>
      <td><UntitledButton size="sm" color="secondary" isDisabled={busy} onPress={() => create([row])}>Criar campanha</UntitledButton></td></tr>)}</tbody></table></div>}
  </article>;
}
