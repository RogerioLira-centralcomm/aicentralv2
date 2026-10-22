import React from 'react';
import {Button, Empty, Icon, useAsk} from './ui.jsx';

const STATUS = [
  ['planejada', 'Planejada'], ['em_contato', 'Em contato'], ['reuniao', 'Reunião'], ['proposta', 'Proposta'],
  ['ganha', 'Ganha'], ['pausada', 'Pausada'], ['perdida', 'Perdida'],
];
const ROLES = [['marketing', 'Mkt'], ['midia', 'Mídia'], ['criacao', 'Criação'], ['diretoria', 'Dir.']];
const MARCO = {primeira_conversa: '1ª conversa', reuniao: 'Reunião', apresentacao: 'Apresentação', proposta: 'Proposta', fechamento: 'Fechamento'};

/** Trimestre anterior, atual e próximo, a partir do atual (aaaa-Qn). */
export function trimestresProximos(atual) {
  const [ano, q] = atual.split('-Q').map(Number);
  const shift = n => { const idx = ano * 4 + (q - 1) + n; return `${Math.floor(idx / 4)}-Q${(idx % 4) + 1}`; };
  return [shift(-1), atual, shift(1)];
}

export function GoldenCircle({boot, data, loading, error, trimestre, setTrimestre, executivo, activeLeadId,
  onOpen, onAdd, onStatus, onRemove, onReload}) {
  const ask = useAsk();
  const contas = data?.contas || [];
  const nomeExec = id => boot.executivos.find(e => e.id === id)?.nome || `#${id}`;
  const cobertas = contas.filter(c => ROLES.every(([r]) => Number(c[r]) > 0)).length;

  return (
    <>
      <div className="lv3-gc__head">
        <select className="lv3-select" value={trimestre} onChange={event => setTrimestre(event.target.value)} aria-label="Trimestre">
          {trimestresProximos(boot.trimestre).map(t => <option key={t} value={t}>{t.replace('-', ' ')}</option>)}
        </select>
        <Button variant="primary" icon="plus" onClick={onAdd}>Adicionar empresas</Button>
      </div>
      {!loading && contas.length > 0 && (
        <div className="lv3-gc__summary">
          <span><strong>{contas.length}</strong> contas</span>
          <span><strong>{cobertas}</strong> com os 4 papéis</span>
          <span><strong>{contas.reduce((s, c) => s + Number(c.pessoas || 0), 0)}</strong> pessoas</span>
          <button type="button" className="lv3-iconbtn" onClick={onReload} aria-label="Atualizar" title="Atualizar"><Icon name="rotate-right"/></button>
        </div>
      )}
      {error ? (
        <Empty icon="triangle-exclamation" title="Não foi possível carregar">{error}</Empty>
      ) : loading ? (
        <div className="lv3-skeleton"/>
      ) : !contas.length ? (
        <Empty icon="bullseye" title="Nenhuma conta neste trimestre">
          {executivo && /^\d+$/.test(executivo) ? `Adicione as contas-alvo de ${nomeExec(Number(executivo))}.` : 'Escolha um executivo no filtro ou adicione contas.'}
        </Empty>
      ) : (
        <ul className="lv3-queue__list">
          {contas.map(c => (
            <li key={c.id} className={`lv3-gcitem ${c.id_lead && c.id_lead === activeLeadId ? 'is-active' : ''}`}>
              <button type="button" className="lv3-gcitem__main" onClick={() => c.id_lead && onOpen(c.id_lead)} disabled={!c.id_lead}>
                <span className="lv3-qitem__top">
                  <span className="lv3-qitem__name">{c.nome_conta}</span>
                  <span className={`lv3-chip ${c.objetivo === 'expansao' ? 'lv3-chip--brand' : 'lv3-chip--neutral'}`}>{c.objetivo === 'expansao' ? 'Expansão' : 'Captação'}</span>
                </span>
                <span className="lv3-roles">
                  {ROLES.map(([r, label]) => (
                    <span key={r} className={`lv3-role ${Number(c[r]) > 0 ? 'is-on' : ''}`} title={`${c[r] || 0} em ${label}`}>{label}{Number(c[r]) > 1 ? ` ${c[r]}` : ''}</span>
                  ))}
                </span>
                {(c.proximo_marco || c.meta) && (
                  <span className="lv3-gcitem__goal">{c.proximo_marco && <strong>Próximo: {MARCO[c.proximo_marco]}</strong>}{c.proximo_marco && c.meta ? ' · ' : ''}{c.meta}</span>
                )}
                <span className="lv3-qitem__meta">
                  <span>{c.pessoas || 0} pessoas · {c.com_email || 0} com e-mail · {c.cadencias_ativas || 0} em cadência</span>
                  {Number(c.candidatos) > 0 && <span className="lv3-qitem__stale">· {c.candidatos} para revisar</span>}
                  {(!executivo || !/^\d+$/.test(executivo)) && <span>· {nomeExec(c.id_executivo)}</span>}
                </span>
              </button>
              <div className="lv3-gcitem__side">
                <select className="lv3-select lv3-select--xs" value={c.status} onChange={event => onStatus(c.id, event.target.value)} aria-label={`Status de ${c.nome_conta}`}>
                  {STATUS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
                <button type="button" className="lv3-iconbtn lv3-iconbtn--danger" title="Tirar do Golden Circle" aria-label={`Tirar ${c.nome_conta} do Golden Circle`}
                  onClick={async () => {
                    if (await ask({title: 'Tirar do Golden Circle', confirmLabel: 'Tirar', danger: true,
                      message: `Tirar ${c.nome_conta} do Golden Circle ${c.trimestre}? O lead continua na base.`})) onRemove(c.id);
                  }}>
                  <Icon name="xmark"/>
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
