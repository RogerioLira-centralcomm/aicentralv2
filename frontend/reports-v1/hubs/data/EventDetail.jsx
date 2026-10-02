import React from 'react';
import {ReportsDrawer} from '../../ReportsDrawer.jsx';
import {reportUrl} from '../../reportsCommon.jsx';
import {friendlyAgo, friendlyDateTime} from '../../friendlyDates.js';
import {AppLink, MetricGroup, Section} from '../../shell/primitives.jsx';
import {number, percent} from '../shared.jsx';

const KIND = {conversion: 'Conversão', custom_event: 'Personalizado', form_submit: 'Formulário enviado', whatsapp_click: 'WhatsApp', page_view: 'Visualização', click: 'Clique'};

const breakdown = (rows, key) => {
  const map = new Map();
  rows.forEach(row => map.set(row[key], (map.get(row[key]) || 0) + Number(row.total)));
  return [...map.entries()].sort((a, b) => b[1] - a[1]);
};

/** Inspect one event without leaving the list: occurrences, where it fires, where visits came from and what to open next. */
export function EventDetail({event, rows, onClose}) {
  const same = event ? rows.filter(row => row.event_kind === event.event_kind && row.event_name === event.event_name) : [];
  const total = same.reduce((sum, row) => sum + Number(row.total), 0);
  const mapped = same.reduce((sum, row) => sum + Number(row.mapped || 0), 0);
  const last = same.map(row => row.last_occurred_at).sort().at(-1);
  const pages = breakdown(same, 'page_path');
  const sources = breakdown(same, 'source_label');
  const isConversion = ['conversion', 'form_submit', 'whatsapp_click'].includes(event?.event_kind);
  return <ReportsDrawer className="rs-drawer" open={Boolean(event)} onOpenChange={open => {if (!open) onClose();}} title={event?.event_name || ''}
    description={event ? `${KIND[event.event_kind] || event.event_kind} · última ocorrência ${friendlyAgo(last)}` : ''}
    footer={event && <div className="rs-actions">
      {isConversion && <AppLink className="rs-link" href={reportUrl('journey/conversions')}>Ver conversões</AppLink>}
      <AppLink className="rs-link" href={reportUrl('journey/navigation')}>Ver navegação</AppLink>
      <AppLink className="rs-link" href={reportUrl('flows')}>Usar em um fluxo</AppLink>
    </div>}>
    {event && <div className="rs-stack rs-drawer-body">
      <MetricGroup label="Resumo do evento" items={[
        {label: 'Ocorrências', value: number(total)},
        {label: 'Páginas', value: number(pages.length)},
        {label: 'Em etapas de fluxo', value: percent(mapped, total), detail: mapped ? 'Associado a uma etapa' : 'Sem etapa mapeada'},
      ]}/>
      <Section title="Onde acontece" description="Páginas com mais ocorrências">
        <ul className="rs-bars">{pages.slice(0, 8).map(([path, count]) => <li key={path}><span className="rs-path" title={path}>{path}</span><i><b style={{width: `${Math.max(2, count * 100 / (total || 1))}%`}}/></i><strong>{number(count)}</strong></li>)}</ul>
      </Section>
      <Section title="Origem das visitas" description="UTM ou domínio de referência">
        <ul className="rs-bars">{sources.slice(0, 6).map(([source, count]) => <li key={source}><span>{source}</span><i><b style={{width: `${Math.max(2, count * 100 / (total || 1))}%`}}/></i><strong>{percent(count, total)}</strong></li>)}</ul>
      </Section>
      <p className="rs-muted">Última ocorrência: {friendlyDateTime(last)}. Os números consideram o período do topo da página.</p>
    </div>}
  </ReportsDrawer>;
}
