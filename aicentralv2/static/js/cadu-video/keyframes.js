import {escapeHtml as esc} from './utils.js';
export function valuesAt(frames,time,defaults={x:.5,y:.5,scale:1,rotation:0,opacity:1}){
  if(!frames?.length)return defaults;
  const rows=[...frames].sort((a,b)=>a.time-b.time);
  if(time<=rows[0].time)return rows[0];
  for(let i=1;i<rows.length;i++)if(time<rows[i].time){
    const a=rows[i-1],b=rows[i];let p=(time-a.time)/(b.time-a.time);p=a.ease==='hold'?0:a.ease==='ease'?p*p*(3-2*p):p;
    return Object.fromEntries(['x','y','scale','rotation','opacity'].map(k=>[k,a[k]+(b[k]-a[k])*p]));
  }
  return rows.at(-1);
}
export function keyframeEditor(frames=[],owner=''){
  const fields=[['time','Tempo (s)',0,1200,.1],['x','X',-1,2,.01],['y','Y',-1,2,.01],['scale','Escala',.1,4,.05],['rotation','Rotação',-360,360,1],['opacity','Opacidade',0,1,.05]];
  return `<details class="mc-keyframes" data-keyframe-owner="${esc(owner)}"><summary>Keyframes · ${frames.length}</summary><p>Tempo relativo ao início da camada. Valores entre pontos são interpolados.</p><button type="button" data-keyframe-add>Adicionar no cursor</button>${frames.map((row,i)=>`<fieldset data-keyframe-index="${i}"><legend>Ponto ${i+1}</legend><div class="mc-studio-pair">${fields.map(([key,label,min,max,step])=>`<label>${label}<input data-keyframe-key="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${row[key]}"></label>`).join('')}</div><label>Movimento<select data-keyframe-key="ease">${[['linear','Linear'],['ease','Suave'],['hold','Manter até o próximo']].map(([key,label])=>`<option value="${key}" ${row.ease===key?'selected':''}>${label}</option>`).join('')}</select></label><button type="button" data-keyframe-remove>Excluir ponto</button></fieldset>`).join('')}</details>`;
}
export function bindKeyframes(host,resolve,commit,playhead){
  host?.addEventListener('click',event=>{
    const editor=event.target.closest('[data-keyframe-owner]');if(!editor)return;
    const row=resolve(editor.dataset.keyframeOwner);if(!row)return;
    row.keyframes ||= [];
    if(event.target.hasAttribute('data-keyframe-add')){
      if(row.keyframes.length>=60)return;
      const at=Math.max(0,Math.round(playhead(row)*1000)/1000),values=valuesAt(row.keyframes,at,{x:row.x??.5,y:row.y??.5,scale:1,rotation:0,opacity:1});
      row.keyframes=row.keyframes.filter(k=>k.time!==at);row.keyframes.push({...values,time:at,ease:'linear'});row.keyframes.sort((a,b)=>a.time-b.time);commit();
    }
    if(event.target.hasAttribute('data-keyframe-remove')){row.keyframes.splice(Number(event.target.closest('[data-keyframe-index]').dataset.keyframeIndex),1);commit();}
  });
  host?.addEventListener('change',event=>{
    const input=event.target,key=input.dataset.keyframeKey;if(!key)return;
    const editor=input.closest('[data-keyframe-owner]'),row=resolve(editor.dataset.keyframeOwner),index=Number(input.closest('[data-keyframe-index]').dataset.keyframeIndex);
    row.keyframes[index][key]=key==='ease'?input.value:Math.max(Number(input.min),Math.min(Number(input.max),Number(input.value)||0));
    row.keyframes.sort((a,b)=>a.time-b.time);row.keyframes=row.keyframes.filter((r,i,a)=>i===a.length-1||r.time!==a[i+1].time);commit();
  });
}
