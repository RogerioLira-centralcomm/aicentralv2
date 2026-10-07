import React, {useEffect, useState} from 'react';
import {Check, Copy01, Download01} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {ReportsWizard} from './ReportsWizard.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {buildRule} from './SuperTagPage.jsx';
import {flowEditorUrl, json} from './reportsCommon.jsx';
import {customerParam} from './shell/customerScope.js';

const API = '/connect/api/v2/reports';
const ART = '/static/images/reports/illustrations/';
const STEPS = [
  {key: 'site', label: 'Site', art: 'site-1-dominio.webp', focus: '40%', title: 'Qual é o site?', text: 'Conferimos se o endereço responde antes de gerar o código. A coleta começa na primeira visita.'},
  {key: 'supertag', label: 'Super Tag', art: 'site-2-supertag.webp', focus: '40%', title: 'Instale a Super Tag', text: 'Cole o código no <head> do site (ou numa tag HTML do Google Tag Manager, não nos dois). Dá para instalar depois.'},
  {key: 'fluxo', label: 'Fluxo', art: 'site-3-fluxo.webp', focus: '30%', title: 'Monte o caminho do visitante', text: 'O fluxo liga anúncio, página, formulário e conversão. Aqui você dá o nome; os passos se desenham no editor.'},
  {key: 'conversao', label: 'Conversão', art: 'site-4-conversao.webp', focus: '45%', title: 'O que conta como resultado?', text: 'Escolha o momento que vale como conversão neste site. Dá para mudar depois em Super Tag › Conversões.'},
  {key: 'revisao', label: 'Revisão', art: 'site-5-revisao.webp', focus: '55%', title: 'Publicar e começar a medir', text: 'Confira o resumo. Ao concluir, abrimos o editor do fluxo para desenhar os passos.'},
];
const CONVERSIONS = [
  ['auto', 'Página de obrigado (automático)', 'Páginas com obrigad, thank, sucesso ou confirmac no endereço. Não cria regra.'],
  ['path:exact', 'Uma página específica', 'A visita a um endereço exato, como /obrigado.'],
  ['valid_form', 'Formulário enviado', 'Qualquer formulário enviado sem erro.'],
  ['event_name', 'Evento do site', 'Um evento próprio enviado com CaduSuperTag.event().'],
];
const FIELD = {'path:exact': ['Endereço da página', '/obrigado'], event_name: ['Nome do evento', 'lead_enviado']};

/** Código da Super Tag do site criado, com cópia, download e verificação de instalação. */
function Install({site, call}) {
  const [full, setFull] = useState(null);
  const [method, setMethod] = useState('direct');
  const [copied, setCopied] = useState(false);
  const [state, setState] = useState(null);
  const [checking, setChecking] = useState(false);
  useEffect(() => {json(`${API}/supertag/sites`).then(body => setFull((body.sites || []).find(item => item.id === site.id) || site)).catch(() => setFull(site));}, [site.id]);
  const code = (method === 'gtm' && full?.snippet_gtm) || full?.snippet || '';
  const copy = async () => {try {await navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 2000);} catch {setCopied(false);}};
  const download = () => {
    const url = URL.createObjectURL(new Blob([code], {type: 'text/plain;charset=utf-8'}));
    const link = Object.assign(document.createElement('a'), {href: url, download: `cadu-supertag-${method === 'gtm' ? 'gtm-' : ''}${site.allowed_host}.txt`});
    link.click(); URL.revokeObjectURL(url);
  };
  const verify = async () => {
    setChecking(true);
    try {setState(await call(`/supertag/sites/${site.id}/verify-install`, 'GET'));} catch (failure) {setState({error: failure.message});} finally {setChecking(false);}
  };
  return <div className="rw__fields">
    <div className="rw__options" role="radiogroup" aria-label="Como instalar" style={{gridTemplateColumns: '1fr 1fr'}}>
      {[['direct', 'No código do site'], ['gtm', 'Google Tag Manager']].map(([id, text]) => <button key={id} type="button" role="radio" aria-checked={method === id} className={`rw__option${method === id ? ' is-chosen' : ''}`} onClick={() => setMethod(id)}><strong>{text}</strong></button>)}
    </div>
    <pre aria-label="Código da Super Tag" className="max-h-40 overflow-auto rounded-lg bg-secondary p-4 font-mono text-xs leading-5 whitespace-pre-wrap break-all text-secondary ring-1 ring-secondary ring-inset">{code || 'Gerando o código…'}</pre>
    <div className="flex flex-wrap gap-2">
      <Button type="button" size="md" color="primary" iconLeading={copied ? Check : Copy01} isDisabled={!code} onPress={copy}>{copied ? 'Copiado' : 'Copiar código'}</Button>
      <Button type="button" size="md" color="secondary" iconLeading={Download01} isDisabled={!code} onPress={download}>Baixar .txt</Button>
      <Button type="button" size="md" color="secondary" isDisabled={checking} isLoading={checking} onPress={verify}>Verificar instalação</Button>
    </div>
    {state && <p role="status" className="text-sm text-secondary">
      {state.error ? <BadgeWithDot type="pill-color" size="sm" color="error">{state.error}</BadgeWithDot>
        : !state.reachable ? <BadgeWithDot type="pill-color" size="sm" color="warning">Não conseguimos abrir o site para conferir.</BadgeWithDot>
        : state.tag_in_html ? <BadgeWithDot type="pill-color" size="sm" color="success">Super Tag encontrada no site</BadgeWithDot>
        : <BadgeWithDot type="pill-color" size="sm" color="warning">{state.gtm_detected ? 'Não está no HTML, mas o site usa Google Tag Manager: publique o contêiner e a coleta aparece com as primeiras visitas.' : 'Ainda não encontramos a Super Tag. Publique a instalação e verifique de novo.'}</BadgeWithDot>}</p>}
  </div>;
}

