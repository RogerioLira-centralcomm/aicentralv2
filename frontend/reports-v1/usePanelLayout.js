import {useEffect,useState} from 'react';
export function usePanelLayout(explorer,inspector,setExplorer,setInspector) {
  const [width,setWidth]=useState(window.innerWidth);
  useEffect(()=>{const resize=()=>setWidth(window.innerWidth);window.addEventListener('resize',resize);return()=>window.removeEventListener('resize',resize);},[]);
  useEffect(()=>{if(explorer&&inspector)setExplorer(false);},[explorer,inspector,setExplorer]);
  return {width,explorerWidth:explorer?288:0,inspectorWidth:inspector?304:0,openExplorer:()=>{setInspector(false);setExplorer(true);}};
}
