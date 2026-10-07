import React, {useEffect, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {PlannerSelect} from './PlannerSelect.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {itemKey, useDebounced} from './Catalog.jsx';
import {AudienceCard} from './AudienceCard.jsx';
import {ShelfEmpty, ShelfGrid} from './PlannerPromo.jsx';
import {ShelfHeader} from './ShelfHeader.jsx';
import {LogoTile} from './PlannerUi.jsx';

const PAGE = 48;
const SORTS = [['relevant', 'Mais relevantes'], ['size', 'Maior público'], ['name', 'Nome (A–Z)']];
// Page URL uses Portuguese names, the API the English ones.
const URL_KEYS = {q: 'q', platform: 'canal', category: 'categoria', subcategory: 'subcategoria', sort: 'ordem'};
const number = value => Number(value || 0).toLocaleString('pt-BR');

const PREFS_KEY = 'planner.audiencias.prefs';
const REMEMBERED = ['platform', 'category', 'sort'];

function readPrefs() {
  try { return JSON.parse(window.localStorage.getItem(PREFS_KEY) || '{}') || {}; } catch { return {}; }
}

/** The URL wins; with a bare URL the person's last channel, category and order come back. */
const urlIsBare = () => { const params = new URLSearchParams(window.location.search); return !Object.values(URL_KEYS).some(name => params.get(name)); };

function filtersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const bare = urlIsBare();
  const prefs = bare ? readPrefs() : {};
  return Object.fromEntries(Object.entries(URL_KEYS).map(([key, name]) => [key, params.get(name) || (REMEMBERED.includes(key) && prefs[key]) || (key === 'sort' ? 'relevant' : '')]));
}

function savePrefs(filters) {
  try { window.localStorage.setItem(PREFS_KEY, JSON.stringify(Object.fromEntries(REMEMBERED.map(key => [key, filters[key] || ''])))); } catch { /* not remembered */ }
}

function writeUrl(filters) {
  const params = new URLSearchParams(window.location.search);
  Object.entries(URL_KEYS).forEach(([key, name]) => {
    const value = filters[key];
    if (value && !(key === 'sort' && value === 'relevant')) params.set(name, value); else params.delete(name);
  });
  const query = params.toString();
  window.history.replaceState(null, '', window.location.pathname + (query ? `?${query}` : ''));
}

/** One row of mutually exclusive choices with live counts ("Todos" clears it). */
export function FacetChips({label, items, value, total, onChange, inline = false}) {
  if (!items.length) return null;
  return <div className={`aud-facet${inline ? ' aud-facet--inline' : ''}`} role="group" aria-label={label}>
    <span className="aud-facet__label">{label}</span>
    <div className="aud-facet__chips">
      <button type="button" className="aud-chip" aria-pressed={!value} onClick={() => onChange('')}>Todos<span>{number(total)}</span></button>
      {items.map(item => <button key={item.value} type="button" className="aud-chip" aria-pressed={value === item.value}
        onClick={() => onChange(value === item.value ? '' : item.value)}>{item.logo && <LogoTile src={item.logo} size="xs"/>}{item.value}<span>{number(item.count)}</span></button>)}
    </div>
  </div>;
}

/**
 * The audience marketplace (900+ audiences): server-side search, channel and
 * category facets with counts, sorting, paging and filters kept in the URL.
 */
