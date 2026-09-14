"""Roteiro de cenas a partir do OCR das stills da marca."""

from __future__ import annotations

import json

from ..creative_media.settings import STORYBOARD_MAX, STORYBOARD_MIN
from .swap import read_swap_reference
from .swap_session import slim_context

SCRIPT_SYSTEM = """Você escreve o roteiro de um anúncio em vídeo a partir de stills já lidos.
Responda só com JSON: {"beats":[{"id":"","purpose":"","visual":"","motion":"","hold":"","spoken":""}]}.
Um beat por cena, na mesma ordem e com o mesmo id. purpose é hook, offer, proof ou end.
visual descreve o que já está na foto. motion é um gesto curto. hold diz o que não pode mudar (tipo, preço, logo).
spoken é a fala, vazia se não houver locução. Sem texto fora do JSON."""


def build_video_script(store, payload, user_id=None, text_callable=None):
    data = payload if isinstance(payload, dict) else {}
    ids = [str(item or "").strip() for item in (data.get("scene_ids") or data.get("ref_ids") or []) if str(item or "").strip()]
    if not (STORYBOARD_MIN <= len(ids) <= STORYBOARD_MAX):
        raise ValueError(f"Selecione de {STORYBOARD_MIN} a {STORYBOARD_MAX} cenas.")
    duration = int(data.get("duration") or 8)
    scenes = []
    for ident in ids:
        item, _run = store.find_still(data, ident, user_id=user_id)
        if not item:
            raise ValueError("Uma cena não está na biblioteca da marca.")
        ocr = slim_context(item.get("ocr")) if isinstance(item.get("ocr"), dict) else None
        if not ocr:
            reference = store.materialize_reference(item.get("image_url") or item.get("image") or "")
            if not reference:
                raise ValueError("Não foi possível ler um still da cena.")
            ocr = slim_context(read_swap_reference({"reference": reference}, text_callable=text_callable)) or {}
        scenes.append(scene_from_ocr(ident, item, ocr))
    script = compose_script(scenes, duration, text_callable)
    return {
        "scenes": scenes,
        "script": script,
        "duration": duration,
    }


def scene_from_ocr(scene_id, item, ocr):
    data = ocr if isinstance(ocr, dict) else {}
    locked = [
        text for text in (
            data.get("headline"),
            data.get("support"),
            data.get("price"),
            data.get("cta"),
            data.get("logo_text"),
            data.get("dates"),
            data.get("venue"),
        ) if text
    ]
    return {
        "id": scene_id,
        "version_id": str(item.get("id") or ""),
        "name": str(item.get("name") or item.get("id") or "Cena"),
        "image_url": item.get("image_url") or item.get("image") or "",
        "headline": str(data.get("headline") or ""),
        "support": str(data.get("support") or ""),
        "cta": str(data.get("cta") or ""),
        "people": int(data.get("faces") or 0),
        "product": str(data.get("style") or ""),
        "setting": str(data.get("venue") or data.get("dates") or ""),
        "locked_type": locked,
        "ocr": data,
    }


def compose_script(scenes, duration, text_callable=None):
    fallback = fallback_script(scenes)
    if text_callable is None:
        return fallback
    try:
        response = text_callable(
            [
                {"role": "system", "content": SCRIPT_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"duration": duration, "scenes": scenes},
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=2400,
        )
        raw = (response or {}).get("message", {}).get("content") if isinstance(response, dict) else response
        parsed = raw if isinstance(raw, dict) else json.loads(str(raw or ""))
        beats = parsed.get("beats") if isinstance(parsed, dict) else None
        if not isinstance(beats, list) or len(beats) != len(scenes):
            return fallback
        aligned = []
        for scene, beat in zip(scenes, beats):
            row = beat if isinstance(beat, dict) else {}
            aligned.append({
                "id": scene["id"],
                "purpose": str(row.get("purpose") or fallback_purpose(scene, scenes.index(scene), len(scenes))),
                "visual": str(row.get("visual") or scene.get("headline") or scene.get("name") or ""),
                "motion": str(row.get("motion") or "Avança para a próxima peça sem saltar."),
                "hold": str(row.get("hold") or ", ".join(scene.get("locked_type") or []) or "Tipo, preço e logo ficam."),
                "spoken": str(row.get("spoken") or ""),
            })
        return {"beats": aligned}
    except Exception:
        return fallback


def fallback_script(scenes):
    total = len(scenes)
    beats = []
    for index, scene in enumerate(scenes):
        beats.append({
            "id": scene["id"],
            "purpose": fallback_purpose(scene, index, total),
            "visual": scene.get("headline") or scene.get("name") or f"Cena {index + 1}",
            "motion": "Avança para a próxima peça sem saltar.",
            "hold": ", ".join(scene.get("locked_type") or []) or "Tipo, preço e logo ficam.",
            "spoken": "",
        })
    return {"beats": beats}


def fallback_purpose(_scene, index, total):
    if index == 0:
        return "hook"
    if index == total - 1:
        return "end"
    if index == 1 and total > 2:
        return "offer"
    return "proof"
