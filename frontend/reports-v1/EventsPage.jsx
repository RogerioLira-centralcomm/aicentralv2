import React, {useEffect, useRef, useState} from 'react';
import {ArrowUpRight, CheckCircle, Code02, Copy01, CursorClick01, File02, MessageChatCircle, SearchLg, Stars01} from '@untitledui/icons';
import {Button} from '../cadu-design-system/untitled-kit/button.tsx';
import {Badge, BadgeWithDot} from '../cadu-design-system/untitled-kit/badges.tsx';
import {ReportsDrawer} from './ReportsDrawer.jsx';
import {ReportsFieldInput} from './ReportsFieldInput.jsx';
import {ReportsNativeSelect} from './ReportsNativeSelect.jsx';
import {ReportsTabs} from './ReportsTabs.jsx';
import {Alert, Callout, Card, EmptyNote, TD, TH} from './ReportsBlocks.jsx';
import {EventDetail} from './hubs/data/EventDetail.jsx';
import {integer, json, reportUrl, shortDate} from './reportsCommon.jsx';

const KINDS = [{id: 'all', label: 'Todos'}, {id: 'standard', label: 'Automáticos'}, {id: 'custom', label: 'Personalizados'}, {id: 'conversion', label: 'Conversões'}];
const ICONS = {conversion: CheckCircle, form_submit: File02, whatsapp_click: MessageChatCircle, custom_event: Stars01};
const TYPE = {custom_event: ['Personalizado', 'purple'], conversion: ['Conversão', 'success']};
const timeAgo = value => {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000));
  return minutes < 60 ? `há ${minutes} min` : minutes < 1440 ? `há ${Math.floor(minutes / 60)} h` : `há ${Math.floor(minutes / 1440)} d`;
};
const eventSlug = value => value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim().replace(/[\s-]+/g, '_').replace(/[^a-z0-9_]/g, '').replace(/^[^a-z]+/, '').slice(0, 80) || 'lead_qualified';

