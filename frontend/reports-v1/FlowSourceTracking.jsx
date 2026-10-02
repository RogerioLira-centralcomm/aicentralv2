import './flow-sources.css';
import React from 'react';
import {CaduTextField} from '../cadu-design-system/components/CaduField.jsx';
import {isSearchSource, searchEnginesOf} from './flowValidation.js';
import {SEARCH_ENGINES, channelLabel, conflictingSource, freeSearchEngines, utmInput} from './flowSourceIdentity.js';

const UTM_FIELDS = [['source', 'utm_source'], ['medium', 'utm_medium'], ['campaign', 'utm_campaign'], ['content', 'utm_content']];

/** How the Super Tag tells this origin apart: UTM fields for ads and messaging, engines for organic search. */
export function FlowSourceTracking({node, nodes, readOnly, onChange, metric}) {
  const conflict = conflictingSource(nodes, node);
  if (isSearchSource(node)) {
    const selected = searchEnginesOf(node);
    const free = new Set([...freeSearchEngines(nodes, node.id), ...selected]);
    const all = selected.includes('*');
    const toggle = id => {
      const current = all ? [] : selected;
      onChange('search_engines', current.includes(id) ? current.filter(item => item !== id) : [...current, id]);
    };
    const sessions = new Map((metric?.search_engines || []).map(item => [item.engine, item.sessions]));
    return <section className="flow-tracking" aria-label="Buscadores">
      <header><strong>Buscadores</strong>{all && <small>Todos, até você escolher</small>}</header>
      <div className="flow-tracking__engines">
        {SEARCH_ENGINES.map(([id, name]) => <label key={id} className={free.has(id) || all ? '' : 'is-taken'}>
          <input type="checkbox" disabled={readOnly || (!free.has(id) && !all)} checked={!all && selected.includes(id)} onChange={() => toggle(id)}/>
          <span>{name}</span>
          {sessions.has(id) ? <b>{Number(sessions.get(id)).toLocaleString('pt-BR')}</b> : !free.has(id) && !all ? <small>em outra origem</small> : null}
        </label>)}
      </div>
      {sessions.has('other') && <p className="flow-tracking__note">Outros buscadores: {Number(sessions.get('other')).toLocaleString('pt-BR')} sessões.</p>}
      {conflict && <p className="flow-tracking__warning" role="alert">{conflict.title || 'Outra busca'} já cobre um destes buscadores. Cada buscador entra em uma só origem.</p>}
    </section>;
  }
  const utm = node.media?.utm || {};
  const setUtm = (field, value) => {
    const next = {...utm, [field]: utmInput(value)};
    if (!next[field]) delete next[field];
    onChange('media', {...(node.media || {}), utm: next});
  };
  return <section className="flow-tracking" aria-label="Rastreamento UTM">
    <header><strong>Rastreamento</strong><small>Campos vazios usam o padrão do canal</small></header>
    <div className="flow-tracking__grid">
      {UTM_FIELDS.map(([field, label]) => <CaduTextField key={field} size="sm" label={label} value={utm[field] || ''} disabled={readOnly} maxLength={100}
        placeholder={field === 'campaign' ? 'nome do fluxo' : field === 'content' ? 'público' : 'padrão'} onChange={event => setUtm(field, event.target.value)}/>)}
    </div>
    {conflict
      ? <p className="flow-tracking__warning" role="alert">{conflict.title || channelLabel(conflict)} usa a mesma utm_source e utm_campaign. Defina uma utm_campaign própria para separar as visitas.</p>
      : <p className="flow-tracking__note">A utm_campaign separa esta origem de outras do mesmo canal no monitoramento.</p>}
  </section>;
}
