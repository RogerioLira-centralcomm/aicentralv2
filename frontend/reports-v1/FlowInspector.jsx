import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {Switch} from 'react-aria-components';
import {FLOW_STAGES,editableStage} from './flowStages.js';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import React,{useState} from 'react';
import {eventMatchesNode} from './flowEventIdentity.js';
import {Button as UntitledButton} from '../cadu-design-system/untitled-kit/button.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';
import {flowBlockFor} from './flowBlockRegistry.js';
import {SPEC_FIELDS,hasRealPath,isPlanned} from './flowLifecycle.js';
import {FlowPagePicker} from './FlowPagePicker.jsx';
import {SEGMENT_KINDS} from './flowMedia.js';
import {FlowSourceTracking} from './FlowSourceTracking.jsx';

// How the Super Tag counts this step; tells the person whether the site needs any change.
export function measurementHint(node){
  if(node.type==='note')return 'Anotação do plano: não é medida e não entra na jornada.';
  if(['page','form','event','conversion','whatsapp','error'].includes(node.type)&&['planned','in_production'].includes(node.status))return 'Planejado: entra na medição quando o endereço real estiver definido e a Situação for Pronto ou No ar.';
  if(node.type==='source')return 'Contado pela origem da sessão (utm_source ou site de referência).';
  if(node.type==='form')return 'Envio do formulário nesta URL, capturado automaticamente.';
  if(node.type==='whatsapp')return 'Clique em link do WhatsApp nesta URL, capturado automaticamente.';
  if(node.type==='event'&&node.event_name==='scroll_depth')return 'Rolagem além de 50% da página, capturada automaticamente.';
  if(['event','conversion'].includes(node.type)&&node.event_name)return `O site precisa chamar CaduSuperTag.${node.type==='conversion'?'trackConversion':'trackEvent'}('${node.event_name}').`;
  if(['page','conversion','error'].includes(node.type))return 'Visita a esta URL, capturada automaticamente.';
  return 'Nó visual, sem medição.';
}

