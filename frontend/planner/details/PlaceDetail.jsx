import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {DetailLayout, Facts, Gallery, OriginBadge, TagList, listText} from './DetailLayout.jsx';

/** A Place is one media point: where it is and how many people pass. */
export function PlaceDetail({boot, selection, plan = null}) {
  const place = boot.record;
  if (!place) return <CaduEmptyState title="Local indisponível" description="Ele pode ter saído do catálogo."/>;
  const gallery = (place.gallery || []).filter(photo => photo?.url);
  const cover = place.image_url || gallery[0]?.url;
  // Every photo is in the carousel, so the gallery section is gone.
  const heroPhotos = [cover, ...gallery.map(photo => photo.url).filter(url => url !== cover)].filter(Boolean);
  const rest = [];

  const hasCoordinates = Number.isFinite(place.lat) && Number.isFinite(place.lng);
  const coordinates = hasCoordinates ? `${place.lat.toFixed(5)}, ${place.lng.toFixed(5)}` : '';

  const DAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
  const week = (place.weekly_movement || []).map((value, index) => [DAYS[index], value]).filter(([, value]) => Number.isFinite(value));
  const peak = Math.max(1, ...week.map(([, value]) => value));

  const sections = [
    {id: 'localizacao', label: 'Localização', hidden: !hasCoordinates, hint: 'Este local é um único ponto de mídia.',
      render: () => <><Facts items={[['Coordenadas', coordinates]]}/>
        {place.map_url && <ul className="pd-links"><li><a href={place.map_url} target="_blank" rel="noreferrer"><Icon name="external" size={16}/>Abrir no mapa</a></li></ul>}</>},
    {id: 'semana', label: 'Movimento na semana', hidden: week.length < 2, hint: 'Pessoas por dia, numa semana típica.',
      render: () => <><ul className="pd-week">{week.map(([day, value]) => <li key={day}>
        <span className="pd-week__bar"><b style={{height: `${Math.round(value * 100 / peak)}%`}}/></span>
        <strong>{value.toLocaleString('pt-BR', {notation: 'compact', maximumFractionDigits: 1})}</strong><small>{day}</small></li>)}</ul>
        <OriginBadge origin={place.weekly_origin}/></>},
    {id: 'fotos', label: 'Fotos', count: rest.length, hidden: !rest.length, wide: true,
      render: () => <Gallery photos={rest.map(photo => ({url: photo.url, title: photo.title}))} name={place.name}/>},
    {id: 'publico', label: 'Quem passa por aqui', hidden: !place.target_audience?.length && !Object.keys(place.demographics || {}).length,
      render: () => <>
        <TagList value={place.target_audience}/>
        <Facts items={[['Faixa etária', place.demographics?.age], ['Gênero', place.demographics?.gender],
          ['Renda', place.demographics?.income], ['Origem', place.demographics?.origin]]}/></>},
    {id: 'canais', label: 'Onde alcançar esse público', hidden: !place.channel_ranking?.length, hint: 'Canais com maior afinidade com quem passa por aqui.',
      render: () => <ol className="pd-text">{place.channel_ranking.map(item => <li key={item.name}><strong>{item.name}</strong>{item.why ? ` — ${item.why}` : ''}</li>)}</ol>},
    {id: 'sobre', label: 'Sobre o lugar', render: () => <Facts items={[['Categoria', place.category], ['Cidade', place.city],
      ['Operador', place.operator], ['Código', place.code], ['Formatos', listText(place.formats)]]}/>},
  ];

  return <DetailLayout boot={boot} selection={selection} kind="places" record={{...place, hero_image_url: cover}} icon="browser"
    eyebrow={[place.category, place.city].filter(Boolean).join(' · ')}
    media={heroPhotos.length ? {type: 'carousel', items: heroPhotos} : null}
    metrics={[
      {icon: 'users', label: place.traffic_label || 'Movimento', value: place.traffic, origin: place.traffic_origin},
      {icon: 'pulse', label: 'Audiência', value: place.audience, origin: place.audience_origin},
      {icon: 'plan', label: 'Cidade', value: place.city},
    ]}
    sections={sections}/>;
}
