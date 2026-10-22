import React, {useEffect, useRef, useState} from 'react';
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

const pessoa = e => (e?.email ? (e.name ? `${e.name} <${e.email}>` : e.email) : '—');
const diaMes = v => (v ? `${String(v).slice(8, 10)}/${String(v).slice(5, 7)}` : '');

/** Visualizador do e-mail como ele vai sair pela Brevo: envelope, assunto (ou "Re:" da conversa) e o HTML final. */
export function EmailPreview({api, item, assunto, setAssunto, texto, naConversa, setNaConversa, versao, onPrevia}) {
  const [p, setP] = useState(null);
  const [erro, setErro] = useState('');
  useEffect(() => {
    // Espera o executivo parar de digitar; a prévia é montada no servidor, igual ao envio.
    const t = setTimeout(() => {
      api.previewEmail(item.id, {assunto, texto, na_conversa: naConversa})
        .then(r => { setP(r); setErro(''); onPrevia?.(r); })
        .catch(error => setErro(error.message));
    }, 500);
    return () => clearTimeout(t);
  }, [api, item.id, assunto, texto, naConversa, versao]); // eslint-disable-line react-hooks/exhaustive-deps

  const emConversa = naConversa && p?.conversa;
  return (
    <section className="lv3-mailview" aria-label="Prévia do e-mail">
      <dl className="lv3-mailview__env">
        <dt>De</dt><dd>{pessoa(p?.de)}</dd>
        <dt>Para</dt><dd>{pessoa(p?.para)}</dd>
        <dt>Responder para</dt><dd>{p?.reply_to?.email || '—'} <span className="lv3-muted">· a resposta cai na sua caixa</span></dd>
        <dt>Assunto</dt>
        <dd>
          {emConversa
            ? <span className="lv3-mailview__thread"><Icon name="reply"/><strong>{p.assunto}</strong><span className="lv3-muted"> · mesma conversa do e-mail de {diaMes(p.conversa.enviado_em)}</span></span>
            : <input className="lv3-input lv3-input--sm" value={assunto} placeholder="assunto curto, em minúsculas" onChange={e => setAssunto(e.target.value)} aria-label="Assunto"/>}
        </dd>
      </dl>
      {p?.tem_conversa && (
        <label className="lv3-mailview__toggle">
          <input type="checkbox" checked={naConversa} onChange={e => setNaConversa(e.target.checked)}/>
          Responder na mesma conversa (o e-mail chega agrupado com os anteriores)
        </label>
      )}
      {(erro || p?.bloqueio) && <p className="lv3-op__warn"><Icon name="triangle-exclamation"/>{erro || p.bloqueio}</p>}
      {/* Sem scripts; links abrem em outra aba (o HTML vem do servidor, com o texto escapado). */}
      <iframe className="lv3-mailview__body" title="Corpo do e-mail" sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
        srcDoc={p?.html ? `<base target="_blank"><body style="margin:16px">${p.html}</body>` : ''}/>
      <p className="lv3-muted lv3-mailview__note"><Icon name="eye"/>Abertura e cliques nos links voltam para as atividades do lead e da pessoa.</p>
    </section>
  );
}

/** Insere "[texto](https://…)" onde está o cursor; no e-mail vira link com o texto, e o clique é medido. */
export function LinkInserter({textareaRef, texto, setTexto, notify}) {
  const [aberto, setAberto] = useState(false);
  const [rotulo, setRotulo] = useState('');
  const [url, setUrl] = useState('');
  const pos = useRef(null);
  const abrir = () => {
    const el = textareaRef.current;
    pos.current = el ? [el.selectionStart, el.selectionEnd] : [texto.length, texto.length];
    setRotulo(el && el.selectionEnd > el.selectionStart ? texto.slice(el.selectionStart, el.selectionEnd) : '');
    setUrl('');
    setAberto(true);
  };
  const inserir = () => {
    let link = url.trim();
    if (link && !/^https?:\/\//i.test(link)) link = `https://${link}`;
    if (!/^https?:\/\/[^\s.]+\.[^\s]+$/i.test(link)) return notify('Cole um link válido (https://…).', 'error');
    const [ini, fim] = pos.current || [texto.length, texto.length];
    const trecho = rotulo.trim() ? `[${rotulo.trim().replace(/[[\]]/g, '')}](${link})` : link;
    setTexto(texto.slice(0, ini) + trecho + texto.slice(fim));
    setAberto(false);
  };
  if (!aberto) return <button type="button" className="lv3-link lv3-link--muted" onClick={abrir}><Icon name="link"/> Inserir link</button>;
  return (
    <div className="lv3-linkins">
      <input className="lv3-input lv3-input--sm" value={rotulo} placeholder="texto do link (ex.: o estudo da Kantar)" onChange={e => setRotulo(e.target.value)} aria-label="Texto do link"/>
      <input className="lv3-input lv3-input--sm" value={url} placeholder="https://…" onChange={e => setUrl(e.target.value)} aria-label="Endereço do link"
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); inserir(); } }}/>
      <Button size="sm" variant="primary" onClick={inserir}>Inserir</Button>
      <Button size="sm" variant="ghost" onClick={() => setAberto(false)}>Cancelar</Button>
    </div>
  );
}
