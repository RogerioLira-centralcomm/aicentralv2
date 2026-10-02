import React,{useEffect,useState} from 'react';
import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {applyBlueprint,previewBlueprint} from './flowBlueprintApply.js';

const KINDS=[['landing','Landing page (passos dentro da página)'],['institucional','Site institucional'],['multipagina','Site com muitas páginas'],['ecommerce','E-commerce']];
const PURPOSE={lead:'Captação de lead',newsletter:'Newsletter',search:'Busca',login:'Acesso',payment:'Pagamento',other:'Formulário'};

const OUTCOME={
  redirect_confirmation:['ok','Conversão confirmada','O envio levou a uma página de confirmação.'],
  in_page_message:['ok','Conversão confirmada','O site mostrou uma mensagem de sucesso na própria página.'],
  redirect:['warn','Atenção: o envio redirecionou, mas sem sinal de confirmação','A página mudou, porém o endereço e o texto não indicam que o contato foi recebido. Confira se é uma página de obrigado.'],
  no_confirmation_signal:['error','Erro de conversão: nada aconteceu depois do envio','Não houve redirecionamento nem mensagem de sucesso. O visitante não sabe se o contato foi enviado e a conversão não será medida.'],
};
function ProbeOutcome({submitted}) {
  const outcome=submitted.outcome||{};
  const [tone,title,detail]=OUTCOME[outcome.type]||['warn',outcome.label||'Resultado do envio',''];
  const pixels=submitted.fired_on_submit||[];
  return <section className={`flow-probe-callout is-${tone}`} role={tone==='error'?'alert':'status'}>
    <h3>{title}</h3><p>{detail}{outcome.path&&['redirect','redirect_confirmation'].includes(outcome.type)?` Endereço: ${outcome.path}.`:''}</p>
    <p>{pixels.length?`Pixels disparados no envio: ${pixels.join(', ')}.`:'Nenhum pixel disparou no envio: a conversão não chega às plataformas de mídia.'}</p>
    {submitted.filled?.length>0&&<details><summary>Dados fictícios enviados</summary><ul>{submitted.filled.map(item=><li key={item.label}><b>{item.label}:</b> {String(item.value)}</li>)}</ul></details>}
  </section>;
}

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
  const [render,setRender]=useState(false);

  const call=async body=>{
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),45000);
    try{
      const response=await fetch(`/connect/api/v2/reports/flow/flows/${flowId}/probe`,{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({...body})});
      const value=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(value.description||value.error||'Não foi possível testar esta página.');
      return value;
    }finally{clearTimeout(timer);}
  };
  const analyze=async nextKind=>{
    setBusy(true);setError('');setSubmitted(null);
    try{const value=await call({mode:'analyze',path,render:render||undefined,site_kind:nextKind||savedKind||undefined});setResult(value);setKind(value.selected_kind);}
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
    {result?.submit_available&&<label className="flow-inspector__checkbox"><input type="checkbox" checked={render} onChange={event=>setRender(event.target.checked)}/> Abrir com scripts para ver quais pixels disparam</label>}
    <small>{render?'Abre a página num navegador de testes, sem capturar imagens e sem enviar formulários.':'A análise lê o HTML da página. Não envia formulários e não captura imagens.'}</small>
    {result&&<>
      <section className="flow-probe-block"><h3>Tipo de site</h3>
        <ReportsNativeSelect value={kind} onChange={event=>{setKind(event.target.value);analyze(event.target.value);}} aria-label="Tipo de site">{KINDS.map(([id,label])=><option key={id} value={id}>{label}{id===result.site_kind.kind?' · sugerido':''}</option>)}</ReportsNativeSelect>
        <small>{result.site_kind.reasons.join(' ')} Sugestão automática, confiança {result.site_kind.confidence}.</small></section>
      <section className="flow-probe-block"><h3>Medição</h3>
        <div className="flow-probe-chips">{result.tags.filter(tag=>tag.detected).map(tag=><span key={tag.name} className="is-on">✓ {tag.name}</span>)}{!result.tags.some(tag=>tag.detected)&&<small>Nenhuma tag de medição encontrada.</small>}</div>
        {result.tags.some(tag=>!tag.detected)&&<small>Não encontradas: {result.tags.filter(tag=>!tag.detected).map(tag=>tag.name).join(', ')}.</small>}
        {result.fired_tags&&<small>{result.fired_tags.length?`Dispararam ao abrir: ${result.fired_tags.join(', ')}.`:'Nenhum pixel disparou ao abrir a página.'}</small>}
        <small>{result.events.length?`Eventos encontrados: ${result.events.join(', ')}.`:'Nenhum evento de conversão no código da página.'}</small>
        {result.limits?.[0]&&<small className="flow-probe-muted">{result.limits[0]}</small>}</section>
      <section className="flow-probe-block"><h3>O que o visitante pode fazer</h3>
        {result.forms.length?result.forms.map(form=><p key={form.index} className="flow-probe-item"><b>{PURPOSE[form.purpose]||'Formulário'}</b><span>{form.fields.length} campos{form.submit_label?` · botão “${form.submit_label}”`:''}</span><small>{form.can_submit?'Pode ser testado com dados fictícios.':form.blocked_reason}</small></p>):<small>Nenhum formulário nesta página.</small>}
        {(result.whatsapp||result.phone)&&<small>{[result.whatsapp&&'Link de WhatsApp',result.phone&&'Link de telefone'].filter(Boolean).join(' · ')}</small>}</section>
      {proposal?.warnings?.length>0&&<section className="flow-probe-block is-warning"><h3>Atenção</h3><ul>{proposal.warnings.map(item=><li key={item}>{item}</li>)}</ul></section>}
      {submittable.length>0&&<section className="flow-probe-block"><h3>Testar envio do formulário</h3>
        <small>O Cadu preenche o formulário com dados fictícios (e-mail @example.invalid), envia uma vez e observa se abre uma página de obrigado ou mostra uma mensagem de sucesso. Se nada acontecer, aponta erro de conversão. Pode gerar um lead falso no CRM do cliente; limite de 3 por dia neste fluxo.</small>
        {submittable.length>1&&<ReportsNativeSelect value={formIndex} onChange={event=>setFormIndex(Number(event.target.value))} aria-label="Formulário a testar">{submittable.map(form=><option key={form.index} value={form.index}>{PURPOSE[form.purpose]} · {form.fields.length} campos</option>)}</ReportsNativeSelect>}
        {result.submit_available
          ?<><label className="flow-inspector__checkbox"><input type="checkbox" checked={confirmSubmit} onChange={event=>setConfirmSubmit(event.target.checked)}/> Autorizo este envio de teste</label>
            <Button color="primary" disabled={!confirmSubmit||busy} onClick={submit}>{busy?'Enviando e observando…':'Enviar teste'}</Button></>
          :<p className="flow-probe-callout is-warning" role="status">O navegador de testes ainda não está instalado neste servidor, então o envio não pode ser feito agora. A análise acima continua válida.</p>}</section>}
      {submitted&&<ProbeOutcome submitted={submitted}/>}
      {proposal?.use_catalog&&<section className="flow-probe-block"><h3>Próximo passo</h3><small>{proposal.note}</small></section>}
      {proposal&&!proposal.use_catalog&&<section className="flow-probe-block"><h3>Caminho proposto</h3><small>{proposal.nodes.length} etapas, da origem do tráfego até a conversão, já no mapa como prévia.</small></section>}
    </>}
  </ReportsPanelShell>;
}
