import React, {useEffect, useMemo, useState} from 'react';
import StudioNavbar from '../cadu-studio-ui/StudioNavbar';
import {Icon} from '../cadu-design-system/components/Icon.jsx';

const PROJECT_KEY = 'cadu-studio-home-project';
const GOALS = [
  ['create', 'plus', 'Criar uma peça', 'Anúncio, post, landing ou site em imagem, com a identidade da marca.'],
  ['videos', 'image', 'Montar um vídeo', 'Cortes, legendas e narração em um só lugar.'],
  ['editor', 'compose', 'Melhorar uma imagem', 'Troque texto, fundo ou elementos de uma imagem que você já tem.'],
  ['analyzer', 'analysis', 'Analisar um criativo', 'Receba uma leitura do que funciona e do que melhorar.'],
];
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

const workTitle = item => item.headline || item.name || item.title || (item.media === 'video' ? 'Vídeo' : 'Imagem');

function WorkCard({item, href, onPreview}) {
  const thumb = safeUrl(item.thumb_url || item.poster_url || item.image_url);
  const title = workTitle(item);
  return <li className="sh-card">
    <button type="button" className="sh-card__media" onClick={() => onPreview(item)} aria-label={`Ver ${title}`}>
      {thumb ? <img src={thumb} alt="" loading="lazy"/> : <span className="sh-card__placeholder"><Icon name="image" size={22}/></span>}
      {item.media === 'video' && <span className="sh-card__badge">Vídeo</span>}
    </button>
    <div className="sh-card__body"><strong title={title}>{title}</strong>
      <span>{[item.aspect_ratio, shortDate(when(item))].filter(Boolean).join(' · ')}</span></div>
    <a className="sh-card__action" href={href}>Continuar</a>
  </li>;
}

/** Quick start for people who already work here: the idea goes to Criar through ?prompt=, with the project kept. */
function QuickCreate({links, href}) {
  const [text, setText] = useState('');
  if (!links.create) return null;
  const submit = event => {
    event.preventDefault();
    const base = href(links.create);
    const value = text.trim().slice(0, 6000);
    window.location.href = value ? `${base}${base.includes('?') ? '&' : '?'}prompt=${encodeURIComponent(value)}` : base;
  };
  return <form className="sh-quick" onSubmit={submit}>
    <input type="text" value={text} onChange={event => setText(event.target.value)} maxLength={600} aria-label="O que você quer criar?" placeholder="O que você quer criar? Ex.: anúncio de lançamento para Instagram"/>
    <button type="submit" className="sh-button">Criar</button>
  </form>;
}

/** New accounts (no work in any project): says what the Studio is for and routes by goal, not by tool name. */
function Onboarding({project, noProjects, firstName, links, href, credits}) {
  const goals = GOALS.filter(([key]) => links[key]);
  return <section className="sh-onboard" aria-label="Primeiros passos no Studio">
    <div className="sh-onboard__hero">
      <div><h1>Bem-vindo ao Studio{firstName ? `, ${firstName}` : ''}</h1>
        <p>Crie anúncios, posts e vídeos já com a identidade da sua marca. O que você quer fazer primeiro?</p>
        {credits && <span className="sh-onboard__credits">Saldo: {Math.round(credits.available).toLocaleString('pt-BR')} tokens</span>}</div>
      <ol className="sh-steps">
        <li className={project ? 'is-done' : ''}><span className="sh-steps__n" aria-hidden="true">{project ? '✓' : 1}</span>
          <div><strong>Escolha o projeto e a marca</strong><span>{noProjects ? 'Ainda não há projeto com marca. Crie um no Workspace.' : 'Na barra de cima: a marca guia cores, tom e logotipo.'}</span></div></li>
        <li><span className="sh-steps__n" aria-hidden="true">2</span><div><strong>Gere a primeira peça</strong><span>Descreva o que precisa e refine o resultado.</span></div></li>
      </ol>
    </div>
    {noProjects && links.workspace && <p className="sh-onboard__cta"><a className="sh-button" href={links.workspace}>Criar projeto no Workspace</a></p>}
    <ul className="sh-tools">{goals.map(([key, icon, label, hint]) => <li key={key}>
      <a className="sh-tool" href={key === 'analyzer' ? links[key] : href(links[key])}>
        <span className="sh-tool__icon"><Icon name={icon} size={18}/></span><strong>{label}</strong><span>{hint}</span></a></li>)}</ul>
  </section>;
}

