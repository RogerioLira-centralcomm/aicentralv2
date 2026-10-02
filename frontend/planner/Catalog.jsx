import React, {useEffect, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduSelectField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {VisualIdentity} from '../cadu-design-system/components/VisualIdentity.jsx';
import {PlannerPanel, SelectionButton} from './PlannerUi.jsx';
import {MODULE_LABELS, moduleUrl} from './api.js';
import {ActivePlanChip, PlannerHeader} from './PlannerHeader.jsx';

const PORTAL_PAGE = 50;
const DESCRIPTIONS = {
  canais: 'Onde a campanha aparece e o papel que cada canal cumpre no plano.',
  audiencias: 'Públicos compráveis, com tamanho estimado e contexto de uso.',
  formatos: 'Peças por canal, com especificações e finalidade.',
  interativos: 'Formatos com interação para engajar e medir atenção.',
  portais: 'Veículos editoriais com dados públicos e fontes verificáveis.',
  places: 'Pontos físicos, circulação e produtos de mídia em lugares.',
};
const KIND_ICON = {places: 'browser', audiencias: 'users', canais: 'share', interativos: 'plugin', formatos: 'plan', portais: 'library'};
const number = value => Number(value).toLocaleString('pt-BR');
const audienceLabel = item => item.audience_estimate || item.audience || item.tamanho || '';
const itemKey = item => item.id || item.slug;

export function catalogDetailUrl(urls, kind, item) {
  // Places are addressed by slug; every other catalog by numeric id.
  return `${moduleUrl(urls, kind)}/${encodeURIComponent(kind === 'places' ? item.slug || item.id : item.id)}`;
}

function useDebounced(value, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

// The one number that helps choose, shown at the card's foot.
function keyFact(kind, item) {
  const audience = audienceLabel(item);
  if (kind === 'places') return item.traffic ? `${item.traffic_label || 'Movimento'}: ${item.traffic}` : item.investment ? `Investimento ${item.investment}` : '';
  if (kind === 'audiencias') return audience && `Público ${audience}`;
  if (kind === 'canais') return item.audience && `Alcance ${item.audience}`;
  return item.dimensions || '';
}

function cardChips(kind, item, eyebrow) {
  const values = kind === 'places' ? [item.city, item.points?.length && `${item.points.length} pontos`]
    : kind === 'audiencias' ? [item.platform, item.subcategory, item.perfil_socioeconomico && `Classe ${item.perfil_socioeconomico}`]
      : kind === 'canais' ? [] : [item.format_type, item.purpose];
  const seen = new Set([String(eyebrow || '').toLowerCase()]);
  const tidy = value => /^[a-z0-9]+([_-][a-z0-9]+)+$/.test(value) ? value.replace(/[_-]+/g, ' ').replace(/^./, letter => letter.toUpperCase()) : value;
  return values.filter(Boolean).map(String).map(tidy).filter(value => !seen.has(value.toLowerCase()) && seen.add(value.toLowerCase())).slice(0, 3);
}

const VISUAL_KINDS = new Set(['audiencias', 'places']);
// Platform logos served by the Planner itself (the legacy /assets_images path is not).
const PLATFORM_LOGOS = {
  google_ads: '/static/images/canais/google-ads.png', tiktok_ads: '/static/images/canais/tiktok.png',
  dv360: '/static/images/canais/google-dv360.svg', the_trade_desk: '/static/images/canais/the-trade-desk.png',
  interativos: '/static/images/canais/interativos.svg', kwai_ads: '/static/images/canais/kwai.svg',
};

export function platformLogo(item) {
  const slug = String(item.platform_slug || item.plataforma_slug || '').replace(/-/g, '_');
  if (PLATFORM_LOGOS[slug]) return PLATFORM_LOGOS[slug];
  const logo = item.platform_logo || '';
  return logo.startsWith('/static/') || /^https?:/.test(logo) ? logo : '';
}

function CardMark({kind, item}) {
  const logo = kind === 'canais' ? (item.logo_path || item.logo_url || '') : platformLogo(item);
  const label = kind === 'canais' ? item.name : (item.platform || item.name);
  return <span className="planner-mark planner-mark--sm" style={item.cor ? {'--planner-mark-color': item.cor} : undefined}>
    {logo ? <VisualIdentity src={logo} initials={label} label={label} imageTreatment="brand"/> : <Icon name={KIND_ICON[kind] || 'plan'} size={18}/>}
  </span>;
}

const InPlan = () => <span className="planner-card__inplan"><Icon name="check" size={12}/>No plano</span>;

/** The whole card is the link to the detail page; adding to the plan happens there. */
function CatalogCard({kind, item, urls, selected}) {
  const [imageFailed, setImageFailed] = useState(false);
  const visual = VISUAL_KINDS.has(kind);
  const showImage = visual && item.image_url && !imageFailed;
  // Never repeat the page title on every card ("Interativos" on the Interativos page).
  const eyebrow = [item.platform, item.category, item.segment, item.city]
    .find(value => value && String(value).toLowerCase() !== String(MODULE_LABELS[kind]).toLowerCase()) || '';
  const chips = cardChips(kind, item, eyebrow);
  const fact = keyFact(kind, item);
  return <a className={`planner-card${visual ? ' is-visual' : ''}${selected ? ' is-selected' : ''}`} href={catalogDetailUrl(urls, kind, item)}>
    {visual && <span className={`planner-card__art${showImage ? ' has-image' : ''}`}>
      {showImage ? <img src={item.image_url} alt="" loading="lazy" onError={() => setImageFailed(true)}/> : <Icon name={KIND_ICON[kind] || 'plan'} size={22}/>}
      {selected && <InPlan/>}
    </span>}
    <span className="planner-card__body">
      {visual ? (eyebrow && <span className="planner-card__eyebrow">{eyebrow}</span>)
        : <span className="planner-card__identity"><CardMark kind={kind} item={item}/><span className="planner-card__eyebrow">{eyebrow}</span>{selected && <InPlan/>}</span>}
      <strong className="planner-card__title">{item.name}</strong>
      <span className="planner-card__text">{item.description || item.purpose || 'Referência para apoiar as decisões do plano.'}</span>
      {(fact || chips.length > 0) && <span className="planner-card__foot">
        {fact && <b title={fact}>{fact}</b>}
        {chips.map(value => <span key={value}>{value}</span>)}
      </span>}
    </span>
  </a>;
}

function PortalRow({item, urls, selected}) {
  const [faviconFailed, setFaviconFailed] = useState(false);
  const pages = Number(item.discovered_pages_count);
  return <a className={`planner-portal${selected ? ' is-selected' : ''}`} href={catalogDetailUrl(urls, 'portais', item)}>
    <span className="planner-portal__favicon">{faviconFailed ? <Icon name="browser" size={18}/> : <img src={`https://${item.domain}/favicon.ico`} alt="" loading="lazy" onError={() => setFaviconFailed(true)}/>}</span>
    <span className="planner-portal__main">
      <span className="planner-portal__title"><strong>{item.name}</strong>{item.featured_rank && <CaduBadge tone="brand">Destaque</CaduBadge>}{selected && <InPlan/>}</span>
      <small>{item.domain} · {item.description || 'Veículo editorial independente.'}</small>
    </span>
    <span className="planner-portal__fact"><small>Categoria</small><b>{item.category || 'Não categorizado'}</b></span>
    <span className="planner-portal__fact"><small>Audiência pública</small><b>{audienceLabel(item) || 'Sem estimativa'}</b></span>
    <span className="planner-portal__fact"><small>Páginas lidas</small><b>{pages > 0 ? number(pages) : item.last_crawled_at ? '—' : 'Aguardando'}</b></span>
    <Icon name="chevron" size={16}/>
  </a>;
}

export function CatalogPage({boot, request, selection, notify}) {
  const kind = boot.module;
  const portalMode = kind === 'portais';
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [offset, setOffset] = useState(0);
  const [records, setRecords] = useState(Array.isArray(boot.records) ? boot.records : []);
  const [total, setTotal] = useState(boot.records?.length || 0);
  const [loading, setLoading] = useState(false);
  const search = useDebounced(query);
  // The first page arrives with the HTML (portals need the total, so they fetch).
  const preloaded = useRef(Array.isArray(boot.records) && !portalMode);

  useEffect(() => {
    if (preloaded.current) { preloaded.current = false; return undefined; }
    const params = new URLSearchParams({q: search, category});
    if (portalMode) { params.set('limit', String(PORTAL_PAGE)); params.set('offset', String(offset)); }
    const path = kind === 'places' ? `/places?${params}` : `/catalog/${kind}?${params}`;
    const controller = new AbortController();
    let current = true;
    setLoading(true);
    request(path, {signal: controller.signal})
      .then(data => {
        if (!current) return;
        const next = data.records || [];
        setRecords(next);
        setTotal(portalMode ? Number(data.total || 0) : next.length);
      })
      .catch(error => { if (current && error.name !== 'AbortError') notify({tone: 'error', message: error.message}); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [request, notify, kind, portalMode, search, category, offset]);

  const countLabel = loading ? 'Atualizando…' : portalMode ? `${number(total)} portais · página ${Math.floor(offset / PORTAL_PAGE) + 1}` : `${number(records.length)} ${records.length === 1 ? 'referência' : 'referências'}`;

  return <>
    <PlannerHeader title={MODULE_LABELS[kind]} description={DESCRIPTIONS[kind]} withContext actions={<ActivePlanChip/>}/>
    <div className="planner-toolbar">
      <CaduInput className="planner-toolbar__search" aria-label="Pesquisar referências" type="search" value={query} placeholder={portalMode ? 'Buscar por portal, domínio ou categoria' : 'Buscar por nome, descrição ou categoria'}
        leading={<span className="planner-toolbar__search-icon" aria-hidden="true"><Icon name="search" size={16}/></span>}
        onChange={event => { setQuery(event.target.value); setOffset(0); }}/>
      {(boot.categories || []).length > 0 && <CaduSelectField className="planner-toolbar__category" aria-label="Categoria" value={category} onChange={event => { setCategory(event.target.value); setOffset(0); }}
        options={[{value: '', label: 'Todas as categorias'}, ...boot.categories.map(value => ({value, label: value}))]}/>}
      <span className="planner-toolbar__count" aria-live="polite">{countLabel}</span>
    </div>
    {!records.length && !loading ? <PlannerPanel className="planner-panel--flush"><CaduEmptyState title="Nenhuma referência encontrada" description="Ajuste a busca ou escolha outra categoria."/></PlannerPanel>
      : portalMode ? <div className="planner-list" aria-label="Portais disponíveis">{records.map(item => <PortalRow key={itemKey(item)} item={item} urls={boot.urls} selected={selection.isSelected(kind, itemKey(item))}/>)}</div>
        : <div className="planner-grid" aria-label={`${MODULE_LABELS[kind]} disponíveis`}>{records.map(item => <CatalogCard key={itemKey(item)} kind={kind} item={item} urls={boot.urls} selected={selection.isSelected(kind, itemKey(item))}/>)}</div>}
    {portalMode && total > PORTAL_PAGE && <nav className="planner-pagination" aria-label="Páginas de portais">
      <CaduButton variant="secondary" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - PORTAL_PAGE))}>Anterior</CaduButton>
      <CaduButton variant="secondary" disabled={offset + records.length >= total} onClick={() => setOffset(offset + PORTAL_PAGE)}>Próxima</CaduButton>
    </nav>}
  </>;
}

const FACTS = [
  ['Categoria', 'category'], ['Plataforma', 'platform'], ['Público estimado', item => audienceLabel(item)], ['Período da estimativa', 'audience_period'],
  ['Cidade', 'city'], ['Operador', 'operator'], ['Movimento', item => item.traffic && `${item.traffic}${item.traffic_label ? ` · ${item.traffic_label}` : ''}`],
  ['Investimento', 'investment'], ['Finalidade', 'purpose'], ['Especificação', 'dimensions'], ['Arquivos', 'files'],
];
const listText = value => Array.isArray(value) ? value.filter(Boolean).join(', ') : value;

function DetailHero({src}) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return <figure className="planner-detail-hero"><img src={src} alt="" onError={() => setFailed(true)}/></figure>;
}

export function CatalogDetail({boot, selection}) {
  const kind = boot.module;
  const item = boot.audience || boot.record;
  if (!item) return <CaduEmptyState title="Referência indisponível" description="Ela pode ter saído do catálogo."/>;
  const id = itemKey(item);
  const facts = FACTS.map(([label, field]) => [label, typeof field === 'function' ? field(item) : item[field]]).filter(([, value]) => value);
  const attributes = Array.isArray(item.public_attributes) ? item.public_attributes.filter(entry => entry && typeof entry === 'object' && entry.atributo !== 'status_curadoria') : [];
  return <>
    <PlannerHeader crumbs={[[MODULE_LABELS[kind], moduleUrl(boot.urls, kind)]]} title={item.name}
      description={[item.domain, item.description].filter(Boolean).join(' · ')}
      actions={<><ActivePlanChip/><SelectionButton size="md" selected={selection.isSelected(kind, id)} onToggle={() => selection.toggle(kind, id)}/></>}/>
    {item.image_url && !item.gallery?.length && <DetailHero src={item.image_url}/>}
    {item.gallery?.length > 0 && <div className="planner-gallery" aria-label="Fotos">{item.gallery.slice(0, 8).map((photo, index) => <img key={photo.url} src={photo.url} alt={photo.caption || `Foto ${index + 1} de ${item.name}`} loading="lazy"/>)}</div>}
    {facts.length > 0 && <PlannerPanel title="Resumo"><dl className="planner-facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      {item.audience_source_url && <p className="planner-source">Fonte da audiência: <a href={item.audience_source_url} target="_blank" rel="noreferrer">{item.audience_source_url}</a></p>}
    </PlannerPanel>}
    {(item.markets?.length > 0 || item.segments?.length > 0) && <PlannerPanel title="Onde se aplica"><dl className="planner-facts">
      {item.markets?.length > 0 && <div><dt>Mercados</dt><dd>{listText(item.markets)}</dd></div>}
      {item.segments?.length > 0 && <div><dt>Segmentos</dt><dd>{listText(item.segments)}</dd></div>}
    </dl></PlannerPanel>}
    {item.points?.length > 0 && <PlannerPanel title="Pontos de mídia" description={`${item.points.length} ${item.points.length === 1 ? 'ponto disponível' : 'pontos disponíveis'}`}>
      <ul className="planner-items">{item.points.map(point => <li key={point.id || point.name}><span><strong>{point.name}</strong><small>{[point.kind, point.audience, listText(point.formats)].filter(Boolean).join(' · ')}</small></span></li>)}</ul>
    </PlannerPanel>}
    {(item.data_groups || []).map(group => {
      const fields = (group.fields || []).filter(field => !field.is_empty && !field.is_structured);
      return fields.length ? <PlannerPanel key={group.title} title={group.title}><dl className="planner-facts">{fields.map(field => <div key={field.variable}><dt>{field.label}</dt><dd>{field.value}</dd></div>)}</dl></PlannerPanel> : null;
    })}
    {attributes.length > 0 && <PlannerPanel title="Características públicas e evidências" className="planner-attributes">
      {attributes.map((entry, index) => <div key={`${entry.atributo || 'atributo'}-${index}`}>
        <strong>{String(entry.atributo || 'Característica').replaceAll('_', ' ')}</strong>
        <span>{String(entry.valor ?? '—')}</span>
        {entry.observed_at && <small>Verificado em {entry.observed_at}</small>}
        {entry.source_url && <a href={entry.source_url} target="_blank" rel="noreferrer">Abrir fonte</a>}
      </div>)}
    </PlannerPanel>}
  </>;
}
