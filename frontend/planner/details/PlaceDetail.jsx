import React from 'react';
import {CaduEmptyState} from '../../cadu-design-system/components/CaduEmptyState.jsx';
import {DetailLayout, Facts, Gallery, TagList, listText} from './DetailLayout.jsx';
import {PlanSidebar} from './PlanSidebar.jsx';

/** A Place: where it is, how many people pass, which media points it sells. */
export function PlaceDetail({boot, selection, plan = null}) {
  const place = boot.record;
  if (!place) return <CaduEmptyState title="Local indisponível" description="Ele pode ter saído do catálogo."/>;
  const gallery = (place.gallery || []).filter(photo => photo?.url);
  const points = place.points || [];
  const cover = place.image_url || gallery[0]?.url;
  // Every photo is in the carousel, so the gallery section is gone.
  const heroPhotos = [cover, ...gallery.map(photo => photo.url).filter(url => url !== cover)].filter(Boolean);
  const rest = [];

  const sections = [
    {id: 'pontos', label: 'Pontos de mídia', count: points.length, hidden: !points.length,
      render: () => <ul className="pd-points">{points.map(point => <li key={point.id || point.name}>
        <strong>{point.name}</strong>
        <span>{[point.kind, point.audience].filter(Boolean).join(' · ')}</span>
        {point.formats && <TagList value={point.formats}/>}
      </li>)}</ul>},
    {id: 'fotos', label: 'Fotos', count: rest.length, hidden: !rest.length, wide: true,
      render: () => <Gallery photos={rest.map(photo => ({url: photo.url, title: photo.title}))} name={place.name}/>},
    {id: 'sobre', label: 'Sobre o lugar', render: () => <Facts items={[['Categoria', place.category], ['Cidade', place.city],
      ['Operador', place.operator], ['Código', place.code], ['Formatos', listText(place.formats)]]}/>},
  ];

  return <DetailLayout boot={boot} selection={selection} kind="places" record={{...place, hero_image_url: cover}} icon="browser"
    eyebrow={[place.category, place.city].filter(Boolean).join(' · ')}
    media={heroPhotos.length ? {type: 'carousel', items: heroPhotos} : null}
    aside={<PlanSidebar plan={plan} selection={selection} boot={boot} plansUrl={boot.urls.plans}/>}
    metrics={[
      {icon: 'users', label: place.traffic_label || 'Movimento', value: place.traffic},
      {icon: 'pulse', label: 'Audiência', value: place.audience},
      {icon: 'plan', label: 'Pontos de mídia', value: points.length || null},
    ]}
    sections={sections}/>;
}
