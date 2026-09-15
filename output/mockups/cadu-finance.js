/* Local simulation only. No provider requests, payments or production ledger. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CaduFinance = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const date = '2026-09-15';
  const sources = {
    image: 'https://openrouter.ai/openai/gpt-image-2',
    chat: 'https://openrouter.ai/openai/gpt-5-mini',
    video: 'https://openrouter.ai/blog/insights/seedance-2-5-review/',
    tts: 'https://openrouter.ai/google/gemini-3.1-flash-tts-preview',
    fees: 'https://openrouter.ai/docs/faq'
  };
  const catalog = [
    {id:'draft', product:'studio', name:'Imagem rascunho', model:'GPT Image 2 · low 1K', unit:'imagem', usd:.006, qty:40, feeIncluded:true, evidence:'Estimativa do código', source:sources.image, code:'creative_image_fidelity.py', note:'Valor configurado; comentário já inclui taxa. Tokens, tamanho, referências e retries alteram a fatura.'},
    {id:'image', product:'studio', name:'Imagem / edição publicável', model:'GPT Image 2 · high 2K', unit:'imagem', usd:.22, qty:20, feeIncluded:true, evidence:'Estimativa do código', source:sources.image, code:'creative_image_fidelity.py', note:'Tarifa oficial por milhão: texto US$5; imagem entrada US$8; saída US$30. Não é preço fixo por imagem.'},
    {id:'video', product:'studio', name:'Vídeo 720p sem referência', model:'Seedance 2.5', unit:'segundo', usd:.23112, qty:24, feeIncluded:false, evidence:'Tarifa publicada + geometria', source:sources.video, code:'creative_media/quoting.py', note:'1280 × 720 × 24 ÷ 1024 × US$0,0000107 por segundo. Referência: 0,0000064/token; entrada e fallback a conciliar.'},
    {id:'tts', product:'studio', name:'Voz sintetizada', model:'Gemini 3.1 Flash TTS', unit:'1k texto + 2k áudio tokens', usd:.041, qty:1, feeIncluded:false, evidence:'Tarifa publicada + volume assumido', source:sources.tts, code:'creative_media/quoting.py', note:'US$1/M texto e US$20/M áudio. Código estima caracteres, que não equivalem a tokens faturados.'},
    {id:'chat', product:'workspace', name:'Conversa', model:'GPT-5 mini · exemplo, não modelo único', unit:'2k entrada + 2k saída', usd:.0045, qty:100, feeIncluded:false, evidence:'Tarifa publicada + volume assumido', source:sources.chat, code:'services/openrouter_service.py', note:'US$0,25/M entrada, US$2/M saída, cache OpenAI US$0,025/M. Contexto e ferramentas acumulam tokens.'},
    {id:'ocr', product:'workspace', name:'OCR / relatório', model:'Modelo e pipeline a conciliar', unit:'página / extração', usd:null, qty:10, evidence:'Pendente', code:'services/openrouter_service.py', note:'Medir imagens/páginas, extração, normalização, validação e transcrição.'},
    {id:'planner', product:'planner', name:'Planejamento completo', model:'Pipeline multiagente', unit:'plano', usd:.54, qty:2, feeIncluded:false, evidence:'Estimativa do código', code:'smart_planner/models.py', note:'Preview soma US$0,54; generation_map soma US$0,32. Reconciliar caminho real, pesquisa, revisão, taxas e reformulações.'},
    {id:'mcp', product:'connect', name:'MCP / sincronização', model:'Conector + agente', unit:'execução', usd:null, qty:30, evidence:'Pendente', note:'Hospedagem, chamadas, egress, frequência, credenciais e suporte. MCP não define uma tarifa universal.'},
    {id:'rag', product:'workspace', name:'Projetos e RAG', model:'Embeddings + busca + contexto', unit:'ingestão / recuperação', usd:null, qty:20, evidence:'Pendente', code:'services/intelligence/service.py', note:'Há SentenceTransformer e índice no código. Custo depende de CPU, armazenamento, OCR e tokens recuperados; metadata não gera cobrança IA presumida.'},
    {id:'delivery', product:'studio', name:'Entrega de ativos', model:'Render + storage + transferência', unit:'entrega', usd:null, qty:20, evidence:'Pendente', note:'Ratear renderização, retenção, download e tráfego sem repetir servidor fixo.'},
    {id:'skill', product:'skills', name:'Skill privada', model:'Criação / atualização / execução', unit:'ação IA', usd:null, qty:4, evidence:'Pendente', note:'Instruções, referências autorizadas, versões e contexto. Catálogo público e leitura sem IA gratuitos.'}
  ].map(x => Object.freeze({...x, date}));
  const defaults = Object.freeze({fx:6.25, pricingFx:6.25, tax:.17, markup:7.5, dev:15000, devUsd:1000, server:1600, investment:150000,
    monthly:20, annual:5, budgetUsd:20, discount:0, utilization:1, retries:.1, videoFactor:1,
    routerFee:0, directShare:.5, paymentFee:0, extraSold:1000, extraUsed:500, extraOpening:0,
    openingCash:0, otherFixed:0, unknownBudget:null, rates:{}, quantities:{}});
  const money = n => n == null || !Number.isFinite(n) ? 'Pendente' : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(n);
  const percent = n => n == null || !Number.isFinite(n) ? '—' : new Intl.NumberFormat('pt-BR',{style:'percent',maximumFractionDigits:2}).format(n);
  function numeric(n, key, min=0, max=Infinity) {
    if (typeof n !== 'number' || !Number.isFinite(n) || n < min || n > max) throw new RangeError('Valor inválido: '+key);
    return n;
  }
  function calculate(input={}) {
    const v={...defaults,...input};
    for(const k of Object.keys(defaults)) if(typeof defaults[k]==='number') numeric(v[k],k);
    ['tax','discount','directShare','paymentFee'].forEach(k=>numeric(v[k],k,0,1));
    if (!v.fx || !v.pricingFx || !v.markup) throw new RangeError('Câmbio e multiplicador devem ser positivos');
    if(v.extraUsed > v.extraOpening+v.extraSold) throw new RangeError('Consumo de extras excede o saldo comprado');
    if(v.unknownBudget!==null) numeric(v.unknownBudget,'orçamento de lacunas');
    const customers=v.monthly+v.annual, pending=[], products={workspace:0,studio:0,connect:0,skills:0,planner:0};
    const operations=catalog.map(op=>{
      const override=v.rates?.[op.id];
      const rate=Object.hasOwn(v.rates||{},op.id)?(override===null?null:numeric(override,op.id)):op.usd;
      const qty=numeric(v.quantities?.[op.id]??op.qty,op.id+' quantidade')*v.utilization*customers*(op.id==='video'?v.videoFactor:1);
      const fee=op.feeIncluded?0:v.routerFee*(['chat','image','draft','planner'].includes(op.id)?1-v.directShare:1);
      const cost=rate===null?null:rate*qty*(1+v.retries)*(1+fee)*v.fx;
      if(rate===null && qty>0) pending.push(op.name);
      products[op.product]+=cost??0;
      return {...op,rate,quantity:qty,cost};
    });
    const price=v.budgetUsd*v.pricingFx*v.markup;
    const monthlyRevenue=v.monthly*price, annualRevenue=v.annual*price*(1-v.discount);
    const revenue=monthlyRevenue+annualRevenue+v.extraUsed;
    const taxes=revenue*v.tax, payments=revenue*v.paymentFee;
    const operationCost=Object.values(products).reduce((a,b)=>a+b,0);
    const extraCost=v.extraUsed/v.markup*v.fx/v.pricingFx;
    const variable=operationCost+extraCost+payments+(v.unknownBudget??0);
    const contribution=revenue-taxes-variable, contributionRate=revenue?contribution/revenue:null;
    const fixed=v.dev+v.devUsd*v.fx+v.server+v.otherFixed;
    const result=contribution-fixed;
    const provisional=pending.length>0;
    let cash=v.openingCash, operatingCash=0, payback=null, expiredExtras=0;
    const extraLots=[{month:0,balance:v.extraOpening}];
    const cashflow=Array.from({length:36},(_,i)=>{
      for(const lot of extraLots) if(i-lot.month>=12){expiredExtras+=lot.balance;lot.balance=0;}
      extraLots.push({month:i,balance:v.extraSold});
      const consumed=Math.min(v.extraUsed,extraLots.reduce((n,l)=>n+l.balance,0));
      let left=consumed;for(const lot of extraLots){const used=Math.min(left,lot.balance);lot.balance-=used;left-=used;}
      const extraBalance=extraLots.reduce((n,l)=>n+l.balance,0);
      const annualCash=i%12===0?annualRevenue*12:0;
      const receipts=monthlyRevenue+annualCash+v.extraSold;
      const monthRevenue=monthlyRevenue+annualRevenue+consumed;
      const monthExtraCost=consumed/v.markup*v.fx/v.pricingFx;
      // Payment fees follow cash receipts; no double charge of the accrued DRE fee.
      const out=monthRevenue*v.tax+operationCost+monthExtraCost+(v.unknownBudget??0)+fixed+receipts*v.paymentFee, net=receipts-out;
      cash+=net; operatingCash+=net;
      if(payback===null && operatingCash>=v.investment) payback=i+1;
      return {month:i+1,receipts,annualCash,out,net,cash,operatingCash,annualDeferred:annualRevenue*(11-i%12),extraBalance,consumed,expiredExtras};
    });
    return {v,customers,price,monthlyRevenue,annualRevenue,revenue,taxes,payments,products,operations,operationCost,extraCost,variable,contribution,contributionRate,fixed,result,
      breakEven:contributionRate>0?fixed/contributionRate:null, effectiveMarkup:v.markup*(1-v.discount)*v.pricingFx/v.fx,
      pending,provisional,cashflow,payback, currentBurn:fixed+250};
  }
  function simplified(markup, fixed=22850, tax=.17) {
    numeric(markup,'markup',Number.EPSILON); const rate=1-tax-1/markup;
    return {markup,rate,breakEven:rate>0?fixed/rate:null};
  }
  // Prototype ledger. Immutable quote snapshot and FIFO-by-expiry reservations.
  function wallet(now='2026-09-15') {
    return {now,lots:[{id:'monthly',kind:'Assinatura',expires:'2026-09-30',remaining:1000},{id:'extra',kind:'Pacote extra',expires:'2027-09-15',remaining:500}],jobs:[],events:[]};
  }
  function reserve(w,quote) {
    numeric(quote.credits,'créditos',1);
    const lots=w.lots.filter(l=>l.expires>=w.now).sort((a,b)=>a.expires.localeCompare(b.expires));
    if(lots.reduce((a,b)=>a+b.remaining,0)<quote.credits) throw new Error('Saldo insuficiente');
    let left=quote.credits; const allocations=[];
    for(const lot of lots){const n=Math.min(left,lot.remaining);if(n){lot.remaining-=n;left-=n;allocations.push({id:lot.id,n});}}
    const job={id:w.jobs.length+1,state:'reserved',quote:Object.freeze({...quote}),allocations,providerCost:0};
    w.jobs.push(job);w.events.unshift({label:'Reserva #'+job.id,credits:-quote.credits});return job;
  }
  function settle(w,id,success,providerCost=0) {
    numeric(providerCost,'custo provedor'); const job=w.jobs.find(j=>j.id===id);
    if(!job || job.state!=='reserved') throw new Error('Reserva já encerrada ou inexistente');
    job.state=success?'consumed':'refunded';job.providerCost=providerCost;
    if(!success) for(const a of job.allocations) w.lots.find(l=>l.id===a.id).remaining+=a.n;
    w.events.unshift({label:(success?'Concluído #':'Estorno #')+id,credits:success?0:job.quote.credits});return job;
  }
  return {date,sources,catalog,defaults,money,percent,calculate,simplified,wallet,reserve,settle};
});
