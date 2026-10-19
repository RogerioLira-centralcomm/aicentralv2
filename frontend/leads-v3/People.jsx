import React, {useState} from 'react';
import {Button, Chip, Empty, Field, Icon, decode, linkedinSearchUrl, whatsappUrl} from './ui.jsx';

// Papéis que o Golden Circle precisa cobrir em cada conta.
const COVERAGE = [
  {value: 'marketing', label: 'Marketing'},
  {value: 'midia', label: 'Mídia'},
  {value: 'criacao', label: 'Criação'},
  {value: 'diretoria', label: 'Diretoria'},
];
const EMPTY_CONTACT = {nome: '', cargo: '', email: '', telefone: ''};
const SOURCE_LABEL = {apollo: 'Apollo', pesquisa_web: 'Web', site: 'Site', manual: 'Manual', import: 'Importação'};

function Coverage({contacts}) {
  return (
    <div className="lv3-coverage" aria-label="Cobertura do comitê de compra">
      {COVERAGE.map(p => {
        const n = contacts.filter(c => c.papel === p.value).length;
        return (
          <span key={p.value} className={`lv3-coverage__item ${n ? 'is-on' : ''}`} title={n ? `${n} em ${p.label}` : `Ninguém de ${p.label} ainda`}>
            <Icon name={n ? 'circle-check' : 'circle'}/>{p.label}{n > 1 ? ` · ${n}` : ''}
          </span>
        );
      })}
    </div>
  );
}

