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
  const commercial = COMMERCIAL.map(([key, label]) => [label, splitList(attributeValue(attributes, key))]).filter(([, items]) => items.length);
  const demographics = portal.demographics && typeof portal.demographics === 'object' ? portal.demographics : null;
  const inherited = portal.popularity_source === 'tranco_parent';
  const place = String(attributeValue(attributes, 'localizacao') || '').trim();

  const shots = (portal.prints || []).filter(shot => shot?.url);
  const cover = portal.thumb_url ? [portal.thumb_url] : [];

  const formats = Array.isArray(portal.ad_formats) ? portal.ad_formats : [];
  const editorias = Array.isArray(portal.site_sections) ? portal.site_sections : [];
  const sellers = Number(portal.ads_txt_records) || 0;
  const programmatic = ['valid', 'partial'].includes(portal.ads_txt_status) || ['detected', 'ads_txt_declared'].includes(portal.programmatic_status);
  const directOnly = ['missing', 'empty', 'invalid'].includes(portal.ads_txt_status) && ['not_detected', 'adsense_native'].includes(portal.programmatic_status);
  const topSeal = portal.featured_rank >= 1 && portal.featured_rank <= 10 ? 'Top 10 nacional' : portal.uf_top ? `Top 10 · ${portal.uf}` : '';
  const coverage = portal.scope === 'nacional_premium' ? 'Nacional' : [place.split('·')[0].trim(), portal.uf].filter(Boolean).join(' · ');
  const audienceText = demographics ? [LEAN[demographics.genero], demographics.idade_dominante && `faixa predominante de ${demographics.idade_dominante} anos`,
    demographics.classe && `classe ${demographics.classe}`].filter(Boolean).join(', ') : '';
  const displayFormats = formats.filter(item => item.size);
  const richFormats = formats.filter(item => !item.size);

  const sections = [
    {id: 'formatos', label: 'Formatos de anúncio', hidden: !formats.length, count: formats.length,
      hint: `Observados na página inicial${portal.signals_checked_at ? ` em ${date(portal.signals_checked_at)}` : ''}. Formatos que carregam sob demanda podem não aparecer aqui.`,
      render: () => <div className="pd-profile">
        {displayFormats.length > 0 && <div><span>Display</span><ul className="pd-chips">{displayFormats.map(item => <li key={item.format}>{item.format} · {item.size.replace('x', '×')}</li>)}</ul></div>}
        {richFormats.length > 0 && <div><span>Vídeo, nativo e conteúdo de marca</span><ul className="pd-chips">{richFormats.map(item => <li key={item.format}>{item.format}</li>)}</ul></div>}
      </div>},
    {id: 'programatica', label: 'Compra programática', hint: portal.ads_txt_checked_at ? `Leitura automática do site em ${date(portal.ads_txt_checked_at)}.` : 'Ainda não lemos o ads.txt deste portal.',
      render: () => <ProgrammaticPanel portal={portal}/>},
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
        caption: `${shot.kind === 'home' ? 'Página inicial' : shot.kind} · capturada em ${date(shot.captured_at)}`}))}/>},
    {id: 'sobre', label: 'Sobre o portal', render: () => <Facts items={[
      ['Cobertura', place || null],
      ['Domínio', portal.domain && <a href={`https://${portal.domain}`} target="_blank" rel="noreferrer">{portal.domain}</a>],
      ['Categoria', portal.category], ['Escopo', portal.scope === 'nacional_premium' ? 'Premium nacional' : portal.uf ? `Regional · ${portal.uf}` : null], ['Título do site', portal.site_title], ['Período da audiência', portal.audience_period], ['Audiência conferida em', date(portal.audience_checked_at)]]}/>},
  ];

  const highlights = [
    ['Compra programática', programmatic ? `Pode ser comprado em programática${sellers > 0 ? `: o ads.txt autoriza ${number(sellers)} vendedores` : ''}.`
      : directOnly ? 'Sem ads.txt utilizável nem tags de programática: a compra é direta, com o comercial do portal.' : ''],
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
      {icon: 'check', label: 'Programática', value: programmatic ? 'Pronta' : directOnly ? 'Venda direta' : null, hint: sellers > 0 ? `${number(sellers)} vendedores autorizados` : null},
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
