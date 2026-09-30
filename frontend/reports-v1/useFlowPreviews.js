import {useCallback,useEffect,useRef,useState} from 'react';

export function useFlowPreviews({flowId,clientId,csrf,canCapture=false,revision}={}) {
  const url=flowId&&clientId?`/connect/api/v2/reports/flow/flows/${flowId}/previews?client_id=${clientId}${revision?`&revision=${revision}`:''}`:null;
  const [state,setState]=useState({url:null,items:{},available:true,error:null});
  const [refresh,setRefresh]=useState(0);
  const requestedCapture=useRef(null);
  const capture=useCallback(id=>{
    if(!url||!canCapture||!id)return;
    requestedCapture.current={url,nodeId:id};
    setRefresh(n=>n+1);
  },[url,canCapture]);
  useEffect(()=>{
    if(!url)return;
    let disposed=false,timer,pending=false;
    let controller;
    // A captura só é solicitada pelo clique; consultas e tentativas seguintes usam GET.
    const requested=requestedCapture.current?.url===url?requestedCapture.current.nodeId:null;
    requestedCapture.current=null;
    let nextRequest=requested;
    const poll=async()=>{
      if(pending||disposed||document.hidden)return;
      pending=true;
      controller=new AbortController();
      let timedOut=false;
      const timeout=setTimeout(()=>{timedOut=true;controller.abort();},12000);
      const nodeId=nextRequest;
      nextRequest=null;
      try {
        const response=await fetch(url,{method:nodeId?'POST':'GET',credentials:'same-origin',signal:controller.signal,headers:nodeId?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},...(nodeId?{body:JSON.stringify({node_id:nodeId})}:{})});
        const result=await response.json();
        if(!response.ok)throw new Error(result.message||'Captura indisponível');
        if(!disposed)setState({url,items:result.items||{},available:result.available!==false,error:null});
        if(!disposed&&result.available!==false)timer=setTimeout(poll,Object.values(result.items||{}).some(item=>item.status==='capturing')?5000:30000);
      }catch(error){
        if(!disposed&&(!controller.signal.aborted||timedOut)){
          const message=timedOut?'A consulta de capturas demorou mais que o esperado. Tentando novamente…':error.message||'Não foi possível consultar as capturas.';
          setState(old=>({url,items:old.url===url?old.items:{},available:old.url===url?old.available:true,error:message}));
          if(!document.hidden)timer=setTimeout(poll,30000);
        }
      }finally{clearTimeout(timeout);pending=false;}
    };
    const visible=()=>{clearTimeout(timer);if(document.hidden)controller?.abort();else poll();};
    poll();document.addEventListener('visibilitychange',visible);
    return()=>{disposed=true;clearTimeout(timer);controller?.abort();document.removeEventListener('visibilitychange',visible);};
  },[url,canCapture,csrf,refresh]);
  return {...(state.url===url?state:{items:{},available:true,error:null}),regenerate:capture};
}
