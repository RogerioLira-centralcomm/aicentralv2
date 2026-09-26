import React, {useEffect, useMemo, useState} from 'react';
import {request} from '../lib/api';
import {Icon} from '../lib/icons';
import {availableFlows, PLUGIN_FLOWS} from '../lib/pluginFlows';
import './plugins.css';
import './pluginFlows.css';
export {pluginPrompt} from '../lib/pluginPrompts';

const integrationLogo = name => `/static/images/cadu/technology-logos/${name}`;
const pluginIcons = {insights:'analysis', 'market-intelligence':'analysis', planner:'table', 'project-search':'search', 'project-activities':'list', 'campaign-search':'search', reports:'analysis', studio:'image', 'google-connect':'brand', 'google-drive':'drive', 'google-calendar':'calendar', 'google-meet':'browser', 'market-radar':'analysis', 'audience-map':'search', 'investment-simulator':'table', 'media-plan-audit':'list', 'campaign-tracker':'analysis', 'creative-concept':'image', 'channel-copy':'list', 'page-review':'browser', 'meeting-copilot':'calendar', 'client-delivery':'list'};

function CaduPluginMark({logo, caduMark, name, pluginId}) {
  const [failed, setFailed] = useState(false);
  const src = logo ? integrationLogo(logo) : caduMark;
  return <span className={`cv-plugin-mark${logo ? ' is-external' : ''}`} aria-hidden="true">
    {logo && src && !failed ? <img src={src} alt="" onError={() => setFailed(true)}/> : !logo && pluginId ? <Icon name={pluginIcons[pluginId] || 'brand'} size={19}/> : src && !failed ? <img src={src} alt="" onError={() => setFailed(true)}/> : <Icon name="brand" size={19}/>}
  </span>;
}

