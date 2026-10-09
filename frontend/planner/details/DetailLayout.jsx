import React, {useEffect, useRef, useState} from 'react';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {LogoTile, RowAddButton} from '../PlannerUi.jsx';
import {MODULE_LABELS, moduleUrl} from '../api.js';

// Catalog rows sometimes carry placeholder text instead of an empty value.
const PLACEHOLDERS = /^(n[ãa]o informado\.?|dados n[ãa]o dispon[íi]veis\.?|n\/?d|-|—)$/i;
export const hasValue = value => !(value === null || value === undefined || value === '' || (Array.isArray(value) && !value.length)
  || (typeof value === 'string' && PLACEHOLDERS.test(value.trim()))
  || (typeof value === 'object' && !Array.isArray(value) && !Object.keys(value).length));

/** "ultra_segmentado" → "Ultra segmentado"; free text is left alone. */
export const tidy = value => typeof value === 'string' && /^[a-z0-9]+(_[a-z0-9]+)+$/.test(value)
  ? value.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase()) : value;

// A hero number is a number: long sentences ("mensurável por campanha…") are notes about the method, not tiles.
const METRIC_MAX = 28;
export const isTileValue = value => typeof value !== 'string' || value.trim().length <= METRIC_MAX;
// Where a number comes from, as a small badge on its tile.
const ORIGIN = {official: ['Dado oficial', 'is-official'], estimate: ['Estimativa', 'is-estimate'], to_validate: ['A validar', 'is-pending']};
export function OriginBadge({origin}) {
  const [label, tone] = ORIGIN[origin] || [];
  return label ? <span className={`pd-origin ${tone}`}>{label}</span> : null;
}

/** Long text shows its first sentence; the rest opens on demand. */
export function ReadMore({text, limit = 180}) {
  const [open, setOpen] = useState(false);
  const value = String(text || '').trim();
  if (!value) return null;
  const sentence = value.match(/^.{40,}?[.!?](\s|$)/)?.[0]?.trim() || value.slice(0, limit);
  const short = sentence.length < value.length - 20 ? sentence : value;
  if (short === value) return <p className="pd-text">{value}</p>;
  return <p className="pd-text">{open ? value : short}{' '}
    <button type="button" className="pd-readmore" aria-expanded={open} onClick={() => setOpen(current => !current)}>{open ? 'Mostrar menos' : 'Ler mais'}</button></p>;
}

export const listText = value => Array.isArray(value) ? value.filter(Boolean).map(item => typeof item === 'object' ? (item.nome || item.name || item.label || '') : item).filter(Boolean).join(', ') : value;

export function Facts({items}) {
  const visible = items.filter(([, value]) => hasValue(value));
  if (!visible.length) return null;
  return <dl className="pd-facts">{visible.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{tidy(value)}</dd></div>)}</dl>;
}

/** Channel/platform logo first (it is how people recognise a channel), then a cover, then an icon. */
export function DetailMark({record, icon, size = 'lg'}) {
  const [failed, setFailed] = useState(false);
  const logo = record.logo_url || record.logo_path || record.platform_logo || '';
  const cover = !logo && record.hero_image_url && !failed;
  if (!logo && cover) return <span className={`planner-mark planner-mark--${size}`}><img src={record.hero_image_url} alt="" onError={() => setFailed(true)}/></span>;
  return <LogoTile src={logo} name={record.name} icon={icon} size={size} color={record.cor}/>;
}

/** Key numbers as report-style tiles: one value, one label, the source when it matters. */
export function MetricTiles({items}) {
  const visible = items.filter(item => hasValue(item.value));
  if (!visible.length) return null;
  return <ul className="planner-metrics" aria-label="Números" style={{'--metric-count': visible.length}}>
    {visible.map(item => <li key={item.label}>
      <small>{item.label}</small>
      <strong>{item.value}</strong>
      {item.hint && <span>{item.hint}</span>}
    </li>)}
  </ul>;
}

/** Split a long "a, b, c" or "a; b" text into short items when it reads as a list. */
export function splitList(value) {
  if (Array.isArray(value)) return value.map(item => (item && typeof item === 'object') ? (item.nome || item.name || item.label || '') : String(item || '')).filter(Boolean);
  const text = String(value || '').trim();
  if (!text) return [];
  const parts = text.split(/\s*[;\n•]\s*|,\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])/).map(part => part.trim()).filter(Boolean);
  return parts.length > 1 ? parts : [text];
}

/** Short items as soft tags; a single long sentence stays a paragraph. */
export function TagList({value}) {
  const items = splitList(value);
  if (!items.length) return null;
  if (items.length === 1 && items[0].length > 60) return <p className="pd-text">{items[0]}</p>;
  return <ul className="pd-tags">{items.map(item => <li key={item}>{tidy(item)}</li>)}</ul>;
}

