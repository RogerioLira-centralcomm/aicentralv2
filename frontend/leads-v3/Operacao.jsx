import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {Button, Empty, Field, Icon, decode, formatDate, gmailUrl, linkedinSearchUrl, prettyName as pretty, todayLocal, whatsappUrl} from './ui.jsx';
import {FocusEditor, GoldenTarget, MarketContext} from './Focus.jsx';

const CANAL = {
  email: {label: 'E-mail', icon: 'envelope'},
  whatsapp: {label: 'WhatsApp', icon: 'comment'},
  linkedin: {label: 'LinkedIn', icon: 'user-group'},
  telefone: {label: 'Ligação', icon: 'phone'},
};
const TIPO_TAREFA = {ligacao: 'Ligação', whatsapp: 'WhatsApp', email_enviado: 'E-mail', reuniao: 'Reunião', follow_up: 'Follow-up',
  apresentacao: 'Apresentação', proposta_enviada: 'Proposta', nota: 'Nota'};

function atraso(data) {
  if (!data) return '';
  const dia = String(data).slice(0, 10);
  const hoje = todayLocal();
  if (dia >= hoje) return 'hoje';
  const dias = Math.round((new Date(`${hoje}T00:00`) - new Date(`${dia}T00:00`)) / 86400000);
  return dias === 1 ? 'atrasado 1 dia' : `atrasado ${dias} dias`;
}

const canalDaMensagem = passo => (passo?.canal === 'linkedin' ? (passo.acao === 'conectar' ? 'linkedin_conexao' : 'linkedin') : passo?.canal || 'email');

