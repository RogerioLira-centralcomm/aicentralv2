import React, {useMemo, useState} from 'react';
import {CaduButton} from '../cadu-design-system/components/CaduButton.jsx';
import {Icon} from '../cadu-design-system/components/Icon.jsx';
import {PlannerSelect} from './PlannerSelect.jsx';
import {LogoTile} from './PlannerUi.jsx';
import {AngleGroups} from './RadarDetail.jsx';
import {RadarGlyph, stamp, themeOf} from './RadarHub.jsx';
import './radar-results.css';

const TYPE = {midia: ['Mídia', 'midia'], conteudo: ['Pauta', 'pauta'], inteligencia: ['Para saber', 'tendencias']};
const STATUS = {nova: ['Nova', 'new'], salva: ['Salva', 'saved'], em_plano: ['Em plano', 'plan']};
const ORDERS = [{value: 'recent', label: 'Mais recentes'}, {value: 'signals', label: 'Mais sinais'}];
const PAUTAS_VISIBLE = 5;
const CHANNELS_VISIBLE = 4;

const subjectOf = item => detailOf(item).subject;
const detailOf = item => item.score_breakdown || {};
const kindOf = item => detailOf(item).type;

/** Canais sugeridos de um ângulo de mídia: logos do catálogo e "+N" para o resto. */
function Channels({item}) {
  const media = detailOf(item).media || [];
  if (!media.length) return null;
  const shown = media.slice(0, CHANNELS_VISIBLE);
  return <div className="rr-channels"><small>Canais sugeridos</small>
    <span>{shown.map(entry => <LogoTile key={entry.id} src={entry.logo_path} name={entry.name} icon="share" size="sm" color={entry.color}/>)}
      {media.length > shown.length && <em>+{media.length - shown.length}</em>}</span></div>;
}

function AngleRow({item, open, onToggle, isNew, busy, onPlan, groupProps}) {
  const kind = TYPE[kindOf(item)] || TYPE.inteligencia;
  const inPlan = item.status === 'em_plano';
  const content = detailOf(item).content || {};
  return <li className={`rr-row${open ? ' is-open' : ''}`}>
    <div className="rr-angle">
      <span className={`rr-icon is-${kindOf(item) || 'inteligencia'}`}><RadarGlyph name={themeOf(`${item.title} ${item.thesis}`, kind[1])} size={24}/></span>
      <div className="rr-angle__text"><strong>{item.title}{isNew && <i className="rr-new">Novo</i>}</strong><p>{item.thesis || content.message}</p></div>
      <span className="rr-tag">{subjectOf(item) || kind[0]}</span>
      <Channels item={item}/>
      <dl className="rr-meta"><div><dt>Sinais</dt><dd>{(item.signal_ids || []).length}</dd></div><div><dt>Atualizado</dt><dd>{stamp(item.created_at)}</dd></div></dl>
      <span className="rr-action">{kindOf(item) === 'midia'
        ? <CaduButton size="sm" variant="secondary" loading={busy} disabled={inPlan} onClick={() => onPlan(item)}>{inPlan ? 'Já virou plano' : 'Criar planejamento'}</CaduButton> : null}</span>
      <button type="button" className="rr-toggle" aria-expanded={open} aria-label={open ? 'Recolher ângulo' : 'Ver ângulo completo'} onClick={onToggle}><Icon name="chevron" size={16}/></button>
    </div>
    {open && <div className="rr-detail"><AngleGroups angles={[item]} full {...groupProps}/></div>}
  </li>;
}

