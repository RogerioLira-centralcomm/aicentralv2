// Pure Sankey layout: columns of nodes, links drawn as stroked cubic curves whose width is the session count.
// One scale is shared by every column so a ribbon keeps its width from one end to the other.
export function sankeyLayout({nodes, links}, {width = 960, height = 420, nodeWidth = 14, gap = 12, labelPad = 150} = {}) {
  const columns = [...new Set(nodes.map(node => node.column))].sort((a, b) => a - b);
  const valueOf = node => Math.max(
    links.filter(link => link.target === node.id).reduce((sum, link) => sum + link.value, 0),
    links.filter(link => link.source === node.id).reduce((sum, link) => sum + link.value, 0));
  const placed = nodes.map(node => ({...node, value: valueOf(node)}));
  const byColumn = columns.map(column => placed.filter(node => node.column === column).sort((a, b) => b.value - a.value));
  const scale = Math.min(...byColumn.map(list => {
    const total = list.reduce((sum, node) => sum + node.value, 0);
    return total ? (height - gap * (list.length - 1)) / total : Infinity;
  }));
  const k = Number.isFinite(scale) ? scale : 0;
  const step = columns.length > 1 ? (width - labelPad * 2 - nodeWidth) / (columns.length - 1) : 0;
  byColumn.forEach((list, index) => {
    let y = 0;
    list.forEach(node => {
      node.x = labelPad + index * step; node.y = y; node.h = node.value * k; node.w = nodeWidth;
      y += node.h + gap;
    });
  });
  const index = new Map(placed.map(node => [node.id, node]));
  const outOffset = new Map(placed.map(node => [node.id, 0]));
  const inOffset = new Map(placed.map(node => [node.id, 0]));
  const ordered = [...links].sort((a, b) => index.get(a.target).y - index.get(b.target).y || index.get(a.source).y - index.get(b.source).y);
  const drawn = ordered.map(link => {
    const source = index.get(link.source), target = index.get(link.target), w = link.value * k;
    const y0 = source.y + outOffset.get(source.id) + w / 2, y1 = target.y + inOffset.get(target.id) + w / 2;
    outOffset.set(source.id, outOffset.get(source.id) + w); inOffset.set(target.id, inOffset.get(target.id) + w);
    const x0 = source.x + source.w, x1 = target.x, mid = (x0 + x1) / 2;
    return {...link, width: w, path: `M${x0},${y0} C${mid},${y0} ${mid},${y1} ${x1},${y1}`};
  });
  return {nodes: placed, links: drawn, width, height, scale: k};
}