/** Horizontal rail of related items; each tile is a link (no buttons). */
export function Rail({items, empty}) {
  if (!items?.length) return empty ? <p className="planner-muted">{empty}</p> : null;
  return <div className="pd-rail" role="list">{items.map(item => <a key={item.href} role="listitem" className="pd-rail__item" href={item.href}>
    {item.image ? <span className="pd-rail__media"><img src={item.image} alt="" loading="lazy"/></span>
      : <LogoTile src={item.logo} name={item.title} icon={item.icon || 'plan'} size="sm"/>}
    <strong>{item.title}</strong>
    {item.subtitle && <small>{item.subtitle}</small>}
  </a>)}</div>;
}

/** Photo grid; the first photo leads. */
export function Gallery({photos, name}) {
  const visible = (photos || []).filter(photo => photo?.url).slice(0, 12);
  if (!visible.length) return null;
  return <div className="pd-gallery">{visible.map((photo, index) => <figure key={photo.url} className={index === 0 ? 'is-lead' : ''}>
    <img src={photo.url} alt={photo.title || `Foto ${index + 1} de ${name}`} loading="lazy"/>
    {photo.caption && <figcaption>{photo.caption}</figcaption>}
  </figure>)}</div>;
}

/**
 * Detail pages read top to bottom like a short report: a visual hero with the
 * identity, the pitch and the key numbers; then stacked sections with a sticky
 * section index. The name lives only in the page header, the "add to plan"
 * action with the header actions; related items are links, never buttons.
 */
export function DetailLayout({boot, selection, kind, record, icon = 'plan', eyebrow, metrics = [], sections = [], media = null, aside = null, extraMeta = null, highlights = [], sourceNote = null}) {
  const id = record.id || record.slug;
  const visible = sections.filter(section => section && !section.hidden);
  const photos = (media?.type === 'carousel' || media?.type === 'gallery' ? media.items : media?.src ? [media.src] : []).filter(Boolean);
  const [bannerFailed, setBannerFailed] = useState(false);
  const firstPhoto = photos[0] || '';
  // A banner photo that does not load falls back to the plain dark banner (keyed on the URL, so it cannot loop).
  useEffect(() => {
    setBannerFailed(false);
    if (!firstPhoto) return undefined;
    const probe = new Image();
    probe.onerror = () => setBannerFailed(true);
    probe.src = firstPhoto;
    return () => { probe.onerror = null; };
  }, [firstPhoto]);
  const [current, setCurrent] = useState(visible[0]?.id);
  const refs = useRef({});

  useEffect(() => {
    if (!('IntersectionObserver' in window)) return undefined;
    const observer = new IntersectionObserver(entries => {
      const top = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (top) setCurrent(top.target.id.replace(/^pd-/, ''));
    }, {rootMargin: '-96px 0px -60% 0px'});
    Object.values(refs.current).forEach(node => node && observer.observe(node));
    return () => observer.disconnect();
  }, [visible.length]);

  const filled = metrics.filter(item => hasValue(item.value));
  const shownMetrics = filled.filter(item => isTileValue(item.value)).slice(0, 6);
  const metricNotes = filled.filter(item => !isTileValue(item.value));
  const shownHighlights = highlights.filter(([, text]) => hasValue(text));
  const bannerImage = bannerFailed ? null : photos[0];
  // Extra photos are a section of their own; the first one is the banner.
  const more = photos.slice(1).map(url => ({url}));
  const all = more.length ? [...visible, {id: 'fotos', label: 'Fotos', count: more.length, wide: true, render: () => <Gallery photos={more} name={record.name}/>}] : visible;
  const scrollTo = (event, id) => { event.preventDefault(); refs.current[id]?.scrollIntoView({behavior: 'smooth', block: 'start'}); setCurrent(id); };

  // A marketplace listing: the photo is the banner (identity and key numbers over it), the pitch right below, a horizontal
  // index, the sections, and on the right the related items to compare.
  return <article className="pd pd--market">
    <header className={`pdb${bannerImage ? ' has-image' : ''}`} style={bannerImage ? {'--pdb-image': `url("${bannerImage}")`} : undefined}>
      {bannerImage && media?.illustrative && <span className="pdb__badge">Ilustração</span>}
      <div className="pdb__inner">
        <span className="pdb__mark"><DetailMark record={record} icon={icon} size="md"/></span>
        <div className="pdb__title">
          <nav className="pdb__crumbs" aria-label="Você está em"><a href={moduleUrl(boot.urls, kind)}>{MODULE_LABELS[kind]}</a><span aria-hidden="true">/</span></nav>
          <h1>{record.name}</h1>
          {(eyebrow || extraMeta) && <span className="pdb__chips">{eyebrow && <em>{eyebrow}</em>}{extraMeta}</span>}
        </div>
        {shownMetrics.length > 0 && <dl className="pdb__metrics" style={{'--metric-count': shownMetrics.length}}>{shownMetrics.map(item => <div key={item.label} title={typeof item.hint === 'string' ? item.hint : undefined}>
          <dt>{item.label}{item.hint && typeof item.hint !== 'string' && <small>{item.hint}</small>}</dt><dd>{item.value}</dd>
          {(item.origin || (typeof item.hint === 'string' && /estimativa/i.test(item.hint))) && <OriginBadge origin={item.origin || 'estimate'}/>}
        </div>)}</dl>}
      </div>
    </header>
    <div className={`pd-market${aside ? ' has-side' : ''}`}>
      <div className="pd-main">
        {metricNotes.length > 0 && <aside className="pd-method" aria-label="Sobre os números">{metricNotes.map(item => <div key={item.label}>
          <strong>{item.label}</strong><ReadMore text={item.value}/></div>)}</aside>}
        {(record.description || shownHighlights.length > 0) && <section className="pd-intro" aria-label="Resumo">
          {record.description && <p className="pd-hero__lead">{record.description}</p>}
          {shownHighlights.length > 0 && <div className="pd-highlights"><div className="pd-highlights__cards">{shownHighlights.map(([label, text]) => <section key={label}><h2>{label}</h2><ReadMore text={text} limit={220}/></section>)}</div>
            {sourceNote && <small>{sourceNote}</small>}</div>}
        </section>}
        {all.length > 1 && <nav className="pd-nav" aria-label="Nesta página">{all.map(section => <a key={section.id} href={`#pd-${section.id}`}
          className={current === section.id ? 'is-active' : ''} aria-current={current === section.id ? 'true' : undefined} onClick={event => scrollTo(event, section.id)}>
          {section.label}{section.count ? <span>{section.count}</span> : null}</a>)}</nav>}
        <div className="pd-sections">{all.map(section => <section key={section.id} id={`pd-${section.id}`} ref={node => { refs.current[section.id] = node; }}
          className={`pd-section${section.wide ? ' is-wide' : ''}`} aria-labelledby={`pd-${section.id}-title`}>
          <header><h2 id={`pd-${section.id}-title`}>{section.label}</h2>{section.hint && <p>{section.hint}</p>}</header>
          <div className="pd-section__body">{section.render()}</div>
        </section>)}</div>
      </div>
      {aside && <aside className="pd-side">{aside}</aside>}
    </div>
  </article>;
}

