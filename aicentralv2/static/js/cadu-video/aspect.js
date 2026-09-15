const RATIOS=['9:16','4:5','3:4','1:1','4:3','16:9','21:9'];
export function nearestAspect(width,height){
  if(!(width>0&&height>0))return '';
  const ratio=width/height;
  return RATIOS.reduce((best,next)=>Math.abs(Math.log(ratio/(next.split(':')[0]/next.split(':')[1])))<Math.abs(Math.log(ratio/(best.split(':')[0]/best.split(':')[1])))?next:best);
}
export async function sourceAspect(item){
  if(item?.width && item?.height)return nearestAspect(item.width,item.height);
  const url=item?.image_url||item?.thumb_url;
  if(url){
    const image=new Image();image.src=url;
    try{await image.decode();return nearestAspect(image.naturalWidth,image.naturalHeight);}catch{/* Fall back to recorded metadata. */}
  }
  return RATIOS.includes(item?.aspect_ratio)?item.aspect_ratio:'';
}
