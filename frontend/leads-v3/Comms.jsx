import React, {useState} from 'react';
import {Button, Chip, Empty, Field, Icon, decode, whatsappUrl} from './ui.jsx';

function splitEmail(text) {
  const lines = String(text || '').split('\n');
  if (lines[0]?.toLowerCase().startsWith('assunto:')) {
    return {subject: lines[0].replace(/^assunto:\s*/i, '').trim(), body: lines.slice(1).join('\n').trim()};
  }
  return {subject: '', body: text};
}

export function Comms({api, lead, contacts, communications, onChanged, notify}) {
  const [tipo, setTipo] = useState('whatsapp');
  const [contato, setContato] = useState('');
  const [objetivo, setObjetivo] = useState('');
  const [tamanho, setTamanho] = useState('medio');
  const [texto, setTexto] = useState('');
  const [busy, setBusy] = useState('');

  const pessoa = contacts.find(c => String(c.id) === contato);
  const telefone = pessoa?.telefone || lead.telefone;
  const email = pessoa?.email || lead.email;

  const generate = async () => {
    if (!objetivo.trim()) return notify('Diga o objetivo da mensagem.', 'error');
    setBusy('gerar');
    try {
      const result = await api.generateCommunication({lead_id: lead.id, tipo, objetivo: objetivo.trim(), tamanho, tom: 'cordial',
        incluir_dados_lead: true, contato_id: contato || null});
      setTexto(result.texto || result.mensagem || '');
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const save = status => async () => {
    setBusy(status);
    try {
      await api.saveCommunication(lead.id, {tipo_canal: tipo, objetivo, texto, status, id_contato: contato || null, tom: 'cordial', tamanho, gerado_por_ia: true});
      notify(status === 'enviado' ? 'Comunicação marcada como enviada.' : 'Rascunho salvo.');
      if (status === 'enviado') { setTexto(''); setObjetivo(''); }
      onChanged();
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(texto); notify('Texto copiado.'); } catch { notify('Não foi possível copiar.', 'error'); }
  };
  const openChannel = () => {
    if (tipo === 'whatsapp') {
      const url = whatsappUrl(telefone, texto);
      if (!url) return notify('Este lead não tem telefone.', 'error');
      window.open(url, '_blank', 'noopener');
    } else {
      if (!email) return notify('Este lead não tem e-mail.', 'error');
      const {subject, body} = splitEmail(texto);
      window.open(`mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`);
    }
  };

  return (
    <div className="lv3-comms">
      <div className="lv3-card lv3-form">
        <div className="lv3-segmented" role="radiogroup" aria-label="Canal">
          {[['whatsapp', 'WhatsApp', 'comment'], ['email', 'E-mail', 'envelope']].map(([value, label, icon]) => (
            <button key={value} type="button" role="radio" aria-checked={tipo === value} className={tipo === value ? 'is-on' : ''} onClick={() => setTipo(value)}>
              <Icon name={icon}/>{label}
            </button>
          ))}
        </div>
        <div className="lv3-form__grid">
          <Field label="Para">
            <select className="lv3-select" value={contato} onChange={event => setContato(event.target.value)}>
              <option value="">{lead.email || lead.telefone ? (decode(lead.nome) || 'Contato do lead') : 'Escolha uma pessoa'}</option>
              {contacts.map(c => <option key={c.id} value={c.id}>{decode(c.nome)}</option>)}
            </select>
          </Field>
          <Field label="Tamanho">
            <select className="lv3-select" value={tamanho} onChange={event => setTamanho(event.target.value)}>
              <option value="curto">Curto</option><option value="medio">Médio</option><option value="longo">Longo</option>
            </select>
          </Field>
        </div>
        <Field label="Objetivo" wide>
          <textarea className="lv3-input lv3-textarea" rows={2} placeholder="Ex.: agendar 20 minutos para apresentar mídia programática"
            value={objetivo} onChange={event => setObjetivo(event.target.value)}/>
        </Field>
        <Button variant="ai" icon="wand-magic-sparkles" onClick={generate} disabled={!!busy} className="lv3-btn--block">
          {busy === 'gerar' ? 'Escrevendo…' : texto ? 'Gerar outra versão' : 'Escrever com IA'}
        </Button>

        {texto && (
          <>
            <Field label="Mensagem (editável)" wide>
              <textarea className="lv3-input lv3-textarea lv3-textarea--tall" value={texto} onChange={event => setTexto(event.target.value)}/>
            </Field>
            <div className="lv3-form__actions lv3-form__actions--wrap">
              <Button size="sm" icon="copy" onClick={copy}>Copiar</Button>
              <Button size="sm" icon={tipo === 'whatsapp' ? 'arrow-up-right-from-square' : 'paper-plane'} onClick={openChannel}>
                {tipo === 'whatsapp' ? 'Abrir no WhatsApp' : 'Abrir no e-mail'}
              </Button>
              <Button size="sm" icon="floppy-disk" onClick={save('draft')} disabled={!!busy}>Salvar rascunho</Button>
              <Button size="sm" variant="primary" icon="check" onClick={save('enviado')} disabled={!!busy}>Marcar como enviada</Button>
            </div>
          </>
        )}
      </div>

      {!communications.length ? (
        <Empty icon="comments" title="Nenhuma comunicação registrada"/>
      ) : (
        <ul className="lv3-commlist">
          {communications.map(c => (
            <li key={c.id} className="lv3-card lv3-comm">
              <div className="lv3-comm__head">
                <Icon name={c.tipo_canal === 'email' ? 'envelope' : 'comment'}/>
                <strong>{c.objetivo || (c.tipo_canal === 'email' ? 'E-mail' : 'WhatsApp')}</strong>
                <Chip tone={c.status === 'enviado' ? 'success' : 'neutral'}>{c.status === 'enviado' ? 'Enviada' : 'Rascunho'}</Chip>
              </div>
              <p className="lv3-comm__text">{c.texto}</p>
              <span className="lv3-muted">{[c.contato_nome && decode(c.contato_nome), c.usuario_nome, c.created_at && String(c.created_at).slice(0, 16).replace('T', ' ')].filter(Boolean).join(' · ')}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
