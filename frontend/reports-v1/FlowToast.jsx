import React,{useEffect,useRef} from 'react';

export function FlowToast({message,onDismiss}) {
  const dismissRef=useRef(onDismiss);
  dismissRef.current=onDismiss;
  useEffect(()=>{
    if(!message)return undefined;
    const timer=window.setTimeout(()=>dismissRef.current(),5000);
    return()=>window.clearTimeout(timer);
  },[message]);
  if(!message)return null;
  return <div className="flow-toast-root" aria-live="polite" aria-atomic="false"><div className="flow-toast" role="status"><span>{message}</span><button type="button" aria-label="Fechar mensagem" onClick={onDismiss}>×</button></div></div>;
}
