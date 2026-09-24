import React, {useEffect, useMemo, useState} from 'react';
import {request} from '../lib/api';
import {Icon} from '../lib/icons';

function toolGroups(tools) {
  const groups = new Map();
  tools.forEach(tool => {
    const title = String(tool.category || tool.group || tool.provider || 'Ferramentas disponíveis');
    if (!groups.has(title)) groups.set(title, []);
    groups.get(title).push(tool);
  });
  return [...groups.entries()].map(([title, items]) => ({title, items}));
}

export function PluginsPage({onClose, exploreUrl = ''}) {
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const groups = useMemo(() => toolGroups(tools), [tools]);

  useEffect(() => {
    let current = true;
    request('/workspace/api/v2/capabilities')
      .then(data => { if (current) setTools(Array.isArray(data.tools) ? data.tools : []); })
      .catch(failure => { if (current) setError(failure.message || 'Não foi possível carregar os plugins disponíveis.'); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, []);

  return <section className="cv-plugins-page" aria-label="Plugins">
    <header className="cv-plugins-page__header">
      <button type="button" onClick={onClose} aria-label="Voltar à conversa"><Icon name="chevron" size={18}/><span>Voltar</span></button>
      <div><h1>Plugins</h1><p>Ferramentas disponíveis para usar nas conversas.</p></div>
      <span className="cv-plugins-page__count">{loading ? 'Carregando' : `${tools.length} ${tools.length === 1 ? 'ferramenta' : 'ferramentas'}`}</span>
    </header>
    <div className="cv-plugins-page__content" aria-live="polite">
      {loading && <p role="status">Carregando ferramentas…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && !tools.length && <div className="cv-plugins-page__empty"><Icon name="brand" size={24}/><h2>Nenhum plugin conectado</h2><p>Conecte ferramentas para ampliar o que o Cadu pode fazer nas conversas.</p>{exploreUrl && <a href={exploreUrl}>Explorar conexões</a>}</div>}
      {!loading && !error && groups.map(group => <section className="cv-plugins-page__group" key={group.title}>
        <header><h2>{group.title}</h2><span>{group.items.length}</span></header>
        <ul>{group.items.map((tool, index) => <li key={tool.name || tool.id || `${group.title}-${index}`}><span className="cv-plugins-page__icon"><Icon name="brand" size={17}/></span><span><strong>{tool.title || tool.name || tool.id || 'Ferramenta'}</strong><small>{tool.description || tool.summary || 'Disponível nas conversas.'}</small></span></li>)}</ul>
      </section>)}
    </div>
  </section>;
}
