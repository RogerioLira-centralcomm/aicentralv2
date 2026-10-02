import React, {useEffect, useState} from 'react';
import {AlertTriangle, Check, Copy01, Database01, Download01} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {Card, TD, TH} from './ReportsBlocks.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsConfirmDialog} from './ReportsConfirmDialog.jsx';
import {FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import {GoogleAdsHowItWorks} from './hubs/media/GoogleAdsHowItWorks.jsx';
import {APP_BASE} from './shell/routes.js';
import {integer, json, shortDate} from './reportsCommon.jsx';

const validGoogleAdsAccountId = value => /^(?:\d{10}|\d{3}-\d{3}-\d{4})$/.test(String(value || '').trim());
const formatGoogleId = value => String(value).replace(/^(\d{3})(\d{3})(\d{4})$/, '$1-$2-$3');
const SOURCES = {
  google_ads_script: {label: 'Google Ads Script', short: 'Google Ads · Leitura', name: 'Google Ads · monitoramento', description: 'Dois scripts na conta ou MCC: Leitura (métricas, diário) e Ações (aplica as mudanças aprovadas, de hora em hora).'},
  conversion_webhook: {label: 'CRM / conversões', short: 'CRM', name: 'CRM · conversões', description: 'Vendas e leads confirmados pelo CRM, sem dados pessoais.'},
};
// Listed in the keys table only; generated together with the Leitura script.
const KEY_KINDS = {...SOURCES, google_ads_actions: {short: 'Google Ads · Ações'}};
const SCRIPT_KINDS = {google_ads_script: true, google_ads_actions: true};
const SCRIPTS = {
  read: {file: '/static/cadu_connect/google-ads-engine-v2.js', title: 'Leitura', schedule: 'diariamente', kind: 'google_ads_script'},
  actions: {file: '/static/cadu_connect/google-ads-actions.js', title: 'Acoes', schedule: 'de hora em hora', kind: 'google_ads_actions'},
};

/** Name used for the .txt file and suggested for the script in Google Ads: product, script, account and version. */
export function scriptName(kind, accountLabel, version) {
  return `Cadu_GoogleAds_${SCRIPTS[kind].title}_${accountLabel}_v${version}`;
}
const versionOf = template => (template.match(/engineVersion:\s*'([^']+)'/) || [])[1] || '0';
function downloadText(text, name) {
  const url = URL.createObjectURL(new Blob([text], {type: 'text/plain;charset=utf-8'}));
  const link = Object.assign(document.createElement('a'), {href: url, download: `${name}.txt`});
  document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
}
async function template(kind) {
  const response = await fetch(SCRIPTS[kind].file, {credentials: 'same-origin', cache: 'no-store'});
  if (!response.ok) throw new Error('Não foi possível carregar o script do Google Ads.');
  return response.text();
}

/** One generated script: suggested name, download as .txt and copy. */
function ScriptCard({item}) {
  const [copied, setCopied] = useState('');
  const copy = async (value, what) => {try {await navigator.clipboard.writeText(value); setCopied(what);} catch {setCopied('');}};
  return <Card title={`Script de ${item.kind === 'read' ? 'Leitura' : 'Ações'} · v${item.version}`}
    badge={<Badge type="pill-color" size="sm" color="warning">Baixe ou copie agora</Badge>}
    description={item.kind === 'read'
      ? 'Lê métricas, termos e negativas e envia ao Reports. Nunca altera a conta. Agende diariamente.'
      : `Aplica as mudanças aprovadas no Reports (pausar, ativar, negativar, palavras-chave, lance e orçamento até ±${item.limits.max_budget_change_pct}%/±${item.limits.max_cpc_change_pct}%). Agende de hora em hora.`}
    actions={<div className="flex flex-wrap gap-2">
      <Button size="md" color="primary" iconLeading={Download01} onPress={() => downloadText(item.text, item.name)}>Baixar .txt</Button>
      <Button size="md" color="secondary" iconLeading={copied === 'code' ? Check : Copy01} onPress={() => copy(item.text, 'code')}>{copied === 'code' ? 'Copiado' : 'Copiar código'}</Button>
    </div>}>
    <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg bg-secondary_subtle px-3 py-2 text-sm ring-1 ring-secondary ring-inset">
      <span className="text-tertiary">Nome no Google Ads:</span>
      <code className="font-mono text-xs font-semibold text-primary">{item.name}</code>
      <Button size="sm" color="link-color" onPress={() => copy(item.name, 'name')}>{copied === 'name' ? 'Copiado' : 'Copiar nome'}</Button>
      <span className="ml-auto text-xs text-tertiary">Ferramentas › Scripts › + › cole o código › Programar: {SCRIPTS[item.kind].schedule}</span>
    </div>
    <pre aria-label={`Código do script de ${item.kind === 'read' ? 'Leitura' : 'Ações'}`} className="max-h-64 overflow-auto rounded-lg bg-secondary p-4 font-mono text-xs leading-5 whitespace-pre text-secondary ring-1 ring-secondary ring-inset">{item.text}</pre>
  </Card>;
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
  const active = keys.filter(item => !item.revoked_at);
  const lastRun = runs[0]?.created_at;
  const attention = active.filter(item => health(item)[1] === 'warning').length;

  const reload = () => json(`/connect/api/v2/reports/ingest-keys`).then(value => {setKeys(value.keys || []); setRuns(value.runs || []);});
  useEffect(() => {reload().catch(failure => setError(failure.message));}, [data.client.client_id]);
  // Accounts that only exist under an MCC: start from that MCC instead of an empty direct list.
  useEffect(() => {
    if (managerAccountId || direct.length) return;
    const withAccounts = managers.filter(manager => advertisers.some(account => String(account.parent_account_id || '') === String(manager.id)));
    if (withAccounts.length === 1) setManagerAccountId(String(withAccounts[0].id));
  }, [data.accounts]);
  const choose = kind => {setSourceKind(kind); setLabel(SOURCES[kind].name);};
  const toggle = id => setAccountIds(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
  const managerExternalId = managerAccountId ? managers.find(item => String(item.id) === managerAccountId)?.external_id : '';
  /** Leitura (and, by default, Ações) for the same accounts: one key each, named after the account and the version. */
  const createGoogle = async () => {
    const kinds = withActions ? ['read', 'actions'] : ['read'];
    const templates = await Promise.all(kinds.map(template));
    const accountLabel = managerExternalId ? `MCC-${formatGoogleId(managerExternalId)}` : formatGoogleId(accountIds[0]);
    const today = new Date().toLocaleDateString('pt-BR');
    const generated = [];
    for (const [index, kind] of kinds.entries()) {
      const created = await save('/ingest-keys', {label: kind === 'read' ? label : `${label} · Ações`, source_kind: SCRIPTS[kind].kind,
        manager_account_id: managerExternalId, account_ids: accountIds, limits: kind === 'actions' ? limits : undefined}, false);
      const version = versionOf(templates[index]);
      const name = scriptName(kind, accountLabel, version);
      const accounts = created.allowed_account_ids.map(formatGoogleId);
      const title = `${name} · ${managerExternalId ? `MCC ${formatGoogleId(managerExternalId)} · contas ${accounts.join(', ')}` : `conta ${accounts.join(', ')}`} · gerado em ${today}`;
      let text = templates[index].replace('__CADU_INGEST_URL__', `${location.origin}/connect/api/gads`).replace('__CADU_API_KEY__', created.token)
        .replace('__CADU_ACCOUNT_IDS__', JSON.stringify(accounts));
      text = kind === 'actions'
        ? text.replace('__CADU_SCRIPT_TITLE__', title).replace('__CADU_MAX_BUDGET_PCT__', String(created.limits.max_budget_change_pct))
          .replace('__CADU_MAX_CPC_PCT__', String(created.limits.max_cpc_change_pct))
        : `// ${title}\n${text}`;
      generated.push({kind, name, version, text, limits: created.limits || {}});
    }
    setScripts(generated); setScript('');
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
  const disabled = busy || (google && (!accountIds.length || (managerAccountId && !children.length) || badLimit));

  return <div className="untitled-scope flex flex-col gap-6">
    <dl className="grid gap-px overflow-hidden rounded-xl bg-border-secondary shadow-xs ring-1 ring-secondary sm:grid-cols-4">
      {[['Fontes ativas', integer(active.length)], ['Precisam de atenção', integer(attention)], ['Último envio', lastRun ? shortDate(lastRun) : '—'], ['Lotes recebidos', integer(runs.length)]].map(([term, value]) =>
        <div key={term} className="bg-primary px-5 py-4"><dt className="text-sm font-medium text-tertiary">{term}</dt><dd className="mt-1 text-display-xs font-semibold text-primary tabular-nums">{value}</dd></div>)}
    </dl>
    {error && <p role="alert" className="rounded-lg bg-error-primary px-4 py-3 text-sm text-error-primary ring-1 ring-error_subtle">{error}</p>}

    {canEdit && <Card title="Conectar fonte" description="Cada fonte recebe uma chave própria. Você pode revogar a qualquer momento." actions={<GoogleAdsHowItWorks/>}>
      <form className="flex flex-col gap-6" onSubmit={create}>
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
          {google && <span className="text-sm text-tertiary">{accountIds.length ? `${accountIds.length} conta(s) selecionada(s)` : 'Escolha ao menos uma conta'}</span>}
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

    <Card flush title="Chaves de ingestão" badge={<Badge type="pill-color" size="sm" color="gray">{keys.length}</Badge>} description="Cada instalação usa a própria chave. Revogar interrompe os envios; o histórico fica.">
      {keys.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px]">
        <thead><tr><th className={TH}>Instalação</th><th className={TH}>Contas permitidas</th><th className={TH}>Último envio</th><th className={TH}>Estado</th><th className={TH}><span className="sr-only">Ações</span></th></tr></thead>
        <tbody>{keys.map(item => {
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
      </table></div> : <div className="px-6 py-10 text-center"><p className="text-md font-semibold text-primary">Nenhuma fonte conectada</p><p className="mt-1 text-sm text-tertiary">Gere um script do Google Ads ou uma chave de webhook acima.</p></div>}
    </Card>

    <Card flush title="Últimos envios" badge={<Badge type="pill-color" size="sm" color="gray">{runs.length}</Badge>} description="Lotes recebidos das fontes conectadas.">
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
    <ReportsConfirmDialog open={Boolean(revokeId)} title="Revogar chave de ingestão" description="O script que usa esta chave deixará de enviar dados. Os envios anteriores permanecem no histórico." confirmLabel="Revogar chave" busy={busy} onCancel={() => setRevokeId('')} onConfirm={() => revoke(revokeId)}/>
  </div>;
}
