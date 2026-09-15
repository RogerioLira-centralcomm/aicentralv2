import {drawCaptions} from './caption-style.js';
import {state} from './state.js';
import {valuesAt} from './keyframes.js';
const $=id=>document.getElementById(id);
let canvas,bar,playing=false,at=0,last=0,frame=0,revision='',media=new Map(),music=new Map(),active=false;
const source=row=>(row.kind==='image'?state.library:state.clips).find(r=>r.id===row.asset_id);
const length=row=>row.kind==='image'?row.duration:Math.max(.1,((row.out||source(row)?.duration||4)-row.in)/row.speed);
export function previewTime(){return at;}
export function seekLivePreview(time){at=Math.max(0,Math.min(total(),time));if(active)draw();}
export function schedule(items){let end=0;return items.map((row,i)=>{const overlap=i&&items[i-1].transition!=='cut'?Math.min(items[i-1].transition_duration,length(items[i-1])/2,length(row)/2):0;const start=end-overlap;end=start+length(row);return {row,start,end,overlap};});}
function ensure(){
  if(canvas)return;
  canvas=document.createElement('canvas');canvas.id='mcCompositionLiveCanvas';canvas.setAttribute('aria-label','Prévia instantânea da montagem');
  $('mcSwapVideo').parentElement.appendChild(canvas);
  bar=document.createElement('section');bar.id='mcCompositionLiveControls';bar.className='mc-studio-playback';bar.innerHTML='<button type="button" id="mcLivePlay" class="mc-cadu-video-ghost">Reproduzir montagem</button><input id="mcLiveSeek" type="range" min="0" max="1" step=".01" value="0" aria-label="Posição na montagem"><output id="mcLiveTime"></output>';
  document.querySelector('.mc-studio-playback').after(bar);
  $('mcLivePlay').onclick=()=>{playing=!playing;if(at>=total())at=0;last=performance.now();tick(last);};
  $('mcLiveSeek').oninput=event=>{at=Number(event.target.value);draw();};
  window.addEventListener('pagehide',stop);
  document.addEventListener('cadu:caption-fonts-ready',()=>{if(active)draw();});
}
function total(){return schedule(state.composition?.items||[]).at(-1)?.end||0;}
function stop(){playing=false;cancelAnimationFrame(frame);for(const value of [...media.values(),...music.values()])if(value.pause)value.pause();}
function tick(now){cancelAnimationFrame(frame);if(!active)return;if(playing){at+=Math.min(.1,(now-last)/1000);if(at>=total()){at=total();playing=false;}}last=now;draw();if(playing)frame=requestAnimationFrame(tick);}
export function paintLivePreview(){
  ensure();const c=state.composition;active=Boolean(c?.enabled&&!c.preview_valid&&c.items.length);
  canvas.hidden=!active;bar.hidden=!active;$('mcSwap').classList.toggle('is-live-composition',active);
  if(!active){stop();return false;}
  $('mcSwapVideo').pause();$('mcSwapVideo').hidden=true;$('mcVideoStill').hidden=true;$('mcVideoEmpty').hidden=true;
  const key=JSON.stringify([c.items,c.audio,c.captions,c.caption_style,state.edit.layers,state.aspectRatio,state.clientId,state.sounds?.map(r=>[r.id,r.url])]);
  if(key!==revision){stop();revision=key;at=Math.min(at,total());const used=new Set(c.items.map(r=>r.id));for(const [id,value] of media)if(!used.has(id)){if(value.pause){value.pause();value.removeAttribute('src');value.load();}media.delete(id);}for(const audio of music.values()){audio.pause();audio.removeAttribute('src');audio.load();}music.clear();}
  const [a,b]=state.aspectRatio.split(':').map(Number);canvas.width=a>=b?960:Math.round(960*a/b);canvas.height=a>=b?Math.round(960*b/a):960;
  draw();return true;
}
function element(row){
  const id=row.id;
  if(media.has(id))return media.get(id);
  const asset=source(row);if(!asset)return null;
  const value=row.kind==='image'?new Image():document.createElement('video');value.src=row.kind==='image'?asset.image_url||asset.thumb_url:asset.video_url;
  if(row.kind==='video'){value.playsInline=true;value.preload='auto';value.addEventListener('loadeddata',()=>{if(active)draw();});value.addEventListener('seeked',()=>{if(active&&!playing)draw();});}else value.onload=()=>{if(active)draw();};
  media.set(id,value);return value;
}
function sync(value,time,rate,volume,on){
  value.volume=Math.max(0,Math.min(1,volume));value.playbackRate=rate;
  if(Number.isFinite(value.duration)&&Math.abs(value.currentTime-time)>(playing?.18:.025))value.currentTime=Math.max(0,Math.min(value.duration,time));
  if(playing&&on){if(value.paused)value.play().catch(()=>{});}else value.pause();
}
function gainAt(points,time){
  if(!points?.length)return 1;const rows=[...points].sort((a,b)=>a.time-b.time);
  if(time<=rows[0].time)return rows[0].gain;
  for(let i=1;i<rows.length;i++)if(time<rows[i].time){const a=rows[i-1],b=rows[i],p=(time-a.time)/Math.max(.001,b.time-a.time);return a.gain+(b.gain-a.gain)*p;}
  return rows.at(-1).gain;
}
function draw(){
  if(!active)return;
  const c=state.composition,ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height,plan=schedule(c.items),visible=plan.filter(r=>at>=r.start&&at<r.end),lastItem=plan.at(-1);
  if(!visible.length&&at===total()&&lastItem)visible.push(lastItem);
  ctx.fillStyle='#000';ctx.fillRect(0,0,w,h);
  const used=new Set(),hasSolo=c.audio.some(track=>track.solo&&!track.muted);
  for(const entry of visible){
    const {row,start,overlap}=entry,local=Math.max(0,at-start),value=element(row);if(!value)continue;used.add(row.id);
    const index=plan.indexOf(entry),previous=plan[index-1],next=plan[index+1];
    let gain=1;
    if(overlap&&local<overlap)gain=local/overlap;
    if(next?.overlap&&at>next.start)gain=Math.min(gain,(entry.end-at)/next.overlap);
    if(row.kind==='video')sync(value,row.in+local*row.speed,row.speed,hasSolo?0:row.volume*gain,true);
    const iw=value.videoWidth||value.naturalWidth,ih=value.videoHeight||value.naturalHeight;if(!iw||!ih)continue;
    const k=valuesAt(row.keyframes,local),mode=row.fit==='cover'?Math.max(w/iw,h/ih):Math.min(w/iw,h/ih),zoom=row.motion==='zoom'?1+.08*Math.min(1,local/length(row)):1;
    const p=overlap?Math.min(1,local/overlap):1,transition=previous?.row.transition;
    ctx.save();
    if(next?.overlap&&at>=next.start){const progress=(at-next.start)/next.overlap;if(row.transition==='fadeblack')ctx.globalAlpha=Math.max(0,1-2*progress);if(row.transition==='slideleft')ctx.translate(-w*progress,0);}
    if(previous&&p<1){
      if(transition==='fade')ctx.globalAlpha=p;
      if(transition==='fadeblack')ctx.globalAlpha=Math.max(0,2*p-1);
      if(transition==='slideleft')ctx.translate(w*(1-p),0);
      if(transition==='wipeleft'){ctx.beginPath();ctx.rect(w*(1-p),0,w*p,h);ctx.clip();}
    }
    ctx.translate(w*k.x,h*k.y);ctx.rotate(k.rotation*Math.PI/180);ctx.scale(k.scale*zoom,k.scale*zoom);ctx.globalAlpha*=k.opacity;
    // Clip to the fitted project frame, matching the server's contain/cover stage.
    ctx.beginPath();ctx.rect(-w/2,-h/2,w,h);ctx.clip();ctx.fillStyle='#000';ctx.fillRect(-w/2,-h/2,w,h);ctx.drawImage(value,-iw*mode/2,-ih*mode/2,iw*mode,ih*mode);ctx.restore();
  }
  for(const [id,value] of media)if(value.pause&&!used.has(id))value.pause();
  for(let i=0;i<c.audio.length;i++){
    const track=c.audio[i],time=at-track.start,on=time>=0&&time<track.duration;
    let audio=music.get(i);if(!audio){const sound=state.sounds?.find(r=>r.id===track.sound_id);audio=new Audio(sound?.url||`/parametros/api/format-lab/studio/sounds/${encodeURIComponent(track.sound_id)}?client_id=${encodeURIComponent(state.clientId)}`);audio.preload='auto';music.set(i,audio);}
    let offset=track.in+Math.max(0,time);if(track.loop&&Number.isFinite(audio.duration)&&audio.duration>0)offset%=audio.duration;
    const gain=Math.min(1,track.fade_in?Math.max(0,time)/track.fade_in:1,track.fade_out?Math.max(0,track.duration-time)/track.fade_out:1);
    sync(audio,offset,1,track.muted||(hasSolo&&!track.solo)?0:track.volume*gain*gainAt(track.gain_points,time),on);
  }
  for(const row of state.edit.layers||[]){
    if(row.hidden||at<row.start||at>=row.end)continue;
    const k=valuesAt(row.keyframes,at-row.start,{x:row.x,y:row.y,scale:1,rotation:0,opacity:1});
    const fade=Math.min(.3,(row.end-row.start)/2),alpha=row.animation==='fade'?Math.min(1,(at-row.start)/fade,(row.end-at)/fade):1;
    ctx.save();ctx.translate(w*k.x,h*k.y);ctx.rotate(k.rotation*Math.PI/180);ctx.scale(k.scale,k.scale);ctx.globalAlpha=k.opacity*alpha;ctx.font=`${h*row.size}px StudioOpenSans`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=row.color;ctx.strokeStyle='#000';ctx.lineWidth=2;
    const lines=row.text.split('\n');lines.forEach((line,i)=>{const y=(i-(lines.length-1)/2)*h*row.size*1.35;ctx.strokeText(line,0,y);ctx.fillText(line,0,y);});ctx.restore();
  }
  drawCaptions(ctx,c,at,w,h);
  $('mcLiveSeek').max=total();$('mcLiveSeek').value=at;$('mcLiveTime').value=`${at.toFixed(1)} / ${total().toFixed(1)}s`;$('mcLivePlay').textContent=playing?'Pausar montagem':'Reproduzir montagem';
  document.dispatchEvent(new CustomEvent('cadu:preview-time',{detail:at}));
  // Preload the next source, keeping only the active and adjacent video decoders.
  const next=plan.find(r=>r.start>at);if(next)element(next.row);
}
