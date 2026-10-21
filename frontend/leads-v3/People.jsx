import React, {useEffect, useState} from 'react';
import {Button, Empty, Field, Icon, MoreMenu, decode, formatDate, linkedinSearchUrl, prettyName as pretty, whatsappUrl} from './ui.jsx';
import {FlowSelect, sugerirFluxo} from './Fluxos.jsx';
import {ManageCadence, SwitchLeadFlow} from './CadenceControls.jsx';

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

const CANAL_LABEL = {email: 'e-mail', whatsapp: 'WhatsApp', linkedin: 'LinkedIn', telefone: 'ligação'};

/** Linha da cadência da pessoa: passo, próximo toque e ações (o envio acontece na Operação). */
function CadenceLine({api, contact, inscricao, fluxos = [], notify, onChanged}) {
  const [busy, setBusy] = useState(false);
  const [escolha, setEscolha] = useState(null); // null = fechado; id do fluxo enquanto escolhe
  const [gerir, setGerir] = useState(false);
  const sugerido = sugerirFluxo(fluxos, contact.papel);
  const painel = gerir && inscricao && (
    <ManageCadence api={api} inscricao={inscricao} nome={pretty(contact.nome)} fluxos={fluxos} notify={notify}
      onClose={() => setGerir(false)} onDone={onChanged}/>
  );
  const gerenciar = (
    <button type="button" className="lv3-link" disabled={busy || !inscricao?.passos} onClick={() => setGerir(true)} title="Mudar de passo, adiar ou trocar de fluxo">Gerenciar</button>
  );
  const run = (fn, done) => async () => {
    setBusy(true);
    try { await fn(); notify(done); onChanged(); } catch (error) { notify(error.message, 'error'); } finally { setBusy(false); }
  };
  const abrir = () => setEscolha(String(sugerido?.id || ''));
  const iniciar = async () => {
    await run(() => api.enrollContact(contact.id, Number(escolha) || null), 'Cadência iniciada. O primeiro passo já está na Operação.')();
    setEscolha(null);
  };
  // Escolher o fluxo pelo momento da pessoa: nova, já em conversa, conta parada ou veio do site.
  const picker = escolha !== null && (
    <div className="lv3-cadence lv3-cadence--pick">
      <FlowSelect fluxos={fluxos} value={escolha} onChange={setEscolha} sugerido={sugerido} disabled={busy}/>
      <Button size="xs" variant="primary" icon="play" onClick={iniciar} disabled={busy || !escolha}>Iniciar</Button>
      <button type="button" className="lv3-link lv3-link--muted" onClick={() => setEscolha(null)}>Cancelar</button>
    </div>
  );
  if (!inscricao) {
    return picker || (
      <div className="lv3-cadence lv3-cadence--none">
        <Button size="xs" icon="play" onClick={abrir} disabled={busy || !fluxos.length} title="Escolher o fluxo e iniciar a cadência">Cadência</Button>
        <span className="lv3-muted">{sugerido ? `sugerido: ${sugerido.nome}` : 'escolha o fluxo pelo momento da pessoa'}</span>
      </div>
    );
  }
  const passo = inscricao.passo || {};
  const etapa = `passo ${Math.min(inscricao.passo_atual + 1, inscricao.total)}/${inscricao.total}`;
  if (inscricao.status === 'ativa') {
    return (
      <div className="lv3-cadence is-active">
        <Icon name="circle-play"/>
        <span><strong>{inscricao.cadencia}</strong> · {etapa} · próximo: {CANAL_LABEL[passo.canal] || passo.canal} {inscricao.proxima_em ? `em ${formatDate(inscricao.proxima_em).slice(0, 10)}` : ''}</span>
        {gerenciar}
        <button type="button" className="lv3-link lv3-link--muted" disabled={busy} onClick={run(() => api.stepAction(inscricao.id, 'pausar'), 'Cadência pausada.')}>Pausar</button>
        <button type="button" className="lv3-link lv3-link--muted" disabled={busy} onClick={() => { if (window.confirm('Encerrar a cadência desta pessoa?')) run(() => api.stepAction(inscricao.id, 'cancelar'), 'Cadência encerrada.')(); }}>Encerrar</button>
        {painel}
      </div>
    );
  }
  if (inscricao.status === 'pausada') {
    return (
      <div className="lv3-cadence is-paused">
        <Icon name="circle-pause"/>
        <span><strong>{inscricao.cadencia}</strong> pausada · {etapa}{inscricao.motivo_parada ? ` · ${inscricao.motivo_parada}` : ''}</span>
        <button type="button" className="lv3-link" disabled={busy} onClick={run(() => api.stepAction(inscricao.id, 'retomar'), 'Cadência retomada.')}>Retomar</button>
        {gerenciar}
        {painel}
      </div>
    );
  }
  const fim = {respondeu: 'respondeu', concluida: 'concluída', cancelada: 'encerrada', erro: 'com erro'}[inscricao.status] || inscricao.status;
  return (
    <div className={`lv3-cadence ${inscricao.status === 'respondeu' ? 'is-replied' : ''}`}>
      <Icon name={inscricao.status === 'respondeu' ? 'reply' : 'circle-check'}/>
      <span><strong>{inscricao.cadencia}</strong> {fim}{inscricao.motivo_parada && inscricao.status === 'respondeu' ? `: ${inscricao.motivo_parada}` : ''}</span>
      <button type="button" className="lv3-link" disabled={busy} onClick={abrir}>Nova cadência</button>
      {picker}
    </div>
  );
}

