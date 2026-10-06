import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {moduleUrl} from '../api.js';
import {DetailLayout, Facts, Rail, TagList, hasValue, listText} from './DetailLayout.jsx';
import {BuyBox} from './BuyBox.jsx';
import {platformLogo} from '../Catalog.jsx';

const capitalize = value => value ? String(value).replace(/^./, letter => letter.toUpperCase()) : value;

/** Formats and interactive formats share one page; the preview leads the hero. */
export function FormatDetail({boot, selection, plan = null}) {
  const record = boot.record;
  const kind = boot.module;
  const interactive = kind === 'interativos';
  if (!record) return <CaduEmptyState title="Formato indisponível" description="Ele pode ter saído do catálogo."/>;
  const channels = record.channels || [];
  const links = [[record.creative_url, interactive ? 'Ver a experiência funcionando' : 'Abrir demonstração'], [record.gallery_url, 'Ver galeria de exemplos']].filter(([url]) => url);
  // "1200x628 | 1200x1200" or "300x250, 300x600" become one tag per size.
  const sizes = String(record.dimensions || '').split(/\s*[|,;]\s*/).filter(Boolean);

  const sections = [
    {id: 'especificacoes', label: 'Especificações', render: () => <>
      {sizes.length > 1 && <><h3 className="pd-subtitle">Tamanhos</h3><TagList value={sizes}/></>}
      <Facts items={[['Tipo', capitalize(record.format_type)], ['Dimensões', sizes.length > 1 ? null : record.dimensions],
        ['Arquivos aceitos', listText(record.files)], ['Categoria criativa', capitalize(record.creative_category)]]}/>
      {links.length > 0 && <ul className="pd-links">{links.map(([url, label]) => <li key={url}>
        <a href={url} target="_blank" rel="noreferrer"><Icon name="external" size={16}/>{label}</a></li>)}</ul>}
    </>},
    {id: 'onde', label: 'Onde usar', count: channels.length, wide: true,
      render: () => <Rail empty="Os canais compatíveis ainda não foram ligados a este formato." items={channels.map(channel => ({
        href: `${moduleUrl(boot.urls, 'canais')}/${channel.id}`, title: channel.name, subtitle: channel.category,
        logo: channel.logo_path, icon: 'share',
      }))}/>},
    {id: 'mercados', label: 'Mercados e segmentos', hidden: !hasValue(record.markets) && !hasValue(record.segments), render: () => <>
      {hasValue(record.markets) && <><h3 className="pd-subtitle">Mercados</h3><TagList value={record.markets}/></>}
      {hasValue(record.segments) && <><h3 className="pd-subtitle">Segmentos</h3><TagList value={record.segments}/></>}
    </>},
  ];

  return <DetailLayout boot={boot} selection={selection} kind={kind} record={{...record, logo_url: platformLogo(record)}} icon={interactive ? 'plugin' : 'table'}
    eyebrow={interactive ? 'Formato interativo' : capitalize(record.creative_category || 'Formato')}
    media={record.image_url ? {type: 'image', src: record.image_url, fit: 'contain', alt: `Prévia: ${record.name}`} : null}
    aside={<BuyBox kind={kind} id={record.id || record.slug} name={record.name} selection={selection}
      pitch={String(record.description || '').split(/(?<=[.!?])\s/)[0]}
      facts={[['Tipo', capitalize(record.format_type), 'table'], ['Dimensões', sizes.length > 1 ? `${sizes.length} opções` : record.dimensions, 'table'], ['Finalidade', record.purpose, 'pulse'], ['Canais compatíveis', channels.length ? String(channels.length) : '', 'share']]}/>}
    metrics={[{icon: 'pulse', label: 'Finalidade', value: record.purpose}, {icon: 'table', label: 'Tamanhos', value: sizes.length > 1 ? `${sizes.length} opções` : record.dimensions},
      {icon: 'share', label: 'Canais compatíveis', value: channels.length || null}]}
    sections={sections}/>;
}
