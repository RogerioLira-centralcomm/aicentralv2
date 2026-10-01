import React,{useEffect,useState} from 'react';
import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {applyBlueprint,previewBlueprint} from './flowBlueprintApply.js';

const KINDS=[['landing','Landing page (passos dentro da página)'],['institucional','Site institucional'],['multipagina','Site com muitas páginas'],['ecommerce','E-commerce']];
const PURPOSE={lead:'Captação de lead',newsletter:'Newsletter',search:'Busca',login:'Acesso',payment:'Pagamento',other:'Formulário'};

export function FlowConversionProbe({flowId,clientId,csrf,domain,config,onApply,onClose,onPreview}) {
  const savedKind=config?.site_kind||'';
  const [path,setPath]=useState('/');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [result,setResult]=useState(null);
  const [kind,setKind]=useState('');
  const [formIndex,setFormIndex]=useState(0);
  const [confirmSubmit,setConfirmSubmit]=useState(false);
  const [submitted,setSubmitted]=useState(null);

  const call=async body=>{
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),45000);
    try{
      const response=await fetch(`/connect/api/v2/reports/flow/flows/${flowId}/probe?client_id=${clientId}`,{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({...body,client_id:clientId})});
      const value=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(value.description||value.error||'Não foi possível testar esta página.');
      return value;
    }finally{clearTimeout(timer);}
  };
  const analyze=async nextKind=>{
    setBusy(true);setError('');setSubmitted(null);
    try{const value=await call({mode:'analyze',path,site_kind:nextKind||savedKind||undefined});setResult(value);setKind(value.selected_kind);}
    catch(failure){setError(failure.name==='AbortError'?'A página demorou demais para responder.':failure.message);}
    finally{setBusy(false);}
  };
  const submit=async()=>{
    setBusy(true);setError('');
    try{const value=await call({mode:'submit',path,form_index:formIndex,confirm_submit:true,site_kind:kind});setSubmitted(value);if(value.analysis)setResult(value.analysis);setConfirmSubmit(false);}
    catch(failure){setError(failure.message);}
    finally{setBusy(false);}
  };
  const proposal=result?.proposal;
  useEffect(()=>{
    const ids=proposal?.nodes?.map(node=>node.id)||[];
    onPreview?.(ids.length?previewBlueprint(proposal,ids):{nodes:[],edges:[]});
    return()=>onPreview?.({nodes:[],edges:[]});
  },[proposal]);
  const apply=()=>{try{onApply({...applyBlueprint(config,proposal,proposal.nodes.map(node=>node.id)),site_kind:kind});onClose();}catch(failure){setError(failure.message);}};
  const submittable=(result?.forms||[]).filter(form=>form.can_submit);

  return <ReportsPanelShell className="flow-blueprint-panel flow-probe-panel" title="Testar conversão" description={`${domain}${path}`} onClose={onClose}
    footer={proposal&&!proposal.use_catalog&&proposal.nodes.length?<Button color="primary" onClick={apply}>Montar fluxo com este caminho</Button>:null}>
    {error&&<p role="alert">{error}</p>}
    <label>Página inicial do teste<ReportsFieldInput value={path} onChange={event=>setPath(event.target.value)} placeholder="/"/></label>
    <Button color="primary" disabled={busy||!path.startsWith('/')} onClick={()=>analyze()}>{busy&&!submitted?'Analisando…':result?'Analisar de novo':'Analisar página'}</Button>
    <small>A análise lê o HTML da página. Não envia formulários e não captura imagens.</small>
    {result&&<>
      <section className="flow-probe-block"><h3>Tipo de site</h3>
        <ReportsNativeSelect value={kind} onChange={event=>{setKind(event.target.value);analyze(event.target.value);}} aria-label="Tipo de site">{KINDS.map(([id,label])=><option key={id} value={id}>{label}{id===result.site_kind.kind?' · sugerido':''}</option>)}</ReportsNativeSelect>
        <small>{result.site_kind.reasons.join(' ')} Sugestão por regras, confiança {result.site_kind.confidence}.</small></section>
      <section className="flow-probe-block"><h3>Medição</h3>
        <div className="flow-probe-chips">{result.tags.map(tag=><span key={tag.name} className={tag.detected?'is-on':''}>{tag.name}</span>)}</div>
        <small>{result.events.length?`Eventos encontrados: ${result.events.join(', ')}.`:'Nenhum evento de conversão encontrado no código da página.'} {result.limits[0]}</small></section>
      <section className="flow-probe-block"><h3>O que o visitante pode fazer</h3>
        {result.forms.length?result.forms.map(form=><p key={form.index}><b>{PURPOSE[form.purpose]||'Formulário'}</b> · {form.fields.length} campos{form.submit_label?` · “${form.submit_label}”`:''}<br/><small>{form.can_submit?'Pode ser testado.':form.blocked_reason}</small></p>):<p><small>Nenhum formulário nesta página.</small></p>}
        {(result.whatsapp||result.phone)&&<p><small>{result.whatsapp?'Link de WhatsApp. ':''}{result.phone?'Link de telefone.':''}</small></p>}</section>
      {proposal?.warnings?.length>0&&<section className="flow-probe-block is-warning"><h3>Atenção</h3><ul>{proposal.warnings.map(item=><li key={item}>{item}</li>)}</ul></section>}
      {proposal?.use_catalog?<section className="flow-probe-block"><p>{proposal.note}</p></section>:<section className="flow-probe-block"><h3>Caminho proposto</h3><p><small>{proposal.nodes.length} etapas, da origem do tráfego até a conversão, já no mapa como prévia.</small></p></section>}
      {result.submit_available&&submittable.length>0&&<details className="flow-probe-block"><summary>Enviar formulário de teste</summary>
        <p><small>Envia uma vez, com dados fictícios (e-mail @example.invalid), para descobrir se há página de obrigado. Pode gerar um lead falso no CRM do cliente. Máximo de 3 por dia neste fluxo.</small></p>
        <ReportsNativeSelect value={formIndex} onChange={event=>setFormIndex(Number(event.target.value))} aria-label="Formulário a testar">{submittable.map(form=><option key={form.index} value={form.index}>{PURPOSE[form.purpose]} · {form.fields.length} campos</option>)}</ReportsNativeSelect>
        <label className="flow-inspector__checkbox"><input type="checkbox" checked={confirmSubmit} onChange={event=>setConfirmSubmit(event.target.checked)}/> Entendo e autorizo este envio de teste</label>
        <Button disabled={!confirmSubmit||busy} onClick={submit}>{busy?'Enviando…':'Enviar teste'}</Button></details>}
      {submitted&&<section className="flow-probe-block"><h3>Resultado do envio</h3><p>{submitted.outcome.label}{submitted.outcome.path&&submitted.outcome.type!=='no_confirmation_signal'?` (${submitted.outcome.path})`:''}</p></section>}
    </>}
  </ReportsPanelShell>;
}
