import React, {useCallback, useEffect, useState} from 'react';
import {Button, Empty, Field, Icon, Modal, MoreMenu} from './ui.jsx';

// Fluxos de cadência comuns a todos os executivos. O estágio diz para quem o fluxo serve; a etapa
// de cada passo (topo, meio, fundo) é o que a IA usa para escrever a mensagem daquele toque.
export const ESTAGIOS = [
  ['novo', 'Pessoa nova', 'Ainda sem conversa'],
  ['em_conversa', 'Já conversou', 'Já falou com a gente'],
  ['reativacao', 'Reativar', 'Conta parada'],
  ['inbound', 'Veio do site', 'Pediu contato'],
];
export const ESTAGIO_LABEL = Object.fromEntries(ESTAGIOS.map(([v, l]) => [v, l]));
export const ETAPAS = [
  ['topo', 'Topo', 'Puxar conversa com um fato; sem pedir reunião'],
  ['meio', 'Meio', 'Aprofundar o desafio com conteúdo sob medida; 15 minutos sobre um ponto'],
  ['fundo', 'Fundo', 'Próximo passo concreto, depois de interesse ou no último toque'],
];
const CANAIS = [['email', 'E-mail', 'envelope'], ['linkedin', 'LinkedIn', 'user-group'], ['whatsapp', 'WhatsApp', 'comment'], ['telefone', 'Ligação', 'phone']];
const CANAL = Object.fromEntries(CANAIS.map(([v, l, i]) => [v, {label: l, icon: i}]));
const passoVazio = dia => ({dia, canal: 'email', acao: 'enviar', etapa: 'topo', titulo: '', objetivo: ''});

/** Sugestão quando o executivo não escolhe (a mesma regra do servidor): fluxo de pessoa nova da área da pessoa. */
export function sugerirFluxo(fluxos, papel) {
  const novos = fluxos.filter(f => f.estagio === 'novo');
  return novos.find(f => (f.papeis || []).includes(papel)) || novos.find(f => f.chave === 'marketing_midia') || novos[0] || fluxos[0] || null;
}

/** Escolha do fluxo ao iniciar a cadência: agrupado por estágio, com a sugestão pela área marcada. */
export function FlowSelect({fluxos, value, onChange, sugerido, disabled, className = ''}) {
  return (
    <select className={`lv3-select lv3-select--sm ${className}`} value={value || ''} onChange={event => onChange(event.target.value)} disabled={disabled} aria-label="Fluxo da cadência">
      {ESTAGIOS.map(([estagio, label]) => {
        const lista = fluxos.filter(f => f.estagio === estagio);
        return lista.length ? (
          <optgroup key={estagio} label={label}>
            {lista.map(f => <option key={f.id} value={f.id}>{f.nome}{sugerido && f.id === sugerido.id ? ' (sugerido)' : ''} · {f.total} passos</option>)}
          </optgroup>
        ) : null;
      })}
    </select>
  );
}

function Trilha({passos}) {
  return (
    <ol className="lv3-flow__steps">
      {passos.map((p, i) => (
        <li key={i} className={`is-${p.etapa}`} title={p.objetivo || p.titulo}>
          <span className="lv3-flow__day">D{p.dia}</span>
          <Icon name={(CANAL[p.canal] || {}).icon || 'circle'}/>
          <span className="lv3-flow__title">{p.titulo}</span>
          <span className={`lv3-funnel lv3-funnel--${p.etapa}`}>{p.etapa}</span>
        </li>
      ))}
    </ol>
  );
}

