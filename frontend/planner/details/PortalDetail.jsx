import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {DetailLayout, Facts, Gallery} from './DetailLayout.jsx';
import {moduleUrl} from '../api.js';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {FormatPreview} from '../FormatPreview.jsx';

// Cadastro fields that help a media planner, in plain words. Everything else we hold is technical and stays out of the page.
const COMMERCIAL = [
  ['modelos_de_negocio_declarados', 'Formatos de publicidade que o portal vende'],
  ['caracteristicas_declaradas', 'Linha editorial e seções'],
];
/** "A, B (x, y), C" -> ["A", "B (x, y)", "C"]: commas inside parentheses do not split. */
function splitList(value) {
  const parts = []; let depth = 0; let current = '';
  for (const char of String(value ?? '')) {
    if (char === '(') depth += 1;
    if (char === ')') depth = Math.max(0, depth - 1);
    if (char === ',' && depth === 0) { parts.push(current.trim()); current = ''; } else current += char;
  }
  parts.push(current.trim());
  return parts.filter(Boolean);
}
const attributeValue = (attributes, key) => attributes.find(entry => String(entry.atributo || '').toLowerCase() === key)?.valor;

const TIER_LABELS = {grande: 'Grande porte', medio: 'Médio porte', pequeno: 'Pequeno porte', nicho: 'Nicho local'};
const LEAN = {masculino: 'Público mais masculino', feminino: 'Público mais feminino', equilibrado: 'Público equilibrado entre homens e mulheres'};

const number = value => Number(value).toLocaleString('pt-BR');
const minutes = seconds => Number(seconds) > 0 ? `${Math.floor(seconds / 60)}min ${String(Math.round(seconds % 60)).padStart(2, '0')}s` : null;
const date = value => value ? new Date(value).toLocaleDateString('pt-BR') : '';

