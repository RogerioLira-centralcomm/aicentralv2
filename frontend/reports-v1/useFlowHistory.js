import {useCallback,useEffect,useRef,useState} from 'react';
const snapshot=config=>JSON.stringify(config);
/** Document history. A gesture is one undo entry; view state never enters config. */
export function useFlowHistory(config,setConfig) {
  const state=useRef({past:[],present:snapshot(config),future:[],gesture:false});
  const current=useRef(config);current.current=config;
  const [,refresh]=useState(0);
  const commit=useCallback(()=>{
    const history=state.current,next=snapshot(current.current);
    if(next===history.present)return;
    history.past.push(history.present);if(history.past.length>100)history.past.shift();
    history.present=next;history.future=[];refresh(n=>n+1);
  },[]);
  useEffect(()=>{if(!state.current.gesture)commit();},[config,commit]);
  const begin=useCallback(()=>{commit();state.current.gesture=true;refresh(n=>n+1);},[commit]);
  const end=useCallback(()=>{state.current.gesture=false;queueMicrotask(commit);refresh(n=>n+1);},[commit]);
  const reset=useCallback(value=>{current.current=value;state.current={past:[],present:snapshot(value),future:[],gesture:false};refresh(n=>n+1);},[]);
  const undo=useCallback(()=>{commit();const h=state.current;if(!h.past.length)return;h.future.push(h.present);h.present=h.past.pop();current.current=JSON.parse(h.present);setConfig(current.current);refresh(n=>n+1);},[commit,setConfig]);
  const redo=useCallback(()=>{const h=state.current;if(!h.future.length)return;h.past.push(h.present);h.present=h.future.pop();current.current=JSON.parse(h.present);setConfig(current.current);refresh(n=>n+1);},[setConfig]);
  return {undo,redo,reset,begin,end,isInteracting:state.current.gesture,canUndo:state.current.past.length>0,canRedo:state.current.future.length>0};
}
