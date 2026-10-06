import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {Icon} from '../../cadu-design-system/components/Icon.jsx';
import {DetailLayout, Facts, Gallery, listText} from './DetailLayout.jsx';

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

  const sections = [
    {id: 'localizacao', label: 'Localização', hidden: !hasCoordinates, hint: 'Este local é um único ponto de mídia.',
      render: () => <><Facts items={[['Coordenadas', coordinates]]}/>
        {place.map_url && <ul className="pd-links"><li><a href={place.map_url} target="_blank" rel="noreferrer"><Icon name="external" size={16}/>Abrir no mapa</a></li></ul>}</>},
    {id: 'fotos', label: 'Fotos', count: rest.length, hidden: !rest.length, wide: true,
      render: () => <Gallery photos={rest.map(photo => ({url: photo.url, title: photo.title}))} name={place.name}/>},
    {id: 'sobre', label: 'Sobre o lugar', render: () => <Facts items={[['Categoria', place.category], ['Cidade', place.city],
      ['Operador', place.operator], ['Código', place.code], ['Formatos', listText(place.formats)]]}/>},
  ];

  return <DetailLayout boot={boot} selection={selection} kind="places" record={{...place, hero_image_url: cover}} icon="browser"
    eyebrow={[place.category, place.city].filter(Boolean).join(' · ')}
    media={heroPhotos.length ? {type: 'carousel', items: heroPhotos} : null}
    metrics={[
      {icon: 'users', label: place.traffic_label || 'Movimento', value: place.traffic},
      {icon: 'pulse', label: 'Audiência', value: place.audience},
      {icon: 'plan', label: 'Cidade', value: place.city},
    ]}
    sections={sections}/>;
}
