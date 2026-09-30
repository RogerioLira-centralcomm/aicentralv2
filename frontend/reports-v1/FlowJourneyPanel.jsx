import React from 'react';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';

export function FlowJourneyPanel({journey,days,onDaysChange,onAddSuggestion,onClose,loading,error}) {
  const suggestions=journey?.suggestions||[];
  const byId=Object.fromEntries((journey?.config?.nodes||[]).map(node=>[node.id,node.title]));
  const funnel=journey?.funnel;
  return <section className="flow-journey-panel" aria-label="Jornada observada"><div className="flow-journey-panel__head"><div><strong>Jornada observada</strong><small>Versão publicada {journey?.revision?`· v${journey.revision}`:''}</small></div><Button size="sm" color="tertiary" onPress={onClose}>Fechar</Button></div>
    <div className="flow-journey-panel__filters">{[7,30,90].map(period=><Button key={period} size="sm" color={period===days?'secondary':'tertiary'} onPress={()=>onDaysChange(period)}>{period} dias</Button>)}</div>
    {loading?<p>Carregando eventos da Super Tag…</p>:error?<p role="alert">{error}</p>:journey?.status!=='ready'?<p>Publique o fluxo e mantenha a instalação ativa para acompanhar a jornada.</p>:journey.collection?.status==='no_data'?<p>Sem eventos recebidos neste período. Confira a Super Tag antes de interpretar taxas e volumes.</p>:<><p><strong>{funnel?.rate==null?'—':`${funnel.rate}%`}</strong> de conversão observada · {Number(funnel?.conversions||0).toLocaleString('pt-BR')} de {Number(funnel?.entries||0).toLocaleString('pt-BR')} sessões de entrada. Cada nó mostra sessões únicas; cada seta mostra passagem direta entre etapas.</p><div className="flow-journey-panel__suggestions"><strong>Caminhos observados fora do desenho</strong>{suggestions.length?<ul>{suggestions.slice(0,5).map(item=><li key={`${item.from}:${item.to}`}><span>{byId[item.from]||item.from} → {byId[item.to]||item.to} · {item.sessions.toLocaleString('pt-BR')} sessões</span><Button size="xs" color="secondary" onPress={()=>onAddSuggestion(item)}>Adicionar ao rascunho</Button></li>)}</ul>:<small>Nenhum caminho adicional encontrado neste período.</small>}</div></>}
  </section>;
}
