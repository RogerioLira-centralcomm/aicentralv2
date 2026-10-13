import {escapeHtml as esc} from './utils.js';
import {brandFontFamily,brandFontLabel,brandFontPath,ensureBrandFont,readableOn} from './brand-font.js';
import {state} from './state.js';
let catalog=null,getComposition,onChange;
const base={preset:'classic',font:'open',size:.045,x:.5,y:.86,color:'#ffffff',outline_color:'#000000',outline:.06,background:'#000000',background_opacity:0,uppercase:false,align:'center'};
export const captionStyle=c=>({...base,...c?.caption_style});
export function bindCaptionStyle(getter,changed){
  getComposition=getter;onChange=changed;
  const root=document.getElementById('mcCaptionStyle');if(!root)return;
  document.addEventListener('cadu:brand-kit',paintCaptionStyle);
  root.addEventListener('click',event=>{
    const preset=catalog?.presets.find(p=>p.id===event.target.closest('[data-caption-preset]')?.dataset.captionPreset);
    if(preset){getComposition().caption_style=structuredClone(preset.style);onChange();}
    if(event.target.closest('[data-caption-brand]')){
      // Legenda da marca: fonte da marca e caixa na cor principal, com texto legível sobre ela.
      const kit=state.brandKit||{},path=brandFontPath(),primary=kit.primary_color||'#000000';
      getComposition().caption_style={...captionStyle(getComposition()),preset:'brand',...(path?{font:'brand',brand_font:path,brand_family:brandFontLabel()}:{}),
        background:primary,background_opacity:.85,color:readableOn(primary),outline:0};
      ensureBrandFont(path);onChange();
    }
    const position=event.target.closest('[data-caption-position]')?.dataset.captionPosition;
    if(position){getComposition().caption_style={...captionStyle(getComposition()),x:.5,y:Number(position)};onChange();}
  });
  root.addEventListener('change',event=>{
    const input=event.target,key=input.dataset.captionStyle;if(!key)return;
    const value=input.type==='checkbox'?input.checked:input.type==='number'?Math.max(Number(input.min),Math.min(Number(input.max),Number(input.value)||0))/100:input.value;
    const brand=key==='font'&&value==='brand'?{brand_font:brandFontPath(),brand_family:brandFontLabel()}:{};
    if(brand.brand_font)ensureBrandFont(brand.brand_font);
    getComposition().caption_style={...captionStyle(getComposition()),[key]:value,...brand};onChange();
  });
  fetch('/static/fonts/captions/styles.json').then(r=>{if(!r.ok)throw new Error();return r.json();}).then(async data=>{
    catalog=data;
    await Promise.all(data.fonts.map(async f=>{
      const font=new FontFace(`Caption_${f.id}`,`url(/static/fonts/${f.file})`);await font.load();document.fonts.add(font);
    }));
    root.innerHTML=`<p>Estilo aplicado a todas as legendas, em todos os trechos.</p><div class="mc-caption-presets" role="group" aria-label="Modelos de legendas">${data.presets.map(p=>`<button type="button" data-caption-preset="${p.id}" aria-pressed="false"><span style="font-family:Caption_${p.style.font};color:${p.style.color};background:${p.style.background_opacity?p.style.background:'#17202b'};text-shadow:${p.style.outline?'0 1px 2px #000':'none'}">${p.style.uppercase?'SUA LEGENDA':'Sua legenda'}</span><small>${esc(p.name)}</small></button>`).join('')}</div>
    <div class="mc-caption-brand" data-caption-brand-row></div>
    <label>Fonte<select data-caption-style="font">${data.fonts.map(f=>`<option value="${f.id}">${esc(f.name)}</option>`).join('')}<option value="brand" data-brand-font hidden>Fonte da marca</option></select></label>
    <div class="mc-studio-pair">${[['size','Tamanho (% da altura)',2,12],['x','Posição horizontal (%)',0,100],['y','Posição vertical (%)',0,100],['outline','Contorno (%)',0,15],['background_opacity','Opacidade do fundo (%)',0,100]].map(([key,label,min,max])=>`<label>${label}<input type="number" step="0.1" min="${min}" max="${max}" data-caption-style="${key}"></label>`).join('')}</div>
    <div class="mc-caption-position" role="group" aria-label="Posição das legendas"><button type="button" data-caption-position=".14">Topo</button><button type="button" data-caption-position=".5">Centro</button><button type="button" data-caption-position=".86">Base</button></div>
    <div class="mc-studio-pair">${[['color','Cor do texto'],['outline_color','Cor do contorno'],['background','Cor do fundo']].map(([key,label])=>`<label>${label}<input type="color" list="mcBrandColors" data-caption-style="${key}"></label>`).join('')}</div>
    <label>Alinhamento<select data-caption-style="align"><option value="left">Esquerda</option><option value="center">Centro</option><option value="right">Direita</option></select></label>
    <label class="mc-caption-check"><input type="checkbox" data-caption-style="uppercase"> Letras maiúsculas</label><p>O texto permanece dentro do quadro. SRT contém apenas texto e tempos; o estilo aparece no vídeo exportado.</p>`;
    paintCaptionStyle();document.dispatchEvent(new Event('cadu:caption-fonts-ready'));
  }).catch(()=>{root.textContent='Não foi possível carregar os modelos de legenda. Reabra o editor para tentar novamente.';});
}
export function paintCaptionStyle(){
  const root=document.getElementById('mcCaptionStyle');if(!root||!getComposition)return;
  const style=captionStyle(getComposition());
  // O que a marca oferece: só aparece quando ela tem fonte ou cor própria.
  const kit=state.brandKit,path=brandFontPath(),row=root.querySelector('[data-caption-brand-row]');
  const option=root.querySelector('[data-brand-font]');
  if(option){option.hidden=!path&&style.font!=='brand';option.textContent=`Marca · ${style.font==='brand'&&style.brand_family?style.brand_family:brandFontLabel()}`;}
  if(row)row.innerHTML=kit&&(path||kit.primary_color)?`<button type="button" data-caption-brand aria-pressed="${style.preset==='brand'}">Legenda da marca</button><small>${esc([path?brandFontLabel():'',kit.primary_color?'cor principal da marca':''].filter(Boolean).join(' · '))}</small>`:'';
  if(style.font==='brand')ensureBrandFont(style.brand_font);
  root.querySelectorAll('[data-caption-style]').forEach(input=>{const v=style[input.dataset.captionStyle];if(input.type==='checkbox')input.checked=!!v;else input.value=input.type==='number'?Math.round(v*1000)/10:v;});
  root.querySelectorAll('[data-caption-preset]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.captionPreset===style.preset)));
}
export function drawCaptions(ctx,c,at,w,h){
  const text=c.captions.filter(r=>at>=r.start&&at<r.end).map(r=>r.text).join('\n');if(!text)return;
  const s=captionStyle(c),content=s.uppercase?text.toUpperCase():text;
  ctx.save();let size=Math.max(6,Math.round(h*s.size)),lines,pad,lineHeight,boxHeight;
  const wrap=()=>{const result=[];for(const paragraph of content.split('\n')){let line='';for(const word of paragraph.trim().split(/\s+/)){const candidate=(line+' '+word).trim();if(ctx.measureText(candidate).width<=w*.86){line=candidate;continue;}if(line)result.push(line);line='';for(const char of word){if(line&&ctx.measureText(line+char).width>w*.86){result.push(line);line='';}line+=char;}}result.push(line);}return result;};
  const family=s.font==='brand'?brandFontFamily(s.brand_font):`Caption_${s.font}`;
  do{ctx.font=`${size}px ${family}, StudioOpenSans`;lines=wrap();pad=size*.3;lineHeight=size*1.3;boxHeight=lines.length*lineHeight+pad*2;if(boxHeight<=h*.94||size<=6)break;size--;}while(size>=6);
  const boxWidth=Math.max(...lines.map(l=>ctx.measureText(l).width))+2*pad;
  const x=Math.max(w*.02,Math.min(w-boxWidth-w*.02,w*s.x-boxWidth/2)),y=Math.max(h*.02,Math.min(h-boxHeight-h*.02,h*s.y-boxHeight/2));
  if(s.background_opacity){ctx.globalAlpha=s.background_opacity;ctx.fillStyle=s.background;ctx.beginPath();ctx.roundRect(x,y,boxWidth,boxHeight,size*.15);ctx.fill();ctx.globalAlpha=1;}
  ctx.textAlign='left';ctx.textBaseline='alphabetic';ctx.fillStyle=s.color;ctx.strokeStyle=s.outline_color;ctx.lineWidth=2*Math.round(size*s.outline);ctx.lineJoin='round';
  lines.forEach((line,i)=>{const width=ctx.measureText(line).width,tx=s.align==='left'?x+pad:s.align==='right'?x+boxWidth-pad-width:x+(boxWidth-width)/2,ty=y+pad+size+i*lineHeight;if(ctx.lineWidth&&s.outline)ctx.strokeText(line,tx,ty);ctx.fillText(line,tx,ty);});ctx.restore();
}
