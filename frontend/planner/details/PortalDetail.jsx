import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {DetailLayout, Facts, Gallery} from './DetailLayout.jsx';
import {moduleUrl} from '../api.js';

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

const SHOT_KINDS = {home: 'Página inicial', noticia: 'Página de matéria', editoria: 'Página de editoria', anuncio: 'Anúncio no portal'};
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

  const shots = (portal.prints || []).filter(shot => shot?.url);
  const cover = portal.thumb_url ? [portal.thumb_url] : [];

  const formats = Array.isArray(portal.ad_formats) ? portal.ad_formats : [];
  const editorias = Array.isArray(portal.site_sections) ? portal.site_sections : [];
  const programmatic = ['valid', 'partial'].includes(portal.ads_txt_status) || ['detected', 'ads_txt_declared'].includes(portal.programmatic_status);
  const directOnly = ['missing', 'empty', 'invalid'].includes(portal.ads_txt_status) && ['not_detected', 'adsense_native'].includes(portal.programmatic_status);
  const topSeal = portal.featured_rank >= 1 && portal.featured_rank <= 10 ? 'Top 10 nacional' : portal.uf_top ? `Top 10 · ${portal.uf}` : '';
  const coverage = portal.scope === 'nacional_premium' ? 'Nacional' : [place.split('·')[0].trim(), portal.uf].filter(Boolean).join(' · ');
  const audienceText = demographics ? [LEAN[demographics.genero], demographics.idade_dominante && `faixa predominante de ${demographics.idade_dominante} anos`,
    demographics.classe && `classe ${demographics.classe}`].filter(Boolean).join(', ') : '';
  const groups = {own: portal.formats?.own || [], observed: portal.formats?.observed || [], market: portal.formats?.market || []};
  const formatCount = groups.own.length + groups.observed.length + groups.market.length;
  const formatLink = (item, label) => item?.id ? <a href={`${moduleUrl(boot.urls, 'formatos')}/${item.id}`}>{label}</a> : label;

  const sections = [
    {id: 'formatos', label: 'Formatos de anúncio', hidden: !formatCount, count: formatCount,
      hint: 'Do catálogo de Formatos: abra cada um para ver especificações e orientações de criativo.',
      render: () => <div className="pd-profile">
        {groups.own.length > 0 && <div><span>Formatos do portal</span><ul className="pd-chips">{groups.own.map(item => <li key={item.id}>{formatLink(item, `${item.nome}`)}</li>)}</ul></div>}
        {groups.observed.length > 0 && <div><span>Vistos na página inicial{portal.signals_checked_at ? ` em ${date(portal.signals_checked_at)}` : ''}</span>
          <ul className="pd-chips">{groups.observed.map(item => <li key={item.id || item.label}>{formatLink(item.linked ? item : null, `${item.label}${item.size ? ` · ${item.size.replace('x', '×')}` : ''}`)}</li>)}</ul></div>}
        {groups.market.length > 0 && <div><span>Padrão de mercado, a confirmar com o portal</span><ul className="pd-chips is-soft">{groups.market.map(item => <li key={item.id}>{formatLink(item, item.nome)}</li>)}</ul></div>}
      </div>},
    {id: 'compra', label: 'Como comprar', hidden: !programmatic && !directOnly,
      hint: 'Modalidades de compra, a partir do que o portal expõe publicamente.',
      render: () => <ul className="pd-chips">{programmatic ? <><li>Compra programática</li><li>Negociação direta com o comercial</li></> : <li>Negociação direta com o comercial do portal</li>}</ul>},
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
    {id: 'prints', label: 'Como o portal aparece', hidden: !shots.length,
      hint: 'Capturas reais da página, sem edição. O que aparece como anúncio é o que o portal exibiu naquele momento.',
      render: () => <Gallery name={portal.name} photos={shots.map(shot => ({url: shot.url,
        caption: `${SHOT_KINDS[shot.kind] || shot.kind} · capturada em ${date(shot.captured_at)}`}))}/>},
    {id: 'sobre', label: 'Sobre o portal', render: () => <Facts items={[
      ['Cobertura', place || null],
      ['Domínio', portal.domain && <a href={`https://${portal.domain}`} target="_blank" rel="noreferrer">{portal.domain}</a>],
      ['Categoria', portal.category], ['Escopo', portal.scope === 'nacional_premium' ? 'Premium nacional' : portal.uf ? `Regional · ${portal.uf}` : null], ['Período da audiência', portal.audience_period], ['Audiência conferida em', date(portal.audience_checked_at)]]}/>},
  ];

  const highlights = [
    ['Como comprar', programmatic ? 'Disponível em compra programática, além da negociação direta com o comercial do portal.'
      : directOnly ? 'Venda direta: a compra é negociada com o comercial do portal.' : ''],
    ['Formatos de anúncio', formats.length ? `Vimos ${formats.length} ${formats.length === 1 ? 'formato' : 'formatos'} na home: ${formats.slice(0, 4).map(item => item.format).join(', ')}${formats.length > 4 ? ' e outros' : ''}.` : ''],
    ['Quem lê (estimado)', audienceText ? `${audienceText.charAt(0).toUpperCase()}${audienceText.slice(1)}.` : ''],
  ];

  return <DetailLayout boot={boot} selection={selection} kind="portais" record={{...portal, logo_url: portal.favicon_url || (portal.domain ? `https://${portal.domain}/favicon.ico` : '')}} icon="library"
    eyebrow={[topSeal, portal.category].filter(Boolean).join(' · ')}
    media={cover.length || shots.length ? {type: 'carousel', items: [...cover, ...shots.map(shot => shot.url)], illustrative: cover.length > 0} : null}
    highlights={highlights}
    metrics={[
      {icon: 'pulse', label: 'Porte', value: TIER_LABELS[portal.traffic_tier] || null,
        hint: portal.popularity_rank ? `Estimativa pelo ranking público Tranco: #${number(portal.popularity_rank)}${inherited ? ' (do site principal)' : ''}` : 'Estimativa: fora do ranking público Tranco'},
      {icon: 'check', label: 'Programática', value: programmatic ? 'Pronta' : directOnly ? 'Venda direta' : null},
      {icon: 'layout', label: 'Formatos vistos', value: formats.length ? number(formats.length) : null, hint: 'Na página inicial'},
      {icon: 'file', label: 'Editorias', value: editorias.length ? number(editorias.length) : null},
      {icon: 'users', label: 'Cobertura', value: coverage || null},
      {icon: 'users', label: 'Audiência pública', value: portal.audience_estimate, hint: portal.audience_source_url
        ? <a href={portal.audience_source_url} target="_blank" rel="noreferrer">Ver fonte</a> : null},
      {icon: 'pulse', label: 'Acessos por mês', value: Number(portal.monthly_visits) > 0 ? number(portal.monthly_visits) : null, hint: portal.metrics_source_url ? <a href={portal.metrics_source_url} target="_blank" rel="noreferrer">Ver fonte</a> : null},
      {icon: 'clock', label: 'Tempo médio na página', value: minutes(portal.avg_time_seconds)},
    ]}
    sections={sections}/>;
}
