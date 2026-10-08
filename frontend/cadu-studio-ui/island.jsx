import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import StudioNavbar from './StudioNavbar';

// Jinja pages keep `select#mcCaduProject` (filled by mc-cadu-nav.js) as the context contract that
// Criar, Editar and Vídeo read. The navbar mirrors that select and writes back through it, so every
// legacy listener (`change`, `cadu:project-change`, `cadu:brand-change`) keeps working untouched.
function readProjects(select) {
  return Array.from(select?.options || []).filter(option => option.value && option.dataset.clientId).map(option => {
    const extra = /\+(\d+)$/.exec(option.textContent.trim());
    return {
      id: option.value,
      name: option.textContent.split(' · ')[0].trim(),
      brandName: option.dataset.brandName || '',
      extraBrands: extra ? Number(extra[1]) : 0,
    };
  });
}

function snapshot(select) {
  return {
    projects: readProjects(select),
    projectId: select?.value || '',
    loading: !select || select.disabled && /Carregando/.test(select.selectedOptions[0]?.textContent || ''),
    allowQuick: Array.from(select?.options || []).some(option => option.dataset.quickMode === 'true'),
  };
}

async function readCredits(url) {
  const response = await fetch(url, {credentials: 'same-origin', headers: {Accept: 'application/json'}});
  const payload = await response.json().catch(() => ({}));
  const data = payload?.data !== undefined ? payload.data : payload;
  if (!response.ok || !data?.configured) return null;
  const total = Number(data.monthly || 0);
  const available = Number(data.available || 0);
  return {available, usagePercent: total > 0 ? ((total - available) * 100) / total : 0};
}

function BridgedNavbar({bootstrap, select}) {
  const [state, setState] = useState(() => snapshot(select));
  const [credits, setCredits] = useState(null);
  useEffect(() => {
    if (!select) return undefined;
    const sync = () => setState(snapshot(select));
    const observer = new MutationObserver(sync);
    observer.observe(select, {childList: true, subtree: true, attributes: true, attributeFilter: ['disabled']});
    select.addEventListener('change', sync);
    document.addEventListener('cadu:project-ready', sync);
    return () => { observer.disconnect(); select.removeEventListener('change', sync); document.removeEventListener('cadu:project-ready', sync); };
  }, [select]);
  useEffect(() => {
    let alive = true;
    const refresh = () => readCredits(bootstrap.creditSummaryUrl || '/workspace/api/creditos/resumo').then(value => { if (alive && value) setCredits(value); }).catch(() => {});
    refresh();
    document.addEventListener('cadu:credits-refresh', refresh);
    return () => { alive = false; document.removeEventListener('cadu:credits-refresh', refresh); };
  }, [bootstrap.creditSummaryUrl]);
  const onProjectChange = id => {
    if (!select) return;
    select.value = id;
    select.dispatchEvent(new Event('change', {bubbles: true}));
  };
  return <StudioNavbar active={bootstrap.active} links={bootstrap.links || {}} user={bootstrap.user || {}}
    projects={state.projects} projectId={state.projectId} projectsLoading={state.loading} allowQuick={state.allowQuick}
    onProjectChange={select ? onProjectChange : undefined} credits={credits}/>;
}

export function mountStudioNavbar() {
  const mount = document.getElementById('caduStudioNavbar');
  const data = document.getElementById('caduStudioNavbarBootstrap');
  const bar = document.getElementById('mcCaduBar');
  if (!mount || !data) return;
  let bootstrap;
  try { bootstrap = JSON.parse(data.textContent || '{}'); } catch (_error) { return; }
  createRoot(mount).render(<BridgedNavbar bootstrap={bootstrap} select={document.getElementById('mcCaduProject')}/>);
  bar?.classList.add('has-studio-navbar');
}

mountStudioNavbar();
