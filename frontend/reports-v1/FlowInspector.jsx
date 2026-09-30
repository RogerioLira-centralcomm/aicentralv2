import React from 'react';
import {Button as UntitledButton} from './untitled-kit/src/components/base/buttons/button.tsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';
import {flowBlockFor} from './flowBlockRegistry.js';

export function FlowInspector({node,activity=[],journeyMetric=null,integrationsUrl='',readOnly,onChange,onRemove,onClose}) {
  if(!node)return null;
  const block=flowBlockFor(node);
  const configured=Boolean(node.path&&!node.path.startsWith('/configurar-'));
  const observed=activity.find(item=>item.page_path===node.path);
  const status=!block.trackable?'Etapa visual':!configured?'Configure a URL real':journeyMetric?'Passagens observadas':observed?'Eventos recebidos':'Sem eventos no período';
  return <aside className="reports-node-settings flow-inspector" aria-label={`Propriedades de ${node.title}`}>
    <div className="flow-inspector__head"><div><span>{block.category}</span><h3>{node.title}</h3></div><UntitledButton color="tertiary" size="sm" aria-label="Fechar propriedades" onPress={onClose}>×</UntitledButton></div>
    <div className="flow-inspector__body">
      <section className="flow-inspector__status" aria-live="polite"><strong>Super Tag</strong><span className={observed||journeyMetric?'is-receiving':''}>{status}</span>{journeyMetric&&<small>{Number(journeyMetric.sessions||0).toLocaleString('pt-BR')} sessões únicas · {Number(journeyMetric.events||0).toLocaleString('pt-BR')} eventos nesta etapa</small>}{observed&&!journeyMetric&&<small>{Number(observed.views||0).toLocaleString('pt-BR')} visitas no período selecionado</small>}{!block.trackable&&<small>Este bloco organiza o desenho da jornada. Nenhuma ação é executada.</small>}</section>
      {block.category==='Segmentação e CRM'&&<section className="flow-inspector__integration"><strong>Integração de CRM</strong><p>Esta etapa pertence ao cliente selecionado em Reports. O webhook de conversões desse cliente recebe confirmações de lead, qualificação e venda; este bloco ainda não dispara ações nem lê segmentos do CRM.</p>{integrationsUrl&&<a href={integrationsUrl}>Ver integração e webhook do cliente ↗</a>}<small>API para CRM próprio e vínculo com contas individuais: em breve.</small></section>}
      <label>Nome<ReportsFieldInput disabled={readOnly} value={node.title||''} maxLength="120" onChange={event=>onChange('title',event.target.value)}/></label>
      <label>Descrição<ReportsTextArea disabled={readOnly} value={node.description||''} maxLength="500" rows={3} onChange={event=>onChange('description',event.target.value)}/></label>
      {block.trackable&&<label>Caminho da página<ReportsFieldInput disabled={readOnly} value={node.path||''} placeholder="/caminho-real" onChange={event=>onChange('path',event.target.value)}/><small>Use uma página do domínio autorizado.</small></label>}
      {['event','conversion'].includes(node.type)&&<label>Nome do evento{node.type==='conversion'?' (opcional)':''}<ReportsFieldInput disabled={readOnly} value={node.event_name||''} placeholder="lead_enviado" onChange={event=>onChange('event_name',event.target.value)}/><small>Deve corresponder ao nome enviado pela Super Tag.</small></label>}
      {node.type==='source'&&<label>Origem de tráfego<ReportsFieldInput disabled={readOnly} value={node.source||block.source||''} onChange={event=>onChange('source',event.target.value)}/></label>}
      <label>Grupo<ReportsFieldInput disabled={readOnly} value={node.pageGroup||''} placeholder="Ex.: Aquisição" onChange={event=>onChange('pageGroup',event.target.value)}/></label>
      <label className="flow-inspector__checkbox"><input type="checkbox" disabled={readOnly} checked={Boolean(node.isEntry)} onChange={event=>onChange('isEntry',event.target.checked)}/> Ponto de entrada</label>
      {node.type==='form'&&<section><strong>Campos observados</strong>{(node.fields||[]).length?<ul>{node.fields.map((field,index)=><li key={`${field.name}:${index}`}>{field.label||field.name}</li>)}</ul>:<p>Os campos aparecem após o mapeamento da página.</p>}</section>}
    </div>
    {!readOnly&&<div className="flow-inspector__footer"><UntitledButton color="tertiary-destructive" size="sm" onPress={onRemove}>Excluir etapa</UntitledButton></div>}
  </aside>;
}
