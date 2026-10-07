import React, {useEffect, useState} from 'react';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {ReportsWizard} from './ReportsWizard.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ScriptCard, digits, formatGoogleId, generateGoogleScripts, validGoogleAdsAccountId} from './googleAdsScripts.jsx';
import {createFromGoogle, loadUnlinkedGoogleCampaigns} from './GoogleCampaignLinks.jsx';
import {json} from './reportsCommon.jsx';
import {APP_BASE} from './shell/routes.js';

const ART = '/static/images/reports/illustrations/';
const STEPS = [
  {key: 'fonte', label: 'Fonte', art: 'gads-1-fonte.webp', focus: '45%', title: 'De onde vêm os dados?', text: 'Escolha a conta do Google Ads (ou a MCC) onde o script vai rodar. Ele só lê métricas; nada é alterado na conta.'},
  {key: 'script', label: 'Script', art: 'gads-2-script.webp', focus: '45%', title: 'Cole o script no Google Ads', text: 'Geramos o script com a chave da sua conta. Em Ferramentas › Scripts, crie um script novo e cole o código.'},
  {key: 'campanha', label: 'Campanha', art: 'gads-3-campanha.webp', focus: '42%', optional: true, title: 'Qual campanha acompanhar?', text: 'Os relatórios saem por campanha. Cadastre agora com o ID do Google Ads ou espere o primeiro envio para criar a partir do que chegar.'},
  {key: 'aguardando', label: 'Primeiro envio', art: 'gads-4-aguardando.webp', focus: '40%', title: 'Conectado. Esperando os dados', text: 'Depois que o script rodar pela primeira vez, os dados aparecem em Mídia. Você pode fechar e voltar depois.'},
];
const radio = 'size-4 accent-brand-600';

/** Contas do Google Ads ainda sem script: o que dá para escolher e para onde cada escolha leva. */
function Source({data, state, set, locked}) {
  const {managers, advertisers} = state.accounts;
  const children = advertisers.filter(item => String(item.parent_account_id || '') === state.managerId);
  const direct = advertisers.filter(item => !item.parent_account_id);
  const list = state.managerId ? children : direct;
  const toggle = id => set({accountIds: state.accountIds.includes(id) ? state.accountIds.filter(item => item !== id) : [...state.accountIds, id]});
  return <div className="rw__fields">
    {managers.length > 0 && <ReportsNativeSelect label="Onde o script será instalado" disabled={locked} value={state.managerId} onChange={event => set({managerId: event.target.value, accountIds: []})}>
      <option value="">Direto em uma conta anunciante</option>
      {managers.map(item => <option key={item.id} value={item.id}>{item.name} · {formatGoogleId(item.external_id)}</option>)}
    </ReportsNativeSelect>}
    <fieldset className="flex flex-col gap-2" disabled={locked}>
      <legend className="mb-2 text-sm font-medium text-secondary">{state.managerId ? 'Contas autorizadas nesta MCC' : 'Conta que receberá os dados'}</legend>
      {list.length ? <div className="overflow-hidden rounded-lg ring-1 ring-secondary">
        {list.map(item => <label key={item.id} className="flex cursor-pointer items-center gap-3 border-b border-secondary px-4 py-3 last:border-b-0 hover:bg-primary_hover">
          <input type={state.managerId ? 'checkbox' : 'radio'} name="gads-account" className={radio} checked={state.accountIds.includes(item.external_id)}
            onChange={() => state.managerId ? toggle(item.external_id) : set({accountIds: [item.external_id]})}/>
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-primary">{item.name}</span>
          <span className="font-mono text-xs text-tertiary">{formatGoogleId(item.external_id)}</span>
        </label>)}
      </div> : <p className="rounded-lg bg-secondary_subtle px-4 py-3 text-sm text-tertiary ring-1 ring-secondary ring-inset">
        {state.managerId ? 'Nenhuma conta anunciante ligada a esta MCC.' : managers.length ? 'Suas contas estão ligadas a uma MCC: escolha a MCC acima.' : 'Nenhuma conta anunciante do Google Ads com ID válido.'}{' '}
        Cadastre em <a className="font-semibold text-brand-secondary hover:underline" href={`${APP_BASE}/settings/accounts`}>Clientes e contas</a>.
      </p>}
    </fieldset>
    <ReportsFieldInput label="Nome da instalação" required maxLength={120} disabled={locked} value={state.label} onChange={event => set({label: event.target.value})} hint="Aparece na lista de chaves."/>
    {locked && <p className="text-sm text-tertiary">Os scripts já foram gerados com estas contas. Para mudar, revogue a chave em Conexões e chaves e comece de novo.</p>}
  </div>;
}

