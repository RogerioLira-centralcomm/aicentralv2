import {ReportsPanelShell} from './ReportsPanelShell.jsx';
import {Switch} from 'react-aria-components';
import {FLOW_STAGES,editableStage} from './flowStages.js';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import React,{useId,useState} from 'react';
import {eventMatchesNode} from './flowEventIdentity.js';
import {Button as UntitledButton} from '../cadu-design-system/untitled-kit/button.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';
import {flowBlockFor} from './flowBlockRegistry.js';
import {NODE_STATUSES,NODE_STATUS_LABELS,SPEC_FIELDS,hasRealPath,isPlanned,nodeStatus} from './flowLifecycle.js';
import {SEGMENT_KINDS} from './flowMedia.js';

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

export function FlowInspector({onSplitSegment,node,nodes=[],groups=[],activity=[],journeyMetric=null,integrationsUrl='',readOnly,onChange,onConnect,onCreateGroup,onRemove,onClose,onGestureStart,onGestureEnd}) {
  const [tab,setTab]=useState('configuration');
  const tabId=useId();
  if(!node)return null;
  const block=flowBlockFor(node);
  const configured=hasRealPath(node);
  const planned=isPlanned(node);
  const spec=node.spec||{};
  const observed=activity.find(item=>eventMatchesNode(item,node));
  const status=!block.trackable?'Nó visual':planned?`${NODE_STATUS_LABELS[nodeStatus(node)]} · fora da medição`:!configured?'Configure a URL real':journeyMetric?.sessions>0?'Passagens observadas':observed?'Eventos recebidos':'Sem eventos no período';
  return <ReportsPanelShell className="reports-node-settings flow-inspector" title={node.title} context={block.category} onClose={onClose} closeLabel="Fechar propriedades" footer={!readOnly&&<UntitledButton type="button" color="tertiary-destructive" size="sm" onPress={onRemove}>Remover do fluxo</UntitledButton>}>
    <div className="reports-tabs" role="tablist" aria-label="Detalhes do nó">{[['summary','Resumo'],['configuration','Configuração']].map(([id,label])=><UntitledButton key={id} type="button" color="tertiary" role="tab" id={`${tabId}-${id}`} aria-controls={`${tabId}-${id}-panel`} aria-selected={tab===id} tabIndex={tab===id?0:-1} onKeyDown={event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?'summary':event.key==='End'?'configuration':tab==='summary'?'configuration':'summary';setTab(next);document.getElementById(`${tabId}-${next}`)?.focus();}}} onPress={()=>setTab(id)}>{label}</UntitledButton>)}</div>
    <section role="tabpanel" id={`${tabId}-summary-panel`} aria-labelledby={`${tabId}-summary`} hidden={tab!=='summary'}><h3>{status}</h3><p>{node.path||'Nó visual'}</p><p>{node.evidence||'Acompanhe os eventos recebidos para verificar este nó.'}</p>{node.description&&<p>{node.description}</p>}{journeyMetric&&<p>{Number(journeyMetric.sessions||0).toLocaleString('pt-BR')} sessões no período</p>}</section>
    <div role="tabpanel" id={`${tabId}-configuration-panel`} aria-labelledby={`${tabId}-configuration`} hidden={tab!=='configuration'} className="flow-inspector__body" onFocus={onGestureStart} onBlur={onGestureEnd}>
      {node.type!=='note'&&<section className="flow-inspector__status" aria-live="polite"><strong>Super Tag</strong><span className={observed||journeyMetric?'is-receiving':''}>{status}</span><small>{measurementHint(node)}</small>{journeyMetric&&<small>{Number(journeyMetric.sessions||0).toLocaleString('pt-BR')} sessões únicas · {Number(journeyMetric.events||0).toLocaleString('pt-BR')} eventos neste nó</small>}{observed&&!journeyMetric&&<small>{Number(observed.total??observed.views??0).toLocaleString('pt-BR')} eventos no período selecionado</small>}{!block.trackable&&<small>Este nó organiza o desenho da jornada. Nenhuma ação é executada.</small>}</section>}
      {block.category==='Segmentação e CRM'&&<section className="flow-inspector__integration"><strong>Integração de CRM</strong><p>Esta etapa pertence ao cliente selecionado em Reports. O webhook de conversões desse cliente recebe confirmações de lead, qualificação e venda; este bloco ainda não dispara ações nem lê segmentos do CRM.</p>{integrationsUrl&&<a href={integrationsUrl}>Ver integração e webhook do cliente ↗</a>}<small>API para CRM próprio e vínculo com contas individuais: em breve.</small></section>}
      <label>Nome<ReportsFieldInput disabled={readOnly} value={node.title||''} maxLength="60" onChange={event=>onChange('title',event.target.value)}/></label>
      {node.type==='note'&&<NoteEditor node={node} readOnly={readOnly} onChange={onChange}/>}
      {block.trackable&&<label>Situação<ReportsNativeSelect disabled={readOnly} value={nodeStatus(node)} onChange={event=>onChange('status',event.target.value)}>{NODE_STATUSES.map(value=><option key={value} value={value}>{NODE_STATUS_LABELS[value]}</option>)}</ReportsNativeSelect><small>{planned?'Passos planejados ou em produção entram no desenho e na folha de produção, mas não na medição.':'Pronto e No ar exigem a página real e entram na medição.'}</small></label>}
      {block.trackable&&planned&&<details className="flow-inspector__spec"><summary>Especificação para produção · {SPEC_FIELDS.filter(([field])=>spec[field]).length} de {SPEC_FIELDS.length}</summary>{SPEC_FIELDS.map(([field,label,kind,limit])=><label key={field}>{label}{kind==='textarea'?<ReportsTextArea disabled={readOnly} value={spec[field]||''} maxLength={limit} rows={3} onChange={event=>onChange('spec',{...spec,[field]:event.target.value})}/>:<ReportsFieldInput disabled={readOnly} type={kind==='date'?'date':'text'} value={spec[field]||''} maxLength={limit} placeholder={field==='suggested_path'?'/nova-pagina':undefined} onChange={event=>onChange('spec',{...spec,[field]:event.target.value})}/>}</label>)}</details>}

      {node.pageTypeStatus==='unresolved'&&<small>Tipo de página ainda não definido por falta de evidência. Escolha uma opção para confirmar.</small>}
      {['page','form','conversion','error'].includes(node.type)&&<label>Tipo de página<ReportsNativeSelect disabled={readOnly} value={node.pageTypeStatus==='unresolved'?'unresolved':node.pageType||'other'} onChange={event=>onChange('pageType',event.target.value)}>{node.pageTypeStatus==='unresolved'&&<option value="unresolved" disabled>Não definido</option>}{[['home','Home'],['service','Serviço'],['institutional','Institucional'],['contact','Contato'],['case','Case'],['content','Conteúdo'],['other','Outro']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label>}
      {node.type==='note'?null:node.type==='source'?<p>Canal na etapa Origem.</p>:<label>Etapa<ReportsNativeSelect disabled={readOnly} value={editableStage(node)} onChange={event=>onChange('stage',event.target.value)}>{node.stage==='source'&&node.type!=='page'&&<option value="source" disabled>Origem (posição antiga; escolha outra Etapa)</option>}{FLOW_STAGES.filter(stage=>stage.id!=='source').map(stage=><option key={stage.id} value={stage.id}>{stage.label}</option>)}</ReportsNativeSelect></label>}
      {node.type==='page'&&editableStage(node)==='conversion'&&<small>Uma página nesta Etapa faz parte do plano. Confirme um evento recebido pela Super Tag para medir a conversão.</small>}
      {!readOnly&&nodes.length>1&&<label>Criar conexão para<ReportsNativeSelect value="" onChange={event=>{if(event.target.value)onConnect?.(node.id,event.target.value);}}><option value="">Escolha o nó de destino</option>{nodes.filter(item=>item.id!==node.id).map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</ReportsNativeSelect></label>}
      {node.type!=='note'&&<Switch className="flow-inspector-toggle" isDisabled={readOnly} isSelected={Boolean(node.locked)} onChange={value=>onChange('locked',value)}><span className="flow-toggle-track"/>Fixar ordem vertical</Switch>}
      {block.trackable&&<label>{planned?'Endereço real (quando existir)':'Caminho da página'}<ReportsFieldInput disabled={readOnly} value={node.path||''} placeholder={spec.suggested_path||'/caminho-real'} onChange={event=>{const value=event.target.value.trim();onChange('path',value&&!value.startsWith('/')?`/${value}`:value);}}/><small>{planned?'Ao preencher, mude a Situação para Pronto para incluir o passo na medição.':'Use uma página do domínio autorizado.'}</small></label>}
      {['event','conversion'].includes(node.type)&&<label>Nome do evento{node.type==='conversion'?' (opcional)':''}<ReportsFieldInput disabled={readOnly} value={node.event_name||''} placeholder="lead_enviado" onChange={event=>onChange('event_name',event.target.value)}/><small>Deve corresponder ao nome enviado pela Super Tag.</small></label>}
      {node.type==='source'&&<label>Origem de tráfego<ReportsFieldInput disabled={readOnly} value={node.source||block.source||''} onChange={event=>onChange('source',event.target.value)}/></label>}
      {node.type==='source'&&<fieldset className="flow-inspector__segment"><legend>Público</legend>
        <label>Nome do público<ReportsFieldInput disabled={readOnly} maxLength="80" value={node.segment?.name||''} placeholder="Ex.: Remarketing 30 dias" onChange={event=>onChange('segment',{...(node.segment||{}),name:event.target.value})}/></label>
        <label>Tipo de público<ReportsNativeSelect disabled={readOnly} value={node.segment?.kind||'prospeccao'} onChange={event=>onChange('segment',{...(node.segment||{}),kind:event.target.value})}>{SEGMENT_KINDS.map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label>
        <label>Como encontrar este público<ReportsTextArea disabled={readOnly} maxLength="500" rows={3} value={node.segment?.description||''} placeholder="Interesses, palavras-chave, lista ou regra de remarketing" onChange={event=>onChange('segment',{...(node.segment||{}),description:event.target.value})}/></label>
        {!readOnly&&onSplitSegment&&<UntitledButton type="button" color="secondary" size="sm" onPress={()=>onSplitSegment(node.id)}>Criar outro público deste canal</UntitledButton>}
        <small>Cada público vira uma origem própria, com página de destino, previsão, criativos e setup.</small>
      </fieldset>}
      <label>Grupo<ReportsFieldInput list="flow-existing-groups" disabled={readOnly} value={node.pageGroup||''} placeholder="Ex.: Aquisição" onChange={event=>onChange('pageGroup',event.target.value)}/><datalist id="flow-existing-groups">{groups.map(name=><option key={name} value={name}/>)}</datalist></label>{node.pageGroup&&!groups.includes(node.pageGroup)&&<UntitledButton color="tertiary" size="sm" isDisabled={readOnly} onPress={()=>onCreateGroup(node.pageGroup)}>Criar grupo “{node.pageGroup}”</UntitledButton>}
      {node.type!=='note'&&<Switch className="flow-inspector-toggle" isDisabled={readOnly} isSelected={Boolean(node.isEntry)} onChange={value=>onChange('isEntry',value)}><span className="flow-toggle-track"/>Ponto de entrada</Switch>}
      {node.type!=='note'&&<details><summary>Mais detalhes</summary><label>Função na jornada<ReportsNativeSelect disabled={readOnly} value={node.role||'none'} onChange={event=>onChange('role',event.target.value)}>{[['none','Não definida'],['entry','Entrada'],['institutional','Institucional'],['offer','Oferta'],['content','Conteúdo'],['intent','Intenção'],['form','Formulário'],['checkout','Finalização de compra'],['conversion','Confirmação'],['legal','Página legal'],['error','Erro']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label><small>A função ajuda a descrever a jornada. Ela não muda a Etapa nem confirma uma conversão.</small><label>Descrição<ReportsTextArea disabled={readOnly} value={node.description||''} maxLength="500" rows={3} onChange={event=>onChange('description',event.target.value)}/></label></details>}
      {node.type==='form'&&<section><strong>Campos observados</strong>{(node.fields||[]).length?<ul>{node.fields.map((field,index)=><li key={`${field.name}:${index}`}>{field.label||field.name}</li>)}</ul>:<p>Os campos aparecem após o mapeamento da página.</p>}</section>}
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
