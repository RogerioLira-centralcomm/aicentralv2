import React, {useState} from 'react';
import {Button, Chip, Empty, Field, Icon, decode, gmailUrl, linkedinSearchUrl, prettyName, whatsappUrl} from './ui.jsx';

const CANAIS = [
  {value: 'email', label: 'E-mail', icon: 'envelope'},
  {value: 'whatsapp', label: 'WhatsApp', icon: 'comment'},
  {value: 'linkedin', label: 'LinkedIn', icon: 'user-group'},
  {value: 'linkedin_conexao', label: 'Convite', icon: 'user-plus'},
];
const STATUS_CADENCIA = {ativa: 'em cadência', pausada: 'cadência pausada', respondeu: 'respondeu', concluida: 'cadência concluída'};

/** Comunicação por pessoa: escolher o contato, escrever com canal e etapa de funil, e ver o histórico só com ele. */
export function Comms({api, lead, contacts, communications, cadences = [], onChanged, notify}) {
  const principal = contacts.find(c => c.is_principal) || contacts[0];
  const [escolhida, setPessoaId] = useState(principal?.id ?? null);
  // Pessoa adicionada ou removida com a coluna aberta: cai na principal (ou na primeira).
  const pessoaId = contacts.some(c => c.id === escolhida) ? escolhida : (principal?.id ?? null);
  const pessoa = contacts.find(c => c.id === pessoaId) || null;
  const [canal, setCanal] = useState('email');
  const [etapa, setEtapa] = useState('topo');
  const [objetivo, setObjetivo] = useState('');
  const [assunto, setAssunto] = useState('');
  const [texto, setTexto] = useState('');
  const [busy, setBusy] = useState('');

  if (!contacts.length) {
    return (
      <Empty icon="users" title="Sem pessoas nesta empresa">
        A comunicação é feita pessoa a pessoa. Adicione ou encontre pessoas na coluna do lead e elas aparecem aqui.
      </Empty>
    );
  }

  const nome = prettyName(pessoa?.nome);
  const empresa = decode(lead.empresa || lead.nome);
  const historico = communications.filter(c => c.id_contato === pessoaId);
  const inscricao = cadences.find(i => i.id_contato === pessoaId);
  const trocarPessoa = id => { setPessoaId(id); setTexto(''); setAssunto(''); };

  const escrever = async () => {
    setBusy('ia');
    try {
      const r = await api.writeMessage({id_contato: pessoaId, canal, etapa, objetivo});
      setTexto(r.texto || '');
      setAssunto(r.assunto || '');
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const corpo = (assunto ? `Assunto: ${assunto}\n\n` : '') + texto;
  const salvar = status => async () => {
    setBusy(status);
    try {
      await api.saveCommunication(lead.id, {tipo_canal: canal.startsWith('linkedin') ? 'linkedin' : canal, objetivo, texto: corpo, status,
        id_contato: pessoaId, gerado_por_ia: true, tom: 'cordial', tamanho: 'medio'});
      notify(status === 'enviado' ? `Registrado como enviado para ${nome}.` : 'Rascunho salvo.');
      if (status === 'enviado') { setTexto(''); setAssunto(''); }
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const copiar = async () => {
    try { await navigator.clipboard.writeText(assunto ? `${assunto}\n\n${texto}` : texto); notify('Texto copiado.'); return true; }
    catch { notify('Não foi possível copiar.', 'error'); return false; }
  };
  const abrir = async () => {
    if (canal === 'email') {
      if (!pessoa?.email) return notify(`${nome} não tem e-mail. Use "Achar e-mail" em Pessoas.`, 'error');
      window.open(gmailUrl(pessoa.email, assunto, texto), '_blank', 'noopener');
    } else if (canal === 'whatsapp') {
      const url = whatsappUrl(pessoa?.telefone, texto);
      if (!url) return notify(`${nome} não tem telefone.`, 'error');
      window.open(url, '_blank', 'noopener');
    } else {
      if (texto) await copiar();
      window.open(pessoa?.linkedin_url || linkedinSearchUrl(nome, empresa), '_blank', 'noopener');
    }
  };
  const disponivel = {email: !!pessoa?.email, whatsapp: !!pessoa?.telefone, linkedin: true, linkedin_conexao: true};

  return (
    <div className="lv3-comms">
      <div className="lv3-comms__people" role="tablist" aria-label="Pessoa">
        {contacts.map(c => {
          const i = cadences.find(x => x.id_contato === c.id);
          return (
            <button key={c.id} type="button" role="tab" aria-selected={c.id === pessoaId} className={`lv3-comms__person ${c.id === pessoaId ? 'is-on' : ''}`} onClick={() => trocarPessoa(c.id)}>
              <span className="lv3-person__avatar" aria-hidden="true">{prettyName(c.nome).slice(0, 1).toUpperCase()}</span>
              <span className="lv3-comms__personbody">
                <strong>{prettyName(c.nome)}</strong>
                <span>{prettyName(c.cargo) || 'Cargo não informado'}</span>
              </span>
              {i && ['ativa', 'respondeu'].includes(i.status) && <span className={`lv3-comms__dot is-${i.status}`} title={STATUS_CADENCIA[i.status]}/>}
            </button>
          );
        })}
      </div>

      <div className="lv3-card lv3-form">
        <div className="lv3-comms__who">
          <span>Para <strong>{nome}</strong>{pessoa?.cargo ? ` · ${prettyName(pessoa.cargo)}` : ''}</span>
          {inscricao && <span className="lv3-muted">{STATUS_CADENCIA[inscricao.status] || inscricao.status}</span>}
        </div>
        <div className="lv3-segmented lv3-segmented--4" role="radiogroup" aria-label="Canal">
          {CANAIS.map(c => (
            <button key={c.value} type="button" role="radio" aria-checked={canal === c.value} className={canal === c.value ? 'is-on' : ''}
              onClick={() => setCanal(c.value)} title={disponivel[c.value] ? '' : 'Sem esse contato para a pessoa'}>
              <Icon name={c.icon}/>{c.label}{!disponivel[c.value] && <span className="lv3-comms__missing" aria-label="indisponível">!</span>}
            </button>
          ))}
        </div>
        <div className="lv3-segmented" role="radiogroup" aria-label="Etapa do funil">
          {[['topo', 'Topo', 'Gerar interesse com conteúdo útil'], ['meio', 'Meio', 'Aprofundar: case, diagnóstico, conversa curta']].map(([v, l, t]) => (
            <button key={v} type="button" role="radio" aria-checked={etapa === v} className={etapa === v ? 'is-on' : ''} onClick={() => setEtapa(v)} title={t}>{l} de funil</button>
          ))}
        </div>
        <Field label="Objetivo" wide>
          <textarea className="lv3-input lv3-textarea" rows={2} value={objetivo} onChange={e => setObjetivo(e.target.value)}
            placeholder={etapa === 'topo' ? 'Ex.: compartilhar um estudo de audiência do setor' : 'Ex.: propor 20 minutos para mostrar um case parecido'}/>
        </Field>
        <Button variant="ai" icon="wand-magic-sparkles" onClick={escrever} disabled={!!busy} className="lv3-btn--block">
          {busy === 'ia' ? `Escrevendo para ${nome}…` : texto ? 'Escrever outra versão' : `Escrever para ${nome.split(' ')[0] || 'a pessoa'}`}
        </Button>

        {texto && (
          <>
            {canal === 'email' && <Field label="Assunto" wide><input className="lv3-input" value={assunto} onChange={e => setAssunto(e.target.value)}/></Field>}
            <Field label="Mensagem (editável)" wide>
              <textarea className="lv3-input lv3-textarea lv3-textarea--tall" value={texto} onChange={e => setTexto(e.target.value)}/>
            </Field>
            {canal === 'linkedin_conexao' && <p className={`lv3-muted ${texto.length > 300 ? 'lv3-danger' : ''}`}>{texto.length}/300 caracteres</p>}
            <div className="lv3-form__actions lv3-form__actions--wrap">
              <Button size="sm" variant="primary" icon={canal === 'email' ? 'paper-plane' : 'arrow-up-right-from-square'} onClick={abrir}>
                {{email: 'Abrir no Gmail', whatsapp: 'Abrir no WhatsApp'}[canal] || 'Copiar e abrir LinkedIn'}
              </Button>
              <Button size="sm" icon="copy" onClick={copiar}>Copiar</Button>
              <Button size="sm" icon="floppy-disk" onClick={salvar('draft')} disabled={!!busy}>Rascunho</Button>
              <Button size="sm" icon="check" onClick={salvar('enviado')} disabled={!!busy}>Marcar enviada</Button>
            </div>
          </>
        )}
      </div>

      <h4 className="lv3-comms__title">Histórico com {nome.split(' ')[0] || 'a pessoa'} {historico.length > 0 && <span className="lv3-count">{historico.length}</span>}</h4>
      {!historico.length ? (
        <p className="lv3-muted">Nada enviado para esta pessoa ainda.</p>
      ) : (
        <ul className="lv3-commlist">
          {historico.map(c => (
            <li key={c.id} className="lv3-card lv3-comm">
              <div className="lv3-comm__head">
                <Icon name={c.tipo_canal === 'email' ? 'envelope' : c.tipo_canal === 'linkedin' ? 'user-group' : 'comment'}/>
                <strong>{c.objetivo || ({email: 'E-mail', whatsapp: 'WhatsApp', linkedin: 'LinkedIn'}[c.tipo_canal] || 'Mensagem')}</strong>
                <Chip tone={c.status === 'enviado' ? 'success' : 'neutral'}>{c.status === 'enviado' ? 'Enviada' : 'Rascunho'}</Chip>
              </div>
              <p className="lv3-comm__text">{c.texto}</p>
              <span className="lv3-muted">{[c.usuario_nome, c.created_at && String(c.created_at).slice(0, 16).replace('T', ' ')].filter(Boolean).join(' · ')}</span>
            </li>
          ))}
        </ul>
      )}
      {communications.length > historico.length && (
        <p className="lv3-muted">{communications.length - historico.length} {communications.length - historico.length === 1 ? 'comunicação' : 'comunicações'} com outras pessoas desta empresa.</p>
      )}
    </div>
  );
}
