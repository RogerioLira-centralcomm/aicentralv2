import {escapeHtml as esc} from './utils.js';

const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
const timecode=(value,fps=30)=>{
  const frames=Math.max(0,Math.round(Number(value||0)*fps));
  const hours=Math.floor(frames/(fps*3600));
  const minutes=Math.floor(frames/(fps*60))%60;
  const seconds=Math.floor(frames/fps)%60;
  const frame=frames%fps;
  return `${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}:${String(frame).padStart(2,'0')}`;
};
const rulerLabel=(value,pps,fps)=>{
  if(pps>=180){const seconds=Math.floor(value)%60,minutes=Math.floor(value/60);return `${minutes}:${String(seconds).padStart(2,'0')}:${String(Math.round((value%1)*fps)).padStart(2,'0')}`;}
  if(value>=60)return `${Math.floor(value/60)}:${String(Math.floor(value%60)).padStart(2,'0')}`;
  return `${Number(value.toFixed(value<10?1:0))}s`;
};

function rulerStep(pps){
  if(pps>=240)return .25;
  if(pps>=120)return .5;
  if(pps>=56)return 1;
  if(pps>=28)return 2;
  return 5;
}

function waveform(values=[],width=0,window={}){
  if(values&&!Array.isArray(values))values=width>=900?values.detail:width>=360?values.medium:values.overview;
  if(!values.length)return '';
  const sourceDuration=Math.max(.001,Number(window.sourceDuration)||Number(window.duration)||1),start=Math.max(0,Number(window.start)||0),duration=Math.max(.001,Number(window.duration)||sourceDuration);
  let safe=[];
  if(window.loop){for(let at=0;at<duration&&safe.length<4096;){const offset=(start+at)%sourceDuration,available=Math.min(duration-at,sourceDuration-offset),from=Math.floor(offset/sourceDuration*values.length),to=Math.max(from+1,Math.ceil((offset+available)/sourceDuration*values.length));safe.push(...values.slice(from,to));at+=available;}}
  else{const from=Math.floor(start/sourceDuration*values.length),to=Math.max(from+1,Math.ceil(Math.min(sourceDuration,start+duration)/sourceDuration*values.length));safe=values.slice(from,to);}
  safe=safe.map(value=>clamp(Number(value)||0,0,1));if(!safe.length)return '';
  const path=safe.map((value,index)=>{const x=index+.5,height=Math.max(3,value*82),top=50-height/2,bottom=50+height/2;return `M${x.toFixed(1)} ${top.toFixed(1)}V${bottom.toFixed(1)}`;}).join('');
  return `<svg viewBox="0 0 ${safe.length} 100" preserveAspectRatio="none" data-peaks="${safe.length}" focusable="false"><path d="${path}"></path></svg>`;
}

function envelope(points=[],duration=1){
  const rows=[{time:0,gain:1},...points,{time:duration,gain:points.at(-1)?.gain??1}]
    .map(point=>{const gain=Number(point.gain);return {time:clamp(Number(point.time)||0,0,duration),gain:clamp(Number.isFinite(gain)?gain:1,0,2)};})
    .sort((a,b)=>a.time-b.time);
  const line=rows.map(point=>`${point.time/duration*100},${100-point.gain/2*100}`).join(' ');
  return `<svg class="mc-pro-envelope" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polyline points="${line}"></polyline></svg>${points.map((point,index)=>{const gain=Number(point.gain),safeGain=Number.isFinite(gain)?gain:1;return `<button type="button" class="mc-pro-gain-point" data-gain-point="${index}" style="left:${clamp(Number(point.time)||0,0,duration)/duration*100}%;top:${100-clamp(safeGain,0,2)/2*100}%" title="Volume ${Math.round(safeGain*100)}%"></button>`;}).join('')}`;
}

function row(label,kind,content,extra=''){
  return `<div class="mc-pro-row ${extra}" data-track-kind="${kind}"><div class="mc-pro-label">${label}</div><div class="mc-pro-lane" data-timeline-seek>${content}</div></div>`;
}

