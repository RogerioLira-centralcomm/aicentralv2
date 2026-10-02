import React,{useEffect,useMemo,useState} from 'react';
import {Dialog,Modal,ModalOverlay} from 'react-aria-components';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';
import {DateField} from './ReportsBlocks.jsx';
import {json} from './reportsCommon.jsx';
import {agentBriefing,briefingContext,suggestedSpec,teamBriefing} from './flowBriefing.js';

const FORMATS=[['team','Para o time de criação'],['agent','Para outro agente']];
const FIELDS=[['goal','Objetivo','textarea'],['headline','Título ou mensagem principal','text'],['content','Conteúdo e blocos','textarea'],['cta','Chamada para ação','text'],['references','Referências','textarea'],['notes','Observações','textarea']];

/** Brief for a page that will be built: written from what the board already knows, ready to hand to a team or another agent. */
export function FlowBriefingDialog({open,node,config,clientId,csrf,flowId,clientName,host,flowName,readOnly,onSave,onClose}) {
  const ctx=useMemo(()=>node?briefingContext(node,config,{clientName,host,flowName}):null,[node,config,clientName,host,flowName]);
  const [spec,setSpec]=useState({});
  const [format,setFormat]=useState('team');
  const [busy,setBusy]=useState(false);
  const [note,setNote]=useState('');
  const [copied,setCopied]=useState('');
  useEffect(()=>{if(open&&node&&ctx){setSpec(suggestedSpec(node,ctx));setNote('');setCopied('');setFormat('team');}},[open,node?.id]);
  if(!open||!node||!ctx)return null;
  const text=(format==='team'?teamBriefing:agentBriefing)(ctx,spec);
  const set=(field,value)=>setSpec(current=>({...current,[field]:value}));
  const generate=async()=>{
    setBusy(true);setNote('');
    try{
      const result=await json(`/connect/api/v2/reports/flow/flows/${flowId}/pages/briefing`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({client_id:clientId,context:{
        brand:ctx.brand,host:ctx.host,flow_name:ctx.flowName,title:ctx.title,path:ctx.path,type:ctx.type,stage:ctx.stage,from:ctx.from,to:ctx.to,conversions:ctx.conversions,spec}})});
      setSpec(current=>({...current,...result.spec}));setNote('Sugestão da IA aplicada. Revise antes de enviar.');
    }catch(failure){setNote(failure.message||'A IA não respondeu. O briefing base continua disponível.');}
    finally{setBusy(false);}
  };
  const copy=async which=>{
    const value=which==='team'?teamBriefing(ctx,spec):agentBriefing(ctx,spec);
    try{await navigator.clipboard.writeText(value);setCopied(which);setTimeout(()=>setCopied(''),1800);}catch{setNote('Não foi possível copiar. Selecione o texto e copie manualmente.');}
  };
  return <ModalOverlay className="cadu-ds-overlay cadu-ds-overlay--center" isOpen={open} onOpenChange={value=>{if(!value&&!busy)onClose();}} isDismissable={!busy}>
    <Modal className="cadu-ds-confirm flow-briefing-modal"><Dialog aria-label="Briefing da página" className="cadu-ds-confirm__dialog flow-briefing">
      <header className="flow-briefing__head"><div><h2>Briefing · {node.title||'Página'}</h2><p>{[ctx.brand,ctx.host,ctx.path].filter(Boolean).join(' · ')||'Sem marca ou site associado'}</p></div>
        {!readOnly&&<Button color="secondary" size="sm" onPress={generate} isDisabled={busy} isLoading={busy}>Gerar com IA</Button>}</header>
      {note&&<p className="flow-briefing__note" role="status">{note}</p>}
      <div className="flow-briefing__body">
        <section className="flow-briefing__fields" aria-label="Informações do briefing">
          {FIELDS.map(([field,label,kind])=><label key={field}>{label}{kind==='textarea'
            ?<ReportsTextArea disabled={readOnly} rows={field==='content'?5:2} value={spec[field]||''} onChange={event=>set(field,event.target.value)}/>
            :<ReportsFieldInput disabled={readOnly} value={spec[field]||''} onChange={event=>set(field,event.target.value)}/>}</label>)}
          <div className="flow-briefing__pair"><label>Responsável<ReportsFieldInput disabled={readOnly} maxLength="120" value={spec.owner||''} onChange={event=>set('owner',event.target.value)}/></label>
            <DateField label="Prazo" disabled={readOnly} value={spec.due_date||''} onChange={event=>set('due_date',event.target.value)}/></div>
        </section>
        <section className="flow-briefing__preview" aria-label="Texto do briefing">
          <div className="flow-briefing__tabs" role="tablist">{FORMATS.map(([id,label])=><button key={id} type="button" role="tab" aria-selected={format===id} className={format===id?'is-active':''} onClick={()=>setFormat(id)}>{label}</button>)}</div>
          <pre tabIndex={0}>{text}</pre>
        </section>
      </div>
      <div className="cadu-ds-confirm__actions flow-briefing__actions">
        <Button color="secondary" onPress={onClose} isDisabled={busy}>Fechar</Button>
        {!readOnly&&<Button color="secondary" onPress={()=>{onSave(spec);onClose();}} isDisabled={busy}>Salvar no passo</Button>}
        {FORMATS.map(([id,label])=><Button key={id} color={format===id?'primary':'secondary'} onPress={()=>copy(id)}>{copied===id?'Copiado ✓':`Copiar ${id==='team'?'para o time':'para o agente'}`}</Button>)}
      </div>
    </Dialog></Modal>
  </ModalOverlay>;
}
