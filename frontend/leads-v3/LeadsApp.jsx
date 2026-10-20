import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {createApi} from './api.js';
import {Queue} from './Queue.jsx';
import {LeadPanel} from './LeadPanel.jsx';
import {Activities} from './Activities.jsx';
import {Comms} from './Comms.jsx';
import {CompanyDialog, ConvertDialog, DisqualifyDialog, EditDialog, GoldenAddDialog, NewLeadDialog} from './Dialogs.jsx';
import {GoldenCircle} from './GoldenCircle.jsx';
import {Operacao} from './Operacao.jsx';
import {Button, Empty, Icon, Toasts} from './ui.jsx';

const FILTERS_KEY = 'leads-v3:filtros';
const MODE_KEY = 'leads-v3:modo';
const VIEW_KEY = 'leads-v3:vista';
const readView = () => { try { return localStorage.getItem(VIEW_KEY) === 'operacao' ? 'operacao' : 'mesa'; } catch { return 'mesa'; } };
const readMode = () => { try { return localStorage.getItem(MODE_KEY) === 'golden' ? 'golden' : 'fila'; } catch { return 'fila'; } };

function readFilters(boot) {
  const base = {executivo: boot.filtroExecutivoInicial || '', status: '', potencial: '', origem: '', q: ''};
  try { const {golden, ...salvos} = JSON.parse(localStorage.getItem(FILTERS_KEY) || '{}'); return {...base, ...salvos, q: ''}; } catch { return base; }
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
  const listSeq = useRef(0);
  const detailSeq = useRef(0);

  const [activeId, setActiveId] = useState(null);
  const [detail, setDetail] = useState({lead: null, contacts: [], activities: [], communications: [], candidates: [], golden: null, cadences: [], loading: false});
  const [mode, setModeState] = useState(readMode);
  const [view, setViewState] = useState(readView);
  const [trimestre, setTrimestre] = useState(boot.trimestre);
  const [golden, setGolden] = useState({data: null, loading: false, error: ''});
  const goldenSeq = useRef(0);
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
    const seq = ++listSeq.current;
    setListState(s => ({...s, loading: true, error: ''}));
    try {
      const data = await api.listLeads(filters);
      if (seq !== listSeq.current) return; // resposta de um filtro antigo
      setLeads(data.leads);
      setSelected(current => new Set([...current].filter(id => data.leads.some(l => l.id === id))));
      setListState({loading: false, error: ''});
    } catch (error) {
      if (seq === listSeq.current) setListState({loading: false, error: error.message});
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
    const seq = ++detailSeq.current;
    if (!quiet) setDetail(d => ({...d, loading: true, ...(d.lead?.id === id ? {} : {lead: null, contacts: [], activities: [], communications: [], candidates: [], golden: null, cadences: []})}));
    try {
      const [lead, contacts, activities, communications, candidates, golden, cadences] = await Promise.all([
        api.lead(id), api.contacts(id), api.activities(id), api.communications(id).catch(() => []),
        // Partes do Leads v3: sem a migração aplicada, ficam vazias em vez de quebrar a tela.
        api.candidates(id).catch(() => []), api.leadGolden(id).catch(() => null), api.leadCadences(id).catch(() => []),
      ]);
      if (seq !== detailSeq.current) return; // o usuário já abriu outro lead
      setDetail({lead, contacts, activities, communications, candidates, golden, cadences, loading: false});
    } catch (error) {
      if (seq !== detailSeq.current) return;
      setDetail(d => ({...d, loading: false}));
      notify(error.message, 'error');
    }
  }, [api, notify]);

  useEffect(() => { if (activeId) loadDetail(activeId); }, [activeId, loadDetail]);

  // Golden Circle ------------------------------------------------------
  const setMode = value => { setModeState(value); try { localStorage.setItem(MODE_KEY, value); } catch { /* sem armazenamento */ } };
  const loadGolden = useCallback(async () => {
    const seq = ++goldenSeq.current;
    setGolden(g => ({...g, loading: true, error: ''}));
    try {
      const executivo = /^\d+$/.test(filters.executivo) ? filters.executivo : '';
      const data = await api.golden(trimestre, executivo);
      if (seq === goldenSeq.current) setGolden({data, loading: false, error: ''});
    } catch (error) {
      if (seq === goldenSeq.current) setGolden({data: null, loading: false, error: error.message});
    }
  }, [api, trimestre, filters.executivo]);
  useEffect(() => { if (mode === 'golden') loadGolden(); }, [mode, loadGolden]);

  const refreshActive = useCallback(() => {
    loadDetail(activeId, {quiet: true});
    loadList();
    if (mode === 'golden') loadGolden();
  }, [activeId, loadDetail, loadList, loadGolden, mode]);

  const setView = value => { setViewState(value); try { localStorage.setItem(VIEW_KEY, value); } catch { /* sem armazenamento */ } };
  const openLead = id => { setView('mesa'); setActiveId(id); };
  const markGolden = async () => {
    if (!detail.lead) return;
    const l = detail.lead;
    const exec = l.id_executivo || (boot.executivos.some(e => e.id === boot.user?.id) ? boot.user.id : null);
    if (!exec) { notify('Defina o responsável do lead antes de marcar como Golden Circle.', 'error'); return; }
    try {
      const r = await api.createGolden({id_executivo: exec, trimestre: boot.trimestre,
        contas: [{nome: l.empresa || l.nome, dominio: l.dominio || l.url_site || '', cnpj: l.cnpj || ''}]});
      if (r.recusadas.length) notify(r.recusadas[0].bloqueios.join(' '), 'error');
      else notify(`Lead marcado como Golden Circle ${boot.trimestre.replace('-', ' ')}.`);
      refreshActive();
    } catch (error) { notify(error.message, 'error'); }
  };

  // Navegação pelo teclado na fila: ↑/↓ (fora de campos de texto).
  useEffect(() => {
    const onKey = event => {
      if (view !== 'mesa' || dialog || /input|textarea|select/i.test(event.target.tagName) || !leads.length) return;
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      event.preventDefault();
      const index = leads.findIndex(l => l.id === activeId);
      const nextIndex = event.key === 'ArrowDown' ? Math.min(leads.length - 1, index + 1) : Math.max(0, index - 1);
      setActiveId(leads[nextIndex].id);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [leads, activeId, dialog, view]);

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

  const saveCompany = async body => {
    try { await api.updateCompany(activeId, body); notify('Dados da empresa salvos.'); setDialog(null); refreshActive(); return true; }
    catch (error) { notify(error.message, 'error'); return false; }
  };
  const goldenAction = (fn, done) => async (...args) => {
    try { await fn(...args); if (done) notify(done); loadGolden(); } catch (error) { notify(error.message, 'error'); }
  };

  const {lead} = detail;
  const activities = lead && <Activities key={lead.id} api={api} leadId={lead.id} contacts={detail.contacts} activities={detail.activities} onChanged={refreshActive} notify={notify}/>;
  const comms = lead && <Comms key={lead.id} api={api} lead={lead} contacts={detail.contacts} communications={detail.communications} cadences={detail.cadences} onChanged={refreshActive} notify={notify}/>;

  return (
    <div className="lv3">
      <header className="lv3-topbar">
        <div className="lv3-topbar__title">
          <h1>Leads</h1>
          <div className="lv3-viewswitch" role="tablist" aria-label="Visão">
            <button type="button" role="tab" aria-selected={view === 'mesa'} className={view === 'mesa' ? 'is-on' : ''} onClick={() => setView('mesa')}><Icon name="table-columns"/>Mesa</button>
            <button type="button" role="tab" aria-selected={view === 'operacao'} className={view === 'operacao' ? 'is-on' : ''} onClick={() => setView('operacao')}><Icon name="bolt"/>Operação</button>
          </div>
        </div>
        <div className="lv3-topbar__actions">
          <a className="lv3-btn lv3-btn--ghost lv3-btn--md" href={`${boot.legacyUrl}/analise`}><Icon name="chart-simple"/><span>Análise</span></a>
          <a className="lv3-btn lv3-btn--ghost lv3-btn--md" href={boot.legacyUrl} title="Importação em massa e kanban ficam no Leads atual"><Icon name="file-import"/><span>Importar</span></a>
          <Button variant="primary" icon="plus" onClick={() => setDialog({type: 'new'})}>Novo lead</Button>
        </div>
      </header>

      {view === 'operacao' ? (
        <Operacao boot={boot} api={api} executivo={filters.executivo} notify={notify} onOpenLead={openLead}
          setExecutivo={value => setFilters(f => ({...f, executivo: value}))}/>
      ) : (
      <div className={`lv3-grid ${wide ? 'lv3-grid--wide' : ''}`}>
        <Queue boot={boot} leads={leads} loading={listState.loading} error={listState.error} filters={filters} setFilters={setFilters}
          activeId={activeId} selected={selected} busy={bulkBusy}
          onOpen={setActiveId} onToggle={toggle} onToggleAll={toggleAll} onSelectAll={() => setSelected(new Set(leads.map(l => l.id)))} onClear={() => setSelected(new Set())} onReload={loadList}
          onBulk={(acao, valor) => runBulk(acao, [...selected], {valor})}
          onDisqualify={() => setDialog({type: 'disqualify', ids: [...selected]})}
          mode={mode} setMode={setMode}>
          <GoldenCircle boot={boot} data={golden.data} loading={golden.loading} error={golden.error}
            trimestre={trimestre} setTrimestre={setTrimestre} executivo={filters.executivo} activeLeadId={activeId}
            onOpen={setActiveId} onAdd={() => setDialog({type: 'golden'})} onReload={loadGolden}
            onStatus={goldenAction((id, status) => api.updateGolden(id, status))}
            onRemove={goldenAction(id => api.removeGolden(id), 'Conta retirada do Golden Circle.')}/>
        </Queue>

        <LeadPanel boot={boot} api={api} lead={lead} contacts={detail.contacts} candidates={detail.candidates} loading={detail.loading} notify={notify}
          golden={detail.golden} cadences={detail.cadences} onMarkGolden={markGolden}
          onChanged={refreshActive} onEdit={() => setDialog({type: 'edit'})}
          onEditCompany={() => setDialog({type: 'company'})} onConvert={() => setDialog({type: 'convert'})}
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
      )}

      {dialog?.type === 'disqualify' && <DisqualifyDialog boot={boot} count={dialog.ids.length} onCancel={() => setDialog(null)} onConfirm={confirmDisqualify}/>}
      {dialog?.type === 'edit' && lead && <EditDialog lead={lead} onCancel={() => setDialog(null)} onSave={saveEdit}/>}
      {dialog?.type === 'new' && <NewLeadDialog boot={boot} onCancel={() => setDialog(null)} onSave={createLead}/>}
      {dialog?.type === 'company' && lead && <CompanyDialog lead={lead} onCancel={() => setDialog(null)} onSave={saveCompany}/>}
      {dialog?.type === 'convert' && lead && (
        <ConvertDialog boot={boot} api={api} lead={lead} notify={notify} onCancel={() => setDialog(null)}
          onDone={() => { notify('Lead convertido em cliente.'); setDialog(null); refreshActive(); }}/>
      )}
      {dialog?.type === 'golden' && (
        <GoldenAddDialog boot={boot} api={api} trimestre={trimestre} executivo={filters.executivo} notify={notify} onCancel={() => setDialog(null)}
          onDone={r => {
            notify(`${r.criadas.length} ${r.criadas.length === 1 ? 'empresa adicionada' : 'empresas adicionadas'}${r.recusadas.length ? ` · ${r.recusadas.length} recusadas` : ''}.`);
            setDialog(null); loadGolden(); loadList();
          }}/>
      )}
      <Toasts items={toasts} onDismiss={id => setToasts(list => list.filter(t => t.id !== id))}/>
    </div>
  );
}
