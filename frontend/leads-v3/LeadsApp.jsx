import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {createApi} from './api.js';
import {Queue} from './Queue.jsx';
import {LeadPanel} from './LeadPanel.jsx';
import {Activities} from './Activities.jsx';
import {Comms} from './Comms.jsx';
import {DisqualifyDialog, EditDialog, NewLeadDialog} from './Dialogs.jsx';
import {Button, Empty, Icon, Toasts} from './ui.jsx';

const FILTERS_KEY = 'leads-v3:filtros';

function readFilters(boot) {
  const base = {executivo: boot.filtroExecutivoInicial || '', status: '', potencial: '', q: ''};
  try { return {...base, ...JSON.parse(localStorage.getItem(FILTERS_KEY) || '{}'), q: ''}; } catch { return base; }
}

function useWide(query) {
  const [match, setMatch] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setMatch(media.matches);
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [query]);
  return match;
}

export function LeadsApp({boot}) {
  const api = useMemo(() => createApi(boot), [boot]);
  const wide = useWide('(min-width: 1600px)');

  const [filters, setFilters] = useState(() => readFilters(boot));
  const [leads, setLeads] = useState([]);
  const [listState, setListState] = useState({loading: true, error: ''});
  const [selected, setSelected] = useState(() => new Set());
  const anchor = useRef(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const [activeId, setActiveId] = useState(null);
  const [detail, setDetail] = useState({lead: null, contacts: [], activities: [], communications: [], loading: false});
  const [tab, setTab] = useState('atividades');
  const [dialog, setDialog] = useState(null); // {type: 'disqualify', ids} | {type: 'edit'} | {type: 'new'}
  const [toasts, setToasts] = useState([]);

  const notify = useCallback((text, tone = 'success') => {
    const id = Date.now() + Math.random();
    setToasts(list => [...list.slice(-3), {id, text, tone}]);
    setTimeout(() => setToasts(list => list.filter(t => t.id !== id)), tone === 'error' ? 7000 : 3500);
  }, []);

  // Fila ---------------------------------------------------------------
  const loadList = useCallback(async () => {
    setListState(s => ({...s, loading: true, error: ''}));
    try {
      const data = await api.listLeads(filters);
      setLeads(data.leads);
      setSelected(current => new Set([...current].filter(id => data.leads.some(l => l.id === id))));
      setListState({loading: false, error: ''});
    } catch (error) {
      setListState({loading: false, error: error.message});
    }
  }, [api, filters]);

  useEffect(() => {
    const timer = setTimeout(loadList, filters.q ? 300 : 0);
    try { localStorage.setItem(FILTERS_KEY, JSON.stringify({...filters, q: ''})); } catch { /* armazenamento indisponível */ }
    return () => clearTimeout(timer);
  }, [loadList, filters]);

  const toggle = useCallback((id, shift) => {
    setSelected(current => {
      const next = new Set(current);
      if (shift && anchor.current != null) {
        const ids = leads.map(l => l.id);
        const [a, b] = [ids.indexOf(anchor.current), ids.indexOf(id)].sort((x, y) => x - y);
        if (a >= 0 && b >= 0) { ids.slice(a, b + 1).forEach(i => next.add(i)); return next; }
      }
      if (next.has(id)) next.delete(id); else next.add(id);
      anchor.current = id;
      return next;
    });
  }, [leads]);

  const toggleAll = () => setSelected(current => current.size === leads.length ? new Set() : new Set(leads.map(l => l.id)));

  const runBulk = async (acao, ids, extra = {}) => {
    setBulkBusy(true);
    try {
      const result = await api.bulk(acao, ids, extra);
      const n = result.alterados.length;
      notify(n ? `${n} ${n === 1 ? 'lead atualizado' : 'leads atualizados'}${result.ignorados ? ` · ${result.ignorados} já estavam assim` : ''}.` : 'Nada mudou: os leads já estavam assim.');
      setSelected(new Set());
      await loadList();
      if (activeId && ids.includes(activeId)) loadDetail(activeId);
      return true;
    } catch (error) {
      notify(error.message, 'error');
      return false;
    } finally { setBulkBusy(false); }
  };

  // Detalhe ------------------------------------------------------------
  const loadDetail = useCallback(async (id, {quiet = false} = {}) => {
    if (!id) return;
    if (!quiet) setDetail(d => ({...d, loading: true, ...(d.lead?.id === id ? {} : {lead: null, contacts: [], activities: [], communications: []})}));
    try {
      const [lead, contacts, activities, communications] = await Promise.all([
        api.lead(id), api.contacts(id), api.activities(id), api.communications(id).catch(() => []),
      ]);
      setDetail({lead, contacts, activities, communications, loading: false});
    } catch (error) {
      setDetail(d => ({...d, loading: false}));
      notify(error.message, 'error');
    }
  }, [api, notify]);

  useEffect(() => { if (activeId) loadDetail(activeId); }, [activeId, loadDetail]);

  const refreshActive = useCallback(() => { loadDetail(activeId, {quiet: true}); loadList(); }, [activeId, loadDetail, loadList]);

  // Navegação pelo teclado na fila: ↑/↓ (fora de campos de texto).
  useEffect(() => {
    const onKey = event => {
      if (dialog || /input|textarea|select/i.test(event.target.tagName) || !leads.length) return;
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      event.preventDefault();
      const index = leads.findIndex(l => l.id === activeId);
      const nextIndex = event.key === 'ArrowDown' ? Math.min(leads.length - 1, index + 1) : Math.max(0, index - 1);
      setActiveId(leads[nextIndex].id);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [leads, activeId, dialog]);

  // Ações vindas dos diálogos -------------------------------------------
  const confirmDisqualify = async motivo => {
    const ok = await runBulk('desqualificar', dialog.ids, {motivo});
    if (ok) setDialog(null);
    return ok;
  };
  const saveEdit = async body => {
    try { await api.updateLead(activeId, body); notify('Dados salvos.'); setDialog(null); refreshActive(); return true; }
    catch (error) { notify(error.message, 'error'); return false; }
  };
  const createLead = async body => {
    try {
      const result = await api.createLead(body);
      notify('Lead criado.');
      setDialog(null);
      await loadList();
      if (result.id) setActiveId(result.id);
      return true;
    } catch (error) { notify(error.message, 'error'); return false; }
  };

  const {lead} = detail;
  const activities = lead && <Activities api={api} leadId={lead.id} contacts={detail.contacts} activities={detail.activities} onChanged={refreshActive} notify={notify}/>;
  const comms = lead && <Comms api={api} lead={lead} contacts={detail.contacts} communications={detail.communications} onChanged={refreshActive} notify={notify}/>;

  return (
    <div className="lv3">
      <header className="lv3-topbar">
        <div className="lv3-topbar__title">
          <h1>Leads</h1>
          <span className="lv3-badge">Mesa v3</span>
        </div>
        <div className="lv3-topbar__actions">
          <a className="lv3-btn lv3-btn--ghost lv3-btn--md" href={`${boot.legacyUrl}/analise`}><Icon name="chart-simple"/><span>Análise</span></a>
          <a className="lv3-btn lv3-btn--ghost lv3-btn--md" href={boot.legacyUrl} title="Importação em massa e kanban ficam no Leads atual"><Icon name="file-import"/><span>Importar</span></a>
          <Button variant="primary" icon="plus" onClick={() => setDialog({type: 'new'})}>Novo lead</Button>
        </div>
      </header>

      <div className={`lv3-grid ${wide ? 'lv3-grid--wide' : ''}`}>
        <Queue boot={boot} leads={leads} loading={listState.loading} error={listState.error} filters={filters} setFilters={setFilters}
          activeId={activeId} selected={selected} busy={bulkBusy}
          onOpen={setActiveId} onToggle={toggle} onToggleAll={toggleAll} onClear={() => setSelected(new Set())} onReload={loadList}
          onBulk={(acao, valor) => runBulk(acao, [...selected], {valor})}
          onDisqualify={() => setDialog({type: 'disqualify', ids: [...selected]})}/>

        <LeadPanel boot={boot} api={api} lead={lead} contacts={detail.contacts} loading={detail.loading} notify={notify}
          onChanged={refreshActive} onEdit={() => setDialog({type: 'edit'})}
          onDisqualify={() => setDialog({type: 'disqualify', ids: [lead.id]})}/>

        {wide ? (
          <>
            <section className="lv3-col lv3-side" aria-label="Atividades">
              <header className="lv3-col__head"><Icon name="list-check"/><h2>Atividades</h2></header>
              <div className="lv3-col__scroll">{activities || <Empty icon="list-check" title="Sem lead selecionado"/>}</div>
            </section>
            <section className="lv3-col lv3-side" aria-label="Comunicação">
              <header className="lv3-col__head"><Icon name="comments"/><h2>Comunicação</h2></header>
              <div className="lv3-col__scroll">{comms || <Empty icon="comments" title="Sem lead selecionado"/>}</div>
            </section>
          </>
        ) : (
          <section className="lv3-col lv3-side" aria-label="Atividades e comunicação">
            <div className="lv3-tabs" role="tablist">
              <button type="button" role="tab" aria-selected={tab === 'atividades'} className={tab === 'atividades' ? 'is-on' : ''} onClick={() => setTab('atividades')}>
                <Icon name="list-check"/>Atividades{detail.activities.length ? <span className="lv3-count">{detail.activities.length}</span> : null}
              </button>
              <button type="button" role="tab" aria-selected={tab === 'comunicacao'} className={tab === 'comunicacao' ? 'is-on' : ''} onClick={() => setTab('comunicacao')}>
                <Icon name="comments"/>Comunicação{detail.communications.length ? <span className="lv3-count">{detail.communications.length}</span> : null}
              </button>
            </div>
            <div className="lv3-col__scroll">
              {(tab === 'atividades' ? activities : comms) || <Empty icon="hand-pointer" title="Sem lead selecionado"/>}
            </div>
          </section>
        )}
      </div>

      {dialog?.type === 'disqualify' && <DisqualifyDialog boot={boot} count={dialog.ids.length} onCancel={() => setDialog(null)} onConfirm={confirmDisqualify}/>}
      {dialog?.type === 'edit' && lead && <EditDialog lead={lead} onCancel={() => setDialog(null)} onSave={saveEdit}/>}
      {dialog?.type === 'new' && <NewLeadDialog boot={boot} onCancel={() => setDialog(null)} onSave={createLead}/>}
      <Toasts items={toasts} onDismiss={id => setToasts(list => list.filter(t => t.id !== id))}/>
    </div>
  );
}
