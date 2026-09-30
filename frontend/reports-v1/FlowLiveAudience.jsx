import React from 'react';
import {ReportsActionButton as Button} from './ReportsActionButton.jsx';
import {XClose} from '@untitledui/icons';
const labels={page_view:'Página',form_submit:'Formulário enviado',conversion:'Conversão',custom_event:'Evento',whatsapp_click:'WhatsApp',error_view:'Página de erro'};
export function FlowLiveAudience({snapshot,ready,onClose,filter,onFilterChange}) {
  const sessions=ready?snapshot?.sessions||[]:[];
  return <aside className="flow-workspace-panel is-inspector flow-live-audience"><header><strong>Navegação ao vivo</strong><Button color="tertiary" size="sm" aria-label="Fechar navegação ao vivo" onClick={onClose}><XClose size={18}/></Button></header>
    <p className="flow-audience-explanation">Online: atividade nos últimos 90 segundos, inclusive sessões de publicações anteriores. Cada caminho permanece na publicação em que começou; o mapa mostra apenas a publicação atual.</p>
    {ready?<><div className="flow-audience-totals"><span><b>{snapshot.active_visitors??'—'}</b> visitantes medidos</span><span><b>{snapshot.active_sessions??'—'}</b> sessões online</span><span><b>{snapshot.sessions_on_conversion_pages??'—'}</b> sessões em página de conversão</span></div>
    <label>Identificação<select value={filter} onChange={event=>onFilterChange(event.target.value)}><option value="all">Todas as sessões</option><option value="known">Identificadas</option><option value="anonymous">Anônimas</option><option value="unavailable">Identificação indisponível</option></select></label>
    <div className="flow-panel-scroll">{sessions.map(item=><details key={item.session_id} className="flow-audience-session"><summary><strong>{item.identity_status==='known'?(item.display_name||'Visitante identificado'):item.identity_status==='anonymous'?'Visitante anônimo':'Identificação indisponível'}</strong><small>Sessão {item.session_id.slice(0,8)} · {item.page} · publicação v{item.revision}</small><small>{item.conversions} conversões · {new Date(item.last_seen_at).toLocaleTimeString('pt-BR')}</small></summary><ol>{item.journey.map((event,index)=><li key={`${event.at}:${index}`}><strong>{labels[event.kind]||'Interação'}</strong><span>{event.path}</span><time>{new Date(event.at).toLocaleTimeString('pt-BR')}</time></li>)}</ol></details>)}{!sessions.length&&<p>Nenhuma sessão online neste filtro.</p>}</div>{snapshot.sessions_truncated&&<small>Exibindo 100 de {snapshot.sessions_total} sessões neste filtro.</small>}</>:<p role="status">Aguardando uma atualização válida da publicação atual. Retome a atualização para acompanhar a navegação.</p>}
    <small>Identidades são fornecidas pelo site. Identificadores de visitantes não equivalem necessariamente a pessoas únicas entre dispositivos.</small>
  </aside>;
}