/**
 * "Adicionar site, fluxo e Super Tag": o domínio, o código a instalar, o fluxo e o que conta como conversão.
 * O site é criado ao sair do primeiro passo; o fluxo e a regra de conversão só no fim, e então abre o editor do fluxo.
 */
export function NewSiteWizard({data, onClose}) {
  const call = (path, method = 'POST', payload) => json(`${API}${path}`, method === 'GET' ? undefined
    : {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.csrf}, body: JSON.stringify({...payload})});
  const customers = (data.customers || []).filter(item => item.status !== 'archived');
  const [form, setForm] = useState(() => ({url: '', label: '', customerId: customerParam(), flowName: '', campaignId: '', conversion: 'auto', conversionValue: ''}));
  const [check, setCheck] = useState(null);
  const [checking, setChecking] = useState(false);
  const [site, setSite] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = patch => setForm(value => ({...value, ...patch}));
  const trimmed = form.url.trim();
  const verified = Boolean(check && !check.error && check.verifiedUrl === trimmed);
  const campaigns = (data.campaigns || []).filter(item => !form.customerId || String(item.customer_id || '') === form.customerId);
  const flowName = form.flowName.trim() || `Jornada ${site?.allowed_host || check?.host || ''}`.trim();
  const rule = form.conversion === 'auto' ? null : buildRule(form.conversion, form.conversionValue, '');

  const verify = async () => {
    if (!trimmed) return;
    setChecking(true); setCheck(null);
    try {
      const result = await json(`${API}/supertag/site-check?url=${encodeURIComponent(trimmed.includes('://') ? trimmed : `https://${trimmed}`)}`);
      setCheck({...result, verifiedUrl: trimmed});
      if (result.title && !form.label) set({label: result.title.slice(0, 120)});
    } catch (failure) {setCheck({error: failure.message});} finally {setChecking(false);}
  };
  const canContinue = index => index === 0 ? verified && Boolean((form.label || check?.host || '').trim())
    : index === 3 ? !rule || !rule.error : true;
  // The site exists from the first step on; going back and forward again must not create it twice.
  const onNext = async index => {
    if (index !== 0 || site) return;
    const created = await call('/supertag/sites', 'POST', {label: (form.label || check.host).trim(), allowed_host: check.host, ...(form.customerId ? {customer_id: form.customerId} : {})});
    setSite(created.site);
  };
  const finish = async () => {
    setBusy(true); setError('');
    try {
      if (rule && !rule.error) await call(`/supertag/sites/${site.id}`, 'PATCH', {conversion_rules: [rule.rule]});
      const created = await call('/flow/flows', 'POST', {name: flowName, allowed_host: site.allowed_host, customer_id: form.customerId || null, campaign_id: form.campaignId || null, config: {nodes: [], edges: []}});
      location.assign(flowEditorUrl(created.flow.id));
    } catch (failure) {setError(failure.message || 'Não foi possível concluir.'); setBusy(false);}
  };

  const renderStep = index => {
    if (index === 0) return <div className="rw__fields">
      <div className="flex items-end gap-3">
        <div className="flex-1"><ReportsFieldInput label="Endereço do site" required inputMode="url" autoCapitalize="none" value={form.url} disabled={Boolean(site)} placeholder="www.exemplo.com.br" onChange={event => {setCheck(null); set({url: event.target.value});}}/></div>
        <Button type="button" size="md" color="secondary" isDisabled={!trimmed || checking || Boolean(site)} isLoading={checking} onPress={verify}>Verificar</Button>
      </div>
      {check && (check.error ? <p role="alert" className="text-sm text-error-primary">Não foi possível acessar o site: {check.error}</p>
        : <div className="flex items-center gap-3 rounded-lg p-4 ring-1 ring-secondary ring-inset">
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-primary">{check.title || check.host || 'Site encontrado'}</p><p className="text-xs text-tertiary">{check.host}{check.status ? ` · HTTP ${check.status}` : ''}</p></div>
          <BadgeWithDot type="pill-color" size="sm" color="success">Respondeu</BadgeWithDot></div>)}
      <ReportsFieldInput label="Nome desta instalação" required maxLength={120} disabled={Boolean(site)} value={form.label} onChange={event => set({label: event.target.value})} placeholder={check?.title || 'Preenchido ao verificar'}/>
      <ReportsNativeSelect label="Cliente / anunciante" disabled={Boolean(site)} value={form.customerId} onChange={event => set({customerId: event.target.value, campaignId: ''})}>
        <option value="">Sem cliente</option>{customers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </ReportsNativeSelect>
    </div>;
    if (index === 1) return site ? <Install site={site} call={call}/> : null;
    if (index === 2) return <div className="rw__fields">
      <ReportsFieldInput label="Nome do fluxo" maxLength={120} value={form.flowName} onChange={event => set({flowName: event.target.value})} placeholder={flowName}/>
      <ReportsNativeSelect label="Campanha (opcional)" value={form.campaignId} onChange={event => set({campaignId: event.target.value})}>
        <option value="">Sem campanha</option>{campaigns.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </ReportsNativeSelect>
    </div>;
    if (index === 3) return <div className="rw__fields">
      <div className="rw__options" role="radiogroup" aria-label="Conversão">
        {CONVERSIONS.map(([id, title, text]) => <button key={id} type="button" role="radio" aria-checked={form.conversion === id} className={`rw__option${form.conversion === id ? ' is-chosen' : ''}`} onClick={() => set({conversion: id, conversionValue: ''})}>
          <span style={{flex: 1}}><strong>{title}</strong><small>{text}</small></span>{form.conversion === id && <Check size={18} aria-hidden="true"/>}</button>)}
      </div>
      {FIELD[form.conversion] && <ReportsFieldInput label={FIELD[form.conversion][0]} value={form.conversionValue} onChange={event => set({conversionValue: event.target.value})} placeholder={FIELD[form.conversion][1]}
/>}
      {rule?.error && form.conversionValue && <p role="alert" className="text-sm text-error-primary">{rule.error}</p>}
    </div>;
    return <dl className="rw__summary">
      <div><dt>Site</dt><dd>{site?.allowed_host}</dd></div>
      <div><dt>Super Tag</dt><dd>Instalação criada</dd></div>
      <div><dt>Fluxo</dt><dd>{flowName}</dd></div>
      <div><dt>Conversão</dt><dd>{CONVERSIONS.find(item => item[0] === form.conversion)[1]}{FIELD[form.conversion] && form.conversionValue ? ` · ${form.conversionValue}` : ''}</dd></div>
    </dl>;
  };

  return <ReportsWizard label="Site, fluxo e Super Tag" steps={STEPS} artBase={ART} renderStep={renderStep} canContinue={index => index === 3 && FIELD[form.conversion] ? Boolean(rule && !rule.error) : canContinue(index)}
    onNext={onNext} onFinish={finish} onClose={onClose} finishLabel="Criar fluxo e abrir o editor" busy={busy} error={error}/>;
}
