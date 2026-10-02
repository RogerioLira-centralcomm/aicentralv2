import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {DetailLayout, Facts} from './DetailLayout.jsx';

const number = value => Number(value).toLocaleString('pt-BR');
const date = value => value ? new Date(value).toLocaleDateString('pt-BR') : '';

/** An editorial portal: public audience with its source, and what we have read of it. */
export function PortalDetail({boot, selection}) {
  const portal = boot.record;
  if (!portal) return <CaduEmptyState title="Portal indisponível" description="Ele pode ter saído do catálogo."/>;
  const attributes = (Array.isArray(portal.public_attributes) ? portal.public_attributes : [])
    .filter(entry => entry && typeof entry === 'object' && entry.atributo !== 'status_curadoria');
  const pages = Number(portal.discovered_pages_count);

  const sections = [
    {id: 'evidencias', label: 'Evidências públicas', count: attributes.length, hint: 'Características verificadas em fontes públicas.',
      render: () => attributes.length ? <ul className="pd-evidence">{attributes.map((entry, index) => <li key={`${entry.atributo}-${index}`}>
        <span>{String(entry.atributo || 'Característica').replaceAll('_', ' ')}</span>
        <strong>{String(entry.valor ?? '—')}</strong>
        <small>{[entry.observed_at && `Verificado em ${entry.observed_at}`].filter(Boolean).join('')}
          {entry.source_url && <a href={entry.source_url} target="_blank" rel="noreferrer">Fonte</a>}</small>
      </li>)}</ul> : <p className="planner-muted">Ainda não há características públicas verificadas para este portal.</p>},
    {id: 'sobre', label: 'Sobre o portal', render: () => <Facts items={[
      ['Domínio', portal.domain && <a href={`https://${portal.domain}`} target="_blank" rel="noreferrer">{portal.domain}</a>],
      ['Categoria', portal.category], ['Período da audiência', portal.audience_period], ['Audiência conferida em', date(portal.audience_checked_at)]]}/>},
  ];

  return <DetailLayout boot={boot} selection={selection} kind="portais" record={{...portal, logo_url: portal.domain ? `https://${portal.domain}/favicon.ico` : ''}} icon="library"
    eyebrow={portal.featured_rank ? 'Destaque' : portal.category}
    metrics={[
      {label: 'Audiência pública', value: portal.audience_estimate, hint: portal.audience_source_url
        ? <a href={portal.audience_source_url} target="_blank" rel="noreferrer">Ver fonte</a> : 'Sem fonte publicada'},
      {label: 'Páginas lidas', value: pages > 0 ? number(pages) : null, hint: portal.last_crawled_at ? `Última leitura em ${date(portal.last_crawled_at)}` : null},
      {label: 'Leituras', value: Number(portal.crawl_updates_count) > 0 ? number(portal.crawl_updates_count) : null},
    ]}
    sections={sections}/>;
}
