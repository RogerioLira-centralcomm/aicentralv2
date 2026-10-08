import React, {Fragment, useEffect, useMemo, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {LogoTile, PlannerPanel, RowAddButton, SelectionButton} from './PlannerUi.jsx';
import {MODULE_LABELS, moduleUrl} from './api.js';
import {ActivePlanChip, PlannerHeader} from './PlannerHeader.jsx';
import {ShelfHeader, ShelfIndex} from './ShelfHeader.jsx';
import {ChannelCard, ChannelRow} from './ChannelCard.jsx';
import {PlaceCard} from './PlaceCard.jsx';
import {PlanBanner, ShelfEmpty, ShelfGrid} from './PlannerPromo.jsx';
import {PlannerSelect} from './PlannerSelect.jsx';

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
  if (kind === 'places') return item.traffic ? `${item.traffic_label || 'Movimento'}: ${item.traffic}` : '';
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
  const values = kind === 'places' ? [item.city]
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

const groupAnchor = title => `grupo-${String(title).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;

/** Todos: uma seção por categoria (ou por papel no plano), na ordem do catálogo; com categoria escolhida, uma grade só. */
function channelGroups(records, category, groupBy) {
  if (category || groupBy === 'nenhum') return [{title: '', items: records}];
  const field = groupBy === 'papel' ? 'role' : 'category';
  const groups = new Map();
  records.forEach(item => { const title = item[field] || (field === 'role' ? 'Outros papéis' : 'Outros'); if (!groups.has(title)) groups.set(title, []); groups.get(title).push(item); });
  return [...groups].map(([title, items]) => ({title, items}));
}

const SCOPES = [['', 'Todos'], ['top10', 'Top 10'], ['nacional_premium', 'Premium nacionais'], ['regional', 'Regionais']];

function minutes(seconds) {
  const value = Number(seconds);
  if (!(value > 0)) return '';
  return value >= 60 ? `${Math.floor(value / 60)}min ${String(Math.round(value % 60)).padStart(2, '0')}s` : `${Math.round(value)}s`;
}

function PortalRow({item, urls, selected, onToggle}) {
  const visits = Number(item.monthly_visits);
  const region = item.scope === 'nacional_premium' ? 'Premium nacional' : item.uf ? `Regional · ${item.uf}` : '';
  return <div className={`portal-row${selected ? ' is-selected' : ''} has-shot`}>
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'portais', item)} aria-label={`Ver portal ${item.site_title || item.name}`}/>
    <span className={`portal-row__shot${item.print_url ? '' : ' is-empty'}`}>{item.print_url
      ? <img src={item.print_url} alt="" loading="lazy" onError={event => { event.currentTarget.remove(); }}/> : <Icon name="browser" size={20}/>}</span>
    <LogoTile src={item.favicon_url} fallbacks={item.domain ? [`https://${item.domain}/favicon.ico`, `https://www.google.com/s2/favicons?domain=${item.domain}&sz=64`] : []} name={item.name} icon="browser" size="md"/>
    <span className="portal-row__main"><strong>{item.site_title || item.name}{item.featured_rank >= 1 && item.featured_rank <= 10 && <em className="portal-row__top">Top 10</em>}</strong><small>{item.domain}</small></span>
    <span className="portal-row__fact"><small>Categoria</small><b>{item.category || 'Não categorizado'}</b><small>{region}</small></span>
    <span className="portal-row__fact"><small>Acessos / mês</small><b>{visits > 0 ? visits.toLocaleString('pt-BR', {notation: 'compact', maximumFractionDigits: 1}) : 'Sem fonte'}</b><small>{item.avg_time_seconds > 0 ? `Tempo médio ${minutes(item.avg_time_seconds)}` : 'Tempo médio: sem fonte'}</small></span>
    <span className="portal-row__action"><RowAddButton name={item.site_title || item.name} selected={selected} onToggle={onToggle}/></span>
  </div>;
}

/** "Mais filtros" as one more field of the bar: same trigger and list as the dropdowns beside it. */
function MoreFilters({value, onChange}) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  const count = [value.measurable, value.formats].filter(Boolean).length;
  useEffect(() => {
    if (!open) return undefined;
    const outside = event => { if (!root.current?.contains(event.target)) setOpen(false); };
    const escape = event => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [open]);
  return <div className="planner-select aud-more" ref={root}>
    <button type="button" className="planner-select__trigger" aria-haspopup="true" aria-expanded={open} onClick={() => setOpen(current => !current)}>
      <span className="planner-select__text"><small>Mais filtros</small><span className="planner-select__value"><b>{count ? `${count} ativo${count === 1 ? '' : 's'}` : 'Nenhum'}</b></span></span>
      <Icon name="chevron" size={16}/>
    </button>
    {open && <div className="planner-select__list aud-more__menu" role="group" aria-label="Mais filtros">
      <label><input type="checkbox" checked={value.measurable} onChange={event => onChange({...value, measurable: event.target.checked})}/>Só canais mensuráveis</label>
      <label><input type="checkbox" checked={value.formats} onChange={event => onChange({...value, formats: event.target.checked})}/>Só com formatos cadastrados</label>
    </div>}
  </div>;
}

