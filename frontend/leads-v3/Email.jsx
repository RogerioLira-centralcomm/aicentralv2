import React, {useState} from 'react';
import {Button, Field, Icon, Modal} from './ui.jsx';

const parse = valor => (valor ? new Date(String(valor).slice(0, 16)) : null);

/** "há 10 min" medido no relógio do servidor (`agora` vem com a Operação; os eventos usam o mesmo relógio). */
export function haQuanto(valor, agora) {
  const quando = parse(valor);
  if (!quando) return '';
  const minutos = Math.max(0, Math.round(((parse(agora) || new Date()) - quando) / 60000));
  if (minutos < 1) return 'agora';
  if (minutos < 60) return `há ${minutos} min`;
  if (minutos < 48 * 60) return `há ${Math.round(minutos / 60)} h`;
  return `há ${Math.round(minutos / 1440)} dias`;
}

/** Resumo do último e-mail enviado pela Brevo à pessoa: o que de mais forte aconteceu com ele. */
export function seloEmail(ultimo, agora) {
  if (!ultimo) return null;
  const ev = ultimo.eventos || {};
  const aberto = ev.aberto || {};
  if (ev.optout) return {tone: 'danger', icon: 'ban', text: ev.optout.tipo === 'spam' ? 'marcou como spam' : 'pediu para parar'};
  if (ev.bounce && ['hard_bounce', 'invalid_email'].includes(ev.bounce.tipo)) return {tone: 'danger', icon: 'triangle-exclamation', text: 'e-mail voltou'};
  if (ev.clicado) return {tone: 'success', icon: 'arrow-pointer', text: `clicou${ev.clicado.vezes > 1 ? ` ${ev.clicado.vezes}x` : ''} · ${haQuanto(ev.clicado.ultimo_em, agora)}`,
    title: (ev.clicado.urls || []).join('\n')};
  if (aberto.reais) return {tone: 'success', icon: 'envelope-open', text: `abriu ${aberto.reais}x · ${haQuanto(aberto.ultima_real, agora)}`};
  if (aberto.proxy) return {tone: 'neutral', icon: 'envelope', text: 'aberto só pelo proxy',
    title: 'O Apple Mail (e outros) baixa o e-mail sozinho para proteger a privacidade. Não conta como abertura real.'};
  if (ev.bounce || ev.falhou) return {tone: 'warning', icon: 'triangle-exclamation', text: 'problema na entrega', title: (ev.bounce || ev.falhou).motivo || ''};
  if (ev.entregue) return {tone: 'neutral', icon: 'check', text: 'entregue, sem abertura'};
  return {tone: 'neutral', icon: 'paper-plane', text: 'enviado'};
}

export function EmailSeal({ultimo, agora, full = false}) {
  const selo = seloEmail(ultimo, agora);
  if (!selo) return null;
  return (
    <span className={`lv3-seal lv3-seal--${selo.tone}`} title={selo.title || (ultimo.assunto ? `Último e-mail: ${ultimo.assunto}` : '')}>
      <Icon name={selo.icon}/>{full && ultimo.assunto ? `“${ultimo.assunto}” · ` : ''}{selo.text}
    </span>
  );
}

/** Mesma montagem do bloco "simples" de leads_v3_email._assinatura_simples, para a prévia ao editar. */
function previa(campos, nomeLogin) {
  const nome = campos.nome_assinatura || nomeLogin || '';
  const linha2 = [campos.cargo, 'CentralComm'].filter(Boolean).join(' · ');
  const contato = [campos.telefone, campos.linkedin_url, 'centralcomm.media'].filter(Boolean).join(' · ');
  return [nome, linha2, contato].filter(Boolean).join('\n');
}

export function SignatureDialog({api, prefs, notify, onClose, onSaved}) {
  const [campos, setCampos] = useState({
    assinatura: prefs.assinatura || '', nome_assinatura: prefs.nome_assinatura || '', cargo: prefs.cargo || '',
    telefone: prefs.telefone || '', linkedin_url: prefs.linkedin_url || '', modelo_assinatura: prefs.modelo_assinatura || 'simples',
  });
  const [busy, setBusy] = useState(false);
  const set = chave => e => setCampos(c => ({...c, [chave]: e.target.value}));
  const salvar = async () => {
    setBusy(true);
    try {
      const salvo = await api.savePreferences({...prefs, ...campos});
      notify('Assinatura salva.');
      onSaved(salvo);
      onClose();
    } catch (error) { notify(error.message, 'error'); setBusy(false); }
  };
  const nomeLogin = prefs.remetente?.nome;
  return (
    <Modal title="Assinatura dos e-mails" onClose={onClose} width={560} footer={(
      <>
        <Button variant="ghost" onClick={onClose}>Cancelar</Button>
        <Button variant="primary" icon="check" onClick={salvar} disabled={busy}>{busy ? 'Salvando…' : 'Salvar'}</Button>
      </>
    )}>
      <div className="lv3-form">
        <div className="lv3-form__grid">
          <Field label="Modelo">
            <select className="lv3-select" value={campos.modelo_assinatura} onChange={set('modelo_assinatura')}>
              {(prefs.modelos || [{id: 'simples', rotulo: 'Simples'}]).map(m => <option key={m.id} value={m.id}>{m.rotulo}</option>)}
            </select>
          </Field>
          <Field label="Nome"><input className="lv3-input" value={campos.nome_assinatura} placeholder={nomeLogin || ''} onChange={set('nome_assinatura')}/></Field>
          <Field label="Cargo"><input className="lv3-input" value={campos.cargo} placeholder="Diretor comercial" onChange={set('cargo')}/></Field>
          <Field label="Telefone / WhatsApp"><input className="lv3-input" value={campos.telefone} placeholder="(11) 99999-0000" onChange={set('telefone')}/></Field>
        </div>
        <Field label="LinkedIn" wide><input className="lv3-input" value={campos.linkedin_url} placeholder="https://www.linkedin.com/in/…" onChange={set('linkedin_url')}/></Field>
        <Field label="Fecho (antes da assinatura)" wide>
          <textarea className="lv3-input lv3-textarea" rows={2} value={campos.assinatura} placeholder={`Abs,\n${(nomeLogin || '').split(' ')[0]}`} onChange={set('assinatura')}/>
        </Field>
        <div className="lv3-sigpreview">
          <span className="lv3-field__label">Prévia</span>
          <pre>{[campos.assinatura.trim() || `Abs,\n${(nomeLogin || '').split(' ')[0]}`, previa(campos, nomeLogin)].join('\n\n')}</pre>
        </div>
        <p className="lv3-muted">O fecho entra no texto que a IA escreve (vale a partir da próxima mensagem). O bloco com nome, cargo e contatos vai no envio pela Brevo; os links dele contam clique.</p>
      </div>
    </Modal>
  );
}