/** Composer do passo: etapa do funil, objetivo, mensagem da IA e envio assistido. */
function StepComposer({api, item, notify, onDone}) {
  const passo = item.passo || {};
  const canal = canalDaMensagem(passo);
  const [etapa, setEtapa] = useState(item.passo_atual < Math.ceil((item.total || 2) / 2) ? 'topo' : 'meio');
  const [objetivo, setObjetivo] = useState(passo.objetivo || passo.titulo || '');
  const [assunto, setAssunto] = useState('');
  const [texto, setTexto] = useState('');
  const [busy, setBusy] = useState('');
  const nome = pretty(item.contato_nome);
  const empresa = decode(item.empresa || item.lead_nome);
  const corpoCompleto = (assunto ? `Assunto: ${assunto}\n\n` : '') + texto;

  const escrever = async () => {
    setBusy('ia');
    try {
      const r = await api.writeMessage({id_contato: item.id_contato, canal, etapa, objetivo});
      setTexto(r.texto || '');
      setAssunto(r.assunto || '');
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const copiar = async () => {
    try { await navigator.clipboard.writeText(assunto ? `${assunto}\n\n${texto}` : texto); notify('Texto copiado.'); return true; }
    catch { notify('Não foi possível copiar.', 'error'); return false; }
  };
  const abrir = async () => {
    if (passo.canal === 'email') {
      if (!item.email) return notify('Esta pessoa não tem e-mail. Use "Achar e-mail" na mesa.', 'error');
      window.open(gmailUrl(item.email, assunto, texto), '_blank', 'noopener');
    } else if (passo.canal === 'whatsapp') {
      const url = whatsappUrl(item.telefone, texto);
      if (!url) return notify('Esta pessoa não tem telefone.', 'error');
      window.open(url, '_blank', 'noopener');
    } else if (passo.canal === 'linkedin') {
      if (texto) await copiar();
      window.open(item.linkedin_url || linkedinSearchUrl(nome, empresa), '_blank', 'noopener');
    } else if (passo.canal === 'telefone') {
      if (!item.telefone) return notify('Esta pessoa não tem telefone.', 'error');
      window.location.href = `tel:${String(item.telefone).replace(/[^\d+]/g, '')}`;
    }
  };
  const acao = (nome_acao, pedirNota) => async () => {
    let nota = '';
    if (pedirNota) {
      nota = window.prompt(pedirNota) ?? null;
      if (nota === null) return;
    }
    setBusy(nome_acao);
    try {
      if (nome_acao === 'feito' && texto && passo.canal !== 'telefone') {
        // Guarda o texto enviado no histórico de comunicações do lead (mesma tabela do Leads v2).
        await api.saveCommunication(item.id_lead, {tipo_canal: passo.canal, objetivo, texto: corpoCompleto, status: 'enviado',
          id_contato: item.id_contato, gerado_por_ia: true, tamanho: 'medio', tom: 'cordial'}).catch(() => null);
      }
      await api.stepAction(item.id, nome_acao, nota || (nome_acao === 'feito' && texto ? texto.slice(0, 140) : ''));
      notify({feito: 'Passo feito. Próximo agendado.', respondeu: 'Resposta registrada; cadência encerrada.', pular: 'Passo pulado.', pausar: 'Cadência pausada.'}[nome_acao]);
      onDone();
    } catch (error) { notify(error.message, 'error'); setBusy(''); }
  };

  const info = CANAL[passo.canal] || CANAL.email;
  return (
    <div className="lv3-op__composer">
      <header className="lv3-op__person">
        <div className="lv3-person__avatar" aria-hidden="true">{nome.slice(0, 1).toUpperCase()}</div>
        <div>
          <h2>{nome}{item.golden && <span className="lv3-gc-badge">Golden Circle</span>}</h2>
          <p>{[pretty(item.cargo), empresa].filter(Boolean).join(' · ')}</p>
          <p className="lv3-op__links">
            {item.email && <a href={`mailto:${item.email}`}><Icon name="envelope"/>{String(item.email).toLowerCase()}</a>}
            {item.telefone && <a href={whatsappUrl(item.telefone)} target="_blank" rel="noopener noreferrer"><Icon name="phone"/>{item.telefone}</a>}
            <a href={item.linkedin_url || linkedinSearchUrl(nome, empresa)} target="_blank" rel="noopener noreferrer"><Icon name="user-group"/>{item.linkedin_url ? 'LinkedIn' : 'Achar no LinkedIn'}</a>
          </p>
        </div>
      </header>

      <div className="lv3-op__step">
        <span className="lv3-op__stepicon"><Icon name={info.icon}/></span>
        <div>
          <strong>{passo.titulo}</strong>
          <span className="lv3-muted">{item.cadencia} · passo {item.passo_atual + 1} de {item.total} · {atraso(item.proxima_em)}</span>
        </div>
      </div>

        <div className="lv3-card lv3-form">
          <div className="lv3-form__grid">
            <Field label="Etapa do funil">
              <div className="lv3-segmented" role="radiogroup" aria-label="Etapa do funil">
                {[['topo', 'Topo · interesse'], ['meio', 'Meio · aprofundar']].map(([v, l]) => (
                  <button key={v} type="button" role="radio" aria-checked={etapa === v} className={etapa === v ? 'is-on' : ''} onClick={() => setEtapa(v)}>{l}</button>
                ))}
              </div>
            </Field>
            <Field label="Canal"><div className="lv3-op__channel"><Icon name={info.icon}/>{canal === 'linkedin_conexao' ? 'Convite de conexão (até 300 caracteres)' : info.label}</div></Field>
          </div>
          <Field label="Objetivo deste toque" wide>
            <textarea className="lv3-input lv3-textarea" rows={2} value={objetivo} onChange={e => setObjetivo(e.target.value)}/>
          </Field>
          <Button variant="ai" icon="wand-magic-sparkles" className="lv3-btn--block" onClick={escrever} disabled={!!busy}>
            {busy === 'ia' ? 'Escrevendo com o contexto da empresa…' : texto ? 'Escrever outra versão' : 'Escrever mensagem personalizada'}
          </Button>
          {texto && (
            <>
              {passo.canal === 'email' && (
                <Field label="Assunto" wide><input className="lv3-input" value={assunto} onChange={e => setAssunto(e.target.value)}/></Field>
              )}
              <Field label={passo.canal === 'telefone' ? 'Roteiro' : 'Mensagem (editável)'} wide>
                <textarea className="lv3-input lv3-textarea lv3-textarea--tall" value={texto} onChange={e => setTexto(e.target.value)}/>
              </Field>
              {canal === 'linkedin_conexao' && <p className={`lv3-muted ${texto.length > 300 ? 'lv3-danger' : ''}`}>{texto.length}/300 caracteres</p>}
            </>
          )}
        </div>

      <div className="lv3-op__actions">
        <Button variant="primary" icon={passo.canal === 'linkedin' ? 'arrow-up-right-from-square' : passo.canal === 'telefone' ? 'phone' : 'paper-plane'} onClick={abrir}>
          {{email: 'Abrir no Gmail', whatsapp: 'Abrir no WhatsApp', linkedin: texto ? 'Copiar e abrir LinkedIn' : 'Abrir LinkedIn', telefone: 'Ligar'}[passo.canal] || 'Abrir'}
        </Button>
        {texto && <Button icon="copy" onClick={copiar}>Copiar</Button>}
        {passo.canal === 'email' && item.email && texto && (
          <a className="lv3-btn lv3-btn--ghost lv3-btn--md" href={`mailto:${item.email}?subject=${encodeURIComponent(assunto)}&body=${encodeURIComponent(texto)}`}><Icon name="envelope"/><span>Outro app de e-mail</span></a>
        )}
      </div>
      <div className="lv3-op__actions lv3-op__actions--done">
        <Button variant="primary" icon="check" onClick={acao('feito')} disabled={!!busy}>{busy === 'feito' ? 'Registrando…' : 'Marcar como feito'}</Button>
        <Button icon="reply" onClick={acao('respondeu', 'O que a pessoa respondeu? (opcional)')} disabled={!!busy}>Respondeu</Button>
        <Button variant="ghost" icon="forward" onClick={acao('pular')} disabled={!!busy}>Pular passo</Button>
        <Button variant="ghost" icon="pause" onClick={acao('pausar', 'Motivo da pausa (opcional)')} disabled={!!busy}>Pausar</Button>
      </div>
    </div>
  );
}

function TaskPanel({api, item, notify, onDone, onOpenLead}) {
  const [busy, setBusy] = useState(false);
  const concluir = async () => {
    setBusy(true);
    try { await api.toggleActivity(item.id, true); notify('Tarefa concluída.'); onDone(); }
    catch (error) { notify(error.message, 'error'); setBusy(false); }
  };
  return (
    <div className="lv3-op__composer">
      <header className="lv3-op__person">
        <div className="lv3-person__avatar" aria-hidden="true"><Icon name="list-check"/></div>
        <div>
          <h2>{TIPO_TAREFA[item.tipo] || 'Tarefa'}{item.golden && <span className="lv3-gc-badge">Golden Circle</span>}</h2>
          <p>{[decode(item.empresa), pretty(item.contato_nome)].filter(Boolean).join(' · ')} · prazo {formatDate(item.data_prazo)} ({atraso(item.data_prazo)})</p>
        </div>
      </header>
      <div className="lv3-card lv3-op__task">{decode(item.descricao)}</div>
      <div className="lv3-op__actions">
        <Button variant="primary" icon="check" onClick={concluir} disabled={busy}>{busy ? 'Concluindo…' : 'Concluir tarefa'}</Button>
        <Button icon="arrow-right" onClick={() => onOpenLead(item.id_lead)}>Abrir na mesa</Button>
      </div>
    </div>
  );
}

function CompanyPanel({api, leadId, notify, onOpenLead}) {
  const [lead, setLead] = useState(null);
  const [conta, setConta] = useState(null);
  const [contacts, setContacts] = useState([]);
  const load = useCallback(async () => {
    try {
      const [l, g, c] = await Promise.all([api.lead(leadId), api.leadGolden(leadId).catch(() => null), api.contacts(leadId).catch(() => [])]);
      setLead(l); setConta(g); setContacts(c);
    } catch (error) { notify(error.message, 'error'); }
  }, [api, leadId, notify]);
  useEffect(() => { setLead(null); load(); }, [load]);
  if (!lead) return <div className="lv3-skeleton"/>;
  const nome = decode(lead.empresa || lead.nome);
  return (
    <div className="lv3-op__company">
      <header className="lv3-op__companyhead">
        <h3>{nome}</h3>
        <div className="lv3-section__tools">
          <a className="lv3-iconbtn" href={linkedinSearchUrl(nome)} target="_blank" rel="noopener noreferrer" title="Empresa no LinkedIn"><Icon name="user-group"/></a>
          <button type="button" className="lv3-iconbtn" title="Abrir na mesa" onClick={() => onOpenLead(leadId)}><Icon name="arrow-right"/></button>
        </div>
      </header>
      {conta && (
        <section className="lv3-op__block">
          <h4><Icon name="bullseye"/>Alvo Golden Circle</h4>
          <GoldenTarget api={api} conta={conta} contacts={contacts} notify={notify} onChanged={load}/>
        </section>
      )}
      <section className="lv3-op__block">
        <h4><Icon name="crosshairs"/>Foco: canais e conteúdo</h4>
        <FocusEditor api={api} lead={lead} notify={notify} onChanged={load} compact/>
      </section>
      <section className="lv3-op__block">
        <h4><Icon name="newspaper"/>Contexto de mercado</h4>
        <MarketContext api={api} lead={lead} notify={notify} onChanged={load}/>
      </section>
    </div>
  );
}

export function Operacao({boot, api, executivo, setExecutivo, notify, onOpenLead}) {
  const [data, setData] = useState({passos: [], tarefas: []});
  const [state, setState] = useState({loading: true, error: ''});
  const [selected, setSelected] = useState(null); // {tipo, id}

  const load = useCallback(async () => {
    setState(s => ({...s, loading: true, error: ''}));
    try {
      const d = await api.operation(/^\d+$/.test(executivo) ? executivo : '');
      setData(d);
      setState({loading: false, error: ''});
      setSelected(sel => {
        const existe = sel && (sel.tipo === 'passo' ? d.passos : d.tarefas).some(i => i.id === sel.id);
        if (existe) return sel;
        if (d.passos[0]) return {tipo: 'passo', id: d.passos[0].id};
        if (d.tarefas[0]) return {tipo: 'tarefa', id: d.tarefas[0].id};
        return null;
      });
    } catch (error) { setState({loading: false, error: error.message}); }
  }, [api, executivo]);
  useEffect(() => { load(); }, [load]);

  const item = useMemo(() => {
    if (!selected) return null;
    return (selected.tipo === 'passo' ? data.passos : data.tarefas).find(i => i.id === selected.id) || null;
  }, [selected, data]);

  const total = data.passos.length + data.tarefas.length;
  return (
    <div className="lv3-op">
      <aside className="lv3-col lv3-op__list" aria-label="Pendências">
        <div className="lv3-op__filters">
          <select className="lv3-select" value={executivo} onChange={e => setExecutivo(e.target.value)} aria-label="Executivo">
            <option value="">Todos os executivos</option>
            {boot.executivos.map(e => <option key={e.id} value={String(e.id)}>{e.nome}</option>)}
          </select>
          <button type="button" className="lv3-iconbtn" onClick={load} aria-label="Atualizar" title="Atualizar"><Icon name="rotate-right"/></button>
        </div>
        <div className="lv3-op__summary">{state.loading ? 'Carregando…' : `${total} ${total === 1 ? 'pendência' : 'pendências'} até hoje`}</div>
        {state.error ? (
          <Empty icon="triangle-exclamation" title="Não foi possível carregar">{state.error}</Empty>
        ) : !state.loading && !total ? (
          <Empty icon="mug-hot" title="Nada pendente hoje">Inscreva as pessoas das contas em cadências na mesa (Pessoas › Iniciar cadência).</Empty>
        ) : (
          <div className="lv3-op__scroll">
            {data.passos.length > 0 && <h3 className="lv3-op__group">Cadências <span className="lv3-count">{data.passos.length}</span></h3>}
            <ul className="lv3-op__items">
              {data.passos.map(p => {
                const info = CANAL[p.passo?.canal] || CANAL.email;
                const late = atraso(p.proxima_em);
                return (
                  <li key={`p${p.id}`}>
                    <button type="button" className={`lv3-op__item ${selected?.tipo === 'passo' && selected.id === p.id ? 'is-active' : ''}`} onClick={() => setSelected({tipo: 'passo', id: p.id})}>
                      <span className="lv3-op__itemicon"><Icon name={info.icon}/></span>
                      <span className="lv3-op__itembody">
                        <span className="lv3-op__itemtop"><strong>{pretty(p.contato_nome)}</strong>{p.golden && <span className="lv3-gc-dot" title="Golden Circle"/>}</span>
                        <span className="lv3-op__itemsub">{decode(p.empresa || p.lead_nome)} · {p.passo?.titulo}</span>
                        <span className={`lv3-op__itemdue ${late !== 'hoje' ? 'is-late' : ''}`}>{late} · passo {p.passo_atual + 1}/{p.total}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {data.tarefas.length > 0 && <h3 className="lv3-op__group">Tarefas <span className="lv3-count">{data.tarefas.length}</span></h3>}
            <ul className="lv3-op__items">
              {data.tarefas.map(t => (
                <li key={`t${t.id}`}>
                  <button type="button" className={`lv3-op__item ${selected?.tipo === 'tarefa' && selected.id === t.id ? 'is-active' : ''}`} onClick={() => setSelected({tipo: 'tarefa', id: t.id})}>
                    <span className="lv3-op__itemicon"><Icon name="list-check"/></span>
                    <span className="lv3-op__itembody">
                      <span className="lv3-op__itemtop"><strong>{TIPO_TAREFA[t.tipo] || 'Tarefa'} · {decode(t.empresa)}</strong>{t.golden && <span className="lv3-gc-dot" title="Golden Circle"/>}</span>
                      <span className="lv3-op__itemsub">{decode(t.descricao)}</span>
                      <span className={`lv3-op__itemdue ${atraso(t.data_prazo) !== 'hoje' ? 'is-late' : ''}`}>{atraso(t.data_prazo)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>

      <section className="lv3-col lv3-op__main" aria-label="Pendência selecionada">
        {item ? (
          selected.tipo === 'passo'
            ? <StepComposer key={`p${item.id}-${item.passo_atual}`} api={api} item={item} notify={notify} onDone={load}/>
            : <TaskPanel key={`t${item.id}`} api={api} item={item} notify={notify} onDone={load} onOpenLead={onOpenLead}/>
        ) : <Empty icon="hand-pointer" title="Escolha uma pendência"/>}
      </section>

      <aside className="lv3-col lv3-op__side" aria-label="Empresa">
        {item ? <CompanyPanel key={item.id_lead} api={api} leadId={item.id_lead} notify={notify} onOpenLead={onOpenLead}/> : <Empty icon="building" title="Sem empresa selecionada"/>}
      </aside>
    </div>
  );
}
