import React, {useEffect, useRef, useState} from 'react';
import {Button, Empty, Icon, decode, formatDate, linkedinSearchUrl, prettyName, whatsappUrl} from './ui.jsx';
import {People} from './People.jsx';
import {FocusEditor, GoldenTarget, MarketContext} from './Focus.jsx';

const CLOSED_LABELS = {nao_qualificado: 'Desqualificado', fechado_ganho: 'Ganho', fechado_perdido: 'Perdido'};
const TIPO_LEAD = {cliente: 'Cliente', parceiro: 'Parceiro', fornecedor: 'Fornecedor', midia: 'Mídia', outro: 'Outro'};
const PORTE = {micro: 'Micro', pequeno: 'Pequeno', medio: 'Médio', grande: 'Grande', enterprise: 'Enterprise'};

function Info({label, children, wide = false}) {
  return (
    <div className={`lv3-info ${wide ? 'lv3-info--wide' : ''}`}>
      <dt>{label}</dt>
      <dd>{children || <span className="lv3-muted">—</span>}</dd>
    </div>
  );
}

const asList = value => (Array.isArray(value) ? value : value ? String(value).split(/[,;\n]/) : []).map(v => decode(v).trim()).filter(Boolean);
const formatCnpj = value => {
  const d = String(value || '').replace(/\D/g, '');
  return d.length === 14 ? d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5') : value;
};
const siteUrl = value => (/^https?:/.test(value) ? value : `https://${value}`);

function Socials({value}) {
  let redes = value;
  if (typeof redes === 'string') { try { redes = JSON.parse(redes); } catch { redes = null; } }
  const entries = redes && typeof redes === 'object' ? Object.entries(redes).filter(([, url]) => typeof url === 'string' && /^https?:/.test(url)) : [];
  if (!entries.length) return null;
  return (
    <div className="lv3-socials">
      {entries.map(([rede, url]) => <a key={rede} href={url} target="_blank" rel="noopener noreferrer"><Icon name="arrow-up-right-from-square"/>{rede}</a>)}
    </div>
  );
}

