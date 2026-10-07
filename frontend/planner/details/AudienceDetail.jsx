import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {moduleUrl} from '../api.js';
import {DetailLayout, Facts, Rail, ReadMore, RelatedList, TagList, hasValue} from './DetailLayout.jsx';
import {FormatCards} from '../FormatCards.jsx';

const PROFILE_GROUP = 'Público, perfil e comportamento';
const DEMOGRAPHY_GROUP = 'Demografia e dispositivos';
const NARRATIVE_GROUP = 'Narrativa e aplicação';
const INDICATORS_GROUP = 'Indicadores estimados';
// Already in the hero numbers or the description.
const SHOWN_ELSEWHERE = new Set(['publico_estimado', 'publico_numero', 'descricao', 'descricao_curta']);
// Fields that read as lists of short items.
const LIST_FIELDS = new Set(['tags', 'interesses_correlatos', 'momentos_chave', 'categorias_alto_desempenho', 'diferenciais_competitivos']);

const fieldsOf = group => (group?.fields || []).filter(field => !SHOWN_ELSEWHERE.has(field.variable) && hasValue(field.value));

/** Long text reads as paragraphs, list-like fields as tags, short values as facts. */
function Narrative({group}) {
  const fields = fieldsOf(group);
  const lists = fields.filter(field => LIST_FIELDS.has(field.variable));
  const long = fields.filter(field => !LIST_FIELDS.has(field.variable) && String(field.value).length > 90);
  const short = fields.filter(field => !lists.includes(field) && !long.includes(field));
  return <>
    {long.length > 0 && <div className="pd-cards">{long.map(field => <div key={field.variable} className="pd-card">
      <h3 className="pd-subtitle">{field.label}</h3><ReadMore text={field.value} limit={160}/></div>)}</div>}
    {lists.map(field => <div key={field.variable}><h3 className="pd-subtitle">{field.label}</h3><TagList value={field.value}/></div>)}
    {short.length > 0 && <Facts items={short.map(field => [field.label, field.value])}/>}
  </>;
}

/** Percentages from the demography group, split into gender, age and devices. */
function Demography({group}) {
  const rows = (group?.fields || []).map(field => [field.variable, field.label, parseFloat(String(field.value).replace(',', '.'))])
    .filter(([, , value]) => Number.isFinite(value));
  const part = (title, prefix) => {
    const items = rows.filter(([variable]) => variable.startsWith(prefix));
    // A group where every share is 0 means "not measured", not "nobody".
    return items.some(([, , value]) => value > 0) ? <div><h3>{title}</h3><ul className="planner-bars">{items.map(([variable, label, value]) => <li key={variable}>
      <span>{label}</span><i><b style={{width: `${Math.max(0, Math.min(100, value))}%`}}/></i><strong>{value}%</strong>
    </li>)}</ul></div> : null;
  };
  if (!rows.length) return null;
  return <div className="planner-demography">{part('Gênero', 'demografia_')}{part('Idade', 'idade_')}{part('Dispositivos', 'dispositivo_')}</div>;
}

export function AudienceDetail({boot, selection, plan = null}) {
  const audience = boot.record;
  if (!audience) return <CaduEmptyState title="Audiência indisponível" description="Ela pode ter saído do catálogo."/>;
  const groups = audience.data_groups || [];
  const byTitle = Object.fromEntries(groups.map(group => [group.title, group]));
  const related = audience.related || [];
  const field = variable => groups.flatMap(group => group.fields || []).find(item => item.variable === variable)?.value;
  const cpa = [field('cpa_estimado_min'), field('cpa_estimado_max')].filter(hasValue).join(' a ');
  const demographyRows = (byTitle[DEMOGRAPHY_GROUP]?.fields || []).filter(item => Number.isFinite(parseFloat(String(item.value).replace(',', '.'))));

  const sections = [
    {id: 'perfil', label: 'Quem são', hidden: !fieldsOf(byTitle[PROFILE_GROUP]).length, render: () => <Narrative group={byTitle[PROFILE_GROUP]}/>},
    {id: 'demografia', label: 'Demografia', hidden: !demographyRows.length, render: () => <Demography group={byTitle[DEMOGRAPHY_GROUP]}/>},
    {id: 'uso', label: 'Como usar no plano', hidden: !fieldsOf(byTitle[NARRATIVE_GROUP]).length, render: () => <Narrative group={byTitle[NARRATIVE_GROUP]}/>},
    {id: 'onde', label: 'Onde comprar', hidden: !audience.channel_ref, hint: 'O canal em que esta audiência é ativada.',
      render: () => <Rail items={audience.channel_ref ? [{href: `${moduleUrl(boot.urls, 'canais')}/${audience.channel_ref.id}`, title: audience.channel_ref.name,
        subtitle: audience.channel_ref.category, logo: audience.channel_ref.logo, icon: 'share'}] : []}/>},
    {id: 'formatos', label: 'Formatos para ativar', count: (audience.channel_formats || []).length, hidden: !(audience.channel_formats || []).length, wide: true,
      hint: 'Peças que este canal aceita para alcançar o público.',
      render: () => <FormatCards formats={audience.channel_formats} urls={boot.urls} selection={selection}/>},
  ];

  return <DetailLayout boot={boot} selection={selection} kind="audiencias" record={{...audience, logo_url: audience.platform_logo}} icon="users"
    eyebrow={[audience.category, audience.subcategory].filter(Boolean).join(' · ') || 'Audiência'}
    media={audience.image_url ? {type: 'carousel', items: [audience.image_url]} : null}
    metrics={[
      {icon: 'users', label: 'Público estimado', value: audience.audience},
      {icon: 'share', label: 'Onde comprar', value: audience.channel || 'Portais e programática'},
      {icon: 'pulse', label: 'CTR médio', value: field('ctr_medio_estimado'), hint: 'Estimativa'},
      {icon: 'check', label: 'Conversão', value: field('taxa_conversao_estimada'), hint: 'Estimativa'},
      {icon: 'pulse', label: 'CPA', value: cpa, hint: 'Estimativa'},
      {icon: 'users', label: 'Alcance incremental', value: field('alcance_incremental')},
    ]}
    aside={related.length > 0 ? <RelatedList title="Audiências parecidas" items={related.map(item => ({
      href: `${moduleUrl(boot.urls, 'audiencias')}/${item.id}`, title: item.name, icon: 'users', logo: item.platform_logo,
      subtitle: [item.platform, item.audience].filter(Boolean).join(' · '),
      selected: selection.isSelected('audiencias', item.id), onToggle: () => selection.toggle('audiencias', item.id)}))}/> : null}
    sections={sections}/>;
}
