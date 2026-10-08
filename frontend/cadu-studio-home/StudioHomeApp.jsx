import React, {useEffect, useMemo, useState} from 'react';
import StudioNavbar from '../cadu-studio-ui/StudioNavbar';
import {Icon} from '../cadu-design-system/components/Icon.jsx';

const PROJECT_KEY = 'cadu-studio-home-project';
const FILTERS = [['all', 'Todos'], ['still', 'Imagens'], ['video', 'Vídeos']];
const remember = id => {try {localStorage.setItem(PROJECT_KEY, id);} catch (_) { /* storage may be blocked */ }};
const recall = () => {try {return localStorage.getItem(PROJECT_KEY) || '';} catch (_) {return '';}};
const when = item => item.updated_at || item.created_at || item.saved_at || item.createdAt || '';
const shortDate = value => {const date = value ? new Date(value) : null; return date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString('pt-BR', {day: '2-digit', month: 'short'}) : '';};
const safeUrl = value => (typeof value === 'string' && (value.startsWith('/') || value.startsWith('https://')) ? value : '');

async function getJson(url, csrf) {
  const response = await fetch(url, {credentials: 'same-origin', headers: {Accept: 'application/json', 'X-Trocr-CSRF-Token': csrf || '', 'X-Studio-CSRF-Token': csrf || ''}});
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.success === false) throw new Error(body.error || 'Não foi possível carregar.');
  return body.data !== undefined ? body.data : body;
}

async function readCredits(url) {
  const data = await getJson(url);
  if (!data?.configured) return null;
  const total = Number(data.monthly || 0), available = Number(data.available || 0);
  return {available, usagePercent: total > 0 ? ((total - available) * 100) / total : 0};
}

