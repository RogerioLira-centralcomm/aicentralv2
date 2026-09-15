import {keyframeEditor,bindKeyframes,valuesAt} from './keyframes.js';
import {state} from './state.js';
import {escapeHtml} from './utils.js';
const $=id=>document.getElementById(id);
let signature='';
export function bindTextLayers(dirty) {
  bindKeyframes($('mcStudioTextLayers'),owner=>state.edit.layers?.[Number(owner)],()=>{dirty();signature='';document.activeElement?.blur();paintTextLayers();},row=>Math.max(0,($('mcSwapVideo').currentTime-state.edit.start)/(state.edit.speed||1)-row.start));
  $('mcStudioAddText')?.addEventListener('click',()=>{
    state.edit.layers ||= [];if(state.edit.layers.length>=8)return;
    state.edit.layers.push({text:'Seu texto',start:0,end:5,x:.5,y:.8,size:.06,color:'#ffffff',animation:'fade',hidden:false});
    dirty();paintTextLayers();
  });
  $('mcStudioTextLayers')?.addEventListener('input',event=>{
    const input=event.target, row=state.edit.layers?.[Number(input.dataset.layer)];if(!row)return;
    const key=input.dataset.key;if(!key)return;
    row[key]=input.type==='number'?Math.min(Number(input.max),Math.max(Number(input.min),Number(input.value)||0)):input.type==='checkbox'?input.checked:input.value;
    paintTextPreview();
  });
  $('mcStudioTextLayers')?.addEventListener('change',()=>{dirty();});
  $('mcStudioTextLayers')?.addEventListener('click',event=>{
    const index=event.target.dataset.removeLayer;if(index===undefined)return;
    state.edit.layers.splice(Number(index),1);dirty();paintTextLayers();
  });
  new ResizeObserver(paintTextPreview).observe($('mcSwapVideo'));
}
export function paintTextLayers(){
  const rows=state.edit?.layers||[],key=JSON.stringify(rows);if(!$('mcStudioTextLayers'))return;
  if(key!==signature && !$('mcStudioTextLayers').contains(document.activeElement)){
    signature=key;
    $('mcStudioTextLayers').innerHTML=rows.map((row,i)=>`<fieldset class="mc-studio-text-card"><legend>Texto ${i+1}</legend><textarea aria-label="Texto ${i+1}" maxlength="200" data-layer="${i}" data-key="text">${escapeHtml(row.text)}</textarea><div class="mc-studio-pair">${[['start','Início (s)',0,1200,.1],['end','Fim (s)',.1,1200,.1],['x','Posição X',0,1,.01],['y','Posição Y',0,1,.01],['size','Tamanho',.02,.2,.01]].map(([name,label,min,max,step])=>`<label>${label}<input type="number" min="${min}" max="${max}" step="${step}" value="${row[name]}" data-layer="${i}" data-key="${name}"></label>`).join('')}<label>Cor<input type="color" value="${escapeHtml(row.color)}" data-layer="${i}" data-key="color"></label></div><label>Animação<select data-layer="${i}" data-key="animation"><option value="none" ${row.animation==='none'?'selected':''}>Sem animação</option><option value="fade" ${row.animation==='fade'?'selected':''}>Fade de entrada e saída</option></select></label>${keyframeEditor(row.keyframes,String(i))}<label><input type="checkbox" data-layer="${i}" data-key="hidden" ${row.hidden?'checked':''}> Ocultar camada</label><button type="button" class="mc-cadu-video-ghost" data-remove-layer="${i}">Excluir texto</button></fieldset>`).join('');
  }
  const video=$('mcSwapVideo');
  const duration=Math.max(.1,((state.edit.end||video?.duration||5)-state.edit.start)/(state.edit.speed||1));
  $('mcStudioTextTracks').innerHTML=rows.map((row,i)=>`<div class="mc-studio-track-row"><span class="mc-studio-track-name">Texto ${i+1}</span><div class="mc-studio-text-track"><span style="left:${Math.min(100,row.start/duration*100)}%;width:${Math.max(0,(Math.min(duration,row.end)-row.start)/duration*100)}%;opacity:${row.hidden ? .35 : 1}" title="${escapeHtml(row.text)}">${escapeHtml(row.text)} · ${row.animation==='fade'?'Fade':'Fixo'}</span></div></div>`).join('');
  $('mcStudioAddText').disabled=rows.length>=8;
  paintTextPreview();
}
export function paintTextPreview(){
  const host=$('mcStudioLayersPreview'),video=$('mcSwapVideo');if(!host||!video)return;
  host.replaceChildren();if(state.composition?.enabled)return;if(state.previewMode!=='clip'||!video.videoWidth)return;
  const scale=Math.min(video.clientWidth/video.videoWidth,video.clientHeight/video.videoHeight);
  const width=video.videoWidth*scale,height=video.videoHeight*scale;
  host.style.cssText=`position:absolute;left:${(video.clientWidth-width)/2}px;top:${(video.clientHeight-height)/2}px;width:${width}px;height:${height}px;pointer-events:none;overflow:hidden`;
  const at=(video.currentTime-state.edit.start)/(state.edit.speed||1);
  for(const row of state.edit.layers||[]){
    if(row.hidden||at<row.start||at>row.end)continue;
    const span=document.createElement('span');span.textContent=row.text;
    const values=valuesAt(row.keyframes,at-row.start,{x:row.x,y:row.y,scale:1,rotation:0,opacity:1});
    const fade=Math.min(.3,(row.end-row.start)/2);
    const opacity=row.animation==='fade'?Math.max(0,Math.min(1,(at-row.start)/fade,(row.end-at)/fade)):1;
    span.style.cssText=`position:absolute;left:${values.x*100}%;top:${values.y*100}%;transform:translate(-50%,-50%) rotate(${values.rotation}deg) scale(${values.scale});font-family:StudioOpenSans;font-size:${height*row.size}px;color:${row.color};white-space:pre;text-align:center;line-height:1.35;opacity:${opacity*values.opacity};text-shadow:0 1px 1px #000;`;
    host.appendChild(span);
  }
}
