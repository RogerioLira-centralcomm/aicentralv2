import React, {useState} from 'react';
import {Button, Empty, Field, Icon, decode, formatDate, linkedinSearchUrl, whatsappUrl} from './ui.jsx';
import {People} from './People.jsx';

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

export function LeadPanel({boot, api, lead, contacts, candidates, loading, notify, onChanged, onEdit, onEditCompany, onConvert, onDisqualify}) {
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
  const temEnriquecimento = lead.descricao_empresa || lead.mercado_alvo || lead.presenca_digital || lead.oportunidades_midia || servicos.length;

  return (
    <section className="lv3-col lv3-lead" aria-label="Lead selecionado">
      <header className="lv3-lead__head">
        <div className="lv3-lead__title">
          {lead.favicon_url && <img src={lead.favicon_url} alt="" className="lv3-lead__favicon"/>}
          <div>
            <h2>{nome || 'Sem nome'}{lead.prioridade_conta && <span className="lv3-prio">Prioridade {lead.prioridade_conta}</span>}</h2>
            <p>{[lead.segmento, lead.fonte && `via ${lead.fonte}`, lead.created_at && `entrou em ${formatDate(lead.created_at)}`].filter(Boolean).join(' · ')}</p>
          </div>
        </div>

        {converted && (
          <div className="lv3-banner lv3-banner--success"><Icon name="circle-check"/>Convertido em cliente{lead.data_conversao ? ` em ${formatDate(lead.data_conversao)}` : ''}.</div>
        )}
        {lead.status === 'nao_qualificado' && (
          <div className="lv3-banner lv3-banner--danger"><Icon name="ban"/>Desqualificado{lead.motivo_desqualificacao ? `: ${lead.motivo_desqualificacao}` : ''}.</div>
        )}

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
          <Button icon="pen" onClick={onEdit} disabled={busy}>Editar</Button>
          {!converted && <Button icon="user-check" onClick={onConvert} disabled={busy}>Converter em cliente</Button>}
          <Button variant="danger-ghost" icon="ban" onClick={onDisqualify} disabled={busy || lead.status === 'nao_qualificado'}>Desqualificar</Button>
        </div>
      </header>

      <div className="lv3-lead__scroll">
        <section className="lv3-section">
          <header className="lv3-section__head"><h3>Contato do lead</h3></header>
          <dl className="lv3-infos">
            <Info label="Nome">{decode(lead.nome)}</Info>
            <Info label="Cargo">{lead.cargo}</Info>
            <Info label="E-mail">{lead.email && <a href={`mailto:${lead.email}`}>{lead.email}</a>}</Info>
            <Info label="Telefone">{lead.telefone && <a href={whatsappUrl(lead.telefone)} target="_blank" rel="noopener noreferrer">{lead.telefone} <Icon name="arrow-up-right-from-square"/></a>}</Info>
          </dl>
          {lead.mensagem && <blockquote className="lv3-message"><Icon name="quote-left"/>{decode(lead.mensagem)}</blockquote>}
        </section>

        <section className="lv3-section">
          <header className="lv3-section__head">
            <h3>Empresa</h3>
            <div className="lv3-section__tools">
              <a className="lv3-btn lv3-btn--ghost lv3-btn--sm" href={linkedinSearchUrl(nome)} target="_blank" rel="noopener noreferrer"><Icon name="arrow-up-right-from-square"/><span>LinkedIn</span></a>
              <Button size="sm" variant="ghost" icon="building" onClick={onEditCompany}>Dados da empresa</Button>
            </div>
          </header>
          <dl className="lv3-infos">
            <Info label="Empresa">{decode(lead.empresa)}</Info>
            <Info label="CNPJ">{lead.cnpj && formatCnpj(lead.cnpj)}</Info>
            <Info label="Site">{lead.url_site && <a href={siteUrl(lead.url_site)} target="_blank" rel="noopener noreferrer">{lead.url_site}</a>}</Info>
            <Info label="Domínio">{lead.dominio}</Info>
            <Info label="Segmento">{lead.segmento}</Info>
            <Info label="Porte">{PORTE[lead.porte_estimado] || lead.porte_estimado}</Info>
            <Info label="Grupo econômico">{lead.grupo_economico}</Info>
            <Info label="Tipo">{TIPO_LEAD[lead.tipo_lead] || lead.tipo_lead}</Info>
          </dl>
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

        <People key={lead.id} boot={boot} api={api} lead={lead} contacts={contacts} candidates={candidates} onChanged={onChanged} notify={notify} onEditCompany={onEditCompany}/>

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
