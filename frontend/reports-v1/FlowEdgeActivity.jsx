import React, {useEffect, useRef, useState} from 'react';

/** Monitored traffic runs toward the goal: more dots and a faster pace on busier connections (0 = none). */
function TrafficDots({path, flow}) {
  const count = 1 + Math.round(flow * 2);
  const duration = (4.2 - 2 * flow).toFixed(2);
  return <g className="flow-traffic-dots" aria-hidden="true">{Array.from({length: count}, (_, index) =>
    <circle key={index} r={3 + flow * 1.5} opacity="0" fill="var(--color-bg-primary)" stroke="var(--color-fg-brand-primary)" strokeWidth={1.5}>
      <animateMotion dur={`${duration}s`} begin={`${(duration * index / count).toFixed(2)}s`} repeatCount="indefinite" path={path} keyPoints="0;1" keyTimes="0;1" calcMode="linear"/>
      <animate attributeName="opacity" values="0;.9;.9;0" keyTimes="0;.08;.9;1" dur={`${duration}s`} begin={`${(duration * index / count).toFixed(2)}s`} repeatCount="indefinite"/>
    </circle>)}</g>;
}

/** The continuous dot is collection health, never a visitor counter. */
export function FlowEdgeActivity({path, flow = 0, operational, transitionId, ready, scope}) {
  const baseline=useRef({scope:null,id:null});
  const [pulse,setPulse]=useState(false);
  useEffect(()=>{
    setPulse(false);
    const id=/^\d+$/.test(String(transitionId||''))?BigInt(transitionId):null;
    const previous=baseline.current;
    if(!ready||previous.scope!==scope){baseline.current={scope:ready?scope:null,id};return;}
    if(id===null||previous.id!==null&&id<=previous.id)return;
    baseline.current={scope,id};setPulse(true);
    const timer=setTimeout(()=>setPulse(false),1800);
    return()=>clearTimeout(timer);
  },[transitionId,ready,scope]);
  return <>{flow>0&&<TrafficDots path={path} flow={flow}/>}{operational&&<circle className="flow-operational-dot" r="3.5" fill="var(--color-fg-success-primary)"><title>Passagem observada nos últimos 90 segundos · não representa visitantes</title><animateMotion dur="4s" repeatCount="indefinite" path={path}/></circle>}{pulse&&<circle className="flow-transition-dot" r="3.5" fill="var(--color-fg-brand-primary)"><title>Nova passagem observada</title><animateMotion dur="1.8s" repeatCount="1" fill="freeze" path={path}/><animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.85;1" dur="1.8s" repeatCount="1"/></circle>}</>;
}
