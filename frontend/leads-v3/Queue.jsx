import React, {useEffect, useRef, useState} from 'react';
import {Button, Chip, Empty, Icon, decode, potencialTone, prettyName} from './ui.jsx';

const ORIGENS_FILTRO = [['site', 'Vieram do site'], ['adicionados', 'Adicionados pela equipe']];

/** Etapa, potencial e origem num menu: a coluna fica com uma linha só de filtros. */
function FilterMenu({boot, filters, setFilters}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const ativos = ['status', 'potencial', 'origem'].filter(k => filters[k]).length;
  useEffect(() => {
    if (!open) return undefined;
    const close = event => { if (event.type === 'keydown' ? event.key === 'Escape' : !ref.current?.contains(event.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close); };
  }, [open]);
  const set = key => event => setFilters(f => ({...f, [key]: event.target.value}));
  return (
    <div className="lv3-menu" ref={ref}>
      <button type="button" className={`lv3-filterbtn ${ativos ? 'is-on' : ''}`} onClick={() => setOpen(o => !o)} aria-expanded={open} aria-label="Mais filtros">
        <Icon name="sliders"/>{ativos ? <span className="lv3-filterbtn__count">{ativos}</span> : 'Filtros'}
      </button>
      {open && (
        <div className="lv3-menu__list lv3-filtermenu" role="dialog" aria-label="Filtros">
          <label className="lv3-field"><span className="lv3-field__label">Etapa</span>
            <select className="lv3-select" value={filters.status} onChange={set('status')}>
              <option value="">Todas</option>
              {boot.status.map(st => <option key={st.value} value={st.value}>{st.label}</option>)}
            </select></label>
          <label className="lv3-field"><span className="lv3-field__label">Potencial</span>
            <select className="lv3-select" value={filters.potencial} onChange={set('potencial')}>
              <option value="">Todos</option>
              {boot.potenciais.map(pt => <option key={pt.value} value={pt.value}>{pt.label}</option>)}
            </select></label>
          <label className="lv3-field"><span className="lv3-field__label">Origem</span>
            <select className="lv3-select" value={filters.origem || ''} onChange={set('origem')}>
              <option value="">Todas</option>
              {ORIGENS_FILTRO.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select></label>
          {ativos > 0 && (
            <button type="button" className="lv3-link" onClick={() => setFilters(f => ({...f, status: '', potencial: '', origem: ''}))}>Limpar filtros</button>
          )}
        </div>
      )}
    </div>
  );
}

/** Filtros ativos como etiquetas removíveis (só aparece quando há algum). */
function ActiveFilters({boot, filters, setFilters}) {
  const tags = [
    filters.status && ['status', boot.status.find(x => x.value === filters.status)?.label || filters.status],
    filters.potencial && ['potencial', `Potencial ${boot.potenciais.find(x => x.value === filters.potencial)?.label || filters.potencial}`],
    filters.origem && ['origem', ORIGENS_FILTRO.find(([v]) => v === filters.origem)?.[1] || filters.origem],
  ].filter(Boolean);
  if (!tags.length) return null;
  return (
    <div className="lv3-activefilters">
      {tags.map(([k, label]) => (
        <button key={k} type="button" className="lv3-activefilter" onClick={() => setFilters(f => ({...f, [k]: ''}))} aria-label={`Remover filtro ${label}`}>
          {label}<Icon name="xmark"/>
        </button>
      ))}
    </div>
  );
}

/** Barra que substitui o cabeçalho da fila enquanto há leads selecionados. */
function BulkBar({boot, count, total, busy, onAction, onDisqualify, onClear, onSelectAll}) {
  const pick = acao => event => {
    const valor = event.target.value;
    event.target.value = '';
    if (valor !== '') onAction(acao, valor);
  };
  return (
    <div className="lv3-bulk" role="toolbar" aria-label="Ações em massa">
      <div className="lv3-bulk__count">
        <strong>{count}</strong> {count === 1 ? 'selecionado' : 'selecionados'}
        {count < total && <button type="button" className="lv3-link" onClick={onSelectAll} disabled={busy}>Selecionar os {total}</button>}
        <button type="button" className="lv3-link" onClick={onClear} disabled={busy}>Limpar</button>
      </div>
      <div className="lv3-bulk__actions">
        <select className="lv3-select lv3-select--sm" defaultValue="" onChange={pick('status')} disabled={busy} aria-label="Mudar etapa dos selecionados">
          <option value="" disabled>Mudar etapa…</option>
          {boot.status.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <select className="lv3-select lv3-select--sm" defaultValue="" onChange={pick('potencial')} disabled={busy} aria-label="Mudar potencial dos selecionados">
          <option value="" disabled>Potencial…</option>
          {boot.potenciais.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
        </select>
        <select className="lv3-select lv3-select--sm" defaultValue="" onChange={pick('responsavel')} disabled={busy} aria-label="Atribuir responsável aos selecionados">
          <option value="" disabled>Responsável…</option>
          <option value="sem">Sem responsável</option>
          {boot.executivos.map(e => <option key={e.id} value={e.id}>{e.nome}</option>)}
        </select>
        <Button variant="danger" size="sm" icon="ban" onClick={onDisqualify} disabled={busy}>Desqualificar</Button>
      </div>
    </div>
  );
}

// De onde o lead veio: site (formulário) ou adicionado pela equipe.
const ORIGEM = {
  site: {label: 'Site', tone: 'site', title: 'Veio de formulário do site ou landing page'},
  import: {label: 'Importado', tone: 'added', title: 'Adicionado por importação em massa'},
  manual: {label: 'Manual', tone: 'added', title: 'Cadastrado pela equipe'},
  indicacao: {label: 'Indicação', tone: 'added', title: 'Veio por indicação'},
  evento: {label: 'Evento', tone: 'added', title: 'Veio de evento'},
  outro: {label: 'Outro', tone: 'added', title: 'Outra origem'},
};

function QueueItem({lead, statusLabel, active, selected, onOpen, onToggle}) {
  const origem = ORIGEM[lead.fonte];
  const parado = lead.dias_sem_atividade != null && lead.dias_sem_atividade >= 7;
  return (
    <li className={`lv3-qitem ${active ? 'is-active' : ''} ${selected ? 'is-selected' : ''}`}>
      {/* O clique fica só no input: no <label>, a ativação repassa o clique ao input e o toggle rodaria duas vezes. */}
      <label className="lv3-qitem__check">
        <input type="checkbox" checked={selected} readOnly aria-label={`Selecionar ${decode(lead.nome_lead)}`}
          onClick={event => onToggle(lead.id, event.shiftKey)}/>
      </label>
      <button type="button" className="lv3-qitem__main" onClick={() => onOpen(lead.id)} aria-current={active ? 'true' : undefined}>
        <span className="lv3-qitem__top">
          <span className="lv3-qitem__name">{lead.golden && <span className="lv3-gc-dot" title="Golden Circle do trimestre"/>}{decode(lead.nome_lead) || 'Sem nome'}</span>
          <Chip tone={potencialTone(lead.potencial)}>{lead.potencial === 'medio' ? 'Médio' : (lead.potencial || '—').replace(/^./, c => c.toUpperCase())}</Chip>
        </span>
        <span className="lv3-qitem__meta">
          {origem && <span className={`lv3-origin lv3-origin--${origem.tone}`} title={origem.title}>{origem.label}</span>}
          <span>{statusLabel}</span>
          <span aria-hidden="true">·</span>
          <span>{lead.qtd_contatos ? `${lead.qtd_contatos} ${lead.qtd_contatos === 1 ? 'contato' : 'contatos'}` : 'sem contatos'}</span>
          {lead.dias_sem_atividade != null && (
            <span className={parado ? 'lv3-qitem__stale' : ''}>· {lead.dias_sem_atividade}d sem atividade</span>
          )}
        </span>
        {lead.contato_principal_nome && lead.contato_principal_nome !== lead.nome_lead && (
          <span className="lv3-qitem__sub"><Icon name="user"/>{prettyName(lead.contato_principal_nome)}</span>
        )}
      </button>
    </li>
  );
}

export function Queue({boot, leads, loading, error, filters, setFilters, activeId, selected, busy,
  onOpen, onToggle, onToggleAll, onSelectAll, onBulk, onDisqualify, onClear, onReload, mode, setMode, children}) {
  const statusLabel = Object.fromEntries(boot.status.map(s => [s.value, s.label]));
  const allSelected = leads.length > 0 && leads.every(l => selected.has(l.id));
  const someSelected = selected.size > 0;
  const set = key => event => setFilters(f => ({...f, [key]: event.target.value}));

  return (
    <aside className="lv3-col lv3-queue" aria-label="Fila de leads">
      <div className="lv3-tabs lv3-tabs--queue" role="tablist">
        <button type="button" role="tab" aria-selected={mode === 'fila'} className={mode === 'fila' ? 'is-on' : ''} onClick={() => setMode('fila')}>
          <Icon name="inbox"/>Fila
        </button>
        <button type="button" role="tab" aria-selected={mode === 'golden'} className={mode === 'golden' ? 'is-on' : ''} onClick={() => setMode('golden')}>
          <Icon name="bullseye"/>Golden Circle
        </button>
      </div>
      <div className="lv3-queue__filters lv3-queue__filters--row">
        {mode === 'fila' && (
          <div className="lv3-search lv3-search--sm">
            <Icon name="magnifying-glass"/>
            <input type="search" placeholder="Buscar" value={filters.q} onChange={set('q')} aria-label="Buscar empresa, nome ou e-mail"/>
          </div>
        )}
        <label className={`lv3-pill-select lv3-pill-select--lg lv3-queue__owner ${filters.executivo ? 'is-set' : ''}`} title="Responsável">
          <Icon name="user"/>
          <select value={filters.executivo} onChange={set('executivo')} aria-label="Responsável">
            <option value="">Todos</option>
            <option value="sem">Sem responsável</option>
            {boot.executivos.map(e => <option key={e.id} value={String(e.id)}>{e.nome}</option>)}
          </select>
        </label>
        {mode === 'fila' && <FilterMenu boot={boot} filters={filters} setFilters={setFilters}/>}
      </div>
      {mode === 'fila' && <ActiveFilters boot={boot} filters={filters} setFilters={setFilters}/>}

      {mode === 'golden' ? children : <>
      {someSelected ? (
        <BulkBar boot={boot} count={selected.size} total={leads.length} onSelectAll={onSelectAll} busy={busy} onAction={onBulk} onDisqualify={onDisqualify} onClear={onClear}/>
      ) : (
        <div className="lv3-queue__head">
          <label className="lv3-queue__all">
            <input type="checkbox" checked={allSelected} onChange={onToggleAll} disabled={!leads.length} aria-label="Selecionar todos"/>
            <span>{loading ? 'Carregando…' : `${leads.length} ${leads.length === 1 ? 'lead' : 'leads'}`}</span>
          </label>
          <button type="button" className="lv3-iconbtn" onClick={onReload} aria-label="Atualizar lista" title="Atualizar"><Icon name="rotate-right"/></button>
        </div>
      )}

      {error ? (
        <Empty icon="triangle-exclamation" title="Não foi possível carregar">
          {error} <button type="button" className="lv3-link" onClick={onReload}>Tentar de novo</button>
        </Empty>
      ) : !loading && !leads.length ? (
        <Empty title="Nenhum lead aqui">Mude os filtros ou cadastre um lead novo.</Empty>
      ) : (
        <ul className="lv3-queue__list">
          {leads.map(lead => (
            <QueueItem key={lead.id} lead={lead} statusLabel={statusLabel[lead.status] || lead.status}
              active={lead.id === activeId} selected={selected.has(lead.id)} onOpen={onOpen} onToggle={onToggle}/>
          ))}
        </ul>
      )}
      </>}
    </aside>
  );
}
