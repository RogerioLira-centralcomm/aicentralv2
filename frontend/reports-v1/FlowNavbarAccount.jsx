import React, {useEffect, useState} from 'react';
import {CaduSolutionSwitcher} from '../cadu-design-system/components/WorkspaceSelectors';
import {VisualIdentity} from '../cadu-design-system/components/VisualIdentity';
import {workspaceSolutionItems} from '../cadu-design-system/workspaceSolutions';
import './flow-navbar-account.css';

const session = () => document.getElementById('cadu-reports-v1-root')?.dataset || {};
export function FlowSolutionSwitcher() {
  const data=session();
  const urls={workspace:data.workspaceUrl,planner:data.plannerUrl,studio:data.studioUrl,connect:location.pathname+location.search,skills:data.skillsUrl};
  const icons=Object.fromEntries(Object.entries({workspace:'cadu',planner:'planner',studio:'studio',connect:'connect',skills:'skills'}).map(([key,name])=>[key,`/static/images/cadu/products/${name}-icon.png`]));
  return <div className="flow-navbar-solutions"><CaduSolutionSwitcher logo={icons.connect} solutions={workspaceSolutionItems({urls:{solutions:urls},solutionIcons:icons})} activeId="connect" showActiveLabel overlay overlayAccent="#175cd3"/></div>;
}
export function FlowNavbarAccount() {
  const data=session(),name=data.userName||'Minha conta';
  const [usage,setUsage]=useState(null);
  useEffect(()=>{
    const controller=new AbortController();
    const refresh=async()=>{
      try {
        const response=await fetch('/workspace/api/creditos/resumo',{credentials:'same-origin',headers:{Accept:'application/json'},signal:controller.signal});
        if(!response.ok)throw new Error('Indisponível');
        const result=await response.json(),raw=result.monthly_usage_percentage;
        setUsage(raw!=null&&raw!==''&&Number.isFinite(Number(raw))?Math.max(0,Math.min(100,Number(raw))):null);
      } catch(error){if(!controller.signal.aborted)setUsage(null);}
    };
    refresh();const timer=setInterval(refresh,60000);
    return()=>{controller.abort();clearInterval(timer);};
  },[]);
  const percent=usage==null?'—':`${new Intl.NumberFormat('pt-BR',{maximumFractionDigits:1}).format(usage)}%`;
  const Profile=data.profileUrl?'a':'span',Credits=data.creditsUrl?'a':'span';
  return <div className="flow-navbar-account">
    <Profile href={data.profileUrl||undefined} className="flow-navbar-profile" title={name} aria-label={`Perfil de ${name}`}><VisualIdentity src={data.userAvatar||''} initials={name} label={name} imageAlt={`Foto de ${name}`} className="flow-navbar-avatar"/><span>{name.split(' ')[0]}</span></Profile>
    <Credits href={data.creditsUrl||undefined} className="flow-navbar-credits" title={usage==null?'Consumo de créditos indisponível':`${percent} dos créditos utilizados`} aria-label={usage==null?'Consumo de créditos indisponível':`${percent} dos créditos utilizados`}><span>{percent}</span><small>Créditos usados</small><i aria-hidden="true"><b style={{width:`${usage??0}%`}}/></i></Credits>
  </div>;
}