function Person({boot, api, leadId, contact: c, empresa, fontes, notify, onChanged}) {
  const [busy, setBusy] = useState('');
  const [linkedin, setLinkedin] = useState(null);
  const nome = decode(c.nome);
  const run = (key, fn, done) => async () => {
    setBusy(key);
    try { const r = await fn(); if (done) notify(typeof done === 'function' ? done(r) : done); onChanged(); }
    catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const setProfile = campo => event => run(campo, () => api.updateProfile(c.id, {[campo]: event.target.value || null}))();
  const saveLinkedin = event => {
    event.preventDefault();
    run('linkedin', () => api.updateProfile(c.id, {linkedin_url: linkedin}), 'LinkedIn salvo.')().then(() => setLinkedin(null));
  };

  return (
    <li className="lv3-person">
      <div className="lv3-person__avatar" aria-hidden="true">{nome.slice(0, 1).toUpperCase()}</div>
      <div className="lv3-person__body">
        <div className="lv3-person__name">
          {nome}
          {c.is_principal && <span className="lv3-chip lv3-chip--brand">Principal</span>}
          {c.origem_dado && SOURCE_LABEL[c.origem_dado] && <span className="lv3-chip lv3-chip--neutral lv3-chip--tiny">{SOURCE_LABEL[c.origem_dado]}</span>}
        </div>
        <div className="lv3-person__role">{c.cargo || c.departamento || 'Cargo não informado'}</div>

        <div className="lv3-person__profile">
          <select className="lv3-select lv3-select--xs" value={c.papel || ''} onChange={setProfile('papel')} disabled={!!busy} aria-label={`Área de ${nome}`}>
            <option value="">Área…</option>
            {boot.papeis.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <select className="lv3-select lv3-select--xs" value={c.senioridade || ''} onChange={setProfile('senioridade')} disabled={!!busy} aria-label={`Senioridade de ${nome}`}>
            <option value="">Nível…</option>
            {boot.senioridades.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <select className="lv3-select lv3-select--xs" value={c.influencia || ''} onChange={setProfile('influencia')} disabled={!!busy} aria-label={`Influência de ${nome}`}>
            <option value="">Influência…</option>
            {boot.influencias.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>

        <div className="lv3-person__links">
          {c.email && <a href={`mailto:${c.email}`}><Icon name="envelope"/>{c.email}{c.email_status === 'valido' && <Icon name="circle-check" className="lv3-ok"/>}</a>}
          {c.telefone && <a href={whatsappUrl(c.telefone)} target="_blank" rel="noopener noreferrer"><Icon name="phone"/>{c.telefone}</a>}
          {c.linkedin_url
            ? <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer"><Icon name="arrow-up-right-from-square"/>Perfil no LinkedIn</a>
            : <a href={linkedinSearchUrl(nome.replace(/\*/g, ''), empresa)} target="_blank" rel="noopener noreferrer"><Icon name="magnifying-glass"/>Achar no LinkedIn</a>}
          {!c.linkedin_url && linkedin === null && <button type="button" className="lv3-link" onClick={() => setLinkedin('')}>Colar link</button>}
        </div>
        {linkedin !== null && (
          <form className="lv3-inline-form" onSubmit={saveLinkedin}>
            <input className="lv3-input lv3-input--sm" type="url" placeholder="https://www.linkedin.com/in/…" value={linkedin} onChange={event => setLinkedin(event.target.value)} autoFocus/>
            <Button size="sm" variant="primary" type="submit" disabled={!!busy}>Salvar</Button>
            <Button size="sm" onClick={() => setLinkedin(null)}>Cancelar</Button>
          </form>
        )}
        {!c.email && fontes.apollo && (
          <Button size="sm" variant="ghost" icon="envelope-open-text" disabled={!!busy} className="lv3-person__reveal"
            onClick={run('reveal', () => api.revealContact(c.id), r => r.encontrou_email ? 'E-mail encontrado no Apollo.' : 'O Apollo não tem e-mail para esta pessoa.')}>
            {busy === 'reveal' ? 'Buscando…' : 'Buscar e-mail no Apollo (1 crédito)'}
          </Button>
        )}
      </div>
      <div className="lv3-person__actions">
        {!c.is_principal && (
          <button type="button" className="lv3-iconbtn" title="Tornar principal" aria-label={`Tornar ${nome} principal`}
            onClick={run('primary', () => api.makePrimary(leadId, c.id), 'Contato principal atualizado.')}><Icon name="star"/></button>
        )}
        <button type="button" className="lv3-iconbtn lv3-iconbtn--danger" title="Remover" aria-label={`Remover ${nome}`}
          onClick={() => { if (window.confirm(`Remover ${nome} deste lead?`)) run('remove', () => api.removeContact(c.id), 'Contato removido.')(); }}>
          <Icon name="trash"/>
        </button>
      </div>
    </li>
  );
}

function Discovery({boot, api, lead, candidates, onChanged, notify, onEditCompany}) {
  const [busy, setBusy] = useState('');
  const empresa = decode(lead.empresa || lead.nome);
  const dominio = lead.dominio || '';
  const discover = fonte => async () => {
    setBusy(fonte);
    try {
      const r = await api.discover(lead.id, fonte);
      notify(r.novos ? `${r.novos} ${r.novos === 1 ? 'pessoa nova' : 'pessoas novas'} para revisar.` : `Nada novo (${r.encontrados} encontradas, já revisadas ou cadastradas).`);
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const act = (key, fn, done) => async () => {
    setBusy(key);
    try { const r = await fn(); notify(typeof done === 'function' ? done(r) : done); onChanged(); }
    catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };

  return (
    <section className="lv3-section">
      <header className="lv3-section__head">
        <h3>Encontrar pessoas {candidates.length > 0 && <span className="lv3-count">{candidates.length}</span>}</h3>
        <a className="lv3-btn lv3-btn--ghost lv3-btn--sm" href={linkedinSearchUrl(empresa, 'marketing')} target="_blank" rel="noopener noreferrer">
          <Icon name="arrow-up-right-from-square"/><span>Buscar no LinkedIn</span>
        </a>
      </header>
      <p className="lv3-muted lv3-help">Foco em marketing, mídia, criação e diretoria. A busca não gasta crédito; nada vira contato sem sua aprovação.</p>
      <div className="lv3-discovery__actions">
        <Button icon="address-book" onClick={discover('apollo')} disabled={!!busy || !boot.fontes.apollo || !dominio}
          title={!boot.fontes.apollo ? 'Cadastre a chave do Apollo em Integrações' : !dominio ? 'Preencha o domínio da empresa' : ''}>
          {busy === 'apollo' ? 'Buscando no Apollo…' : 'Buscar no Apollo'}
        </Button>
        <Button icon="globe" onClick={discover('web')} disabled={!!busy || !boot.fontes.web}
          title={!boot.fontes.web ? 'Cadastre a chave do Firecrawl em Integrações' : ''}>
          {busy === 'web' ? 'Buscando na web…' : 'Buscar perfis públicos'}
        </Button>
      </div>
      {!dominio && (
        <p className="lv3-hint"><Icon name="circle-info"/>Sem domínio, o Apollo não busca. <button type="button" className="lv3-link" onClick={onEditCompany}>Preencher domínio</button></p>
      )}

      {candidates.length > 0 && (
        <ul className="lv3-candidates">
          {candidates.map(k => (
            <li key={k.id} className="lv3-candidate">
              <div className="lv3-candidate__body">
                <div className="lv3-person__name">
                  {decode(k.nome)}
                  <span className="lv3-chip lv3-chip--neutral lv3-chip--tiny">{k.provedor === 'apollo' ? 'Apollo' : 'Web'}</span>
                  {k.papel_sugerido && k.papel_sugerido !== 'outro' && <Chip tone="brand">{boot.papeis.find(p => p.value === k.papel_sugerido)?.label}</Chip>}
                </div>
                <div className="lv3-person__role">{k.cargo || 'Cargo não informado'}</div>
                <div className="lv3-person__links">
                  {k.linkedin_url && <a href={k.linkedin_url} target="_blank" rel="noopener noreferrer"><Icon name="arrow-up-right-from-square"/>LinkedIn</a>}
                  {k.provedor === 'apollo' && <span className="lv3-muted">{k.payload?.has_email ? 'Apollo tem e-mail' : 'Sem e-mail no Apollo'}</span>}
                </div>
              </div>
              <div className="lv3-candidate__actions">
                {k.provedor === 'apollo' && k.payload?.has_email ? (
                  <>
                    <Button size="sm" variant="primary" icon="check" disabled={!!busy}
                      onClick={act(`a${k.id}`, () => api.approveCandidate(k.id, true), r => r.email ? `Adicionado com e-mail ${r.email}.` : 'Adicionado (o Apollo não liberou e-mail).')}>
                      Adicionar + e-mail (1 crédito)
                    </Button>
                    <Button size="sm" disabled={!!busy} onClick={act(`s${k.id}`, () => api.approveCandidate(k.id, false), 'Adicionado sem e-mail.')}>Só adicionar</Button>
                  </>
                ) : (
                  <Button size="sm" variant="primary" icon="check" disabled={!!busy} onClick={act(`a${k.id}`, () => api.approveCandidate(k.id, false), 'Pessoa adicionada.')}>Adicionar</Button>
                )}
                <button type="button" className="lv3-iconbtn" title="Descartar" aria-label={`Descartar ${decode(k.nome)}`} disabled={!!busy}
                  onClick={act(`d${k.id}`, () => api.discardCandidate(k.id), 'Descartado.')}><Icon name="xmark"/></button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function People({boot, api, lead, contacts, candidates, onChanged, notify, onEditCompany}) {
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const set = key => event => setDraft(d => ({...d, [key]: event.target.value}));
  const empresa = decode(lead.empresa || lead.nome);

  const save = async event => {
    event.preventDefault();
    if (!draft.nome.trim()) return notify('Informe o nome do contato.', 'error');
    setSaving(true);
    try {
      await api.addContact(lead.id, draft);
      setDraft(null);
      notify('Contato adicionado.');
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setSaving(false); }
  };

  return (
    <>
      <section className="lv3-section">
        <header className="lv3-section__head">
          <h3>Pessoas <span className="lv3-count">{contacts.length}</span></h3>
          {!draft && <Button size="sm" icon="user-plus" onClick={() => setDraft(EMPTY_CONTACT)}>Adicionar pessoa</Button>}
        </header>
        <Coverage contacts={contacts}/>

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
          <Empty icon="users" title="Nenhuma pessoa cadastrada">Use "Encontrar pessoas" abaixo ou adicione manualmente.</Empty>
        ) : (
          <ul className="lv3-people">
            {contacts.map(c => <Person key={c.id} boot={boot} api={api} leadId={lead.id} contact={c} empresa={empresa} fontes={boot.fontes} notify={notify} onChanged={onChanged}/>)}
          </ul>
        )}
      </section>
      <Discovery boot={boot} api={api} lead={lead} candidates={candidates} onChanged={onChanged} notify={notify} onEditCompany={onEditCompany}/>
    </>
  );
}
