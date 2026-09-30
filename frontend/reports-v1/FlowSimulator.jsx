import React, {useEffect, useMemo, useState} from 'react';
import {Button} from './untitled-kit/src/components/base/buttons/button.tsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';

export function FlowSimulator({config,onPathChange,onClose}) {
  const nodes=config.nodes||[],edges=config.edges||[];
  const starts=useMemo(()=>nodes.filter(node=>node.type==='source'||node.isEntry),[nodes]);
  const [startId,setStartId]=useState(starts[0]?.id||nodes[0]?.id||'');
  const [path,setPath]=useState([]);
  const [playing,setPlaying]=useState(false);
  const current=nodes.find(node=>node.id===path.at(-1));
  const next=edges.filter(edge=>edge.from===current?.id).map(edge=>({edge,node:nodes.find(node=>node.id===edge.to)})).filter(item=>item.node);
  useEffect(()=>{onPathChange(path);},[path,onPathChange]);
  useEffect(()=>{if(!playing)return;const timer=window.setTimeout(()=>{if(next.length!==1||path.length>=Math.max(30,nodes.length*2)){setPlaying(false);return;}setPath(value=>[...value,next[0].node.id]);},750);return()=>window.clearTimeout(timer);},[playing,path,next,nodes.length]);
  const unmapped=path.map(id=>nodes.find(node=>node.id===id)).filter(node=>node&&['page','form','event','conversion','whatsapp','error'].includes(node.type)&&(!node.path||node.path.startsWith('/configurar-')));
  return <section className="flow-simulator" aria-label="Simulação fictícia do fluxo"><div className="flow-simulator__head"><div><strong>Simulação fictícia da jornada</strong><small>Nenhum evento real é enviado à Super Tag.</small></div><Button size="sm" color="tertiary" onPress={onClose}>Fechar</Button></div>
    <div className="flow-simulator__controls"><label>Origem<ReportsNativeSelect value={startId} onChange={event=>{setStartId(event.target.value);setPath([]);setPlaying(false);}}>{(starts.length?starts:nodes).map(node=><option key={node.id} value={node.id}>{node.title}</option>)}</ReportsNativeSelect></label><Button size="sm" onPress={()=>{setPath(startId?[startId]:[]);setPlaying(false);}} isDisabled={!startId}>Iniciar</Button><Button size="sm" color="secondary" onPress={()=>setPlaying(value=>!value)} isDisabled={!current||next.length!==1}>{playing?'Pausar':'Reproduzir'}</Button><span>{path.length} etapa{path.length===1?'':'s'} percorrida{path.length===1?'':'s'}</span></div>
    {current&&<div className="flow-simulator__step"><strong>Agora: {current.title}</strong>{next.length?<div>{next.length>1&&<small>Há uma divisão no fluxo. Escolha o próximo caminho para continuar.</small>}Próxima etapa: {next.map(item=><Button key={item.edge.id} size="sm" color="secondary" onPress={()=>{setPlaying(false);setPath(value=>[...value,item.node.id]);}}>{item.edge.label&&item.edge.label!=='Próximo'?`${item.edge.label} → `:''}{item.node.title}</Button>)}</div>:<small>Fim do caminho desenhado.</small>}</div>}
    {unmapped.length>0&&<p className="flow-simulator__warning">{unmapped.length} etapa{unmapped.length===1?'':'s'} percorrida{unmapped.length===1?'':'s'} ainda sem URL real: {unmapped.map(node=>node.title).join(', ')}. A Super Tag não as reconheceria.</p>}
  </section>;
}
