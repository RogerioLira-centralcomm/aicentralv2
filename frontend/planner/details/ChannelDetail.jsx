import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {moduleUrl} from '../api.js';
import {DemographyBars, DetailLayout, Facts, Rail, TagList, hasValue, listText} from './DetailLayout.jsx';

// Percent fields are stored as bare numbers; never double the sign.
const pct = value => (typeof value === 'number' || /^\s*\d+([.,]\d+)?\s*$/.test(String(value ?? ''))) && hasValue(value) ? `${value}%` : value;
const date = value => value ? new Date(value).toLocaleDateString('pt-BR', {day: '2-digit', month: 'short', year: 'numeric'}) : '';

export function ChannelDetail({boot, selection}) {
  const channel = boot.record;
  if (!channel) return <CaduEmptyState title="Canal indisponível" description="Ele pode ter saído do catálogo."/>;
  const formats = channel.formats || [];
  const ads = channel.ad_examples || [];
  const concepts = channel.concepts || [];
  const news = channel.news || [];
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

  const sections = [
    {id: 'papel', label: 'Papel no plano', hidden: !roles.length, hint: 'Como este canal costuma trabalhar num plano. O Cadu ajusta por campanha.',
      render: () => <ul className="pd-roles">{roles.map(role => <li key={role.role}><strong>{role.role}</strong><span>{role.description}</span></li>)}</ul>},
    {id: 'publico', label: 'Quem está no canal', hidden: !hasValue(channel.demografia),
      render: () => <DemographyBars value={channel.demografia}/>},
    {id: 'diferenciais', label: 'Diferenciais', hidden: !hasValue(channel.diferenciais), render: () => <TagList value={channel.diferenciais}/>},
    {id: 'compra', label: 'Como comprar', hidden: !buying.some(([, value]) => hasValue(value)) && !segmentation.length,
      render: () => <><Facts items={buying}/>{segmentation.length > 0 && <><h3 className="pd-subtitle">Segmentação disponível</h3>
        <dl className="pd-segments">{segmentation.map(([title, options]) => <div key={title}><dt>{title}</dt><dd><TagList value={options}/></dd></div>)}</dl></>}</>},
    {id: 'estrategias', label: 'Quando usar cada segmentação', count: playbook.length, hidden: !playbook.length, wide: true,
      render: () => <ul className="pd-playbook">{playbook.map(item => <li key={item.nome}>
        <strong>{item.nome}</strong>
        {item.quando && <p><span>Quando</span>{item.quando}</p>}
        {item.exemplo && <p><span>Exemplo</span>{item.exemplo}</p>}
      </li>)}</ul>},
    {id: 'formatos', label: 'Formatos', count: formats.length, wide: true,
      render: () => <Rail empty="Ainda não há formatos cadastrados para este canal." items={formats.map(format => ({
        href: `${moduleUrl(boot.urls, 'formatos')}/${format.id}`, title: format.name, icon: 'table',
        subtitle: [format.format_type, format.dimensions].filter(Boolean).join(' · '),
      }))}/>},
    {id: 'exemplos', label: 'Exemplos', count: examples.length, hidden: !examples.length, wide: true,
      hint: concepts.length ? 'Conceitos de ativação são demonstrações do formato, não campanhas reais.' : null,
      render: () => <div className="pd-gallery">{examples.map((item, index) => <figure key={item.url} className={index === 0 ? 'is-lead' : ''}>
        <img src={item.url} alt={item.caption || 'Exemplo de anúncio'} loading="lazy"/>{item.caption && <figcaption>{item.caption}</figcaption>}
      </figure>)}</div>},
    {id: 'novidades', label: 'Novidades', count: news.length, hidden: !news.length,
      render: () => <ul className="pd-news">{news.map(item => <li key={`${item.titulo}-${item.data_publicacao}`}>
        <small>{[item.fonte, date(item.data_publicacao)].filter(Boolean).join(' · ')}</small>
        <strong>{item.fonte_url ? <a href={item.fonte_url} target="_blank" rel="noreferrer">{item.titulo}</a> : item.titulo}</strong>
        {item.resumo && <p>{item.resumo}</p>}
      </li>)}</ul>},
  ];

  return <DetailLayout boot={boot} selection={selection} kind="canais" record={channel} icon="share"
    eyebrow={[channel.categoria, channel.tipo].filter(Boolean).join(' · ') || 'Canal'}
    media={channel.hero_image_url ? {type: 'image', src: channel.hero_image_url} : (channel.gallery?.[0]?.url ? {type: 'image', src: channel.gallery[0].url} : null)}
    metrics={[
      {label: 'Alcance', value: channel.alcance, hint: 'Declarado pelo canal'},
      {label: 'Usuários únicos', value: channel.usuarios_unicos},
      {label: 'Tempo médio', value: channel.tempo_medio},
      {label: 'Viewability', value: pct(channel.viewability)},
      {label: 'Taxa de conclusão', value: pct(channel.completion_rate)},
      {label: 'Engajamento', value: pct(channel.taxa_engajamento)},
    ]}
    sections={sections}/>;
}
