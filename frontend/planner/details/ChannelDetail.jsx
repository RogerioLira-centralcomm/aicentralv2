import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {moduleUrl} from '../api.js';
import {CaduBadge} from '../../cadu-design-system/components/CaduBadge.jsx';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {FormatCards} from '../FormatCards.jsx';
import {SelectionButton} from '../PlannerUi.jsx';
import {DemographyBars, DetailLayout, Facts, Rail, TagList, hasValue, listText} from './DetailLayout.jsx';

// Percent fields are stored as bare numbers; never double the sign.
const pct = value => (typeof value === 'number' || /^\s*\d+([.,]\d+)?\s*$/.test(String(value ?? ''))) && hasValue(value) ? `${value}%` : value;
const date = value => value ? new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'}) : '';

// Icon per role: the card should say what the channel does before the text does.
const ROLE_ICON = [[/captur|busca/i, 'search'], [/alcance|cobertura/i, 'pulse'], [/frequ|contexto/i, 'audio'], [/complement|conex|ativa/i, 'share'], [/convers|venda|perform/i, 'check']];
const roleIcon = role => (ROLE_ICON.find(([pattern]) => pattern.test(role || '')) || [null, 'plan'])[1];
const audienceSize = value => /^\s*[+≈~]?\d/.test(String(value || '')) ? `${String(value).trim()} de pessoas` : String(value || '');

