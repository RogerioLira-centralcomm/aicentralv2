/* Panel geometry and timeline gestures, independent of network and render jobs. */
const $ = id => document.getElementById(id);
const prefsKey='cadu-studio-workspace-v1';
const clamp=(value,low,high)=>Math.max(low,Math.min(high,value));
let state, changed, paint, prefs={}, observer, lastRuler='', lastTimeline='', trackWidth=1;
const seconds=value => `${Math.floor(value/60)}:${String(Math.floor(value%60)).padStart(2,'0')}`;
const getVideo=()=>$('mcSwapVideo');

export function bindWorkspace(project, commit, refresh) {
  state=project;changed=commit;paint=refresh;
  try {prefs=JSON.parse(localStorage.getItem(prefsKey)||'{}');} catch {prefs={};}
  if(!prefs || typeof prefs!=='object')prefs={};
  const root=$('mcSwap');
  root.dataset.theme='dark';
  document.querySelectorAll('[data-studio-section]').forEach(button=>button.addEventListener('click',()=>{
    root.classList.remove('is-library-collapsed');$('mcStudioCollapseLibrary').setAttribute('aria-pressed','false');
    document.querySelector(`[data-lib-tab="${button.dataset.studioSection}"]`)?.click();
  }));
  document.querySelectorAll('[data-studio-panel]').forEach(button=>button.addEventListener('click',()=>{
    root.classList.remove('is-inspector-collapsed');$('mcStudioCollapseInspector').setAttribute('aria-pressed','false');
    document.querySelector(`[data-panel-tab="${button.dataset.studioPanel}"]`)?.click();
  }));
  for(const [id,className] of [['mcStudioCollapseLibrary','is-library-collapsed'],['mcStudioCollapseInspector','is-inspector-collapsed']]){
    $(id)?.addEventListener('click',()=>$(id).setAttribute('aria-pressed',String(root.classList.toggle(className))));
  }
  if ($('mcStudioTheme')) $('mcStudioTheme').hidden=true;
  $('mcStudioFocus').addEventListener('click',()=>{
    const on=root.classList.toggle('is-focus');$('mcStudioFocus').setAttribute('aria-pressed',String(on));
    $('mcStudioFocus').setAttribute('aria-label',on?'Restaurar painéis':'Ampliar área de edição');
  });
  for(const [id,key,axis,sign,min,max,initial] of [
    ['mcStudioLibraryResize','--vs-library','x',1,210,380,250],
    ['mcStudioInspectorResize','--vs-inspector','x',-1,260,420,290],
    ['mcStudioTimelineResize','--vs-timeline','y',-1,190,360,250],
  ]) {
    const handle=$(id);
    if(Number.isFinite(prefs[key]))root.style.setProperty(key,`${clamp(prefs[key],min,max)}px`);
    handle.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;
      event.preventDefault();handle.setPointerCapture(event.pointerId);root.classList.add('is-resizing');
      const at=axis==='x'?event.clientX:event.clientY;
      const value=parseFloat(getComputedStyle(root).getPropertyValue(key))||initial;
      const move=ev=>{
        const available=axis==='y'?Math.min(max,root.clientHeight-230):Math.min(max,root.clientWidth-600);
        const next=clamp(value+sign*((axis==='x'?ev.clientX:ev.clientY)-at),min,Math.max(min,available));
        root.style.setProperty(key,`${next}px`);handle.setAttribute('aria-valuenow',String(Math.round(next)));prefs[key]=next;
      };
      const end=()=>{root.classList.remove('is-resizing');handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',end);handle.removeEventListener('pointercancel',end);savePrefs();};
      handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',end);
    });
    handle.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(event.key))return;
      event.preventDefault();const value=parseFloat(getComputedStyle(root).getPropertyValue(key))||initial;
      const delta=['ArrowLeft','ArrowUp'].includes(event.key)?-10:10;
      const next=event.key==='Home'?initial:clamp(value+delta*sign,min,max);
      root.style.setProperty(key,`${next}px`);prefs[key]=next;handle.setAttribute('aria-valuenow',String(next));savePrefs();
    });
  }
  function fit(){
    if(window.innerWidth<=900){root.style.removeProperty('--vs-height');return;}
    const height=Math.max(500,Math.floor(window.innerHeight-root.getBoundingClientRect().top-4));
    if(root.style.getPropertyValue('--vs-height')!==`${height}px`)root.style.setProperty('--vs-height',`${height}px`);
  }
  observer=new ResizeObserver(()=>{fit();trackWidth=$('mcStudioClipTrack').clientWidth;paintTimelinePosition();});
  observer.observe(root);observer.observe(document.documentElement);
  window.addEventListener('resize',fit);fit();
  $('mcStudioZoom').addEventListener('input',event=>{
    $('mcStudioTrackContent').style.width=`${Number(event.target.value)*100}%`;trackWidth=$('mcStudioClipTrack').clientWidth;paintTimelinePosition();
  });
  $('mcStudioClipTrack').addEventListener('pointerdown',event=>{
    if(event.target.closest('.mc-studio-trim-handle'))return;
    seekAt(event,$('mcStudioClipTrack'));
  });
  $('mcStudioRuler').addEventListener('pointerdown',event=>seekAt(event,$('mcStudioRuler')));
  for(const [id,key] of [['mcStudioTrimInHandle','start'],['mcStudioTrimOutHandle','end']]) {
    const handle=$(id);
    handle.addEventListener('pointerdown',event=>{
      const video=getVideo();if(!Number.isFinite(video?.duration)||event.button!==0)return;
      event.preventDefault();event.stopPropagation();video.pause();handle.setPointerCapture(event.pointerId);
      const rect=$('mcStudioClipTrack').getBoundingClientRect();
      const move=ev=>{
        const at=Math.round(clamp((ev.clientX-rect.left)/rect.width,0,1)*video.duration*10)/10;
        updateTrim(key,at);paint();
      };
      const end=()=>{handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',end);handle.removeEventListener('pointercancel',end);changed();};
      handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',end);
    });
    handle.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();
      updateTrim(key,(key==='end'?(state.edit.end||getVideo()?.duration):state.edit.start)+(event.key==='ArrowLeft'?-.1:.1));changed();paint();
    });
  }
  $('mcStudioMarkIn').addEventListener('click',()=>{updateTrim('start',getVideo().currentTime);changed();paint();});
  $('mcStudioMarkOut').addEventListener('click',()=>{updateTrim('end',getVideo().currentTime);changed();paint();});
  window.addEventListener('pagehide',()=>observer?.disconnect());
}
function savePrefs(){try{localStorage.setItem(prefsKey,JSON.stringify(prefs));}catch{/* Workspace stays usable without storage. */}}
function seekAt(event,node){const video=getVideo();if(!Number.isFinite(video?.duration))return;const rect=node.getBoundingClientRect();video.currentTime=clamp((event.clientX-rect.left)/rect.width,0,1)*video.duration;}
function updateTrim(key,value){const duration=getVideo()?.duration;if(!Number.isFinite(duration))return;state.edit[key]=key==='start'?clamp(value,0,(state.edit.end||duration)-.1):clamp(value,state.edit.start+.1,duration);}
export function paintTimelinePosition(){
  if(!state || !$('mcStudioEditClip'))return;
  const video=getVideo(), duration=video?.duration, valid=Number.isFinite(duration)&&duration>0&&Boolean(video.getAttribute('src'));
  if(valid)$('mcStudioEditPlayhead').style.left=`${82+clamp(video.currentTime/duration,0,1)*trackWidth}px`;
  const signature=JSON.stringify([valid,duration,state.activeClipId,state.edit.start,state.edit.end]);
  if(signature===lastTimeline)return;lastTimeline=signature;
  $('mcStudioEditClip').hidden=!valid;$('mcStudioEditPlayhead').hidden=!valid;$('mcStudioTrackEmpty').hidden=valid;
  $('mcStudioMarkIn').disabled=!valid;$('mcStudioMarkOut').disabled=!valid;
  $('mcStudioTimelineDuration').textContent=valid?`${seconds(Math.max(0,(state.edit.end||duration)-state.edit.start))} selecionados`:'Sem clipe';
  if(!valid)return;
  const clip=state.clips.find(row=>row.id===state.activeClipId);
  $('mcStudioClipName').textContent=clip?.name||'Clipe gerado';
  $('mcStudioEditClip').style.left=`${state.edit.start/duration*100}%`;
  $('mcStudioEditClip').style.width=`${Math.max(0,(state.edit.end||duration)-state.edit.start)/duration*100}%`;
  const ruler=`${duration}`;
  if(ruler!==lastRuler){lastRuler=ruler;$('mcStudioRuler').replaceChildren(...Array.from({length:11},(_,i)=>{const span=document.createElement('span');span.textContent=(duration*i/10).toFixed(duration<10?1:0)+'s';return span;}));}
}