/** Studio home: only the recent work of the project chosen in the bar, to pick up where it stopped. */
export default function StudioHomeApp({bootstrap = {}}) {
  const api = bootstrap.apiRoot || '/studio/api';
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState('');
  const [projectState, setProjectState] = useState({loading: true, error: ''});
  const [credits, setCredits] = useState(null);
  const [items, setItems] = useState({status: 'idle', list: [], error: ''});
  const [filter, setFilter] = useState('all');
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    let alive = true;
    getJson(`${api}/format-lab/studio/project-contexts`).then(data => {
      if (!alive) return;
      const list = data?.items || [];
      setProjects(list);
      const wanted = String(bootstrap.projectId || recall() || '').replace(/^ci:/, '');
      const match = list.find(item => [item.id, item.external_project_id].some(id => String(id || '').replace(/^ci:/, '') === wanted)) || list[0];
      setProjectId(match ? String(match.id) : '');
      setProjectState({loading: false, error: ''});
    }).catch(error => alive && setProjectState({loading: false, error: error.message}));
    readCredits(bootstrap.creditSummaryUrl || '/workspace/api/creditos/resumo').then(value => alive && value && setCredits(value)).catch(() => {});
    return () => {alive = false;};
  }, [api, bootstrap.projectId, bootstrap.creditSummaryUrl]);

  const project = projects.find(item => String(item.id) === String(projectId)) || null;
  useEffect(() => {
    if (!project?.client_id) {setItems({status: projectState.loading ? 'loading' : 'idle', list: [], error: ''}); return undefined;}
    let alive = true;
    setItems({status: 'loading', list: [], error: ''});
    const load = media => getJson(`${api}/format-lab/swap/library?client_id=${encodeURIComponent(project.client_id)}&media=${media}`, bootstrap.csrf)
      .then(data => (Array.isArray(data?.items) ? data.items : []).filter(item => item && typeof item === 'object').map(item => ({...item, media})));
    Promise.all([load('still'), load('video')]).then(([stills, videos]) => {
      if (!alive) return;
      const list = [...stills, ...videos].sort((a, b) => String(when(b)).localeCompare(String(when(a))));
      setItems({status: 'ready', list, error: ''});
    }).catch(error => alive && setItems({status: 'error', list: [], error: error.message}));
    return () => {alive = false;};
  }, [api, bootstrap.csrf, project?.client_id, projectState.loading]);

  const visible = useMemo(() => items.list.filter(item => filter === 'all' || item.media === filter).slice(0, 24), [items.list, filter]);
  const options = projects.map(item => ({id: String(item.id), name: item.name, brandName: item.brand_name || ''}));
  const changeProject = id => {setProjectId(id); remember(id);};
  const editorHref = item => {
    const base = bootstrap.links?.[item.media === 'video' ? 'videos' : 'editor'] || '#';
    return project ? `${base}${base.includes('?') ? '&' : '?'}project_id=${encodeURIComponent(project.external_project_id || project.id)}` : base;
  };

  return <div className="sh-app">
    <StudioNavbar active="home" links={bootstrap.links || {}} user={bootstrap.user || {}} projects={options} projectId={projectId}
      projectsLoading={projectState.loading} onProjectChange={changeProject} credits={credits}/>
    <main className="sh-main">
      <header className="sh-head">
        <div><h1>Trabalhos recentes</h1>
          <p>{project ? <>Do projeto <strong>{project.name}</strong> · {project.brand_name || 'marca vinculada'}</> : projectState.loading ? 'Carregando projetos…' : 'Escolha um projeto na barra para ver os trabalhos.'}</p></div>
        <div className="sh-filters" role="group" aria-label="Filtrar por tipo">{FILTERS.map(([key, label]) =>
          <button key={key} type="button" aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>)}</div>
      </header>
      {projectState.error && <p className="sh-note is-error" role="alert">{projectState.error}</p>}
      {items.status === 'loading' && <ul className="sh-grid" aria-busy="true">{Array.from({length: 8}, (_, index) => <li key={index} className="sh-card is-skeleton"><span/></li>)}</ul>}
      {items.status === 'error' && <p className="sh-note is-error" role="alert">{items.error}</p>}
      {items.status === 'ready' && !visible.length && <div className="sh-empty"><Icon name="image" size={28}/><strong>Nenhum trabalho ainda</strong>
        <span>Crie a primeira peça deste projeto.</span>{bootstrap.links?.create && <a className="sh-button" href={bootstrap.links.create}>Criar</a>}</div>}
      {visible.length > 0 && <ul className="sh-grid">{visible.map(item => {
        const thumb = safeUrl(item.thumb_url || item.poster_url || item.image_url);
        const title = item.headline || item.name || item.title || (item.media === 'video' ? 'Vídeo' : 'Imagem');
        return <li key={`${item.media}-${item.id}`} className="sh-card">
          <button type="button" className="sh-card__media" onClick={() => setPreview(item)} aria-label={`Ver ${title}`}>
            {thumb ? <img src={thumb} alt="" loading="lazy"/> : <span className="sh-card__placeholder"><Icon name="image" size={22}/></span>}
            {item.media === 'video' && <span className="sh-card__badge">Vídeo</span>}
          </button>
          <div className="sh-card__body"><strong title={title}>{title}</strong>
            <span>{[item.aspect_ratio, shortDate(when(item))].filter(Boolean).join(' · ')}</span></div>
          <a className="sh-card__action" href={editorHref(item)}>Continuar</a>
        </li>;
      })}</ul>}
      {items.list.length > visible.length && bootstrap.links?.library && <p className="sh-more"><a href={bootstrap.links.library}>Ver todos na biblioteca</a></p>}
    </main>
    {preview && <div className="sh-preview" role="dialog" aria-modal="true" aria-label="Prévia do trabalho" onClick={() => setPreview(null)}>
      <button type="button" className="sh-preview__close" aria-label="Fechar" onClick={() => setPreview(null)}><Icon name="close" size={18}/></button>
      <figure onClick={event => event.stopPropagation()}>
        {preview.media === 'video' && safeUrl(preview.video_url) ? <video src={safeUrl(preview.video_url)} controls autoPlay playsInline/>
          : <img src={safeUrl(preview.image_url || preview.thumb_url || preview.poster_url)} alt=""/>}
        <figcaption><strong>{preview.headline || preview.name || preview.title || 'Trabalho'}</strong><a className="sh-button" href={editorHref(preview)}>Continuar editando</a></figcaption>
      </figure>
    </div>}
  </div>;
}
