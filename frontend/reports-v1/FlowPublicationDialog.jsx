import React, {useEffect, useState} from 'react';
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

export function FlowPublicationDialog({open,name,host,revision,config,previous,issues,note,onNoteChange,busy,onClose,onPublish,onPublishPlan,hasMeasuredSteps=true}) {
  const [mode,setMode]=useState(hasMeasuredSteps?'measure':'plan');
  useEffect(()=>{if(open)setMode(hasMeasuredSteps?'measure':'plan');},[open,hasMeasuredSteps]);
  if(!open)return null;
  const nodes=changed(previous?.nodes,config.nodes);
  const edges=changed(previous?.edges,config.edges);
  const errors=issues.filter(item=>item.severity==='error');
  const warnings=issues.filter(item=>item.severity==='warning');
  const planned=issues.filter(item=>item.code==='planned_step');
  const measure=mode==='measure';
  const measureBlocked=errors.length>0||!hasMeasuredSteps;
  return <ModalOverlay className="cadu-ds-overlay cadu-ds-overlay--center" isOpen={open} onOpenChange={value=>{if(!value&&!busy)onClose();}} isDismissable={!busy}>
    <Modal className="cadu-ds-confirm"><Dialog aria-label="Publicar" className="cadu-ds-confirm__dialog flow-publication-dialog">
      <h2>Publicar</h2><p><strong>{name}</strong> · {host} · rascunho r{revision}</p>
      <fieldset className="flow-publication-mode"><legend className="reports-sr-only">O que publicar</legend>
        <label className={mode==='plan'?'is-selected':''}><input type="radio" name="publication-mode" value="plan" checked={mode==='plan'} onChange={()=>setMode('plan')}/><span><strong>Publicar plano</strong><small>Congela esta versão do desenho para aprovação. Não liga a medição. A folha de produção só acompanha se houver páginas a criar.</small></span></label>
        <label className={measure?'is-selected':''}><input type="radio" name="publication-mode" value="measure" checked={measure} onChange={()=>setMode('measure')}/><span><strong>Ativar medição</strong><small>{hasMeasuredSteps?'Os passos prontos passam a ser medidos pela Super Tag; os dados anteriores continuam ligados às versões em que foram coletados.':'Disponível quando ao menos um passo estiver Pronto ou No ar, com a página real.'}</small></span></label>
      </fieldset>
      <p>{config.nodes.length} nós · {config.edges.length} conexões{measure?` · ${warnings.length} avisos permanecem após a publicação`:''}.</p>
      {measure&&<div className="flow-publication-summary"><strong>Mudanças desde a publicação anterior</strong><span>Nós: +{nodes.added} · {nodes.updated} alterados · −{nodes.removed}</span><span>Conexões: +{edges.added} · {edges.updated} alteradas · −{edges.removed}</span></div>}
      {measure&&errors.length>0&&<section className="flow-publication-errors" role="alert"><strong>{errors.length} problema{errors.length===1?'':'s'} impedem ativar a medição</strong><ul>{errors.slice(0,5).map((issue,index)=><li key={`${issue.code}:${index}`}>{issue.message}</li>)}</ul></section>}
      {planned.length>0&&<p className="flow-publication-planned">{planned.length} passo{planned.length===1?'':'s'} planejado{planned.length===1?'':'s'} {measure?`fica${planned.length===1?'':'m'} fora da medição até ter${planned.length===1?'':'em'} página no ar.`:`entra${planned.length===1?'':'m'} na folha de produção.`}</p>}
      {measure&&warnings.length>0&&<section className="flow-publication-warnings"><strong>Avisos que permanecerão</strong><ul>{warnings.map((issue,index)=><li key={`${issue.code}:${index}`}>{issue.message} {issue.consequence}</li>)}</ul></section>}
      <label>Nota desta versão (opcional)<ReportsTextArea value={note} maxLength="500" rows={3} onChange={event=>onNoteChange(event.target.value)} placeholder={measure?'O que mudou nesta publicação?':'O que este plano propõe ou o que mudou desde a última versão?'}/></label>
      <div className="cadu-ds-confirm__actions"><Button color="secondary" onPress={onClose} isDisabled={busy}>Cancelar</Button>{measure
        ?<Button color="primary" onPress={onPublish} isDisabled={busy||measureBlocked} isLoading={busy}>Ativar medição</Button>
        :<Button color="primary" onPress={onPublishPlan} isDisabled={busy||!config.nodes.length} isLoading={busy}>Publicar plano</Button>}</div>
    </Dialog></Modal>
  </ModalOverlay>;
}
