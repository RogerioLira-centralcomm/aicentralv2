import React, {useEffect, useRef, useState} from 'react';
import {request} from '../lib/api';

const labels = {
  'google-connect': 'Conectar Google',
  'google-drive': 'Google Drive',
  'google-calendar': 'Google Calendar',
  'google-meet': 'Google Meet',
};

const nextPrompts = {
  'google-drive': 'Encontre no meu Google Drive ',
  'google-calendar': 'Mostre os próximos eventos do meu Google Calendar.',
  'google-meet': 'Mostre as reuniões e os artefatos disponíveis no meu Google Meet.',
};

export function GooglePluginPanel({pluginId, connection, loading, error, draft, onDraftChange,
  onClose, onRefresh, onConnect, onUse, onSyncDrive, syncing, projects = [], onLinkResource}) {
  const [linked, setLinked] = useState({});
  const [linkError, setLinkError] = useState('');
  const [searchText, setSearchText] = useState('');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [resources, setResources] = useState([]);
  const [nextOffset, setNextOffset] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [searchRevision, setSearchRevision] = useState(0);
  const previousSync = useRef(connection?.last_sync_at);
  const connected = Boolean(connection?.connected);
  const service = (pluginId || '').replace('google-', '');
  const serviceState = (connection?.services || []).find(item => item.key === service);
  const ready = pluginId === 'google-connect' || serviceState?.enabled;
  useEffect(() => {
    if (previousSync.current !== undefined && previousSync.current !== connection?.last_sync_at) {
      setResources([]);
      setNextOffset(null);
      setOffset(0);
      setSearchRevision(value => value + 1);
    }
    previousSync.current = connection?.last_sync_at;
  }, [connection?.last_sync_at]);
  useEffect(() => {
    if (!connected || !ready || pluginId !== 'google-drive') return undefined;
    let current = true;
    setSearchLoading(true);
    const params = new URLSearchParams({query, offset:String(offset), limit:'20'});
    request(`/workspace/api/v2/google/drive/resources?${params}`)
      .then(data => { if (current) { setResources(previous => offset ? [...previous, ...(data.resources || [])] : data.resources || []); setNextOffset(data.next_offset); setSearchError(''); } })
      .catch(failure => { if (current) setSearchError(failure.message || 'Não foi possível consultar o Drive.'); })
      .finally(() => { if (current) setSearchLoading(false); });
    return () => { current = false; };
  }, [connected, ready, pluginId, query, offset, searchRevision]);
  if (!pluginId) return null;
  return <section className="cv-google-plugin-panel" aria-label={labels[pluginId] || 'Google Workspace'}>
    <div className="cv-google-plugin-panel__top"><span>GOOGLE WORKSPACE · CLIENTE {connection?.client_id || 'ATUAL'}</span><button type="button" onClick={onClose} aria-label="Fechar painel Google">×</button></div>
    <h2>{labels[pluginId] || 'Google Workspace'}</h2>
    {loading ? <p role="status">Verificando sua conexão…</p> : error ? <p role="alert">{error}</p> : <>
      <p>{connected ? <>Conectado como <strong>{connection.google_email}</strong>. Esta autorização pertence à sua conta neste cliente.</>
        : 'Conecte sua conta Google para usar este recurso na conversa. Cada pessoa autoriza a própria conta.'}</p>
      {!connection?.configured && <p className="cv-google-plugin-panel__notice">A configuração do Google Workspace ainda precisa ser concluída no servidor.</p>}
      {connected && !ready && <p className="cv-google-plugin-panel__notice">Esta conta precisa atualizar as permissões para usar {labels[pluginId]}.</p>}
      {connected && pluginId === 'google-drive' && <p>Os arquivos continuam no Drive. Ao associá-los a um projeto, o Cadu guarda a referência ao original.</p>}
      {connected && pluginId === 'google-drive' && connection?.drive_sync_pending && <p role="status">O Drive ainda tem páginas de arquivos para indexar. Continue a sincronização para encontrar os próximos itens.</p>}
      {connected && ready && pluginId === 'google-drive' && <form className="cv-google-plugin-panel__search" onSubmit={event => { event.preventDefault(); setResources([]); setNextOffset(null); setOffset(0); setQuery(searchText.trim()); setSearchRevision(value => value + 1); }}><input value={searchText} onChange={event => setSearchText(event.target.value)} placeholder="Buscar arquivos e pastas" aria-label="Buscar no Google Drive"/><button type="submit">Buscar</button></form>}
      {connected && ready && pluginId === 'google-drive' && <div className="cv-google-plugin-panel__resources"><strong>{query ? `Resultados para “${query}”` : 'Arquivos encontrados'}</strong>{resources.map(item => <div key={item.id}>{/^https:\/\//i.test(item.external_url || '') ? <a href={item.external_url} target="_blank" rel="noreferrer">{item.name}</a> : <span>{item.name}</span>}{!item.accessible_to_me && <small>Descoberto por outra pessoa deste cliente; o Google pode pedir acesso.</small>}{projects.length > 0 && <form onSubmit={async event => {
          event.preventDefault();
          const projectRef = new FormData(event.currentTarget).get('project_ref');
          if (!projectRef) return;
          try { await onLinkResource?.(item.id, projectRef); setLinked(previous => ({...previous, [item.id]: true})); setLinkError(''); }
          catch (failure) { setLinkError(failure.message || 'Não foi possível associar o arquivo.'); }
        }}><select name="project_ref" aria-label={`Projeto para ${item.name}`} required><option value="">Escolher projeto</option>{projects.map(project => {
          const ref = String(project.projectRef || project.ref || (project.id ? `ci:${project.id}` : ''));
          return ref.startsWith('ci:') && <option key={ref} value={ref}>{project.title || project.name || ref}</option>;
        })}</select><button type="submit">{linked[item.id] ? 'Associado' : 'Associar original'}</button></form>}</div>)}{searchLoading && <p role="status">Consultando arquivos…</p>}{!searchLoading && !resources.length && !searchError && <p>{query ? 'Nenhum arquivo encontrado para esta busca.' : 'Nenhum arquivo indexado. Atualize o Drive para procurar.'}</p>}{nextOffset !== null && <button type="button" onClick={() => setOffset(nextOffset)} disabled={searchLoading}>Carregar mais</button>}</div>}
      {searchError && <p role="alert">{searchError}</p>}
      {linkError && <p role="alert">{linkError}</p>}
      {draft && <label className="cv-google-plugin-panel__draft">Seu pedido continua aqui<textarea value={draft} onChange={event => onDraftChange?.(event.target.value)} rows={2}/></label>}
      <div className="cv-google-plugin-panel__actions">
        {(!connected || !ready) && connection?.configured && <button type="button" className="is-primary" onClick={onConnect}>{connected ? 'Atualizar permissões' : 'Conectar minha conta'}</button>}
        {connected && ready && pluginId !== 'google-connect' && <button type="button" className="is-primary" onClick={() => onUse?.(draft || nextPrompts[pluginId])}>Usar na conversa</button>}
        {connected && ready && pluginId === 'google-drive' && <button type="button" onClick={onSyncDrive} disabled={syncing}>{syncing ? 'Atualizando Drive…' : connection?.drive_sync_pending ? 'Continuar sincronização' : 'Atualizar arquivos'}</button>}
        {connected && pluginId === 'google-connect' && <button type="button" className="is-primary" onClick={() => onUse?.(draft || 'Mostre o que posso fazer com minha conta Google conectada.')}>Continuar na conversa</button>}
        <button type="button" onClick={onRefresh}>Atualizar estado</button>
      </div>
    </>}
  </section>;
}
