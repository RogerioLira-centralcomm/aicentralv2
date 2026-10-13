import {state} from './state.js';

// A fonte da marca no editor: o mesmo arquivo que o servidor usa no MP4 (caminho em /static/, sem o prefixo).
const loaded=new Map();
export const brandFontPath=()=>String(state.brandKit?.font?.url||'').replace(/^\/static\//,'');
export const brandFontFamily=path=>'StudioBrand_'+String(path||'').replace(/[^a-z0-9]/gi,'_');
export const brandFontLabel=()=>state.brandKit?.font?.family||'Marca';
export function ensureBrandFont(path){
  if(!path)return Promise.resolve(false);
  if(!loaded.has(path)){
    const face=new FontFace(brandFontFamily(path),`url(/static/${path})`);
    loaded.set(path,face.load().then(font=>{document.fonts.add(font);document.dispatchEvent(new Event('cadu:caption-fonts-ready'));paintBrandFontUsers();return true;}).catch(()=>false));
  }
  return loaded.get(path);
}
// Quem desenha com a fonte da marca e precisa repintar quando ela chega.
const painters=new Set();
export const onBrandFont=paint=>painters.add(paint);
function paintBrandFontUsers(){painters.forEach(paint=>paint());}
// Cores da marca como sugestões dos seletores de cor (atributo list), sem trocar o seletor nativo.
export function paintBrandColors(){
  let list=document.getElementById('mcBrandColors');
  if(!list){list=document.createElement('datalist');list.id='mcBrandColors';document.body.appendChild(list);}
  list.replaceChildren(...['#ffffff','#000000',...(state.brandKit?.palette||[]).map(color=>color.hex)].filter((hex,i,all)=>all.indexOf(hex)===i).map(hex=>Object.assign(document.createElement('option'),{value:hex})));
}
// Texto legível sobre a cor de fundo: branco ou quase preto, pela luminância.
export function readableOn(hex){
  const [r,g,b]=[1,3,5].map(i=>parseInt(String(hex).slice(i,i+2),16)/255);
  return .2126*r+.7152*g+.0722*b>.55?'#111111':'#ffffff';
}