/** "Similar items" column of a marketplace: tall, borderless tiles (photo with the logo over it) that link to the item. */
export function RelatedList({title, items, empty = null}) {
  if (!items?.length) return empty;
  return <section className="pd-related" aria-label={title}>
    <h2>{title}<span>{items.length}</span></h2>
    <ul>{items.map(item => <li key={item.href}>
      <a className="pd-related__link" href={item.href}>
        <span className="pd-related__photo">
          {item.image ? <img src={item.image} alt="" loading="lazy"/> : <Icon name={item.icon || 'plan'} size={28}/>}
          <LogoTile src={item.logo} name={item.title} icon={item.icon || 'plan'} size="md"/>
        </span>
        <span className="pd-related__text"><strong>{item.title}</strong>{item.subtitle && <small>{item.subtitle}</small>}</span>
      </a>
      {item.onToggle && <RowAddButton name={item.title} selected={item.selected} onToggle={item.onToggle}/>}
    </li>)}</ul>
  </section>;
}

const prettyKey = key => String(key).length <= 2 ? String(key).toUpperCase() : String(key).replace(/^(\d+)_(\d+)$/, '$1–$2').replace(/^(\d+)_plus$/, '$1+')
  .replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase());
const numeric = value => typeof value === 'number' ? value : (typeof value === 'string' && /^\s*\d+([.,]\d+)?\s*%?\s*$/.test(value) ? parseFloat(value.replace(',', '.')) : null);

/** Percent bars for flat or grouped demographics ({homens: 52, faixas: {18_24: 28}}). */
export function DemographyBars({value}) {
  if (!value || typeof value !== 'object') return null;
  const flat = Object.entries(value).filter(([, entry]) => numeric(entry) !== null);
  const groups = Object.entries(value).filter(([, entry]) => entry && typeof entry === 'object' && !Array.isArray(entry)
    && Object.values(entry).some(item => numeric(item) !== null));
  const bars = rows => <ul className="planner-bars">{rows.map(([label, entry]) => {
    const number = numeric(entry);
    return <li key={label}><span>{prettyKey(label)}</span><i><b style={{width: `${Math.max(0, Math.min(100, number))}%`}}/></i><strong>{number}%</strong></li>;
  })}</ul>;
  if (!flat.length && !groups.length) return null;
  return <div className="planner-demography">
    {flat.length > 0 && <div><h3>Gênero</h3>{bars(flat)}</div>}
    {groups.map(([title, entry]) => <div key={title}><h3>{prettyKey(title)}</h3>
      {bars(Object.entries(entry).filter(([, item]) => numeric(item) !== null))}</div>)}
  </div>;
}