function FlowEditor({boot, inicial, onClose, onSave}) {
  const [form, setForm] = useState(() => inicial ? {...inicial, papeis: inicial.papeis || [], passos: (inicial.passos || []).map(p => ({...p}))}
    : {nome: '', descricao: '', estagio: 'novo', papeis: [], passos: [passoVazio(0)]});
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState('');
  const set = (campo, valor) => setForm(f => ({...f, [campo]: valor}));
  const setPasso = (i, campo, valor) => setForm(f => ({...f, passos: f.passos.map((p, j) => j === i ? {...p, [campo]: valor} : p)}));
  const mover = (i, d) => setForm(f => {
    const passos = [...f.passos];
    [passos[i], passos[i + d]] = [passos[i + d], passos[i]];
    return {...f, passos};
  });
  const papel = valor => set('papeis', form.papeis.includes(valor) ? form.papeis.filter(p => p !== valor) : [...form.papeis, valor]);
  const etapas = form.passos.reduce((acc, p) => ({...acc, [p.etapa]: (acc[p.etapa] || 0) + 1}), {});

  const salvar = async event => {
    event.preventDefault();
    setSaving(true); setErro('');
    try {
      await onSave({nome: form.nome, descricao: form.descricao, estagio: form.estagio, papeis: form.papeis,
        passos: form.passos.map(p => ({...p, dia: Number(p.dia) || 0}))});
    } catch (error) { setErro(error.message); setSaving(false); }
  };

  return (
    <Modal title={inicial?.id ? `Editar fluxo · ${inicial.nome}` : 'Novo fluxo'} onClose={onClose} width={860}
      footer={<>
        {erro && <span className="lv3-flow__error" role="alert">{erro}</span>}
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="primary" type="submit" form="lv3-flow-form" disabled={saving}>{saving ? 'Salvando…' : 'Salvar fluxo'}</Button>
      </>}>
      <form id="lv3-flow-form" className="lv3-flow-form" onSubmit={salvar}>
        <div className="lv3-form__grid">
          <Field label="Nome"><input className="lv3-input" value={form.nome} onChange={e => set('nome', e.target.value)} maxLength={80} placeholder="Ex.: Pós-evento" required/></Field>
          <Field label="Para quem (estágio)">
            <select className="lv3-select" value={form.estagio} onChange={e => set('estagio', e.target.value)}>
              {ESTAGIOS.map(([v, l, d]) => <option key={v} value={v}>{l} · {d}</option>)}
            </select>
          </Field>
          <Field label="Quando usar" wide><input className="lv3-input" value={form.descricao || ''} onChange={e => set('descricao', e.target.value)} maxLength={300} placeholder="Ex.: Para quem esteve no nosso estande; começa no meio do funil"/></Field>
        </div>
        <fieldset className="lv3-flow-form__roles">
          <legend>Áreas sugeridas <small>(o fluxo aparece como sugestão para pessoas dessas áreas)</small></legend>
          {(boot.papeis || []).map(({value, label}) => (
            <label key={value} className={`lv3-chip-toggle ${form.papeis.includes(value) ? 'is-on' : ''}`}>
              <input type="checkbox" checked={form.papeis.includes(value)} onChange={() => papel(value)}/>{label}
            </label>
          ))}
        </fieldset>

        <div className="lv3-flow-form__head">
          <strong>Passos</strong>
          <span className="lv3-muted">{ETAPAS.filter(([v]) => etapas[v]).map(([v, l]) => `${etapas[v]} de ${l.toLowerCase()}`).join(' · ')}</span>
        </div>
        <ol className="lv3-flow-form__steps">
          {form.passos.map((p, i) => (
            <li key={i} className={`is-${p.etapa}`}>
              <div className="lv3-flow-form__row">
                <span className="lv3-flow-form__n">{i + 1}</span>
                <label className="lv3-flow-form__day">Dia<input className="lv3-input lv3-input--sm" type="number" min="0" max="120" value={p.dia} onChange={e => setPasso(i, 'dia', e.target.value)} aria-label={`Dia do passo ${i + 1}`}/></label>
                <select className="lv3-select lv3-select--sm" value={p.canal} onChange={e => setPasso(i, 'canal', e.target.value)} aria-label={`Canal do passo ${i + 1}`}>
                  {CANAIS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
                {p.canal === 'linkedin' && (
                  <label className="lv3-flow-form__check"><input type="checkbox" checked={p.acao === 'conectar'} onChange={e => setPasso(i, 'acao', e.target.checked ? 'conectar' : 'enviar')}/>convite</label>
                )}
                <div className="lv3-segmented lv3-segmented--sm" role="radiogroup" aria-label={`Etapa do passo ${i + 1}`}>
                  {ETAPAS.map(([v, l, d]) => (
                    <button key={v} type="button" role="radio" aria-checked={p.etapa === v} className={p.etapa === v ? 'is-on' : ''} title={d} onClick={() => setPasso(i, 'etapa', v)}>{l}</button>
                  ))}
                </div>
                <span className="lv3-flow-form__tools">
                  <button type="button" className="lv3-iconbtn" disabled={i === 0} onClick={() => mover(i, -1)} aria-label="Subir passo"><Icon name="arrow-up"/></button>
                  <button type="button" className="lv3-iconbtn" disabled={i === form.passos.length - 1} onClick={() => mover(i, 1)} aria-label="Descer passo"><Icon name="arrow-down"/></button>
                  <button type="button" className="lv3-iconbtn" disabled={form.passos.length === 1} onClick={() => set('passos', form.passos.filter((_, j) => j !== i))} aria-label="Remover passo"><Icon name="trash-can"/></button>
                </span>
              </div>
              <input className="lv3-input lv3-input--sm" value={p.titulo} onChange={e => setPasso(i, 'titulo', e.target.value)} maxLength={80} placeholder="Título (ex.: Diagnóstico curto)" aria-label={`Título do passo ${i + 1}`} required/>
              <textarea className="lv3-input lv3-input--sm" rows={2} value={p.objetivo} onChange={e => setPasso(i, 'objetivo', e.target.value)} maxLength={300}
                placeholder="Objetivo deste toque: o que a mensagem precisa fazer (a IA escreve a partir daqui)" aria-label={`Objetivo do passo ${i + 1}`}/>
            </li>
          ))}
        </ol>
        {form.passos.length < 12 && (
          <Button size="sm" icon="plus" onClick={() => set('passos', [...form.passos, passoVazio(Number(form.passos.at(-1)?.dia || 0) + 3)])}>Adicionar passo</Button>
        )}
        {inicial?.em_andamento > 0 && (
          <p className="lv3-flow__note"><Icon name="circle-info"/>{inicial.em_andamento} {inicial.em_andamento === 1 ? 'pessoa está' : 'pessoas estão'} neste fluxo. Se mudar os passos, quem já está termina na versão atual e as próximas inscrições usam a nova.</p>
        )}
      </form>
    </Modal>
  );
}

/** Visão Fluxos: os modelos de cadência da equipe, por estágio da relação. */
export function Fluxos({boot, api, notify}) {
  const [fluxos, setFluxos] = useState([]);
  const [state, setState] = useState({loading: true, error: ''});
  const [editor, setEditor] = useState(null); // null | {} (novo) | fluxo

  const load = useCallback(async () => {
    setState({loading: true, error: ''});
    try { setFluxos(await api.cadenceModels()); setState({loading: false, error: ''}); } catch (error) { setState({loading: false, error: error.message}); }
  }, [api]);
  useEffect(() => { load(); }, [load]);

  const salvar = async dados => {
    const r = editor?.id ? await api.updateFlow(editor.id, dados) : await api.createFlow(dados);
    notify(r?.nova_versao ? 'Fluxo salvo como nova versão. Quem já estava termina na anterior.' : 'Fluxo salvo.');
    setEditor(null);
    load();
  };
  const arquivar = async f => {
    if (!window.confirm(`Arquivar o fluxo "${f.nome}"? Quem está nele segue até o fim; ele só sai da lista.`)) return;
    try { await api.archiveFlow(f.id); notify('Fluxo arquivado.'); load(); } catch (error) { notify(error.message, 'error'); }
  };

  return (
    <div className="lv3-flows">
      <header className="lv3-flows__head">
        <div>
          <h2>Fluxos de cadência</h2>
          <p className="lv3-muted">Comuns a toda a equipe. Escolha o fluxo pelo momento da pessoa ao iniciar a cadência. A etapa de cada passo orienta a IA a escrever conteúdo de topo, meio ou fundo.</p>
        </div>
        <Button variant="primary" icon="plus" onClick={() => setEditor({})}>Novo fluxo</Button>
      </header>
      {state.error && <p className="lv3-error" role="alert">{state.error}</p>}
      {state.loading && !fluxos.length ? <p className="lv3-muted">Carregando fluxos…</p> : !fluxos.length ? (
        <Empty icon="route" title="Nenhum fluxo ativo">Crie o primeiro fluxo para iniciar cadências.</Empty>
      ) : ESTAGIOS.map(([estagio, label, desc]) => {
        const lista = fluxos.filter(f => f.estagio === estagio);
        if (!lista.length) return null;
        return (
          <section key={estagio} className="lv3-flows__group">
            <h3>{label} <small>{desc}</small></h3>
            <div className="lv3-flows__grid">
              {lista.map(f => (
                <article key={f.id} className="lv3-flow">
                  <header>
                    <div>
                      <strong>{f.nome}</strong>
                      {f.descricao && <p>{f.descricao}</p>}
                    </div>
                    <MoreMenu items={[
                      {label: 'Editar', icon: 'pen', onClick: () => setEditor(f)},
                      {label: 'Duplicar', icon: 'copy', onClick: () => setEditor({...f, id: undefined, em_andamento: 0, nome: `${f.nome} (cópia)`})},
                      {label: 'Arquivar', icon: 'box-archive', onClick: () => arquivar(f)},
                    ]}/>
                  </header>
                  <Trilha passos={f.passos || []}/>
                  <footer>
                    <span>{f.total} passos · {f.passos?.length ? `${f.passos.at(-1).dia} dias` : ''}</span>
                    {f.em_andamento > 0 && <span><Icon name="circle-play"/>{f.em_andamento} em andamento</span>}
                    {(f.papeis || []).length > 0 && <span className="lv3-muted">sugerido para {(f.papeis || []).map(p => (boot.papeis || []).find(o => o.value === p)?.label || p).join(', ')}</span>}
                  </footer>
                </article>
              ))}
            </div>
          </section>
        );
      })}
      {editor && <FlowEditor boot={boot} inicial={editor.id || editor.nome ? editor : null} onClose={() => setEditor(null)} onSave={salvar}/>}
    </div>
  );
}
