import {bindCaptionStyle,paintCaptionStyle} from './caption-style.js';
import {deliveryOptions,downloadExport,beginDownload,updateDownload} from './delivery.js';
import {paintLivePreview,previewTime,seekLivePreview,schedule} from './live-preview.js';
import {keyframeEditor,bindKeyframes,valuesAt} from './keyframes.js';
import {timelineMarkup,bindTimeline,updateTimelinePlayhead} from './timeline.js';
import {mediaTask} from './media-tasks.js';
import {state} from './state.js';
import {get,post,studioApi} from './api.js?v=2';
import {escapeHtml as esc,newId} from './utils.js';
import {showProcessing,updateProcessing,notify} from '../media-progress.js';
const $=id=>document.getElementById(id),base=studioApi;
let dirty,refresh,signature='',dragId='',rendering=false,timelineZoom=1,snapEnabled=true;
export const emptyComposition=()=>({enabled:false,items:[],audio:[],captions:[],selected:'',selected_audio:-1,resolution:720,fps:30,preview_url:'',preview_valid:false});
const comp=()=>state.composition ||= emptyComposition();
const fingerprint=()=>JSON.stringify({items:comp().items,audio:comp().audio,captions:comp().captions,caption_style:comp().caption_style,resolution:comp().resolution,fps:comp().fps,ratio:state.aspectRatio,layers:state.edit?.layers||[]});
const item=()=>comp().items.find(row=>row.id===comp().selected);
const asset=row=>(row?.kind==='image'?state.library:state.clips).find(source=>source.id===row?.asset_id);
const length=row=>row.kind==='image'?row.duration:Math.max(.1,((row.out||asset(row)?.duration||4)-row.in)/row.speed);
const timelineDuration=()=>Math.max(compositionDuration(),...comp().audio.map(row=>(Number(row.start)||0)+(Number(row.duration)||0)),...comp().captions.map(row=>Number(row.end)||0));
function gainAt(points,time){if(!points?.length)return 1;const rows=[...points].sort((a,b)=>a.time-b.time);if(time<=rows[0].time)return rows[0].gain;for(let i=1;i<rows.length;i++)if(time<rows[i].time){const a=rows[i-1],b=rows[i],p=(time-a.time)/Math.max(.001,b.time-a.time);return a.gain+(b.gain-a.gain)*p;}return rows.at(-1).gain;}
function splitFrames(frames=[],at=0){if(!frames.length)return [[],[]];const keys=['x','y','scale','rotation','opacity'],value=valuesAt(frames,at),boundary=Object.fromEntries(keys.map(key=>[key,Number(value[key])])),ease=value.ease||'linear';return [[...frames.filter(row=>row.time<at).map(row=>structuredClone(row)),{...boundary,time:at,ease}],[{...boundary,time:0,ease},...frames.filter(row=>row.time>at).map(row=>({...structuredClone(row),time:row.time-at}))]];}
function mapCutTime(time,cuts){let removed=0;for(const cut of cuts){if(time>=cut.out)removed+=cut.out-cut.in;else if(time>cut.in)return Math.max(0,cut.in-removed);else break;}return Math.max(0,time-removed);}
function rippleCaption(row,start,end){
  const gap=end-start,captionStart=Number(row.start)||0,captionEnd=Number(row.end)||0;
  if(captionEnd<=start)return row;
  if(captionStart>=end)return {...row,start:captionStart-gap,end:captionEnd-gap};
  if(captionStart>=start&&captionEnd<=end)return null;
  if(captionStart<start&&captionEnd>end)return {...row,end:captionEnd-gap};
  if(captionStart<start)return {...row,end:start};
  return {...row,start,end:captionEnd-gap};
}
function shiftFollowing(boundary,delta){
  if(Math.abs(delta)<.0001)return;
  const c=comp();
  c.audio.forEach(track=>{
    if(track.ripple===false||(Number(track.start)||0)<boundary-.0001)return;
    track.start=Math.max(0,(Number(track.start)||0)+delta);
    if(Number.isFinite(Number(track.sync_origin)))track.sync_origin=Math.max(0,Number(track.sync_origin)+delta);
  });
  c.captions=c.captions.map(caption=>{
    if((Number(caption.start)||0)<boundary-.0001)return caption;
    return {...caption,start:Math.max(0,caption.start+delta),end:Math.max(.03,caption.end+delta)};
  });
}
function rippleDelete(row){
  const c=comp(),before=schedule(c.items),entry=before.find(planRow=>planRow.row.id===row.id),index=c.items.indexOf(row);
  if(index<0||!entry)return false;
  const durationBefore=compositionDuration();
  if(index>0)c.items[index-1].transition='cut';
  c.items.splice(index,1);
  const durationAfter=compositionDuration(),gap=Math.max(0,durationBefore-durationAfter),start=entry.start,end=start+gap;
  if(gap>.0001){
    c.audio.forEach(track=>{
      if(track.ripple===false)return;
      const originalStart=Number(track.start)||0,shift=Math.min(gap,Math.max(0,originalStart-start));
      if(shift<=0)return;
      track.start=Math.max(0,originalStart-shift);
      if(Number.isFinite(Number(track.sync_origin)))track.sync_origin=Math.max(0,Number(track.sync_origin)-shift);
    });
    c.captions=c.captions.map(caption=>rippleCaption(caption,start,end)).filter(caption=>caption&&caption.end-caption.start>=.03);
  }
  c.selected=c.items[Math.min(index,c.items.length-1)]?.id||'';
  c.selected_audio=-1;
  seekLivePreview(Math.min(start,durationAfter));
  return true;
}
function makeSnapper(exclude=[]){
  const plan=schedule(comp().items),targets=[0,previewTime(),compositionDuration(),...plan.flatMap(entry=>[entry.start,entry.end]),...comp().captions.flatMap(row=>[row.start,row.end])].filter(point=>Number.isFinite(point)&&!exclude.some(skip=>Math.abs(skip-point)<.0001));
  return (value,options={})=>{if(!snapEnabled||options.snap===false)return {value};const closest=targets.reduce((best,point)=>Math.abs(point-value)<Math.abs(best-value)?point:best,Infinity),tolerance=8/(64*timelineZoom);return Number.isFinite(closest)&&Math.abs(closest-value)<=tolerance?{value:closest,snap:closest}:{value};};
}
export function compositionDuration(){return comp().items.reduce((total,row,index)=>total+length(row)-(index&&comp().items[index-1].transition!=='cut'?Math.min(comp().items[index-1].transition_duration,length(row)/2,length(comp().items[index-1])/2):0),0);}
function changed(){comp().preview_valid=false;dirty();paintComposition();paintCompositionCanvas();}
export function bindComposition(commit,paint){
  dirty=commit;refresh=paint;
  const tracks=$('mcCompositionTracks');
  bindTimeline(tracks,{
    select:id=>{if(!comp().items.some(row=>row.id===id))return;comp().selected=id;comp().selected_audio=-1;comp().preview_valid=false;paintComposition();paintCompositionCanvas();},
    selectAudio:index=>{if(!comp().audio[index])return;comp().selected_audio=index;signature='';const panel=$('mcCompositionAudio')?.closest('details');if(panel)panel.open=true;paintComposition();},
    seek:time=>seekLivePreview(time),
    keyframeTime:(id,index)=>{const entry=schedule(comp().items).find(row=>row.row.id===id);return (entry?.start||0)+(entry?.row.keyframes?.[index]?.time||0);},
    captionTime:index=>comp().captions[index]?.start||0,
    cutTime:index=>comp().autocut?.cuts?.[index]?.in||0,
    reviewCut:index=>{comp().autocut.selected=index;signature='';paintComposition();},
    selectTransition:index=>{const row=comp().items[index];if(row){comp().selected=row.id;signature='';paintComposition();}},
    beginClipTrim:(id,edge)=>{
      const row=comp().items.find(entry=>entry.id===id);if(!row)return null;
      const source=asset(row),original={in:Number(row.in)||0,out:Number(row.out)||Number(source?.duration)||Number(row.duration)||4,duration:Number(row.duration)||4},originalLength=length(row);
      const index=comp().items.indexOf(row),next=comp().items[index+1],entry=schedule(comp().items).find(planRow=>planRow.row.id===id),nextStart=schedule(comp().items).find(planRow=>planRow.row.id===next?.id)?.start,baseEnd=entry?.end||length(row),snap=makeSnapper([baseEnd]);
      return (delta,done,options)=>{
        const target=snap(baseEnd+(edge==='out'?delta:-delta),options),applied=edge==='out'?target.value-baseEnd:baseEnd-target.value;
        if(row.kind==='image')row.duration=Math.max(.2,original.duration+(edge==='out'?applied:-applied));
        else if(edge==='in')row.in=Math.max(0,Math.min(original.out-.1,original.in+applied*row.speed));
        else row.out=Math.max(original.in+.1,Math.min(Number(source?.duration)||300,original.out+applied*row.speed));
        const visualDelta=edge==='in'?originalLength-length(row):length(row)-originalLength;comp().preview_valid=false;if(done){if(next&&Number.isFinite(nextStart)){const moved=schedule(comp().items).find(planRow=>planRow.row.id===next.id)?.start-nextStart;shiftFollowing(nextStart,moved);}signature='';changed();}return {delta:visualDelta,...(target.snap===undefined?{}:{snap:target.snap})};
      };
    },
    beginAudioGesture:(index,edge)=>{
      const row=comp().audio[index];if(!row)return null;
      const original={start:Number(row.start)||0,in:Number(row.in)||0,duration:Number(row.duration)||.1};
      const baseBoundary=edge==='out'?original.start+original.duration:original.start,snap=makeSnapper([baseBoundary]);
      return (delta,done,options)=>{
        const boundary=baseBoundary+delta,target=snap(boundary,options),applied=target.value-baseBoundary;
        if(edge==='move')row.start=Math.max(0,original.start+applied);
        if(edge==='in'){const trim=Math.max(-original.in,Math.min(original.duration-.1,applied));row.start=Math.max(0,original.start+trim);row.in=Math.max(0,original.in+trim);row.duration=Math.max(.1,original.duration-trim);}
        if(edge==='out')row.duration=Math.max(.1,original.duration+applied);
        const visualDelta=edge==='out'?row.duration-original.duration:row.start-original.start;comp().preview_valid=false;if(done){signature='';changed();}return {delta:visualDelta,...(target.snap===undefined?{}:{snap:target.snap})};
      };
    },
    beginKeyframe:(id,index)=>{
      const row=comp().items.find(entry=>entry.id===id),key=row?.keyframes?.[index];if(!row||!key)return null;
      const original=Number(key.time)||0,limit=length(row);
      const entry=schedule(comp().items).find(planRow=>planRow.row.id===id),start=entry?.start||0,snap=makeSnapper([start+original]);
      return (delta,done,options)=>{const target=snap(start+original+delta,options);key.time=Math.round(Math.max(0,Math.min(limit,target.value-start))*1000)/1000;comp().preview_valid=false;if(done){row.keyframes.sort((a,b)=>a.time-b.time);signature='';changed();}return {delta:key.time-original,...(target.snap===undefined?{}:{snap:target.snap})};};
    },
    addGainPoint:(index,time)=>{const row=comp().audio[index];if(!row||(row.gain_points?.length||0)>=32)return;row.gain_points||=[];row.gain_points.push({time:Math.round(time*1000)/1000,gain:1});row.gain_points.sort((a,b)=>a.time-b.time);changed();},
    beginGainPoint:(trackIndex,pointIndex)=>{
      const row=comp().audio[trackIndex],point=row?.gain_points?.[pointIndex];if(!row||!point)return null;
      const gain=Number(point.gain),original={time:Number(point.time)||0,gain:Number.isFinite(gain)?gain:1},snap=makeSnapper([row.start+(Number(point.time)||0)]);
      return (delta,done,options)=>{const target=snap(row.start+original.time+delta,options);point.time=Math.round(Math.max(0,Math.min(row.duration,target.value-row.start))*1000)/1000;point.gain=Math.round(Math.max(0,Math.min(2,original.gain-(options.vertical||0)*2))*100)/100;comp().preview_valid=false;if(done){row.gain_points.sort((a,b)=>a.time-b.time);signature='';changed();}return {delta:point.time-original.time,...(target.snap===undefined?{}:{snap:target.snap})};};
    },
    beginTransition:index=>{
      const row=comp().items[index],next=comp().items[index+1];if(!row||!next)return null;
      const original=Number(row.transition_duration)||.1,limit=Math.min(2,length(row)/2,length(next)/2);
      return (delta,done)=>{row.transition_duration=Math.round(Math.max(.05,Math.min(limit,original+delta))*1000)/1000;comp().preview_valid=false;if(done){signature='';changed();}};
    },
    fit:()=>{const input=$('mcStudioZoom'),available=Math.max(320,tracks?.clientWidth-96||760),duration=Math.max(.1,compositionDuration());timelineZoom=Math.max(1,Math.min(5,available/(duration*64)));if(input)input.value=String(timelineZoom);signature='';paintComposition();}
  });
  $('mcStudioZoom')?.addEventListener('input',event=>{timelineZoom=Number(event.target.value)||1;signature='';paintComposition();});
  document.addEventListener('cadu:preview-time',event=>updateTimelinePlayhead(tracks,Number(event.detail)||0));
  const triggerAction=action=>$('mcCompositionControls')?.querySelector(`[data-compose-action="${action}"]`)?.click();
  $('mcTimelineSplit')?.addEventListener('click',()=>triggerAction('split'));
  $('mcTimelineRemove')?.addEventListener('click',()=>triggerAction('ripple'));
  $('mcTimelineSnap')?.addEventListener('click',()=>{snapEnabled=!snapEnabled;paintSnapButton();});
  document.addEventListener('keydown',event=>{
    if(!comp().enabled||event.ctrlKey||event.metaKey||event.altKey||event.target.closest('input,textarea,select,[contenteditable]'))return;
    if(event.key.toLowerCase()==='s'){event.preventDefault();triggerAction('split');}
    if(event.key.toLowerCase()==='n'){event.preventDefault();snapEnabled=!snapEnabled;paintSnapButton();}
    if((event.key==='Delete'||event.key==='Backspace')&&item()){event.preventDefault();triggerAction(event.shiftKey?'ripple':'delete');}
  });
  bindCaptionStyle(comp,changed);
  document.addEventListener('cadu:apply-autocut',event=>{
    const source=event.detail,analysis=source.autocut;if(!analysis)return;
    if(!comp().items.length){comp().items=[{id:newId(),asset_id:source.id,kind:'video',in:0,out:analysis.duration,duration:analysis.duration,speed:1,volume:1,fit:'contain',motion:'none',transition:'cut',transition_duration:.1}];comp().selected=comp().items[0].id;}
    comp().autocut={asset_id:source.id,...structuredClone(analysis),cuts:analysis.cuts.map(cut=>({...cut,decision:'pending'})),applied:false,selected:0,original:{items:structuredClone(comp().items),audio:structuredClone(comp().audio),captions:structuredClone(comp().captions),selected:comp().selected,selected_audio:comp().selected_audio}};
    comp().enabled=true;changed();refresh();seekLivePreview(0);
  });
  $('mcCompositionControls')?.addEventListener('click',event=>{
    const a=comp().autocut;
    if(!a)return;
    if(event.target.dataset.cutJump!==undefined){seekLivePreview(a.cuts[Number(event.target.dataset.cutJump)]?.in||0);}
    if(event.target.dataset.cutDecision!==undefined){const cut=a.cuts[Number(event.target.dataset.cutDecision)];if(cut){cut.decision=event.target.dataset.decision;changed();}}
    if(event.target.hasAttribute('data-accept-safe')){a.cuts.forEach(cut=>{if(cut.confidence>=.99)cut.decision='accepted';});changed();}
    if(event.target.hasAttribute('data-reject-all')){a.cuts.forEach(cut=>cut.decision='rejected');changed();}
    if(event.target.hasAttribute('data-apply-autocut')){const accepted=a.cuts.filter(cut=>cut.decision==='accepted');if(!accepted.length){notify('Aceite pelo menos uma sugestão antes de aplicar.');return;}rebuildAutoCuts(accepted);}
    if(event.target.hasAttribute('data-restore-all')){restoreAutoCutOriginal();}
  });
  bindKeyframes($('mcCompositionControls'),()=>item(),changed,row=>Math.max(0,previewTime()-(schedule(comp().items).find(r=>r.row.id===row.id)?.start||0)));
  $('mcCompositionMode')?.addEventListener('click',()=>{comp().enabled=!comp().enabled;dirty();refresh();paintComposition();});
  $('mcCompositionAdd')?.addEventListener('click',()=>{
    const value=$('mcCompositionAsset').value;const kind=value.startsWith('image:')?'image':'video',id=value.slice(kind.length+1);
    const source=(kind==='image'?state.library:state.clips).find(row=>row.id===id);if(!source||comp().items.length>=120)return;
    const row={id:newId(),asset_id:id,kind,in:0,out:Number(source.duration)||0,duration:4,speed:1,volume:1,fit:'contain',motion:'none',transition:'cut',transition_duration:.4};
    comp().items.push(row);comp().selected=row.id;comp().enabled=true;changed();refresh();seekLivePreview(schedule(comp().items).find(r=>r.row.id===row.id)?.start||0);
  });
  tracks?.addEventListener('click',event=>{
    const button=event.target.closest('[data-composition-item]');if(!button)return;
    comp().selected=button.dataset.compositionItem;comp().preview_valid=false;paintComposition();paintCompositionCanvas();seekLivePreview(schedule(comp().items).find(r=>r.row.id===comp().selected)?.start||0);
  });
  tracks?.addEventListener('dragstart',event=>{dragId=event.target.closest('[data-composition-item]')?.dataset.compositionItem||'';});
  tracks?.addEventListener('dragover',event=>event.preventDefault());
  tracks?.addEventListener('drop',event=>{
    event.preventDefault();const target=event.target.closest('[data-composition-item]')?.dataset.compositionItem;
    const from=comp().items.findIndex(row=>row.id===dragId),to=comp().items.findIndex(row=>row.id===target);
    if(from>=0&&to>=0){const [row]=comp().items.splice(from,1);comp().items.splice(to,0,row);changed();}
  });
  $('mcCompositionControls')?.addEventListener('change',event=>{
    const input=event.target,row=item(),key=input.dataset.composeKey;if(!row||!key)return;
    if(key==='voice_amount'){row.voice={preset:row.voice?.preset||'clean',amount:Math.max(0,Math.min(1,Number(input.value)||0))};changed();return;}
    if(key==='voice'){row.voice={preset:input.value,amount:.5};changed();return;}
    row[key]=input.type==='number'?Math.min(Number(input.max),Math.max(Number(input.min),Number(input.value)||0)):input.value;changed();
  });
  $('mcCompositionControls')?.addEventListener('click',event=>{
    const action=event.target.dataset.composeAction,row=item();if(!action||!row)return;
    const index=comp().items.indexOf(row);
    if(action==='delete'){comp().items.splice(index,1);comp().selected=comp().items[Math.min(index,comp().items.length-1)]?.id||'';}
    if(action==='ripple'){if(rippleDelete(row))changed();return;}
    if(action==='duplicate'&&comp().items.length<120){const copy={...structuredClone(row),id:newId()};comp().items.splice(index+1,0,copy);comp().selected=copy.id;}
    if(action==='split'&&comp().items.length<120){
      const copy={...structuredClone(row),id:newId()};let local;
      if(row.kind==='image'){if(row.duration<.4)return;local=row.duration/2;row.duration=local;copy.duration=local;}
      else{const end=row.out||asset(row)?.duration,at=row.in+Math.max(0,(comp().preview_valid?$('mcSwapVideo').currentTime:previewTime())-(schedule(comp().items).find(r=>r.row.id===row.id)?.start||0))*row.speed;if(!(at>row.in+.1&&at<end-.1)){notify('Posicione a reprodução dentro do clipe para dividir.');return;}local=(at-row.in)/row.speed;row.out=at;copy.in=at;copy.out=end;}
      [row.keyframes,copy.keyframes]=splitFrames(row.keyframes,local);
      row.transition='cut';comp().items.splice(index+1,0,copy);comp().selected=copy.id;
    }
    if(action==='before'&&index>0){comp().items.splice(index,1);comp().items.splice(index-1,0,row);}
    if(action==='after'&&index<comp().items.length-1){comp().items.splice(index,1);comp().items.splice(index+1,0,row);}
    changed();
  });
  document.addEventListener('cadu:composition-sound',event=>{
    if(comp().audio.length>=8){notify('A montagem aceita até oito faixas adicionais.');return;}
    const row=event.detail;comp().audio.push({sound_id:row.id,name:row.name,start:0,sync_origin:0,in:0,duration:Math.min(row.duration||10,compositionDuration()||10),volume:.35,muted:false,solo:false,ripple:true,fade_in:0,fade_out:0,loop:false,gain_points:[]});changed();
  });
  $('mcCompositionAudio')?.addEventListener('change',event=>{
    if(event.target.dataset.gainKey){const row=comp().audio[Number(event.target.dataset.audioIndex)],point=row?.gain_points?.[Number(event.target.dataset.gainIndex)],key=event.target.dataset.gainKey;if(point){point[key]=Math.max(Number(event.target.min),Math.min(Number(event.target.max),Number(event.target.value)||0));row.gain_points.sort((a,b)=>a.time-b.time);changed();}return;}
    const input=event.target,row=comp().audio[Number(input.dataset.audioIndex)],key=input.dataset.audioKey;if(!row||!key)return;
    if(key==='voice_amount'){row.voice={preset:row.voice?.preset||'clean',amount:Math.max(0,Math.min(1,Number(input.value)||0))};changed();return;}
    if(key==='voice'){row.voice={preset:input.value,amount:.5};changed();return;}
    row[key]=input.type==='checkbox'?input.checked:Math.min(Number(input.max),Math.max(Number(input.min),Number(input.value)||0));changed();
  });
  $('mcCompositionAudio')?.addEventListener('click',event=>{
    const remove=event.target.dataset.audioRemove,split=event.target.dataset.audioSplit,sync=event.target.dataset.audioSync,restore=event.target.dataset.audioRestoreSync,gainAdd=event.target.dataset.gainAdd,gainRemove=event.target.dataset.gainRemove;
    if(remove!==undefined){comp().audio.splice(Number(remove),1);changed();return;}
    if(split!==undefined){
      const index=Number(split),row=comp().audio[index],at=previewTime(),end=row?(Number(row.start)+Number(row.duration)):0;
      if(!row||at<=row.start+.1||at>=end-.1){notify('Posicione a reprodução dentro da faixa para dividir.');return;}
      const firstDuration=at-row.start,points=row.gain_points||[],boundary=gainAt(points,firstDuration),copy={...structuredClone(row),start:at,sync_origin:at,in:(Number(row.in)||0)+firstDuration,duration:end-at,gain_points:[{time:0,gain:boundary},...points.filter(point=>point.time>firstDuration).map(point=>({...point,time:point.time-firstDuration}))]};row.duration=firstDuration;row.gain_points=[...points.filter(point=>point.time<firstDuration),{time:firstDuration,gain:boundary}];comp().audio.splice(index+1,0,copy);changed();return;
    }
    if(sync!==undefined){const row=comp().audio[Number(sync)];if(row){row.start=Math.max(0,previewTime());changed();}return;}
    if(restore!==undefined){const row=comp().audio[Number(restore)];if(row){row.start=Number(row.sync_origin)||0;changed();}return;}
    if(gainAdd!==undefined){const row=comp().audio[Number(gainAdd)];if(row){const time=Math.max(0,Math.min(row.duration,previewTime()-row.start));row.gain_points||=[];if(row.gain_points.length<32){row.gain_points.push({time:Math.round(time*1000)/1000,gain:1});row.gain_points.sort((a,b)=>a.time-b.time);changed();}}return;}
    if(gainRemove!==undefined){const [trackIndex,pointIndex]=gainRemove.split(':').map(Number),row=comp().audio[trackIndex];if(row){row.gain_points.splice(pointIndex,1);changed();}}
  });
  $('mcCompositionResolution')?.addEventListener('change',event=>{comp().resolution=Number(event.target.value);changed();});
  $('mcCompositionFps')?.addEventListener('change',event=>{comp().fps=Number(event.target.value);changed();});
  $('mcCompositionPreview')?.addEventListener('click',()=>exportComposition(true));
  $('mcCompositionCaptionFile')?.addEventListener('change',async event=>{
    const file=event.target.files?.[0];event.target.value='';if(!file)return;
    if(file.size>1024*1024){notify('Envie um SRT de até 1 MB.');return;}
    try{comp().captions=parseSrt(await file.text());changed();}catch(error){notify(error.message);}
  });
  $('mcCompositionCaptions')?.addEventListener('change',event=>{const input=event.target,row=comp().captions[Number(input.dataset.caption)],key=input.dataset.captionKey;if(!row||!key)return;row[key]=key==='text'?input.value:Number(input.value);changed();});
  $('mcCompositionTranscribe')?.addEventListener('click',async event=>{
    if(!comp().items.length){notify('Adicione imagens e vídeos antes de transcrever.');return;}
    const button=event.currentTarget,client=state.clientId,before=fingerprint();button.disabled=true;
    try{
      const result=await mediaTask('transcribe',{client_id:client,composition:{...structuredClone(comp()),ratio:state.aspectRatio}},{overlay:true,title:'Transcrevendo áudio da montagem'});
      if(client!==state.clientId)return;
      if(before!==fingerprint()){notify('A montagem mudou durante a transcrição. As legendas estão salvas em Renderizações; gere novamente para os novos tempos.');return;}
      comp().captions=result.captions;changed();notify(result.captions.length?'Legendas geradas. Revise os nomes e a pontuação.':'Nenhuma fala reconhecida neste áudio.');
    }catch(error){notify(error.message);}finally{button.disabled=false;}
  });
  $('mcCompositionCaptions')?.addEventListener('click',event=>{const index=event.target.dataset.captionRemove;if(index!==undefined){comp().captions.splice(Number(index),1);changed();}});
  $('mcCompositionCaptionAdd')?.addEventListener('click',()=>{if(comp().captions.length<500){comp().captions.push({start:0,end:3,text:'Nova legenda'});changed();}});
  $('mcCompositionCaptionDownload')?.addEventListener('click',()=>{
    const url=URL.createObjectURL(new Blob([toSrt(comp().captions)],{type:'application/x-subrip;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='legendas.srt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
}
function rebuildAutoCuts(cuts){
  const c=comp(),a=c.autocut;if(!a)return;
  const chosen=[...(cuts||a.cuts.filter(cut=>cut.decision==='accepted'))].sort((left,right)=>left.in-right.in),merged=[];
  for(const cut of chosen){const previous=merged.at(-1);if(previous&&cut.in<=previous.out)previous.out=Math.max(previous.out,cut.out);else merged.push({...cut});}
  a.original={items:structuredClone(c.items),audio:structuredClone(c.audio),captions:structuredClone(c.captions),selected:c.selected,selected_audio:c.selected_audio};
  const kept=[];let cursor=0;
  for(const cut of merged){if(cut.in>cursor+.1)kept.push({start:cursor,end:cut.in,cutAfter:cut});cursor=Math.max(cursor,cut.out);}
  if(a.duration>cursor+.1)kept.push({start:cursor,end:a.duration,cutAfter:null});
  c.items=kept.map(segment=>({id:newId(),asset_id:a.asset_id,kind:'video',in:segment.start,out:segment.end,duration:segment.end-segment.start,speed:1,volume:1,fit:'contain',motion:'none',transition:segment.cutAfter?.reason==='Pausa'?a.options.transition:'cut',transition_duration:segment.cutAfter?.reason==='Pausa'?Math.min(a.options.transition_duration,a.options.mode==='aggressive'?.05:.1):.1}));
  c.audio=a.original.audio.map(track=>{const start=mapCutTime(track.start,merged),end=mapCutTime(track.start+track.duration,merged);return {...structuredClone(track),start,duration:Math.max(.1,end-start)};});
  c.captions=a.original.captions.map(caption=>({...structuredClone(caption),start:mapCutTime(caption.start,merged),end:mapCutTime(caption.end,merged)})).filter(caption=>caption.end>caption.start+.02);
  a.applied=true;c.selected=c.items[0]?.id||'';c.selected_audio=-1;c.enabled=true;
  changed();refresh();seekLivePreview(0);
}
function restoreAutoCutOriginal(){
  const c=comp(),a=c.autocut;if(!a)return;
  const original=a.original;
  if(original){c.items=structuredClone(original.items);c.audio=structuredClone(original.audio);c.captions=structuredClone(original.captions);c.selected=original.selected||c.items[0]?.id||'';c.selected_audio=Number.isInteger(original.selected_audio)?original.selected_audio:-1;}
  else{c.items=[{id:newId(),asset_id:a.asset_id,kind:'video',in:0,out:a.duration,duration:a.duration,speed:1,volume:1,fit:'contain',motion:'none',transition:'cut',transition_duration:.1}];c.selected=c.items[0].id;}
  a.applied=false;if(!original)c.selected_audio=-1;changed();refresh();seekLivePreview(0);
}
function paintSnapButton(){const button=$('mcTimelineSnap');if(button){button.setAttribute('aria-pressed',String(snapEnabled));button.textContent=snapEnabled?'Ímã ligado':'Ímã desligado';}}
function voiceControl(row,index){return `<label>Melhorar voz<select ${index===undefined?'data-compose-key="voice"':`data-audio-index="${index}" data-audio-key="voice"`}>${[['off','Original'],['clean','Voz limpa'],['warm','Voz encorpada'],['denoise','Reduzir ruído']].map(([v,t])=>`<option value="${v}" ${(row.voice?.preset||'off')===v?'selected':''}>${t}</option>`).join('')}</select></label><label>Intensidade<input type="number" min="0" max="1" step=".1" value="${row.voice?.amount??.5}" ${index===undefined?'data-compose-key="voice_amount"':`data-audio-index="${index}" data-audio-key="voice_amount"`}></label><small>Use “Renderizar prévia da montagem” para ouvir o tratamento aplicado na exportação.</small>`;}
function number(key,label,value,min,max,step='.1',extra=''){return `<label>${label}<input type="number" min="${min}" max="${max}" step="${step}" value="${Number(value)||0}" ${extra||`data-compose-key="${key}"`}></label>`;}
export function paintComposition(){
  if(!$('mcCompositionTracks'))return;
  paintCaptionStyle();
  const c=comp(),row=item();if(c.preview_valid&&c.preview_signature!==fingerprint())c.preview_valid=false;$('mcCompositionMode').setAttribute('aria-pressed',String(c.enabled));$('mcCompositionMode').textContent=c.enabled?'Timeline ativa':'Ativar montagem';
  if($('mcTimelineSplit'))$('mcTimelineSplit').disabled=!c.enabled||!row;
  if($('mcTimelineRemove'))$('mcTimelineRemove').disabled=!c.enabled||!row;
  paintSnapButton();
  $('mcSwap').classList.toggle('is-composition',c.enabled);$('mcCompositionTracks').hidden=!c.enabled;
  const selectedAsset=$('mcCompositionAsset').value;
  $('mcCompositionAsset').innerHTML=[...state.clips.map(row=>`<option value="video:${esc(row.id)}">Vídeo · ${esc(row.name)}</option>`),...state.library.filter(row=>!row.broken).map(row=>`<option value="image:${esc(row.id)}">Imagem · ${esc(row.name)}</option>`)].join('');
  if([...$('mcCompositionAsset').options].some(option=>option.value===selectedAsset))$('mcCompositionAsset').value=selectedAsset;
  const key=JSON.stringify([c,state.aspectRatio,state.clips.map(r=>r.id),state.library.map(r=>r.id)]);if(key===signature)return;signature=key;
  $('mcCompositionDuration').textContent=`${compositionDuration().toFixed(1)}s · ${c.items.length} itens${c.preview_valid?' · Prévia atualizada':' · Prévia instantânea'}`;
  const plan=schedule(c.items);
  $('mcCompositionTracks').innerHTML=timelineMarkup({composition:c,plan,duration:timelineDuration(),projectDuration:compositionDuration(),selected:c.selected,selectedAudio:Number(c.selected_audio),sources:asset,sounds:state.sounds||[],zoom:timelineZoom,playhead:previewTime(),minWidth:Math.max(520,$('mcCompositionTracks').clientWidth-96)});
  const select=(key,label,values)=>`<label>${label}<select data-compose-key="${key}">${values.map(([value,text])=>`<option value="${value}" ${row?.[key]===value?'selected':''}>${text}</option>`).join('')}</select></label>`;
  $('mcCompositionControls').innerHTML=row?`<h4>${esc(asset(row)?.name||'Item selecionado')}</h4><div class="mc-studio-pair">${row.kind==='image'?number('duration','Duração (s)',row.duration,.2,300):number('in','Entrada (s)',row.in,0,300)+number('out','Saída (s)',row.out,0,300)+number('speed','Velocidade',row.speed,.25,4,'.25')}${number('volume','Volume original',row.volume,0,1,'.05')}</div>${select('fit','Enquadramento',[['contain','Caber sem cortar'],['cover','Preencher com corte central']])}${row.kind==='image'?select('motion','Animação da imagem',[['none','Fixa'],['zoom','Zoom suave']]):''}${select('transition','Próxima cena',[['cut','Corte'],['fade','Dissolver'],['fadeblack','Passar pelo preto'],['slideleft','Deslizar'],['wipeleft','Revelar']])}${number('transition_duration','Duração da transição',row.transition_duration,.05,2)}${voiceControl(row)}${keyframeEditor(row.keyframes)}<div class="mc-composition-actions">${[['split','Dividir'],['duplicate','Duplicar'],['before','Antes'],['after','Depois'],['delete','Excluir'],['ripple','Remover e fechar']].map(([a,t])=>`<button type="button" data-compose-action="${a}">${t}</button>`).join('')}</div>`:'<p>Adicione e selecione uma mídia na sequência.</p>';
  if(c.autocut){const accepted=c.autocut.cuts.filter(cut=>cut.decision==='accepted').length;$('mcCompositionControls').insertAdjacentHTML('beforeend',`<details open class="mc-cut-review"><summary>${c.autocut.applied?'Cortes aplicados':'Revisar sugestões'} · ${c.autocut.cuts.length}</summary><p>${c.autocut.applied?'A montagem usa os cortes aceitos. Restaure o original para revisar novamente.':`${accepted} aceitos · ${(c.autocut.removed_duration||0).toFixed(1)}s sugeridos. Ouça cada região antes de aplicar.`}</p>${c.autocut.options.transition!=='cut'?'<p>Transições curtas nas pausas; corte seco nas hesitações para preservar palavras.</p>':''}${c.autocut.cuts.map((cut,i)=>`<div class="mc-cut-review-row ${cut.decision==='accepted'?'is-accepted':cut.decision==='rejected'?'is-rejected':''}"><button type="button" data-cut-jump="${i}">${cut.in.toFixed(2)}–${cut.out.toFixed(2)}s · ${esc(cut.reason)}</button>${!c.autocut.applied?`<button type="button" data-cut-decision="${i}" data-decision="accepted">Aceitar</button><button type="button" data-cut-decision="${i}" data-decision="rejected">Ignorar</button>`:''}</div>`).join('')}${!c.autocut.applied?'<div class="mc-cut-review-actions"><button type="button" data-accept-safe>Aceitar seguras</button><button type="button" data-reject-all>Ignorar todas</button><button type="button" data-apply-autocut>Aplicar cortes aceitos</button></div>':''}<button type="button" data-restore-all>Restaurar original</button>${c.autocut.review.map(r=>`<p>${r.in.toFixed(2)}s · ${esc(r.reason)}</p>`).join('')}</details>`);}
  $('mcCompositionAudio').innerHTML=c.audio.map((track,i)=>`<fieldset class="${i===Number(c.selected_audio)?'is-selected':''}"><legend>${esc(track.name||`Áudio ${i+1}`)}</legend><div class="mc-studio-pair">${[['start','Posição (s)',600],['in','Cortar início (s)',600],['duration','Duração (s)',600],['volume','Volume',1],['fade_in','Fade in (s)',10],['fade_out','Fade out (s)',10]].map(([key,label,max])=>number(key,label,track[key],0,max,'.1',`data-audio-index="${i}" data-audio-key="${key}"`)).join('')}</div>${voiceControl(track,i)}<label><input type="checkbox" data-audio-index="${i}" data-audio-key="muted" ${track.muted?'checked':''}> Mutar faixa</label><label><input type="checkbox" data-audio-index="${i}" data-audio-key="solo" ${track.solo?'checked':''}> Solo</label><label><input type="checkbox" data-audio-index="${i}" data-audio-key="loop" ${track.loop?'checked':''}> Repetir</label><label title="Desative para manter esta faixa fixa quando clipes forem aparados ou removidos"><input type="checkbox" data-audio-index="${i}" data-audio-key="ripple" ${track.ripple!==false?'checked':''}> Acompanhar cortes</label><div class="mc-audio-envelope-editor"><strong>Envelope de volume</strong><small>Duplo clique na waveform também cria um ponto. Ganho: 1,00 mantém o volume; 2,00 dobra.</small>${(track.gain_points||[]).map((point,p)=>`<div><input aria-label="Tempo do ponto ${p+1}" type="number" min="0" max="${track.duration}" step=".01" value="${point.time}" data-audio-index="${i}" data-gain-index="${p}" data-gain-key="time"><input aria-label="Ganho do ponto ${p+1}" type="number" min="0" max="2" step=".05" value="${point.gain}" data-audio-index="${i}" data-gain-index="${p}" data-gain-key="gain"><button type="button" data-gain-remove="${i}:${p}" aria-label="Excluir ponto ${p+1}">×</button></div>`).join('')}</div><div class="mc-composition-actions"><button type="button" data-gain-add="${i}">Ponto de volume</button><button type="button" data-audio-sync="${i}">Alinhar ao cursor</button><button type="button" data-audio-restore-sync="${i}">Restaurar posição</button><button type="button" data-audio-split="${i}">Dividir no cursor</button><button type="button" data-audio-remove="${i}">Remover faixa</button></div></fieldset>`).join('');
  $('mcCompositionCaptions').innerHTML=c.captions.map((row,i)=>`<div class="mc-composition-caption"><input aria-label="Início da legenda ${i+1}" type="number" min="0" max="600" step=".1" value="${row.start}" data-caption="${i}" data-caption-key="start"><input aria-label="Fim da legenda ${i+1}" type="number" min="0" max="600" step=".1" value="${row.end}" data-caption="${i}" data-caption-key="end"><textarea aria-label="Legenda ${i+1}" maxlength="300" data-caption="${i}" data-caption-key="text">${esc(row.text)}</textarea><button type="button" data-caption-remove="${i}" aria-label="Excluir legenda ${i+1}">Excluir</button></div>`).join('');
  $('mcCompositionResolution').value=c.resolution;$('mcCompositionFps').value=c.fps;
}
export function paintCompositionCanvas(){
  const c=comp();if(paintLivePreview())return true;if(!c.enabled)return false;
  const row=item(),source=asset(row),video=$('mcSwapVideo'),still=$('mcVideoStill');
  const url=c.preview_valid&&c.preview_url?c.preview_url:row?.kind==='video'?source?.video_url:'';
  if(url){
    if(video.getAttribute('src')!==url){video.pause();video.src=url;video.load();}
    video.hidden=false;still.hidden=true;$('mcVideoEmpty').hidden=true;
    video.playbackRate=c.preview_valid?1:row?.speed||1;video.volume=c.preview_valid?1:row?.volume??1;
    video.style.filter='';video.style.transform='';video.style.opacity=1;
  }else{video.pause();video.hidden=true;still.hidden=!source;still.src=source?.image_url||source?.thumb_url||'';$('mcVideoEmpty').hidden=Boolean(source);}
  $('mcVideoStageMeta').textContent=c.preview_valid?'Prévia da montagem':source?.name||'Monte sua sequência';
  return true;
}
export function syncCompositionPlayback(){
  if(!comp().enabled)return false;
  const video=$('mcSwapVideo'),row=item();
  if(!comp().preview_valid&&row?.kind==='video'&&!video.paused){const end=row.out||video.duration;if(video.currentTime<row.in)video.currentTime=row.in;if(video.currentTime>=end){video.pause();video.currentTime=row.in;}}
  return true;
}
export async function exportComposition(preview=false){
  const c=comp();if(rendering||!c.items.length)return;
  if(c.captions.some(row=>!Number.isFinite(row.start)||!Number.isFinite(row.end)||row.end<=row.start)){notify('Corrija o início e o fim das legendas antes de renderizar.');return;}
  const client=state.clientId,id=newId().replaceAll('-',''),snapshot=fingerprint(),delivery=deliveryOptions(preview);
  if(!preview)beginDownload(id,client,delivery.format);
  const composition={...structuredClone(c),ratio:state.aspectRatio,layers:structuredClone(state.edit.layers||[])};
  $('mcStudioExportFormat').dataset.busy='1';$('mcStudioExportFormat').disabled=true;
  rendering=true;if(preview)showProcessing({job_id:`export:${id}`,kind:'export',title:preview?'Preparando prévia':'Renderizando montagem',background_supported:false,status:'queued',message:'Salvando a sequência…',preview_images:c.items.map(row=>asset(row)?.thumb_url||asset(row)?.poster_url||asset(row)?.image_url).filter(Boolean),plan:{aspect_ratio:state.aspectRatio,duration:compositionDuration()},ui_stages:[{id:'queued',label:'Na fila'},{id:'rendering',label:'Compondo cenas, áudio e legendas'},{id:'ready',label:'Pronto'}]});
  try{
    await post(`${base}/composition/exports`,{client_id:client,request_id:id,composition,delivery});
    updateProcessing({job_id:`export:${id}`,status:'queued',background_supported:true});
    const poll=async()=>{
      if(client!==state.clientId){rendering=false;delete $('mcStudioExportFormat').dataset.busy;refresh();return;}
      try{
        const result=await get(`${base}/exports/${id}?client_id=${encodeURIComponent(client)}`),url=`${base}/exports/${id}/content?client_id=${encodeURIComponent(client)}&format=mp4&inline=1`;
        if(!preview)updateDownload(result);
        updateProcessing({...result,job_id:`export:${id}`,kind:'export',auto_download:!preview,stage:result.status,version:result.status==='ready'?{video_url:url}:undefined,message:result.status==='ready'?'Montagem concluída.':'Renderizando sequência…'});
        if(['ready','failed'].includes(result.status)){
          rendering=false;delete $('mcStudioExportFormat').dataset.busy;refresh();
          if(result.status==='ready'&&!preview)downloadExport(result,client);
          if(result.status==='ready'&&snapshot===fingerprint()){comp().preview_url=url;comp().preview_valid=true;comp().preview_signature=snapshot;dirty();paintComposition();paintCompositionCanvas();}
          return;
        }
      }catch(error){if(!preview)updateDownload({id,status:'failed'});notify(`Acompanhamento interrompido: ${error.message}. Consulte Renderizações.`);rendering=false;delete $('mcStudioExportFormat').dataset.busy;refresh();return;}
      setTimeout(poll,3000);
    };poll();
  }catch(error){if(!preview)updateDownload({id,status:'failed'});rendering=false;delete $('mcStudioExportFormat').dataset.busy;refresh();updateProcessing({job_id:`export:${id}`,status:'failed',error:error.message});}
}
export function parseSrt(text){
  const time=value=>{const [h,m,s]=value.replace(',','.').split(':').map(Number);return h*3600+m*60+s;};
  const rows=String(text).replace(/^\uFEFF/,'').replace(/\r/g,'').trim().split(/\n\s*\n/).map(block=>{
    const lines=block.split('\n'),index=lines.findIndex(line=>line.includes('-->'));if(index<0)return null;
    const parts=lines[index].match(/(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})/);if(!parts)return null;
    return {start:time(parts[1]),end:time(parts[2]),text:lines.slice(index+1).join('\n').slice(0,300)};
  }).filter(row=>row&&row.end>row.start&&row.start>=0&&row.end<=600);
  if(!rows.length||rows.length>500)throw new Error('Use um SRT válido, com até 500 legendas e duração de até 10 minutos.');return rows;
}
export function toSrt(rows){const stamp=value=>{const ms=Math.round(value*1000);return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`;};return rows.map((row,i)=>`${i+1}\n${stamp(row.start)} --> ${stamp(row.end)}\n${row.text}`).join('\n\n');}
