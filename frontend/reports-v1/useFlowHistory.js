import {useCallback, useEffect, useRef, useState} from 'react';

const LIMIT = 100;
const snapshot = config => JSON.stringify({nodes:config.nodes || [], edges:config.edges || []});

export function useFlowHistory(config, setConfig) {
  const history = useRef({past:[], present:snapshot(config), future:[], timer:null});
  const [, refresh] = useState(0);
  const update = () => refresh(value => value + 1);
  const commitPending = useCallback(() => {
    const state = history.current;
    if (state.timer) {window.clearTimeout(state.timer); state.timer=null;}
    const next=snapshot(config);
    if(next===state.present)return;
    state.past.push(state.present);
    if(state.past.length>LIMIT)state.past.shift();
    state.present=next;
    state.future=[];
    update();
  },[config]);
  useEffect(() => {
    const state=history.current;
    if(snapshot(config)===state.present)return;
    if(state.timer)window.clearTimeout(state.timer);
    state.timer=window.setTimeout(commitPending,200);
    return () => {if(state.timer){window.clearTimeout(state.timer);state.timer=null;}};
  },[config,commitPending]);
  const reset=useCallback(value=>{const state=history.current;if(state.timer)window.clearTimeout(state.timer);Object.assign(state,{past:[],present:snapshot(value),future:[],timer:null});update();},[]);
  const undo=useCallback(() => {
    commitPending();
    const state=history.current;
    if(!state.past.length)return;
    const previous=state.past.pop();
    state.future.push(state.present);
    state.present=previous;
    setConfig(current=>({...current,...JSON.parse(previous)}));
    update();
  },[commitPending,setConfig]);
  const redo=useCallback(() => {
    commitPending();
    const state=history.current;
    if(!state.future.length)return;
    const next=state.future.pop();
    state.past.push(state.present);
    state.present=next;
    setConfig(current=>({...current,...JSON.parse(next)}));
    update();
  },[commitPending,setConfig]);
  useEffect(()=>()=>{if(history.current.timer)window.clearTimeout(history.current.timer);},[]);
  return {undo,redo,reset,canUndo:history.current.past.length>0,canRedo:history.current.future.length>0};
}
