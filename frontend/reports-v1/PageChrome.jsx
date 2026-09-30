import React from 'react';
import {Button as UntitledButton} from './untitled-kit/src/components/base/buttons/button.tsx';
import {FilterLines, RefreshCw01} from '@untitledui/icons';

export const REPORT_FILTER_DEFAULTS = Object.freeze({
  platform: '', account: '', campaign: '', period: '30', startDate: '', endDate: '',
});

export const REPORT_PAGE_META = {
  overview: {title: 'Visão geral', description: 'Acompanhe mídia, dados importados e resultados deste cliente.'},
  accounts: {title: 'Contas', description: 'Organize as contas de mídia vinculadas a este cliente.'},
  campaigns: {title: 'Campanhas', description: 'Consulte campanhas, identifique sua origem e abra os resultados.'},
  reports: {title: 'Relatórios', description: 'Crie e consulte relatórios de mídia deste cliente.'},
  imports: {title: 'Importações', description: 'Envie arquivos e revise os dados antes de incluí-los nos relatórios.'},
  monitor: {title: 'Dados de mídia', description: 'Conecte fontes e acompanhe os envios recebidos.'},
  supertag: {title: 'Super Tag', description: 'Instale uma única tag para medir atividade consentida no site.'},
  flow: {title: 'Fluxos', description: 'Desenhe jornadas do site e acompanhe cada etapa.'},
  events: {title: 'Eventos', description: 'Explore a atividade recebida e prepare eventos personalizados.'},
  links: {title: 'Link Tester', description: 'Verifique destinos e associe links às campanhas corretas.'},
  access: {title: 'Acessos', description: 'Gerencie quem pode consultar e operar os dados deste cliente.'},
};

export function ReportsPageHeader({page, clients = [], client, onAction, titleOverride, descriptionOverride}) {
  const meta = REPORT_PAGE_META[page] || REPORT_PAGE_META.overview;
  const chooseClient = event => {
    const url = new URL(window.location.href);
    url.searchParams.set('client_id', event.target.value);
    window.location.assign(url.href);
  };

  return <header className="reports-page-header"><div className="reports-page-header__inner">
    <div className="reports-page-header__copy">
      <h1>{titleOverride || meta.title}</h1>
      <p className="reports-sr-only">{descriptionOverride || meta.description}</p>
    </div>
    <div className="reports-page-header__actions">
      {onAction && <UntitledButton className="reports-page-header__action" size="sm" color="tertiary" onPress={onAction.onClick}>{onAction.label}</UntitledButton>}
      {clients.length > 1 ? <label className="reports-client-select"><span className="reports-sr-only">Cliente Reports</span>
        <select value={client?.client_id ?? ''} onChange={chooseClient} aria-label="Cliente Reports">
          {clients.map(item => {
            const isOrganization = Number(item.id) === Number(client?.organization_id);
            return <option key={item.id} value={item.id}>{item.name}{!isOrganization ? ' · Reports' : ''}</option>;
          })}
        </select>
      </label> : null}
    </div>
  </div></header>;
}

export function ReportsFilterBar({data, filters, onChange, onRefresh}) {
  const platforms = [...new Set((data?.accounts || []).map(item => item.platform))];
  const accounts = (data?.accounts || []).filter(item => item.account_kind === 'advertiser' &&
    (!filters.platform || item.platform === filters.platform));
  const campaigns = (data?.campaigns || []).filter(item =>
    (!filters.platform || item.platform === filters.platform) &&
    (!filters.account || String(item.account_id) === filters.account));
  const activeCount = [filters.platform, filters.account, filters.campaign].filter(Boolean).length;
  const clearFilters = () => onChange({platform: '', account: '', campaign: ''});

  return <section className="reports-filter-bar" aria-label="Filtros da página">
    <div className="reports-filter-bar__heading"><span className="reports-filter-bar__icon" aria-hidden="true"><FilterLines size={16}/></span><div><strong>Filtros</strong><small>Refine os dados desta página</small></div></div>
    <div className="reports-filter-bar__fields">
    <label><span>Plataforma</span><select value={filters.platform} onChange={event => onChange({platform: event.target.value, account: '', campaign: ''})}>
      <option value="">Todas</option>{platforms.map(value => <option key={value} value={value}>{{google_ads:'Google Ads',meta_ads:'Meta Ads',microsoft_ads:'Microsoft Ads',other:'Outra'}[value] || value.replaceAll('_',' ')}</option>)}
    </select></label>
    <label><span>Conta</span><select value={filters.account} onChange={event => onChange({account: event.target.value, campaign: ''})}>
      <option value="">Todas</option>{accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select></label>
    <label><span>Campanha</span><select value={filters.campaign} onChange={event => onChange({campaign: event.target.value})}>
      <option value="">Todas</option>{campaigns.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select></label>
    <label className="reports-filter-bar__period"><span>Período</span><span className="reports-filter-bar__period-control"><svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="3.25" y="4.5" width="13.5" height="12" rx="2" stroke="currentColor" strokeWidth="1.4"/><path d="M6.5 3v3M13.5 3v3M3.5 8h13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg><select value={filters.period} onChange={event => {
      const period = event.target.value;
      const end = new Date();
      const start = new Date(end);
      start.setDate(start.getDate() - Number(period) + 1);
      const date = value => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
      onChange({period, startDate: date(start), endDate: date(end)});
    }}><option value="7">Últimos 7 dias</option><option value="30">Últimos 30 dias</option><option value="90">Últimos 90 dias</option></select></span></label>
    </div>
    <div className="reports-filter-bar__actions">{activeCount > 0 && <><span className="reports-filter-bar__count">{activeCount} {activeCount === 1 ? 'filtro ativo' : 'filtros ativos'}</span><UntitledButton size="sm" color="tertiary" onPress={clearFilters}>Limpar</UntitledButton></>}<UntitledButton className="reports-filter-bar__refresh" size="sm" color="tertiary" onPress={onRefresh}><RefreshCw01 size={16} aria-hidden="true"/>Atualizar</UntitledButton></div>
  </section>;
}