/** An editorial portal: public audience with its source, and what we have read of it. */
export function PortalDetail({boot, selection, plan = null}) {
  const portal = boot.record;
  if (!portal) return <CaduEmptyState title="Portal indisponível" description="Ele pode ter saído do catálogo."/>;
  const attributes = (Array.isArray(portal.public_attributes) ? portal.public_attributes : [])
    .filter(entry => entry && typeof entry === 'object' && entry.atributo !== 'status_curadoria');
  const commercial = COMMERCIAL.map(([key, label]) => [label, splitList(attributeValue(attributes, key))]).filter(([, items]) => items.length);
  const demographics = portal.demographics && typeof portal.demographics === 'object' ? portal.demographics : null;
  const inherited = portal.popularity_source === 'tranco_parent';
  const place = String(attributeValue(attributes, 'localizacao') || '').trim();

  const examples = (portal.ad_examples || []).filter(photo => photo?.url);
  const cover = portal.thumb_url ? [portal.thumb_url] : [];

  const editorias = Array.isArray(portal.site_sections) ? portal.site_sections : [];
  const topSeal = portal.featured_rank >= 1 && portal.featured_rank <= 10 ? 'Top 10 nacional' : portal.uf_top ? `Top 10 · ${portal.uf}` : '';
  const coverage = portal.scope === 'nacional_premium' ? 'Nacional' : [place.split('·')[0].trim(), portal.uf].filter(Boolean).join(' · ');
  const audienceText = demographics ? [LEAN[demographics.genero], demographics.idade_dominante && `faixa predominante de ${demographics.idade_dominante} anos`,
    demographics.classe && `classe ${demographics.classe}`].filter(Boolean).join(', ') : '';
  const groups = {own: portal.formats?.own || [], observed: portal.formats?.observed || []};
  const availableFormats = [...groups.own, ...groups.observed].filter((item, index, items) =>
    items.findIndex(other => (other.id || other.label || other.nome) === (item.id || item.label || item.nome)) === index);
  const formatCount = availableFormats.length;
  const formatLink = (item, label) => item?.id ? <a href={`${moduleUrl(boot.urls, 'formatos')}/${item.id}`}>{label}</a> : label;

  const sections = [
    {id: 'formatos', label: 'Formatos de anúncio', hidden: !formatCount, count: formatCount,
      hint: 'Conheça os formatos e veja as especificações para sua campanha.',
      render: () => <ul className="pd-fcards">{availableFormats.map(item => {
        const label = item.nome || item.label;
        const size = item.size || item.dimensoes;
        const body = <>
          <FormatPreview dimensions={size} name={label} type={item.tipo}/>
          <span className="pd-fcards__text"><strong>{label}</strong>{size && <small>{String(size).replace('x', '×')}</small>}</span>
          {item.id && <Icon name="chevron" size={16}/>}
        </>;
        return <li key={item.id || label}>{item.id ? <a href={`${moduleUrl(boot.urls, 'formatos')}/${item.id}`}>{body}</a> : <div>{body}</div>}</li>;
      })}</ul>},
    {id: 'demografia', label: 'Perfil do público', hidden: !demographics,
      hint: `Estimado pela categoria editorial${demographics?.regiao ? ' e pela região' : ''}; confiança ${demographics?.confianca || 'baixa'}. Não é medição do portal.`,
      render: () => <Facts items={[
        ['Gênero', LEAN[demographics.genero] || null],
        ['Faixa etária predominante', demographics.idade_dominante && `${demographics.idade_dominante} anos`],
        ['Classe social predominante', demographics.classe && `Classe ${demographics.classe}`],
        ['Região', [demographics.regiao, demographics.uf].filter(Boolean).join(' · ') || null]]}/>},
    {id: 'editorias', label: 'Editorias e seções', hidden: !editorias.length, count: editorias.length, hint: 'Onde o anunciante pode se associar a conteúdo.',
      render: () => <ul className="pd-chips">{editorias.map(item => <li key={item}>{item}</li>)}</ul>},
    {id: 'comercial', label: 'Perfil comercial', hidden: !commercial.length, hint: 'O que o portal declara vender e sobre o que escreve.',
      render: () => <div className="pd-profile">{commercial.map(([label, items]) => <div key={label}>
        <span>{label}</span>
        <ul className="pd-chips">{items.map(item => <li key={item}>{item}</li>)}</ul></div>)}</div>},
    {id: 'sobre', label: 'Sobre o portal', render: () => <Facts items={[
      ['Cobertura', place || null],
      ['Domínio', portal.domain && <a href={`https://${portal.domain}`} target="_blank" rel="noreferrer">{portal.domain}</a>],
      ['Categoria', portal.category], ['Escopo', portal.scope === 'nacional_premium' ? 'Premium nacional' : portal.uf ? `Regional · ${portal.uf}` : null], ['Período da audiência', portal.audience_period], ['Audiência conferida em', date(portal.audience_checked_at)]]}/>},
    {id: 'fotos', label: 'Fotos', count: examples.length, wide: true,
      hint: 'Simulações ilustrativas de anúncios por formato. As marcas são exemplos de aplicação.',
      render: () => examples.length ? <Gallery name={portal.name} photos={examples.map(photo => ({...photo,
        caption: [portal.name, photo.format, photo.size?.replace('x', '×'), photo.brand, 'Simulação ilustrativa'].filter(Boolean).join(' · ')}))}/>
        : <p className="planner-muted">Os exemplos de anúncios deste portal estão em preparação.</p>},
  ];

  const highlights = [
    ['Formatos de anúncio', formatCount ? availableFormats.slice(0, 4).map(item => item.nome || item.label).join(', ') + (formatCount > 4 ? ' e outros.' : '.') : ''],
    ['Quem lê (estimado)', audienceText ? `${audienceText.charAt(0).toUpperCase()}${audienceText.slice(1)}.` : ''],
  ];

  return <DetailLayout boot={boot} selection={selection} kind="portais" record={{...portal, logo_url: portal.favicon_url || (portal.domain ? `https://${portal.domain}/favicon.ico` : '')}} icon="library"
    eyebrow={[topSeal, portal.category].filter(Boolean).join(' · ')}
    media={cover.length ? {type: 'carousel', items: cover, illustrative: true} : null}
    highlights={highlights}
    metrics={[
      {icon: 'pulse', label: 'Porte', value: TIER_LABELS[portal.traffic_tier] || null,
        hint: portal.popularity_rank ? `Estimativa pelo ranking público Tranco: #${number(portal.popularity_rank)}${inherited ? ' (do site principal)' : ''}` : 'Estimativa: fora do ranking público Tranco'},
      {icon: 'layout', label: 'Formatos', value: formatCount ? number(formatCount) : null},
      {icon: 'file', label: 'Editorias', value: editorias.length ? number(editorias.length) : null},
      {icon: 'users', label: 'Cobertura', value: coverage || null},
      {icon: 'users', label: 'Audiência pública', value: portal.audience_estimate, hint: portal.audience_source_url
        ? <a href={portal.audience_source_url} target="_blank" rel="noreferrer">Ver fonte</a> : null},
      {icon: 'pulse', label: 'Acessos por mês', value: Number(portal.monthly_visits) > 0 ? number(portal.monthly_visits) : null, hint: portal.metrics_source_url ? <a href={portal.metrics_source_url} target="_blank" rel="noreferrer">Ver fonte</a> : null},
      {icon: 'clock', label: 'Tempo médio na página', value: minutes(portal.avg_time_seconds)},
    ]}
    sections={sections}/>;
}
