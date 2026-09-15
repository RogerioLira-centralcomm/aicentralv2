import {get,post} from './api.js';
import {state} from './state.js';
import {notify} from '../media-progress.js';
export async function enablePush(){
  if(!('serviceWorker' in navigator)||!('PushManager' in window)||!globalThis.Notification){notify('Este navegador não oferece notificações persistentes. Consulte Renderizações.');return;}
  const client=state.clientId;
  if(!client){notify('Escolha uma marca.');return;}
  // Ask during the user gesture, before waiting for network I/O.
  const permission=await Notification.requestPermission();if(permission!=='granted'){notify('Permissão de notificação não concedida.');return;}
  try{
    const info=await get(`/parametros/api/format-lab/studio/push?client_id=${encodeURIComponent(client)}`);
    if(!info.available){notify('O servidor precisa instalar as dependências do worker para enviar notificações.');return;}
    const registration=await navigator.serviceWorker.register('/parametros/studio-notifications.js',{scope:'/parametros/'});
    if(!registration.active)await new Promise((resolve,reject)=>{
      const worker=registration.installing||registration.waiting;if(!worker){reject(new Error('Ativação indisponível'));return;}
      const timeout=setTimeout(()=>reject(new Error('A ativação demorou. Tente novamente.')),15000);
      worker.addEventListener('statechange',()=>{if(worker.state==='activated'){clearTimeout(timeout);resolve();}});
    });
    const bytes=Uint8Array.from(atob(info.public_key.replaceAll('-','+').replaceAll('_','/')),c=>c.charCodeAt(0));
    const subscription=await registration.pushManager.getSubscription()||await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:bytes});
    await post('/parametros/api/format-lab/studio/push',{client_id:client,subscription:subscription.toJSON()});
    notify('Notificações ativadas para esta marca, inclusive com a página fechada. A entrega depende das permissões do sistema.');
  }catch(error){notify(`Não foi possível ativar notificações: ${error.message}`);}
}
