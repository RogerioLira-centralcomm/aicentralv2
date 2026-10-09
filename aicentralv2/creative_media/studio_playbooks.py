"""Playbooks por tipo de criação do Studio (ilustração de interface, landing, site…).

Cada tipo é um arquivo Markdown em ``playbooks/<tipo>.md``: um cabeçalho com chaves simples e três seções.
- ``## Diretor``: entra no prompt de sistema do diretor e prevalece sobre as regras de peça publicitária.
- ``## Imagem``: contrato curto enviado ao modelo de imagem, antes da cena.
- ``## Revisor``: chaves para o revisor automático (``no_text: true``).
Anúncio não tem playbook: segue o pipeline medido no Lab, sem mudança.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "playbooks"
_KEY = re.compile(r"^([a-z_]+):\s*(.*)$")


def _value(raw):
    raw = raw.strip()
    return {"true": True, "false": False}.get(raw.lower(), raw)


def parse(text):
    head, sections, current = {}, {}, None
    body = text
    if text.startswith("---"):
        _, header, body = text.split("---", 2)
        for line in header.strip().splitlines():
            match = _KEY.match(line.strip())
            if match:
                head[match.group(1)] = _value(match.group(2))
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current:
            sections[current].append(line)
    sections = {key: "\n".join(lines).strip() for key, lines in sections.items()}
    review = {}
    for line in sections.get("revisor", "").splitlines():
        match = _KEY.match(line.strip())
        if match:
            review[match.group(1)] = _value(match.group(2))
    return {
        "label": head.get("label") or "",
        "brand": head.get("brand") if head.get("brand") in {"brand_asset", "neutral_asset", "branded_creative"} else "brand_asset",
        "transparent": head.get("transparent") is True,
        "text": head.get("text") or "none",
        "director": sections.get("diretor", ""),
        "image": [line.strip() for line in sections.get("imagem", "").splitlines() if line.strip()],
        "review": review,
    }


@lru_cache(maxsize=32)
def get(kind):
    """Playbook do tipo, ou ``None`` (anúncio e tipos sem arquivo seguem o pipeline de anúncio)."""
    kind = str(kind or "").strip().lower()
    if not re.fullmatch(r"[a-z_]{2,40}", kind):
        return None
    path = ROOT / f"{kind}.md"
    return parse(path.read_text(encoding="utf-8")) if path.is_file() else None


def _rgb(hex_value):
    value = str(hex_value or "").lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) if re.fullmatch(r"[0-9a-fA-F]{6}", value) else None


def key_colour(palette):
    """Cor de recorte: verde puro, ou magenta quando a paleta da marca tem verde (o recorte apagaria a marca)."""
    for rgb in filter(None, map(_rgb, palette or [])):
        if rgb[1] > 120 and rgb[1] > rgb[0] + 40 and rgb[1] > rgb[2] + 20:
            return "#FF00FF"
    return "#00FF00"


def chroma_line(key):
    name = "green" if key == "#00FF00" else "magenta"
    return (f"BACKGROUND: place the whole illustration on one perfectly flat, uniform pure {name} {key} background: no gradient, "
            f"texture, cast shadow, floor, checkerboard or frame. Never use that {name} on the illustration itself; keep crisp "
            f"edges. The {name} is removed afterwards to make the background transparent.")


def key_out(png_bytes, key):
    """PNG com o fundo de recorte transparente (borda suave e sem halo da cor de recorte)."""
    if key == "#00FF00":
        from ..creative_format_lab.chroma_key import chroma_key_png
        return chroma_key_png(png_bytes)
    import io
    import numpy as np
    from PIL import Image
    pixels = np.asarray(Image.open(io.BytesIO(png_bytes)).convert("RGBA")).astype(np.float32)
    rgb = pixels[..., :3]
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    magentaish = border[(border[:, 0] > border[:, 1] + 60) & (border[:, 2] > border[:, 1] + 60)]
    target = np.median(magentaish, axis=0) if len(magentaish) >= 8 else np.array([255, 0, 255], dtype=np.float32)
    distance = np.sqrt(((rgb - target) ** 2).sum(axis=-1))
    keyed = np.clip((distance - 60.0) / 90.0, 0.0, 1.0)
    excess = np.minimum(rgb[..., 0], rgb[..., 2]) - rgb[..., 1]
    edge = (keyed < 1.0) & (excess > 0)
    rgb[..., 0] = np.where(edge, rgb[..., 0] - excess * (1 - keyed) * 0.8, rgb[..., 0])
    rgb[..., 2] = np.where(edge, rgb[..., 2] - excess * (1 - keyed) * 0.8, rgb[..., 2])
    out = np.dstack([np.clip(rgb, 0, 255), np.minimum(pixels[..., 3], keyed * 255.0)]).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(out, "RGBA").save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


# ---- Revisor por tipo --------------------------------------------------------------------------------------------
# O revisor de anúncio julga CTA, cópia e margem; uma ilustração de interface é julgada pelo próprio contrato.
REVIEW_SYSTEM = (
    "You are a senior illustrator reviewing ONE finished interface illustration (shown on a light grey canvas; the grey is "
    "the transparent background). Reply with JSON only:\n"
    '{"visible_text": ["every written word/label you can read, excluding letters that are part of a requested third-party logo"], '
    '"own_logo": true/false, "frames_or_cards": true/false, '
    '"third_party_logos": [{"name": "...", "faithful": true/false}], "clusters": 1, "fills_canvas": true/false, '
    '"finish": "soft_3d|flat|cartoon|photo", "score": 0-100, "notes": "one short sentence"}\n'
    "own_logo = the project's own logo/symbol is drawn anywhere. frames_or_cards = a card, panel, background box, "
    "outer frame, button or navigation bar around or behind the illustration. faithful = the logo matches the real "
    "brand's mark (a made-up letter or blob is not faithful). score judges premium craft and fidelity to the brief."
)
FIXES = {
    "stray_text": "REMOVE every written word, label, caption, number and badge; leave the shapes and icons, without letters.",
    "own_logo": "REMOVE the project's own logo or symbol wherever it was drawn (screens, devices, objects); replace it with a neutral shape in the same color.",
    "frames": "REMOVE every card, panel, background box, outer frame, button and navigation bar; keep only the illustration cluster.",
}


def review(image_b64, book, *, brief="", brand_name="", key=""):
    """Veredito no mesmo formato do revisor de anúncio (approved, reason, score, observation…). Nunca levanta."""
    import base64
    import io
    import json
    import time
    started = time.monotonic()
    try:
        from PIL import Image
        from ..creative_lab import evaluation
        from ..services.openrouter_service import chat_completion, message_text
        raw = base64.b64decode(image_b64)
        if key:
            raw = key_out(raw, key)
        picture = Image.open(io.BytesIO(raw)).convert("RGBA")
        canvas = Image.new("RGBA", picture.size, (238, 240, 243, 255))
        canvas.alpha_composite(picture)
        canvas = canvas.convert("RGB")
        canvas.thumbnail((768, 768))
        buffer = io.BytesIO()
        canvas.save(buffer, "JPEG", quality=85)
        data_url = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        ask = (f"Brief of this illustration: {brief[:900]}\n" if brief else "") + (
            f"The project's own brand is {brand_name}." if brand_name else "")
        result = chat_completion(
            [{"role": "system", "content": REVIEW_SYSTEM},
             {"role": "user", "content": [{"type": "text", "text": ask or "Review this illustration."},
                                          {"type": "image_url", "image_url": {"url": data_url}}]}],
            model=evaluation.OBSERVER_MODEL, max_tokens=900, response_format={"type": "json_object"}, timeout=45, provider="openrouter")
        text = message_text(result.get("message") or {})
        seen = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except Exception:
        return {"reviewed": False, "approved": True, "score": None, "reason": "", "reason_text": ""}
    checks = book.get("review") or {}
    reason = ("stray_text" if checks.get("no_text") and [item for item in seen.get("visible_text") or [] if str(item).strip()]
              else "own_logo" if seen.get("own_logo") and "logo" not in brief.lower()
              else "frames" if seen.get("frames_or_cards") else "")
    fake = [item.get("name") for item in seen.get("third_party_logos") or [] if isinstance(item, dict) and not item.get("faithful")]
    notes = [f"Logos de terceiros não fiéis: {', '.join(filter(None, fake))}." if fake else "",
             "Mais de um agrupamento." if (seen.get("clusters") or 1) > 1 else "",
             "Ocupa pouco do quadro." if seen.get("fills_canvas") is False else "",
             f"Acabamento {seen.get('finish')}." if seen.get("finish") not in (None, "soft_3d") else ""]
    labels = {"stray_text": "Texto escrito na ilustração", "own_logo": "Logo da própria marca sem pedido", "frames": "Moldura, card ou botão em volta"}
    return {"reviewed": True, "approved": not reason, "reason": reason, "reason_text": labels.get(reason, ""),
            "score": int(seen.get("score") or 0), "observation": {**seen, "improvements": [note for note in notes if note]},
            "notes": [note for note in notes if note], "seconds": round(time.monotonic() - started, 1), "kind": "playbook"}


def edit_prompt(verdict, key=""):
    """Correção por edição da melhor versão: só o que a revisão apontou, preservando o resto e o fundo de recorte."""
    lines = ["EDIT THE FIRST IMAGE. It is a finished interface illustration. Keep the cluster, objects, materials, lighting and "
             "palette exactly as they are.", "FIX: " + FIXES.get(verdict.get("reason"), FIXES["stray_text"])]
    if key:
        lines.append(f"Keep the background a perfectly flat {key} with nothing on it.")
    return "\n".join(lines)