/** What the Super Tag is receiving: totals, every event/page/source combination, and custom events. */
export function EventsPage({data, filters, initialKind = 'all', refreshRevision}) {
  const [result, setResult] = useState({events: [], event_summary: {}});
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState(initialKind);
  const [source, setSource] = useState('all');
  const [openEvent, setOpenEvent] = useState(null);
  const [customOpen, setCustomOpen] = useState(false);
  const [error, setError] = useState('');
  const requestVersion = useRef(0);
  useEffect(() => setKind(initialKind), [initialKind]);
  useEffect(() => {
    const current = ++requestVersion.current;
    const params = new URLSearchParams({days: filters.period, start_date: filters.startDate, end_date: filters.endDate});
    if (filters.platform) params.set('platform', filters.platform);
    if (filters.account) params.set('account_id', filters.account);
    if (filters.campaign) params.set('campaign_id', filters.campaign);
    json(`/connect/api/v2/reports/flow/events?${params}`)
      .then(value => {if (current === requestVersion.current) {setResult(value); setError('');}})
      .catch(failure => {if (current === requestVersion.current) setError(failure.message);});
    return () => {requestVersion.current += 1;};
  }, [data.client.client_id, filters.period, filters.startDate, filters.endDate, filters.platform, filters.account, filters.campaign, refreshRevision]);

  const all = result.events || [];
  const sources = [...new Set(all.map(item => item.source_label))];
  const term = query.trim().toLowerCase();
  const visible = all.filter(item => {
    const typeMatch = kind === 'all' || (kind === 'custom' ? item.event_kind === 'custom_event' : kind === 'conversion' ? item.event_kind === 'conversion' : item.event_kind !== 'custom_event' && item.event_kind !== 'conversion');
    return typeMatch && (!term || `${item.event_name} ${item.page_path} ${item.source_label}`.toLowerCase().includes(term)) && (source === 'all' || item.source_label === source);
  });
  const summary = result.event_summary || {};
  const attributed = summary.total ? Math.round(Number(summary.attributed || 0) / Number(summary.total) * 100) : 0;
  const counts = {all: all.length, standard: all.filter(item => !['custom_event', 'conversion'].includes(item.event_kind)).length, custom: all.filter(item => item.event_kind === 'custom_event').length, conversion: all.filter(item => item.event_kind === 'conversion').length};
  const period = `${shortDate(filters.startDate)} – ${shortDate(filters.endDate)}`;

  return <div className="untitled-scope flex flex-col gap-6">
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-border-secondary shadow-xs ring-1 ring-secondary lg:grid-cols-4">
      {[['Ocorrências', integer(summary.total), period],
        ['Envios de formulário', integer(summary.form_submissions), 'Sem registrar os valores enviados'],
        ['Conversões', integer(summary.conversions), 'Páginas de conversão mapeadas'],
        ['Origem identificada', `${attributed}%`, attributed >= 80 ? 'Boa atribuição das origens' : summary.total ? 'Parte das visitas sem UTM ou referência' : 'Aguardando os primeiros eventos']].map(([term_, value, detail]) =>
        <div key={term_} className="min-w-0 bg-primary px-4 py-3 sm:px-5 sm:py-4"><dt className="text-sm font-medium text-tertiary">{term_}</dt><dd className="mt-1 text-display-xs font-semibold text-primary tabular-nums">{value}</dd><p className="mt-1 text-xs text-tertiary">{detail}</p></div>)}
    </dl>
    {error && <Alert>{error}</Alert>}
    <Card flush title="Atividade recebida" badge={<Badge type="pill-color" size="sm" color="gray">{integer(result.event_group_count ?? all.length)}</Badge>}
      description="Cada linha é uma combinação de evento, página e origem."
      actions={<>
        <Button size="md" color="secondary" href={reportUrl('flow')} iconTrailing={ArrowUpRight}>Mapear em Fluxos</Button>
        <Button size="md" color="primary" iconLeading={Code02} onPress={() => setCustomOpen(true)}>Evento personalizado</Button>
      </>}>
      <div className="flex flex-wrap items-center gap-3 border-b border-secondary px-6 py-3">
        <ReportsTabs label="Tipos de evento" items={KINDS.map(item => ({...item, count: counts[item.id] || undefined}))} value={kind} onChange={setKind}/>
        <div className="ml-auto flex flex-wrap gap-3 max-sm:ml-0 max-sm:w-full">
          <div className="w-64 max-sm:w-full"><ReportsFieldInput size="sm" type="search" aria-label="Buscar eventos" placeholder="Evento ou página" value={query} onChange={event => setQuery(event.target.value)}
            leading={<SearchLg size={16} aria-hidden="true" className="ml-3 shrink-0 text-fg-quaternary"/>}/></div>
          <div className="w-48 max-sm:w-full"><ReportsNativeSelect size="sm" aria-label="Filtrar fonte" value={source} onChange={event => setSource(event.target.value)}>
            <option value="all">Todas as fontes</option>{sources.map(item => <option key={item} value={item}>{item}</option>)}
          </ReportsNativeSelect></div>
        </div>
      </div>
      {visible.length ? <div className="overflow-x-auto"><table className="w-full min-w-[860px]">
        <thead><tr><th className={TH}>Evento</th><th className={TH}>Tipo</th><th className={TH}>Fonte</th><th className={`${TH} text-right`}>Ocorrências</th><th className={TH}>Última</th><th className={TH}>Fluxo</th></tr></thead>
        <tbody>{visible.map((item, index) => {
          const Icon = ICONS[item.event_kind] || CursorClick01;
          const [type, color] = TYPE[item.event_kind] || ['Automático', 'gray'];
          return <tr key={`${item.event_kind}:${item.event_name}:${item.page_path}:${item.source_label}:${index}`} className="hover:bg-primary_hover">
            <td className={TD}><div className="flex items-center gap-3">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-fg-quaternary"><Icon size={16} aria-hidden="true"/></span>
              <div className="min-w-0"><button type="button" onClick={() => setOpenEvent(item)} className="block max-w-80 truncate text-left font-medium text-primary hover:text-brand-secondary hover:underline">{item.event_name}</button>
                <p className="max-w-80 truncate font-mono text-xs text-tertiary">{item.page_path}</p></div>
            </div></td>
            <td className={TD}><Badge type="pill-color" size="sm" color={color}>{type}</Badge></td>
            <td className={TD}>{item.source_label}</td>
            <td className={`${TD} text-right font-medium text-primary tabular-nums`}>{integer(item.total)}</td>
            <td className={`${TD} whitespace-nowrap`}><p>{timeAgo(item.last_occurred_at)}</p><p className="text-xs text-tertiary">{shortDate(item.last_occurred_at)}</p></td>
            <td className={TD}><BadgeWithDot type="pill-color" size="sm" color={Number(item.mapped) > 0 ? 'success' : 'gray'}>{Number(item.mapped) > 0 ? 'Em uma etapa' : 'Sem etapa'}</BadgeWithDot></td>
          </tr>;
        })}</tbody>
      </table></div> : <EmptyNote title={all.length ? 'Nada corresponde aos filtros' : 'Nenhum evento no período'}>{all.length ? 'Ajuste a busca, o tipo ou a fonte.' : 'A atividade aparece quando a Super Tag enviar eventos.'}</EmptyNote>}
      <p className="px-6 py-3 text-xs text-tertiary">Mostrando {integer(visible.length)} de {integer(result.event_group_count ?? all.length)} combinações · {period}{Number(result.event_group_count) > all.length ? ' · as 300 mais recentes' : ''}</p>
    </Card>
    <CustomEventDrawer open={customOpen} onClose={() => setCustomOpen(false)}/>
    <EventDetail event={openEvent} rows={all} onClose={() => setOpenEvent(null)}/>
  </div>;
}

