export function catalogSections(rows) {
  const groups=new Map(),loose=new Map();
  for(const page of rows){
    if(page.template_id){
      if(!groups.has(page.template_id))groups.set(page.template_id,{id:page.template_id,pattern:page.template_pattern,pages:[],locales:new Set()});
      const group=groups.get(page.template_id);
      group.pages.push(page);
      group.locales.add(page.locale||'pt');
    }else{
      if(!loose.has(page.role))loose.set(page.role,[]);
      loose.get(page.role).push(page);
    }
  }
  return {groups:[...groups.values()].sort((a,b)=>b.pages.length-a.pages.length||a.pattern.localeCompare(b.pattern)),loose:[...loose.entries()]};
}
