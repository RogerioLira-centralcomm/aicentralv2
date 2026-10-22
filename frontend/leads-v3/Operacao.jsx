import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {Button, Empty, Field, Icon, decode, formatDate, gmailUrl, linkedinSearchUrl, prettyName as pretty, todayLocal, whatsappUrl} from './ui.jsx';
import {ManageCadence} from './CadenceControls.jsx';
import {FocusEditor, GoldenTarget, MarketContext} from './Focus.jsx';
import {EmailSeal, SignatureDialog} from './Email.jsx';

const CANAL = {
  email: {label: 'E-mail', icon: 'envelope'},
  whatsapp: {label: 'WhatsApp', icon: 'comment'},
  linkedin: {label: 'LinkedIn', icon: 'user-group'},
  telefone: {label: 'Ligação', icon: 'phone'},
};
// Em qual lista de /api/operacao cada tipo de item selecionado mora.
const LISTA = {passo: 'passos', tarefa: 'tarefas', proximo: 'proximos', feito: 'feitos'};
const TIPO_TAREFA = {ligacao: 'Ligação', whatsapp: 'WhatsApp', email_enviado: 'E-mail', reuniao: 'Reunião', follow_up: 'Follow-up',
  apresentacao: 'Apresentação', proposta_enviada: 'Proposta', nota: 'Nota'};

function atraso(data) {
  if (!data) return '';
  const dia = String(data).slice(0, 10);
  const hoje = todayLocal();
  if (dia >= hoje) return 'hoje';
  const dias = Math.round((new Date(`${hoje}T00:00`) - new Date(`${dia}T00:00`)) / 86400000);
  return dias === 1 ? 'atrasado 1 dia' : `atrasado ${dias} dias`;
}

