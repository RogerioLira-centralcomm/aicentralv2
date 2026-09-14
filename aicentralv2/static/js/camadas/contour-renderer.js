import { layerBox } from "./utils.js";

export function bindContours(store) {
  const svg = document.getElementById("mcCv2Svg");
  if (!svg) return;

  function paint() {
    const state = store.getState();
    svg.replaceChildren();
    if (state.comparing || state.stageMode === "html" || state.stageMode === "original") return;
    const layer = (state.layers || []).find((item) => item.id === state.selectedLayerId);
    if (!layer || layer.type === "text") return;
    const contours = layer?.metadata?.contours || [];
    const points = layer?.metadata?.points || [];
    if (!contours.length) {
      const box = layerBox(layer);
      if (box.w && box.h) svg.append(boxFor(box));
    }
    contours.forEach((contour) => svg.append(pathFor(contour)));
    const step = (state.zoom || 1) < 1 ? 2 : 1;
    points.forEach((point, index) => {
      if (index % step) return;
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", String(point.x));
      dot.setAttribute("cy", String(point.y));
      dot.setAttribute("r", "1.1");
      dot.setAttribute("fill", "#2eb8c9");
      dot.setAttribute("fill-opacity", "0.9");
      svg.append(dot);
    });
  }

  store.subscribe(paint);
  paint();
}

function boxFor(box) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  node.setAttribute("x", String(box.x));
  node.setAttribute("y", String(box.y));
  node.setAttribute("width", String(box.w));
  node.setAttribute("height", String(box.h));
  node.setAttribute("fill", "none");
  node.setAttribute("stroke", "#2eb8c9");
  node.setAttribute("stroke-opacity", "0.95");
  node.setAttribute("stroke-width", "1.25");
  return node;
}

function pathFor(contour) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  node.setAttribute("points", (contour || []).map((item) => `${item.x},${item.y}`).join(" "));
  node.setAttribute("fill", "none");
  node.setAttribute("stroke", "#2eb8c9");
  node.setAttribute("stroke-opacity", "0.95");
  node.setAttribute("stroke-width", "1.25");
  node.setAttribute("stroke-dasharray", "3 3");
  return node;
}
