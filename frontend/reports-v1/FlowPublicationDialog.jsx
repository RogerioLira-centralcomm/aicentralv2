import React from 'react';
import {Dialog, Modal, ModalOverlay} from 'react-aria-components';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {ReportsTextArea} from './ReportsTextArea.jsx';

const changed=(before,after)=>{
  const old=new Map((before||[]).map(item=>[item.id,item]));
  const next=new Map((after||[]).map(item=>[item.id,item]));
  return {added:[...next.keys()].filter(id=>!old.has(id)).length,
    removed:[...old.keys()].filter(id=>!next.has(id)).length,
    updated:[...next.keys()].filter(id=>old.has(id)&&JSON.stringify(next.get(id))!==JSON.stringify(old.get(id))).length};
};
export const flowChangeSummary=(before,after)=>({
  nodes:changed(before?.nodes,after?.nodes),edges:changed(before?.edges,after?.edges),
});

export function FlowPublicationDialog({open,name,host,revision,config,previous,issues,note,onNoteChange,busy,onClose,onPublish}) {
  if(!open)return null;
  const nodes=changed(previous?.nodes,config.nodes);
  const edges=changed(previous?.edges,config.edges);
  const errors=issues.filter(item=>item.severity==='error');
  const warnings=issues.filter(item=>item.severity==='warning');
  return <ModalOverlay className="reports-untitled-overlay reports-confirm-overlay" isOpen={open} onOpenChange={value=>{if(!value&&!busy)onClose();}} isDismissable={!busy}>
    <Modal className="reports-confirm-modal"><Dialog aria-label="Publicar fluxo" className="reports-confirm-dialog flow-publication-dialog">
      <h2>Publicar fluxo</h2><p><strong>{name}</strong> · {host} · rascunho r{revision}. Esta versão será usada no monitoramento dos próximos eventos; os dados anteriores continuam ligados às versões em que foram coletados.</p>
      <p>{config.nodes.length} nós · {config.edges.length} conexões · {issues.filter(item=>item.severity==='warning').length} avisos permanecem após a publicação.</p>
      <div className="flow-publication-summary"><strong>Mudanças desde a publicação anterior</strong><span>Nós: +{nodes.added} · {nodes.updated} alterados · −{nodes.removed}</span><span>Conexões: +{edges.added} · {edges.updated} alteradas · −{edges.removed}</span></div>
      {errors.length>0&&<section className="flow-publication-errors" role="alert"><strong>{errors.length} problema{errors.length===1?'':'s'} impedem a publicação</strong><ul>{errors.slice(0,5).map((issue,index)=><li key={`${issue.code}:${index}`}>{issue.message}</li>)}</ul></section>}
      {warnings.length>0&&<section className="flow-publication-warnings"><strong>Avisos que permanecerão</strong><ul>{warnings.map((issue,index)=><li key={`${issue.code}:${index}`}>{issue.message} {issue.consequence}</li>)}</ul></section>}
      <label>Nota desta versão (opcional)<ReportsTextArea value={note} maxLength="500" rows={3} onChange={event=>onNoteChange(event.target.value)} placeholder="O que mudou nesta publicação?"/></label>
      <div className="reports-confirm-actions"><Button color="secondary" onPress={onClose} isDisabled={busy}>Cancelar</Button><Button color="primary" onPress={onPublish} isDisabled={busy||errors.length>0} isLoading={busy}>Publicar versão</Button></div>
    </Dialog></Modal>
  </ModalOverlay>;
}
