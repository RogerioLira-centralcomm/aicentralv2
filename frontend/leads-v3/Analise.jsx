import React, {useCallback, useEffect, useState} from 'react';
import {Empty, Icon, decode, formatDate, todayLocal} from './ui.jsx';

const ETAPAS = {
  inbox: 'Inbox', tentativa_contato: 'Tentativa de contato', reuniao_agendada: 'Reunião agendada', nutricao: 'Nutrição',
  contato: 'Em contato', qualificado: 'Qualificado', proposta: 'Proposta', negociacao: 'Negociação',
  nao_qualificado: 'Desqualificado', fechado_ganho: 'Ganho', fechado_perdido: 'Perdido',
};
const CANAL = {email: 'E-mail', whatsapp: 'WhatsApp', linkedin: 'LinkedIn', telefone: 'Ligação'};
const FONTE = {site: 'Site', import: 'Importado', manual: 'Manual', indicacao: 'Indicação', evento: 'Evento', outro: 'Outro'};
const moeda = v => Number(v || 0).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL', maximumFractionDigits: 0});
const num = v => (v == null || v === '' ? '—' : Number(v).toLocaleString('pt-BR', {maximumFractionDigits: 1}));
const pct = (a, b) => (b ? `${Math.round((Number(a) / Number(b)) * 100)}%` : '—');

