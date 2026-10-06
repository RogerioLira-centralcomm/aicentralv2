import React, {useEffect, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduSelectField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {LogoTile, PlannerPanel, SelectionButton} from './PlannerUi.jsx';
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
export const itemKey = item => item.id || item.slug;

export function catalogDetailUrl(urls, kind, item) {
  // Places are addressed by slug; every other catalog by numeric id.
  return `${moduleUrl(urls, kind)}/${encodeURIComponent(kind === 'places' ? item.slug || item.id : item.id)}`;
}

export function useDebounced(value, delay = 250) {
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
  if (kind === 'audiencias') {
    // The numeric size gives one consistent format ("86,6 mi"); the label is the fallback.
    const size = Number(item.audience_size);
    if (size > 0) return `Público ${size.toLocaleString('pt-BR', {notation: 'compact', maximumFractionDigits: 1})}`;
    return audience && `Público ${audience}`;
  }
  if (kind === 'canais') return item.audience && `Alcance ${item.audience}`;
  return item.dimensions || '';
}

function cardChips(kind, item, eyebrow) {
  const values = kind === 'places' ? [item.city, item.points?.length && `${item.points.length} pontos`]
    : kind === 'audiencias' ? [item.platform, item.subcategory, item.perfil_socioeconomico && `Classe ${item.perfil_socioeconomico}`]
      : kind === 'canais' ? [] : [item.format_type, item.purpose];
  const seen = new Set([String(eyebrow || '').toLowerCase()]);
  const tidy = value => /^[a-z0-9]+([_-][a-z0-9]+)+$/.test(value) ? value.replace(/[_-]+/g, ' ').replace(/^./, letter => letter.toUpperCase()) : value;
  return values.filter(Boolean).map(String).map(tidy).filter(value => !seen.has(value.toLowerCase()) && seen.add(value.toLowerCase())).slice(0, 2);
}

const VISUAL_KINDS = new Set(['audiencias', 'places']);
/** The API resolves the logo that exists in the app; anything else falls back to an icon. */
export function platformLogo(item) {
  const logo = item.platform_logo || '';
  return logo.startsWith('/static/') || /^https?:/.test(logo) ? logo : '';
}

function CardMark({kind, item}) {
  const logo = kind === 'canais' ? (item.logo_path || item.logo_url || '') : platformLogo(item);
  const label = kind === 'canais' ? item.name : (item.platform || item.name);
  return <LogoTile src={logo} name={label} icon={KIND_ICON[kind] || 'plan'} color={item.cor}/>;
}

const InPlan = () => <span className="planner-card__inplan"><Icon name="check" size={12}/>No plano</span>;

/** The whole card is the link to the detail page; adding to the plan happens there. */
export function CatalogCard({kind, item, urls, selected}) {
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
      {visual ? (item.platform_logo ? <span className="planner-card__identity"><LogoTile src={item.platform_logo} name={item.platform} size="xs"/><span className="planner-card__eyebrow">{[item.platform, item.category].filter(Boolean).join(' · ')}</span></span>
        : eyebrow && <span className="planner-card__eyebrow">{eyebrow}</span>)
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

const SCOPES = [['', 'Todos'], ['nacional_premium', 'Premium nacionais'], ['regional', 'Regionais']];
const PROGRAMMATIC = [['', 'Programático: todos'], ['any', 'Com programático'], ['detected', 'Tags detectadas'], ['declared', 'Só ads.txt'], ['adsense_native', 'AdSense / nativo'], ['not_detected', 'Não detectado'], ['unchecked', 'Não verificado']];
const ADS_TXT = [['', 'ads.txt: todos'], ['valid', 'ads.txt válido'], ['partial', 'ads.txt parcial'], ['missing', 'Sem ads.txt válido'], ['unchecked', 'Não verificado']];
const BULK_LIMIT = 50;

function minutes(seconds) {
  const value = Number(seconds);
  if (!(value > 0)) return '';
  return value >= 60 ? `${Math.floor(value / 60)}min ${String(Math.round(value % 60)).padStart(2, '0')}s` : `${Math.round(value)}s`;
}

function adsBadge(item) {
  if (!item.ads_txt_status) return <CaduBadge tone="neutral">Aguardando verificação</CaduBadge>;
  if (item.ads_txt_status === 'valid') return <CaduBadge tone="success">ads.txt válido · {number(item.ads_txt_records)}</CaduBadge>;
  if (item.ads_txt_status === 'partial') return <CaduBadge tone="warning">ads.txt parcial</CaduBadge>;
  if (item.ads_txt_status === 'unreachable' || String(item.ads_txt_status).startsWith('http_')) return <CaduBadge tone="neutral">ads.txt indisponível</CaduBadge>;
  return <CaduBadge tone="neutral">Sem ads.txt válido</CaduBadge>;
}

function programmaticLabel(item) {
  const signals = (item.programmatic_signals || []).map(entry => entry.signal).slice(0, 2).join(', ');
  switch (item.programmatic_status) {
    case 'detected': return ['Programático', signals];
    case 'ads_txt_declared': return ['Programático (ads.txt)', 'Tags carregadas por script'];
    case 'adsense_native': return ['AdSense / nativo', signals];
    case 'not_detected': return ['Não detectado', 'Na home estática'];
    default: return ['—', item.programmatic_status ? 'Home indisponível' : 'Aguardando'];
  }
}

function PortalRow({item, urls, selected}) {
  const [programmatic, hint] = programmaticLabel(item);
  const visits = Number(item.monthly_visits);
  const region = item.scope === 'nacional_premium' ? 'Premium nacional' : item.uf ? `Regional · ${item.uf}` : '';
  return <a className={`planner-portal planner-portal--wide${selected ? ' is-selected' : ''}`} href={catalogDetailUrl(urls, 'portais', item)}>
    <LogoTile src={item.favicon_url || (item.domain ? `https://${item.domain}/favicon.ico` : '')} name={item.name} icon="browser" size="md"/>
    <span className="planner-portal__main">
      <span className="planner-portal__title"><strong>{item.site_title || item.name}</strong>{selected && <InPlan/>}</span>
      <small>{item.domain}</small>
    </span>
    <span className="planner-portal__fact"><small>Categoria</small><b>{item.category || 'Não categorizado'}</b><small>{region}</small></span>
    <span className="planner-portal__fact"><small>Acessos / mês</small><b>{visits > 0 ? visits.toLocaleString('pt-BR', {notation: 'compact', maximumFractionDigits: 1}) : 'Sem fonte'}</b><small>{item.avg_time_seconds > 0 ? `Tempo médio ${minutes(item.avg_time_seconds)}` : 'Tempo médio: sem fonte'}</small></span>
    <span className="planner-portal__fact"><small>Anúncios</small><b>{programmatic}</b><small>{hint}</small></span>
    <span className="planner-portal__fact">{adsBadge(item)}</span>
    <Icon name="chevron" size={16}/>
  </a>;
}

export function CatalogPage({boot, request, selection, notify}) {
  const kind = boot.module;
  const portalMode = kind === 'portais';
  const [query, setQuery] = useState('');
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState('');
  const [filters, setFilters] = useState({scope: '', uf: '', programmatic: '', ads_txt: ''});
  const [offset, setOffset] = useState(0);
  const [records, setRecords] = useState(Array.isArray(boot.records) ? boot.records : []);
  const [total, setTotal] = useState(boot.records?.length || 0);
  const [loading, setLoading] = useState(false);
  const search = useDebounced(query);
  // The first page arrives with the HTML (portals need the total, so they fetch).
  const preloaded = useRef(Array.isArray(boot.records) && !portalMode);

  useEffect(() => {
    if (preloaded.current) { preloaded.current = false; return undefined; }
    const params = new URLSearchParams({q: search, category: portalMode ? categories.join(',') : category});
    if (portalMode) {
      params.set('limit', String(PORTAL_PAGE)); params.set('offset', String(offset));
      Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
    }
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
  }, [request, notify, kind, portalMode, search, category, categories, filters, offset]);

  const setFilter = (key, value) => { setFilters(current => ({...current, [key]: value, ...(key === 'scope' && value === 'nacional_premium' ? {uf: ''} : {})})); setOffset(0); };
  const toggleCategory = value => { setCategories(current => current.includes(value) ? current.filter(item => item !== value) : [...current, value]); setOffset(0); };
  const [bulkBusy, setBulkBusy] = useState(false);
  async function addFiltered() {
    setBulkBusy(true);
    try {
      const params = new URLSearchParams({q: search, category: categories.join(',')});
      Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
      const {ids = []} = await request(`/catalog/portais/ids?${params}`);
      const pending = ids.filter(id => !selection.isSelected(kind, id)).slice(0, BULK_LIMIT);
      for (const id of pending) await selection.toggle(kind, id);
      notify({message: ids.length > BULK_LIMIT ? `${pending.length} adicionados (limite de ${BULK_LIMIT} por vez; refine o filtro para o restante).` : `${pending.length} portais adicionados ao plano.`});
    } catch (error) { notify({tone: 'error', message: error.message}); } finally { setBulkBusy(false); }
  }

  const countLabel = loading ? 'Atualizando…' : portalMode ? `${number(total)} portais · página ${Math.floor(offset / PORTAL_PAGE) + 1}` : `${number(records.length)} ${records.length === 1 ? 'referência' : 'referências'}`;

  return <>
    <PlannerHeader title={MODULE_LABELS[kind]} description={DESCRIPTIONS[kind]} withContext actions={<ActivePlanChip/>}/>
    <div className="planner-toolbar">
      <CaduInput className="planner-toolbar__search" aria-label="Pesquisar referências" type="search" value={query} placeholder={portalMode ? 'Buscar por portal, domínio ou categoria' : 'Buscar por nome, descrição ou categoria'}
        leading={<span className="planner-toolbar__search-icon" aria-hidden="true"><Icon name="search" size={16}/></span>}
        onChange={event => { setQuery(event.target.value); setOffset(0); }}/>
      {!portalMode && (boot.categories || []).length > 0 && <CaduSelectField className="planner-toolbar__category" aria-label="Categoria" value={category} onChange={event => { setCategory(event.target.value); setOffset(0); }}
        options={[{value: '', label: 'Todas as categorias'}, ...boot.categories.map(value => ({value, label: value}))]}/>}
      <span className="planner-toolbar__count" aria-live="polite">{countLabel}</span>
    </div>
    {portalMode && <div className="planner-portal-filters">
      <div className="planner-segmented" role="group" aria-label="Escopo">
        {SCOPES.map(([value, label]) => <button key={value || 'all'} type="button" aria-pressed={filters.scope === value} className={filters.scope === value ? 'is-active' : ''} onClick={() => setFilter('scope', value)}>{label}</button>)}
      </div>
      {filters.scope !== 'nacional_premium' && (boot.ufs || []).length > 0 && <CaduSelectField className="planner-toolbar__category" aria-label="Estado" value={filters.uf} onChange={event => setFilter('uf', event.target.value)}
        options={[{value: '', label: 'Todos os estados'}, ...boot.ufs.map(value => ({value, label: value}))]}/>}
      <CaduSelectField className="planner-toolbar__category" aria-label="Programático" value={filters.programmatic} onChange={event => setFilter('programmatic', event.target.value)} options={PROGRAMMATIC.map(([value, label]) => ({value, label}))}/>
      <CaduSelectField className="planner-toolbar__category" aria-label="ads.txt" value={filters.ads_txt} onChange={event => setFilter('ads_txt', event.target.value)} options={ADS_TXT.map(([value, label]) => ({value, label}))}/>
      {(boot.categories || []).length > 0 && <details className="planner-multi">
        <summary>{categories.length ? `${categories.length} categorias` : 'Todas as categorias'}</summary>
        <div className="planner-multi__menu">
          {boot.categories.map(value => <label key={value}><input type="checkbox" checked={categories.includes(value)} onChange={() => toggleCategory(value)}/> {value}</label>)}
          {categories.length > 0 && <CaduButton variant="tertiary" size="sm" onClick={() => { setCategories([]); setOffset(0); }}>Limpar</CaduButton>}
        </div>
      </details>}
      <CaduButton variant="secondary" disabled={bulkBusy || !total} onClick={addFiltered}>{bulkBusy ? 'Adicionando…' : `Adicionar filtrados ao plano (${Math.min(total, BULK_LIMIT)})`}</CaduButton>
    </div>}
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
