import {Switch} from 'react-aria-components';
import {FLOW_STAGES,stageFor} from './flowStages.js';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import React from 'react';
import {eventMatchesNode} from './flowEventIdentity.js';
import {Button as UntitledButton} from './untitled-kit/src/components/base/buttons/button.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';
import {flowBlockFor} from './flowBlockRegistry.js';

export function FlowInspector({node,groups=[],activity=[],journeyMetric=null,integrationsUrl='',readOnly,onChange,onCreateGroup,onRemove,onClose,onGestureStart,onGestureEnd}) {
  if(!node)return null;
  const block=flowBlockFor(node);
  const configured=Boolean(node.path&&!node.path.startsWith('/configurar-'));
  const observed=activity.find(item=>eventMatchesNode(item,node));
  const status=!block.trackable?'Etapa visual':!configured?'Configure a URL real':journeyMetric?.sessions>0?'Passagens observadas':observed?'Eventos recebidos':'Sem eventos no período';
  return <aside className="reports-node-settings flow-inspector" aria-label={`Propriedades de ${node.title}`}>
    <div className="flow-inspector__head"><div><span>{block.category}</span><h3>{node.title}</h3></div><UntitledButton color="tertiary" size="sm" aria-label="Fechar propriedades" onPress={onClose}>×</UntitledButton></div>
    <div className="flow-inspector__body" onFocus={onGestureStart} onBlur={onGestureEnd}>
      <section className="flow-inspector__status" aria-live="polite"><strong>Super Tag</strong><span className={observed||journeyMetric?'is-receiving':''}>{status}</span>{journeyMetric&&<small>{Number(journeyMetric.sessions||0).toLocaleString('pt-BR')} sessões únicas · {Number(journeyMetric.events||0).toLocaleString('pt-BR')} eventos nesta etapa</small>}{observed&&!journeyMetric&&<small>{Number(observed.total??observed.views??0).toLocaleString('pt-BR')} eventos no período selecionado</small>}{!block.trackable&&<small>Este bloco organiza o desenho da jornada. Nenhuma ação é executada.</small>}</section>
      {block.category==='Segmentação e CRM'&&<section className="flow-inspector__integration"><strong>Integração de CRM</strong><p>Esta etapa pertence ao cliente selecionado em Reports. O webhook de conversões desse cliente recebe confirmações de lead, qualificação e venda; este bloco ainda não dispara ações nem lê segmentos do CRM.</p>{integrationsUrl&&<a href={integrationsUrl}>Ver integração e webhook do cliente ↗</a>}<small>API para CRM próprio e vínculo com contas individuais: em breve.</small></section>}
      <label>Nome<ReportsFieldInput disabled={readOnly} value={node.title||''} maxLength="60" onChange={event=>onChange('title',event.target.value)}/></label>

      <label>Papel<ReportsNativeSelect disabled={readOnly} value={node.role||'none'} onChange={event=>onChange('role',event.target.value)}>{[['none','Sem papel'],['entry','Entrada'],['institutional','Institucional'],['offer','Oferta'],['content','Conteúdo'],['intent','Intenção'],['form','Formulário'],['checkout','Checkout'],['conversion','Conversão'],['legal','Legal'],['error','Erro']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</ReportsNativeSelect></label>
      <label>Etapa do funil<ReportsNativeSelect disabled={readOnly} value={stageFor(node)} onChange={event=>onChange('stage',event.target.value)}>{FLOW_STAGES.map(stage=><option key={stage.id} value={stage.id}>{stage.label}</option>)}</ReportsNativeSelect></label>
      <Switch className="flow-inspector-toggle" isDisabled={readOnly} isSelected={Boolean(node.locked)} onChange={value=>onChange('locked',value)}><span className="flow-toggle-track"/>Fixar posição</Switch>
      {block.trackable&&<label>Caminho da página<ReportsFieldInput disabled={readOnly} value={node.path||''} placeholder="/caminho-real" onChange={event=>onChange('path',event.target.value)}/><small>Use uma página do domínio autorizado.</small></label>}
      {['event','conversion'].includes(node.type)&&<label>Nome do evento{node.type==='conversion'?' (opcional)':''}<ReportsFieldInput disabled={readOnly} value={node.event_name||''} placeholder="lead_enviado" onChange={event=>onChange('event_name',event.target.value)}/><small>Deve corresponder ao nome enviado pela Super Tag.</small></label>}
      {node.type==='source'&&<label>Origem de tráfego<ReportsFieldInput disabled={readOnly} value={node.source||block.source||''} onChange={event=>onChange('source',event.target.value)}/></label>}
      <label>Grupo<ReportsFieldInput list="flow-existing-groups" disabled={readOnly} value={node.pageGroup||''} placeholder="Ex.: Aquisição" onChange={event=>onChange('pageGroup',event.target.value)}/><datalist id="flow-existing-groups">{groups.map(name=><option key={name} value={name}/>)}</datalist></label>{node.pageGroup&&!groups.includes(node.pageGroup)&&<UntitledButton color="tertiary" size="sm" isDisabled={readOnly} onPress={()=>onCreateGroup(node.pageGroup)}>Criar grupo “{node.pageGroup}”</UntitledButton>}
      <Switch className="flow-inspector-toggle" isDisabled={readOnly} isSelected={Boolean(node.isEntry)} onChange={value=>onChange('isEntry',value)}><span className="flow-toggle-track"/>Ponto de entrada</Switch>
      <details><summary>Mais detalhes</summary><label>Descrição<ReportsTextArea disabled={readOnly} value={node.description||''} maxLength="500" rows={3} onChange={event=>onChange('description',event.target.value)}/></label></details>
      {node.type==='form'&&<section><strong>Campos observados</strong>{(node.fields||[]).length?<ul>{node.fields.map((field,index)=><li key={`${field.name}:${index}`}>{field.label||field.name}</li>)}</ul>:<p>Os campos aparecem após o mapeamento da página.</p>}</section>}
    </div>
    {!readOnly&&<div className="flow-inspector__footer"><UntitledButton color="tertiary-destructive" size="sm" onPress={onRemove}>Excluir etapa</UntitledButton></div>}
  </aside>;
}
