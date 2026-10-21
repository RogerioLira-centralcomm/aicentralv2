import React, {useState} from 'react';
import {Button, Icon, Modal, todayLocal} from './ui.jsx';
import {FlowSelect} from './Fluxos.jsx';

// Controle do executivo sobre a cadência: mudar de passo, adiar o próximo toque e trocar de fluxo
// (por pessoa ou para a conta toda). Cada ação fica registrada no histórico do lead.
const CANAL = {email: 'e-mail', whatsapp: 'WhatsApp', linkedin: 'LinkedIn', telefone: 'ligação'};
const rotuloPasso = (p, i) => `${i + 1}. D${p.dia} · ${CANAL[p.canal] || p.canal} · ${p.etapa || ''} · ${p.titulo || 'sem título'}`;

function PassoSelect({passos, value, onChange, label, atual}) {
  return (
    <select className="lv3-select lv3-select--sm" value={value} onChange={event => onChange(Number(event.target.value))} aria-label={label}>
      {(passos || []).map((p, i) => <option key={i} value={i}>{rotuloPasso(p, i)}{i === atual ? ' (atual)' : ''}</option>)}
    </select>
  );
}

/** Painel de uma cadência em andamento (ativa ou pausada). `inscricao` traz passos, passo_atual e id_cadencia. */
export function ManageCadence({api, inscricao, nome, fluxos, notify, onClose, onDone}) {
  const passos = inscricao.passos || [];
  const ativa = inscricao.status === 'ativa';
  const [passo, setPasso] = useState(Math.min(inscricao.passo_atual + 1, Math.max(passos.length - 1, 0)));
  const [data, setData] = useState(todayLocal());
  const outros = fluxos.filter(f => f.id !== inscricao.id_cadencia);
  const [destino, setDestino] = useState(String(outros[0]?.id || ''));
  const fluxoDestino = fluxos.find(f => String(f.id) === destino);
  const [passoDestino, setPassoDestino] = useState(0);
  const [busy, setBusy] = useState('');

  const run = (key, fn, msg) => async () => {
    setBusy(key);
    try { await fn(); notify(msg); onDone(); onClose(); } catch (error) { notify(error.message, 'error'); setBusy(''); }
  };

  return (
    <Modal title={`Cadência de ${nome}`} onClose={onClose} width={640}>
      <p className="lv3-manage__now">
        <Icon name={ativa ? 'circle-play' : 'circle-pause'}/>
        <span><strong>{inscricao.cadencia}</strong> · {ativa ? 'ativa' : 'pausada'} · passo {Math.min(inscricao.passo_atual + 1, passos.length)} de {passos.length}
          {passos[inscricao.passo_atual] ? ` (${passos[inscricao.passo_atual].titulo})` : ''}</span>
      </p>

      <section className="lv3-manage__block">
        <h3>Ir para outro passo</h3>
        <p className="lv3-muted">Para frente ou para trás no mesmo fluxo. {ativa ? 'O passo escolhido entra hoje na Operação.' : 'A cadência continua pausada, já no passo novo.'}</p>
        <div className="lv3-manage__row">
          <PassoSelect passos={passos} value={passo} onChange={setPasso} label="Passo de destino" atual={inscricao.passo_atual}/>
          <Button size="sm" onClick={run('passo', () => api.moveStep(inscricao.id, passo), `Agora no passo ${passo + 1}.`)} disabled={!!busy || passo === inscricao.passo_atual}>Mover</Button>
        </div>
      </section>

      <section className="lv3-manage__block">
        <h3>Adiar o próximo toque</h3>
        <p className="lv3-muted">{ativa ? 'O passo atual some da Operação até a data escolhida.' : 'Retome a cadência para escolher a data.'}</p>
        <div className="lv3-manage__row">
          <input className="lv3-input lv3-input--sm" type="date" value={data} min={todayLocal()} onChange={event => setData(event.target.value)} disabled={!ativa} aria-label="Data do próximo toque"/>
          <Button size="sm" onClick={run('adiar', () => api.reschedule(inscricao.id, data), 'Próximo toque remarcado.')} disabled={!!busy || !ativa || !data}>Adiar</Button>
        </div>
      </section>

      <section className="lv3-manage__block">
        <h3>Trocar de fluxo</h3>
        <p className="lv3-muted">A cadência atual é encerrada e a pessoa entra no outro fluxo, no passo que você escolher. Útil quando ela muda de momento (respondeu, esfriou, pediu contato).</p>
        {outros.length ? (
          <>
            <div className="lv3-manage__row">
              <FlowSelect fluxos={outros} value={destino} onChange={value => { setDestino(value); setPassoDestino(0); }}/>
            </div>
            {fluxoDestino && (
              <div className="lv3-manage__row">
                <span className="lv3-manage__label">Começar no passo</span>
                <PassoSelect passos={fluxoDestino.passos} value={passoDestino} onChange={setPassoDestino} label="Passo inicial no novo fluxo"/>
              </div>
            )}
            <div className="lv3-manage__row">
              <Button size="sm" variant="primary" icon="shuffle" disabled={!!busy || !destino}
                onClick={run('trocar', () => api.switchFlow(inscricao.id, Number(destino), passoDestino), `${nome} agora está em ${fluxoDestino?.nome}.`)}>
                {busy === 'trocar' ? 'Trocando…' : 'Trocar de fluxo'}
              </Button>
            </div>
          </>
        ) : <p className="lv3-muted">Não há outro fluxo ativo. Crie um na aba Fluxos.</p>}
      </section>
    </Modal>
  );
}

/** Troca o fluxo de todas as pessoas da conta que estão com cadência ativa ou pausada. */
export function SwitchLeadFlow({api, leadId, empresa, total, fluxos, notify, onClose, onDone}) {
  const [destino, setDestino] = useState(String(fluxos[0]?.id || ''));
  const [passo, setPasso] = useState(0);
  const [busy, setBusy] = useState(false);
  const fluxo = fluxos.find(f => String(f.id) === destino);
  const trocar = async () => {
    setBusy(true);
    try {
      const r = await api.switchLeadFlow(leadId, Number(destino), passo);
      notify(r.trocadas ? `${r.trocadas} ${r.trocadas === 1 ? 'pessoa foi' : 'pessoas foram'} para ${fluxo?.nome}.` : 'Ninguém para trocar: todos já estão nesse fluxo.');
      onDone(); onClose();
    } catch (error) { notify(error.message, 'error'); setBusy(false); }
  };
  return (
    <Modal title={`Trocar o fluxo da conta · ${empresa}`} onClose={onClose} width={560}
      footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" icon="shuffle" onClick={trocar} disabled={busy || !destino}>{busy ? 'Trocando…' : `Trocar ${total} ${total === 1 ? 'pessoa' : 'pessoas'}`}</Button></>}>
      <p className="lv3-muted">As cadências em andamento ({total}) são encerradas e as pessoas entram no fluxo escolhido. Quem já está nele fica como está.</p>
      <div className="lv3-manage__row"><FlowSelect fluxos={fluxos} value={destino} onChange={value => { setDestino(value); setPasso(0); }}/></div>
      {fluxo && (
        <div className="lv3-manage__row">
          <span className="lv3-manage__label">Começar no passo</span>
          <PassoSelect passos={fluxo.passos} value={passo} onChange={setPasso} label="Passo inicial"/>
        </div>
      )}
    </Modal>
  );
}