export function timelineMarkup({composition,plan,duration,projectDuration=duration,selected,selectedAudio=-1,sources,sounds,zoom=1,playhead=0,minWidth=760}){
  const fps=Number(composition.fps)||30;
  const pps=64*clamp(Number(zoom)||1,1,5);
  const width=Math.max(minWidth,Math.ceil(Math.max(duration,.1)*pps));
  const step=rulerStep(pps),ticks=[];
  for(let at=0;at<=duration+.0001&&ticks.length<500;at+=step){
    const left=at*pps;
    ticks.push(`<span class="${Number.isInteger(at)?'is-major':''}" style="left:${left}px"><b>${rulerLabel(at,pps,fps)}</b></span>`);
  }
  const ruler=row('', 'ruler', ticks.join(''),'mc-pro-ruler-row');
  const clips=plan.map((entry,index)=>{
    const source=sources(entry.row),left=entry.start*pps,widthPx=Math.max(12,(entry.end-entry.start)*pps);
    const thumb=source?.thumb_url||source?.poster_url||source?.image_url||'';
    const transition=entry.overlap?`<span role="slider" tabindex="0" aria-label="Duração da transição" class="mc-pro-transition" data-transition-index="${index-1}" style="left:${left}px;width:${Math.max(12,entry.overlap*pps)}px" title="${esc(plan[index-1]?.row.transition||'Transição')} · ${entry.overlap.toFixed(2)}s">⌁</span>`:'';
    return `${transition}<div role="button" tabindex="0" draggable="true" class="mc-pro-clip ${entry.row.id===selected?'is-selected':''}" data-composition-item="${esc(entry.row.id)}" style="left:${left}px;width:${widthPx}px" title="${esc(source?.name||'Mídia')} · ${(entry.end-entry.start).toFixed(2)}s"><span role="slider" tabindex="0" class="mc-pro-trim is-in" data-timeline-trim="in" aria-label="Aparar início"></span>${thumb?`<img src="${esc(thumb)}" alt="">`:''}<strong>${index+1}. ${esc(source?.name||'Mídia')}</strong><small>${(entry.end-entry.start).toFixed(1)}s</small><span role="slider" tabindex="0" class="mc-pro-trim is-out" data-timeline-trim="out" aria-label="Aparar fim"></span></div>`;
  }).join('');
  const original=plan.map((entry,index)=>{
    const source=sources(entry.row),left=entry.start*pps,widthPx=Math.max(12,(entry.end-entry.start)*pps);
    if(entry.row.kind!=='video')return '';
    return `<div class="mc-pro-original ${entry.row.volume===0?'is-muted':''}" style="left:${left}px;width:${widthPx}px"><span class="mc-pro-waveform" aria-hidden="true">${waveform(source?.waveform_levels||source?.waveform,widthPx,{start:entry.row.in,duration:(entry.row.out||source?.duration)-entry.row.in,sourceDuration:source?.duration})}</span><small>${entry.row.volume===0?'Mudo':`Áudio ${index+1}`}</small></div>`;
  }).join('');
  const rows=[ruler,row('V1 · Vídeo','video',clips,'mc-pro-video-row'),row('A1 · Original','original',original)];
  composition.audio.forEach((track,index)=>{
    const source=sounds.find(sound=>sound.id===track.sound_id),start=Number(track.start)||0,duration=Number(track.duration)||.1,left=start*pps,widthPx=Math.max(12,duration*pps);
    const status=track.muted?'Mudo':track.solo?'Solo':'Áudio';
    rows.push(row(`A${index+2} · ${status}`,'audio',`<div role="button" tabindex="0" aria-label="Faixa ${track.name||source?.name||index+1}" class="mc-pro-audio ${track.muted?'is-muted':''} ${track.solo?'is-solo':''} ${index===selectedAudio?'is-selected':''}" data-audio-timeline="${index}" style="left:${left}px;width:${widthPx}px"><span role="slider" tabindex="0" class="mc-pro-trim is-in" data-audio-trim="in" aria-label="Aparar início do áudio"></span><span class="mc-pro-waveform" aria-hidden="true">${waveform(source?.waveform_levels||source?.waveform,widthPx,{start:track.in,duration,sourceDuration:source?.duration,loop:track.loop})}</span>${envelope(track.gain_points||[],duration)}<strong>${esc(track.name||source?.name||`Áudio ${index+1}`)}</strong><small>${start.toFixed(1)}s → ${(start+duration).toFixed(1)}s</small><span class="mc-pro-fade is-in" style="width:${Math.min(50,(Number(track.fade_in)||0)/duration*100)}%"></span><span class="mc-pro-fade is-out" style="width:${Math.min(50,(Number(track.fade_out)||0)/duration*100)}%"></span><span role="slider" tabindex="0" class="mc-pro-trim is-out" data-audio-trim="out" aria-label="Aparar fim do áudio"></span></div>`));
  });
  if(composition.captions.length){
    const captions=composition.captions.map((caption,index)=>`<button type="button" class="mc-pro-caption" data-caption-timeline="${index}" style="left:${caption.start*pps}px;width:${Math.max(8,(caption.end-caption.start)*pps)}px" title="${esc(caption.text)}">${esc(caption.text)}</button>`).join('');
    rows.push(row('CC · Legendas','captions',captions));
  }
  if(composition.autocut?.cuts?.length&&!composition.autocut.applied){
    const suggestions=composition.autocut.cuts.map((cut,index)=>`<button type="button" class="mc-pro-cut-suggestion is-${esc(cut.decision||'pending')}" data-cut-timeline="${index}" style="left:${cut.in*pps}px;width:${Math.max(8,(cut.out-cut.in)*pps)}px" title="${esc(cut.reason)} · ${(cut.out-cut.in).toFixed(2)}s">${cut.decision==='accepted'?'✓':cut.decision==='rejected'?'×':'!'}</button>`).join('');
    rows.push(row('IA · Cortes','suggestions',suggestions));
  }
  const selectedEntry=plan.find(entry=>entry.row.id===selected);
  if(selectedEntry?.row.keyframes?.length){
    const keys=selectedEntry.row.keyframes.map((key,index)=>`<button type="button" class="mc-pro-keyframe" data-keyframe-timeline="${index}" data-keyframe-owner="${esc(selected)}" style="left:${(selectedEntry.start+key.time)*pps}px" title="Keyframe ${index+1} · ${timecode(selectedEntry.start+key.time,fps)}">◆</button>`).join('');
    rows.push(row('KF · Movimento','keyframes',keys,'mc-pro-keyframe-row'));
  }
  const overflow=duration>projectDuration+.01?`<div class="mc-pro-overflow" style="left:${82+projectDuration*pps}px;width:${(duration-projectDuration)*pps}px"><span>Fora do vídeo</span></div>`:'';
  return `<div class="mc-pro-timeline" data-pps="${pps}" data-duration="${projectDuration}" data-content-duration="${duration}" data-fps="${fps}"><div class="mc-pro-toolbar"><span>${timecode(playhead,fps)}</span><span>${projectDuration.toFixed(1)}s · ${composition.items.length} itens</span><button type="button" data-timeline-fit>Ajustar projeto</button></div><div class="mc-pro-scroll"><div class="mc-pro-canvas" style="--timeline-width:${width}px;width:${width+82}px">${rows.join('')}${overflow}<div class="mc-pro-snap-guide" hidden></div><div class="mc-pro-playhead" style="left:${82+clamp(playhead,0,projectDuration)*pps}px"><span></span></div></div></div></div>`;
}

