import {AlertCircle, Annotation, CheckCircle, Clock, File01, Flag01, Globe01, Mail01, QrCode01, Target01, Zap} from '@untitledui/icons';

// One registry drives palette, canvas shape and inspector metadata. These
// entries describe a journey; they do not execute CRM or communication actions.
const groups = [
  ['Tráfego pago','source','circle','paid',[
    ['traffic.google_search','Google Ads · Search','google'],['traffic.google_display','Google Ads · Display','google'],
    ['traffic.youtube','YouTube Ads','youtube'],['traffic.meta','Meta Ads','meta'],['traffic.instagram','Instagram Ads','instagram'],
    ['traffic.tiktok','TikTok Ads','tiktok'],['traffic.linkedin','LinkedIn Ads','linkedin'],['traffic.dv360','DV360','dv360'],
    ['traffic.retargeting','Retargeting','retargeting']]],
  ['Tráfego orgânico','source','circle','neutral',[
    ['traffic.organic_search','Busca orgânica','organic'],['traffic.organic_social','Redes sociais','social'],
    ['traffic.direct','Acesso direto','direct'],['traffic.referral','Referência','referral'],
    ['traffic.affiliate','Afiliado','affiliate'],['traffic.qr','QR Code','qr'],
    ['traffic.ai_chatgpt','ChatGPT','chatgpt'],['traffic.ai_gemini','Gemini','gemini'],['traffic.ai_claude','Claude','claude']]],
  ['Comunicação','source','circle','communication',[
    ['communication.email','E-mail','email'],['communication.email_sequence','Sequência de e-mail','email'],
    ['communication.sms','SMS','sms'],['communication.whatsapp','WhatsApp','whatsapp'],
    ['communication.push','Push','push'],['communication.call','Ligação','phone']]],
  ['Páginas','page','page','neutral',[
    ['page.generic','Página / URL','generic'],['page.landing','Landing page','landing'],['page.blog','Blog','blog'],
    ['page.sales','Página de vendas','sales'],['page.form','Formulário','form'],['page.checkout','Checkout','checkout'],
    ['page.thanks','Obrigado','thanks'],['page.webinar','Webinar','webinar'],['page.calendar','Agendamento','calendar'],
    ['page.error','Página de erro','error']]],
  ['Eventos','event','diamond','capture',[
    ['event.custom','Evento personalizado'],['event.button','Clique em botão'],['event.whatsapp','Clique WhatsApp'],
    ['event.form_submit','Envio de formulário'],['event.scroll','Rolagem'],['event.video','Vídeo assistido'],['event.download','Download']]],
  ['Conversão','conversion','diamond','success',[
    ['conversion.lead','Lead'],['conversion.signup','Cadastro'],['conversion.purchase','Compra'],
    ['conversion.upsell','Upsell'],['conversion.customer','Cliente'],['conversion.generic','Conversão personalizada']]],
  ['Segmentação e CRM','segment','diamond','warning',[
    ['crm.segment','Segmento'],['logic.condition','Divisão / condição'],['crm.pipeline','Pipeline'],
    ['crm.deal_won','Negócio ganho'],['crm.deal_lost','Negócio perdido'],['crm.meeting','Reunião agendada']]],
  ['Anotações','note','note','neutral',[
    ['annotation.note','Nota e checklist']]],
  ['Utilitários','webhook','circle','neutral',[
    ['logic.delay','Espera'],['utility.webhook','Webhook']]],
];

const typeFor = (kind,base) => ({'page.form':'form','page.thanks':'conversion','page.error':'error',
  'event.whatsapp':'whatsapp','event.form_submit':'form','logic.condition':'condition','logic.delay':'delay',
  'utility.webhook':'webhook'})[kind] || base;
const iconFor = (kind,type) => type==='note'?Annotation:kind==='traffic.qr'?QrCode01:kind.includes('error')||kind.includes('lost')?AlertCircle:
  kind.includes('email')||kind.includes('whatsapp')||kind.includes('sms')?Mail01:
  kind.includes('delay')||kind.includes('meeting')||kind.includes('calendar')?Clock:
  type==='conversion'?CheckCircle:type==='form'?File01:type==='condition'||type==='segment'?Target01:
  type==='event'?Flag01:type==='webhook'?Zap:Globe01;
const toneFor = (kind,base) => kind.includes('error')||kind.includes('lost')?'error':
  kind.includes('thanks')||kind.includes('won')?'success':base;
export const flowBlocks = Object.freeze(groups.flatMap(([category,baseType,shape,tone,entries])=>entries.map(([kind,label,detail])=>{
  const type=typeFor(kind,baseType);
  return {kind,type,category,label,shape:['segment','condition','webhook','delay'].includes(type)?'visual':kind==='page.form'||kind==='page.thanks'||kind==='page.error'?'page':shape,
    icon:iconFor(kind,type),tone:toneFor(kind,tone),trackable:['page','form','event','conversion','whatsapp','error'].includes(type),
    source:baseType==='source'?detail:undefined,preview:baseType==='page'?detail:undefined};
})));
export const flowBlockRegistry = Object.freeze(Object.fromEntries(flowBlocks.map(item=>[item.kind,item])));
const fallbackKinds = {source:'traffic.direct',page:'page.generic',form:'page.form',event:'event.custom',
  condition:'logic.condition',delay:'logic.delay',segment:'crm.segment',conversion:'conversion.generic',
  webhook:'utility.webhook',whatsapp:'event.whatsapp',error:'page.error',note:'annotation.note'};
const sourceBlocks = new Map(flowBlocks.filter(item=>item.source).reverse().map(item=>[item.source,item]));
// Older configs keep only the platform in `source`; resolve it before the generic fallback.
export const flowBlockFor = node => flowBlockRegistry[node?.kind] || (node?.type==='source'&&sourceBlocks.get(node?.source)) || flowBlockRegistry[fallbackKinds[node?.type]] || flowBlockRegistry['event.custom'];
export const flowPaletteGroups = Object.freeze(groups.map(([category])=>[category,flowBlocks.filter(item=>item.category===category)]));
