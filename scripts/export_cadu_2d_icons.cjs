/* Raster-only crop and size exports from approved generated PNG masters.
 * Usage: CADU_NODE_MODULES=/path/node_modules node scripts/export_cadu_2d_icons.cjs manifest.json
 * Manifest is {"workspace":"/absolute/generated.png", ...}. No geometry is drawn here.
 */
const fs=require('node:fs/promises');
const path=require('node:path');
const sharp=require(path.join(process.env.CADU_NODE_MODULES||'../node_modules','sharp'));
const sizes=[16,20,24,32,40,48,64,96,128,192,512,1024];
(async()=>{
 const manifest=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
 const root=path.resolve(__dirname,'../output/mockups/brand-assets/icons-2d');
 const report=[];
 for(const [id,source] of Object.entries(manifest)){
  if(!['workspace','studio','connect','skills','planner'].includes(id))throw new Error('Unknown family');
  const dir=path.join(root,id);await fs.mkdir(dir,{recursive:true});
  const metadata=await sharp(source).metadata();
  const stats=await sharp(source).stats();
  if(!metadata.hasAlpha||stats.isOpaque)throw new Error(id+': source lacks actual transparency; regenerate instead of faking alpha');
  await fs.copyFile(source,path.join(dir,'master.png'));
  // Remove empty surrounding canvas, preserving the model-generated silhouette.
  const crop=await sharp(source).trim({threshold:10}).png().toBuffer();
  for(const size of sizes){
   const inset=Math.max(1,Math.round(size*.07));
   await sharp(crop).resize(size-inset*2,size-inset*2,{fit:'contain',background:'#00000000',kernel:'lanczos3'}).extend({top:inset,bottom:inset,left:inset,right:inset,background:'#00000000'}).png().toFile(path.join(dir,`icon-${size}.png`));
  }
  report.push({id,source,width:metadata.width,height:metadata.height,alpha:true,sizes});
 }
 await fs.writeFile(path.join(root,'exports.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
})().catch(error=>{console.error(error);process.exit(1);});
