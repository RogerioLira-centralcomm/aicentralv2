"""Revisor automático do Studio: olha a imagem pronta e diz se ela pode ser entregue.

O TypeSafe não enxerga imagem (lê o base64 como texto), então a revisão tem dois passos: um olho rápido
(Haiku 4.5 com um relatório mínimo — texto, logo, extras, corte; ~3 s) e o TypeSafe, que julga esse
relatório mais as medidas por código (texto exato, paleta) em ~0,3 s. Só falhas objetivas rejeitam a
imagem; a correção é uma edição da própria imagem, não uma nova variação. Se o revisor falhar, a imagem
é entregue como está (fail-open): o revisor nunca bloqueia o usuário.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import time

from PIL import Image

logger = logging.getLogger(__name__)

ENABLED = os.getenv("STUDIO_AUTO_REVIEW", "1").strip().lower() not in {"0", "false", "off", "no"}
MIN_SCORE = int(os.getenv("STUDIO_AUTO_REVIEW_MIN_SCORE", "0") or 0)
OBSERVER_TIMEOUT = 45
TYPESAFE_TIMEOUT = 30
CONFIDENCE = 0.6
# Versions per piece: version 1 from the Studio prompt, the rest are edits of the best one. The Studio only goes on
# while the reviewer rejects; the Lab (``modeling.refine_target``) also goes on while the score is below the target.
MAX_ATTEMPTS = max(1, int(os.getenv("STUDIO_AUTO_REVIEW_MAX_ATTEMPTS", "3") or 3))
# Text, CTA and logo closer than this to an edge break the 8% safe margin. The eyes estimate boxes within ~±2%,
# and a 1-2% miss is not worth another generation: only elements clearly at the edge reject the piece.
MARGIN_LIMIT = 5.0
# Falhas que o usuário percebe de imediato e que uma nova tentativa costuma resolver.
REJECT_FAILURES = {"text_rendering", "logo_redrawn", "cropped_content", "identity_changed", "reference_ignored"}
_NUMBER = re.compile(r"\d[\d.,]*")
MARGIN_KINDS = {"headline", "text", "cta", "logo"}
REASONS = {
    "text_rendering": "o texto saiu diferente do pedido",
    "logo_redrawn": "o logo foi redesenhado",
    "cropped_content": "algo importante foi cortado na borda",
    "identity_changed": "o produto ou a pessoa mudou em relação à referência",
    "reference_ignored": "a referência enviada foi ignorada",
    "text_mismatch": "o texto saiu diferente do pedido",
    "cropped": "algo importante foi cortado na borda",
    "margin": "texto, botão ou logo encostado na borda (fora da margem de 8%)",
    "invented_data": "apareceram números ou preços que o pedido não tem",
    "stray_text": "a imagem trouxe texto além do que o Studio aplica (texto repetido)",
    "forbidden": "apareceu um elemento proibido pela marca",
    "low_score": "a nota geral ficou abaixo do mínimo",
}
CORRECTIONS = {
    "text_rendering": "REVIEW FIX: the previous attempt misspelled or changed the required text. Render each required string exactly, letter by letter, accents included, each on its own line, and add no other words.",
    "text_mismatch": "REVIEW FIX: the previous attempt misspelled or changed the required text. Render each required string exactly, letter by letter, accents included, each on its own line, and add no other words.",
    "logo_redrawn": "REVIEW FIX: the previous attempt drew a logo. Draw no logo or brand mark at all; keep the logo zone plain.",
    "cropped_content": "REVIEW FIX: the previous attempt cut content at the edge. Keep text, faces, product and logo fully inside an 8% safe margin.",
    "cropped": "REVIEW FIX: the previous attempt cut content at the edge. Keep text, faces, product and logo fully inside an 8% safe margin.",
    "identity_changed": "REVIEW FIX: the previous attempt altered the product or person. Reproduce the supplied reference faithfully; do not redesign it.",
    "reference_ignored": "REVIEW FIX: the previous attempt ignored a supplied reference. Use every supplied image according to its declared role.",
    "margin": "REVIEW FIX: the previous attempt placed text, button or logo too close to the edge. Keep them at least 8% away from every edge.",
    "forbidden": "REVIEW FIX: the previous attempt showed an element the brand forbids. Remove it and keep the scene clean.",
    "low_score": "REVIEW FIX: the previous attempt was weak. Use one clear focal point, a clean layout and the brand colors.",
}


_EYES_FIELDS = (
    '{"visible_text": [every text line exactly as written, accents and punctuation kept],\n'
    ' "scene": "one sentence: main subject, setting and layout",\n'
    ' "hero": "the element the eye reads first", "reading_order": [elements in reading order],\n'
    ' "logo": {"count": number of logos or brand marks, "looks_redrawn": true if a logo looks invented or distorted},\n'
    ' "unrequested_elements": [icons, badges, seals, UI screens or graphic add-ons that look added; not props of the scene],\n'
    ' "cut_off": [text, face, product or logo cut by the frame edge],\n'
    ' "defects": [visible rendering defects: garbled letters, broken hands, artifacts],\n'
    ' "boxes": [{"kind": "headline|text|cta|logo|face|product", "label": "short", "box": [left, top, right, bottom] '
    'as percent of the canvas width and height, 0-100}]'
)
_IMPROVEMENTS = (
    ',\n "improvements": [up to 4 concrete edits that would make this a better professional ad, most important first: '
    'CTA button design (solid shape, padding, legible label, contrast), hierarchy, contrast, clutter. Imperative, '
    'specific, about size, style or color. Never change the wording of the copy, never move the layout, never remove required text.]'
)


def eyes_system(refine: bool = False) -> str:
    """The eyes' report. The improvement list costs ~3 s more, so only the Lab's refinement asks for it."""
    return ("You are a senior art director inspecting a finished ad image. Reply with JSON only, no prose:\n"
            + _EYES_FIELDS + (_IMPROVEMENTS if refine else "") + "}")


EYES_SYSTEM = eyes_system()
EDIT_FIXES = {
    "text_rendering": "TEXT: replace the wrong text so each string reads exactly as listed below, same position, size and style.",
    "text_mismatch": "TEXT: replace the wrong text so each string reads exactly as listed below, same position, size and style.",
    "logo_redrawn": "LOGO: remove every drawn logo, wordmark or brand mark; leave that area as clean background (the official logo is applied afterwards).",
    "cropped_content": "MARGIN: move or shrink the elements cut by the frame edge so they sit fully inside an 8% safe margin; extend the background to fill.",
    "cropped": "MARGIN: move or shrink the elements cut by the frame edge so they sit fully inside an 8% safe margin; extend the background to fill.",
    "margin": "MARGIN: bring the elements listed below inside the 8% safe margin.",
    "invented_data": "REMOVE every number, price, date or data line that is not in the copy; screens show only abstract interface shapes.",
    "stray_text": "REMOVE every word, letter, number, button and logo painted in the picture; fill those areas with the surrounding background.",
    "identity_changed": "IDENTITY: restore the product or person to match the supplied reference exactly.",
    "reference_ignored": "REFERENCE: bring the supplied reference into the piece according to its role.",
    "forbidden": "REMOVE the element the brand forbids and fill the area with the surrounding background.",
    "low_score": "CLEAN UP: remove clutter and keep one clear focal point.",
}


def eyes_instruction(brand_name: str, logo_mode: str = "none", has_cta: bool = False) -> str:
    """What this piece is supposed to have, so the eyes neither flag the official logo nor ask for a CTA or logo
    that the briefing does not include."""
    parts = [f"Inspect this ad for the brand {brand_name}." if brand_name else "Inspect this ad."]
    if logo_mode != "none" and brand_name:
        parts.append(f"Its official {brand_name} logo is expected: count it in `logo` but never list it in `unrequested_elements`.")
    elif logo_mode == "none":
        parts.append("This piece has no logo by design: do not suggest adding one.")
    parts.append("It has a CTA button." if has_cta else "This piece has no CTA button by design: do not suggest adding one.")
    return " ".join(parts)


def _is_brand_mark(item: str, brand_name: str) -> bool:
    text = str(item or "").casefold()
    return bool(brand_name) and brand_name.casefold() in text and any(word in text for word in ("logo", "mark", "wordmark", "marca"))


def invented_numbers(observation: dict, allowed_text: str) -> list[str]:
    """Visible numbers (prices, kWh, dates on a phone screen) that the request never wrote."""
    allowed = {re.sub(r"[.,]", "", item) for item in _NUMBER.findall(allowed_text or "")}
    found = []
    for line in observation.get("visible_text") or []:
        for number in _NUMBER.findall(str(line)):
            if re.sub(r"[.,]", "", number) not in allowed:
                found.append(str(line))
                break
    return found


def stray_text(observation: dict, required_text: list[str], brand_name: str = "") -> list[str]:
    """Words in the picture that the Studio did not typeset (the model painted copy on a text-free piece)."""
    from ..creative_lab.evaluation import _letters
    known = _letters(" ".join([*required_text, brand_name]))
    brand_tokens = {token for token in _letters(brand_name).split() if len(token) >= 3}
    stray = []
    for line in observation.get("visible_text") or []:
        letters = _letters(str(line))
        if len(letters.replace(" ", "")) < 3 or letters in known:
            continue
        # The official logo's own wordmark ("CEMIG ATENDE", "centralcomm.media") is not stray copy.
        if len(letters.split()) <= 3 and any(token in letters.replace(" ", "") for token in brand_tokens):
            continue
        stray.append(str(line))
    return stray


def code_placed(piece: dict | None) -> set[str]:
    """Kinds the Studio draws itself, inside the safe area by construction: never re-measured by the eyes."""
    piece = piece or {}
    kinds = {"headline", "text", "cta"} if piece.get("text_free") else set()
    return kinds | ({"logo"} if piece.get("logo_mode") == "composed" else set())


def margin_violations(observation: dict, ignore: set[str] | None = None) -> list[str]:
    """Text, CTA and logo boxes that sit closer than MARGIN_LIMIT percent to an edge."""
    found = []
    kinds = MARGIN_KINDS - (ignore or set())
    for item in observation.get("boxes") or []:
        if not isinstance(item, dict) or str(item.get("kind") or "") not in kinds:
            continue
        try:
            left, top, right, bottom = (float(value) for value in item.get("box") or [])
        except (TypeError, ValueError):
            continue
        sides = [side for side, near in (("left", left < MARGIN_LIMIT), ("top", top < MARGIN_LIMIT),
                                         ("right", right > 100 - MARGIN_LIMIT), ("bottom", bottom > 100 - MARGIN_LIMIT)) if near]
        if sides:
            found.append(f"{item.get('label') or item.get('kind')} ({', '.join(sides)})")
    return found


SAFE_MARGIN = 8.0


def reframe_factor(observation: dict) -> float | None:
    """How much to shrink the picture so every text, CTA and logo box clears the 8% safe margin (None: nothing to do)."""
    factor = 1.0
    for item in observation.get("boxes") or []:
        if not isinstance(item, dict) or str(item.get("kind") or "") not in MARGIN_KINDS:
            continue
        try:
            left, top, right, bottom = (float(value) for value in item.get("box") or [])
        except (TypeError, ValueError):
            continue
        for edge in (left, top, 100 - right, 100 - bottom):
            if edge < SAFE_MARGIN:
                factor = min(factor, (50 - SAFE_MARGIN) / (50 - max(0.0, edge)))
    return None if factor >= 0.999 else max(0.8, round(factor - 0.01, 3))


def reframe_prompt(aspect_ratio: str = "") -> str:
    return ("OUTPAINT THE BORDER. The first image is a finished ad scaled down and centred on a plain border band. Fill ONLY "
            "that border so the background continues seamlessly (same colors, gradients, textures, light and scene). Do not "
            "change, move, redraw or add anything inside the central picture; put no text, logo, button or object in the border."
            + (f" Keep the same canvas and aspect ratio ({aspect_ratio})." if aspect_ratio else ""))


def max_attempts(modeling) -> int:
    return max(1, int(getattr(modeling, "review_attempts", 0) or MAX_ATTEMPTS))


def wants_another(verdict: dict, modeling) -> bool:
    """Another version when the reviewer rejects, or, while refining, until the score reaches the target."""
    if not verdict.get("reviewed"):
        return False
    if not verdict.get("approved"):
        return True
    target = getattr(modeling, "refine_target", None)
    return bool(target) and (verdict.get("score") or 0) < target


def attempt_entry(version: int, verdict: dict, source: str) -> dict:
    observation = verdict.get("observation") or {}
    return {"version": version, "source": source, "score": verdict.get("score"), "approved": verdict.get("approved"),
            "reason": verdict.get("reason") or "", "margin": verdict.get("margin") or [],
            "improvements": list(observation.get("improvements") or [])[:4], "seconds": verdict.get("seconds")}


def enabled(modeling) -> bool:
    return ENABLED and bool(getattr(modeling, "auto_review", False))


def _jpeg_data_url(encoded: str, side: int = 768) -> tuple[Image.Image, str]:
    image = Image.open(io.BytesIO(base64.b64decode(encoded)))
    image.load()
    small = image.convert("RGB")
    small.thumbnail((side, side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    small.save(out, "JPEG", quality=85)
    return image, "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def judge(scores: dict, observation: dict, measurements: dict, required_text: list[str], piece: dict | None = None,
          allowed_text: str | None = None) -> dict:
    """Pure verdict from the evaluation: ``approved`` plus the objective reason when rejected."""
    overall = scores.get("overall")
    failure = (scores.get("primary_failure") or {}).get("choice") or ""
    confidence = (scores.get("primary_failure") or {}).get("confidence") or 0
    reason = ""
    visible = observation.get("visible_text")
    text = (measurements or {}).get("text") or {}
    # Letters, accents and digits must match; a period the observer did not transcribe is not a rejection.
    if required_text and visible and (text.get("letters_exact") if "letters_exact" in text else text.get("all_exact")) is False:
        reason = "text_mismatch"
    elif failure in REJECT_FAILURES and confidence >= CONFIDENCE:
        reason = failure
    elif (scores.get("cropped") or 0) >= CONFIDENCE:
        reason = "cropped"
    elif margin_violations(observation, code_placed(piece)):
        reason = "margin"
    elif allowed_text is not None and invented_numbers(observation, allowed_text + " " + " ".join(required_text)):
        reason = "invented_data"
    elif (piece or {}).get("text_free") and required_text and stray_text(observation, required_text, (piece or {}).get("brand_name", "")):
        # Words only: the eyes' boxes are too rough to tell our text from the model's by position (measured: false
        # positives in 2 of 6 clean pieces).
        reason = "stray_text"
    elif (scores.get("forbidden_present") or 0) >= CONFIDENCE:
        reason = "forbidden"
    elif MIN_SCORE and overall is not None and overall < MIN_SCORE:
        reason = "low_score"
    margin = margin_violations(observation, code_placed(piece))
    # A broken safe margin costs 10 points, so a refined version that fixes it wins the comparison.
    score = None if overall is None else max(0, overall - (10 if margin else 0))
    return {"approved": not reason, "score": score, "failure": reason or (failure if failure != "none" else ""),
            "reason": reason, "reason_text": REASONS.get(reason, ""), "margin": margin}


def review(*, image_b64: str, prompt: str, required_text: list[str], palette: list[str], brand_name: str = "",
           forbidden: list[str] | None = None, logo_mode: str = "none", has_cta: bool = False, refine: bool = False,
           text_free: bool = False, allowed_text: str | None = None) -> dict:
    """Review one finished image. Never raises: any problem returns ``reviewed: False`` (deliver as is)."""
    started = time.monotonic()
    try:
        from ..creative_lab import evaluation
        from ..services.openrouter_service import chat_completion, message_text
        from ..services.typesafe_service import system_one

        image, data_url = _jpeg_data_url(image_b64)
        spec = {"task": "generate", "objective": "paid social ad", "instruction": prompt[:1800],
                "must_include_text": required_text, "aspect_ratio": f"{image.width}:{image.height}"}
        measurements = {"size": [image.width, image.height], "palette": evaluation.palette_check(image, palette)}
        result = chat_completion(
            [{"role": "system", "content": eyes_system(refine)},
             {"role": "user", "content": [{"type": "text", "text": eyes_instruction(brand_name, logo_mode, has_cta)},
                                          {"type": "image_url", "image_url": {"url": data_url}}]}],
            model=evaluation.OBSERVER_MODEL, max_tokens=4000, response_format={"type": "json_object"},
            timeout=OBSERVER_TIMEOUT, provider="openrouter")
        text = message_text(result.get("message") or {})
        observation = json.loads(text[text.find("{"):text.rfind("}") + 1])
        # The official logo is never an "added element", even when the eyes list it as one.
        observation["unrequested_elements"] = [item for item in observation.get("unrequested_elements") or []
                                               if not _is_brand_mark(item, brand_name)]
        measurements["text"] = evaluation.text_check(required_text, observation.get("visible_text") or [])
        state = {
            "brief": {"task": "generate", "instruction": spec["instruction"], "must_include_text": required_text,
                      "aspect_ratio": spec["aspect_ratio"]},
            "brand": {"name": brand_name, "palette": palette, "forbidden_elements": forbidden or []} if (brand_name or palette) else None,
            "model_prompt": prompt[:3000], "observation": observation,
            "measurements": {"text": measurements["text"], "palette": measurements["palette"]},
        }
        questions = evaluation._questions(spec, bool(brand_name or palette), False)
        for key in ("prompt_drift", "completeness"):
            questions.pop(key, None)
        answers = system_one(state, questions, timeout=TYPESAFE_TIMEOUT, attempts=1)["answers"]
        scores = evaluation._summarize(answers)
        piece = {"palette": list(palette or [])[:5], "logo_mode": logo_mode, "has_cta": bool(has_cta),
                 "brand_name": brand_name, "text_free": bool(text_free)}
        # Numbers are checked against everything the request wrote (the raw briefing too), not only the edited brief.
        verdict = judge(scores, observation, measurements, required_text, piece,
                        allowed_text=prompt + " " + (allowed_text or ""))
        verdict.update({"reviewed": True, "seconds": round(time.monotonic() - started, 1), "observation": observation,
                        "required_text": list(required_text), "piece": piece})
        return verdict
    except Exception:
        logger.warning("Studio auto review unavailable; delivering without it", exc_info=True)
        return {"reviewed": False, "approved": True, "score": None, "failure": "", "reason": "", "reason_text": "",
                "seconds": round(time.monotonic() - started, 1)}


def correction(verdict: dict) -> str:
    return CORRECTIONS.get(verdict.get("reason") or "", CORRECTIONS["low_score"])


def edit_prompt(verdict: dict, aspect_ratio: str = "") -> str:
    """The editor's instruction for the next version: fix what the reviewer found on the best image so far and
    apply its top improvements, keeping everything else (including every piece of text) as it is."""
    reason = verdict.get("reason") or ""
    observation = verdict.get("observation") or {}
    lines = [
        "EDIT THE FIRST IMAGE. It is a finished ad being refined. Keep the composition, people, product, colors, "
        "lighting, typography style and every correct element as they are. Any other image supplied is a reference only.",
    ]
    piece = verdict.get("piece") or {}
    if reason and not (piece.get("text_free") and reason in {"text_rendering", "text_mismatch"}):
        lines.append("FIX FIRST: " + EDIT_FIXES.get(reason, EDIT_FIXES["low_score"]))
    if piece.get("text_free"):
        # The base is the text-free picture; headline and CTA are typeset by the Studio afterwards.
        lines.append("TEXT-FREE IMAGE: the image must contain no words, letters, numbers, buttons or logos.")
    required = [item for item in verdict.get("required_text") or [] if item]
    if reason in {"text_rendering", "text_mismatch"} and required and not piece.get("text_free"):
        seen = [item for item in observation.get("visible_text") or [] if item]
        if seen:
            lines.append("The image currently reads: " + " / ".join(f'"{item}"' for item in seen[:8]) + ".")
        lines.append("These strings must read exactly (letter by letter, accents included):\n" + "\n".join(f'"{item}"' for item in required))
    margin = verdict.get("margin") or []
    if margin:
        lines.append("Too close to the edge now: " + "; ".join(margin[:5]) + ". Move them inward so every text, button and "
                     "logo sits at least 8% from every edge; scale that group down slightly if needed and extend the background.")
    if reason == "invented_data":
        invented = [str(item) for item in observation.get("visible_text") or [] if _NUMBER.search(str(item))]
        if invented:
            lines.append("Invented data visible now: " + " / ".join(f'"{item}"' for item in invented[:5]) + ".")
    if reason in {"cropped", "cropped_content"} and observation.get("cut_off"):
        lines.append("Cut by the edge now: " + "; ".join(str(item) for item in observation["cut_off"][:5]) + ".")
    palette = [item for item in piece.get("palette") or [] if item]
    if palette:
        lines.append("BRAND COLORS: keep the official colors " + ", ".join(palette) + " clearly visible in the graphic "
                     "elements (background fields, headline accent" + (", CTA button" if piece.get("has_cta") else "") + ").")
    if piece.get("logo_mode") == "composed" or piece.get("text_free"):
        lines.append("LOGO: draw no logo or brand mark; the official logo is applied afterwards, keep its corner calm.")
    elif piece.get("logo_mode") == "in_image":
        lines.append("LOGO: keep the official logo exactly as it is (shape, letters, colors), fully inside the safe margin.")
    else:
        lines.append("There is no logo in this piece: do not add any logo, wordmark or brand mark.")
    if piece and (not piece.get("has_cta") or piece.get("text_free")):
        lines.append("Do not add any button or call to action to the image.")
    improvements = [str(item) for item in observation.get("improvements") or [] if item]
    if piece.get("text_free"):
        improvements = [item for item in improvements if not re.search(r"\b(text|headline|copy|font|cta|button|botão|t[íi]tulo)\b", item, re.I)]
    if piece and not piece.get("has_cta"):
        improvements = [item for item in improvements if not re.search(r"\b(cta|button|botão|call to action)\b", item, re.I)]
    if piece.get("logo_mode", "none") == "none" and piece:
        improvements = [item for item in improvements if not re.search(r"\blogo\b", item, re.I)]
    improvements = improvements[:3]
    if improvements:
        lines.append("THEN IMPROVE, in this order:\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(improvements, 1)))
    lines.append("Do not delete, add or reword any text other than what is listed above; every other text stays exactly as it is.")
    if aspect_ratio:
        lines.append(f"Keep the same canvas and aspect ratio ({aspect_ratio}).")
    return "\n".join(lines)


def prefer_second(first: dict, second: dict) -> bool:
    """Whether ``second`` becomes the version to deliver: approved beats rejected, then the higher score
    (a tie goes to the newer version); an unreviewed version never replaces a reviewed one."""
    if not second.get("reviewed"):
        return not first.get("reviewed")
    if not first.get("reviewed"):
        return True
    if bool(second.get("approved")) != bool(first.get("approved")):
        return bool(second.get("approved"))
    a, b = first.get("score"), second.get("score")
    if b is None:
        return False
    return a is None or b >= a


# -- two passes: a cheap structure draft, our partial review, then the finishing edit --------------------------

DRAFT_HEADER = (
    "DRAFT PASS (structure only): compose the scene, the main subject and where it sits, the setting, the light and "
    "the base palette. Do NOT render any text, letters, numbers or buttons and no small details; keep the text and "
    "logo areas calm. A second pass finishes the piece on top of this draft."
)


def finish_prompt(partial: dict | None, aspect_ratio: str = "") -> str:
    """The second call: edit the approved structure draft into the finished piece, with the partial review's fixes."""
    lines = ["EDIT THE FIRST IMAGE. It is the structure draft of this ad. Keep its composition, the subject and its "
             "placement, the setting, the light and the palette; finish it at full quality and complete everything the "
             "draft left out, following the full instructions below. Any other image supplied is a reference only."]
    verdict = partial or {}
    observation = verdict.get("observation") or {}
    fixes = []
    if verdict.get("reason") and verdict["reason"] not in {"text_rendering", "text_mismatch"}:
        fixes.append(EDIT_FIXES.get(verdict["reason"], EDIT_FIXES["low_score"]))
    if verdict.get("margin"):
        fixes.append("Keep every text, button and logo at least 8% from every edge: " + "; ".join(verdict["margin"][:4]) + ".")
    if observation.get("cut_off"):
        fixes.append("Bring fully inside the frame: " + "; ".join(str(item) for item in observation["cut_off"][:4]) + ".")
    if observation.get("unrequested_elements"):
        fixes.append("Remove what the brief did not ask for: " + "; ".join(str(item) for item in observation["unrequested_elements"][:4]) + ".")
    fixes += [str(item) for item in (observation.get("improvements") or [])[:3]]
    if fixes:
        lines.append("FIX WHILE FINISHING (found by the review of the draft):\n" + "\n".join(f"- {item}" for item in fixes))
    if aspect_ratio:
        lines.append(f"Keep the same canvas and aspect ratio ({aspect_ratio}).")
    return "\n".join(lines)


def variation_prompt(aspect_ratio: str = "") -> str:
    """Another variation made from a finished piece: same campaign, a clearly different take."""
    return ("VARIATION OF THE FIRST IMAGE. It is a finished ad of this campaign. Create a clearly different take of it: "
            "change the camera angle, the pose or the arrangement of the scene, while keeping the brand, the palette, the "
            "layout zones, the subject's identity and every piece of copy exactly as written. Any other image supplied is "
            "a reference only." + (f" Keep the canvas and aspect ratio ({aspect_ratio})." if aspect_ratio else ""))
