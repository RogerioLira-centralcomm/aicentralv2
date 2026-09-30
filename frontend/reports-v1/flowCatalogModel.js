/** Groups catalog rows by HTML template or, failing that, by URL folder; everything else stays loose by role. */
export function catalogSections(rows) {
  const groups=new Map(),loose=new Map();
  for(const page of rows){
    const id=page.template_id||page.section_id;
    if(id){
      if(!groups.has(id))groups.set(id,{id,kind:page.template_id?'template':'path',pattern:page.template_pattern||page.section_pattern,pages:[],locales:new Set()});
      const group=groups.get(id);
      group.pages.push(page);
      group.locales.add(page.locale||'pt');
    }else{
      if(!loose.has(page.role))loose.set(page.role,[]);
      loose.get(page.role).push(page);
    }
  }
  return {groups:[...groups.values()].sort((a,b)=>b.pages.length-a.pages.length||String(a.pattern).localeCompare(String(b.pattern))),loose:[...loose.entries()]};
}

export const CATALOG_PAGE_SIZE=10;
export const CATALOG_GROUP_ADD_LIMIT=30;

/** Window of a list for the pager: 1-based range and whether there are more pages. */
export function pageWindow(total,page,size=CATALOG_PAGE_SIZE) {
  const last=Math.max(0,Math.ceil(total/size)-1),current=Math.min(Math.max(0,page),last),start=current*size;
  return {page:current,last,start,end:Math.min(total,start+size),from:total?start+1:0};
}
