import React, {useState} from 'react';
import {Button, Empty, Icon, decode, formatDate, prettyName, todayLocal} from './ui.jsx';

// Mesmos tipos que o Leads v2 oferece (e que o CHECK de cadu_lead_atividades aceita).
export const ACTIVITY_TYPES = [
  {value: 'ligacao', label: 'Ligação', icon: 'phone'},
  {value: 'whatsapp', label: 'WhatsApp', icon: 'comment'},
  {value: 'email_enviado', label: 'E-mail', icon: 'envelope'},
  {value: 'reuniao', label: 'Reunião', icon: 'calendar'},
  {value: 'follow_up', label: 'Follow-up', icon: 'rotate-left'},
  {value: 'apresentacao', label: 'Apresentação', icon: 'display'},
  {value: 'proposta_enviada', label: 'Proposta', icon: 'file-lines'},
  {value: 'nota', label: 'Nota', icon: 'note-sticky'},
];
const TYPE_BY_VALUE = Object.fromEntries(ACTIVITY_TYPES.map(t => [t.value, t]));

// Etapas do funil (atuais e as antigas do site) em português de gente.
const ETAPAS = {
  inbox: 'Inbox', tentativa_contato: 'Tentativa de contato', reuniao_agendada: 'Reunião agendada', nutricao: 'Nutrição',
  contato: 'Em contato', qualificado: 'Qualificado', proposta: 'Proposta', negociacao: 'Negociação',
  nao_qualificado: 'Desqualificado', fechado_ganho: 'Ganho', fechado_perdido: 'Perdido',
};
const etapa = slug => ETAPAS[slug] || String(slug || '').replace(/_/g, ' ');

/** Eventos automáticos (mudança de etapa, importação, atribuição, edição) viram frases curtas. */
function eventoDoSistema(a) {
  const desc = decode(a.descricao || '');
  if (a.tipo === 'status_change') {
    // "Status alterado de inbox para tentativa_contato" (site), "... para Nutrição (em massa)" (ações em massa).
    const limpo = desc.replace(/\s*\(em massa\)\s*$/, '');
    const novo = a.status_novo || limpo.match(/para\s+(.+)$/i)?.[1]?.trim();
    const antigo = a.status_anterior || limpo.match(/\bde\s+(.+?)\s+para\s/i)?.[1]?.trim();
    if (/desqualificado/i.test(desc)) return {icon: 'ban', texto: desc.replace(/\s*\(em massa\)/, '')};
    if (novo) return {icon: 'arrow-right-arrow-left', texto: antigo ? `Etapa: ${etapa(antigo)} → ${etapa(novo)}` : `Etapa: ${etapa(novo)}`, chave: `etapa:${novo}`};
    return {icon: 'arrow-right-arrow-left', texto: desc};
  }
  if (a.tipo === 'importacao') return {icon: 'file-import', texto: 'Entrou por importação em massa'};
  if (a.tipo === 'atribuicao') return {icon: 'user-tag', texto: 'Responsável definido'};
  if (a.tipo === 'edicao') return {icon: 'pen', texto: desc || 'Dados atualizados'};
  if (a.tipo === 'contato_add') return {icon: 'user-plus', texto: desc || 'Pessoa adicionada'};
  if (a.tipo === 'contato_remove') return {icon: 'user-minus', texto: desc || 'Pessoa removida'};
  return null;
}

/** O site (trigger) e a tela gravam a mesma mudança de etapa: mostra uma só, a mais completa
 * ("Inbox → Tentativa de contato"), com o nome de quem fez a mudança. */
function semDuplicadas(atividades) {
  const grupos = new Map();
  atividades.forEach(a => {
    const ev = a.tipo === 'status_change' ? eventoDoSistema(a) : null;
    if (!ev?.chave) return;
    const chave = `${ev.chave}@${String(a.created_at).slice(0, 16)}`;
    grupos.set(chave, [...(grupos.get(chave) || []), {a, ev}]);
  });
  const manter = new Map(); // id escolhido → atividade (com usuário herdado)
  grupos.forEach(itens => {
    const melhor = itens.find(i => i.ev.texto.includes('→')) || itens[0];
    const usuario = melhor.a.usuario_nome || itens.find(i => i.a.usuario_nome)?.a.usuario_nome;
    manter.set(melhor.a.id, {...melhor.a, usuario_nome: usuario});
    itens.forEach(i => { if (i.a.id !== melhor.a.id) manter.set(i.a.id, null); });
  });
  return atividades.map(a => (manter.has(a.id) ? manter.get(a.id) : a)).filter(Boolean);
}