function PautaTable({pautas, openId, setOpen, freshAngles, pautaState, onPauta, groupProps}) {
  const [all, setAll] = useState(false);
  const [picked, setPicked] = useState(() => new Set());
  const shown = all ? pautas : pautas.slice(0, PAUTAS_VISIBLE);
  const everyone = shown.length > 0 && shown.every(item => picked.has(item.id));
  const toggle = id => setPicked(current => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next; });
  return <div className="rr-table" role="table" aria-label="Pautas de conteúdo">
    <div className="rr-table__head" role="row">
      <input type="checkbox" aria-label="Selecionar todas" checked={everyone} onChange={() => setPicked(everyone ? new Set() : new Set(shown.map(item => item.id)))}/>
      <span>Título</span><span>Resumo</span><span>Canais</span><span>Status</span><span>Atualizado</span><span>Ações</span><span/></div>
    {shown.map(item => {
      const saved = (pautaState[item.id] ?? item.status) === 'salva';
      const status = STATUS[saved ? 'salva' : item.status] || STATUS.nova;
      const content = detailOf(item).content || {};
      return <React.Fragment key={item.id}>
        <div className="rr-table__row" role="row">
          <input type="checkbox" aria-label={`Selecionar ${item.title}`} checked={picked.has(item.id)} onChange={() => toggle(item.id)}/>
          <strong>{item.title}{freshAngles.has(item.id) && <i className="rr-new">Novo</i>}</strong>
          <span className="rr-clamp">{item.thesis || content.message}</span>
          <span className="rr-formats">{(content.channels || []).length > 0
            ? <>{content.channels.slice(0, 3).map(entry => <LogoTile key={entry.id} src={entry.logo_path} name={entry.name} icon="share" size="xs" color={entry.color}/>)}
              {content.channels.length > 3 && <small>+{content.channels.length - 3}</small>}</>
            : (content.formats || []).slice(0, 3).map(tag => <em key={tag}>{tag}</em>)}</span>
          <span className={`rr-status is-${status[1]}`}><i/>{status[0]}</span>
          <span className="rr-when">{stamp(item.created_at)}</span>
          <CaduButton size="sm" variant="secondary" onClick={() => onPauta(item, !saved)}>{saved ? 'Pauta salva' : 'Salvar pauta'}</CaduButton>
          <button type="button" className="rr-toggle" aria-expanded={openId === item.id} aria-label="Ver pauta completa" onClick={() => setOpen(openId === item.id ? '' : item.id)}><Icon name="chevron" size={16}/></button>
        </div>
        {openId === item.id && <div className="rr-detail"><AngleGroups angles={[item]} full {...groupProps}/></div>}
      </React.Fragment>;
    })}
    {pautas.length > PAUTAS_VISIBLE && <button type="button" className="rr-all" onClick={() => setAll(value => !value)}>
      {all ? 'Mostrar menos' : `Ver todas as ${pautas.length} pautas`}<Icon name="chevron" size={14}/></button>}
  </div>;
}

/** Resultados do radar: ângulos em linhas (com canais sugeridos) e pautas em tabela, como no mockup. */
export function RadarResults({angles, freshAngles, planning, onPlan, pautaState, onPauta, groupProps}) {
  const [order, setOrder] = useState('recent');
  const [openId, setOpen] = useState('');
  const sorted = useMemo(() => [...angles].sort((a, b) => order === 'signals'
    ? (b.signal_ids || []).length - (a.signal_ids || []).length : new Date(b.created_at) - new Date(a.created_at)), [angles, order]);
  const strategic = sorted.filter(item => kindOf(item) !== 'conteudo');
  const pautas = sorted.filter(item => kindOf(item) === 'conteudo');
  const props = {...groupProps, changedAngles: freshAngles, pautas: pautaState};
  return <div className="rr">
    <div className="rr-bar"><span className="rr-order"><PlannerSelect ariaLabel="Ordenar" value={order} onChange={setOrder} options={ORDERS}/></span></div>
    {strategic.length > 0 && <section aria-labelledby="rr-angles">
      <header className="rr-title"><div><h2 id="rr-angles">Ângulos estratégicos</h2><p>Principais oportunidades identificadas nesta análise.</p></div>
        <small>{strategic.length} {strategic.length === 1 ? 'ângulo' : 'ângulos'}</small></header>
      <ul className="rr-list">{strategic.map(item => <AngleRow key={item.id} item={item} open={openId === item.id} isNew={freshAngles.has(item.id)}
        onToggle={() => setOpen(openId === item.id ? '' : item.id)} busy={planning === item.id} onPlan={onPlan} groupProps={props}/>)}</ul>
    </section>}
    {pautas.length > 0 && <section aria-labelledby="rr-pautas">
      <header className="rr-title"><div><h2 id="rr-pautas">Pautas de conteúdo</h2><p>Ideias de conteúdo já estruturadas para desenvolvimento.</p></div>
        <small>{pautas.length} {pautas.length === 1 ? 'pauta' : 'pautas'}</small></header>
      <PautaTable pautas={pautas} openId={openId} setOpen={setOpen} freshAngles={freshAngles} pautaState={pautaState} onPauta={onPauta} groupProps={props}/>
    </section>}
  </div>;
}
