"""Revisor automático do Studio: olha a imagem pronta e diz se ela pode ser entregue.

Usa o mesmo método do Lab: medidas por código (texto exato, paleta), um observador de visão e perguntas
tipadas ao TypeSafe. Só falhas objetivas rejeitam a imagem. Se o revisor falhar, a imagem é entregue como
está (fail-open): o revisor nunca bloqueia o usuário.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import time

from PIL import Image

logger = logging.getLogger(__name__)

ENABLED = os.getenv("STUDIO_AUTO_REVIEW", "1").strip().lower() not in {"0", "false", "off", "no"}
MIN_SCORE = int(os.getenv("STUDIO_AUTO_REVIEW_MIN_SCORE", "0") or 0)
# Segunda versão só começa se a primeira ainda estiver dentro deste orçamento (segundos desde o início do pedido).
RETRY_BUDGET_SECONDS = float(os.getenv("STUDIO_AUTO_REVIEW_RETRY_BUDGET", "150") or 150)
OBSERVER_TIMEOUT = 45
TYPESAFE_TIMEOUT = 30
CONFIDENCE = 0.6
# Falhas que o usuário percebe de imediato e que uma nova tentativa costuma resolver.
REJECT_FAILURES = {"text_rendering", "logo_redrawn", "cropped_content", "identity_changed", "reference_ignored"}
REASONS = {
    "text_rendering": "o texto saiu diferente do pedido",
    "logo_redrawn": "o logo foi redesenhado",
    "cropped_content": "algo importante foi cortado na borda",
    "identity_changed": "o produto ou a pessoa mudou em relação à referência",
    "reference_ignored": "a referência enviada foi ignorada",
    "text_mismatch": "o texto saiu diferente do pedido",
    "cropped": "algo importante foi cortado na borda",
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
    "forbidden": "REVIEW FIX: the previous attempt showed an element the brand forbids. Remove it and keep the scene clean.",
    "low_score": "REVIEW FIX: the previous attempt was weak. Use one clear focal point, a clean layout and the brand colors.",
}


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


def judge(scores: dict, observation: dict, measurements: dict, required_text: list[str]) -> dict:
    """Pure verdict from the evaluation: ``approved`` plus the objective reason when rejected."""
    overall = scores.get("overall")
    failure = (scores.get("primary_failure") or {}).get("choice") or ""
    confidence = (scores.get("primary_failure") or {}).get("confidence") or 0
    reason = ""
    visible = observation.get("visible_text")
    text = (measurements or {}).get("text") or {}
    if required_text and visible and text.get("all_exact") is False:
        reason = "text_mismatch"
    elif failure in REJECT_FAILURES and confidence >= CONFIDENCE:
        reason = failure
    elif (scores.get("cropped") or 0) >= CONFIDENCE:
        reason = "cropped"
    elif (scores.get("forbidden_present") or 0) >= CONFIDENCE:
        reason = "forbidden"
    elif MIN_SCORE and overall is not None and overall < MIN_SCORE:
        reason = "low_score"
    return {"approved": not reason, "score": overall, "failure": reason or (failure if failure != "none" else ""),
            "reason": reason, "reason_text": REASONS.get(reason, "")}


def review(*, image_b64: str, prompt: str, required_text: list[str], palette: list[str], brand_name: str = "",
           forbidden: list[str] | None = None) -> dict:
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
            [{"role": "system", "content": evaluation.observer_system()},
             {"role": "user", "content": [{"type": "text", "text": evaluation.observer_instruction(spec, [])},
                                          {"type": "image_url", "image_url": {"url": data_url}}]}],
            model=evaluation.OBSERVER_MODEL, max_tokens=4000, response_format={"type": "json_object"},
            timeout=OBSERVER_TIMEOUT, provider="openrouter")
        text = message_text(result.get("message") or {})
        observation = json.loads(text[text.find("{"):text.rfind("}") + 1])
        measurements["text"] = evaluation.text_check(required_text, observation.get("visible_text") or [])
        state = {
            "brief": {"task": "generate", "instruction": spec["instruction"], "must_include_text": required_text,
                      "aspect_ratio": spec["aspect_ratio"]},
            "brand": {"name": brand_name, "palette": palette, "forbidden_elements": forbidden or []} if (brand_name or palette) else None,
            "model_prompt": prompt[:3000], "observation": observation,
            "measurements": {"text": measurements["text"], "palette": measurements["palette"]},
        }
        questions = evaluation._questions(spec, bool(brand_name or palette), False)
        questions.pop("prompt_drift", None)
        answers = system_one(state, questions, timeout=TYPESAFE_TIMEOUT, attempts=1)["answers"]
        scores = evaluation._summarize(answers)
        verdict = judge(scores, observation, measurements, required_text)
        verdict.update({"reviewed": True, "seconds": round(time.monotonic() - started, 1)})
        return verdict
    except Exception:
        logger.warning("Studio auto review unavailable; delivering without it", exc_info=True)
        return {"reviewed": False, "approved": True, "score": None, "failure": "", "reason": "", "reason_text": "",
                "seconds": round(time.monotonic() - started, 1)}


def correction(verdict: dict) -> str:
    return CORRECTIONS.get(verdict.get("reason") or "", CORRECTIONS["low_score"])


def prefer_second(first: dict, second: dict) -> bool:
    """Keep the new version unless the reviewer is sure it is worse than the first."""
    if not second.get("reviewed"):
        return True
    if second.get("approved"):
        return True
    a, b = first.get("score"), second.get("score")
    return b is not None and a is not None and b >= a
