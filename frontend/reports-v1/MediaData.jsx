import React, {useEffect, useState} from 'react';
import {AlertTriangle, Check, ChevronUp, Copy01, Database01, Download01, Plus} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {Card, TD, TH} from './ReportsBlocks.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsConfirmDialog} from './ReportsConfirmDialog.jsx';
import {FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import {GoogleAdsHowItWorks} from './hubs/media/GoogleAdsHowItWorks.jsx';
import {APP_BASE} from './shell/routes.js';
import {useReportsContext} from './shell/context.js';
import {integer, json, shortDate} from './reportsCommon.jsx';
import {UnlinkedGoogleCampaigns} from './GoogleCampaignLinks.jsx';
import {ConnectGoogleAdsWizard} from './ConnectGoogleAdsWizard.jsx';
import {ScriptCard, digits, formatGoogleId, generateGoogleScripts, scriptName, validGoogleAdsAccountId} from './googleAdsScripts.jsx';

export {scriptName};

const SOURCES = {
  google_ads_script: {label: 'Google Ads Script', short: 'Google Ads · Leitura', name: 'Google Ads · monitoramento', description: 'Dois scripts na conta ou MCC: Leitura (métricas, diário) e Ações (aplica as mudanças aprovadas, de hora em hora).'},
  conversion_webhook: {label: 'CRM / conversões', short: 'CRM', name: 'CRM · conversões', description: 'Vendas e leads confirmados pelo CRM, sem dados pessoais.'},
};
// Listed in the keys table only; generated together with the Leitura script.
const KEY_KINDS = {...SOURCES, google_ads_actions: {short: 'Google Ads · Ações'}};
const SCRIPT_KINDS = {google_ads_script: true, google_ads_actions: true};
/** Numbered step title: the connection reads as choose → configure → install → link campaigns. */
function Step({n, title, children}) {
  return <div className="flex items-start gap-3">
    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-solid text-sm font-semibold text-white">{n}</span>
    <div><p className="text-md font-semibold text-primary">{title}</p>{children && <p className="mt-0.5 text-sm text-tertiary">{children}</p>}</div>
  </div>;
}

/** Health of an ingestion key, in the words the user acts on. */
function health(item) {
  if (item.revoked_at) return ['Revogada', 'gray'];
  if (!item.last_used_at) return [item.source_kind === 'google_ads_actions' ? 'Aguardando primeira execução' : 'Aguardando primeiro envio', 'brand'];
  if (item.source_kind === 'google_ads_actions' && Date.now() - new Date(item.last_used_at).getTime() > 3 * 3600 * 1000) return ['Sem execução há 3 h', 'warning'];
  if (item.source_kind === 'google_ads_script' && Date.now() - new Date(item.last_used_at).getTime() > 48 * 3600 * 1000) return ['Sem envio há 48 h', 'warning'];
  return ['Ativa', 'success'];
}


/** Mídia › Dados: connect Google Ads or a CRM, see each key's health and the batches received. */
export function MediaData({data, save, busy}) {
  const [keys, setKeys] = useState([]);
  const [runs, setRuns] = useState([]);
  const [unlinkedCampaignsCount, setUnlinkedCampaignsCount] = useState(0);
  const [sourceKind, setSourceKind] = useState('google_ads_script');
  const [label, setLabel] = useState(SOURCES.google_ads_script.name);
  const [managerAccountId, setManagerAccountId] = useState('');
  const [accountIds, setAccountIds] = useState([]);
  const [script, setScript] = useState('');
  const [scripts, setScripts] = useState([]);
  const [withActions, setWithActions] = useState(true);
  const [limits, setLimits] = useState({max_budget_change_pct: '30', max_cpc_change_pct: '30'});
  const [generatedKind, setGeneratedKind] = useState('google_ads_script');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const [revokeId, setRevokeId] = useState('');
  const [keyFilter, setKeyFilter] = useState('active');
  const [loaded, setLoaded] = useState(false);
  // null: follow the data (open only while nothing is connected); true/false: the user's choice.
  const [formOpen, setFormOpen] = useState(null);
  const [wizard, setWizard] = useState(false);
  const {scope} = useReportsContext();
  const scopedAccount = scope.account ? data.accounts.find(item => String(item.id) === scope.account) : null;
  const canEdit = data.client.role !== 'viewer';
  const google = sourceKind === 'google_ads_script';
  const managers = data.accounts.filter(account => account.platform === 'google_ads' && account.account_kind === 'manager' && account.status !== 'disabled' && validGoogleAdsAccountId(account.external_id));
  const advertisers = data.accounts.filter(account => account.platform === 'google_ads' && account.account_kind === 'advertiser' && account.status !== 'disabled' && validGoogleAdsAccountId(account.external_id));
  const invalid = data.accounts.filter(account => account.platform === 'google_ads' && account.status !== 'disabled' && !validGoogleAdsAccountId(account.external_id));
  const children = advertisers.filter(account => String(account.parent_account_id || '') === managerAccountId);
  const direct = advertisers.filter(account => !account.parent_account_id);
  const usableManager = managers.some(manager => advertisers.some(account => String(account.parent_account_id || '') === String(manager.id)));
  const blocking = managerAccountId
    ? invalid.filter(account => account.account_kind === 'advertiser' && String(account.parent_account_id || '') === managerAccountId)
    : direct.length || usableManager ? [] : invalid.filter(account => (account.account_kind === 'advertiser' && !account.parent_account_id)
      || (account.account_kind === 'manager' && data.accounts.some(child => child.account_kind === 'advertiser' && child.status !== 'disabled' && String(child.parent_account_id || '') === String(account.id))));
  // The header's source narrows the keys to the ones allowed (or bound) to that account.
  const ofAccount = item => !scopedAccount || (Boolean(digits(scopedAccount.external_id))
    && [...(item.allowed_account_ids || []), item.bound_account_id].map(digits).includes(digits(scopedAccount.external_id)));
  const scopedKeys = keys.filter(ofAccount);
  const active = scopedKeys.filter(item => !item.revoked_at);
  const connected = keys.some(item => !item.revoked_at);
  const showForm = formOpen ?? (loaded && !connected);
  const lastRun = runs[0]?.created_at;
  const attention = active.filter(item => health(item)[1] === 'warning').length;

  const reload = () => json(`/connect/api/v2/reports/ingest-keys`).then(value => {setKeys(value.keys || []); setRuns(value.runs || []); setLoaded(true);});
  useEffect(() => {reload().catch(failure => setError(failure.message));}, [data.client.client_id]);
  // Accounts that only exist under an MCC: start from that MCC instead of an empty direct list.
  useEffect(() => {
    if (managerAccountId || direct.length) return;
    const withAccounts = managers.filter(manager => advertisers.some(account => String(account.parent_account_id || '') === String(manager.id)));
    if (withAccounts.length === 1) setManagerAccountId(String(withAccounts[0].id));
  }, [data.accounts]);
  // A Google Ads account picked in the header starts the form on that account (and its MCC).
  useEffect(() => {
    if (!scopedAccount || scopedAccount.platform !== 'google_ads' || scopedAccount.account_kind !== 'advertiser' || !validGoogleAdsAccountId(scopedAccount.external_id)) return;
    setManagerAccountId(scopedAccount.parent_account_id ? String(scopedAccount.parent_account_id) : '');
    setAccountIds([scopedAccount.external_id]);
  }, [scope.account, data.accounts]);
  const choose = kind => {setSourceKind(kind); setLabel(SOURCES[kind].name);};
  const toggle = id => setAccountIds(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  const managerExternalId = managerAccountId ? managers.find(item => String(item.id) === managerAccountId)?.external_id : '';
  /** Leitura (and, by default, Ações) for the same accounts: one key each, named after the account and the version. */
  const createGoogle = async () => {
    setScripts(await generateGoogleScripts({save, withActions, label, managerExternalId, accountIds, limits})); setScript('');
  };
  const create = async event => {
    event.preventDefault(); setError('');
    try {
      if (google) await createGoogle();
      else {
        const created = await save('/ingest-keys', {label, source_kind: sourceKind, account_ids: []}, false);
        setScript(`POST ${location.origin}/connect/api/v1/reports/ingest/conversions\nAuthorization: Bearer ${created.token}\nContent-Type: application/json\n\n${JSON.stringify({events: [{external_event_id: 'pedido-123', visitor_id: 'UUID recebido de window.CaduSuperTag.getVisitorId()', kind: 'sale', occurred_at: new Date().toISOString(), value_micros: 129000000, currency: 'BRL'}]}, null, 2)}`);
        setScripts([]);
      }
      setGeneratedKind(sourceKind); setCopied(false);
      await reload();
    } catch (failure) {setError(failure.message); await reload().catch(() => {});}
  };
  const copy = async () => {try {await navigator.clipboard.writeText(script); setCopied(true);} catch {setCopied(false);}};
  const revoke = async id => {
    try {await save(`/ingest-keys/${id}/revoke`, {}, false); await reload(); setRevokeId('');} catch (failure) {setError(failure.message);}
  };
  const badLimit = withActions && Object.values(limits).some(value => !(Number(String(value).replace(',', '.')) >= 1 && Number(String(value).replace(',', '.')) <= 100));
  // Why "Gerar" is off, said next to the button instead of only greying it out.
  const reason = !google ? '' : managerAccountId && !children.length ? 'Esta MCC não tem contas anunciantes cadastradas.'
    : !accountIds.length ? (managerAccountId ? 'Marque ao menos uma conta da MCC.' : 'Escolha a conta que receberá os dados.')
    : badLimit ? 'Os tetos de variação devem ficar entre 1% e 100%.' : !label.trim() ? 'Dê um nome à instalação.' : '';
  const disabled = busy || Boolean(reason);
  const shownKeys = scopedKeys.filter(item => keyFilter === 'all' || (keyFilter === 'active' ? !item.revoked_at : item.revoked_at));
  const generated = scripts.length > 0 || Boolean(script);
  const googleKeys = active.filter(item => item.source_kind === 'google_ads_script');
  const receiving = googleKeys.some(item => item.last_used_at);

  return <div className="untitled-scope flex flex-col gap-6">
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-border-secondary shadow-xs ring-1 ring-secondary sm:grid-cols-4">
      {[['Fontes ativas', integer(active.length)], ['Precisam de atenção', integer(attention)], ['Último envio', lastRun ? shortDate(lastRun) : '—'], ['Lotes recebidos', integer(runs.length)]].map(([term, value]) =>
        <div key={term} className="min-w-0 bg-primary px-4 py-3 sm:px-5 sm:py-4"><dt className="text-sm font-medium text-tertiary">{term}</dt><dd className="mt-1 text-display-xs font-semibold text-primary tabular-nums">{value}</dd></div>)}
    </dl>
    {error && <p role="alert" className="rounded-lg bg-error-primary px-4 py-3 text-sm text-error-primary ring-1 ring-error_subtle">{error}</p>}

    {canEdit && !showForm && <Card title="Conectar fonte"
      description={loaded ? `${integer(keys.filter(item => !item.revoked_at).length)} chave(s) ativa(s) neste cliente. Gere outra só para uma nova conta, MCC ou CRM.` : 'Carregando conexões…'}
      actions={<><GoogleAdsHowItWorks/><Button size="md" color="primary" iconLeading={Plus} isDisabled={!loaded} onPress={() => setWizard(true)}>Conectar o Google Ads</Button><Button size="md" color="secondary" isDisabled={!loaded} onPress={() => setFormOpen(true)}>Conexão avançada</Button></>}/>}
    {canEdit && showForm && <Card title="Conectar fonte" description="Cada fonte recebe uma chave própria. Você pode revogar a qualquer momento."
      actions={<><GoogleAdsHowItWorks/><Button size="md" color="primary" iconLeading={Plus} onPress={() => setWizard(true)}>Assistente do Google Ads</Button>{connected && <Button size="md" color="tertiary" iconLeading={ChevronUp} onPress={() => setFormOpen(false)}>Recolher</Button>}</>}>
      <form className="flex flex-col gap-6" onSubmit={create}>
        <Step n={1} title="Escolha a fonte"/>
        <div role="radiogroup" aria-label="Fonte" className="grid gap-3 sm:grid-cols-2">
          {Object.entries(SOURCES).map(([kind, source]) => {
            const on = sourceKind === kind;
            return <label key={kind} className={`flex cursor-pointer items-start gap-3 rounded-xl p-4 ring-inset ${on ? 'bg-brand-primary ring-2 ring-brand' : 'ring-1 ring-secondary hover:bg-primary_hover'}`}>
              <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary ring-1 ring-secondary [&_img]:size-5">{kind === 'google_ads_script' ? <FlowPlatformLogo platform="google_ads"/> : <Database01 size={20} className="text-fg-quaternary"/>}</span>
              <span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-primary">{source.label}</span><span className="mt-0.5 block text-sm text-tertiary">{source.description}</span></span>
              <input type="radio" name="source" className="mt-1 size-4 accent-brand-600" checked={on} onChange={() => choose(kind)}/>
            </label>;
          })}
        </div>
        <Step n={2} title="Configure">{google ? 'Conta ou MCC onde o script roda, contas autorizadas e, se quiser, o script de Ações.' : 'Dê um nome; a chave do webhook é gerada em seguida.'}</Step>
        <div className="grid gap-4 sm:grid-cols-2">
          <ReportsFieldInput label="Nome da instalação" required maxLength={120} value={label} onChange={event => setLabel(event.target.value)} hint="Aparece na lista de chaves."/>
          {google && <ReportsNativeSelect label="Onde o script será instalado" value={managerAccountId} onChange={event => {setManagerAccountId(event.target.value); setAccountIds([]);}}>
            <option value="">Direto em uma conta anunciante</option>
            {managers.map(item => <option key={item.id} value={item.id}>{item.name} · {formatGoogleId(item.external_id)}</option>)}
          </ReportsNativeSelect>}
        </div>
        {google && <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-medium text-secondary">{managerAccountId ? 'Contas autorizadas nesta MCC' : 'Conta que receberá os dados'}</legend>
          {(managerAccountId ? children : direct).length ? <div className="overflow-hidden rounded-lg ring-1 ring-secondary">
            {(managerAccountId ? children : direct).map(item => <label key={item.id} className="flex cursor-pointer items-center gap-3 border-b border-secondary px-4 py-3 last:border-b-0 hover:bg-primary_hover">
              <input type={managerAccountId ? 'checkbox' : 'radio'} name="account" className="size-4 accent-brand-600" checked={accountIds.includes(item.external_id)}
                onChange={() => managerAccountId ? toggle(item.external_id) : setAccountIds([item.external_id])}/>
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-primary">{item.name}</span>
              <span className="font-mono text-xs text-tertiary">{formatGoogleId(item.external_id)}</span>
            </label>)}
          </div> : <p className="rounded-lg bg-secondary_subtle px-4 py-3 text-sm text-tertiary ring-1 ring-secondary ring-inset">
            {managerAccountId ? 'Nenhuma conta anunciante ligada a esta MCC.' : usableManager ? 'Suas contas estão ligadas a uma MCC: escolha a MCC em “Onde o script será instalado”.' : 'Nenhuma conta anunciante Google Ads com ID válido.'} Cadastre em <a className="font-semibold text-brand-secondary hover:underline" href={`${APP_BASE}/settings/accounts`}>Clientes e contas</a>.
          </p>}
        </fieldset>}
        {google && <fieldset className="flex flex-col gap-3 rounded-xl p-4 ring-1 ring-secondary ring-inset">
          <label className="flex cursor-pointer items-start gap-3">
            <input type="checkbox" className="mt-1 size-4 accent-brand-600" checked={withActions} onChange={event => setWithActions(event.target.checked)}/>
            <span><span className="block text-sm font-semibold text-primary">Também gerar o script de Ações</span>
              <span className="mt-0.5 block text-sm text-tertiary">Aplica no Google Ads as mudanças que vocês aprovarem no Reports: pausar e ativar, negativar, adicionar palavras-chave, lances e orçamento. Roda de hora em hora; a escrita pode ser desligada no próprio script.</span></span>
          </label>
          {withActions && <div className="grid gap-4 sm:grid-cols-2 sm:pl-7">
            <ReportsFieldInput label="Teto de variação do orçamento (%)" inputMode="decimal" value={limits.max_budget_change_pct} onChange={event => setLimits(current => ({...current, max_budget_change_pct: event.target.value}))} hint="Padrão 30%. Mudanças maiores são limitadas a este teto."/>
            <ReportsFieldInput label="Teto de variação do lance (%)" inputMode="decimal" value={limits.max_cpc_change_pct} onChange={event => setLimits(current => ({...current, max_cpc_change_pct: event.target.value}))} hint="Padrão 30%. Vale para o CPC máximo das palavras-chave."/>
          </div>}
        </fieldset>}
        {google && blocking.length > 0 && <div role="status" className="flex items-start gap-3 rounded-lg bg-warning-primary px-4 py-3 ring-1 ring-secondary ring-inset">
          <AlertTriangle size={20} className="shrink-0 text-fg-warning-primary"/>
          <p className="text-sm text-warning-primary">{blocking.length} conta(s) sem ID de 10 dígitos. <a className="font-semibold underline" href={`${APP_BASE}/settings/accounts`}>Corrija em Clientes e contas</a> para incluí-las.</p>
        </div>}
        <div className="flex items-center justify-end gap-3 border-t border-secondary pt-5">
          <span role="status" className={`text-sm ${reason ? 'text-warning-primary' : 'text-tertiary'}`}>{reason || (google ? `${accountIds.length} conta(s) selecionada(s)` : '')}</span>
          <Button type="submit" size="md" color="primary" isDisabled={disabled} isLoading={busy}>{google ? (withActions ? 'Gerar os 2 scripts' : 'Gerar script de Leitura') : 'Gerar chave do webhook'}</Button>
        </div>
      </form>
    </Card>}

    {scripts.length > 0 && <div className="flex flex-col gap-4">
      <p role="status" className="rounded-lg bg-warning-primary px-4 py-3 text-sm text-warning-primary ring-1 ring-secondary ring-inset">As chaves dentro dos scripts não serão mostradas de novo. Baixe os arquivos .txt agora e instale cada script com o nome sugerido.</p>
      {scripts.map(item => <ScriptCard key={item.kind} item={item}/>)}
    </div>}
    {script && <Card title={generatedKind === 'conversion_webhook' ? 'Contrato do webhook' : 'Script gerado'}
      badge={<Badge type="pill-color" size="sm" color="warning">Copie agora</Badge>}
      description={generatedKind === 'conversion_webhook' ? 'Envie as conversões neste formato. A chave não será mostrada de novo.' : 'Cole em Ferramentas › Scripts da conta ou MCC e agende a execução diária. A chave não será mostrada de novo.'}
      actions={<Button size="md" color={copied ? 'secondary' : 'primary'} iconLeading={copied ? Check : Copy01} onPress={copy}>{copied ? 'Copiado' : 'Copiar'}</Button>}>
      <pre aria-label="Código da integração" className="max-h-80 overflow-auto rounded-lg bg-secondary p-4 font-mono text-xs leading-5 whitespace-pre text-secondary ring-1 ring-secondary ring-inset">{script}</pre>
    </Card>}

    {unlinkedCampaignsCount > 0 && <div className="flex flex-col gap-3">
      <Step n={4} title="Ligue as campanhas do Google Ads">Os relatórios saem por campanha: cada campanha recebida pelo script precisa existir no Reports com o mesmo ID.</Step>
      <UnlinkedGoogleCampaigns save={save} busy={busy} clientId={data.client.client_id} revision={runs.length} onCountChange={setUnlinkedCampaignsCount}/>
    </div>}

    <Card flush title="Chaves de ingestão" badge={<Badge type="pill-color" size="sm" color="gray">{scopedKeys.length}</Badge>}
      description={scopedAccount ? `Chaves autorizadas para ${scopedAccount.name || formatGoogleId(scopedAccount.external_id)}. Revogar interrompe os envios; o histórico fica.` : 'Cada instalação usa a própria chave. Revogar interrompe os envios; o histórico fica.'}
      actions={scopedKeys.length > 0 && <div className="rs-segmented" role="group" aria-label="Chaves">{[['active', `Ativas · ${active.length}`], ['revoked', `Revogadas · ${scopedKeys.length - active.length}`], ['all', 'Todas']].map(([key, text]) =>
        <button type="button" key={key} aria-pressed={keyFilter === key} onClick={() => setKeyFilter(key)}>{text}</button>)}</div>}>
      {shownKeys.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px]">
        <thead><tr><th className={TH}>Instalação</th><th className={TH}>Contas permitidas</th><th className={TH}>Último envio</th><th className={TH}>Estado</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
        <tbody>{shownKeys.map(item => {
          const [state, color] = health(item);
          return <tr key={item.id} className={item.revoked_at ? 'opacity-60' : 'hover:bg-primary_hover'}>
            <td className={TD}><p className="font-medium text-primary">{item.label}</p><p className="text-xs text-tertiary">{KEY_KINDS[item.source_kind]?.short || item.source_kind}</p></td>
            <td className={TD}>{item.source_kind in SCRIPT_KINDS ? <div className="flex flex-col gap-0.5">
              {item.manager_external_id && <span className="text-xs text-tertiary">MCC <span className="font-mono">{formatGoogleId(item.manager_external_id)}</span></span>}
              <span className="font-mono text-xs text-secondary">{item.allowed_account_ids?.length ? item.allowed_account_ids.map(formatGoogleId).join(', ') : (item.bound_account_id ? formatGoogleId(item.bound_account_id) : 'Vincula no primeiro envio')}</span>
            </div> : <span className="text-quaternary">—</span>}</td>
            <td className={`${TD} whitespace-nowrap`}>{item.last_used_at ? shortDate(item.last_used_at) : '—'}</td>
            <td className={TD}><BadgeWithDot type="pill-color" size="sm" color={color}>{state}</BadgeWithDot></td>
            <td className={`${TD} text-right`}>{!item.revoked_at && canEdit && <Button size="sm" color="link-destructive" isDisabled={busy} onPress={() => setRevokeId(item.id)}>Revogar</Button>}</td>
          </tr>;
        })}</tbody>
      </table></div> : <div className="px-6 py-10 text-center"><p className="text-md font-semibold text-primary">{scopedKeys.length ? 'Nenhuma chave neste filtro' : scopedAccount && keys.length ? 'Nenhuma chave para esta conta' : 'Nenhuma fonte conectada'}</p><p className="mt-1 text-sm text-tertiary">{scopedAccount && keys.length && !scopedKeys.length ? 'Escolha “Todas as fontes” no cabeçalho para ver as demais chaves do cliente.' : 'Gere um script do Google Ads ou uma chave de webhook acima.'}</p></div>}
    </Card>

    <Card flush title="Últimos envios" badge={<Badge type="pill-color" size="sm" color="gray">{runs.length}</Badge>} description={scopedAccount ? 'Lotes recebidos de todas as fontes do cliente: o envio não informa a conta.' : 'Lotes recebidos das fontes conectadas.'}>
      {runs.length ? <div className="overflow-x-auto"><table className="w-full min-w-[560px]">
        <thead><tr><th className={TH}>Recebido</th><th className={TH}>Período</th><th className={`${TH} text-right`}>Linhas</th><th className={TH}>Estado</th></tr></thead>
        <tbody>{runs.map(item => <tr key={item.id} className="hover:bg-primary_hover">
          <td className={`${TD} whitespace-nowrap`}>{shortDate(item.created_at)}</td>
          <td className={`${TD} whitespace-nowrap`}>{shortDate(item.period_start)} – {shortDate(item.period_end)}</td>
          <td className={`${TD} text-right tabular-nums`}>{integer(item.record_count)}</td>
          <td className={TD}><BadgeWithDot type="pill-color" size="sm" color={item.status === 'completed' ? 'success' : item.status === 'failed' ? 'error' : 'gray'}>{item.status === 'completed' ? 'Concluído' : item.status === 'failed' ? 'Falhou' : item.status}</BadgeWithDot></td>
        </tr>)}</tbody>
      </table></div> : <div className="px-6 py-10 text-center"><p className="text-md font-semibold text-primary">Nenhum lote ainda</p><p className="mt-1 text-sm text-tertiary">O primeiro envio aparece aqui depois que o script rodar.</p></div>}
    </Card>
    {wizard && <ConnectGoogleAdsWizard data={data} save={save} busy={busy} reload={reload} onClose={() => setWizard(false)}/>}
    <ReportsConfirmDialog open={Boolean(revokeId)} title="Revogar chave de ingestão" description="O script que usa esta chave deixará de enviar dados. Os envios anteriores permanecem no histórico." confirmLabel="Revogar chave" busy={busy} onCancel={() => setRevokeId('')} onConfirm={() => revoke(revokeId)}/>
  </div>;
}