function CustomEventDrawer({open, onClose}) {
  const [name, setName] = useState('');
  const [copied, setCopied] = useState(false);
  const snippet = `window.CaduSuperTag && window.CaduSuperTag.trackEvent('${eventSlug(name)}');`;
  const copy = async () => {try {await navigator.clipboard.writeText(snippet); setCopied(true); setTimeout(() => setCopied(false), 1800);} catch (_) {setCopied(false);}};
  return <ReportsDrawer open={open} onOpenChange={value => {if (!value) onClose();}} title="Evento personalizado" description="Marque ações do site que a Super Tag não detecta sozinha, como lead qualificado ou início de checkout.">
    <div className="untitled-scope flex flex-col gap-6">
      <ReportsFieldInput label="Nome do evento" value={name} onChange={event => setName(event.target.value)} maxLength={120} placeholder="lead_qualified" hint="Letras minúsculas e sublinhado; o código abaixo já normaliza."/>
      <div>
        <div className="mb-2 flex items-center justify-between"><span className="text-sm font-medium text-secondary">Código para o site</span>
          <Button size="sm" color="secondary" iconLeading={Copy01} onPress={copy}>{copied ? 'Copiado' : 'Copiar'}</Button></div>
        <pre className="rounded-lg bg-secondary p-4 font-mono text-xs leading-5 break-all whitespace-pre-wrap text-secondary ring-1 ring-secondary ring-inset">{snippet}</pre>
      </div>
      <Callout title="Como usar">Com a Super Tag instalada, chame o código no momento da ação. Use identificadores genéricos: nada de nome, e-mail, telefone ou outros dados pessoais.</Callout>
      <Callout tone="brand" title="Para medir no fluxo">Marque a página de obrigado como conversão em Fluxos. Cliques em links wa.me e api.whatsapp.com já são detectados.</Callout>
    </div>
  </ReportsDrawer>;
}
