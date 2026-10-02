import React from 'react';
import {ChevronRight} from '@untitledui/icons';
import {ReportsNativeSelect} from '../ReportsNativeSelect.jsx';
import {ReportsDateRange} from '../ReportsDateRange.jsx';
import {APP_BASE, navigateOnClick} from './routes.js';
import {useReportsContext} from './context.js';

/** Client and period, kept in the header so the analysed context changes without leaving the page. */
export function ContextSelector({clients = [], client, showPeriod}) {
  const {period, setPeriod, switchClient} = useReportsContext();
  return <div className="rs-context" aria-label="Contexto da análise">
    {clients.length > 1 ? <label className="rs-context__client"><span className="reports-sr-only">Cliente</span>
      <ReportsNativeSelect value={client?.client_id ?? ''} onChange={event => switchClient(event.target.value)} aria-label="Cliente">
        {clients.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </ReportsNativeSelect></label>
      : client?.client_name ? <span className="rs-context__name" title="Cliente">{client.client_name}</span> : null}
    {showPeriod && period && <ReportsDateRange value={period} onChange={setPeriod}/>}
  </div>;
}

/** Second navigation level: real links, so tabs can be opened in a new tab and survive reloads. */
export function SectionTabs({tabs, active}) {
  return <nav className="rs-tabs" aria-label="Seções">
    {tabs.map(([path, label]) => {
      const href = `${APP_BASE}/${path}`;
      return <a key={path} href={href} className={active === path ? 'is-active' : ''} aria-current={active === path ? 'page' : undefined}
        onClick={event => navigateOnClick(event, href)}>{label}</a>;
    })}
  </nav>;
}

/**
 * The one title of every screen. Inner components use h2/h3 only.
 * `crumbs` appear only on entity pages (third level), e.g. Mídia / Campanhas / Luz para Todos.
 */
export function PageHeader({title, description, crumbs, actions, context, tabs, activeTab}) {
  return <header className={`rs-header${tabs ? ' rs-header--tabs' : ''}`}>
    <div className="rs-header__row">
      <div className="rs-header__copy">
        {crumbs?.length > 0 && <ol className="rs-crumbs" aria-label="Você está em">{crumbs.map(([label, href], index) => <li key={label}>
          {href ? <a href={href} onClick={event => navigateOnClick(event, href)}>{label}</a> : <span aria-current="page">{label}</span>}
          {index < crumbs.length - 1 && <ChevronRight size={14} aria-hidden="true"/>}
        </li>)}</ol>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="rs-header__actions">{actions}{context}</div>
    </div>
    {tabs && <SectionTabs tabs={tabs} active={activeTab}/>}
  </header>;
}