/** Leitura (e Ações, se quiser): as chaves só aparecem uma vez, então os scripts ficam na tela até concluir. */
function Scripts({state, set, generate, busy, reason}) {
  const [limitsOpen, setLimitsOpen] = useState(false);
  const badLimit = state.withActions && Object.values(state.limits).some(value => !(Number(String(value).replace(',', '.')) >= 1 && Number(String(value).replace(',', '.')) <= 100));
  const blocked = Boolean(reason) || badLimit;
  return <div className="rw__fields">
    {!state.scripts.length && <>
      <label className="flex cursor-pointer items-start gap-3 rounded-xl p-4 ring-1 ring-secondary ring-inset">
        <input type="checkbox" className={`mt-1 ${radio}`} checked={state.withActions} onChange={event => set({withActions: event.target.checked})}/>
        <span><span className="block text-sm font-semibold text-primary">Também gerar o script de Ações</span>
          <span className="mt-0.5 block text-sm text-tertiary">Aplica no Google Ads o que vocês aprovarem no Reports (pausar, negativar, lances, orçamento). Roda de hora em hora e dá para desligar a escrita no próprio script.</span></span>
      </label>
      {state.withActions && <>
        <button type="button" className="self-start text-sm font-semibold text-brand-secondary" onClick={() => setLimitsOpen(value => !value)}>{limitsOpen ? 'Ocultar tetos de variação' : 'Ajustar tetos de variação (padrão 30%)'}</button>
        {limitsOpen && <div className="grid gap-4 sm:grid-cols-2">
          <ReportsFieldInput label="Teto do orçamento (%)" inputMode="decimal" value={state.limits.max_budget_change_pct} onChange={event => set({limits: {...state.limits, max_budget_change_pct: event.target.value}})}/>
          <ReportsFieldInput label="Teto do lance (%)" inputMode="decimal" value={state.limits.max_cpc_change_pct} onChange={event => set({limits: {...state.limits, max_cpc_change_pct: event.target.value}})}/>
        </div>}
      </>}
      {(reason || badLimit) && <p role="status" className="text-sm text-warning-primary">{reason || 'Os tetos de variação devem ficar entre 1% e 100%.'}</p>}
      <Button type="button" size="lg" color="primary" isDisabled={blocked || busy} isLoading={busy} onPress={generate}>{state.withActions ? 'Gerar os 2 scripts' : 'Gerar script de Leitura'}</Button>
    </>}
    {state.scripts.length > 0 && <>
      <p role="status" className="rounded-lg bg-warning-primary px-4 py-3 text-sm text-warning-primary ring-1 ring-secondary ring-inset">As chaves dentro dos scripts não aparecem de novo. Baixe os .txt agora e instale cada script com o nome sugerido.</p>
      {state.scripts.map(item => <ScriptCard key={item.kind} item={item}/>)}
    </>}
  </div>;
}

