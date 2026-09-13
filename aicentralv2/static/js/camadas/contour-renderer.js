export function bindContours(store) {
  const svg = document.getElementById("mcCv2Svg");
  if (!svg) return;

  function paint() {
    const state = store.getState();
    svg.replaceChildren();
    if (state.stageMode !== "masks") return;
    const layer = (state.layers || []).find((item) => item.id === state.selectedLayerId);
    const contours = layer?.metadata?.contours || [];
    const points = layer?.metadata?.points || [];
    const zoom = state.zoom || 1;
    if (zoom < 0.5) {
      contours.forEach((contour) => svg.append(pathFor(contour)));
      return;
    }
    const step = zoom < 1 ? 2 : 1;
    contours.forEach((contour) => svg.append(pathFor(contour)));
    points.forEach((point, index) => {
      if (index % step) return;
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", String(point.x));
      dot.setAttribute("cy", String(point.y));
      dot.setAttribute("r", "0.6");
      dot.setAttribute("fill", "#5eead4");
      svg.append(dot);
    });
  }

  store.subscribe(paint);
  paint();
}

function pathFor(contour) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  node.setAttribute("points", (contour || []).map((item) => `${item.x},${item.y}`).join(" "));
  node.setAttribute("fill", "none");
  node.setAttribute("stroke", "#5eead4");
  node.setAttribute("stroke-width", "0.4");
  return node;
}