export function PluginsPage({onClose, onUsePlugin, caduMark = '', exploreUrl = ''}) {
  const [plugins, setPlugins] = useState([]);
  const [integrations, setIntegrations] = useState([]);
  const [googleState, setGoogleState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const ready = useMemo(() => plugins.filter(plugin => plugin.selectable && ['active', 'in_development'].includes(plugin.maturity)), [plugins]);
  const flows = useMemo(() => availableFlows(plugins), [plugins]);
  const googlePlugins = useMemo(() => ready.filter(plugin => plugin.id.startsWith('google-')).sort((a, b) => a.sort_order - b.sort_order), [ready]);
  const knownModes = useMemo(() => new Set(PLUGIN_FLOWS.flatMap(flow => flow.modes.map(([id]) => id))), []);
  const developing = useMemo(() => plugins.filter(plugin => !knownModes.has(plugin.id) && !plugin.id.startsWith('google-') &&
    (!plugin.selectable || !['active', 'in_development'].includes(plugin.maturity))), [plugins, knownModes]);

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
    request('/workspace/api/v2/google/connection')
      .then(data => { if (current) setGoogleState(data); })
      .catch(() => { /* The connection card explains unavailable state. */ });
    return () => { current = false; };
  }, []);

  return <section className="cv-plugins-page" aria-label="Plugins">
    <header className="cv-plugins-page__header">
      <button type="button" onClick={onClose} aria-label="Voltar à conversa"><Icon name="chevron" size={18}/><span>Voltar</span></button>
      <div><h1>Plugins</h1><p>Recursos do Cadu que trabalham junto com suas conversas e planos.</p></div>
      <span className="cv-plugins-page__count">{loading ? 'Carregando' : `${flows.length} fluxos de trabalho`}</span>
    </header>
    <div className="cv-plugins-page__content" aria-live="polite">
      {loading && <p role="status">Carregando plugins…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && <>
        <section className="cv-plugin-shelf cv-plugin-flow-shelf">
          <header><div><h2>Fluxos do Cadu</h2><p>Escolha o trabalho. Cada modo aproveita as fontes e ferramentas disponíveis.</p></div><span>NESTA FASE</span></header>
          <ul>{flows.map(flow => <li key={flow.id} className="cv-plugin-flow-card">
            <div className="cv-plugin-flow-card__heading">
              <span className="cv-plugin-mark" aria-hidden="true"><Icon name={flow.icon} size={19}/></span>
              <div><h3>{flow.name}</h3><p>{flow.description}</p></div>
            </div>
            <ol className="cv-plugin-flow-card__steps" aria-label={`Etapas do fluxo ${flow.name}`}>
              {flow.steps.map((step, index) => <li key={`${flow.id}-step-${index}`}><span>{index + 1}</span><p>{step}</p></li>)}
            </ol>
            <div className="cv-plugin-flow-card__modes" aria-label={`Modos de ${flow.name}`}>
              {flow.availableModes.map(mode => <button key={mode.id} type="button" onClick={() => onUsePlugin?.(mode.plugin)}
                aria-label={`${flow.name}: ${mode.label}`}>{mode.label}</button>)}
              {flow.upcomingModes.map(mode => <span key={mode.id} className="is-upcoming" title="Em desenvolvimento">
                {mode.label} · em breve
              </span>)}
            </div>
          </li>)}</ul>
        </section>
        {!!googlePlugins.length && <section className="cv-plugin-shelf cv-plugin-shelf--google">
          <header><div><h2>Google Workspace</h2><p>Conecte sua conta para usar Drive, Calendar e Meet dentro dos fluxos.</p></div><span>INTEGRAÇÕES</span></header>
          <ul>{googlePlugins.map(plugin => <li key={plugin.id}><button type="button" className="cv-plugin-card" onClick={() => onUsePlugin?.(plugin)} aria-label={`Abrir ${plugin.name}`}>
            <CaduPluginMark caduMark={caduMark} name={plugin.name} pluginId={plugin.id}/>
            <span className="cv-plugin-card__copy"><strong>{plugin.name}</strong><small>{plugin.description}</small></span>
            <span className="cv-plugin-status is-active">{plugin.id === 'google-connect' ? (googleState?.connected ? 'Conectado' : 'Conectar') : !googleState?.connected ? 'Requer conexão' : googleState?.services?.find(item => item.key === plugin.id.replace('google-', ''))?.enabled ? 'Usar' : 'Atualizar acesso'}</span>
          </button></li>)}</ul>
        </section>}
        {!!developing.length && <section className="cv-plugin-shelf">
          <header><div><h2>Em desenvolvimento</h2><p>Alguns fluxos e páginas ainda estão sendo integrados ao chat.</p></div><span>PRÓXIMOS</span></header>
          <ul>{developing.map(plugin => <li key={plugin.id}>
            <div className="cv-plugin-card is-disabled" aria-disabled="true">
              <CaduPluginMark caduMark={caduMark} name={plugin.name} pluginId={plugin.id}/>
              <span className="cv-plugin-card__copy"><strong>{plugin.name}</strong><small>{plugin.description}</small></span>
              <span className="cv-plugin-status">{plugin.maturity === 'early' ? 'Em evolução' : 'Em breve'}</span>
            </div>
          </li>)}</ul>
        </section>}
        {!!integrations.length && <section className="cv-plugin-shelf cv-plugin-shelf--integrations">
          <header><div><h2>Integrações externas</h2><p>Conexões que queremos trazer para dentro dos fluxos do Cadu.</p></div><span>PLANEJADAS</span></header>
          <ul>{integrations.map(item => <li key={item.id}>
            <div className="cv-plugin-card is-disabled" aria-disabled="true">
              <CaduPluginMark logo={item.logo} name={item.name}/>
              <span className="cv-plugin-card__copy"><strong>{item.name}</strong><small>{item.category}</small></span>
              <span className="cv-plugin-status">Planejada</span>
            </div>
          </li>)}</ul>
        </section>}
      </>}
    </div>
  </section>;
}