export function bindTimeline(host,actions){
  if(!host||host.dataset.timelineBound)return;
  host.dataset.timelineBound='1';
  host.addEventListener('click',event=>{
    if(event.target.closest('[data-gain-point]'))return;
    const key=event.target.closest('[data-keyframe-timeline]');
    if(key){actions.select?.(key.dataset.keyframeOwner);actions.seek?.(actions.keyframeTime?.(key.dataset.keyframeOwner,Number(key.dataset.keyframeTimeline))||0);return;}
    const caption=event.target.closest('[data-caption-timeline]');
    if(caption){actions.seek?.(actions.captionTime?.(Number(caption.dataset.captionTimeline))||0);return;}
    const cut=event.target.closest('[data-cut-timeline]');
    if(cut){actions.seek?.(actions.cutTime?.(Number(cut.dataset.cutTimeline))||0);actions.reviewCut?.(Number(cut.dataset.cutTimeline));return;}
    const transition=event.target.closest('[data-transition-index]');
    if(transition){actions.selectTransition?.(Number(transition.dataset.transitionIndex));return;}
    const audio=event.target.closest('[data-audio-timeline]');
    if(audio){actions.selectAudio?.(Number(audio.dataset.audioTimeline));return;}
    const clip=event.target.closest('[data-composition-item]');
    if(clip){actions.select?.(clip.dataset.compositionItem);return;}
    if(event.target.closest('[data-timeline-fit]')){actions.fit?.();return;}
    const lane=event.target.closest('[data-timeline-seek]');
    if(lane){
      const rect=lane.getBoundingClientRect(),pps=Number(host.querySelector('.mc-pro-timeline')?.dataset.pps)||64;
      actions.seek?.(clamp((event.clientX-rect.left)/pps,0,Number(host.querySelector('.mc-pro-timeline')?.dataset.duration)||0));
    }
  });
  host.addEventListener('dblclick',event=>{
    const audio=event.target.closest('[data-audio-timeline]');if(!audio||event.target.closest('[data-audio-trim],[data-gain-point]'))return;
    const rect=audio.getBoundingClientRect(),timeline=host.querySelector('.mc-pro-timeline'),pps=Number(timeline?.dataset.pps)||64;
    actions.addGainPoint?.(Number(audio.dataset.audioTimeline),clamp((event.clientX-rect.left)/pps,0,rect.width/pps));
  });
  host.addEventListener('pointerdown',event=>{
    if(event.button!==0)return;
    const timeline=host.querySelector('.mc-pro-timeline'),pps=Number(timeline?.dataset.pps)||64;
    const clip=event.target.closest('[data-composition-item]'),clipHandle=event.target.closest('[data-timeline-trim]');
    const audio=event.target.closest('[data-audio-timeline]'),audioHandle=event.target.closest('[data-audio-trim]');
    const keyframe=event.target.closest('[data-keyframe-timeline]'),transition=event.target.closest('[data-transition-index]'),gainPoint=event.target.closest('[data-gain-point]');
    if(!clipHandle&&!audio&&!keyframe&&!transition&&!gainPoint)return;
    const node=clipHandle||audioHandle||gainPoint||keyframe||transition||audio,visualNode=gainPoint||clip||audio||keyframe||transition,startX=event.clientX,startY=event.clientY,startLeft=parseFloat(visualNode.style.left)||0,startWidth=parseFloat(visualNode.style.width)||visualNode.offsetWidth,startLeftPx=gainPoint?startLeft/100*(audio?.clientWidth||1):startLeft;
    const edge=clipHandle?.dataset.timelineTrim||audioHandle?.dataset.audioTrim||'move';
    const update=gainPoint?actions.beginGainPoint?.(Number(audio.dataset.audioTimeline),Number(gainPoint.dataset.gainPoint)):keyframe?actions.beginKeyframe?.(keyframe.dataset.keyframeOwner,Number(keyframe.dataset.keyframeTimeline)):transition?actions.beginTransition?.(Number(transition.dataset.transitionIndex)):clip?actions.beginClipTrim?.(clip.dataset.compositionItem,edge):actions.beginAudioGesture?.(Number(audio.dataset.audioTimeline),edge);
    if(!update)return;
    event.preventDefault();event.stopPropagation();node.setPointerCapture(event.pointerId);visualNode.classList.add('is-dragging');
    const move=ev=>{
      const delta=ev.clientX-startX,result=update(delta/pps,false,{snap:!ev.shiftKey,vertical:(ev.clientY-startY)/Math.max(1,audio?.clientHeight||1)}),visualDelta=Number.isFinite(result?.delta)?result.delta*pps:delta,guide=host.querySelector('.mc-pro-snap-guide');
      if(gainPoint){visualNode.style.left=`${clamp((startLeftPx+visualDelta)/(audio.clientWidth||1)*100,0,100)}%`;visualNode.style.top=`${clamp((parseFloat(visualNode.style.top)||50)+(ev.clientY-startY)/(audio.clientHeight||1)*100,0,100)}%`;}
      else if(keyframe)visualNode.style.left=`${Math.max(0,startLeft+visualDelta)}px`;
      else if(transition)visualNode.style.width=`${Math.max(12,startWidth+delta)}px`;
      else if(edge==='in'){if(!clip)visualNode.style.left=`${Math.max(0,startLeft+visualDelta)}px`;visualNode.style.width=`${Math.max(8,startWidth-visualDelta)}px`;}
      else if(edge==='out')visualNode.style.width=`${Math.max(8,startWidth+visualDelta)}px`;
      else visualNode.style.left=`${Math.max(0,startLeft+visualDelta)}px`;
      if(guide){guide.hidden=result?.snap===undefined;if(result?.snap!==undefined)guide.style.left=`${82+result.snap*pps}px`;}
    };
    const end=ev=>{visualNode.classList.remove('is-dragging');node.removeEventListener('pointermove',move);node.removeEventListener('pointerup',end);node.removeEventListener('pointercancel',end);const endX=Number.isFinite(ev.clientX)?ev.clientX:startX,endY=Number.isFinite(ev.clientY)?ev.clientY:startY,moved=Math.hypot(endX-startX,endY-startY);update((endX-startX)/pps,true,{snap:!ev.shiftKey,vertical:(endY-startY)/Math.max(1,audio?.clientHeight||1)});if(audio&&!audioHandle&&moved<3)actions.selectAudio?.(Number(audio.dataset.audioTimeline));const guide=host.querySelector('.mc-pro-snap-guide');if(guide)guide.hidden=true;};
    node.addEventListener('pointermove',move);node.addEventListener('pointerup',end);node.addEventListener('pointercancel',end);
  });
  host.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Enter',' '].includes(event.key))return;
    const clip=event.target.closest('[data-composition-item]'),audio=event.target.closest('[data-audio-timeline]'),trim=event.target.closest('[data-timeline-trim],[data-audio-trim]'),transition=event.target.closest('[data-transition-index]'),key=event.target.closest('[data-keyframe-timeline]'),gain=event.target.closest('[data-gain-point]');
    if((event.key==='Enter'||event.key===' ')&&!trim&&!transition&&!key&&!gain){event.preventDefault();if(clip)actions.select?.(clip.dataset.compositionItem);if(audio)actions.selectAudio?.(Number(audio.dataset.audioTimeline));return;}
    if(clip&&!trim&&!transition&&!key)return;
    const horizontal=event.key==='ArrowLeft'?-1:event.key==='ArrowRight'?1:0;if(!horizontal&&!gain)return;event.preventDefault();const step=(event.shiftKey?10:1)/(Number(host.querySelector('.mc-pro-timeline')?.dataset.fps)||30);
    const update=gain?actions.beginGainPoint?.(Number(audio.dataset.audioTimeline),Number(gain.dataset.gainPoint)):key?actions.beginKeyframe?.(key.dataset.keyframeOwner,Number(key.dataset.keyframeTimeline)):transition?actions.beginTransition?.(Number(transition.dataset.transitionIndex)):clip?actions.beginClipTrim?.(clip.dataset.compositionItem,trim?.dataset.timelineTrim):actions.beginAudioGesture?.(Number(audio.dataset.audioTimeline),trim?.dataset.audioTrim||'move');
    update?.(horizontal*step,true,{snap:false,vertical:gain?(event.key==='ArrowUp'?-.05:event.key==='ArrowDown'?0.05:0):0});
  });
}

export function updateTimelinePlayhead(host,time){
  const timeline=host?.querySelector('.mc-pro-timeline'),head=host?.querySelector('.mc-pro-playhead');
  if(!timeline||!head)return;
  const pps=Number(timeline.dataset.pps)||64,duration=Number(timeline.dataset.duration)||0;
  head.style.left=`${82+clamp(time,0,duration)*pps}px`;
  const label=host.querySelector('.mc-pro-toolbar span');if(label)label.textContent=timecode(time,Number(timeline.dataset.fps)||30);
}
