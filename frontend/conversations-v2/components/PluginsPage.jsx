import React, {useEffect, useMemo, useState} from 'react';
import {request} from '../lib/api';
import {Icon} from '../lib/icons';

const integrationLogo = name => `/static/images/cadu/technology-logos/${name}`;

function CaduPluginMark({logo, caduMark, name}) {
  const [failed, setFailed] = useState(false);
  const src = logo ? integrationLogo(logo) : caduMark;
  return <span className={`cv-plugin-mark${logo ? ' is-external' : ''}`} aria-hidden="true">
    {src && !failed ? <img src={src} alt="" onError={() => setFailed(true)}/> : <Icon name="brand" size={19}/>}
  </span>;
}

export function PluginsPage({onClose, caduMark = '', exploreUrl = ''}) {
  const [plugins, setPlugins] = useState([]);
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const ready = useMemo(() => plugins.filter(plugin => ['active', 'in_development'].includes(plugin.maturity)), [plugins]);
  const developing = useMemo(() => plugins.filter(plugin => !['active', 'in_development'].includes(plugin.maturity)), [plugins]);

  useEffect(() => {
    let current = true;
    request('/workspace/api/v2/capabilities')
      .then(data => {
        if (!current) return;
        setPlugins(Array.isArray(data.plugins) ? data.plugins : []);
        setIntegrations(Array.isArray(data.future_integrations) ? data.future_integrations : []);
      })
      .catch(failure => { if (current) setError(failure.message || 'Não foi possível carregar os plugins disponíveis.'); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, []);

  return <section className="cv-plugins-page" aria-label="Plugins">
    <header className="cv-plugins-page__header">
      <button type="button" onClick={onClose} aria-label="Voltar à conversa"><Icon name="chevron" size={18}/><span>Voltar</span></button>
      <div><h1>Plugins</h1><p>Recursos do Cadu que trabalham junto com suas conversas e planos.</p></div>
      <span className="cv-plugins-page__count">{loading ? 'Carregando' : `${ready.length} recursos nesta fase`}</span>
    </header>
    <div className="cv-plugins-page__content" aria-live="polite">
      {loading && <p role="status">Carregando plugins…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && <>
        <section className="cv-plugin-shelf">
          <header><div><h2>Plugins do Cadu</h2><p>Selecionados automaticamente quando ajudam na tarefa.</p></div><span>NESTA FASE</span></header>
          <ul>{ready.map(plugin => <li key={plugin.id}>
            <CaduPluginMark caduMark={caduMark} name={plugin.name}/>
            <span className="cv-plugin-card__copy"><strong>{plugin.name}</strong><small>{plugin.description}</small></span>
            <span className={`cv-plugin-status${plugin.maturity === 'active' ? ' is-active' : ''}`}>{plugin.maturity === 'active' ? 'Disponível' : 'Em integração'}</span>
          </li>)}</ul>
        </section>
        {!!developing.length && <section className="cv-plugin-shelf">
          <header><div><h2>Em desenvolvimento</h2><p>Alguns fluxos e páginas ainda estão sendo integrados ao chat.</p></div><span>PRÓXIMOS</span></header>
          <ul>{developing.map(plugin => <li key={plugin.id}>
            <CaduPluginMark caduMark={caduMark} name={plugin.name}/>
            <span className="cv-plugin-card__copy"><strong>{plugin.name}</strong><small>{plugin.description}</small>
              {!!plugin.known_gaps?.length && <small className="cv-plugin-card__detail">{plugin.known_gaps[0]}</small>}
            </span><span className="cv-plugin-status">{plugin.maturity === 'early' ? 'Em evolução' : 'Em breve'}</span>
          </li>)}</ul>
        </section>}
        {!!integrations.length && <section className="cv-plugin-shelf cv-plugin-shelf--integrations">
          <header><div><h2>Integrações externas</h2><p>Conexões que queremos trazer para dentro dos fluxos do Cadu.</p></div><span>PLANEJADAS</span></header>
          <ul>{integrations.map(item => <li key={item.id}>
            <CaduPluginMark logo={item.logo} name={item.name}/>
            <span className="cv-plugin-card__copy"><strong>{item.name}</strong><small>{item.category}</small></span>
            <span className="cv-plugin-status">Planejada</span>
          </li>)}</ul>
        </section>}
      </>}
    </div>
  </section>;
}
