import React, {useState} from 'react';
import {Button, Empty, Field, Icon, decode, linkedinSearchUrl, whatsappUrl} from './ui.jsx';

// Papéis que o Golden Circle precisa cobrir em cada conta.
const COVERAGE = [
  {value: 'marketing', label: 'Marketing'},
  {value: 'midia', label: 'Mídia'},
  {value: 'criacao', label: 'Criação'},
  {value: 'diretoria', label: 'Diretoria'},
];
const EMPTY_CONTACT = {nome: '', cargo: '', email: '', telefone: ''};
const SOURCE_LABEL = {apollo: 'Apollo', pesquisa_web: 'Web', site: 'Site', manual: 'Manual', import: 'Importação'};
const FREE_EMAIL = new Set(['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'yahoo.com.br', 'bol.com.br', 'uol.com.br', 'terra.com.br', 'icloud.com', 'live.com']);
const hostOf = url => { if (!url) return ''; try { return new URL(/^https?:/.test(url) ? url : `http://${url}`).hostname.replace(/^www\./, ''); } catch { return ''; } };
const corporateDomain = email => { const d = String(email || '').split('@')[1]?.toLowerCase() || ''; return d && !FREE_EMAIL.has(d) ? d : ''; };

/** "GABRIELA MARTINS" → "Gabriela Martins" (só quando o texto vem todo em maiúsculas). */
function pretty(text) {
  const value = decode(text || '').trim();
  if (!value || value !== value.toUpperCase() || !/[A-ZÀ-Ý]/.test(value)) return value;
  return value.toLowerCase().replace(/(^|[\s-])(\p{L})/gu, (_, sep, ch) => sep + ch.toUpperCase())
    .replace(/\b(De|Da|Do|Das|Dos|E)\b/g, w => w.toLowerCase());
}

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

function emailFoundMessage(r) {
  if (r.encontrou === false) return r.motivo || 'Não achei o e-mail.';
  const fonte = r.metodo === 'padrao_contatos' ? 'padrão dos contatos da empresa' : 'e-mails públicos do domínio';
  return `E-mail sugerido: ${r.email} (${fonte}). Confira antes de enviar.`;
}

function Person({boot, api, leadId, contact: c, empresa, notify, onChanged}) {
  const [busy, setBusy] = useState('');
  const [linkedin, setLinkedin] = useState(null);
  const nome = pretty(c.nome);
  const run = (key, fn, done) => async () => {
    setBusy(key);
    try {
      const r = await fn();
      if (done) notify(typeof done === 'function' ? done(r) : done, r?.encontrou === false ? 'error' : 'success');
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const setProfile = campo => event => run(campo, () => api.updateProfile(c.id, {[campo]: event.target.value || null}))();
  const saveLinkedin = event => {
    event.preventDefault();
    run('linkedin', () => api.updateProfile(c.id, {linkedin_url: linkedin}), 'LinkedIn salvo.')().then(() => setLinkedin(null));
  };
  const palpite = c.email && c.email_status === 'arriscado';

  return (
    <li className="lv3-person">
      <div className="lv3-person__head">
        <div className="lv3-person__avatar" aria-hidden="true">{nome.slice(0, 1).toUpperCase()}</div>
        <div className="lv3-person__id">
          <div className="lv3-person__name">
            <span>{nome}</span>
            {c.is_principal && <span className="lv3-chip lv3-chip--brand lv3-chip--tiny">Principal</span>}
            {c.origem_dado && SOURCE_LABEL[c.origem_dado] && <span className="lv3-chip lv3-chip--neutral lv3-chip--tiny">{SOURCE_LABEL[c.origem_dado]}</span>}
          </div>
          <div className="lv3-person__role">{pretty(c.cargo || c.departamento) || 'Cargo não informado'}</div>
        </div>
        <div className="lv3-person__actions">
          {c.linkedin_url
            ? <a className="lv3-iconbtn" href={c.linkedin_url} target="_blank" rel="noopener noreferrer" title="Abrir perfil no LinkedIn" aria-label={`LinkedIn de ${nome}`}><Icon name="arrow-up-right-from-square"/></a>
            : <a className="lv3-iconbtn" href={linkedinSearchUrl(nome.replace(/\*/g, ''), empresa)} target="_blank" rel="noopener noreferrer" title="Procurar no LinkedIn" aria-label={`Procurar ${nome} no LinkedIn`}><Icon name="magnifying-glass"/></a>}
          {!c.is_principal && (
            <button type="button" className="lv3-iconbtn" title="Tornar principal" aria-label={`Tornar ${nome} principal`}
              onClick={run('primary', () => api.makePrimary(leadId, c.id), 'Contato principal atualizado.')}><Icon name="star"/></button>
          )}
          <button type="button" className="lv3-iconbtn lv3-iconbtn--danger" title="Remover" aria-label={`Remover ${nome}`}
            onClick={() => { if (window.confirm(`Remover ${nome} deste lead?`)) run('remove', () => api.removeContact(c.id), 'Contato removido.')(); }}>
            <Icon name="trash"/>
          </button>
        </div>
      </div>

      <div className="lv3-person__contact">
        {c.email ? (
          <a href={`mailto:${c.email}`} className="lv3-person__email">
            <Icon name="envelope"/>{String(c.email).toLowerCase()}
            {c.email_status === 'valido' && <Icon name="circle-check" className="lv3-ok"/>}
            {palpite && <span className="lv3-chip lv3-chip--warning lv3-chip--tiny" title="Montado pelo padrão da empresa; confira antes de enviar">palpite</span>}
          </a>
        ) : (
          <span className="lv3-person__noemail">
            <Button size="xs" variant="primary" icon="wand-magic-sparkles" disabled={!!busy}
              onClick={run('find', () => api.findEmail(c.id), emailFoundMessage)}>
              {busy === 'find' ? 'Procurando…' : 'Achar e-mail'}
            </Button>
            {boot.fontes.apollo && (
              <button type="button" className="lv3-link lv3-link--muted" disabled={!!busy} title="Último recurso: consome 1 crédito do Apollo"
                onClick={run('reveal', () => api.revealContact(c.id), r => r.encontrou_email ? 'E-mail encontrado no Apollo.' : 'O Apollo não tem e-mail para esta pessoa.')}>
                {busy === 'reveal' ? 'Consultando Apollo…' : 'Apollo (1 crédito)'}
              </button>
            )}
          </span>
        )}
        {c.telefone && <a href={whatsappUrl(c.telefone)} target="_blank" rel="noopener noreferrer"><Icon name="phone"/>{c.telefone}</a>}
        {!c.linkedin_url && linkedin === null && <button type="button" className="lv3-link" onClick={() => setLinkedin('')}>Colar LinkedIn</button>}
      </div>

      {linkedin !== null && (
        <form className="lv3-inline-form" onSubmit={saveLinkedin}>
          <input className="lv3-input lv3-input--sm" type="url" placeholder="https://www.linkedin.com/in/…" value={linkedin} onChange={event => setLinkedin(event.target.value)} autoFocus/>
          <Button size="sm" variant="primary" type="submit" disabled={!!busy}>Salvar</Button>
          <Button size="sm" onClick={() => setLinkedin(null)}>Cancelar</Button>
        </form>
      )}

      <div className="lv3-person__profile">
        {[['papel', 'Área', boot.papeis], ['senioridade', 'Nível', boot.senioridades], ['influencia', 'Influência', boot.influencias]].map(([campo, label, opcoes]) => (
          <label key={campo} className={`lv3-pill-select ${c[campo] ? 'is-set' : ''}`}>
            <span>{label}</span>
            <select value={c[campo] || ''} onChange={setProfile(campo)} disabled={!!busy} aria-label={`${label} de ${nome}`}>
              <option value="">—</option>
              {opcoes.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </label>
        ))}
      </div>
    </li>
  );
}

function Discovery({boot, api, lead, candidates, onChanged, notify, onEditCompany}) {
  const [busy, setBusy] = useState('');
  const empresa = decode(lead.empresa || lead.nome);
  // Mesma regra do backend (_lead_para_busca): domínio, senão site, senão e-mail corporativo.
  const dominio = lead.dominio || hostOf(lead.url_site) || corporateDomain(lead.email);
  const papelLabel = value => boot.papeis.find(p => p.value === value)?.label;
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
  const addAll = async () => {
    setBusy('all');
    let ok = 0;
    for (const k of candidates) {
      try { await api.approveCandidate(k.id, false); ok += 1; } catch { /* segue com os demais */ }
    }
    notify(`${ok} ${ok === 1 ? 'pessoa adicionada' : 'pessoas adicionadas'}. Use "Achar e-mails" em Pessoas.`);
    setBusy('');
    onChanged();
  };

  return (
    <section className="lv3-section">
      <header className="lv3-section__head">
        <h3>Encontrar pessoas {candidates.length > 0 && <span className="lv3-count">{candidates.length}</span>}</h3>
        <a className="lv3-btn lv3-btn--ghost lv3-btn--sm" href={linkedinSearchUrl(empresa, 'marketing')} target="_blank" rel="noopener noreferrer">
          <Icon name="arrow-up-right-from-square"/><span>LinkedIn</span>
        </a>
      </header>
      <div className="lv3-discovery__bar">
        <Button icon="globe" variant="secondary" onClick={discover('web')} disabled={!!busy || !boot.fontes.web}
          title={!boot.fontes.web ? 'Cadastre a chave do Firecrawl em Integrações' : 'Perfis públicos do LinkedIn Brasil (Firecrawl)'}>
          {busy === 'web' ? 'Buscando…' : 'Buscar perfis públicos'}
        </Button>
        <Button icon="address-book" variant="ghost" onClick={discover('apollo')} disabled={!!busy || !boot.fontes.apollo || !dominio}
          title={!boot.fontes.apollo ? 'Cadastre a chave do Apollo em Integrações' : !dominio ? 'Preencha o domínio da empresa' : 'Busca no Apollo (não gasta crédito)'}>
          {busy === 'apollo' ? 'Buscando…' : 'Buscar no Apollo'}
        </Button>
      </div>
      <p className="lv3-muted lv3-help">Marketing, mídia, criação e diretoria. Buscar não gasta crédito; ninguém vira contato sem sua aprovação.</p>
      {!dominio && (
        <p className="lv3-hint"><Icon name="circle-info"/>Sem domínio, o Apollo e o "Achar e-mail" não funcionam. <button type="button" className="lv3-link" onClick={onEditCompany}>Preencher domínio</button></p>
      )}

      {candidates.length > 0 && (
        <>
          <div className="lv3-candidates__head">
            <span>{candidates.length} para revisar</span>
            <button type="button" className="lv3-link" onClick={addAll} disabled={!!busy}>{busy === 'all' ? 'Adicionando…' : 'Adicionar todos'}</button>
          </div>
          <ul className="lv3-candidates">
            {candidates.map(k => (
              <li key={k.id} className="lv3-candidate">
                <div className="lv3-candidate__body">
                  <div className="lv3-candidate__name">
                    <span>{pretty(k.nome)}</span>
                    {k.papel_sugerido && k.papel_sugerido !== 'outro' && <span className="lv3-chip lv3-chip--brand lv3-chip--tiny">{papelLabel(k.papel_sugerido)}</span>}
                    <span className="lv3-chip lv3-chip--neutral lv3-chip--tiny">{k.provedor === 'apollo' ? 'Apollo' : 'Web'}</span>
                  </div>
                  <div className="lv3-candidate__role" title={k.cargo || ''}>
                    {pretty(k.cargo) || 'Cargo não informado'}
                    {k.linkedin_url && <a href={k.linkedin_url} target="_blank" rel="noopener noreferrer" aria-label="Abrir LinkedIn"> <Icon name="arrow-up-right-from-square"/></a>}
                  </div>
                </div>
                <div className="lv3-candidate__actions">
                  <Button size="xs" variant="primary" icon="check" disabled={!!busy} onClick={act(`a${k.id}`, () => api.approveCandidate(k.id, false), 'Pessoa adicionada.')}>Adicionar</Button>
                  {k.provedor === 'apollo' && k.payload?.has_email && (
                    <button type="button" className="lv3-link lv3-link--muted" disabled={!!busy} title="Último recurso: consome 1 crédito do Apollo"
                      onClick={act(`r${k.id}`, () => api.approveCandidate(k.id, true), r => r.email ? `Adicionado com e-mail ${r.email}.` : 'Adicionado (o Apollo não liberou e-mail).')}>
                      + e-mail Apollo
                    </button>
                  )}
                  <button type="button" className="lv3-iconbtn" title="Descartar" aria-label={`Descartar ${pretty(k.nome)}`} disabled={!!busy}
                    onClick={act(`d${k.id}`, () => api.discardCandidate(k.id), 'Descartado.')}><Icon name="xmark"/></button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export function People({boot, api, lead, contacts, candidates, onChanged, notify, onEditCompany}) {
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [bulk, setBulk] = useState('');
  const set = key => event => setDraft(d => ({...d, [key]: event.target.value}));
  const empresa = decode(lead.empresa || lead.nome);
  const semEmail = contacts.filter(c => !c.email);

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
  const findAll = async () => {
    let achados = 0;
    let motivo = '';
    for (const [i, c] of semEmail.entries()) {
      setBulk(`${i + 1}/${semEmail.length}`);
      try {
        const r = await api.findEmail(c.id);
        if (r.encontrou) achados += 1;
        else {
          motivo = r.motivo || motivo;
          if (r.nivel === 'empresa') break; // sem domínio, MX ou padrão: as próximas pessoas falhariam igual
        }
      } catch (error) { motivo = error.message; break; }
    }
    setBulk('');
    notify(achados ? `${achados} de ${semEmail.length} e-mails sugeridos pelo padrão da empresa. Confira antes de enviar.` : (motivo || 'Nenhum e-mail encontrado.'), achados ? 'success' : 'error');
    onChanged();
  };

  return (
    <>
      <section className="lv3-section">
        <header className="lv3-section__head">
          <h3>Pessoas <span className="lv3-count">{contacts.length}</span></h3>
          <div className="lv3-section__tools">
            {semEmail.length > 0 && (
              <Button size="sm" variant="ghost" icon="wand-magic-sparkles" onClick={findAll} disabled={!!bulk}>
                {bulk ? `Procurando ${bulk}…` : `Achar e-mails (${semEmail.length})`}
              </Button>
            )}
            {!draft && <Button size="sm" icon="user-plus" onClick={() => setDraft(EMPTY_CONTACT)}>Adicionar</Button>}
          </div>
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
            {contacts.map(c => <Person key={c.id} boot={boot} api={api} leadId={lead.id} contact={c} empresa={empresa} notify={notify} onChanged={onChanged}/>)}
          </ul>
        )}
      </section>
      <Discovery boot={boot} api={api} lead={lead} candidates={candidates} onChanged={onChanged} notify={notify} onEditCompany={onEditCompany}/>
    </>
  );
}
