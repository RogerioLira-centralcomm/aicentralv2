import React, {useEffect, useRef, useState} from 'react';
import {CaduBadge} from '../../cadu-design-system/components/CaduBadge.jsx';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {LogoTile, SelectionButton} from '../PlannerUi.jsx';
import {ActivePlanChip, PlannerHeader} from '../PlannerHeader.jsx';
import {MODULE_LABELS, moduleUrl} from '../api.js';

// Catalog rows sometimes carry placeholder text instead of an empty value.
const PLACEHOLDERS = /^(n[ãa]o informado\.?|dados n[ãa]o dispon[íi]veis\.?|n\/?d|-|—)$/i;
export const hasValue = value => !(value === null || value === undefined || value === '' || (Array.isArray(value) && !value.length)
  || (typeof value === 'string' && PLACEHOLDERS.test(value.trim()))
  || (typeof value === 'object' && !Array.isArray(value) && !Object.keys(value).length));

/** "ultra_segmentado" → "Ultra segmentado"; free text is left alone. */
export const tidy = value => typeof value === 'string' && /^[a-z0-9]+(_[a-z0-9]+)+$/.test(value)
  ? value.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase()) : value;

export const listText = value => Array.isArray(value) ? value.filter(Boolean).map(item => typeof item === 'object' ? (item.nome || item.name || item.label || '') : item).filter(Boolean).join(', ') : value;

/** Flatten a small JSON object (demographics, specs) into label/value facts. */
export function objectFacts(value, limit = 12) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
  return Object.entries(value).filter(([, entry]) => hasValue(entry)).slice(0, limit).map(([key, entry]) => [
    key.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase()),
    typeof entry === 'object' ? (Array.isArray(entry) ? listText(entry) : Object.entries(entry).map(([k, v]) => `${k}: ${v}`).join(' · ')) : String(entry),
  ]);
}

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

/** One big photo with arrows and a thumbnail strip; works with a single photo too. */
function HeroCarousel({photos, name, illustrative = false}) {
  const [index, setIndex] = useState(0);
  const [broken, setBroken] = useState(() => new Set());
  const list = photos.filter(src => !broken.has(src));
  if (!list.length) return null;
  const current = Math.min(index, list.length - 1);
  const go = step => setIndex((current + step + list.length) % list.length);
  const drop = src => setBroken(previous => new Set(previous).add(src));
  return <div className="pd-carousel" aria-roledescription="carrossel" aria-label={`Fotos de ${name}`}>
    <figure className="pd-carousel__stage">
      <img src={list[current]} alt={`Foto ${current + 1} de ${list.length} de ${name}`} onError={() => drop(list[current])}/>
      {illustrative && <span className="pd-carousel__tag">Ilustração</span>}
      {list.length > 1 && <>
        <button type="button" className="pd-carousel__nav is-prev" aria-label="Foto anterior" onClick={() => go(-1)}><Icon name="chevron" size={18}/></button>
        <button type="button" className="pd-carousel__nav is-next" aria-label="Próxima foto" onClick={() => go(1)}><Icon name="chevron" size={18}/></button>
      </>}
    </figure>
    {list.length > 1 && <ul className="pd-carousel__thumbs">{list.slice(0, 8).map((src, position) => <li key={src}>
      <button type="button" className={position === current ? 'is-active' : ''} aria-label={`Ver foto ${position + 1}`} aria-current={position === current ? 'true' : undefined} onClick={() => setIndex(position)}>
        <img src={src} alt="" loading="lazy" onError={() => drop(src)}/></button></li>)}</ul>}
  </div>;
}

function HeroMedia({media, name}) {
  const [failed, setFailed] = useState(false);
  if (!media || failed) return null;
  if (media.type === 'carousel') return <HeroCarousel photos={media.items || []} name={name} illustrative={Boolean(media.illustrative)}/>;
  if (media.type === 'gallery') {
    const photos = (media.items || []).filter(Boolean).slice(0, 3);
    if (!photos.length) return null;
    return <div className={`pd-hero__mosaic is-${photos.length}`}>{photos.map((src, index) => <img key={src} src={src} alt={index ? '' : `Foto de ${name}`} onError={index ? undefined : () => setFailed(true)}/>)}</div>;
  }
  return <figure className={`pd-hero__media${media.fit === 'contain' ? ' is-contain' : ''}`}><img src={media.src} alt={media.alt || ''} onError={() => setFailed(true)}/></figure>;
}

/**
 * Detail pages read top to bottom like a short report: a visual hero with the
 * identity, the pitch and the key numbers; then stacked sections with a sticky
 * section index. The name lives only in the page header, the "add to plan"
 * action with the header actions; related items are links, never buttons.
 */
export function DetailLayout({boot, selection, kind, record, icon = 'plan', eyebrow, metrics = [], sections = [], media = null, aside = null, extraMeta = null}) {
  const id = record.id || record.slug;
  const visible = sections.filter(section => section && !section.hidden);
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

  const shownMetrics = metrics.filter(item => hasValue(item.value));
  // One accent for every page (the Planner green); the channel colour stays on its logo.
  return <article className={`pd${aside ? ' pd--aside' : ''}`}>
    <PlannerHeader crumbs={[[MODULE_LABELS[kind], moduleUrl(boot.urls, kind)]]} title={record.name}
      leading={<DetailMark record={record} icon={icon}/>}
      meta={eyebrow || extraMeta ? <>{eyebrow && <CaduBadge tone="neutral">{eyebrow}</CaduBadge>}{extraMeta}</> : null}
      actions={<ActivePlanChip/>}/>
    <div className={`pd-shell${aside ? ' has-aside' : ''}`}><div className="pd-main">
    <section className={`pd-hero${media ? ' has-media' : ''}`} aria-label="Resumo">
      <div className="pd-hero__copy">
        <p>{record.description || 'Sem descrição publicada.'}</p>
        {shownMetrics.length > 0 && <dl className="pd-hero__metrics" style={{'--metric-count': Math.min(shownMetrics.length, 6)}}>{shownMetrics.map(item => <div key={item.label}>
          {item.icon && <Icon name={item.icon} size={18}/>}<dt>{item.label}</dt><dd>{item.value}</dd>{item.hint && <small>{item.hint}</small>}
        </div>)}</dl>}
      </div>
      <HeroMedia media={media} name={record.name}/>
    </section>
    {visible.length > 1 && <nav className="pd-nav" aria-label="Nesta página">{visible.map(section => <a key={section.id} href={`#pd-${section.id}`}
      className={current === section.id ? 'is-active' : ''} aria-current={current === section.id ? 'true' : undefined}
      onClick={event => { event.preventDefault(); refs.current[section.id]?.scrollIntoView({behavior: 'smooth', block: 'start'}); setCurrent(section.id); }}>
      {section.label}{section.count ? <span>{section.count}</span> : null}</a>)}</nav>}
    <div className="pd-sections">{visible.map(section => <section key={section.id} id={`pd-${section.id}`} ref={node => { refs.current[section.id] = node; }}
      className={`pd-section${section.wide ? ' is-wide' : ''}`} aria-labelledby={`pd-${section.id}-title`}>
      <header><h2 id={`pd-${section.id}-title`}>{section.label}</h2>{section.hint && <p>{section.hint}</p>}</header>
      <div className="pd-section__body">{section.render()}</div>
    </section>)}</div>
    </div>{aside && <aside className="pd-aside" aria-label="Seu plano">{aside}</aside>}</div>
  </article>;
}

export function EmptyTab({text}) {
  return <p className="planner-muted">{text}</p>;
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