function diasAtras(n) {
  const d = new Date(); d.setDate(d.getDate() - n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Número de destaque: rótulo, valor e uma linha de contexto (sem gráfico: o número é a mensagem). */
function Stat({label, value, hint, tone}) {
  return (
    <div className={`lv3-stat ${tone ? `lv3-stat--${tone}` : ''}`}>
      <span className="lv3-stat__label">{label}</span>
      <strong className="lv3-stat__value">{value}</strong>
      {hint && <span className="lv3-stat__hint">{hint}</span>}
    </div>
  );
}

function Table({cols, rows, empty, onRow}) {
  if (!rows.length) return <p className="lv3-muted">{empty}</p>;
  return (
    <div className="lv3-table__wrap">
      <table className="lv3-table">
        <thead><tr>{cols.map(c => <th key={c.key} className={c.num ? 'is-num' : ''}>{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id ?? i} className={onRow ? 'is-clickable' : ''} onClick={onRow ? () => onRow(r) : undefined}>
              {cols.map(c => <td key={c.key} className={c.num ? 'is-num' : ''}>{c.render ? c.render(r) : r[c.key] ?? '—'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Analise({boot, api, executivo, setExecutivo, notify, onOpenLead}) {
  const [inicio, setInicio] = useState(diasAtras(90));
  const [fim, setFim] = useState(todayLocal());
  const [dados, setDados] = useState(null);
  const [v3, setV3] = useState(null);
  const [loading, setLoading] = useState(true);
  const exec = /^\d+$/.test(executivo) ? executivo : '';
  const nomeExec = id => boot.executivos.find(e => e.id === id)?.nome || (id ? `#${id}` : 'Sem responsável');

  const load = useCallback(async () => {
    setLoading(true);
    const params = {data_inicio: inicio, data_fim: fim, id_executivo: exec};
    try {
      const [legado, novo] = await Promise.all([api.analyticsLegacy(params), api.analyticsV3(params).catch(() => null)]);
      setDados(legado); setV3(novo);
    } catch (error) { notify(error.message, 'error'); } finally { setLoading(false); }
  }, [api, inicio, fim, exec, notify]);
  useEffect(() => { load(); }, [load]);

  const k = dados?.kpis || {};
  const t = dados?.tempo_conversao || {};
  const ativ = Object.fromEntries((dados?.atividades_executivo || []).map(a => [a.id_executivo, a]));
  const canais = v3?.canais || [];
  const feitos = canais.reduce((s, c) => s + Number(c.feitos || 0), 0);
  const respostas = canais.reduce((s, c) => s + Number(c.respostas || 0), 0);
  const gc = v3?.golden || {};

  return (
    <div className="lv3-an">
      <div className="lv3-an__filters">
        <label className="lv3-pill-select lv3-pill-select--lg is-set" title="De"><Icon name="calendar"/>
          <input type="date" value={inicio} max={fim} onChange={e => setInicio(e.target.value)} aria-label="De"/></label>
        <label className="lv3-pill-select lv3-pill-select--lg is-set" title="Até"><Icon name="calendar-check"/>
          <input type="date" value={fim} min={inicio} onChange={e => setFim(e.target.value)} aria-label="Até"/></label>
        <label className={`lv3-pill-select lv3-pill-select--lg ${exec ? 'is-set' : ''}`} title="Executivo"><Icon name="user"/>
          <select value={exec} onChange={e => setExecutivo(e.target.value)} aria-label="Executivo">
            <option value="">Toda a equipe</option>
            {boot.executivos.map(e => <option key={e.id} value={String(e.id)}>{e.nome}</option>)}
          </select></label>
        <div className="lv3-an__quick">
          {[[30, '30 dias'], [90, '90 dias'], [365, '12 meses']].map(([n, l]) => (
            <button key={n} type="button" className="lv3-chipbtn" onClick={() => { setInicio(diasAtras(n)); setFim(todayLocal()); }}>{l}</button>
          ))}
        </div>
        {loading && <span className="lv3-muted">Atualizando…</span>}
      </div>

      {!dados && loading ? <div className="lv3-skeleton"/> : !dados ? <Empty icon="chart-simple" title="Sem dados"/> : (
        <div className="lv3-an__body">
          <section className="lv3-an__section">
            <h3>Funil no período</h3>
            <div className="lv3-stats">
              <Stat label="Leads que entraram" value={num(k.total_leads)}/>
              <Stat label="Convertidos em cliente" value={num(k.convertidos)} hint={`taxa ${k.taxa_conversao != null ? `${num(k.taxa_conversao)}%` : '—'}`}/>
              <Stat label="Desqualificados" value={num(k.desqualificados)} hint={pct(k.desqualificados, k.total_leads) + ' dos que entraram'}/>
              <Stat label="Perdidos" value={num(k.perdidos)}/>
              <Stat label="Receita fechada" value={moeda(k.receita_total)}/>
              <Stat label="Dias até converter" value={num(t.avg_dias_conversao)} hint={t.min_dias != null ? `de ${Math.round(t.min_dias)} a ${Math.round(t.max_dias)} dias` : 'média'}/>
            </div>
          </section>

          {v3 && (
            <section className="lv3-an__section">
              <h3>Cadências e Golden Circle</h3>
              <div className="lv3-stats">
                <Stat label="Toques feitos" value={num(feitos)} hint="passos de cadência marcados como feitos"/>
                <Stat label="Respostas" value={num(respostas)} hint={`taxa de resposta ${pct(respostas, feitos)}`}/>
                <Stat label="Pessoas em cadência" value={num(v3.inscricoes?.ativas)} hint={`${num(v3.inscricoes?.responderam)} responderam no total`}/>
                <Stat label={`Golden Circle ${String(gc.trimestre || '').replace('-', ' ')}`} value={num(gc.contas)} hint={`${num(gc.em_andamento)} em andamento · ${num(gc.ganhas)} ganhas`}/>
                <Stat label="Contas com os papéis cobertos" value={num(gc.cobertas)} hint={pct(gc.cobertas, gc.contas) + ' das contas'}/>
                <Stat label="Valor-alvo do trimestre" value={moeda(gc.valor_alvo)}/>
              </div>
              <Table empty="Nenhum toque registrado no período." rows={canais}
                cols={[
                  {key: 'canal', label: 'Canal', render: r => CANAL[r.canal] || r.canal},
                  {key: 'feitos', label: 'Toques', num: true},
                  {key: 'respostas', label: 'Respostas', num: true},
                  {key: 'taxa', label: 'Taxa de resposta', num: true, render: r => pct(r.respostas, r.feitos)},
                ]}/>
            </section>
          )}

          <section className="lv3-an__section">
            <h3>Equipe</h3>
            <Table empty="Sem dados de produtividade no período." rows={dados.produtividade_executivo || []}
              cols={[
                {key: 'id_executivo', label: 'Executivo', render: r => nomeExec(r.id_executivo)},
                {key: 'total_leads', label: 'Leads', num: true},
                {key: 'convertidos', label: 'Convertidos', num: true},
                {key: 'taxa_conversao', label: 'Conversão', num: true, render: r => `${num(r.taxa_conversao || 0)}%`},
                {key: 'receita', label: 'Receita', num: true, render: r => moeda(r.receita)},
                {key: 'avg_horas_primeiro_contato', label: '1º contato (h)', num: true, render: r => num(r.avg_horas_primeiro_contato)},
                {key: 'ativ', label: 'Atividades', num: true, render: r => num(ativ[r.id_executivo]?.total_atividades)},
                {key: 'lig', label: 'Ligações', num: true, render: r => num(ativ[r.id_executivo]?.ligacoes)},
                {key: 'wpp', label: 'WhatsApp', num: true, render: r => num(ativ[r.id_executivo]?.whatsapp)},
                {key: 'mail', label: 'E-mails', num: true, render: r => num(ativ[r.id_executivo]?.emails)},
                {key: 'reu', label: 'Reuniões', num: true, render: r => num(ativ[r.id_executivo]?.reunioes)},
              ]}/>
          </section>

          <section className="lv3-an__section">
            <h3>Tempo por etapa</h3>
            <Table empty="Sem mudanças de etapa no período." rows={dados.tempo_por_status || []}
              cols={[
                {key: 'status_destino', label: 'Chegou em', render: r => ETAPAS[r.status_destino] || r.status_destino},
                {key: 'transicoes', label: 'Leads', num: true},
                {key: 'avg_dias_desde_criacao', label: 'Dias desde a entrada (média)', num: true, render: r => num(r.avg_dias_desde_criacao)},
              ]}/>
          </section>

          <section className="lv3-an__section">
            <h3>Desqualificados no período <span className="lv3-count">{(dados.desqualificados || []).length}</span></h3>
            <Table empty="Nenhum lead desqualificado no período." rows={dados.desqualificados || []} onRow={r => r.id && onOpenLead(r.id)}
              cols={[
                {key: 'empresa', label: 'Empresa', render: r => decode(r.empresa || r.nome)},
                {key: 'motivo_desqualificacao', label: 'Motivo'},
                {key: 'id_executivo', label: 'Executivo', render: r => nomeExec(r.id_executivo)},
                {key: 'fonte', label: 'Origem', render: r => FONTE[r.fonte] || r.fonte || '—'},
                {key: 'updated_at', label: 'Quando', render: r => (r.updated_at ? formatDate(String(r.updated_at)).slice(0, 10) : '—')},
              ]}/>
          </section>
        </div>
      )}
    </div>
  );
}
