import React from 'react';
import {ChevronRight} from '@untitledui/icons';
import {platformName} from './media.jsx';
import {ReportsNativeSelect} from '../ReportsNativeSelect.jsx';
import {ReportsDateRange} from '../ReportsDateRange.jsx';
import {APP_BASE, navigateOnClick} from './routes.js';
import {useReportsContext} from './context.js';

/** Sources, campaigns or sites of the chosen client, plus the period; the client itself is picked in the sidebar. Kept in the header so the analysed context changes without leaving the page. */
export function ContextSelector({showPeriod, accounts, campaigns, sites, siteRequired = false}) {
  const {period, setPeriod, scope, setScope} = useReportsContext();
  const sources = (accounts || []).filter(item => item.status !== 'disabled');
  const scoped = (campaigns || []).filter(item => !scope.account || String(item.account_id) === scope.account);
  return <div className="rs-context" aria-label="Contexto da análise">
    {accounts && sources.length > 0 && <label className="rs-context__client"><span className="reports-sr-only">Fonte de dados</span>
      <ReportsNativeSelect value={scope.account} onChange={event => setScope({...scope, account: event.target.value, campaign: ''})} aria-label="Fonte de dados">
        <option value="">Todas as fontes</option>
        {sources.map(item => <option key={item.id} value={item.id}>{item.name || item.external_id} · {platformName(item.platform)}</option>)}
      </ReportsNativeSelect></label>}
    {campaigns && (campaigns.length > 0) && <label className="rs-context__client"><span className="reports-sr-only">Campanha</span>
      <ReportsNativeSelect value={scope.campaign} onChange={event => setScope({...scope, account: scope.account || String(campaigns.find(item => String(item.id) === event.target.value)?.account_id || ''), campaign: event.target.value})} aria-label="Campanha">
        <option value="">Todas as campanhas</option>
        {scope.account || sources.length < 2 ? scoped.map(item => <option key={item.id} value={item.id}>{item.name}</option>)
          : sources.map(source => {
            const own = scoped.filter(item => item.account_id === source.id);
            return own.length ? <optgroup key={source.id} label={`${source.name || source.external_id} · ${platformName(source.platform)}`}>{own.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</optgroup> : null;
          }).concat(scoped.filter(item => !sources.some(source => source.id === item.account_id)).map(item => <option key={item.id} value={item.id}>{item.name}</option>))}
      </ReportsNativeSelect></label>}
    {sites && sites.length > 0 && <label className="rs-context__client"><span className="reports-sr-only">Site</span>
      <ReportsNativeSelect value={scope.site} onChange={event => setScope({...scope, site: event.target.value})} aria-label="Site">
        {sites.length > 1 && !siteRequired && <option value="">Todos os sites</option>}
        {sites.map(item => <option key={item.id} value={item.id}>{item.allowed_host || item.label}</option>)}
      </ReportsNativeSelect></label>}
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
