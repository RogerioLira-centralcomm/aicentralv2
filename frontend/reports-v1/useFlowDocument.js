import {useRef,useSyncExternalStore} from 'react';

/** Per-editor document store. Pointer movement stays in React Flow until drop. */
export function createFlowDocument(initial) {
  let document=initial;
  const listeners=new Set();
  return {
    getSnapshot:()=>document,
    subscribe:listener=>{listeners.add(listener);return()=>listeners.delete(listener);},
    set:change=>{const next=typeof change==='function'?change(document):change;if(next===document)return;document=next;listeners.forEach(listener=>listener());},
  };
}
export function useFlowDocument(initial) {
  const ref=useRef(null);
  if(!ref.current)ref.current=createFlowDocument(initial);
  const store=ref.current;
  return [useSyncExternalStore(store.subscribe,store.getSnapshot,store.getSnapshot),store.set];
}