/** Empty project of someone who already uses the Studio: no tour, just the next step and a way to the work they have elsewhere. */
function EmptyProject({project, links, href, others, onPick}) {
  return <section className="sh-onboard" aria-label="Projeto sem peças">
    <div className="sh-empty">
      <strong>{project ? `${project.name} ainda não tem peças` : 'Este projeto ainda não tem peças'}</strong>
      <span>Comece por aqui ou continue o trabalho de outro projeto.</span>
      <div className="sh-onboard__cta">
        {links.create && <a className="sh-button" href={href(links.create)}>Criar uma peça</a>}
        {links.editor && <a className="sh-onboard__link" href={href(links.editor)}>Editar uma imagem</a>}
        {links.videos && <a className="sh-onboard__link" href={href(links.videos)}>Montar um vídeo</a>}
      </div>
    </div>
    {others.length > 0 && <div><h2 className="sh-onboard__title">Continuar em outro projeto</h2>
      <ul className="sh-tools">{others.map(({id, name, brand, count}) => <li key={id}>
        <button type="button" className="sh-tool" onClick={() => onPick(id)}><strong>{name}</strong>
          <span>{[brand, `${count} ${count === 1 ? 'trabalho' : 'trabalhos'}`].filter(Boolean).join(' · ')}</span></button></li>)}</ul></div>}
  </section>;
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
      const match = list.find(item => [item.id, item.external_project_id].some(id => String(id || '').replace(/^ci:/, '') === wanted));
      const requested = Boolean(String(bootstrap.projectId || '').trim());
      const chosen = match || (requested ? null : list[0]);
      setProjectId(chosen ? String(chosen.id) : '');
      setProjectState({loading: false, error: requested && !match ? 'O projeto escolhido ainda não está disponível no Studio. Selecione um projeto na barra.' : ''});
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
  // The page template falls back to "Minha conta" when the session has no name: not a name to greet.
  const rawName = String(bootstrap.user?.name || '').trim();
  const firstName = rawName && rawName !== 'Minha conta' ? rawName.split(/\s+/)[0] : '';
  const toolHref = base => (project ? `${base}${base.includes('?') ? '&' : '?'}project_id=${encodeURIComponent(project.external_project_id || project.id)}` : base);
  const editorHref = item => toolHref(bootstrap.links?.[item.media === 'video' ? 'videos' : 'editor'] || '#');
  const projectEmpty = items.status === 'ready' && !items.list.length;
  // Is the account new, or is only this project empty? Look for work in the other projects (one library call per client).
  const [others, setOthers] = useState({status: 'idle', list: []});
  useEffect(() => {
    if (!projectEmpty) {setOthers({status: 'idle', list: []}); return undefined;}
    const seen = new Set([String(project?.client_id)]);
    const candidates = projects.filter(item => item.client_id && !seen.has(String(item.client_id)) && seen.add(String(item.client_id))).slice(0, 12);
    if (!candidates.length) {setOthers({status: 'done', list: []}); return undefined;}
    let alive = true;
    setOthers({status: 'loading', list: []});
    const count = (clientId, media) => getJson(`${api}/format-lab/swap/library?client_id=${encodeURIComponent(clientId)}&media=${media}`, bootstrap.csrf)
      .then(data => (Array.isArray(data?.items) ? data.items.length : 0)).catch(() => 0);
    Promise.all(candidates.map(item => Promise.all([count(item.client_id, 'still'), count(item.client_id, 'video')])
      .then(([stills, videos]) => ({id: String(item.id), name: item.name, brand: item.brand_name || '', count: stills + videos}))))
      .then(rows => alive && setOthers({status: 'done', list: rows.filter(row => row.count > 0).sort((a, b) => b.count - a.count).slice(0, 6)}));
    return () => {alive = false;};
  }, [api, bootstrap.csrf, projectEmpty, projects, project?.client_id]);
  // Brand-new accounts may have no project at all, so no items are ever fetched.
  const noProjects = !projectState.loading && !projectState.error && !projects.length;
  const showEmpty = projectEmpty || noProjects;
  const checking = showEmpty && !noProjects && others.status !== 'done';
  // With every type shown, the latest work gets its own larger row and is not repeated in the grid below.
  const recents = filter === 'all' && visible.length > 3 ? visible.slice(0, 3) : [];
  const rest = recents.length ? visible.slice(3) : visible;
  const filterEmpty = items.status === 'ready' && items.list.length > 0 && !visible.length;
  return <div className="sh-app">
    <StudioNavbar active="home" links={bootstrap.links || {}} user={bootstrap.user || {}} projects={options} projectId={projectId}
      projectsLoading={projectState.loading} onProjectChange={changeProject} credits={credits}/>
    <main className="sh-main">
      <header className="sh-head" hidden={showEmpty}>
        <div><h1>{project ? project.name : 'Studio'}</h1>
          <p>{project ? <>{project.brand_name || 'Marca vinculada'} · {items.list.length ? `${items.list.length} ${items.list.length === 1 ? 'trabalho' : 'trabalhos'}` : 'sem trabalhos'}</> : projectState.loading ? 'Carregando projetos…' : 'Escolha um projeto na barra para ver os trabalhos.'}</p></div>
        <div className="sh-filters" role="group" aria-label="Filtrar por tipo">{FILTERS.map(([key, label]) =>
          <button key={key} type="button" aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}</button>)}</div>
      </header>
      {projectState.error && <p className="sh-note is-error" role="alert">{projectState.error}</p>}
      {items.status === 'loading' && <ul className="sh-grid" aria-busy="true">{Array.from({length: 8}, (_, index) => <li key={index} className="sh-card is-skeleton"><span/></li>)}</ul>}
      {items.status === 'error' && <p className="sh-note is-error" role="alert">{items.error}</p>}
      {checking && <ul className="sh-grid" aria-busy="true">{Array.from({length: 4}, (_, index) => <li key={index} className="sh-card is-skeleton"><span/></li>)}</ul>}
      {filterEmpty && <div className="sh-empty"><strong>{filter === 'video' ? 'Nenhum vídeo' : 'Nenhuma imagem'} neste projeto ainda</strong>
        <button type="button" className="sh-button" onClick={() => setFilter('all')}>Mostrar todos</button></div>}
      {showEmpty && !checking && (noProjects || !others.list.length
        ? <Onboarding project={project} noProjects={noProjects} firstName={firstName} links={bootstrap.links || {}} href={toolHref} credits={credits}/>
        : <EmptyProject project={project} links={bootstrap.links || {}} href={toolHref} others={others.list} onPick={changeProject}/>)}
      {visible.length > 0 && <>
        <QuickCreate links={bootstrap.links || {}} href={toolHref}/>
        {recents.length > 0 && <section aria-label="Continuar de onde parou"><h2 className="sh-section">Continuar de onde parou</h2>
          <ul className="sh-grid sh-grid--recent">{recents.map(item => <WorkCard key={`${item.media}-${item.id}`} item={item} onPreview={setPreview} href={editorHref(item)}/>)}</ul></section>}
        {rest.length > 0 && <section aria-label="Todos os trabalhos">{recents.length > 0 && <h2 className="sh-section">Todos os trabalhos</h2>}
          <ul className="sh-grid">{rest.map(item => <WorkCard key={`${item.media}-${item.id}`} item={item} onPreview={setPreview} href={editorHref(item)}/>)}</ul></section>}
      </>}
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
