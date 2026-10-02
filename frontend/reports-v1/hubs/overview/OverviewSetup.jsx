import React from 'react';
import {CheckCircle} from '@untitledui/icons';
import {Button as UntitledButton} from '../../../cadu-design-system/untitled-kit/button.tsx';
import {reportUrl} from '../../reportsCommon.jsx';

/** Onboarding while the client has no media data yet: one next action and the preparation checklist. */
export function OverviewSetup({data, sites, sources, imported}) {
  const activeSource = sources?.find(source => source.source_kind === 'google_ads_script' && !source.revoked_at);
  const sourceRegistered = Boolean(activeSource);
  const campaignRegistered = data.campaigns.length > 0;
  const activeSite = sites?.find(site => site.enabled && !site.revoked_at && Number(site.events_30d) > 0);
  const siteRegistered = sites?.some(site => site.enabled && !site.revoked_at);
  const nextAction = imported?.conflicts
    ? {title:'Revise os dados importados', description:'Há valores divergentes que precisam de confirmação antes de aparecerem nos relatórios.', label:'Revisar importações', href:reportUrl('imports')}
    : sources === null
      ? {title:'Confira os dados de mídia', description:'Não conseguimos confirmar o estado da integração. Verifique as fontes conectadas e os últimos envios.', label:'Ver fontes de dados', href:reportUrl('monitor')}
      : !sourceRegistered
      ? {title:'Comece pelos dados de mídia', description:'Conecte uma fonte de mídia para acompanhar impressões, cliques e investimento aqui.', label:'Conectar fonte de mídia', href:reportUrl('monitor')}
      : !campaignRegistered
        ? {title:'Organize as campanhas deste cliente', description:'A conta já está cadastrada. Associe uma campanha para reunir seus resultados.', label:'Adicionar campanha', href:reportUrl('campaigns')}
        : {title:'Aguardando os primeiros dados de mídia', description:'As contas e campanhas estão cadastradas. Confira o envio de dados para preencher esta visão.', label:'Ver fontes de dados', href:reportUrl('monitor')};
  const steps = [
    {label:'Fonte de mídia', detail:activeSource?.last_used_at ? 'Dados recebidos' : sourceRegistered ? 'Conectada; aguardando envio' : sources ? 'Nenhuma fonte conectada' : 'Verificar integração', done:sourceRegistered, href:reportUrl('monitor')},
    {label:'Site e eventos', detail:activeSite ? 'Eventos recebidos' : siteRegistered ? 'Site cadastrado; aguardando eventos' : sites ? 'Nenhum site conectado' : 'Verificar instalação', done:Boolean(activeSite), href:reportUrl('supertag')},
    {label:'Campanhas', detail:campaignRegistered ? `${data.campaigns.length} cadastrada${data.campaigns.length === 1 ? '' : 's'}` : 'Nenhuma campanha cadastrada', done:campaignRegistered, href:reportUrl('campaigns')},
  ];
  return <section className="reports-overview-setup" aria-labelledby="reports-overview-next-title">
    <div className="reports-overview-setup__next">
      <span className="reports-overview-setup__eyebrow">Próxima ação</span>
      <h2 id="reports-overview-next-title">{nextAction.title}</h2>
      <p>{nextAction.description}</p>
      <div className="reports-overview-setup__actions"><UntitledButton color="primary" size="sm" href={nextAction.href}>{nextAction.label}</UntitledButton><UntitledButton color="tertiary" size="sm" href={reportUrl('imports')}>Enviar arquivo</UntitledButton></div>
    </div>
    <div className="reports-overview-setup__progress" aria-label="Preparação do Reports">
      <div className="reports-overview-setup__progress-heading"><h3>Preparação</h3><span>{steps.filter(step => step.done).length} de {steps.length} prontos</span></div>
      <ol>{steps.map((step, index) => <li key={step.label}><a href={step.href} aria-label={`${step.label}: ${step.detail}. ${step.done ? 'Ver' : 'Configurar'}`}><span className={`reports-overview-setup__step-icon${step.done ? ' is-done' : ''}`} aria-hidden="true">{step.done ? <CheckCircle size={18}/> : index + 1}</span><span className="reports-overview-setup__step-copy"><strong>{step.label}</strong><small>{step.detail}</small></span><span className="reports-overview-setup__step-arrow" aria-hidden="true">→</span></a></li>)}</ol>
    </div>
  </section>;
}
