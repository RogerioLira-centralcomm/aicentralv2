import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {moduleUrl} from '../api.js';
import {DetailLayout, Facts, Rail, TagList, hasValue, listText} from './DetailLayout.jsx';
import {platformLogo} from '../Catalog.jsx';
import {parseSize} from '../FormatPreview.jsx';

const BOARD_HEIGHT = 180;
/** Every size of the format drawn at ONE common scale, so a 970x250 and a 300x250 compare at a glance. */
function SizeBoard({sizes}) {
  const parsed = sizes.map(label => ({label, size: parseSize(label)})).filter(item => item.size && !item.size.ratio);
  if (!parsed.length) return null;
  const scale = Math.min(BOARD_HEIGHT / Math.max(...parsed.map(item => item.size.height)), 320 / Math.max(...parsed.map(item => item.size.width)));
  return <ul className="pd-sizes" aria-label="Tamanhos em escala">{parsed.map(({label, size}) => <li key={label}>
    <span className="pd-sizes__box" style={{width: Math.max(12, size.width * scale), height: Math.max(12, size.height * scale)}}/>
    <strong>{size.width}×{size.height}</strong>
    {label.replace(/^\s*\d+\s*[x×]\s*\d+\s*(px)?/i, '').replace(/[()]/g, '').trim() && <small>{label.replace(/^\s*\d+\s*[x×]\s*\d+\s*(px)?/i, '').replace(/[()]/g, '').trim()}</small>}
  </li>)}</ul>;
}

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
    {id: 'tamanhos', label: 'Tamanhos em escala', hidden: !sizes.some(value => parseSize(value) && !parseSize(value).ratio), wide: true,
      hint: 'Todos desenhados na mesma escala, para comparar o espaço de cada peça.', render: () => <SizeBoard sizes={sizes}/>},
    {id: 'especificacoes', label: 'Especificações', render: () => <>
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
    metrics={[{icon: 'pulse', label: 'Finalidade', value: record.purpose}, {icon: 'table', label: 'Tamanhos', value: sizes.length > 1 ? `${sizes.length} opções` : record.dimensions},
      {icon: 'share', label: 'Canais compatíveis', value: channels.length || null}]}
    sections={sections}/>;
}
