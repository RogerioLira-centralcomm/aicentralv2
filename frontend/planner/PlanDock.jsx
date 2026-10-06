import React, {useEffect, useState} from 'react';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {CaduInput} from '../cadu-design-system/components/CaduInput.jsx';
import {CaduSelectField} from '../cadu-design-system/components/CaduField.jsx';
import {LogoTile} from './PlannerUi.jsx';
import {moduleUrl} from './api.js';

const SECTIONS = [['canais', 'Canais'], ['audiencias', 'Audiências'], ['formatos', 'Formatos'], ['interativos', 'Interativos'],
  ['portais', 'Portais e veículos'], ['places', 'Locais']];
const OBJECTIVES = [['awareness', 'Awareness'], ['consideracao', 'Consideração'], ['leads', 'Leads'], ['vendas', 'Vendas'], ['trafego', 'Tráfego']];

/**
 * The plan, always at hand: a closed tab at the corner that opens a side panel.
 * People build a session (channels, audiences, formats) without leaving the page;
 * with no plan open, a quick form creates one and carries the loose picks into it.
 */
export function PlanDock({boot, request, plan, setPlan, selection, notify}) {
  const [open, setOpen] = useState(false);
  const [loose, setLoose] = useState([]);
  const [title, setTitle] = useState('');
  const [objective, setObjective] = useState('awareness');
  const [busy, setBusy] = useState(false);
  const remember = setOpen;

  // Without a plan the picks live in the visitor's loose selection: read them whenever they change.
  useEffect(() => {
    if (plan) return undefined;
    let active = true;
    request('/selections').then(data => { if (active) setLoose(data.selections || []); }).catch(() => {});
    return () => { active = false; };
  }, [request, plan, selection.signature]);

  useEffect(() => {
    if (!open) return undefined;
    const close = event => { if (event.key === 'Escape') remember(false); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [open]);

  const items = plan ? (plan.items || []) : loose;
  const total = items.length;
  const planUrl = plan ? `${boot.urls.plans}/${encodeURIComponent(plan.id)}` : boot.urls.plans;

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const name = title.trim() || `Plano rápido ${new Date().toLocaleDateString('pt-BR')}`;
      const data = await request('/plans', {method: 'POST', body: JSON.stringify({title: name, objective, briefing: {}})});
      const id = data.plan.id;
      for (const [kind] of SECTIONS) {
        const ids = loose.filter(item => item.kind === kind).map(item => String(item.resource_id));
        if (ids.length) await request(`/plans/${id}/items/bulk`, {method: 'POST', body: JSON.stringify({kind, resource_ids: ids})});
      }
      const full = await request(`/plans/${id}`);
      setPlan(full.plan);
      notify?.({message: 'Plano criado. Continue escolhendo aqui mesmo.'});
    } catch (error) {
      notify?.({tone: 'error', message: error.message});
    }
    setBusy(false);
  }

  return <>
    {!open && <button type="button" className="plan-dock__tab" onClick={() => remember(true)} aria-label="Abrir o seu plano">
      <Icon name="plan" size={16}/><span>Seu plano</span>{total > 0 && <b>{total}</b>}
    </button>}
    <aside className={`plan-dock${open ? ' is-open' : ''}`} aria-label="Seu plano" aria-hidden={!open} inert={!open ? '' : undefined}>
      <header className="plan-dock__head">
        <span><small>{plan ? 'Plano aberto' : 'Seleção rápida'}</small><strong>{plan ? plan.title : 'Seu plano'}</strong></span>
        <button type="button" onClick={() => remember(false)} aria-label="Fechar o plano"><Icon name="close" size={18}/></button>
      </header>
      <div className="plan-dock__body">
        {!total ? <p className="plan-dock__empty">Nada escolhido ainda. Use o botão <b>Adicionar ao plano</b> nos canais, audiências e formatos que combinam com a sua campanha.</p>
          : SECTIONS.map(([kind, label]) => {
            const group = items.filter(item => item.kind === kind);
            if (!group.length) return null;
            return <section key={kind}><h3>{label}<span>{group.length}</span></h3>
              <ul>{group.map(item => <li key={item.resource_id}>
                <LogoTile src={item.logo || item.snapshot?.logo_path} name={item.snapshot?.name} icon="plan" size="sm"/>
                <a href={`${moduleUrl(boot.urls, item.kind)}/${encodeURIComponent(item.resource_id)}`}>{item.snapshot?.name || item.resource_id}</a>
                <button type="button" aria-label={`Remover ${item.snapshot?.name || 'item'}`} onClick={() => selection.toggle(item.kind, item.resource_id)}><Icon name="trash" size={15}/></button>
              </li>)}</ul></section>;
          })}
        {!plan && <form className="plan-dock__create" onSubmit={create}>
          <h3>Criar plano rápido</h3>
          <CaduInput aria-label="Nome do plano" placeholder="Nome (ex.: Lançamento verão)" value={title} onChange={event => setTitle(event.target.value)}/>
          <CaduSelectField aria-label="Objetivo" value={objective} onChange={event => setObjective(event.target.value)} options={OBJECTIVES.map(([value, label]) => ({value, label}))}/>
          <CaduButton type="submit" variant="primary" disabled={busy}>{busy ? 'Criando…' : total ? `Criar plano com ${total} ${total === 1 ? 'item' : 'itens'}` : 'Criar plano'}</CaduButton>
        </form>}
      </div>
      {plan && <footer className="plan-dock__foot"><a href={planUrl}>Revisar plano e pedir cotação<Icon name="chevron" size={14}/></a></footer>}
    </aside>
  </>;
}
