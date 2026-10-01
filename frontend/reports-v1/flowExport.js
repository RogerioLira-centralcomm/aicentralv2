import {flowBlockFor} from './flowBlockRegistry.js';

const escape=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'})[char]);

export function flowSvg(config) {
  const nodes=config.nodes||[],edges=config.edges||[];
  const byId=new Map(nodes.map(node=>[node.id,node]));
  const width=Math.max(900,...nodes.map(node=>Number(node.x||0)+270));
  const height=Math.max(560,...nodes.map(node=>Number(node.y||0)+230));
  const links=edges.map(edge=>{
    const from=byId.get(edge.from),to=byId.get(edge.to);
    if(!from||!to)return '';
    const x1=Number(from.x||0)+160,y1=Number(from.y||0)+74,x2=Number(to.x||0),y2=Number(to.y||0)+74;
    const control=Math.max(60,Math.abs(x2-x1)/2);
    return `<path d="M${x1} ${y1} C${x1+control} ${y1},${x2-control} ${y2},${x2} ${y2}" fill="none" stroke="${edge.variant==='planned'?'#98a2b3':'#175cd3'}" stroke-width="2" ${edge.variant==='planned'?'stroke-dasharray="6 6"':''} marker-end="url(#arrow)"/>`;
  }).join('');
  const shapes=nodes.map(node=>{
    const block=flowBlockFor(node),x=Number(node.x||0)+80,y=Number(node.y||0)+72;
    const fill=block.tone==='success'?'#079455':block.tone==='error'?'#d92d20':block.tone==='warning'||block.tone==='capture'?'#dc6803':block.tone==='paid'?'#e04f5f':block.tone==='neutral'?'#475467':'#175cd3';
    const shape=block.shape==='page'?`<rect x="${x-48}" y="${y-18}" width="96" height="112" rx="9" fill="#fff" stroke="#d0d5dd"/><rect x="${x-40}" y="${y-8}" width="80" height="11" rx="3" fill="#f2f4f7"/><rect x="${x-38}" y="${y+14}" width="76" height="42" rx="4" fill="#d1e9ff"/><rect x="${x-38}" y="${y+65}" width="64" height="4" rx="2" fill="#d0d5dd"/>`:block.shape==='diamond'?`<rect x="${x-23}" y="${y-23}" width="46" height="46" rx="8" transform="rotate(45 ${x} ${y})" fill="${fill}"/>`:`<circle cx="${x}" cy="${y}" r="26" fill="${fill}"/>`;
    return `<g><text x="${x}" y="${y-47}" text-anchor="middle" fill="#101828" font-family="Inter,Arial,sans-serif" font-size="12" font-weight="600">${escape((node.title||block.label).slice(0,38))}</text>${shape}${node.path?`<text x="${x}" y="${y+112}" text-anchor="middle" fill="#667085" font-family="Inter,Arial,sans-serif" font-size="10">${escape(node.path.slice(0,42))}</text>`:''}</g>`;
  }).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#667085"/></marker></defs><rect width="100%" height="100%" fill="#f9fafb"/>${links}${shapes}</svg>`;
}

function download(blob,name) {
  const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name;link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export function downloadFlowSvg(config,name='fluxo') {
  download(new Blob([flowSvg(config)],{type:'image/svg+xml;charset=utf-8'}),`${name}.svg`);
}

export async function downloadFlowPng(config,name='fluxo') {
  const source=flowSvg(config),image=new Image(),url=URL.createObjectURL(new Blob([source],{type:'image/svg+xml;charset=utf-8'}));
  try {
    await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=reject;image.src=url;});
    const canvas=document.createElement('canvas');canvas.width=image.width*2;canvas.height=image.height*2;
    const context=canvas.getContext('2d');context.scale(2,2);context.drawImage(image,0,0);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
    if(!blob)throw new Error('O navegador não conseguiu gerar o PNG.');
    download(blob,`${name}.png`);
  } finally {URL.revokeObjectURL(url);}
}
