import React, {useState} from 'react';
import {Button, Field, Modal, decode} from './ui.jsx';

export function DisqualifyDialog({boot, count, onCancel, onConfirm}) {
  const [motivo, setMotivo] = useState(boot.motivos[0]?.value || 'outro');
  const [detalhe, setDetalhe] = useState('');
  const [busy, setBusy] = useState(false);
  const label = boot.motivos.find(m => m.value === motivo)?.label || motivo;
  const confirm = async () => {
    setBusy(true);
    const ok = await onConfirm(detalhe.trim() ? `${label}: ${detalhe.trim()}` : label);
    if (!ok) setBusy(false);
  };
  return (
    <Modal title={count === 1 ? 'Desqualificar lead' : `Desqualificar ${count} leads`} onClose={onCancel}
      footer={<>
        <Button onClick={onCancel} disabled={busy}>Cancelar</Button>
        <Button variant="danger" icon="ban" onClick={confirm} disabled={busy}>{busy ? 'Desqualificando…' : 'Desqualificar'}</Button>
      </>}>
      <p className="lv3-muted">{count === 1 ? 'O lead sai da fila ativa.' : 'Os leads saem da fila ativa.'} O motivo fica registrado no histórico.</p>
      <div className="lv3-radio-list" role="radiogroup" aria-label="Motivo">
        {boot.motivos.map(m => (
          <label key={m.value} className={`lv3-radio ${motivo === m.value ? 'is-on' : ''}`}>
            <input type="radio" name="motivo" value={m.value} checked={motivo === m.value} onChange={() => setMotivo(m.value)}/>
            {m.label}
          </label>
        ))}
      </div>
      <Field label="Detalhe (opcional)" wide>
        <input className="lv3-input" value={detalhe} maxLength={80} onChange={event => setDetalhe(event.target.value)}/>
      </Field>
    </Modal>
  );
}

const EDIT_FIELDS = [
  ['empresa', 'Empresa'], ['nome', 'Contato'], ['email', 'E-mail'], ['telefone', 'Telefone'],
  ['cargo', 'Cargo'], ['segmento', 'Segmento'], ['url_site', 'Site'], ['valor_estimado', 'Valor estimado (R$)'],
];

export function EditDialog({lead, onCancel, onSave}) {
  const [form, setForm] = useState(() => ({
    ...Object.fromEntries(EDIT_FIELDS.map(([key]) => [key, lead[key] == null ? '' : decode(lead[key])])),
    notas_internas: lead.notas_internas || '',
  }));
  const [busy, setBusy] = useState(false);
  const set = key => event => setForm(f => ({...f, [key]: event.target.value}));
  const save = async event => {
    event.preventDefault();
    setBusy(true);
    const body = {...form, valor_estimado: form.valor_estimado === '' ? null : Number(String(form.valor_estimado).replace(',', '.'))};
    const ok = await onSave(body);
    if (!ok) setBusy(false);
  };
  return (
    <Modal title="Editar dados do lead" onClose={onCancel} width={640}
      footer={<>
        <Button onClick={onCancel} disabled={busy}>Cancelar</Button>
        <Button variant="primary" type="submit" form="lv3-edit-form" disabled={busy}>{busy ? 'Salvando…' : 'Salvar'}</Button>
      </>}>
      <form id="lv3-edit-form" className="lv3-form__grid" onSubmit={save}>
        {EDIT_FIELDS.map(([key, label]) => (
          <Field key={key} label={label}><input className="lv3-input" value={form[key]} onChange={set(key)}/></Field>
        ))}
        <Field label="Notas internas" wide>
          <textarea className="lv3-input lv3-textarea" rows={3} value={form.notas_internas} onChange={set('notas_internas')}/>
        </Field>
      </form>
    </Modal>
  );
}

export function NewLeadDialog({boot, onCancel, onSave}) {
  const [form, setForm] = useState({empresa: '', nome: '', email: '', telefone: '', cargo: '', potencial: 'medio',
    id_executivo: boot.user?.id && boot.executivos.some(e => e.id === boot.user.id) ? String(boot.user.id) : '', fonte: 'manual'});
  const [busy, setBusy] = useState(false);
  const set = key => event => setForm(f => ({...f, [key]: event.target.value}));
  const save = async event => {
    event.preventDefault();
    setBusy(true);
    const ok = await onSave({...form, id_executivo: form.id_executivo ? Number(form.id_executivo) : null});
    if (!ok) setBusy(false);
  };
  return (
    <Modal title="Novo lead" onClose={onCancel} width={640}
      footer={<>
        <Button onClick={onCancel} disabled={busy}>Cancelar</Button>
        <Button variant="primary" type="submit" form="lv3-new-form" disabled={busy}>{busy ? 'Criando…' : 'Criar lead'}</Button>
      </>}>
      <form id="lv3-new-form" className="lv3-form__grid" onSubmit={save}>
        <Field label="Empresa"><input className="lv3-input" value={form.empresa} onChange={set('empresa')}/></Field>
        <Field label="Contato *"><input className="lv3-input" value={form.nome} onChange={set('nome')} required/></Field>
        <Field label="E-mail"><input className="lv3-input" type="email" value={form.email} onChange={set('email')}/></Field>
        <Field label="Telefone"><input className="lv3-input" value={form.telefone} onChange={set('telefone')}/></Field>
        <Field label="Cargo"><input className="lv3-input" value={form.cargo} onChange={set('cargo')}/></Field>
        <Field label="Potencial">
          <select className="lv3-select" value={form.potencial} onChange={set('potencial')}>
            {boot.potenciais.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </Field>
        <Field label="Responsável">
          <select className="lv3-select" value={form.id_executivo} onChange={set('id_executivo')}>
            <option value="">Sem responsável</option>
            {boot.executivos.map(e => <option key={e.id} value={String(e.id)}>{e.nome}</option>)}
          </select>
        </Field>
        <Field label="Fonte">
          <select className="lv3-select" value={form.fonte} onChange={set('fonte')}>
            <option value="manual">Manual</option><option value="indicacao">Indicação</option>
            <option value="evento">Evento</option><option value="outro">Outro</option>
          </select>
        </Field>
      </form>
    </Modal>
  );
}
