import {AlertCircle, CheckCircle, Clock, File01, Flag01, Globe01, Mail01, Target01, Zap} from '@untitledui/icons';

export const flowBlockRegistry = Object.freeze({
  source: {kind:'traffic.source',label:'Origem de tráfego',shape:'circle',icon:Globe01,trackable:false},
  page: {kind:'page.generic',label:'Página',shape:'page',icon:Globe01,trackable:true},
  form: {kind:'page.form',label:'Formulário',shape:'page',icon:File01,trackable:true},
  event: {kind:'event.custom',label:'Evento',shape:'diamond',icon:Flag01,trackable:true},
  condition: {kind:'logic.condition',label:'Condição',shape:'diamond',icon:Target01,trackable:false},
  delay: {kind:'logic.delay',label:'Espera',shape:'circle',icon:Clock,trackable:false},
  segment: {kind:'crm.segment',label:'Segmento',shape:'diamond',icon:Target01,trackable:false},
  conversion: {kind:'conversion.generic',label:'Conversão',shape:'diamond',icon:CheckCircle,trackable:true},
  webhook: {kind:'utility.webhook',label:'Webhook',shape:'circle',icon:Zap,trackable:false},
  whatsapp: {kind:'event.whatsapp',label:'Clique WhatsApp',shape:'circle',icon:Mail01,trackable:true},
  error: {kind:'page.error',label:'Página de erro',shape:'page',icon:AlertCircle,trackable:true},
});

export const flowBlockFor = node => flowBlockRegistry[node?.type] || flowBlockRegistry.event;
