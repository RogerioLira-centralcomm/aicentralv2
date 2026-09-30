const node=(type,kind,title,x,y,index)=>({id:crypto.randomUUID(),type,kind,title,
  path:type==='source'?'':`/configurar-modelo-${index}`,x,y,
  data:{label:title,url:type==='source'?'':`/configurar-modelo-${index}`}});

export function flowTemplateConfig(template) {
  if(template==='blank')return {schema_version:2,nodes:[],edges:[],viewport:{x:0,y:0,zoom:1}};
  const lead=template==='lead';
  const nodes=lead?[
    node('source','traffic.google_search','Google Ads',80,150,1),
    node('page','page.landing','Landing page',320,150,2),
    node('form','page.form','Formulário',560,150,3),
    node('conversion','conversion.lead','Lead',800,150,4),
  ]:[
    node('source','traffic.organic_search','Busca orgânica',80,150,1),
    node('page','page.sales','Produto',320,150,2),
    node('page','page.checkout','Checkout',560,150,3),
    node('conversion','conversion.purchase','Compra',800,150,4),
  ];
  nodes[0].source=lead?'google':'organic';
  nodes[0].isEntry=true;
  const edges=nodes.slice(0,-1).map((current,index)=>({id:crypto.randomUUID(),from:current.id,
    to:nodes[index+1].id,variant:index===0?'planned':'direct',label:'Próximo'}));
  return {schema_version:2,nodes,edges,viewport:{x:0,y:0,zoom:1},settings:{edge_style:'bezier',grid:true}};
}