function emailFoundMessage(r) {
  if (r.encontrou === false) return r.motivo || 'Não achei o e-mail.';
  const fonte = r.metodo === 'padrao_contatos' ? 'padrão dos contatos da empresa' : 'e-mails públicos do domínio';
  return `E-mail sugerido: ${r.email} (${fonte}). Confira antes de enviar.`;
}

function Person({boot, api, leadId, contact: c, empresa, inscricao, fluxos, notify, onChanged}) {
  const [busy, setBusy] = useState('');
  const [linkedin, setLinkedin] = useState(null);
  const [edit, setEdit] = useState(null);
  const nome = pretty(c.nome);
  const abrirEdicao = (limpar = {}) => setEdit({nome: pretty(c.nome), cargo: pretty(c.cargo), email: String(c.email || '').toLowerCase(), telefone: c.telefone || '', ...limpar});
  const salvarEdicao = async event => {
    event.preventDefault();
    if (!edit.nome.trim()) return notify('Informe o nome.', 'error');
    await run('edit', () => api.updateContact(c.id, edit), 'Pessoa atualizada.')();
    setEdit(null);
  };
  const run = (key, fn, done) => async () => {
    setBusy(key);
    try {
      const r = await fn();
      const falhou = r?.encontrou === false || r?.encontrou_email === false;
      if (done) notify(typeof done === 'function' ? done(r) : done, falhou ? 'error' : 'success');
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const setProfile = campo => event => run(campo, () => api.updateProfile(c.id, {[campo]: event.target.value || null}))();
  const saveLinkedin = event => {
    event.preventDefault();
    run('linkedin', () => api.updateProfile(c.id, {linkedin_url: linkedin}), 'LinkedIn salvo.')().then(() => setLinkedin(null));
  };
  const palpite = c.email && c.email_status === 'arriscado';
  const revelar = run('reveal', () => api.revealContact(c.id), r => r.encontrou_email ? `E-mail verificado: ${r.email}.` : (r.motivo || 'O Apollo não tem e-mail para esta pessoa.'));
  const errado = (campo, valor) => () => {
    if (window.confirm(`${valor} não é de ${nome}? Ele sai da ficha (fica registrado no histórico) e você pode digitar o certo.`)) {
      run('wrong', () => api.wrongData(c.id, campo), `${campo === 'email' ? 'E-mail' : 'Celular'} retirado. Digite o certo em Editar.`)().then(() => abrirEdicao({[campo]: ''}));
    }
  };
  // Tudo que completa a ficha fica num menu só; a linha de contato mostra só o dado e a situação dele.
  const enriquecer = [
    !c.email && {icon: 'wand-magic-sparkles', label: 'Achar e-mail', hint: 'padrão da empresa, grátis', onClick: run('find', () => api.findEmail(c.id), emailFoundMessage)},
    boot.fontes.apollo && (!c.email || palpite) && {icon: 'envelope-circle-check', label: palpite ? 'Verificar e-mail no Apollo' : 'E-mail verificado (Apollo)', hint: '1 crédito', onClick: revelar},
    boot.fontes.apollo && !c.telefone && c.telefone_status !== 'pedido' && {icon: 'mobile-screen', label: 'Buscar celular (Apollo)', hint: c.telefone_status === 'sem_numero' ? 'o Apollo já disse que não tem; tentar de novo gasta créditos' : 'créditos de telefone, chega em minutos',
      onClick: () => { if (window.confirm(`Pedir o celular de ${nome} ao Apollo? Consome créditos de telefone do plano (mais que um e-mail).`)) run('phone', () => api.requestPhone(c.id), 'Celular pedido ao Apollo. Chega em alguns minutos.')(); }},
    !c.linkedin_url && {icon: 'link', label: 'Colar LinkedIn', onClick: () => setLinkedin('')},
    {icon: 'keyboard', label: 'Digitar e-mail ou celular', onClick: () => abrirEdicao()},
    c.email && {icon: 'envelope', label: 'E-mail está errado', danger: true, onClick: errado('email', String(c.email).toLowerCase())},
    c.telefone && {icon: 'phone-slash', label: 'Celular está errado', danger: true, onClick: errado('telefone', c.telefone)},
  ].filter(Boolean);

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
          <div className="lv3-person__role" title={pretty(c.cargo || c.departamento) || ''}>{pretty(c.cargo || c.departamento) || 'Cargo não informado'}</div>
        </div>
        <div className="lv3-person__actions">
          {c.linkedin_url
            ? <a className="lv3-iconbtn" href={c.linkedin_url} target="_blank" rel="noopener noreferrer" title="Abrir perfil no LinkedIn" aria-label={`LinkedIn de ${nome}`}><Icon name="arrow-up-right-from-square"/></a>
            : <a className="lv3-iconbtn" href={linkedinSearchUrl(nome.replace(/\*/g, ''), empresa)} target="_blank" rel="noopener noreferrer" title="Procurar no LinkedIn" aria-label={`Procurar ${nome} no LinkedIn`}><Icon name="magnifying-glass"/></a>}
          <MoreMenu trigger="icon" icon="wand-magic-sparkles" label={`Completar dados de ${nome}`} disabled={!!busy} items={enriquecer}/>
          <MoreMenu trigger="icon" label={`Mais ações de ${nome}`} disabled={!!busy} items={[
            {icon: 'pen', label: 'Editar', onClick: () => abrirEdicao()},
            !c.is_principal && {icon: 'star', label: 'Tornar principal', onClick: run('primary', () => api.makePrimary(leadId, c.id), 'Contato principal atualizado.')},
            {icon: 'trash', label: 'Remover', danger: true, onClick: () => { if (window.confirm(`Remover ${nome} deste lead?`)) run('remove', () => api.removeContact(c.id), 'Contato removido.')(); }},
          ].filter(Boolean)}/>
        </div>
      </div>

      {edit && (
        <form className="lv3-person__edit" onSubmit={salvarEdicao}>
          <div className="lv3-form__grid">
            <Field label="Nome"><input className="lv3-input lv3-input--sm" value={edit.nome} onChange={e => setEdit(f => ({...f, nome: e.target.value}))} required/></Field>
            <Field label="Cargo"><input className="lv3-input lv3-input--sm" value={edit.cargo} onChange={e => setEdit(f => ({...f, cargo: e.target.value}))}/></Field>
            <Field label="E-mail"><input className="lv3-input lv3-input--sm" type="email" value={edit.email} onChange={e => setEdit(f => ({...f, email: e.target.value}))}/></Field>
            <Field label="Telefone"><input className="lv3-input lv3-input--sm" value={edit.telefone} onChange={e => setEdit(f => ({...f, telefone: e.target.value}))}/></Field>
          </div>
          <div className="lv3-form__actions">
            <Button size="sm" onClick={() => setEdit(null)}>Cancelar</Button>
            <Button size="sm" variant="primary" type="submit" disabled={!!busy}>{busy === 'edit' ? 'Salvando…' : 'Salvar'}</Button>
          </div>
        </form>
      )}

      <div className="lv3-person__contact">
        {c.email ? (
          <a href={`mailto:${c.email}`} className="lv3-person__email" title={palpite ? 'Montado pelo padrão da empresa; confira antes de enviar' : String(c.email).toLowerCase()}>
            <Icon name="envelope"/><span>{String(c.email).toLowerCase()}</span>
            {c.email_status === 'valido' && <Icon name="circle-check" className="lv3-ok"/>}
            {palpite && <span className="lv3-chip lv3-chip--warning lv3-chip--tiny">palpite</span>}
          </a>
        ) : <span className="lv3-person__missing"><Icon name="envelope"/>{busy === 'find' || busy === 'reveal' ? 'procurando…' : 'sem e-mail'}</span>}
        {c.telefone ? (
          <a href={whatsappUrl(c.telefone)} target="_blank" rel="noopener noreferrer"><Icon name="phone"/>{c.telefone}</a>
        ) : c.telefone_status === 'pedido' ? (
          <span className="lv3-person__phonewait" title="O Apollo envia o número alguns minutos depois do pedido">
            <Icon name="hourglass-half"/>celular pedido<button type="button" className="lv3-link" onClick={onChanged}>atualizar</button>
          </span>
        ) : <span className="lv3-person__missing" title={c.telefone_status === 'sem_numero' ? 'O Apollo não tem celular desta pessoa' : ''}>
          <Icon name={c.telefone_status === 'sem_numero' ? 'phone-slash' : 'phone'}/>{c.telefone_status === 'sem_numero' ? 'Apollo sem celular' : 'sem celular'}
        </span>}
      </div>

      {linkedin !== null && (
        <form className="lv3-inline-form" onSubmit={saveLinkedin}>
          <input className="lv3-input lv3-input--sm" type="url" placeholder="https://www.linkedin.com/in/…" value={linkedin} onChange={event => setLinkedin(event.target.value)} autoFocus/>
          <Button size="sm" variant="primary" type="submit" disabled={!!busy}>Salvar</Button>
          <Button size="sm" onClick={() => setLinkedin(null)}>Cancelar</Button>
        </form>
      )}

      <div className="lv3-person__meta">
        <CadenceLine api={api} contact={c} inscricao={inscricao} fluxos={fluxos} notify={notify} onChanged={onChanged}/>
        <div className="lv3-person__profile">
          {[['papel', 'Área', boot.papeis], ['senioridade', 'Nível', boot.senioridades], ['influencia', 'Influência', boot.influencias]].map(([campo, label, opcoes]) => (
            <label key={campo} className={`lv3-pill-select ${c[campo] ? 'is-set' : ''}`}>
              <span>{label}</span>
              <select value={c[campo] || ''} onChange={setProfile(campo)} disabled={!!busy} aria-label={`${label} de ${nome}`} title={label}>
                <option value="">{label}</option>
                {opcoes.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </label>
          ))}
        </div>
      </div>
    </li>
  );
}

/** Pares de contatos que parecem a mesma pessoa (nome mascarado do Apollo, importação repetida, e-mail igual). */
function Duplicates({api, lead, contacts, notify, onChanged}) {
  const [pares, setPares] = useState([]);
  const [busy, setBusy] = useState(false);
  const chave = contacts.map(c => `${c.id}:${c.nome}:${c.email}`).join('|');
  useEffect(() => { api.duplicates(lead.id).then(setPares).catch(() => setPares([])); }, [api, lead.id, chave]);
  if (!pares.length) return null;
  const mesclar = (a, b) => async () => {
    setBusy(true);
    try { await api.mergeContacts(a.id, b.id); notify('Contatos mesclados. Histórico e cadências foram para uma ficha só.'); onChanged(); }
    catch (error) { notify(error.message, 'error'); } finally { setBusy(false); }
  };
  const rotulo = c => `${pretty(c.nome)}${c.email ? ` (${String(c.email).toLowerCase()})` : ''}`;
  return (
    <div className="lv3-dups" role="status">
      <p><Icon name="clone"/>{pares.length === 1 ? 'Parece haver uma pessoa repetida' : `Parece haver ${pares.length} pessoas repetidas`}</p>
      <ul>
        {pares.map(([a, b]) => (
          <li key={`${a.id}-${b.id}`}>
            <span>{rotulo(a)} <span className="lv3-muted">e</span> {rotulo(b)}</span>
            <Button size="xs" variant="primary" icon="code-merge" disabled={busy} onClick={mesclar(a, b)}>Mesclar</Button>
          </li>
        ))}
      </ul>
      <p className="lv3-muted">Fica a ficha mais completa; o histórico, as cadências e as mensagens das duas vão junto.</p>
    </div>
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
    for (const k of candidates.filter(c => !c.existente)) {
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
                  {k.existente && (
                    <p className="lv3-candidate__match"><Icon name="user-check"/>Já na base como <strong>{pretty(k.existente.nome)}</strong></p>
                  )}
                </div>
                <div className="lv3-candidate__actions">
                  {k.existente ? (
                    <Button size="xs" variant="primary" icon="code-merge" disabled={!!busy} title="Soma cargo, LinkedIn e nível do Apollo à ficha que já existe (não gasta crédito)"
                      onClick={act(`a${k.id}`, () => api.linkCandidate(k.id, false), `Dados somados a ${pretty(k.existente.nome)}.`)}>Completar ficha</Button>
                  ) : (
                    <Button size="xs" variant="primary" icon="check" disabled={!!busy} onClick={act(`a${k.id}`, () => api.approveCandidate(k.id, false), r => r.mesclado_com ? `Já existia: dados somados a ${pretty(r.mesclado_com)}.` : 'Pessoa adicionada.')}>Adicionar</Button>
                  )}
                  {k.provedor === 'apollo' && k.payload?.has_email && (
                    <button type="button" className="lv3-link lv3-link--muted" disabled={!!busy} title="Último recurso: consome 1 crédito do Apollo"
                      onClick={act(`r${k.id}`, () => api.approveCandidate(k.id, true), r => r.mesclado_com ? `Já existia: ${pretty(r.mesclado_com)} completado${r.email ? ` (e-mail ${r.email})` : ''}.` : r.email ? `Adicionado com e-mail ${r.email}.` : 'Adicionado (o Apollo não liberou e-mail).')}>
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

export function People({boot, api, lead, contacts, candidates, cadences = [], onChanged, notify, onEditCompany}) {
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [bulk, setBulk] = useState('');
  const [fluxos, setFluxos] = useState([]);
  const [fluxoTodos, setFluxoTodos] = useState(null); // null = fechado; '' = cada pessoa pela sua área
  const [trocarConta, setTrocarConta] = useState(false);
  useEffect(() => { api.cadenceModels().then(setFluxos).catch(() => setFluxos([])); }, [api]);
  const set = key => event => setDraft(d => ({...d, [key]: event.target.value}));
  const empresa = decode(lead.empresa || lead.nome);
  const semEmail = contacts.filter(c => !c.email);
  // Quem ainda não tem e-mail verificado (sem e-mail ou só palpite): onde o crédito do Apollo rende.
  const paraVerificar = contacts.filter(c => !c.email || c.email_status === 'arriscado');
  // Inscrição que importa por pessoa: a ativa/pausada; senão a mais recente (a API já ordena assim).
  const inscricaoDe = id => cadences.find(i => i.id_contato === id);
  const semCadencia = contacts.filter(c => !cadences.some(i => i.id_contato === c.id && ['ativa', 'pausada'].includes(i.status)));
  const emAndamento = cadences.filter(i => ['ativa', 'pausada'].includes(i.status)).length;
  const inscreverTodos = async () => {
    setBulk('cad');
    try {
      const r = await api.enrollLead(lead.id, Number(fluxoTodos) || null);
      setFluxoTodos(null);
      notify(r.inscritas ? `${r.inscritas} ${r.inscritas === 1 ? 'pessoa entrou' : 'pessoas entraram'} em cadência. Os passos aparecem na Operação.` : 'Todos já estão em cadência.');
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setBulk(''); }
  };

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
  const verificarTodos = async () => {
    const n = paraVerificar.length;
    if (!window.confirm(`Verificar no Apollo o e-mail de ${n} ${n === 1 ? 'pessoa' : 'pessoas'}? Usa até ${n} ${n === 1 ? 'crédito' : 'créditos'} de e-mail do plano (a cobrança exata depende do plano Apollo).`)) return;
    let achados = 0;
    let motivo = '';
    for (const [i, c] of paraVerificar.entries()) {
      setBulk(`apollo ${i + 1}/${n}`);
      try {
        const r = await api.revealContact(c.id);
        if (r.encontrou_email) achados += 1;
        else if (r.motivo && /cr[eé]dito|permite/i.test(r.motivo)) { motivo = r.motivo; break; } // plano travou: não insiste
      } catch (error) {
        motivo = error.message;
        if (/cr[eé]dito|chave|plano|limite/i.test(error.message)) break;
      }
    }
    setBulk('');
    notify(achados ? `${achados} de ${n} e-mails verificados no Apollo.${motivo ? ` Parou: ${motivo}` : ''}` : (motivo || 'O Apollo não encontrou e-mail para essas pessoas.'), achados ? 'success' : 'error');
    onChanged();
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
            {boot.fontes.apollo && paraVerificar.length > 0 && (
              <Button size="sm" variant="ghost" icon="envelope-circle-check" onClick={verificarTodos} disabled={!!bulk}
                title="E-mail verificado do Apollo para quem não tem e-mail ou só tem palpite (até 1 crédito por pessoa)">
                {String(bulk).startsWith('apollo') ? `Verificando ${String(bulk).slice(7)}…` : `Verificar e-mails no Apollo (${paraVerificar.length})`}
              </Button>
            )}
            {semCadencia.length > 0 && contacts.length > 0 && (
              fluxoTodos === null ? (
                <Button size="sm" variant="ghost" icon="route" onClick={() => setFluxoTodos('')} disabled={!!bulk || !fluxos.length}>
                  {`Cadência para todos (${semCadencia.length})`}
                </Button>
              ) : (
                <span className="lv3-cadence lv3-cadence--pick">
                  <select className="lv3-select lv3-select--sm" value={fluxoTodos} onChange={e => setFluxoTodos(e.target.value)} disabled={!!bulk} aria-label="Fluxo para todos">
                    <option value="">Cada pessoa no fluxo sugerido pela área</option>
                    {fluxos.map(f => <option key={f.id} value={f.id}>{f.nome}</option>)}
                  </select>
                  <Button size="sm" variant="primary" icon="play" onClick={inscreverTodos} disabled={!!bulk}>{bulk === 'cad' ? 'Inscrevendo…' : 'Iniciar'}</Button>
                  <button type="button" className="lv3-link lv3-link--muted" onClick={() => setFluxoTodos(null)}>Cancelar</button>
                </span>
              )
            )}
            {emAndamento > 0 && fluxos.length > 1 && (
              <Button size="sm" variant="ghost" icon="shuffle" onClick={() => setTrocarConta(true)} disabled={!!bulk} title="Encerrar as cadências em andamento e pôr todos em outro fluxo">
                {`Trocar fluxo da conta (${emAndamento})`}
              </Button>
            )}
            {trocarConta && (
              <SwitchLeadFlow api={api} leadId={lead.id} empresa={empresa} total={emAndamento} fluxos={fluxos} notify={notify}
                onClose={() => setTrocarConta(false)} onDone={onChanged}/>
            )}
            {semEmail.length > 0 && (
              <Button size="sm" variant="ghost" icon="wand-magic-sparkles" onClick={findAll} disabled={!!bulk}>
                {bulk && bulk !== 'cad' && !String(bulk).startsWith('apollo') ? `Procurando ${bulk}…` : `Achar e-mails (${semEmail.length})`}
              </Button>
            )}
            {!draft && <Button size="sm" icon="user-plus" onClick={() => setDraft(EMPTY_CONTACT)}>Adicionar</Button>}
          </div>
        </header>
        <Coverage contacts={contacts}/>
        <Duplicates api={api} lead={lead} contacts={contacts} notify={notify} onChanged={onChanged}/>

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
            {contacts.map(c => <Person key={c.id} boot={boot} api={api} leadId={lead.id} contact={c} empresa={empresa} inscricao={inscricaoDe(c.id)} fluxos={fluxos} notify={notify} onChanged={onChanged}/>)}
          </ul>
        )}
      </section>
      <Discovery boot={boot} api={api} lead={lead} candidates={candidates} onChanged={onChanged} notify={notify} onEditCompany={onEditCompany}/>
    </>
  );
}
