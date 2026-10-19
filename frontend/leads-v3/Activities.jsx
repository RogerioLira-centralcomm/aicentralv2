import React, {useState} from 'react';
import {Button, Empty, Field, Icon, decode, formatDate, todayLocal} from './ui.jsx';

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
const SYSTEM_TYPES = {status_change: {label: 'Etapa', icon: 'arrow-right-arrow-left'}, atribuicao: {label: 'Atribuição', icon: 'user-tag'}};

export function Activities({api, leadId, contacts, activities, onChanged, notify}) {
  const [tipo, setTipo] = useState('ligacao');
  const [descricao, setDescricao] = useState('');
  const [prazo, setPrazo] = useState('');
  const [contato, setContato] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async event => {
    event.preventDefault();
    if (!descricao.trim()) return notify('Descreva a atividade.', 'error');
    setSaving(true);
    try {
      await api.addActivity(leadId, {tipo, descricao: descricao.trim(), data_prazo: prazo || null, id_contato: contato ? Number(contato) : null});
      setDescricao(''); setPrazo('');
      notify('Atividade registrada.');
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setSaving(false); }
  };
  const toggle = async activity => {
    try { await api.toggleActivity(activity.id, !activity.concluida); onChanged(); }
    catch (error) { notify(error.message, 'error'); }
  };

  const pendentes = activities.filter(a => a.data_prazo && !a.concluida);

  return (
    <div className="lv3-activities">
      <form className="lv3-composer" onSubmit={submit}>
        <div className="lv3-typepicker" role="radiogroup" aria-label="Tipo de atividade">
          {ACTIVITY_TYPES.map(t => (
            <button key={t.value} type="button" role="radio" aria-checked={tipo === t.value}
              className={`lv3-typebtn ${tipo === t.value ? 'is-on' : ''}`} onClick={() => setTipo(t.value)}>
              <Icon name={t.icon}/><span>{t.label}</span>
            </button>
          ))}
        </div>
        <textarea className="lv3-input lv3-textarea" rows={3} placeholder="O que aconteceu ou o que precisa ser feito?"
          value={descricao} onChange={event => setDescricao(event.target.value)} aria-label="Descrição da atividade"/>
        <div className="lv3-composer__row">
          <Field label="Prazo (opcional)"><input className="lv3-input" type="date" value={prazo} onChange={event => setPrazo(event.target.value)}/></Field>
          <Field label="Pessoa">
            <select className="lv3-select" value={contato} onChange={event => setContato(event.target.value)}>
              <option value="">Nenhuma</option>
              {contacts.map(c => <option key={c.id} value={c.id}>{decode(c.nome)}</option>)}
            </select>
          </Field>
          <Button variant="primary" type="submit" icon="plus" disabled={saving}>{saving ? 'Salvando…' : 'Registrar'}</Button>
        </div>
      </form>

      {pendentes.length > 0 && (
        <div className="lv3-pending"><Icon name="clock"/>{pendentes.length} {pendentes.length === 1 ? 'tarefa pendente' : 'tarefas pendentes'}</div>
      )}

      {!activities.length ? (
        <Empty icon="list-check" title="Nenhuma atividade ainda">Registre a primeira tentativa de contato acima.</Empty>
      ) : (
        <ol className="lv3-timeline">
          {activities.map(a => {
            const type = TYPE_BY_VALUE[a.tipo] || SYSTEM_TYPES[a.tipo] || {label: a.tipo, icon: 'circle'};
            const atrasada = a.data_prazo && !a.concluida && a.data_prazo < todayLocal();
            return (
              <li key={a.id} className={`lv3-tl ${a.concluida ? 'is-done' : ''}`}>
                <span className="lv3-tl__dot"><Icon name={type.icon}/></span>
                <div className="lv3-tl__body">
                  <div className="lv3-tl__head">
                    <strong>{type.label}</strong>
                    <span className="lv3-muted">{a.created_at}{a.usuario_nome ? ` · ${a.usuario_nome}` : ''}</span>
                  </div>
                  <p>{decode(a.descricao)}</p>
                  {a.data_prazo && (
                    <label className={`lv3-tl__task ${atrasada ? 'is-late' : ''}`}>
                      <input type="checkbox" checked={!!a.concluida} onChange={() => toggle(a)}/>
                      <span>{a.concluida ? 'Concluída' : atrasada ? `Atrasada · ${formatDate(a.data_prazo)}` : `Prazo ${formatDate(a.data_prazo)}`}</span>
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
