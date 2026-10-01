import React, {useEffect, useRef, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduBadge} from '../cadu-design-system/components/CaduBadge.jsx';
import {CaduEmptyState} from '../cadu-design-system/components/CaduEmptyState.jsx';
import {CaduPageHeader} from '../cadu-design-system/components/CaduPageHeader.jsx';
import {CaduSelectField} from '../cadu-design-system/components/CaduField.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {VisualIdentity} from '../cadu-design-system/components/VisualIdentity.jsx';
import {PlannerPanel, SelectionButton} from './PlannerUi.jsx';
import {MODULE_LABELS, moduleUrl} from './api.js';

const PORTAL_PAGE = 50;
const DESCRIPTIONS = {
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

function cardMeta(kind, item) {
  const audience = audienceLabel(item);
  if (kind === 'places') return [item.city, item.traffic && `${item.traffic_label || 'Movimento'}: ${item.traffic}`, item.points?.length && `${item.points.length} pontos`];
  if (kind === 'audiencias') return [item.platform, item.subcategory, audience && `Público: ${audience}`];
  if (kind === 'canais') return [item.category, item.audience && `Alcance: ${item.audience}`];
  return [item.platform, item.dimensions || item.format_type, item.purpose];
}

function CatalogCard({kind, item, urls, selected, onToggle}) {
  const logo = kind === 'canais' ? (item.logo_path || item.logo_url || '') : (item.platform_logo || item.logo_path || '');
  const image = kind === 'canais' ? '' : item.image_url || '';
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = image && !imageFailed;
  const meta = cardMeta(kind, item).filter(Boolean);
  return <article className="planner-card">
    <a className="planner-card__hit" href={catalogDetailUrl(urls, kind, item)} aria-label={`Abrir detalhes: ${item.name}`}/>
    <div className={`planner-card__art${showImage ? ' has-image' : ''}${!showImage ? ' is-identity' : ''}`}>
      {showImage ? <img src={image} alt="" loading="lazy" onError={() => setImageFailed(true)}/>
        : logo ? <VisualIdentity src={logo} initials={item.name} label={item.name} imageTreatment="brand"/>
          : <Icon name={KIND_ICON[kind] || 'plan'} size={24}/>}
    </div>
    <div className="planner-card__body">
      <span className="planner-card__eyebrow">{item.category || item.platform || item.segment || item.city || MODULE_LABELS[kind]}</span>
      <h2>{item.name}</h2>
      <p>{item.description || item.purpose || 'Referência para apoiar as decisões do plano.'}</p>
      {meta.length > 0 && <div className="planner-card__meta">{meta.map((value, index) => <span key={`${index}-${value}`}>{value}</span>)}</div>}
      <footer className="planner-card__footer"><span>Ver detalhes</span><SelectionButton selected={selected} onToggle={onToggle}/></footer>
    </div>
  </article>;
}

function PortalRow({item, urls, selected, onToggle}) {
  const [faviconFailed, setFaviconFailed] = useState(false);
  const pages = Number(item.discovered_pages_count);
  const updates = Number(item.crawl_updates_count);
  return <article className="planner-portal">
    <a className="planner-card__hit" href={catalogDetailUrl(urls, 'portais', item)} aria-label={`Abrir ficha do portal: ${item.name}`}/>
    <span className="planner-portal__favicon">{faviconFailed ? <Icon name="browser" size={18}/> : <img src={`https://${item.domain}/favicon.ico`} alt="" loading="lazy" onError={() => setFaviconFailed(true)}/>}</span>
    <span className="planner-portal__main">
      <span className="planner-portal__title"><strong>{item.name}</strong>{item.featured_rank && <CaduBadge tone="brand">Destaque</CaduBadge>}</span>
      <small>{item.domain}</small>
      <span className="planner-portal__description">{item.description || 'Veículo editorial independente.'}</span>
    </span>
    <span className="planner-portal__fact planner-portal__fact--category"><small>Categoria</small><b>{item.category || 'Não categorizado'}</b></span>
    <span className="planner-portal__fact planner-portal__fact--audience"><small>Audiência pública</small><b>{audienceLabel(item) || 'Sem estimativa publicada'}</b>
      {item.audience_source_url && <a href={item.audience_source_url} target="_blank" rel="noreferrer">Fonte ↗</a>}</span>
    <span className="planner-portal__fact planner-portal__fact--pages"><small>Páginas lidas</small><b>{pages > 0 ? number(pages) : item.last_crawled_at ? '—' : 'Aguardando leitura'}</b>
      {item.last_crawled_at && <small>{updates > 0 ? `${number(updates)} leituras · ` : ''}{new Date(item.last_crawled_at).toLocaleDateString('pt-BR')}</small>}</span>
    <SelectionButton selected={selected} onToggle={onToggle}/>
  </article>;
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

  const toggle = item => selection.toggle(kind, itemKey(item));
  const countLabel = loading ? 'Atualizando…' : portalMode ? `${number(total)} portais · página ${Math.floor(offset / PORTAL_PAGE) + 1}` : `${number(records.length)} ${records.length === 1 ? 'referência' : 'referências'}`;

  return <>
    <CaduPageHeader title={MODULE_LABELS[kind]} description={DESCRIPTIONS[kind] || 'Referências selecionadas para encontrar o contexto certo para o plano.'}
      actions={<CaduButton variant="secondary" href={boot.urls.plans}>Ver planos</CaduButton>}/>
    <div className="planner-toolbar">
      <CaduInput className="planner-toolbar__search" aria-label="Pesquisar referências" type="search" value={query} placeholder={portalMode ? 'Buscar por portal, domínio ou categoria' : 'Buscar por nome, descrição ou categoria'}
        leading={<span className="planner-toolbar__search-icon" aria-hidden="true"><Icon name="search" size={16}/></span>}
        onChange={event => { setQuery(event.target.value); setOffset(0); }}/>
      {(boot.categories || []).length > 0 && <CaduSelectField className="planner-toolbar__category" aria-label="Categoria" value={category} onChange={event => { setCategory(event.target.value); setOffset(0); }}
        options={[{value: '', label: 'Todas as categorias'}, ...boot.categories.map(value => ({value, label: value}))]}/>}
      <span className="planner-toolbar__count" aria-live="polite">{countLabel}</span>
    </div>
    {!records.length && !loading ? <PlannerPanel className="planner-panel--flush"><CaduEmptyState title="Nenhuma referência encontrada" description="Ajuste a busca ou escolha outra categoria."/></PlannerPanel>
      : portalMode ? <div className="planner-list" aria-label="Portais disponíveis">{records.map(item => <PortalRow key={itemKey(item)} item={item} urls={boot.urls} selected={selection.isSelected(kind, itemKey(item))} onToggle={() => toggle(item)}/>)}</div>
        : <div className="planner-grid" aria-label={`${MODULE_LABELS[kind]} disponíveis`}>{records.map(item => <CatalogCard key={itemKey(item)} kind={kind} item={item} urls={boot.urls} selected={selection.isSelected(kind, itemKey(item))} onToggle={() => toggle(item)}/>)}</div>}
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
    <CaduPageHeader back={{href: moduleUrl(boot.urls, kind), label: MODULE_LABELS[kind]}} title={item.name}
      description={[item.domain, item.description].filter(Boolean).join(' · ')}
      actions={<SelectionButton size="md" selected={selection.isSelected(kind, id)} onToggle={() => selection.toggle(kind, id)}/>}/>
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