function ViewToggle({value, onChange}) {
  return <div className="aud-view" role="group" aria-label="Exibição">
    {[['grade', 'table', 'Grade'], ['lista', 'list', 'Lista']].map(([id, icon, label]) => <button key={id} type="button" aria-pressed={value === id}
      className={value === id ? 'is-active' : ''} onClick={() => onChange(id)}><Icon name={icon} size={16}/><span>{label}</span></button>)}
  </div>;
}

export function CatalogPage({boot, request, selection, notify}) {
  const kind = boot.module;
  const portalMode = kind === 'portais';
  // Channels and places share the shelf layout: chips on top, state kept in the URL.
  const shelf = kind === 'canais' || kind === 'places';
  const fromUrl = key => (shelf ? new URLSearchParams(window.location.search).get(key) || '' : '');
  const [query, setQuery] = useState(() => fromUrl('q'));
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState(() => fromUrl('categoria'));
  const [city, setCity] = useState(() => fromUrl('cidade') || (() => { try { return window.localStorage.getItem('planner.places.city') || ''; } catch { return ''; } })());
  const remembered = (key, fallback) => { try { return JSON.parse(window.localStorage.getItem(`planner.${kind}.${key}`)) ?? fallback; } catch { return fallback; } };
  const [groupBy, setGroupByState] = useState(() => remembered('groupMode', 'nenhum'));
  const setGroupBy = value => { setGroupByState(value); try { window.localStorage.setItem(`planner.${kind}.groupMode`, JSON.stringify(value)); } catch { /* not remembered */ } };
  const [view, setViewState] = useState(() => { try { return window.localStorage.getItem('planner.canais.view') === 'lista' ? 'lista' : 'grade'; } catch { return 'grade'; } });
  const setView = value => { setViewState(value); try { window.localStorage.setItem('planner.canais.view', value); } catch { /* the choice just is not remembered */ } };
  const [more, setMoreState] = useState(() => remembered('more', {measurable: false, formats: false}));
  const setMore = update => setMoreState(current => { const next = typeof update === 'function' ? update(current) : update; try { window.localStorage.setItem(`planner.${kind}.more`, JSON.stringify(next)); } catch { /* not remembered */ } return next; });
  // Chip counts come from the full list that arrives with the page, not from the filtered one.
  const categoryCounts = useMemo(() => {
    const counts = new Map();
    (Array.isArray(boot.records) ? boot.records : []).forEach(item => counts.set(item.category, (counts.get(item.category) || 0) + 1));
    return counts;
  }, [boot.records]);
  const [filters, setFilters] = useState({scope: '', uf: ''});
  const [offset, setOffset] = useState(0);
  const [records, setRecords] = useState(Array.isArray(boot.records) ? boot.records : []);
  const [total, setTotal] = useState(boot.records?.length || 0);
  const [loading, setLoading] = useState(false);
  const search = useDebounced(query);
  useEffect(() => {
    if (!shelf) return;
    const params = new URLSearchParams(window.location.search);
    [['q', search], ['categoria', category], ['cidade', city]].forEach(([key, value]) => { if (value) params.set(key, value); else params.delete(key); });
    const text = params.toString();
    window.history.replaceState(null, '', window.location.pathname + (text ? `?${text}` : ''));
  }, [shelf, search, category, city]);
  // The first page arrives with the HTML (portals need the total, so they fetch).
  const preloaded = useRef(Array.isArray(boot.records) && !portalMode && !(shelf && (query || category || city)));

  useEffect(() => {
    if (preloaded.current) { preloaded.current = false; return undefined; }
    const params = new URLSearchParams({q: search, category: portalMode ? categories.join(',') : category});
    if (kind === 'places' && city) params.set('city', city);
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
  }, [request, notify, kind, portalMode, search, category, city, categories, filters, offset]);

  const setFilter = (key, value) => { setFilters(current => ({...current, [key]: value, ...(key === 'scope' && (value === 'nacional_premium' || value === 'top10') ? {uf: ''} : {})})); setOffset(0); };
  const toggleCategory = value => { setCategories(current => current.includes(value) ? current.filter(item => item !== value) : [...current, value]); setOffset(0); };

  const shown = kind === 'canais' ? records.filter(item => (!more.measurable || item.measurable) && (!more.formats || Number(item.formats_count) > 0)) : records;

  const channels = kind === 'canais';
  const channelFilters = Boolean(query || category || more.measurable || more.formats);
  const clearChannelFilters = () => { setQuery(''); setCategory(''); setMore({measurable: false, formats: false}); setOffset(0); };
  const channelBar = channels && <div className="aud-bar" role="search">
    <label className="aud-bar__field aud-bar__field--search"><Icon name="search" size={16}/>
      <span className="aud-bar__text"><small>Buscar</small>
        <input type="search" aria-label="Pesquisar canais" value={query} placeholder="Canal ou categoria" onChange={event => { setQuery(event.target.value); setOffset(0); }}/></span></label>
    {(boot.categories || []).length > 0 && <div className="aud-bar__field"><PlannerSelect label="Categoria" value={category} onChange={value => { setCategory(value); setOffset(0); }}
      options={[{value: '', label: `Todas (${boot.records?.length || 0})`}, ...boot.categories.map(value => ({value, label: value, count: categoryCounts.get(value) || 0}))]}/></div>}
    <div className="aud-bar__field"><PlannerSelect label="Agrupar" value={groupBy} onChange={setGroupBy}
      options={[{value: 'nenhum', label: 'Sem agrupar'}, {value: 'categoria', label: 'Por categoria'}, {value: 'papel', label: 'Por papel no plano'}]}/></div>
    <div className="aud-bar__field"><MoreFilters value={more} onChange={setMore}/></div>
  </div>;

  const headerCount = channels
    ? `${number(shown.length)} ${shown.length === 1 ? 'canal' : 'canais'}${channelFilters ? ' com estes filtros' : ''}`
    : loading ? 'Atualizando…' : portalMode ? `${number(total)} portais · página ${Math.floor(offset / PORTAL_PAGE) + 1}` : `${number(shown.length)} ${shown.length === 1 ? 'local' : 'locais'}`;
  const searchField = <label className="aud-bar__field aud-bar__field--search"><Icon name="search" size={16}/>
    <span className="aud-bar__text"><small>Buscar</small>
      <input type="search" aria-label="Pesquisar referências" value={query} placeholder={portalMode ? 'Portal, domínio ou categoria' : 'Nome, descrição ou categoria'} onChange={event => { setQuery(event.target.value); setOffset(0); }}/></span></label>;
  const categoryMenu = useRef(null);
  // The category menu closes on an outside click or Escape, like the other selects of the bar.
  useEffect(() => {
    const node = categoryMenu.current;
    if (!node) return undefined;
    const outside = event => { if (node.open && !node.contains(event.target)) node.open = false; };
    const escape = event => { if (event.key === 'Escape') node.open = false; };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [portalMode, (boot.categories || []).length]);
  const portalFields = portalMode && <>
    <div className="aud-bar__field"><PlannerSelect label="Escopo" value={filters.scope} onChange={value => setFilter('scope', value)}
      options={SCOPES.map(([value, label]) => ({value, label}))}/></div>
    {!['nacional_premium', 'top10'].includes(filters.scope) && (boot.ufs || []).length > 0 && <div className="aud-bar__field"><PlannerSelect label="Estado" value={filters.uf} onChange={value => setFilter('uf', value)}
      options={[{value: '', label: 'Todos'}, ...boot.ufs.map(value => ({value, label: value}))]}/></div>}
    {(boot.categories || []).length > 0 && <div className="aud-bar__field aud-bar__field--multi"><details className="planner-multi" ref={categoryMenu}>
      <summary><span>Categorias:</span> <b>{categories.length ? `${categories.length} selecionadas` : 'Todas'}</b></summary>
      <div className="planner-multi__menu">
        {boot.categories.map(value => <label key={value}><input type="checkbox" checked={categories.includes(value)} onChange={() => toggleCategory(value)}/> {value}</label>)}
        {categories.length > 0 && <CaduButton variant="tertiary" size="sm" onClick={() => { setCategories([]); setOffset(0); }}>Limpar</CaduButton>}
      </div>
    </details></div>}
  </>;
  const shelfBar = !channels && <div className="aud-bar" role="search">
    {searchField}
    {portalFields}
    {shelf && (boot.categories || []).length > 0 && <div className="aud-bar__field"><PlannerSelect label="Categoria" value={category} onChange={value => { setCategory(value); setOffset(0); }}
      options={[{value: '', label: `Todas (${boot.records?.length || 0})`}, ...boot.categories.map(value => ({value, label: value, count: categoryCounts.get(value) || 0}))]}/></div>}
    {kind === 'places' && (boot.cities || []).length > 0 && <div className="aud-bar__field"><PlannerSelect label="Cidade" value={city}
      onChange={value => { setCity(value); setOffset(0); try { window.localStorage.setItem('planner.places.city', value); } catch { /* not remembered */ } }}
      options={[{value: '', label: 'Todas as cidades'}, ...boot.cities.map(value => ({value, label: value}))]}/></div>}
  </div>;

  return <>
    <ShelfHeader title={MODULE_LABELS[kind]} description={headerCount}
      bar={channels ? channelBar : shelfBar} tools={channels ? <ViewToggle value={view} onChange={setView}/> : null}/>
    {channels && channelFilters && <div className="aud-filters__summary aud-filters__summary--bar">
      <span aria-live="polite">{loading ? 'Atualizando…' : `${number(shown.length)} ${shown.length === 1 ? 'resultado' : 'resultados'}`}</span>
      <CaduButton variant="tertiary" size="sm" onClick={clearChannelFilters}>Limpar filtros</CaduButton>
    </div>}
    {!records.length && !loading ? <ShelfEmpty title="Nenhuma referência encontrada" description="Ajuste a busca ou escolha outra categoria. Se preferir, o Planejar monta uma sugestão com você." action={<CaduButton variant="secondary" onClick={() => { setQuery(''); setCategory(''); setMore({measurable: false, formats: false}); }}>Limpar filtros</CaduButton>}/>
      : portalMode ? <div className="planner-list" aria-label="Portais disponíveis">{records.map(item => <PortalRow key={itemKey(item)} item={item} urls={boot.urls} selected={selection.isSelected(kind, itemKey(item))} onToggle={() => selection.toggle(kind, itemKey(item))}/>)}</div>
        : kind === 'canais' ? (() => {
          // The invitation to plan sits after the first eight cards (or at the end of a short list).
          const groups = channelGroups(shown, category, groupBy);
          const index = groups.filter(group => group.title).map(group => ({id: groupAnchor(group.title), label: group.title, count: group.items.length}));
          let seen = 0;
          let placed = false;
          const blocks = groups.map((group, position) => {
            // Ungrouped shelf: the invitation to plan is a full-width row inside the same grid, after the first eight cards.
            const inline = false;
            seen += group.items.length;
            const banner = !inline && !placed && (seen >= 8 || position === groups.length - 1);
            if (banner || inline) placed = true;
            return <Fragment key={group.title || 'canais'}>
              <section className="fmt-group" id={group.title ? groupAnchor(group.title) : undefined} aria-label={group.title || 'Canais'}>
                {group.title && <h2 className="fmt-group__title">{group.title}<span>{group.items.length}</span></h2>}
                {view === 'lista'
                  ? <div className="channel-list">{group.items.map(item => <ChannelRow key={itemKey(item)} item={item} urls={boot.urls}
                    selected={selection.isSelected(kind, itemKey(item))} onToggle={() => selection.toggle(kind, itemKey(item))}/>)}</div>
                  : <ShelfGrid items={group.items} urls={boot.urls} variants={['formatos', 'planejar']} render={item => <ChannelCard key={itemKey(item)} item={item} urls={boot.urls}
                    selected={selection.isSelected(kind, itemKey(item))} onToggle={() => selection.toggle(kind, itemKey(item))}/>}/>}
              </section>
              {banner && <PlanBanner urls={boot.urls}/>}
            </Fragment>;
          });
          return index.length > 1 ? <div className="shelf-layout"><div className="shelf-layout__main">{blocks}</div><ShelfIndex items={index}/></div> : blocks;
        })()
        : kind === 'places' ? <><ShelfGrid aria-label="Locais disponíveis" items={records} urls={boot.urls} variants={['canais', 'formatos', 'planejar']}
          render={item => <PlaceCard key={itemKey(item)} item={item} urls={boot.urls} selected={selection.isSelected(kind, itemKey(item))} onToggle={() => selection.toggle(kind, itemKey(item))}/>}/>{records.length > 0 && <PlanBanner urls={boot.urls} variant="formatos"/>}</>
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
  ['Finalidade', 'purpose'], ['Especificação', 'dimensions'], ['Arquivos', 'files'],
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
