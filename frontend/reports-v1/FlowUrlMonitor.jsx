import {AlertTriangle, CheckCircle, RefreshCw01, XCircle} from '@untitledui/icons';
import React from 'react';
import './flow-url-monitor.css';

const STATES = {
  online: {icon: CheckCircle, label: 'No ar'},
  degraded: {icon: AlertTriangle, label: 'Instável'},
  offline: {icon: XCircle, label: 'Fora do ar'},
  checking: {icon: RefreshCw01, label: 'Verificando'},
};

/** One tile per monitored URL: status icon, page name, path, HTTP code and response time. */
export function FlowUrlMonitor({pages = [], busy = false, alertNote = ''}) {
  const list = pages.map(page => ({...page, state: busy ? 'checking' : page.status}));
  const down = list.filter(page => page.state === 'offline' || page.state === 'degraded').length;
  return <div className="flow-url-monitor">
    <p className={`flow-url-monitor__summary${down ? ' is-down' : ''}`} role="status">
      {busy ? 'Verificando as páginas…' : down ? `${down} de ${list.length} páginas com problema` : `${list.length} de ${list.length} páginas no ar`}
      {alertNote && <small>{alertNote}</small>}
    </p>
    <ul className="flow-url-monitor__grid">
      {list.map((page, index) => {
        const {icon: Icon, label} = STATES[page.state] || STATES.checking;
        return <li key={`${page.host}:${page.path}:${index}`} className={`flow-url-monitor__tile is-${page.state}`}>
          <Icon size={22} aria-hidden="true"/>
          <span className="flow-url-monitor__text"><strong title={page.label}>{page.label}</strong><small title={`${page.host}${page.path}`}>{page.path}</small></span>
          <span className="flow-url-monitor__meta"><b>{label}</b><small>{page.http_status ? `HTTP ${page.http_status}` : '—'}{page.duration_ms != null ? ` · ${page.duration_ms} ms` : ''}</small></span>
          {page.state !== 'online' && page.state !== 'checking' && page.detail && <em>{page.detail}</em>}
        </li>;
      })}
    </ul>
  </div>;
}
