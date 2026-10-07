import React, {useRef, useState} from 'react';
import {Check} from '@untitledui/icons';
import {ReportsWizard} from './ReportsWizard.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {FlowPlatformLogo} from './FlowPlatformLogo.jsx';
import {platformName} from './shell/media.jsx';

const ART = '/static/images/reports/illustrations/';
const STEPS = [
  {key: 'cliente', label: 'Cliente', art: 'conta-1-cliente.webp', focus: '42%', title: 'Quem é o cliente?', text: 'O nome aparece nos relatórios, nos filtros e no seletor da barra lateral. Dá para vincular a marca do Workspace.'},
  {key: 'midia', label: 'Conta de mídia', art: 'conta-2-midia.webp', focus: '38%', optional: true, title: 'Em que plataforma ele anuncia?', text: 'Cadastre a conta de anúncios para receber investimento e resultado. Se preferir, adicione depois.'},
  {key: 'revisao', label: 'Revisão', art: 'conta-3-revisao.webp', focus: '48%', title: 'Tudo certo?', text: 'Confira o resumo. Você pode editar tudo depois em Clientes e contas.'},
];
const PLATFORMS = ['google_ads', 'meta_ads', 'microsoft_ads', 'linkedin_ads', 'tiktok_ads', 'other'];
const blank = {name: '', brand: '', platform: '', accountName: '', externalId: ''};

/**
 * "Novo cliente e conta": o cliente (com a marca do Workspace, se houver) e, opcionalmente, a primeira conta de mídia dele.
 * `save`/`send` são os do Reports; `onDone(customerId)` recebe o cliente criado.
 */
export function NewClientWizard({freeBrands = [], save, send, reload, onDone, onClose}) {
  const [form, setForm] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // What already exists after a failed attempt: retrying must finish the job, not create the client again.
  const done = useRef({customerId: null, brand: false, account: false});
  const set = patch => setForm(value => ({...value, ...patch}));
  const chosen = freeBrands.find(item => item.ref === form.brand);
  const name = form.name.trim() || chosen?.name || '';
  const withAccount = Boolean(form.platform);
  const accountReady = !withAccount || (form.accountName.trim() && form.externalId.trim());
  const canContinue = index => index === 0 ? Boolean(name) : index === 1 ? Boolean(accountReady) : Boolean(name && accountReady);

  const finish = async () => {
    setBusy(true); setError('');
    try {
      if (!done.current.customerId) done.current.customerId = (await save('/customers', {name, status: 'active'}, false)).customer?.id;
      const id = done.current.customerId;
      if (chosen && id && !done.current.brand) {await send('/customers/' + id + '/brands', 'POST', {brand_ref: chosen.ref}); done.current.brand = true;}
      if (withAccount && id && !done.current.account) {
        await save('/accounts', {platform: form.platform, account_kind: 'advertiser', name: form.accountName.trim(), external_id: form.externalId.trim(), parent_account_id: null, customer_id: id}, false);
        done.current.account = true;
      }
      await reload();
      await onDone(id);
    } catch (failure) {setError(failure.message || 'Não foi possível criar o cliente.'); setBusy(false);}
  };

  const renderStep = index => {
    if (index === 0) return <div className="rw__fields">
      {freeBrands.length > 0 && <ReportsNativeSelect label="A partir de uma marca do Workspace" value={form.brand} onChange={event => set({brand: event.target.value})}
        hint="O cliente já nasce vinculado à marca; o logo dela aparece no seletor.">
        <option value="">Nenhuma, criar só no Reports</option>
        {freeBrands.map(item => <option key={item.ref} value={item.ref}>{item.name}</option>)}
      </ReportsNativeSelect>}
      <ReportsFieldInput label="Nome do cliente ou anunciante" required maxLength={200} value={form.name} onChange={event => set({name: event.target.value})} placeholder={chosen?.name || 'Ex.: Loja Verão'}/>
    </div>;
    if (index === 1) return <div className="rw__fields">
      <div className="rw__options" role="radiogroup" aria-label="Plataforma">
        {PLATFORMS.map(id => <button key={id} type="button" role="radio" aria-checked={form.platform === id} className={`rw__option${form.platform === id ? ' is-chosen' : ''}`} onClick={() => set({platform: form.platform === id ? '' : id})}>
          <span className="rw__option-icon"><FlowPlatformLogo platform={id}/></span>
          <span style={{flex: 1}}><strong>{id === 'other' ? 'Outra plataforma' : platformName(id)}</strong></span>
          {form.platform === id && <Check size={18} aria-hidden="true"/>}
        </button>)}
      </div>
      {withAccount && <>
        <ReportsFieldInput label="Nome da conta" required maxLength={240} value={form.accountName} onChange={event => set({accountName: event.target.value})} placeholder="Nome exibido na plataforma"/>
        <ReportsFieldInput label="ID da conta" required maxLength={160} className="font-mono" value={form.externalId} onChange={event => set({externalId: event.target.value})}
          placeholder={form.platform === 'google_ads' ? '123-456-7890' : 'ID fornecido pela plataforma'} hint={form.platform === 'google_ads' ? '10 dígitos, com ou sem hífens.' : 'Copie o identificador exibido na plataforma.'}/>
      </>}
    </div>;
    return <dl className="rw__summary">
      <div><dt>Cliente</dt><dd>{name}</dd></div>
      {chosen && <div><dt>Marca</dt><dd>{chosen.name}</dd></div>}
      <div><dt>Conta de mídia</dt><dd>{withAccount ? `${form.accountName.trim()} · ${form.platform === 'other' ? 'Outra' : platformName(form.platform)}` : 'Nenhuma por enquanto'}</dd></div>
    </dl>;
  };

  return <ReportsWizard label="Novo cliente e conta" steps={STEPS} artBase={ART} renderStep={renderStep} canContinue={canContinue} onFinish={finish} onClose={onClose}
    finishLabel="Criar cliente" busy={busy} error={error}/>;
}