export function FlowInspector({sitePages,onSplitSegment,node,nodes=[],groups=[],activity=[],journeyMetric=null,integrationsUrl='',readOnly,onChange,onConnect,onCreateGroup,onRemove,onClose,onGestureStart,onGestureEnd}) {
  if(!node)return null;
  const block=flowBlockFor(node);
  const planned=isPlanned(node);
  const spec=node.spec||{};
  const observed=activity.find(item=>eventMatchesNode(item,node));
  const pageLike=block.trackable&&node.type!=='note';
  const chip=node.type==='note'?null:!block.trackable?null:planned?['Planejada · fora da medição','']:!hasRealPath(node)?['Falta a URL','is-warn']:journeyMetric?.sessions>0||observed?['Recebendo dados','is-ok']:['URL definida',''];
  return <ReportsPanelShell compact className="reports-node-settings flow-inspector" title={node.title||block.label} onClose={onClose} closeLabel="Fechar propriedades" footer={!readOnly&&<UntitledButton type="button" color="tertiary-destructive" size="sm" className="flow-inspector__remove" onPress={onRemove}>Remover</UntitledButton>}>
    <div className="flow-inspector__body" onFocus={onGestureStart} onBlur={onGestureEnd}>
      <div className="flow-inspector__kind"><span>{block.category}</span>{chip&&<em className={chip[1]} aria-live="polite">{chip[0]}</em>}</div>
      <label>Nome<ReportsFieldInput disabled={readOnly} value={node.title||''} maxLength="60" onChange={event=>onChange('title',event.target.value)}/></label>
      {node.type==='note'&&<NoteEditor node={node} readOnly={readOnly} onChange={onChange}/>}
      {pageLike&&<PageSource node={node} spec={spec} planned={planned} readOnly={readOnly} onChange={onChange} sitePages={sitePages} integrationsUrl={integrationsUrl}/>}
      {['event','conversion'].includes(node.type)&&<label>Nome do evento{node.type==='conversion'?' (opcional)':''}<ReportsFieldInput disabled={readOnly} value={node.event_name||''} placeholder="lead_enviado" onChange={event=>onChange('event_name',event.target.value)}/>{node.event_name&&<small>{measurementHint(node)}</small>}</label>}
      {node.type==='source'&&<>
        <label>Público<ReportsFieldInput disabled={readOnly} maxLength="80" value={node.segment?.name||''} placeholder="Ex.: Remarketing 30 dias" onChange={event=>onChange('segment',{...(node.segment||{}),name:event.target.value})}/></label>
        <label>Tipo<ReportsNativeSelect disabled={readOnly} value={node.segment?.kind||'prospeccao'} onChange={event=>onChange('segment',{...(node.segment||{}),kind:event.target.value})}>{SEGMENT_KINDS.map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label>
        <FlowSourceTracking node={node} nodes={nodes} readOnly={readOnly} onChange={onChange} metric={journeyMetric}/>
        {!readOnly&&onSplitSegment&&<UntitledButton type="button" color="secondary" size="sm" onPress={()=>onSplitSegment(node.id)}>Criar outro público deste canal</UntitledButton>}
      </>}
      {node.type!=='note'&&<details className="flow-inspector__more" open={node.type==='conversion'||undefined}><summary>Mais opções</summary>
        {node.type==='source'&&<label>Origem de tráfego<ReportsFieldInput disabled={readOnly} value={node.source||block.source||''} onChange={event=>onChange('source',event.target.value)}/></label>}
        {node.type==='source'&&<label>Como encontrar o público<ReportsTextArea disabled={readOnly} maxLength="500" rows={2} value={node.segment?.description||''} placeholder="Interesses, palavras-chave, lista ou regra" onChange={event=>onChange('segment',{...(node.segment||{}),description:event.target.value})}/></label>}
        {['page','form','conversion','error'].includes(node.type)&&<label>Tipo de página<ReportsNativeSelect disabled={readOnly} value={node.pageTypeStatus==='unresolved'?'unresolved':node.pageType||'other'} onChange={event=>onChange('pageType',event.target.value)}>{node.pageTypeStatus==='unresolved'&&<option value="unresolved" disabled>Não definido</option>}{[['home','Home'],['service','Serviço'],['institutional','Institucional'],['contact','Contato'],['case','Case'],['content','Conteúdo'],['other','Outro']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label>}
        {node.type!=='source'&&<label>Etapa<ReportsNativeSelect disabled={readOnly} value={editableStage(node)} onChange={event=>onChange('stage',event.target.value)}>{node.stage==='source'&&node.type!=='page'&&<option value="source" disabled>Origem (posição antiga)</option>}{FLOW_STAGES.filter(stage=>stage.id!=='source').map(stage=><option key={stage.id} value={stage.id}>{stage.label}</option>)}</ReportsNativeSelect></label>}
        {!readOnly&&nodes.length>1&&<label>Conectar a<ReportsNativeSelect value="" onChange={event=>{if(event.target.value)onConnect?.(node.id,event.target.value);}}><option value="">Escolha o destino</option>{nodes.filter(item=>item.id!==node.id).map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</ReportsNativeSelect></label>}
        <label>Grupo<ReportsFieldInput list="flow-existing-groups" disabled={readOnly} value={node.pageGroup||''} placeholder="Ex.: Aquisição" onChange={event=>onChange('pageGroup',event.target.value)}/><datalist id="flow-existing-groups">{groups.map(name=><option key={name} value={name}/>)}</datalist></label>
        {node.pageGroup&&!groups.includes(node.pageGroup)&&<UntitledButton color="tertiary" size="sm" isDisabled={readOnly} onPress={()=>onCreateGroup(node.pageGroup)}>Criar grupo “{node.pageGroup}”</UntitledButton>}
        <Switch className="flow-inspector-toggle" isDisabled={readOnly} isSelected={Boolean(node.isEntry)} onChange={value=>onChange('isEntry',value)}><span className="flow-toggle-track"/>Ponto de entrada</Switch>
        <Switch className="flow-inspector-toggle" isDisabled={readOnly} isSelected={Boolean(node.locked)} onChange={value=>onChange('locked',value)}><span className="flow-toggle-track"/>Fixar ordem vertical</Switch>
        <label>Função na jornada<ReportsNativeSelect disabled={readOnly} value={node.role||(node.type==='conversion'?'conversion':'none')} onChange={event=>onChange('role',event.target.value)}>{[['none','Não definida'],['entry','Entrada'],['institutional','Institucional'],['offer','Oferta'],['content','Conteúdo'],['intent','Intenção'],['form','Formulário'],['checkout','Finalização de compra'],['conversion','Confirmação'],['legal','Página legal'],['error','Erro']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label>
        <label>Descrição<ReportsTextArea disabled={readOnly} value={node.description||''} maxLength="500" rows={2} onChange={event=>onChange('description',event.target.value)}/></label>
        {node.type==='form'&&(node.fields||[]).length>0&&<p className="flow-inspector__fields"><strong>Campos observados:</strong> {node.fields.map(field=>field.label||field.name).join(', ')}</p>}
        {block.category==='Segmentação e CRM'&&integrationsUrl&&<a href={integrationsUrl}>Webhook de conversões do cliente ↗</a>}
        {journeyMetric&&<p className="flow-inspector__fields">{Number(journeyMetric.sessions||0).toLocaleString('pt-BR')} sessões · {Number(journeyMetric.events||0).toLocaleString('pt-BR')} eventos no período</p>}
      </details>}
    </div>
  </ReportsPanelShell>;
}

const MAX_CHECKLIST=30;
function NoteEditor({node,readOnly,onChange}){
  const checklist=node.checklist||[];
  const [draft,setDraft]=useState('');
  const update=next=>onChange('checklist',next);
  const add=()=>{const text=draft.replace(/\s+/g,' ').trim().slice(0,200);if(!text||checklist.length>=MAX_CHECKLIST)return;update([...checklist,{text,done:false}]);setDraft('');};
  return <>
    <label>Texto<ReportsTextArea disabled={readOnly} value={node.description||''} maxLength="2000" rows={4} onChange={event=>onChange('description',event.target.value)} placeholder="Contexto, decisões e combinados do plano"/></label>
    <fieldset className="flow-inspector__checklist"><legend>Checklist <small>{checklist.filter(item=>item.done).length}/{checklist.length}</small></legend>
      {checklist.map((item,index)=><div key={index} className="flow-inspector__check">
        <input type="checkbox" aria-label={`Concluir: ${item.text}`} disabled={readOnly} checked={item.done} onChange={event=>update(checklist.map((entry,position)=>position===index?{...entry,done:event.target.checked}:entry))}/>
        <ReportsFieldInput aria-label={`Item ${index+1}`} disabled={readOnly} value={item.text} maxLength="200" onChange={event=>update(checklist.map((entry,position)=>position===index?{...entry,text:event.target.value}:entry))}/>
        {!readOnly&&<UntitledButton type="button" color="tertiary" size="sm" aria-label={`Remover ${item.text}`} onPress={()=>update(checklist.filter((_,position)=>position!==index))}>×</UntitledButton>}
      </div>)}
      {!readOnly&&checklist.length<MAX_CHECKLIST&&<form className="flow-inspector__check-add" onSubmit={event=>{event.preventDefault();add();}}><ReportsFieldInput aria-label="Novo item do checklist" placeholder="Novo item" maxLength="200" value={draft} onChange={event=>setDraft(event.target.value)}/><UntitledButton type="submit" color="secondary" size="sm" isDisabled={!draft.trim()}>Adicionar</UntitledButton></form>}
      <small>Itens abertos aparecem na folha de produção.</small>
    </fieldset>
  </>;
}

function PageSource({node,spec,planned,readOnly,onChange,sitePages,integrationsUrl}){
  const installed=sitePages?.hosts||[];
  const covered=host=>installed.some(root=>{const base=root.replace(/^www\./,'');return host===base||host.endsWith(`.${base}`)||host===root;});
  const needsTag=!planned&&node.host&&installed.length>0&&!covered(node.host);
  const setMode=create=>{onChange('status',create?'planned':'ready');};
  const placeholderTitle=!node.title||/^(P[aá]gina( \/ URL)?|Formul[aá]rio|Convers[aã]o|Erro|Evento|Clique WhatsApp)$/i.test(node.title.trim());
  const pick=({host,path,name})=>{onChange('host',host);onChange('path',path);if(placeholderTitle&&name)onChange('title',name.slice(0,60));};
  const setUrl=parsed=>{
    if(parsed.empty){onChange('path','');onChange('host','');return;}
    onChange('path',parsed.path);onChange('host',parsed.host);
  };
  const setSpec=(field,value)=>onChange('spec',{...spec,[field]:value});
  const more=SPEC_FIELDS.filter(([field])=>!['goal','owner','due_date','suggested_path'].includes(field));
  return <>
    <div className="flow-inspector__mode" role="radiogroup" aria-label="Situação da página">
      <button type="button" role="radio" aria-checked={!planned} disabled={readOnly} onClick={()=>setMode(false)}>Já existe</button>
      <button type="button" role="radio" aria-checked={planned} disabled={readOnly} onClick={()=>setMode(true)}>Vai ser criada</button>
    </div>
    <FlowPagePicker node={node} readOnly={readOnly} planned={planned} clientId={sitePages?.clientId} csrf={sitePages?.csrf} hosts={sitePages?.hosts||[]} notice={sitePages?.notice||''} defaultHost={sitePages?.defaultHost||''} onPick={pick} onUrl={setUrl}/>
    {needsTag&&<small className="flow-inspector__tag-note">Outro domínio: instale a Super Tag em <strong>{node.host}</strong> para medir esta página.{integrationsUrl&&<> <a href={integrationsUrl}>Instalar ↗</a></>}</small>}
    {planned&&<div className="flow-inspector__brief">
      <label>O que a página precisa ter<ReportsTextArea disabled={readOnly} rows={2} maxLength="500" value={spec.goal||''} placeholder="Objetivo, oferta e chamada principal" onChange={event=>setSpec('goal',event.target.value)}/></label>
      <div className="flow-inspector__pair"><label>Responsável<ReportsFieldInput disabled={readOnly} maxLength="120" value={spec.owner||''} onChange={event=>setSpec('owner',event.target.value)}/></label>
        <label>Prazo<ReportsFieldInput disabled={readOnly} type="date" value={spec.due_date||''} onChange={event=>setSpec('due_date',event.target.value)}/></label></div>
      <details><summary>Briefing completo · {more.filter(([field])=>spec[field]).length}/{more.length}</summary>{more.map(([field,label,kind,limit])=><label key={field}>{label}{kind==='textarea'?<ReportsTextArea disabled={readOnly} rows={3} maxLength={limit} value={spec[field]||''} onChange={event=>setSpec(field,event.target.value)}/>:<ReportsFieldInput disabled={readOnly} maxLength={limit} value={spec[field]||''} onChange={event=>setSpec(field,event.target.value)}/>}</label>)}</details>
    </div>}
  </>;
}