export function Activities({api, leadId, contacts, activities, onChanged, notify}) {
  const [tipo, setTipo] = useState('ligacao');
  const [descricao, setDescricao] = useState('');
  const [prazo, setPrazo] = useState('');
  const [contato, setContato] = useState('');
  const [saving, setSaving] = useState(false);
  const [maisOpcoes, setMaisOpcoes] = useState(false);
  const [ia, setIa] = useState('');
  const [editando, setEditando] = useState(null); // {id, descricao, data_prazo}

  const sugerir = async () => {
    setIa('sugerir');
    try {
      const s = await api.suggestActivity(leadId);
      if (!s) { notify('Sem sugestão agora.', 'error'); return; }
      if (TYPE_BY_VALUE[s.tipo]) setTipo(s.tipo);
      setDescricao(s.descricao || '');
      if (s.prazo_dias) {
        const d = new Date(); d.setDate(d.getDate() + Number(s.prazo_dias));
        setPrazo(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
        setMaisOpcoes(true);
      }
    } catch (error) { notify(error.message, 'error'); } finally { setIa(''); }
  };
  const melhorar = async () => {
    if (!descricao.trim()) return notify('Escreva algo primeiro.', 'error');
    setIa('melhorar');
    try { setDescricao(await api.improveText(descricao)); } catch (error) { notify(error.message, 'error'); } finally { setIa(''); }
  };
  const salvarEdicao = async () => {
    try {
      const original = activities.find(a => a.id === editando.id);
      await api.updateActivity(editando.id, {tipo: original?.tipo, descricao: editando.descricao, data_prazo: editando.data_prazo || null,
        id_contato: original?.id_contato || null});
      setEditando(null); notify('Registro atualizado.'); onChanged();
    } catch (error) { notify(error.message, 'error'); }
  };

  const submit = async event => {
    event.preventDefault();
    if (!descricao.trim()) return notify('Descreva o que aconteceu ou o que precisa ser feito.', 'error');
    setSaving(true);
    try {
      await api.addActivity(leadId, {tipo, descricao: descricao.trim(), data_prazo: prazo || null, id_contato: contato ? Number(contato) : null});
      setDescricao(''); setPrazo('');
      notify(prazo ? 'Tarefa agendada.' : 'Atividade registrada.');
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setSaving(false); }
  };
  const toggle = async activity => {
    try { await api.toggleActivity(activity.id, !activity.concluida); onChanged(); }
    catch (error) { notify(error.message, 'error'); }
  };

  const lista = semDuplicadas(activities);
  const pendentes = lista.filter(a => a.data_prazo && !a.concluida);

  return (
    <div className="lv3-activities">
      <form className="lv3-composer lv3-composer--compact" onSubmit={submit}>
        <div className="lv3-chips" role="radiogroup" aria-label="Tipo de atividade">
          {ACTIVITY_TYPES.map(t => (
            <button key={t.value} type="button" role="radio" aria-checked={tipo === t.value}
              className={`lv3-chipbtn ${tipo === t.value ? 'is-on' : ''}`} onClick={() => setTipo(t.value)}>
              <Icon name={t.icon}/>{t.label}
            </button>
          ))}
        </div>
        <textarea className="lv3-input lv3-textarea" rows={2} placeholder="O que aconteceu? Ex.: liguei, pediu retorno na quinta."
          value={descricao} onChange={event => setDescricao(event.target.value)} aria-label="Descrição"/>
        {maisOpcoes && (
          <div className="lv3-composer__row lv3-composer__row--2">
            <label className="lv3-field"><span className="lv3-field__label">Lembrar em</span>
              <input className="lv3-input" type="date" value={prazo} onChange={event => setPrazo(event.target.value)}/></label>
            <label className="lv3-field"><span className="lv3-field__label">Com quem</span>
              <select className="lv3-select" value={contato} onChange={event => setContato(event.target.value)}>
                <option value="">Ninguém específico</option>
                {contacts.map(c => <option key={c.id} value={c.id}>{prettyName(c.nome)}</option>)}
              </select></label>
          </div>
        )}
        <div className="lv3-composer__foot">
          <span className="lv3-composer__tools">
            <button type="button" className="lv3-link lv3-link--muted" onClick={sugerir} disabled={!!ia} title="A IA sugere o próximo passo pelo histórico do lead">
              <Icon name="wand-magic-sparkles"/> {ia === 'sugerir' ? 'Pensando…' : 'Sugerir próximo passo'}</button>
            {descricao.trim() && <button type="button" className="lv3-link lv3-link--muted" onClick={melhorar} disabled={!!ia}>{ia === 'melhorar' ? 'Melhorando…' : 'Melhorar texto'}</button>}
            <button type="button" className="lv3-link lv3-link--muted" onClick={() => setMaisOpcoes(v => !v)}>
              {maisOpcoes ? 'Menos opções' : 'Lembrete ou pessoa'}
            </button>
          </span>
          <Button variant="primary" size="sm" type="submit" icon="plus" disabled={saving}>{saving ? 'Salvando…' : prazo ? 'Agendar' : 'Registrar'}</Button>
        </div>
      </form>

      {pendentes.length > 0 && (
        <div className="lv3-pending"><Icon name="clock"/>{pendentes.length} {pendentes.length === 1 ? 'lembrete pendente' : 'lembretes pendentes'}</div>
      )}

      {!lista.length ? (
        <Empty icon="list-check" title="Nada registrado ainda">Registre a primeira tentativa de contato acima.</Empty>
      ) : (
        <ol className="lv3-timeline">
          {lista.map(a => {
            const sistema = TYPE_BY_VALUE[a.tipo] ? null : eventoDoSistema(a);
            if (sistema) {
              return (
                <li key={a.id} className="lv3-tl lv3-tl--system">
                  <span className="lv3-tl__dot"><Icon name={sistema.icon}/></span>
                  <div className="lv3-tl__line">
                    <span>{sistema.texto}</span>
                    <span className="lv3-muted">{String(a.created_at).slice(0, 10)}{a.usuario_nome ? ` · ${a.usuario_nome}` : ''}</span>
                  </div>
                </li>
              );
            }
            const type = TYPE_BY_VALUE[a.tipo] || {label: 'Registro', icon: 'circle'};
            const atrasada = a.data_prazo && !a.concluida && a.data_prazo < todayLocal();
            return (
              <li key={a.id} className={`lv3-tl ${a.concluida ? 'is-done' : ''}`}>
                <span className="lv3-tl__dot"><Icon name={type.icon}/></span>
                <div className="lv3-tl__body">
                  <div className="lv3-tl__head">
                    <strong>{type.label}{a.contato_nome ? ` · ${prettyName(a.contato_nome)}` : ''}</strong>
                    <span className="lv3-muted">{a.created_at}{a.usuario_nome ? ` · ${a.usuario_nome}` : ''}
                      {editando?.id !== a.id && <button type="button" className="lv3-iconbtn lv3-iconbtn--xs" title="Editar" aria-label="Editar registro"
                        onClick={() => setEditando({id: a.id, descricao: decode(a.descricao), data_prazo: a.data_prazo || ''})}><Icon name="pen"/></button>}
                    </span>
                  </div>
                  {editando?.id === a.id ? (
                    <div className="lv3-tl__edit">
                      <textarea className="lv3-input lv3-textarea" rows={3} value={editando.descricao} onChange={e => setEditando(x => ({...x, descricao: e.target.value}))}/>
                      <div className="lv3-tl__editbar">
                        <input className="lv3-input lv3-input--sm" type="date" value={editando.data_prazo} onChange={e => setEditando(x => ({...x, data_prazo: e.target.value}))} aria-label="Lembrar em"/>
                        <Button size="sm" onClick={() => setEditando(null)}>Cancelar</Button>
                        <Button size="sm" variant="primary" onClick={salvarEdicao}>Salvar</Button>
                      </div>
                    </div>
                  ) : <p>{decode(a.descricao)}</p>}
                  {a.data_prazo && (
                    <label className={`lv3-tl__task ${atrasada ? 'is-late' : ''}`}>
                      <input type="checkbox" checked={!!a.concluida} onChange={() => toggle(a)}/>
                      <span>{a.concluida ? 'Feito' : atrasada ? `Atrasado desde ${formatDate(a.data_prazo)}` : `Lembrar em ${formatDate(a.data_prazo)}`}</span>
                    </label>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
