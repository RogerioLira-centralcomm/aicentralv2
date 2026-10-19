import React, {useState} from 'react';
import {Button, Empty, Field, Icon, decode, formatDate, whatsappUrl} from './ui.jsx';

function Info({label, children}) {
  return (
    <div className="lv3-info">
      <dt>{label}</dt>
      <dd>{children || <span className="lv3-muted">—</span>}</dd>
    </div>
  );
}

const CLOSED_LABELS = {nao_qualificado: 'Desqualificado', fechado_ganho: 'Ganho', fechado_perdido: 'Perdido'};
const EMPTY_CONTACT ={nome: '', cargo: '', email: '', telefone: ''};

function Contacts({api, leadId, contacts, onChanged, notify}) {
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const set = key => event => setDraft(d => ({...d, [key]: event.target.value}));

  const save = async event => {
    event.preventDefault();
    if (!draft.nome.trim()) return notify('Informe o nome do contato.', 'error');
    setSaving(true);
    try {
      await api.addContact(leadId, draft);
      setDraft(null);
      notify('Contato adicionado.');
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setSaving(false); }
  };
  const act = (fn, done) => async () => {
    try { await fn(); notify(done); onChanged(); } catch (error) { notify(error.message, 'error'); }
  };

  return (
    <section className="lv3-section">
      <header className="lv3-section__head">
        <h3>Pessoas <span className="lv3-count">{contacts.length}</span></h3>
        {!draft && <Button size="sm" icon="user-plus" onClick={() => setDraft(EMPTY_CONTACT)}>Adicionar pessoa</Button>}
      </header>

      {draft && (
        <form className="lv3-card lv3-form" onSubmit={save}>
          <div className="lv3-form__grid">
            <Field label="Nome"><input className="lv3-input" value={draft.nome} onChange={set('nome')} required/></Field>
            <Field label="Cargo"><input className="lv3-input" value={draft.cargo} onChange={set('cargo')}/></Field>
            <Field label="E-mail"><input className="lv3-input" type="email" value={draft.email} onChange={set('email')}/></Field>
            <Field label="Telefone"><input className="lv3-input" value={draft.telefone} onChange={set('telefone')}/></Field>
          </div>
          <div className="lv3-form__actions">
            <Button onClick={() => setDraft(null)} disabled={saving}>Cancelar</Button>
            <Button variant="primary" type="submit" disabled={saving}>{saving ? 'Salvando…' : 'Salvar pessoa'}</Button>
          </div>
        </form>
      )}

      {!contacts.length && !draft ? (
        <Empty icon="users" title="Nenhuma pessoa cadastrada">Adicione quem decide ou influencia a compra nesta empresa.</Empty>
      ) : (
        <ul className="lv3-people">
          {contacts.map(c => (
            <li key={c.id} className="lv3-person">
              <div className="lv3-person__avatar" aria-hidden="true">{decode(c.nome).slice(0, 1).toUpperCase()}</div>
              <div className="lv3-person__body">
                <div className="lv3-person__name">
                  {decode(c.nome)}
                  {c.is_principal && <span className="lv3-chip lv3-chip--brand">Principal</span>}
                </div>
                <div className="lv3-person__role">{c.cargo || c.departamento || 'Cargo não informado'}</div>
                <div className="lv3-person__links">
                  {c.email && <a href={`mailto:${c.email}`}><Icon name="envelope"/>{c.email}</a>}
                  {c.telefone && <a href={whatsappUrl(c.telefone)} target="_blank" rel="noopener noreferrer"><Icon name="phone"/>{c.telefone}</a>}
                </div>
              </div>
              <div className="lv3-person__actions">
                {!c.is_principal && (
                  <button type="button" className="lv3-iconbtn" title="Tornar principal" aria-label={`Tornar ${decode(c.nome)} principal`}
                    onClick={act(() => api.makePrimary(leadId, c.id), 'Contato principal atualizado.')}><Icon name="star"/></button>
                )}
                <button type="button" className="lv3-iconbtn lv3-iconbtn--danger" title="Remover" aria-label={`Remover ${decode(c.nome)}`}
                  onClick={() => { if (window.confirm(`Remover ${decode(c.nome)} deste lead?`)) act(() => api.removeContact(c.id), 'Contato removido.')(); }}>
                  <Icon name="trash"/>
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function LeadPanel({boot, api, lead, contacts, loading, notify, onChanged, onEdit, onDisqualify}) {
  const [busy, setBusy] = useState(false);
  if (loading && !lead) return <section className="lv3-col lv3-lead"><div className="lv3-skeleton"/></section>;
  if (!lead) {
    return (
      <section className="lv3-col lv3-lead">
        <Empty icon="hand-pointer" title="Escolha um lead na fila">Use as caixas de seleção para agir em vários leads de uma vez.</Empty>
      </section>
    );
  }

  const statusIndex = boot.status.findIndex(s => s.value === lead.status);
  const next = statusIndex >= 0 ? boot.status[statusIndex + 1] : null;
  const closed = statusIndex < 0;
  const patch = async (body, done) => {
    setBusy(true);
    try { await api.updateStatus(lead.id, body); notify(done); onChanged(); }
    catch (error) { notify(error.message, 'error'); } finally { setBusy(false); }
  };
  const nome = decode(lead.empresa || lead.nome);

  return (
    <section className="lv3-col lv3-lead" aria-label="Lead selecionado">
      <header className="lv3-lead__head">
        <div className="lv3-lead__title">
          {lead.favicon_url && <img src={lead.favicon_url} alt="" className="lv3-lead__favicon"/>}
          <div>
            <h2>{nome || 'Sem nome'}</h2>
            <p>{[lead.segmento, lead.fonte && `via ${lead.fonte}`, lead.created_at && `entrou em ${formatDate(lead.created_at)}`].filter(Boolean).join(' · ')}</p>
          </div>
        </div>

        <div className="lv3-lead__controls">
          <Field label="Etapa">
            <select className="lv3-select" value={closed ? '' : lead.status} disabled={busy}
              onChange={event => patch({status: event.target.value}, 'Etapa atualizada.')}>
              {closed && <option value="">{CLOSED_LABELS[lead.status] || lead.status}</option>}
              {boot.status.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </Field>
          <Field label="Potencial">
            <select className="lv3-select" value={lead.potencial || ''} disabled={busy}
              onChange={event => patch({potencial: event.target.value}, 'Potencial atualizado.')}>
              {boot.potenciais.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </Field>
          <Field label="Responsável">
            <select className="lv3-select" value={lead.id_executivo ? String(lead.id_executivo) : '0'} disabled={busy}
              onChange={event => patch({id_executivo: Number(event.target.value)}, 'Responsável atualizado.')}>
              <option value="0">Sem responsável</option>
              {boot.executivos.map(e => <option key={e.id} value={String(e.id)}>{e.nome}</option>)}
            </select>
          </Field>
        </div>

        <div className="lv3-lead__ctas">
          {next && (
            <Button variant="primary" icon="arrow-right" disabled={busy}
              onClick={() => patch({status: next.value}, `Lead movido para ${next.label}.`)}>
              Avançar para {next.label}
            </Button>
          )}
          <Button icon="pen" onClick={onEdit} disabled={busy}>Editar dados</Button>
          <a className="lv3-btn lv3-btn--secondary lv3-btn--md" href={`${boot.legacyUrl}`} target="_blank" rel="noopener noreferrer"
            title="Converter e mesclar ainda ficam no Leads atual">
            <Icon name="user-check"/><span>Converter em cliente</span>
          </a>
          <Button variant="danger-ghost" icon="ban" onClick={onDisqualify} disabled={busy || lead.status === 'nao_qualificado'}>Desqualificar</Button>
        </div>
      </header>

      <div className="lv3-lead__scroll">
        <section className="lv3-section">
          <header className="lv3-section__head"><h3>Dados do lead</h3></header>
          <dl className="lv3-infos">
            <Info label="Empresa">{decode(lead.empresa)}</Info>
            <Info label="Contato">{decode(lead.nome)}</Info>
            <Info label="Cargo">{lead.cargo}</Info>
            <Info label="E-mail">{lead.email && <a href={`mailto:${lead.email}`}>{lead.email}</a>}</Info>
            <Info label="Telefone">{lead.telefone && <a href={whatsappUrl(lead.telefone)} target="_blank" rel="noopener noreferrer">{lead.telefone} <Icon name="arrow-up-right-from-square"/></a>}</Info>
            <Info label="Site">{lead.url_site && <a href={/^https?:/.test(lead.url_site) ? lead.url_site : `https://${lead.url_site}`} target="_blank" rel="noopener noreferrer">{lead.url_site}</a>}</Info>
            <Info label="Valor estimado">{lead.valor_estimado != null && Number(lead.valor_estimado).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})}</Info>
            <Info label="Score">{`${lead.qualificacao_score || 0}/100`}</Info>
          </dl>
          {lead.mensagem && (
            <blockquote className="lv3-message"><Icon name="quote-left"/>{decode(lead.mensagem)}</blockquote>
          )}
          <details className="lv3-details">
            <summary>Origem e campanha</summary>
            <dl className="lv3-infos">
              <Info label="Fonte">{lead.fonte}</Info>
              <Info label="Origem">{lead.origem}</Info>
              <Info label="Canal">{lead.canal}</Info>
              <Info label="Página">{lead.pagina_origem}</Info>
              <Info label="UTM source">{lead.utm_source}</Info>
              <Info label="UTM campaign">{lead.utm_campaign}</Info>
            </dl>
          </details>
          {lead.notas_internas && <p className="lv3-notes"><strong>Notas internas:</strong> {lead.notas_internas}</p>}
        </section>

        <Contacts api={api} leadId={lead.id} contacts={contacts} onChanged={onChanged} notify={notify}/>
      </div>
    </section>
  );
}