/** Campanhas: as que o script já mandou (sem cadastro), as já cadastradas e o cadastro manual pelo ID do Google Ads. */
function Campaigns({data, state, save, reportsAccounts, created, setCreated, busy}) {
  const [unlinked, setUnlinked] = useState([]);
  const [manual, setManual] = useState({accountId: '', name: '', externalId: ''});
  const [error, setError] = useState('');
  const ids = new Set(state.accountIds.map(digits));
  const chosen = reportsAccounts.filter(item => ids.has(digits(item.external_id)));
  const known = (data.campaigns || []).filter(item => chosen.some(account => account.id === item.account_id));
  useEffect(() => {loadUnlinkedGoogleCampaigns().then(rows => setUnlinked(rows.filter(row => chosen.some(account => account.id === row.account_id)))).catch(() => {});}, []);
  useEffect(() => {if (!manual.accountId && chosen[0]) setManual(current => ({...current, accountId: String(chosen[0].id)}));}, [chosen.length]);
  const run = async action => {setError(''); try {await action();} catch (failure) {setError(failure.message || 'Não foi possível cadastrar.');}};
  const addFromGoogle = row => run(async () => {
    const result = await createFromGoogle(save, row, false);
    setCreated(list => [...list, {id: result.campaign?.id ?? `g${row.campaign_external_id}`, name: row.campaign_name || `Campanha ${row.campaign_external_id}`, externalId: row.campaign_external_id}]);
    setUnlinked(rows => rows.filter(item => item !== row));
  });
  const addManual = () => run(async () => {
    const account = chosen.find(item => String(item.id) === manual.accountId);
    const result = await save('/campaigns', {account_id: account.id, name: manual.name.trim(), external_id: manual.externalId.trim(), customer_id: account.customer_id || null}, false);
    setCreated(list => [...list, {id: result.campaign?.id ?? `m${manual.externalId}`, name: manual.name.trim(), externalId: manual.externalId.trim()}]);
    setManual(current => ({...current, name: '', externalId: ''}));
  });
  const ready = manual.accountId && manual.name.trim() && manual.externalId.trim();
  return <div className="rw__fields">
    {unlinked.length > 0 && <div className="flex flex-col gap-2">
      <p className="text-sm font-medium text-secondary">Já enviadas pelo script, sem cadastro</p>
      {unlinked.map(row => <div key={`${row.account_id}:${row.campaign_external_id}`} className="flex items-center gap-3 rounded-lg px-4 py-3 ring-1 ring-secondary ring-inset">
        <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-primary">{row.campaign_name || `Campanha ${row.campaign_external_id}`}</span><span className="font-mono text-xs text-tertiary">ID {row.campaign_external_id}</span></span>
        <Button size="sm" color="secondary" isDisabled={busy} onPress={() => addFromGoogle(row)}>Cadastrar</Button>
      </div>)}
    </div>}
    {(known.length > 0 || created.length > 0) && <div className="flex flex-col gap-2">
      <p className="text-sm font-medium text-secondary">Campanhas no Reports</p>
      <ul className="flex flex-col gap-1.5">{[...known.map(item => ({id: item.id, name: item.name, externalId: item.external_id})), ...created].map(item => <li key={item.id} className="flex items-center gap-2 text-sm text-secondary">
        <BadgeWithDot type="pill-color" size="sm" color="success">{item.name}</BadgeWithDot>{item.externalId && <span className="font-mono text-xs text-tertiary">{item.externalId}</span>}</li>)}</ul>
    </div>}
    <div className="flex flex-col gap-3 rounded-xl p-4 ring-1 ring-secondary ring-inset">
      <p className="text-sm font-semibold text-primary">Cadastrar pelo ID</p>
      {chosen.length > 1 && <ReportsNativeSelect label="Conta" value={manual.accountId} onChange={event => setManual({...manual, accountId: event.target.value})}>
        {chosen.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</ReportsNativeSelect>}
      <ReportsFieldInput label="Nome da campanha" maxLength={240} value={manual.name} onChange={event => setManual({...manual, name: event.target.value})} placeholder="Como aparece no Google Ads"/>
      <ReportsFieldInput label="ID da campanha" maxLength={160} className="font-mono" value={manual.externalId} onChange={event => setManual({...manual, externalId: event.target.value})} placeholder="Ex.: 1234567890" hint="Está na coluna ID da campanha, no Google Ads."/>
      <Button type="button" size="md" color="secondary" isDisabled={!ready || busy} onPress={addManual}>Cadastrar campanha</Button>
    </div>
    {error && <p role="alert" className="text-sm text-error-primary">{error}</p>}
  </div>;
}

/** Espera o primeiro envio das chaves geradas aqui: consulta de tempos em tempos e avisa quando chegar. */
function Waiting({keyIds, onReceived}) {
  const [received, setReceived] = useState(false);
  useEffect(() => {
    let live = true;
    const check = () => json('/connect/api/v2/reports/ingest-keys').then(value => {
      const hit = (value.keys || []).some(item => keyIds.includes(item.id) && item.last_used_at);
      if (live && hit) {setReceived(true); onReceived?.();}
    }).catch(() => {});
    check();
    const timer = setInterval(() => {if (!received) check();}, 6000);
    return () => {live = false; clearInterval(timer);};
  }, [keyIds.join(',')]);
  return <div className="rw__fields">
    <div className="flex items-start gap-3 rounded-xl p-4 ring-1 ring-secondary ring-inset" role="status" aria-live="polite">
      <BadgeWithDot type="pill-color" size="md" color={received ? 'success' : 'warning'}>{received ? 'Dados recebidos' : 'Aguardando primeiro envio'}</BadgeWithDot>
      <p className="text-sm text-tertiary">{received ? 'O script já enviou os primeiros dados. Veja o resultado em Mídia.' : 'No Google Ads, abra o script e clique em Executar para não esperar o agendamento.'}</p>
    </div>
    <ol className="flex flex-col gap-1 pl-5 text-sm text-secondary" style={{listStyleType: 'decimal'}}>
      <li>Em Ferramentas › Scripts, cole o código e autorize o acesso.</li>
      <li>Programe a execução (Leitura: diariamente; Ações: de hora em hora).</li>
      <li>Clique em Executar uma vez para o primeiro envio.</li>
    </ol>
  </div>;
}

/**
 * "Conectar o Google Ads": conta ou MCC, scripts com a chave, campanhas e a espera pelo primeiro envio.
 * Reaproveita a geração de chaves da tela Conexões e chaves (googleAdsScripts.jsx).
 */
export function ConnectGoogleAdsWizard({data, save, busy, reload, onDone, onClose}) {
  const reportsAccounts = data.accounts.filter(item => item.platform === 'google_ads' && item.status !== 'disabled');
  const accounts = {
    managers: reportsAccounts.filter(item => item.account_kind === 'manager' && validGoogleAdsAccountId(item.external_id)),
    advertisers: reportsAccounts.filter(item => item.account_kind === 'advertiser' && validGoogleAdsAccountId(item.external_id)),
  };
  const withKids = accounts.managers.filter(manager => accounts.advertisers.some(item => String(item.parent_account_id || '') === String(manager.id)));
  const [state, setState] = useState(() => ({accounts, managerId: !accounts.advertisers.some(item => !item.parent_account_id) && withKids.length === 1 ? String(withKids[0].id) : '', accountIds: [],
    label: 'Google Ads · monitoramento', withActions: true, limits: {max_budget_change_pct: '30', max_cpc_change_pct: '30'}, scripts: []}));
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [created, setCreated] = useState([]);
  const set = patch => setState(current => ({...current, ...patch}));
  const manager = state.managerId ? accounts.managers.find(item => String(item.id) === state.managerId) : null;
  const sourceReady = state.accountIds.length > 0 && state.label.trim();
  const reason = sourceReady ? '' : 'Volte e escolha a conta e o nome da instalação.';

  const generate = async () => {
    setGenerating(true); setError('');
    try {set({scripts: await generateGoogleScripts({save, withActions: state.withActions, label: state.label.trim(), managerExternalId: manager?.external_id || '', accountIds: state.accountIds, limits: state.limits})});}
    catch (failure) {setError(failure.message || 'Não foi possível gerar os scripts.');}
    finally {setGenerating(false);}
  };
  const keyIds = state.scripts.map(item => item.keyId).filter(Boolean);
  const finish = async () => {await reload(); await onDone?.(keyIds.length > 0); onClose();};

  const renderStep = index => index === 0 ? <Source data={data} state={state} set={set} locked={state.scripts.length > 0}/>
    : index === 1 ? <Scripts state={state} set={set} generate={generate} busy={generating} reason={reason}/>
    : index === 2 ? <Campaigns data={data} state={state} save={save} reportsAccounts={reportsAccounts} created={created} setCreated={setCreated} busy={busy}/>
    : <Waiting keyIds={keyIds}/>;
  const canContinue = index => index === 0 ? Boolean(sourceReady) : index === 1 ? state.scripts.length > 0 : true;

  return <ReportsWizard label="Conectar o Google Ads" steps={STEPS} artBase={ART} renderStep={renderStep} canContinue={canContinue} onFinish={finish} onClose={onClose}
    finishLabel="Concluir" busy={generating || busy} error={error}/>;
}