export function ChannelDetail({boot, selection, plan = null}) {
  const channel = boot.record;
  if (!channel) return <CaduEmptyState title="Canal indisponível" description="Ele pode ter saído do catálogo."/>;
  const formats = channel.formats || [];
  const ads = channel.ad_examples || [];
  const concepts = channel.concepts || [];
  const news = channel.news || [];
  const audiences = channel.audiences || [];
  const roles = channel.roles || [];
  // {temporal: {nome: 'Temporal', opcoes: [...]}} or [{nome, opcoes}] → one group of tags each.
  const playbook = (Array.isArray(channel.segmentacoes) ? channel.segmentacoes : []).filter(item => item && typeof item === 'object' && item.nome);
  const segmentation = Object.entries(channel.segmentacao || {})
    .map(([key, value]) => {
      const title = (value && typeof value === 'object' && !Array.isArray(value)) ? (value.nome || value.name || key) : key;
      const options = (value && typeof value === 'object' && !Array.isArray(value)) ? (value.opcoes || value.options || value.valores || listText(Object.values(value))) : value;
      return [String(title).replace(/^./, letter => letter.toUpperCase()), options];
    }).filter(([title, options]) => hasValue(options) && typeof title === 'string' && !/^\d+$/.test(title));
  const buying = [['Modelo de compra', listText(channel.modelo_compra)], ['Mensuração', listText(channel.medicao)],
    ['Brand safety', listText(channel.brand_safety)], ['Produtos', listText(channel.produtos)]];
  const examples = [...ads.map(ad => ({url: ad.image_url, caption: ad.title || ad.source_domain})),
    ...concepts.map(concept => ({url: concept.image_url, caption: `${concept.title} · conceito`}))];

  const photos = [channel.hero_image_url, ...(channel.gallery || []).map(photo => photo.url)].filter((url, index, all) => url && all.indexOf(url) === index);
  const heroMedia = photos.length ? {type: 'carousel', items: photos, illustrative: Boolean(channel.hero_illustrative)} : null;

  const reachSource = channel.fontes_metricas?.alcance || {};
  const profileSource = channel.fontes_metricas?.perfil || {};
  const spec = [['Categoria', channel.categoria], ['Tipo', channel.tipo],
    ['Alcance', [channel.alcance, reachSource.ano && `(${reachSource.ano})`].filter(Boolean).join(' ')],
    ['Formatos', formats.length ? `${formats.length} ${formats.length === 1 ? 'formato' : 'formatos'}` : ''],
    ['Prazo de entrega', listText(channel.prazo_entrega)], ['Integração', listText(channel.integracao)]];

  const sections = [
    {id: 'ficha', label: 'Ficha técnica', hidden: !spec.some(([, value]) => hasValue(value)), hint: 'Os dados essenciais para decidir, num só lugar.',
      render: () => <Facts items={spec}/>},
    {id: 'papel', label: 'Papel no plano', hidden: !roles.length, hint: 'Como este canal costuma trabalhar num plano. O Cadu ajusta por campanha.',
      render: () => <ul className="pd-roles">{roles.map(role => <li key={role.role}><Icon name={roleIcon(role.role)} size={22}/><span><strong>{role.role}</strong><small>{role.description}</small></span></li>)}</ul>},
    {id: 'formatos', label: 'Formatos', count: formats.length, hidden: !formats.length, wide: true, hint: 'Escolha o formato ideal para o seu objetivo.',
      render: () => <FormatCards formats={formats} urls={boot.urls} selection={selection} empty="Ainda não há formatos cadastrados para este canal."/>},
    {id: 'audiencias', label: 'Audiências neste canal', count: audiences.length, hidden: !audiences.length, wide: true,
      hint: 'Segmente por interesses, comportamentos e contextos.',
      render: () => <ul className="pd-audiences pd-audiences--pick">{audiences.map(audience => {
        const selected = selection.isSelected('audiencias', audience.id);
        return <li key={audience.id} className={selected ? 'is-selected' : ''}>
          <button type="button" aria-pressed={selected} onClick={() => selection.toggle('audiencias', audience.id)}>
            <span className="pd-formats__tick" aria-hidden="true"><Icon name={selected ? 'check' : 'plus'} size={14}/></span>
            <strong>{audience.name}</strong>
            <small>{[audience.category, audienceSize(audience.audience)].filter(Boolean).join(' · ')}</small>
          </button>
          <a href={`${moduleUrl(boot.urls, 'audiencias')}/${audience.id}`}>Ver detalhes</a>
        </li>;
      })}</ul>},
    {id: 'exemplos', label: 'Exemplos', count: examples.length, hidden: !examples.length, wide: true,
      hint: concepts.length ? 'Conceitos de ativação são demonstrações do formato, não campanhas reais.' : null,
      render: () => <div className="pd-gallery">{examples.map((item, index) => <figure key={item.url} className={index === 0 ? 'is-lead' : ''}>
        <img src={item.url} alt={item.caption || 'Exemplo de anúncio'} loading="lazy"/>{item.caption && <figcaption>{item.caption}</figcaption>}
      </figure>)}</div>},
    {id: 'diferenciais', label: 'Diferenciais', hidden: !hasValue(channel.diferenciais), render: () => <TagList value={channel.diferenciais}/>},
    {id: 'publico', label: 'Quem está no canal', hidden: !hasValue(channel.demografia),
      render: () => <DemographyBars value={channel.demografia}/>},
    {id: 'compra', label: 'Como comprar', hidden: !buying.some(([, value]) => hasValue(value)) && !segmentation.length,
      render: () => <><Facts items={buying}/>{segmentation.length > 0 && <><h3 className="pd-subtitle">Segmentação disponível</h3>
        <dl className="pd-segments">{segmentation.map(([title, options]) => <div key={title}><dt>{title}</dt><dd><TagList value={options}/></dd></div>)}</dl></>}</>},
    {id: 'estrategias', label: 'Quando usar cada segmentação', count: playbook.length, hidden: !playbook.length, wide: true,
      render: () => <ul className="pd-playbook">{playbook.map(item => <li key={item.nome}>
        <strong>{item.nome}</strong>
        {item.quando && <p><span>Quando</span>{item.quando}</p>}
        {item.exemplo && <p><span>Exemplo</span>{item.exemplo}</p>}
      </li>)}</ul>},
    {id: 'novidades', label: 'Novidades', count: news.length, hidden: !news.length,
      render: () => <ul className="pd-news">{news.map(item => <li key={`${item.titulo}-${item.data_publicacao}`}>
        <small>{[item.fonte, date(item.data_publicacao)].filter(Boolean).join(' · ')}</small>
        <strong>{item.fonte_url ? <a href={item.fonte_url} target="_blank" rel="noreferrer">{item.titulo}</a> : item.titulo}</strong>
        {item.resumo && <p>{item.resumo}</p>}
      </li>)}</ul>},
  ];

  return <DetailLayout boot={boot} selection={selection} kind="canais" record={channel} icon="share"
    eyebrow={[channel.categoria, channel.tipo].filter(Boolean).join(' · ') || 'Canal'}
    media={heroMedia}
    metrics={[
      {icon: 'users', label: 'Alcance', value: channel.alcance, hint: 'Declarado pelo canal'},
      {icon: 'users', label: 'Usuários únicos', value: channel.usuarios_unicos},
      {icon: 'clock', label: 'Tempo médio', value: channel.tempo_medio},
      {icon: 'pulse', label: 'Viewability', value: pct(channel.viewability)},
      {icon: 'check', label: 'Taxa de conclusão', value: pct(channel.completion_rate)},
      {icon: 'pulse', label: 'Engajamento', value: pct(channel.taxa_engajamento)},
    ]}
    highlights={[['Quem você alcança', channel.perfil_audiencia], ['Melhor uso', channel.melhor_uso]]}
    sourceNote={profileSource.pesquisado_em ? `Resumo de fontes públicas, pesquisado em ${date(profileSource.pesquisado_em)}.` : null}
    extraMeta={hasValue(channel.medicao) ? <CaduBadge tone="success">Mensurável</CaduBadge> : null}
    sections={sections}/>;
}
