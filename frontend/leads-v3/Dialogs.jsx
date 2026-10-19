import React, {useState} from 'react';
import {Button, Field, Icon, Modal, decode} from './ui.jsx';

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

const digitsOnly = value => String(value || '').replace(/\D/g, '');

export function ConvertDialog({boot, lead, api, onCancel, onDone, notify}) {
  const listas = boot.conversao || {tipos: [], agencias: [], estados: []};
  const [form, setForm] = useState({
    pessoa: 'J', cnpj: lead.cnpj || '', nome_fantasia: decode(lead.empresa || lead.nome || ''), razao_social: '',
    id_tipo_cliente: '', vendas_central_comm: lead.id_executivo ? String(lead.id_executivo) : '', pk_id_tbl_agencia: '',
    inscricao_estadual: '', inscricao_municipal: '', cep: '', pk_id_aux_estado: '', cidade: '', bairro: '',
    logradouro: '', numero: '', complemento: '',
  });
  const [busy, setBusy] = useState('');
  const set = key => event => setForm(f => ({...f, [key]: event.target.value}));
  const pj = form.pessoa === 'J';

  const lookup = async () => {
    const cnpj = digitsOnly(form.cnpj);
    if (cnpj.length !== 14) return notify('Digite os 14 dígitos do CNPJ.', 'error');
    setBusy('cnpj');
    try {
      const d = await api.lookupCnpj(cnpj);
      const estado = listas.estados.find(e => e.sigla === d.uf);
      setForm(f => ({...f,
        razao_social: d.razao_social || f.razao_social, nome_fantasia: f.nome_fantasia || d.nome_fantasia || '',
        inscricao_estadual: d.inscricao_estadual || f.inscricao_estadual, cep: d.cep || f.cep,
        pk_id_aux_estado: estado ? String(estado.id) : f.pk_id_aux_estado, cidade: d.municipio || f.cidade,
        bairro: d.bairro || f.bairro, logradouro: d.logradouro || f.logradouro, numero: d.numero || f.numero,
        complemento: d.complemento || f.complemento}));
      notify('Dados da Receita preenchidos.');
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };

  const submit = async event => {
    event.preventDefault();
    const cnpj = digitsOnly(form.cnpj);
    if (pj && cnpj && cnpj.length !== 14) return notify('CNPJ inválido.', 'error');
    if (!form.nome_fantasia.trim()) return notify('Informe o nome fantasia.', 'error');
    if (pj && !form.razao_social.trim()) return notify('Informe a razão social.', 'error');
    if (!form.id_tipo_cliente || !form.vendas_central_comm || (pj && !form.pk_id_tbl_agencia)) {
      return notify('Preencha tipo, executivo e agência.', 'error');
    }
    setBusy('save');
    try {
      const result = await api.convert(lead.id, {
        ...form, cnpj: cnpj || null,
        razao_social: pj ? form.razao_social.trim() : form.nome_fantasia.trim(),
        nome_fantasia: form.nome_fantasia.trim(),
        id_tipo_cliente: Number(form.id_tipo_cliente), vendas_central_comm: Number(form.vendas_central_comm),
        pk_id_tbl_agencia: pj ? Number(form.pk_id_tbl_agencia) : 2,
        pk_id_aux_estado: form.pk_id_aux_estado || null, cep: digitsOnly(form.cep) || null,
      });
      onDone(result.cliente_id);
    } catch (error) { notify(error.message, 'error'); setBusy(''); }
  };

  return (
    <Modal title="Converter em cliente" onClose={onCancel} width={720}
      footer={<>
        <Button onClick={onCancel} disabled={!!busy}>Cancelar</Button>
        <Button variant="primary" type="submit" form="lv3-convert-form" icon="user-check" disabled={!!busy}>{busy === 'save' ? 'Convertendo…' : 'Converter'}</Button>
      </>}>
      <p className="lv3-muted">Cria o cliente na carteira e liga ao lead. Agências vinculadas extras continuam no cadastro do cliente.</p>
      <form id="lv3-convert-form" className="lv3-form__grid" onSubmit={submit}>
        <div className="lv3-segmented lv3-field--wide" role="radiogroup" aria-label="Pessoa">
          {[['J', 'Pessoa jurídica'], ['F', 'Pessoa física']].map(([value, label]) => (
            <button key={value} type="button" role="radio" aria-checked={form.pessoa === value} className={form.pessoa === value ? 'is-on' : ''}
              onClick={() => setForm(f => ({...f, pessoa: value}))}>{label}</button>
          ))}
        </div>
        <Field label={pj ? 'CNPJ' : 'CPF'}>
          <div className="lv3-inline-form">
            <input className="lv3-input" value={form.cnpj} onChange={set('cnpj')} inputMode="numeric"/>
            {pj && <Button onClick={lookup} disabled={!!busy} icon="magnifying-glass">{busy === 'cnpj' ? '…' : 'Receita'}</Button>}
          </div>
        </Field>
        <Field label="Nome fantasia *"><input className="lv3-input" value={form.nome_fantasia} onChange={set('nome_fantasia')} required/></Field>
        {pj && <Field label="Razão social *" wide><input className="lv3-input" value={form.razao_social} onChange={set('razao_social')}/></Field>}
        <Field label="Tipo de cliente *">
          <select className="lv3-select" value={form.id_tipo_cliente} onChange={set('id_tipo_cliente')}>
            <option value="">Escolha…</option>
            {listas.tipos.map(t => <option key={t.id} value={t.id}>{t.nome}</option>)}
          </select>
        </Field>
        <Field label="Executivo de vendas *">
          <select className="lv3-select" value={form.vendas_central_comm} onChange={set('vendas_central_comm')}>
            <option value="">Escolha…</option>
            {boot.executivos.map(e => <option key={e.id} value={e.id}>{e.nome}</option>)}
          </select>
        </Field>
        {pj && (
          <Field label="Agência *">
            <select className="lv3-select" value={form.pk_id_tbl_agencia} onChange={set('pk_id_tbl_agencia')}>
              <option value="">Escolha…</option>
              {listas.agencias.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
            </select>
          </Field>
        )}
        {pj && <Field label="Inscrição estadual"><input className="lv3-input" value={form.inscricao_estadual} onChange={set('inscricao_estadual')}/></Field>}
        <Field label="CEP"><input className="lv3-input" value={form.cep} onChange={set('cep')} inputMode="numeric"/></Field>
        <Field label="UF">
          <select className="lv3-select" value={form.pk_id_aux_estado} onChange={set('pk_id_aux_estado')}>
            <option value="">—</option>
            {listas.estados.map(e => <option key={e.id} value={e.id}>{e.sigla}</option>)}
          </select>
        </Field>
        <Field label="Cidade"><input className="lv3-input" value={form.cidade} onChange={set('cidade')}/></Field>
        <Field label="Bairro"><input className="lv3-input" value={form.bairro} onChange={set('bairro')}/></Field>
        <Field label="Logradouro"><input className="lv3-input" value={form.logradouro} onChange={set('logradouro')}/></Field>
        <Field label="Número"><input className="lv3-input" value={form.numero} onChange={set('numero')}/></Field>
      </form>
    </Modal>
  );
}

export function CompanyDialog({lead, onCancel, onSave}) {
  const [form, setForm] = useState({dominio: lead.dominio || '', cnpj: lead.cnpj || '', grupo_economico: lead.grupo_economico || '', prioridade_conta: lead.prioridade_conta || ''});
  const [busy, setBusy] = useState(false);
  const set = key => event => setForm(f => ({...f, [key]: event.target.value}));
  const save = async event => {
    event.preventDefault();
    setBusy(true);
    if (!(await onSave(form))) setBusy(false);
  };
  return (
    <Modal title="Dados da empresa" onClose={onCancel}
      footer={<>
        <Button onClick={onCancel} disabled={busy}>Cancelar</Button>
        <Button variant="primary" type="submit" form="lv3-company-form" disabled={busy}>{busy ? 'Salvando…' : 'Salvar'}</Button>
      </>}>
      <form id="lv3-company-form" className="lv3-form__grid" onSubmit={save}>
        <Field label="Domínio do site"><input className="lv3-input" placeholder="gerdau.com.br" value={form.dominio} onChange={set('dominio')}/></Field>
        <Field label="CNPJ"><input className="lv3-input" value={form.cnpj} onChange={set('cnpj')} inputMode="numeric"/></Field>
        <Field label="Grupo econômico"><input className="lv3-input" placeholder="Ex.: Sistema Unimed" value={form.grupo_economico} onChange={set('grupo_economico')}/></Field>
        <Field label="Prioridade">
          <select className="lv3-select" value={form.prioridade_conta} onChange={set('prioridade_conta')}>
            <option value="">Sem prioridade</option><option value="A">A</option><option value="B">B</option><option value="C">C</option>
          </select>
        </Field>
      </form>
      <p className="lv3-muted">O domínio é o que o Apollo usa para achar as pessoas da empresa.</p>
    </Modal>
  );
}

/** "Empresa; domínio; CNPJ" por linha (domínio e CNPJ opcionais, em qualquer ordem). */
function parseLinhas(texto) {
  return texto.split('\n').map(linha => linha.trim()).filter(Boolean).map(linha => {
    const partes = linha.split(/[;|\t]/).map(p => p.trim()).filter(Boolean);
    const conta = {nome: partes[0] || '', dominio: '', cnpj: ''};
    partes.slice(1).forEach(p => {
      if (digitsOnly(p).length >= 11 && !/[a-z]/i.test(p)) conta.cnpj = p;
      else if (/\./.test(p)) conta.dominio = p;
    });
    return conta;
  });
}

export function GoldenAddDialog({boot, api, trimestre, executivo, onCancel, onDone, notify}) {
  const [exec, setExec] = useState(executivo && /^\d+$/.test(executivo) ? executivo : '');
  const [texto, setTexto] = useState('');
  const [resultados, setResultados] = useState(null);
  const [busy, setBusy] = useState('');
  const contas = parseLinhas(texto);

  const validar = async () => {
    if (!exec) return notify('Escolha o executivo.', 'error');
    if (!contas.length) return notify('Digite ao menos uma empresa.', 'error');
    setBusy('validar');
    try {
      const r = await api.validateGolden({id_executivo: Number(exec), trimestre, contas});
      setResultados(r.resultados);
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const validas = (resultados || []).filter(r => r.ok);
  const confirmar = async () => {
    setBusy('criar');
    try {
      const r = await api.createGolden({id_executivo: Number(exec), trimestre,
        contas: validas.map(v => ({nome: v.dados.nome, dominio: v.dados.dominio, cnpj: v.dados.cnpj}))});
      onDone(r);
    } catch (error) { notify(error.message, 'error'); setBusy(''); }
  };

  return (
    <Modal title={`Adicionar ao Golden Circle ${trimestre}`} onClose={onCancel} width={720}
      footer={resultados ? <>
        <Button onClick={() => setResultados(null)} disabled={!!busy}>Voltar e editar</Button>
        <Button variant="primary" icon="plus" onClick={confirmar} disabled={!!busy || !validas.length}>
          {busy === 'criar' ? 'Adicionando…' : `Adicionar ${validas.length} ${validas.length === 1 ? 'empresa' : 'empresas'}`}
        </Button>
      </> : <>
        <Button onClick={onCancel} disabled={!!busy}>Cancelar</Button>
        <Button variant="primary" icon="shield-check" onClick={validar} disabled={!!busy}>{busy === 'validar' ? 'Validando…' : 'Validar'}</Button>
      </>}>
      {!resultados ? (
        <>
          <Field label="Executivo *">
            <select className="lv3-select" value={exec} onChange={event => setExec(event.target.value)}>
              <option value="">Escolha…</option>
              {boot.executivos.map(e => <option key={e.id} value={e.id}>{e.nome}</option>)}
            </select>
          </Field>
          <Field label="Empresas (uma por linha)" wide>
            <textarea className="lv3-input lv3-textarea lv3-textarea--tall" value={texto} onChange={event => setTexto(event.target.value)}
              placeholder={'Gerdau; gerdau.com.br; 33.611.500/0001-19\nVale; vale.com\nOnfly'}/>
          </Field>
          <p className="lv3-muted">Domínio e CNPJ são opcionais, separados por ponto e vírgula. A validação confere CNPJ ativo na Receita, duplicidade e se a empresa já é lead ou cliente (vira expansão).</p>
        </>
      ) : (
        <ul className="lv3-validation">
          {resultados.map((r, i) => (
            <li key={i} className={`lv3-validation__item ${r.ok ? 'is-ok' : 'is-blocked'}`}>
              <Icon name={r.ok ? 'circle-check' : 'circle-xmark'}/>
              <div>
                <strong>{r.dados.nome || '(sem nome)'}</strong>
                {r.ok && <span className="lv3-muted">{[r.dados.objetivo === 'expansao' ? 'Expansão (já é cliente)' : 'Captação', r.dados.id_lead ? 'liga ao lead existente' : 'cria lead novo', r.dados.dominio].filter(Boolean).join(' · ')}</span>}
                {r.bloqueios.map(b => <p key={b} className="lv3-validation__block">{b}</p>)}
                {r.avisos.map(a => <p key={a} className="lv3-validation__warn">{a}</p>)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