export function AudienceShowcase({boot, request, selection, notify}) {
  const meta = boot.catalogMeta || {};
  const [filters, setFilters] = useState(filtersFromUrl);
  const restored = useRef(REMEMBERED.some(key => filters[key] && !(key === 'sort' && filters[key] === 'relevant')) && urlIsBare());
  const [records, setRecords] = useState(Array.isArray(boot.records) ? boot.records : []);
  const [total, setTotal] = useState(Number(meta.total || 0));
  const [facets, setFacets] = useState(meta.facets || {platforms: [], categories: [], subcategories: []});
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const search = useDebounced(filters.q);
  const touched = useRef(false);
  const first = useRef(Boolean(boot.catalogMeta) && !restored.current);
  const query = {...filters, q: search};

  const params = (offset = 0) => new URLSearchParams({q: query.q, platform: query.platform, category: query.category,
    subcategory: query.subcategory, sort: query.sort, limit: String(PAGE), offset: String(offset)});

  useEffect(() => {
    writeUrl(query);
    if (touched.current) savePrefs(query);
    if (first.current) { first.current = false; return undefined; }
    const controller = new AbortController();
    let current = true;
    setLoading(true);
    request(`/catalog/audiencias?${params()}`, {signal: controller.signal})
      .then(data => {
        if (!current) return;
        setRecords(data.records || []);
        setTotal(Number(data.total || 0));
        setFacets(data.facets || {platforms: [], categories: [], subcategories: []});
      })
      .catch(error => { if (current && error.name !== 'AbortError') notify({tone: 'error', message: error.message}); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, filters.platform, filters.category, filters.subcategory, filters.sort]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const data = await request(`/catalog/audiencias?${params(records.length)}`);
      setRecords(current => [...current, ...(data.records || [])]);
      setTotal(Number(data.total || 0));
    } catch (error) {
      notify({tone: 'error', message: error.message});
    } finally {
      setLoadingMore(false);
    }
  };

  const set = (key, value) => { restored.current = false; touched.current = true; setFilters(current => ({...current, [key]: value, ...(key === 'category' ? {subcategory: ''} : {})})); };
  const active = [filters.platform, filters.category, filters.subcategory, filters.q].filter(Boolean).length;
  // "Todos" in each facet shows what the other filters allow.
  const platformTotal = facets.platforms.reduce((sum, item) => sum + item.count, 0);
  const categoryTotal = facets.categories.reduce((sum, item) => sum + item.count, 0);

  const bar = (
    <div className="aud-bar" role="search">
      <label className="aud-bar__field aud-bar__field--search"><Icon name="search" size={16}/>
        <span className="aud-bar__text"><small>Buscar</small>
          <input type="search" aria-label="Buscar audiências" value={filters.q} placeholder="Público, interesse ou canal" onChange={event => set('q', event.target.value)}/></span></label>
      <div className="aud-bar__field"><PlannerSelect label="Canal de compra" value={filters.platform} onChange={value => set('platform', value)}
        options={[{value: '', label: `Todos (${number(platformTotal)})`}, ...facets.platforms.map(item => ({value: item.value, label: item.value, count: number(item.count), logo: item.logo}))]}/></div>
      <div className="aud-bar__field"><PlannerSelect label="Categoria" value={filters.category} onChange={value => set('category', value)}
        options={[{value: '', label: `Todas (${number(categoryTotal)})`}, ...facets.categories.map(item => ({value: item.value, label: item.value, count: number(item.count)}))]}/></div>
      {facets.subcategories.length > 0 && <div className="aud-bar__field"><PlannerSelect label="Subcategoria" value={filters.subcategory} onChange={value => set('subcategory', value)}
        options={[{value: '', label: 'Todas'}, ...facets.subcategories.map(item => ({value: item.value, label: item.value, count: number(item.count)}))]}/></div>}
      <div className="aud-bar__field"><PlannerSelect label="Ordenar" value={filters.sort} onChange={value => set('sort', value)}
        options={SORTS.map(([value, label]) => ({value, label}))}/></div>
    </div>
  );

  const firstName = String(boot.user?.name || '').trim().split(/\s+/)[0];
  const clear = () => { restored.current = false; touched.current = true; setFilters({q: '', platform: '', category: '', subcategory: '', sort: 'relevant'}); };

  // Título e filtros na mesma linha: busca, canal (com logos), categoria e ordem lado a lado.
  return <>
    <ShelfHeader title="Audiências" bar={bar}
      description={`${number(total)} ${total === 1 ? 'audiência' : 'audiências'}${active ? ' com estes filtros' : ''}`}/>
    {(active > 0 || restored.current) && <div className="aud-filters__summary aud-filters__summary--bar">
      <span aria-live="polite">{loading ? 'Atualizando…' : restored.current && !filters.q ? `${firstName ? `${firstName}, mantivemos` : 'Mantivemos'} seus filtros da última visita` : `${number(total)} ${total === 1 ? 'resultado' : 'resultados'}`}</span>
      <CaduButton variant="tertiary" size="sm" onClick={clear}>Limpar filtros</CaduButton>
    </div>}

    {!records.length && !loading ? <ShelfEmpty title="Nenhuma audiência com estes filtros"
      description="Tire um filtro ou busque por outro termo." action={<CaduButton variant="secondary"
        onClick={clear}>Ver todas as audiências</CaduButton>}/>
      : <ShelfGrid className={`planner-grid planner-grid--channels${loading ? ' is-loading' : ''}`} aria-label="Audiências disponíveis" aria-busy={loading} urls={boot.urls} variants={['formatos', 'canais', 'planejar']}
        items={records} render={item => <AudienceCard key={itemKey(item)} item={item} urls={boot.urls} selected={selection.isSelected('audiencias', itemKey(item))}
          onToggle={() => selection.toggle('audiencias', itemKey(item))}/>}/>}

    {records.length > 0 && <footer className="aud-more">
      <span>Mostrando {number(records.length)} de {number(total)}</span>
      {records.length < total && <CaduButton variant="secondary" loading={loadingMore} onClick={loadMore}>
        Carregar mais {number(Math.min(PAGE, total - records.length))}</CaduButton>}
    </footer>}
  </>;
}