const DIAS_SEMANA = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
/** "Amanhã", "qui 23/10" — para agrupar os próximos passos por dia. */
function rotuloDia(valor) {
  const dia = String(valor || '').slice(0, 10);
  if (!dia) return 'Sem data';
  const d = new Date(`${dia}T12:00`);
  const amanha = new Date(`${todayLocal()}T12:00`); amanha.setDate(amanha.getDate() + 1);
  const ddmm = `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
  if (d.toDateString() === amanha.toDateString()) return `Amanhã · ${DIAS_SEMANA[d.getDay()]} ${ddmm}`;
  return `${DIAS_SEMANA[d.getDay()]} ${ddmm}`;
}
const somaDias = (valor, dias) => { const d = new Date(String(valor).slice(0, 10) + 'T12:00'); d.setDate(d.getDate() + dias); return d; };
const ddmm = d => `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;

/** Trilha da cadência: passos feitos ✓, o atual em destaque e os seguintes com data prevista. */
function CadenceTrack({item}) {
  const passos = Array.isArray(item.passos) ? item.passos : [];
  if (!passos.length) return null;
  const atual = passos[item.passo_atual] || {};
  return (
    <ol className="lv3-track" aria-label="Trilha da cadência">
      {passos.map((p, i) => {
        const estado = i < item.passo_atual ? 'feito' : i === item.passo_atual ? 'atual' : 'futuro';
        // Feito; atual vencido = "agora", atual agendado = data; seguintes = data prevista pelo espaçamento do modelo.
        let quando = '';
        if (estado === 'feito') quando = 'feito';
        else if (item.proxima_em && estado === 'atual') quando = String(item.proxima_em).slice(0, 10) <= todayLocal() ? 'agora' : ddmm(somaDias(item.proxima_em, 0));
        // Passo atual atrasado: ao fazer hoje, a cadência reagenda a partir de hoje (leads_v3_cadencias.avancar).
        else if (item.proxima_em) {
          const base = String(item.proxima_em).slice(0, 10) > todayLocal() ? item.proxima_em : todayLocal();
          quando = `~${ddmm(somaDias(base, Number(p.dia || 0) - Number(atual.dia || 0)))}`;
        }
        const info = CANAL[p.canal] || CANAL.email;
        return (
          <li key={i} className={`lv3-track__step is-${estado}`} title={`${p.titulo} · ${info.label}`}>
            <span className="lv3-track__dot"><Icon name={estado === 'feito' ? 'check' : info.icon}/></span>
            <span className="lv3-track__label">{p.titulo}</span>
            <span className="lv3-track__when">{quando}</span>
          </li>
        );
      })}
    </ol>
  );
}

const canalDaMensagem = passo => (passo?.canal === 'linkedin' ? (passo.acao === 'conectar' ? 'linkedin_conexao' : 'linkedin') : passo?.canal || 'email');

/** Composer do passo: etapa do funil, objetivo, mensagem da IA e envio assistido. */
const RODAPES = {nenhum: '', iphone: 'Enviado do meu iPhone', galaxy: 'Enviado do meu Galaxy'};
const RODAPE_RE = /\n+Enviado do meu (iPhone|Galaxy)\s*$/;

function StepComposer({api, item, agora, fluxos = [], notify, onDone, pautaVersao}) {
  const passo = item.passo || {};
  const canal = canalDaMensagem(passo);
  // A etapa vem do passo do fluxo; fluxo antigo sem etapa segue a regra de antes (primeira metade topo).
  const [etapa, setEtapa] = useState(passo.etapa || (item.passo_atual < Math.ceil((item.total || 2) / 2) ? 'topo' : 'meio'));
  const [objetivo, setObjetivo] = useState(passo.objetivo || passo.titulo || '');
  const [assunto, setAssunto] = useState('');
  const [texto, setTexto] = useState('');
  const [busy, setBusy] = useState('');
  const [ganchos, setGanchos] = useState([]);
  const [idGancho, setIdGancho] = useState(''); // '' = a IA escolhe o melhor ainda não usado com a pessoa
  const [usado, setUsado] = useState(null);
  const [alertas, setAlertas] = useState([]);
  const [prefs, setPrefs] = useState({dispositivo: 'nenhum', assinatura: ''});
  const [gerir, setGerir] = useState(false);
  const [editandoAssinatura, setEditandoAssinatura] = useState(false);
  const nome = pretty(item.contato_nome);
  const empresa = decode(item.empresa || item.lead_nome);
  const corpoCompleto = (assunto ? `Assunto: ${assunto}\n\n` : '') + texto;

  useEffect(() => {
    api.hooks(item.id_lead, item.id_contato).then(lista => setGanchos(lista.filter(g => g.status !== 'descartado'))).catch(() => setGanchos([]));
  }, [api, item.id_lead, item.id_contato, pautaVersao]);
  useEffect(() => { api.preferences().then(p => setPrefs({...p, dispositivo: p.dispositivo || 'nenhum', assinatura: p.assinatura || ''})).catch(() => null); }, [api]);
  const podeEnviar = passo.canal === 'email' && !!item.email && !!prefs.remetente?.pode_enviar;

  const escrever = async () => {
    setBusy('ia');
    try {
      const r = await api.writeMessage({id_contato: item.id_contato, id_inscricao: item.id, canal, etapa, objetivo, id_gancho: idGancho || null});
      setTexto(r.texto || '');
      setAssunto(r.assunto || '');
      setUsado(r.gancho || null);
      setAlertas(r.alertas || []);
    } catch (error) { notify(error.message, 'error'); } finally { setBusy(''); }
  };
  // "Enviado do meu…" é preferência do executivo: muda o texto aberto e vale para as próximas mensagens.
  const mudarRodape = async dispositivo => {
    setPrefs(p => ({...p, dispositivo}));
    setTexto(t => (t ? t.replace(RODAPE_RE, '') + (RODAPES[dispositivo] ? `\n\n${RODAPES[dispositivo]}` : '') : t));
    try { await api.savePreferences({dispositivo}); } catch (error) { notify(error.message, 'error'); }
  };
  // Envia pela Brevo em nome do executivo (resposta volta para a caixa dele) e o passo anda sozinho.
  const enviar = async () => {
    if (!assunto.trim()) return notify('Escreva o assunto antes de enviar.', 'error');
    setBusy('enviar');
    try {
      const r = await api.sendEmail(item.id, {passo: item.passo_atual, assunto, texto, id_gancho: usado?.id || null});
      await api.saveCommunication(item.id_lead, {tipo_canal: 'email', objetivo, texto: `Assunto: ${assunto}\n\n${r.texto || texto}`, status: 'enviado',
        id_contato: item.id_contato, gerado_por_ia: true, tamanho: 'medio', tom: 'cordial'}).catch(() => null);
      notify(`E-mail enviado para ${String(item.email).toLowerCase()}. Abertura e clique aparecem na Operação.`);
      onDone();
    } catch (error) { notify(error.message, 'error'); setBusy(''); }
  };
  const copiar = async () => {
    try { await navigator.clipboard.writeText(assunto ? `${assunto}\n\n${texto}` : texto); notify('Texto copiado.'); return true; }
    catch { notify('Não foi possível copiar.', 'error'); return false; }
  };
  const abrir = async () => {
    if (passo.canal === 'email') {
      if (!item.email) return notify('Esta pessoa não tem e-mail. Use "Achar e-mail" na mesa.', 'error');
      window.open(gmailUrl(item.email, assunto, texto), '_blank', 'noopener');
    } else if (passo.canal === 'whatsapp') {
      const url = whatsappUrl(item.telefone, texto);
      if (!url) return notify('Esta pessoa não tem telefone.', 'error');
      window.open(url, '_blank', 'noopener');
    } else if (passo.canal === 'linkedin') {
      if (texto) await copiar();
      window.open(item.linkedin_url || linkedinSearchUrl(nome, empresa), '_blank', 'noopener');
    } else if (passo.canal === 'telefone') {
      if (!item.telefone) return notify('Esta pessoa não tem telefone.', 'error');
      window.location.href = `tel:${String(item.telefone).replace(/[^\d+]/g, '')}`;
    }
  };
  const acao = (nome_acao, pedirNota) => async () => {
    let nota = '';
    if (pedirNota) {
      nota = window.prompt(pedirNota) ?? null;
      if (nota === null) return;
    }
    setBusy(nome_acao);
    try {
      if (nome_acao === 'feito' && texto && passo.canal !== 'telefone') {
        // Guarda o texto enviado no histórico de comunicações do lead (mesma tabela do Leads v2).
        await api.saveCommunication(item.id_lead, {tipo_canal: passo.canal, objetivo, texto: corpoCompleto, status: 'enviado',
          id_contato: item.id_contato, gerado_por_ia: true, tamanho: 'medio', tom: 'cordial'}).catch(() => null);
      }
      await api.stepAction(item.id, nome_acao, nota || (nome_acao === 'feito' && texto ? texto.slice(0, 140) : ''), nome_acao === 'feito' ? usado?.id : null);
      notify({feito: 'Passo feito. Próximo agendado.', respondeu: 'Resposta registrada; cadência encerrada.', pular: 'Passo pulado.', pausar: 'Cadência pausada.'}[nome_acao]);
      onDone();
    } catch (error) { notify(error.message, 'error'); setBusy(''); }
  };

  const info = CANAL[passo.canal] || CANAL.email;
  return (
    <div className="lv3-op__composer">
      <header className="lv3-op__person">
        <div className="lv3-person__avatar" aria-hidden="true">{nome.slice(0, 1).toUpperCase()}</div>
        <div>
          <h2>{nome}{item.golden && <span className="lv3-gc-badge">Golden Circle</span>}</h2>
          <p>{[pretty(item.cargo), empresa].filter(Boolean).join(' · ')}</p>
          {item.ultimo_email && <p className="lv3-op__lastmail"><span className="lv3-muted">Último e-mail:</span> <EmailSeal ultimo={item.ultimo_email} agora={agora} full/></p>}
          <p className="lv3-op__links">
            {item.email && <a href={`mailto:${item.email}`}><Icon name="envelope"/>{String(item.email).toLowerCase()}</a>}
            {item.telefone && <a href={whatsappUrl(item.telefone)} target="_blank" rel="noopener noreferrer"><Icon name="phone"/>{item.telefone}</a>}
            <a href={item.linkedin_url || linkedinSearchUrl(nome, empresa)} target="_blank" rel="noopener noreferrer"><Icon name="user-group"/>{item.linkedin_url ? 'LinkedIn' : 'Achar no LinkedIn'}</a>
          </p>
        </div>
      </header>

      <div className="lv3-op__step">
        <span className="lv3-op__stepicon"><Icon name={info.icon}/></span>
        <div>
          <strong>{passo.titulo}</strong>
          <span className="lv3-muted">{item.cadencia} · passo {item.passo_atual + 1} de {item.total} · {String(item.proxima_em).slice(0, 10) > todayLocal() ? `agendado para ${rotuloDia(item.proxima_em)} (dá para adiantar)` : atraso(item.proxima_em)}</span>
        </div>
      </div>
      <CadenceTrack item={item}/>

        <div className="lv3-card lv3-form">
          <div className="lv3-form__grid">
            <Field label="Etapa do funil">
              <div className="lv3-segmented lv3-segmented--3" role="radiogroup" aria-label="Etapa do funil">
                {[['topo', 'Topo', 'Puxar interesse com um fato'], ['meio', 'Meio', 'Aprofundar o desafio da pessoa'], ['fundo', 'Fundo', 'Propor o próximo passo']].map(([v, l, d]) => (
                  <button key={v} type="button" role="radio" aria-checked={etapa === v} className={etapa === v ? 'is-on' : ''} title={d} onClick={() => setEtapa(v)}>{l}</button>
                ))}
              </div>
            </Field>
            <Field label="Canal"><div className="lv3-op__channel"><Icon name={info.icon}/>{canal === 'linkedin_conexao' ? 'Convite de conexão (até 300 caracteres)' : info.label}</div></Field>
          </div>
          <Field label="Objetivo deste toque" wide>
            <textarea className="lv3-input lv3-textarea" rows={2} value={objetivo} onChange={e => setObjetivo(e.target.value)}/>
          </Field>
          <Field label="Gancho" wide>
            {ganchos.length ? (
              <select className="lv3-select" value={idGancho} onChange={e => setIdGancho(e.target.value)}>
                <option value="">Automático: o melhor de {etapa} ainda não usado com {nome.split(' ')[0]}</option>
                {ganchos.map(g => (
                  <option key={g.id} value={g.id}>{g.status === 'escolhido' ? '★ ' : ''}{g.usado_com_pessoa ? '(já usado) ' : ''}[{g.etapa}] {g.fato.slice(0, 110)}</option>
                ))}
              </select>
            ) : <p className="lv3-muted lv3-op__nohook">Sem pauta pesquisada: a mensagem sai sem fato concreto. Use "Pesquisar pauta" ao lado.</p>}
          </Field>
          <Button variant="ai" icon="wand-magic-sparkles" className="lv3-btn--block" onClick={escrever} disabled={!!busy}>
            {busy === 'ia' ? 'Escrevendo com o contexto da empresa…' : texto ? 'Escrever outra versão' : 'Escrever mensagem personalizada'}
          </Button>
          {texto && (
            <>
              {usado && (
                <p className="lv3-op__usedhook"><Icon name="lightbulb"/><span>Gancho: {usado.fato}{usado.fonte_url && <> · <a href={usado.fonte_url} target="_blank" rel="noopener noreferrer">fonte</a></>}</span></p>
              )}
              {alertas.length > 0 && <p className="lv3-op__warn"><Icon name="triangle-exclamation"/>Ainda soa como IA: {alertas.join(', ')}. Ajuste antes de enviar.</p>}
              {passo.canal === 'email' && (
                <Field label="Assunto" wide><input className="lv3-input" value={assunto} onChange={e => setAssunto(e.target.value)}/></Field>
              )}
              <Field label={passo.canal === 'telefone' ? 'Roteiro' : 'Mensagem (editável)'} wide>
                <textarea className="lv3-input lv3-textarea lv3-textarea--tall" value={texto} onChange={e => setTexto(e.target.value)}/>
              </Field>
              {canal === 'linkedin_conexao' && <p className={`lv3-muted ${texto.length > 300 ? 'lv3-danger' : ''}`}>{texto.length}/300 caracteres</p>}
              {passo.canal === 'email' && (
                <div className="lv3-op__signature">
                  <span className="lv3-muted">Rodapé</span>
                  <div className="lv3-segmented lv3-segmented--sm" role="radiogroup" aria-label="Rodapé do e-mail">
                    {[['nenhum', 'Nenhum'], ['iphone', 'iPhone'], ['galaxy', 'Galaxy']].map(([v, l]) => (
                      <button key={v} type="button" role="radio" aria-checked={prefs.dispositivo === v} className={prefs.dispositivo === v ? 'is-on' : ''} onClick={() => mudarRodape(v)}>{l}</button>
                    ))}
                  </div>
                  <button type="button" className="lv3-link lv3-link--muted" onClick={() => setEditandoAssinatura(true)}>Editar assinatura</button>
                </div>
              )}
              {passo.canal === 'email' && prefs.assinatura_texto && (
                <div className="lv3-sigpreview">
                  <span className="lv3-field__label">Assinatura no envio pela Brevo</span>
                  <pre>{prefs.assinatura_texto}</pre>
                </div>
              )}
              {passo.canal === 'email' && prefs.remetente && (
                prefs.remetente.pode_enviar
                  ? <p className="lv3-muted lv3-op__from">De: {prefs.remetente.nome} &lt;{prefs.remetente.email}&gt; · a resposta cai na sua caixa</p>
                  : <p className="lv3-op__warn"><Icon name="triangle-exclamation"/>Seu login ({prefs.remetente.email || 'sem e-mail'}) não é @centralcomm.media: o envio pela Brevo fica desligado. Use "Abrir no Gmail".</p>
              )}
            </>
          )}
        </div>

      {editandoAssinatura && <SignatureDialog api={api} prefs={prefs} notify={notify} onClose={() => setEditandoAssinatura(false)}
        onSaved={salvo => setPrefs(p => ({...p, ...salvo}))}/>}
      <div className="lv3-op__actions">
        {podeEnviar && texto && (
          <Button variant="primary" icon="paper-plane" onClick={enviar} disabled={!!busy}>{busy === 'enviar' ? 'Enviando…' : 'Enviar'}</Button>
        )}
        <Button variant={podeEnviar && texto ? 'secondary' : 'primary'} icon={passo.canal === 'linkedin' ? 'arrow-up-right-from-square' : passo.canal === 'telefone' ? 'phone' : passo.canal === 'email' ? 'envelope' : 'paper-plane'} onClick={abrir}>
          {{email: 'Abrir no Gmail', whatsapp: 'Abrir no WhatsApp', linkedin: texto ? 'Copiar e abrir LinkedIn' : 'Abrir LinkedIn', telefone: 'Ligar'}[passo.canal] || 'Abrir'}
        </Button>
        {texto && <Button icon="copy" onClick={copiar}>Copiar</Button>}
        {passo.canal === 'email' && item.email && texto && (
          <a className="lv3-btn lv3-btn--ghost lv3-btn--md" href={`mailto:${item.email}?subject=${encodeURIComponent(assunto)}&body=${encodeURIComponent(texto)}`}><Icon name="envelope"/><span>Outro app de e-mail</span></a>
        )}
      </div>
      <div className="lv3-op__actions lv3-op__actions--done">
        <Button variant="primary" icon="check" onClick={acao('feito')} disabled={!!busy}>{busy === 'feito' ? 'Registrando…' : 'Marcar como feito'}</Button>
        <Button icon="reply" onClick={acao('respondeu', 'O que a pessoa respondeu? (opcional)')} disabled={!!busy}>Respondeu</Button>
        <Button variant="ghost" icon="forward" onClick={acao('pular')} disabled={!!busy}>Pular passo</Button>
        <Button variant="ghost" icon="sliders" onClick={() => setGerir(true)} disabled={!!busy} title="Ir para outro passo, adiar ou trocar de fluxo">Gerenciar cadência</Button>
        {gerir && <ManageCadence api={api} inscricao={{...item, status: 'ativa'}} nome={nome} fluxos={fluxos} notify={notify} onClose={() => setGerir(false)} onDone={onDone}/>}
        <Button variant="ghost" icon="pause" onClick={acao('pausar', 'Motivo da pausa (opcional)')} disabled={!!busy}>Pausar</Button>
      </div>
    </div>
  );
}

function DonePanel({item, agora, onOpenLead}) {
  const info = CANAL[item.canal] || CANAL.email;
  const respondeu = item.evento === 'respondeu';
  const prox = item.proximo_passo;
  return (
    <div className="lv3-op__composer">
      <header className="lv3-op__person">
        <div className="lv3-person__avatar lv3-person__avatar--ok" aria-hidden="true"><Icon name={respondeu ? 'reply' : 'check'}/></div>
        <div>
          <h2>{pretty(item.contato_nome) || 'Pessoa'}{item.golden && <span className="lv3-gc-badge">Golden Circle</span>}</h2>
          <p>{decode(item.empresa)}</p>
        </div>
      </header>
      <div className="lv3-op__step">
        <span className="lv3-op__stepicon lv3-op__stepicon--ok"><Icon name={respondeu ? 'reply' : info.icon}/></span>
        <div>
          <strong>{respondeu ? 'Respondeu' : (item.titulo || `${info.label} feito`)}</strong>
          <span className="lv3-muted">{item.cadencia ? `${item.cadencia} · ` : ''}hoje às {String(item.ocorreu_em).slice(11, 16)}</span>
        </div>
      </div>
      {item.canal === 'email' && item.ultimo_email && <p className="lv3-op__lastmail"><span className="lv3-muted">E-mail:</span> <EmailSeal ultimo={item.ultimo_email} agora={agora} full/></p>}
      <div className="lv3-card lv3-op__next">
        <h4>Próximo toque</h4>
        {item.status_cadencia === 'ativa' && prox ? (
          <p><Icon name={(CANAL[prox.canal] || CANAL.email).icon}/> <strong>{prox.titulo}</strong> · {rotuloDia(item.proxima_em)}</p>
        ) : item.status_cadencia === 'respondeu' ? (
          <p>A cadência parou porque a pessoa respondeu. Siga a conversa e registre o próximo passo na mesa.</p>
        ) : item.status_cadencia === 'concluida' ? (
          <p>Cadência concluída. Avalie na mesa se vale uma nova cadência ou outro canal.</p>
        ) : <p className="lv3-muted">Sem próximo toque agendado.</p>}
      </div>
      <div className="lv3-op__actions">
        <Button icon="arrow-right" onClick={() => onOpenLead(item.id_lead)}>Abrir na mesa</Button>
      </div>
    </div>
  );
}

function TaskPanel({api, item, notify, onDone, onOpenLead}) {
  const [busy, setBusy] = useState(false);
  const concluir = async () => {
    setBusy(true);
    try { await api.toggleActivity(item.id, true); notify('Tarefa concluída.'); onDone(); }
    catch (error) { notify(error.message, 'error'); setBusy(false); }
  };
  return (
    <div className="lv3-op__composer">
      <header className="lv3-op__person">
        <div className="lv3-person__avatar" aria-hidden="true"><Icon name="list-check"/></div>
        <div>
          <h2>{TIPO_TAREFA[item.tipo] || 'Tarefa'}{item.golden && <span className="lv3-gc-badge">Golden Circle</span>}</h2>
          <p>{[decode(item.empresa), pretty(item.contato_nome)].filter(Boolean).join(' · ')} · prazo {formatDate(item.data_prazo)} ({atraso(item.data_prazo)})</p>
        </div>
      </header>
      <div className="lv3-card lv3-op__task">{decode(item.descricao)}</div>
      <div className="lv3-op__actions">
        <Button variant="primary" icon="check" onClick={concluir} disabled={busy}>{busy ? 'Concluindo…' : 'Concluir tarefa'}</Button>
        <Button icon="arrow-right" onClick={() => onOpenLead(item.id_lead)}>Abrir na mesa</Button>
      </div>
    </div>
  );
}

function CompanyPanel({api, leadId, notify, onOpenLead, onPauta}) {
  const [lead, setLead] = useState(null);
  const [conta, setConta] = useState(null);
  const [contacts, setContacts] = useState([]);
  const load = useCallback(async () => {
    try {
      const [l, g, c] = await Promise.all([api.lead(leadId), api.leadGolden(leadId).catch(() => null), api.contacts(leadId).catch(() => [])]);
      setLead(l); setConta(g); setContacts(c);
    } catch (error) { notify(error.message, 'error'); }
  }, [api, leadId, notify]);
  useEffect(() => { setLead(null); load(); }, [load]);
  if (!lead) return <div className="lv3-skeleton"/>;
  const nome = decode(lead.empresa || lead.nome);
  return (
    <div className="lv3-op__company">
      <header className="lv3-op__companyhead">
        <h3>{nome}</h3>
        <div className="lv3-section__tools">
          <a className="lv3-iconbtn" href={linkedinSearchUrl(nome)} target="_blank" rel="noopener noreferrer" title="Empresa no LinkedIn"><Icon name="user-group"/></a>
          <button type="button" className="lv3-iconbtn" title="Abrir na mesa" onClick={() => onOpenLead(leadId)}><Icon name="arrow-right"/></button>
        </div>
      </header>
      {conta && (
        <section className="lv3-op__block">
          <h4><Icon name="bullseye"/>Alvo Golden Circle</h4>
          <GoldenTarget api={api} conta={conta} contacts={contacts} notify={notify} onChanged={load}/>
        </section>
      )}
      <section className="lv3-op__block">
        <h4><Icon name="crosshairs"/>Foco: canais e conteúdo</h4>
        <FocusEditor api={api} lead={lead} notify={notify} onChanged={load} compact/>
      </section>
      <section className="lv3-op__block">
        <h4><Icon name="newspaper"/>Pauta: ganchos com fonte</h4>
        <MarketContext api={api} lead={lead} notify={notify} onChanged={() => { load(); onPauta(); }}/>
      </section>
    </div>
  );
}

export function Operacao({boot, api, executivo, setExecutivo, notify, onOpenLead}) {
  const [data, setData] = useState({passos: [], tarefas: [], proximos: [], feitos: []});
  const [aba, setAba] = useState('hoje');
  const [state, setState] = useState({loading: true, error: ''});
  const [selected, setSelected] = useState(null); // {tipo, id}
  const [pautaVersao, setPautaVersao] = useState(0); // pesquisa ou estrela na pauta recarrega os ganchos do composer
  const [fluxos, setFluxos] = useState([]);
  useEffect(() => { api.cadenceModels().then(setFluxos).catch(() => setFluxos([])); }, [api]);

  const load = useCallback(async () => {
    setState(s => ({...s, loading: true, error: ''}));
    try {
      const d = await api.operation(/^\d+$/.test(executivo) ? executivo : '');
      setData(d);
      setState({loading: false, error: ''});
      setSelected(sel => {
        const existe = sel && (LISTA[sel.tipo] ? (d[LISTA[sel.tipo]] || []).some(i => i.id === sel.id) : false);
        if (existe) return sel;
        // O passo feito saiu de "Hoje": segue para a próxima pendência (o feito aparece em "Feitos hoje").
        if (d.passos[0]) return {tipo: 'passo', id: d.passos[0].id};
        if (d.tarefas[0]) return {tipo: 'tarefa', id: d.tarefas[0].id};
        return null;
      });
    } catch (error) { setState({loading: false, error: error.message}); }
  }, [api, executivo]);
  useEffect(() => { load(); }, [load]);

  const item = useMemo(() => {
    if (!selected) return null;
    return (data[LISTA[selected.tipo]] || []).find(i => i.id === selected.id) || null;
  }, [selected, data]);

  const total = data.passos.length + data.tarefas.length;
  const proximos = data.proximos || [];
  const feitos = data.feitos || [];
  const porDia = proximos.reduce((grupos, p) => {
    const chave = String(p.proxima_em).slice(0, 10);
    (grupos[chave] = grupos[chave] || []).push(p);
    return grupos;
  }, {});
  const itemPasso = (p, tipo) => {
    const info = CANAL[p.passo?.canal] || CANAL.email;
    const late = atraso(p.proxima_em);
    return (
      <li key={`${tipo}${p.id}`}>
        <button type="button" className={`lv3-op__item ${selected?.tipo === tipo && selected.id === p.id ? 'is-active' : ''}`} onClick={() => setSelected({tipo, id: p.id})}>
          <span className="lv3-op__itemicon"><Icon name={info.icon}/></span>
          <span className="lv3-op__itembody">
            <span className="lv3-op__itemtop"><strong>{pretty(p.contato_nome)}</strong>{p.golden && <span className="lv3-gc-dot" title="Golden Circle"/>}</span>
            <span className="lv3-op__itemsub">{decode(p.empresa || p.lead_nome)} · {p.passo?.titulo}</span>
            {p.ultimo_email && <EmailSeal ultimo={p.ultimo_email} agora={data.agora}/>}
            <span className={`lv3-op__itemdue ${tipo === 'passo' && late !== 'hoje' ? 'is-late' : ''}`}>{tipo === 'passo' ? late : (CANAL[p.passo?.canal] || CANAL.email).label} · passo {p.passo_atual + 1}/{p.total}</span>
          </span>
        </button>
      </li>
    );
  };
  return (
    <div className="lv3-op">
      <aside className="lv3-col lv3-op__list" aria-label="Pendências">
        <div className="lv3-op__filters">
          <select className="lv3-select" value={executivo} onChange={e => setExecutivo(e.target.value)} aria-label="Executivo">
            <option value="">Todos os executivos</option>
            {boot.executivos.map(e => <option key={e.id} value={String(e.id)}>{e.nome}</option>)}
          </select>
          <button type="button" className="lv3-iconbtn" onClick={load} aria-label="Atualizar" title="Atualizar"><Icon name="rotate-right"/></button>
        </div>
        <div className="lv3-tabs lv3-tabs--queue lv3-op__tabs" role="tablist">
          <button type="button" role="tab" aria-selected={aba === 'hoje'} className={aba === 'hoje' ? 'is-on' : ''} onClick={() => setAba('hoje')}>
            Hoje{total ? <span className="lv3-count">{total}</span> : null}</button>
          <button type="button" role="tab" aria-selected={aba === 'proximos'} className={aba === 'proximos' ? 'is-on' : ''} onClick={() => setAba('proximos')}>
            Próximos{proximos.length ? <span className="lv3-count">{proximos.length}</span> : null}</button>
          <button type="button" role="tab" title="Feitos hoje" aria-selected={aba === 'feitos'} className={aba === 'feitos' ? 'is-on' : ''} onClick={() => setAba('feitos')}>
            Feitos{feitos.length ? <span className="lv3-count">{feitos.length}</span> : null}</button>
        </div>
        {state.error ? (
          <Empty icon="triangle-exclamation" title="Não foi possível carregar">{state.error}</Empty>
        ) : state.loading && !total && !proximos.length && !feitos.length ? (
          <div className="lv3-skeleton"/>
        ) : aba === 'hoje' ? (
          !total ? (
            <Empty icon="mug-hot" title="Nada pendente até hoje">
              {proximos.length ? `${proximos.length} ${proximos.length === 1 ? 'passo agendado' : 'passos agendados'} nos próximos 14 dias: veja em Próximos.` : 'Inscreva as pessoas das contas em cadências na mesa (Pessoas › Iniciar cadência).'}
            </Empty>
          ) : (
            <div className="lv3-op__scroll">
              {data.passos.length > 0 && <h3 className="lv3-op__group">Cadências <span className="lv3-count">{data.passos.length}</span></h3>}
              <ul className="lv3-op__items">{data.passos.map(p => itemPasso(p, 'passo'))}</ul>
              {data.tarefas.length > 0 && <h3 className="lv3-op__group">Tarefas <span className="lv3-count">{data.tarefas.length}</span></h3>}
              <ul className="lv3-op__items">
                {data.tarefas.map(t => (
                  <li key={`t${t.id}`}>
                    <button type="button" className={`lv3-op__item ${selected?.tipo === 'tarefa' && selected.id === t.id ? 'is-active' : ''}`} onClick={() => setSelected({tipo: 'tarefa', id: t.id})}>
                      <span className="lv3-op__itemicon"><Icon name="list-check"/></span>
                      <span className="lv3-op__itembody">
                        <span className="lv3-op__itemtop"><strong>{TIPO_TAREFA[t.tipo] || 'Tarefa'} · {decode(t.empresa)}</strong>{t.golden && <span className="lv3-gc-dot" title="Golden Circle"/>}</span>
                        <span className="lv3-op__itemsub">{decode(t.descricao)}</span>
                        <span className={`lv3-op__itemdue ${atraso(t.data_prazo) !== 'hoje' ? 'is-late' : ''}`}>{atraso(t.data_prazo)}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )
        ) : aba === 'proximos' ? (
          !proximos.length ? <Empty icon="calendar" title="Nada agendado nos próximos 14 dias"/> : (
            <div className="lv3-op__scroll">
              {Object.entries(porDia).map(([dia, itens]) => (
                <React.Fragment key={dia}>
                  <h3 className="lv3-op__group">{rotuloDia(dia)} <span className="lv3-count">{itens.length}</span></h3>
                  <ul className="lv3-op__items">{itens.map(p => itemPasso(p, 'proximo'))}</ul>
                </React.Fragment>
              ))}
            </div>
          )
        ) : (
          !feitos.length ? <Empty icon="circle-check" title="Nada feito hoje ainda">Os passos marcados como feitos aparecem aqui, com o próximo toque de cada pessoa.</Empty> : (
            <div className="lv3-op__scroll">
              <ul className="lv3-op__items">
                {feitos.map(f => {
                  const info = CANAL[f.canal] || CANAL.email;
                  return (
                    <li key={`f${f.id}`}>
                      <button type="button" className={`lv3-op__item ${selected?.tipo === 'feito' && selected.id === f.id ? 'is-active' : ''}`} onClick={() => setSelected({tipo: 'feito', id: f.id})}>
                        <span className="lv3-op__itemicon lv3-op__itemicon--ok"><Icon name={f.evento === 'respondeu' ? 'reply' : 'check'}/></span>
                        <span className="lv3-op__itembody">
                          <span className="lv3-op__itemtop"><strong>{pretty(f.contato_nome) || 'Pessoa'}</strong>{f.golden && <span className="lv3-gc-dot" title="Golden Circle"/>}</span>
                          <span className="lv3-op__itemsub">{decode(f.empresa)} · {f.evento === 'respondeu' ? 'respondeu' : (f.titulo || info.label)}</span>
                          {f.canal === 'email' && f.ultimo_email && <EmailSeal ultimo={f.ultimo_email} agora={data.agora}/>}
                          <span className="lv3-op__itemdue">{String(f.ocorreu_em).slice(11, 16)}{f.status_cadencia === 'ativa' && f.proximo_passo ? ` · próximo: ${f.proximo_passo.titulo} (${rotuloDia(f.proxima_em)})` : ''}</span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )
        )}
      </aside>

      <section className="lv3-col lv3-op__main" aria-label="Pendência selecionada">
        {item ? (
          selected.tipo === 'passo' || selected.tipo === 'proximo'
            ? <StepComposer key={`p${item.id}-${item.passo_atual}`} api={api} item={item} agora={data.agora} fluxos={fluxos} notify={notify} onDone={load} pautaVersao={pautaVersao}/>
            : selected.tipo === 'feito'
              ? <DonePanel key={`f${item.id}`} item={item} agora={data.agora} onOpenLead={onOpenLead}/>
              : <TaskPanel key={`t${item.id}`} api={api} item={item} notify={notify} onDone={load} onOpenLead={onOpenLead}/>
        ) : <Empty icon="hand-pointer" title="Escolha uma pendência"/>}
      </section>

      <aside className="lv3-col lv3-op__side" aria-label="Empresa">
        {item ? <CompanyPanel key={item.id_lead} api={api} leadId={item.id_lead} notify={notify} onOpenLead={onOpenLead} onPauta={() => setPautaVersao(v => v + 1)}/> : <Empty icon="building" title="Sem empresa selecionada"/>}
      </aside>
    </div>
  );
}
