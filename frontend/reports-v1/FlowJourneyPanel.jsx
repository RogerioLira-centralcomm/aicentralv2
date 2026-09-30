import React from 'react';
import {Button} from './untitled-kit/src/components/base/buttons/button.tsx';

export function FlowJourneyPanel({journey,days,onDaysChange,onAddSuggestion,onClose,loading,error}) {
  const suggestions=journey?.suggestions||[];
  const byId=Object.fromEntries((journey?.config?.nodes||[]).map(node=>[node.id,node.title]));
  const sessions=(journey?.nodes||[]).reduce((largest,node)=>Math.max(largest,Number(node.sessions)||0),0);
  return <section className="flow-journey-panel" aria-label="Jornada observada"><div className="flow-journey-panel__head"><div><strong>Jornada observada</strong><small>Versão publicada {journey?.revision?`· v${journey.revision}`:''}</small></div><Button size="sm" color="tertiary" onPress={onClose}>Fechar</Button></div>
    <div className="flow-journey-panel__filters">{[7,30,90].map(period=><Button key={period} size="sm" color={period===days?'secondary':'tertiary'} onPress={()=>onDaysChange(period)}>{period} dias</Button>)}</div>
    {loading?<p>Carregando eventos da Super Tag…</p>:error?<p role="alert">{error}</p>:journey?.status!=='ready'?<p>Publique o fluxo e mantenha a instalação ativa para acompanhar a jornada.</p>:<><p><strong>{sessions.toLocaleString('pt-BR')}</strong> sessões na etapa de maior alcance. Cada nó mostra sessões únicas; cada seta mostra passagem entre etapas.</p><div className="flow-journey-panel__suggestions"><strong>Caminhos observados fora do desenho</strong>{suggestions.length?<ul>{suggestions.slice(0,5).map(item=><li key={`${item.from}:${item.to}`}><span>{byId[item.from]||item.from} → {byId[item.to]||item.to} · {item.sessions.toLocaleString('pt-BR')} sessões</span><Button size="xs" color="secondary" onPress={()=>onAddSuggestion(item)}>Adicionar ao rascunho</Button></li>)}</ul>:<small>Nenhum caminho adicional encontrado neste período.</small>}</div></>}
  </section>;
}
