import React from 'react';
import {Button, Empty, Icon, prettyName, todayLocal} from './ui.jsx';
import {CadenceTrack} from './Operacao.jsx';

const CANAL = {email: 'e-mail', whatsapp: 'WhatsApp', linkedin: 'LinkedIn', telefone: 'ligação'};
const STATUS = {ativa: 'Em andamento', pausada: 'Pausada', respondeu: 'Respondeu', concluida: 'Concluída', cancelada: 'Encerrada', erro: 'Erro'};

function quando(valor) {
  const dia = String(valor || '').slice(0, 10);
  if (!dia) return '';
  if (dia < todayLocal()) return 'atrasado';
  if (dia === todayLocal()) return 'hoje';
  return `${dia.slice(8, 10)}/${dia.slice(5, 7)}`;
}

/** Coluna da conta: em que fluxo e passo cada pessoa está, com atalho para fazer o passo na Operação. */
export function AccountCadences({contacts, cadences, onDo}) {
  const nome = id => prettyName(contacts.find(c => c.id === id)?.nome) || 'Pessoa';
  const andamento = cadences.filter(i => ['ativa', 'pausada'].includes(i.status));
  const encerradas = cadences.filter(i => !['ativa', 'pausada'].includes(i.status));
  const semCadencia = contacts.filter(c => !andamento.some(i => i.id_contato === c.id)).length;

  if (!cadences.length) {
    return <Empty icon="route" title="Ninguém em cadência">Inicie pelo cartão da pessoa em Pessoas (botão Cadência) ou "Cadência para todos".</Empty>;
  }
  return (
    <div className="lv3-cads">
      {andamento.map(i => {
        const passo = i.passo || {};
        return (
          <article key={i.id} className={`lv3-cad is-${i.status}`}>
            <header className="lv3-cad__head">
              <strong>{nome(i.id_contato)}</strong>
              <span className={`lv3-cad__status is-${i.status}`}>{STATUS[i.status]}</span>
            </header>
            <p className="lv3-cad__flow">{i.cadencia} · passo {i.passo_atual + 1} de {i.total}</p>
            <CadenceTrack item={i} compact/>
            {i.status === 'ativa' ? (
              <div className="lv3-cad__next">
                <span><Icon name="arrow-right"/>{passo.titulo || 'Próximo passo'} · {CANAL[passo.canal] || passo.canal} · <b>{quando(i.proxima_em)}</b></span>
                <Button size="sm" variant="primary" icon="bolt" onClick={() => onDo(i.id)}>Fazer na Operação</Button>
              </div>
            ) : <p className="lv3-muted lv3-cad__why">{i.motivo_parada || 'Pausada sem motivo registrado.'}</p>}
          </article>
        );
      })}
      {semCadencia > 0 && <p className="lv3-muted lv3-cad__hint">{semCadencia} {semCadencia === 1 ? 'pessoa sem cadência' : 'pessoas sem cadência'}: inicie pelo cartão em Pessoas.</p>}
      {encerradas.length > 0 && (
        <details className="lv3-cad__done">
          <summary>Encerradas ({encerradas.length})</summary>
          <ul>
            {encerradas.map(i => (
              <li key={i.id}><strong>{nome(i.id_contato)}</strong> · {i.cadencia} · {STATUS[i.status] || i.status}{i.motivo_parada ? `: ${i.motivo_parada}` : ''}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
