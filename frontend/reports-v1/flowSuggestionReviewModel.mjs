export function suggestionAlternatives(probabilities,labels) {
  return Object.entries(probabilities||{}).filter(([key,value])=>labels[key]&&Number.isFinite(Number(value)))
    .sort((a,b)=>Number(b[1])-Number(a[1])).slice(0,3)
    .map(([key,value])=>`${labels[key]} ${Math.round(Number(value)*100)}%`).join(' · ');
}
