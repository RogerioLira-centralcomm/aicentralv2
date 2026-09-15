self.addEventListener('push',event=>{
  let data;try{data=event.data.json();}catch{return;}
  event.waitUntil(self.registration.showNotification(data.title||'Cadu Media Studio',{body:data.body||'Resultado disponível.',tag:data.tag,data:{url:data.url}}));
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const url=new URL(event.notification.data?.url||'/parametros/modelagem-criativos/video',self.location.origin);
  if(url.origin!==self.location.origin||!url.pathname.startsWith('/parametros/'))return;
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(async windows=>{
    const existing=windows.find(client=>new URL(client.url).pathname===url.pathname);
    if(existing){await existing.navigate(url.href);return existing.focus();}
    return clients.openWindow(url.href);
  }));
});
