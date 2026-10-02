import React, {useEffect, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduDialog} from '../cadu-design-system/components/CaduDialog.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {MODULE_LABELS} from './api.js';
import {itemKey, useDebounced} from './Catalog.jsx';
import {LogoTile, SelectionButton} from './PlannerUi.jsx';

const KINDS = ['canais', 'audiencias', 'formatos', 'interativos', 'portais', 'places'];
const KIND_ICON = {canais: 'share', audiencias: 'users', formatos: 'table', interativos: 'plugin', portais: 'library', places: 'browser'};

function pathFor(kind, query) {
  const params = new URLSearchParams({q: query});
  if (kind === 'places') return `/places?${params}`;
  if (kind === 'audiencias' || kind === 'portais') params.set('limit', '24');
  return `/catalog/${kind}?${params}`;
}

function logoFor(kind, item) {
  if (kind === 'canais') return item.logo_path || item.logo_url || '';
  if (kind === 'portais') return item.domain ? `https://${item.domain}/favicon.ico` : '';
  return item.platform_logo || '';
}

function subtitleFor(kind, item) {
  const parts = {
    canais: [item.category, item.audience], audiencias: [item.platform, item.category, item.audience],
    formatos: [item.platform, item.dimensions], interativos: [item.platform, item.purpose],
    portais: [item.domain, item.category], places: [item.city, item.category],
  }[kind] || [];
  return parts.filter(Boolean).join(' · ');
}

/**
 * Inclusão de itens sem sair do plano: o usuário busca em qualquer vitrine e
 * adiciona ou tira na hora. O plano atualiza a composição e o balanceamento.
 */
export function AddItemsDialog({request, selection, onClose, initialKind = 'canais'}) {
  const [kind, setKind] = useState(initialKind);
  const [query, setQuery] = useState('');
  const [state, setState] = useState({records: [], loading: true});
  const search = useDebounced(query);

  useEffect(() => {
    const controller = new AbortController();
    setState(current => ({...current, loading: true}));
    request(pathFor(kind, search), {signal: controller.signal})
      .then(data => setState({records: (data.records || []).slice(0, 30), loading: false}))
      .catch(error => { if (error.name !== 'AbortError') setState({records: [], loading: false, error: error.message}); });
    return () => controller.abort();
  }, [request, kind, search]);

  return <CaduDialog className="planner-dialog planner-dialog--wide add-items" closeOnBackdrop onClose={onClose}>{({titleId}) => <>
    <header><h2 id={titleId}>Adicionar ao plano</h2>
      <CaduButton variant="tertiary" size="sm" aria-label="Fechar" onClick={onClose}><Icon name="close" size={18}/></CaduButton></header>
    <div className="add-items__kinds" role="tablist" aria-label="Vitrine">{KINDS.map(value => <button key={value} type="button" role="tab"
      aria-selected={kind === value} className="aud-chip" onClick={() => { setKind(value); setQuery(''); }}>{MODULE_LABELS[value]}</button>)}</div>
    <CaduInput aria-label={`Buscar em ${MODULE_LABELS[kind]}`} type="search" value={query} autoFocus placeholder={`Buscar em ${MODULE_LABELS[kind].toLowerCase()}`}
      leading={<span className="planner-toolbar__search-icon" aria-hidden="true"><Icon name="search" size={16}/></span>}
      onChange={event => setQuery(event.target.value)}/>
    <ul className={`add-items__list${state.loading ? ' is-loading' : ''}`} aria-busy={state.loading} aria-label="Resultados">
      {state.records.map(item => {
        const id = itemKey(item);
        return <li key={id}>
          <LogoTile src={logoFor(kind, item)} name={item.name} icon={KIND_ICON[kind]}/>
          <span><strong>{item.name}</strong><small>{subtitleFor(kind, item)}</small></span>
          <SelectionButton quiet selected={selection.isSelected(kind, id)} onToggle={() => selection.toggle(kind, id)}/>
        </li>;
      })}
      {!state.loading && !state.records.length && <li className="add-items__empty">{state.error || 'Nada encontrado. Tente outro termo.'}</li>}
    </ul>
    <footer><span className="planner-muted">Os itens entram direto na composição e no balanceamento.</span><CaduButton onClick={onClose}>Concluir</CaduButton></footer>
  </>}</CaduDialog>;
}
