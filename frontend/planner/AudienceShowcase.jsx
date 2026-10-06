import React, {useContext, useEffect, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduSelectField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {itemKey, useDebounced} from './Catalog.jsx';
import {AudienceCard} from './AudienceCard.jsx';
import {PlanBar} from './PlanBar.jsx';
import {PlannerChrome} from './PlannerHeader.jsx';
import {ActivePlanChip, PlannerHeader} from './PlannerHeader.jsx';
import {LogoTile} from './PlannerUi.jsx';

const PAGE = 48;
const SORTS = [['relevant', 'Mais relevantes'], ['size', 'Maior público'], ['name', 'Nome (A–Z)']];
// Page URL uses Portuguese names, the API the English ones.
const URL_KEYS = {q: 'q', platform: 'canal', category: 'categoria', subcategory: 'subcategoria', sort: 'ordem'};
const number = value => Number(value || 0).toLocaleString('pt-BR');

function filtersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return Object.fromEntries(Object.entries(URL_KEYS).map(([key, name]) => [key, params.get(name) || (key === 'sort' ? 'relevant' : '')]));
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
  const {activePlan} = useContext(PlannerChrome);
  const [filters, setFilters] = useState(filtersFromUrl);
  const [records, setRecords] = useState(Array.isArray(boot.records) ? boot.records : []);
  const [total, setTotal] = useState(Number(meta.total || 0));
  const [facets, setFacets] = useState(meta.facets || {platforms: [], categories: [], subcategories: []});
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const search = useDebounced(filters.q);
  const first = useRef(Boolean(boot.catalogMeta));
  const query = {...filters, q: search};

  const params = (offset = 0) => new URLSearchParams({q: query.q, platform: query.platform, category: query.category,
    subcategory: query.subcategory, sort: query.sort, limit: String(PAGE), offset: String(offset)});

  useEffect(() => {
    writeUrl(query);
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

  const set = (key, value) => setFilters(current => ({...current, [key]: value, ...(key === 'category' ? {subcategory: ''} : {})}));
  const active = [filters.platform, filters.category, filters.subcategory, filters.q].filter(Boolean).length;
  // "Todos" in each facet shows what the other filters allow.
  const platformTotal = facets.platforms.reduce((sum, item) => sum + item.count, 0);
  const categoryTotal = facets.categories.reduce((sum, item) => sum + item.count, 0);

  return <>
    <PlannerHeader title="Audiências" withContext actions={<ActivePlanChip/>}
      description={`${number(total)} ${total === 1 ? 'audiência comprável' : 'audiências compráveis'}${active ? ' com estes filtros' : ''}`}/>
    <section className="aud-filters aud-filters--aud" aria-label="Filtros de audiências">
      <div className="aud-filters__top aud-filters__top--aud">
        <CaduInput className="aud-filters__search" aria-label="Buscar audiências" type="search" value={filters.q}
          placeholder="Buscar por público, interesse, categoria ou canal"
          leading={<span className="planner-toolbar__search-icon" aria-hidden="true"><Icon name="search" size={16}/></span>}
          onChange={event => set('q', event.target.value)}/>
        <CaduSelectField className="aud-filters__select" aria-label="Categoria" value={filters.category}
          onChange={event => set('category', event.target.value)}
          options={[{value: '', label: `Todas as categorias (${number(categoryTotal)})`}, ...facets.categories.map(item => ({value: item.value, label: `${item.value} (${number(item.count)})`}))]}/>
        {facets.subcategories.length > 0 && <CaduSelectField className="aud-filters__select" aria-label="Subcategoria" value={filters.subcategory}
          onChange={event => set('subcategory', event.target.value)}
          options={[{value: '', label: 'Todas as subcategorias'}, ...facets.subcategories.map(item => ({value: item.value, label: `${item.value} (${number(item.count)})`}))]}/>}
        <CaduSelectField className="aud-filters__select aud-filters__select--sort" aria-label="Ordenar" value={filters.sort}
          onChange={event => set('sort', event.target.value)} options={SORTS.map(([value, label]) => ({value, label}))}/>
      </div>
      <FacetChips inline label="Canal de compra" items={facets.platforms} value={filters.platform} total={platformTotal} onChange={value => set('platform', value)}/>
      {active > 0 && <div className="aud-filters__summary">
        <span aria-live="polite">{loading ? 'Atualizando…' : `${number(total)} ${total === 1 ? 'resultado' : 'resultados'}`}</span>
        <CaduButton variant="tertiary" size="sm" onClick={() => setFilters({q: '', platform: '', category: '', subcategory: '', sort: filters.sort})}>Limpar filtros</CaduButton>
      </div>}
    </section>

    {!records.length && !loading ? <CaduEmptyState title="Nenhuma audiência com estes filtros"
      description="Tire um filtro ou busque por outro termo." action={<CaduButton variant="secondary"
        onClick={() => setFilters({q: '', platform: '', category: '', subcategory: '', sort: 'relevant'})}>Ver todas as audiências</CaduButton>}/>
      : <div className={`planner-grid planner-grid--channels${loading ? ' is-loading' : ''}`} aria-label="Audiências disponíveis" aria-busy={loading}>
        {records.map(item => <AudienceCard key={itemKey(item)} item={item} urls={boot.urls} selected={selection.isSelected('audiencias', itemKey(item))}
          onToggle={() => selection.toggle('audiencias', itemKey(item))}/>)}
      </div>}

    {records.length > 0 && <footer className="aud-more">
      <span>Mostrando {number(records.length)} de {number(total)}</span>
      {records.length < total && <CaduButton variant="secondary" loading={loadingMore} onClick={loadMore}>
        Carregar mais {number(Math.min(PAGE, total - records.length))}</CaduButton>}
    </footer>}
    <PlanBar noun={['audiência', 'audiências']} count={selection.count('audiencias')} href={activePlan ? `${boot.urls.plans}/${encodeURIComponent(activePlan.id)}` : boot.urls.plans}
      chosen={records.filter(item => selection.isSelected('audiencias', itemKey(item))).map(item => ({key: itemKey(item), logo: item.platform_logo, name: item.name}))}/>
  </>;
}