/** Menu "⋯" para as ações menos usadas do lead (fecha com clique fora ou Esc). */
function MoreMenu({items, disabled}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = event => { if (event.type === 'keydown' ? event.key === 'Escape' : !ref.current?.contains(event.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close); };
  }, [open]);
  return (
    <div className="lv3-menu" ref={ref}>
      <Button size="sm" icon="ellipsis" onClick={() => setOpen(o => !o)} disabled={disabled} aria-label="Mais ações" aria-expanded={open} title="Mais ações"/>
      {open && (
        <div className="lv3-menu__list" role="menu">
          {items.map(item => (
            <button key={item.label} type="button" role="menuitem" className={`lv3-menu__item ${item.danger ? 'is-danger' : ''}`}
              onClick={() => { setOpen(false); item.onClick(); }}>
              <Icon name={item.icon}/>{item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function LeadPanel({boot, api, lead, contacts, candidates, golden, cadences, loading, notify, onChanged, onEdit, onEditCompany, onConvert, onDisqualify, onMarkGolden, onExtract, onMerge}) {
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
  const converted = !!lead.convertido_cliente_id;
  const patch = async (body, done) => {
    setBusy(true);
    try { await api.updateStatus(lead.id, body); notify(done); onChanged(); }
    catch (error) { notify(error.message, 'error'); } finally { setBusy(false); }
  };
  const nome = decode(lead.empresa || lead.nome);
  const servicos = asList(lead.servicos);
  const clientes = asList(lead.clientes_mencionados);
  // Boolean(): com `0 && <jsx>` o React renderiza o "0" na tela.
  const temEnriquecimento = Boolean(lead.descricao_empresa || lead.mercado_alvo || lead.presenca_digital || lead.oportunidades_midia || servicos.length || clientes.length);
  // Conta criada pelo Golden Circle não tem contato: o nome da empresa só preenche o campo obrigatório.
  // O contato do formulário já é uma das pessoas (mesmo e-mail ou nome)? Então não repete o bloco.
  const contatoDuplicado = contacts.some(c => (lead.email && String(c.email || '').toLowerCase() === String(lead.email).toLowerCase())
    || (lead.nome && decode(c.nome).trim().toLowerCase() === decode(lead.nome).trim().toLowerCase()));
  const focoVazio = !(lead.canais_foco || []).length && !lead.foco_conteudo;
  const contextoVazio = !(lead.contexto_mercado && (lead.contexto_mercado.texto || String(lead.contexto_mercado).includes('texto')));
  const temContato = !contatoDuplicado && Boolean(lead.email || lead.telefone || lead.cargo || lead.mensagem
    || (decode(lead.nome).trim() && decode(lead.nome).trim().toLowerCase() !== decode(lead.empresa).trim().toLowerCase()));

  return (
    <section className="lv3-col lv3-lead" aria-label="Lead selecionado">
      <header className="lv3-lead__head">
        <div className="lv3-lead__title">
          {lead.favicon_url && <img src={lead.favicon_url} alt="" className="lv3-lead__favicon"/>}
          <div>
            <h2>{nome || 'Sem nome'}{golden && <span className="lv3-gc-badge">Golden Circle {golden.trimestre.replace('-', ' ')}</span>}{lead.prioridade_conta && <span className="lv3-prio">Prioridade {lead.prioridade_conta}</span>}</h2>
            <p>{[lead.segmento, lead.fonte && `via ${lead.fonte}`, lead.created_at && `entrou em ${formatDate(lead.created_at)}`].filter(Boolean).join(' · ')}</p>
          </div>
          <div className="lv3-lead__actions">
          {next && (
            <Button variant="primary" size="sm" icon="arrow-right" disabled={busy} title={`Mover para ${next.label}`}
              onClick={() => patch({status: next.value}, `Lead movido para ${next.label}.`)}>
              {next.label}
            </Button>
          )}
          <Button size="sm" icon="pen" onClick={onEdit} disabled={busy} title="Editar dados do lead" aria-label="Editar"/>
          <MoreMenu disabled={busy} items={[
            !golden && !converted && {icon: 'bullseye', label: 'Marcar como Golden Circle', onClick: onMarkGolden},
            !converted && {icon: 'user-check', label: 'Converter em cliente', onClick: onConvert},
            {icon: 'building', label: 'Dados da empresa', onClick: onEditCompany},
            {icon: 'wand-magic-sparkles', label: 'Ler site com IA', onClick: onExtract},
            {icon: 'code-merge', label: 'Mesclar duplicado', onClick: onMerge},
            lead.status !== 'nao_qualificado' && {icon: 'ban', label: 'Desqualificar', onClick: onDisqualify, danger: true},
          ].filter(Boolean)}/>
          </div>
        </div>

        {converted && (
          <div className="lv3-banner lv3-banner--success"><Icon name="circle-check"/>Convertido em cliente{lead.data_conversao ? ` em ${formatDate(lead.data_conversao)}` : ''}.</div>
        )}
        {lead.status === 'nao_qualificado' && (
          <div className="lv3-banner lv3-banner--danger"><Icon name="ban"/>Desqualificado{lead.motivo_desqualificacao ? `: ${lead.motivo_desqualificacao}` : ''}.</div>
        )}

        <div className="lv3-lead__bar">
          <label className="lv3-pill-select is-set lv3-pill-select--lg" title="Etapa">
            <Icon name="flag"/>
            <select value={closed ? '' : lead.status} disabled={busy} aria-label="Etapa"
              onChange={event => patch({status: event.target.value}, 'Etapa atualizada.')}>
              {closed && <option value="">{CLOSED_LABELS[lead.status] || lead.status}</option>}
              {boot.status.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </label>
          <label className="lv3-pill-select is-set lv3-pill-select--lg" title="Potencial">
            <Icon name="signal"/>
            <select value={lead.potencial || ''} disabled={busy} aria-label="Potencial"
              onChange={event => patch({potencial: event.target.value}, 'Potencial atualizado.')}>
              {boot.potenciais.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </label>
          <label className={`lv3-pill-select lv3-pill-select--lg ${lead.id_executivo ? 'is-set' : ''}`} title="Responsável">
            <Icon name="user"/>
            <select value={lead.id_executivo ? String(lead.id_executivo) : '0'} disabled={busy} aria-label="Responsável"
              onChange={event => patch({id_executivo: Number(event.target.value)}, 'Responsável atualizado.')}>
              <option value="0">Ninguém</option>
              {boot.executivos.map(e => <option key={e.id} value={String(e.id)}>{e.nome}</option>)}
            </select>
          </label>
        </div>
      </header>

      <div className="lv3-lead__scroll">
        {golden && (
          <section className="lv3-section lv3-section--golden">
            <header className="lv3-section__head"><h3><Icon name="bullseye"/>&nbsp;Alvo Golden Circle</h3></header>
            <GoldenTarget api={api} conta={golden} contacts={contacts} notify={notify} onChanged={onChanged}/>
          </section>
        )}

        {/* Pessoas logo no topo: é com elas que a conexão acontece. */}
        <People key={lead.id} cadences={cadences} boot={boot} api={api} lead={lead} contacts={contacts} candidates={candidates} onChanged={onChanged} notify={notify} onEditCompany={onEditCompany}/>
        {temContato && <section className="lv3-section">
          <header className="lv3-section__head"><h3>Contato do lead</h3></header>
          <dl className="lv3-infos">
            <Info label="Nome">{prettyName(lead.nome)}</Info>
            <Info label="Cargo">{prettyName(lead.cargo)}</Info>
            <Info label="E-mail">{lead.email && <a href={`mailto:${lead.email}`}>{String(lead.email).toLowerCase()}</a>}</Info>
            <Info label="Telefone">{lead.telefone && <a href={whatsappUrl(lead.telefone)} target="_blank" rel="noopener noreferrer">{lead.telefone} <Icon name="arrow-up-right-from-square"/></a>}</Info>
          </dl>
          {lead.mensagem && <blockquote className="lv3-message"><Icon name="quote-left"/>{decode(lead.mensagem)}</blockquote>}
        </section>}
        {!temContato && lead.mensagem && (
          <section className="lv3-section">
            <header className="lv3-section__head"><h3>Mensagem do formulário</h3></header>
            <blockquote className="lv3-message lv3-message--flush"><Icon name="quote-left"/>{decode(lead.mensagem)}</blockquote>
          </section>
        )}

        <section className="lv3-section">
          <header className="lv3-section__head">
            <h3>Empresa</h3>
            <div className="lv3-section__tools">
              <a className="lv3-btn lv3-btn--ghost lv3-btn--sm" href={linkedinSearchUrl(nome)} target="_blank" rel="noopener noreferrer"><Icon name="arrow-up-right-from-square"/><span>LinkedIn</span></a>
              <Button size="sm" variant="ghost" icon="wand-magic-sparkles" onClick={onExtract}>Ler site</Button>
              <Button size="sm" variant="ghost" icon="building" onClick={onEditCompany}>Dados</Button>
            </div>
          </header>
          {(() => {
            // Só o que está preenchido; o que falta vira um lembrete curto no fim.
            const campos = [
              ['CNPJ', lead.cnpj && formatCnpj(lead.cnpj)],
              ['Site', lead.url_site && <a href={siteUrl(lead.url_site)} target="_blank" rel="noopener noreferrer">{lead.url_site}</a>],
              ['Domínio', lead.dominio],
              ['Segmento', lead.segmento],
              ['Porte', PORTE[lead.porte_estimado] || lead.porte_estimado],
              ['Grupo econômico', lead.grupo_economico],
              ['Tipo', TIPO_LEAD[lead.tipo_lead] || lead.tipo_lead],
            ];
            const cheios = campos.filter(([, v]) => v);
            const faltam = campos.filter(([l, v]) => !v && ['CNPJ', 'Domínio', 'Segmento'].includes(l)).map(([l]) => l);
            return (
              <>
                {cheios.length > 0 && <dl className="lv3-infos">{cheios.map(([l, v]) => <Info key={l} label={l}>{v}</Info>)}</dl>}
                {faltam.length > 0 && (
                  <p className="lv3-hint lv3-hint--muted">
                    <Icon name="circle-info"/>Falta {faltam.join(', ').replace(/, ([^,]*)$/, ' e $1')}{faltam.includes('Domínio') ? ' (o domínio libera o Apollo e o "Achar e-mail")' : ''}.
                    <button type="button" className="lv3-link" onClick={onEditCompany}>Completar</button>
                  </p>
                )}
              </>
            );
          })()}
          <Socials value={lead.redes_sociais}/>
        </section>

        {temEnriquecimento && (
          <section className="lv3-section">
            <header className="lv3-section__head"><h3>O que sabemos da empresa</h3></header>
            <dl className="lv3-infos">
              {lead.descricao_empresa && <Info label="Descrição" wide>{decode(lead.descricao_empresa)}</Info>}
              {lead.mercado_alvo && <Info label="Mercado-alvo" wide>{decode(lead.mercado_alvo)}</Info>}
              {lead.presenca_digital && <Info label="Presença digital" wide>{decode(lead.presenca_digital)}</Info>}
              {lead.oportunidades_midia && <Info label="Oportunidades de mídia" wide>{decode(lead.oportunidades_midia)}</Info>}
              {servicos.length > 0 && <Info label="Serviços" wide><span className="lv3-tags">{servicos.map(s => <span key={s} className="lv3-tag">{s}</span>)}</span></Info>}
              {clientes.length > 0 && <Info label="Clientes citados" wide><span className="lv3-tags">{clientes.map(s => <span key={s} className="lv3-tag">{s}</span>)}</span></Info>}
            </dl>
          </section>
        )}

        {focoVazio && contextoVazio ? (
          <section className="lv3-section">
            <header className="lv3-section__head"><h3>Personalizar a abordagem</h3></header>
            <p className="lv3-muted lv3-help">Canais, conteúdos de topo e meio de funil e o contexto de mercado alimentam as mensagens da IA para cada pessoa.</p>
            <div className="lv3-personalize">
              <div><h4>Foco: canais e conteúdo</h4><FocusEditor api={api} lead={lead} notify={notify} onChanged={onChanged} bare/></div>
              <div><h4>Contexto de mercado</h4><MarketContext api={api} lead={lead} notify={notify} onChanged={onChanged} bare/></div>
            </div>
          </section>
        ) : (
          <>
            <section className="lv3-section">
              <header className="lv3-section__head"><h3>Foco: canais e conteúdo</h3></header>
              <FocusEditor api={api} lead={lead} notify={notify} onChanged={onChanged}/>
            </section>
            <section className="lv3-section">
              <header className="lv3-section__head"><h3>Contexto de mercado</h3></header>
              <MarketContext api={api} lead={lead} notify={notify} onChanged={onChanged}/>
            </section>
          </>
        )}


        <section className="lv3-section">
          <header className="lv3-section__head"><h3>Qualificação e histórico</h3></header>
          <dl className="lv3-infos">
            <Info label="Score">{`${lead.qualificacao_score || 0}/100`}</Info>
            <Info label="Valor estimado">{lead.valor_estimado != null && Number(lead.valor_estimado).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})}</Info>
            <Info label="Entrou">{formatDate(lead.created_at)}</Info>
            <Info label="Atribuído">{lead.atribuido_em && formatDate(lead.atribuido_em)}</Info>
            <Info label="Primeiro contato">{lead.contatado_em && formatDate(lead.contatado_em)}</Info>
            <Info label="Atualizado">{lead.updated_at && formatDate(lead.updated_at)}</Info>
            {lead.qualificacao_notas && <Info label="Notas de qualificação" wide>{lead.qualificacao_notas}</Info>}
            {lead.notas_internas && <Info label="Notas internas" wide>{lead.notas_internas}</Info>}
          </dl>
          <details className="lv3-details">
            <summary>Origem e campanha</summary>
            <dl className="lv3-infos">
              <Info label="Fonte">{lead.fonte}</Info>
              <Info label="Origem">{lead.origem}</Info>
              <Info label="Canal">{lead.canal}</Info>
              <Info label="Interesse">{lead.interesse}</Info>
              <Info label="Página" wide>{lead.pagina_origem}</Info>
              <Info label="UTM source">{lead.utm_source}</Info>
              <Info label="UTM medium">{lead.utm_medium}</Info>
              <Info label="UTM campaign">{lead.utm_campaign}</Info>
              <Info label="Lote de importação">{lead.lote_importacao}</Info>
            </dl>
          </details>
        </section>
      </div>
    </section>
  );
}
