import React, {useEffect, useRef, useState} from 'react';

/** The continuous dot is collection health, never a visitor counter. */
export function FlowEdgeActivity({path, operational, transitionId, ready, scope}) {
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
  return <>{operational&&<circle className="flow-operational-dot" r="3.5" fill="var(--color-fg-success-primary)"><title>Passagem observada nos últimos 90 segundos · não representa visitantes</title><animateMotion dur="4s" repeatCount="indefinite" path={path}/></circle>}{pulse&&<circle className="flow-transition-dot" r="5" fill="var(--color-fg-brand-primary)"><title>Nova passagem observada</title><animateMotion dur="1.8s" repeatCount="1" path={path}/></circle>}</>;
}
