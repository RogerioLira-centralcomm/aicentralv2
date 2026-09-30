import {useEffect,useState} from 'react';
export function usePanelLayout(explorer,inspector,setExplorer,setInspector) {
  const [width,setWidth]=useState(window.innerWidth);
  useEffect(()=>{const resize=()=>setWidth(window.innerWidth);window.addEventListener('resize',resize);return()=>window.removeEventListener('resize',resize);},[]);
  useEffect(()=>{if(explorer&&inspector&&(width<1440||width-48-288-320<720))setExplorer(false);},[width,explorer,inspector,setExplorer]);
  return {width,explorerWidth:explorer?304:0,inspectorWidth:inspector?336:0,openExplorer:()=>{if(width<1440)setInspector(false);setExplorer(true);}};
}
