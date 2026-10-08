import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {DetailLayout, Facts, Gallery} from './DetailLayout.jsx';

// What we read on the site, as a checklist: can this portal be bought in programmatic?
const ADS_TXT = {valid: ['ok', 'ads.txt válido'], partial: ['warn', 'ads.txt parcial'], empty: ['warn', 'ads.txt vazio'],
  invalid: ['no', 'ads.txt inválido'], missing: ['no', 'Sem ads.txt']};
const PROGRAMMATIC = {detected: ['ok', 'Tags de programática no site'], ads_txt_declared: ['ok', 'Programática declarada no ads.txt'],
  adsense_native: ['warn', 'Só AdSense ou nativo'], not_detected: ['no', 'Sem programática detectada']};
function ProgrammaticPanel({portal}) {
  const rows = [
    ADS_TXT[portal.ads_txt_status] || (portal.ads_txt_status ? ['unknown', 'ads.txt não pôde ser lido'] : null),
    Number(portal.ads_txt_records) > 0 ? ['ok', `${Number(portal.ads_txt_records).toLocaleString('pt-BR')} vendedores autorizados`] : null,
    PROGRAMMATIC[portal.programmatic_status] || (portal.programmatic_status ? ['unknown', 'Site não pôde ser lido'] : null),
  ].filter(Boolean);
  if (!rows.length) return <p className="planner-muted">Verificação pendente: ainda não sabemos se este portal vende programática.</p>;
  const icon = {ok: 'check', warn: 'pulse', no: 'close', unknown: 'search'};
  return <ul className="pd-checks">{rows.map(([state, label]) => <li key={label} className={`is-${state}`}><Icon name={icon[state]} size={16}/>{label}</li>)}</ul>;
}

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
  const pages = Number(portal.discovered_pages_count);
  const commercial = COMMERCIAL.map(([key, label]) => [label, splitList(attributeValue(attributes, key))]).filter(([, items]) => items.length);
  const demographics = portal.demographics && typeof portal.demographics === 'object' ? portal.demographics : null;
  const inherited = portal.popularity_source === 'tranco_parent';
  const place = String(attributeValue(attributes, 'localizacao') || '').trim();

  const shots = (portal.prints || []).filter(shot => shot?.url);

  const sections = [
    {id: 'prints', label: 'Como o portal aparece', hidden: !shots.length,
      hint: 'Capturas reais da página, sem edição. O que aparece como anúncio é o que o portal exibiu naquele momento.',
      render: () => <Gallery name={portal.name} photos={shots.map(shot => ({url: shot.url,
        caption: `${shot.kind === 'home' ? 'Página inicial' : shot.kind} · capturada em ${date(shot.captured_at)}`}))}/>},
    {id: 'programatica', label: 'Pronto para programática', hint: portal.ads_txt_checked_at ? `Leitura automática do site em ${date(portal.ads_txt_checked_at)}.` : 'Ainda não lemos o ads.txt deste portal.',
      render: () => <ProgrammaticPanel portal={portal}/>},
    {id: 'comercial', label: 'Perfil comercial', hidden: !commercial.length, hint: 'O que o portal declara vender e sobre o que escreve.',
      render: () => <div className="pd-profile">{commercial.map(([label, items]) => <div key={label}>
        <span>{label}</span>
        <ul className="pd-chips">{items.map(item => <li key={item}>{item}</li>)}</ul></div>)}</div>},
    {id: 'demografia', label: 'Perfil do público', hidden: !demographics,
      hint: `Estimado pela categoria editorial${demographics?.regiao ? ' e pela região' : ''}; confiança ${demographics?.confianca || 'baixa'}. Não é medição do portal.`,
      render: () => <Facts items={[
        ['Gênero', LEAN[demographics.genero] || null],
        ['Faixa etária predominante', demographics.idade_dominante && `${demographics.idade_dominante} anos`],
        ['Classe social predominante', demographics.classe && `Classe ${demographics.classe}`],
        ['Região', [demographics.regiao, demographics.uf].filter(Boolean).join(' · ') || null]]}/>},
    {id: 'sobre', label: 'Sobre o portal', render: () => <Facts items={[
      ['Cobertura', place || null],
      ['Domínio', portal.domain && <a href={`https://${portal.domain}`} target="_blank" rel="noreferrer">{portal.domain}</a>],
      ['Categoria', portal.category], ['Escopo', portal.scope === 'nacional_premium' ? 'Premium nacional' : portal.uf ? `Regional · ${portal.uf}` : null], ['Título do site', portal.site_title], ['Período da audiência', portal.audience_period], ['Audiência conferida em', date(portal.audience_checked_at)]]}/>},
  ];

  return <DetailLayout boot={boot} selection={selection} kind="portais" record={{...portal, logo_url: portal.favicon_url || (portal.domain ? `https://${portal.domain}/favicon.ico` : '')}} icon="library"
    eyebrow={portal.featured_rank ? 'Destaque' : portal.category}
    media={shots.length ? {type: 'carousel', items: shots.map(shot => shot.url)} : null}
    metrics={[
      {icon: 'pulse', label: 'Porte estimado', value: TIER_LABELS[portal.traffic_tier] || null,
        hint: portal.popularity_rank ? `Ranking público Tranco: #${number(portal.popularity_rank)}${inherited ? ' (do site principal)' : ''}` : 'Fora do ranking público dos 1 milhão de sites mais acessados'},
      {icon: 'users', label: 'Audiência pública', value: portal.audience_estimate, hint: portal.audience_source_url
        ? <a href={portal.audience_source_url} target="_blank" rel="noreferrer">Ver fonte</a> : 'Sem fonte publicada'},
      {icon: 'pulse', label: 'Acessos por mês', value: Number(portal.monthly_visits) > 0 ? number(portal.monthly_visits) : null, hint: portal.metrics_source_url ? <a href={portal.metrics_source_url} target="_blank" rel="noreferrer">Ver fonte</a> : 'Sem fonte publicada'},
      {icon: 'clock', label: 'Tempo médio na página', value: minutes(portal.avg_time_seconds)},
      {icon: 'file', label: 'Páginas lidas', value: pages > 0 ? number(pages) : null, hint: portal.last_crawled_at ? `Última leitura em ${date(portal.last_crawled_at)}` : null},
      {label: 'Leituras', value: Number(portal.crawl_updates_count) > 0 ? number(portal.crawl_updates_count) : null},
    ]}
    sections={sections}/>;
}
