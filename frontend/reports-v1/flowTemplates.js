const node=(type,kind,title,x,y,index)=>({id:crypto.randomUUID(),type,kind,title,
  path:type==='source'?'':`/configurar-modelo-${index}`,x,y,
  data:{label:title,url:type==='source'?'':`/configurar-modelo-${index}`}});

export function flowTemplateConfig(template) {
  if(template==='blank')return {schema_version:2,nodes:[],edges:[],viewport:{x:0,y:0,zoom:1}};
  const definitions={
    lead:[['source','traffic.google_search','Google Ads','google'],['page','page.landing','Landing page'],['form','page.form','Formulário'],['conversion','conversion.lead','Lead']],
    commerce:[['source','traffic.organic_search','Busca orgânica','organic'],['page','page.sales','Produto'],['page','page.checkout','Checkout'],['conversion','conversion.purchase','Compra']],
    webinar:[['source','communication.email','E-mail','email'],['page','page.webinar','Página do webinar'],['form','page.form','Inscrição'],['conversion','conversion.signup','Inscrito']],
    whatsapp:[['source','traffic.meta','Meta Ads','facebook'],['page','page.landing','Landing page'],['whatsapp','event.whatsapp','Clique WhatsApp'],['conversion','conversion.lead','Lead']],
  };
  const steps=definitions[template];
  if(!steps)throw new Error('Modelo de fluxo desconhecido.');
  const nodes=steps.map(([type,kind,title],index)=>node(type,kind,title,80+index*240,150,index+1));
  nodes[0].source=steps[0][3];
  nodes[0].isEntry=true;
  const edges=nodes.slice(0,-1).map((current,index)=>({id:crypto.randomUUID(),from:current.id,
    to:nodes[index+1].id,variant:index===0?'planned':'direct',label:'Próximo'}));
  return {schema_version:2,nodes,edges,viewport:{x:0,y:0,zoom:1},settings:{edge_style:'bezier',grid:true}};
}
