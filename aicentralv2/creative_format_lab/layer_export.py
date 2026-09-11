"""HTML do protótipo → camadas percentuais no contrato da Bancada."""

from __future__ import annotations

from html.parser import HTMLParser

from ..creative_compose_library import sanitize_compose_regions

LAYER_BOXES = {
    "layer-safe": ("overlay", 5, 5, 90, 90, 1),
    "layer-ground": ("fundo", 0, 0, 100, 100, 1),
    "layer-cast": ("elenco", 10, 34, 80, 50, 4),
    "layer-meta": ("texto", 66, 8, 28, 16, 12),
    "layer-chips": ("texto", 5, 74, 90, 10, 13),
    "layer-lockup": ("logo", 5, 88, 90, 8, 13),
    "layer-key-visual": ("fundo", 42, 8, 56, 84, 3),
    "layer-visual-mountain-1": ("fundo", 0, 78, 100, 22, 2),
    "layer-visual-mountain-2": ("fundo", 0, 86, 100, 14, 2),
    "layer-visual-mountain-3": ("fundo", 0, 92, 100, 8, 2),
    "layer-sun": ("forma", 70, 16, 10, 18, 4),
    "layer-city": ("fundo", 50, 38, 44, 48, 4),
    "layer-screen": ("video", 59, 20, 30, 32, 5),
    "layer-sofa": ("forma", 48, 70, 42, 16, 5),
    "layer-silhouette": ("forma", 64, 40, 16, 46, 6),
    "layer-head": ("forma", 69, 32, 6, 10, 7),
    "layer-plant": ("forma", 88, 56, 7, 26, 6),
    "layer-ctv-icon": ("icone", 76, 20, 16, 12, 7),
    "layer-brand": ("logo", 6, 7, 28, 8, 12),
    "layer-brand-mark": ("logo", 6, 7, 3, 5, 13),
    "layer-platform": ("texto", 70, 7, 24, 6, 12),
    "layer-copy": ("texto", 6, 22, 38, 42, 12),
    "layer-headline": ("texto", 6, 22, 38, 28, 13),
    "layer-support": ("texto", 6, 52, 32, 10, 13),
    "layer-cta": ("cta", 6, 78, 22, 6, 14),
    "layer-qr": ("icone", 86, 72, 8, 14, 14),
    "layer-tip": ("texto", 82, 64, 12, 5, 14),
    "layer-timeline": ("overlay", 5, 92, 90, 5, 20),
}

SKIP_IDS = {"layer-safe"}


class _StageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_stage = False
        self.depth = 0
        self.layers = []
        self._current = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if not self.in_stage and "stage" in classes:
            self.in_stage = True
            self.depth = 1
            return
        if not self.in_stage:
            return
        self.depth += 1
        layer_id = attrs.get("id") or ""
        if "layer" in classes or layer_id.startswith("layer-"):
            self.layers.append({
                "id": layer_id,
                "classes": classes,
                "text": "",
            })
            self._current = self.layers[-1]
            self._buf = []

    def handle_endtag(self, tag):
        if not self.in_stage:
            return
        if self._current is not None and self._buf:
            text = " ".join("".join(self._buf).split())
            if text and not self._current["text"]:
                self._current["text"] = text
            self._buf = []
            self._current = None
        self.depth -= 1
        if self.depth <= 0:
            self.in_stage = False

    def handle_data(self, data):
        if self._current is not None:
            self._buf.append(data)


def export_layers(html, scene_id="scene_01"):
    parser = _StageParser()
    parser.feed(str(html or ""))
    layers = []
    for item in parser.layers:
        layer_id = item["id"]
        if not layer_id or layer_id in SKIP_IDS:
            continue
        box = LAYER_BOXES.get(layer_id)
        if not box:
            continue
        tipo, x, y, w, h, z = box
        content = {}
        if item["text"] and tipo in {"texto", "cta", "logo"}:
            content["text"] = item["text"][:180]
        layers.append({
            "id": f"{scene_id}-{layer_id}",
            "tipo": tipo,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "z": z,
            "visible": True,
            "content": content,
            "motion": {},
        })
    return sanitize_compose_regions(layers)


def export_scene_cards(scenes):
    cards = []
    for item in scenes or []:
        if not isinstance(item, dict):
            continue
        scene_id = str(item.get("id") or "scene_01")
        html = item.get("html") or ""
        layers = item.get("layers") or export_layers(html, scene_id)
        cards.append({
            "id": scene_id,
            "label": item.get("label") or scene_id,
            "duration": item.get("duration") or 7,
            "role": item.get("role") or "unico",
            "layers": layers,
            "regenerate": ["fundo"],
        })
    return cards
