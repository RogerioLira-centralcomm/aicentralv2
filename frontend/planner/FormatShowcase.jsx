import React, {useContext, useMemo, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduSelectField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {FacetChips} from './AudienceShowcase.jsx';
import {itemKey, useDebounced} from './Catalog.jsx';
import {FormatCard} from './FormatCard.jsx';
import {PlanBar} from './PlanBar.jsx';
import {ShelfEmpty} from './PlannerPromo.jsx';
import {PlannerChrome} from './PlannerHeader.jsx';
import {ShelfBanner} from './ShelfBanner.jsx';

const URL_KEYS = {q: 'q', family: 'familia', platform: 'canal'};
const number = value => Number(value || 0).toLocaleString('pt-BR');
const fold = value => String(value || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

function filtersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return Object.fromEntries(Object.entries(URL_KEYS).map(([key, name]) => [key, params.get(name) || '']));
}

function writeUrl(filters) {
  const params = new URLSearchParams(window.location.search);
  Object.entries(URL_KEYS).forEach(([key, name]) => { if (filters[key]) params.set(name, filters[key]); else params.delete(name); });
  const query = params.toString();
  window.history.replaceState(null, '', window.location.pathname + (query ? `?${query}` : ''));
}

const tally = (records, key) => {
  const counts = new Map();
  records.forEach(item => { const value = item[key]; if (value) counts.set(value, (counts.get(value) || 0) + 1); });
  return counts;
};

/**
 * The creative-format catalog (100+ formats): grouped by family — display,
 * video, CTV… — with search, channel filter and live counts per family.
 */
export function FormatShowcase({boot, selection}) {
  const kind = boot.module === 'interativos' ? 'interativos' : 'formatos';
  const all = Array.isArray(boot.records) ? boot.records : [];
  const {activePlan} = useContext(PlannerChrome);
  const [filters, setFilters] = useState(filtersFromUrl);
  const search = useDebounced(filters.q);
  const set = (key, value) => setFilters(current => { const next = {...current, [key]: value}; writeUrl(next); return next; });

  const matches = (item, ignore) => (ignore === 'family' || !filters.family || item.family === filters.family)
    && (ignore === 'platform' || !filters.platform || item.platform_slug === filters.platform)
    && (!search || fold([item.name, item.description, item.platform, item.format_type, item.dimensions, item.purpose].join(' ')).includes(fold(search)));

  const visible = useMemo(() => all.filter(item => matches(item)), [all, filters.family, filters.platform, search]); // eslint-disable-line react-hooks/exhaustive-deps
  // Each facet counts what the other filters leave, so the numbers always add up.
  const familyCounts = tally(all.filter(item => matches(item, 'family')), 'family');
  const platformCounts = tally(all.filter(item => matches(item, 'platform')), 'platform_slug');
  const order = new Map(all.map(item => [item.family, item.family_order || 99]));
  const families = [...familyCounts.keys()].sort((a, b) => order.get(a) - order.get(b)).map(value => ({value, count: familyCounts.get(value)}));
  const platforms = [...new Map(all.map(item => [item.platform_slug, item.platform || item.platform_slug])).entries()]
    .filter(([slug]) => platformCounts.has(slug)).map(([slug, name]) => ({slug, name, count: platformCounts.get(slug)}))
    .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));
  const groups = families.filter(({value}) => visible.some(item => item.family === value))
    .map(({value}) => ({family: value, items: visible.filter(item => item.family === value)}));
  const familyTotal = [...familyCounts.values()].reduce((sum, count) => sum + count, 0);
  const active = Object.values(filters).filter(Boolean).length;
  const clear = () => { const empty = {q: '', family: '', platform: ''}; writeUrl(empty); setFilters(empty); };

  return <>
    <ShelfBanner kind={kind === 'interativos' ? 'interativos' : 'formatos'} title={kind === 'interativos' ? 'Interativos' : 'Formatos'}
      description={`${number(visible.length)} ${kind === 'interativos' ? (visible.length === 1 ? 'formato interativo' : 'formatos interativos') : (visible.length === 1 ? 'formato' : 'formatos')} de mídia${active ? ' com estes filtros' : ''}, agrupados por família`}/>
    <section className="aud-filters" aria-label="Filtros de formatos">
      <div className="aud-filters__top fmt-filters__top">
        <CaduInput className="aud-filters__search" aria-label="Buscar formatos" type="search" value={filters.q}
          placeholder="Buscar formato, canal ou tamanho"
          leading={<span className="planner-toolbar__search-icon" aria-hidden="true"><Icon name="search" size={16}/></span>}
          onChange={event => set('q', event.target.value)}/>
        <CaduSelectField className="aud-filters__select" aria-label="Canal" value={filters.platform} onChange={event => set('platform', event.target.value)}
          options={[{value: '', label: 'Todos os canais'}, ...platforms.map(item => ({value: item.slug, label: `${item.name} (${number(item.count)})`}))]}/>
      </div>
      <FacetChips label="Família" items={families} value={filters.family} total={familyTotal} onChange={value => set('family', value)}/>
      {active > 0 && <div className="aud-filters__summary">
        <span aria-live="polite">{number(visible.length)} {visible.length === 1 ? 'resultado' : 'resultados'}</span>
        <CaduButton variant="tertiary" size="sm" onClick={clear}>Limpar filtros</CaduButton>
      </div>}
    </section>

    {!groups.length ? <ShelfEmpty title="Nenhum formato com estes filtros" description="Tire um filtro ou busque por outro termo."
      action={<CaduButton variant="secondary" onClick={clear}>Ver todos os formatos</CaduButton>}/>
      : groups.map(group => <section key={group.family} className="fmt-group" aria-labelledby={`fmt-${group.items[0].family_order}`}>
        <h2 id={`fmt-${group.items[0].family_order}`} className="fmt-group__title">{group.family}<span>{number(group.items.length)}</span></h2>
        <div className="planner-grid planner-grid--formats" aria-label={`Formatos de ${group.family}`}>
          {group.items.map(item => <FormatCard key={itemKey(item)} kind={kind} item={item} urls={boot.urls} selected={selection.isSelected(kind, itemKey(item))}
            onToggle={() => selection.toggle(kind, itemKey(item))}/>)}
        </div>
      </section>)}
    <PlanBar noun={kind === 'interativos' ? ['interativo', 'interativos'] : ['formato', 'formatos']} count={selection.count(kind)} href={activePlan ? `${boot.urls.plans}/${encodeURIComponent(activePlan.id)}` : boot.urls.plans}
      chosen={all.filter(item => selection.isSelected(kind, itemKey(item))).map(item => ({key: itemKey(item), logo: item.platform_logo, name: item.name}))}/>
  </>;
}
